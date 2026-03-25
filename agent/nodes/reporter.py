from agent.tracing import TraceLogger

tracer = TraceLogger()

def reporter_node(state: dict) -> dict:
    edit_history = state.get("edit_history", [])
    error_state = state.get("error_state")
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)

    if error_state is None:
        status = "completed"
    elif current_step < len(plan):
        status = "waiting_for_human"
    else:
        status = "failed"

    summary = {
        "steps_completed": current_step,
        "total_steps": len(plan),
        "edits_made": len(edit_history),
        "files_edited": list(set(e["file"] for e in edit_history if "file" in e)),
        "error": error_state,
        "status": status,
        "model_usage": state.get("model_usage", {}),
    }

    # Log ast-grep statistics if available
    try:
        from agent.tools.ast_ops import get_stats
        stats = get_stats()
        summary["ast_grep"] = {
            "structural_matches": stats.structural_matches,
            "fallbacks_to_text": stats.fallbacks_to_text,
            "unsupported_language_skips": stats.unsupported_language_skips,
            "cache_hits": stats.cache_hits,
            "cache_misses": stats.cache_misses,
        }
    except ImportError:
        pass

    tracer.log("reporter", summary)
    tracer.save()

    return {"error_state": error_state}
