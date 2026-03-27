import pytest
import pytest_asyncio
from store.sqlite import SQLiteSessionStore
from store.models import Project, Run, Event, EditRecord


@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = str(tmp_path / "test.db")
    s = SQLiteSessionStore(db_path)
    await s.initialize()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_create_and_get_project(store):
    project = Project(name="test-project", path="/tmp/test")
    created = await store.create_project(project)
    assert created.id == project.id
    fetched = await store.get_project(project.id)
    assert fetched is not None
    assert fetched.name == "test-project"
    assert fetched.path == "/tmp/test"


@pytest.mark.asyncio
async def test_list_projects(store):
    await store.create_project(Project(name="p1", path="/a"))
    await store.create_project(Project(name="p2", path="/b"))
    projects = await store.list_projects()
    assert len(projects) == 2


@pytest.mark.asyncio
async def test_create_and_get_run(store):
    project = Project(name="p", path="/tmp")
    await store.create_project(project)
    run = Run(project_id=project.id, instruction="do stuff")
    created = await store.create_run(run)
    assert created.status == "running"
    fetched = await store.get_run(run.id)
    assert fetched is not None
    assert fetched.instruction == "do stuff"


@pytest.mark.asyncio
async def test_update_run_status(store):
    project = Project(name="p", path="/tmp")
    await store.create_project(project)
    run = Run(project_id=project.id, instruction="test")
    await store.create_run(run)
    run.status = "completed"
    await store.update_run(run)
    fetched = await store.get_run(run.id)
    assert fetched.status == "completed"


@pytest.mark.asyncio
async def test_append_and_replay_events(store):
    e1 = Event(project_id="p1", run_id="r1", type="status", node="planner", seq=1, data={"step": 1})
    e2 = Event(project_id="p1", run_id="r1", type="diff", node="editor", seq=2, data={"file": "a.ts"})
    e3 = Event(project_id="p1", run_id="r1", type="status", node="validator", seq=3, data={"step": 2})
    await store.append_event(e1)
    await store.append_event(e2)
    await store.append_event(e3)
    events = await store.replay_events("r1")
    assert len(events) == 3
    assert events[0].type == "status"
    assert events[2].node == "validator"


@pytest.mark.asyncio
async def test_replay_events_after_cursor(store):
    e1 = Event(project_id="p1", run_id="r1", type="status", seq=1, data={"a": 1})
    e2 = Event(project_id="p1", run_id="r1", type="diff", seq=2, data={"b": 2})
    await store.append_event(e1)
    await store.append_event(e2)
    events = await store.replay_events("r1", after_seq=1)
    assert len(events) == 1
    assert events[0].id == e2.id


@pytest.mark.asyncio
async def test_create_and_get_edits(store):
    edit = EditRecord(run_id="r1", file_path="a.ts", step=0, status="proposed")
    await store.create_edit(edit)
    edits = await store.get_edits("r1")
    assert len(edits) == 1
    assert edits[0].file_path == "a.ts"


@pytest.mark.asyncio
async def test_update_edit_status(store):
    edit = EditRecord(run_id="r1", file_path="a.ts")
    await store.create_edit(edit)
    await store.update_edit_status(edit.id, "approved")
    edits = await store.get_edits("r1")
    assert edits[0].status == "approved"


@pytest.mark.asyncio
async def test_get_project_returns_none_for_missing(store):
    result = await store.get_project("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_get_run_returns_none_for_missing(store):
    result = await store.get_run("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_wal_mode_enabled(tmp_path):
    """SQLite database uses WAL journal mode after initialization."""
    db_path = str(tmp_path / "wal_test.db")
    s = SQLiteSessionStore(db_path)
    await s.initialize()
    try:
        async with s._db.execute("PRAGMA journal_mode") as cursor:
            row = await cursor.fetchone()
        assert row[0] == "wal"
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_git_ops_run_index_exists(tmp_path):
    from store.sqlite import SQLiteSessionStore
    store = SQLiteSessionStore(str(tmp_path / "test.db"))
    await store.initialize()
    try:
        async with store._db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_git_ops_run'"
        ) as cursor:
            row = await cursor.fetchone()
        assert row is not None
    finally:
        await store.close()
