"""Tests for observability: decision traces and heatmap aggregation."""
import pytest
from agent.orchestrator.metrics import build_decision_trace, aggregate_heatmap
from agent.orchestrator.models import DecisionTrace


def test_build_decision_trace_basic():
    trace = build_decision_trace("t1", "dag1", "some error")
    assert trace.task_id == "t1"
    assert trace.dag_id == "dag1"
    assert trace.error_message == "some error"
    assert trace.error_category == "structural"
    assert trace.llm_prompt is None
    assert trace.files_read == []


def test_build_decision_trace_truncates_llm():
    long = "x" * 5000
    trace = build_decision_trace("t1", "dag1", "err", llm_prompt=long, llm_response=long)
    assert len(trace.llm_prompt) == 2000
    assert len(trace.llm_response) == 2000


def test_build_decision_trace_default_category():
    trace = build_decision_trace("t1", "dag1", "err")
    assert trace.error_category == "structural"


def test_aggregate_heatmap_empty():
    assert aggregate_heatmap([]) == {}


def test_aggregate_heatmap_groups_correctly():
    traces = [
        build_decision_trace("t1", "d1", "e1", module_name="auth", error_category="syntax"),
        build_decision_trace("t2", "d1", "e2", module_name="auth", error_category="syntax"),
        build_decision_trace("t3", "d1", "e3", module_name="api", error_category="test"),
    ]
    hm = aggregate_heatmap(traces)
    assert hm["auth"]["syntax"] == 2
    assert hm["api"]["test"] == 1


def test_aggregate_heatmap_unknown_module():
    traces = [build_decision_trace("t1", "d1", "e1")]
    hm = aggregate_heatmap(traces)
    assert "unknown" in hm
