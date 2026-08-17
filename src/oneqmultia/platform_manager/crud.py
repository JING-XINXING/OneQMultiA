"""平台配置 CRUD。"""

from datetime import datetime, timezone
from typing import Any, List, Optional
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from oneqmultia.storage.models import PlatformConfigRow


def _host_from_url(url: str) -> str:
    """从平台 URL 提取期望主机名。"""
    try:
        return urlparse(url or "").netloc.removeprefix("www.").lower()
    except Exception:
        return ""


def list_platforms(db: Session, *, enabled_only: bool = False) -> List[PlatformConfigRow]:
    """列出平台，按 sort_order、id 排序。"""
    q = select(PlatformConfigRow).order_by(
        PlatformConfigRow.sort_order.asc(),
        PlatformConfigRow.id.asc(),
    )
    if enabled_only:
        q = q.where(PlatformConfigRow.enabled.is_(True))
    return list(db.scalars(q).all())


def get_platform(db: Session, platform_id: str) -> Optional[PlatformConfigRow]:
    """按 id 获取平台。"""
    return db.get(PlatformConfigRow, platform_id)


def create_platform(db: Session, data: dict[str, Any]) -> PlatformConfigRow:
    """新增平台。"""
    row = PlatformConfigRow(
        id=data["id"],
        display_name=data["display_name"],
        url=data["url"],
        icon=data.get("icon") or "",
        group=data.get("group") or "custom",
        enabled=bool(data.get("enabled", True)),
        sort_order=int(data.get("sort_order") or 0),
        timeout_seconds=int(data.get("timeout_seconds") or 120),
        selectors=data.get("selectors") or {},
        interaction=data.get("interaction") or {},
        adapter_type=data.get("adapter_type") or "generic",
        adapter_module=data.get("adapter_module") or "",
        health_status="unknown",
        login_status=data.get("login_status") or "unknown",
        login_message=data.get("login_message") or "",
        url_status=data.get("url_status") or "unknown",
        url_check_message=data.get("url_check_message") or "",
        expected_host=data.get("expected_host") or _host_from_url(data.get("url") or ""),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_platform(db: Session, platform_id: str, data: dict[str, Any]) -> Optional[PlatformConfigRow]:
    """部分更新平台。"""
    row = get_platform(db, platform_id)
    if row is None:
        return None
    for key in (
        "display_name",
        "url",
        "icon",
        "group",
        "enabled",
        "sort_order",
        "timeout_seconds",
        "selectors",
        "interaction",
        "adapter_type",
        "adapter_module",
        "login_status",
        "login_message",
        "url_status",
        "url_check_message",
        "expected_host",
    ):
        if key in data:
            setattr(row, key, data[key])
    if "url" in data:
        # 修改网址后重置校验状态；已有期望域名保持不变，用于核对是否改错站
        row.url_status = "unknown"
        row.url_check_message = ""
        if "expected_host" not in data and not (row.expected_host or "").strip():
            row.expected_host = _host_from_url(str(data["url"]))
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


def delete_platform(db: Session, platform_id: str) -> bool:
    """删除平台配置。"""
    row = get_platform(db, platform_id)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def set_platforms_enabled(db: Session, ids: List[str], enabled: bool) -> int:
    """批量启用/禁用，返回影响行数。"""
    n = 0
    for pid in ids:
        row = get_platform(db, pid)
        if row:
            row.enabled = enabled
            row.updated_at = datetime.now(timezone.utc)
            n += 1
    db.commit()
    return n
