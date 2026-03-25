"""Tests for agent/tools/ast_ops.py — ast-grep structural operations."""
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
