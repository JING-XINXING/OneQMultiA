"""答案对比 API 测试。"""

from starlette.testclient import TestClient


def test_compare_api(client: TestClient) -> None:
    r = client.post("/api/sessions", json={"title": "compare test"})
    sid = r.json()["id"]
    r2 = client.post(
        f"/api/sessions/{sid}/ask",
        json={"question": "hi", "platform_ids": ["chatgpt", "deepseek"]},
    )
    qa_id = r2.json()["qa_pair_id"]
    r3 = client.get(f"/api/sessions/{sid}/qa/{qa_id}/compare")
    assert r3.status_code == 200
    body = r3.json()
    assert "compared_count" in body
    assert "similarity_matrix" in body
    assert "optimal_answer" in body
    assert "text" in body["optimal_answer"]


def test_llm_status_api(client: TestClient) -> None:
    r = client.get("/api/llm/status")
    assert r.status_code == 200
    body = r.json()
    assert "configured" in body
    assert "api_key" not in body
    assert "providers" in body
    ids = {item["id"] for item in body["providers"]}
    assert "qwen" in ids and "glm" in ids
