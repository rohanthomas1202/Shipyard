import json
import os
from agent.prompts.editor import EDITOR_SYSTEM, EDITOR_USER
from agent.tools.file_ops import edit_file, read_file
from agent.llm import call_llm
from agent.tracing import TraceLogger

tracer = TraceLogger()

async def editor_node(state: dict) -> dict:
    """Perform an anchor-based surgical edit on a file."""
    plan = state["plan"]
    step = state["current_step"]
    instruction = plan[step] if step < len(plan) else state["instruction"]
    working_dir = state["working_directory"]

    file_buffer = state["file_buffer"]
    if not file_buffer:
        return {**state, "error_state": "No files in buffer. Run reader first."}

    file_path = list(file_buffer.keys())[0]
    file_content = file_buffer[file_path]

    context_section = ""
    if state.get("context"):
        ctx = state["context"]
        if ctx.get("schema"):
            context_section += f"\nRelevant schema:\n{ctx['schema']}\n"
        if ctx.get("spec"):
            context_section += f"\nSpec:\n{ctx['spec']}\n"

    numbered_content = "\n".join(
        f"{i+1}: {line}" for i, line in enumerate(file_content.split("\n"))
    )
    user_prompt = EDITOR_USER.format(
        file_path=file_path,
        file_content=numbered_content,
        edit_instruction=instruction,
        context_section=context_section,
    )

    response = await call_llm(EDITOR_SYSTEM, user_prompt)

    try:
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        edit_data = json.loads(text)
        anchor = edit_data["anchor"]
        replacement = edit_data["replacement"]
    except (json.JSONDecodeError, KeyError) as e:
        return {
            "error_state": f"Failed to parse editor response: {e}\nResponse: {response[:500]}",
            "edit_history": state["edit_history"],
        }

    result = edit_file(file_path, anchor, replacement)

    if not result["success"]:
        tracer.log("editor", {"file": file_path, "anchor": anchor[:100], "result": "failed", "error": result["error"]})
        return {
            "error_state": result["error"],
            "edit_history": state["edit_history"],
        }

    edit_entry = {
        "file": file_path,
        "anchor": anchor,
        "replacement": replacement,
        "snapshot": result["snapshot"],
    }
    new_history = state["edit_history"] + [edit_entry]
    new_content = open(file_path).read()
    new_buffer = {**file_buffer, file_path: new_content}

    tracer.log("editor", {"file": file_path, "anchor": anchor[:100], "result": "success"})

    return {
        "error_state": None,
        "edit_history": new_history,
        "file_buffer": new_buffer,
    }
