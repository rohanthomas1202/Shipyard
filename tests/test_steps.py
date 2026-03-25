import pytest
import json
from agent.steps import PlanStep, parse_plan_steps


def test_plan_step_creation():
    step = PlanStep(
        id="step-1",
        kind="edit",
        target_files=["src/auth.ts"],
        complexity="simple",
    )
    assert step.id == "step-1"
    assert step.kind == "edit"
    assert step.target_files == ["src/auth.ts"]
    assert step.complexity == "simple"
    assert step.depends_on == []
    assert step.command is None
    assert step.acceptance_criteria == []


def test_plan_step_valid_kinds():
    for kind in ("read", "edit", "exec", "test", "git"):
        step = PlanStep(id="s", kind=kind, complexity="simple")
        assert step.kind == kind


def test_plan_step_invalid_kind():
    with pytest.raises(ValueError):
        PlanStep(id="s", kind="invalid", complexity="simple")


def test_plan_step_valid_complexities():
    for c in ("simple", "complex"):
        step = PlanStep(id="s", kind="read", complexity=c)
        assert step.complexity == c


def test_plan_step_invalid_complexity():
    with pytest.raises(ValueError):
        PlanStep(id="s", kind="read", complexity="medium")


def test_parse_plan_steps_from_json():
    raw = json.dumps([
        {"id": "1", "kind": "read", "target_files": ["a.ts"], "complexity": "simple"},
        {"id": "2", "kind": "edit", "target_files": ["a.ts"], "complexity": "complex", "depends_on": ["1"]},
    ])
    steps = parse_plan_steps(raw)
    assert len(steps) == 2
    assert steps[0].kind == "read"
    assert steps[1].depends_on == ["1"]


def test_parse_plan_steps_fallback_on_invalid_json():
    steps = parse_plan_steps("just do the thing")
    assert len(steps) == 1
    assert steps[0].kind == "exec"
    assert steps[0].complexity == "complex"
