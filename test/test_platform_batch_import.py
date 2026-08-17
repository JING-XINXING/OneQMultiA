"""测试批量启用/禁用与 JSON 导入 API。"""

import json

from starlette.testclient import TestClient


def test_batch_enable_disable(client: TestClient) -> None:
    """批量禁用再启用 chatgpt。"""
    r = client.post(
        "/api/platforms/batch-enable",
        json={"platform_ids": ["chatgpt"], "enabled": False},
    )
    assert r.status_code == 200
    assert r.json()["updated"] == 1
    assert r.json()["enabled"] is False

    r2 = client.get("/api/platforms/chatgpt")
    assert r2.json()["enabled"] is False

    r3 = client.post(
        "/api/platforms/batch-enable",
        json={"platform_ids": ["chatgpt"], "enabled": True},
    )
    assert r3.status_code == 200
    assert r3.json()["updated"] == 1


def test_import_platforms(client: TestClient) -> None:
    """JSON 导入后平台数量正确。"""
    export_r = client.get("/api/platforms/export/all")
    assert export_r.status_code == 200
    platforms = json.loads(export_r.json()["json"])

    # 修改一条后导入
    for p in platforms:
        if p["id"] == "chatgpt":
            p["display_name"] = "ChatGPT Import Test"
            break

    r = client.post("/api/platforms/import", json={"platforms": platforms})
    assert r.status_code == 200
    assert r.json()["imported"] == len(platforms)

    r2 = client.get("/api/platforms/chatgpt")
    assert r2.json()["display_name"] == "ChatGPT Import Test"

    # 恢复原名
    for p in platforms:
        if p["id"] == "chatgpt":
            p["display_name"] = "ChatGPT"
            break
    client.post("/api/platforms/import", json={"platforms": platforms})
