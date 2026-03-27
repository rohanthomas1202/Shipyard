"""Tests for parallel batch execution, merge, and graph routing."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from agent.parallel import run_parallel_batches
from agent.nodes.merger import merge_batch_results
from agent.graph import after_coordinator


# ---------------------------------------------------------------------------
# run_parallel_batches tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_batches_execute_concurrently():
    """Two batches run via asyncio.gather and both return results."""
    mock_graph = MagicMock()

    async def fake_ainvoke(state, config=None):
        plan = state["plan"]
        return {
            "edit_history": [{"file": f"file_{plan[0]}.py", "anchor": "a", "replacement": "b"}],
            "file_buffer": {f"file_{plan[0]}.py": "content"},
            "error_state": None,
        }

    mock_graph.ainvoke = AsyncMock(side_effect=fake_ainvoke)

    base_state = {
        "plan": ["step0", "step1", "step2"],
        "current_step": 0,
        "edit_history": [],
        "file_buffer": {},
        "file_hashes": {},
        "error_state": None,
        "is_parallel": True,
        "parallel_batches": [[0], [1, 2]],
        "sequential_first": [],
    }

    results = await run_parallel_batches(
        mock_graph, [[0], [1, 2]], base_state, config={}
    )

    assert len(results) == 2
    assert mock_graph.ainvoke.call_count == 2
    # First batch gets plan[0], second batch gets plan[1] and plan[2]
    assert len(results[0]["edit_history"]) == 1
    assert len(results[1]["edit_history"]) == 1


@pytest.mark.asyncio
async def test_parallel_batches_handle_exception():
    """If a batch raises an exception, it is caught and returned as error dict."""
    mock_graph = MagicMock()

    call_count = 0

    async def fake_ainvoke(state, config=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "edit_history": [{"file": "ok.py", "anchor": "a", "replacement": "b"}],
                "file_buffer": {"ok.py": "content"},
                "error_state": None,
            }
        raise RuntimeError("Batch failed")

    mock_graph.ainvoke = AsyncMock(side_effect=fake_ainvoke)

    base_state = {
        "plan": ["step0", "step1"],
        "current_step": 0,
        "edit_history": [],
        "file_buffer": {},
        "file_hashes": {},
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
    }

    results = await run_parallel_batches(
        mock_graph, [[0], [1]], base_state, config={}
    )

    assert len(results) == 2
    assert results[0]["edit_history"] == [{"file": "ok.py", "anchor": "a", "replacement": "b"}]
    assert results[1]["error_state"] == "Batch failed"
    assert results[1]["edit_history"] == []


# ---------------------------------------------------------------------------
# merge_batch_results tests
# ---------------------------------------------------------------------------

def test_merge_batch_results_combines_edits():
    """Merging two results concatenates edit_histories and merges file_buffers."""
    results = [
        {
            "edit_history": [{"file": "a.py", "anchor": "x", "replacement": "y"}],
            "file_buffer": {"a.py": "content_a"},
            "error_state": None,
        },
        {
            "edit_history": [{"file": "b.py", "anchor": "m", "replacement": "n"}],
            "file_buffer": {"b.py": "content_b"},
            "error_state": None,
        },
    ]
    merged = merge_batch_results(results)

    assert len(merged["edit_history"]) == 2
    assert merged["file_buffer"] == {"a.py": "content_a", "b.py": "content_b"}
    assert merged["has_conflicts"] is False
    assert merged["error_state"] is None


def test_merge_batch_results_detects_conflicts():
    """Same file edited in two batches triggers has_conflicts."""
    results = [
        {
            "edit_history": [{"file": "shared.py", "anchor": "x", "replacement": "y"}],
            "file_buffer": {"shared.py": "v1"},
            "error_state": None,
        },
        {
            "edit_history": [{"file": "shared.py", "anchor": "a", "replacement": "b"}],
            "file_buffer": {"shared.py": "v2"},
            "error_state": None,
        },
    ]
    merged = merge_batch_results(results)

    assert merged["has_conflicts"] is True
    assert len(merged["edit_history"]) == 2


def test_merge_batch_results_handles_errors():
    """Error results are captured; successful batch edits preserved."""
    results = [
        {
            "edit_history": [{"file": "ok.py", "anchor": "x", "replacement": "y"}],
            "file_buffer": {"ok.py": "content"},
            "error_state": None,
        },
        {
            "edit_history": [],
            "file_buffer": {},
            "error_state": "RuntimeError: Batch failed",
        },
    ]
    merged = merge_batch_results(results)

    assert merged["error_state"] == "RuntimeError: Batch failed"
    assert len(merged["edit_history"]) == 1
    assert merged["edit_history"][0]["file"] == "ok.py"


# ---------------------------------------------------------------------------
# Graph routing tests
# ---------------------------------------------------------------------------

def test_after_coordinator_routes_parallel():
    """When is_parallel and batches exist, route to parallel_executor."""
    state = {
        "is_parallel": True,
        "parallel_batches": [[0], [1]],
    }
    assert after_coordinator(state) == "parallel_executor"


def test_after_coordinator_routes_sequential():
    """When not parallel, route to classify for normal sequential execution."""
    state = {
        "is_parallel": False,
        "parallel_batches": [],
    }
    assert after_coordinator(state) == "classify"


def test_after_coordinator_routes_sequential_empty_batches():
    """Even if is_parallel is True, empty batches routes to classify."""
    state = {
        "is_parallel": True,
        "parallel_batches": [],
    }
    assert after_coordinator(state) == "classify"


@pytest.mark.asyncio
async def test_parallel_executor_node_runs_batches():
    """parallel_executor_node builds sub-graph, runs batches, returns merged results."""
    from agent.nodes.coordinator import parallel_executor_node

    mock_graph = MagicMock()

    async def fake_ainvoke(state, config=None):
        return {
            "edit_history": [{"file": "test.py", "anchor": "a", "replacement": "b"}],
            "file_buffer": {"test.py": "content"},
            "error_state": None,
        }

    mock_graph.ainvoke = AsyncMock(side_effect=fake_ainvoke)

    state = {
        "plan": ["step0", "step1"],
        "current_step": 0,
        "edit_history": [],
        "file_buffer": {},
        "file_hashes": {},
        "error_state": None,
        "is_parallel": True,
        "parallel_batches": [[0], [1]],
        "sequential_first": [],
    }

    with patch("agent.graph.build_graph", return_value=mock_graph):
        result = await parallel_executor_node(state, config={})

    assert len(result["edit_history"]) == 2
    assert result["has_conflicts"] is True  # same file "test.py" in both batches
    assert result["error_state"] is None
