"""
用途：将数据库中的平台配置（selectors / interaction）与 default_platforms.yaml 同步。

运行方式（项目根目录，激活 venv）：
    python -m oneqmultia.tools.reset_db             # 预览变更（dry-run）
    python -m oneqmultia.tools.reset_db --apply     # 执行同步
    python -m oneqmultia.tools.reset_db --full      # 删除旧数据，全量重新 seed

行为（默认 --apply）：
  - 只更新已存在平台的 selectors / interaction / url / display_name / timeout_seconds
  - 不影响用户已通过 PATCH /api/platforms 修改的 enabled / sort_order 等字段
  - --full 模式会清空整张表后重新插入（慎用：会重置所有自定义改动）
"""

from __future__ import annotations

import sys
from typing import Any, Dict
from urllib.parse import urlparse

from oneqmultia.config.settings import ensure_data_dir
from oneqmultia.platform_manager.seed import load_yaml_platforms, seed_platforms_if_empty
from oneqmultia.storage import init_db
from oneqmultia.storage.backup import backup_database
from oneqmultia.storage.database import SessionLocal, engine
from oneqmultia.storage.models import PlatformConfigRow


def _merge_selectors(db_row: PlatformConfigRow, yaml_row: Dict[str, Any]) -> bool:
    """
    把 YAML 中 selectors / interaction / url 等技术字段更新到 DB 行。
    返回 True 表示有改动。
    """
    changed = False
    for field in ("selectors", "interaction"):
        new_val = yaml_row.get(field) or {}
        if getattr(db_row, field) != new_val:
            setattr(db_row, field, new_val)
            changed = True
    for field in ("url", "display_name", "timeout_seconds"):
        new_val = yaml_row.get(field)
        if new_val is not None and getattr(db_row, field) != new_val:
            setattr(db_row, field, new_val)
            changed = True
    return changed


def run(dry_run: bool = True, full: bool = False) -> None:
    ensure_data_dir()
    init_db()
    db = SessionLocal()
    try:
        if not dry_run:
            # 同步或清空前先热备，避免误操作丢掉已有平台配置
            backup_database(engine, reason="reset_full" if full else "reset_apply")
        if full:
            n = seed_platforms_if_empty(db, force=True)
            print(f"[full] 已清空并重新 seed {n} 个平台。")
            return

        yaml_platforms = load_yaml_platforms()
        yaml_map: Dict[str, Dict[str, Any]] = {p["id"]: p for p in yaml_platforms}

        updated, skipped, added = 0, 0, 0
        for pid, yrow in yaml_map.items():
            db_row: PlatformConfigRow | None = db.get(PlatformConfigRow, pid)
            if db_row is None:
                if not dry_run:
                    # 新平台：直接插入
                    new_row = PlatformConfigRow(
                        id=pid,
                        display_name=yrow["display_name"],
                        url=yrow["url"],
                        icon=yrow.get("icon") or "",
                        group=yrow.get("group") or "custom",
                        enabled=bool(yrow.get("enabled", True)),
                        sort_order=int(yrow.get("sort_order") or 0),
                        timeout_seconds=int(yrow.get("timeout_seconds") or 120),
                        selectors=yrow.get("selectors") or {},
                        interaction=yrow.get("interaction") or {},
                        adapter_type=yrow.get("adapter_type") or "generic",
                        adapter_module=yrow.get("adapter_module") or "",
                        health_status="unknown",
                        health_checked_at=None,
                        # 新增平台写入期望域名，便于 URL 校验与登录检测
                        expected_host=urlparse(yrow["url"]).netloc.removeprefix("www.").lower(),
                        login_status="unknown",
                        url_status="unknown",
                    )
                    db.add(new_row)
                    added += 1
                    print(f"  [add]  {pid}")
                else:
                    print(f"  [add?] {pid}（dry-run，未写入）")
            else:
                changed = _merge_selectors(db_row, yrow)
                if changed:
                    if not dry_run:
                        db.add(db_row)
                    updated += 1
                    print(f"  [upd]  {pid}")
                else:
                    skipped += 1

        if not dry_run:
            db.commit()
            print(f"\n✓ 同步完成：更新 {updated} 个，新增 {added} 个，跳过 {skipped} 个。")
        else:
            print(
                f"\n[dry-run] 预计：更新 {updated} 个，新增 {added} 个，跳过 {skipped} 个。"
                "\n加 --apply 参数执行实际写入。"
            )
    finally:
        db.close()


if __name__ == "__main__":
    dry_run = "--apply" not in sys.argv and "--full" not in sys.argv
    full = "--full" in sys.argv
    if dry_run:
        print("=== dry-run 模式（只预览，不写入）===\n")
    elif full:
        print("=== full 模式：清空并重新 seed ===\n")
    else:
        print("=== apply 模式：同步 selectors/interaction ===\n")
    run(dry_run=dry_run, full=full)
