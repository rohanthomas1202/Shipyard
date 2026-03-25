"""ast-grep structural operations for Shipyard's edit pipeline.

Provides AST-aware anchor validation and structural replacement using
ast-grep-py (tree-sitter). Falls back gracefully when ast-grep is unavailable
or the language is unsupported.
"""
from __future__ import annotations

import hashlib
import os
import subprocess as _subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

try:
    from ast_grep_py import SgRoot
    AST_GREP_AVAILABLE = True
except ImportError:
    AST_GREP_AVAILABLE = False


@dataclass
class AnchorResult:
    """Result of structural anchor validation."""
    structural_match: bool
    unsupported_language: bool = False
    node_type: str | None = None


@dataclass
class MatchStats:
    """Per-run ast-grep match statistics."""
    structural_matches: int = 0
    fallbacks_to_text: int = 0
    unsupported_language_skips: int = 0
    cache_hits: int = 0
    cache_misses: int = 0


# Module-level stats, reset per run
_stats = MatchStats()


def get_stats() -> MatchStats:
    return _stats


def reset_stats() -> None:
    global _stats
    _stats = MatchStats()


# --- Parse tree cache ---

_parse_cache: dict[tuple[str, str], Any] = {}
_cache_max_size: int = 64


def _content_hash(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()


def _get_cached_root(content: str, language: str):
    key = (language, _content_hash(content))
    if key in _parse_cache:
        _stats.cache_hits += 1
        return _parse_cache[key]
    _stats.cache_misses += 1
    root = SgRoot(content, language)
    if len(_parse_cache) >= _cache_max_size:
        oldest_key = next(iter(_parse_cache))
        del _parse_cache[oldest_key]
    _parse_cache[key] = root
    return root


def clear_cache() -> None:
    _parse_cache.clear()


def set_cache_size(size: int) -> None:
    global _cache_max_size
    _cache_max_size = size


# --- validate_anchor ---

def validate_anchor(content: str, anchor: str, language: str) -> AnchorResult:
    """Check if anchor aligns with AST node boundaries."""
    if not AST_GREP_AVAILABLE:
        _stats.unsupported_language_skips += 1
        return AnchorResult(structural_match=False, unsupported_language=True)

    try:
        root = _get_cached_root(content, language)
    except BaseException:
        _stats.unsupported_language_skips += 1
        return AnchorResult(structural_match=False, unsupported_language=True)

    start = content.find(anchor)
    if start == -1:
        return AnchorResult(structural_match=False)

    end = start + len(anchor)
    tree_root = root.root()

    result = _check_node_boundaries(tree_root, start, end)
    if result.structural_match:
        _stats.structural_matches += 1
    else:
        _stats.fallbacks_to_text += 1
    return result


def _check_node_boundaries(node, start: int, end: int) -> AnchorResult:
    node_start = node.range().start.index
    node_end = node.range().end.index

    if node_start == start and node_end == end:
        return AnchorResult(structural_match=True, node_type=node.kind())

    children = list(node.children())
    if not children:
        return AnchorResult(structural_match=False, node_type=node.kind())

    for i in range(len(children)):
        cs = children[i].range().start.index
        if cs > start:
            break
        if cs == start:
            for j in range(i, len(children)):
                ce = children[j].range().end.index
                if ce == end:
                    return AnchorResult(structural_match=True, node_type=node.kind())
                if ce > end:
                    break

    for child in children:
        cs = child.range().start.index
        ce = child.range().end.index
        if cs <= start and ce >= end:
            result = _check_node_boundaries(child, start, end)
            if result.structural_match:
                return result
            return AnchorResult(structural_match=False, node_type=child.kind())

    return AnchorResult(structural_match=False, node_type=node.kind())


# --- structural_replace ---

def structural_replace(content: str, anchor: str, replacement: str, language: str) -> str:
    """Perform indentation-aware replacement using AST context.
    Pure function — returns new file content without writing to disk."""
    if not AST_GREP_AVAILABLE:
        return content.replace(anchor, replacement, 1)

    result = validate_anchor(content, anchor, language)

    if not result.structural_match or result.unsupported_language:
        return content.replace(anchor, replacement, 1)

    return _apply_with_indentation(content, anchor, replacement)


def _apply_with_indentation(content: str, anchor: str, replacement: str) -> str:
    """Apply replacement preserving the original anchor's indentation context."""
    start = content.find(anchor)
    if start == -1:
        return content.replace(anchor, replacement, 1)

    line_start = content.rfind("\n", 0, start)
    if line_start == -1:
        original_indent = ""
    else:
        between = content[line_start + 1:start]
        original_indent = between if between.isspace() else ""

    if not replacement or "\n" not in replacement:
        return content[:start] + replacement + content[start + len(anchor):]

    rep_lines = replacement.split("\n")
    if len(rep_lines) <= 1:
        return content[:start] + replacement + content[start + len(anchor):]

    subsequent = rep_lines[1:]
    if subsequent:
        non_empty = [l for l in subsequent if l.strip()]
        if non_empty:
            min_indent = min(len(l) - len(l.lstrip()) for l in non_empty)
        else:
            min_indent = 0

        adjusted = [rep_lines[0]]
        for line in subsequent:
            if not line.strip():
                adjusted.append("")
            else:
                stripped_indent = len(line) - len(line.lstrip())
                extra = stripped_indent - min_indent
                adjusted.append(original_indent + " " * extra + line.lstrip())
        replacement = "\n".join(adjusted)

    return content[:start] + replacement + content[start + len(anchor):]


# Extension → ast-grep language mapping
_EXT_TO_LANGUAGE: dict[str, str] = {
    ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript",
    ".py": "python",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".swift": "swift",
    ".kt": "kotlin",
    ".lua": "lua",
    ".html": "html",
    ".css": "css",
    ".json": "json",
    ".yaml": "yaml", ".yml": "yaml",
}


def detect_languages(working_directory: str) -> dict[str, bool]:
    """Detect languages in a working directory and check ast-grep grammar support."""
    extensions = _collect_extensions(working_directory)
    languages: set[str] = set()
    for ext in extensions:
        lang = _EXT_TO_LANGUAGE.get(ext)
        if lang:
            languages.add(lang)

    result: dict[str, bool] = {}
    for lang in languages:
        result[lang] = _probe_grammar(lang)
    return result


def _collect_extensions(directory: str) -> set[str]:
    try:
        proc = _subprocess.run(
            ["git", "ls-files"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            extensions = set()
            for line in proc.stdout.strip().split("\n")[:10_000]:
                _, ext = os.path.splitext(line)
                if ext:
                    extensions.add(ext.lower())
            return extensions
    except (FileNotFoundError, _subprocess.TimeoutExpired):
        pass

    exclusions = {"node_modules", ".git", "__pycache__", "dist", "build", ".venv", "target"}
    extensions = set()
    count = 0
    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames[:] = [d for d in dirnames if d not in exclusions]
        for f in filenames:
            _, ext = os.path.splitext(f)
            if ext:
                extensions.add(ext.lower())
            count += 1
            if count >= 10_000:
                return extensions
    return extensions


def _probe_grammar(language: str) -> bool:
    if not AST_GREP_AVAILABLE:
        return False
    try:
        SgRoot("x", language)
        return True
    except BaseException:
        return False
