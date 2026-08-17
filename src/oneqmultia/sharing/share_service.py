"""生成与解析分享 token。"""

import secrets
from typing import Optional

from sqlalchemy.orm import Session

from oneqmultia.core.session_manager import get_session, load_session_with_qa
from oneqmultia.storage.models import SessionRow, ShareLinkRow


def create_share_link(db: Session, session_id: str) -> str:
    """为会话创建分享 token（可重复创建多条，各自独立）。"""
    if get_session(db, session_id) is None:
        raise ValueError("session not found")
    token = secrets.token_urlsafe(24)
    row = ShareLinkRow(token=token, session_id=session_id)
    db.add(row)
    db.commit()
    return token


def resolve_shared_session(db: Session, token: str) -> Optional[SessionRow]:
    """根据 token 加载会话及问答（只读展示）。"""
    link = db.get(ShareLinkRow, token)
    if link is None:
        return None
    return load_session_with_qa(db, link.session_id)
