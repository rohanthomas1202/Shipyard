import inspect
import os
import pytest
from agent.nodes.validator import validator_node, _syntax_check


@pytest.fixture
def valid_edit_state(tmp_codebase):
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    return {
        "messages": [],
        "instruction": "Add due_date",
        "working_directory": tmp_codebase,
        "context": {},
        "plan": ["Add due_date"],
        "current_step": 0,
        "file_buffer": {ts_path: open(ts_path).read()},
        "edit_history": [{"file": ts_path, "snapshot": open(ts_path).read()}],
        "error_state": None,
    }


@pytest.mark.asyncio
async def test_validator_passes_valid_file(valid_edit_state):
    result = await validator_node(valid_edit_state)
    assert result["error_state"] is None


@pytest.mark.asyncio
async def test_validator_catches_invalid_json(tmp_codebase):
    json_path = os.path.join(tmp_codebase, "config.json")
    with open(json_path, "w") as f:
        f.write('{"port": 3000,}')
    state = {
        "messages": [],
        "instruction": "test",
        "working_directory": tmp_codebase,
        "context": {},
        "plan": [],
        "current_step": 0,
        "file_buffer": {json_path: open(json_path).read()},
        "edit_history": [{"file": json_path, "snapshot": '{"port": 3000}'}],
        "error_state": None,
    }
    result = await validator_node(state)
    assert result["error_state"] is not None


# ---------------------------------------------------------------------------
# Task 3: Structured error output tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validator_error_includes_file_path(tmp_codebase):
    """When syntax check fails, error_state string contains the file path."""
    json_path = os.path.join(tmp_codebase, "config.json")
    with open(json_path, "w") as f:
        f.write('{"port": 3000,}')
    state = {
        "messages": [],
        "instruction": "test",
        "working_directory": tmp_codebase,
        "context": {},
        "plan": [],
        "current_step": 0,
        "file_buffer": {json_path: '{"port": 3000,}'},
        "edit_history": [{"file": json_path, "snapshot": '{"port": 3000}'}],
        "error_state": None,
    }
    result = await validator_node(state)
    assert json_path in result["error_state"]


@pytest.mark.asyncio
async def test_validator_error_includes_error_message(tmp_codebase):
    """When syntax check fails, error_state contains the actual error."""
    json_path = os.path.join(tmp_codebase, "config.json")
    with open(json_path, "w") as f:
        f.write('{"port": 3000,}')
    state = {
        "messages": [],
        "instruction": "test",
        "working_directory": tmp_codebase,
        "context": {},
        "plan": [],
        "current_step": 0,
        "file_buffer": {json_path: '{"port": 3000,}'},
        "edit_history": [{"file": json_path, "snapshot": '{"port": 3000}'}],
        "error_state": None,
    }
    result = await validator_node(state)
    # Should contain some error detail from JSON parser
    assert "Expecting" in result["error_state"] or "property name" in result["error_state"] or "trailing comma" in result["error_state"].lower()


@pytest.mark.asyncio
async def test_validator_error_includes_rolled_back(tmp_codebase):
    """When syntax check fails, error_state contains 'rolled back'."""
    json_path = os.path.join(tmp_codebase, "config.json")
    with open(json_path, "w") as f:
        f.write('{"port": 3000,}')
    state = {
        "messages": [],
        "instruction": "test",
        "working_directory": tmp_codebase,
        "context": {},
        "plan": [],
        "current_step": 0,
        "file_buffer": {json_path: '{"port": 3000,}'},
        "edit_history": [{"file": json_path, "snapshot": '{"port": 3000}'}],
        "error_state": None,
    }
    result = await validator_node(state)
    assert "rolled back" in result["error_state"].lower()


@pytest.mark.asyncio
async def test_validator_sets_last_validation_error(tmp_codebase):
    """When validation fails, returned state includes last_validation_error dict."""
    json_path = os.path.join(tmp_codebase, "config.json")
    with open(json_path, "w") as f:
        f.write('{"port": 3000,}')
    state = {
        "messages": [],
        "instruction": "test",
        "working_directory": tmp_codebase,
        "context": {},
        "plan": [],
        "current_step": 0,
        "file_buffer": {json_path: '{"port": 3000,}'},
        "edit_history": [{"file": json_path, "snapshot": '{"port": 3000}'}],
        "error_state": None,
    }
    result = await validator_node(state)

    assert "last_validation_error" in result
    lve = result["last_validation_error"]
    assert lve["file_path"] == json_path
    assert "error_message" in lve
    assert lve["validator_type"] == "syntax_check"


# ---------------------------------------------------------------------------
# Task 2: Async conversion verification
# ---------------------------------------------------------------------------


def test_syntax_check_is_async():
    """Verify _syntax_check is a coroutine function after async conversion."""
    assert inspect.iscoroutinefunction(_syntax_check)
