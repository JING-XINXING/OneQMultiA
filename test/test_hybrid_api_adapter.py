"""v0.4.0：API 直连与网页失败后的自动降级。"""

from datetime import datetime, timezone

import httpx
import pytest

from oneqmultia.core.dispatcher import dispatch_to_adapters
from oneqmultia.platforms.api_adapter import ApiPlatformAdapter
from oneqmultia.platforms.base import AskResult, AskTiming, BasePlatformAdapter, PlatformRuntimeConfig


def _cfg(**kwargs) -> PlatformRuntimeConfig:
    data = dict(
        id="deepseek",
        display_name="DeepSeek",
        url="https://chat.deepseek.com/",
        timeout_seconds=10,
        selectors={"input_box": "textarea"},
        interaction={},
        adapter_type="generic",
        adapter_module="",
        execution_mode="api_only",
        api_provider="deepseek",
        api_model="deepseek-v4-flash",
    )
    data.update(kwargs)
    return PlatformRuntimeConfig(**data)


def _sse_client() -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        body = (
            'data: {"choices":[{"delta":{"content":"你"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"好"}}],"usage":{"total_tokens":3}}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(200, text=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_api_only_streams_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONEQMULTIA_DEEPSEEK_API_KEY", "test-key")
    adapter = ApiPlatformAdapter(_cfg(), client=_sse_client())
    result = await adapter.ask(None, "你好")
    assert result.status == "success"
    assert result.answer_text == "你好"
    assert result.tokens_count == 3
    assert result.timing.request_sent_at < result.timing.first_token_at <= result.timing.completed_at


class _TimeoutWeb(BasePlatformAdapter):
    async def ask(self, page, question: str, emit=None) -> AskResult:
        timing = AskTiming()
        timing.request_sent_at = datetime.now(timezone.utc)
        timing.completed_at = datetime.now(timezone.utc)
        return AskResult(
            platform_id=self.platform_id,
            platform_name=self.config.display_name,
            platform_url=self.config.url,
            answer_text="",
            status="timeout",
            error_message="selector timeout",
            timing=timing,
        )


@pytest.mark.asyncio
async def test_web_timeout_falls_back_to_api(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _api_ask(self, page, question: str, emit=None) -> AskResult:
        timing = AskTiming()
        timing.request_sent_at = datetime.now(timezone.utc)
        timing.first_token_at = datetime.now(timezone.utc)
        timing.completed_at = datetime.now(timezone.utc)
        return AskResult(
            platform_id=self.platform_id,
            platform_name=self.config.display_name,
            platform_url=self.config.url,
            answer_text="api-fallback",
            status="success",
            error_message="",
            timing=timing,
            tokens_count=2,
        )

    monkeypatch.setattr(ApiPlatformAdapter, "ask", _api_ask)
    cfg = _cfg(execution_mode="web_with_api_fallback")
    adapter = _TimeoutWeb(cfg)

    class _Page:
        url = "https://chat.deepseek.com/a"

        async def goto(self, *_args, **_kwargs) -> None:
            return None

    class _Ctx:
        pages = [_Page()]

        async def new_page(self) -> _Page:
            return _Page()

    results = await dispatch_to_adapters([adapter], "问题", _Ctx())
    assert results[0].status == "success"
    assert results[0].answer_text == "api-fallback"


@pytest.mark.asyncio
async def test_api_only_without_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _api_ask(self, page, question: str, emit=None) -> AskResult:
        timing = AskTiming()
        now = datetime.now(timezone.utc)
        timing.request_sent_at = now
        timing.first_token_at = now
        timing.completed_at = now
        return AskResult(
            platform_id=self.platform_id,
            platform_name="DeepSeek",
            platform_url=self.config.url,
            answer_text="direct",
            status="success",
            error_message="",
            timing=timing,
        )

    monkeypatch.setattr(ApiPlatformAdapter, "ask", _api_ask)
    adapter = _TimeoutWeb(_cfg(execution_mode="api_only"))
    results = await dispatch_to_adapters([adapter], "问题", None)
    assert results[0].status == "success"
    assert results[0].answer_text == "direct"
