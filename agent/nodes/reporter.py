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
        "files_edited": list(set(e["file"] for e in edit_history)),
        "error": error_state,
        "status": status,
        "model_usage": state.get("model_usage", {}),
    }
    tracer.log("reporter", summary)
    tracer.save()

    return {"error_state": error_state}
