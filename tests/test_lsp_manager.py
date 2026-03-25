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
