import json
import os
import re
import subprocess
from agent.tracing import TraceLogger


def _normalize_error_msg(msg: str) -> str:
    """Strip line/col numbers and paths for error dedup comparison."""
    normalized = re.sub(r'[Ll]ine \d+', 'Line N', msg)
    normalized = re.sub(r'col \d+|column \d+|offset \d+', 'col N', normalized)
    normalized = re.sub(r'/[^\s:]+/', '/', normalized)
    return normalized.strip()

tracer = TraceLogger()

def _syntax_check(file_path: str) -> dict:
    """Run a language-appropriate syntax check."""
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

    # For .md, .sh, .css — skip syntax check
    return {"valid": True, "error": None}

def _rollback(edit_entry: dict):
    """Restore a file from its snapshot."""
    with open(edit_entry["file"], "w") as f:
        f.write(edit_entry["snapshot"])

def validator_node(state: dict) -> dict:
    """Validate the most recent edit. Rollback if syntax check fails."""
    edit_history = state["edit_history"]
    if not edit_history:
        return {"error_state": None}

    last_edit = edit_history[-1]
    file_path = last_edit["file"]

    check = _syntax_check(file_path)

    tracer.log("validator", {"file": file_path, "syntax_valid": check["valid"], "error": check["error"]})

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
