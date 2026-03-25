import json
import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from agent.nodes.editor import editor_node
from agent.state import AgentState
from store.models import EditRecord, Project, Run
from store.sqlite import SQLiteSessionStore
from agent.approval import ApprovalManager
from agent.events import EventBus


def make_config_with_mock_router(return_value):
    mock_router = MagicMock()
    mock_router.call = AsyncMock(return_value=return_value)
    return {"configurable": {"router": mock_router}}


@pytest.fixture
def sample_state(tmp_codebase):
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    content = open(ts_path).read()
    return {
        "messages": [],
        "instruction": "Add a due_date field to the Issue interface",
        "working_directory": tmp_codebase,
        "context": {},
        "plan": ["Add due_date field to Issue interface in sample.ts"],
        "current_step": 0,
        "file_buffer": {ts_path: content},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
    }


@pytest.mark.asyncio
async def test_editor_node_successful_edit(sample_state, tmp_codebase):
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    mock_response = json.dumps({
        "anchor": '  description: string;\n  status: "open" | "closed";',
        "replacement": '  description: string;\n  due_date: string;\n  status: "open" | "closed";',
    })

    config = make_config_with_mock_router(mock_response)
    result = await editor_node(sample_state, config=config)

    assert result["error_state"] is None
    assert len(result["edit_history"]) == 1
    assert result["edit_history"][0]["file"] == ts_path
    content = open(ts_path).read()
    assert "due_date: string;" in content


@pytest.mark.asyncio
async def test_editor_node_anchor_not_found(sample_state):
    mock_response = json.dumps({
        "anchor": "this does not exist in the file",
        "replacement": "whatever",
    })

    config = make_config_with_mock_router(mock_response)
    result = await editor_node(sample_state, config=config)

    assert result["error_state"] is not None
    assert "not found" in result["error_state"].lower()


# ---------------------------------------------------------------------------
# Approval gate tests
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def approval_store(tmp_path):
    db_path = str(tmp_path / "approval_test.db")
    s = SQLiteSessionStore(db_path)
    await s.initialize()
    yield s
    await s.close()


@pytest_asyncio.fixture
async def approval_manager(approval_store):
    mock_bus = MagicMock()
    mock_bus.emit = AsyncMock()
    # Stub get_run so project_id lookup doesn't fail
    approval_store_orig_get_run = approval_store.get_run

    async def _get_run(run_id):
        run = await approval_store_orig_get_run(run_id)
        return run

    return ApprovalManager(store=approval_store, event_bus=mock_bus)


@pytest_asyncio.fixture
async def run_in_store(approval_store):
    project = Project(name="test", path="/tmp/test")
    await approval_store.create_project(project)
    run = Run(project_id=project.id, instruction="test")
    await approval_store.create_run(run)
    return run


@pytest.mark.asyncio
async def test_editor_node_supervised_mode_returns_waiting(
    sample_state, tmp_codebase, approval_manager, run_in_store
):
    """Supervised mode: proposes edit, returns waiting_for_human=True, file NOT modified."""
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    original_content = open(ts_path).read()

    mock_response = json.dumps({
        "anchor": '  description: string;\n  status: "open" | "closed";',
        "replacement": '  description: string;\n  due_date: string;\n  status: "open" | "closed";',
    })

    mock_router = MagicMock()
    mock_router.call = AsyncMock(return_value=mock_response)
    config = {
        "configurable": {
            "router": mock_router,
            "approval_manager": approval_manager,
            "run_id": run_in_store.id,
            "supervised": True,
        }
    }

    result = await editor_node(sample_state, config=config)

    assert result.get("waiting_for_human") is True
    assert result["error_state"] is None
    # File should NOT be modified in supervised mode
    current_content = open(ts_path).read()
    assert current_content == original_content


@pytest.mark.asyncio
async def test_editor_node_autonomous_mode_applies_edit(
    sample_state, tmp_codebase, approval_manager, run_in_store
):
    """Autonomous mode: proposes + approves + applies, file IS modified."""
    ts_path = os.path.join(tmp_codebase, "sample.ts")

    mock_response = json.dumps({
        "anchor": '  description: string;\n  status: "open" | "closed";',
        "replacement": '  description: string;\n  due_date: string;\n  status: "open" | "closed";',
    })

    mock_router = MagicMock()
    mock_router.call = AsyncMock(return_value=mock_response)
    config = {
        "configurable": {
            "router": mock_router,
            "approval_manager": approval_manager,
            "run_id": run_in_store.id,
            "supervised": False,
        }
    }

    result = await editor_node(sample_state, config=config)

    assert result.get("waiting_for_human") is not True
    assert result["error_state"] is None
    # File SHOULD be modified in autonomous mode
    current_content = open(ts_path).read()
    assert "due_date: string;" in current_content
