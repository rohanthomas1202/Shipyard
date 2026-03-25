import json
import os
from agent.prompts.editor import EDITOR_SYSTEM, EDITOR_USER
from agent.tools.file_ops import read_file, edit_file
from agent.tracing import TraceLogger
from store.models import EditRecord

tracer = TraceLogger()


def _detect_language(file_path: str) -> str | None:
    """Detect ast-grep language from file extension. Uses ast_ops mapping (DRY)."""
    try:
        from agent.tools.ast_ops import _EXT_TO_LANGUAGE
        _, ext = os.path.splitext(file_path)
        return _EXT_TO_LANGUAGE.get(ext.lower())
    except ImportError:
        return None


def _read_raw(file_path: str) -> str:
    """Read file content as raw text (not numbered). For file_buffer updates."""
    with open(file_path, "r") as f:
        return f.read()


def _select_file(state: dict) -> str:
    """Select the file to edit from step target_files or file_buffer."""
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    file_buffer = state.get("file_buffer", {})

    if current_step < len(plan):
        step = plan[current_step]
        if isinstance(step, dict):
            target_files = step.get("target_files", [])
            if target_files:
                for tf in target_files:
                    if tf in file_buffer:
                        return tf
    return list(file_buffer.keys())[0] if file_buffer else ""


async def editor_node(state: dict, config: dict) -> dict:
    router = config["configurable"]["router"]
    approval_manager = config["configurable"].get("approval_manager")
    run_id = config["configurable"].get("run_id", "")
    supervised = config["configurable"].get("supervised", False)

    file_buffer = state.get("file_buffer", {})
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)

    if not file_buffer:
        return {"error_state": "No files in buffer to edit"}

    # Clear ast-grep cache if files were invalidated by executor
    if state.get("invalidated_files") == ["*"]:
        try:
            from agent.tools.ast_ops import clear_cache
            clear_cache()
        except ImportError:
            pass

    file_path = _select_file(state)
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

    # --- ast-grep enhancement: structural validation + replace ---
    ast_available = state.get("ast_available", {})
    language = _detect_language(file_path)
    new_content = None

    if language and ast_available.get(language):
        try:
            from agent.tools.ast_ops import validate_anchor, structural_replace
            result = validate_anchor(content, anchor, language)
            if result.structural_match:
                try:
                    new_content = structural_replace(content, anchor, replacement, language)
                except Exception:
                    tracer.log("editor", {"ast_grep": "structural_replace_failed", "file": file_path})
                    new_content = None
            else:
                tracer.log("editor", {
                    "ast_grep": "non_structural_anchor",
                    "node_type": result.node_type,
                    "file": file_path,
                })
        except ImportError:
            pass  # ast-grep-py not available
    # --- End ast-grep enhancement ---

    # If approval_manager is present, use approval gates
    if approval_manager is not None:
        # When using full-file content: ApprovalManager._write_edit_to_file() handles
        # this correctly — it does content.replace(old_content, new_content, 1), and
        # when old_content IS the full file, this replaces the entire file content.
        edit_old = anchor
        edit_new = replacement
        if new_content is not None:
            edit_old = content
            edit_new = new_content

        edit_record = EditRecord(
            run_id=run_id,
            file_path=file_path,
            old_content=edit_old,
            new_content=edit_new,
            step=current_step,
        )
        proposed = await approval_manager.propose_edit(run_id, edit_record)

        if supervised:
            tracer.log("editor", {"file": file_path, "edit_id": proposed.id, "mode": "supervised"})
            return {
                "waiting_for_human": True,
                "edit_history": state.get("edit_history", []) + [
                    {"file": file_path, "edit_id": proposed.id, "status": "proposed"}
                ],
                "error_state": None,
            }
        else:
            op_id = f"op_{proposed.id}_auto"
            await approval_manager.approve(proposed.id, op_id)
            applied = await approval_manager.apply_edit(proposed.id)
            tracer.log("editor", {"file": file_path, "edit_id": applied.id, "mode": "autonomous"})
            updated_content = _read_raw(file_path)  # raw content, not numbered
            return {
                "file_buffer": {**file_buffer, file_path: updated_content},
                "edit_history": state.get("edit_history", []) + [
                    {"file": file_path, "edit_id": applied.id, "old": anchor, "new": replacement, "status": "applied"}
                ],
                "error_state": None,
            }

    # Legacy path (no approval_manager)
    if new_content is not None:
        # ast-grep produced the result — write it directly
        snapshot = content
        with open(file_path, "w") as f:
            f.write(new_content)
        tracer.log("editor", {"file": file_path, "anchor": anchor[:50], "model": task_type, "ast_grep": True})
        return {
            "file_buffer": {**file_buffer, file_path: new_content},
            "edit_history": state.get("edit_history", []) + [
                {"file": file_path, "old": anchor, "new": replacement, "snapshot": snapshot}
            ],
            "error_state": None,
        }

    # Fallback: existing str.replace path
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

    updated_content = _read_raw(file_path)  # raw content, not numbered
    return {
        "file_buffer": {**file_buffer, file_path: updated_content},
        "edit_history": state.get("edit_history", []) + [
            {"file": file_path, "old": anchor, "new": replacement, "snapshot": result.get("snapshot")}
        ],
        "error_state": None,
    }
