"""Validator node — syntax and semantic validation of edits.

Uses LSP diagnostics when available (Phase 3+), falls back to subprocess
syntax checks. Rolls back edits that introduce errors.

Diagnostic diffing: only NEW errors trigger rollback. Pre-existing errors
in the project are ignored.
"""
import ast
import asyncio
import json
import os
import re
from langgraph.types import RunnableConfig
from agent.tools.shell import run_command_async
from agent.tracing import TraceLogger


def _normalize_error_msg(msg: str) -> str:
    """Strip line/col numbers and paths for error dedup comparison."""
    normalized = re.sub(r'[Ll]ine \d+', 'Line N', msg)
    normalized = re.sub(r'col \d+|column \d+|offset \d+', 'col N', normalized)
    normalized = re.sub(r'/[^\s:]+/', '/', normalized)
    return normalized.strip()

tracer = TraceLogger()


async def _syntax_check(file_path: str) -> dict:
    """Run a language-appropriate syntax check (async)."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".json":
        try:
            with open(file_path) as f:
                json.load(f)
            return {"valid": True, "error": None}
        except json.JSONDecodeError as e:
            return {"valid": False, "error": str(e)}

    if ext in (".ts", ".tsx"):
        result = await run_command_async(["npx", "esbuild", file_path], timeout=30)
        if result["exit_code"] != 0:
            return {"valid": False, "error": result["stderr"][:500]}
        return {"valid": True, "error": None}

    if ext in (".js", ".jsx"):
        result = await run_command_async(["node", "--check", file_path], timeout=10)
        if result["exit_code"] != 0:
            return {"valid": False, "error": result["stderr"][:500]}
        return {"valid": True, "error": None}

    if ext in (".yaml", ".yml"):
        try:
            import yaml
            with open(file_path) as f:
                yaml.safe_load(f)
            return {"valid": True, "error": None}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    if ext == ".py":
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
            ast.parse(source, filename=file_path)
            return {"valid": True, "error": None}
        except SyntaxError as e:
            error = f"Line {e.lineno}, col {e.offset}: {e.msg}"
            if e.text:
                error += f" | {e.text.strip()}"
            return {"valid": False, "error": error}

    return {"valid": True, "error": None}


def _rollback(edit_entry: dict):
    """Restore a file from its snapshot."""
    if "snapshot" in edit_entry:
        with open(edit_entry["file"], "w") as f:
            f.write(edit_entry["snapshot"])


def _detect_language(file_path: str) -> str | None:
    """Detect language from file extension for LSP client lookup."""
    ext_map = {
        ".ts": "typescript", ".tsx": "typescript",
        ".js": "javascript", ".jsx": "javascript",
        ".py": "python", ".rs": "rust", ".go": "go",
    }
    _, ext = os.path.splitext(file_path)
    return ext_map.get(ext.lower())


async def validator_node(state: dict, config: RunnableConfig | None = None) -> dict:
    """Validate the most recent edit. Rollback if validation fails.

    Uses LSP diagnostics when lsp_manager is available, falls back to
    subprocess syntax checks otherwise.

    Note: config parameter added for LSP integration. LangGraph auto-injects
    it for nodes that declare it. Default None for backward compatibility
    with existing tests that call validator_node(state) without config.
    """
    if config is None:
        config = {"configurable": {}}
    edit_history = state.get("edit_history", [])
    if not edit_history:
        return {"error_state": None}

    last_edit = edit_history[-1]
    if "file" not in last_edit:
        return {"error_state": None}

    file_path = last_edit["file"]

    # Try LSP validation first
    lsp_manager = config["configurable"].get("lsp_manager")
    if lsp_manager is not None:
        language = _detect_language(file_path)
        if language:
            client = lsp_manager.get_client(language)
            if client is not None:
                try:
                    result = await asyncio.wait_for(
                        _lsp_validate(client, file_path, last_edit),
                        timeout=30.0,
                    )
                    if result is not None:
                        return result
                except (Exception, asyncio.TimeoutError) as e:
                    tracer.log("validator", {
                        "file": file_path,
                        "lsp_error": str(e),
                        "lsp_error_type": type(e).__name__,
                        "fallback": "syntax_check",
                    })

    # Fallback: async syntax check
    check = await _syntax_check(file_path)

    tracer.log("validator", {"file": file_path, "syntax_valid": check["valid"], "error": check["error"]})

    context = state.get("context", {})
    if context.get("test_results"):
        tracer.log("validator_context", {"test_results_available": True})

    if not check["valid"]:
        _rollback(last_edit)
        error_msg = f"Syntax check failed for {file_path}: {check['error']}. Edit rolled back."
        error_history = list(state.get("validation_error_history", []))
        error_history.append({
            "step": state.get("current_step", 0),
            "file_path": file_path,
            "normalized_error": _normalize_error_msg(check["error"]),
        })
        return {
            "error_state": error_msg,
            "last_validation_error": {
                "file_path": file_path,
                "error_message": check["error"],
                "validator_type": "syntax_check",
            },
            "validation_error_history": error_history,
        }

    return {"error_state": None}


async def _lsp_validate(client, file_path: str, edit_entry: dict) -> dict | None:
    """Validate using LSP diagnostic diffing.

    Returns validation result dict, or None to fall back to syntax check.
    """
    from agent.tools.lsp_client import diff_diagnostics
    from lsprotocol import types

    # Read current (post-edit) content
    try:
        with open(file_path, "r") as f:
            post_content = f.read()
    except OSError:
        return None

    # Get baseline diagnostics (pre-edit content from snapshot)
    baseline_content = edit_entry.get("snapshot")
    baseline_diags = []
    try:
        if baseline_content:
            baseline_diags = await client.get_diagnostics(file_path, baseline_content)
    except Exception:
        return None  # Fall back to syntax check

    # Get post-edit diagnostics
    try:
        post_diags = await client.get_diagnostics(file_path, post_content)
    except Exception:
        return None  # Fall back to syntax check

    # Diff: only new errors trigger rollback
    new_errors = diff_diagnostics(baseline_diags, post_diags)

    tracer.log("validator", {
        "file": file_path,
        "lsp": True,
        "baseline_errors": len([d for d in baseline_diags if d.severity == types.DiagnosticSeverity.Error]),
        "post_errors": len([d for d in post_diags if d.severity == types.DiagnosticSeverity.Error]),
        "new_errors": len(new_errors),
    })

    if new_errors:
        # Rollback and notify LSP
        _rollback(edit_entry)
        await client.notify_rollback(file_path, baseline_content or "")

        error_msgs = "; ".join(f"{e.message} (code {e.code})" for e in new_errors[:3])
        error_msg = f"LSP validation failed for {file_path}: {error_msgs}. Edit rolled back."
        return {
            "error_state": error_msg,
            "last_validation_error": {
                "file_path": file_path,
                "error_message": error_msgs,
                "validator_type": "lsp",
            },
            "validation_error_history": error_history,
        }

    return {"error_state": None}
