"""v0.3.0：WebSocket 断线后续订，不重复创建提问。"""

import asyncio
from datetime import datetime, timezone

import pytest
from starlette.testclient import TestClient

from oneqmultia.platforms.base import AskResult, AskTiming
from oneqmultia.storage.database import SessionLocal
from oneqmultia.storage.models import QAPairRow


@pytest.mark.asyncio
async def test_subscribe_replays_same_qa_pair(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """subscribe 接到已有 qa_pair_id 时，库里仍只有一条提问，且能看到 platform_done。"""

    async def _fake_dispatch(adapters, question, context, progress=None, cancel_state=None, is_first_in_session=False):
        adapter = adapters[0]
        if progress:
            await progress({"type": "platform_start", "platform_id": adapter.platform_id, "platform_name": adapter.config.display_name})
        await asyncio.sleep(0.3)
        timing = AskTiming()
        timing.request_sent_at = datetime.now(timezone.utc)
        timing.first_token_at = datetime.now(timezone.utc)
        timing.completed_at = datetime.now(timezone.utc)
        result = AskResult(
            platform_id=adapter.platform_id,
            platform_name=adapter.config.display_name,
            platform_url=adapter.config.url,
            answer_text="续传回答",
            status="success",
            error_message="",
            timing=timing,
        )
        if progress:
            await progress(
                {
                    "type": "platform_done",
                    "platform_id": result.platform_id,
                    "platform_name": result.platform_name,
                    "platform_url": result.platform_url,
                    "status": result.status,
                    "answer_text": result.answer_text,
                    "error_message": "",
                    "request_sent_at": timing.request_sent_at.isoformat(),
                    "first_token_at": timing.first_token_at.isoformat(),
                    "completed_at": timing.completed_at.isoformat(),
                    "response_duration_ms": 1,
                }
            )
        return [result]

    monkeypatch.setattr("oneqmultia.api.ws_routes.dispatch_to_adapters", _fake_dispatch)

    sid = client.post("/api/sessions", json={"title": "续传"}).json()["id"]
    with client.websocket_connect("/api/ws/ask") as ws:
        ws.send_json({"action": "ask", "session_id": sid, "question": "只要一次", "platform_ids": ["chatgpt"]})
        first = ws.receive_json()
        assert first["type"] == "qa_pair"
        qa_id = first["qa_pair_id"]
        # 先把这一轮收完，再模拟断线后的续订回放
        while True:
            msg = ws.receive_json()
            if msg.get("type") == "complete":
                break

    with client.websocket_connect("/api/ws/ask") as ws2:
        ws2.send_json({"action": "subscribe", "qa_pair_id": qa_id})
        types = []
        while True:
            msg = ws2.receive_json()
            types.append(msg.get("type"))
            if msg.get("type") in {"complete", "error"}:
                break
    assert "platform_done" in types
    assert "complete" in types

    db = SessionLocal()
    try:
        count = db.query(QAPairRow).filter(QAPairRow.session_id == sid).count()
    finally:
        db.close()
    assert count == 1
