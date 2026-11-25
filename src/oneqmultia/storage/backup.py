"""SQLite 在线热备份与恢复。

使用标准库 sqlite3.Connection.backup()，可在连接仍被 SQLAlchemy 占用时复制一致性快照。
默认写到数据库同级目录 backups/，并只保留最近若干份。
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from sqlalchemy.engine import Engine

_log = logging.getLogger(__name__)

# 文件名：oneqmultia_YYYYMMDD_HHMMSS_<reason>.db
_KEEP_DEFAULT = 10


def sqlite_file_from_engine(engine: Engine) -> Optional[Path]:
    """从 Engine 解析 SQLite 文件路径；内存库返回 None。"""
    url = engine.url
    if not url.drivername.startswith("sqlite"):
        return None
    database = url.database
    if not database or database == ":memory:":
        return None
    return Path(database)


def backup_dir_for(db_file: Path) -> Path:
    """备份目录：<db 所在目录>/backups。"""
    return db_file.parent / "backups"


def backup_database(engine: Engine, reason: str, *, keep: int = _KEEP_DEFAULT) -> Optional[Path]:
    """
    为当前 SQLite 库做在线热备。

    reason 会写入文件名，便于区分 migrate / import_replace / reset_db。
    库文件不存在或为空时跳过，返回 None。
    """
    src_path = sqlite_file_from_engine(engine)
    if src_path is None or not src_path.is_file() or src_path.stat().st_size == 0:
        _log.info("跳过备份（无 SQLite 文件或为空）：reason=%s", reason)
        return None

    safe_reason = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in reason)[:40] or "manual"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_dir = backup_dir_for(src_path)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"oneqmultia_{stamp}_{safe_reason}.db"

    # backup() 走 SQLite 在线备份 API，避免直接 copy 读到半写页
    src = sqlite3.connect(str(src_path))
    dst = sqlite3.connect(str(dest))
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        src.close()

    _log.info("已创建数据库热备 %s", dest)
    _prune(dest_dir, keep)
    return dest


def list_backups(engine: Engine) -> List[Path]:
    """按修改时间从新到旧列出热备文件。"""
    src_path = sqlite_file_from_engine(engine)
    if src_path is None:
        return []
    folder = backup_dir_for(src_path)
    if not folder.is_dir():
        return []
    files = [p for p in folder.glob("oneqmultia_*.db") if p.is_file()]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def restore_database(engine: Engine, backup_file: Path) -> Path:
    """
    用指定热备覆盖当前库文件。

    覆盖前再自动留一份 reason=before_restore 的热备，避免恢复操作本身不可逆。
    """
    src_path = sqlite_file_from_engine(engine)
    if src_path is None:
        raise RuntimeError("当前数据库不是可恢复的 SQLite 文件")
    backup_file = Path(backup_file)
    if not backup_file.is_file():
        raise FileNotFoundError(str(backup_file))
    backup_database(engine, reason="before_restore")
    src_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_file, src_path)
    _log.info("已从 %s 恢复数据库到 %s", backup_file, src_path)
    return src_path


def _prune(folder: Path, keep: int) -> None:
    """只保留最近 keep 份热备。"""
    files = sorted(folder.glob("oneqmultia_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[max(keep, 1):]:
        try:
            old.unlink()
        except OSError:
            _log.warning("删除旧备份失败：%s", old, exc_info=True)
