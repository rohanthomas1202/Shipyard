import json
import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from agent.nodes.editor import editor_node, _build_error_feedback
from agent.schemas import EditResponse
from agent.state import AgentState
from agent.tools.file_ops import content_hash
from agent.prompts.editor import EDITOR_USER, ERROR_FEEDBACK_TEMPLATE
from store.models import EditRecord, Project, Run
from store.sqlite import SQLiteSessionStore
from agent.approval import ApprovalManager
from agent.events import EventBus


def make_config_with_mock_router(return_value):
    """Legacy helper: mocks both router.call (string) and router.call_structured.

    For simple tier edits, call_structured is used. We parse the return_value
    JSON string to create an EditResponse for call_structured.
    """
    mock_router = MagicMock()
    mock_router.call = AsyncMock(return_value=return_value)
    # Also provide call_structured that returns an EditResponse
    try:
        data = json.loads(return_value)
        edit_resp = EditResponse(anchor=data["anchor"], replacement=data["replacement"])
        mock_router.call_structured = AsyncMock(return_value=edit_resp)
    except (json.JSONDecodeError, KeyError):
        mock_router.call_structured = AsyncMock(return_value=return_value)
    return {"configurable": {"router": mock_router}}


def make_config_with_structured_router(edit_response: EditResponse):
    """Helper: mocks router.call_structured returning an EditResponse."""
    mock_router = MagicMock()
    mock_router.call = AsyncMock(return_value=json.dumps({"anchor": edit_response.anchor, "replacement": edit_response.replacement}))
    mock_router.call_structured = AsyncMock(return_value=edit_response)
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

    data = json.loads(mock_response)
    edit_resp = EditResponse(anchor=data["anchor"], replacement=data["replacement"])
    mock_router = MagicMock()
    mock_router.call = AsyncMock(return_value=mock_response)
    mock_router.call_structured = AsyncMock(return_value=edit_resp)
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

    data = json.loads(mock_response)
    edit_resp = EditResponse(anchor=data["anchor"], replacement=data["replacement"])
    mock_router = MagicMock()
    mock_router.call = AsyncMock(return_value=mock_response)
    mock_router.call_structured = AsyncMock(return_value=edit_resp)
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


@pytest.mark.asyncio
async def test_editor_uses_structural_replace_when_available(tmp_codebase):
    """Editor should use structural_replace for structurally valid anchors."""
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    content = open(ts_path).read()

    mock_response = json.dumps({
        "anchor": '  description: string;\n  status: "open" | "closed";',
        "replacement": '  description: string;\n  due_date: string;\n  status: "open" | "closed";',
    })

    config = make_config_with_mock_router(mock_response)
    state = {
        "messages": [],
        "instruction": "Add due_date field",
        "working_directory": tmp_codebase,
        "context": {},
        "plan": [{"id": "step-1", "kind": "edit", "target_files": [ts_path], "complexity": "simple", "depends_on": []}],
        "current_step": 0,
        "file_buffer": {ts_path: content},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
        "ast_available": {"typescript": True},
        "invalidated_files": [],
    }

    result = await editor_node(state, config=config)
    assert result["error_state"] is None
    assert "due_date" in result["file_buffer"][ts_path]


# ---------------------------------------------------------------------------
# Prompt template tests (Task 1)
# ---------------------------------------------------------------------------


def test_error_feedback_template_formats():
    """ERROR_FEEDBACK_TEMPLATE.format() produces a string containing all four values."""
    result = ERROR_FEEDBACK_TEMPLATE.format(
        failed_anchor="def foo():",
        error_message="Anchor not found in main.py",
        best_score="0.45",
        best_match="def foobar():",
    )
    assert "def foo():" in result
    assert "Anchor not found in main.py" in result
    assert "0.45" in result
    assert "def foobar():" in result
    assert "PREVIOUS ATTEMPT FAILED" in result


def test_editor_user_has_error_feedback_placeholder():
    """EDITOR_USER contains {error_feedback} placeholder."""
    assert "{error_feedback}" in EDITOR_USER


# ---------------------------------------------------------------------------
# Task 2: Structured output, error feedback, file freshness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_editor_uses_structured_output(tmp_codebase):
    """editor_node calls router.call_structured with EditResponse for simple edits."""
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    content = open(ts_path).read()

    edit_resp = EditResponse(
        anchor='  description: string;\n  status: "open" | "closed";',
        replacement='  description: string;\n  due_date: string;\n  status: "open" | "closed";',
    )
    config = make_config_with_structured_router(edit_resp)

    state = {
        "messages": [],
        "instruction": "Add due_date field",
        "working_directory": tmp_codebase,
        "context": {},
        "plan": ["Add due_date field to Issue interface"],
        "current_step": 0,
        "file_buffer": {ts_path: content},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
    }

    result = await editor_node(state, config=config)

    # Should use call_structured, NOT call
    router = config["configurable"]["router"]
    router.call_structured.assert_called_once()
    assert result["error_state"] is None


@pytest.mark.asyncio
async def test_editor_error_feedback_on_retry(tmp_codebase):
    """When state has error_state + edit_history error, retry prompt contains PREVIOUS ATTEMPT FAILED."""
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    content = open(ts_path).read()

    edit_resp = EditResponse(
        anchor='  description: string;\n  status: "open" | "closed";',
        replacement='  description: string;\n  due_date: string;\n  status: "open" | "closed";',
    )
    config = make_config_with_structured_router(edit_resp)

    state = {
        "messages": [],
        "instruction": "Add due_date field",
        "working_directory": tmp_codebase,
        "context": {},
        "plan": ["Add due_date field"],
        "current_step": 0,
        "file_buffer": {ts_path: content},
        "edit_history": [
            {
                "file": ts_path,
                "error": "Anchor not found in sample.ts",
                "failed_anchor": "nonexistent anchor text",
                "best_score": 0.45,
                "best_match_preview": "  description: string;",
            }
        ],
        "error_state": "Anchor not found in sample.ts",
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
    }

    result = await editor_node(state, config=config)

    router = config["configurable"]["router"]
    user_prompt = router.call_structured.call_args[0][2]  # 3rd positional arg
    assert "PREVIOUS EDIT ATTEMPT FAILED" in user_prompt
    assert "nonexistent anchor text" in user_prompt


@pytest.mark.asyncio
async def test_editor_error_feedback_from_validation_error(tmp_codebase):
    """When state has last_validation_error (from validator), retry prompt contains VALIDATION ERROR."""
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    content = open(ts_path).read()

    edit_resp = EditResponse(
        anchor='  description: string;\n  status: "open" | "closed";',
        replacement='  description: string;\n  due_date: string;\n  status: "open" | "closed";',
    )
    config = make_config_with_structured_router(edit_resp)

    state = {
        "messages": [],
        "instruction": "Add due_date field",
        "working_directory": tmp_codebase,
        "context": {},
        "plan": ["Add due_date field"],
        "current_step": 0,
        "file_buffer": {ts_path: content},
        "edit_history": [],  # No edit-level errors
        "error_state": "Syntax check failed for foo.py: SyntaxError: unexpected indent. Edit rolled back.",
        "last_validation_error": {
            "file_path": "foo.py",
            "error_message": "SyntaxError: unexpected indent",
            "validator_type": "syntax_check",
        },
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
    }

    result = await editor_node(state, config=config)

    router = config["configurable"]["router"]
    user_prompt = router.call_structured.call_args[0][2]
    assert "VALIDATION ERROR" in user_prompt
    assert "foo.py" in user_prompt
    assert "SyntaxError: unexpected indent" in user_prompt


@pytest.mark.asyncio
async def test_editor_freshness_check_reread(tmp_codebase):
    """When file_hashes[path] != current file hash, editor re-reads file before LLM call."""
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    original_content = open(ts_path).read()

    # Stale hash (doesn't match current file)
    stale_hash = "0000000000000000"

    edit_resp = EditResponse(
        anchor='  description: string;\n  status: "open" | "closed";',
        replacement='  description: string;\n  due_date: string;\n  status: "open" | "closed";',
    )
    config = make_config_with_structured_router(edit_resp)

    state = {
        "messages": [],
        "instruction": "Add due_date field",
        "working_directory": tmp_codebase,
        "context": {},
        "plan": ["Add due_date field"],
        "current_step": 0,
        "file_buffer": {ts_path: original_content},
        "file_hashes": {ts_path: stale_hash},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
    }

    result = await editor_node(state, config=config)

    # Should succeed (file was re-read and is fine)
    assert result["error_state"] is None


@pytest.mark.asyncio
async def test_editor_freshness_check_skip_when_no_hash(tmp_codebase):
    """When file_hashes is empty, editor proceeds without re-reading (backward compat)."""
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    content = open(ts_path).read()

    edit_resp = EditResponse(
        anchor='  description: string;\n  status: "open" | "closed";',
        replacement='  description: string;\n  due_date: string;\n  status: "open" | "closed";',
    )
    config = make_config_with_structured_router(edit_resp)

    state = {
        "messages": [],
        "instruction": "Add due_date field",
        "working_directory": tmp_codebase,
        "context": {},
        "plan": ["Add due_date field"],
        "current_step": 0,
        "file_buffer": {ts_path: content},
        # No file_hashes key at all
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
    }

    result = await editor_node(state, config=config)
    assert result["error_state"] is None


@pytest.mark.asyncio
async def test_editor_updates_file_hashes_after_edit(tmp_codebase):
    """After successful edit, returned state includes updated file_hashes."""
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    content = open(ts_path).read()

    edit_resp = EditResponse(
        anchor='  description: string;\n  status: "open" | "closed";',
        replacement='  description: string;\n  due_date: string;\n  status: "open" | "closed";',
    )
    config = make_config_with_structured_router(edit_resp)

    state = {
        "messages": [],
        "instruction": "Add due_date field",
        "working_directory": tmp_codebase,
        "context": {},
        "plan": ["Add due_date field"],
        "current_step": 0,
        "file_buffer": {ts_path: content},
        "file_hashes": {},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
    }

    result = await editor_node(state, config=config)

    assert result["error_state"] is None
    assert "file_hashes" in result
    assert ts_path in result["file_hashes"]
    # Verify the hash matches the new file content
    new_content = open(ts_path).read()
    assert result["file_hashes"][ts_path] == content_hash(new_content)


@pytest.mark.asyncio
async def test_editor_fallback_to_string_call_on_reasoning_tier(tmp_codebase):
    """When task_type is edit_complex (reasoning tier), falls back to router.call()."""
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    content = open(ts_path).read()

    mock_response = json.dumps({
        "anchor": '  description: string;\n  status: "open" | "closed";',
        "replacement": '  description: string;\n  due_date: string;\n  status: "open" | "closed";',
    })

    mock_router = MagicMock()
    mock_router.call = AsyncMock(return_value=mock_response)
    mock_router.call_structured = AsyncMock()
    config = {"configurable": {"router": mock_router}}

    state = {
        "messages": [],
        "instruction": "Complex edit",
        "working_directory": tmp_codebase,
        "context": {},
        "plan": [{"id": "step-1", "kind": "edit", "target_files": [ts_path], "complexity": "complex", "depends_on": []}],
        "current_step": 0,
        "file_buffer": {ts_path: content},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
    }

    result = await editor_node(state, config=config)

    # Should use router.call (string), NOT call_structured
    mock_router.call.assert_called_once()
    mock_router.call_structured.assert_not_called()
    assert result["error_state"] is None
