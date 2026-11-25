"""轻量 SQLite 列迁移：为已有库补齐新增字段，避免 create_all 无法 ALTER。"""

from __future__ import annotations

import logging
from typing import Iterable
from urllib.parse import urlparse

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

_log = logging.getLogger(__name__)

# 平台表新增列：账号绑定状态 + 网址校验结果
_PLATFORM_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("login_status", "VARCHAR(32) DEFAULT 'unknown'"),
    ("login_checked_at", "DATETIME"),
    ("login_message", "TEXT DEFAULT ''"),
    ("url_status", "VARCHAR(32) DEFAULT 'unknown'"),
    ("url_checked_at", "DATETIME"),
    ("url_check_message", "TEXT DEFAULT ''"),
    ("expected_host", "VARCHAR(256) DEFAULT ''"),
    ("execution_mode", "VARCHAR(32) DEFAULT 'web_only'"),
    ("api_provider", "VARCHAR(64) DEFAULT ''"),
    ("api_model", "VARCHAR(128) DEFAULT ''"),
)

_SESSION_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("pinned", "BOOLEAN DEFAULT 0"),
)

_SHARE_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("expires_at", "DATETIME"),
    ("revoked_at", "DATETIME"),
    ("view_count", "INTEGER DEFAULT 0"),
)

# 问答表：缓存最优答案 JSON
_QA_NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("optimal_answer", "JSON"),
)


def _add_missing_columns(conn, table: str, existing: set[str], columns: tuple[tuple[str, str], ...]) -> list[str]:
    """给已有表补列，返回本次新增列名。"""
    added: list[str] = []
    for name, ddl in columns:
        if name in existing:
            continue
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        added.append(name)
    return added


def _schema_needs_alter(engine: Engine) -> bool:
    """是否存在尚未执行的 ADD COLUMN。有变更时才做热备。"""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "platform_configs" in tables:
        existing = {col["name"] for col in inspector.get_columns("platform_configs")}
        if any(name not in existing for name, _ddl in _PLATFORM_NEW_COLUMNS):
            return True
    if "qa_pairs" in tables:
        existing_qa = {col["name"] for col in inspector.get_columns("qa_pairs")}
        if any(name not in existing_qa for name, _ddl in _QA_NEW_COLUMNS):
            return True
    if "sessions" in tables:
        existing_sessions = {col["name"] for col in inspector.get_columns("sessions")}
        if any(name not in existing_sessions for name, _ddl in _SESSION_NEW_COLUMNS):
            return True
    if "share_links" in tables:
        existing_share = {col["name"] for col in inspector.get_columns("share_links")}
        if any(name not in existing_share for name, _ddl in _SHARE_NEW_COLUMNS):
            return True
    return False


def migrate_schema(engine: Engine) -> None:
    """为已存在的表补齐缺失列，并回填 expected_host。"""
    if _schema_needs_alter(engine):
        # ALTER 前先热备，避免迁移失败后无法回到旧结构
        from oneqmultia.storage.backup import backup_database

        backup_database(engine, reason="migrate")

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        if "platform_configs" in tables:
            existing = {col["name"] for col in inspector.get_columns("platform_configs")}
            added = _add_missing_columns(conn, "platform_configs", existing, _PLATFORM_NEW_COLUMNS)
            if added:
                _log.info("已为 platform_configs 增加列：%s", ", ".join(added))
            _backfill_expected_host(conn)
        if "qa_pairs" in tables:
            existing_qa = {col["name"] for col in inspector.get_columns("qa_pairs")}
            added_qa = _add_missing_columns(conn, "qa_pairs", existing_qa, _QA_NEW_COLUMNS)
            if added_qa:
                _log.info("已为 qa_pairs 增加列：%s", ", ".join(added_qa))
        if "sessions" in tables:
            existing_sessions = {col["name"] for col in inspector.get_columns("sessions")}
            added_sessions = _add_missing_columns(conn, "sessions", existing_sessions, _SESSION_NEW_COLUMNS)
            if added_sessions:
                _log.info("已为 sessions 增加列：%s", ", ".join(added_sessions))
        if "share_links" in tables:
            existing_share = {col["name"] for col in inspector.get_columns("share_links")}
            added_share = _add_missing_columns(conn, "share_links", existing_share, _SHARE_NEW_COLUMNS)
            if added_share:
                _log.info("已为 share_links 增加列：%s", ", ".join(added_share))


def _backfill_expected_host(conn) -> None:
    """用现有 url 的主机名填充空的 expected_host，作为后续校验基准。"""
    rows: Iterable = conn.execute(
        text("SELECT id, url, expected_host FROM platform_configs")
    ).fetchall()
    for row in rows:
        current = (row[2] or "").strip()
        if current:
            continue
        host = _host_from_url(row[1] or "")
        if not host:
            continue
        conn.execute(
            text("UPDATE platform_configs SET expected_host = :host WHERE id = :pid"),
            {"host": host, "pid": row[0]},
        )


def _host_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.removeprefix("www.").lower()
    except Exception:
        return ""
