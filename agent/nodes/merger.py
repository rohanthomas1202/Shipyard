from agent.tracing import TraceLogger

tracer = TraceLogger()

def merger_node(state: dict) -> dict:
    """Merge outputs from parallel subgraphs. Stub — full implementation in Task 6."""
    edit_history = state.get("edit_history", [])
    all_files = [e["file"] for e in edit_history]
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
