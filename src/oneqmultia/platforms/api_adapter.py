"""官方 API 直连适配器。

支持 OpenAI Chat Completions 兼容流、Anthropic Messages 和 Gemini generateContent。
密钥只从环境配置读取，不写入平台表。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from oneqmultia.core.llm_catalog import key_for_provider, model_in_provider, provider_by_id
from oneqmultia.config.settings import Settings
from oneqmultia.platforms.base import AskResult, AskTiming, BasePlatformAdapter, PlatformRuntimeConfig, ProgressEmit

logger = logging.getLogger(__name__)


class ApiPlatformAdapter(BasePlatformAdapter):
    """不依赖 Chrome 的流式问答适配器。"""

    def __init__(self, config: PlatformRuntimeConfig, client: Optional[httpx.AsyncClient] = None) -> None:
        super().__init__(config)
        self._client = client

    async def ask(self, page, question: str, emit: ProgressEmit = None) -> AskResult:
        """page 对 API 通道无意义，保留签名以符合适配器协议。"""
        del page
        timing = AskTiming()
        timing.request_sent_at = datetime.now(timezone.utc)
        settings = Settings()
        provider = provider_by_id(self.config.api_provider)
        if provider is None:
            return self._fail(timing, "error", "未配置 api_provider，无法走 API 通道")
        api_key = key_for_provider(settings, provider)
        if not api_key:
            return self._fail(timing, "error", f"{provider['label']} 未配置 API Key")
        model = model_in_provider(provider, self.config.api_model or "")
        if model is None:
            models = provider.get("models") or ()
            model = models[0] if models else None
        if model is None:
            return self._fail(timing, "error", "未配置 api_model")

        protocol = _protocol_for(provider["id"])
        try:
            text, tokens = await self._stream(provider, model["id"], api_key, question, timing, emit, protocol)
        except Exception as exc:
            logger.exception("[%s] API 问答失败", self.config.id)
            timing.completed_at = datetime.now(timezone.utc)
            return self._fail(timing, "error", str(exc))

        timing.completed_at = datetime.now(timezone.utc)
        return AskResult(
            platform_id=self.config.id,
            platform_name=self.config.display_name,
            platform_url=self.config.url,
            answer_text=text,
            status="success" if text else "timeout",
            error_message="" if text else "API 未返回文本",
            timing=timing,
            tokens_count=tokens,
        )

    def _fail(self, timing: AskTiming, status: str, message: str) -> AskResult:
        timing.completed_at = timing.completed_at or datetime.now(timezone.utc)
        return AskResult(
            platform_id=self.config.id,
            platform_name=self.config.display_name,
            platform_url=self.config.url,
            answer_text="",
            status=status,
            error_message=message,
            timing=timing,
        )

    async def _stream(
        self,
        provider: dict[str, Any],
        model: str,
        api_key: str,
        question: str,
        timing: AskTiming,
        emit: ProgressEmit,
        protocol: str,
    ) -> tuple[str, Optional[int]]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.config.timeout_seconds)
        try:
            if protocol == "anthropic":
                return await self._stream_anthropic(client, provider, model, api_key, question, timing, emit)
            if protocol == "gemini":
                return await self._stream_gemini(client, provider, model, api_key, question, timing, emit)
            return await self._stream_openai(client, provider, model, api_key, question, timing, emit)
        finally:
            if owns_client:
                await client.aclose()

    async def _stream_openai(self, client, provider, model, api_key, question, timing, emit) -> tuple[str, Optional[int]]:
        url = provider["base_url"].rstrip("/") + "/chat/completions"
        payload = {
            "model": model,
            "stream": True,
            "messages": [{"role": "user", "content": question}],
        }
        headers = {"Authorization": f"Bearer {api_key}"}
        parts: list[str] = []
        tokens: Optional[int] = None
        async with client.stream("POST", url, json=payload, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                delta, usage = _openai_delta(line)
                if usage is not None:
                    tokens = usage
                if not delta:
                    continue
                if timing.first_token_at is None:
                    timing.first_token_at = datetime.now(timezone.utc)
                parts.append(delta)
                if emit:
                    await emit({"type": "answer_delta", "preview": "".join(parts)[:12000]})
        return "".join(parts), tokens

    async def _stream_anthropic(self, client, provider, model, api_key, question, timing, emit) -> tuple[str, Optional[int]]:
        base = provider.get("base_url") or "https://api.anthropic.com"
        url = base.rstrip("/") + "/messages"
        payload = {
            "model": model,
            "max_tokens": 2048,
            "stream": True,
            "messages": [{"role": "user", "content": question}],
        }
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        parts: list[str] = []
        async with client.stream("POST", url, json=payload, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                delta = _anthropic_delta(line)
                if not delta:
                    continue
                if timing.first_token_at is None:
                    timing.first_token_at = datetime.now(timezone.utc)
                parts.append(delta)
                if emit:
                    await emit({"type": "answer_delta", "preview": "".join(parts)[:12000]})
        return "".join(parts), None

    async def _stream_gemini(self, client, provider, model, api_key, question, timing, emit) -> tuple[str, Optional[int]]:
        base = provider.get("base_url") or "https://generativelanguage.googleapis.com/v1beta"
        url = f"{base.rstrip('/')}/models/{model}:streamGenerateContent"
        payload = {"contents": [{"role": "user", "parts": [{"text": question}]}]}
        parts: list[str] = []
        async with client.stream("POST", url, params={"key": api_key, "alt": "sse"}, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                delta = _gemini_delta(line)
                if not delta:
                    continue
                if timing.first_token_at is None:
                    timing.first_token_at = datetime.now(timezone.utc)
                parts.append(delta)
                if emit:
                    await emit({"type": "answer_delta", "preview": "".join(parts)[:12000]})
        return "".join(parts), None


def _protocol_for(provider_id: str) -> str:
    """按厂商选择协议。目录里的国内模型默认走 OpenAI 兼容接口。"""
    if provider_id == "anthropic":
        return "anthropic"
    if provider_id == "gemini":
        return "gemini"
    return "openai"


def _openai_delta(line: str) -> tuple[str, Optional[int]]:
    raw = (line or "").strip()
    if not raw.startswith("data:"):
        return "", None
    data = raw[5:].strip()
    if not data or data == "[DONE]":
        return "", None
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return "", None
    usage = payload.get("usage") or {}
    tokens = usage.get("total_tokens")
    choices = payload.get("choices") or []
    if not choices:
        return "", tokens
    delta = (choices[0].get("delta") or {}).get("content") or ""
    return str(delta), tokens


def _anthropic_delta(line: str) -> str:
    raw = (line or "").strip()
    if not raw.startswith("data:"):
        return ""
    try:
        payload = json.loads(raw[5:].strip())
    except json.JSONDecodeError:
        return ""
    delta = payload.get("delta") or {}
    return str(delta.get("text") or "")


def _gemini_delta(line: str) -> str:
    raw = (line or "").strip()
    if raw.startswith("data:"):
        raw = raw[5:].strip()
    if not raw:
        return ""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    parts = ((candidates[0].get("content") or {}).get("parts") or [])
    return "".join(str(part.get("text") or "") for part in parts)
