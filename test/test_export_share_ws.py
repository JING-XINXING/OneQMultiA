"""导出、分享、WebSocket 集成测试。"""

from starlette.testclient import TestClient

from oneqmultia.export.export_service import content_disposition_attachment


def test_content_disposition_is_latin1() -> None:
    header = content_disposition_attachment("你好会话.html")
    header.encode("latin-1")
    assert "filename*=UTF-8''" in header
    assert "session.html" in header or "html" in header


def test_export_formats_list(client: TestClient) -> None:
    r = client.get("/api/export/formats")
    assert r.status_code == 200
    assert "md" in r.json()["formats"]


def test_export_md_after_ask(client: TestClient) -> None:
    sid = client.post("/api/sessions", json={"title": "e1"}).json()["id"]
    client.post(
        f"/api/sessions/{sid}/ask",
        json={"question": "q1", "platform_ids": ["chatgpt"]},
    )
    r = client.get(f"/api/sessions/{sid}/export", params={"format": "md"})
    assert r.status_code == 200
    assert "q1" in r.text
    assert "chatgpt" in r.text.lower() or "ChatGPT" in r.text


def test_export_chinese_title_all_formats(client: TestClient) -> None:
    """中文标题不得再因 Content-Disposition latin-1 报 500。"""
    sid = client.post("/api/sessions", json={"title": "你好会话"}).json()["id"]
    client.post(
        f"/api/sessions/{sid}/ask",
        json={"question": "介绍一下你自己", "platform_ids": ["chatgpt"]},
    )
    for fmt in ("md", "txt", "html", "pdf", "docx"):
        r = client.get(f"/api/sessions/{sid}/export", params={"format": fmt})
        assert r.status_code == 200, f"{fmt} -> {r.status_code} {r.text[:200]}"
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd
        cd.encode("latin-1")
        assert r.content


def test_share_and_public_read(client: TestClient) -> None:
    sid = client.post("/api/sessions", json={"title": "s1"}).json()["id"]
    client.post(
        f"/api/sessions/{sid}/ask",
        json={"question": "shared?", "platform_ids": ["deepseek"]},
    )
    tr = client.post(f"/api/sessions/{sid}/share")
    assert tr.status_code == 200
    token = tr.json()["token"]
    pr = client.get(f"/api/public/share/{token}")
    assert pr.status_code == 200
    body = pr.json()
    assert body["id"] == sid
    assert len(body["qa_pairs"]) >= 1


def test_websocket_ask_skipped(client: TestClient) -> None:
    sid = client.post("/api/sessions", json={}).json()["id"]
    with client.websocket_connect("/api/ws/ask") as ws:
        ws.send_json(
            {
                "action": "ask",
                "session_id": sid,
                "question": "ws hi",
                "platform_ids": ["chatgpt"],
            }
        )
        types = []
        while True:
            msg = ws.receive_json()
            types.append(msg.get("type"))
            if msg.get("type") == "complete":
                assert "summary" in msg
                break
            if msg.get("type") == "error":
                raise AssertionError(msg)
        assert "qa_pair" in types
        assert "platform_start" in types
        assert "platform_done" in types
