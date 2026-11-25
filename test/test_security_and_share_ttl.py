"""v1.0.0：SSRF 拦截、分享有效期、远程写操作鉴权。"""

from datetime import datetime, timedelta, timezone

from starlette.testclient import TestClient

from oneqmultia.core.access_guard import request_is_allowed
from oneqmultia.core.consensus import build_consensus_matrix
from oneqmultia.config.settings import Settings
from oneqmultia.platform_manager.url_validator import check_url_reachable, ssrf_block_reason
from oneqmultia.storage.database import SessionLocal
from oneqmultia.storage.models import ShareLinkRow


def test_ssrf_blocks_loopback_and_metadata() -> None:
    assert ssrf_block_reason("http://127.0.0.1:38421/health")
    assert ssrf_block_reason("http://169.254.169.254/latest/meta-data")
    assert ssrf_block_reason("http://localhost/admin")
    blocked = check_url_reachable("http://127.0.0.1:38421/health")
    assert blocked.ok is False
    assert "内网" in blocked.message or "本机" in blocked.message


def test_share_expiry_and_revoke(client: TestClient) -> None:
    sid = client.post("/api/sessions", json={"title": "分享安全"}).json()["id"]
    client.post(f"/api/sessions/{sid}/ask", json={"question": "可见内容", "platform_ids": ["chatgpt"]})

    fresh = client.post(f"/api/sessions/{sid}/share", params={"ttl": "24h"})
    assert fresh.status_code == 200
    token = fresh.json()["token"]
    assert client.get(f"/api/public/share/{token}").status_code == 200

    db = SessionLocal()
    try:
        row = db.get(ShareLinkRow, token)
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()
    assert client.get(f"/api/public/share/{token}").status_code == 410

    another = client.post(f"/api/sessions/{sid}/share").json()["token"]
    assert client.post(f"/api/shares/{another}/revoke").status_code == 200
    assert client.get(f"/api/public/share/{another}").status_code == 410


def test_remote_write_requires_bearer(monkeypatch, client: TestClient) -> None:
    monkeypatch.setenv("ONEQMULTIA_API_HOST", "0.0.0.0")
    monkeypatch.setenv("ONEQMULTIA_ACCESS_TOKEN", "secret-token")
    denied = client.post("/api/sessions", json={"title": "远程"})
    assert denied.status_code == 401
    allowed = client.post(
        "/api/sessions",
        json={"title": "远程"},
        headers={"Authorization": "Bearer secret-token"},
    )
    assert allowed.status_code == 200
    settings = Settings()
    assert request_is_allowed("GET", "/api/public/share/abc", "", settings) is True
    assert request_is_allowed("POST", "/api/platforms/import", "", settings) is False


def test_consensus_matrix_finds_agreement_and_conflict() -> None:
    matrix = build_consensus_matrix([
        {
            "platform_name": "甲",
            "status": "success",
            "answer_text": "共识句是水在标准大气压下一百度沸腾。实验重复了 3 次。",
            "response_duration_ms": 1000,
        },
        {
            "platform_name": "乙",
            "status": "success",
            "answer_text": "共识句是水在标准大气压下一百度沸腾。实验重复了 5 次。",
            "response_duration_ms": 2000,
        },
    ])
    assert any("一百度" in item["text"] for item in matrix["agreements"])
    assert matrix["conflicts"]
    assert len(matrix["scores"]) == 2
