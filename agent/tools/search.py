import os
import re

def search_content(pattern: str, directory: str, file_glob: str = "*") -> str:
    results = []
    for root, _dirs, files in os.walk(directory):
        for fname in files:
            if file_glob != "*" and not fname.endswith(file_glob.lstrip("*")):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r") as f:
                    for i, line in enumerate(f, 1):
                        if re.search(pattern, line):
                            rel = os.path.relpath(fpath, directory)
                            results.append(f"{rel}:{i}: {line.rstrip()}")
            except (UnicodeDecodeError, PermissionError):
                continue
    if not results:
        return "No matches found."
    return "\n".join(results)
