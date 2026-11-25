"""v0.3.0：非法导入不破坏原平台，并且事先留下热备。"""

import json

from starlette.testclient import TestClient

from oneqmultia.storage.backup import list_backups
from oneqmultia.storage.database import engine


def test_invalid_import_keeps_platforms_and_writes_backup(client: TestClient) -> None:
    export_r = client.get("/api/platforms/export/all")
    assert export_r.status_code == 200
    platforms = json.loads(export_r.json()["json"])
    original_count = len(platforms)
    assert original_count >= 5

    broken = json.loads(json.dumps(platforms))
    broken[4]["url"] = "ftp://bad.example.com/nope"
    before = {item.name for item in list_backups(engine)}

    response = client.post("/api/platforms/import", json={"platforms": broken})
    assert response.status_code == 422

    listed = client.get("/api/platforms")
    assert listed.status_code == 200
    assert len(listed.json()) == original_count
    names = {item["id"]: item["display_name"] for item in listed.json()}
    assert names[platforms[0]["id"]] == platforms[0]["display_name"]

    created = [item for item in list_backups(engine) if item.name not in before]
    assert created, "导入前应自动生成热备文件"
    assert any("import_replace" in item.name for item in created)
