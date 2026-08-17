"""平台配置导入/导出（JSON）。"""

import json
from typing import Any, List

from sqlalchemy.orm import Session

from oneqmultia.platform_manager import crud
from oneqmultia.storage.models import PlatformConfigRow


def platform_to_dict(row: PlatformConfigRow) -> dict[str, Any]:
    """ORM 转可序列化字典。"""
    return {
        "id": row.id,
        "display_name": row.display_name,
        "url": row.url,
        "icon": row.icon,
        "group": row.group,
        "enabled": row.enabled,
        "sort_order": row.sort_order,
        "timeout_seconds": row.timeout_seconds,
        "selectors": row.selectors,
        "interaction": row.interaction,
        "adapter_type": row.adapter_type,
        "adapter_module": row.adapter_module,
        "expected_host": row.expected_host or "",
    }


def export_all_json(db: Session) -> str:
    """导出全部平台为 JSON 字符串。"""
    rows = crud.list_platforms(db)
    return json.dumps([platform_to_dict(r) for r in rows], ensure_ascii=False, indent=2)


def import_json_replace(db: Session, payload: str) -> int:
    """
    用 JSON 数组替换全部平台配置（谨慎使用）。
    返回导入条数。
    """
    data: List[dict[str, Any]] = json.loads(payload)
    for r in crud.list_platforms(db):
        db.delete(r)
    db.commit()
    for item in data:
        crud.create_platform(db, item)
    return len(data)
