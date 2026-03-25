"""GitManager — local git operations via async subprocess."""
from __future__ import annotations
import asyncio
import os
from typing import ClassVar
from agent.tools.shell import run_command_async


class GitManager:
    """Manages local git operations using async subprocess calls.

    Uses a class-level lock registry keyed by working directory
    to prevent concurrent git operations on the same repo.
    """
    _repo_locks: ClassVar[dict[str, asyncio.Lock]] = {}

    def __init__(self, working_directory: str):
        self.cwd = os.path.abspath(working_directory)
        if self.cwd not in GitManager._repo_locks:
            GitManager._repo_locks[self.cwd] = asyncio.Lock()
        self._lock = GitManager._repo_locks[self.cwd]

    async def _run(self, argv: list[str]) -> dict:
        """Run a command. Caller provides full argv including 'git'."""
        return await run_command_async(argv, cwd=self.cwd)

    async def _run_checked(self, argv: list[str], error_msg: str = "") -> str:
        """Run a command; raise RuntimeError on failure. Returns stdout."""
        result = await self._run(argv)
        if result["exit_code"] != 0:
            msg = error_msg or f"Command failed: {' '.join(argv)}"
            raise RuntimeError(f"{msg}: {result['stderr'].strip()}")
        return result["stdout"].strip()

    async def _check_is_repo(self) -> None:
        """Raise if cwd is not inside a git repo."""
        result = await self._run(["git", "rev-parse", "--git-dir"])
        if result["exit_code"] != 0:
            raise RuntimeError(f"not a git repo: {self.cwd}")

    async def get_current_branch(self) -> str:
        async with self._lock:
            return await self._get_current_branch_unlocked()

    async def _get_current_branch_unlocked(self) -> str:
        await self._check_is_repo()
        return await self._run_checked(
            ["git", "branch", "--show-current"],
            "Failed to get current branch"
        )

    async def create_branch(self, name: str) -> str:
        async with self._lock:
            return await self._create_branch_unlocked(name)

    async def _create_branch_unlocked(self, name: str) -> str:
        """Internal — create and checkout branch. Caller must hold lock."""
        await self._run_checked(
            ["git", "checkout", "-b", name],
            f"Failed to create branch {name}"
        )
        return name

    async def stage_files(self, paths: list[str]) -> None:
        async with self._lock:
            await self._run_checked(
                ["git", "add"] + paths,
                "Failed to stage files"
            )

    async def commit(self, message: str) -> str:
        """Commit staged changes. Returns short SHA."""
        async with self._lock:
            await self._run_checked(
                ["git", "commit", "-m", message],
                "Failed to commit"
            )
            stdout = await self._run_checked(
                ["git", "rev-parse", "--short", "HEAD"],
                "Failed to get commit SHA"
            )
            return stdout

    async def push(self, branch: str | None = None) -> None:
        async with self._lock:
            if branch is None:
                branch = await self._get_current_branch_unlocked()
            await self._run_checked(
                ["git", "push", "--set-upstream", "origin", branch],
                "Push failed"
            )

    async def get_status(self) -> dict:
        """Return {modified, untracked, staged} lists."""
        async with self._lock:
            result = await self._run(["git", "status", "--porcelain"])
            modified, untracked, staged = [], [], []
            for line in result["stdout"].splitlines():
                if len(line) < 3:
                    continue
                x, y = line[0], line[1]
                path = line[3:].strip()
                if x == "?" and y == "?":
                    untracked.append(path)
                elif x in ("M", "A", "D", "R"):
                    staged.append(path)
                elif y == "M":
                    modified.append(path)
            return {"modified": modified, "untracked": untracked, "staged": staged}

    async def get_diff_summary(self) -> str:
        """Get a summary of staged changes for commit message generation."""
        async with self._lock:
            return await self._run_checked(
                ["git", "diff", "--cached", "--stat"],
                "Failed to get diff"
            )
