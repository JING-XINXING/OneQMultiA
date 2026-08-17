"""历史会话详情：恢复时必须带上各平台回答。"""

from starlette.testclient import TestClient


def test_session_detail_includes_platform_answers(client: TestClient) -> None:
    sid = client.post("/api/sessions", json={"title": ""}).json()["id"]
    ask = client.post(
        f"/api/sessions/{sid}/ask",
        json={"question": "什么是虚拟细胞", "platform_ids": ["chatgpt", "deepseek"]},
    )
    assert ask.status_code == 200

    detail = client.get(f"/api/sessions/{sid}")
    assert detail.status_code == 200
    pairs = detail.json()["qa_pairs"]
    assert len(pairs) == 1
    assert pairs[0]["question"] == "什么是虚拟细胞"
    ids = {a["platform_id"] for a in pairs[0]["answers"]}
    assert "chatgpt" in ids
    assert "deepseek" in ids
    for ans in pairs[0]["answers"]:
        assert "answer_text" in ans
        assert ans["status"] in {"success", "skipped", "error", "timeout", "cancelled"}
