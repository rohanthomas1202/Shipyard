# ast-grep Phase 3: LSP Validation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add LSP-powered semantic validation to Shipyard's edit pipeline, replacing subprocess syntax checks with real language server diagnostics — scoped to TypeScript only for Phase 3.

**Architecture:** A two-layer LSP client (`LspConnection` wrapping pygls `BaseLanguageClient` + `LspDiagnosticClient` providing `get_diagnostics()`) connects to `typescript-language-server` over stdio. `LspManager` handles server lifecycle as an async context manager injected into the graph run. The `validator_node` migrates from sync to async, using LSP diagnostics when available and falling back to existing subprocess checks. Diagnostic diffing (baseline vs post-edit) prevents false rollbacks from pre-existing errors.

**Tech Stack:** Python 3.11+, pygls (includes lsprotocol), typescript-language-server, pytest, pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-25-ast-grep-lsp-integration-design.md` (Sections 2, 3)

**Prerequisites:** Phase 1 + Phase 2 complete. `typescript-language-server` and `typescript` installed (`npm i -g typescript-language-server typescript`).

**Commit rule:** Never include `Co-Authored-By` lines in commit messages.

**Budget:** 3-4 weeks. LSP protocol edge cases are the primary risk.

**Spec directive:** Build the integration test FIRST, then build the client against it.

---

## File Structure

### New Files
- `agent/tools/lsp_client.py` — Two-layer LSP client: LspConnection (pygls transport) + LspDiagnosticClient (diagnostics + diffing)
- `agent/tools/lsp_manager.py` — Server lifecycle: registry, auto-discovery, async context manager, per-file locking
- `tests/test_lsp_client.py` — Unit tests for LspConnection, LspDiagnosticClient, diagnostic diffing
- `tests/test_lsp_manager.py` — Unit tests for LspManager lifecycle, discovery, crash handling
- `tests/test_lsp_integration.py` — Integration test: real typescript-language-server, real diagnostics

### Modified Files
- `agent/nodes/validator.py` — Migrate sync → async, add config param, use LSP when available
- `agent/graph.py` — No changes needed (LangGraph handles async nodes natively)
- `server/main.py` — Wrap graph run in LspManager context manager
- `pyproject.toml` — Add pygls dependency
- `requirements.txt` — Add pygls
- `tests/test_validator_node.py` — Update for async validator

---

## Task 1: Add pygls Dependency

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`

- [ ] **Step 1: Add pygls to dependencies**

In `pyproject.toml`, add to the `dependencies` list:
```
"pygls>=2.0.0",
```

In `requirements.txt`, add:
```
pygls>=2.0.0
```

- [ ] **Step 2: Install**

Run: `.venv/bin/pip install pygls`
Expected: Installs pygls + lsprotocol + cattrs.

- [ ] **Step 3: Verify**

Run:
```bash
.venv/bin/python -c "
from pygls.lsp.client import BaseLanguageClient
from lsprotocol import types
print(f'pygls BaseLanguageClient: OK')
print(f'lsprotocol types.Diagnostic: {types.Diagnostic}')
print(f'TEXT_DOCUMENT_PUBLISH_DIAGNOSTICS: {types.TEXT_DOCUMENT_PUBLISH_DIAGNOSTICS}')
"
```
Expected: All imports succeed, prints type info.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml requirements.txt
git commit -m "deps: add pygls for LSP client support"
```

---

## Task 2: Integration Test First — Real typescript-language-server

**Files:**
- Create: `tests/test_lsp_integration.py`

Per the spec: "Build the integration test first, then build the client against it." This test starts a real `typescript-language-server`, opens a file with a known type error, and verifies a diagnostic comes back. It tests the protocol end-to-end before we build abstractions.

- [ ] **Step 1: Check typescript-language-server is available**

Run: `which typescript-language-server && typescript-language-server --version`

If not installed: `npm i -g typescript-language-server typescript`

- [ ] **Step 2: Create the integration test**

Create `tests/test_lsp_integration.py`:

```python
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
```

- [ ] **Step 3: Run the integration test**

Run: `.venv/bin/pytest tests/test_lsp_integration.py -v --timeout=60`
Expected: Both tests PASS (or SKIP if typescript-language-server not installed).

This validates the protocol works end-to-end before we build abstractions.

- [ ] **Step 4: Commit**

```bash
git add tests/test_lsp_integration.py
git commit -m "test: LSP integration test with real typescript-language-server"
```

---

## Task 3: LspConnection — pygls Transport Wrapper

**Files:**
- Create: `agent/tools/lsp_client.py`
- Create: `tests/test_lsp_client.py`

The LspConnection wraps pygls `BaseLanguageClient` and adds:
- Stderr draining (background task)
- Readiness tracking (workDoneProgress)
- Diagnostic collection via asyncio.Event

- [ ] **Step 1: Write failing tests for LspConnection**

Create `tests/test_lsp_client.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_lsp_client.py -v`
Expected: FAIL — `agent.tools.lsp_client` does not exist.

- [ ] **Step 3: Implement LspConnection and diagnostic utilities**

Create `agent/tools/lsp_client.py`:

```python
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
    - Crash detection (EOF on stdout → degraded status)
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

    async def wait_for_diagnostics(self, file_path: str, timeout: float = 5.0) -> list[types.Diagnostic]:
        """Wait for publishDiagnostics notification for a file."""
        uri = _file_uri(file_path)
        waiter = self._waiters.get(uri)
        if waiter is None:
            return []
        try:
            await asyncio.wait_for(waiter.event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            tracer.log("lsp_connection", {
                "language": self.language,
                "file": file_path,
                "timeout": timeout,
                "status": "diagnostic_timeout",
            })
        return waiter.diagnostics

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
        self._first_call_just_happened = False
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
            self._first_call_just_happened = True

        version = self._next_version(file_path)

        if file_path not in self._opened_files:
            await self.connection.open_document(file_path, content, version)
            self._opened_files.add(file_path)
        else:
            await self.connection.change_document(file_path, content, version)

        diagnostics = await self.connection.wait_for_diagnostics(file_path, timeout=timeout)

        # First-timeout retry: if first call got no diagnostics, retry with 2x timeout
        if self._first_call_just_happened:
            self._first_call_just_happened = False  # always reset, regardless of outcome
        if not diagnostics and not self.connection.is_degraded and timeout == self.timeout_first:
            tracer.log("lsp_diagnostic", {"file": file_path, "status": "first_timeout_retry", "timeout": timeout * 2})
            version = self._next_version(file_path)
            await self.connection.change_document(file_path, content, version)
            diagnostics = await self.connection.wait_for_diagnostics(file_path, timeout=timeout * 2)

        return diagnostics

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
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_lsp_client.py -v`
Expected: All diagnostic diffing tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/tools/lsp_client.py tests/test_lsp_client.py
git commit -m "feat: add LSP client with diagnostic diffing"
```

---

## Task 4: LspManager — Server Lifecycle

**Files:**
- Create: `agent/tools/lsp_manager.py`
- Create: `tests/test_lsp_manager.py`

- [ ] **Step 1: Write tests for LspManager**

Create `tests/test_lsp_manager.py`:

```python
"""Tests for agent/tools/lsp_manager.py — LSP server lifecycle."""
import asyncio
import shutil
import pytest


class TestServerRegistry:
    def test_registry_has_typescript(self):
        from agent.tools.lsp_manager import REGISTRY
        assert "typescript" in REGISTRY
        assert "cmd" in REGISTRY["typescript"]

    def test_discover_finds_installed_server(self):
        from agent.tools.lsp_manager import _discover_server
        if shutil.which("typescript-language-server"):
            result = _discover_server("typescript")
            assert result is not None
            assert "typescript-language-server" in result[0]
        else:
            pytest.skip("typescript-language-server not installed")

    def test_discover_returns_none_for_missing(self):
        from agent.tools.lsp_manager import _discover_server
        result = _discover_server("nonexistent_lang_xyz")
        assert result is None


class TestLspManagerLifecycle:
    @pytest.mark.asyncio
    @pytest.mark.skipif(
        shutil.which("typescript-language-server") is None,
        reason="typescript-language-server not installed",
    )
    async def test_context_manager_starts_and_stops(self, tmp_path):
        from agent.tools.lsp_manager import LspManager
        (tmp_path / "tsconfig.json").write_text('{}')
        (tmp_path / "a.ts").write_text("const x = 1;\n")

        async with LspManager(str(tmp_path), {"typescript": True}) as mgr:
            status = mgr.server_status()
            assert status.get("typescript") in ("running", "unavailable")

            client = mgr.get_client("typescript")
            if status.get("typescript") == "running":
                assert client is not None

        # After exit, get_client should return None
        # (manager is no longer valid after context exit)

    @pytest.mark.asyncio
    async def test_unavailable_language_returns_none(self, tmp_path):
        from agent.tools.lsp_manager import LspManager
        async with LspManager(str(tmp_path), {"typescript": True}) as mgr:
            client = mgr.get_client("nonexistent_xyz")
            assert client is None
```

- [ ] **Step 2: Implement LspManager**

Create `agent/tools/lsp_manager.py`:

```python
"""LSP Server Lifecycle Manager for Shipyard.

Manages LSP server processes as an async context manager.
Injected into the graph run via config["configurable"]["lsp_manager"].

Scoped to TypeScript for Phase 3. Multi-language in Phase 4.
"""
from __future__ import annotations

import asyncio
import atexit
import os
import shutil
import signal
from typing import Any

from agent.tools.lsp_client import LspConnection, LspDiagnosticClient
from agent.tracing import TraceLogger

tracer = TraceLogger()

# Track PIDs for atexit cleanup
_active_pids: list[int] = []


# Server registry — TypeScript only for Phase 3
REGISTRY: dict[str, dict[str, Any]] = {
    "typescript": {
        "cmd": ["typescript-language-server", "--stdio"],
        "timeout_first": 10,
        "timeout_incremental": 5,
        "readiness_timeout": 15,
    },
    # Phase 4 additions:
    # "python": {"cmd": ["pyright-langserver", "--stdio"], ...},
    # "rust": {"cmd": ["rust-analyzer"], ...},
    # "go": {"cmd": ["gopls", "serve"], ...},
}


def _cleanup_pids():
    """atexit handler: forcefully kill any lingering LSP server processes."""
    for pid in _active_pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def _discover_server(language: str, project_path: str = "") -> list[str] | None:
    """Discover an LSP server binary for a language.

    Checks: (1) project-local paths, (2) PATH, (3) fallback command.
    Returns the command list if found, None if not.
    """
    entry = REGISTRY.get(language)
    if entry is None:
        return None

    cmd = entry["cmd"]

    # Check project-local paths first (e.g., node_modules/.bin/)
    if project_path:
        local_paths = [
            os.path.join(project_path, "node_modules", ".bin", cmd[0]),
            os.path.join(project_path, ".venv", "bin", cmd[0]),
        ]
        for local in local_paths:
            if os.path.isfile(local) and os.access(local, os.X_OK):
                return [local] + cmd[1:]

    # Check PATH
    if shutil.which(cmd[0]):
        return cmd

    # Check fallback
    fallback = entry.get("fallback_cmd")
    if fallback and shutil.which(fallback[0]):
        return fallback

    return None


class LspManager:
    """Manages LSP server lifecycles for a single graph run.

    Usage:
        async with LspManager(project_path, detected_languages) as mgr:
            client = mgr.get_client("typescript")
            if client:
                diags = await client.get_diagnostics(path, content)
    """

    def __init__(self, project_path: str, detected_languages: dict[str, bool]):
        self.project_path = project_path
        self.detected_languages = detected_languages
        self._connections: dict[str, LspConnection] = {}
        self._clients: dict[str, LspDiagnosticClient] = {}
        self._status: dict[str, str] = {}  # language → "running" | "degraded" | "unavailable"

    async def __aenter__(self) -> LspManager:
        """Start available LSP servers for detected languages."""
        # Auto-detect languages if none provided (S6 fix)
        if not self.detected_languages:
            try:
                from agent.tools.ast_ops import detect_languages
                self.detected_languages = detect_languages(self.project_path)
            except Exception:
                pass  # No languages detected — all LSP skipped

        # Register atexit handler for orphan cleanup (S2 fix)
        atexit.register(_cleanup_pids)

        for language, available in self.detected_languages.items():
            if not available:
                continue

            cmd = _discover_server(language, self.project_path)
            if cmd is None:
                self._status[language] = "unavailable"
                tracer.log("lsp_manager", {"language": language, "status": "unavailable", "reason": "binary not found"})
                continue

            try:
                entry = REGISTRY.get(language, {})
                conn = LspConnection(cmd, self.project_path, language)
                await conn.start()
                self._connections[language] = conn
                self._clients[language] = LspDiagnosticClient(
                    conn,
                    timeout_first=entry.get("timeout_first", 30.0),
                    timeout_incremental=entry.get("timeout_incremental", 5.0),
                )
                self._status[language] = "running"
                # Track PID for atexit cleanup
                if hasattr(conn._client, '_server') and conn._client._server:
                    _active_pids.append(conn._client._server.pid)
                tracer.log("lsp_manager", {"language": language, "status": "running", "cmd": cmd[0]})
            except Exception as e:
                self._status[language] = "unavailable"
                tracer.log("lsp_manager", {"language": language, "status": "unavailable", "error": str(e)})

        return self

    async def __aexit__(self, *exc) -> None:
        """Stop all LSP servers and clean up."""
        for language, conn in self._connections.items():
            try:
                await conn.stop()
            except Exception:
                pass
            tracer.log("lsp_manager", {"language": language, "status": "stopped"})
        self._connections.clear()
        self._clients.clear()
        _active_pids.clear()

    def get_client(self, language: str) -> LspDiagnosticClient | None:
        """Get a diagnostic client for a language. Returns None if unavailable/degraded."""
        if self._status.get(language) != "running":
            return None
        return self._clients.get(language)

    def server_status(self) -> dict[str, str]:
        """Get status of all servers."""
        return dict(self._status)

    # Note: Per-file locking deferred to Phase 4 (when multi-language parallel validation is added)
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/pytest tests/test_lsp_manager.py -v --timeout=60`
Expected: All pass (some may skip if typescript-language-server not installed).

- [ ] **Step 4: Commit**

```bash
git add agent/tools/lsp_manager.py tests/test_lsp_manager.py
git commit -m "feat: add LspManager for server lifecycle management"
```

---

## Task 5: Migrate validator_node to Async + LSP Integration

**Files:**
- Modify: `agent/nodes/validator.py`
- Modify: `tests/test_validator_node.py`

This is the core integration — the validator uses LSP diagnostics when available, falls back to subprocess checks.

- [ ] **Step 1: Write test for async validator with LSP fallback**

Add to `tests/test_validator_node.py` (or create it if it needs restructuring for async):

```python
import pytest


@pytest.mark.asyncio
async def test_validator_falls_back_to_syntax_check_without_lsp(tmp_path):
    """Without lsp_manager in config, validator uses existing subprocess checks."""
    from agent.nodes.validator import validator_node

    # Create a valid JSON file
    test_file = tmp_path / "data.json"
    test_file.write_text('{"valid": true}')

    state = {
        "edit_history": [{"file": str(test_file), "snapshot": '{"valid": true}'}],
    }
    config = {"configurable": {}}
    result = await validator_node(state, config)
    assert result["error_state"] is None


@pytest.mark.asyncio
async def test_validator_detects_invalid_json_without_lsp(tmp_path):
    """Invalid JSON should be caught by fallback syntax check."""
    from agent.nodes.validator import validator_node

    test_file = tmp_path / "data.json"
    test_file.write_text('{invalid json}')

    state = {
        "edit_history": [{"file": str(test_file), "snapshot": '{}'}],
    }
    config = {"configurable": {}}
    result = await validator_node(state, config)
    assert result["error_state"] is not None
    assert "Syntax check failed" in result["error_state"]
    # File should be rolled back
    assert test_file.read_text() == '{}'
```

- [ ] **Step 2: Migrate validator_node to async**

Replace `agent/nodes/validator.py`:

```python
"""Validator node — syntax and semantic validation of edits.

Uses LSP diagnostics when available (Phase 3+), falls back to subprocess
syntax checks. Rolls back edits that introduce errors.

Diagnostic diffing: only NEW errors trigger rollback. Pre-existing errors
in the project are ignored.
"""
import asyncio
import json
import os
import subprocess
from agent.tracing import TraceLogger

tracer = TraceLogger()


def _syntax_check(file_path: str) -> dict:
    """Run a language-appropriate syntax check (synchronous)."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".json":
        try:
            with open(file_path) as f:
                json.load(f)
            return {"valid": True, "error": None}
        except json.JSONDecodeError as e:
            return {"valid": False, "error": str(e)}

    if ext in (".ts", ".tsx"):
        result = subprocess.run(
            ["npx", "esbuild", file_path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return {"valid": False, "error": result.stderr[:500]}
        return {"valid": True, "error": None}

    if ext in (".js", ".jsx"):
        result = subprocess.run(
            ["node", "--check", file_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return {"valid": False, "error": result.stderr[:500]}
        return {"valid": True, "error": None}

    if ext in (".yaml", ".yml"):
        try:
            import yaml
            with open(file_path) as f:
                yaml.safe_load(f)
            return {"valid": True, "error": None}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    return {"valid": True, "error": None}


def _rollback(edit_entry: dict):
    """Restore a file from its snapshot."""
    if "snapshot" in edit_entry:
        with open(edit_entry["file"], "w") as f:
            f.write(edit_entry["snapshot"])


def _detect_language(file_path: str) -> str | None:
    """Detect language from file extension for LSP client lookup."""
    ext_map = {
        ".ts": "typescript", ".tsx": "typescript",
        ".js": "javascript", ".jsx": "javascript",
        ".py": "python", ".rs": "rust", ".go": "go",
    }
    _, ext = os.path.splitext(file_path)
    return ext_map.get(ext.lower())


async def validator_node(state: dict, config: dict | None = None) -> dict:
    """Validate the most recent edit. Rollback if validation fails.

    Uses LSP diagnostics when lsp_manager is available, falls back to
    subprocess syntax checks otherwise.

    Note: config parameter added for LSP integration. LangGraph auto-injects
    it for nodes that declare it. Default None for backward compatibility
    with existing tests that call validator_node(state) without config.
    """
    if config is None:
        config = {"configurable": {}}
    edit_history = state.get("edit_history", [])
    if not edit_history:
        return {"error_state": None}

    last_edit = edit_history[-1]
    if "file" not in last_edit:
        return {"error_state": None}

    file_path = last_edit["file"]

    # Try LSP validation first
    lsp_manager = config["configurable"].get("lsp_manager")
    if lsp_manager is not None:
        language = _detect_language(file_path)
        if language:
            client = lsp_manager.get_client(language)
            if client is not None:
                try:
                    result = await _lsp_validate(client, file_path, last_edit)
                    if result is not None:
                        return result
                except Exception as e:
                    tracer.log("validator", {"file": file_path, "lsp_error": str(e), "fallback": "syntax_check"})

    # Fallback: subprocess syntax check (wrapped in thread to avoid blocking)
    check = await asyncio.to_thread(_syntax_check, file_path)

    tracer.log("validator", {"file": file_path, "syntax_valid": check["valid"], "error": check["error"]})

    if not check["valid"]:
        _rollback(last_edit)
        return {"error_state": f"Syntax check failed for {file_path}: {check['error']}. Edit rolled back."}

    return {"error_state": None}


async def _lsp_validate(client, file_path: str, edit_entry: dict) -> dict | None:
    """Validate using LSP diagnostic diffing.

    Returns validation result dict, or None to fall back to syntax check.
    """
    from agent.tools.lsp_client import diff_diagnostics
    from lsprotocol import types

    # Read current (post-edit) content
    try:
        with open(file_path, "r") as f:
            post_content = f.read()
    except OSError:
        return None

    # Get baseline diagnostics (pre-edit content from snapshot)
    baseline_content = edit_entry.get("snapshot")
    baseline_diags = []
    if baseline_content:
        baseline_diags = await client.get_diagnostics(file_path, baseline_content)

    # Get post-edit diagnostics
    post_diags = await client.get_diagnostics(file_path, post_content)

    # Diff: only new errors trigger rollback
    new_errors = diff_diagnostics(baseline_diags, post_diags)

    tracer.log("validator", {
        "file": file_path,
        "lsp": True,
        "baseline_errors": len([d for d in baseline_diags if d.severity == types.DiagnosticSeverity.Error]),
        "post_errors": len([d for d in post_diags if d.severity == types.DiagnosticSeverity.Error]),
        "new_errors": len(new_errors),
    })

    if new_errors:
        # Rollback and notify LSP
        _rollback(edit_entry)
        await client.notify_rollback(file_path, baseline_content or "")

        error_msgs = "; ".join(f"{e.message} (code {e.code})" for e in new_errors[:3])
        return {"error_state": f"LSP validation failed for {file_path}: {error_msgs}. Edit rolled back."}

    return {"error_state": None}
```

- [ ] **Step 3: Run validator tests**

Run: `.venv/bin/pytest tests/test_validator_node.py -v`
Expected: All pass (new async tests + any existing tests updated).

Note: Existing tests may need updating from `validator_node(state)` to `await validator_node(state, config)`. Check and update the test calls.

- [ ] **Step 4: Run full test suite for regressions**

Run: `.venv/bin/pytest tests/ -v --timeout=60 -k "validator or editor or graph or ast_ops or refactor"`
Expected: All pass. The graph handles async nodes natively — no edge changes needed.

- [ ] **Step 5: Commit**

```bash
git add agent/nodes/validator.py tests/test_validator_node.py
git commit -m "feat: migrate validator_node to async with LSP diagnostic diffing"
```

---

## Task 6: Wire LspManager into server/main.py

**Files:**
- Modify: `server/main.py`

- [ ] **Step 1: Update execute() to wrap in LspManager**

In the `execute()` function inside `submit_instruction`, wrap the `graph.ainvoke` call:

```python
async def execute():
    try:
        graph = app.state.graph
        initial_state = { ... }  # existing

        # Start LSP servers for detected languages
        from agent.tools.lsp_manager import LspManager
        lsp_config = {}  # TODO: read from project settings in Phase 4
        detected_languages = {}  # Will be populated by receive_node

        async with LspManager(req.working_directory, detected_languages) as lsp_mgr:
            config = {
                "configurable": {
                    "store": store,
                    "router": router,
                    "approval_manager": app.state.approval_manager,
                    "run_id": run_id,
                    "lsp_manager": lsp_mgr,
                }
            }
            result = await graph.ainvoke(initial_state, config=config)
            # ... existing result handling ...
    except Exception as e:
        runs[run_id] = {"status": "error", "result": str(e)}
```

Note: `detected_languages` starts empty — the `receive_node` populates `ast_available` which is the same data. For Phase 3, the LspManager could also auto-detect, but the simpler approach is to start with the languages detected in `receive_node`. Since LspManager is created before the graph runs, and `receive_node` runs first inside the graph, we have a chicken-and-egg problem. **Resolution:** LspManager does its own language detection from file extensions on start, independent of `receive_node`. This duplicates a small amount of work but avoids the ordering issue.

- [ ] **Step 2: Also update _resume_run AND continue_run similarly**

The `continue_run` endpoint (`POST /instruction/{run_id}`) also has its own `execute()` closure that calls `graph.ainvoke`. Update it with the same `LspManager` wrapping pattern.

Add `lsp_manager` to the resume config. For resumed runs, the LspManager needs to start fresh (servers from the previous run are gone):

```python
async with LspManager(working_dir, {}) as lsp_mgr:
    config = {
        "configurable": {
            ...
            "lsp_manager": lsp_mgr,
        }
    }
```

- [ ] **Step 3: Run server tests**

Run: `.venv/bin/pytest tests/test_server.py -v --timeout=30` (if available)
Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add server/main.py
git commit -m "feat: wire LspManager into graph run lifecycle"
```

---

## Task 7: Full LSP Validation Integration Test

**Files:**
- Modify: `tests/test_lsp_integration.py`

- [ ] **Step 1: Add end-to-end validator test with LSP**

Add to `tests/test_lsp_integration.py`:

```python
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
```

- [ ] **Step 2: Run integration tests**

Run: `.venv/bin/pytest tests/test_lsp_integration.py -v --timeout=120`
Expected: All pass (or skip if typescript-language-server not installed).

- [ ] **Step 3: Commit**

```bash
git add tests/test_lsp_integration.py
git commit -m "test: end-to-end LSP validation integration tests"
```

---

## Task 8: Final Verification

- [ ] **Step 1: Run all Phase 3 tests**

Run: `.venv/bin/pytest tests/test_lsp_client.py tests/test_lsp_manager.py tests/test_lsp_integration.py tests/test_validator_node.py -v --timeout=120`
Expected: All pass (integration tests skip if no server).

- [ ] **Step 2: Run full regression suite**

Run: `.venv/bin/pytest tests/test_ast_ops.py tests/test_refactor_node.py tests/test_editor_node.py tests/test_graph.py tests/test_steps.py -v --timeout=60`
Expected: All pass — no regressions from Phase 3.

- [ ] **Step 3: Verify import chain**

Run:
```bash
.venv/bin/python -c "
from agent.tools.lsp_client import LspConnection, LspDiagnosticClient, diagnostic_key, diff_diagnostics
from agent.tools.lsp_manager import LspManager, REGISTRY, _discover_server
from agent.nodes.validator import validator_node
print('All imports successful')
print(f'Registry languages: {list(REGISTRY.keys())}')
"
```

- [ ] **Step 4: Verify graph still compiles**

Run:
```bash
.venv/bin/python -c "from agent.graph import build_graph; g = build_graph(); print(f'Graph: {len(g.nodes)} nodes')"
```

- [ ] **Step 5: Commit if cleanup needed**

```bash
git status
```
