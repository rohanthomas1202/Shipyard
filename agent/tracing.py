import json
import os
from datetime import datetime, timezone

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
