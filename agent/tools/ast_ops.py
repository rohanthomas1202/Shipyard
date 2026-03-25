"""ast-grep structural operations for Shipyard's edit pipeline.

Provides AST-aware anchor validation and structural replacement using
ast-grep-py (tree-sitter). Falls back gracefully when ast-grep is unavailable
or the language is unsupported.
"""
from __future__ import annotations

import hashlib
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
