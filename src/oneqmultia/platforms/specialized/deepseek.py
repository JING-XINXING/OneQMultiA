"""DeepSeek 专用适配器。"""

from playwright.async_api import Page

from oneqmultia.platforms.generic import GenericAdapter


class DeepSeekAdapter(GenericAdapter):
    """DeepSeek 聊天页：发送前确保 textarea 可见。"""

    async def send_question(self, page: Page, question: str) -> None:
        try:
            ta = await page.wait_for_selector("textarea", timeout=5000)
            if ta:
                await ta.scroll_into_view_if_needed()
        except Exception:
            pass
        await super().send_question(page, question)
