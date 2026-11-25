"""Kimi 专用适配器。"""

from playwright.async_api import Page

from oneqmultia.platforms.generic import GenericAdapter


class KimiAdapter(GenericAdapter):
    """发送前滚到页面底部，让输入区进入可视区域。"""

    async def prepare_page(self, page: Page) -> None:
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except Exception:
            pass

    async def send_question(self, page: Page, question: str) -> None:
        await self.prepare_page(page)
        await super().send_question(page, question)
