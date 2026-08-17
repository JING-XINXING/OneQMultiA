"""用 OpenAI 兼容接口把多平台回答重写成一篇最优解。"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from oneqmultia.config.settings import Settings
from oneqmultia.core.llm_catalog import (
    first_configured_provider,
    key_for_provider,
    model_in_provider,
    provider_by_id,
    public_catalog,
)

_log = logging.getLogger(__name__)

_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


@dataclass(frozen=True)
class LlmEndpoint:
    """解析后的调用配置，不含完整 Key 的对外展示。"""

    provider: str
    label: str
    base_url: str
    model: str
    api_key: str
    timeout_sec: int
    max_input_chars: int

    def public_status(self) -> Dict[str, Any]:
        catalog = public_catalog()
        return {
            "configured": True,
            "provider": self.provider,
            "label": self.label,
            "model": self.model,
            "providers": catalog["providers"],
            "default_provider": catalog["default_provider"],
            "default_model": catalog["default_model"],
        }


def resolve_llm_endpoint(
    settings: Optional[Settings] = None,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Optional[LlmEndpoint]:
    """按页面选择或 .env 解析可调用的模型；都未配置则返回 None。"""
    s = settings or Settings()
    requested = (provider or s.llm_provider or "auto").strip().lower()
    catalog_item = None
    if requested in {"", "auto"}:
        catalog_item = first_configured_provider(s)
    else:
        catalog_item = provider_by_id(requested)

    if catalog_item is None:
        if (s.llm_base_url or "").strip() and (s.llm_api_key or "").strip():
            return LlmEndpoint(
                provider="openai",
                label="OpenAI 兼容",
                base_url=s.llm_base_url.rstrip("/"),
                model=(model or s.llm_model or "gpt-4o-mini").strip(),
                api_key=s.llm_api_key.strip(),
                timeout_sec=max(15, int(s.llm_timeout_sec or 75)),
                max_input_chars=max(4000, int(s.llm_max_input_chars or 24000)),
            )
        if requested not in {"", "auto"}:
            _log.warning("未知 LLM 提供方 %s", requested)
        return None

    api_key = key_for_provider(s, catalog_item)
    if not api_key:
        return None

    chosen = (model or s.llm_model or "").strip()
    if not chosen:
        models = catalog_item.get("models") or ()
        chosen = models[0]["id"] if models else ""
    meta = model_in_provider(catalog_item, chosen)
    if meta is None:
        return None

    # 通用 llm_base_url 只覆盖 OpenAI 兼容项，避免误改国内厂商网关
    base = str(catalog_item["base_url"]).rstrip("/")
    if catalog_item["id"] == "openai" and (s.llm_base_url or "").strip():
        base = s.llm_base_url.rstrip("/")
    return LlmEndpoint(
        provider=catalog_item["id"],
        label=catalog_item["label"],
        base_url=base,
        model=meta["id"],
        api_key=api_key,
        timeout_sec=max(15, int(s.llm_timeout_sec or 75)),
        max_input_chars=max(4000, int(s.llm_max_input_chars or 24000)),
    )


def llm_public_status(settings: Optional[Settings] = None) -> Dict[str, Any]:
    """前端可展示的配置与目录，不返回 Key。"""
    s = settings or Settings()
    catalog = public_catalog(s)
    endpoint = resolve_llm_endpoint(s)
    if endpoint is None:
        return {
            "configured": False,
            "provider": None,
            "label": None,
            "model": None,
            "providers": catalog["providers"],
            "default_provider": catalog["default_provider"],
            "default_model": catalog["default_model"],
        }
    return endpoint.public_status()


def _trim_answers(answers: List[Dict[str, Any]], budget: int) -> str:
    """按预算截断各平台正文，优先保留靠前的完整段落。"""
    usable = [a for a in answers if (a.get("answer_text") or "").strip()]
    if not usable:
        return ""
    per = max(400, budget // max(1, len(usable)))
    chunks: List[str] = []
    used = 0
    for item in usable:
        name = item.get("platform_name") or item.get("platform_id") or "未知"
        body = str(item.get("answer_text") or "").strip()
        if len(body) > per:
            body = body[: per - 20].rstrip() + "\n…（已截断）"
        block = f"### {name}\n{body}\n"
        if used + len(block) > budget:
            remain = budget - used
            if remain < 80:
                break
            block = block[:remain] + "\n…（已截断）\n"
            chunks.append(block)
            break
        chunks.append(block)
        used += len(block)
    return "\n".join(chunks)


def _extract_json(content: str) -> Dict[str, Any]:
    """从模型输出中取出 JSON 对象。"""
    raw = _JSON_FENCE.sub("", (content or "").strip()).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        data = json.loads(raw[start : end + 1])
        if isinstance(data, dict):
            return data
    raise ValueError("模型未返回可解析的 JSON")


def _chat_complete(endpoint: LlmEndpoint, system: str, user: str) -> str:
    """调用 Chat Completions，只取第一条 assistant 文本。"""
    url = f"{endpoint.base_url}/chat/completions"
    payload = {
        "model": endpoint.model,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Authorization": f"Bearer {endpoint.api_key}",
        "api-key": endpoint.api_key,
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=endpoint.timeout_sec) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("LLM 返回空 choices")
    return str((choices[0].get("message") or {}).get("content") or "").strip()


def synthesize_with_llm(
    question: str,
    answers: List[Dict[str, Any]],
    heuristic: Dict[str, Any],
    settings: Optional[Settings] = None,
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    阅读全部有效回答后重写一篇完整最优解。
    失败返回 None，由调用方回退本地整理。
    """
    endpoint = resolve_llm_endpoint(settings, provider=provider, model=model)
    if endpoint is None:
        return None
    corpus = _trim_answers(answers, endpoint.max_input_chars)
    if not corpus.strip():
        return None

    system = (
        "你是一名严谨的答案编辑。根据用户问题和多个 AI 助手的回答，"
        "重写一份可直接采用的最优答案。要求：\n"
        "1. 使用与问题相同的语言；结构清楚，可含小标题和列表。\n"
        "2. 融合各家正确、互补的信息，去掉重复、错误和抓取失败内容。\n"
        "3. 不要罗列「某模型说…」，写成一篇完整解答。\n"
        "4. 只输出 JSON，不要 Markdown 围栏，字段为："
        '{"text":"完整答案","summary":"一句话摘要",'
        '"key_points":[{"text":"要点","sources":["来源助手名"]}]}'
    )
    user = f"用户问题：\n{question.strip() or '（未提供问题）'}\n\n各助手回答：\n{corpus}"

    try:
        content = _chat_complete(endpoint, system, user)
        parsed = _extract_json(content)
    except Exception as exc:
        _log.warning("LLM 合成失败（%s/%s）：%s", endpoint.provider, endpoint.model, exc)
        return None

    text = str(parsed.get("text") or content).strip()
    if len(text) < 24:
        return None

    key_points: List[Dict[str, Any]] = []
    for item in parsed.get("key_points") or []:
        if not isinstance(item, dict):
            continue
        point = str(item.get("text") or "").strip()
        if not point:
            continue
        sources = item.get("sources") or []
        if not isinstance(sources, list):
            sources = [str(sources)]
        key_points.append(
            {
                "text": point,
                "sources": [str(s) for s in sources if str(s).strip()],
                "consensus": 0.0,
            }
        )

    merged = dict(heuristic)
    merged.update(
        {
            "text": text,
            "summary": str(parsed.get("summary") or heuristic.get("summary") or "")[:200],
            "key_points": key_points or heuristic.get("key_points") or [],
            "method": "llm",
            "provider": endpoint.provider,
            "provider_label": endpoint.label,
            "model": endpoint.model,
            "confidence": max(float(heuristic.get("confidence") or 0.5), 0.78),
            "rationale": (
                f"已用 {endpoint.label} / {endpoint.model} 阅读 "
                f"{len(answers)} 个有效回答后重新撰写。"
            ),
        }
    )
    return merged
