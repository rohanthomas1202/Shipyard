import pytest
from agent.graph import build_graph, should_continue, _normalize_error, _has_repeated_error

def test_graph_compiles():
    graph = build_graph()
    assert graph is not None

def test_classify_step_routes_git_to_git_ops():
    from agent.graph import classify_step
    state = {"plan": [{"kind": "git", "id": "g1", "complexity": "simple"}], "current_step": 0}
    assert classify_step(state) == "git_ops"


def test_graph_has_expected_nodes():
    graph = build_graph()
    node_names = set(graph.get_graph().nodes.keys())
    expected = {"receive", "planner", "coordinator", "reader", "editor", "executor", "validator", "merger", "reporter", "advance", "classify"}
    assert expected.issubset(node_names)

def test_classify_step_routes_refactor():
    from agent.graph import classify_step
    state = {
        "plan": [{"kind": "refactor", "pattern": "old($A)", "refactor_replacement": "new($A)", "language": "typescript"}],
        "current_step": 0,
    }
    result = classify_step(state)
    assert result == "refactor"


# ---------------------------------------------------------------------------
# Circuit breaker tests
# ---------------------------------------------------------------------------

def _make_state(current_step=0, plan_len=3, error_state="some error",
                last_validation_error=None, validation_error_history=None):
    """Helper to build a minimal state dict for should_continue tests."""
    return {
        "error_state": error_state,
        "plan": [f"step{i}" for i in range(plan_len)],
        "current_step": current_step,
        "edit_history": [],
        "last_validation_error": last_validation_error,
        "validation_error_history": validation_error_history or [],
    }


def test_circuit_breaker_triggers_on_repeated_errors():
    """After 2 identical errors on same step, should_continue returns 'advance'."""
    norm_err = "SyntaxError: invalid syntax"
    state = _make_state(
        current_step=0,
        plan_len=3,
        error_state="Syntax check failed",
        last_validation_error={"error_message": norm_err, "file_path": "foo.py", "validator_type": "syntax_check"},
        validation_error_history=[
            {"step": 0, "file_path": "foo.py", "normalized_error": norm_err},
            {"step": 0, "file_path": "foo.py", "normalized_error": norm_err},
        ],
    )
    assert should_continue(state) == "advance"


def test_circuit_breaker_does_not_trigger_on_different_errors():
    """Different errors on the same step should retry normally."""
    state = _make_state(
        current_step=0,
        plan_len=3,
        error_state="Syntax check failed",
        last_validation_error={"error_message": "SyntaxError: invalid syntax", "file_path": "foo.py", "validator_type": "syntax_check"},
        validation_error_history=[
            {"step": 0, "file_path": "foo.py", "normalized_error": "SyntaxError: invalid syntax"},
            {"step": 0, "file_path": "foo.py", "normalized_error": "NameError: name 'x' is not defined"},
        ],
    )
    assert should_continue(state) == "reader"


def test_circuit_breaker_reporter_on_last_step():
    """On the last step, circuit breaker should route to reporter instead of advance."""
    norm_err = "SyntaxError: invalid syntax"
    state = _make_state(
        current_step=2,
        plan_len=3,
        error_state="Syntax check failed",
        last_validation_error={"error_message": norm_err, "file_path": "foo.py", "validator_type": "syntax_check"},
        validation_error_history=[
            {"step": 2, "file_path": "foo.py", "normalized_error": norm_err},
            {"step": 2, "file_path": "foo.py", "normalized_error": norm_err},
        ],
    )
    assert should_continue(state) == "reporter"


def test_normalize_error_strips_line_numbers():
    """Error normalization makes line/col-differing messages compare equal."""
    a = _normalize_error("Line 42, col 5: invalid syntax")
    b = _normalize_error("Line 99, col 12: invalid syntax")
    assert a == b


def test_graph_compiles_with_checkpointer():
    """build_graph(checkpointer=MemorySaver()) returns a compiled graph with checkpointer."""
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer=checkpointer)
    assert graph is not None


def test_graph_compiles_without_checkpointer():
    """build_graph(checkpointer=None) returns a compiled graph (backward compat)."""
    graph = build_graph(checkpointer=None)
    assert graph is not None


import os

@pytest.mark.asyncio
@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="Requires API key")
async def test_end_to_end_edit(tmp_codebase):
    """Full integration: instruct the agent to add a field, verify it works."""
    graph = build_graph()
    result = await graph.ainvoke({
        "messages": [],
        "instruction": "Add a 'priority: string;' field to the Issue interface in sample.ts",
        "working_directory": tmp_codebase,
        "context": {"files": [os.path.join(tmp_codebase, "sample.ts")]},
        "plan": [],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
    })
    content = open(os.path.join(tmp_codebase, "sample.ts")).read()
    assert "priority" in content.lower()
