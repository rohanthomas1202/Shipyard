"""Integration tests for the complete execution engine pipeline.

Tests cover branch isolation, CI gating, failure classification with tiered
retry, ownership validation, merge conflict requeue, and context pack delivery.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.orchestrator.dag import TaskDAG
from agent.orchestrator.models import DAGRun, TaskNode, MAX_TOTAL_RETRIES
from agent.orchestrator.scheduler import DAGScheduler
from agent.orchestrator.context_packs import ContextPack
from agent.orchestrator.ci_runner import CIPipelineResult, CIStageResult
from agent.orchestrator.failure_classifier import FailureClassifier, RETRY_BUDGETS
from agent.orchestrator.ownership import OwnershipViolation
from agent.orchestrator.events import (
    CI_STARTED, CI_PASSED, CI_FAILED,
    OWNERSHIP_VIOLATION, TASK_REQUEUED,
    TASK_STARTED, TASK_COMPLETED, TASK_FAILED,
)
from store.models import Event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _single_task_dag() -> tuple[TaskDAG, DAGRun]:
    """Single task DAG for focused tests."""
    dag = TaskDAG(dag_id="eng")
    dag.add_task("t1", label="Task1", metadata={"target_files": ["a.py"], "module": "mod_a"})
    run = DAGRun(id="eng", project_id="p1", total_tasks=1)
    return dag, run


class MockEventBus:
    """Captures emitted events for assertion."""

    def __init__(self):
        self.events: list[Event] = []

    async def emit(self, event: Event) -> None:
        self.events.append(event)

    def types(self) -> list[str]:
        return [e.type for e in self.events]


def _passing_ci() -> CIPipelineResult:
    return CIPipelineResult(stages=[CIStageResult(name="test", passed=True, exit_code=0)])


def _failing_ci(stage_name: str = "test", stderr: str = "FAILED tests/foo") -> CIPipelineResult:
    return CIPipelineResult(stages=[
        CIStageResult(name=stage_name, passed=False, exit_code=1, stderr=stderr),
    ])


# ---------------------------------------------------------------------------
# test_success_path: branch create -> execute -> CI -> merge -> cleanup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_success_path_full_pipeline():
    """_run_task creates branch, executes, runs CI, merges on success, cleans up."""
    dag, run = _single_task_dag()
    bus = MockEventBus()

    branch_mgr = AsyncMock()
    branch_mgr.create_and_checkout.return_value = True
    branch_mgr.rebase_and_merge.return_value = True

    ci_runner = AsyncMock()
    ci_runner.run_pipeline.return_value = _passing_ci()

    ctx_assembler = MagicMock()
    ctx_assembler.assemble.return_value = ContextPack(task_id="t1", primary_files=["a.py"])

    ownership_validator = AsyncMock()
    ownership_validator.validate.return_value = []

    executed = []

    async def executor(task_id, task):
        executed.append(task_id)
        return {"success": True}

    scheduler = DAGScheduler(
        dag, run,
        event_bus=bus,
        task_executor=executor,
        branch_manager=branch_mgr,
        ci_runner=ci_runner,
        failure_classifier=FailureClassifier(),
        context_assembler=ctx_assembler,
        ownership_validator=ownership_validator,
    )
    result = await scheduler.run()

    assert result["t1"] == "completed"
    assert "t1" in executed
    branch_mgr.create_and_checkout.assert_called_once()
    ci_runner.run_pipeline.assert_called_once()
    branch_mgr.rebase_and_merge.assert_called_once()
    branch_mgr.cleanup.assert_called_once()


# ---------------------------------------------------------------------------
# test_retry_syntax_up_to_3
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_syntax_failure_up_to_3():
    """_run_task retries on syntax failure up to 3 times."""
    dag, run = _single_task_dag()

    branch_mgr = AsyncMock()
    branch_mgr.create_and_checkout.return_value = True

    ci_runner = AsyncMock()
    ci_runner.run_pipeline.return_value = _failing_ci(stderr="SyntaxError: invalid syntax")

    classifier = FailureClassifier()

    call_count = 0

    async def executor(task_id, task):
        nonlocal call_count
        call_count += 1
        return {"success": True}

    scheduler = DAGScheduler(
        dag, run,
        task_executor=executor,
        branch_manager=branch_mgr,
        ci_runner=ci_runner,
        failure_classifier=classifier,
    )
    result = await scheduler.run()

    # Should have attempted 1 initial + 3 retries = 4 calls
    assert call_count == 4
    assert result["t1"] == "failed"


# ---------------------------------------------------------------------------
# test_retry_test_failure_up_to_2
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_test_failure_up_to_2():
    """_run_task retries on test failure up to 2 times."""
    dag, run = _single_task_dag()

    branch_mgr = AsyncMock()
    branch_mgr.create_and_checkout.return_value = True

    ci_runner = AsyncMock()
    ci_runner.run_pipeline.return_value = _failing_ci(stderr="FAILED tests/test_foo.py")

    classifier = FailureClassifier()
    call_count = 0

    async def executor(task_id, task):
        nonlocal call_count
        call_count += 1
        return {"success": True}

    scheduler = DAGScheduler(
        dag, run,
        task_executor=executor,
        branch_manager=branch_mgr,
        ci_runner=ci_runner,
        failure_classifier=classifier,
    )
    result = await scheduler.run()

    # 1 initial + 2 retries = 3 calls
    assert call_count == 3
    assert result["t1"] == "failed"


# ---------------------------------------------------------------------------
# test_retry_contract_failure_only_1
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_contract_failure_only_1():
    """_run_task retries on contract failure only 1 time then fails permanently."""
    dag, run = _single_task_dag()

    branch_mgr = AsyncMock()
    branch_mgr.create_and_checkout.return_value = True

    ci_runner = AsyncMock()
    ci_runner.run_pipeline.return_value = _failing_ci(stderr="ImportError: cannot import name 'Foo'")

    classifier = FailureClassifier()
    call_count = 0

    async def executor(task_id, task):
        nonlocal call_count
        call_count += 1
        return {"success": True}

    scheduler = DAGScheduler(
        dag, run,
        task_executor=executor,
        branch_manager=branch_mgr,
        ci_runner=ci_runner,
        failure_classifier=classifier,
    )
    result = await scheduler.run()

    # 1 initial + 1 retry = 2 calls
    assert call_count == 2
    assert result["t1"] == "failed"


# ---------------------------------------------------------------------------
# test_max_total_retries_capped_at_4
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_max_total_retries_capped_at_4():
    """_run_task caps total retries at MAX_TOTAL_RETRIES (4)."""
    dag, run = _single_task_dag()

    branch_mgr = AsyncMock()
    branch_mgr.create_and_checkout.return_value = True

    # Use syntax (budget=3) but we check the absolute cap of 4
    ci_runner = AsyncMock()
    ci_runner.run_pipeline.return_value = _failing_ci(stderr="SyntaxError: oops")

    classifier = FailureClassifier()
    call_count = 0

    async def executor(task_id, task):
        nonlocal call_count
        call_count += 1
        return {"success": True}

    scheduler = DAGScheduler(
        dag, run,
        task_executor=executor,
        branch_manager=branch_mgr,
        ci_runner=ci_runner,
        failure_classifier=classifier,
    )
    result = await scheduler.run()

    # Syntax budget=3, absolute cap=4. Should use min(3, 4) = 3 retries
    # So 1 initial + 3 retries = 4 total
    assert call_count <= MAX_TOTAL_RETRIES + 1  # +1 for initial attempt
    assert result["t1"] == "failed"


# ---------------------------------------------------------------------------
# test_merge_conflict_requeue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_merge_conflict_requeue():
    """_run_task requeues on merge conflict (rebase_and_merge returns False)."""
    dag, run = _single_task_dag()
    bus = MockEventBus()

    branch_mgr = AsyncMock()
    branch_mgr.create_and_checkout.return_value = True
    # First attempt: merge conflict. Second attempt: success
    branch_mgr.rebase_and_merge.side_effect = [False, True]

    ci_runner = AsyncMock()
    ci_runner.run_pipeline.return_value = _passing_ci()

    ctx_assembler = MagicMock()
    ctx_assembler.assemble.return_value = ContextPack(task_id="t1")

    call_count = 0

    async def executor(task_id, task):
        nonlocal call_count
        call_count += 1
        return {"success": True}

    scheduler = DAGScheduler(
        dag, run,
        event_bus=bus,
        task_executor=executor,
        branch_manager=branch_mgr,
        ci_runner=ci_runner,
        context_assembler=ctx_assembler,
    )
    result = await scheduler.run()

    assert call_count == 2  # Executed twice (initial + after requeue)
    assert result["t1"] == "completed"
    assert TASK_REQUEUED in bus.types()


# ---------------------------------------------------------------------------
# test_ownership_violation_fails_task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ownership_violation_fails_task():
    """_run_task rejects task on ownership violation."""
    dag, run = _single_task_dag()
    bus = MockEventBus()

    branch_mgr = AsyncMock()
    branch_mgr.create_and_checkout.return_value = True

    ownership_validator = AsyncMock()
    ownership_validator.validate.return_value = [
        OwnershipViolation(
            file_path="other.py", owning_module="mod_b",
            task_module="mod_a", reason="File owned by mod_b, modified by mod_a task",
        ),
    ]

    async def executor(task_id, task):
        return {"success": True}

    scheduler = DAGScheduler(
        dag, run,
        event_bus=bus,
        task_executor=executor,
        branch_manager=branch_mgr,
        ownership_validator=ownership_validator,
    )
    result = await scheduler.run()

    assert result["t1"] == "failed"
    assert OWNERSHIP_VIOLATION in bus.types()


# ---------------------------------------------------------------------------
# test_ci_failure_emits_ci_failed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ci_failure_emits_ci_failed():
    """CI failure emits CI_FAILED event."""
    dag, run = _single_task_dag()
    bus = MockEventBus()

    branch_mgr = AsyncMock()
    branch_mgr.create_and_checkout.return_value = True

    ci_runner = AsyncMock()
    ci_runner.run_pipeline.return_value = _failing_ci(stderr="FAILED tests/foo")

    async def executor(task_id, task):
        return {"success": True}

    scheduler = DAGScheduler(
        dag, run,
        event_bus=bus,
        task_executor=executor,
        branch_manager=branch_mgr,
        ci_runner=ci_runner,
        failure_classifier=FailureClassifier(),
    )
    await scheduler.run()

    assert CI_STARTED in bus.types()
    assert CI_FAILED in bus.types()


# ---------------------------------------------------------------------------
# test_ci_success_emits_ci_passed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ci_success_emits_ci_passed():
    """CI success emits CI_PASSED event."""
    dag, run = _single_task_dag()
    bus = MockEventBus()

    branch_mgr = AsyncMock()
    branch_mgr.create_and_checkout.return_value = True
    branch_mgr.rebase_and_merge.return_value = True

    ci_runner = AsyncMock()
    ci_runner.run_pipeline.return_value = _passing_ci()

    async def executor(task_id, task):
        return {"success": True}

    scheduler = DAGScheduler(
        dag, run,
        event_bus=bus,
        task_executor=executor,
        branch_manager=branch_mgr,
        ci_runner=ci_runner,
    )
    await scheduler.run()

    assert CI_STARTED in bus.types()
    assert CI_PASSED in bus.types()


# ---------------------------------------------------------------------------
# test_branch_cleanup_always_runs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_branch_cleanup_always_runs():
    """Branch cleanup always runs even on failure/exception."""
    dag, run = _single_task_dag()

    branch_mgr = AsyncMock()
    branch_mgr.create_and_checkout.return_value = True

    async def failing_executor(task_id, task):
        raise RuntimeError("Boom")

    scheduler = DAGScheduler(
        dag, run,
        task_executor=failing_executor,
        branch_manager=branch_mgr,
        failure_classifier=FailureClassifier(),
    )
    await scheduler.run()

    branch_mgr.cleanup.assert_called()


# ---------------------------------------------------------------------------
# test_concurrency_preserved
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrency_preserved():
    """Concurrency limited by semaphore (existing ORCH-04 behavior preserved)."""
    dag = TaskDAG(dag_id="conc")
    for i in range(5):
        dag.add_task(f"t{i}", label=f"Task {i}")
    run = DAGRun(id="conc", project_id="p1", total_tasks=5)

    max_concurrent = 0
    current_concurrent = 0
    lock = asyncio.Lock()

    async def counting_executor(task_id, task):
        nonlocal max_concurrent, current_concurrent
        async with lock:
            current_concurrent += 1
            if current_concurrent > max_concurrent:
                max_concurrent = current_concurrent
        await asyncio.sleep(0.03)
        async with lock:
            current_concurrent -= 1
        return {"success": True}

    scheduler = DAGScheduler(
        dag, run,
        task_executor=counting_executor,
        max_concurrency=2,
    )
    await scheduler.run()

    assert max_concurrent <= 2


# ---------------------------------------------------------------------------
# test_context_pack_delivered_via_metadata
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_context_pack_delivered_via_metadata():
    """Assembled context pack is attached to task.metadata['context_pack'] before executor runs."""
    dag, run = _single_task_dag()

    branch_mgr = AsyncMock()
    branch_mgr.create_and_checkout.return_value = True
    branch_mgr.rebase_and_merge.return_value = True

    ci_runner = AsyncMock()
    ci_runner.run_pipeline.return_value = _passing_ci()

    expected_pack = ContextPack(task_id="t1", primary_files=["a.py"])
    ctx_assembler = MagicMock()
    ctx_assembler.assemble.return_value = expected_pack

    captured_metadata = {}

    async def capturing_executor(task_id, task):
        # Capture metadata at time of execution
        captured_metadata.update(task.metadata)
        return {"success": True}

    scheduler = DAGScheduler(
        dag, run,
        task_executor=capturing_executor,
        branch_manager=branch_mgr,
        ci_runner=ci_runner,
        context_assembler=ctx_assembler,
    )
    await scheduler.run()

    assert "context_pack" in captured_metadata
    assert captured_metadata["context_pack"] is expected_pack
    ctx_assembler.assemble.assert_called_once()
