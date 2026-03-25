import os
import pytest
import pytest_asyncio
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

    # Import the app fresh after env var is set
    import importlib
    import server.main as main_module
    importlib.reload(main_module)
    from server.main import app

    # Manually initialize store and attach to app state so endpoints work
    # without relying on lifespan (ASGITransport doesn't trigger lifespan)
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
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_submit_instruction_returns_run_id(client):
    response = await client.post("/instruction", json={
        "instruction": "test",
        "working_directory": "/tmp",
        "context": {},
    })
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_get_status_not_found(client):
    response = await client.get("/status/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_project(client):
    response = await client.post("/projects", json={
        "name": "MyProject",
        "path": "/workspace/myproject",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "MyProject"
    assert data["path"] == "/workspace/myproject"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_projects(client):
    # Create two projects
    await client.post("/projects", json={"name": "Alpha", "path": "/alpha"})
    await client.post("/projects", json={"name": "Beta", "path": "/beta"})

    response = await client.get("/projects")
    assert response.status_code == 200
    projects = response.json()
    assert len(projects) == 2
    names = {p["name"] for p in projects}
    assert names == {"Alpha", "Beta"}


@pytest.mark.asyncio
async def test_get_project(client):
    # Create a project
    create_resp = await client.post("/projects", json={"name": "Gamma", "path": "/gamma"})
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    # Fetch it by ID
    response = await client.get(f"/projects/{project_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Gamma"
    assert data["id"] == project_id


@pytest.mark.asyncio
async def test_get_project_not_found(client):
    response = await client.get("/projects/doesnotexist")
    assert response.status_code == 404
