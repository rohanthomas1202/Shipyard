from agent.tracing import TraceLogger

tracer = TraceLogger()

def receive_instruction_node(state: dict) -> dict:
    tracer.log("receive_instruction", {
        "instruction": state.get("instruction", ""),
        "has_context": bool(state.get("context")),
    })
    return {"current_step": 0, "error_state": None, "model_usage": {}}
