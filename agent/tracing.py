"""Tracing utilities: local JSON trace logger and LangSmith shared link generation."""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone

from langsmith import Client

logger = logging.getLogger(__name__)


async def share_trace_link(run_id: str, metadata_filter: dict | None = None) -> str | None:
    """Generate a public LangSmith shared trace link for a run.

    Uses the Shipyard run_id as a tag to find the corresponding
    LangSmith trace, then shares it publicly.

    Returns the public URL or None if tracing is unavailable.
    """
    if not os.environ.get("LANGCHAIN_API_KEY"):
        return None

    try:
        client = Client()
        project_name = os.environ.get("LANGCHAIN_PROJECT", "default")

        loop = asyncio.get_event_loop()

        # Find LangSmith run by tag
        ls_runs = await loop.run_in_executor(
            None,
            lambda: list(client.list_runs(
                project_name=project_name,
                filter=f'has(tags, "run_id:{run_id}")',
                limit=5,
            )),
        )

        if not ls_runs:
            logger.warning("No LangSmith run found with tag run_id:%s", run_id)
            return None

        ls_run = ls_runs[0]
        shared_url = await loop.run_in_executor(
            None,
            lambda: client.share_run(ls_run.id),
        )
        return str(shared_url) if shared_url else None

    except Exception:
        logger.warning("Failed to generate LangSmith trace link for run %s", run_id, exc_info=True)
        return None


class TraceLogger:
    def __init__(self, trace_dir: str = "traces"):
        self.trace_dir = trace_dir
        os.makedirs(trace_dir, exist_ok=True)
        self.run_id: str | None = None
        self.entries: list[dict] = []

    def start_run(self, run_id: str):
        self.run_id = run_id
        self.entries = []

    def log(self, node: str, data: dict):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "node": node,
            "data": data,
        }
        self.entries.append(entry)

    def save(self):
        if not self.run_id:
            return
        path = os.path.join(self.trace_dir, f"{self.run_id}.json")
        with open(path, "w") as f:
            json.dump(self.entries, f, indent=2)

    def get_entries(self) -> list[dict]:
        return self.entries
