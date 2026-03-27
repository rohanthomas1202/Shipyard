"""Tests for checkpoint persistence and crash recovery resume flow."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_checkpoint_written():
    """Graph with MemorySaver persists checkpoint after invocation."""
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import StateGraph, END
    from typing import TypedDict

    class MiniState(TypedDict):
        value: int

    def add_one(state: dict) -> dict:
        return {"value": state["value"] + 1}

    checkpointer = MemorySaver()
    graph = StateGraph(MiniState)
    graph.add_node("add", add_one)
    graph.set_entry_point("add")
    graph.add_edge("add", END)
    compiled = graph.compile(checkpointer=checkpointer)

    thread_id = "test-thread-001"
    config = {"configurable": {"thread_id": thread_id}}
    result = await compiled.ainvoke({"value": 0}, config=config)
    assert result["value"] == 1

    # Verify checkpoint was persisted
    checkpoint_tuple = await checkpointer.aget_tuple(config)
    assert checkpoint_tuple is not None
    assert checkpoint_tuple.checkpoint is not None


@pytest.mark.asyncio
async def test_resume_interrupted_runs_finds_running():
    """_resume_interrupted_runs queries for runs with status 'running' and creates tasks."""
    from store.models import Run

    mock_store = AsyncMock()
    mock_store.list_runs_by_status = AsyncMock(return_value=[
        Run(id="run-1", project_id="proj-1", instruction="do something", status="running"),
        Run(id="run-2", project_id="proj-1", instruction="do another", status="running"),
    ])

    mock_app_state = MagicMock()
    mock_app_state.store = mock_store
    mock_app_state.router = MagicMock()
    mock_app_state.graph = AsyncMock()
    mock_app_state.approval_manager = MagicMock()
    mock_app_state.checkpointer = MagicMock()

    with patch("server.main.app") as mock_app:
        mock_app.state = mock_app_state

        from server.main import _resume_interrupted_runs
        with patch("server.main.asyncio.create_task") as mock_create_task:
            await _resume_interrupted_runs()

            mock_store.list_runs_by_status.assert_called_once_with("running")
            assert mock_create_task.call_count == 2


@pytest.mark.asyncio
async def test_resume_from_checkpoint_updates_status():
    """_resume_from_checkpoint calls ainvoke(None, config) and updates run status."""
    from store.models import Run

    mock_run = Run(id="run-1", project_id="proj-1", instruction="test", status="running")
    mock_store = AsyncMock()
    mock_store.get_run = AsyncMock(return_value=mock_run)
    mock_store.update_run = AsyncMock(return_value=mock_run)

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value={"error_state": None})

    mock_app_state = MagicMock()
    mock_app_state.store = mock_store
    mock_app_state.router = MagicMock()
    mock_app_state.graph = mock_graph
    mock_app_state.approval_manager = MagicMock()

    with patch("server.main.app") as mock_app:
        mock_app.state = mock_app_state

        from server.main import _resume_from_checkpoint, runs
        await _resume_from_checkpoint("run-1")

        # Verify ainvoke was called with None (resume from checkpoint)
        mock_graph.ainvoke.assert_called_once()
        call_args = mock_graph.ainvoke.call_args
        assert call_args[0][0] is None  # First positional arg is None
        assert call_args[1]["config"]["configurable"]["thread_id"] == "run-1"

        # Status should be completed since error_state is None
        assert runs["run-1"]["status"] == "completed"
