"""Integration tests validating Shipyard agent handles Ship-like TypeScript/React codebases."""
import json
import os
import shutil
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.nodes.reader import reader_node
from agent.nodes.editor import editor_node
from agent.nodes.planner import planner_node
from agent.models import ModelConfig

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "ship_sample_project")


@pytest.fixture
def ship_project_dir():
    """Copy the Ship sample fixture into a temp directory so edits don't mutate fixtures."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dest = os.path.join(tmpdir, "ship_sample_project")
        shutil.copytree(FIXTURE_DIR, dest)
        yield dest


@pytest.fixture
def mock_router():
    """Create a ModelRouter mock with pre-canned responses by task_type."""
    router = MagicMock()

    # resolve_model returns a realistic ModelConfig for context budget calculations
    router.resolve_model.return_value = ModelConfig(
        id="gpt-4o",
        context_window=128_000,
        max_output=16_384,
        tier="general",
        timeout=60,
    )
    router.resolve_escalation.return_value = None

    async def mock_call(task_type, system, user):
        if task_type == "plan":
            return json.dumps([
                {
                    "id": "step-1",
                    "kind": "read",
                    "target_files": ["src/types/index.ts"],
                    "acceptance_criteria": ["Read the Document interface"],
                    "complexity": "simple",
                },
                {
                    "id": "step-2",
                    "kind": "edit",
                    "target_files": ["src/types/index.ts"],
                    "acceptance_criteria": ["Add status field to Document interface"],
                    "complexity": "simple",
                },
            ])
        if task_type in ("edit_simple", "edit_complex"):
            return json.dumps({
                "anchor": "  updated_at: string;\n}",
                "replacement": "  updated_at: string;\n  status: 'active' | 'archived';\n}",
            })
        if task_type == "read":
            return "File summary: Express health route with GET /health endpoint"
        if task_type == "validate":
            return "no errors found"
        return ""

    async def mock_call_structured(task_type, system, user, response_model):
        """Return a mock EditResponse-like object for structured calls."""
        mock_response = MagicMock()
        mock_response.anchor = "  updated_at: string;\n}"
        mock_response.replacement = "  updated_at: string;\n  status: 'active' | 'archived';\n}"
        return mock_response

    router.call = AsyncMock(side_effect=mock_call)
    router.call_structured = AsyncMock(side_effect=mock_call_structured)
    return router


def _base_state(working_dir: str) -> dict:
    """Build a minimal AgentState-compatible dict."""
    return {
        "messages": [],
        "instruction": "",
        "working_directory": working_dir,
        "context": {},
        "plan": [],
        "current_step": 0,
        "file_buffer": {},
        "file_hashes": {},
        "edit_history": [],
        "error_state": None,
        "last_validation_error": None,
        "validation_error_history": [],
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
        "model_usage": {},
        "autonomy_mode": "autonomous",
        "ast_available": {},
        "invalidated_files": [],
    }


# ---------------------------------------------------------------------------
# Test 1: Reader node reads TypeScript files from fixture project
# ---------------------------------------------------------------------------

def test_agent_reads_typescript_files(ship_project_dir):
    """Verify reader_node loads .ts files from a Ship-like project into file_buffer."""
    health_ts = os.path.join(ship_project_dir, "src", "routes", "health.ts")

    state = _base_state(ship_project_dir)
    state["instruction"] = "Read the health route"
    state["plan"] = [
        {
            "id": "step-1",
            "kind": "read",
            "target_files": [health_ts],
            "acceptance_criteria": ["Read the health route file"],
            "complexity": "simple",
        }
    ]
    state["current_step"] = 0

    result = reader_node(state)

    assert "file_buffer" in result
    assert health_ts in result["file_buffer"]
    content = result["file_buffer"][health_ts]
    assert "Router" in content
    assert "/health" in content
    assert "file_hashes" in result
    assert health_ts in result["file_hashes"]


# ---------------------------------------------------------------------------
# Test 2: Editor node edits a TypeScript file with anchor-based replacement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_edits_typescript_file(ship_project_dir, mock_router):
    """Verify editor_node applies an anchor-based edit to a .ts file."""
    types_ts = os.path.join(ship_project_dir, "src", "types", "index.ts")
    with open(types_ts, "r") as f:
        original_content = f.read()

    state = _base_state(ship_project_dir)
    state["instruction"] = "Add status field to Document"
    state["plan"] = [
        {
            "id": "step-1",
            "kind": "edit",
            "target_files": [types_ts],
            "acceptance_criteria": ["Add status field to Document interface"],
            "complexity": "simple",
        }
    ]
    state["current_step"] = 0
    state["file_buffer"] = {types_ts: original_content}

    config = {"configurable": {"router": mock_router}}

    result = await editor_node(state, config)

    # Editor should succeed without error
    assert result.get("error_state") is None, f"Editor error: {result.get('error_state')}"

    # File on disk should now contain the status field
    with open(types_ts, "r") as f:
        edited = f.read()
    assert "status" in edited
    assert "'active'" in edited or '"active"' in edited

    # edit_history should have an entry
    assert len(result.get("edit_history", [])) >= 1


# ---------------------------------------------------------------------------
# Test 3: Planner node produces a valid plan for a Ship-like instruction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_plans_for_ship_task(ship_project_dir, mock_router):
    """Verify planner_node produces a plan with steps targeting .ts files."""
    state = _base_state(ship_project_dir)
    state["instruction"] = "Add a status field to the Document interface"

    config = {"configurable": {"router": mock_router}}

    result = await planner_node(state, config)

    assert "plan" in result
    plan = result["plan"]
    assert len(plan) >= 1, "Plan should have at least 1 step"

    # At least one step should target a .ts file
    has_ts_target = False
    for step in plan:
        for tf in step.get("target_files", []):
            if tf.endswith(".ts"):
                has_ts_target = True
                break
    assert has_ts_target, "Plan should target at least one .ts file"


# ---------------------------------------------------------------------------
# Test 4: Reader handles multiple TypeScript files
# ---------------------------------------------------------------------------

def test_agent_reads_multiple_ts_files(ship_project_dir):
    """Verify reader_node can load multiple Ship-like files in one pass."""
    types_ts = os.path.join(ship_project_dir, "src", "types", "index.ts")
    model_ts = os.path.join(ship_project_dir, "src", "models", "document.ts")

    state = _base_state(ship_project_dir)
    state["plan"] = [
        {
            "id": "step-1",
            "kind": "read",
            "target_files": [types_ts, model_ts],
            "acceptance_criteria": ["Read type definitions and model"],
            "complexity": "simple",
        }
    ]
    state["current_step"] = 0

    result = reader_node(state)

    assert types_ts in result["file_buffer"]
    assert model_ts in result["file_buffer"]
    assert "Document" in result["file_buffer"][types_ts]
    assert "findById" in result["file_buffer"][model_ts]
