"""ORM 模型：平台配置、会话、问答对、平台回答。"""

import uuid
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """声明式基类。"""


def _uuid() -> str:
    return str(uuid.uuid4())


class PlatformConfigRow(Base):
    """运行时平台配置（可增删改）。"""

    __tablename__ = "platform_configs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    icon: Mapped[str] = mapped_column(String(256), default="")
    group: Mapped[str] = mapped_column(String(64), default="custom")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=120)
    # 选择器与交互：存 JSON（SQLite 下 JSON 类型可用）
    selectors: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    interaction: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    adapter_type: Mapped[str] = mapped_column(String(32), default="generic")
    adapter_module: Mapped[str] = mapped_column(String(512), default="")
    health_status: Mapped[str] = mapped_column(String(32), default="unknown")
    health_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # 账号绑定：logged_in / logged_out / unknown；不保存密码，仅记录 CDP 检测结果
    login_status: Mapped[str] = mapped_column(String(32), default="unknown")
    login_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    login_message: Mapped[str] = mapped_column(Text, default="")
    # 服务网址校验：valid / invalid / unknown
    url_status: Mapped[str] = mapped_column(String(32), default="unknown")
    url_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    url_check_message: Mapped[str] = mapped_column(Text, default="")
    expected_host: Mapped[str] = mapped_column(String(256), default="")
    # web_only：只走网页；api_only：只走官方 API；web_with_api_fallback：网页失败后降级
    execution_mode: Mapped[str] = mapped_column(String(32), default="web_only")
    api_provider: Mapped[str] = mapped_column(String(64), default="")
    api_model: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SessionRow(Base):
    """用户问答会话。"""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(512), default="")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    qa_pairs: Mapped[List["QAPairRow"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class QAPairRow(Base):
    """一轮用户提问及多平台回答。"""

    __tablename__ = "qa_pairs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    question_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # 缓存 LLM/本地整理后的最优解，避免每次打开历史都重新计费
    optimal_answer: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    session: Mapped["SessionRow"] = relationship(back_populates="qa_pairs")
    answers: Mapped[List["PlatformAnswerRow"]] = relationship(
        back_populates="qa_pair", cascade="all, delete-orphan"
    )


class PlatformAnswerRow(Base):
    """单个平台对某次提问的回答快照。"""

    __tablename__ = "platform_answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    qa_pair_id: Mapped[str] = mapped_column(String(36), ForeignKey("qa_pairs.id"), nullable=False)
    platform_id: Mapped[str] = mapped_column(String(64), nullable=False)
    platform_name: Mapped[str] = mapped_column(String(256), nullable=False)
    platform_url: Mapped[str] = mapped_column(String(2048), default="")
    answer_text: Mapped[str] = mapped_column(Text, default="")
    request_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_token_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    response_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    error_message: Mapped[str] = mapped_column(Text, default="")
    tokens_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    qa_pair: Mapped["QAPairRow"] = relationship(back_populates="answers")


class ShareLinkRow(Base):
    """只读分享链接：通过 token 查看整段会话（不含修改权限）。"""

    __tablename__ = "share_links"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
