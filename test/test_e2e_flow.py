"""E2E 测试：API 完整问答流程（无 CDP）。"""

from starlette.testclient import TestClient


def test_full_qa_flow(client: TestClient) -> None:
    """创建会话 → 提问 → 列表 → 对比 → 分享 → 导出。"""
    sid = client.post("/api/sessions", json={"title": "Web 会话"}).json()["id"]

    ask = client.post(f"/api/sessions/{sid}/ask", json={"question": "test", "platform_ids": ["chatgpt"]})
    assert ask.status_code == 200
    qa_id = ask.json()["qa_pair_id"]

    sessions = client.get("/api/sessions")
    found = next(s for s in sessions.json() if s["id"] == sid)
    assert found["qa_count"] >= 1
    assert found["preview"] or found["title"]

    detail = client.get(f"/api/sessions/{sid}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["qa_pairs"]
    assert body["qa_pairs"][0]["question"] == "test"
    assert isinstance(body["qa_pairs"][0]["answers"], list)

    compare = client.get(f"/api/sessions/{sid}/qa/{qa_id}/compare")
    assert compare.status_code == 200

    share = client.post(f"/api/sessions/{sid}/share")
    assert share.status_code == 200
    token = share.json()["token"]
    pub = client.get(f"/api/public/share/{token}")
    assert pub.status_code == 200

    export = client.get(f"/api/sessions/{sid}/export?format=md")
    assert export.status_code == 200
    assert "test" in export.text or len(export.content) > 0
