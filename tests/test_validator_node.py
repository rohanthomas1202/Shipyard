import os
import pytest
from agent.nodes.validator import validator_node


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
