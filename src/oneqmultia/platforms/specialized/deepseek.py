"""DeepSeek 专用适配器。"""

from playwright.async_api import Page

from oneqmultia.platforms.generic import GenericAdapter


class DeepSeekAdapter(GenericAdapter):
    """发送前把 textarea 滚进视口，避免被顶栏挡住。"""

    async def prepare_page(self, page: Page) -> None:
        try:
            ta = await page.wait_for_selector("textarea", timeout=5000)
            if ta:
                await ta.scroll_into_view_if_needed()
        except Exception:
            pass

    async def send_question(self, page: Page, question: str) -> None:
        await self.prepare_page(page)
        await super().send_question(page, question)
