"""会话与问答对管理。"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from oneqmultia.storage.models import QAPairRow, SessionRow

# 前端/历史占位标题：有真实问题后应被首问摘要替换
_PLACEHOLDER_TITLES = frozenset(
    {
        "",
        "新对话",
        "新会话",
        "Web 会话",
        "自动会话",
        "未命名",
        "未命名会话",
        "Streamlit 会话",
        "Streamlit 自动会话",
    }
)


def is_placeholder_title(title: Optional[str]) -> bool:
    """判断标题是否为占位文案，无法区分会话主题。"""
    return (title or "").strip() in _PLACEHOLDER_TITLES


def make_session_title(question: str, *, max_len: int = 36) -> str:
    """
    用首问生成可扫读的会话标题：压空白、取首句、超长截断。
    """
    text = " ".join((question or "").split())
    if not text:
        return "未命名会话"
    for sep in ("。", "？", "?", "！", "!", "\n"):
        if sep in text:
            text = text.split(sep, 1)[0].strip()
            break
    if len(text) > max_len:
        return text[:max_len].rstrip() + "…"
    return text


def make_session_preview(question: str, *, max_len: int = 48) -> str:
    """历史列表副标题：保留更多问题原文，便于区分同主题多轮。"""
    text = " ".join((question or "").split())
    if not text:
        return ""
    if len(text) > max_len:
        return text[:max_len].rstrip() + "…"
    return text


def maybe_update_session_title(sess: SessionRow, question: str) -> bool:
    """占位标题或空标题时，用问题摘要覆盖。返回是否改写。"""
    if not is_placeholder_title(sess.title):
        return False
    new_title = make_session_title(question)
    if new_title and new_title != sess.title:
        sess.title = new_title
        return True
    return False


def create_session(db: Session, title: str = "") -> SessionRow:
    """新建会话。"""
    sid = str(uuid.uuid4())
    row = SessionRow(id=sid, title=title or "新对话")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_session(db: Session, session_id: str) -> Optional[SessionRow]:
    """按 id 获取会话。"""
    return db.get(SessionRow, session_id)


def add_qa_pair(db: Session, session_id: str, question: str) -> QAPairRow:
    """在会话下新增一轮提问，并用首问（或占位标题）刷新会话标题。"""
    qid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    row = QAPairRow(
        id=qid,
        session_id=session_id,
        question=question,
        question_time=now,
    )
    db.add(row)
    sess = get_session(db, session_id)
    if sess:
        sess.updated_at = now
        maybe_update_session_title(sess, question)
    db.commit()
    db.refresh(row)
    return row


def load_session_with_qa(db: Session, session_id: str) -> Optional[SessionRow]:
    """加载会话及问答对、回答。"""
    stmt = (
        select(SessionRow)
        .where(SessionRow.id == session_id)
        .options(
            selectinload(SessionRow.qa_pairs).selectinload(QAPairRow.answers),
        )
    )
    return db.execute(stmt).scalar_one_or_none()
