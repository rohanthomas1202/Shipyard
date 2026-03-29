"""Tests for context pack assembly — scoped file selection for agent execution."""
import os
import tempfile
import pytest

from agent.orchestrator.context_packs import (
    ContextPack,
    ContextPackAssembler,
    MAX_CONTEXT_FILES,
    parse_python_imports,
)
from agent.orchestrator.models import TaskNode


# ---------------------------------------------------------------------------
# ContextPack dataclass tests
# ---------------------------------------------------------------------------

def test_context_pack_all_files_deduplicates():
    """Duplicate files across categories should appear only once."""
    pack = ContextPack(
        task_id="t1",
        primary_files=["a.py", "b.py"],
        dependency_files=["b.py", "c.py"],
        contracts=["a.py", "d.py"],
        recent_changes=[],
    )
    assert pack.all_files == ["a.py", "b.py", "c.py", "d.py"]


def test_context_pack_all_files_caps_at_max():
    """all_files must never return more than MAX_CONTEXT_FILES."""
    pack = ContextPack(
        task_id="t1",
        primary_files=["f1.py", "f2.py", "f3.py"],
        dependency_files=["f4.py", "f5.py", "f6.py"],
        contracts=["f7.py"],
        recent_changes=[],
    )
    assert len(pack.all_files) <= MAX_CONTEXT_FILES
    assert len(pack.all_files) == 5


def test_context_pack_priority_order():
    """Primary files come before deps, deps before contracts."""
    pack = ContextPack(
        task_id="t1",
        primary_files=["primary.py"],
        dependency_files=["dep.py"],
        contracts=["contract.py"],
        recent_changes=[],
    )
    result = pack.all_files
    assert result.index("primary.py") < result.index("dep.py")
    assert result.index("dep.py") < result.index("contract.py")


# ---------------------------------------------------------------------------
# ContextPackAssembler tests
# ---------------------------------------------------------------------------

def test_assemble_returns_primary_from_metadata():
    """assemble extracts primary_files from task.metadata['target_files']."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a dummy target file
        target = os.path.join(tmpdir, "models.py")
        with open(target, "w") as f:
            f.write("# empty\n")

        task = TaskNode(
            id="t1",
            dag_id="d1",
            label="build-models",
            metadata={"target_files": ["models.py"]},
        )
        assembler = ContextPackAssembler(tmpdir)
        pack = assembler.assemble(task)
        assert "models.py" in pack.primary_files


def test_assemble_adds_contract_files():
    """assemble includes contract_inputs in contracts field."""
    with tempfile.TemporaryDirectory() as tmpdir:
        task = TaskNode(
            id="t2",
            dag_id="d1",
            label="build-api",
            contract_inputs=["schema.sql", "openapi.yaml"],
            metadata={"target_files": []},
        )
        assembler = ContextPackAssembler(tmpdir)
        pack = assembler.assemble(task)
        assert pack.contracts == ["schema.sql", "openapi.yaml"]


def test_assemble_parses_imports_for_deps():
    """assemble parses Python imports from primary files to find deps."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create primary file with an import
        os.makedirs(os.path.join(tmpdir, "agent", "tools"), exist_ok=True)
        primary = os.path.join(tmpdir, "agent", "main.py")
        with open(primary, "w") as f:
            f.write("from agent.tools.shell import run_command_async\n")
        dep = os.path.join(tmpdir, "agent", "tools", "shell.py")
        with open(dep, "w") as f:
            f.write("# shell tools\n")

        task = TaskNode(
            id="t3",
            dag_id="d1",
            label="agent-main",
            metadata={"target_files": ["agent/main.py"]},
        )
        assembler = ContextPackAssembler(tmpdir)
        pack = assembler.assemble(task)
        assert "agent/tools/shell.py" in pack.dependency_files


def test_assemble_caps_total_at_max():
    """assemble caps total files at MAX_CONTEXT_FILES."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create 8 target files
        files = [f"file_{i}.py" for i in range(8)]
        for f in files:
            with open(os.path.join(tmpdir, f), "w") as fh:
                fh.write("# stub\n")

        task = TaskNode(
            id="t4",
            dag_id="d1",
            label="big-task",
            metadata={"target_files": files},
        )
        assembler = ContextPackAssembler(tmpdir)
        pack = assembler.assemble(task)
        assert len(pack.all_files) <= MAX_CONTEXT_FILES


def test_assemble_handles_missing_files():
    """assemble skips missing files gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        task = TaskNode(
            id="t5",
            dag_id="d1",
            label="missing",
            metadata={"target_files": ["nonexistent.py"]},
        )
        assembler = ContextPackAssembler(tmpdir)
        pack = assembler.assemble(task)
        # Should not crash; primary_files still populated (they are metadata, not validated)
        assert "nonexistent.py" in pack.primary_files
        # But dependency analysis should produce empty (file doesn't exist)
        assert pack.dependency_files == []


def test_assemble_recent_changes():
    """assemble passes recent_changes through."""
    with tempfile.TemporaryDirectory() as tmpdir:
        task = TaskNode(
            id="t6",
            dag_id="d1",
            label="with-changes",
            metadata={"target_files": []},
        )
        assembler = ContextPackAssembler(tmpdir)
        pack = assembler.assemble(task, recent_changes=["changed.py"])
        assert pack.recent_changes == ["changed.py"]


# ---------------------------------------------------------------------------
# parse_python_imports tests
# ---------------------------------------------------------------------------

def test_parse_python_imports_from_import():
    """parse_python_imports resolves 'from X import Y' to file paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "pkg"), exist_ok=True)
        target = os.path.join(tmpdir, "pkg", "mod.py")
        with open(target, "w") as f:
            f.write("# module\n")

        source = os.path.join(tmpdir, "main.py")
        with open(source, "w") as f:
            f.write("from pkg.mod import something\n")

        result = parse_python_imports(source, tmpdir)
        assert "pkg/mod.py" in result


def test_parse_python_imports_missing_file():
    """parse_python_imports returns empty list for nonexistent file."""
    result = parse_python_imports("/nonexistent/path.py", "/nonexistent")
    assert result == []
