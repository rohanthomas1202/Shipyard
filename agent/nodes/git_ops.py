"""git_ops_node -- automatic git operations after edits complete."""
from __future__ import annotations

import re
from agent.git import GitManager


async def git_ops_node(state: dict, config: dict = None) -> dict:
    """Branch, stage, commit edited files.

    Reads edited file paths from edit_history. Resolves project_id from
    config["configurable"] with fallback to state context.
    Push is skipped when no remote is configured (local-only repos).
    """
    config = config or {}
    configurable = config.get("configurable", {})

    # Resolve project_id: config first, then state context fallback
    project_id = configurable.get("project_id", "")
    if not project_id:
        ctx = state.get("context", {})
        project_id = ctx.get("project_id", "")

    working_directory = state.get("working_directory", "")
    if not working_directory:
        return {"error_state": "git_ops: no working_directory"}

    edit_history = state.get("edit_history", [])
    if not edit_history:
        return {"error_state": None}

    # Collect unique file paths from edit_history
    files = list({e["file"] for e in edit_history if e.get("file")})
    if not files:
        return {"error_state": None}

    gm = GitManager(working_directory)

    try:
        # Create branch from project slug and run_id
        run_id = configurable.get("run_id", "auto")
        slug = _slugify(project_id) if project_id else "shipyard"
        branch_name = f"{slug}/{run_id}"

        current_branch = await gm.get_current_branch()
        if current_branch in ("main", "master"):
            await gm.create_branch(branch_name)

        # Stage edited files
        await gm.stage_files(files)

        # Build commit message from instruction
        instruction = state.get("instruction", "agent edits")
        message = f"feat: {instruction[:72]}"
        sha = await gm.commit(message)

        # Push (best-effort, skip if no remote)
        try:
            await gm.push()
        except RuntimeError:
            pass  # No remote configured — local-only is fine

        return {
            "branch": branch_name if current_branch in ("main", "master") else current_branch,
            "error_state": None,
        }

    except RuntimeError as exc:
        return {"error_state": f"git_ops failed: {exc}"}


def _slugify(text: str) -> str:
    """Convert text to a git-safe branch slug."""
    return re.sub(r"[^a-z0-9-]", "-", text.lower().strip())[:40].strip("-")
