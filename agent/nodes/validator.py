"""Validator node — syntax and semantic validation of edits.

Uses LSP diagnostics when available (Phase 3+), falls back to subprocess
syntax checks. Rolls back edits that introduce errors.

Diagnostic diffing: only NEW errors trigger rollback. Pre-existing errors
in the project are ignored.
"""
import asyncio
import json
import os
import subprocess
from agent.tracing import TraceLogger

tracer = TraceLogger()


def _syntax_check(file_path: str) -> dict:
    """Run a language-appropriate syntax check (synchronous)."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".json":
        try:
            with open(file_path) as f:
                json.load(f)
            return {"valid": True, "error": None}
        except json.JSONDecodeError as e:
            return {"valid": False, "error": str(e)}

    if ext in (".ts", ".tsx"):
        result = subprocess.run(
            ["npx", "esbuild", file_path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return {"valid": False, "error": result.stderr[:500]}
        return {"valid": True, "error": None}

    if ext in (".js", ".jsx"):
        result = subprocess.run(
            ["node", "--check", file_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return {"valid": False, "error": result.stderr[:500]}
        return {"valid": True, "error": None}

    if ext in (".yaml", ".yml"):
        try:
            import yaml
            with open(file_path) as f:
                yaml.safe_load(f)
            return {"valid": True, "error": None}
        except Exception as e:
            return {"valid": False, "error": str(e)}

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


async def validator_node(state: dict, config: dict | None = None) -> dict:
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
                    result = await _lsp_validate(client, file_path, last_edit)
                    if result is not None:
                        return result
                except Exception as e:
                    tracer.log("validator", {"file": file_path, "lsp_error": str(e), "fallback": "syntax_check"})

    # Fallback: subprocess syntax check (wrapped in thread to avoid blocking)
    check = await asyncio.to_thread(_syntax_check, file_path)

    tracer.log("validator", {"file": file_path, "syntax_valid": check["valid"], "error": check["error"]})

    if not check["valid"]:
        _rollback(last_edit)
        return {"error_state": f"Syntax check failed for {file_path}: {check['error']}. Edit rolled back."}

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
    if baseline_content:
        baseline_diags = await client.get_diagnostics(file_path, baseline_content)

    # Get post-edit diagnostics
    post_diags = await client.get_diagnostics(file_path, post_content)

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
        return {"error_state": f"LSP validation failed for {file_path}: {error_msgs}. Edit rolled back."}

    return {"error_state": None}
