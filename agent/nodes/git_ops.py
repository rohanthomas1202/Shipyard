"""git_ops node -- handles branch, commit, push, PR after all edits are done."""
from __future__ import annotations
from langgraph.types import RunnableConfig
import logging
import re
from agent.git import GitManager
from agent.github import GitHubClient
from agent.prompts.git import COMMIT_MSG_SYSTEM, COMMIT_MSG_USER
from agent.tracing import TraceLogger
from store.models import GitOperation

logger = logging.getLogger(__name__)
tracer = TraceLogger()


async def git_ops_node(state: dict, config: RunnableConfig = None) -> dict:
    """Execute git operations: branch, stage, commit, push, PR.

    Reads edited file paths from edit_history. Resolves project_id from
    config["configurable"] with fallback to state context.
    Push is skipped when no remote is configured (local-only repos).
    """
    config = config or {}
    configurable = config.get("configurable", {})

    store = configurable.get("store")
    router = configurable.get("router")
    run_id = configurable.get("run_id", "")

    # Resolve project_id: config first, then state context fallback
    project_id = configurable.get("project_id", "")
    if not project_id:
        ctx = state.get("context", {})
        project_id = ctx.get("project_id", "")

    working_dir = state.get("working_directory", "")
    if not working_dir:
        return {"error_state": "No working directory for git operations"}

    gm = GitManager(working_dir)
    ops_log = []

    # 1. Ensure branch
    task_slug = _slugify(state.get("instruction", "edit"))
    try:
        branch = await gm.ensure_branch(task_slug, run_id)
        ops_log.append({"type": "branch", "branch": branch, "status": "ok"})
    except RuntimeError as e:
        ops_log.append({"type": "branch", "status": "failed", "error": str(e)})
        tracer.log("git_ops", {"ops": ops_log, "error": str(e)})
        return {"error_state": f"Git branch failed: {e}", "branch": ""}

    # 2. Stage applied edits (from store if available, else edit_history)
    edited_files = []
    applied_edits = []
    if store and run_id:
        try:
            applied_edits = await store.get_edits(run_id, status="applied")
            edited_files = list(set(e.file_path for e in applied_edits))
        except Exception:
            pass

    if not edited_files:
        edit_history = state.get("edit_history", [])
        edited_files = list(set(entry.get("file", "") for entry in edit_history if entry.get("file")))

    if not edited_files:
        tracer.log("git_ops", {"ops": ops_log, "note": "no files to commit"})
        return {"branch": branch, "error_state": None}

    try:
        await gm.stage_files(edited_files)
        ops_log.append({"type": "stage", "files": edited_files, "status": "ok"})
    except RuntimeError as e:
        ops_log.append({"type": "stage", "status": "failed", "error": str(e)})
        tracer.log("git_ops", {"ops": ops_log})
        return {"error_state": f"Git stage failed: {e}", "branch": branch}

    # 3. Generate commit message
    message = f"feat: apply {len(edited_files)} edit(s) from Shipyard run {run_id[:8]}"
    if router:
        try:
            diff_summary = await gm.get_diff_summary()
            message = await router.call("summarize", COMMIT_MSG_SYSTEM, COMMIT_MSG_USER.format(diff_summary=diff_summary))
            message = message.strip().split("\n")[0]  # first line only
        except Exception:
            pass

    # 4. Commit
    try:
        sha = await gm.commit(message)
        ops_log.append({"type": "commit", "sha": sha, "message": message, "status": "ok"})
        if store and run_id:
            await store.log_git_op(GitOperation(run_id=run_id, type="commit", branch=branch, commit_sha=sha, status="ok"))

        # Mark edits as committed
        if applied_edits:
            approval_manager = configurable.get("approval_manager")
            if approval_manager:
                await approval_manager.mark_committed(run_id, [e.id for e in applied_edits])
    except RuntimeError as e:
        ops_log.append({"type": "commit", "status": "failed", "error": str(e)})
        tracer.log("git_ops", {"ops": ops_log})
        return {"error_state": f"Git commit failed: {e}", "branch": branch}

    # 5. Push (best-effort)
    try:
        await gm.push(branch)
        ops_log.append({"type": "push", "branch": branch, "status": "pushed"})
        if store and run_id:
            await store.log_git_op(GitOperation(run_id=run_id, type="push", branch=branch, status="ok"))
    except RuntimeError as e:
        err_msg = str(e).lower()
        if "no remote" in err_msg or "does not appear to be a git" in err_msg:
            ops_log.append({"type": "push", "status": "skipped", "reason": "no remote configured"})
        else:
            ops_log.append({"type": "push", "status": "failed", "error": str(e)})
            if store and run_id:
                await store.log_git_op(GitOperation(run_id=run_id, type="push", branch=branch, status="failed"))

    # 6. PR (if GitHub configured)
    project = None
    if store and project_id:
        try:
            project = await store.get_project(project_id)
        except Exception:
            pass

    github_repo = project.github_repo if project else None
    github_pat = project.github_pat if project else None

    if github_repo and github_pat:
        try:
            gh = GitHubClient(repo=github_repo, token=github_pat)
            pr_data = await gh.create_pr(branch=branch, title=message, body=f"Shipyard run: {run_id}")
            ops_log.append({"type": "pr", "number": pr_data["number"], "url": pr_data["html_url"], "status": "ok"})
            if store and run_id:
                await store.log_git_op(GitOperation(run_id=run_id, type="pr_create", branch=branch, pr_url=pr_data["html_url"], pr_number=pr_data["number"], status="ok"))
            await gh.close()
        except Exception as e:
            ops_log.append({"type": "pr", "status": "failed", "error": str(e)})

    tracer.log("git_ops", {"ops": ops_log, "branch": branch, "run_id": run_id})
    return {"branch": branch, "error_state": None}


def _slugify(text: str) -> str:
    """Convert text to a git-safe branch slug."""
    return re.sub(r"[^a-z0-9-]", "-", text.lower().strip())[:40].strip("-") or "edit"
