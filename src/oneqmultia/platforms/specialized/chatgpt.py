"""ChatGPT 专用适配器：在通用生命周期上补 ProseMirror 输入区准备。"""

from playwright.async_api import Page

from oneqmultia.platforms.generic import GenericAdapter


class ChatGPTAdapter(GenericAdapter):
    """发送前先点中可见的 composer，避免打进隐藏副本。"""

    async def prepare_page(self, page: Page) -> None:
        # ask() 会调用本钩子；旧的 send_question 覆写因此不再是死代码路径
        for sel in (
            "div#prompt-textarea",
            "#prompt-textarea",
            "div[contenteditable='true'][role='textbox']",
        ):
            try:
                el = await page.wait_for_selector(sel, timeout=3000)
                if el:
                    await el.click()
                    break
            except Exception:
                continue

    async def send_question(self, page: Page, question: str) -> None:
        """保留显式入口：先准备页面，再走通用填充与提交。"""
        await self.prepare_page(page)
        await super().send_question(page, question)
