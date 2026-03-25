"""Typed plan step schema and parsing utilities."""
import json
from pydantic import BaseModel, field_validator
from typing import Literal


class PlanStep(BaseModel):
    id: str
    kind: Literal["read", "edit", "exec", "test", "git"]
    target_files: list[str] = []
    command: str | None = None
    acceptance_criteria: list[str] = []
    complexity: Literal["simple", "complex"]
    depends_on: list[str] = []

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        allowed = {"read", "edit", "exec", "test", "git"}
        if v not in allowed:
            raise ValueError(f"kind must be one of {allowed}, got '{v}'")
        return v

    @field_validator("complexity")
    @classmethod
    def validate_complexity(cls, v: str) -> str:
        allowed = {"simple", "complex"}
        if v not in allowed:
            raise ValueError(f"complexity must be one of {allowed}, got '{v}'")
        return v


def parse_plan_steps(raw: str) -> list[PlanStep]:
    """Parse LLM output into typed PlanStep objects. Fallback on parse failure."""
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [PlanStep(**item) for item in data]
        if isinstance(data, dict) and "steps" in data:
            return [PlanStep(**item) for item in data["steps"]]
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    return [PlanStep(
        id="fallback-1",
        kind="exec",
        command=raw.strip(),
        complexity="complex",
    )]
