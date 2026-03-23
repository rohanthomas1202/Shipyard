from agent.tools.shell import run_command
from agent.tracing import TraceLogger

tracer = TraceLogger()

def executor_node(state: dict) -> dict:
    plan = state.get("plan", [])
    step = state.get("current_step", 0)
    working_dir = state["working_directory"]

    if step >= len(plan):
        return {"error_state": None}

    step_text = plan[step]
    command = step_text
    for prefix in ["Run:", "run:", "Execute:", "execute:"]:
        if prefix in step_text:
            command = step_text.split(prefix, 1)[1].strip()
            break

    result = run_command(command, cwd=working_dir)
    tracer.log("executor", {
        "command": command,
        "exit_code": result["exit_code"],
        "stdout_preview": result["stdout"][:200],
        "stderr_preview": result["stderr"][:200],
    })

    if result["exit_code"] != 0:
        return {"error_state": f"Command failed (exit {result['exit_code']}): {result['stderr'][:500]}"}

    return {"error_state": None}
