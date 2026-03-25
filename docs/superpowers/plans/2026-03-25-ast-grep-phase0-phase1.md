# ast-grep Integration: Phase 0 + Phase 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ast-grep structural anchor validation and indentation-aware replacement to Shipyard's edit pipeline, with language detection, parse tree caching, and buffer invalidation.

**Architecture:** Phase 0 spikes `validate_anchor()` against ast-grep-py to confirm feasibility (go/no-go gate). Phase 1a integrates `validate_anchor()` and `structural_replace()` into the editor flow as a transparent layer — the LLM prompt doesn't change. Phase 1b adds supporting infrastructure: language detection via `git ls-files`, LRU parse tree cache, blanket `file_buffer` invalidation after exec steps, and `AgentState.plan` type migration from `list[str]` to `list[str | dict]`.

**Tech Stack:** Python 3.11+, ast-grep-py, pytest, pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-25-ast-grep-lsp-integration-design.md` (Sections 1a-1e, 5-7)

**Commit rule:** Never include `Co-Authored-By` lines in commit messages.

---

## File Structure

### New Files
- `agent/tools/ast_ops.py` — validate_anchor, structural_replace, detect_languages, parse tree cache, match statistics
- `tests/test_ast_ops.py` — unit tests for all ast_ops functions
- `spike/validate_anchor_spike.py` — Phase 0 standalone spike script

### Modified Files
- `agent/state.py` — add `ast_available`, `invalidated_files` fields; change `plan` type
- `agent/nodes/receive.py` — call `detect_languages()` at run start
- `agent/nodes/editor.py` — add ast-grep validate/replace before approval flow; use step `target_files`
- `agent/nodes/executor.py` — set `invalidated_files: ["*"]` after successful execution
- `agent/graph.py` — pass `invalidated_files` through state; no new nodes in Phase 1
- `pyproject.toml` — add `ast-grep-py` dependency
- `requirements.txt` — add `ast-grep-py`

---

## Task 1: Add ast-grep-py Dependency

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`

- [ ] **Step 1: Add ast-grep-py to dependencies**

In `pyproject.toml`, add to the `dependencies` list:
```
"ast-grep-py>=0.30.0",
```

In `requirements.txt`, add:
```
ast-grep-py>=0.30.0
```

- [ ] **Step 2: Install the dependency**

Run: `pip install ast-grep-py`
Expected: Successful installation, `import ast_grep_py` works in Python.

- [ ] **Step 3: Verify ast-grep-py API works**

Run:
```bash
python -c "from ast_grep_py import SgRoot; root = SgRoot('print(1)', 'python'); print(root.root().text())"
```
Expected: Prints `print(1)` — confirms tree-sitter parsing works.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml requirements.txt
git commit -m "deps: add ast-grep-py for structural code analysis"
```

---

## Task 2: Phase 0 Spike — validate_anchor Feasibility

**Files:**
- Create: `spike/validate_anchor_spike.py`

This is the go/no-go gate. Timebox: 1-2 hours. If <40% of real anchors match AST boundaries, Phase 1a simplifies.

- [ ] **Step 1: Create spike directory**

Run: `mkdir -p spike`

- [ ] **Step 2: Write the spike script**

Create `spike/validate_anchor_spike.py`:

```python
"""Phase 0 spike: validate_anchor feasibility test.

Tests whether ast-grep-py can detect if an anchor string aligns with AST
node boundaries. Run against sample anchors to measure structural match rate.

Usage: python spike/validate_anchor_spike.py
"""
import time
from ast_grep_py import SgRoot


def validate_anchor(content: str, anchor: str, language: str) -> dict:
    """Check if anchor aligns with AST node boundaries.

    Returns dict with:
        structural_match: bool
        node_type: str | None (enclosing node if not structural)
        unsupported_language: bool
    """
    try:
        root = SgRoot(content, language)
    except Exception:
        return {"structural_match": False, "unsupported_language": True, "node_type": None}

    # Find anchor position in content
    start = content.find(anchor)
    if start == -1:
        return {"structural_match": False, "unsupported_language": False, "node_type": None}
    end = start + len(anchor)

    # Walk AST to find nodes that cover the anchor span
    tree_root = root.root()

    def find_covering_nodes(node):
        """Find the smallest node(s) whose range covers the anchor span."""
        node_start = node.range().start.index
        node_end = node.range().end.index

        # Check if this node exactly covers the anchor
        if node_start == start and node_end == end:
            return {"structural_match": True, "unsupported_language": False, "node_type": node.kind()}

        # Check children
        children = list(node.children())
        if not children:
            return None

        # Check if a contiguous sequence of siblings exactly covers the anchor
        for i in range(len(children)):
            child_start = children[i].range().start.index
            if child_start > end:
                break
            if child_start > start:
                continue
            # Try contiguous sequences starting from this child
            for j in range(i, len(children)):
                seq_end = children[j].range().end.index
                if seq_end == end and child_start == start:
                    return {"structural_match": True, "unsupported_language": False, "node_type": node.kind()}
                if seq_end > end:
                    break

        # Recurse into child that contains the span
        for child in children:
            child_start = child.range().start.index
            child_end = child.range().end.index
            if child_start <= start and child_end >= end:
                result = find_covering_nodes(child)
                if result:
                    return result
                # This node contains anchor but no child exactly covers it
                return {"structural_match": False, "unsupported_language": False, "node_type": child.kind()}

        return {"structural_match": False, "unsupported_language": False, "node_type": tree_root.kind()}

    result = find_covering_nodes(tree_root)
    return result or {"structural_match": False, "unsupported_language": False, "node_type": None}


# --- Test cases ---

TYPESCRIPT_FILE = """
import { useState } from 'react';

interface Props {
    name: string;
    count: number;
}

function Counter({ name, count }: Props) {
    const [value, setValue] = useState(count);

    const increment = () => {
        setValue(v => v + 1);
    };

    return (
        <div>
            <h1>{name}</h1>
            <p>Count: {value}</p>
            <button onClick={increment}>+</button>
        </div>
    );
}

export default Counter;
""".strip()

PYTHON_FILE = """
import os
from pathlib import Path

class FileManager:
    def __init__(self, root: str):
        self.root = Path(root)

    def read(self, path: str) -> str:
        full = self.root / path
        return full.read_text()

    def write(self, path: str, content: str) -> None:
        full = self.root / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)

def main():
    fm = FileManager("/tmp")
    fm.write("test.txt", "hello")
    print(fm.read("test.txt"))
""".strip()

# Structural anchors (should match AST boundaries)
STRUCTURAL_ANCHORS = [
    ("typescript", TYPESCRIPT_FILE, "const [value, setValue] = useState(count);"),
    ("typescript", TYPESCRIPT_FILE, """const increment = () => {
        setValue(v => v + 1);
    };"""),
    ("python", PYTHON_FILE, """def read(self, path: str) -> str:
        full = self.root / path
        return full.read_text()"""),
    ("python", PYTHON_FILE, """def __init__(self, root: str):
        self.root = Path(root)"""),
    ("python", PYTHON_FILE, "import os"),
]

# Non-structural anchors (cross AST boundaries — typical "context window" anchors)
NON_STRUCTURAL_ANCHORS = [
    ("typescript", TYPESCRIPT_FILE, """};

    return ("""),  # crosses function body + return
    ("typescript", TYPESCRIPT_FILE, """import { useState } from 'react';

interface Props {"""),  # crosses import + interface
    ("python", PYTHON_FILE, """return full.read_text()

    def write"""),  # crosses two methods
    ("python", PYTHON_FILE, """fm = FileManager("/tmp")
    fm.write("test.txt", "hello")
    print"""),  # partial statement
]


def generate_large_file(lines: int) -> str:
    """Generate a TypeScript file with N lines for performance testing."""
    parts = []
    for i in range(lines // 4):
        parts.append(f"function func_{i}(x: number): number {{\n    return x + {i};\n}}\n")
    return "\n".join(parts)


def run_spike():
    print("=" * 60)
    print("Phase 0 Spike: validate_anchor feasibility")
    print("=" * 60)

    structural_correct = 0
    structural_total = 0
    non_structural_correct = 0
    non_structural_total = 0
    total = 0
    matches = 0
    timings = []

    print("\n--- Structural anchors (should match) ---")
    for lang, content, anchor in STRUCTURAL_ANCHORS:
        t0 = time.perf_counter_ns()
        result = validate_anchor(content, anchor, lang)
        elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000
        timings.append(elapsed_ms)
        total += 1
        structural_total += 1
        if result["structural_match"]:
            matches += 1
            structural_correct += 1
        status = "MATCH" if result["structural_match"] else f"NO MATCH ({result['node_type']})"
        print(f"  [{lang}] {status} ({elapsed_ms:.1f}ms) — {anchor[:50]}...")

    print("\n--- Non-structural anchors (should NOT match) ---")
    for lang, content, anchor in NON_STRUCTURAL_ANCHORS:
        t0 = time.perf_counter_ns()
        result = validate_anchor(content, anchor, lang)
        elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000
        timings.append(elapsed_ms)
        total += 1
        non_structural_total += 1
        if result["structural_match"]:
            matches += 1
        else:
            non_structural_correct += 1
        status = "MATCH" if result["structural_match"] else f"NO MATCH ({result['node_type']})"
        print(f"  [{lang}] {status} ({elapsed_ms:.1f}ms) — {anchor[:50]}...")

    # Performance test on large files (spec requirement)
    print("\n--- Large file performance ---")
    for size in [100, 1000, 5000]:
        large_content = generate_large_file(size)
        anchor = f"function func_0(x: number): number {{\n    return x + 0;\n}}"
        t0 = time.perf_counter_ns()
        validate_anchor(large_content, anchor, "typescript")
        elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000
        timings.append(elapsed_ms)
        print(f"  {size} lines: {elapsed_ms:.1f}ms")

    match_rate = matches / total * 100 if total else 0
    tp_rate = structural_correct / structural_total * 100 if structural_total else 0
    tn_rate = non_structural_correct / non_structural_total * 100 if non_structural_total else 0
    avg_ms = sum(timings) / len(timings) if timings else 0
    max_ms = max(timings) if timings else 0

    print(f"\n--- Results ---")
    print(f"True positive rate (structural detected): {structural_correct}/{structural_total} ({tp_rate:.0f}%)")
    print(f"True negative rate (non-structural detected): {non_structural_correct}/{non_structural_total} ({tn_rate:.0f}%)")
    print(f"Overall match rate: {matches}/{total} ({match_rate:.0f}%)")
    print(f"Average time: {avg_ms:.1f}ms")
    print(f"Max time: {max_ms:.1f}ms")
    print(f"\nGo/no-go: {'GO' if tp_rate >= 40 and max_ms < 10 else 'NEEDS INVESTIGATION'}")
    print(f"  True positive rate >= 40%: {'YES' if tp_rate >= 40 else 'NO'}")
    print(f"  Max time < 10ms: {'YES' if max_ms < 10 else 'NO'}")


if __name__ == "__main__":
    run_spike()
```

- [ ] **Step 3: Run the spike**

Run: `python spike/validate_anchor_spike.py`

Expected output:
- Structural anchors → mostly MATCH
- Non-structural anchors → mostly NO MATCH
- Match rate: ≥40% overall (structural ones match, non-structural don't)
- All timings < 10ms

**Go/no-go decision:**
- If GO: proceed to Task 3
- If NEEDS INVESTIGATION: review the results, adjust the algorithm, re-run. If still failing after 1 hour, simplify Phase 1a to use ast-grep only for codebase search (not anchor validation)

- [ ] **Step 4: Commit**

```bash
git add spike/validate_anchor_spike.py
git commit -m "spike: Phase 0 validate_anchor feasibility test"
```

---

## Task 3: AgentState Type Migration

**Files:**
- Modify: `agent/state.py`
- Modify: `tests/test_state.py`

- [ ] **Step 1: Write test for new state fields**

Add to `tests/test_state.py`:

```python
def test_state_has_ast_available_field():
    """AgentState should accept ast_available dict."""
    state = {
        "messages": [],
        "instruction": "",
        "working_directory": "",
        "context": {},
        "plan": [],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
        "model_usage": {},
        "autonomy_mode": "autonomous",
        "ast_available": {"typescript": True, "python": True},
        "invalidated_files": [],
    }
    assert state["ast_available"]["typescript"] is True
    assert state["invalidated_files"] == []


def test_plan_accepts_dict_steps():
    """AgentState.plan should accept both str and dict entries."""
    state = {
        "messages": [],
        "instruction": "",
        "working_directory": "",
        "context": {},
        "plan": [
            "legacy string step",
            {"id": "step-1", "kind": "edit", "target_files": ["a.py"], "complexity": "simple", "depends_on": []},
        ],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
        "model_usage": {},
        "autonomy_mode": "autonomous",
        "ast_available": {},
        "invalidated_files": [],
    }
    assert isinstance(state["plan"][0], str)
    assert isinstance(state["plan"][1], dict)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_state.py -v -k "ast_available or dict_steps"`
Expected: FAIL — `ast_available` and `invalidated_files` are not in `AgentState`.

- [ ] **Step 3: Update AgentState**

Modify `agent/state.py`:

```python
from typing import Annotated, Any, Optional, TypedDict, Union
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    instruction: str
    working_directory: str
    context: dict
    plan: list[Union[str, dict]]
    current_step: int
    file_buffer: dict[str, str]
    edit_history: list[dict]
    error_state: Optional[str]
    # Multi-agent coordination fields
    is_parallel: bool
    parallel_batches: list[list[int]]
    sequential_first: list[int]
    has_conflicts: bool
    model_usage: dict[str, int]
    autonomy_mode: str  # "supervised" | "autonomous"
    # ast-grep integration fields
    ast_available: dict[str, bool]
    invalidated_files: list[str]
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_state.py -v`
Expected: All PASS.

- [ ] **Step 5: Run full test suite for regressions**

Run: `pytest tests/ -v --timeout=30`
Expected: All existing tests pass. The new fields have no default so confirm LangGraph handles missing keys gracefully, or add defaults to `execute()` in `server/main.py`.

- [ ] **Step 6: Update initial_state in server/main.py (mandatory)**

Add the new fields to the `initial_state` dict in `server/main.py` `execute()` function (around line 170). LangGraph requires all TypedDict fields to be present:

```python
"ast_available": {},
"invalidated_files": [],
```

Also add to `_resume_run()` state reset (around line 125):
```python
state["invalidated_files"] = []
```

- [ ] **Step 7: Commit**

```bash
git add agent/state.py tests/test_state.py server/main.py
git commit -m "feat: add ast_available and invalidated_files to AgentState"
```

---

## Task 4: ast_ops.py — validate_anchor and structural_replace

**Files:**
- Create: `agent/tools/ast_ops.py`
- Create: `tests/test_ast_ops.py`

### Step Group A: validate_anchor

- [ ] **Step 1: Write failing tests for validate_anchor**

Create `tests/test_ast_ops.py`:

```python
"""Tests for agent/tools/ast_ops.py — ast-grep structural operations."""
import pytest


# --- validate_anchor tests ---

class TestValidateAnchor:
    """Test structural anchor validation against AST boundaries."""

    def test_structural_match_single_statement(self):
        from agent.tools.ast_ops import validate_anchor
        content = "const x = 1;\nconst y = 2;\n"
        result = validate_anchor(content, "const x = 1;", "typescript")
        assert result.structural_match is True

    def test_structural_match_function_body(self):
        from agent.tools.ast_ops import validate_anchor
        content = "function foo() {\n  return 1;\n}\n"
        result = validate_anchor(content, "function foo() {\n  return 1;\n}", "typescript")
        assert result.structural_match is True

    def test_non_structural_cross_boundary(self):
        from agent.tools.ast_ops import validate_anchor
        content = "const x = 1;\n\nfunction foo() {\n  return 1;\n}\n"
        # Anchor crosses statement + function boundary
        anchor = "const x = 1;\n\nfunction foo() {"
        result = validate_anchor(content, anchor, "typescript")
        assert result.structural_match is False
        assert result.node_type is not None

    def test_anchor_not_found(self):
        from agent.tools.ast_ops import validate_anchor
        content = "const x = 1;\n"
        result = validate_anchor(content, "DOES NOT EXIST", "typescript")
        assert result.structural_match is False

    def test_unsupported_language(self):
        from agent.tools.ast_ops import validate_anchor
        content = "some content"
        result = validate_anchor(content, "some content", "nonexistent_language_xyz")
        assert result.unsupported_language is True

    def test_python_method(self):
        from agent.tools.ast_ops import validate_anchor
        content = "class Foo:\n    def bar(self):\n        return 1\n"
        result = validate_anchor(content, "def bar(self):\n        return 1", "python")
        assert result.structural_match is True

    def test_anchor_inside_string_literal(self):
        from agent.tools.ast_ops import validate_anchor
        content = 'const msg = "function foo() { return 1; }";\n'
        result = validate_anchor(content, "function foo() { return 1; }", "typescript")
        # Anchor is inside a string literal — should not crash
        assert result is not None

    def test_anchor_inside_comment(self):
        from agent.tools.ast_ops import validate_anchor
        content = "// const x = 1;\nconst y = 2;\n"
        result = validate_anchor(content, "const x = 1;", "typescript")
        # Anchor text exists inside a comment — should not crash
        assert result is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ast_ops.py::TestValidateAnchor -v`
Expected: FAIL — `agent.tools.ast_ops` does not exist.

- [ ] **Step 3: Implement validate_anchor**

Create `agent/tools/ast_ops.py`:

```python
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
    """Get current run statistics."""
    return _stats


def reset_stats() -> None:
    """Reset statistics for a new run."""
    global _stats
    _stats = MatchStats()


# --- Parse tree cache ---

_parse_cache: dict[tuple[str, str], Any] = {}
_cache_max_size: int = 64


def _content_hash(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()


def _get_cached_root(content: str, language: str):
    """Get or create a parsed SgRoot, using LRU cache."""
    key = (language, _content_hash(content))
    if key in _parse_cache:
        _stats.cache_hits += 1
        return _parse_cache[key]
    _stats.cache_misses += 1
    root = SgRoot(content, language)
    # Evict oldest if over capacity
    if len(_parse_cache) >= _cache_max_size:
        oldest_key = next(iter(_parse_cache))
        del _parse_cache[oldest_key]
    _parse_cache[key] = root
    return root


def clear_cache() -> None:
    """Clear the parse tree cache."""
    _parse_cache.clear()


def set_cache_size(size: int) -> None:
    """Set maximum cache size."""
    global _cache_max_size
    _cache_max_size = size


# --- validate_anchor ---

def validate_anchor(content: str, anchor: str, language: str) -> AnchorResult:
    """Check if anchor aligns with AST node boundaries.

    Note: Spec defines signature as (file_path, content, anchor). This implementation
    uses (content, anchor, language) instead — the caller already knows the language
    from file extension, and file_path is not needed for AST parsing. The spec will
    be updated to match.

    Args:
        content: Full file content.
        anchor: The anchor substring to validate.
        language: Tree-sitter language name (e.g., "typescript", "python").

    Returns:
        AnchorResult with structural_match, unsupported_language, and node_type.
    """
    if not AST_GREP_AVAILABLE:
        _stats.unsupported_language_skips += 1
        return AnchorResult(structural_match=False, unsupported_language=True)

    try:
        root = _get_cached_root(content, language)
    except Exception:
        _stats.unsupported_language_skips += 1
        return AnchorResult(structural_match=False, unsupported_language=True)

    # Find anchor position
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
    """Recursively check if any node or contiguous siblings exactly cover [start, end)."""
    node_start = node.range().start.index
    node_end = node.range().end.index

    # Exact match on this node
    if node_start == start and node_end == end:
        return AnchorResult(structural_match=True, node_type=node.kind())

    children = list(node.children())
    if not children:
        return AnchorResult(structural_match=False, node_type=node.kind())

    # Check contiguous sibling sequences
    for i in range(len(children)):
        cs = children[i].range().start.index
        if cs > start:
            break
        if cs == start:
            # Try contiguous sequences starting from child i
            for j in range(i, len(children)):
                ce = children[j].range().end.index
                if ce == end:
                    return AnchorResult(structural_match=True, node_type=node.kind())
                if ce > end:
                    break

    # Recurse into the child that contains the anchor span
    for child in children:
        cs = child.range().start.index
        ce = child.range().end.index
        if cs <= start and ce >= end:
            result = _check_node_boundaries(child, start, end)
            if result.structural_match:
                return result
            return AnchorResult(structural_match=False, node_type=child.kind())

    return AnchorResult(structural_match=False, node_type=node.kind())
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_ast_ops.py::TestValidateAnchor -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/tools/ast_ops.py tests/test_ast_ops.py
git commit -m "feat: add validate_anchor with AST boundary detection"
```

### Step Group B: structural_replace

- [ ] **Step 6: Write failing tests for structural_replace**

Add to `tests/test_ast_ops.py`:

```python
class TestStructuralReplace:
    """Test indentation-aware structural replacement."""

    def test_single_line_replacement(self):
        from agent.tools.ast_ops import structural_replace
        content = "const x = 1;\nconst y = 2;\n"
        result = structural_replace(content, "const x = 1;", "const x = 42;", "typescript")
        assert "const x = 42;" in result
        assert "const y = 2;" in result

    def test_preserves_indentation_nested(self):
        from agent.tools.ast_ops import structural_replace
        content = "class Foo {\n    bar() {\n        return 1;\n    }\n}\n"
        result = structural_replace(
            content,
            "return 1;",
            "return 42;",
            "typescript",
        )
        assert "        return 42;" in result  # preserves 8-space indent

    def test_multiline_replacement_preserves_relative_indent(self):
        from agent.tools.ast_ops import structural_replace
        content = "function foo() {\n    const x = 1;\n}\n"
        result = structural_replace(
            content,
            "const x = 1;",
            "const x = 1;\n    const y = 2;",
            "typescript",
        )
        assert "    const x = 1;" in result
        assert "    const y = 2;" in result

    def test_fallback_when_not_structural(self):
        """Non-structural anchors should still work via text replacement."""
        from agent.tools.ast_ops import structural_replace
        content = "a = 1\n\ndef foo():\n    pass\n"
        # Crosses boundary — structural_replace should still work (falls back to text)
        anchor = "a = 1\n\ndef foo():"
        result = structural_replace(content, anchor, "a = 2\n\ndef foo():", "python")
        assert "a = 2" in result

    def test_empty_replacement_deletion(self):
        from agent.tools.ast_ops import structural_replace
        content = "const x = 1;\nconst y = 2;\nconst z = 3;\n"
        result = structural_replace(content, "const y = 2;\n", "", "typescript")
        assert "const y" not in result
        assert "const x = 1;" in result
        assert "const z = 3;" in result

    def test_multiline_at_top_level_zero_indent(self):
        from agent.tools.ast_ops import structural_replace
        content = "const a = 1;\nconst b = 2;\n"
        result = structural_replace(content, "const a = 1;", "const a = 1;\nconst c = 3;", "typescript")
        assert "const a = 1;" in result
        assert "const c = 3;" in result

    def test_deeply_nested_3_plus_levels(self):
        from agent.tools.ast_ops import structural_replace
        content = (
            "class Outer {\n"
            "    class Inner {\n"
            "        method() {\n"
            "            return 1;\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        result = structural_replace(content, "return 1;", "return 42;", "typescript")
        assert "            return 42;" in result

    def test_python_method_inside_class(self):
        from agent.tools.ast_ops import structural_replace
        content = (
            "class Foo:\n"
            "    def bar(self):\n"
            "        x = 1\n"
            "        return x\n"
        )
        result = structural_replace(
            content,
            "x = 1\n        return x",
            "x = 42\n        return x",
            "python",
        )
        assert "        x = 42" in result

    def test_replacement_adds_indent_levels(self):
        from agent.tools.ast_ops import structural_replace
        content = "function foo() {\n    doThing();\n}\n"
        result = structural_replace(
            content,
            "doThing();",
            "if (cond) {\n    doThing();\n}",
            "typescript",
        )
        assert "    if (cond) {" in result

    def test_returns_full_content(self):
        """structural_replace returns the full file content, not just the replacement."""
        from agent.tools.ast_ops import structural_replace
        content = "line1\nline2\nline3\n"
        result = structural_replace(content, "line2", "LINE2", "typescript")
        assert result == "line1\nLINE2\nline3\n"
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `pytest tests/test_ast_ops.py::TestStructuralReplace -v`
Expected: FAIL — `structural_replace` not defined.

- [ ] **Step 8: Implement structural_replace**

Add to `agent/tools/ast_ops.py`:

```python
def structural_replace(content: str, anchor: str, replacement: str, language: str) -> str:
    """Perform indentation-aware replacement using AST context.

    Pure function — returns the new file content without writing to disk.

    If the anchor aligns with AST boundaries, uses ast-grep's tree-sitter
    context to preserve indentation. Otherwise, falls back to str.replace().

    Args:
        content: Full file content.
        anchor: The text to replace (must appear exactly once).
        replacement: The replacement text.
        language: Tree-sitter language name.

    Returns:
        New file content with the replacement applied.
    """
    if not AST_GREP_AVAILABLE:
        return content.replace(anchor, replacement, 1)

    # Check if anchor is structural
    result = validate_anchor(content, anchor, language)

    if not result.structural_match or result.unsupported_language:
        # Fall back to plain text replacement
        return content.replace(anchor, replacement, 1)

    # Structural match — apply with indentation awareness
    return _apply_with_indentation(content, anchor, replacement)


def _apply_with_indentation(content: str, anchor: str, replacement: str) -> str:
    """Apply replacement preserving the original anchor's indentation context."""
    start = content.find(anchor)
    if start == -1:
        return content.replace(anchor, replacement, 1)

    # Detect the indentation of the anchor's first line
    line_start = content.rfind("\n", 0, start)
    if line_start == -1:
        # Anchor starts on the first line
        original_indent = ""
    else:
        # Characters between newline and anchor start
        between = content[line_start + 1:start]
        original_indent = between if between.isspace() else ""

    if not replacement or "\n" not in replacement:
        # Single-line or empty replacement — no indentation adjustment needed
        return content[:start] + replacement + content[start + len(anchor):]

    # Multi-line replacement: detect replacement's base indentation
    rep_lines = replacement.split("\n")
    if len(rep_lines) <= 1:
        return content[:start] + replacement + content[start + len(anchor):]

    # First line keeps the original indent (it's positioned by context)
    # Subsequent lines: detect their common indent and adjust to match original
    subsequent = rep_lines[1:]
    if subsequent:
        # Find minimum indent of non-empty subsequent lines
        non_empty = [l for l in subsequent if l.strip()]
        if non_empty:
            min_indent = min(len(l) - len(l.lstrip()) for l in non_empty)
        else:
            min_indent = 0

        # Re-indent subsequent lines relative to original indent
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
```

- [ ] **Step 9: Run tests**

Run: `pytest tests/test_ast_ops.py::TestStructuralReplace -v`
Expected: All PASS.

- [ ] **Step 10: Commit**

```bash
git add agent/tools/ast_ops.py tests/test_ast_ops.py
git commit -m "feat: add structural_replace with indentation preservation"
```

---

## Task 5: detect_languages and Cache Invalidation

**Files:**
- Modify: `agent/tools/ast_ops.py`
- Add tests to: `tests/test_ast_ops.py`

- [ ] **Step 1: Write failing tests for detect_languages**

Add to `tests/test_ast_ops.py`:

```python
import os
import subprocess

class TestDetectLanguages:
    """Test language detection from working directory."""

    def test_detects_typescript_files(self, tmp_path):
        from agent.tools.ast_ops import detect_languages
        (tmp_path / "app.ts").write_text("const x = 1;")
        (tmp_path / "comp.tsx").write_text("<div/>")
        # Initialize git repo so git ls-files works
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        result = detect_languages(str(tmp_path))
        assert result.get("typescript") is True

    def test_detects_python_files(self, tmp_path):
        from agent.tools.ast_ops import detect_languages
        (tmp_path / "main.py").write_text("x = 1")
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        result = detect_languages(str(tmp_path))
        assert result.get("python") is True

    def test_unsupported_language_returns_false(self, tmp_path):
        from agent.tools.ast_ops import detect_languages
        (tmp_path / "data.csv").write_text("a,b,c")
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        result = detect_languages(str(tmp_path))
        # CSV has no tree-sitter grammar
        assert "csv" not in result or result.get("csv") is False

    def test_non_git_directory_fallback(self, tmp_path):
        from agent.tools.ast_ops import detect_languages
        (tmp_path / "main.py").write_text("x = 1")
        # No git init — should fall back to os.walk
        result = detect_languages(str(tmp_path))
        assert result.get("python") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ast_ops.py::TestDetectLanguages -v`
Expected: FAIL — `detect_languages` not defined.

- [ ] **Step 3: Implement detect_languages**

Add to `agent/tools/ast_ops.py`:

```python
import os
import subprocess as _subprocess

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
    """Detect languages in a working directory and check ast-grep grammar support.

    Uses `git ls-files` when in a git repo (fast, respects .gitignore).
    Falls back to os.walk with standard exclusions.

    Returns: dict mapping language name → bool (True if ast-grep grammar available).
    """
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
    """Collect unique file extensions from the directory."""
    # Try git ls-files first
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

    # Fallback: os.walk with exclusions
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
    """Check if ast-grep-py has a grammar for this language."""
    if not AST_GREP_AVAILABLE:
        return False
    try:
        SgRoot("x", language)
        return True
    except Exception:
        return False
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_ast_ops.py::TestDetectLanguages -v`
Expected: All PASS.

- [ ] **Step 5: Write test for cache clearing**

Add to `tests/test_ast_ops.py`:

```python
class TestCacheOperations:
    def test_clear_cache(self):
        from agent.tools.ast_ops import validate_anchor, clear_cache, get_stats, reset_stats
        reset_stats()
        # First call — cache miss
        validate_anchor("const x = 1;", "const x = 1;", "typescript")
        assert get_stats().cache_misses == 1
        # Second call same content — cache hit
        validate_anchor("const x = 1;", "const x = 1;", "typescript")
        assert get_stats().cache_hits == 1
        # Clear and call again — cache miss
        clear_cache()
        validate_anchor("const x = 1;", "const x = 1;", "typescript")
        assert get_stats().cache_misses == 2

    def test_stats_reset(self):
        from agent.tools.ast_ops import get_stats, reset_stats
        reset_stats()
        stats = get_stats()
        assert stats.structural_matches == 0
        assert stats.fallbacks_to_text == 0
```

- [ ] **Step 6: Run cache tests**

Run: `pytest tests/test_ast_ops.py::TestCacheOperations -v`
Expected: All PASS (cache logic already implemented in Task 4).

- [ ] **Step 7: Commit**

```bash
git add agent/tools/ast_ops.py tests/test_ast_ops.py
git commit -m "feat: add detect_languages and parse tree cache"
```

---

## Task 6: Integrate detect_languages into receive_node

**Files:**
- Modify: `agent/nodes/receive.py`
- Modify: `tests/test_integration.py` (or create a focused test)

- [ ] **Step 1: Write test for receive_node populating ast_available**

Add to a new section in `tests/test_ast_ops.py`:

```python
class TestReceiveNodeIntegration:
    def test_receive_node_populates_ast_available(self, tmp_path):
        from agent.nodes.receive import receive_instruction_node
        (tmp_path / "app.ts").write_text("const x = 1;")
        # Init git repo
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)

        state = {
            "instruction": "edit app.ts",
            "working_directory": str(tmp_path),
            "context": {},
            "ast_available": {},
        }
        result = receive_instruction_node(state)
        assert "ast_available" in result
        assert result["ast_available"].get("typescript") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ast_ops.py::TestReceiveNodeIntegration -v`
Expected: FAIL — receive_node doesn't return `ast_available`.

- [ ] **Step 3: Update receive_node**

Modify `agent/nodes/receive.py`:

```python
from agent.tracing import TraceLogger

tracer = TraceLogger()


def receive_instruction_node(state: dict) -> dict:
    tracer.log("receive_instruction", {
        "instruction": state.get("instruction", ""),
        "has_context": bool(state.get("context")),
    })

    result = {"current_step": 0, "error_state": None, "model_usage": {}}

    # Detect languages for ast-grep support
    working_dir = state.get("working_directory", "")
    if working_dir:
        try:
            from agent.tools.ast_ops import detect_languages, reset_stats, clear_cache
            reset_stats()
            clear_cache()
            result["ast_available"] = detect_languages(working_dir)
            tracer.log("language_detection", {"ast_available": result["ast_available"]})
        except Exception as e:
            tracer.log("language_detection", {"error": str(e)})
            result["ast_available"] = {}

    return result
```

- [ ] **Step 4: Run test**

Run: `pytest tests/test_ast_ops.py::TestReceiveNodeIntegration -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/nodes/receive.py tests/test_ast_ops.py
git commit -m "feat: detect languages at run start in receive_node"
```

---

## Task 7: Integrate ast-grep into editor_node

**Files:**
- Modify: `agent/nodes/editor.py`
- Modify: `tests/test_editor_node.py`

This is the core integration — adding the transparent ast-grep layer to the editor flow.

- [ ] **Step 1: Read existing editor tests**

Run: Read `tests/test_editor_node.py` to understand the test patterns used.

- [ ] **Step 2: Write test for ast-grep enhanced editor flow**

Add to `tests/test_editor_node.py`:

```python
@pytest.mark.asyncio
async def test_editor_uses_structural_replace_when_available(tmp_path):
    """Editor should use structural_replace for structurally valid anchors."""
    test_file = tmp_path / "app.ts"
    test_file.write_text("function foo() {\n    return 1;\n}\n")

    # Mock router to return anchor/replacement JSON
    mock_router = AsyncMock()
    mock_router.call.return_value = json.dumps({
        "anchor": "return 1;",
        "replacement": "return 42;",
    })

    state = {
        "file_buffer": {str(test_file): test_file.read_text()},
        "plan": [{"id": "step-1", "kind": "edit", "target_files": [str(test_file)], "complexity": "simple", "depends_on": []}],
        "current_step": 0,
        "edit_history": [],
        "context": {},
        "ast_available": {"typescript": True},
    }
    config = {"configurable": {"router": mock_router}}

    result = await editor_node(state, config)
    assert result["error_state"] is None
    # File should have been updated
    updated = result["file_buffer"][str(test_file)]
    assert "return 42;" in updated
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_editor_node.py::test_editor_uses_structural_replace_when_available -v`
Expected: FAIL — editor_node doesn't use ast_ops.

- [ ] **Step 4: Update editor_node**

Modify `agent/nodes/editor.py` to add the ast-grep layer. The key changes:

1. File selection from step `target_files` when available
2. `validate_anchor` + `structural_replace` before the existing flow
3. Fall through to `str.replace()` on any failure

```python
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
                # Use step's target file if it's in the buffer
                for tf in target_files:
                    if tf in file_buffer:
                        return tf
    # Fallback: first file in buffer
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
        # Use ast-grep content if available, otherwise use anchor/replacement pair.
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

    # Legacy path (no approval_manager): apply edit directly
    if new_content is not None:
        # ast-grep produced the result — write it directly
        snapshot = content
        import os
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
```

- [ ] **Step 5: Run the new test**

Run: `pytest tests/test_editor_node.py::test_editor_uses_structural_replace_when_available -v`
Expected: PASS.

- [ ] **Step 6: Run all editor tests for regressions**

Run: `pytest tests/test_editor_node.py -v`
Expected: All PASS. Existing tests should still work because:
- `ast_available` defaults to `{}` → ast-grep path is skipped
- File selection falls back to first buffer key
- Legacy `str.replace` path is unchanged

- [ ] **Step 7: Commit**

```bash
git add agent/nodes/editor.py tests/test_editor_node.py
git commit -m "feat: integrate ast-grep validate/replace into editor flow"
```

---

## Task 8: Buffer Invalidation After Executor Steps

**Files:**
- Modify: `agent/nodes/executor.py`
- Modify: `tests/test_ast_ops.py`

- [ ] **Step 1: Write test for executor invalidation**

Add to `tests/test_ast_ops.py`:

```python
class TestExecutorInvalidation:
    def test_executor_sets_invalidated_files(self):
        from agent.nodes.executor import executor_node
        state = {
            "plan": ["Run: echo hello"],
            "current_step": 0,
            "working_directory": "/tmp",
        }
        result = executor_node(state)
        assert result.get("invalidated_files") == ["*"]

    def test_executor_does_not_invalidate_on_failure(self):
        from agent.nodes.executor import executor_node
        state = {
            "plan": ["Run: false"],  # exits with code 1
            "current_step": 0,
            "working_directory": "/tmp",
        }
        result = executor_node(state)
        # On failure: error_state is set, invalidated_files is NOT set
        assert result.get("error_state") is not None
        assert "invalidated_files" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ast_ops.py::TestExecutorInvalidation -v`
Expected: FAIL — executor doesn't set `invalidated_files`.

- [ ] **Step 3: Update executor_node**

Modify `agent/nodes/executor.py`:

```python
from agent.tools.shell import run_command
from agent.tracing import TraceLogger

tracer = TraceLogger()

def executor_node(state: dict) -> dict:
    plan = state.get("plan", [])
    step = state.get("current_step", 0)
    working_dir = state["working_directory"]

    if step >= len(plan):
        return {"error_state": None}

    step_text = plan[step]
    if isinstance(step_text, dict):
        command = step_text.get("command", "")
    else:
        command = step_text
        for prefix in ["Run:", "run:", "Execute:", "execute:"]:
            if prefix in step_text:
                command = step_text.split(prefix, 1)[1].strip()
                break

    result = run_command(command, cwd=working_dir)
    tracer.log("executor", {
        "command": command,
        "exit_code": result["exit_code"],
        "stdout_preview": result["stdout"][:200],
        "stderr_preview": result["stderr"][:200],
    })

    if result["exit_code"] != 0:
        return {"error_state": f"Command failed (exit {result['exit_code']}): {result['stderr'][:500]}"}

    # Invalidate all cached state — exec may have modified files on disk
    return {"error_state": None, "invalidated_files": ["*"]}
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_ast_ops.py::TestExecutorInvalidation -v`
Expected: All PASS.

- [ ] **Step 5: Run existing executor tests for regressions**

Run: `pytest tests/ -v -k "executor or shell" --timeout=30`
Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/nodes/executor.py tests/test_ast_ops.py
git commit -m "feat: invalidate file_buffer and cache after executor steps"
```

---

## Task 9: Full Integration Test

**Files:**
- Add to: `tests/test_ast_ops.py`

- [ ] **Step 1: Write end-to-end integration test**

Add to `tests/test_ast_ops.py`:

```python
class TestEndToEndIntegration:
    """Integration tests for the full ast-grep enhanced edit flow."""

    def test_full_flow_structural_edit(self, tmp_path):
        """Simulate: detect_languages → validate_anchor → structural_replace."""
        from agent.tools.ast_ops import detect_languages, validate_anchor, structural_replace, reset_stats, get_stats

        # Create a TypeScript project
        (tmp_path / "index.ts").write_text(
            "function greet(name: string) {\n"
            "    console.log(`Hello ${name}`);\n"
            "    return name;\n"
            "}\n"
        )
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)

        reset_stats()

        # Step 1: detect languages
        langs = detect_languages(str(tmp_path))
        assert langs.get("typescript") is True

        # Step 2: validate anchor
        content = (tmp_path / "index.ts").read_text()
        anchor = "console.log(`Hello ${name}`);"
        result = validate_anchor(content, anchor, "typescript")
        assert result.structural_match is True

        # Step 3: structural replace
        new_content = structural_replace(
            content, anchor, 'console.log(`Hi ${name}!`);', "typescript"
        )
        assert 'console.log(`Hi ${name}!`);' in new_content
        assert "return name;" in new_content  # rest preserved

        # Step 4: check stats
        stats = get_stats()
        assert stats.structural_matches >= 1

    def test_full_flow_fallback_to_text(self, tmp_path):
        """When anchor is non-structural, falls back to str.replace."""
        from agent.tools.ast_ops import detect_languages, validate_anchor, structural_replace, reset_stats, get_stats

        (tmp_path / "app.ts").write_text("const a = 1;\n\nconst b = 2;\n")
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)

        reset_stats()
        content = (tmp_path / "app.ts").read_text()
        # Cross-boundary anchor
        anchor = "const a = 1;\n\nconst b"
        result = validate_anchor(content, anchor, "typescript")
        assert result.structural_match is False

        # structural_replace still works (falls back to text)
        new_content = structural_replace(content, anchor, "const a = 42;\n\nconst b", "typescript")
        assert "const a = 42;" in new_content

        stats = get_stats()
        assert stats.fallbacks_to_text >= 1
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/test_ast_ops.py::TestEndToEndIntegration -v`
Expected: All PASS.

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v --timeout=60`
Expected: All PASS — no regressions across the entire codebase.

- [ ] **Step 4: Commit**

```bash
git add tests/test_ast_ops.py
git commit -m "test: add end-to-end integration tests for ast-grep edit flow"
```

---

## Task 10: Observability — Log Stats at Run End

**Files:**
- Modify: `agent/nodes/reporter.py`

- [ ] **Step 1: Update reporter to log ast-grep stats**

Modify `agent/nodes/reporter.py`:

```python
from agent.tracing import TraceLogger

tracer = TraceLogger()

def reporter_node(state: dict) -> dict:
    edit_history = state.get("edit_history", [])
    error_state = state.get("error_state")
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)

    if error_state is None:
        status = "completed"
    elif current_step < len(plan):
        status = "waiting_for_human"
    else:
        status = "failed"

    summary = {
        "steps_completed": current_step,
        "total_steps": len(plan),
        "edits_made": len(edit_history),
        "files_edited": list(set(e["file"] for e in edit_history if "file" in e)),
        "error": error_state,
        "status": status,
        "model_usage": state.get("model_usage", {}),
    }

    # Log ast-grep statistics if available
    try:
        from agent.tools.ast_ops import get_stats
        stats = get_stats()
        summary["ast_grep"] = {
            "structural_matches": stats.structural_matches,
            "fallbacks_to_text": stats.fallbacks_to_text,
            "unsupported_language_skips": stats.unsupported_language_skips,
            "cache_hits": stats.cache_hits,
            "cache_misses": stats.cache_misses,
        }
    except ImportError:
        pass

    tracer.log("reporter", summary)
    tracer.save()

    return {"error_state": error_state}
```

- [ ] **Step 2: Run reporter tests**

Run: `pytest tests/ -v -k "reporter" --timeout=30`
Expected: All PASS (reporter change is additive — try/except handles ImportError).

- [ ] **Step 3: Commit**

```bash
git add agent/nodes/reporter.py
git commit -m "feat: log ast-grep match statistics at run end"
```

---

## Task 11: Clean Up and Final Verification

- [ ] **Step 1: Run the complete test suite**

Run: `pytest tests/ -v --timeout=60`
Expected: All tests pass, no regressions.

- [ ] **Step 2: Verify the spike script still works**

Run: `python spike/validate_anchor_spike.py`
Expected: GO result.

- [ ] **Step 3: Verify import chain works**

Run:
```bash
python -c "
from agent.tools.ast_ops import validate_anchor, structural_replace, detect_languages, get_stats
from agent.nodes.editor import editor_node
from agent.nodes.receive import receive_instruction_node
from agent.nodes.executor import executor_node
from agent.nodes.reporter import reporter_node
print('All imports successful')
"
```
Expected: "All imports successful"

- [ ] **Step 4: Final commit if any cleanup needed**

```bash
git status
# If clean, skip. If changes, commit:
git add -A
git commit -m "chore: Phase 1 cleanup"
```
