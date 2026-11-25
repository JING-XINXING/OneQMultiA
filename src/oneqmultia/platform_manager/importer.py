"""平台配置导入/导出（JSON）。"""

import json
from typing import Any, List

from pydantic import ValidationError
from sqlalchemy import delete
from sqlalchemy.orm import Session

from oneqmultia.api.schemas import PlatformCreateBody
from oneqmultia.platform_manager import crud
from oneqmultia.storage.backup import backup_database
from oneqmultia.storage.database import engine
from oneqmultia.storage.models import PlatformConfigRow


class ImportValidationError(ValueError):
    """整包校验失败。此时数据库尚未改动。"""


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
        "execution_mode": row.execution_mode or "web_only",
        "api_provider": row.api_provider or "",
        "api_model": row.api_model or "",
    }


def export_all_json(db: Session) -> str:
    """导出全部平台为 JSON 字符串。"""
    rows = crud.list_platforms(db)
    return json.dumps([platform_to_dict(r) for r in rows], ensure_ascii=False, indent=2)


def import_json_replace(db: Session, payload: str) -> int:
    """
    用 JSON 数组替换全部平台配置。

    先热备，再全量校验。任一记录非法则抛 ImportValidationError，不删除旧数据。
    校验通过后在同一个事务里删除并插入，失败则 rollback。
    """
    data: List[dict[str, Any]] = json.loads(payload)
    # 覆盖写入前先留快照，即使随后校验失败也能回溯
    backup_database(engine, reason="import_replace")
    validated: List[dict[str, Any]] = []
    for index, item in enumerate(data, start=1):
        try:
            body = PlatformCreateBody.model_validate(item)
        except ValidationError as exc:
            first = exc.errors()[0] if exc.errors() else {"msg": str(exc)}
            raise ImportValidationError(f"第 {index} 条平台配置非法：{first.get('msg')}") from exc
        validated.append(body.model_dump())

    try:
        # 批量删除，避免同一主键先删后插时卡在 identity map
        db.execute(delete(PlatformConfigRow))
        db.flush()
        db.expire_all()
        for item in validated:
            crud.create_platform(db, item, commit=False)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return len(validated)
