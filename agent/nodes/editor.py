import json
from agent.prompts.editor import EDITOR_SYSTEM, EDITOR_USER
from agent.tools.file_ops import read_file, edit_file
from agent.tracing import TraceLogger

tracer = TraceLogger()


async def editor_node(state: dict, config: dict) -> dict:
    router = config["configurable"]["router"]
    file_buffer = state.get("file_buffer", {})
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)

    if not file_buffer:
        return {"error_state": "No files in buffer to edit"}

    file_path = list(file_buffer.keys())[0]
    content = file_buffer[file_path]

    # Determine complexity from typed step
    complexity = "simple"
    if current_step < len(plan):
        step = plan[current_step]
        if isinstance(step, dict):
            complexity = step.get("complexity", "simple")

    task_type = "edit_complex" if complexity == "complex" else "edit_simple"

    # Number the lines for the LLM
    lines = content.split("\n")
    numbered = "\n".join(f"{i+1}: {line}" for i, line in enumerate(lines))

    # Build instruction from step
    step_text = ""
    if current_step < len(plan):
        step = plan[current_step]
        step_text = step if isinstance(step, str) else step.get("id", "edit")

    context = state.get("context", {})
    context_section = ""
    if context.get("spec"):
        context_section = f"Spec: {context['spec']}"

    user_prompt = EDITOR_USER.format(
        file_path=file_path,
        numbered_content=numbered,
        edit_instruction=step_text,
        context_section=context_section,
    )

    raw = await router.call(task_type, EDITOR_SYSTEM, user_prompt)

    # Parse JSON response
    try:
        data = json.loads(raw)
        anchor = data["anchor"]
        replacement = data["replacement"]
    except (json.JSONDecodeError, KeyError) as e:
        return {"error_state": f"Editor output parse error: {e}"}

    # Apply edit
    result = edit_file(file_path, anchor, replacement)
    if result.get("error"):
        tracer.log("editor", {"file": file_path, "error": result["error"]})
        return {
            "error_state": result["error"],
            "edit_history": state.get("edit_history", []) + [
                {"file": file_path, "error": result["error"]}
            ],
        }

    tracer.log("editor", {"file": file_path, "anchor": anchor[:50], "model": task_type})

    updated_content = read_file(file_path)
    return {
        "file_buffer": {**file_buffer, file_path: updated_content},
        "edit_history": state.get("edit_history", []) + [
            {"file": file_path, "old": anchor, "new": replacement, "snapshot": result.get("snapshot")}
        ],
        "error_state": None,
    }
