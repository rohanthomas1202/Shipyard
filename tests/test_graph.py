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
