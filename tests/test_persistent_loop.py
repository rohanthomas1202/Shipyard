"""Tests proving sequential runs on the same server have independent state."""

import os
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from store.sqlite import SQLiteSessionStore
from agent.router import ModelRouter
from agent.events import EventBus
from server.websocket import ConnectionManager


@pytest_asyncio.fixture
async def client(tmp_path):
    """Provide an AsyncClient wired to a real app with temp SQLite store."""
    db_file = str(tmp_path / "test_persistent.db")
    os.environ["SHIPYARD_DB_PATH"] = db_file

    import importlib
    import server.main as main_module
    importlib.reload(main_module)
    from server.main import app

    store = SQLiteSessionStore(db_file)
    await store.initialize()
    event_bus = EventBus(store)
    conn_manager = ConnectionManager(event_bus)
    app.state.store = store
    app.state.router = ModelRouter()
    app.state.event_bus = event_bus
    app.state.conn_manager = conn_manager

    # Mock graph to avoid real LLM calls
    mock_graph = MagicMock()

    async def mock_ainvoke(initial_state, config=None):
        """Return a canned result that mimics a completed run."""
        return {
            "messages": [],
            "instruction": initial_state["instruction"],
            "working_directory": initial_state["working_directory"],
            "context": initial_state["context"],
            "plan": [{"id": "step1", "kind": "edit"}],
            "current_step": 1,
            "file_buffer": {},
            "edit_history": [{"file": "test.py", "old": "a", "new": "b"}],
            "error_state": None,
            "is_parallel": False,
            "parallel_batches": [],
            "sequential_first": [],
            "has_conflicts": False,
        }

    mock_graph.ainvoke = AsyncMock(side_effect=mock_ainvoke)
    app.state.graph = mock_graph

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await event_bus.shutdown()
    await store.close()


@pytest.mark.asyncio
async def test_sequential_runs_no_state_leakage(client):
    """Two POST /instruction calls produce independent runs with no shared state."""
    # Submit first instruction
    resp1 = await client.post("/instruction", json={
        "instruction": "First task: add function foo",
        "working_directory": "/tmp",
        "context": {"spec": "first spec"},
    })
    assert resp1.status_code == 200
    run_id_1 = resp1.json()["run_id"]

    # Wait for the async task to complete
    await asyncio.sleep(0.2)

    # Submit second instruction
    resp2 = await client.post("/instruction", json={
        "instruction": "Second task: add function bar",
        "working_directory": "/tmp",
        "context": {"spec": "second spec"},
    })
    assert resp2.status_code == 200
    run_id_2 = resp2.json()["run_id"]

    # Wait for second task
    await asyncio.sleep(0.2)

    # Get status of both runs
    status1 = await client.get(f"/status/{run_id_1}")
    status2 = await client.get(f"/status/{run_id_2}")

    assert status1.status_code == 200
    assert status2.status_code == 200

    result1 = status1.json()
    result2 = status2.json()

    # Both should have completed (mock returns clean result)
    assert result1["status"] == "completed"
    assert result2["status"] == "completed"

    # Verify the second run received its own instruction, not the first
    assert result2["result"]["instruction"] == "Second task: add function bar"
    assert result1["result"]["instruction"] == "First task: add function foo"

    # Verify edit_history is independent per run (each gets 1 edit from mock)
    assert len(result1["result"]["edit_history"]) == 1
    assert len(result2["result"]["edit_history"]) == 1


@pytest.mark.asyncio
async def test_second_instruction_gets_new_run_id(client):
    """Two sequential POST /instruction calls return different run_ids."""
    resp1 = await client.post("/instruction", json={
        "instruction": "Task A",
        "working_directory": "/tmp",
        "context": {},
    })
    resp2 = await client.post("/instruction", json={
        "instruction": "Task B",
        "working_directory": "/tmp",
        "context": {},
    })

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    run_id_1 = resp1.json()["run_id"]
    run_id_2 = resp2.json()["run_id"]

    assert run_id_1 != run_id_2
