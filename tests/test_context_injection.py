"""Tests proving external context flows through editor and reader nodes."""

import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock

from agent.nodes.editor import editor_node
from agent.nodes.reader import reader_node


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
        "instruction": "Add a due_date field",
        "working_directory": tmp_codebase,
        "context": {
            "spec": "The Issue type must include a due_date field.",
            "schema": "interface Issue { id: string; title: string; due_date: string; }",
            "test_results": "FAIL: test_issue_due_date - missing due_date property",
            "extra": "Priority: high",
        },
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


@pytest.mark.asyncio
async def test_editor_receives_context_spec_and_schema(sample_state, tmp_codebase):
    """Verify schema and spec content appear in the prompt sent to the LLM."""
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    mock_response = json.dumps({
        "anchor": '  description: string;\n  status: "open" | "closed";',
        "replacement": '  description: string;\n  due_date: string;\n  status: "open" | "closed";',
    })

    config = make_config_with_mock_router(mock_response)
    await editor_node(sample_state, config=config)

    # Capture the user_prompt argument passed to router.call
    call_args = config["configurable"]["router"].call.call_args
    user_prompt = call_args[0][2]  # positional: (task_type, system, user)

    assert "Schema:" in user_prompt
    assert "interface Issue" in user_prompt
    assert "Spec:" in user_prompt
    assert "due_date" in user_prompt


@pytest.mark.asyncio
async def test_editor_receives_test_results_as_error(sample_state, tmp_codebase):
    """Verify test_results context appears in the prompt sent to the LLM."""
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    mock_response = json.dumps({
        "anchor": '  description: string;\n  status: "open" | "closed";',
        "replacement": '  description: string;\n  due_date: string;\n  status: "open" | "closed";',
    })

    config = make_config_with_mock_router(mock_response)
    await editor_node(sample_state, config=config)

    call_args = config["configurable"]["router"].call.call_args
    user_prompt = call_args[0][2]

    assert "Test Results:" in user_prompt
    assert "FAIL: test_issue_due_date" in user_prompt


@pytest.mark.asyncio
async def test_editor_receives_extra_context(sample_state, tmp_codebase):
    """Verify extra context key appears in the prompt sent to the LLM."""
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    mock_response = json.dumps({
        "anchor": '  description: string;\n  status: "open" | "closed";',
        "replacement": '  description: string;\n  due_date: string;\n  status: "open" | "closed";',
    })

    config = make_config_with_mock_router(mock_response)
    await editor_node(sample_state, config=config)

    call_args = config["configurable"]["router"].call.call_args
    user_prompt = call_args[0][2]

    assert "Extra Context:" in user_prompt
    assert "Priority: high" in user_prompt


def test_reader_uses_context_files(tmp_codebase):
    """Verify reader_node reads files specified in context['files']."""
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    state = {
        "messages": [],
        "instruction": "Read the file",
        "working_directory": tmp_codebase,
        "context": {"files": [ts_path]},
        "plan": [],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
    }

    result = reader_node(state)

    assert ts_path in result["file_buffer"]
    assert "interface Issue" in result["file_buffer"][ts_path]


@pytest.mark.asyncio
async def test_editor_empty_context_still_works(tmp_codebase):
    """Verify editor handles empty context dict without errors in prompt building."""
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    content = open(ts_path).read()
    state = {
        "messages": [],
        "instruction": "Add a field",
        "working_directory": tmp_codebase,
        "context": {},
        "plan": ["Add field"],
        "current_step": 0,
        "file_buffer": {ts_path: content},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
    }

    mock_response = json.dumps({
        "anchor": '  description: string;\n  status: "open" | "closed";',
        "replacement": '  description: string;\n  due_date: string;\n  status: "open" | "closed";',
    })

    config = make_config_with_mock_router(mock_response)
    result = await editor_node(state, config=config)
    assert result["error_state"] is None
