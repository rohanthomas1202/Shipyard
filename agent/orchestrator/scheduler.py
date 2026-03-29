"""Async DAG-aware task scheduler with dependency enforcement and crash recovery."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from store.models import Event
from agent.orchestrator.dag import TaskDAG
from agent.orchestrator.models import DAGRun, TaskNode, MAX_TOTAL_RETRIES, _new_id
from agent.orchestrator.events import (
    TASK_STARTED,
    TASK_COMPLETED,
    TASK_FAILED,
    DAG_STARTED,
    DAG_COMPLETED,
    DAG_FAILED,
    PROGRESS_UPDATE,
    DECISION_TRACE,
    CI_STARTED,
    CI_PASSED,
    CI_FAILED,
    OWNERSHIP_VIOLATION,
    TASK_REQUEUED,
)
from agent.orchestrator.metrics import build_decision_trace
from agent.orchestrator.branch_manager import BranchManager
from agent.orchestrator.ci_runner import CIRunner, CIPipelineResult
from agent.orchestrator.failure_classifier import FailureClassifier, RETRY_BUDGETS
from agent.orchestrator.context_packs import ContextPackAssembler
from agent.orchestrator.ownership import OwnershipValidator

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
        project_path: str | None = None,
        branch_manager: BranchManager | None = None,
        ci_runner: CIRunner | None = None,
        failure_classifier: FailureClassifier | None = None,
        context_assembler: ContextPackAssembler | None = None,
        ownership_validator: OwnershipValidator | None = None,
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
        self._project_path = project_path
        self._branch_manager = branch_manager
        self._ci_runner = ci_runner
        self._failure_classifier = failure_classifier
        self._context_assembler = context_assembler
        self._ownership_validator = ownership_validator
        self._retry_counts: dict[str, int] = {}
        self._failure_types: dict[str, str] = {}

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
        """Execute a single task with branch isolation, CI gating, and retry.

        Pipeline: branch-create -> context-pack -> execute -> ownership check
        -> CI -> rebase+merge -> cleanup. When branch_manager/ci_runner/etc
        are None, the corresponding step is skipped (backward compatible).
        """
        async with self._semaphore:
            task = self._dag.get_task(task_id)
            branch_name = f"agent/task-{task_id}"

            await self._emit(TASK_STARTED, task_id=task_id)
            if self._persistence is not None:
                await self._persistence.update_task_status(
                    self._dag_run.id, task_id, "running",
                    branch_name=branch_name,
                )

            try:
                # 1. Create branch (if branch_manager available)
                if self._branch_manager is not None:
                    ok = await self._branch_manager.create_and_checkout(branch_name)
                    if not ok:
                        raise RuntimeError(f"Failed to create branch {branch_name}")

                # 2. Assemble context pack and attach to task metadata (per EXEC-02)
                if self._context_assembler is not None:
                    context_pack = self._context_assembler.assemble(task)
                    task.metadata["context_pack"] = context_pack

                # 3. Execute task (executor reads context from task.metadata["context_pack"])
                result = await self._task_executor(task_id, task)

                # 4. Validate ownership (if validator available)
                if self._ownership_validator is not None:
                    module_name = task.metadata.get("module", task.label)
                    violations = await self._ownership_validator.validate(task_id, module_name)
                    if violations:
                        violation_msg = "; ".join(v.reason for v in violations)
                        await self._emit(OWNERSHIP_VIOLATION, task_id=task_id, data={
                            "violations": [
                                {"file": v.file_path, "owner": v.owning_module, "task_module": v.task_module}
                                for v in violations
                            ],
                        })
                        raise RuntimeError(f"Ownership violations: {violation_msg}")

                # 5. Run CI (if ci_runner available)
                if self._ci_runner is not None:
                    await self._emit(CI_STARTED, task_id=task_id)
                    ci_result = await self._ci_runner.run_pipeline()

                    if ci_result.passed:
                        await self._emit(CI_PASSED, task_id=task_id)
                    else:
                        await self._emit(CI_FAILED, task_id=task_id, data={
                            "stage": ci_result.first_failure.name if ci_result.first_failure else "unknown",
                            "error": ci_result.error_output[:500],
                        })
                        raise RuntimeError(
                            f"CI failed: {ci_result.error_output[:200]}"
                        )

                # 6. Rebase and merge (if branch_manager available)
                if self._branch_manager is not None:
                    merged = await self._branch_manager.rebase_and_merge(branch_name)
                    if not merged:
                        # Merge conflict -- requeue per D-03
                        await self._handle_requeue(task_id, "Merge conflict during rebase")
                        return

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
                error_msg = str(exc)
                await self._handle_failure(task_id, error_msg)

            finally:
                self._running.discard(task_id)
                # Always clean up branch
                if self._branch_manager is not None:
                    await self._branch_manager.cleanup(branch_name)
                self._progress_event.set()

    async def _handle_failure(self, task_id: str, error_msg: str) -> None:
        """Classify failure and retry or fail permanently."""
        # Classify
        category = "structural"
        if self._failure_classifier is not None:
            category = await self._failure_classifier.classify(error_msg)

        self._failure_types[task_id] = category
        current_retries = self._retry_counts.get(task_id, 0)

        # Check retry budget
        budget = RETRY_BUDGETS.get(category, 1)
        if current_retries < budget and current_retries < MAX_TOTAL_RETRIES:
            # Retry: requeue
            self._retry_counts[task_id] = current_retries + 1
            await self._handle_requeue(
                task_id,
                f"Retry {current_retries + 1}/{budget} for {category}: {error_msg[:200]}",
            )
        else:
            # Permanent failure
            trace = build_decision_trace(
                task_id=task_id,
                dag_id=self._dag_run.id,
                error_message=error_msg,
                error_category=category,
            )
            await self._emit(DECISION_TRACE, task_id=task_id, data={
                "task_id": trace.task_id,
                "dag_id": trace.dag_id,
                "error_message": trace.error_message,
                "error_category": trace.error_category,
                "timestamp": trace.timestamp.isoformat(),
            })
            if self._persistence is not None:
                await self._persistence.update_task_status(
                    self._dag_run.id, task_id, "failed",
                    error_message=error_msg,
                    retry_count=current_retries,
                    failure_type=category,
                )
            self._failed.add(task_id)
            await self._emit(TASK_FAILED, task_id=task_id, data={
                "error": error_msg, "failure_type": category,
            })
            await self._emit_progress()
            logger.warning(
                "Task %s permanently failed (%s, %d retries): %s",
                task_id, category, current_retries, error_msg[:200],
            )

    async def _handle_requeue(self, task_id: str, reason: str) -> None:
        """Requeue a task for retry.

        Removes from running; the main loop will pick it up again since it is
        not in _completed or _failed and its deps are met.
        """
        logger.info("Requeueing task %s: %s", task_id, reason)
        await self._emit(TASK_REQUEUED, task_id=task_id, data={"reason": reason})

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
