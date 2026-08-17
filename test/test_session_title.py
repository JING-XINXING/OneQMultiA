"""会话标题生成与占位标题回填。"""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from oneqmultia.core.session_manager import (
    add_qa_pair,
    create_session,
    is_placeholder_title,
    make_session_preview,
    make_session_title,
)
from oneqmultia.storage.models import Base, SessionRow


def test_make_session_title_first_sentence() -> None:
    assert make_session_title("你好，请介绍一下你自己") == "你好，请介绍一下你自己"
    title = make_session_title("什么是 CRISPR？请详细说明原理。")
    assert title.startswith("什么是 CRISPR")
    assert len(title) <= 36
    assert is_placeholder_title("Web 会话")
    assert is_placeholder_title("新会话")
    assert is_placeholder_title("Streamlit 会话")
    assert not is_placeholder_title("什么是 CRISPR")
    preview = make_session_preview("你好，请介绍一下你自己")
    assert "介绍" in preview


def test_add_qa_pair_replaces_web_session_title() -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    sess = create_session(db, title="Web 会话")
    add_qa_pair(db, sess.id, "你好，请介绍一下你自己")
    row = db.get(SessionRow, sess.id)
    assert row is not None
    assert row.title == "你好，请介绍一下你自己"
    db.close()


def test_custom_title_not_overwritten() -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    sess = create_session(db, title="我的专题研究")
    add_qa_pair(db, sess.id, "另一问题")
    row = db.execute(select(SessionRow).where(SessionRow.id == sess.id)).scalar_one()
    assert row.title == "我的专题研究"
    db.close()
