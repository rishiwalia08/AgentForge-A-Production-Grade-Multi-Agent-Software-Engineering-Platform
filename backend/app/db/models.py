from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


JSONType = JSON().with_variant(JSONB, "postgresql")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    picture_url: Mapped[str] = mapped_column(String(1024), default="")

    projects: Mapped[list["Project"]] = relationship(back_populates="user")
    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user")


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    repo_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    @property
    def owner_id(self) -> str:
        return self.user_id

    user: Mapped[User] = relationship(back_populates="projects")
    threads: Mapped[list["AgentThread"]] = relationship(back_populates="project")


class AgentThread(Base, TimestampMixin):
    __tablename__ = "agent_threads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    thread_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    current_node: Mapped[str] = mapped_column(String(128), default="")
    checkpoint_state: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    last_error: Mapped[str] = mapped_column(Text, default="")

    project: Mapped[Project] = relationship(back_populates="threads")
    runs: Mapped[list["AgentRun"]] = relationship(back_populates="thread")


class AgentRun(Base, TimestampMixin):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    thread_id: Mapped[str] = mapped_column(ForeignKey("agent_threads.thread_id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    input_message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="running")
    supervisor_decision: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    final_state: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")

    thread: Mapped[AgentThread] = relationship(back_populates="runs")
    tool_executions: Mapped[list["ToolExecution"]] = relationship(back_populates="run")
    approval_requests: Mapped[list["ApprovalRequest"]] = relationship(back_populates="run")


class ToolExecution(Base, TimestampMixin):
    __tablename__ = "tool_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("agent_threads.thread_id"), index=True)
    tool_name: Mapped[str] = mapped_column(String(255), index=True)
    tool_args: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    tool_output: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    observation: Mapped[str] = mapped_column(Text, default="")
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)

    run: Mapped[AgentRun] = relationship(back_populates="tool_executions")


class ApprovalRequest(Base, TimestampMixin):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("agent_threads.thread_id"), index=True)
    tool_execution_id: Mapped[str | None] = mapped_column(ForeignKey("tool_executions.id"), nullable=True)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    decision: Mapped[str] = mapped_column(String(32), default="pending")
    decided_by: Mapped[str] = mapped_column(String(255), default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped[AgentRun] = relationship(back_populates="approval_requests")


class MemoryItem(Base, TimestampMixin):
    __tablename__ = "memory_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("agent_threads.thread_id"), index=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)


class UserSession(Base, TimestampMixin):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    access_token_hash: Mapped[str] = mapped_column(String(255))
    refresh_token_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship(back_populates="sessions")


class CheckpointRecord(Base, TimestampMixin):
    __tablename__ = "checkpoint_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    thread_id: Mapped[str] = mapped_column(String(128), index=True)
    checkpoint_id: Mapped[str] = mapped_column(String(128), index=True)
    checkpoint_data: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)

