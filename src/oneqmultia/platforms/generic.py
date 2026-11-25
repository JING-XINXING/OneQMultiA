"""通用适配器：根据 selectors + interaction 驱动 Playwright。

核心设计：
- input_method=keyboard：Ctrl+A + type()，触发 React/Vue 合成事件
- 发送前记录已有响应数，发送后等待「新增」回答出现，避免复用页面时误读旧回答
- 配置选择器失败时自动尝试通用备用选择器
- 响应文本稳定 2s 后提前退出轮询
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from playwright._impl._errors import TargetClosedError

from oneqmultia.core.page_nav import is_new_answer, should_open_entry_url
from oneqmultia.platforms.base import (
    AskResult,
    AskTiming,
    BasePlatformAdapter,
    PlatformRuntimeConfig,
)
from oneqmultia.platforms.markdown_extract import MARKDOWN_EXTRACT_JS
from oneqmultia.storage.models import PlatformConfigRow

logger = logging.getLogger(__name__)

# 响应文本连续稳定多少次（×0.5s）后视为完成
_STABLE_COUNT_DONE = 4  # 2 秒稳定 → 完成
# 找输入框 / 点击发送：短超时，避免选不到框时把整段 generation timeout 耗完
_INPUT_WAIT_MS = 12000
_ACTION_MS = 12000
_FALLBACK_INPUT_WAIT_MS = 3000

# Super Agent 等站点会长时间停在 Thinking...，不能当作成答
_INCOMPLETE_HINTS = (
    "thinking",
    "思考中",
    "正在思考",
    "正在输入",
    "typing",
    "loading",
)


def _looks_incomplete(text: str) -> bool:
    """占位/思考中文案不计入稳定完成，避免提前结束或假成功。"""
    t = (text or "").strip().lower()
    if not t:
        return True
    return any(h in t for h in _INCOMPLETE_HINTS) and len(t) < 80

# 配置选择器失败时依次尝试的通用输入框选择器
_FALLBACK_INPUT_SELECTORS = [
    ".ql-editor[contenteditable='true']",
    "rich-textarea >>> [contenteditable='true']",
    "textarea[enterkeyhint='enter']",
    "textarea",
    "div[contenteditable='true'][role='textbox']",
    "div[contenteditable='true']",
    "[contenteditable='true']",
]

# 通用响应容器备选（在配置选择器找不到文本时兜底）
_FALLBACK_RESPONSE_SELECTORS = [
    "model-response",
    "[data-message-author-role='assistant']",
    "[class*='markdown']",
    "[class*='message-content']",
    "[class*='chat-message']",
    "[class*='assistant']",
    "[class*='bot-message']",
    "[class*='ai-message']",
    "[class*='receive']",
    "article",
]

# 登录墙/Cookie 条等挡住提问框时尝试关掉
_OVERLAY_BUTTONS = (
    "button:has-text('Accept all')",
    "button:has-text('Accept')",
    "button:has-text('同意')",
    "button:has-text('接受')",
    "button:has-text('关闭')",
    "[aria-label='Close']",
    "[aria-label='关闭']",
)


async def _emit_progress(emit, payload: dict) -> None:
    if emit:
        await emit(payload)


async def _dismiss_overlays(page: Page) -> None:
    """点掉挡住输入框的 Cookie/登录提示，失败忽略。"""
    for sel in _OVERLAY_BUTTONS:
        try:
            btn = page.locator(sel).first
            if await btn.count() and await btn.is_visible():
                await btn.click(timeout=1200)
                await asyncio.sleep(0.2)
        except Exception:
            continue


async def _first_usable(page: Page, sel: str, timeout_ms: int):
    """等到选择器出现后，优先返回可见节点，避免点到隐藏的重复输入框。"""
    loc = page.locator(sel)
    await loc.first.wait_for(state="attached", timeout=timeout_ms)
    try:
        n = min(await loc.count(), 12)
    except Exception:
        n = 1
    for i in range(n):
        item = loc.nth(i)
        try:
            if await item.is_visible():
                return item
        except Exception:
            continue
    return loc.first


async def _find_input_box(page: Page, configured_sel: str, timeout_ms: int):
    """
    先尝试配置选择器（支持 CSS 多选 "sel1, sel2"），
    失败后逐一尝试通用备用，最终抛 PlaywrightTimeoutError。
    """
    await _dismiss_overlays(page)
    try:
        return await _first_usable(page, configured_sel, min(_INPUT_WAIT_MS, timeout_ms))
    except (PlaywrightTimeoutError, TargetClosedError) as e:
        if isinstance(e, TargetClosedError):
            raise  # 页面/上下文已关闭，向上抛由 ask 统一处理
        logger.debug("configured input selector %r not found, trying fallbacks", configured_sel)

    for fallback in _FALLBACK_INPUT_SELECTORS:
        if fallback in configured_sel:
            continue
        try:
            box = await _first_usable(page, fallback, _FALLBACK_INPUT_WAIT_MS)
            logger.info("[%s] 使用备用输入选择器: %r（配置: %r 未找到）",
                        page.url, fallback, configured_sel)
            return box
        except (PlaywrightTimeoutError, TargetClosedError) as e:
            if isinstance(e, TargetClosedError):
                raise
            continue

    raise PlaywrightTimeoutError(
        f"找不到输入框（配置: {configured_sel!r}，备用选择器也未命中）。"
        "请通过 PATCH /api/platforms 更新 selectors.input_box。"
    )


async def _fill_input(page: Page, box, question: str, input_method: str) -> None:
    """
    向输入框注入文本，兼容 React/Vue SPA 合成事件。

    input_method:
      keyboard (推荐) — Ctrl+A + type()，触发完整键盘事件链
      fill              — playwright fill + dispatch input/change
      type              — 同 keyboard（向后兼容）
    """
    # 可见但被遮挡时普通 click 会空等 12s（ChatGPT 近期失败即此）
    try:
        await box.scroll_into_view_if_needed(timeout=3000)
    except Exception:
        pass
    try:
        await box.click(timeout=_ACTION_MS)
    except Exception:
        try:
            await box.click(timeout=3000, force=True)
        except Exception:
            await box.evaluate("el => el.focus()")
    method = (input_method or "keyboard").lower()

    if method in ("keyboard", "type", "insert"):
        # 优先在元素上注入文本，不把窗口拉到前台，避免多平台抢焦点丢字
        inserted = await _insert_text_without_window_focus(box, question)
        if not inserted:
            await box.press("Control+a", timeout=_ACTION_MS)
            await box.press("Backspace", timeout=_ACTION_MS)
            type_ms = max(_ACTION_MS, len(question) * 20 + 5000)
            await box.type(question, delay=15, timeout=type_ms)
    else:
        await box.fill(question)
        await box.evaluate(
            "(el) => {"
            "  el.dispatchEvent(new Event('input', {bubbles:true, cancelable:true}));"
            "  el.dispatchEvent(new Event('change', {bubbles:true, cancelable:true}));"
            "}"
        )

    # 等框架状态更新后再发送
    await asyncio.sleep(0.35)


async def _insert_text_without_window_focus(box, question: str) -> bool:
    """用 DOM focus + insertText / value 写入，不依赖操作系统窗口焦点。"""
    try:
        ok = await box.evaluate(
            """(el, text) => {
                el.focus();
                if (el.isContentEditable) {
                    const sel = window.getSelection();
                    const range = document.createRange();
                    range.selectNodeContents(el);
                    sel.removeAllRanges();
                    sel.addRange(range);
                    const inserted = document.execCommand("insertText", false, text);
                    if (!inserted) el.textContent = text;
                } else {
                    el.value = text;
                }
                el.dispatchEvent(new InputEvent("input", {bubbles: true, data: text, inputType: "insertText"}));
                el.dispatchEvent(new Event("change", {bubbles: true}));
                return true;
            }""",
            question,
        )
        return bool(ok)
    except Exception:
        logger.debug("DOM insertText failed", exc_info=True)
        return False


async def _send_message(page: Page, box, send_sel: str, send_method: str) -> None:
    """
    发送消息：优先配置选择器（跳过 disabled），失败降级到 Enter 键。
    """
    if send_method == "enter":
        await box.press("Enter", timeout=_ACTION_MS)
        return

    if send_sel:
        try:
            enabled_sel = f"{send_sel}:not([disabled]):not([aria-disabled='true'])"
            await page.wait_for_selector(enabled_sel, timeout=_INPUT_WAIT_MS)
            await page.locator(enabled_sel).first.click(timeout=_ACTION_MS)
            return
        except Exception as e:
            logger.debug("send button %r failed (%s), falling back to Enter", send_sel, e)

    await box.press("Enter", timeout=_ACTION_MS)


async def _count_responses(page: Page, response_sel: str) -> int:
    """统计当前页面上响应区域的数量（用于判断新回答是否出现）。"""
    if not response_sel:
        return 0
    try:
        return await page.locator(response_sel).count()
    except Exception:
        return 0


async def _extract_markdown(locator) -> str:
    """把定位到的 DOM 转成 Markdown；失败时退回纯文本。"""
    try:
        md = await locator.evaluate(MARKDOWN_EXTRACT_JS)
        if isinstance(md, str) and md.strip():
            return md.strip()
    except Exception:
        logger.debug("markdown extract failed, fallback to inner_text", exc_info=True)
    try:
        return (await locator.inner_text()).strip()
    except Exception:
        return ""


async def _tail_text(page: Page, sel: str) -> str:
    """读取某选择器最后一条 Markdown/文本，供发送前后对比。"""
    if not sel:
        return ""
    try:
        loc = page.locator(sel)
        n = await loc.count()
        if n <= 0:
            return ""
        return await _extract_markdown(loc.nth(n - 1))
    except Exception:
        return ""


def _mark_first_token(timing: AskTiming) -> None:
    """只在真正出现非思考态新文本时记录一次首字时间。"""
    if timing.first_token_at is None:
        timing.first_token_at = datetime.now(timezone.utc)


async def _get_response_text(
    page: Page,
    response_sel: str,
    pre_count: int,
    pre_last_text: str,
    timeout_seconds: float,
    emit,
    pre_fallback_texts: Optional[dict] = None,
    timing: Optional[AskTiming] = None,
) -> str:
    """
    轮询等待新回答：节点变多，或最后一条相对发送前发生变化。

    - 响应稳定 _STABLE_COUNT_DONE * 0.5s 后提前退出
    - 配置选择器无新文本时，用备用选择器对比发送前快照
    """
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    last_text = ""
    stable_count = 0
    pre_fallback_texts = pre_fallback_texts or {}

    while asyncio.get_event_loop().time() < deadline:
        loc = page.locator(response_sel)
        try:
            curr_count = await loc.count()
            if curr_count > 0:
                txt = await _extract_markdown(loc.nth(curr_count - 1))
                if is_new_answer(curr_count, pre_count, txt, pre_last_text):
                    if txt != last_text:
                        last_text = txt
                        stable_count = 0
                        # 思考占位不算首字，避免 TTFT 记到本地填框时刻
                        if timing is not None and not _looks_incomplete(txt):
                            _mark_first_token(timing)
                        await _emit_progress(emit, {"type": "answer_delta", "preview": txt[:12000]})
                    elif _looks_incomplete(txt):
                        stable_count = 0
                    else:
                        stable_count += 1
                        if stable_count >= _STABLE_COUNT_DONE:
                            logger.debug("响应稳定（%d 次），提前退出", stable_count)
                            break
        except Exception:
            pass
        await asyncio.sleep(0.5)

    if last_text:
        return last_text

    # 配置选择器没捕到新文本：备用选择器按「相对发送前是否变化」判断
    for fallback_sel in _FALLBACK_RESPONSE_SELECTORS:
        if fallback_sel in (response_sel or ""):
            continue
        try:
            txt = await _tail_text(page, fallback_sel)
            pre_txt = pre_fallback_texts.get(fallback_sel, "")
            if txt and txt != pre_txt and not _looks_incomplete(txt):
                logger.info("使用备用响应选择器 %r 捕获到文本", fallback_sel)
                if timing is not None:
                    _mark_first_token(timing)
                await _emit_progress(emit, {"type": "answer_delta", "preview": txt[:12000]})
                return txt
        except Exception:
            continue

    return last_text


class GenericAdapter(BasePlatformAdapter):
    """配置驱动的通用网页聊天适配器。

    ask() 按固定生命周期调用可覆写钩子，专用适配器只需改前置步骤：
    prepare_page → ensure_conversation_mode → locate_input → fill_question
    → submit_question → stream_response。
    """

    def __init__(self, config: PlatformRuntimeConfig) -> None:
        super().__init__(config)
        # 调度器在会话首问时置 True，用于点击 new_chat_button
        self.is_first_in_session: bool = False
        # 提交完成时刻，测试用来断言 TTFT 晚于发送
        self.last_submit_at: Optional[datetime] = None

    async def prepare_page(self, page: Page) -> None:
        """发送前的页面准备。专用适配器覆写此钩子，默认不做额外操作。"""
        return None

    async def ensure_conversation_mode(self, page: Page) -> None:
        """会话首问时点击新对话按钮，避免沿用上一次页面上下文。"""
        if not self.is_first_in_session:
            return
        sel = (self.config.selectors or {}).get("new_chat_button") or ""
        if not sel:
            return
        try:
            btn = page.locator(sel).first
            if await btn.count() and await btn.is_visible():
                await btn.click(timeout=3000)
                await asyncio.sleep(0.2)
        except Exception:
            logger.debug("[%s] 新对话按钮未点击", self.config.id, exc_info=True)

    async def locate_input(self, page: Page):
        """定位输入框；停在首页时先拉回配置的对话入口再试一次。"""
        sel = self.config.selectors or {}
        input_sel = sel.get("input_box") or ""
        timeout_ms = max(1000, self.config.timeout_seconds * 1000)
        try:
            return await _find_input_box(page, input_sel, timeout_ms)
        except PlaywrightTimeoutError:
            if should_open_entry_url(page.url, self.config.url):
                logger.info("[%s] 输入框未找到，导航到对话入口 %s", self.config.id, self.config.url)
                await page.goto(self.config.url, wait_until="domcontentloaded", timeout=timeout_ms)
                return await _find_input_box(page, input_sel, timeout_ms)
            raise

    async def fill_question(self, page: Page, box, question: str) -> None:
        """按 interaction.input_method 写入问题。"""
        input_method = ((self.config.interaction or {}).get("input_method") or "keyboard").lower()
        await _fill_input(page, box, question, input_method)

    async def submit_question(self, page: Page, box) -> None:
        """点击发送或回车。成功调用后记录 last_submit_at。"""
        sel = self.config.selectors or {}
        send_method = ((self.config.interaction or {}).get("send_method") or "click").lower()
        await _send_message(page, box, sel.get("send_button") or "", send_method)
        self.last_submit_at = datetime.now(timezone.utc)

    async def send_question(self, page: Page, question: str) -> None:
        """兼容入口：定位、填充、提交。专用适配器可覆写后再调用 super()。"""
        box = await self.locate_input(page)
        await self.fill_question(page, box, question)
        await self.submit_question(page, box)

    async def stream_response(
        self,
        page: Page,
        emit,
        timing: AskTiming,
        pre_count: int,
        pre_last: str,
        pre_fallback: dict,
    ) -> str:
        """轮询新回答。首个非思考态字符到达时写入 timing.first_token_at。"""
        response_sel = (self.config.selectors or {}).get("response_container") or ""
        timeout_ms = max(1000, self.config.timeout_seconds * 1000)
        if not response_sel:
            await asyncio.sleep(2)
            await _emit_progress(emit, {"type": "answer_delta", "preview": ""})
            return ""
        try:
            await page.wait_for_selector(response_sel, timeout=min(20000, timeout_ms))
        except PlaywrightTimeoutError:
            logger.warning("[%s] 等待响应区域 %r 超时，继续轮询", self.config.id, response_sel)
        return await _get_response_text(
            page,
            response_sel,
            pre_count,
            pre_last,
            self.config.timeout_seconds,
            emit,
            pre_fallback_texts=pre_fallback,
            timing=timing,
        )

    async def ask(self, page: Page, question: str, emit=None) -> AskResult:
        timing = AskTiming()
        # 记录调度开始时间；真正的首字时间在 stream_response 里写入
        timing.request_sent_at = datetime.now(timezone.utc)
        input_sel = (self.config.selectors or {}).get("input_box") or ""
        if not input_sel:
            timing.completed_at = datetime.now(timezone.utc)
            return AskResult(
                platform_id=self.config.id,
                platform_name=self.config.display_name,
                platform_url=self.config.url,
                answer_text="",
                status="error",
                error_message="selectors.input_box 未配置",
                timing=timing,
            )

        try:
            response_sel = (self.config.selectors or {}).get("response_container") or ""
            # 发送前快照，避免复用 Tab 时把上一轮回答当成新回答
            pre_count = await _count_responses(page, response_sel)
            pre_last = await _tail_text(page, response_sel)
            pre_fallback = {sel_name: await _tail_text(page, sel_name) for sel_name in _FALLBACK_RESPONSE_SELECTORS}

            await self.prepare_page(page)
            await self.ensure_conversation_mode(page)
            box = await self.locate_input(page)
            await self.fill_question(page, box, question)
            await self.submit_question(page, box)
            text = await self.stream_response(page, emit, timing, pre_count, pre_last, pre_fallback)

            timing.completed_at = datetime.now(timezone.utc)
            await _emit_progress(emit, {"type": "answer_delta", "preview": (text or "")[:12000]})
            return AskResult(
                platform_id=self.config.id,
                platform_name=self.config.display_name,
                platform_url=self.config.url,
                answer_text=text,
                status="success" if text or not response_sel else "timeout",
                error_message=(
                    "" if text or not response_sel
                    else "未检测到回答文本（响应区域为空或选择器不匹配，请通过 PATCH /api/platforms 更新 response_container）"
                ),
                timing=timing,
            )
        except PlaywrightTimeoutError as e:
            timing.completed_at = datetime.now(timezone.utc)
            return AskResult(
                platform_id=self.config.id,
                platform_name=self.config.display_name,
                platform_url=self.config.url,
                answer_text="",
                status="timeout",
                error_message=str(e),
                timing=timing,
            )
        except Exception as e:
            timing.completed_at = datetime.now(timezone.utc)
            logger.exception("[%s] ask 异常", self.config.id)
            return AskResult(
                platform_id=self.config.id,
                platform_name=self.config.display_name,
                platform_url=self.config.url,
                answer_text="",
                status="error",
                error_message=str(e),
                timing=timing,
            )


def build_adapter(row: PlatformConfigRow) -> BasePlatformAdapter:
    """根据数据库行构造适配器。"""
    cfg = PlatformRuntimeConfig.from_row(row)
    if cfg.adapter_type == "specialized" and cfg.adapter_module:
        return _load_specialized(cfg)
    return GenericAdapter(cfg)


def _load_specialized(cfg: PlatformRuntimeConfig) -> BasePlatformAdapter:
    mod_name, _, cls_name = cfg.adapter_module.partition(":")
    if not mod_name or not cls_name:
        return GenericAdapter(cfg)
    import importlib
    mod = importlib.import_module(mod_name)
    cls = getattr(mod, cls_name)
    return cls(cfg)
