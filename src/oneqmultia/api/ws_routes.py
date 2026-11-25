"""WebSocket：流式推送各平台开始、回答片段、完成与汇总。

断线不取消后台任务。客户端可用 action=subscribe + qa_pair_id 接上同一轮，
避免重连后再次插入提问。
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from playwright.async_api import BrowserContext
from sqlalchemy import func, select

from oneqmultia.core.active_runs import ActiveRun, registry
from oneqmultia.core.aggregator import summarize_results
from oneqmultia.core.dispatcher import CancelState, dispatch_to_adapters, persist_answers
from oneqmultia.core.platform_registry import PlatformRegistry
from oneqmultia.core.session_manager import add_qa_pair, get_session
from oneqmultia.storage.database import SessionLocal
from oneqmultia.storage.models import QAPairRow

logger = logging.getLogger(__name__)

router = APIRouter()


def _browser_context(ws: WebSocket) -> Optional[BrowserContext]:
    return getattr(ws.app.state, "browser_context", None)


async def _read_control(websocket: WebSocket, cancel_state: CancelState) -> None:
    """只处理取消。连接断开时不终止后台问答，方便稍后 subscribe。"""
    try:
        while True:
            msg = await websocket.receive_json()
            if msg.get("action") == "cancel":
                cancel_state.cancel(msg.get("platform_id") or None)
                if cancel_state.all:
                    return
    except WebSocketDisconnect:
        return
    except Exception:
        return


async def _stream_run(websocket: WebSocket, run: ActiveRun, cancel_state: CancelState) -> None:
    """把运行缓冲和后续事件写回当前连接。"""
    queue = await run.subscribe()
    control = asyncio.create_task(_read_control(websocket, cancel_state))
    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            await websocket.send_json(event)
            if event.get("type") in {"complete", "error"}:
                break
    finally:
        run.unsubscribe(queue)
        control.cancel()
        try:
            await control
        except asyncio.CancelledError:
            pass


async def _execute_run(
    run: ActiveRun,
    adapters,
    question: str,
    ctx: Optional[BrowserContext],
    cancel_state: CancelState,
    is_first: bool,
) -> None:
    """在独立数据库会话中跑完一轮，结果写入缓冲，供多个连接订阅。"""
    db = SessionLocal()
    try:
        results = await dispatch_to_adapters(
            adapters,
            question,
            ctx,
            progress=run.publish,
            cancel_state=cancel_state,
            is_first_in_session=is_first,
        )
        qa = db.get(QAPairRow, run.qa_pair_id)
        if qa is not None:
            persist_answers(db, qa, results)
        await run.publish({"type": "complete", "summary": summarize_results(results)})
    except Exception as exc:
        logger.exception("websocket ask failed")
        await run.publish({"type": "error", "message": str(exc)})
    finally:
        await run.finish()
        db.close()


@router.websocket("/ws/ask")
async def websocket_ask(websocket: WebSocket) -> None:
    """
    客户端首条消息 JSON：
    {"action":"ask","session_id":"...","question":"...","platform_ids":null|["id",...]}
    断线后续订：
    {"action":"subscribe","qa_pair_id":"..."}
    随后可发送：
    {"action":"cancel"} 或 {"action":"cancel","platform_id":"genspark"}
    """
    await websocket.accept()
    db = SessionLocal()
    try:
        payload: Dict[str, Any] = await websocket.receive_json()
        action = payload.get("action")
        if action == "subscribe":
            run = registry.get(str(payload.get("qa_pair_id") or ""))
            if run is None:
                await websocket.send_json({"type": "error", "message": "问答任务不存在或已过期"})
                return
            await _stream_run(websocket, run, CancelState())
            return
        if action != "ask":
            await websocket.send_json({"type": "error", "message": "需要 action=ask"})
            return

        session_id = payload.get("session_id")
        question = (payload.get("question") or "").strip()
        platform_ids: Optional[List[str]] = payload.get("platform_ids")

        if not session_id or not question:
            await websocket.send_json({"type": "error", "message": "缺少 session_id 或 question"})
            return

        if get_session(db, session_id) is None:
            await websocket.send_json({"type": "error", "message": "session 不存在"})
            return

        # 同一问题仍在跑时直接续订，不再插入新的 QAPair
        existing = registry.find_open(session_id, question)
        if existing is not None:
            await _stream_run(websocket, existing, CancelState())
            return

        registry_obj = PlatformRegistry(db)
        adapters = registry_obj.get_enabled_adapters()
        if platform_ids:
            wanted = set(platform_ids)
            adapters = [a for a in adapters if a.platform_id in wanted]

        qa = add_qa_pair(db, session_id, question)
        count = db.scalar(
            select(func.count()).select_from(QAPairRow).where(QAPairRow.session_id == session_id)
        )
        is_first = int(count or 0) <= 1
        run = ActiveRun(qa_pair_id=qa.id, session_id=session_id, question=question)
        registry.put(run)
        await run.publish({"type": "qa_pair", "qa_pair_id": qa.id, "question": question})

        ctx = _browser_context(websocket)
        cancel_state = CancelState()
        asyncio.create_task(
            _execute_run(run, adapters, question, ctx, cancel_state, is_first)
        )
        await _stream_run(websocket, run, cancel_state)
    except WebSocketDisconnect:
        logger.debug("websocket client disconnected")
    except Exception as exc:
        logger.exception("websocket ask failed")
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        db.close()
