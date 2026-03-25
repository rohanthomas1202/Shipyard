"""Tests for PATCH /runs/{run_id}/edits/{edit_id} endpoint."""
import os
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
from store.sqlite import SQLiteSessionStore
from store.models import Project, Run, EditRecord
from agent.router import ModelRouter
from agent.events import EventBus
from agent.approval import ApprovalManager
from server.websocket import ConnectionManager


@pytest_asyncio.fixture
async def client(tmp_path):
    """Provide an AsyncClient wired to a real app with temp SQLite store."""
    db_file = str(tmp_path / "test_approval.db")
    os.environ["SHIPYARD_DB_PATH"] = db_file

    import importlib
    import server.main as main_module
    importlib.reload(main_module)
    from server.main import app

    store = SQLiteSessionStore(db_file)
    await store.initialize()
    event_bus = EventBus(store)
    conn_manager = ConnectionManager(event_bus)
    approval_manager = ApprovalManager(store=store, event_bus=event_bus)
    conn_manager.set_approval_manager(approval_manager)

    app.state.store = store
    app.state.router = ModelRouter()
    app.state.event_bus = event_bus
    app.state.conn_manager = conn_manager
    app.state.approval_manager = approval_manager

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await event_bus.shutdown()
    await store.close()


@pytest_asyncio.fixture
async def project_and_run(tmp_path):
    """Return (store, project, run) with a real SQLite store."""
    db_file = str(tmp_path / "fixture.db")
    store = SQLiteSessionStore(db_file)
    await store.initialize()
    project = Project(name="test", path="/tmp/test")
    await store.create_project(project)
    run = Run(project_id=project.id, instruction="test instruction")
    await store.create_run(run)
    yield store, project, run
    await store.close()


@pytest_asyncio.fixture
async def setup_edit(client, tmp_path):
    """Create a project, run, and proposed edit; return (run_id, edit_id, file_path)."""
    from server.main import app
    store: SQLiteSessionStore = app.state.store
    approval_manager: ApprovalManager = app.state.approval_manager

    project = Project(name="test-proj", path="/tmp/test-proj")
    await store.create_project(project)
    run = Run(project_id=project.id, instruction="test")
    await store.create_run(run)

    # Create a real file for apply_edit to write to
    target_file = tmp_path / "edit_target.py"
    target_file.write_text("old content here")

    edit = EditRecord(
        run_id=run.id,
        file_path=str(target_file),
        old_content="old content here",
        new_content="new content here",
    )
    proposed = await approval_manager.propose_edit(run.id, edit)
    return run.id, proposed.id, str(target_file)


@pytest.mark.asyncio
async def test_patch_approve_returns_200_applied(client, setup_edit):
    """PATCH approve returns 200 with status 'applied'."""
    run_id, edit_id, _ = setup_edit
    response = await client.patch(
        f"/runs/{run_id}/edits/{edit_id}",
        json={"action": "approve", "op_id": "op-test-1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "applied"
    assert data["edit_id"] == edit_id
    assert data["run_id"] == run_id


@pytest.mark.asyncio
async def test_patch_reject_returns_200_rejected(client, setup_edit):
    """PATCH reject returns 200 with status 'rejected'."""
    run_id, edit_id, _ = setup_edit
    response = await client.patch(
        f"/runs/{run_id}/edits/{edit_id}",
        json={"action": "reject", "op_id": "op-reject-1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rejected"
    assert data["edit_id"] == edit_id
    assert data["run_id"] == run_id


@pytest.mark.asyncio
async def test_patch_nonexistent_edit_returns_404(client, setup_edit):
    """PATCH nonexistent edit returns 404."""
    run_id, _, _ = setup_edit
    response = await client.patch(
        f"/runs/{run_id}/edits/nonexistent-edit-id",
        json={"action": "approve", "op_id": "op-1"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_wrong_run_id_returns_404(client, setup_edit):
    """PATCH with wrong run_id returns 404 (ownership check)."""
    _, edit_id, _ = setup_edit
    response = await client.patch(
        f"/runs/wrong-run-id/edits/{edit_id}",
        json={"action": "approve", "op_id": "op-1"},
    )
    assert response.status_code == 404
    assert "Edit not found for this run" in response.json()["detail"]


@pytest.mark.asyncio
async def test_patch_invalid_transition_returns_409(client, setup_edit):
    """PATCH invalid transition (e.g., approve already-applied) returns 409."""
    run_id, edit_id, _ = setup_edit
    # First approve+apply
    await client.patch(
        f"/runs/{run_id}/edits/{edit_id}",
        json={"action": "approve", "op_id": "op-first"},
    )
    # Now try to approve again with a different op_id (invalid transition from applied)
    response = await client.patch(
        f"/runs/{run_id}/edits/{edit_id}",
        json={"action": "approve", "op_id": "op-second"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_patch_idempotent_approve_first_call_200(client, setup_edit):
    """PATCH approve is 200 on first call and returns applied status."""
    run_id, edit_id, _ = setup_edit
    response = await client.patch(
        f"/runs/{run_id}/edits/{edit_id}",
        json={"action": "approve", "op_id": "op-idem-1"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "applied"
