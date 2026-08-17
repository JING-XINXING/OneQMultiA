"""数据库引擎与会话工厂。"""

from contextlib import contextmanager
from typing import Generator, Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from oneqmultia.config.settings import Settings, ensure_data_dir


def make_engine():
    """创建 SQLAlchemy Engine（SQLite 启用 check_same_thread=False 供 FastAPI 使用）。"""
    settings = Settings()
    url = settings.database_url
    if url.startswith("sqlite"):
        ensure_data_dir()
        connect_args = {"check_same_thread": False}
    else:
        connect_args = {}
    return create_engine(url, connect_args=connect_args, echo=False)


engine = make_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Iterator[Session]:
    """FastAPI 依赖：每请求一个会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """脚本/测试用：with session_scope() as db: ..."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
