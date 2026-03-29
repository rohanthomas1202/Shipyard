"""SQLite persistence layer for DAG state -- crash recovery and resume."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import aiosqlite

from agent.orchestrator.dag import TaskDAG
from agent.orchestrator.models import DAGRun, TaskEdge, TaskExecution


_DAG_SCHEMA = """
CREATE TABLE IF NOT EXISTS dag_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    status TEXT DEFAULT 'pending',
    max_concurrency INTEGER DEFAULT 10,
    total_tasks INTEGER DEFAULT 0,
    completed_tasks INTEGER DEFAULT 0,
    failed_tasks INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_nodes (
    id TEXT PRIMARY KEY,
    dag_id TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    task_type TEXT DEFAULT 'agent',
    contract_inputs TEXT,
    contract_outputs TEXT,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_task_nodes_dag ON task_nodes(dag_id);

CREATE TABLE IF NOT EXISTS task_edges (
    id TEXT PRIMARY KEY,
    dag_id TEXT NOT NULL,
    from_task TEXT NOT NULL,
    to_task TEXT NOT NULL,
    UNIQUE(dag_id, from_task, to_task)
);
CREATE INDEX IF NOT EXISTS idx_task_edges_dag ON task_edges(dag_id);

CREATE TABLE IF NOT EXISTS task_executions (
    id TEXT PRIMARY KEY,
    dag_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    attempt INTEGER DEFAULT 1,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    result_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_task_exec_dag ON task_executions(dag_id);
CREATE INDEX IF NOT EXISTS idx_task_exec_status ON task_executions(dag_id, status);
"""


_MIGRATION_V2_COLUMNS = [
    "ALTER TABLE task_executions ADD COLUMN retry_count INTEGER DEFAULT 0",
    "ALTER TABLE task_executions ADD COLUMN failure_type TEXT",
    "ALTER TABLE task_executions ADD COLUMN branch_name TEXT",
]


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class DAGPersistence:
    """Persist and recover DAG execution state from SQLite.

    Handles save/load of TaskDAG + DAGRun, task status updates,
    and crash recovery (marking interrupted tasks as failed).
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Open database connection and ensure schema exists."""
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_DAG_SCHEMA)
        # Run V2 migration: add retry/CI columns (safe to re-run)
        for stmt in _MIGRATION_V2_COLUMNS:
            try:
                await self._db.execute(stmt)
            except Exception:
                # Column already exists -- ignore "duplicate column name" errors
                pass
        await self._db.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    async def save_dag(self, dag: TaskDAG, dag_run: DAGRun) -> None:
        """Persist a full DAG (run, nodes, edges, executions) to SQLite."""
        assert self._db is not None

        # Insert dag_run
        await self._db.execute(
            """INSERT INTO dag_runs
               (id, project_id, status, max_concurrency, total_tasks,
                completed_tasks, failed_tasks, created_at, started_at, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                dag_run.id, dag_run.project_id, dag_run.status,
                dag_run.max_concurrency, dag_run.total_tasks,
                dag_run.completed_tasks, dag_run.failed_tasks,
                dag_run.created_at.isoformat(),
                dag_run.started_at.isoformat() if dag_run.started_at else None,
                dag_run.completed_at.isoformat() if dag_run.completed_at else None,
            ),
        )

        # Insert task_nodes
        for task_id in dag._graph.nodes:
            task = dag.get_task(task_id)
            if task is None:
                continue
            await self._db.execute(
                """INSERT INTO task_nodes
                   (id, dag_id, label, description, task_type,
                    contract_inputs, contract_outputs, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task.id, dag.dag_id, task.label, task.description,
                    task.task_type,
                    json.dumps(task.contract_inputs),
                    json.dumps(task.contract_outputs),
                    json.dumps(task.metadata),
                    task.created_at.isoformat(),
                ),
            )

        # Insert task_edges
        for from_task, to_task in dag._graph.edges:
            edge_id = _new_id()
            await self._db.execute(
                """INSERT INTO task_edges (id, dag_id, from_task, to_task)
                   VALUES (?, ?, ?, ?)""",
                (edge_id, dag.dag_id, from_task, to_task),
            )

        # Insert task_executions (one per task, status="pending")
        for task_id in dag._graph.nodes:
            exec_id = _new_id()
            await self._db.execute(
                """INSERT INTO task_executions
                   (id, dag_id, task_id, status, attempt, created_at)
                   VALUES (?, ?, ?, 'pending', 1, ?)""",
                (exec_id, dag.dag_id, task_id,
                 datetime.now(timezone.utc).isoformat()),
            )

        await self._db.commit()

    async def load_dag(self, dag_id: str) -> tuple[TaskDAG, DAGRun] | None:
        """Load a DAG and its run state from SQLite. Returns None if not found."""
        assert self._db is not None

        # Load dag_run
        async with self._db.execute(
            "SELECT * FROM dag_runs WHERE id = ?", (dag_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None

        data = dict(row)
        dag_run = DAGRun(
            id=data["id"],
            project_id=data["project_id"] or "",
            status=data["status"] or "pending",
            max_concurrency=data["max_concurrency"] or 10,
            total_tasks=data["total_tasks"] or 0,
            completed_tasks=data["completed_tasks"] or 0,
            failed_tasks=data["failed_tasks"] or 0,
        )

        # Load task_nodes
        dag = TaskDAG(dag_id=dag_id)
        async with self._db.execute(
            "SELECT * FROM task_nodes WHERE dag_id = ?", (dag_id,)
        ) as cursor:
            nodes = await cursor.fetchall()

        for node_row in nodes:
            nd = dict(node_row)
            dag.add_task(
                nd["id"],
                label=nd["label"] or "",
                description=nd["description"],
                task_type=nd["task_type"] or "agent",
                contract_inputs=json.loads(nd["contract_inputs"]) if nd["contract_inputs"] else [],
                contract_outputs=json.loads(nd["contract_outputs"]) if nd["contract_outputs"] else [],
                metadata=json.loads(nd["metadata"]) if nd["metadata"] else {},
            )

        # Load task_edges
        async with self._db.execute(
            "SELECT * FROM task_edges WHERE dag_id = ?", (dag_id,)
        ) as cursor:
            edges = await cursor.fetchall()

        for edge_row in edges:
            ed = dict(edge_row)
            dag.add_dependency(ed["from_task"], ed["to_task"])

        return dag, dag_run

    async def update_task_status(
        self,
        dag_id: str,
        task_id: str,
        status: str,
        error_message: str | None = None,
        result_summary: dict | None = None,
        retry_count: int | None = None,
        failure_type: str | None = None,
        branch_name: str | None = None,
    ) -> None:
        """Update a task execution's status and timestamps."""
        assert self._db is not None

        now = datetime.now(timezone.utc).isoformat()

        # Build dynamic SET clause for optional new fields
        extra_sets: list[str] = []
        extra_params: list = []
        if retry_count is not None:
            extra_sets.append("retry_count = ?")
            extra_params.append(retry_count)
        if failure_type is not None:
            extra_sets.append("failure_type = ?")
            extra_params.append(failure_type)
        if branch_name is not None:
            extra_sets.append("branch_name = ?")
            extra_params.append(branch_name)
        extra_clause = (", " + ", ".join(extra_sets)) if extra_sets else ""

        # Update started_at when transitioning to running
        if status == "running":
            await self._db.execute(
                f"""UPDATE task_executions
                   SET status = ?, started_at = ?{extra_clause}
                   WHERE dag_id = ? AND task_id = ?""",
                (status, now, *extra_params, dag_id, task_id),
            )
        elif status in ("completed", "failed"):
            await self._db.execute(
                f"""UPDATE task_executions
                   SET status = ?, completed_at = ?, error_message = ?,
                       result_summary = ?{extra_clause}
                   WHERE dag_id = ? AND task_id = ?""",
                (
                    status, now, error_message,
                    json.dumps(result_summary) if result_summary else None,
                    *extra_params, dag_id, task_id,
                ),
            )
        else:
            await self._db.execute(
                f"""UPDATE task_executions
                   SET status = ?{extra_clause}
                   WHERE dag_id = ? AND task_id = ?""",
                (status, *extra_params, dag_id, task_id),
            )

        # Update dag_runs counters
        if status == "completed":
            await self._db.execute(
                """UPDATE dag_runs SET completed_tasks = completed_tasks + 1
                   WHERE id = ?""",
                (dag_id,),
            )
        elif status == "failed":
            await self._db.execute(
                """UPDATE dag_runs SET failed_tasks = failed_tasks + 1
                   WHERE id = ?""",
                (dag_id,),
            )

        await self._db.commit()

    async def update_dag_status(self, dag_id: str, status: str) -> None:
        """Update the overall DAG run status."""
        assert self._db is not None

        now = datetime.now(timezone.utc).isoformat()
        if status == "running":
            await self._db.execute(
                "UPDATE dag_runs SET status = ?, started_at = ? WHERE id = ?",
                (status, now, dag_id),
            )
        elif status in ("completed", "failed"):
            await self._db.execute(
                "UPDATE dag_runs SET status = ?, completed_at = ? WHERE id = ?",
                (status, now, dag_id),
            )
        else:
            await self._db.execute(
                "UPDATE dag_runs SET status = ? WHERE id = ?",
                (status, dag_id),
            )
        await self._db.commit()

    async def load_completed_tasks(self, dag_id: str) -> set[str]:
        """Return task IDs that have completed for a given DAG."""
        assert self._db is not None

        async with self._db.execute(
            "SELECT task_id FROM task_executions WHERE dag_id = ? AND status = 'completed'",
            (dag_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        return {dict(row)["task_id"] for row in rows}

    async def load_failed_tasks(self, dag_id: str) -> set[str]:
        """Return task IDs that have failed for a given DAG."""
        assert self._db is not None

        async with self._db.execute(
            "SELECT task_id FROM task_executions WHERE dag_id = ? AND status = 'failed'",
            (dag_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        return {dict(row)["task_id"] for row in rows}

    async def mark_interrupted(self, dag_id: str) -> int:
        """Mark all 'running' task executions as 'failed' (crash recovery).

        Returns the number of tasks marked as interrupted.
        """
        assert self._db is not None

        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._db.execute(
            """UPDATE task_executions
               SET status = 'failed', completed_at = ?,
                   error_message = 'interrupted: process crash recovery'
               WHERE dag_id = ? AND status = 'running'""",
            (now, dag_id),
        )
        count = cursor.rowcount
        await self._db.commit()
        return count
