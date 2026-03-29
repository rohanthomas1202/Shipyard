"""Tests for Planner v2 validation gates."""
# ---------------------------------------------------------------------------
import pytest

from agent.planner_v2.models import (
    PRDModule,
    PRDOutput,
    ContractDefinition,
    TechSpecModule,
    TechSpecOutput,
    PlannedTask,
    PlannedEdge,
    TaskDAGOutput,
)
from agent.planner_v2.validation import (
    validate_prd,
    validate_tech_spec,
    validate_task_dag,
    estimate_cost,
    ValidationError,
)
from agent.analyzer.models import ModuleMap, ModuleInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(
    task_id: str = "t1",
    label: str = "Task 1",
    description: str = "Do something",
    estimated_loc: int = 100,
    target_files: list[str] | None = None,
    contract_inputs: list[str] | None = None,
    contract_outputs: list[str] | None = None,
    indivisible: bool = False,
    indivisible_justification: str | None = None,
) -> PlannedTask:
    return PlannedTask(
        id=task_id,
        label=label,
        description=description,
        estimated_loc=estimated_loc,
        target_files=target_files or [],
        contract_inputs=contract_inputs or [],
        contract_outputs=contract_outputs or [],
        indivisible=indivisible,
        indivisible_justification=indivisible_justification,
    )


# ---------------------------------------------------------------------------
# validate_task_dag tests
# ---------------------------------------------------------------------------

def test_validate_task_dag_loc_exceeds_300_no_indivisible():
    """Task with estimated_loc > 300 and indivisible=False returns error."""
    task = _make_task(estimated_loc=400, indivisible=False)
    dag = TaskDAGOutput(tasks=[task], edges=[])
    spec = TechSpecOutput(modules=[], contracts=[])
    errors = validate_task_dag(dag, spec)
    assert any("300 LOC" in e.message for e in errors)


def test_validate_task_dag_loc_exceeds_300_with_indivisible():
    """Task with estimated_loc > 300 and indivisible=True returns NO error."""
    task = _make_task(
        estimated_loc=400,
        indivisible=True,
        indivisible_justification="Tightly coupled migration",
    )
    dag = TaskDAGOutput(tasks=[task], edges=[])
    spec = TechSpecOutput(modules=[], contracts=[])
    errors = validate_task_dag(dag, spec)
    assert not any("300 LOC" in e.message for e in errors)


def test_validate_task_dag_files_exceeds_3_no_indivisible():
    """Task with >3 target_files and indivisible=False returns error."""
    task = _make_task(
        target_files=["a.py", "b.py", "c.py", "d.py"],
        indivisible=False,
    )
    dag = TaskDAGOutput(tasks=[task], edges=[])
    spec = TechSpecOutput(modules=[], contracts=[])
    errors = validate_task_dag(dag, spec)
    assert any("files" in e.message.lower() for e in errors)


def test_validate_task_dag_detects_cycles():
    """Cycle A->B->A is detected."""
    task_a = _make_task(task_id="A", label="A")
    task_b = _make_task(task_id="B", label="B")
    edges = [
        PlannedEdge(from_task="A", to_task="B"),
        PlannedEdge(from_task="B", to_task="A"),
    ]
    dag = TaskDAGOutput(tasks=[task_a, task_b], edges=edges)
    spec = TechSpecOutput(modules=[], contracts=[])
    errors = validate_task_dag(dag, spec)
    assert any("cycle" in e.message.lower() for e in errors)


def test_validate_task_dag_flags_unknown_contract():
    """Task referencing unknown contract_input is flagged."""
    task = _make_task(contract_inputs=["nonexistent_contract"])
    dag = TaskDAGOutput(tasks=[task], edges=[])
    spec = TechSpecOutput(
        modules=[],
        contracts=[
            ContractDefinition(name="real_contract", contract_type="api", content="{}"),
        ],
    )
    errors = validate_task_dag(dag, spec)
    assert any("unknown contract" in e.message.lower() for e in errors)


def test_validate_task_dag_valid_dag_passes():
    """Valid acyclic DAG with bounded tasks passes validation."""
    task_a = _make_task(task_id="A", label="A", estimated_loc=100)
    task_b = _make_task(task_id="B", label="B", estimated_loc=200)
    edges = [PlannedEdge(from_task="A", to_task="B")]
    dag = TaskDAGOutput(tasks=[task_a, task_b], edges=edges)
    spec = TechSpecOutput(modules=[], contracts=[])
    errors = validate_task_dag(dag, spec)
    assert len(errors) == 0


# ---------------------------------------------------------------------------
# validate_prd tests
# ---------------------------------------------------------------------------

def test_validate_prd_unknown_dependency():
    """PRD module referencing non-existent dependency returns error."""
    prd = PRDOutput(
        project_name="test",
        overview="test",
        modules=[
            PRDModule(
                name="auth",
                description="Auth module",
                depends_on=["nonexistent_module"],
            ),
        ],
        build_order=["auth"],
    )
    module_map = ModuleMap(
        project_path="/tmp",
        modules=[ModuleInfo(name="auth", path="/tmp/auth")],
    )
    errors = validate_prd(prd, module_map)
    assert any("unknown module" in e.message.lower() for e in errors)


# ---------------------------------------------------------------------------
# validate_tech_spec tests
# ---------------------------------------------------------------------------

def test_validate_tech_spec_unknown_contract_input():
    """Tech Spec module referencing unknown contract_input returns error."""
    prd = PRDOutput(project_name="test", overview="test")
    spec = TechSpecOutput(
        modules=[
            TechSpecModule(
                name="auth",
                contract_inputs=["missing_contract"],
            ),
        ],
        contracts=[
            ContractDefinition(name="user_schema", contract_type="db_schema", content=""),
        ],
    )
    errors = validate_tech_spec(spec, prd)
    assert any("unknown contract" in e.message.lower() for e in errors)


# ---------------------------------------------------------------------------
# estimate_cost tests
# ---------------------------------------------------------------------------

def test_estimate_cost_returns_sum_loc_times_50():
    """estimate_cost returns sum(estimated_loc * 50) for all tasks."""
    task_a = _make_task(task_id="A", estimated_loc=100)
    task_b = _make_task(task_id="B", estimated_loc=200)
    dag = TaskDAGOutput(tasks=[task_a, task_b], edges=[])
    cost = estimate_cost(dag)
    assert cost == (100 + 200) * 50
