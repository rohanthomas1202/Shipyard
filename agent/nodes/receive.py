from agent.node_events import emit_status, flush_node
from agent.tracing import TraceLogger

tracer = TraceLogger()


async def receive_instruction_node(state: dict, config: dict = None) -> dict:
    if config is None:
        config = {"configurable": {}}
    await emit_status(config, "receive", "Receiving instruction...")

    tracer.log("receive_instruction", {
        "instruction": state.get("instruction", ""),
        "has_context": bool(state.get("context")),
    })

    result = {"current_step": 0, "error_state": None, "model_usage": {}}

    # Detect languages for ast-grep support
    working_dir = state.get("working_directory", "")
    if working_dir:
        try:
            from agent.tools.ast_ops import detect_languages, reset_stats, clear_cache
            reset_stats()
            clear_cache()
            result["ast_available"] = detect_languages(working_dir)
            tracer.log("language_detection", {"ast_available": result["ast_available"]})
        except Exception as e:
            tracer.log("language_detection", {"error": str(e)})
            result["ast_available"] = {}

    await flush_node(config)
    return result
