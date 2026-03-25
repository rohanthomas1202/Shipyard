"""Tests for agent/nodes/refactor.py — codebase-wide refactoring."""
import os
import pytest
import subprocess


@pytest.fixture
def refactor_state(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.ts").write_text("const x = oldFunc(1);\nexport default x;\n")
    (tmp_path / "src" / "b.ts").write_text("const y = oldFunc(2);\nconst z = oldFunc(3);\n")
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)

    return {
        "plan": [{
            "id": "refactor-1",
            "kind": "refactor",
            "pattern": "oldFunc($ARG)",
            "refactor_replacement": "newFunc($ARG)",
            "language": "typescript",
            "scope": str(tmp_path / "src"),
            "complexity": "complex",
        }],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
        "working_directory": str(tmp_path),
        "ast_available": {"typescript": True},
    }


@pytest.mark.asyncio
async def test_refactor_node_autonomous_applies(refactor_state, tmp_path):
    from agent.nodes.refactor import refactor_node
    config = {"configurable": {}}
    result = await refactor_node(refactor_state, config)

    assert result["error_state"] is None
    assert "newFunc(1)" in (tmp_path / "src" / "a.ts").read_text()
    assert "newFunc(2)" in (tmp_path / "src" / "b.ts").read_text()
    assert len(result["edit_history"]) >= 2
    batch_ids = {e.get("batch_id") for e in result["edit_history"]}
    assert len(batch_ids) == 1
    assert None not in batch_ids


@pytest.mark.asyncio
async def test_refactor_node_no_matches(tmp_path):
    from agent.nodes.refactor import refactor_node
    (tmp_path / "a.ts").write_text("const x = 1;\n")
    state = {
        "plan": [{
            "id": "refactor-1",
            "kind": "refactor",
            "pattern": "nonExistent($ARG)",
            "refactor_replacement": "replacement($ARG)",
            "language": "typescript",
            "scope": str(tmp_path),
            "complexity": "complex",
        }],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
        "working_directory": str(tmp_path),
        "ast_available": {"typescript": True},
    }
    config = {"configurable": {}}
    result = await refactor_node(state, config)
    assert result["error_state"] is None


@pytest.mark.asyncio
async def test_refactor_node_updates_file_buffer(refactor_state, tmp_path):
    from agent.nodes.refactor import refactor_node
    config = {"configurable": {}}
    result = await refactor_node(refactor_state, config)
    file_buffer = result.get("file_buffer", {})
    assert len(file_buffer) >= 2
    for path, content in file_buffer.items():
        assert "newFunc" in content


@pytest.mark.asyncio
async def test_refactor_rollback_on_apply_failure(tmp_path):
    from agent.nodes.refactor import refactor_node
    (tmp_path / "a.ts").write_text("const x = oldFunc(1);\n")
    (tmp_path / "b.ts").write_text("const y = oldFunc(2);\n")
    os.chmod(str(tmp_path / "b.ts"), 0o444)

    state = {
        "plan": [{
            "id": "refactor-1",
            "kind": "refactor",
            "pattern": "oldFunc($ARG)",
            "refactor_replacement": "newFunc($ARG)",
            "language": "typescript",
            "scope": str(tmp_path),
            "complexity": "complex",
        }],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
        "working_directory": str(tmp_path),
        "ast_available": {"typescript": True},
    }
    config = {"configurable": {}}
    result = await refactor_node(state, config)

    # Should report an error
    assert result["error_state"] is not None
    # a.ts should be rolled back to original
    assert "oldFunc(1)" in (tmp_path / "a.ts").read_text()

    os.chmod(str(tmp_path / "b.ts"), 0o644)
