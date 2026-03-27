#!/usr/bin/env python3
"""Orchestrates the Ship rebuild by sending graduated instructions to the Shipyard agent.

Sends a predefined sequence of natural-language instructions to the running
Shipyard agent via its REST API, polls each to completion, and logs every
outcome to SHIP-REBUILD-LOG.md.  Supports --dry-run to preview the
instruction list and --start-from to resume after a failure.

Usage:
    python scripts/rebuild_orchestrator.py --dry-run
    python scripts/rebuild_orchestrator.py --project-id ship
    python scripts/rebuild_orchestrator.py --start-from 3 --timeout 600
"""

import argparse
import asyncio
import os
import re
import sys
import time

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Instruction set — graduated from simple to complex
# ---------------------------------------------------------------------------

INSTRUCTIONS: list[dict] = [
    {
        "label": "Add status field to Document",
        "instruction": (
            "Add a 'status' field of type string to the Document interface in "
            "src/types/index.ts. It should accept values 'draft', 'published', "
            "or 'archived'."
        ),
        "expected_files": ["src/types/index.ts"],
    },
    {
        "label": "Add GET /ready health endpoint",
        "instruction": (
            "Add a GET /ready endpoint to src/routes/health.ts that returns "
            "{ status: 'ready', uptime: process.uptime() }."
        ),
        "expected_files": ["src/routes/health.ts"],
    },
    {
        "label": "Add documents CRUD routes",
        "instruction": (
            "Add a new route file src/routes/documents.ts with GET /documents "
            "(returns all documents) and GET /documents/:id (returns one document "
            "or 404). Use the findAll and findById functions from "
            "src/models/document.ts. Register the router in the main app."
        ),
        "expected_files": [
            "src/routes/documents.ts",
            "src/app.ts",
        ],
    },
    {
        "label": "Add tags field and filter",
        "instruction": (
            "Add a 'tags' field (string array) to the Document interface, "
            "update the create function in src/models/document.ts to accept "
            "tags, and add a DocumentList filter that only shows documents "
            "matching a selected tag."
        ),
        "expected_files": [
            "src/types/index.ts",
            "src/models/document.ts",
            "src/components/DocumentList.tsx",
        ],
    },
    {
        "label": "Parallel: priority field + DELETE endpoint",
        "instruction": (
            "In parallel: (1) Add a 'priority' field to Document interface with "
            "values 'low', 'medium', 'high' and (2) Add a DELETE /documents/:id "
            "endpoint to src/routes/documents.ts."
        ),
        "expected_files": [
            "src/types/index.ts",
            "src/routes/documents.ts",
        ],
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MAX_RETRIES = 3
RETRY_BACKOFF = 5  # seconds

TERMINAL_STATUSES = {"completed", "failed", "error", "cancelled"}


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _default_working_dir() -> str:
    return os.path.join(_repo_root(), "ship-rebuild")


# ---------------------------------------------------------------------------
# Core async functions
# ---------------------------------------------------------------------------


async def send_instruction(
    client: httpx.AsyncClient,
    host: str,
    instruction: str,
    working_dir: str,
    project_id: str | None,
) -> str:
    """POST /instruction and return the run_id."""
    payload = {
        "instruction": instruction,
        "working_directory": working_dir,
    }
    if project_id:
        payload["project_id"] = project_id

    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = await client.post(f"{host}/instruction", json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data["run_id"]
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                print(f"  [retry {attempt}/{MAX_RETRIES}] {exc!r} — retrying in {RETRY_BACKOFF}s")
                await asyncio.sleep(RETRY_BACKOFF)

    raise ConnectionError(
        f"Failed to send instruction after {MAX_RETRIES} attempts: {last_exc!r}"
    )


async def poll_status(
    client: httpx.AsyncClient,
    host: str,
    run_id: str,
    timeout: int = 300,
    interval: int = 3,
) -> dict:
    """Poll GET /status/{run_id} until a terminal status is reached.

    Returns the final status dict.  Raises TimeoutError if *timeout* seconds
    elapse without reaching a terminal state.
    """
    deadline = time.monotonic() + timeout
    while True:
        if time.monotonic() > deadline:
            raise TimeoutError(
                f"Run {run_id} did not complete within {timeout}s"
            )
        try:
            resp = await client.get(f"{host}/status/{run_id}", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status", "unknown")
            if status in TERMINAL_STATUSES:
                return data
        except (httpx.ConnectError, httpx.TimeoutException):
            pass  # transient — keep polling

        await asyncio.sleep(interval)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def log_result(
    log_path: str,
    index: int,
    label: str,
    instruction: str,
    status: str,
    duration: float,
    trace_url: str | None,
) -> None:
    """Append an entry to the Instructions Log table in SHIP-REBUILD-LOG.md.

    If the status is failed/error, also appends an intervention template to
    the Interventions section.
    """
    if log_path == "/dev/null":
        return

    needs_intervention = "Yes" if status in ("failed", "error") else "No"
    notes = trace_url or ""
    row = f"| {index} | {label} | {status} | {duration:.0f}s | {needs_intervention} | {notes} |"

    try:
        content = open(log_path, "r").read()
    except FileNotFoundError:
        print(f"  WARNING: log file {log_path} not found — skipping log entry")
        return

    # Replace the placeholder first-row if it still exists
    placeholder = "| 1 | —           | —      | —        | —             | —     |"
    if placeholder in content:
        content = content.replace(placeholder, row)
    else:
        # Append after the last row in the Instructions Log table
        table_pattern = r"(\| *# *\| *Instruction *\|.*\n\|[-| ]+\n(?:\|.*\n)*)"
        match = re.search(table_pattern, content)
        if match:
            content = content[: match.end()] + row + "\n" + content[match.end() :]
        else:
            # Fallback: append at end
            content += "\n" + row + "\n"

    # Add intervention template for failures
    if status in ("failed", "error"):
        intervention_block = (
            f"\n### Intervention (Instruction {index})\n\n"
            f"- **Instruction #:** {index}\n"
            f"- **What Broke:** {status} — see trace: {trace_url or 'N/A'}\n"
            f"- **What Was Done Manually:** TODO\n"
            f"- **Root Cause:** TODO\n"
            f"- **What It Reveals:** TODO\n"
            f"- **Time Spent:** TODO\n"
        )
        # Insert before "## Agent Limitation Categories"
        marker = "## Agent Limitation Categories"
        if marker in content:
            content = content.replace(marker, intervention_block + "\n" + marker)
        else:
            content += intervention_block

    with open(log_path, "w") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# Main orchestration loop
# ---------------------------------------------------------------------------


async def run_rebuild(
    host: str,
    working_dir: str,
    project_id: str | None,
    dry_run: bool,
    start_from: int,
    log_path: str,
    timeout: int,
) -> None:
    """Send each instruction to the agent, poll for results, and log outcomes."""
    total = len(INSTRUCTIONS)
    succeeded = 0
    failed = 0
    interventions = 0

    print(f"Ship Rebuild Orchestrator — {total} instructions")
    print(f"  Host: {host}")
    print(f"  Working dir: {working_dir}")
    print(f"  Project ID: {project_id or '(default)'}")
    print(f"  Log: {log_path}")
    print(f"  Timeout per instruction: {timeout}s")
    if dry_run:
        print("  MODE: DRY RUN (no HTTP calls)")
    print()

    for idx_0, entry in enumerate(INSTRUCTIONS):
        idx = idx_0 + 1  # 1-based
        if idx < start_from:
            print(f"[{idx}/{total}] SKIP (start-from={start_from}): {entry['label']}")
            continue

        print(f"[{idx}/{total}] {entry['label']}")
        print(f"  Instruction: {entry['instruction'][:100]}...")
        print(f"  Expected files: {', '.join(entry['expected_files'])}")

        if dry_run:
            print("  -> dry-run, skipping\n")
            continue

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient() as client:
                run_id = await send_instruction(
                    client, host, entry["instruction"], working_dir, project_id
                )
                print(f"  -> run_id: {run_id}")

                result = await poll_status(client, host, run_id, timeout=timeout)
                duration = time.monotonic() - t0
                status = result.get("status", "unknown")
                trace_url = result.get("trace_url")
                print(f"  -> status: {status} ({duration:.1f}s)")

                if status == "completed":
                    succeeded += 1
                else:
                    failed += 1
                    if status in ("failed", "error"):
                        interventions += 1

                log_result(log_path, idx, entry["label"], entry["instruction"],
                           status, duration, trace_url)

        except (ConnectionError, TimeoutError) as exc:
            duration = time.monotonic() - t0
            print(f"  -> ERROR: {exc}")
            failed += 1
            interventions += 1
            log_result(log_path, idx, entry["label"], entry["instruction"],
                       "error", duration, None)

        print()

    # Summary
    print("=" * 60)
    print("REBUILD SUMMARY")
    print(f"  Total:         {total}")
    print(f"  Succeeded:     {succeeded}")
    print(f"  Failed:        {failed}")
    print(f"  Interventions: {interventions}")
    if succeeded + failed > 0:
        print(f"  Success rate:  {succeeded / (succeeded + failed) * 100:.0f}%")
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Orchestrate the Ship rebuild via the Shipyard agent API"
    )
    parser.add_argument(
        "--host",
        default="http://localhost:8000",
        help="Shipyard API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--working-dir",
        default=_default_working_dir(),
        help="Working directory for the agent (default: ship-rebuild/)",
    )
    parser.add_argument(
        "--project-id",
        default=None,
        help="Shipyard project ID (default: use 'default')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview instructions without sending HTTP calls",
    )
    parser.add_argument(
        "--start-from",
        type=int,
        default=1,
        help="Resume from instruction N (1-based, default: 1)",
    )
    parser.add_argument(
        "--log-path",
        default=os.path.join(_repo_root(), "SHIP-REBUILD-LOG.md"),
        help="Path to rebuild log markdown file",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout per instruction in seconds (default: 300)",
    )
    args = parser.parse_args()

    if not args.dry_run and httpx is None:
        print("ERROR: httpx is required. Install with: pip install httpx", file=sys.stderr)
        sys.exit(1)

    asyncio.run(
        run_rebuild(
            host=args.host,
            working_dir=args.working_dir,
            project_id=args.project_id,
            dry_run=args.dry_run,
            start_from=args.start_from,
            log_path=args.log_path,
            timeout=args.timeout,
        )
    )


if __name__ == "__main__":
    main()
