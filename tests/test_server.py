import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from store.sqlite import SQLiteSessionStore
from store.models import Run, EditRecord
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


@pytest.mark.asyncio
async def test_update_project(client):
    create_resp = await client.post("/projects", json={"name": "Original", "path": "/orig"})
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    response = await client.put(f"/projects/{project_id}", json={"name": "Updated", "path": "/new"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated"
    assert data["path"] == "/new"
    assert data["id"] == project_id


@pytest.mark.asyncio
async def test_update_project_not_found(client):
    response = await client.put("/projects/nonexistent", json={"name": "X"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_project_excludes_github_pat(client):
    create_resp = await client.post("/projects", json={"name": "Secret", "path": "/sec"})
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    response = await client.put(f"/projects/{project_id}", json={"github_pat": "my-secret-token"})
    assert response.status_code == 200
    data = response.json()
    assert "github_pat" not in data


@pytest.mark.asyncio
async def test_get_run_edits(client):
    # Create a project and run, then add edits directly via store
    store = client._transport.app.state.store
    run = Run(id="run-edits-1", project_id="proj-x", instruction="test", status="running")
    await store.create_run(run)

    edit = EditRecord(run_id="run-edits-1", file_path="foo.py", status="proposed")
    await store.create_edit(edit)

    response = await client.get("/runs/run-edits-1/edits")
    assert response.status_code == 200
    edits = response.json()
    assert len(edits) == 1
    assert edits[0]["file_path"] == "foo.py"


@pytest.mark.asyncio
async def test_get_run_edits_status_filter(client):
    store = client._transport.app.state.store
    run = Run(id="run-edits-2", project_id="proj-y", instruction="test", status="running")
    await store.create_run(run)

    edit_proposed = EditRecord(run_id="run-edits-2", file_path="a.py", status="proposed")
    edit_applied = EditRecord(run_id="run-edits-2", file_path="b.py", status="applied")
    await store.create_edit(edit_proposed)
    await store.create_edit(edit_applied)

    response = await client.get("/runs/run-edits-2/edits?status=proposed")
    assert response.status_code == 200
    edits = response.json()
    assert len(edits) == 1
    assert edits[0]["file_path"] == "a.py"
    assert edits[0]["status"] == "proposed"


@pytest.mark.asyncio
async def test_list_projects_excludes_github_pat(client):
    await client.post("/projects", json={"name": "PatTest", "path": "/pat"})

    response = await client.get("/projects")
    assert response.status_code == 200
    projects = response.json()
    for p in projects:
        assert "github_pat" not in p


# ---------------------------------------------------------------------------
# /browse endpoint tests (enhanced with files, filtering, project scoping)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def browse_project(client, tmp_path):
    """Create a project with a known filesystem layout for browse tests."""
    # Create directory structure
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("print('hello')")
    (tmp_path / "README.md").write_text("# Test")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / ".venv").mkdir()

    # Create project pointing to tmp_path
    resp = await client.post("/projects", json={
        "name": "BrowseTest",
        "path": str(tmp_path),
    })
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_browse_returns_files(client, browse_project):
    """GET /browse returns both files and directories."""
    pid = browse_project["id"]
    resp = await client.get(f"/browse?project_id={pid}")
    assert resp.status_code == 200
    data = resp.json()
    entries = data["entries"]
    names = {e["name"] for e in entries}
    assert "src" in names  # directory
    assert "README.md" in names  # file
    # Check both types present
    dir_entries = [e for e in entries if e["is_dir"]]
    file_entries = [e for e in entries if not e["is_dir"]]
    assert len(dir_entries) >= 1
    assert len(file_entries) >= 1


@pytest.mark.asyncio
async def test_browse_subdir(client, browse_project):
    """GET /browse with path=subdir returns children of that subdir."""
    pid = browse_project["id"]
    resp = await client.get(f"/browse?project_id={pid}&path=src")
    assert resp.status_code == 200
    data = resp.json()
    entries = data["entries"]
    names = {e["name"] for e in entries}
    assert "main.py" in names


@pytest.mark.asyncio
async def test_browse_filters_ignored(client, browse_project):
    """Entries named .git, node_modules, __pycache__, .venv are excluded."""
    pid = browse_project["id"]
    resp = await client.get(f"/browse?project_id={pid}")
    assert resp.status_code == 200
    data = resp.json()
    names = {e["name"] for e in data["entries"]}
    assert ".git" not in names
    assert "node_modules" not in names
    assert "__pycache__" not in names
    assert ".venv" not in names


@pytest.mark.asyncio
async def test_browse_path_traversal(client, browse_project):
    """Path traversal attempts return 403."""
    pid = browse_project["id"]
    resp = await client.get(f"/browse?project_id={pid}&path=../../etc")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_browse_nonexistent_project(client):
    """Nonexistent project_id returns 404."""
    resp = await client.get("/browse?project_id=nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_browse_file_entry_has_size(client, browse_project):
    """File entries include size field as integer bytes."""
    pid = browse_project["id"]
    resp = await client.get(f"/browse?project_id={pid}")
    assert resp.status_code == 200
    file_entries = [e for e in resp.json()["entries"] if not e["is_dir"]]
    assert len(file_entries) >= 1
    for entry in file_entries:
        assert "size" in entry
        assert isinstance(entry["size"], int)


@pytest.mark.asyncio
async def test_browse_dir_entry_has_children(client, browse_project):
    """Directory entries include has_children boolean."""
    pid = browse_project["id"]
    resp = await client.get(f"/browse?project_id={pid}")
    assert resp.status_code == 200
    dir_entries = [e for e in resp.json()["entries"] if e["is_dir"]]
    assert len(dir_entries) >= 1
    for entry in dir_entries:
        assert "has_children" in entry
        assert isinstance(entry["has_children"], bool)


@pytest.mark.asyncio
async def test_browse_sorted_dirs_first(client, browse_project):
    """Entries sorted: directories first, then files, alphabetically."""
    pid = browse_project["id"]
    resp = await client.get(f"/browse?project_id={pid}")
    assert resp.status_code == 200
    entries = resp.json()["entries"]
    # All dirs should come before all files
    saw_file = False
    for entry in entries:
        if entry["is_dir"]:
            assert not saw_file, "Directory appeared after a file"
        else:
            saw_file = True


# ---------------------------------------------------------------------------
# /files endpoint tests (file content with language detection)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def files_project(client, tmp_path):
    """Create a project with known files for /files tests."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.py").write_text("print('hello')")
    (tmp_path / "README.md").write_text("# Test Project")
    (tmp_path / "style.css").write_text("body { color: red; }")
    (tmp_path / "data").mkdir()
    # Binary file (PNG header)
    (tmp_path / "icon.png").write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 20)

    resp = await client.post("/projects", json={
        "name": "FilesTest",
        "path": str(tmp_path),
    })
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_files_returns_content(client, files_project):
    """GET /files returns file content with language detection."""
    pid = files_project["id"]
    resp = await client.get(f"/files?project_id={pid}&path=src/main.py")
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "print('hello')"
    assert data["language"] == "python"
    assert isinstance(data["size"], int)
    assert data["size"] > 0


@pytest.mark.asyncio
async def test_files_markdown_language(client, files_project):
    """README.md returns language 'markdown'."""
    pid = files_project["id"]
    resp = await client.get(f"/files?project_id={pid}&path=README.md")
    assert resp.status_code == 200
    assert resp.json()["language"] == "markdown"


@pytest.mark.asyncio
async def test_files_css_language(client, files_project):
    """style.css returns language 'css'."""
    pid = files_project["id"]
    resp = await client.get(f"/files?project_id={pid}&path=style.css")
    assert resp.status_code == 200
    assert resp.json()["language"] == "css"


@pytest.mark.asyncio
async def test_files_path_traversal(client, files_project):
    """Path traversal attempts return 403."""
    pid = files_project["id"]
    resp = await client.get(f"/files?project_id={pid}&path=../../etc/passwd")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_files_not_found(client, files_project):
    """Nonexistent file returns 404."""
    pid = files_project["id"]
    resp = await client.get(f"/files?project_id={pid}&path=nonexistent.txt")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_files_directory_returns_400(client, files_project):
    """Requesting a directory returns 400."""
    pid = files_project["id"]
    resp = await client.get(f"/files?project_id={pid}&path=data")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_files_nonexistent_project(client):
    """Nonexistent project returns 404."""
    resp = await client.get("/files?project_id=nonexistent&path=foo")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_files_binary_detection(client, files_project):
    """Binary files return content=null and binary=true."""
    pid = files_project["id"]
    resp = await client.get(f"/files?project_id={pid}&path=icon.png")
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] is None
    assert data["language"] == "binary"
    assert data["binary"] is True
    assert isinstance(data["size"], int)
