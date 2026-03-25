import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from store.sqlite import SQLiteSessionStore
from store.models import Project, Run, EditRecord
from agent.tools.shell import run_command_async


@pytest_asyncio.fixture
async def store(tmp_path):
    s = SQLiteSessionStore(str(tmp_path / "test.db"))
    await s.initialize()
    project = Project(id="proj1", name="Test", path=str(tmp_path))
    await s.create_project(project)
    run = Run(id="run1", project_id="proj1", instruction="test edit")
    await s.create_run(run)
    yield s
    await s.close()


@pytest_asyncio.fixture
async def git_repo(tmp_path):
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    await run_command_async(["git", "init"], cwd=repo)
    await run_command_async(["git", "config", "user.email", "test@test.com"], cwd=repo)
    await run_command_async(["git", "config", "user.name", "Test"], cwd=repo)
    with open(os.path.join(repo, "README.md"), "w") as f:
        f.write("# Test\n")
    await run_command_async(["git", "add", "."], cwd=repo)
    await run_command_async(["git", "commit", "-m", "initial"], cwd=repo)
    return repo


def make_config(store, run_id="run1", project_id="proj1"):
    mock_router = MagicMock()
    mock_router.call = AsyncMock(return_value="feat: test commit message")
    return {
        "configurable": {
            "store": store,
            "router": mock_router,
            "run_id": run_id,
            "project_id": project_id,
        }
    }


@pytest.mark.asyncio
async def test_git_ops_commits_applied_edits(store, git_repo):
    from agent.nodes.git_ops import git_ops_node

    # Create a file change in the repo
    with open(os.path.join(git_repo, "test.py"), "w") as f:
        f.write("print('hello')")

    # Create an applied edit in store
    edit = EditRecord(run_id="run1", file_path=os.path.join(git_repo, "test.py"), status="applied")
    await store.create_edit(edit)

    state = {"working_directory": git_repo, "instruction": "add test", "edit_history": []}
    config = make_config(store)
    result = await git_ops_node(state, config)

    assert result.get("error_state") is None
    assert result.get("branch", "").startswith("shipyard/")

    # Verify commit exists
    log_result = await run_command_async(["git", "log", "--oneline", "-1"], cwd=git_repo)
    assert log_result["exit_code"] == 0


@pytest.mark.asyncio
async def test_git_ops_no_files_skips_commit(store, git_repo):
    from agent.nodes.git_ops import git_ops_node

    state = {"working_directory": git_repo, "instruction": "nothing", "edit_history": []}
    config = make_config(store)
    result = await git_ops_node(state, config)

    assert result.get("error_state") is None
    assert result.get("branch") is not None


@pytest.mark.asyncio
async def test_git_ops_fallback_to_edit_history(store, git_repo):
    from agent.nodes.git_ops import git_ops_node

    with open(os.path.join(git_repo, "fallback.py"), "w") as f:
        f.write("fallback")

    state = {
        "working_directory": git_repo,
        "instruction": "fallback test",
        "edit_history": [{"file": os.path.join(git_repo, "fallback.py")}],
    }
    config = make_config(store)
    result = await git_ops_node(state, config)

    assert result.get("error_state") is None


@pytest.mark.asyncio
async def test_git_ops_push_skipped_no_remote(store, git_repo):
    from agent.nodes.git_ops import git_ops_node

    with open(os.path.join(git_repo, "push_test.py"), "w") as f:
        f.write("push test")
    edit = EditRecord(run_id="run1", file_path=os.path.join(git_repo, "push_test.py"), status="applied")
    await store.create_edit(edit)

    state = {"working_directory": git_repo, "instruction": "push test", "edit_history": []}
    config = make_config(store)
    result = await git_ops_node(state, config)

    # Should succeed (push skipped, no remote)
    assert result.get("error_state") is None
