"""File operations for the Shipyard agent: read, edit, create, delete, list.

Provides a 3-tier fuzzy anchor matching chain for edit_file(), indentation
preservation when applying replacements, and content hashing for freshness
detection.
"""

import os
import re
import hashlib
import glob as globlib
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FUZZY_THRESHOLD = 0.85

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _normalize_whitespace(text: str) -> str:
    """Collapse all whitespace runs to a single space, then strip."""
    return re.sub(r'\s+', ' ', text).strip()


def _find_fuzzy_match(
    content: str,
    anchor: str,
    threshold: float = FUZZY_THRESHOLD,
) -> tuple[str | None, float]:
    """Slide a window across content lines and return the best fuzzy match.

    Returns (best_match_text, best_score). If best_score < threshold the
    first element is None.
    """
    content_lines = content.split('\n')
    anchor_lines_count = anchor.count('\n') + 1

    best_score = 0.0
    best_match: str | None = None

    for i in range(len(content_lines) - anchor_lines_count + 1):
        candidate = '\n'.join(content_lines[i:i + anchor_lines_count])
        score = SequenceMatcher(None, anchor, candidate).ratio()
        if score > best_score:
            best_score = score
            best_match = candidate

    if best_score >= threshold:
        return (best_match, best_score)
    return (None, best_score)


def _detect_indent(line: str) -> tuple[str, int]:
    """Detect the indentation character and count for a line.

    Returns (char, count) where char is ' ' or '\\t'.
    """
    stripped = line.lstrip()
    indent = line[:len(line) - len(stripped)]
    if '\t' in indent:
        return ('\t', indent.count('\t'))
    return (' ', len(indent))


def _adjust_replacement_indent(
    anchor_text: str,
    replacement: str,
    content: str,
) -> str:
    """Re-indent *replacement* so it matches the indentation context of
    *anchor_text* within *content*.
    """
    # Find the first non-empty line of the anchor in content to determine
    # the base indentation level of the context.
    anchor_lines = anchor_text.split('\n')
    context_first_line = ""
    for aline in anchor_lines:
        if aline.strip():
            context_first_line = aline
            break

    if not context_first_line:
        return replacement

    ctx_char, ctx_base = _detect_indent(context_first_line)

    # Determine the replacement's own base indent (first non-empty line).
    rep_lines = replacement.split('\n')
    rep_base = 0
    rep_char = ctx_char
    for rline in rep_lines:
        if rline.strip():
            rep_char, rep_base = _detect_indent(rline)
            break

    if ctx_char == rep_char and ctx_base == rep_base:
        return replacement

    # Re-indent each line.
    result_lines: list[str] = []
    for rline in rep_lines:
        if not rline.strip():
            result_lines.append(rline)
            continue
        _, line_level = _detect_indent(rline)
        relative = line_level - rep_base
        new_level = ctx_base + relative
        new_indent = ctx_char * max(new_level, 0)
        result_lines.append(new_indent + rline.lstrip())

    return '\n'.join(result_lines)


def content_hash(content: str) -> str:
    """Return a deterministic 16-char hex digest of *content*."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Core file operations
# ---------------------------------------------------------------------------


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
    """Replace *anchor* with *replacement* in the file at *path*.

    Uses a 3-tier matching chain:
      1. Exact string match
      2. Whitespace-normalized match
      3. Fuzzy SequenceMatcher match (>= FUZZY_THRESHOLD)

    Returns a dict with 'success', 'snapshot', 'error', and match metadata.
    """
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        return {"success": False, "snapshot": None, "error": f"File not found: {path}"}

    snapshot = content

    # ---- Layer 1: Exact match ----
    count = content.count(anchor)
    if count == 1:
        adjusted = _adjust_replacement_indent(anchor, replacement, content)
        new_content = content.replace(anchor, adjusted, 1)
        with open(path, "w") as f:
            f.write(new_content)
        return {
            "success": True,
            "snapshot": snapshot,
            "error": None,
            "match_type": "exact",
        }
    if count > 1:
        return {
            "success": False,
            "snapshot": None,
            "error": f"Anchor not unique in {path} (found {count} occurrences). Provide a longer anchor.",
        }

    # ---- Layer 2: Whitespace-normalized match ----
    content_lines = content.split('\n')
    anchor_line_count = anchor.count('\n') + 1
    norm_anchor = _normalize_whitespace(anchor)

    ws_matches: list[str] = []
    for i in range(len(content_lines) - anchor_line_count + 1):
        candidate = '\n'.join(content_lines[i:i + anchor_line_count])
        if _normalize_whitespace(candidate) == norm_anchor:
            ws_matches.append(candidate)

    if len(ws_matches) == 1:
        matched_text = ws_matches[0]
        adjusted = _adjust_replacement_indent(matched_text, replacement, content)
        new_content = content.replace(matched_text, adjusted, 1)
        with open(path, "w") as f:
            f.write(new_content)
        return {
            "success": True,
            "snapshot": snapshot,
            "error": None,
            "match_type": "whitespace_normalized",
        }
    if len(ws_matches) > 1:
        return {
            "success": False,
            "snapshot": None,
            "error": f"Anchor not unique in {path} (found {len(ws_matches)} whitespace-normalized matches). Provide a longer anchor.",
        }

    # ---- Layer 3: Fuzzy match ----
    fuzzy_match, fuzzy_score = _find_fuzzy_match(content, anchor)
    if fuzzy_match is not None:
        adjusted = _adjust_replacement_indent(fuzzy_match, replacement, content)
        new_content = content.replace(fuzzy_match, adjusted, 1)
        with open(path, "w") as f:
            f.write(new_content)
        return {
            "success": True,
            "snapshot": snapshot,
            "error": None,
            "match_type": "fuzzy",
            "fuzzy_score": fuzzy_score,
        }

    # ---- All layers failed ----
    # Re-run fuzzy with threshold=0 to get best diagnostic info.
    _, best_score = _find_fuzzy_match(content, anchor, threshold=0.0)
    # Get best match text for diagnostics (use internal search).
    best_match_text: str | None = None
    best_s = 0.0
    for i in range(len(content_lines) - anchor_line_count + 1):
        candidate = '\n'.join(content_lines[i:i + anchor_line_count])
        s = SequenceMatcher(None, anchor, candidate).ratio()
        if s > best_s:
            best_s = s
            best_match_text = candidate

    return {
        "success": False,
        "snapshot": None,
        "error": f"Anchor not found in {path}",
        "best_score": best_s,
        "anchor_preview": anchor[:200],
        "best_match_preview": (best_match_text or "")[:200],
    }


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
