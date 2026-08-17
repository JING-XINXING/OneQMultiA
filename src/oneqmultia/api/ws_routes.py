"""WebSocket：流式推送各平台开始、回答片段、完成与汇总。"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from playwright.async_api import BrowserContext

from oneqmultia.core.aggregator import summarize_results
from oneqmultia.core.dispatcher import CancelState, dispatch_to_adapters, persist_answers
from oneqmultia.core.platform_registry import PlatformRegistry
from oneqmultia.core.session_manager import add_qa_pair, get_session
from oneqmultia.storage.database import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter()


def _browser_context(ws: WebSocket) -> Optional[BrowserContext]:
    return getattr(ws.app.state, "browser_context", None)


@router.websocket("/ws/ask")
async def websocket_ask(websocket: WebSocket) -> None:
    """
    客户端首条消息 JSON：
    {"action":"ask","session_id":"...","question":"...","platform_ids":null|["id",...]}
    随后可发送：
    {"action":"cancel"} 或 {"action":"cancel","platform_id":"genspark"}

    服务端事件（均为 JSON）：
    - qa_pair: 已创建问答对
    - platform_start / answer_delta / platform_done: 调度与流式片段
    - complete: 全部结束 + summary
    - error: 异常说明
    """
    await websocket.accept()
    db = SessionLocal()
    try:
        payload: Dict[str, Any] = await websocket.receive_json()
        if payload.get("action") != "ask":
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

        registry = PlatformRegistry(db)
        adapters = registry.get_enabled_adapters()
        if platform_ids:
            wanted = set(platform_ids)
            adapters = [a for a in adapters if a.platform_id in wanted]

        qa = add_qa_pair(db, session_id, question)
        await websocket.send_json(
            {
                "type": "qa_pair",
                "qa_pair_id": qa.id,
                "question": question,
            }
        )

        ctx = _browser_context(websocket)
        cancel_state = CancelState()

        async def progress(evt: Dict[str, Any]) -> None:
            try:
                await websocket.send_json(evt)
            except Exception:
                logger.debug("websocket send failed during progress", exc_info=True)

        async def listen_cancel() -> None:
            """并行接收 cancel；客户端断开也视为终止全部。"""
            try:
                while True:
                    msg = await websocket.receive_json()
                    if msg.get("action") == "cancel":
                        cancel_state.cancel(msg.get("platform_id") or None)
                        if cancel_state.all:
                            return
            except WebSocketDisconnect:
                cancel_state.cancel()
            except Exception:
                cancel_state.cancel()

        listen_task = asyncio.create_task(listen_cancel())
        try:
            results = await dispatch_to_adapters(
                adapters, question, ctx, progress=progress, cancel_state=cancel_state
            )
            persist_answers(db, qa, results)
            await websocket.send_json(
                {
                    "type": "complete",
                    "summary": summarize_results(results),
                }
            )
        finally:
            listen_task.cancel()
            try:
                await listen_task
            except asyncio.CancelledError:
                pass
    except WebSocketDisconnect:
        logger.debug("websocket client disconnected")
    except Exception as e:
        logger.exception("websocket ask failed")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        db.close()
