"""平台管理 API。"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from oneqmultia.api.schemas import (
    PlatformBatchEnableBody,
    PlatformCreateBody,
    PlatformImportBody,
    PlatformOut,
    PlatformPatchBody,
)
from oneqmultia.platform_manager import crud
from oneqmultia.platform_manager.account_binder import bind_or_check_login, validate_and_store_url
from oneqmultia.platform_manager.health_checker import run_health_check
from oneqmultia.platform_manager.importer import export_all_json, import_json_replace
from oneqmultia.storage.database import get_db

router = APIRouter(prefix="/platforms", tags=["platforms"])


def _cdp_context(request: Request):
    """读取应用启动时连接的 CDP 浏览器上下文。"""
    return getattr(request.app.state, "browser_context", None)


def _platform_account_payload(row) -> dict:
    """账号绑定与网址校验的统一返回结构。"""
    return {
        "id": row.id,
        "display_name": row.display_name,
        "url": row.url,
        "expected_host": row.expected_host,
        "url_status": row.url_status,
        "url_checked_at": row.url_checked_at,
        "url_check_message": row.url_check_message,
        "login_status": row.login_status,
        "login_checked_at": row.login_checked_at,
        "login_message": row.login_message,
    }


@router.get("", response_model=List[PlatformOut])
def list_platforms(enabled_only: bool = False, db: Session = Depends(get_db)) -> List[PlatformOut]:
    rows = crud.list_platforms(db, enabled_only=enabled_only)
    return [PlatformOut.model_validate(r) for r in rows]


@router.get("/export/all")
def export_platforms(db: Session = Depends(get_db)) -> dict:
    """必须在 /{platform_id} 之前注册，避免被当成 id。"""
    return {"json": export_all_json(db)}


@router.get("/cdp-status")
def cdp_status(request: Request) -> dict:
    """调试版 Chrome 是否已连接，账号绑定依赖该连接。"""
    ctx = _cdp_context(request)
    connected = ctx is not None
    return {
        "connected": connected,
        "message": "已连接调试版 Chrome" if connected else "未连接，请先运行 ./scripts/start_chrome_cdp.sh",
    }


@router.post("/batch-enable")
def batch_enable_platforms(body: PlatformBatchEnableBody, db: Session = Depends(get_db)) -> dict:
    """批量启用或禁用多个平台。"""
    n = crud.set_platforms_enabled(db, body.platform_ids, body.enabled)
    return {"updated": n, "enabled": body.enabled}


@router.post("/import")
def import_platforms(body: PlatformImportBody, db: Session = Depends(get_db)) -> dict:
    """用 JSON 数组全量替换平台配置（谨慎使用，建议先 export 备份）。"""
    import json

    payload = json.dumps(body.platforms, ensure_ascii=False)
    n = import_json_replace(db, payload)
    return {"imported": n}


@router.post("/accounts/scan")
async def scan_accounts(
    request: Request,
    check_network: bool = True,
    db: Session = Depends(get_db),
) -> dict:
    """批量校验网址；若 CDP 已连接则同时扫描登录态。"""
    ctx = _cdp_context(request)
    results = []
    for row in crud.list_platforms(db):
        url_row = validate_and_store_url(db, row.id, check_network=check_network)
        login_error = None
        if ctx is not None:
            try:
                url_row = await bind_or_check_login(db, row.id, ctx, open_tab=False)
            except Exception as exc:
                login_error = str(exc)
        item = _platform_account_payload(url_row)
        if login_error:
            item["login_message"] = login_error
        results.append(item)
    return {"cdp_connected": ctx is not None, "results": results}


@router.get("/{platform_id}", response_model=PlatformOut)
def get_platform(platform_id: str, db: Session = Depends(get_db)) -> PlatformOut:
    row = crud.get_platform(db, platform_id)
    if row is None:
        raise HTTPException(status_code=404, detail="platform not found")
    return PlatformOut.model_validate(row)


@router.post("", response_model=PlatformOut)
def create_platform(body: PlatformCreateBody, db: Session = Depends(get_db)) -> PlatformOut:
    if crud.get_platform(db, body.id):
        raise HTTPException(status_code=409, detail="platform id already exists")
    row = crud.create_platform(db, body.model_dump())
    return PlatformOut.model_validate(row)


@router.patch("/{platform_id}", response_model=PlatformOut)
def patch_platform(
    platform_id: str,
    body: PlatformPatchBody,
    db: Session = Depends(get_db),
) -> PlatformOut:
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    row = crud.update_platform(db, platform_id, data)
    if row is None:
        raise HTTPException(status_code=404, detail="platform not found")
    if "url" in data:
        row = validate_and_store_url(db, platform_id, check_network=False)
    return PlatformOut.model_validate(row)


@router.delete("/{platform_id}")
def delete_platform(platform_id: str, db: Session = Depends(get_db)) -> dict:
    ok = crud.delete_platform(db, platform_id)
    if not ok:
        raise HTTPException(status_code=404, detail="platform not found")
    return {"ok": True}


@router.post("/{platform_id}/health")
async def health_platform(platform_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        row = await run_health_check(db, platform_id, use_cdp=None)
    except ValueError:
        raise HTTPException(status_code=404, detail="platform not found")
    msg = getattr(row, "_last_health_message", None)
    return {
        "id": row.id,
        "health_status": row.health_status,
        "health_checked_at": row.health_checked_at,
        "message": msg,
    }


@router.post("/{platform_id}/url/validate")
def validate_platform_url_api(
    platform_id: str,
    check_network: bool = True,
    db: Session = Depends(get_db),
) -> dict:
    """校验该助手服务网址格式、期望域名，以及可选的网络可达性。"""
    try:
        row = validate_and_store_url(db, platform_id, check_network=check_network)
    except ValueError:
        raise HTTPException(status_code=404, detail="platform not found")
    return _platform_account_payload(row)


@router.post("/{platform_id}/login/open")
async def open_platform_login(
    platform_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """在调试版 Chrome 中打开该助手，供用户手动登录绑定（不保存密码）。"""
    ctx = _cdp_context(request)
    if ctx is None:
        raise HTTPException(status_code=503, detail="CDP 未连接：请先启动调试版 Chrome")
    try:
        row = await bind_or_check_login(db, platform_id, ctx, open_tab=True)
    except ValueError:
        raise HTTPException(status_code=404, detail="platform not found")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    payload = _platform_account_payload(row)
    payload["opened"] = True
    return payload


@router.post("/{platform_id}/login/check")
async def check_platform_login(
    platform_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """检测调试版 Chrome 中该助手是否已登录。"""
    ctx = _cdp_context(request)
    if ctx is None:
        raise HTTPException(status_code=503, detail="CDP 未连接：请先启动调试版 Chrome")
    try:
        row = await bind_or_check_login(db, platform_id, ctx, open_tab=False)
    except ValueError:
        raise HTTPException(status_code=404, detail="platform not found")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _platform_account_payload(row)
