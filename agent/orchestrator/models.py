"""Pydantic models for the orchestrator DAG engine and contract layer."""
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from typing import Literal
import uuid


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TaskNode(BaseModel):
    id: str = Field(default_factory=_new_id)
    dag_id: str = ""
    label: str = ""
    description: str | None = None
    task_type: str = "agent"
    contract_inputs: list[str] = Field(default_factory=list)
    contract_outputs: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)


class TaskEdge(BaseModel):
    id: str = Field(default_factory=_new_id)
    dag_id: str = ""
    from_task: str = ""
    to_task: str = ""


class TaskExecution(BaseModel):
    id: str = Field(default_factory=_new_id)
    dag_id: str = ""
    task_id: str = ""
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    attempt: int = 1
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    result_summary: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)


class DAGRun(BaseModel):
    id: str = Field(default_factory=_new_id)
    project_id: str = ""
    status: Literal["pending", "running", "completed", "failed", "paused"] = "pending"
    max_concurrency: int = 10
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    created_at: datetime = Field(default_factory=_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
