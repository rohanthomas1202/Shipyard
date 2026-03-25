import pytest
from agent.context import ContextAssembler


def test_assembler_includes_task_context():
    assembler = ContextAssembler(max_tokens=10000)
    assembler.add_task("Edit auth.ts", step=2, total_steps=5)
    result = assembler.build()
    assert "Edit auth.ts" in result
    assert "Step 2/5" in result


def test_assembler_includes_working_set():
    assembler = ContextAssembler(max_tokens=10000)
    assembler.add_file("src/auth.ts", "export function verify() {}")
    result = assembler.build()
    assert "src/auth.ts" in result
    assert "export function verify" in result


def test_assembler_deduplicates_files():
    assembler = ContextAssembler(max_tokens=10000)
    assembler.add_file("src/auth.ts", "content")
    assembler.add_file("src/auth.ts", "content")
    result = assembler.build()
    assert result.count("src/auth.ts") == 1


def test_assembler_includes_error_context():
    assembler = ContextAssembler(max_tokens=10000)
    assembler.add_error("TypeError: x is not a function\n  at line 42")
    result = assembler.build()
    assert "TypeError" in result


def test_assembler_respects_max_tokens():
    assembler = ContextAssembler(max_tokens=100)
    assembler.add_file("big.ts", "x" * 10000)
    result = assembler.build()
    assert len(result) < 10000


def test_assembler_prioritizes_working_set():
    assembler = ContextAssembler(max_tokens=200)
    assembler.add_file("current.ts", "important", priority="working")
    assembler.add_file("reference.ts", "y" * 5000, priority="reference")
    result = assembler.build()
    assert "current.ts" in result
    assert "important" in result


def test_assembler_empty():
    assembler = ContextAssembler(max_tokens=10000)
    result = assembler.build()
    assert result == ""
