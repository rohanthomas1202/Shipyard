"""Refactor node — codebase-wide structural transformations via ast-grep.

Handles dry-run, apply, snapshot-based rollback, and approval integration.
Refactor steps are always sequential (never parallelized by the coordinator).
"""
from __future__ import annotations

import uuid
from langgraph.types import RunnableConfig
from agent.tracing import TraceLogger
from agent.tools.ast_ops import apply_rule

tracer = TraceLogger()


async def refactor_node(state: dict, config: RunnableConfig) -> dict:
    """Execute a codebase-wide refactoring step."""
    approval_manager = config["configurable"].get("approval_manager")
    supervised = config["configurable"].get("supervised", False)
    run_id = config["configurable"].get("run_id", "")

    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    file_buffer = state.get("file_buffer", {})
    edit_history = state.get("edit_history", [])

    if current_step >= len(plan):
        return {"error_state": None}

    step = plan[current_step]
    if not isinstance(step, dict) or step.get("kind") != "refactor":
        return {"error_state": "Expected refactor step"}

    pattern = step.get("pattern", "")
    replacement = step.get("refactor_replacement", "")
    language = step.get("language", "")
    scope = step.get("scope", state.get("working_directory", ""))

    if not pattern or not language:
        return {"error_state": "Refactor step missing pattern or language"}

    batch_id = uuid.uuid4().hex[:12]
    rule = {"pattern": pattern, "fix": replacement, "language": language}

    # Check if resuming after approval
    existing_batch_id = _find_pending_batch(edit_history)
    if existing_batch_id:
        batch_id = existing_batch_id
        tracer.log("refactor", {"batch_id": batch_id, "status": "resuming_after_approval"})

    # Dry-run to see what would change
    dry_results = apply_rule(rule, scope, dry_run=True)

    if not dry_results:
        tracer.log("refactor", {"batch_id": batch_id, "matches": 0, "status": "no_matches"})
        return {"error_state": None}

    total_matches = sum(r.match_count for r in dry_results)
    tracer.log("refactor", {
        "batch_id": batch_id,
        "files_matched": len(dry_results),
        "total_matches": total_matches,
        "scope": scope,
    })

    # If supervised with approval_manager, propose batch and wait
    if approval_manager is not None and supervised and not existing_batch_id:
        from store.models import EditRecord
        records = []
        for dr in dry_results:
            records.append(EditRecord(
                run_id=run_id,
                file_path=dr.file_path,
                old_content=dr.old_content,
                new_content=dr.new_content,
                batch_id=batch_id,
            ))
        await approval_manager.propose_batch(run_id, records, batch_id)
        return {
            "waiting_for_human": True,
            "batch_id": batch_id,
            "edit_history": edit_history + [
                {"file": dr.file_path, "batch_id": batch_id, "status": "proposed"}
                for dr in dry_results
            ],
            "error_state": None,
        }

    # Capture snapshots from dry-run BEFORE applying (for reliable rollback)
    snapshots: dict[str, str] = {r.file_path: r.old_content for r in dry_results}
    new_edit_history = list(edit_history)
    new_file_buffer = dict(file_buffer)

    try:
        results = apply_rule(rule, scope, dry_run=False)
        for r in results:
            new_file_buffer[r.file_path] = r.new_content
            new_edit_history.append({
                "file": r.file_path,
                "old": pattern,
                "new": replacement,
                "snapshot": snapshots.get(r.file_path, r.old_content),
                "batch_id": batch_id,
            })
    except Exception as e:
        _rollback_snapshots(snapshots)
        tracer.log("refactor", {"batch_id": batch_id, "error": str(e), "rolled_back": list(snapshots.keys())})
        return {"error_state": f"Refactor failed: {e}. Rolled back {len(snapshots)} files."}

    tracer.log("refactor", {
        "batch_id": batch_id,
        "files_changed": len(results),
        "total_matches": sum(r.match_count for r in results),
        "status": "applied",
    })

    return {
        "file_buffer": new_file_buffer,
        "edit_history": new_edit_history,
        "error_state": None,
    }


def _rollback_snapshots(snapshots: dict[str, str]) -> None:
    """Best-effort rollback: restore files from snapshots."""
    for file_path, original_content in snapshots.items():
        try:
            with open(file_path, "w") as f:
                f.write(original_content)
        except OSError:
            pass


def _find_pending_batch(edit_history: list[dict]) -> str | None:
    """Find a batch_id from a pending refactor in edit_history."""
    for entry in edit_history:
        if entry.get("status") == "proposed" and entry.get("batch_id"):
            return entry["batch_id"]
    return None
