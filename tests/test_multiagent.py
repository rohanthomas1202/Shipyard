import pytest
from agent.nodes.coordinator import coordinator_node
from agent.nodes.merger import merger_node

def test_coordinator_identifies_parallel_tasks():
    state = {
        "messages": [],
        "instruction": "Update API and Web",
        "working_directory": "/tmp",
        "context": {},
        "plan": [
            "Edit api/src/routes/issues.ts to add endpoint",
            "Edit web/src/pages/Issues.tsx to add form field",
        ],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
    }
    result = coordinator_node(state)
    assert result["is_parallel"] is True
    assert "parallel_batches" in result
    assert len(result["parallel_batches"]) == 2

def test_coordinator_sequential_for_single_dir():
    state = {
        "messages": [],
        "instruction": "Update API",
        "working_directory": "/tmp",
        "context": {},
        "plan": [
            "Edit api/src/routes/issues.ts to add endpoint",
            "Edit api/src/models/issue.ts to add field",
        ],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
    }
    result = coordinator_node(state)
    assert result["is_parallel"] is False

def test_coordinator_shared_runs_first():
    state = {
        "messages": [],
        "instruction": "Update shared and API",
        "working_directory": "/tmp",
        "context": {},
        "plan": [
            "Edit shared/types.ts to add type",
            "Edit api/src/routes/issues.ts to use new type",
            "Edit web/src/pages/Issues.tsx to use new type",
        ],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
    }
    result = coordinator_node(state)
    assert 0 in result["sequential_first"]  # shared step runs first

def test_merger_no_conflicts():
    state = {
        "edit_history": [
            {"file": "api/route.ts", "anchor": "a", "replacement": "b", "snapshot": "old"},
            {"file": "web/page.tsx", "anchor": "c", "replacement": "d", "snapshot": "old2"},
        ],
    }
    result = merger_node(state)
    assert result["has_conflicts"] is False

def test_merger_detects_same_file_conflict():
    state = {
        "edit_history": [
            {"file": "shared/types.ts", "anchor": "a", "replacement": "b", "snapshot": "old"},
            {"file": "shared/types.ts", "anchor": "c", "replacement": "d", "snapshot": "old"},
        ],
    }
    result = merger_node(state)
    assert result["has_conflicts"] is True

def test_merger_empty_history():
    state = {"edit_history": []}
    result = merger_node(state)
    assert result["has_conflicts"] is False
