"""前端静态资源挂载（不依赖仓库里是否已有 frontend/dist）。"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from starlette.testclient import TestClient

from oneqmultia.webui import mount_frontend


def test_mount_without_dist_redirects_to_docs() -> None:
    app = FastAPI()
    ok = mount_frontend(app, dist_dir=Path("/nonexistent/oneqmultia-dist"))
    assert ok is False
    with TestClient(app) as client:
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 302
        assert r.headers.get("location") == "/docs"


def test_mount_with_dist_serves_spa(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<html>OneQMultiA-SPA</html>", encoding="utf-8")
    (assets / "app.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "manifest.json").write_text("{}", encoding="utf-8")

    app = FastAPI()

    @app.get("/api/ping")
    def ping() -> dict:
        return {"ok": True}

    ok = mount_frontend(app, dist_dir=dist)
    assert ok is True
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert "OneQMultiA-SPA" in r.text
        js = client.get("/assets/app.js")
        assert js.status_code == 200
        assert "console.log" in js.text
        man = client.get("/manifest.json")
        assert man.status_code == 200
        api = client.get("/api/ping")
        assert api.status_code == 200
        assert api.json()["ok"] is True
