"""生成与解析分享 token。"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from oneqmultia.core.session_manager import get_session, load_session_with_qa
from oneqmultia.storage.models import SessionRow, ShareLinkRow

# 允许的有效期。None 表示永久。
_TTL_HOURS = {
    "24h": 24,
    "7d": 24 * 7,
    "30d": 24 * 30,
    "never": None,
}


def normalize_ttl(ttl: Optional[str]) -> Optional[datetime]:
    """把 24h / 7d / 30d / never 换成过期时间。空值按永久处理。"""
    key = (ttl or "never").strip().lower()
    if key not in _TTL_HOURS:
        raise ValueError("ttl 只能是 24h、7d、30d 或 never")
    hours = _TTL_HOURS[key]
    if hours is None:
        return None
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def create_share_link(db: Session, session_id: str, ttl: Optional[str] = None) -> str:
    """为会话创建分享 token。ttl 控制过期时间。"""
    if get_session(db, session_id) is None:
        raise ValueError("session not found")
    token = secrets.token_urlsafe(24)
    row = ShareLinkRow(token=token, session_id=session_id, expires_at=normalize_ttl(ttl), view_count=0)
    db.add(row)
    db.commit()
    return token


def share_link_state(db: Session, token: str) -> str:
    """返回 ok / missing / expired / revoked。"""
    link = db.get(ShareLinkRow, token)
    if link is None:
        return "missing"
    if link.revoked_at is not None:
        return "revoked"
    expires = link.expires_at
    if expires is not None:
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            return "expired"
    return "ok"


def resolve_shared_session(db: Session, token: str) -> Optional[SessionRow]:
    """根据 token 加载会话。过期或撤销时返回 None。"""
    if share_link_state(db, token) != "ok":
        return None
    link = db.get(ShareLinkRow, token)
    if link is None:
        return None
    link.view_count = int(link.view_count or 0) + 1
    db.commit()
    return load_session_with_qa(db, link.session_id)


def revoke_share_link(db: Session, token: str) -> bool:
    """吊销一条分享链接。不存在时返回 False。"""
    link = db.get(ShareLinkRow, token)
    if link is None:
        return False
    link.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return True


def list_share_links(db: Session, session_id: str) -> list[ShareLinkRow]:
    """列出某个会话发出的分享链接。"""
    return list(
        db.query(ShareLinkRow)
        .filter(ShareLinkRow.session_id == session_id)
        .order_by(ShareLinkRow.created_at.desc())
        .all()
    )
