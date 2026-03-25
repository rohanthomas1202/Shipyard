import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock
from agent.nodes.editor import editor_node
from agent.state import AgentState


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
