from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base
from ..models import uid, now

class AIAccess(Base):
    __tablename__ = "ai_access"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class AIConversation(Base):
    __tablename__ = "ai_conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120), default="Новый диалог")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class AIRequest(Base):
    __tablename__ = "ai_requests"
    __table_args__ = (UniqueConstraint("user_id", "request_key", name="uq_ai_request_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("ai_conversations.id", ondelete="SET NULL"), nullable=True)
    request_key: Mapped[str] = mapped_column(String(36))
    prompt: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="running")
    provider: Mapped[str] = mapped_column(String(30))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class AIProposal(Base):
    __tablename__ = "ai_proposals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    request_id: Mapped[str] = mapped_column(ForeignKey("ai_requests.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    expected_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    changes: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    result_task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class AIQuota(Base):
    __tablename__ = "ai_quotas"
    scope: Mapped[str] = mapped_column(String(60), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    requests: Mapped[int] = mapped_column(Integer, default=0)
