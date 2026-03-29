"""Async DAG-aware task scheduler with dependency enforcement and crash recovery."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from store.models import Event
from agent.orchestrator.dag import TaskDAG
from agent.orchestrator.models import DAGRun, TaskNode, _new_id
from agent.orchestrator.events import (
    TASK_STARTED,
    TASK_COMPLETED,
    TASK_FAILED,
    DAG_STARTED,
    DAG_COMPLETED,
    DAG_FAILED,
    PROGRESS_UPDATE,
)

logger = logging.getLogger(__name__)


class DAGScheduler:
    """Execute a TaskDAG respecting dependencies and concurrency limits.

    Features:
    - Dependency enforcement via TaskDAG.get_ready_tasks()
    - Concurrency control via asyncio.Semaphore
    - SQLite persistence on every status transition (crash recovery)
    - EventBus integration for task lifecycle events
    - Event-driven wake (no polling) via asyncio.Event
    """

    def __init__(
        self,
        dag: TaskDAG,
        dag_run: DAGRun,
        *,
        persistence: Any | None = None,
        event_bus: Any | None = None,
        task_executor: Callable[[str, TaskNode], Awaitable[dict]] | None = None,
        max_concurrency: int = 10,
    ) -> None:
        self._dag = dag
        self._dag_run = dag_run
        self._persistence = persistence
        self._event_bus = event_bus
        self._task_executor = task_executor or self._default_executor
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._completed: set[str] = set()
        self._failed: set[str] = set()
        self._running: set[str] = set()
        self._progress_event = asyncio.Event()

    async def run(self) -> dict[str, str]:
        """Main scheduling loop. Returns {task_id: final_status} map."""
        # Crash recovery: mark interrupted tasks as failed
        if self._persistence is not None:
            interrupted = await self._persistence.mark_interrupted(self._dag_run.id)
            if interrupted > 0:
                logger.info(
                    "Crash recovery: marked %d interrupted tasks as failed",
                    interrupted,
                )

            # Load completed and failed tasks from persistence
            self._completed = await self._persistence.load_completed_tasks(self._dag_run.id)
            self._failed = await self._persistence.load_failed_tasks(self._dag_run.id)

        # Emit dag_started
        await self._emit(DAG_STARTED)
        await self._emit_progress()  # initial 0% progress

        # Main scheduling loop
        while True:
            # Find tasks ready to run (predecessors completed, not running/completed/failed)
            # Only completed predecessors unlock downstream tasks -- failed ones do not
            ready = self._dag.get_ready_tasks(self._completed)
            ready = [
                t for t in ready
                if t not in self._running and t not in self._failed
            ]

            if not ready and not self._running:
                # Nothing more can run -- either all done or blocked by failures
                break

            # Launch ready tasks
            for task_id in ready:
                self._running.add(task_id)
                asyncio.create_task(self._run_task(task_id))

            # Wait for at least one task to finish
            if self._running:
                self._progress_event.clear()
                await self._progress_event.wait()

        # Determine final status
        all_tasks = set(self._dag._graph.nodes)
        has_failures = len(self._failed) > 0
        all_done = self._completed == all_tasks

        if all_done:
            await self._emit(DAG_COMPLETED)
        else:
            await self._emit(DAG_FAILED)

        # Build result map
        result: dict[str, str] = {}
        for task_id in all_tasks:
            if task_id in self._completed:
                result[task_id] = "completed"
            elif task_id in self._failed:
                result[task_id] = "failed"
            else:
                result[task_id] = "pending"

        return result

    async def _run_task(self, task_id: str) -> None:
        """Execute a single task with semaphore-based concurrency control."""
        async with self._semaphore:
            task = self._dag.get_task(task_id)

            # Emit task_started and persist
            await self._emit(TASK_STARTED, task_id=task_id)
            if self._persistence is not None:
                await self._persistence.update_task_status(
                    self._dag_run.id, task_id, "running",
                )

            try:
                result = await self._task_executor(task_id, task)

                # Success
                if self._persistence is not None:
                    await self._persistence.update_task_status(
                        self._dag_run.id, task_id, "completed",
                        result_summary=result,
                    )
                self._completed.add(task_id)
                await self._emit(TASK_COMPLETED, task_id=task_id, data=result)
                await self._emit_progress()

            except Exception as exc:
                # Failure
                error_msg = str(exc)
                if self._persistence is not None:
                    await self._persistence.update_task_status(
                        self._dag_run.id, task_id, "failed",
                        error_message=error_msg,
                    )
                self._failed.add(task_id)
                await self._emit(TASK_FAILED, task_id=task_id, data={"error": error_msg})
                await self._emit_progress()
                logger.warning("Task %s failed: %s", task_id, error_msg)

            finally:
                self._running.discard(task_id)
                self._progress_event.set()

    async def _default_executor(self, task_id: str, task: TaskNode) -> dict:
        """No-op executor used in tests."""
        return {"success": True}

    async def _emit_progress(self) -> None:
        """Emit progress metrics after task state changes."""
        total = self._dag_run.total_tasks
        completed = len(self._completed)
        failed = len(self._failed)
        running = len(self._running)
        coverage = round((completed / total * 100), 1) if total > 0 else 0.0
        ci_pass_rate = round(
            (completed / (completed + failed) * 100), 1
        ) if (completed + failed) > 0 else 100.0

        await self._emit(PROGRESS_UPDATE, data={
            "total_tasks": total,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "running_tasks": running,
            "coverage_pct": coverage,
            "ci_pass_rate": ci_pass_rate,
        })

    async def _emit(
        self,
        event_type: str,
        task_id: str | None = None,
        data: dict | None = None,
    ) -> None:
        """Emit an event through the EventBus if available."""
        if self._event_bus is None:
            return

        event_data = data or {}
        if task_id is not None:
            event_data["task_id"] = task_id
        event_data["dag_id"] = self._dag_run.id

        event = Event(
            id=_new_id(),
            project_id=self._dag_run.project_id,
            run_id=self._dag_run.id,
            type=event_type,
            data=event_data,
        )
        await self._event_bus.emit(event)
