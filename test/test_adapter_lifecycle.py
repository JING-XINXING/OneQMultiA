"""v0.3.0：适配器生命周期钩子、真实 TTFT、会话首问新对话。"""

from datetime import datetime

import pytest

from oneqmultia.platforms.base import PlatformRuntimeConfig
from oneqmultia.platforms.specialized.chatgpt import ChatGPTAdapter
from oneqmultia.platforms.specialized.deepseek import DeepSeekAdapter
from oneqmultia.platforms.specialized.kimi import KimiAdapter


class _Node:
    """同时扮演 Locator 与 ElementHandle 的最小假页面节点。"""

    def __init__(self, page: "FakePage", selector: str) -> None:
        self.page = page
        self.selector = selector

    @property
    def first(self) -> "_Node":
        # Playwright 的 locator.first 是属性，不是方法
        return self

    def nth(self, _index: int) -> "_Node":
        return self

    async def wait_for(self, **_kwargs) -> None:
        return None

    async def count(self) -> int:
        return 1

    async def is_visible(self) -> bool:
        return True

    async def scroll_into_view_if_needed(self, **_kwargs) -> None:
        return None

    async def click(self, **_kwargs) -> None:
        self.page.clicks.append(self.selector)
        if "send" in self.selector.lower():
            self.page.generation += 1

    async def press(self, key: str, **_kwargs) -> None:
        self.page.presses.append(key)

    async def type(self, text: str, **_kwargs) -> None:
        self.page.typed.append(text)

    async def fill(self, text: str) -> None:
        self.page.typed.append(text)

    async def evaluate(self, *_args, **_kwargs) -> None:
        # 返回空，让填充逻辑退回键盘路径，便于断言 type 被调用
        return None

    async def inner_text(self) -> str:
        return self.page.text_for(self.selector)


class FakePage:
    """按轮次吐出思考态再吐出正式回答的假页面。"""

    def __init__(self, url: str) -> None:
        self.url = url
        self.clicks: list[str] = []
        self.presses: list[str] = []
        self.typed: list[str] = []
        self.generation = 0
        self._reads: dict[int, int] = {}

    def locator(self, selector: str) -> _Node:
        return _Node(self, selector)

    async def wait_for_selector(self, selector: str, timeout: int = 0):
        self.clicks.append(f"wait:{selector}")
        return self

    async def click(self, **_kwargs) -> None:
        self.clicks.append("element.click")

    async def scroll_into_view_if_needed(self) -> None:
        return None

    async def evaluate(self, script, *_args) -> None:
        self.clicks.append(f"eval:{str(script)[:40]}")
        return None

    async def goto(self, url: str, **_kwargs) -> None:
        self.url = url

    def text_for(self, selector: str) -> str:
        if "assistant" not in selector and "markdown" not in selector and "response" not in selector:
            return ""
        gen = self.generation
        self._reads[gen] = self._reads.get(gen, 0) + 1
        if self._reads[gen] < 2:
            return "Thinking..."
        return f"正式回答第{gen}轮。" + ("内容" * 30)


def _config(adapter_name: str) -> PlatformRuntimeConfig:
    return PlatformRuntimeConfig(
        id=adapter_name,
        display_name=adapter_name,
        url="https://chatgpt.com/",
        timeout_seconds=8,
        selectors={
            "input_box": "textarea",
            "send_button": "button[data-testid='send-button']",
            "response_container": "[data-message-author-role='assistant'] .markdown",
            "new_chat_button": "button.new-chat",
        },
        interaction={"input_method": "keyboard", "send_method": "click"},
        adapter_type="specialized",
        adapter_module="",
    )


@pytest.mark.asyncio
async def test_specialized_prepare_hooks_run_inside_ask(monkeypatch: pytest.MonkeyPatch) -> None:
    """三个专用适配器的 prepare_page 必须由 ask() 调用到。"""
    called: list[str] = []

    def _wrap(cls):
        original = cls.prepare_page

        async def _spy(self, page) -> None:
            called.append(cls.__name__)
            await original(self, page)

        monkeypatch.setattr(cls, "prepare_page", _spy)

    for cls in (ChatGPTAdapter, DeepSeekAdapter, KimiAdapter):
        _wrap(cls)
        page = FakePage("https://chatgpt.com/c/1")
        adapter = cls(_config(cls.__name__))
        result = await adapter.ask(page, "你好")
        assert result.status == "success"
        assert result.answer_text.startswith("正式回答")

    assert called == ["ChatGPTAdapter", "DeepSeekAdapter", "KimiAdapter"]


@pytest.mark.asyncio
async def test_first_token_is_after_submit_not_fill() -> None:
    """首字时间应晚于提交，并且早于完成时间。"""
    page = FakePage("https://chatgpt.com/c/1")
    adapter = ChatGPTAdapter(_config("chatgpt"))
    result = await adapter.ask(page, "测量首字")
    timing = result.timing
    assert timing.request_sent_at is not None
    assert timing.first_token_at is not None
    assert timing.completed_at is not None
    assert adapter.last_submit_at is not None
    assert timing.request_sent_at <= adapter.last_submit_at < timing.first_token_at < timing.completed_at
    assert isinstance(timing.first_token_at, datetime)


@pytest.mark.asyncio
async def test_new_chat_only_on_first_question() -> None:
    """会话首问点击新对话，追问保持上下文。"""
    page = FakePage("https://chatgpt.com/c/1")
    adapter = ChatGPTAdapter(_config("chatgpt"))
    adapter.is_first_in_session = True
    await adapter.ask(page, "第一问")
    assert "button.new-chat" in page.clicks

    page.clicks.clear()
    adapter.is_first_in_session = False
    await adapter.ask(page, "第二问")
    assert "button.new-chat" not in page.clicks
