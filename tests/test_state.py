from agent.state import AgentState

def test_agent_state_has_required_fields():
    state = AgentState(
        messages=[],
        instruction="test instruction",
        working_directory="/tmp/test",
        context={},
        plan=[],
        current_step=0,
        file_buffer={},
        edit_history=[],
        error_state=None,
        is_parallel=False,
        parallel_batches=[],
        sequential_first=[],
        has_conflicts=False,
        model_usage={},
    )
    assert state["instruction"] == "test instruction"
    assert state["working_directory"] == "/tmp/test"
    assert state["messages"] == []
    assert state["context"] == {}
    assert state["plan"] == []
    assert state["current_step"] == 0
    assert state["file_buffer"] == {}
    assert state["edit_history"] == []
    assert state["error_state"] is None
    assert state["is_parallel"] is False
    assert state["parallel_batches"] == []
    assert state["sequential_first"] == []
    assert state["has_conflicts"] is False
    assert state["model_usage"] == {}


def test_agent_state_has_autonomy_mode():
    from agent.state import AgentState
    state: AgentState = {
        "messages": [], "instruction": "test", "working_directory": "/tmp",
        "context": {}, "plan": [], "current_step": 0, "file_buffer": {},
        "edit_history": [], "error_state": None, "is_parallel": False,
        "parallel_batches": [], "sequential_first": [], "has_conflicts": False,
        "model_usage": {}, "autonomy_mode": "supervised",
    }
    assert state["autonomy_mode"] == "supervised"


def test_state_has_ast_available_field():
    """AgentState should accept ast_available dict."""
    state = {
        "messages": [],
        "instruction": "",
        "working_directory": "",
        "context": {},
        "plan": [],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
        "model_usage": {},
        "autonomy_mode": "autonomous",
        "ast_available": {"typescript": True, "python": True},
        "invalidated_files": [],
    }
    assert state["ast_available"]["typescript"] is True
    assert state["invalidated_files"] == []


def test_plan_accepts_dict_steps():
    """AgentState.plan should accept both str and dict entries."""
    state = {
        "messages": [],
        "instruction": "",
        "working_directory": "",
        "context": {},
        "plan": [
            "legacy string step",
            {"id": "step-1", "kind": "edit", "target_files": ["a.py"], "complexity": "simple", "depends_on": []},
        ],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
        "model_usage": {},
        "autonomy_mode": "autonomous",
        "ast_available": {},
        "invalidated_files": [],
    }
    assert isinstance(state["plan"][0], str)
    assert isinstance(state["plan"][1], dict)
