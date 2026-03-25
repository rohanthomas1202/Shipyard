"""Tests for agent/tools/ast_ops.py — ast-grep structural operations."""
import os
import subprocess
import pytest


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
        assert result is not None

    def test_anchor_inside_comment(self):
        from agent.tools.ast_ops import validate_anchor
        content = "// const x = 1;\nconst y = 2;\n"
        result = validate_anchor(content, "const x = 1;", "typescript")
        assert result is not None


class TestStructuralReplace:
    def test_single_line_replacement(self):
        from agent.tools.ast_ops import structural_replace
        content = "const x = 1;\nconst y = 2;\n"
        result = structural_replace(content, "const x = 1;", "const x = 42;", "typescript")
        assert "const x = 42;" in result
        assert "const y = 2;" in result

    def test_preserves_indentation_nested(self):
        from agent.tools.ast_ops import structural_replace
        content = "class Foo {\n    bar() {\n        return 1;\n    }\n}\n"
        result = structural_replace(content, "return 1;", "return 42;", "typescript")
        assert "        return 42;" in result

    def test_multiline_replacement_preserves_relative_indent(self):
        from agent.tools.ast_ops import structural_replace
        content = "function foo() {\n    const x = 1;\n}\n"
        result = structural_replace(content, "const x = 1;", "const x = 1;\n    const y = 2;", "typescript")
        assert "    const x = 1;" in result
        assert "    const y = 2;" in result

    def test_fallback_when_not_structural(self):
        from agent.tools.ast_ops import structural_replace
        content = "a = 1\n\ndef foo():\n    pass\n"
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
        content = "class Outer {\n    class Inner {\n        method() {\n            return 1;\n        }\n    }\n}\n"
        result = structural_replace(content, "return 1;", "return 42;", "typescript")
        assert "            return 42;" in result

    def test_python_method_inside_class(self):
        from agent.tools.ast_ops import structural_replace
        content = "class Foo:\n    def bar(self):\n        x = 1\n        return x\n"
        result = structural_replace(content, "x = 1\n        return x", "x = 42\n        return x", "python")
        assert "        x = 42" in result

    def test_replacement_adds_indent_levels(self):
        from agent.tools.ast_ops import structural_replace
        content = "function foo() {\n    doThing();\n}\n"
        result = structural_replace(content, "doThing();", "if (cond) {\n    doThing();\n}", "typescript")
        assert "    if (cond) {" in result

    def test_returns_full_content(self):
        from agent.tools.ast_ops import structural_replace
        content = "line1\nline2\nline3\n"
        result = structural_replace(content, "line2", "LINE2", "typescript")
        assert result == "line1\nLINE2\nline3\n"


class TestDetectLanguages:
    def test_detects_typescript_files(self, tmp_path):
        from agent.tools.ast_ops import detect_languages
        (tmp_path / "app.ts").write_text("const x = 1;")
        (tmp_path / "comp.tsx").write_text("<div/>")
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
        assert "csv" not in result or result.get("csv") is False

    def test_non_git_directory_fallback(self, tmp_path):
        from agent.tools.ast_ops import detect_languages
        (tmp_path / "main.py").write_text("x = 1")
        result = detect_languages(str(tmp_path))
        assert result.get("python") is True


class TestCacheOperations:
    def test_clear_cache(self):
        from agent.tools.ast_ops import validate_anchor, clear_cache, get_stats, reset_stats
        reset_stats()
        validate_anchor("const x = 1;", "const x = 1;", "typescript")
        assert get_stats().cache_misses == 1
        validate_anchor("const x = 1;", "const x = 1;", "typescript")
        assert get_stats().cache_hits == 1
        clear_cache()
        validate_anchor("const x = 1;", "const x = 1;", "typescript")
        assert get_stats().cache_misses == 2

    def test_stats_reset(self):
        from agent.tools.ast_ops import get_stats, reset_stats
        reset_stats()
        stats = get_stats()
        assert stats.structural_matches == 0
        assert stats.fallbacks_to_text == 0


class TestEndToEndIntegration:
    def test_full_flow_structural_edit(self, tmp_path):
        from agent.tools.ast_ops import detect_languages, validate_anchor, structural_replace, reset_stats, get_stats
        import subprocess

        (tmp_path / "index.ts").write_text(
            "function greet(name: string) {\n"
            "    console.log(`Hello ${name}`);\n"
            "    return name;\n"
            "}\n"
        )
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)

        reset_stats()
        langs = detect_languages(str(tmp_path))
        assert langs.get("typescript") is True

        content = (tmp_path / "index.ts").read_text()
        anchor = "console.log(`Hello ${name}`);"
        result = validate_anchor(content, anchor, "typescript")
        assert result.structural_match is True

        new_content = structural_replace(content, anchor, 'console.log(`Hi ${name}!`);', "typescript")
        assert 'console.log(`Hi ${name}!`);' in new_content
        assert "return name;" in new_content

        stats = get_stats()
        assert stats.structural_matches >= 1

    def test_full_flow_fallback_to_text(self, tmp_path):
        from agent.tools.ast_ops import detect_languages, validate_anchor, structural_replace, reset_stats, get_stats
        import subprocess

        (tmp_path / "app.ts").write_text("const a = 1;\n\nconst b = 2;\n")
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)

        reset_stats()
        content = (tmp_path / "app.ts").read_text()
        anchor = "const a = 1;\n\nconst b"
        result = validate_anchor(content, anchor, "typescript")
        assert result.structural_match is False

        new_content = structural_replace(content, anchor, "const a = 42;\n\nconst b", "typescript")
        assert "const a = 42;" in new_content

        stats = get_stats()
        assert stats.fallbacks_to_text >= 1


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
            "plan": ["Run: false"],
            "current_step": 0,
            "working_directory": "/tmp",
        }
        result = executor_node(state)
        assert result.get("error_state") is not None
        assert "invalidated_files" not in result


class TestReceiveNodeIntegration:
    def test_receive_node_populates_ast_available(self, tmp_path):
        from agent.nodes.receive import receive_instruction_node
        (tmp_path / "app.ts").write_text("const x = 1;")
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


class TestApplyRule:
    """Test codebase-wide structural refactoring via ast-grep rules."""

    def test_dry_run_finds_matches(self, tmp_path):
        from agent.tools.ast_ops import apply_rule
        (tmp_path / "a.ts").write_text("const x = oldFunc(1);\n")
        (tmp_path / "b.ts").write_text("const y = oldFunc(2);\nconst z = oldFunc(3);\n")
        rule = {"pattern": "oldFunc($ARG)", "fix": "newFunc($ARG)", "language": "typescript"}
        results = apply_rule(rule, str(tmp_path), dry_run=True)
        assert len(results) == 2
        total_matches = sum(r.match_count for r in results)
        assert total_matches == 3
        assert (tmp_path / "a.ts").read_text() == "const x = oldFunc(1);\n"

    def test_apply_modifies_files(self, tmp_path):
        from agent.tools.ast_ops import apply_rule
        (tmp_path / "a.ts").write_text("const x = oldFunc(1);\n")
        rule = {"pattern": "oldFunc($ARG)", "fix": "newFunc($ARG)", "language": "typescript"}
        results = apply_rule(rule, str(tmp_path), dry_run=False)
        assert len(results) == 1
        assert results[0].match_count == 1
        assert "newFunc(1)" in (tmp_path / "a.ts").read_text()

    def test_apply_returns_old_and_new_content(self, tmp_path):
        from agent.tools.ast_ops import apply_rule
        original = "const x = oldFunc(1);\n"
        (tmp_path / "a.ts").write_text(original)
        rule = {"pattern": "oldFunc($ARG)", "fix": "newFunc($ARG)", "language": "typescript"}
        results = apply_rule(rule, str(tmp_path), dry_run=False)
        assert results[0].old_content == original
        assert "newFunc(1)" in results[0].new_content

    def test_no_matches_returns_empty(self, tmp_path):
        from agent.tools.ast_ops import apply_rule
        (tmp_path / "a.ts").write_text("const x = 1;\n")
        rule = {"pattern": "nonExistent($ARG)", "fix": "replacement($ARG)", "language": "typescript"}
        results = apply_rule(rule, str(tmp_path), dry_run=True)
        assert len(results) == 0

    def test_respects_scope_exclusions(self, tmp_path):
        from agent.tools.ast_ops import apply_rule
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.ts").write_text("const x = oldFunc(1);\n")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "b.ts").write_text("const y = oldFunc(2);\n")
        rule = {"pattern": "oldFunc($ARG)", "fix": "newFunc($ARG)", "language": "typescript"}
        results = apply_rule(rule, str(tmp_path), dry_run=True)
        assert len(results) == 1
        assert "src" in results[0].file_path

    def test_unsupported_language_returns_empty(self, tmp_path):
        from agent.tools.ast_ops import apply_rule
        (tmp_path / "a.xyz").write_text("content")
        rule = {"pattern": "x", "fix": "y", "language": "nonexistent_xyz"}
        results = apply_rule(rule, str(tmp_path), dry_run=True)
        assert len(results) == 0
