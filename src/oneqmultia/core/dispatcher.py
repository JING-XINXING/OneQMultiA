"""并发调度：将同一问题分发到多个适配器，可选进度回调（WebSocket 流式）。

架构说明：
  优先复用 Chrome 中已打开的平台 Tab，避免重新导航和重新登录；
  若找不到已打开的 Tab，则新建 Tab 并导航；问答结束后不关闭，便于核对。
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Set
from urllib.parse import urlparse

from playwright.async_api import BrowserContext, Page
from sqlalchemy.orm import Session

from oneqmultia.config.settings import Settings
from oneqmultia.core.page_nav import should_open_entry_url
from oneqmultia.platforms.base import AskResult, AskTiming, BasePlatformAdapter, ProgressEmit
from oneqmultia.storage.models import PlatformAnswerRow, QAPairRow

logger = logging.getLogger(__name__)

# 进度回调：与 WebSocket 事件结构一致
ProgressFn = Optional[Callable[[Dict[str, Any]], Awaitable[None]]]


@dataclass
class CancelState:
    """提问取消状态：可终止全部，或只停某个平台。"""

    all: bool = False
    platforms: Set[str] = field(default_factory=set)

    def is_cancelled(self, platform_id: str = "") -> bool:
        if self.all:
            return True
        return bool(platform_id) and platform_id in self.platforms

    def cancel(self, platform_id: Optional[str] = None) -> None:
        if platform_id:
            self.platforms.add(platform_id)
        else:
            self.all = True


def _format_dispatch_error(exc: BaseException) -> str:
    """把底层异常转成对用户更可读的中文说明（仍保留原始信息）。"""
    raw = str(exc)
    name = type(exc).__name__
    if "TargetClosed" in name or "Target page" in raw:
        return (
            "页面/Tab 在操作过程中被关闭。"
            "请保持 Chrome 中各平台页面打开，不要在问答期间手动关闭 Tab。"
            f" 原始错误: {raw}"
        )
    if "Timeout" in name or "timeout" in raw.lower():
        return (
            "页面打开超时：请确认本机/VPN 能访问该站点，或设置更大的 ONEQMULTIA_GOTO_TIMEOUT_MS；"
            "无法访问的国内站可在数据库或 PATCH /api/platforms 中禁用。"
            f" 原始错误: {raw}"
        )
    return raw


def _domain_match(url_a: str, url_b: str) -> bool:
    """判断两个 URL 是否属于同一域名（忽略 www. 前缀）。"""
    def _netloc(u: str) -> str:
        try:
            return urlparse(u).netloc.removeprefix("www.")
        except Exception:
            return ""

    a, b = _netloc(url_a), _netloc(url_b)
    if not a or not b:
        return False
    # 精确匹配 或 子域匹配（chat.qwen.ai ↔ qwen.ai）
    return a == b or a.endswith("." + b) or b.endswith("." + a)


async def _get_or_open_page(
    context: BrowserContext, url: str, settings: Settings
) -> Page:
    """
    优先复用 Chrome 中已打开的该平台 Tab；没有则新建并导航。

    问答结束后不关闭页面，方便用户对照原始回答；下次同域提问会复用。
    """
    for page in context.pages:
        try:
            page_url = page.url
        except Exception:
            # Tab 可能已被关闭或不可访问
            continue
        if not page_url or page_url.startswith(("about:", "chrome:", "data:", "blob:")):
            continue
        if _domain_match(page_url, url):
            logger.debug("复用已有 Tab: %s", page_url)
            try:
                # 验证 Tab 仍然可用
                await page.bring_to_front()
                # 停在官网首页时拉回 /chat、/home 等对话入口，避免找不到提问框
                if should_open_entry_url(page_url, url):
                    logger.info("复用 Tab 不在对话入口，导航到 %s", url)
                    await page.goto(
                        url,
                        wait_until=settings.goto_wait_until,
                        timeout=settings.goto_timeout_ms,
                    )
                return page
            except Exception as e:
                logger.warning("Tab %s 不可用（%s），将新建", page_url, e)
                continue

    # 未找到可用 Tab → 新建并导航，用完后仍保留
    page = await context.new_page()
    await page.goto(
        url,
        wait_until=settings.goto_wait_until,
        timeout=settings.goto_timeout_ms,
    )
    return page


def _result_to_event(r: AskResult) -> Dict[str, Any]:
    """将 AskResult 转为可 JSON 序列化的 platform_done 负载（时间用 ISO 字符串）。"""
    return {
        "type": "platform_done",
        "platform_id": r.platform_id,
        "platform_name": r.platform_name,
        "platform_url": r.platform_url,
        "status": r.status,
        "answer_text": r.answer_text,
        "error_message": r.error_message or "",
        "request_sent_at": r.timing.request_sent_at.isoformat() if r.timing.request_sent_at else None,
        "first_token_at": r.timing.first_token_at.isoformat() if r.timing.first_token_at else None,
        "completed_at": r.timing.completed_at.isoformat() if r.timing.completed_at else None,
        "response_duration_ms": r.response_duration_ms,
    }


def _cancelled_result(adapter: BasePlatformAdapter, text: str = "") -> AskResult:
    """用户终止时的占位结果，便于落库与前端展示。"""
    from datetime import datetime, timezone

    t = AskTiming()
    t.request_sent_at = datetime.now(timezone.utc)
    t.completed_at = datetime.now(timezone.utc)
    return AskResult(
        platform_id=adapter.platform_id,
        platform_name=adapter.config.display_name,
        platform_url=adapter.config.url,
        answer_text=text,
        status="cancelled",
        error_message="用户已终止提问",
        timing=t,
    )


async def dispatch_to_adapters(
    adapters: Sequence[BasePlatformAdapter],
    question: str,
    context: Optional[BrowserContext],
    progress: ProgressFn = None,
    cancel_state: Optional[CancelState] = None,
) -> List[AskResult]:
    """
    并发对每个适配器执行问答。
      - context 为 None → 所有平台返回 skipped（无浏览器模式）
      - 有 context → 优先复用已打开 Tab，找不到再新建并导航
      - cancel_state 置位后取消未完成任务，已完成结果保留
    """
    if not adapters:
        return []

    async def _prog(evt: Dict[str, Any]) -> None:
        if progress:
            await progress(evt)

    if context is None:
        results = [
            AskResult(
                platform_id=a.platform_id,
                platform_name=a.config.display_name,
                platform_url=a.config.url,
                answer_text="",
                status="skipped",
                error_message="未连接浏览器：请设置 ONEQMULTIA_CDP_URL 并启动带远程调试的 Chrome",
                timing=AskTiming(),
            )
            for a in adapters
        ]
        for a, r in zip(adapters, results):
            await _prog({"type": "platform_start", "platform_id": a.platform_id, "platform_name": a.config.display_name})
            await _prog(_result_to_event(r))
        return results

    settings = Settings()
    # 信号量限制并发 Tab 数，防止资源耗尽
    sem = asyncio.Semaphore(max(1, settings.max_concurrent_platforms))

    async def _one(adapter: BasePlatformAdapter) -> AskResult:
        async with sem:
            return await _one_inner(adapter)

    async def _run_ask(adapter: BasePlatformAdapter, page: Page, emit: ProgressEmit) -> AskResult:
        """可被 CancelState 打断的 ask；每 0.3s 检查一次。"""
        ask_task = asyncio.create_task(adapter.ask(page, question, emit=emit))
        try:
            while not ask_task.done():
                if cancel_state and cancel_state.is_cancelled(adapter.platform_id):
                    ask_task.cancel()
                    try:
                        await ask_task
                    except asyncio.CancelledError:
                        pass
                    return _cancelled_result(adapter)
                done, _ = await asyncio.wait({ask_task}, timeout=0.3)
                if done:
                    break
            return await ask_task
        except asyncio.CancelledError:
            return _cancelled_result(adapter)

    async def _one_inner(adapter: BasePlatformAdapter) -> AskResult:
        await _prog({
            "type": "platform_start",
            "platform_id": adapter.platform_id,
            "platform_name": adapter.config.display_name,
        })

        if cancel_state and cancel_state.is_cancelled(adapter.platform_id):
            result = _cancelled_result(adapter)
            await _prog(_result_to_event(result))
            return result

        async def child_emit(payload: Dict[str, Any]) -> None:
            await _prog({
                "platform_id": adapter.platform_id,
                "platform_name": adapter.config.display_name,
                **payload,
            })

        try:
            page = await _get_or_open_page(context, adapter.config.url, settings)
            emit: ProgressEmit = child_emit if progress else None
            result = await _run_ask(adapter, page, emit)
            await _prog(_result_to_event(result))
            return result
        except asyncio.CancelledError:
            result = _cancelled_result(adapter)
            await _prog(_result_to_event(result))
            return result
        except Exception as e:
            logger.exception("dispatch failed for %s", adapter.platform_id)
            from datetime import datetime, timezone
            t = AskTiming()
            t.request_sent_at = datetime.now(timezone.utc)
            t.completed_at = datetime.now(timezone.utc)
            result = AskResult(
                platform_id=adapter.platform_id,
                platform_name=adapter.config.display_name,
                platform_url=adapter.config.url,
                answer_text="",
                status="error",
                error_message=_format_dispatch_error(e),
                timing=t,
            )
            await _prog(_result_to_event(result))
            return result

    return await asyncio.gather(*[_one(a) for a in adapters])


def persist_answers(db: Session, qa_pair: QAPairRow, results: Sequence[AskResult]) -> List[PlatformAnswerRow]:
    """将 AskResult 写入 platform_answers 表。"""
    rows: List[PlatformAnswerRow] = []
    for r in results:
        row = PlatformAnswerRow(
            qa_pair_id=qa_pair.id,
            platform_id=r.platform_id,
            platform_name=r.platform_name,
            platform_url=r.platform_url,
            answer_text=r.answer_text,
            request_sent_at=r.timing.request_sent_at,
            first_token_at=r.timing.first_token_at,
            completed_at=r.timing.completed_at,
            response_duration_ms=r.response_duration_ms,
            status=r.status,
            error_message=r.error_message or "",
            tokens_count=r.tokens_count,
        )
        db.add(row)
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows
