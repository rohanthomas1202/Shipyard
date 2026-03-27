from agent.node_events import emit_status, emit_node_event, flush_node
from agent.tools.shell import run_command_async
from agent.tracing import TraceLogger

tracer = TraceLogger()


async def executor_node(state: dict, config: dict = None) -> dict:
    if config is None:
        config = {"configurable": {}}

    plan = state.get("plan", [])
    step = state.get("current_step", 0)
    working_dir = state["working_directory"]

    if step >= len(plan):
        return {"error_state": None}

    step_text = plan[step]
    if isinstance(step_text, dict):
        command = step_text.get("command", "")
    else:
        command = step_text
        for prefix in ["Run:", "run:", "Execute:", "execute:"]:
            if prefix in step_text:
                command = step_text.split(prefix, 1)[1].strip()
                break

    await emit_status(config, "executor", f"Running: {command[:80]}...")

    result = await run_command_async(["sh", "-c", command], cwd=working_dir)
    tracer.log("executor", {
        "command": command,
        "exit_code": result["exit_code"],
        "stdout_preview": result["stdout"][:200],
        "stderr_preview": result["stderr"][:200],
    })

    await emit_node_event(config, "executor", "exec_result", {"command": command, "exit_code": result["exit_code"]})

    if result["exit_code"] != 0:
        await flush_node(config)
        return {"error_state": f"Command failed (exit {result['exit_code']}): {result['stderr'][:500]}"}

    # Invalidate all cached state — exec may have modified files on disk
    await flush_node(config)
    return {"error_state": None, "invalidated_files": ["*"]}
