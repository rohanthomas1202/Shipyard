"""Tests for LangSmith trace link generation and server integration."""
import os
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
from store.sqlite import SQLiteSessionStore
from agent.events import EventBus
from agent.router import ModelRouter
from server.websocket import ConnectionManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(tmp_path):
    """Provide an AsyncClient wired to a real app with temp SQLite store."""
    db_file = str(tmp_path / "test_shipyard.db")
    os.environ["SHIPYARD_DB_PATH"] = db_file

    import importlib
    import server.main as main_module
    importlib.reload(main_module)
    from server.main import app

    store = SQLiteSessionStore(db_file)
    await store.initialize()
    event_bus = EventBus(store)
    conn_manager = ConnectionManager(event_bus)
    app.state.store = store
    app.state.router = ModelRouter()
    app.state.event_bus = event_bus
    app.state.conn_manager = conn_manager

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await event_bus.shutdown()
    await store.close()


# ---------------------------------------------------------------------------
# share_trace_link tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_share_trace_link_success():
    """share_trace_link returns a public URL when LangSmith run is found."""
    mock_run = MagicMock()
    mock_run.id = "ls-run-uuid-123"

    mock_client = MagicMock()
    mock_client.list_runs.return_value = [mock_run]
    mock_client.share_run.return_value = "https://smith.langchain.com/public/abc123"

    with patch.dict(os.environ, {"LANGCHAIN_API_KEY": "test-key"}):
        with patch("agent.tracing.Client", return_value=mock_client):
            from agent.tracing import share_trace_link
            url = await share_trace_link("test-run-id")

    assert url == "https://smith.langchain.com/public/abc123"
    mock_client.share_run.assert_called_once_with(mock_run.id)


@pytest.mark.asyncio
async def test_share_trace_link_no_api_key():
    """share_trace_link returns None when LANGCHAIN_API_KEY is not set."""
    env = {k: v for k, v in os.environ.items() if k != "LANGCHAIN_API_KEY"}
    with patch.dict(os.environ, env, clear=True):
        from agent.tracing import share_trace_link
        url = await share_trace_link("test-run-id")

    assert url is None


@pytest.mark.asyncio
async def test_share_trace_link_exception():
    """share_trace_link returns None when Client raises an exception."""
    mock_client = MagicMock()
    mock_client.list_runs.side_effect = Exception("LangSmith API error")

    with patch.dict(os.environ, {"LANGCHAIN_API_KEY": "test-key"}):
        with patch("agent.tracing.Client", return_value=mock_client):
            from agent.tracing import share_trace_link
            url = await share_trace_link("test-run-id")

    assert url is None


# ---------------------------------------------------------------------------
# /status endpoint trace_url test
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# TraceLogger unified format tests
# ---------------------------------------------------------------------------

class TestTraceLoggerUnifiedFormat:
    """Tests for TraceLogger unified structured logging format."""

    def test_log_backward_compat(self, tmp_path):
        """log(node, data) without new params produces entry with defaults."""
        from agent.tracing import TraceLogger
        t = TraceLogger(trace_dir=str(tmp_path))
        t.start_run("run-1")
        t.log("my_node", {"k": "v"})
        entries = t.get_entries()
        assert len(entries) == 1
        e = entries[0]
        assert e["agent_id"] is None
        assert e["task_id"] is None
        assert e["severity"] == "info"
        assert e["node"] == "my_node"
        assert e["data"] == {"k": "v"}

    def test_log_unified_format(self, tmp_path):
        """log() with all new kwargs produces entry with correct values."""
        from agent.tracing import TraceLogger
        t = TraceLogger(trace_dir=str(tmp_path))
        t.start_run("run-1")
        t.log("editor", {"action": "edit"}, agent_id="agent-1", task_id="task-1", severity="error")
        entries = t.get_entries()
        assert len(entries) == 1
        e = entries[0]
        assert e["agent_id"] == "agent-1"
        assert e["task_id"] == "task-1"
        assert e["severity"] == "error"

    def test_log_default_severity(self, tmp_path):
        """Default severity is 'info'."""
        from agent.tracing import TraceLogger
        t = TraceLogger(trace_dir=str(tmp_path))
        t.start_run("run-1")
        t.log("node", {})
        assert t.get_entries()[0]["severity"] == "info"

    def test_filter_by_severity(self, tmp_path):
        """filter_entries(severity='error') returns only error-level entries."""
        from agent.tracing import TraceLogger
        t = TraceLogger(trace_dir=str(tmp_path))
        t.start_run("run-1")
        t.log("n1", {}, severity="info")
        t.log("n2", {}, severity="error")
        t.log("n3", {}, severity="warn")
        result = t.filter_entries(severity="error")
        assert len(result) == 1
        assert result[0]["node"] == "n2"

    def test_filter_by_agent_id(self, tmp_path):
        """filter_entries(agent_id='agent-1') returns only that agent's entries."""
        from agent.tracing import TraceLogger
        t = TraceLogger(trace_dir=str(tmp_path))
        t.start_run("run-1")
        t.log("n1", {}, agent_id="agent-1")
        t.log("n2", {}, agent_id="agent-2")
        t.log("n3", {}, agent_id="agent-1")
        result = t.filter_entries(agent_id="agent-1")
        assert len(result) == 2
        assert all(e["agent_id"] == "agent-1" for e in result)

    def test_filter_combined(self, tmp_path):
        """filter_entries with task_id + severity returns intersection."""
        from agent.tracing import TraceLogger
        t = TraceLogger(trace_dir=str(tmp_path))
        t.start_run("run-1")
        t.log("n1", {}, task_id="task-1", severity="warn")
        t.log("n2", {}, task_id="task-1", severity="error")
        t.log("n3", {}, task_id="task-2", severity="warn")
        result = t.filter_entries(task_id="task-1", severity="warn")
        assert len(result) == 1
        assert result[0]["node"] == "n1"

    def test_save_includes_unified_fields(self, tmp_path):
        """save() writes JSON with agent_id, task_id, severity in each entry."""
        import json
        from agent.tracing import TraceLogger
        t = TraceLogger(trace_dir=str(tmp_path))
        t.start_run("run-save-test")
        t.log("editor", {"x": 1}, agent_id="a1", task_id="t1", severity="warn")
        t.save()
        path = tmp_path / "run-save-test.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data) == 1
        e = data[0]
        assert e["agent_id"] == "a1"
        assert e["task_id"] == "t1"
        assert e["severity"] == "warn"


# ---------------------------------------------------------------------------
# /status endpoint trace_url test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_includes_trace_url(client):
    """GET /status/{run_id} includes trace_url field."""
    import server.main as main_module
    main_module.runs["test-run-1"] = {
        "status": "completed",
        "result": {"instruction": "test"},
        "trace_url": "https://smith.langchain.com/public/abc123",
    }

    resp = await client.get("/status/test-run-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["trace_url"] == "https://smith.langchain.com/public/abc123"
