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
import weakref
from typing import Any

from agent.tools.lsp_client import LspConnection, LspDiagnosticClient
from agent.tracing import TraceLogger

tracer = TraceLogger()

# Track active managers for atexit cleanup (instance-level PIDs, not module-level)
_active_managers: weakref.WeakSet["LspManager"] = weakref.WeakSet()


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


def _cleanup_all_managers():
    """atexit handler: forcefully kill any lingering LSP server processes."""
    for mgr in list(_active_managers):
        for pid in mgr._pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass


# Register once at module load
atexit.register(_cleanup_all_managers)


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
        self._pids: list[int] = []  # instance-level PID tracking for atexit cleanup

    async def __aenter__(self) -> LspManager:
        """Start available LSP servers for detected languages."""
        # Auto-detect languages if none provided (S6 fix)
        if not self.detected_languages:
            try:
                from agent.tools.ast_ops import detect_languages
                self.detected_languages = detect_languages(self.project_path)
            except Exception:
                pass  # No languages detected — all LSP skipped

        # Register this manager for atexit cleanup
        _active_managers.add(self)

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
                # Track PID for atexit cleanup (instance-level, not module-level)
                if hasattr(conn._client, '_server') and conn._client._server:
                    self._pids.append(conn._client._server.pid)
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
        self._pids.clear()
        _active_managers.discard(self)

    def get_client(self, language: str) -> LspDiagnosticClient | None:
        """Get a diagnostic client for a language. Returns None if unavailable/degraded."""
        if self._status.get(language) != "running":
            return None
        return self._clients.get(language)

    def server_status(self) -> dict[str, str]:
        """Get status of all servers."""
        return dict(self._status)

    # Note: Per-file locking deferred to Phase 4 (when multi-language parallel validation is added)
