"""调度器单元测试（Mock Page）。"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from oneqmultia.core.dispatcher import CancelState, dispatch_to_adapters
from oneqmultia.platforms.base import AskResult, AskTiming, BasePlatformAdapter, PlatformRuntimeConfig


class _FakeAdapter(BasePlatformAdapter):
    async def ask(self, page, question: str, emit=None) -> AskResult:
        t = AskTiming()
        t.request_sent_at = datetime.now(timezone.utc)
        t.completed_at = datetime.now(timezone.utc)
        return AskResult(
            platform_id=self.config.id,
            platform_name=self.config.display_name,
            platform_url=self.config.url,
            answer_text=f"echo:{question}",
            status="success",
            error_message="",
            timing=t,
        )


@pytest.mark.asyncio
async def test_dispatch_no_browser_returns_skipped() -> None:
    cfg = PlatformRuntimeConfig(
        id="x",
        display_name="X",
        url="https://example.com",
        timeout_seconds=5,
        selectors={"input_box": "textarea"},
        interaction={},
        adapter_type="generic",
        adapter_module="",
    )
    adapter = _FakeAdapter(cfg)
    results = await dispatch_to_adapters([adapter], "hi", None)
    assert len(results) == 1
    assert results[0].status == "skipped"


@pytest.mark.asyncio
async def test_dispatch_progress_events() -> None:
    """带 progress 时应收到 platform_start 与 platform_done。"""
    cfg = PlatformRuntimeConfig(
        id="x",
        display_name="X",
        url="https://example.com",
        timeout_seconds=5,
        selectors={"input_box": "textarea"},
        interaction={},
        adapter_type="generic",
        adapter_module="",
    )
    adapter = _FakeAdapter(cfg)
    page = AsyncMock()
    page.goto = AsyncMock()
    page.close = AsyncMock()
    ctx = MagicMock()
    ctx.new_page = AsyncMock(return_value=page)
    events: list = []

    async def prog(evt: dict) -> None:
        events.append(evt)

    await dispatch_to_adapters([adapter], "hi", ctx, progress=prog)
    types = [e.get("type") for e in events]
    assert "platform_start" in types
    assert "platform_done" in types


@pytest.mark.asyncio
async def test_dispatch_with_mock_context() -> None:
    """使用伪造 BrowserContext：验证会调用 adapter.ask。"""
    cfg = PlatformRuntimeConfig(
        id="x",
        display_name="X",
        url="https://example.com",
        timeout_seconds=5,
        selectors={"input_box": "textarea"},
        interaction={},
        adapter_type="generic",
        adapter_module="",
    )
    adapter = _FakeAdapter(cfg)

    page = AsyncMock()
    page.goto = AsyncMock()
    page.close = AsyncMock()

    ctx = MagicMock()
    ctx.new_page = AsyncMock(return_value=page)

    results = await dispatch_to_adapters([adapter], "hi", ctx)
    assert results[0].status == "success"
    assert "echo:hi" in results[0].answer_text
    page.goto.assert_awaited_once()
    # 问答结束后保持助手页打开，供用户核对
    page.close.assert_not_called()


class _SlowAdapter(BasePlatformAdapter):
    async def ask(self, page, question: str, emit=None) -> AskResult:
        await asyncio.sleep(8)
        t = AskTiming()
        t.request_sent_at = datetime.now(timezone.utc)
        t.completed_at = datetime.now(timezone.utc)
        return AskResult(
            platform_id=self.config.id,
            platform_name=self.config.display_name,
            platform_url=self.config.url,
            answer_text="late",
            status="success",
            error_message="",
            timing=t,
        )


@pytest.mark.asyncio
async def test_dispatch_cancel_stops_slow_ask() -> None:
    cfg = PlatformRuntimeConfig(
        id="slow",
        display_name="Slow",
        url="https://example.com",
        timeout_seconds=5,
        selectors={"input_box": "textarea"},
        interaction={},
        adapter_type="generic",
        adapter_module="",
    )
    adapter = _SlowAdapter(cfg)
    page = AsyncMock()
    page.goto = AsyncMock()
    page.close = AsyncMock()
    ctx = MagicMock()
    ctx.new_page = AsyncMock(return_value=page)
    cancel = CancelState()

    async def _cancel_soon() -> None:
        await asyncio.sleep(0.2)
        cancel.cancel()

    results, _ = await asyncio.gather(
        dispatch_to_adapters([adapter], "hi", ctx, cancel_state=cancel),
        _cancel_soon(),
    )
    assert results[0].status == "cancelled"
    page.close.assert_not_called()
