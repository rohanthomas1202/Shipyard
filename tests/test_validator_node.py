import asyncio
import inspect
import os
from unittest.mock import AsyncMock, MagicMock, patch
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


# ---------------------------------------------------------------------------
# Plan 02 Task 1: Python syntax checking tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_python_syntax_valid(tmp_path):
    """Valid Python file passes syntax check."""
    py_path = tmp_path / "valid.py"
    py_path.write_text("def hello():\n    return 42\n")
    result = await _syntax_check(str(py_path))
    assert result["valid"] is True
    assert result["error"] is None


@pytest.mark.asyncio
async def test_python_syntax_error(tmp_path):
    """Invalid Python file is caught by ast.parse."""
    py_path = tmp_path / "invalid.py"
    py_path.write_text("def foo(\n    x = \n")
    result = await _syntax_check(str(py_path))
    assert result["valid"] is False
    assert "Line" in result["error"]


# ---------------------------------------------------------------------------
# Plan 02 Task 2: LSP fallback tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lsp_unavailable_falls_back_to_syntax(tmp_path):
    """When LSP client raises ConnectionError, validator falls back to syntax check."""
    py_path = tmp_path / "valid.py"
    py_path.write_text("x = 1\n")

    mock_client = AsyncMock()
    mock_client.get_diagnostics = AsyncMock(side_effect=ConnectionError("LSP down"))

    mock_lsp_manager = MagicMock()
    mock_lsp_manager.get_client.return_value = mock_client

    state = {
        "messages": [],
        "instruction": "test",
        "working_directory": str(tmp_path),
        "context": {},
        "plan": [],
        "current_step": 0,
        "file_buffer": {str(py_path): "x = 1\n"},
        "edit_history": [{"file": str(py_path), "snapshot": "x = 1\n"}],
        "error_state": None,
    }
    config = {"configurable": {"lsp_manager": mock_lsp_manager}}
    result = await validator_node(state, config)
    assert result["error_state"] is None


@pytest.mark.asyncio
async def test_lsp_timeout_falls_back_to_syntax(tmp_path):
    """When LSP hangs, the 30s timeout triggers fallback to syntax check."""
    py_path = tmp_path / "valid.py"
    py_path.write_text("x = 1\n")

    async def hanging_diagnostics(*args, **kwargs):
        await asyncio.sleep(60)

    mock_client = AsyncMock()
    mock_client.get_diagnostics = hanging_diagnostics

    mock_lsp_manager = MagicMock()
    mock_lsp_manager.get_client.return_value = mock_client

    state = {
        "messages": [],
        "instruction": "test",
        "working_directory": str(tmp_path),
        "context": {},
        "plan": [],
        "current_step": 0,
        "file_buffer": {str(py_path): "x = 1\n"},
        "edit_history": [{"file": str(py_path), "snapshot": "x = 1\n"}],
        "error_state": None,
    }
    config = {"configurable": {"lsp_manager": mock_lsp_manager}}

    # Temporarily reduce timeout for test speed
    with patch("agent.nodes.validator.asyncio.wait_for", wraps=asyncio.wait_for) as mock_wait:
        result = await asyncio.wait_for(validator_node(state, config), timeout=35.0)
    assert result["error_state"] is None
