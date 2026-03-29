"""Integration tests for the three-layer planning pipeline with mocked LLM calls."""
import copy
from unittest.mock import AsyncMock

import pytest

from agent.analyzer.models import ModuleMap, ModuleInfo, FileInfo, DependencyEdge
from agent.planner_v2.models import (
    PRDOutput, PRDModule,
    TechSpecOutput, TechSpecModule, ContractDefinition,
    TaskDAGOutput, PlannedTask, PlannedEdge,
    PipelineResult,
)
from agent.planner_v2.prd import generate_prd, render_prd_markdown
from agent.planner_v2.tech_spec import generate_tech_spec, render_tech_spec_markdown
from agent.planner_v2.dag_builder import generate_task_dag, build_orchestrator_dag
from agent.planner_v2.pipeline import run_pipeline, PlanValidationError
from agent.router import ModelRouter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_PRD = PRDOutput(
    project_name="ship-fixture",
    overview="Test project",
    modules=[
        PRDModule(
            name="types",
            description="Shared types",
            responsibilities=["Define interfaces"],
            depends_on=[],
            estimated_complexity="low",
        ),
        PRDModule(
            name="models",
            description="Data models",
            responsibilities=["User CRUD"],
            depends_on=["types"],
            estimated_complexity="medium",
        ),
        PRDModule(
            name="routes",
            description="API routes",
            responsibilities=["HTTP handlers"],
            depends_on=["models", "types"],
            estimated_complexity="medium",
        ),
    ],
    build_order=["types", "models", "routes"],
)

MOCK_SPEC = TechSpecOutput(
    modules=[
        TechSpecModule(name="types", contract_outputs=["shared_types"]),
        TechSpecModule(
            name="models",
            contract_inputs=["shared_types"],
            contract_outputs=["db_schema"],
        ),
        TechSpecModule(
            name="routes",
            contract_inputs=["shared_types", "db_schema"],
        ),
    ],
    contracts=[
        ContractDefinition(
            name="shared_types",
            contract_type="shared_types",
            content="interface User {...}",
        ),
        ContractDefinition(
            name="db_schema",
            contract_type="db_schema",
            content="CREATE TABLE users (...)",
        ),
    ],
)

MOCK_DAG = TaskDAGOutput(
    tasks=[
        PlannedTask(
            id="task-1",
            label="Create shared types",
            description="Define TypeScript interfaces",
            target_files=["src/types/index.ts"],
            estimated_loc=50,
            contract_outputs=["shared_types"],
        ),
        PlannedTask(
            id="task-2",
            label="Create user model",
            description="Implement User model",
            target_files=["src/models/user.ts"],
            estimated_loc=80,
            contract_inputs=["shared_types"],
            contract_outputs=["db_schema"],
            depends_on=["task-1"],
        ),
        PlannedTask(
            id="task-3",
            label="Create user routes",
            description="Implement user API routes",
            target_files=["src/routes/users.ts"],
            estimated_loc=120,
            contract_inputs=["shared_types", "db_schema"],
            depends_on=["task-2"],
        ),
    ],
    edges=[
        PlannedEdge(from_task="task-1", to_task="task-2"),
        PlannedEdge(from_task="task-2", to_task="task-3"),
    ],
)

MODULE_MAP = ModuleMap(
    project_path="/tmp/ship",
    modules=[
        ModuleInfo(
            name="types",
            path="src/types",
            files=[FileInfo(path="src/types/index.ts", loc=30)],
        ),
        ModuleInfo(
            name="models",
            path="src/models",
            files=[FileInfo(path="src/models/user.ts", loc=60)],
            dependencies=["types"],
        ),
        ModuleInfo(
            name="routes",
            path="src/routes",
            files=[FileInfo(path="src/routes/users.ts", loc=90)],
            dependencies=["models", "types"],
        ),
    ],
    edges=[
        DependencyEdge(source="models", target="types"),
        DependencyEdge(source="routes", target="models"),
        DependencyEdge(source="routes", target="types"),
    ],
    total_files=3,
    total_loc=180,
)


def _mock_router() -> ModelRouter:
    """Build a ModelRouter with call_structured mocked to return fixtures."""
    router = ModelRouter.__new__(ModelRouter)

    async def _side_effect(task_type: str, system: str, user: str, response_model=None):
        if task_type == "plan_prd":
            return copy.deepcopy(MOCK_PRD)
        elif task_type == "plan_spec":
            return copy.deepcopy(MOCK_SPEC)
        elif task_type == "plan_dag":
            return copy.deepcopy(MOCK_DAG)
        raise ValueError(f"Unexpected task_type: {task_type}")

    router.call_structured = AsyncMock(side_effect=_side_effect)
    return router


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prd_generation():
    """PLAN-01: generate_prd returns a PRDOutput from a ModuleMap."""
    router = _mock_router()
    result = await generate_prd(MODULE_MAP, router)
    assert result.project_name == "ship-fixture"
    assert len(result.modules) == 3
    router.call_structured.assert_called_once()
    call_args = router.call_structured.call_args
    assert call_args[0][0] == "plan_prd"


@pytest.mark.asyncio
async def test_tech_spec_generation():
    """PLAN-02: generate_tech_spec returns a TechSpecOutput."""
    router = _mock_router()
    result = await generate_tech_spec(MOCK_PRD, MODULE_MAP, router)
    assert len(result.contracts) == 2
    contract_names = {c.name for c in result.contracts}
    assert "shared_types" in contract_names
    assert "db_schema" in contract_names
    call_args = router.call_structured.call_args
    assert call_args[0][0] == "plan_spec"


@pytest.mark.asyncio
async def test_task_dag_bounds():
    """PLAN-03: generate_task_dag returns bounded tasks."""
    router = _mock_router()
    result = await generate_task_dag(MOCK_SPEC, router)
    for task in result.tasks:
        assert task.estimated_loc <= 300
        assert len(task.target_files) <= 3
    assert len(result.tasks) == 3
    assert len(result.edges) == 2


@pytest.mark.asyncio
async def test_full_pipeline():
    """Full pipeline produces PipelineResult with all three layers."""
    router = _mock_router()
    result = await run_pipeline(MODULE_MAP, router)
    assert isinstance(result, PipelineResult)
    assert result.prd is not None
    assert result.spec is not None
    assert result.dag is not None
    # Cost: (50 + 80 + 120) * 50 = 12500
    assert result.estimated_total_tokens == 12500
    assert router.call_structured.call_count == 3


@pytest.mark.asyncio
async def test_pipeline_rejects_cycle():
    """Pipeline raises PlanValidationError for cyclic DAGs."""
    cyclic_dag = TaskDAGOutput(
        tasks=[
            PlannedTask(
                id="task-1",
                label="Task A",
                description="A",
                target_files=["a.ts"],
                estimated_loc=50,
            ),
            PlannedTask(
                id="task-2",
                label="Task B",
                description="B",
                target_files=["b.ts"],
                estimated_loc=50,
            ),
        ],
        edges=[
            PlannedEdge(from_task="task-1", to_task="task-2"),
            PlannedEdge(from_task="task-2", to_task="task-1"),
        ],
    )

    router = ModelRouter.__new__(ModelRouter)

    async def _cycle_side_effect(task_type, system, user, response_model=None):
        if task_type == "plan_prd":
            return copy.deepcopy(MOCK_PRD)
        elif task_type == "plan_spec":
            return copy.deepcopy(MOCK_SPEC)
        elif task_type == "plan_dag":
            return copy.deepcopy(cyclic_dag)
        raise ValueError(f"Unexpected: {task_type}")

    router.call_structured = AsyncMock(side_effect=_cycle_side_effect)

    with pytest.raises(PlanValidationError) as exc_info:
        await run_pipeline(MODULE_MAP, router)
    assert "cycles" in str(exc_info.value).lower()


def test_build_orchestrator_dag():
    """build_orchestrator_dag converts TaskDAGOutput to Phase 12 TaskDAG."""
    dag = build_orchestrator_dag(MOCK_DAG, dag_id="test-dag")
    assert dag.task_count == 3
    assert dag.edge_count == 2
    assert dag.validate() is True
    node = dag.get_task("task-1")
    assert node is not None
    assert node.label == "Create shared types"


def test_prd_markdown_rendering():
    """render_prd_markdown produces expected markdown sections."""
    md = render_prd_markdown(MOCK_PRD)
    assert "# PRD:" in md
    assert "## Modules" in md
    assert "### types" in md
    assert "### models" in md
    assert "## Build Order" in md


def test_tech_spec_markdown_rendering():
    """render_tech_spec_markdown produces expected markdown sections."""
    md = render_tech_spec_markdown(MOCK_SPEC)
    assert "# Tech Spec" in md
    assert "### shared_types" in md
    assert "### db_schema" in md
