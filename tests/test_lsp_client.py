"""Tests for agent/tools/lsp_client.py — LSP client layers."""
import asyncio
import shutil
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark_requires_server = pytest.mark.skipif(
    shutil.which("typescript-language-server") is None,
    reason="typescript-language-server not installed",
)


class TestDiagnosticKey:
    """Test diagnostic comparison key function."""

    def test_key_with_code(self):
        from agent.tools.lsp_client import diagnostic_key
        from lsprotocol import types
        d = types.Diagnostic(
            range=types.Range(start=types.Position(0, 0), end=types.Position(0, 10)),
            message="Type error",
            severity=types.DiagnosticSeverity.Error,
            code=2322,
            source="typescript",
        )
        key = diagnostic_key(d)
        assert key == (2322, types.DiagnosticSeverity.Error, "typescript")

    def test_key_without_code_uses_message(self):
        from agent.tools.lsp_client import diagnostic_key
        from lsprotocol import types
        d = types.Diagnostic(
            range=types.Range(start=types.Position(0, 0), end=types.Position(0, 10)),
            message="Something wrong",
            severity=types.DiagnosticSeverity.Warning,
            source="eslint",
        )
        key = diagnostic_key(d)
        assert key == (types.DiagnosticSeverity.Warning, "eslint", "Something wrong")

    def test_diff_diagnostics_finds_new_errors(self):
        from agent.tools.lsp_client import diff_diagnostics
        from lsprotocol import types
        baseline = [
            types.Diagnostic(
                range=types.Range(start=types.Position(0, 0), end=types.Position(0, 10)),
                message="Pre-existing error",
                severity=types.DiagnosticSeverity.Error,
                code=1001,
                source="ts",
            ),
        ]
        post_edit = [
            types.Diagnostic(
                range=types.Range(start=types.Position(0, 0), end=types.Position(0, 10)),
                message="Pre-existing error",
                severity=types.DiagnosticSeverity.Error,
                code=1001,
                source="ts",
            ),
            types.Diagnostic(
                range=types.Range(start=types.Position(5, 0), end=types.Position(5, 10)),
                message="New error introduced",
                severity=types.DiagnosticSeverity.Error,
                code=2002,
                source="ts",
            ),
        ]
        new_errors = diff_diagnostics(baseline, post_edit)
        assert len(new_errors) == 1
        assert new_errors[0].code == 2002

    def test_diff_diagnostics_ignores_preexisting(self):
        from agent.tools.lsp_client import diff_diagnostics
        from lsprotocol import types
        baseline = [
            types.Diagnostic(
                range=types.Range(start=types.Position(0, 0), end=types.Position(0, 10)),
                message="Pre-existing",
                severity=types.DiagnosticSeverity.Error,
                code=1001,
                source="ts",
            ),
        ]
        # Same error after edit (line number changed but code/source same)
        post_edit = [
            types.Diagnostic(
                range=types.Range(start=types.Position(3, 0), end=types.Position(3, 10)),
                message="Pre-existing",
                severity=types.DiagnosticSeverity.Error,
                code=1001,
                source="ts",
            ),
        ]
        new_errors = diff_diagnostics(baseline, post_edit)
        assert len(new_errors) == 0

    def test_diff_diagnostics_ignores_warnings(self):
        from agent.tools.lsp_client import diff_diagnostics
        from lsprotocol import types
        baseline = []
        post_edit = [
            types.Diagnostic(
                range=types.Range(start=types.Position(0, 0), end=types.Position(0, 10)),
                message="A warning",
                severity=types.DiagnosticSeverity.Warning,
                code=3001,
                source="ts",
            ),
        ]
        new_errors = diff_diagnostics(baseline, post_edit)
        assert len(new_errors) == 0  # warnings don't count as errors
