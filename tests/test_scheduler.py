"""Tests for DAGScheduler -- dependency enforcement, concurrency, and crash recovery."""
import asyncio
import time

import pytest
import pytest_asyncio

from agent.orchestrator.dag import TaskDAG
from agent.orchestrator.models import DAGRun, TaskNode
from agent.orchestrator.persistence import DAGPersistence
from agent.orchestrator.scheduler import DAGScheduler
from store.models import Event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _mock_executor(task_id: str, task: TaskNode) -> dict:
    """Simple mock executor that sleeps briefly."""
    await asyncio.sleep(0.01)
    return {"success": True}


def _linear_dag() -> tuple[TaskDAG, DAGRun]:
    """a -> b -> c"""
    dag = TaskDAG(dag_id="linear")
    dag.add_task("a", label="A")
    dag.add_task("b", label="B")
    dag.add_task("c", label="C")
    dag.add_dependency("a", "b")
    dag.add_dependency("b", "c")
    run = DAGRun(id="linear", project_id="p1", total_tasks=3)
    return dag, run


def _parallel_dag() -> tuple[TaskDAG, DAGRun]:
    """a and b are independent roots"""
    dag = TaskDAG(dag_id="parallel")
    dag.add_task("a", label="A")
    dag.add_task("b", label="B")
    run = DAGRun(id="parallel", project_id="p1", total_tasks=2)
    return dag, run


def _five_independent() -> tuple[TaskDAG, DAGRun]:
    """5 independent tasks for concurrency testing."""
    dag = TaskDAG(dag_id="five")
    for i in range(5):
        dag.add_task(f"t{i}", label=f"Task {i}")
    run = DAGRun(id="five", project_id="p1", total_tasks=5, max_concurrency=2)
    return dag, run


def _diamond_dag() -> tuple[TaskDAG, DAGRun]:
    """a -> c, b -> c. Diamond shape."""
    dag = TaskDAG(dag_id="diamond")
    dag.add_task("a", label="A")
    dag.add_task("b", label="B")
    dag.add_task("c", label="C")
    dag.add_dependency("a", "c")
    dag.add_dependency("b", "c")
    run = DAGRun(id="diamond", project_id="p1", total_tasks=3)
    return dag, run


# ---------------------------------------------------------------------------
# test_dependency_enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dependency_enforcement():
    """a->b->c: scheduler runs a first, then b, then c."""
    dag, run = _linear_dag()
    order: list[str] = []

    async def tracking_executor(task_id: str, task: TaskNode) -> dict:
        order.append(task_id)
        await asyncio.sleep(0.01)
        return {"success": True}

    scheduler = DAGScheduler(
        dag, run,
        task_executor=tracking_executor,
    )
    result = await scheduler.run()

    assert order == ["a", "b", "c"]
    assert all(v == "completed" for v in result.values())


# ---------------------------------------------------------------------------
# test_parallel_independent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parallel_independent():
    """a and b have no deps -- both start before either finishes."""
    dag, run = _parallel_dag()
    started: dict[str, float] = {}
    finished: dict[str, float] = {}

    async def timing_executor(task_id: str, task: TaskNode) -> dict:
        started[task_id] = time.monotonic()
        await asyncio.sleep(0.05)
        finished[task_id] = time.monotonic()
        return {"success": True}

    scheduler = DAGScheduler(
        dag, run,
        task_executor=timing_executor,
        max_concurrency=10,
    )
    await scheduler.run()

    # Both should have started before either finished
    assert started["a"] < finished["b"]
    assert started["b"] < finished["a"]


# ---------------------------------------------------------------------------
# test_concurrency_limit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrency_limit():
    """5 independent tasks with max_concurrency=2: never more than 2 running."""
    dag, run = _five_independent()
    max_concurrent = 0
    current_concurrent = 0
    lock = asyncio.Lock()

    async def counting_executor(task_id: str, task: TaskNode) -> dict:
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
# test_task_failure_does_not_block_independent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_task_failure_does_not_block_independent():
    """a->c, b->c. a fails. b still runs. c does not run."""
    dag, run = _diamond_dag()
    executed: list[str] = []

    async def failing_executor(task_id: str, task: TaskNode) -> dict:
        executed.append(task_id)
        if task_id == "a":
            raise RuntimeError("Task a failed")
        await asyncio.sleep(0.01)
        return {"success": True}

    scheduler = DAGScheduler(
        dag, run,
        task_executor=failing_executor,
    )
    result = await scheduler.run()

    assert "a" in executed
    assert "b" in executed
    assert "c" not in executed
    assert result["a"] == "failed"
    assert result["b"] == "completed"
    assert result["c"] == "pending"


# ---------------------------------------------------------------------------
# test_all_complete_status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_complete_status():
    """After all tasks complete, result shows all completed."""
    dag, run = _linear_dag()
    scheduler = DAGScheduler(dag, run, task_executor=_mock_executor)
    result = await scheduler.run()

    assert result == {"a": "completed", "b": "completed", "c": "completed"}


# ---------------------------------------------------------------------------
# test_crash_recovery_skips_completed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_crash_recovery_skips_completed(tmp_path):
    """Save DAG with 2/3 completed, new scheduler skips those 2."""
    db_path = str(tmp_path / "recovery.db")
    persistence = DAGPersistence(db_path)
    await persistence.initialize()

    dag, run = _linear_dag()
    await persistence.save_dag(dag, run)

    # Mark a and b as completed
    await persistence.update_task_status("linear", "a", "completed")
    await persistence.update_task_status("linear", "b", "completed")

    executed: list[str] = []

    async def tracking_executor(task_id: str, task: TaskNode) -> dict:
        executed.append(task_id)
        await asyncio.sleep(0.01)
        return {"success": True}

    scheduler = DAGScheduler(
        dag, run,
        persistence=persistence,
        task_executor=tracking_executor,
    )
    result = await scheduler.run()

    # Only c should have been executed
    assert executed == ["c"]
    assert result["a"] == "completed"
    assert result["b"] == "completed"
    assert result["c"] == "completed"

    await persistence.close()


# ---------------------------------------------------------------------------
# test_crash_recovery_marks_interrupted
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_crash_recovery_marks_interrupted(tmp_path):
    """Save DAG with 1 'running', resume marks it 'failed'."""
    db_path = str(tmp_path / "interrupt.db")
    persistence = DAGPersistence(db_path)
    await persistence.initialize()

    dag, run = _linear_dag()
    await persistence.save_dag(dag, run)

    # Simulate crash: a was running
    await persistence.update_task_status("linear", "a", "running")

    scheduler = DAGScheduler(
        dag, run,
        persistence=persistence,
        task_executor=_mock_executor,
    )
    result = await scheduler.run()

    # a should have been marked failed (interrupted), then re-attempted is not
    # part of the basic scheduler -- it stays failed
    assert result["a"] == "failed"

    await persistence.close()


# ---------------------------------------------------------------------------
# test_events_emitted
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_events_emitted():
    """Scheduler emits task_started and task_completed events."""
    dag = TaskDAG(dag_id="evt")
    dag.add_task("x", label="X")
    run = DAGRun(id="evt", project_id="p1", total_tasks=1)

    emitted: list[Event] = []

    class MockEventBus:
        async def emit(self, event: Event) -> None:
            emitted.append(event)

    scheduler = DAGScheduler(
        dag, run,
        event_bus=MockEventBus(),
        task_executor=_mock_executor,
    )
    await scheduler.run()

    types = [e.type for e in emitted]
    assert "dag_started" in types
    assert "task_started" in types
    assert "task_completed" in types
    assert "dag_completed" in types
