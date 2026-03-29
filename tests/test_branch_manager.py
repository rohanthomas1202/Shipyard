"""Tests for BranchManager git branch lifecycle operations."""
import asyncio
from unittest.mock import AsyncMock, call, patch

import pytest

from agent.orchestrator.branch_manager import BranchManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "") -> dict:
    """Simulate a successful git command."""
    return {"stdout": stdout, "stderr": "", "exit_code": 0}


def _fail(stderr: str = "error") -> dict:
    """Simulate a failed git command."""
    return {"stdout": "", "stderr": stderr, "exit_code": 1}


PATCH_TARGET = "agent.orchestrator.branch_manager.run_command_async"


# ---------------------------------------------------------------------------
# create_and_checkout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_and_checkout():
    """create_and_checkout checks out base, deletes stale branch, creates new."""
    mock_run = AsyncMock(return_value=_ok())
    bm = BranchManager("/repo")

    with patch(PATCH_TARGET, mock_run):
        result = await bm.create_and_checkout("agent/task-42")

    assert result is True
    calls = mock_run.call_args_list
    # 1. checkout main
    assert calls[0] == call(["git", "checkout", "main"], cwd="/repo", timeout=30)
    # 2. force-delete stale branch (may fail, that's ok)
    assert calls[1] == call(["git", "branch", "-D", "agent/task-42"], cwd="/repo", timeout=30)
    # 3. create and checkout new branch
    assert calls[2] == call(["git", "checkout", "-b", "agent/task-42"], cwd="/repo", timeout=30)


@pytest.mark.asyncio
async def test_create_and_checkout_stale_branch_cleanup():
    """Stale branch delete failure is ignored; create still proceeds."""
    responses = [_ok(), _fail("branch not found"), _ok()]
    mock_run = AsyncMock(side_effect=responses)
    bm = BranchManager("/repo")

    with patch(PATCH_TARGET, mock_run):
        result = await bm.create_and_checkout("agent/task-7")

    assert result is True
    assert mock_run.call_count == 3


@pytest.mark.asyncio
async def test_create_and_checkout_idempotent():
    """Calling create_and_checkout twice for same branch succeeds both times."""
    mock_run = AsyncMock(return_value=_ok())
    bm = BranchManager("/repo")

    with patch(PATCH_TARGET, mock_run):
        r1 = await bm.create_and_checkout("agent/task-1")
        r2 = await bm.create_and_checkout("agent/task-1")

    assert r1 is True
    assert r2 is True


# ---------------------------------------------------------------------------
# rebase_and_merge
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rebase_and_merge_success():
    """Successful rebase followed by ff-only merge."""
    mock_run = AsyncMock(return_value=_ok())
    bm = BranchManager("/repo")

    with patch(PATCH_TARGET, mock_run):
        result = await bm.rebase_and_merge("agent/task-5")

    assert result is True
    calls = mock_run.call_args_list
    # checkout branch -> rebase main -> checkout main -> merge --ff-only
    assert calls[0] == call(["git", "checkout", "agent/task-5"], cwd="/repo", timeout=30)
    assert calls[1] == call(["git", "rebase", "main"], cwd="/repo", timeout=30)
    assert calls[2] == call(["git", "checkout", "main"], cwd="/repo", timeout=30)
    assert calls[3] == call(["git", "merge", "--ff-only", "agent/task-5"], cwd="/repo", timeout=30)


@pytest.mark.asyncio
async def test_rebase_conflict_aborts():
    """Rebase conflict triggers abort and returns False."""
    responses = [_ok(), _fail("CONFLICT"), _ok()]  # checkout, rebase fail, abort
    mock_run = AsyncMock(side_effect=responses)
    bm = BranchManager("/repo")

    with patch(PATCH_TARGET, mock_run):
        result = await bm.rebase_and_merge("agent/task-9")

    assert result is False
    calls = mock_run.call_args_list
    assert calls[0] == call(["git", "checkout", "agent/task-9"], cwd="/repo", timeout=30)
    assert calls[1] == call(["git", "rebase", "main"], cwd="/repo", timeout=30)
    assert calls[2] == call(["git", "rebase", "--abort"], cwd="/repo", timeout=30)
    # No merge attempt after conflict
    assert mock_run.call_count == 3


# ---------------------------------------------------------------------------
# cleanup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cleanup():
    """Cleanup checks out main and force-deletes branch."""
    mock_run = AsyncMock(return_value=_ok())
    bm = BranchManager("/repo")

    with patch(PATCH_TARGET, mock_run):
        await bm.cleanup("agent/task-3")

    calls = mock_run.call_args_list
    assert calls[0] == call(["git", "checkout", "main"], cwd="/repo", timeout=30)
    assert calls[1] == call(["git", "branch", "-D", "agent/task-3"], cwd="/repo", timeout=30)


# ---------------------------------------------------------------------------
# verify_branch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_branch():
    """verify_branch returns current branch name."""
    mock_run = AsyncMock(return_value=_ok("agent/task-42\n"))
    bm = BranchManager("/repo")

    with patch(PATCH_TARGET, mock_run):
        branch = await bm.verify_branch()

    assert branch == "agent/task-42"
    mock_run.assert_called_once_with(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd="/repo", timeout=30
    )


# ---------------------------------------------------------------------------
# Lock serialization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lock_serialization():
    """Concurrent calls are serialized via asyncio.Lock (no interleaving)."""
    call_order: list[str] = []

    async def tracking_run(argv: list[str], **kwargs) -> dict:
        label = f"{argv[1]}:{argv[-1]}"
        call_order.append(f"start:{label}")
        await asyncio.sleep(0.01)  # simulate async work
        call_order.append(f"end:{label}")
        return _ok()

    mock_run = AsyncMock(side_effect=tracking_run)
    bm = BranchManager("/repo")

    with patch(PATCH_TARGET, mock_run):
        # Launch two concurrent create_and_checkout calls
        await asyncio.gather(
            bm.create_and_checkout("branch-a"),
            bm.create_and_checkout("branch-b"),
        )

    # With lock serialization, all calls from branch-a should complete
    # before branch-b starts (or vice versa). Find the boundary.
    a_indices = [i for i, c in enumerate(call_order) if "branch-a" in c]
    b_indices = [i for i, c in enumerate(call_order) if "branch-b" in c]

    # No interleaving: all of one group comes before all of the other
    assert max(a_indices) < min(b_indices) or max(b_indices) < min(a_indices), \
        f"Calls interleaved: {call_order}"
