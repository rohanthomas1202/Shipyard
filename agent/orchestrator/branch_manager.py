"""Git branch lifecycle management for isolated task execution."""
import asyncio
import logging

from agent.tools.shell import run_command_async

logger = logging.getLogger(__name__)


class BranchManager:
    """Manages git branch create/rebase/merge/cleanup for per-task isolation.

    All public methods acquire an asyncio.Lock to serialize git mutations,
    preventing race conditions when tasks run concurrently.
    """

    def __init__(self, project_path: str) -> None:
        self._cwd = project_path
        self._lock = asyncio.Lock()

    async def _git(self, *args: str) -> dict:
        """Run a git command. Does NOT acquire lock (callers do)."""
        result = await run_command_async(["git", *args], cwd=self._cwd, timeout=30)
        if result["exit_code"] != 0:
            logger.warning(
                "git %s failed (exit %d): %s",
                " ".join(args),
                result["exit_code"],
                result["stderr"].strip(),
            )
        return result

    async def create_and_checkout(self, branch: str, base: str = "main") -> bool:
        """Create a fresh branch from *base* and switch to it.

        Deletes any stale branch with the same name first (idempotent).
        Returns True on success.
        """
        async with self._lock:
            await self._git("checkout", base)
            # Force-delete stale branch -- ignore failure (may not exist)
            await self._git("branch", "-D", branch)
            result = await self._git("checkout", "-b", branch)
            return result["exit_code"] == 0

    async def rebase_and_merge(self, branch: str) -> bool:
        """Rebase *branch* on main then fast-forward merge into main.

        Returns False on rebase conflict (aborts rebase automatically).
        Per D-09, only fast-forward merges are allowed.
        """
        async with self._lock:
            await self._git("checkout", branch)
            rebase = await self._git("rebase", "main")
            if rebase["exit_code"] != 0:
                await self._git("rebase", "--abort")
                return False
            await self._git("checkout", "main")
            merge = await self._git("merge", "--ff-only", branch)
            return merge["exit_code"] == 0

    async def cleanup(self, branch: str) -> None:
        """Check out main and force-delete *branch*. Idempotent."""
        async with self._lock:
            await self._git("checkout", "main")
            await self._git("branch", "-D", branch)

    async def verify_branch(self) -> str:
        """Return the name of the currently checked-out branch."""
        async with self._lock:
            result = await self._git("rev-parse", "--abbrev-ref", "HEAD")
            return result["stdout"].strip()
