import pytest
from agent.graph import build_graph

def test_graph_compiles():
    graph = build_graph()
    assert graph is not None

def test_graph_has_expected_nodes():
    graph = build_graph()
    node_names = set(graph.get_graph().nodes.keys())
    expected = {"receive", "planner", "coordinator", "reader", "editor", "executor", "validator", "merger", "reporter", "advance", "classify"}
    assert expected.issubset(node_names)

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
