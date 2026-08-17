"""FastAPI 应用入口。"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from oneqmultia.api.export_routes import router as export_router
from oneqmultia.api.platform_routes import router as platform_router
from oneqmultia.api.public_routes import router as public_router
from oneqmultia.api.routes import router as qa_router
from oneqmultia.api.ws_routes import router as ws_router
from oneqmultia.config.settings import Settings
from oneqmultia.platform_manager.seed import seed_platforms_if_empty
from oneqmultia.storage import init_db
from oneqmultia.storage.database import SessionLocal
from oneqmultia.webui import mount_frontend

_log = logging.getLogger(__name__)


async def _try_connect_cdp(app: FastAPI, settings: Settings) -> None:
    """尝试连接 CDP 浏览器并写入 app.state。"""
    if not settings.cdp_url:
        return
    try:
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        browser = await pw.chromium.connect_over_cdp(settings.cdp_url)
        app.state._playwright = pw
        app.state._cdp_browser = browser
        if browser.contexts:
            app.state.browser_context = browser.contexts[0]
        else:
            app.state.browser_context = await browser.new_context()
        _log.info("已连接 CDP 浏览器：%s", settings.cdp_url)
    except Exception as e:
        _log.warning("CDP 连接失败：%s", e)
        app.state.browser_context = None


async def _cdp_reconnect_loop(app: FastAPI, interval: int) -> None:
    """后台任务：CDP 断连后定期重连。"""
    while True:
        await asyncio.sleep(interval)
        settings = Settings()
        if not settings.cdp_url:
            continue
        ctx = getattr(app.state, "browser_context", None)
        if ctx is not None:
            continue
        _log.info("尝试 CDP 自动重连…")
        await _try_connect_cdp(app, settings)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """启动时建表、种子数据；可选连接 CDP 浏览器。"""
    init_db()
    db = SessionLocal()
    try:
        seed_platforms_if_empty(db)
    finally:
        db.close()

    settings = Settings()
    app.state.browser_context = None
    app.state._playwright = None
    app.state._cdp_browser = None
    app.state._reconnect_task = None

    await _try_connect_cdp(app, settings)

    if settings.cdp_url and settings.cdp_reconnect_interval_sec > 0:
        app.state._reconnect_task = asyncio.create_task(
            _cdp_reconnect_loop(app, settings.cdp_reconnect_interval_sec)
        )

    yield

    if app.state._reconnect_task is not None:
        app.state._reconnect_task.cancel()
        try:
            await app.state._reconnect_task
        except asyncio.CancelledError:
            pass

    # 不断开用户本机 Chrome，仅关闭 Playwright 侧连接
    if app.state._cdp_browser is not None:
        try:
            await app.state._cdp_browser.close()
        except Exception:
            pass
    if app.state._playwright is not None:
        await app.state._playwright.stop()


def create_app() -> FastAPI:
    settings = Settings()
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        lifespan=lifespan,
    )
    # React/Vite 本地开发、Streamlit、移动端 WebSocket 跨源
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(qa_router, prefix="/api")
    app.include_router(platform_router, prefix="/api")
    app.include_router(export_router, prefix="/api")
    app.include_router(public_router, prefix="/api")
    app.include_router(ws_router, prefix="/api")

    @app.get("/health", include_in_schema=False)
    def health() -> dict:
        return {"status": "ok"}

    # 有 frontend/dist 时同一端口提供 React UI；否则 / 跳转 Swagger
    mounted = mount_frontend(app)
    if not mounted:
        # 减少浏览器自动请求 favicon 产生的 404 日志
        @app.get("/favicon.ico", include_in_schema=False)
        def favicon() -> Response:
            return Response(status_code=204)

    return app


app = create_app()
