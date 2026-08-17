"""FastAPI 集成测试（无 CDP，问答结果为 skipped）。"""

from starlette.testclient import TestClient


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root_serves_docs_or_spa(client: TestClient) -> None:
    """无前端产物时跳转 /docs；本地若已 build frontend/dist 则返回 SPA。"""
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (200, 302)
    if r.status_code == 302:
        assert r.headers.get("location") == "/docs"
    else:
        assert "html" in r.headers.get("content-type", "").lower()


def test_favicon_no_404(client: TestClient) -> None:
    r = client.get("/favicon.ico")
    assert r.status_code in (200, 204)


def test_list_platforms(client: TestClient) -> None:
    r = client.get("/api/platforms")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 23
    assert any(p["id"] == "genspark" for p in data)
    assert data[0]["id"]
    assert "login_status" in data[0]
    assert "url_status" in data[0]
    assert data[0]["expected_host"]


def test_cdp_status_disconnected(client: TestClient) -> None:
    r = client.get("/api/platforms/cdp-status")
    assert r.status_code == 200
    body = r.json()
    assert body["connected"] is False


def test_login_open_requires_cdp(client: TestClient) -> None:
    r = client.post("/api/platforms/chatgpt/login/open")
    assert r.status_code == 503


def test_validate_url_format_only(client: TestClient) -> None:
    r = client.post("/api/platforms/chatgpt/url/validate?check_network=false")
    assert r.status_code == 200
    body = r.json()
    assert body["url_status"] == "valid"
    assert body["expected_host"] == "chatgpt.com"


def test_patch_invalid_url_rejected(client: TestClient) -> None:
    r = client.patch("/api/platforms/chatgpt", json={"url": "javascript:alert(1)"})
    assert r.status_code == 422


def test_patch_wrong_host_marked_invalid(client: TestClient) -> None:
    r = client.patch("/api/platforms/chatgpt", json={"url": "https://example.com/"})
    assert r.status_code == 200
    body = r.json()
    assert body["url_status"] == "invalid"
    # 恢复官方网址，避免影响同进程后续测试
    restore = client.patch("/api/platforms/chatgpt", json={"url": "https://chatgpt.com/", "expected_host": "chatgpt.com"})
    assert restore.status_code == 200


def test_ask_without_browser_skipped(client: TestClient) -> None:
    r = client.post("/api/sessions", json={"title": "t1"})
    assert r.status_code == 200
    sid = r.json()["id"]
    r2 = client.post(
        f"/api/sessions/{sid}/ask",
        json={"question": "hello", "platform_ids": ["chatgpt", "deepseek"]},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["summary"]["total"] == 2
    assert body["summary"]["skipped"] == 2
    assert all(a["status"] == "skipped" for a in body["answers"])
