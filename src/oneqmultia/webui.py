"""将 React 构建产物挂到 FastAPI：安装包/生产态同一端口提供 UI 与 API。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from oneqmultia.paths import frontend_dist_dir


def mount_frontend(app: FastAPI, dist_dir: Optional[Path] = None) -> bool:
    """挂载 SPA。有 ``index.html`` 时 ``/`` 返回前端，否则跳转 ``/docs``。

    必须在 API 路由注册之后调用，避免静态路由抢走 ``/api``。
    返回是否成功挂载了前端。
    """
    dist = Path(dist_dir) if dist_dir is not None else frontend_dist_dir()
    if dist is None or not (dist / "index.html").is_file():
        @app.get("/", include_in_schema=False)
        def root_to_docs() -> RedirectResponse:
            return RedirectResponse(url="/docs", status_code=302)

        return False

    index_file = dist / "index.html"

    @app.get("/", include_in_schema=False)
    def spa_index() -> FileResponse:
        return FileResponse(index_file, media_type="text/html")

    @app.get("/share/{token}", include_in_schema=False)
    def spa_share(token: str) -> FileResponse:
        """分享链接走前端只读页，而不是裸 JSON。"""
        return FileResponse(index_file, media_type="text/html")

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="spa-assets")

    # Vite public 目录拷贝出的根级静态文件
    static_names = ("manifest.json", "service-worker.js", "icon.svg", "index.html")

    def _make_static_handler(path: Path, media_type: Optional[str] = None):
        def _handler() -> FileResponse:
            kwargs = {}
            if media_type:
                kwargs["media_type"] = media_type
            return FileResponse(path, **kwargs)

        _handler.__name__ = f"static_{path.name.replace('.', '_')}"
        return _handler

    media_map = {
        "manifest.json": "application/manifest+json",
        "service-worker.js": "application/javascript",
        "icon.svg": "image/svg+xml",
        "index.html": "text/html",
    }
    for name in static_names:
        path = dist / name
        if not path.is_file():
            continue
        if name == "index.html":
            continue
        app.add_api_route(
            f"/{name}",
            _make_static_handler(path, media_map.get(name)),
            methods=["GET"],
            include_in_schema=False,
        )

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon_from_dist() -> Response:
        icon = dist / "icon.svg"
        if icon.is_file():
            return FileResponse(icon, media_type="image/svg+xml")
        return Response(status_code=204)

    return True
