"""Tests for approval store prerequisites: EDIT_STATUSES, EditRecord, and SQLite methods."""
import pytest
import pytest_asyncio
import tempfile
import os
from pydantic import ValidationError

from store.models import EDIT_STATUSES, EditRecord
from store.sqlite import SQLiteSessionStore
from store.models import Run, Project


# --- Model tests ---

def test_edit_statuses_includes_all_five():
    """EDIT_STATUSES Literal includes all 5 valid states."""
    args = EDIT_STATUSES.__args__
    assert set(args) == {"proposed", "approved", "rejected", "applied", "committed"}


def test_edit_record_defaults_to_proposed():
    edit = EditRecord(run_id="run1", file_path="foo.py")
    assert edit.status == "proposed"


def test_edit_record_accepts_all_valid_statuses():
    for status in ("proposed", "approved", "rejected", "applied", "committed"):
        edit = EditRecord(run_id="run1", file_path="foo.py", status=status)
        assert edit.status == status


def test_edit_record_rejects_invalid_status():
    with pytest.raises(ValidationError):
        EditRecord(run_id="run1", file_path="foo.py", status="bogus")


def test_edit_record_has_last_op_id_defaulting_to_none():
    edit = EditRecord(run_id="run1", file_path="foo.py")
    assert edit.last_op_id is None


# --- SQLite integration tests ---

@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = str(tmp_path / "test.db")
    s = SQLiteSessionStore(db_path)
    await s.initialize()
    yield s
    await s.close()


@pytest_asyncio.fixture
async def run_id(store):
    project = Project(name="p", path="/tmp/p")
    await store.create_project(project)
    run = Run(project_id=project.id, instruction="test")
    await store.create_run(run)
    return run.id


@pytest.mark.asyncio
async def test_get_edit_returns_edit_record(store, run_id):
    edit = EditRecord(run_id=run_id, file_path="a.py")
    await store.create_edit(edit)
    result = await store.get_edit(edit.id)
    assert result is not None
    assert result.id == edit.id
    assert result.file_path == "a.py"


@pytest.mark.asyncio
async def test_get_edit_nonexistent_returns_none(store):
    result = await store.get_edit("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_create_edit_persists_last_op_id(store, run_id):
    edit = EditRecord(run_id=run_id, file_path="b.py", last_op_id="op-abc")
    await store.create_edit(edit)
    result = await store.get_edit(edit.id)
    assert result.last_op_id == "op-abc"


@pytest.mark.asyncio
async def test_update_edit_status_persists_both(store, run_id):
    edit = EditRecord(run_id=run_id, file_path="c.py")
    await store.create_edit(edit)
    await store.update_edit_status(edit.id, "approved", last_op_id="op-xyz")
    result = await store.get_edit(edit.id)
    assert result.status == "approved"
    assert result.last_op_id == "op-xyz"


@pytest.mark.asyncio
async def test_get_edits_filters_by_status(store, run_id):
    e1 = EditRecord(run_id=run_id, file_path="d.py", status="proposed")
    e2 = EditRecord(run_id=run_id, file_path="e.py", status="approved")
    await store.create_edit(e1)
    await store.create_edit(e2)
    proposed = await store.get_edits(run_id, status="proposed")
    assert all(e.status == "proposed" for e in proposed)
    assert any(e.id == e1.id for e in proposed)
    assert not any(e.id == e2.id for e in proposed)


@pytest.mark.asyncio
async def test_get_edits_without_status_returns_all(store, run_id):
    e1 = EditRecord(run_id=run_id, file_path="f.py", status="proposed")
    e2 = EditRecord(run_id=run_id, file_path="g.py", status="committed")
    await store.create_edit(e1)
    await store.create_edit(e2)
    all_edits = await store.get_edits(run_id)
    ids = {e.id for e in all_edits}
    assert e1.id in ids
    assert e2.id in ids


@pytest.mark.asyncio
async def test_idx_edits_run_status_index_exists(store):
    async with store._db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_edits_run_status'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row is not None
