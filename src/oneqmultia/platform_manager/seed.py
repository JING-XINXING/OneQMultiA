"""从 YAML 将预置平台写入数据库（仅在表为空或强制时）。"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any, List

import yaml
from urllib.parse import urlparse

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from oneqmultia.storage.models import PlatformConfigRow


def _default_yaml_bytes() -> bytes:
    """读取包内 default_platforms.yaml。"""
    pkg = resources.files("oneqmultia.config")
    return (pkg / "default_platforms.yaml").read_bytes()


def load_yaml_platforms(path: Path | None = None) -> List[dict[str, Any]]:
    """解析 YAML，返回 platforms 列表。"""
    raw = path.read_bytes() if path else _default_yaml_bytes()
    data = yaml.safe_load(raw)
    if not data or "platforms" not in data:
        return []
    return list(data["platforms"])


def seed_platforms_if_empty(db: Session, *, force: bool = False) -> int:
    """
    若 platform_configs 无数据则插入预置平台。
    返回新增条数。
    """
    count = db.execute(select(PlatformConfigRow.id).limit(1)).first()
    if count is not None and not force:
        return 0

    if force:
        db.execute(delete(PlatformConfigRow))
        db.commit()

    items = load_yaml_platforms()
    n = 0
    for row in items:
        pid = row["id"]
        selectors = row.get("selectors") or {}
        interaction = row.get("interaction") or {}
        cfg = PlatformConfigRow(
            id=pid,
            display_name=row["display_name"],
            url=row["url"],
            icon=row.get("icon") or "",
            group=row.get("group") or "custom",
            enabled=bool(row.get("enabled", True)),
            sort_order=int(row.get("sort_order") or 0),
            timeout_seconds=int(row.get("timeout_seconds") or 120),
            selectors=selectors,
            interaction=interaction,
            adapter_type=row.get("adapter_type") or "generic",
            adapter_module=row.get("adapter_module") or "",
            health_status="unknown",
            health_checked_at=None,
            expected_host=urlparse(row["url"]).netloc.removeprefix("www.").lower(),
            login_status="unknown",
            url_status="unknown",
        )
        db.merge(cfg)
        n += 1
    db.commit()
    return n
