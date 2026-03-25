"""Integration test: real typescript-language-server, real diagnostics.

This test spawns a real LSP server and verifies the full protocol flow.
Skip if typescript-language-server is not installed.

Per spec: "Build the integration test first, then build the client against it."
"""
import asyncio
import json
import os
import shutil
import pytest
from pathlib import Path

# Skip entire module if typescript-language-server not available
pytestmark = pytest.mark.skipif(
    shutil.which("typescript-language-server") is None,
    reason="typescript-language-server not installed",
)


def _file_uri(path: str) -> str:
    """Convert a file path to a file:// URI."""
    return Path(path).as_uri()


@pytest.mark.asyncio
async def test_raw_lsp_protocol_gets_diagnostics(tmp_path):
    """Verify we can talk to typescript-language-server and get diagnostics.

    Uses pygls BaseLanguageClient directly — no Shipyard abstractions.
    This test validates the protocol works before we build our client layer.
    """
    from pygls.lsp.client import BaseLanguageClient
    from lsprotocol import types

    # Create a TypeScript project with a type error
    (tmp_path / "tsconfig.json").write_text('{"compilerOptions": {"strict": true}}')
    (tmp_path / "index.ts").write_text(
        'const x: number = "not a number";\n'
        'console.log(x);\n'
    )

    diagnostics_received = asyncio.Event()
    received_diagnostics: list[types.Diagnostic] = []

    client = BaseLanguageClient("test-client", "v1")

    @client.feature(types.TEXT_DOCUMENT_PUBLISH_DIAGNOSTICS)
    def on_diagnostics(params: types.PublishDiagnosticsParams):
        if params.diagnostics:
            received_diagnostics.extend(params.diagnostics)
            diagnostics_received.set()

    # Start server
    await client.start_io("typescript-language-server", "--stdio")

    try:
        # Initialize
        root_uri = _file_uri(str(tmp_path))
        result = await client.initialize_async(
            types.InitializeParams(
                capabilities=types.ClientCapabilities(
                    text_document=types.TextDocumentClientCapabilities(
                        publish_diagnostics=types.PublishDiagnosticsClientCapabilities(),
                    ),
                ),
                root_uri=root_uri,
                workspace_folders=[
                    types.WorkspaceFolder(uri=root_uri, name="test"),
                ],
            )
        )
        assert result.capabilities is not None
        client.initialized(types.InitializedParams())

        # Open the file with type error
        file_path = str(tmp_path / "index.ts")
        file_uri = _file_uri(file_path)
        content = (tmp_path / "index.ts").read_text()

        client.text_document_did_open(
            types.DidOpenTextDocumentParams(
                text_document=types.TextDocumentItem(
                    uri=file_uri,
                    language_id="typescript",
                    version=1,
                    text=content,
                )
            )
        )

        # Wait for diagnostics (with timeout)
        try:
            await asyncio.wait_for(diagnostics_received.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            pytest.fail("Timed out waiting for diagnostics from typescript-language-server")

        # Verify we got a type error diagnostic
        assert len(received_diagnostics) > 0
        error_diagnostics = [
            d for d in received_diagnostics
            if d.severity == types.DiagnosticSeverity.Error
        ]
        assert len(error_diagnostics) > 0, f"Expected type error, got: {received_diagnostics}"

        # Verify the error is about type mismatch
        error_msg = error_diagnostics[0].message.lower()
        assert "string" in error_msg or "number" in error_msg or "assignable" in error_msg, \
            f"Expected type mismatch error, got: {error_diagnostics[0].message}"

    finally:
        # Shutdown
        try:
            await asyncio.wait_for(client.shutdown_async(None), timeout=5.0)
            client.exit(None)
        except Exception:
            pass
        try:
            await asyncio.wait_for(client.stop(), timeout=5.0)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_raw_lsp_clean_file_no_errors(tmp_path):
    """Verify a clean file produces zero error diagnostics."""
    from pygls.lsp.client import BaseLanguageClient
    from lsprotocol import types

    (tmp_path / "tsconfig.json").write_text('{"compilerOptions": {"strict": true}}')
    (tmp_path / "clean.ts").write_text(
        'const x: number = 42;\n'
        'console.log(x);\n'
    )

    diagnostics_received = asyncio.Event()
    received_diagnostics: list[types.Diagnostic] = []

    client = BaseLanguageClient("test-client", "v1")

    @client.feature(types.TEXT_DOCUMENT_PUBLISH_DIAGNOSTICS)
    def on_diagnostics(params: types.PublishDiagnosticsParams):
        received_diagnostics.extend(params.diagnostics)
        diagnostics_received.set()

    await client.start_io("typescript-language-server", "--stdio")

    try:
        root_uri = _file_uri(str(tmp_path))
        await client.initialize_async(
            types.InitializeParams(
                capabilities=types.ClientCapabilities(
                    text_document=types.TextDocumentClientCapabilities(
                        publish_diagnostics=types.PublishDiagnosticsClientCapabilities(),
                    ),
                ),
                root_uri=root_uri,
                workspace_folders=[
                    types.WorkspaceFolder(uri=root_uri, name="test"),
                ],
            )
        )
        client.initialized(types.InitializedParams())

        file_uri = _file_uri(str(tmp_path / "clean.ts"))
        client.text_document_did_open(
            types.DidOpenTextDocumentParams(
                text_document=types.TextDocumentItem(
                    uri=file_uri,
                    language_id="typescript",
                    version=1,
                    text=(tmp_path / "clean.ts").read_text(),
                )
            )
        )

        # Wait briefly for diagnostics (may arrive as empty list)
        try:
            await asyncio.wait_for(diagnostics_received.wait(), timeout=15.0)
        except asyncio.TimeoutError:
            pass  # No diagnostics is acceptable for a clean file

        error_diagnostics = [
            d for d in received_diagnostics
            if d.severity == types.DiagnosticSeverity.Error
        ]
        assert len(error_diagnostics) == 0, f"Clean file should have no errors, got: {error_diagnostics}"

    finally:
        try:
            await asyncio.wait_for(client.shutdown_async(None), timeout=5.0)
            client.exit(None)
        except Exception:
            pass
        try:
            await asyncio.wait_for(client.stop(), timeout=5.0)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_validator_with_lsp_catches_type_error(tmp_path):
    """End-to-end: validator uses LSP to catch a type error introduced by an edit."""
    from agent.tools.lsp_manager import LspManager
    from agent.nodes.validator import validator_node

    (tmp_path / "tsconfig.json").write_text('{"compilerOptions": {"strict": true}}')

    # Original file is clean
    original = 'const x: number = 42;\nconsole.log(x);\n'
    # Edit introduces a type error
    broken = 'const x: number = "not a number";\nconsole.log(x);\n'
    (tmp_path / "index.ts").write_text(broken)

    async with LspManager(str(tmp_path), {"typescript": True}) as mgr:
        if mgr.server_status().get("typescript") != "running":
            pytest.skip("typescript-language-server not running")

        state = {
            "edit_history": [{
                "file": str(tmp_path / "index.ts"),
                "snapshot": original,  # pre-edit content
            }],
        }
        config = {"configurable": {"lsp_manager": mgr}}
        result = await validator_node(state, config)

        # Should detect the type error and rollback
        assert result["error_state"] is not None
        assert "LSP validation failed" in result["error_state"]
        # File should be rolled back to original
        assert (tmp_path / "index.ts").read_text() == original


@pytest.mark.asyncio
async def test_validator_with_lsp_passes_clean_edit(tmp_path):
    """End-to-end: validator with LSP passes a clean edit."""
    from agent.tools.lsp_manager import LspManager
    from agent.nodes.validator import validator_node

    (tmp_path / "tsconfig.json").write_text('{"compilerOptions": {"strict": true}}')

    original = 'const x: number = 42;\nconsole.log(x);\n'
    edited = 'const x: number = 99;\nconsole.log(x);\n'
    (tmp_path / "index.ts").write_text(edited)

    async with LspManager(str(tmp_path), {"typescript": True}) as mgr:
        if mgr.server_status().get("typescript") != "running":
            pytest.skip("typescript-language-server not running")

        state = {
            "edit_history": [{
                "file": str(tmp_path / "index.ts"),
                "snapshot": original,
            }],
        }
        config = {"configurable": {"lsp_manager": mgr}}
        result = await validator_node(state, config)

        assert result["error_state"] is None
        # File should NOT be rolled back
        assert (tmp_path / "index.ts").read_text() == edited
