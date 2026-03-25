"""Two-layer LSP client for Shipyard's validation pipeline.

Layer 1: LspConnection — wraps pygls BaseLanguageClient for transport
Layer 2: LspDiagnosticClient — high-level get_diagnostics() + diffing

Scoped to TypeScript for Phase 3. Multi-language in Phase 4.
"""
from __future__ import annotations

import asyncio
import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lsprotocol import types
from agent.tracing import TraceLogger

tracer = TraceLogger()


# --- Diagnostic Diffing Utilities ---

def diagnostic_key(d: types.Diagnostic) -> tuple:
    """Compute comparison key for a diagnostic.

    Uses (code, severity, source) — NOT line number (shifts after edits)
    and NOT message text (may include line-specific context).
    Falls back to (severity, source, message) when code is None.
    """
    if d.code is not None:
        return (d.code, d.severity, d.source)
    return (d.severity, d.source, d.message)


def diff_diagnostics(
    baseline: list[types.Diagnostic],
    post_edit: list[types.Diagnostic],
) -> list[types.Diagnostic]:
    """Find new Error-severity diagnostics introduced by an edit.

    Only Error-severity diagnostics trigger rollback.
    Warnings, Info, and Hints are ignored.
    """
    # Count baseline error keys
    baseline_keys: Counter = Counter()
    for d in baseline:
        if d.severity == types.DiagnosticSeverity.Error:
            baseline_keys[diagnostic_key(d)] += 1

    # Find post-edit errors not in baseline
    new_errors: list[types.Diagnostic] = []
    post_keys: Counter = Counter()
    for d in post_edit:
        if d.severity != types.DiagnosticSeverity.Error:
            continue
        key = diagnostic_key(d)
        post_keys[key] += 1
        if post_keys[key] > baseline_keys.get(key, 0):
            new_errors.append(d)

    return new_errors


def _file_uri(path: str) -> str:
    """Convert a filesystem path to a file:// URI."""
    return Path(path).as_uri()


# --- Version-aware diagnostic waiter (fixes P0 race conditions) ---

@dataclass
class _DiagnosticWaiter:
    """Tracks expected version to prevent stale diagnostic notifications."""
    expected_version: int
    event: asyncio.Event = field(default_factory=asyncio.Event)
    diagnostics: list = field(default_factory=list)


# --- LspConnection: Layer 1 ---

class LspConnection:
    """Wraps pygls BaseLanguageClient for stdio LSP transport.

    Handles:
    - Server process lifecycle (start/stop)
    - Initialize handshake + capability detection (push vs pull diagnostics)
    - Readiness tracking via workDoneProgress
    - Diagnostic notification collection
    - Stderr draining (prevents deadlock from full OS pipe buffers)
    """

    def __init__(self, cmd: list[str], root_path: str, language: str):
        self.cmd = cmd
        self.root_path = root_path
        self.root_uri = _file_uri(root_path)
        self.language = language
        self.is_ready = False
        self.is_degraded = False
        self.diagnostic_mode: str = "push"  # "push" (publishDiagnostics) or "pull" (textDocument/diagnostic) or "none"
        self._client = None
        self._capabilities = None
        self._waiters: dict[str, _DiagnosticWaiter] = {}  # uri → version-aware waiter
        self._progress_tokens: set[str] = set()
        self._ready_event = asyncio.Event()
        self._stderr_task: asyncio.Task | None = None
        self._doc_versions: dict[str, int] = {}  # uri → current version

    async def start(self) -> None:
        """Start the LSP server and perform initialize handshake."""
        from pygls.lsp.client import BaseLanguageClient

        self._client = BaseLanguageClient(f"shipyard-{self.language}", "v1")

        # Register diagnostic handler with version tracking (prevents stale notification races)
        @self._client.feature(types.TEXT_DOCUMENT_PUBLISH_DIAGNOSTICS)
        def on_diagnostics(params: types.PublishDiagnosticsParams):
            uri = params.uri
            waiter = self._waiters.get(uri)
            if waiter is None:
                return
            # Accept diagnostics if version matches or server doesn't report version
            if params.version is None or params.version >= waiter.expected_version:
                waiter.diagnostics = list(params.diagnostics)
                waiter.event.set()

        # Register progress handler for readiness tracking
        @self._client.feature(types.WINDOW_WORK_DONE_PROGRESS_CREATE)
        def on_progress_create(params: types.WorkDoneProgressCreateParams):
            token = str(params.token)
            self._progress_tokens.add(token)

        @self._client.feature(types.PROGRESS)
        def on_progress(params: types.ProgressParams):
            token = str(params.token)
            value = params.value
            if isinstance(value, dict) and value.get("kind") == "end":
                self._progress_tokens.discard(token)
                if not self._progress_tokens:
                    self.is_ready = True
                    self._ready_event.set()

        # Start server process
        await self._client.start_io(self.cmd[0], *self.cmd[1:])

        # Initialize handshake
        result = await self._client.initialize_async(
            types.InitializeParams(
                capabilities=types.ClientCapabilities(
                    text_document=types.TextDocumentClientCapabilities(
                        publish_diagnostics=types.PublishDiagnosticsClientCapabilities(),
                    ),
                ),
                root_uri=self.root_uri,
                workspace_folders=[
                    types.WorkspaceFolder(uri=self.root_uri, name="workspace"),
                ],
            )
        )
        self._capabilities = result.capabilities
        self._client.initialized(types.InitializedParams())

        # Capability detection: push vs pull diagnostic model
        caps = result.capabilities
        if caps.diagnostic_provider is not None:
            self.diagnostic_mode = "pull"
        elif caps.text_document_sync is not None:
            self.diagnostic_mode = "push"
        else:
            self.diagnostic_mode = "none"

        # Start stderr drain task to prevent pipe buffer deadlock
        # pygls manages the subprocess internally; access it for stderr draining
        if hasattr(self._client, '_server') and hasattr(self._client._server, 'stderr'):
            self._stderr_task = asyncio.create_task(self._drain_stderr(self._client._server.stderr))

        tracer.log("lsp_connection", {
            "language": self.language,
            "server": self.cmd[0],
            "status": "initialized",
            "diagnostic_mode": self.diagnostic_mode,
        })

    async def _drain_stderr(self, stderr_stream) -> None:
        """Background task: drain server stderr to prevent pipe buffer deadlock.

        Note: stderr EOF does NOT indicate crash — many servers close stderr
        normally during shutdown. Degradation is detected from request failures
        (timeouts + retries), not stderr state.
        """
        try:
            while True:
                line = await stderr_stream.readline()
                if not line:
                    break  # EOF — normal during shutdown, NOT a crash signal
                tracer.log("lsp_stderr", {"language": self.language, "line": line.decode(errors="replace").rstrip()})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            tracer.log("lsp_stderr", {"language": self.language, "error": str(e)})

    async def wait_ready(self, timeout: float = 60.0) -> None:
        """Wait for server readiness (workDoneProgress completion or timeout)."""
        if self.is_ready:
            return
        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass  # Server may not support progress — mark ready anyway
        self.is_ready = True

    async def open_document(self, file_path: str, content: str, version: int = 1) -> None:
        """Send textDocument/didOpen."""
        uri = _file_uri(file_path)
        self._doc_versions[uri] = version
        self._waiters[uri] = _DiagnosticWaiter(expected_version=version)
        self._client.text_document_did_open(
            types.DidOpenTextDocumentParams(
                text_document=types.TextDocumentItem(
                    uri=uri,
                    language_id=self.language,
                    version=version,
                    text=content,
                )
            )
        )

    async def change_document(self, file_path: str, content: str, version: int = 2) -> None:
        """Send textDocument/didChange with full content."""
        uri = _file_uri(file_path)
        self._doc_versions[uri] = version
        # Create new waiter with updated version (atomically replaces old one)
        self._waiters[uri] = _DiagnosticWaiter(expected_version=version)
        self._client.text_document_did_change(
            types.DidChangeTextDocumentParams(
                text_document=types.VersionedTextDocumentIdentifier(
                    uri=uri,
                    version=version,
                ),
                content_changes=[
                    types.TextDocumentContentChangeWholeDocument(text=content),
                ],
            )
        )

    async def close_document(self, file_path: str) -> None:
        """Send textDocument/didClose."""
        uri = _file_uri(file_path)
        self._client.text_document_did_close(
            types.DidCloseTextDocumentParams(
                text_document=types.TextDocumentIdentifier(uri=uri),
            )
        )
        self._waiters.pop(uri, None)
        self._doc_versions.pop(uri, None)

    async def wait_for_diagnostics(self, file_path: str, timeout: float = 5.0) -> list[types.Diagnostic] | None:
        """Wait for publishDiagnostics notification for a file.

        Returns:
            list[Diagnostic] — diagnostics received (may be empty [] for clean files)
            None — timeout, no response received at all
        """
        uri = _file_uri(file_path)
        waiter = self._waiters.get(uri)
        if waiter is None:
            return None
        try:
            await asyncio.wait_for(waiter.event.wait(), timeout=timeout)
            return waiter.diagnostics  # may be [] for clean files — that's a valid response
        except asyncio.TimeoutError:
            tracer.log("lsp_connection", {
                "language": self.language,
                "file": file_path,
                "timeout": timeout,
                "status": "diagnostic_timeout",
            })
            return None  # sentinel: no response at all

    async def stop(self) -> None:
        """Shutdown and stop the server."""
        # Cancel stderr drain
        if self._stderr_task and not self._stderr_task.done():
            self._stderr_task.cancel()
        if self._client is None:
            return
        try:
            await asyncio.wait_for(self._client.shutdown_async(None), timeout=5.0)
            self._client.exit(None)
        except Exception:
            pass
        try:
            await asyncio.wait_for(self._client.stop(), timeout=5.0)
        except Exception:
            pass
        tracer.log("lsp_connection", {"language": self.language, "status": "stopped"})


# --- LspDiagnosticClient: Layer 2 ---

class LspDiagnosticClient:
    """High-level diagnostic client for Shipyard's validator.

    Provides:
    - get_diagnostics(file_path, content) → list[Diagnostic]
    - notify_rollback(file_path, restored_content) → None
    """

    def __init__(self, connection: LspConnection, timeout_first: float = 30.0, timeout_incremental: float = 5.0):
        self.connection = connection
        self.timeout_first = timeout_first
        self.timeout_incremental = timeout_incremental
        self._opened_files: set[str] = set()
        self._first_call = True
        self._version_counter: dict[str, int] = {}

    def _next_version(self, file_path: str) -> int:
        v = self._version_counter.get(file_path, 0) + 1
        self._version_counter[file_path] = v
        return v

    async def get_diagnostics(self, file_path: str, content: str, timeout: float | None = None) -> list[types.Diagnostic]:
        """Get diagnostics for a file.

        Opens the document if not already open, or sends didChange if already open.
        Waits for publishDiagnostics with appropriate timeout.
        """
        if timeout is None:
            timeout = self.timeout_first if self._first_call else self.timeout_incremental

        if self._first_call:
            await self.connection.wait_ready(timeout=60.0)
            self._first_call = False

        version = self._next_version(file_path)

        if file_path not in self._opened_files:
            await self.connection.open_document(file_path, content, version)
            self._opened_files.add(file_path)
        else:
            await self.connection.change_document(file_path, content, version)

        result = await self.connection.wait_for_diagnostics(file_path, timeout=timeout)

        # First-timeout retry: only if we got NO RESPONSE (None), not empty diagnostics ([])
        # Empty [] means server responded with "no errors" — that's valid, don't retry.
        # None means timeout with no response — retry once with 2x timeout.
        if result is None and not self.connection.is_degraded:
            tracer.log("lsp_diagnostic", {"file": file_path, "status": "timeout_retry", "timeout": timeout * 2})
            version = self._next_version(file_path)
            await self.connection.change_document(file_path, content, version)
            result = await self.connection.wait_for_diagnostics(file_path, timeout=timeout * 2)

        return result if result is not None else []

    async def notify_rollback(self, file_path: str, restored_content: str) -> None:
        """Notify the server that a file was rolled back.

        Sends didChange with restored content and waits for fresh diagnostics
        to prevent stale state on next validation.
        """
        if file_path in self._opened_files:
            version = self._next_version(file_path)
            await self.connection.change_document(file_path, restored_content, version)
            # Wait for fresh diagnostics to flush stale state
            await self.connection.wait_for_diagnostics(file_path, timeout=self.timeout_incremental)
