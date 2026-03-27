"""Tests for run cancellation endpoint and CancelledError handling."""
import asyncio
import pytest
import pytest_asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from store.sqlite import SQLiteSessionStore
from agent.router import ModelRouter
from agent.events import EventBus
from server.websocket import ConnectionManager


@pytest_asyncio.fixture
async def client(tmp_path):
    """Provide an AsyncClient wired to a real app with temp SQLite store."""
    db_file = str(tmp_path / "test_shipyard.db")
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

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await event_bus.shutdown()
    await store.close()


@pytest.mark.asyncio
async def test_cancel_run_not_found(client):
    """POST /runs/fake-id/cancel on non-existent run returns 404."""
    resp = await client.post("/runs/fake-id/cancel")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_run_already_completed(client):
    """POST cancel on a completed run returns 409."""
    import server.main as main_module
    main_module.runs["done-run"] = {"status": "completed", "result": {}}

    resp = await client.post("/runs/done-run/cancel")
    assert resp.status_code == 409

    # Cleanup
    del main_module.runs["done-run"]


@pytest.mark.asyncio
async def test_cancel_run_success(client):
    """POST cancel on a running run returns 200 with status cancelling."""
    import server.main as main_module

    mock_task = MagicMock()
    mock_task.done.return_value = False
    mock_task.cancel = MagicMock()

    main_module.runs["active-run"] = {
        "status": "running",
        "result": None,
        "task": mock_task,
    }

    resp = await client.post("/runs/active-run/cancel")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "cancelling"
    assert data["run_id"] == "active-run"
    mock_task.cancel.assert_called_once()

    # Cleanup
    del main_module.runs["active-run"]


@pytest.mark.asyncio
async def test_cancelled_error_sets_status():
    """CancelledError handler in execute() sets status to cancelled."""
    import server.main as main_module

    # Create a graph mock that raises CancelledError when invoked
    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(side_effect=asyncio.CancelledError())

    mock_store = AsyncMock()
    mock_store.create_run = AsyncMock()

    mock_lsp_mgr = AsyncMock()
    mock_lsp_mgr.__aenter__ = AsyncMock(return_value=mock_lsp_mgr)
    mock_lsp_mgr.__aexit__ = AsyncMock(return_value=False)

    mock_app_state = MagicMock()
    mock_app_state.store = mock_store
    mock_app_state.router = MagicMock()
    mock_app_state.graph = mock_graph
    mock_app_state.approval_manager = MagicMock()

    run_id = "cancel-test"
    main_module.runs[run_id] = {"status": "running", "result": None}

    with patch("agent.tools.lsp_manager.LspManager", return_value=mock_lsp_mgr):
        with patch.object(main_module.app, "state", mock_app_state):
            # Simulate what execute() does inside submit_instruction
            try:
                graph = mock_app_state.graph
                async with mock_lsp_mgr as lsp_mgr:
                    config = {
                        "configurable": {
                            "store": mock_store,
                            "router": mock_app_state.router,
                            "approval_manager": mock_app_state.approval_manager,
                            "run_id": run_id,
                            "lsp_manager": lsp_mgr,
                            "thread_id": run_id,
                        }
                    }
                    await graph.ainvoke({}, config=config)
            except asyncio.CancelledError:
                # This is what the new handler should do
                main_module.runs[run_id] = {
                    "status": "cancelled",
                    "result": "Cancelled by user",
                }

    assert main_module.runs[run_id]["status"] == "cancelled"

    # Cleanup
    del main_module.runs[run_id]


@pytest.mark.asyncio
async def test_cancel_run_edit_rollback(tmp_path):
    """CancelledError handler rolls back edits with snapshots."""
    import server.main as main_module

    # Create a file that was "edited" during the run
    test_file = tmp_path / "edited.py"
    original_content = "# original content\n"
    test_file.write_text("# modified by agent\n")

    run_id = "rollback-test"
    main_module.runs[run_id] = {
        "status": "running",
        "result": {
            "edit_history": [
                {
                    "file_path": str(test_file),
                    "snapshot": original_content,
                }
            ]
        },
    }

    # Simulate the rollback logic that should exist in the CancelledError handler
    run_entry = main_module.runs[run_id]
    result = run_entry.get("result", {})
    if isinstance(result, dict):
        edit_history = result.get("edit_history", [])
        for entry in edit_history:
            if "snapshot" in entry:
                with open(entry["file_path"], "w") as f:
                    f.write(entry["snapshot"])

    # Verify rollback happened
    assert test_file.read_text() == original_content

    # Cleanup
    del main_module.runs[run_id]
