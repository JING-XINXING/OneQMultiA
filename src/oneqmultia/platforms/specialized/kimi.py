"""Kimi 专用适配器。"""

from playwright.async_api import Page

from oneqmultia.platforms.generic import GenericAdapter


class KimiAdapter(GenericAdapter):
    """Kimi 页面：发送前滚动到底部输入区。"""

    async def send_question(self, page: Page, question: str) -> None:
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except Exception:
            pass
        await super().send_question(page, question)
