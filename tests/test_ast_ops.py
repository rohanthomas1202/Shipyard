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
