import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc)

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    nickname: Mapped[str | None] = mapped_column(String(40), unique=True, index=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    name: Mapped[str] = mapped_column(String(120), default="Пользователь")
    timezone: Mapped[str] = mapped_column(String(80), default="Europe/Moscow")

class Project(Base, TimestampMixin):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160)); description: Mapped[str] = mapped_column(Text, default="")
    color: Mapped[str] = mapped_column(String(20), default="#5577e7"); priority: Mapped[str] = mapped_column(String(2), default="P3"); team_label: Mapped[str] = mapped_column(String(100), default="", index=True)

class KanbanColumn(Base):
    __tablename__ = "kanban_columns"; __table_args__ = (UniqueConstraint("project_id", "position"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100)); position: Mapped[int] = mapped_column(Integer)

class Task(Base, TimestampMixin):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    column_id: Mapped[str | None] = mapped_column(ForeignKey("kanban_columns.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(500), index=True); description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="planned"); priority: Mapped[str] = mapped_column(String(2), default="P3")
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60); all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    location: Mapped[str] = mapped_column(String(300), default=""); tags: Mapped[list] = mapped_column(JSON, default=list)
    mentions: Mapped[list] = mapped_column(JSON, default=list); recurrence_rule: Mapped[str] = mapped_column(String(300), default="")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True); sync_version: Mapped[int] = mapped_column(Integer, default=1)

class Reminder(Base):
    __tablename__ = "reminders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    offset_minutes: Mapped[int] = mapped_column(Integer); channel: Mapped[str] = mapped_column(String(30), default="internal")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class TaskTemplate(Base, TimestampMixin):
    __tablename__ = "task_templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160)); icon: Mapped[str] = mapped_column(String(10), default="✦"); description: Mapped[str] = mapped_column(Text, default="")
    duration: Mapped[int] = mapped_column(Integer, default=60); priority: Mapped[str] = mapped_column(String(2), default="P3"); location: Mapped[str] = mapped_column(String(300), default="")
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True); reminders: Mapped[list] = mapped_column(JSON, default=list)

class ActivityLog(Base):
    __tablename__ = "activity_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True); action: Mapped[str] = mapped_column(String(80)); changes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class CalendarConnection(Base, TimestampMixin):
    __tablename__ = "calendar_connections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(30), default="google"); access_token_encrypted: Mapped[str] = mapped_column(Text, default=""); refresh_token_encrypted: Mapped[str] = mapped_column(Text, default=""); external_account_id: Mapped[str] = mapped_column(String(300), default="")
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="connected")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class CalendarEventLink(Base):
    __tablename__="calendar_event_links"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);task_id:Mapped[str]=mapped_column(ForeignKey("tasks.id",ondelete="CASCADE"),index=True);calendar_connection_id:Mapped[str]=mapped_column(ForeignKey("calendar_connections.id",ondelete="CASCADE"),index=True)
    external_calendar_id:Mapped[str]=mapped_column(String(300),default="primary");external_event_id:Mapped[str]=mapped_column(String(500));external_updated_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);last_synced_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True);sync_status:Mapped[str]=mapped_column(String(30),default="synced")

class ExternalCalendarEvent(Base, TimestampMixin):
    __tablename__="external_calendar_events";__table_args__=(UniqueConstraint("calendar_connection_id","external_event_id"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    calendar_connection_id:Mapped[str]=mapped_column(ForeignKey("calendar_connections.id",ondelete="CASCADE"),index=True)
    external_calendar_id:Mapped[str]=mapped_column(String(300),default="primary")
    external_event_id:Mapped[str]=mapped_column(String(500),index=True)
    title:Mapped[str]=mapped_column(String(500),default="")
    description:Mapped[str]=mapped_column(Text,default="")
    location:Mapped[str]=mapped_column(String(300),default="")
    start_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True,index=True)
    end_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    all_day:Mapped[bool]=mapped_column(Boolean,default=False)
    external_updated_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    cancelled:Mapped[bool]=mapped_column(Boolean,default=False)

class Contact(Base):
    __tablename__="contacts";__table_args__=(UniqueConstraint("owner_user_id","contact_user_id"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);owner_user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);contact_user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);nickname:Mapped[str]=mapped_column(String(120),default="");tags:Mapped[list]=mapped_column(JSON,default=list);status:Mapped[str]=mapped_column(String(30),default="accepted");created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ProjectRole(Base):
    __tablename__="project_roles";__table_args__=(UniqueConstraint("project_id","name"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);project_id:Mapped[str]=mapped_column(ForeignKey("projects.id",ondelete="CASCADE"),index=True);name:Mapped[str]=mapped_column(String(80));color:Mapped[str]=mapped_column(String(20),default="#7b818b");permissions:Mapped[list]=mapped_column(JSON,default=list);position:Mapped[int]=mapped_column(Integer,default=0)

class ProjectMember(Base):
    __tablename__="project_members";__table_args__=(UniqueConstraint("project_id","user_id"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);project_id:Mapped[str]=mapped_column(ForeignKey("projects.id",ondelete="CASCADE"),index=True);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);role_id:Mapped[str]=mapped_column(ForeignKey("project_roles.id",ondelete="RESTRICT"));joined_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ProjectMemberRole(Base):
    __tablename__="project_member_roles";__table_args__=(UniqueConstraint("member_id","role_id"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);member_id:Mapped[str]=mapped_column(ForeignKey("project_members.id",ondelete="CASCADE"),index=True);role_id:Mapped[str]=mapped_column(ForeignKey("project_roles.id",ondelete="CASCADE"),index=True)

class ChatChannel(Base):
    __tablename__="chat_channels";__table_args__=(UniqueConstraint("project_id","name"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);project_id:Mapped[str]=mapped_column(ForeignKey("projects.id",ondelete="CASCADE"),index=True);name:Mapped[str]=mapped_column(String(100));description:Mapped[str]=mapped_column(String(300),default="");position:Mapped[int]=mapped_column(Integer,default=0);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class ChatMessage(Base):
    __tablename__="chat_messages"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);channel_id:Mapped[str]=mapped_column(ForeignKey("chat_channels.id",ondelete="CASCADE"),index=True);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);content:Mapped[str]=mapped_column(Text,default="");attached_task_id:Mapped[str|None]=mapped_column(ForeignKey("tasks.id",ondelete="SET NULL"),nullable=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now);updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now);deleted_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class DirectChat(Base):
    __tablename__="direct_chats"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);created_by:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now);updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)

class DirectChatMember(Base):
    __tablename__="direct_chat_members";__table_args__=(UniqueConstraint("chat_id","user_id"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);chat_id:Mapped[str]=mapped_column(ForeignKey("direct_chats.id",ondelete="CASCADE"),index=True);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);joined_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class DirectMessage(Base):
    __tablename__="direct_messages"
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid);chat_id:Mapped[str]=mapped_column(ForeignKey("direct_chats.id",ondelete="CASCADE"),index=True);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);content:Mapped[str]=mapped_column(Text);created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now);updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now);deleted_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
