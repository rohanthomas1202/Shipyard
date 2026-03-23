import os
import glob as globlib

def read_file(path: str) -> str:
    try:
        with open(path, "r") as f:
            lines = f.readlines()
        numbered = [f"{i+1}: {line.rstrip()}" for i, line in enumerate(lines)]
        return "\n".join(numbered)
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error reading {path}: {e}"

def edit_file(path: str, anchor: str, replacement: str) -> dict:
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        return {"success": False, "snapshot": None, "error": f"File not found: {path}"}
    count = content.count(anchor)
    if count == 0:
        return {"success": False, "snapshot": None, "error": f"Anchor not found in {path}"}
    if count > 1:
        return {"success": False, "snapshot": None, "error": f"Anchor not unique in {path} (found {count} occurrences). Provide a longer anchor."}
    snapshot = content
    new_content = content.replace(anchor, replacement, 1)
    with open(path, "w") as f:
        f.write(new_content)
    return {"success": True, "snapshot": snapshot, "error": None}

def create_file(path: str, content: str) -> dict:
    if os.path.exists(path):
        return {"success": False, "error": f"File already exists: {path}"}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    return {"success": True, "error": None}

def delete_file(path: str) -> dict:
    try:
        os.remove(path)
        return {"success": True, "error": None}
    except FileNotFoundError:
        return {"success": False, "error": f"File not found: {path}"}

def list_files(directory: str, pattern: str = "*") -> str:
    matches = globlib.glob(os.path.join(directory, "**", pattern), recursive=True)
    relative = [os.path.relpath(m, directory) for m in matches if os.path.isfile(m)]
    return "\n".join(sorted(relative)) if relative else "No files found."
