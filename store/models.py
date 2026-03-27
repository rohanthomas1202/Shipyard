"""Pydantic models for persistence layer."""
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from typing import Any, Literal
import uuid


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Project(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str
    path: str
    github_repo: str | None = None
    github_pat: str | None = None
    default_model: str = "gpt-4o"
    autonomy_mode: str = "supervised"
    test_command: str | None = None
    build_command: str | None = None
    lint_command: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Run(BaseModel):
    id: str = Field(default_factory=_new_id)
    project_id: str
    instruction: str
    status: str = "running"
    branch: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    plan: list[dict] = Field(default_factory=list)
    model_usage: dict[str, int] = Field(default_factory=dict)
    total_tokens: int = 0
    trace_url: str | None = None
    created_at: datetime = Field(default_factory=_now)
    completed_at: datetime | None = None


class Event(BaseModel):
    id: str = Field(default_factory=_new_id)
    project_id: str
    run_id: str
    type: str
    seq: int = 0
    node: str | None = None
    model: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


EDIT_STATUSES = Literal["proposed", "approved", "rejected", "applied", "committed"]


class EditRecord(BaseModel):
    id: str = Field(default_factory=_new_id)
    run_id: str
    file_path: str
    step: int = 0
    anchor: str | None = None
    old_content: str | None = None
    new_content: str | None = None
    status: EDIT_STATUSES = "proposed"
    approved_at: datetime | None = None
    last_op_id: str | None = None
    batch_id: str | None = None  # Groups refactor edits for batch approval/rollback


class Conversation(BaseModel):
    id: str = Field(default_factory=_new_id)
    project_id: str
    title: str | None = None
    messages: list[dict] = Field(default_factory=list)
    model: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class GitOperation(BaseModel):
    id: str = Field(default_factory=_new_id)
    run_id: str
    type: str
    branch: str | None = None
    commit_sha: str | None = None
    pr_url: str | None = None
    pr_number: int | None = None
    status: str | None = None
    created_at: datetime = Field(default_factory=_now)
