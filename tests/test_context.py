"""Tests for ContextAssembler — deterministic context assembly pipeline."""
import pytest
from agent.context import ContextAssembler, CHARS_PER_TOKEN


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
    assembler = ContextAssembler(max_tokens=600, system_prompt_reserve=0)
    assembler.add_file("big.ts", "x" * 10000)
    result = assembler.build()
    assert len(result) < 10000


def test_assembler_prioritizes_working_set():
    assembler = ContextAssembler(max_tokens=700, system_prompt_reserve=0)
    assembler.add_file("current.ts", "important", priority="working")
    assembler.add_file("reference.ts", "y" * 5000, priority="reference")
    result = assembler.build()
    assert "current.ts" in result
    assert "important" in result


def test_assembler_empty():
    assembler = ContextAssembler(max_tokens=10000)
    result = assembler.build()
    assert result == ""


# --- Tests for system_prompt_reserve ---


def test_system_prompt_reserve():
    """system_prompt_reserve subtracts from available budget."""
    assembler = ContextAssembler(max_tokens=1000, system_prompt_reserve=200)
    expected = (1000 - 200) * CHARS_PER_TOKEN
    assert assembler.max_chars == expected


def test_default_reserve():
    """Default system_prompt_reserve is 500 tokens."""
    assembler = ContextAssembler(max_tokens=10000)
    expected = (10000 - 500) * CHARS_PER_TOKEN
    assert assembler.max_chars == expected


def test_model_budget_large_context():
    """Large context window (o3-style 200k) accepts large content without truncation."""
    assembler = ContextAssembler(max_tokens=200000, system_prompt_reserve=1000)
    large_content = "x" * 50000
    assembler.add_file("big.ts", large_content, priority="working")
    result = assembler.build()
    assert large_content in result
