"""Reporter node — summarizes run results and emits token usage.

Collects edit history, error state, ast-grep statistics, and token usage
from the ModelRouter to produce a comprehensive run summary for traces.
"""
from langgraph.types import RunnableConfig
from agent.node_events import emit_status, flush_node
from agent.tracing import TraceLogger

tracer = TraceLogger()


async def reporter_node(state: dict, config: RunnableConfig) -> dict:
    await emit_status(config, "reporter", "Generating summary...")

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

    # Extract token usage from router
    router = config["configurable"]["router"]
    token_summary = router.get_usage_summary()

    summary = {
        "steps_completed": current_step,
        "total_steps": len(plan),
        "edits_made": len(edit_history),
        "files_edited": list(set(e["file"] for e in edit_history if "file" in e)),
        "error": error_state,
        "status": status,
        "token_usage": token_summary,
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

    await flush_node(config)
    return {"error_state": error_state, "model_usage": token_summary}
