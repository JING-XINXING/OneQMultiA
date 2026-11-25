"""v0.3.0：同域互斥、Page 不交错写入，且常规路径不抢前台。"""

import asyncio
from datetime import datetime, timezone

import pytest

from oneqmultia.core.dispatcher import dispatch_to_adapters
from oneqmultia.platforms.base import AskResult, AskTiming, BasePlatformAdapter, PlatformRuntimeConfig


class _Page:
    def __init__(self, url: str) -> None:
        self.url = url
        self.front_calls = 0

    async def bring_to_front(self) -> None:
        self.front_calls += 1

    async def goto(self, url: str, **_kwargs) -> None:
        self.url = url


class _Context:
    def __init__(self, pages: list[_Page]) -> None:
        self.pages = pages

    async def new_page(self) -> _Page:
        page = _Page("https://fresh.example/new")
        self.pages.append(page)
        return page


class _RecordingAdapter(BasePlatformAdapter):
    def __init__(self, config: PlatformRuntimeConfig, log: list[tuple[str, str, int]]) -> None:
        super().__init__(config)
        self.log = log

    async def ask(self, page, question: str, emit=None) -> AskResult:
        self.log.append(("start", self.platform_id, id(page)))
        await asyncio.sleep(0.06)
        self.log.append(("end", self.platform_id, id(page)))
        timing = AskTiming()
        timing.request_sent_at = datetime.now(timezone.utc)
        timing.completed_at = datetime.now(timezone.utc)
        return AskResult(
            platform_id=self.platform_id,
            platform_name=self.config.display_name,
            platform_url=self.config.url,
            answer_text=question,
            status="success",
            error_message="",
            timing=timing,
        )


def _cfg(pid: str, url: str) -> PlatformRuntimeConfig:
    return PlatformRuntimeConfig(
        id=pid,
        display_name=pid,
        url=url,
        timeout_seconds=5,
        selectors={"input_box": "textarea"},
        interaction={},
        adapter_type="generic",
        adapter_module="",
    )


@pytest.mark.asyncio
async def test_same_domain_page_is_not_interleaved_and_not_focused() -> None:
    """同域两个平台串行写同一 Page；异域可以重叠；都不调用 bring_to_front。"""
    shared = _Page("https://chat.example.com/c/1")
    context = _Context([shared])
    log: list[tuple[str, str, int]] = []
    adapters = [
        _RecordingAdapter(_cfg("same-a", "https://chat.example.com/a"), log),
        _RecordingAdapter(_cfg("same-b", "https://www.chat.example.com/b"), log),
        _RecordingAdapter(_cfg("other-a", "https://alpha.test/chat"), log),
        _RecordingAdapter(_cfg("other-b", "https://beta.test/chat"), log),
        _RecordingAdapter(_cfg("other-c", "https://gamma.test/chat"), log),
    ]
    results = await dispatch_to_adapters(adapters, "hi", context)
    assert {item.status for item in results} == {"success"}
    assert shared.front_calls == 0

    same_events = [item for item in log if item[1] in {"same-a", "same-b"}]
    assert [item[2] for item in same_events] == [id(shared)] * 4
    # 同一 Page 上必须是完整的 start→end，不能交叉
    phases = [item[0] for item in same_events]
    assert phases in (["start", "end", "start", "end"],)
    assert same_events[0][1] != same_events[2][1] or same_events[0][1] == same_events[1][1]

    other = [item for item in log if item[1].startswith("other-")]
    # 三个异域任务的开始都应出现在任一结束之前的某个窗口里，说明没有被全局锁串死
    first_end = min(index for index, item in enumerate(other) if item[0] == "end")
    starts_before_first_end = [item for item in other[:first_end] if item[0] == "start"]
    assert len(starts_before_first_end) >= 2
