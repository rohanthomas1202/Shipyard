"""Merger node -- merges outputs from parallel subgraphs and detects conflicts."""
import logging
from agent.tracing import TraceLogger

logger = logging.getLogger(__name__)
tracer = TraceLogger()


def merge_batch_results(batch_results: list[dict]) -> dict:
    """Merge results from parallel batch executions.

    Concatenates edit_history, merges file_buffer, detects same-file conflicts.
    """
    merged_edits = []
    merged_buffer = {}
    all_files_edited = []

    for result in batch_results:
        merged_edits.extend(result.get("edit_history", []))
        merged_buffer.update(result.get("file_buffer", {}))
        for entry in result.get("edit_history", []):
            if entry.get("file"):
                all_files_edited.append(entry["file"])

    # Detect same-file conflicts
    seen = set()
    has_conflicts = False
    for f in all_files_edited:
        if f in seen:
            has_conflicts = True
            break
        seen.add(f)

    # Collect errors
    errors = [r.get("error_state") for r in batch_results if r.get("error_state")]
    error_state = "; ".join(errors) if errors else None

    return {
        "edit_history": merged_edits,
        "file_buffer": merged_buffer,
        "has_conflicts": has_conflicts,
        "error_state": error_state,
    }


def merger_node(state: dict) -> dict:
    """Merge outputs from parallel subgraphs."""
    edit_history = state.get("edit_history", [])
    all_files = [e["file"] for e in edit_history if e.get("file")]
    has_conflicts = False

    seen_files = set()
    for f in all_files:
        if f in seen_files:
            has_conflicts = True
            break
        seen_files.add(f)

    tracer.log("merger", {
        "total_edits": len(edit_history),
        "files": list(seen_files),
        "has_conflicts": has_conflicts,
    })

    return {"has_conflicts": has_conflicts}
