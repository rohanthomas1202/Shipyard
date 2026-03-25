"""Tests for ApprovalManager — edit lifecycle state machine."""
from __future__ import annotations
import os
import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock

from store.models import EditRecord, Project, Run
from store.sqlite import SQLiteSessionStore
from agent.approval import ApprovalManager, InvalidTransitionError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = str(tmp_path / "test.db")
    s = SQLiteSessionStore(db_path)
    await s.initialize()
    yield s
    await s.close()


@pytest_asyncio.fixture
async def project_and_run(store):
    """Create a Project and Run; return (project, run)."""
    project = Project(name="test-project", path="/tmp/test-project")
    await store.create_project(project)
    run = Run(project_id=project.id, instruction="test instruction")
    await store.create_run(run)
    return project, run


@pytest.fixture
def mock_event_bus():
    bus = MagicMock()
    bus.emit = AsyncMock()
    return bus


@pytest_asyncio.fixture
async def manager(store, mock_event_bus):
    return ApprovalManager(store=store, event_bus=mock_event_bus)


@pytest_asyncio.fixture
async def proposed_edit(store, project_and_run, manager):
    """Return an EditRecord that has been proposed via propose_edit."""
    _, run = project_and_run
    edit = EditRecord(run_id=run.id, file_path="foo.py", old_content="old", new_content="new")
    return await manager.propose_edit(run.id, edit)


# ---------------------------------------------------------------------------
# is_valid_transition
# ---------------------------------------------------------------------------

class TestIsValidTransition:
    def test_proposed_to_approved(self, manager):
        assert manager.is_valid_transition("proposed", "approved") is True

    def test_proposed_to_rejected(self, manager):
        assert manager.is_valid_transition("proposed", "rejected") is True

    def test_approved_to_applied(self, manager):
        assert manager.is_valid_transition("approved", "applied") is True

    def test_applied_to_committed(self, manager):
        assert manager.is_valid_transition("applied", "committed") is True

    def test_proposed_to_applied_skips_step(self, manager):
        assert manager.is_valid_transition("proposed", "applied") is False

    def test_approved_to_rejected(self, manager):
        assert manager.is_valid_transition("approved", "rejected") is False

    def test_committed_to_anything(self, manager):
        for target in ("proposed", "approved", "rejected", "applied", "committed"):
            assert manager.is_valid_transition("committed", target) is False

    def test_rejected_to_anything(self, manager):
        for target in ("proposed", "approved", "rejected", "applied", "committed"):
            assert manager.is_valid_transition("rejected", target) is False

    def test_same_to_same(self, manager):
        for status in ("proposed", "approved", "rejected", "applied", "committed"):
            assert manager.is_valid_transition(status, status) is False


# ---------------------------------------------------------------------------
# propose_edit
# ---------------------------------------------------------------------------

class TestProposeEdit:
    @pytest.mark.asyncio
    async def test_creates_with_proposed_status(self, store, project_and_run, manager):
        _, run = project_and_run
        edit = EditRecord(run_id=run.id, file_path="bar.py")
        result = await manager.propose_edit(run.id, edit)
        assert result.status == "proposed"

    @pytest.mark.asyncio
    async def test_persisted_in_store(self, store, project_and_run, manager):
        _, run = project_and_run
        edit = EditRecord(run_id=run.id, file_path="bar.py")
        result = await manager.propose_edit(run.id, edit)
        fetched = await store.get_edit(result.id)
        assert fetched is not None
        assert fetched.id == result.id
        assert fetched.status == "proposed"

    @pytest.mark.asyncio
    async def test_emits_event_with_correct_type_and_subtype(self, project_and_run, manager, mock_event_bus):
        _, run = project_and_run
        edit = EditRecord(run_id=run.id, file_path="bar.py")
        result = await manager.propose_edit(run.id, edit)
        mock_event_bus.emit.assert_called_once()
        emitted = mock_event_bus.emit.call_args[0][0]
        assert emitted.type == "approval"
        assert emitted.data["event"] == "edit.proposed"
        assert emitted.data["edit_id"] == result.id
        assert emitted.run_id == run.id

    @pytest.mark.asyncio
    async def test_emitted_event_has_correct_project_id(self, project_and_run, manager, mock_event_bus):
        project, run = project_and_run
        edit = EditRecord(run_id=run.id, file_path="bar.py")
        await manager.propose_edit(run.id, edit)
        emitted = mock_event_bus.emit.call_args[0][0]
        assert emitted.project_id == project.id


# ---------------------------------------------------------------------------
# approve
# ---------------------------------------------------------------------------

class TestApprove:
    @pytest.mark.asyncio
    async def test_transitions_proposed_to_approved(self, store, proposed_edit, manager):
        result = await manager.approve(proposed_edit.id, "op-1")
        assert result.status == "approved"

    @pytest.mark.asyncio
    async def test_persisted_in_store(self, store, proposed_edit, manager):
        await manager.approve(proposed_edit.id, "op-1")
        fetched = await store.get_edit(proposed_edit.id)
        assert fetched.status == "approved"
        assert fetched.last_op_id == "op-1"

    @pytest.mark.asyncio
    async def test_idempotent_same_op_id(self, store, proposed_edit, manager, mock_event_bus):
        await manager.approve(proposed_edit.id, "op-1")
        mock_event_bus.emit.reset_mock()
        # Second call with same op_id: should not raise, should not emit again
        result = await manager.approve(proposed_edit.id, "op-1")
        assert result.status == "approved"
        mock_event_bus.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_emits_approval_event(self, proposed_edit, manager, mock_event_bus):
        mock_event_bus.emit.reset_mock()
        await manager.approve(proposed_edit.id, "op-1")
        mock_event_bus.emit.assert_called_once()
        emitted = mock_event_bus.emit.call_args[0][0]
        assert emitted.type == "approval"
        assert emitted.data["event"] == "edit.approved"
        assert emitted.data["edit_id"] == proposed_edit.id

    @pytest.mark.asyncio
    async def test_raises_invalid_transition_for_already_approved(self, proposed_edit, manager):
        await manager.approve(proposed_edit.id, "op-1")
        with pytest.raises(InvalidTransitionError):
            await manager.approve(proposed_edit.id, "op-2")  # different op_id, already approved

    @pytest.mark.asyncio
    async def test_raises_value_error_for_nonexistent_edit(self, manager):
        with pytest.raises(ValueError, match="not found"):
            await manager.approve("nonexistent-id", "op-1")


# ---------------------------------------------------------------------------
# reject
# ---------------------------------------------------------------------------

class TestReject:
    @pytest.mark.asyncio
    async def test_transitions_proposed_to_rejected(self, store, proposed_edit, manager):
        result = await manager.reject(proposed_edit.id, "op-r1")
        assert result.status == "rejected"

    @pytest.mark.asyncio
    async def test_persisted_in_store(self, store, proposed_edit, manager):
        await manager.reject(proposed_edit.id, "op-r1")
        fetched = await store.get_edit(proposed_edit.id)
        assert fetched.status == "rejected"

    @pytest.mark.asyncio
    async def test_idempotent_same_op_id(self, proposed_edit, manager, mock_event_bus):
        await manager.reject(proposed_edit.id, "op-r1")
        mock_event_bus.emit.reset_mock()
        result = await manager.reject(proposed_edit.id, "op-r1")
        assert result.status == "rejected"
        mock_event_bus.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_raises_invalid_transition_for_approved_edit(self, proposed_edit, manager):
        await manager.approve(proposed_edit.id, "op-a1")
        with pytest.raises(InvalidTransitionError):
            await manager.reject(proposed_edit.id, "op-r1")

    @pytest.mark.asyncio
    async def test_emits_rejection_event(self, proposed_edit, manager, mock_event_bus):
        mock_event_bus.emit.reset_mock()
        await manager.reject(proposed_edit.id, "op-r1")
        mock_event_bus.emit.assert_called_once()
        emitted = mock_event_bus.emit.call_args[0][0]
        assert emitted.type == "approval"
        assert emitted.data["event"] == "edit.rejected"
        assert emitted.data["edit_id"] == proposed_edit.id

    @pytest.mark.asyncio
    async def test_raises_value_error_for_nonexistent_edit(self, manager):
        with pytest.raises(ValueError, match="not found"):
            await manager.reject("nonexistent-id", "op-r1")


# ---------------------------------------------------------------------------
# apply_edit
# ---------------------------------------------------------------------------

class TestApplyEdit:
    @pytest_asyncio.fixture
    async def approved_edit(self, store, project_and_run, manager, tmp_path):
        """An approved edit pointing at a real temp file."""
        _, run = project_and_run
        target_file = tmp_path / "target.py"
        target_file.write_text("old content here")
        edit = EditRecord(
            run_id=run.id,
            file_path=str(target_file),
            old_content="old content here",
            new_content="new content here",
        )
        proposed = await manager.propose_edit(run.id, edit)
        await manager.approve(proposed.id, "op-approve")
        return proposed

    @pytest.mark.asyncio
    async def test_transitions_approved_to_applied(self, approved_edit, manager):
        result = await manager.apply_edit(approved_edit.id)
        assert result.status == "applied"

    @pytest.mark.asyncio
    async def test_writes_to_filesystem(self, store, approved_edit, manager):
        edit = await store.get_edit(approved_edit.id)
        result = await manager.apply_edit(approved_edit.id)
        with open(result.file_path, "r") as f:
            content = f.read()
        assert content == "new content here"

    @pytest.mark.asyncio
    async def test_raises_invalid_transition_for_proposed(self, store, project_and_run, manager, tmp_path):
        _, run = project_and_run
        target_file = tmp_path / "notapproved.py"
        target_file.write_text("content")
        edit = EditRecord(run_id=run.id, file_path=str(target_file), new_content="updated")
        proposed = await manager.propose_edit(run.id, edit)
        with pytest.raises(InvalidTransitionError):
            await manager.apply_edit(proposed.id)

    @pytest.mark.asyncio
    async def test_file_write_failure_keeps_status_approved(self, store, project_and_run, manager):
        """If file path doesn't exist, OSError is raised and status stays approved."""
        _, run = project_and_run
        edit = EditRecord(
            run_id=run.id,
            file_path="/nonexistent/path/file.py",
            old_content="x",
            new_content="y",
        )
        proposed = await manager.propose_edit(run.id, edit)
        await manager.approve(proposed.id, "op-approve")

        with pytest.raises(OSError):
            await manager.apply_edit(proposed.id)

        fetched = await store.get_edit(proposed.id)
        assert fetched.status == "approved"

    @pytest.mark.asyncio
    async def test_emits_applied_event(self, approved_edit, manager, mock_event_bus):
        mock_event_bus.emit.reset_mock()
        result = await manager.apply_edit(approved_edit.id)
        mock_event_bus.emit.assert_called_once()
        emitted = mock_event_bus.emit.call_args[0][0]
        assert emitted.type == "approval"
        assert emitted.data["event"] == "edit.applied"
        assert emitted.data["edit_id"] == approved_edit.id


# ---------------------------------------------------------------------------
# mark_committed
# ---------------------------------------------------------------------------

class TestMarkCommitted:
    @pytest_asyncio.fixture
    async def applied_edit(self, store, project_and_run, manager, tmp_path):
        _, run = project_and_run
        target_file = tmp_path / "commit_target.py"
        target_file.write_text("old")
        edit = EditRecord(
            run_id=run.id,
            file_path=str(target_file),
            old_content="old",
            new_content="new",
        )
        proposed = await manager.propose_edit(run.id, edit)
        await manager.approve(proposed.id, "op-a")
        await manager.apply_edit(proposed.id)
        return proposed

    @pytest.mark.asyncio
    async def test_transitions_applied_to_committed(self, store, project_and_run, applied_edit, manager):
        _, run = project_and_run
        await manager.mark_committed(run.id, [applied_edit.id])
        fetched = await store.get_edit(applied_edit.id)
        assert fetched.status == "committed"

    @pytest.mark.asyncio
    async def test_skips_non_applied_edits_silently(self, store, project_and_run, proposed_edit, manager):
        _, run = project_and_run
        # proposed_edit is in "proposed" status — should be silently skipped
        await manager.mark_committed(run.id, [proposed_edit.id])
        fetched = await store.get_edit(proposed_edit.id)
        assert fetched.status == "proposed"

    @pytest.mark.asyncio
    async def test_emits_event_only_for_transitioned_edits(
        self, store, project_and_run, applied_edit, proposed_edit, manager, mock_event_bus
    ):
        _, run = project_and_run
        mock_event_bus.emit.reset_mock()
        await manager.mark_committed(run.id, [applied_edit.id, proposed_edit.id])
        mock_event_bus.emit.assert_called_once()
        emitted = mock_event_bus.emit.call_args[0][0]
        assert emitted.type == "approval"
        assert emitted.data["event"] == "edit.committed"
        assert applied_edit.id in emitted.data["edit_ids"]
        assert proposed_edit.id not in emitted.data["edit_ids"]

    @pytest.mark.asyncio
    async def test_emitted_event_includes_run_id(
        self, project_and_run, applied_edit, manager, mock_event_bus
    ):
        _, run = project_and_run
        mock_event_bus.emit.reset_mock()
        await manager.mark_committed(run.id, [applied_edit.id])
        emitted = mock_event_bus.emit.call_args[0][0]
        assert emitted.run_id == run.id

    @pytest.mark.asyncio
    async def test_no_event_when_no_edits_transition(
        self, project_and_run, proposed_edit, manager, mock_event_bus
    ):
        _, run = project_and_run
        mock_event_bus.emit.reset_mock()
        await manager.mark_committed(run.id, [proposed_edit.id])
        mock_event_bus.emit.assert_not_called()


# ---------------------------------------------------------------------------
# auto_approve_pending
# ---------------------------------------------------------------------------

class TestAutoApprovePending:
    @pytest.mark.asyncio
    async def test_approves_all_proposed_returns_list(self, store, project_and_run, manager):
        _, run = project_and_run
        e1 = EditRecord(run_id=run.id, file_path="a.py")
        e2 = EditRecord(run_id=run.id, file_path="b.py")
        await manager.propose_edit(run.id, e1)
        await manager.propose_edit(run.id, e2)
        approved = await manager.auto_approve_pending(run.id)
        assert len(approved) == 2
        assert all(e.status == "approved" for e in approved)

    @pytest.mark.asyncio
    async def test_does_not_apply_edits(self, store, project_and_run, manager):
        """Status should be approved, NOT applied."""
        _, run = project_and_run
        e1 = EditRecord(run_id=run.id, file_path="c.py")
        await manager.propose_edit(run.id, e1)
        approved = await manager.auto_approve_pending(run.id)
        assert all(e.status == "approved" for e in approved)
        fetched = await store.get_edit(approved[0].id)
        assert fetched.status == "approved"

    @pytest.mark.asyncio
    async def test_ignores_rejected_edits(self, store, project_and_run, manager):
        _, run = project_and_run
        e1 = EditRecord(run_id=run.id, file_path="d.py")
        e2 = EditRecord(run_id=run.id, file_path="e.py")
        p1 = await manager.propose_edit(run.id, e1)
        await manager.propose_edit(run.id, e2)
        await manager.reject(p1.id, "op-reject")
        approved = await manager.auto_approve_pending(run.id)
        # Only e2 should be approved; e1 is rejected and not in pending
        assert len(approved) == 1
        assert approved[0].status == "approved"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_pending(self, store, project_and_run, manager):
        _, run = project_and_run
        result = await manager.auto_approve_pending(run.id)
        assert result == []


# ---------------------------------------------------------------------------
# get_pending
# ---------------------------------------------------------------------------

class TestGetPending:
    @pytest.mark.asyncio
    async def test_returns_only_proposed_edits(self, store, project_and_run, manager):
        _, run = project_and_run
        e1 = EditRecord(run_id=run.id, file_path="p1.py")
        e2 = EditRecord(run_id=run.id, file_path="p2.py")
        p1 = await manager.propose_edit(run.id, e1)
        await manager.propose_edit(run.id, e2)
        await manager.approve(p1.id, "op-a")
        pending = await manager.get_pending(run.id)
        ids = {e.id for e in pending}
        assert p1.id not in ids  # approved, not pending
        assert all(e.status == "proposed" for e in pending)

    @pytest.mark.asyncio
    async def test_empty_when_none_proposed(self, store, project_and_run, manager):
        _, run = project_and_run
        pending = await manager.get_pending(run.id)
        assert pending == []

    @pytest.mark.asyncio
    async def test_multiple_proposed_all_returned(self, store, project_and_run, manager):
        _, run = project_and_run
        for i in range(3):
            e = EditRecord(run_id=run.id, file_path=f"file{i}.py")
            await manager.propose_edit(run.id, e)
        pending = await manager.get_pending(run.id)
        assert len(pending) == 3
        assert all(e.status == "proposed" for e in pending)


# ---------------------------------------------------------------------------
# batch propose/approve/reject
# ---------------------------------------------------------------------------

class TestBatchApproval:
    """Test batch propose/approve/reject for refactor operations."""

    @pytest.mark.asyncio
    async def test_propose_batch(self, manager, project_and_run):
        _, run = project_and_run
        records = [
            EditRecord(run_id=run.id, file_path="/tmp/a.ts", old_content="old1", new_content="new1"),
            EditRecord(run_id=run.id, file_path="/tmp/b.ts", old_content="old2", new_content="new2"),
        ]
        result = await manager.propose_batch(run.id, records, "batch-1")
        assert len(result) == 2
        assert all(r.status == "proposed" for r in result)
        assert all(r.batch_id == "batch-1" for r in result)

    @pytest.mark.asyncio
    async def test_approve_batch(self, manager, project_and_run):
        _, run = project_and_run
        records = [
            EditRecord(run_id=run.id, file_path="/tmp/a.ts", old_content="old1", new_content="new1"),
            EditRecord(run_id=run.id, file_path="/tmp/b.ts", old_content="old2", new_content="new2"),
        ]
        await manager.propose_batch(run.id, records, "batch-2")
        approved = await manager.approve_batch("batch-2", "op-approve-1")
        assert len(approved) == 2
        assert all(r.status == "approved" for r in approved)

    @pytest.mark.asyncio
    async def test_reject_batch(self, manager, project_and_run):
        _, run = project_and_run
        records = [
            EditRecord(run_id=run.id, file_path="/tmp/a.ts", old_content="old1", new_content="new1"),
        ]
        await manager.propose_batch(run.id, records, "batch-3")
        rejected = await manager.reject_batch("batch-3", "op-reject-1")
        assert len(rejected) == 1
        assert rejected[0].status == "rejected"
