"""Editor node — structured LLM output, error feedback in retries, file freshness.

Uses router.call_structured() for general-tier edits (guaranteed schema compliance),
falls back to router.call() with manual JSON parsing for reasoning-tier (o3).
Error feedback flows into retry prompts from two sources:
1. Edit-level failures (anchor matching) with failed_anchor, best_match, score
2. Validator-level failures (syntax/LSP) with file_path and error_message
File freshness is checked via content_hash before applying edits.
Uses ContextAssembler for model-aware context budget management.
"""
import json
import logging
import os
from langgraph.types import RunnableConfig
from agent.context import ContextAssembler
from agent.prompts.editor import EDITOR_SYSTEM, EDITOR_USER, ERROR_FEEDBACK_TEMPLATE
from agent.schemas import EditResponse
from agent.tools.file_ops import read_file, edit_file, content_hash
from agent.tracing import TraceLogger
from store.models import EditRecord

tracer = TraceLogger()
logger = logging.getLogger("shipyard.editor")


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


def _build_error_feedback(state: dict) -> str:
    """Build error feedback section for retry prompts.

    Handles two sources of error context:
    1. Edit-level failures (from edit_history) -- anchor not found, fuzzy match below threshold
    2. Validator-level failures (from last_validation_error) -- syntax/LSP errors after edit applied
    """
    error = state.get("error_state")
    if not error:
        return ""

    # Source 1: Check for validator-level error (syntax/LSP failure)
    validation_err = state.get("last_validation_error")
    if validation_err:
        parts = ["VALIDATION ERROR from previous attempt:"]
        parts.append("- File: " + str(validation_err.get("file_path", "unknown")))
        parts.append("- Error: " + str(validation_err.get("error_message", error)))
        vtype = validation_err.get("validator_type")
        if vtype:
            parts.append("- Validator: " + str(vtype))
        parts.append("- The previous edit was syntactically invalid and was rolled back.")
        parts.append("- Fix the issue in your next edit attempt.")
        return "\n".join(parts)

    # Source 2: Check for edit-level failure (anchor matching failure)
    edit_history = state.get("edit_history", [])
    last_error_entry = None
    for entry in reversed(edit_history):
        if entry.get("error"):
            last_error_entry = entry
            break

    if not last_error_entry:
        # Fallback: just include the error string
        return "PREVIOUS ATTEMPT FAILED:\n- Error: " + str(error)

    parts = [
        "PREVIOUS EDIT ATTEMPT FAILED:",
        "- Failed anchor: " + str(last_error_entry.get("failed_anchor", "unknown"))[:500],
        "- Error: " + str(last_error_entry.get("error", error)),
        "- Best match score: " + str(last_error_entry.get("best_score", "N/A")),
        "- Best match preview: " + str(last_error_entry.get("best_match_preview", "N/A"))[:500],
    ]
    return "\n".join(parts)


async def editor_node(state: dict, config: RunnableConfig) -> dict:
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

    # File freshness check
    file_hashes = state.get("file_hashes", {})
    stored_hash = file_hashes.get(file_path)
    if stored_hash:
        current_content = _read_raw(file_path)
        current_hash = content_hash(current_content)
        if stored_hash != current_hash:
            # File changed since last read -- update buffer
            content = current_content
            file_buffer = {**file_buffer, file_path: content}

    # Determine complexity from typed step
    complexity = "simple"
    if current_step < len(plan):
        step = plan[current_step]
        if isinstance(step, dict):
            complexity = step.get("complexity", "simple")

    task_type = "edit_complex" if complexity == "complex" else "edit_simple"

    # Resolve model budget for context assembly
    model_config = router.resolve_model(task_type)
    assembler = ContextAssembler(
        max_tokens=model_config.context_window - model_config.max_output,
    )

    # Number the lines for the LLM
    lines = content.split("\n")
    numbered = "\n".join(f"{i+1}: {line}" for i, line in enumerate(lines))

    # Build instruction from step
    step_text = ""
    if current_step < len(plan):
        step = plan[current_step]
        if isinstance(step, str):
            step_text = step
        else:
            # Typed PlanStep: combine acceptance_criteria for a meaningful instruction
            criteria = step.get("acceptance_criteria", [])
            step_text = "; ".join(criteria) if criteria else step.get("id", "edit")

    # Assemble context with budget-aware priority filling
    assembler.add_task(step_text, step=current_step + 1, total_steps=len(plan))
    assembler.add_file(file_path, numbered, priority="working")

    error_feedback = _build_error_feedback(state)
    if error_feedback:
        assembler.add_error(error_feedback)

    context = state.get("context", {})
    if context.get("spec"):
        assembler.add_file("spec", context["spec"], priority="reference")

    context_section = assembler.build()

    user_prompt = EDITOR_USER.format(
        file_path=file_path,
        numbered_content="",
        edit_instruction="",
        context_section=context_section,
        error_feedback="",
    )

    # Use structured output for general tier, fallback to string for reasoning tier (o3)
    if task_type == "edit_complex":
        # Reasoning tier (o3) may not support structured outputs -- use string path
        raw = await router.call(task_type, EDITOR_SYSTEM, user_prompt)

        logger.warning("LLM raw response: %s", raw[:500] if raw else "EMPTY")

        # Parse JSON response -- strip markdown fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines_raw = cleaned.split("\n")
            lines_raw = [l for l in lines_raw if not l.strip().startswith("```")]
            cleaned = "\n".join(lines_raw)

        try:
            data = json.loads(cleaned)
            anchor = data["anchor"]
            replacement = data["replacement"]
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Parse failed: %s | raw: %s", e, cleaned[:300])
            return {"error_state": f"Editor output parse error: {e}"}
    else:
        # General/fast tier -- use structured output (guaranteed schema compliance)
        edit_response = await router.call_structured(task_type, EDITOR_SYSTEM, user_prompt, EditResponse)
        anchor = edit_response.anchor
        replacement = edit_response.replacement

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
            updated_content = _read_raw(file_path)
            new_hash = content_hash(updated_content)
            updated_hashes = {**state.get("file_hashes", {}), file_path: new_hash}
            return {
                "file_buffer": {**file_buffer, file_path: updated_content},
                "file_hashes": updated_hashes,
                "edit_history": state.get("edit_history", []) + [
                    {"file": file_path, "edit_id": applied.id, "old": anchor, "new": replacement, "status": "applied"}
                ],
                "error_state": None,
            }

    # Legacy path (no approval_manager)
    if new_content is not None:
        # ast-grep produced the result -- write it directly
        snapshot = content
        with open(file_path, "w") as f:
            f.write(new_content)
        tracer.log("editor", {"file": file_path, "anchor": anchor[:50], "model": task_type, "ast_grep": True})
        updated_content = _read_raw(file_path)
        new_hash = content_hash(updated_content)
        updated_hashes = {**state.get("file_hashes", {}), file_path: new_hash}
        return {
            "file_buffer": {**file_buffer, file_path: new_content},
            "file_hashes": updated_hashes,
            "edit_history": state.get("edit_history", []) + [
                {"file": file_path, "old": anchor, "new": replacement, "snapshot": snapshot}
            ],
            "error_state": None,
        }

    # Fallback: existing str.replace path via edit_file
    result = edit_file(file_path, anchor, replacement)
    if result.get("error"):
        tracer.log("editor", {"file": file_path, "error": result["error"]})
        error_entry = {
            "file": file_path,
            "error": result["error"],
            "failed_anchor": anchor[:500],
            "best_score": result.get("best_score"),
            "best_match_preview": result.get("best_match_preview", ""),
        }
        return {
            "error_state": result["error"],
            "edit_history": state.get("edit_history", []) + [error_entry],
        }

    tracer.log("editor", {"file": file_path, "anchor": anchor[:50], "model": task_type})

    updated_content = _read_raw(file_path)
    new_hash = content_hash(updated_content)
    updated_hashes = {**state.get("file_hashes", {}), file_path: new_hash}
    return {
        "file_buffer": {**file_buffer, file_path: updated_content},
        "file_hashes": updated_hashes,
        "edit_history": state.get("edit_history", []) + [
            {"file": file_path, "old": anchor, "new": replacement, "snapshot": result.get("snapshot")}
        ],
        "error_state": None,
    }
