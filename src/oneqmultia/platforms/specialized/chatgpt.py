"""ChatGPT 专用适配器：在 GenericAdapter 基础上增加 ProseMirror 输入优化。"""

from playwright.async_api import Page

from oneqmultia.platforms.generic import GenericAdapter


class ChatGPTAdapter(GenericAdapter):
    """ChatGPT 页面使用 ProseMirror，keyboard 输入已在 GenericAdapter 中处理。"""

    async def send_question(self, page: Page, question: str) -> None:
        # 优先点击输入区获取焦点，再调用通用发送逻辑
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
        await super().send_question(page, question)
