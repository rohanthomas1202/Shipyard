"""Tests for reader_node line-range reading and skeleton views."""
import os
import hashlib
import pytest

from agent.nodes.reader import _read_with_range, reader_node


# ---------------------------------------------------------------------------
# _read_with_range unit tests
# ---------------------------------------------------------------------------

def test_small_file_full_read(tmp_path):
    """Files at or under 200 lines are returned in full."""
    fpath = tmp_path / "small.py"
    lines = [f"line {i}\n" for i in range(1, 51)]
    fpath.write_text("".join(lines))

    result = _read_with_range(str(fpath))
    for i in range(1, 51):
        assert f"line {i}" in result
    assert "skeleton" not in result
    assert "omitted" not in result


def test_large_file_skeleton(tmp_path):
    """Files over 200 lines produce a skeleton view."""
    fpath = tmp_path / "big.py"
    lines = [f"line {i}\n" for i in range(1, 301)]
    fpath.write_text("".join(lines))

    result = _read_with_range(str(fpath))
    assert "[300 lines total -- skeleton view]" in result
    assert "omitted" in result
    # First line present
    assert "line 1" in result
    # Last line present
    assert "line 300" in result


def test_explicit_line_range(tmp_path):
    """Explicit start/end returns only that range with header."""
    fpath = tmp_path / "medium.py"
    lines = [f"line {i}\n" for i in range(1, 101)]
    fpath.write_text("".join(lines))

    result = _read_with_range(str(fpath), 20, 40)
    assert "[Lines 21-40 of 100]" in result
    # Line 21 content present (0-indexed start=20 -> 1-indexed line 21)
    assert "line 21" in result
    # Line 1 should NOT be present
    assert "line 1\n" not in result


# ---------------------------------------------------------------------------
# reader_node integration tests
# ---------------------------------------------------------------------------

def _make_state(tmp_path, file_contents, plan_entry=None):
    """Helper to build a minimal AgentState dict for reader_node."""
    files = []
    for name, content in file_contents.items():
        fpath = tmp_path / name
        fpath.write_text(content)
        files.append(str(fpath))

    plan = []
    if plan_entry is not None:
        plan.append(plan_entry)
    else:
        # Default: a string step mentioning the file paths
        plan.append(" ".join(files))

    return {
        "working_directory": str(tmp_path),
        "file_buffer": {},
        "plan": plan,
        "current_step": 0,
        "context": {},
    }


def test_reader_node_small_file(tmp_path):
    """reader_node loads files under 200 lines in full."""
    content = "".join(f"line {i}\n" for i in range(1, 51))
    state = _make_state(tmp_path, {"small.py": content})

    result = reader_node(state)
    fpath = str(tmp_path / "small.py")
    assert fpath in result["file_buffer"]
    assert "line 1" in result["file_buffer"][fpath]
    assert "skeleton" not in result["file_buffer"][fpath]


def test_reader_node_large_file_skeleton(tmp_path):
    """reader_node loads files over 200 lines as skeleton view."""
    content = "".join(f"line {i}\n" for i in range(1, 301))
    state = _make_state(tmp_path, {"big.py": content})

    result = reader_node(state)
    fpath = str(tmp_path / "big.py")
    assert fpath in result["file_buffer"]
    assert "skeleton view" in result["file_buffer"][fpath]
    assert "omitted" in result["file_buffer"][fpath]


def test_reader_node_line_range_from_step(tmp_path):
    """When PlanStep dict has line_range, reader_node uses that range."""
    content = "".join(f"line {i}\n" for i in range(1, 101))
    fpath = tmp_path / "ranged.py"
    fpath.write_text(content)

    plan_entry = {
        "text": str(fpath),
        "target_files": [str(fpath)],
        "line_range": [10, 30],
    }
    state = _make_state(tmp_path, {}, plan_entry=plan_entry)
    # Need to put the file path in context.files so it gets picked up
    state["context"] = {"files": [str(fpath)]}

    result = reader_node(state)
    buf = result["file_buffer"][str(fpath)]
    assert "[Lines 11-30 of 100]" in buf
    assert "line 11" in buf


def test_reader_node_returns_file_hashes(tmp_path):
    """reader_node returns file_hashes with content_hash values."""
    content = "hello world\n"
    state = _make_state(tmp_path, {"hashed.py": content})

    result = reader_node(state)
    assert "file_hashes" in result
    fpath = str(tmp_path / "hashed.py")
    assert fpath in result["file_hashes"]
    # Verify it's a hex hash string
    assert len(result["file_hashes"][fpath]) > 0
