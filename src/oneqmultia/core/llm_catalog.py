"""最优答案可用的国内/国际模型目录（OpenAI 兼容 Chat Completions）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from oneqmultia.config.settings import Settings

# 每个厂商：默认网关、Settings 密钥字段、可选模型（id 为官方调用名）
LLM_PROVIDERS: Tuple[Dict[str, Any], ...] = (
    {
        "id": "deepseek",
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "key_attr": "deepseek_api_key",
        "models": (
            {"id": "deepseek-v4-flash", "label": "DeepSeek V4 Flash", "tag": "推荐"},
            {"id": "deepseek-v4-pro", "label": "DeepSeek V4 Pro", "tag": "旗舰"},
        ),
    },
    {
        "id": "kimi",
        "label": "Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "key_attr": "kimi_api_key",
        "models": (
            {"id": "kimi-k2-turbo-preview", "label": "Kimi K2 Turbo", "tag": "推荐"},
            {"id": "moonshot-v1-128k", "label": "Moonshot 128K", "tag": "长文"},
            {"id": "moonshot-v1-32k", "label": "Moonshot 32K", "tag": ""},
        ),
    },
    {
        "id": "qwen",
        "label": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "key_attr": "qwen_api_key",
        "models": (
            {"id": "qwen3.7-plus", "label": "Qwen3.7 Plus", "tag": "推荐"},
            {"id": "qwen3.7-max", "label": "Qwen3.7 Max", "tag": "旗舰"},
            {"id": "qwen-plus", "label": "Qwen Plus", "tag": ""},
            {"id": "qwen-flash", "label": "Qwen Flash", "tag": "高速"},
            {"id": "qwen3-max", "label": "Qwen3 Max", "tag": ""},
        ),
    },
    {
        "id": "glm",
        "label": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "key_attr": "glm_api_key",
        "models": (
            {"id": "glm-5.2", "label": "GLM-5.2", "tag": "旗舰"},
            {"id": "glm-5.1", "label": "GLM-5.1", "tag": ""},
            {"id": "glm-5", "label": "GLM-5", "tag": ""},
            {"id": "glm-4.7", "label": "GLM-4.7", "tag": "推荐"},
            {"id": "glm-4.7-flash", "label": "GLM-4.7 Flash", "tag": "免费"},
        ),
    },
    {
        "id": "minimax",
        "label": "MiniMax",
        "base_url": "https://api.minimaxi.com/v1",
        "key_attr": "minimax_api_key",
        "models": (
            {"id": "MiniMax-M3", "label": "MiniMax M3", "tag": "旗舰"},
            {"id": "MiniMax-M2.7", "label": "MiniMax M2.7", "tag": "推荐"},
            {"id": "MiniMax-M2.7-highspeed", "label": "MiniMax M2.7 高速", "tag": "高速"},
            {"id": "MiniMax-M2.5", "label": "MiniMax M2.5", "tag": ""},
        ),
    },
    {
        "id": "doubao",
        "label": "豆包",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "key_attr": "doubao_api_key",
        "models": (
            {"id": "doubao-seed-1-6-251015", "label": "Doubao Seed 1.6", "tag": "推荐"},
            {"id": "doubao-seed-1-6-thinking-250715", "label": "Doubao Seed 1.6 Thinking", "tag": "推理"},
            {"id": "doubao-seed-1-6-flash-250828", "label": "Doubao Seed 1.6 Flash", "tag": "高速"},
            {"id": "doubao-seed-2-0-pro", "label": "Doubao Seed 2.0 Pro", "tag": "旗舰"},
        ),
    },
    {
        "id": "longcat",
        "label": "LongCat",
        "base_url": "https://api.longcat.chat/openai/v1",
        "key_attr": "longcat_api_key",
        "models": (
            {"id": "LongCat-2.0", "label": "LongCat 2.0", "tag": "旗舰"},
            {"id": "LongCat-Flash-Chat", "label": "LongCat Flash Chat", "tag": "高速"},
        ),
    },
    {
        "id": "mimo",
        "label": "小米 MiMo",
        "base_url": "https://api.xiaomimimo.com/v1",
        "key_attr": "mimo_api_key",
        "models": (
            {"id": "mimo-v2.5-pro", "label": "MiMo V2.5 Pro", "tag": "旗舰"},
            {"id": "mimo-v2.5", "label": "MiMo V2.5", "tag": "推荐"},
        ),
    },
    {
        "id": "openai",
        "label": "OpenAI 兼容",
        "base_url": "https://api.openai.com/v1",
        "key_attr": "llm_api_key",
        "models": (
            {"id": "gpt-4o-mini", "label": "GPT-4o mini", "tag": ""},
        ),
    },
)

# auto 选择已配置 Key 的顺序
_AUTO_ORDER = (
    "deepseek",
    "kimi",
    "qwen",
    "glm",
    "minimax",
    "doubao",
    "longcat",
    "mimo",
    "openai",
)


def provider_by_id(provider_id: str) -> Optional[Dict[str, Any]]:
    """按厂商 id 取目录项。"""
    pid = (provider_id or "").strip().lower()
    for item in LLM_PROVIDERS:
        if item["id"] == pid:
            return item
    return None


def model_in_provider(provider: Dict[str, Any], model_id: str) -> Optional[Dict[str, Any]]:
    """校验模型是否属于该厂商；允许自定义模型 id（不在列表里也可调用）。"""
    mid = (model_id or "").strip()
    if not mid:
        return None
    for model in provider.get("models") or ():
        if model["id"] == mid:
            return model
    return {"id": mid, "label": mid, "tag": "自定义"}


def key_for_provider(settings: Settings, provider: Dict[str, Any]) -> str:
    """读取该厂商 API Key；通用 Key 作为兜底。"""
    attr = str(provider.get("key_attr") or "")
    specific = str(getattr(settings, attr, None) or "").strip() if attr else ""
    if specific:
        return specific
    return str(settings.llm_api_key or "").strip()


def first_configured_provider(settings: Settings) -> Optional[Dict[str, Any]]:
    """按推荐顺序返回第一个已配置 Key 的厂商。"""
    by_id = {item["id"]: item for item in LLM_PROVIDERS}
    for pid in _AUTO_ORDER:
        item = by_id.get(pid)
        if item and key_for_provider(settings, item):
            return item
    return None


def public_catalog(settings: Optional[Settings] = None) -> Dict[str, Any]:
    """前端目录：含是否已配置 Key，不返回密钥本身。"""
    s = settings or Settings()
    providers: List[Dict[str, Any]] = []
    for item in LLM_PROVIDERS:
        configured = bool(key_for_provider(s, item))
        providers.append(
            {
                "id": item["id"],
                "label": item["label"],
                "configured": configured,
                "models": [
                    {"id": m["id"], "label": m["label"], "tag": m.get("tag") or ""}
                    for m in item["models"]
                ],
            }
        )
    auto = first_configured_provider(s)
    default_model = ""
    if auto:
        models = auto.get("models") or ()
        default_model = models[0]["id"] if models else ""
    return {
        "configured": auto is not None,
        "providers": providers,
        "default_provider": auto["id"] if auto else None,
        "default_model": default_model or None,
        "default_label": auto["label"] if auto else None,
    }
