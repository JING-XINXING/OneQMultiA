"""持久化层。"""

from oneqmultia.storage.database import SessionLocal, engine, get_db, session_scope
from oneqmultia.storage import models  # noqa: F401 — 注册 ORM（含 share_links）
from oneqmultia.storage.migrate import migrate_schema
from oneqmultia.storage.models import Base

__all__ = ["Base", "engine", "SessionLocal", "get_db", "session_scope", "init_db"]


def init_db() -> None:
    """创建所有表，并为已有 SQLite 库补齐新增列。"""
    Base.metadata.create_all(bind=engine)
    migrate_schema(engine)
