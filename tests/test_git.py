import os
import pytest
import pytest_asyncio
from agent.git import GitManager
from agent.tools.shell import run_command_async


@pytest_asyncio.fixture
async def git_repo(tmp_path):
    """Create a temp git repo with an initial commit."""
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    await run_command_async(["git", "init"], cwd=repo)
    await run_command_async(["git", "config", "user.email", "test@test.com"], cwd=repo)
    await run_command_async(["git", "config", "user.name", "Test"], cwd=repo)
    # Create initial commit
    with open(os.path.join(repo, "README.md"), "w") as f:
        f.write("# Test\n")
    await run_command_async(["git", "add", "."], cwd=repo)
    await run_command_async(["git", "commit", "-m", "initial"], cwd=repo)
    return repo


@pytest.mark.asyncio
async def test_get_current_branch(git_repo):
    gm = GitManager(git_repo)
    branch = await gm.get_current_branch()
    assert branch in ("main", "master")


@pytest.mark.asyncio
async def test_create_branch(git_repo):
    gm = GitManager(git_repo)
    result = await gm.create_branch("feature/test")
    assert result == "feature/test"
    branch = await gm.get_current_branch()
    assert branch == "feature/test"


@pytest.mark.asyncio
async def test_stage_and_commit(git_repo):
    gm = GitManager(git_repo)
    # Create a file
    with open(os.path.join(git_repo, "new.txt"), "w") as f:
        f.write("new content")
    await gm.stage_files(["new.txt"])
    sha = await gm.commit("test: add new file")
    assert sha  # non-empty
    assert len(sha) >= 7  # short SHA


@pytest.mark.asyncio
async def test_get_status(git_repo):
    gm = GitManager(git_repo)
    status = await gm.get_status()
    assert "modified" in status
    assert "untracked" in status
    assert "staged" in status
    # Clean repo
    assert status["modified"] == []
    assert status["untracked"] == []


@pytest.mark.asyncio
async def test_get_status_with_changes(git_repo):
    gm = GitManager(git_repo)
    with open(os.path.join(git_repo, "untracked.txt"), "w") as f:
        f.write("new")
    with open(os.path.join(git_repo, "README.md"), "w") as f:
        f.write("modified")
    status = await gm.get_status()
    assert "untracked.txt" in status["untracked"]
    assert "README.md" in status["modified"]


@pytest.mark.asyncio
async def test_get_diff_summary(git_repo):
    gm = GitManager(git_repo)
    with open(os.path.join(git_repo, "README.md"), "w") as f:
        f.write("changed content")
    await gm.stage_files(["README.md"])
    diff = await gm.get_diff_summary()
    assert "README.md" in diff


@pytest.mark.asyncio
async def test_not_a_git_repo(tmp_path):
    """GitManager should raise error for non-git directory."""
    gm = GitManager(str(tmp_path))
    with pytest.raises(RuntimeError, match="not a git repo"):
        await gm.get_current_branch()
