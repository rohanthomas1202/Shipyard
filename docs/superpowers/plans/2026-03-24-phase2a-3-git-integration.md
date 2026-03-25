# Sub-phase 2a-3: Git Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add full Git/GitHub lifecycle — branch, commit, push, PR — with an asyncio-safe GitManager, GitHub REST client, and git_ops graph node.

**Architecture:** GitManager wraps async subprocess calls (argv form) with a per-instance asyncio.Lock for safety. GitHubClient wraps httpx for GitHub REST API. git_ops node is wired into the LangGraph flow after all edit steps complete. All operations logged to git_operations table.

**Tech Stack:** asyncio subprocess, httpx, FastAPI, LangGraph

**Spec:** `docs/superpowers/specs/2026-03-24-phase2a-backend-features-design.md` (Sub-phase 2a-3)

**Commit rule:** Never include `Co-Authored-By` lines in commit messages.

---

## File Structure

### New Files
- `agent/git.py` — GitManager class (async subprocess git wrapper with lock)
- `agent/github.py` — GitHubClient class (httpx-based GitHub REST API wrapper)
- `agent/prompts/git.py` — Commit message generation prompt
- `agent/nodes/git_ops.py` — git_ops graph node (branch → stage → commit → push → PR)
- `tests/test_git.py` — GitManager tests (real temp git repos)
- `tests/test_github.py` — GitHubClient tests (mocked httpx)
- `tests/test_git_ops_node.py` — git_ops node tests
- `tests/test_git_endpoints.py` — REST endpoint tests

### Modified Files
- `agent/tools/shell.py` — Add `run_command_async` (argv list form)
- `agent/state.py` — Add `git_branch` and `git_ops_log` fields
- `agent/graph.py` — Update `classify_step` to route `kind == "git"` to `"git_ops"`, add node and edges
- `server/main.py` — Add git REST endpoints (commit, push, PR, merge)
- `store/sqlite.py` — Add `idx_git_ops_run` index to schema

---

## Task 1: Async Shell Tool

**Files:**
- Modify: `agent/tools/shell.py`
- Modify: `tests/test_shell.py`

- [ ] **Step 1: Write failing tests for run_command_async**

```python
# tests/test_shell.py — append these tests to the existing file

import pytest
from agent.tools.shell import run_command_async


@pytest.mark.asyncio
async def test_run_command_async_success(tmp_codebase):
    result = await run_command_async(["echo", "hello"], cwd=tmp_codebase)
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]


@pytest.mark.asyncio
async def test_run_command_async_failure(tmp_codebase):
    result = await run_command_async(["false"], cwd=tmp_codebase)
    assert result["exit_code"] != 0


@pytest.mark.asyncio
async def test_run_command_async_captures_stderr(tmp_codebase):
    result = await run_command_async(["bash", "-c", "echo error >&2"], cwd=tmp_codebase)
    assert "error" in result["stderr"]


@pytest.mark.asyncio
async def test_run_command_async_timeout(tmp_codebase):
    result = await run_command_async(["sleep", "10"], cwd=tmp_codebase, timeout=1)
    assert result["exit_code"] == -1
    assert "timed out" in result["stderr"].lower() or "timeout" in result["stderr"].lower()


@pytest.mark.asyncio
async def test_run_command_async_argv_form_no_shell_injection(tmp_codebase):
    """Ensure argv form does not expand shell metacharacters."""
    result = await run_command_async(["echo", "hello; rm -rf /"], cwd=tmp_codebase)
    assert result["exit_code"] == 0
    # The literal string should be in stdout, not interpreted as two commands
    assert "hello; rm -rf /" in result["stdout"]


@pytest.mark.asyncio
async def test_run_command_async_returns_dict_keys(tmp_codebase):
    result = await run_command_async(["echo", "test"], cwd=tmp_codebase)
    assert set(result.keys()) == {"stdout", "stderr", "exit_code"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_shell.py -v -k async`
Expected: FAIL — `ImportError: cannot import name 'run_command_async' from 'agent.tools.shell'`

- [ ] **Step 3: Implement run_command_async**

```python
# agent/tools/shell.py — add to the existing file, after run_command

import asyncio


async def run_command_async(argv: list[str], cwd: str = ".", timeout: int = 60) -> dict:
    """Run a command asynchronously using argv list form (no shell injection)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "exit_code": proc.returncode,
            }
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {"stdout": "", "stderr": "Command timed out", "exit_code": -1}
    except FileNotFoundError as e:
        return {"stdout": "", "stderr": f"Command not found: {e}", "exit_code": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": -1}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_shell.py -v`
Expected: All tests pass (both old sync and new async tests).

- [ ] **Step 5: Commit**

```bash
git add agent/tools/shell.py tests/test_shell.py
git commit -m "feat: add run_command_async with argv-form async subprocess execution"
```

---

## Task 2: GitManager Core Operations

**Files:**
- Create: `agent/git.py`
- Create: `tests/test_git.py`

- [ ] **Step 1: Write failing tests for GitManager core**

All tests use real temporary git repos via a `git_repo` fixture that creates a temp dir, runs `git init`, and makes an initial commit.

```python
# tests/test_git.py
import os
import subprocess
import pytest
from agent.git import GitManager


@pytest.fixture
def git_repo(tmp_path):
    """Create a real temporary git repo with one initial commit."""
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    # Create initial commit so we have a branch
    readme = os.path.join(repo, "README.md")
    with open(readme, "w") as f:
        f.write("# Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, check=True, capture_output=True)
    return repo


@pytest.mark.asyncio
async def test_get_current_branch(git_repo):
    gm = GitManager(git_repo)
    branch = await gm.get_current_branch()
    assert branch in ("main", "master")


@pytest.mark.asyncio
async def test_create_branch(git_repo):
    gm = GitManager(git_repo)
    result = await gm.create_branch("feature/test-branch")
    assert result == "feature/test-branch"
    branch = await gm.get_current_branch()
    assert branch == "feature/test-branch"


@pytest.mark.asyncio
async def test_create_branch_already_exists_appends_suffix(git_repo):
    gm = GitManager(git_repo)
    await gm.create_branch("feature/dup")
    # Go back to main so create_branch can create again
    await gm._run(["git", "checkout", "-"])
    result = await gm.create_branch("feature/dup")
    assert result == "feature/dup-2"


@pytest.mark.asyncio
async def test_stage_files(git_repo):
    gm = GitManager(git_repo)
    # Create a new file
    filepath = os.path.join(git_repo, "new_file.txt")
    with open(filepath, "w") as f:
        f.write("hello\n")
    await gm.stage_files(["new_file.txt"])
    status = await gm.get_status()
    assert "new_file.txt" in status["staged"]


@pytest.mark.asyncio
async def test_commit_returns_sha(git_repo):
    gm = GitManager(git_repo)
    filepath = os.path.join(git_repo, "commit_test.txt")
    with open(filepath, "w") as f:
        f.write("commit this\n")
    await gm.stage_files(["commit_test.txt"])
    sha = await gm.commit("test: add commit_test.txt")
    assert len(sha) >= 7  # short SHA
    assert sha.isalnum()


@pytest.mark.asyncio
async def test_commit_empty_staging_raises(git_repo):
    gm = GitManager(git_repo)
    with pytest.raises(RuntimeError, match="nothing to commit"):
        await gm.commit("empty commit")


@pytest.mark.asyncio
async def test_get_status_categories(git_repo):
    gm = GitManager(git_repo)
    # Create an untracked file
    with open(os.path.join(git_repo, "untracked.txt"), "w") as f:
        f.write("u\n")
    # Modify existing file
    with open(os.path.join(git_repo, "README.md"), "w") as f:
        f.write("# Modified\n")
    status = await gm.get_status()
    assert "untracked.txt" in status["untracked"]
    assert "README.md" in status["modified"]
    assert isinstance(status["staged"], list)


@pytest.mark.asyncio
async def test_get_diff_summary(git_repo):
    gm = GitManager(git_repo)
    with open(os.path.join(git_repo, "README.md"), "w") as f:
        f.write("# Changed\n")
    await gm.stage_files(["README.md"])
    diff = await gm.get_diff_summary()
    assert "README.md" in diff


@pytest.mark.asyncio
async def test_not_a_git_repo(tmp_path):
    """GitManager on a non-git directory returns clear error."""
    gm = GitManager(str(tmp_path))
    with pytest.raises(RuntimeError, match="not a git repository"):
        await gm.get_current_branch()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_git.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent.git'`

- [ ] **Step 3: Implement GitManager core**

```python
# agent/git.py
"""Async Git operations manager with per-instance locking."""
import asyncio
from agent.tools.shell import run_command_async


class GitManager:
    """Wraps local git CLI calls with async subprocess and a mutex."""

    def __init__(self, working_directory: str):
        self.cwd = working_directory
        self._lock = asyncio.Lock()

    async def _run(self, argv: list[str]) -> dict:
        """Run a git command and return {stdout, stderr, exit_code}."""
        return await run_command_async(["git"] + argv, cwd=self.cwd)

    async def _run_checked(self, argv: list[str], error_msg: str = "") -> str:
        """Run a git command; raise RuntimeError on failure. Returns stdout."""
        result = await self._run(argv)
        if result["exit_code"] != 0:
            stderr = result["stderr"].strip()
            if "not a git repository" in stderr.lower():
                raise RuntimeError("not a git repository")
            msg = error_msg or f"git {argv[0]} failed"
            raise RuntimeError(f"{msg}: {stderr}")
        return result["stdout"].strip()

    async def get_current_branch(self) -> str:
        """Return the current branch name. Raises on detached HEAD or non-repo."""
        result = await self._run(["symbolic-ref", "--short", "HEAD"])
        if result["exit_code"] != 0:
            stderr = result["stderr"].strip().lower()
            if "not a git repository" in stderr:
                raise RuntimeError("not a git repository")
            if "not a symbolic ref" in stderr:
                raise RuntimeError("detached HEAD — cannot determine branch")
            raise RuntimeError(f"git symbolic-ref failed: {result['stderr'].strip()}")
        return result["stdout"].strip()

    async def create_branch(self, name: str) -> str:
        """Create and checkout a new branch. Appends -2, -3 etc. if name exists."""
        async with self._lock:
            candidate = name
            suffix = 1
            while True:
                result = await self._run(["checkout", "-b", candidate])
                if result["exit_code"] == 0:
                    return candidate
                if "already exists" in result["stderr"]:
                    suffix += 1
                    candidate = f"{name}-{suffix}"
                else:
                    raise RuntimeError(f"git checkout -b failed: {result['stderr'].strip()}")

    async def stage_files(self, paths: list[str]) -> None:
        """Stage specific files for commit."""
        async with self._lock:
            await self._run_checked(["add", "--"] + paths, "git add failed")

    async def commit(self, message: str) -> str:
        """Commit staged changes. Returns the short SHA. Raises if nothing staged."""
        async with self._lock:
            # Check if there is anything to commit
            result = await self._run(["diff", "--cached", "--quiet"])
            if result["exit_code"] == 0:
                raise RuntimeError("nothing to commit — staging area is empty")

            await self._run_checked(
                ["commit", "-m", message],
                "git commit failed",
            )
            sha = await self._run_checked(
                ["rev-parse", "--short", "HEAD"],
                "failed to get commit SHA",
            )
            return sha

    async def push(self, branch: str | None = None) -> None:
        """Push current branch to origin. Optionally specify branch name."""
        async with self._lock:
            argv = ["push"]
            if branch:
                argv += ["--set-upstream", "origin", branch]
            else:
                argv.append("origin")
            await self._run_checked(argv, "git push failed")

    async def get_status(self) -> dict:
        """Return {modified: [...], untracked: [...], staged: [...]}."""
        output = await self._run_checked(
            ["status", "--porcelain=v1"],
            "git status failed",
        )
        modified, untracked, staged = [], [], []
        for line in output.splitlines():
            if len(line) < 4:
                continue
            x, y = line[0], line[1]
            filepath = line[3:].strip().strip('"')
            # Staged indicators
            if x in ("M", "A", "D", "R"):
                staged.append(filepath)
            # Unstaged modifications
            if y == "M":
                modified.append(filepath)
            # Untracked
            if x == "?" and y == "?":
                untracked.append(filepath)
            # Modified but not staged
            if x == " " and y == "M":
                modified.append(filepath)
        return {"modified": modified, "untracked": untracked, "staged": staged}

    async def get_diff_summary(self) -> str:
        """Return a concise diff stat of staged changes."""
        return await self._run_checked(
            ["diff", "--cached", "--stat"],
            "git diff failed",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_git.py -v`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent/git.py tests/test_git.py
git commit -m "feat: GitManager core — async git wrapper with branch, stage, commit, status"
```

---

## Task 3: GitManager Smart Branching (ensure_branch + edge cases)

**Files:**
- Modify: `agent/git.py`
- Modify: `tests/test_git.py`

- [ ] **Step 1: Write failing tests for ensure_branch and edge cases**

```python
# tests/test_git.py — append these tests

@pytest.fixture
def git_repo_on_main(git_repo):
    """Ensure the repo is on main (not master)."""
    # Rename to main if on master
    subprocess.run(["git", "branch", "-M", "main"], cwd=git_repo, capture_output=True)
    return git_repo


@pytest.mark.asyncio
async def test_ensure_branch_creates_from_main(git_repo_on_main):
    gm = GitManager(git_repo_on_main)
    branch = await gm.ensure_branch("fix-login", "abcdef1234567890")
    assert branch == "shipyard/fix-login-abcdef12"
    current = await gm.get_current_branch()
    assert current == branch


@pytest.mark.asyncio
async def test_ensure_branch_stays_on_feature_branch(git_repo_on_main):
    gm = GitManager(git_repo_on_main)
    await gm.create_branch("feature/existing")
    branch = await gm.ensure_branch("fix-login", "abcdef1234567890")
    assert branch == "feature/existing"
    current = await gm.get_current_branch()
    assert current == "feature/existing"


@pytest.mark.asyncio
async def test_ensure_branch_name_conflict_appends_suffix(git_repo_on_main):
    gm = GitManager(git_repo_on_main)
    # Create the branch manually, then go back to main
    await gm.create_branch("shipyard/fix-login-abcdef12")
    await gm._run(["git", "checkout", "main"])
    branch = await gm.ensure_branch("fix-login", "abcdef1234567890")
    assert branch == "shipyard/fix-login-abcdef12-2"


@pytest.mark.asyncio
async def test_ensure_branch_dirty_tree_stash_and_restore(git_repo_on_main):
    gm = GitManager(git_repo_on_main)
    # Dirty the working tree
    with open(os.path.join(git_repo_on_main, "README.md"), "w") as f:
        f.write("# Dirty\n")
    branch = await gm.ensure_branch("dirty-test", "run123456789012")
    assert branch.startswith("shipyard/dirty-test-")
    # The dirty change should be restored after checkout
    with open(os.path.join(git_repo_on_main, "README.md")) as f:
        content = f.read()
    assert "Dirty" in content


@pytest.mark.asyncio
async def test_ensure_branch_detached_head_error(git_repo):
    gm = GitManager(git_repo)
    # Detach HEAD
    sha_result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True
    )
    sha = sha_result.stdout.strip()
    subprocess.run(["git", "checkout", sha], cwd=git_repo, capture_output=True)
    with pytest.raises(RuntimeError, match="detached HEAD"):
        await gm.ensure_branch("test", "run12345678")


@pytest.mark.asyncio
async def test_ensure_branch_not_a_git_repo(tmp_path):
    gm = GitManager(str(tmp_path))
    with pytest.raises(RuntimeError, match="not a git repository"):
        await gm.ensure_branch("test", "run12345678")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_git.py -v -k ensure`
Expected: FAIL — `AttributeError: 'GitManager' object has no attribute 'ensure_branch'`

- [ ] **Step 3: Implement ensure_branch**

Add this method to the `GitManager` class in `agent/git.py`:

```python
    async def ensure_branch(self, task_slug: str, run_id: str) -> str:
        """Create a task branch if on main/master; stay on current branch otherwise.

        Branch name format: shipyard/{task_slug}-{run_id[:8]}
        Edge cases:
        - Dirty working tree: stash before checkout, pop after
        - Detached HEAD: raise RuntimeError
        - Branch already exists: append -2, -3, etc.
        - Not a git repo: raise RuntimeError
        """
        current = await self.get_current_branch()  # raises on detached HEAD / non-repo

        # If already on a feature branch (not main/master), stay there
        if current not in ("main", "master"):
            return current

        branch_name = f"shipyard/{task_slug}-{run_id[:8]}"

        # Check for dirty working tree
        status_result = await self._run(["status", "--porcelain"])
        is_dirty = bool(status_result["stdout"].strip())

        async with self._lock:
            if is_dirty:
                await self._run_checked(["stash", "push", "-m", "shipyard-auto-stash"])

            try:
                created = await self.create_branch(branch_name)
            except Exception:
                # Restore stash on failure
                if is_dirty:
                    await self._run(["stash", "pop"])
                raise

            if is_dirty:
                await self._run(["stash", "pop"])

            return created
```

**Note:** The `create_branch` method already handles the "already exists" case with suffix appending.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_git.py -v`
Expected: All tests pass (core + ensure_branch + edge cases).

- [ ] **Step 5: Commit**

```bash
git add agent/git.py tests/test_git.py
git commit -m "feat: GitManager.ensure_branch with dirty-tree stash, detached HEAD, and suffix handling"
```

---

## Task 4: GitHubClient

**Files:**
- Create: `agent/github.py`
- Create: `tests/test_github.py`

- [ ] **Step 1: Write failing tests for GitHubClient (mocked httpx)**

```python
# tests/test_github.py
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from agent.github import GitHubClient


@pytest.fixture
def gh_client():
    client = GitHubClient(repo="owner/repo", token="fake-token")
    yield client


@pytest.fixture
def mock_response():
    """Factory for mock httpx.Response objects."""
    def _make(status_code=200, json_data=None):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status_code
        resp.json.return_value = json_data or {}
        resp.raise_for_status = MagicMock()
        if status_code >= 400:
            resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "error", request=MagicMock(), response=resp
            )
        return resp
    return _make


@pytest.mark.asyncio
async def test_create_pr(gh_client, mock_response):
    expected = {
        "number": 42,
        "html_url": "https://github.com/owner/repo/pull/42",
        "title": "feat: add login",
    }
    with patch.object(gh_client._client, "post", new_callable=AsyncMock, return_value=mock_response(201, expected)):
        result = await gh_client.create_pr(
            branch="shipyard/fix-login-abc12345",
            title="feat: add login",
            body="Automated PR by Shipyard",
        )
    assert result["number"] == 42
    assert result["html_url"] == "https://github.com/owner/repo/pull/42"


@pytest.mark.asyncio
async def test_create_pr_draft(gh_client, mock_response):
    expected = {"number": 43, "html_url": "https://github.com/owner/repo/pull/43", "draft": True}
    with patch.object(gh_client._client, "post", new_callable=AsyncMock, return_value=mock_response(201, expected)) as mock_post:
        await gh_client.create_pr(
            branch="feature/x", title="draft pr", body="body", draft=True
        )
    call_kwargs = mock_post.call_args
    payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert payload["draft"] is True


@pytest.mark.asyncio
async def test_create_pr_with_reviewers(gh_client, mock_response):
    pr_resp = {"number": 44, "html_url": "https://github.com/owner/repo/pull/44"}
    reviewer_resp = {"requested_reviewers": [{"login": "alice"}]}
    with patch.object(gh_client._client, "post", new_callable=AsyncMock, side_effect=[
        mock_response(201, pr_resp),
        mock_response(201, reviewer_resp),
    ]):
        result = await gh_client.create_pr(
            branch="feature/x", title="pr", body="body", reviewers=["alice"]
        )
    assert result["number"] == 44


@pytest.mark.asyncio
async def test_get_review_comments(gh_client, mock_response):
    comments = [
        {"id": 1, "body": "Fix this", "user": {"login": "alice"}, "created_at": "2026-03-24T10:00:00Z"},
        {"id": 2, "body": "LGTM", "user": {"login": "bob"}, "created_at": "2026-03-24T11:00:00Z"},
    ]
    with patch.object(gh_client._client, "get", new_callable=AsyncMock, return_value=mock_response(200, comments)):
        result = await gh_client.get_review_comments(pr_number=42)
    assert len(result) == 2
    assert result[0]["body"] == "Fix this"


@pytest.mark.asyncio
async def test_get_review_comments_with_since(gh_client, mock_response):
    with patch.object(gh_client._client, "get", new_callable=AsyncMock, return_value=mock_response(200, [])) as mock_get:
        await gh_client.get_review_comments(pr_number=42, since="2026-03-24T10:00:00Z")
    call_args = mock_get.call_args
    params = call_args.kwargs.get("params") or call_args[1].get("params", {})
    assert params.get("since") == "2026-03-24T10:00:00Z"


@pytest.mark.asyncio
async def test_merge_pr_squash(gh_client, mock_response):
    expected = {"sha": "abc123", "merged": True}
    with patch.object(gh_client._client, "put", new_callable=AsyncMock, return_value=mock_response(200, expected)):
        result = await gh_client.merge_pr(pr_number=42)
    assert result["merged"] is True


@pytest.mark.asyncio
async def test_merge_pr_rebase(gh_client, mock_response):
    expected = {"sha": "def456", "merged": True}
    with patch.object(gh_client._client, "put", new_callable=AsyncMock, return_value=mock_response(200, expected)) as mock_put:
        await gh_client.merge_pr(pr_number=42, method="rebase")
    call_kwargs = mock_put.call_args
    payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert payload["merge_method"] == "rebase"


@pytest.mark.asyncio
async def test_close_shuts_down_client(gh_client):
    with patch.object(gh_client._client, "aclose", new_callable=AsyncMock) as mock_close:
        await gh_client.close()
    mock_close.assert_called_once()


@pytest.mark.asyncio
async def test_client_headers():
    client = GitHubClient(repo="owner/repo", token="my-token")
    assert client._client.headers["authorization"] == "token my-token"
    await client.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_github.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent.github'`

- [ ] **Step 3: Implement GitHubClient**

```python
# agent/github.py
"""GitHub REST API client for PR lifecycle operations."""
import httpx


class GitHubClient:
    """Thin async wrapper around GitHub REST API for PR operations."""

    def __init__(self, repo: str, token: str):
        self.repo = repo  # "owner/repo"
        self._client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=30.0,
        )

    async def create_pr(
        self,
        branch: str,
        title: str,
        body: str,
        base: str = "main",
        draft: bool = False,
        reviewers: list[str] | None = None,
    ) -> dict:
        """Create a pull request. Optionally request reviewers."""
        payload = {
            "head": branch,
            "base": base,
            "title": title,
            "body": body,
            "draft": draft,
        }
        resp = await self._client.post(
            f"/repos/{self.repo}/pulls",
            json=payload,
        )
        resp.raise_for_status()
        pr_data = resp.json()

        if reviewers:
            await self._client.post(
                f"/repos/{self.repo}/pulls/{pr_data['number']}/requested_reviewers",
                json={"reviewers": reviewers},
            )

        return pr_data

    async def get_review_comments(
        self,
        pr_number: int,
        since: str | None = None,
    ) -> list[dict]:
        """Fetch review comments on a PR. Optionally filter by 'since' ISO timestamp."""
        params = {}
        if since:
            params["since"] = since
        resp = await self._client.get(
            f"/repos/{self.repo}/pulls/{pr_number}/comments",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def merge_pr(
        self,
        pr_number: int,
        method: str = "squash",
    ) -> dict:
        """Merge a pull request with the specified method (squash, merge, rebase)."""
        resp = await self._client.put(
            f"/repos/{self.repo}/pulls/{pr_number}/merge",
            json={"merge_method": method},
        )
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        """Shut down the underlying httpx client."""
        await self._client.aclose()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_github.py -v`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent/github.py tests/test_github.py
git commit -m "feat: GitHubClient — async httpx wrapper for PR create, review, merge"
```

---

## Task 5: Commit Message Prompt

**Files:**
- Create: `agent/prompts/git.py`

- [ ] **Step 1: Write the commit message prompt module**

No separate test file needed; this is a static prompt template tested implicitly through the git_ops node tests (Task 6). However, we verify the module imports correctly.

```python
# agent/prompts/git.py
"""Prompt templates for git commit message generation."""

COMMIT_MESSAGE_SYSTEM = """You are a commit message generator. Given a diff summary and task description, produce a single conventional-commit message.

Rules:
- Use conventional-commit format: type(scope): description
- Types: feat, fix, refactor, test, docs, chore, style, perf, ci, build
- Scope is optional but encouraged (e.g., feat(auth): add login endpoint)
- First line max 72 characters
- If needed, add a blank line then a body with more detail (wrap at 72 chars)
- Be specific about what changed, not how
- Use imperative mood ("add" not "added")
- Do not include any Co-Authored-By lines
- Respond with ONLY the commit message text, no markdown fences or other formatting"""

COMMIT_MESSAGE_USER = """Task description: {task_description}

Diff summary:
{diff_summary}

Files changed:
{files_changed}

Generate a conventional-commit message for these changes."""
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from agent.prompts.git import COMMIT_MESSAGE_SYSTEM, COMMIT_MESSAGE_USER; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add agent/prompts/git.py
git commit -m "feat: add commit message generation prompt template"
```

---

## Task 6: git_ops Graph Node

**Files:**
- Create: `agent/nodes/git_ops.py`
- Create: `tests/test_git_ops_node.py`
- Modify: `agent/state.py`

- [ ] **Step 1: Update AgentState with git fields**

Add the following fields to `AgentState` in `agent/state.py`:

```python
    # Git integration fields
    git_branch: str | None
    git_ops_log: list[dict]
```

The full `AgentState` after modification:

```python
from typing import Annotated, Optional, TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    instruction: str
    working_directory: str
    context: dict
    plan: list[str]
    current_step: int
    file_buffer: dict[str, str]
    edit_history: list[dict]
    error_state: Optional[str]
    # Multi-agent coordination fields
    is_parallel: bool
    parallel_batches: list[list[int]]
    sequential_first: list[int]
    has_conflicts: bool
    model_usage: dict[str, int]
    # Git integration fields
    git_branch: str | None
    git_ops_log: list[dict]
```

- [ ] **Step 2: Write failing tests for git_ops node**

```python
# tests/test_git_ops_node.py
import os
import subprocess
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def git_repo_for_node(tmp_path):
    """Create a temp git repo with a committed file and an edited file."""
    repo = str(tmp_path / "node_repo")
    os.makedirs(repo)
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo, check=True, capture_output=True)
    readme = os.path.join(repo, "README.md")
    with open(readme, "w") as f:
        f.write("# Original\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, check=True, capture_output=True)
    # Now make an edit (simulating what the agent did)
    with open(readme, "w") as f:
        f.write("# Edited by agent\n")
    return repo


def _make_state(repo_path, run_id="run12345678", **overrides):
    """Build a minimal AgentState dict for git_ops tests."""
    state = {
        "messages": [],
        "instruction": "Fix the README",
        "working_directory": repo_path,
        "context": {"run_id": run_id, "project_id": "proj1"},
        "plan": [{"kind": "edit", "description": "edit README"}],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [{"file": "README.md", "status": "applied"}],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
        "model_usage": {},
        "git_branch": None,
        "git_ops_log": [],
    }
    state.update(overrides)
    return state


def _make_config(store=None, router=None):
    """Build a LangGraph config dict."""
    return {
        "configurable": {
            "store": store or MagicMock(),
            "router": router or MagicMock(),
        }
    }


@pytest.mark.asyncio
async def test_git_ops_creates_branch_and_commits(git_repo_for_node):
    from agent.nodes.git_ops import git_ops_node

    mock_router = AsyncMock()
    mock_router.call = AsyncMock(return_value="feat(docs): update README with agent edits")
    mock_store = AsyncMock()
    mock_store.log_git_op = AsyncMock()

    state = _make_state(git_repo_for_node)
    config = _make_config(store=mock_store, router=mock_router)

    result = await git_ops_node(state, config)

    assert result["git_branch"] is not None
    assert result["git_branch"].startswith("shipyard/")
    assert len(result["git_ops_log"]) >= 2  # at least branch + commit ops
    # Verify the commit was actually made
    log_result = subprocess.run(
        ["git", "log", "--oneline", "-1"], cwd=git_repo_for_node, capture_output=True, text=True
    )
    assert "update README" in log_result.stdout.lower() or "feat" in log_result.stdout.lower()


@pytest.mark.asyncio
async def test_git_ops_stages_edited_files(git_repo_for_node):
    from agent.nodes.git_ops import git_ops_node

    mock_router = AsyncMock()
    mock_router.call = AsyncMock(return_value="fix: update readme")
    mock_store = AsyncMock()
    mock_store.log_git_op = AsyncMock()

    state = _make_state(git_repo_for_node)
    config = _make_config(store=mock_store, router=mock_router)

    await git_ops_node(state, config)

    # After the node, README.md should be committed (clean status)
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=git_repo_for_node, capture_output=True, text=True
    )
    assert "README.md" not in status.stdout


@pytest.mark.asyncio
async def test_git_ops_logs_operations_to_store(git_repo_for_node):
    from agent.nodes.git_ops import git_ops_node

    mock_router = AsyncMock()
    mock_router.call = AsyncMock(return_value="feat: changes")
    mock_store = AsyncMock()
    mock_store.log_git_op = AsyncMock()

    state = _make_state(git_repo_for_node)
    config = _make_config(store=mock_store, router=mock_router)

    await git_ops_node(state, config)

    assert mock_store.log_git_op.call_count >= 1


@pytest.mark.asyncio
async def test_git_ops_stays_on_feature_branch(git_repo_for_node):
    """If already on a feature branch, git_ops should not create a new one."""
    from agent.nodes.git_ops import git_ops_node

    # Pre-checkout a feature branch
    subprocess.run(
        ["git", "checkout", "-b", "feature/already-here"],
        cwd=git_repo_for_node, check=True, capture_output=True,
    )

    mock_router = AsyncMock()
    mock_router.call = AsyncMock(return_value="fix: something")
    mock_store = AsyncMock()
    mock_store.log_git_op = AsyncMock()

    state = _make_state(git_repo_for_node)
    config = _make_config(store=mock_store, router=mock_router)

    result = await git_ops_node(state, config)
    assert result["git_branch"] == "feature/already-here"


@pytest.mark.asyncio
async def test_git_ops_no_edits_skips_commit(git_repo_for_node):
    """If there are no edited files, the node should skip the commit."""
    from agent.nodes.git_ops import git_ops_node

    # Reset the README so there are no changes
    subprocess.run(
        ["git", "checkout", "--", "README.md"],
        cwd=git_repo_for_node, check=True, capture_output=True,
    )

    mock_router = AsyncMock()
    mock_router.call = AsyncMock(return_value="feat: nothing")
    mock_store = AsyncMock()
    mock_store.log_git_op = AsyncMock()

    state = _make_state(git_repo_for_node, edit_history=[])
    config = _make_config(store=mock_store, router=mock_router)

    result = await git_ops_node(state, config)

    # No commit should have been logged
    commit_ops = [op for op in result.get("git_ops_log", []) if op.get("type") == "commit"]
    assert len(commit_ops) == 0


@pytest.mark.asyncio
async def test_git_ops_generates_commit_message_via_router(git_repo_for_node):
    """The commit message should come from the router 'summarize' call."""
    from agent.nodes.git_ops import git_ops_node

    mock_router = AsyncMock()
    mock_router.call = AsyncMock(return_value="feat(readme): rewrite documentation")
    mock_store = AsyncMock()
    mock_store.log_git_op = AsyncMock()

    state = _make_state(git_repo_for_node)
    config = _make_config(store=mock_store, router=mock_router)

    await git_ops_node(state, config)

    mock_router.call.assert_called_once()
    call_args = mock_router.call.call_args
    assert call_args[1].get("task_type") == "summarize" or call_args[0][0] == "summarize"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_git_ops_node.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent.nodes.git_ops'`

- [ ] **Step 4: Implement git_ops node**

```python
# agent/nodes/git_ops.py
"""Git operations graph node — branch, stage, commit, push, PR."""
from agent.git import GitManager
from agent.github import GitHubClient
from agent.prompts.git import COMMIT_MESSAGE_SYSTEM, COMMIT_MESSAGE_USER
from store.models import GitOperation
from agent.tracing import TraceLogger

tracer = TraceLogger()


async def git_ops_node(state: dict, config: dict) -> dict:
    """Execute the git lifecycle: ensure_branch → stage → commit → push → PR.

    Reads edited files from edit_history, generates commit message via router,
    and logs all operations to the store.
    """
    store = config["configurable"]["store"]
    router = config["configurable"]["router"]
    cwd = state["working_directory"]
    ctx = state.get("context", {})
    run_id = ctx.get("run_id", "unknown")
    project_id = ctx.get("project_id", "")
    instruction = state.get("instruction", "")
    edit_history = state.get("edit_history", [])
    ops_log: list[dict] = []

    gm = GitManager(cwd)

    # 1. Ensure branch
    try:
        task_slug = instruction[:40].lower().replace(" ", "-").replace("/", "-")
        # Remove non-alphanumeric chars except hyphens
        task_slug = "".join(c for c in task_slug if c.isalnum() or c == "-").strip("-")
        branch = await gm.ensure_branch(task_slug, run_id)
        ops_log.append({"type": "branch", "branch": branch, "status": "ok"})
        await _log_op(store, run_id, "branch", branch=branch, status="ok")
    except Exception as e:
        tracer.log("git_ops", {"error": f"ensure_branch failed: {e}"})
        ops_log.append({"type": "branch", "status": "error", "error": str(e)})
        return {"git_branch": None, "git_ops_log": ops_log, "error_state": str(e)}

    # 2. Stage edited files
    edited_files = list(set(entry.get("file", "") for entry in edit_history if entry.get("file")))
    if not edited_files:
        tracer.log("git_ops", {"info": "no edited files to commit"})
        return {"git_branch": branch, "git_ops_log": ops_log}

    # Check which files actually have changes
    status = await gm.get_status()
    files_to_stage = [
        f for f in edited_files
        if f in status["modified"] or f in status["untracked"]
    ]

    if not files_to_stage:
        tracer.log("git_ops", {"info": "edited files have no pending changes"})
        return {"git_branch": branch, "git_ops_log": ops_log}

    await gm.stage_files(files_to_stage)
    ops_log.append({"type": "stage", "files": files_to_stage, "status": "ok"})

    # 3. Generate commit message via router
    diff_summary = await gm.get_diff_summary()
    commit_message = await router.call(
        "summarize",
        system=COMMIT_MESSAGE_SYSTEM,
        user=COMMIT_MESSAGE_USER.format(
            task_description=instruction,
            diff_summary=diff_summary,
            files_changed="\n".join(files_to_stage),
        ),
    )
    commit_message = commit_message.strip().strip("`").strip()

    # 4. Commit
    try:
        sha = await gm.commit(commit_message)
        ops_log.append({"type": "commit", "sha": sha, "message": commit_message, "status": "ok"})
        await _log_op(store, run_id, "commit", branch=branch, commit_sha=sha, status="ok")
    except Exception as e:
        tracer.log("git_ops", {"error": f"commit failed: {e}"})
        ops_log.append({"type": "commit", "status": "error", "error": str(e)})
        return {"git_branch": branch, "git_ops_log": ops_log, "error_state": str(e)}

    # 5. Push (only if a remote is configured — skip silently in local-only repos)
    try:
        await gm.push(branch)
        ops_log.append({"type": "push", "branch": branch, "status": "ok"})
        await _log_op(store, run_id, "push", branch=branch, status="ok")
    except RuntimeError:
        # No remote configured; this is fine for local-only repos
        ops_log.append({"type": "push", "branch": branch, "status": "skipped"})

    # 6. Create PR if GitHub is configured
    github_repo = ctx.get("github_repo")
    github_pat = ctx.get("github_pat")
    if github_repo and github_pat:
        gh = GitHubClient(repo=github_repo, token=github_pat)
        try:
            pr_data = await gh.create_pr(
                branch=branch,
                title=commit_message.split("\n")[0][:72],
                body=f"Automated PR by Shipyard\n\nRun: `{run_id}`\n\n{diff_summary}",
                draft=True,
            )
            pr_url = pr_data.get("html_url", "")
            pr_number = pr_data.get("number")
            ops_log.append({"type": "pr", "pr_url": pr_url, "pr_number": pr_number, "status": "ok"})
            await _log_op(
                store, run_id, "pr",
                branch=branch, pr_url=pr_url, pr_number=pr_number, status="ok",
            )
        except Exception as e:
            tracer.log("git_ops", {"error": f"PR creation failed: {e}"})
            ops_log.append({"type": "pr", "status": "error", "error": str(e)})
        finally:
            await gh.close()

    tracer.log("git_ops", {"ops": ops_log})
    return {"git_branch": branch, "git_ops_log": ops_log}


async def _log_op(store, run_id: str, op_type: str, **kwargs) -> None:
    """Log a git operation to the store (best-effort, never raises)."""
    try:
        op = GitOperation(run_id=run_id, type=op_type, **kwargs)
        await store.log_git_op(op)
    except Exception:
        pass  # Store logging is best-effort
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_git_ops_node.py -v`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add agent/nodes/git_ops.py tests/test_git_ops_node.py agent/state.py
git commit -m "feat: git_ops graph node — branch, stage, commit, push, PR lifecycle"
```

---

## Task 7: Graph Wiring

**Files:**
- Modify: `agent/graph.py`
- Modify: `tests/test_graph.py`

- [ ] **Step 1: Write failing tests for git routing and node wiring**

```python
# tests/test_graph.py — append these tests to the existing file

from agent.graph import classify_step


def test_classify_step_routes_git_to_git_ops():
    """After Phase 2a-3, kind=='git' should route to git_ops, not reporter."""
    state = {
        "plan": [{"kind": "git", "description": "commit and push"}],
        "current_step": 0,
    }
    assert classify_step(state) == "git_ops"


def test_classify_step_git_ops_present_in_graph():
    """The compiled graph should contain the git_ops node."""
    from agent.graph import build_graph
    graph = build_graph()
    # LangGraph compiled graphs expose node names
    node_names = list(graph.nodes.keys()) if hasattr(graph, 'nodes') else []
    assert "git_ops" in node_names or True  # Verify at integration level
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_graph.py -v -k git`
Expected: FAIL — `classify_step` still returns `"reporter"` for `kind == "git"`

- [ ] **Step 3: Update graph.py**

In `agent/graph.py`, make these changes:

**3a. Add import for git_ops_node at the top:**

```python
from agent.nodes.git_ops import git_ops_node
```

**3b. Update classify_step — change the git routing:**

Replace:
```python
        if kind == "git":
            return "reporter"  # git_ops deferred to Phase 2
```

With:
```python
        if kind == "git":
            return "git_ops"
```

**3c. Add git_ops node and edges in `_build_graph_nodes`:**

Add the node:
```python
    graph.add_node("git_ops", git_ops_node)
```

Update the `classify` conditional edges to include the new route:
```python
    graph.add_conditional_edges("classify", classify_step, {
        "executor": "executor",
        "reader_only": "reader",
        "reader_then_edit": "reader",
        "reporter": "reporter",
        "git_ops": "git_ops",
    })
```

Add the edge from git_ops to reporter:
```python
    graph.add_edge("git_ops", "reporter")
```

The full updated `_build_graph_nodes` function:

```python
def _build_graph_nodes(graph: StateGraph):
    graph.add_node("receive", receive_instruction_node)
    graph.add_node("planner", planner_node)
    graph.add_node("coordinator", coordinator_node)
    graph.add_node("reader", reader_node)
    graph.add_node("editor", editor_node)
    graph.add_node("executor", executor_node)
    graph.add_node("validator", validator_node)
    graph.add_node("merger", merger_node)
    graph.add_node("reporter", reporter_node)
    graph.add_node("git_ops", git_ops_node)
    graph.add_node("advance", advance_step)
    graph.add_node("classify", lambda s: {})

    graph.set_entry_point("receive")

    graph.add_edge("receive", "planner")
    graph.add_edge("planner", "coordinator")
    graph.add_edge("coordinator", "classify")

    graph.add_conditional_edges("classify", classify_step, {
        "executor": "executor",
        "reader_only": "reader",
        "reader_then_edit": "reader",
        "reporter": "reporter",
        "git_ops": "git_ops",
    })

    graph.add_conditional_edges("reader", after_reader, {
        "editor": "editor",
        "advance": "advance",
    })

    graph.add_edge("editor", "validator")

    graph.add_conditional_edges("executor", should_continue, {
        "reader": "reader",
        "advance": "advance",
        "reporter": "reporter",
    })

    graph.add_conditional_edges("validator", should_continue, {
        "reader": "reader",
        "advance": "advance",
        "reporter": "reporter",
    })

    graph.add_edge("advance", "classify")
    graph.add_edge("git_ops", "reporter")
    graph.add_edge("reporter", END)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_graph.py -v`
Expected: All tests pass (existing + new git routing tests).

- [ ] **Step 5: Commit**

```bash
git add agent/graph.py tests/test_graph.py
git commit -m "feat: wire git_ops node into LangGraph — route kind=git to git_ops"
```

---

## Task 8: REST Endpoints

**Files:**
- Modify: `server/main.py`
- Create: `tests/test_git_endpoints.py`

- [ ] **Step 1: Write failing tests for git REST endpoints**

```python
# tests/test_git_endpoints.py
import os
import subprocess
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from server.main import app


@pytest.fixture
def git_repo_for_api(tmp_path):
    """Create a temp git repo for API testing."""
    repo = str(tmp_path / "api_repo")
    os.makedirs(repo)
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "branch", "-M", "main"], cwd=repo, check=True, capture_output=True)
    readme = os.path.join(repo, "README.md")
    with open(readme, "w") as f:
        f.write("# Test\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    return repo


@pytest.fixture
def mock_store():
    store = AsyncMock()
    store.get_run = AsyncMock(return_value=MagicMock(
        id="run1",
        project_id="proj1",
        instruction="fix stuff",
        status="completed",
        context={"run_id": "run1"},
    ))
    store.log_git_op = AsyncMock()
    return store


@pytest.fixture
def setup_app(mock_store, git_repo_for_api):
    """Inject mock store and a run record into app state."""
    from server.main import runs
    app.state.store = mock_store
    app.state.router = MagicMock()
    runs["run1"] = {
        "status": "completed",
        "result": {
            "working_directory": git_repo_for_api,
            "edit_history": [{"file": "README.md"}],
            "context": {"run_id": "run1"},
        },
    }
    return git_repo_for_api


@pytest.mark.asyncio
async def test_post_git_commit(setup_app):
    repo_path = setup_app
    # Make a change to commit
    with open(os.path.join(repo_path, "README.md"), "w") as f:
        f.write("# Changed\n")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/runs/run1/git/commit", json={
            "message": "test: update readme",
            "files": ["README.md"],
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "sha" in data
    assert data["sha"]  # non-empty


@pytest.mark.asyncio
async def test_post_git_commit_run_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/runs/nonexistent/git/commit", json={
            "message": "test",
            "files": ["x.txt"],
        })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_post_git_push_no_remote(setup_app):
    """Push should return an error when there is no remote."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/runs/run1/git/push")
    assert resp.status_code in (200, 400, 422)
    # Either succeeds with a skip status or returns an error about no remote


@pytest.mark.asyncio
async def test_post_git_pr_no_github_config(setup_app):
    """PR endpoint should return 400 if GitHub is not configured."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/runs/run1/git/pr", json={
            "title": "test pr",
            "body": "test body",
        })
    assert resp.status_code == 400
    assert "github" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_post_git_merge_no_pr(setup_app):
    """Merge endpoint should return 400 if no PR number is given and none exists."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/runs/run1/git/merge", json={})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_git_endpoints.py -v`
Expected: FAIL — 404 on all `/runs/:id/git/*` routes (not yet defined)

- [ ] **Step 3: Implement REST endpoints**

Add the following to `server/main.py`:

```python
# --- Add these imports at the top ---
from agent.git import GitManager
from agent.github import GitHubClient
from store.models import GitOperation


# --- Add these request models ---
class GitCommitRequest(BaseModel):
    message: str
    files: list[str]


class GitPRRequest(BaseModel):
    title: str
    body: str
    draft: bool = True
    base: str = "main"
    reviewers: list[str] = []


class GitMergeRequest(BaseModel):
    pr_number: int | None = None
    method: str = "squash"


# --- Add these endpoints ---
def _get_run_result(run_id: str) -> dict:
    """Retrieve the run result dict or raise 404."""
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")
    result = runs[run_id].get("result")
    if not isinstance(result, dict):
        raise HTTPException(status_code=400, detail="Run has no result state")
    return result


@app.post("/runs/{run_id}/git/commit")
async def git_commit(run_id: str, req: GitCommitRequest):
    result = _get_run_result(run_id)
    cwd = result.get("working_directory", ".")
    store: SQLiteSessionStore = app.state.store

    gm = GitManager(cwd)
    try:
        await gm.stage_files(req.files)
        sha = await gm.commit(req.message)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await store.log_git_op(GitOperation(
        run_id=run_id, type="commit", commit_sha=sha, status="ok",
    ))
    return {"sha": sha, "message": req.message}


@app.post("/runs/{run_id}/git/push")
async def git_push(run_id: str):
    result = _get_run_result(run_id)
    cwd = result.get("working_directory", ".")
    store: SQLiteSessionStore = app.state.store

    gm = GitManager(cwd)
    try:
        branch = await gm.get_current_branch()
        await gm.push(branch)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await store.log_git_op(GitOperation(
        run_id=run_id, type="push", branch=branch, status="ok",
    ))
    return {"branch": branch, "status": "pushed"}


@app.post("/runs/{run_id}/git/pr")
async def git_create_pr(run_id: str, req: GitPRRequest):
    result = _get_run_result(run_id)
    cwd = result.get("working_directory", ".")
    ctx = result.get("context", {})
    store: SQLiteSessionStore = app.state.store

    github_repo = ctx.get("github_repo")
    github_pat = ctx.get("github_pat")
    if not github_repo or not github_pat:
        raise HTTPException(status_code=400, detail="GitHub not configured for this project")

    gm = GitManager(cwd)
    branch = await gm.get_current_branch()

    gh = GitHubClient(repo=github_repo, token=github_pat)
    try:
        pr_data = await gh.create_pr(
            branch=branch,
            title=req.title,
            body=req.body,
            base=req.base,
            draft=req.draft,
            reviewers=req.reviewers if req.reviewers else None,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PR creation failed: {e}")
    finally:
        await gh.close()

    await store.log_git_op(GitOperation(
        run_id=run_id, type="pr", branch=branch,
        pr_url=pr_data.get("html_url"), pr_number=pr_data.get("number"),
        status="ok",
    ))
    return pr_data


@app.post("/runs/{run_id}/git/merge")
async def git_merge_pr(run_id: str, req: GitMergeRequest):
    result = _get_run_result(run_id)
    ctx = result.get("context", {})
    store: SQLiteSessionStore = app.state.store

    github_repo = ctx.get("github_repo")
    github_pat = ctx.get("github_pat")
    if not github_repo or not github_pat:
        raise HTTPException(status_code=400, detail="GitHub not configured for this project")

    pr_number = req.pr_number
    if not pr_number:
        raise HTTPException(status_code=400, detail="pr_number is required")

    gh = GitHubClient(repo=github_repo, token=github_pat)
    try:
        merge_data = await gh.merge_pr(pr_number=pr_number, method=req.method)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Merge failed: {e}")
    finally:
        await gh.close()

    await store.log_git_op(GitOperation(
        run_id=run_id, type="merge", pr_number=pr_number, status="ok",
    ))
    return merge_data
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_git_endpoints.py -v`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add server/main.py tests/test_git_endpoints.py
git commit -m "feat: git REST endpoints — commit, push, PR, merge"
```

---

## Task 9: Migration — Add Index

**Files:**
- Modify: `store/sqlite.py`

- [ ] **Step 1: Write a test to verify the index exists**

```python
# tests/test_store.py — append this test

@pytest.mark.asyncio
async def test_git_ops_run_index_exists(tmp_path):
    """The idx_git_ops_run index should exist on the git_operations table."""
    from store.sqlite import SQLiteSessionStore
    db_path = str(tmp_path / "test_index.db")
    store = SQLiteSessionStore(db_path)
    await store.initialize()
    try:
        async with store._db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_git_ops_run'"
        ) as cursor:
            row = await cursor.fetchone()
        assert row is not None, "idx_git_ops_run index should exist"
    finally:
        await store.close()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_store.py -v -k idx_git_ops_run`
Expected: FAIL — index does not exist yet

- [ ] **Step 3: Add the index to the schema**

In `store/sqlite.py`, add the following line to `_SCHEMA`, after the `git_operations` table definition:

```sql
CREATE INDEX IF NOT EXISTS idx_git_ops_run ON git_operations(run_id);
```

The `git_operations` section of `_SCHEMA` should look like:

```sql
CREATE TABLE IF NOT EXISTS git_operations (
    id TEXT PRIMARY KEY, run_id TEXT REFERENCES runs(id),
    type TEXT NOT NULL, branch TEXT, commit_sha TEXT,
    pr_url TEXT, pr_number INTEGER, status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_git_ops_run ON git_operations(run_id);
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_store.py -v`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add store/sqlite.py tests/test_store.py
git commit -m "feat: add idx_git_ops_run index on git_operations table"
```

---

## Verification

After all tasks are complete, run the full test suite:

```bash
pytest tests/ -v --tb=short
```

All existing tests plus the new ones should pass:
- `tests/test_shell.py` — async shell tool tests
- `tests/test_git.py` — GitManager core + smart branching tests
- `tests/test_github.py` — GitHubClient mock tests
- `tests/test_git_ops_node.py` — git_ops node tests
- `tests/test_graph.py` — graph wiring tests including git routing
- `tests/test_git_endpoints.py` — REST endpoint tests
- `tests/test_store.py` — store tests including index verification

---

## Addendum: Required Corrections

The agentic worker MUST apply these corrections when implementing the tasks above.

### Fix 1: `_run()` must NOT prepend "git" — callers include it (BLOCKING)

The plan defines `_run()` as `["git"] + argv` but then tests call `_run(["git", "checkout", ...])`. This produces `git git checkout`.

**Fix:** `_run()` passes argv directly to `run_command_async` without prepending anything:
```python
async def _run(self, argv: list[str]) -> dict:
    """Run a command. Caller provides full argv, e.g. ["git", "branch", "--show-current"]."""
    return await run_command_async(argv, cwd=self.cwd)
```

All call sites must include `"git"` as the first element:
```python
await self._run(["git", "branch", "--show-current"])
await self._run(["git", "checkout", "-b", name])
```

Audit every `_run()` call in the plan and every test to ensure `"git"` appears exactly once.

### Fix 2: Fix nested lock deadlock in `ensure_branch()` (BLOCKING)

`ensure_branch()` acquires `self._lock`, then calls `self.create_branch()` which also acquires `self._lock`. asyncio.Lock is non-reentrant — this deadlocks.

**Fix:** Extract `_create_branch_unlocked()` and call that from `ensure_branch()`:
```python
async def _create_branch_unlocked(self, name: str) -> str:
    """Internal — create branch without acquiring lock. Caller must hold lock."""
    result = await self._run(["git", "checkout", "-b", name])
    if result["exit_code"] != 0:
        raise RuntimeError(f"Failed to create branch: {result['stderr']}")
    return name

async def create_branch(self, name: str) -> str:
    """Public API — acquires lock."""
    async with self._lock:
        return await self._create_branch_unlocked(name)

async def ensure_branch(self, task_slug: str, run_id: str) -> str:
    async with self._lock:
        branch = await self._get_current_branch_unlocked()
        if branch in ("main", "master"):
            ...
            return await self._create_branch_unlocked(branch_name)
        return branch
```

Apply the same pattern to any other method called within a locked section (`get_current_branch`, `get_status`).

### Fix 3: Use class-level lock registry keyed by working directory

A per-instance lock provides no safety when multiple `GitManager` instances target the same repo.

**Fix:**
```python
class GitManager:
    _repo_locks: ClassVar[dict[str, asyncio.Lock]] = {}

    def __init__(self, working_directory: str):
        self.cwd = os.path.abspath(working_directory)
        if self.cwd not in GitManager._repo_locks:
            GitManager._repo_locks[self.cwd] = asyncio.Lock()
        self._lock = GitManager._repo_locks[self.cwd]
```

### Fix 4: Improve stash handling in `ensure_branch()`

Current stash logic is incomplete:
- Does not include untracked files (`-u` flag missing)
- Ignores stash pop failure
- Does not verify whether a stash was actually created

**Fix:**
```python
# Check if dirty
status = await self._run(["git", "status", "--porcelain"])
is_dirty = bool(status["stdout"].strip())

if is_dirty:
    stash_result = await self._run(["git", "stash", "push", "-u", "-m", "shipyard-auto-stash"])
    if stash_result["exit_code"] != 0:
        raise RuntimeError(f"Failed to stash: {stash_result['stderr']}")

# ... create branch / checkout ...

if is_dirty:
    pop_result = await self._run(["git", "stash", "pop"])
    if pop_result["exit_code"] != 0:
        raise RuntimeError(
            f"Stash pop failed after branch creation. Branch '{branch_name}' exists. "
            f"Manual intervention needed: {pop_result['stderr']}"
        )
```

### Fix 5: Fix `push()` to always resolve current branch

```python
async def push(self, branch: str | None = None) -> None:
    async with self._lock:
        if branch is None:
            branch = (await self._run(["git", "branch", "--show-current"]))["stdout"].strip()
        result = await self._run(["git", "push", "--set-upstream", "origin", branch])
        if result["exit_code"] != 0:
            raise RuntimeError(f"Push failed: {result['stderr']}")
```

### Fix 6: Decide on commit approval — DEFER for V1

The spec mentions commit approval in supervised mode, but this adds significant complexity to the git_ops flow.

**V1 decision:** Commit approval is **deferred**. In V1, `git_ops_node` always commits and pushes without an approval gate. The edit-level approval (2a-2) is the primary safety mechanism. Commit approval can be added in a future phase.

Document this explicitly in the git_ops_node implementation.

### Fix 7: Stage from store-backed applied edits, not edit_history

```python
# In git_ops_node, replace:
edited_files = list(set(entry.get("file", "") for entry in edit_history if entry.get("file")))

# With:
store = config["configurable"]["store"]
run_id = config["configurable"].get("run_id", "")
applied_edits = await store.get_edits(run_id, status="applied")
edited_files = list(set(e.file_path for e in applied_edits))

# Fallback to edit_history only if no approval system / no applied edits:
if not edited_files:
    edited_files = list(set(entry.get("file", "") for entry in edit_history if entry.get("file")))
```

### Fix 8: Standardize run_id sourcing

Do not source run_id from `state["context"]`. Use consistent pattern across all nodes:

```python
# Primary: from config
run_id = config["configurable"].get("run_id", "")
# Fallback: from state (if set by receive node)
if not run_id:
    run_id = state.get("run_id", "unknown")
```

Same for `project_id`. Apply to git_ops_node and all REST endpoints.

### Fix 9: Replace fake graph assertion with real test

Replace:
```python
assert "git_ops" in node_names or True  # always passes
```

With:
```python
# Test that classify_step routes git kind correctly
from agent.graph import classify_step
state = {"plan": [{"kind": "git", "id": "g1", "complexity": "simple"}], "current_step": 0}
assert classify_step(state) == "git_ops"
```

### Fix 10: Narrow push failure handling

Replace:
```python
except RuntimeError:
    ops_log.append({"type": "push", "status": "skipped"})
```

With:
```python
except RuntimeError as e:
    err_msg = str(e).lower()
    if "no remote" in err_msg or "no upstream" in err_msg or "does not appear to be a git repo" in err_msg:
        ops_log.append({"type": "push", "status": "skipped", "reason": "no remote configured"})
    else:
        ops_log.append({"type": "push", "status": "failed", "error": str(e)})
        # Don't raise — PR creation still possible if push succeeded via other means
```

### Fix 11: Prefer project config over run context for GitHub credentials

```python
# In git_ops_node and REST endpoints:
store = config["configurable"]["store"]
project = await store.get_project(project_id)
github_repo = project.github_repo if project else None
github_pat = project.github_pat if project else None

# Only fall back to run context if project config not available:
if not github_repo:
    github_repo = state.get("context", {}).get("github_repo")
```

### Fix 12: Handle reviewer assignment as best-effort in GitHubClient

```python
async def create_pr(self, branch, title, body, draft=False, reviewers=None):
    # ... create PR ...
    resp.raise_for_status()
    pr_data = resp.json()

    # Reviewer assignment is best-effort
    if reviewers:
        try:
            reviewer_resp = await self._client.post(...)
            reviewer_resp.raise_for_status()
        except httpx.HTTPStatusError:
            pass  # reviewer assignment failed — non-fatal

    return pr_data
```

### Fix 13: Verify GitOperation model and store support exist

Before implementation, confirm that `store/models.py` has `GitOperation` and `store/sqlite.py` has `log_git_op()`. These were created in Phase 1 — the worker should read these files first to verify field names match what git_ops_node expects.

### Fix 14: Normalize PR response shape

The `POST /runs/:id/git/pr` endpoint must not return raw GitHub API data. Normalize to:

```python
return {
    "number": pr_data.get("number"),
    "html_url": pr_data.get("html_url"),
}
```

### Fix 15: Normalize merge response shape

The `POST /runs/:id/git/merge` endpoint must not return raw GitHub API data. Normalize to:

```python
return {
    "merged": merge_data.get("merged", False),
    "sha": merge_data.get("sha", ""),
}
```

### Fix 16: Tighten git endpoint test assertions

- Commit response test must assert `"message"` field is present and matches the input
- Push-no-remote test must assert status code 400 (not a loose `in (200, 400, 422)`)
- Merge response test must assert exactly `{"merged", "sha"}` keys
- PR response test must assert exactly `{"number", "html_url"}` keys
