"""End-to-end integration tests proving the full DAG orchestrator loop (D-10)."""
import asyncio
import time

import pytest
import pytest_asyncio

from agent.orchestrator.contracts import ContractStore
from agent.orchestrator.dag import TaskDAG
from agent.orchestrator.models import DAGRun, TaskNode
from agent.orchestrator.persistence import DAGPersistence
from agent.orchestrator.scheduler import DAGScheduler
from agent.orchestrator.test_dag_factory import build_test_dag, build_test_task_executor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def persistence(tmp_path):
    db_path = str(tmp_path / "test.db")
    p = DAGPersistence(db_path)
    await p.initialize()
    yield p
    await p.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_dag_execution(tmp_path, persistence):
    """Build the 7-task test DAG, run it to completion, verify all tasks complete."""
    dag = build_test_dag(str(tmp_path))
    contract_store = ContractStore(str(tmp_path))
    executor = build_test_task_executor(contract_store)

    dag_run = DAGRun(
        id=dag.dag_id,
        project_id="test",
        total_tasks=dag.task_count,
    )
    await persistence.save_dag(dag, dag_run)

    scheduler = DAGScheduler(
        dag, dag_run,
        persistence=persistence,
        task_executor=executor,
    )
    result = await scheduler.run()

    assert len(result) == 7
    assert all(s == "completed" for s in result.values()), f"Not all completed: {result}"


@pytest.mark.asyncio
async def test_dag_execution_respects_ordering(tmp_path, persistence):
    """Track execution order and verify wave ordering is respected."""
    dag = build_test_dag(str(tmp_path))
    contract_store = ContractStore(str(tmp_path))

    dag_run = DAGRun(
        id=dag.dag_id,
        project_id="test",
        total_tasks=dag.task_count,
    )
    await persistence.save_dag(dag, dag_run)

    # Custom executor that records start timestamps
    start_times: dict[str, float] = {}

    async def timing_executor(task_id: str, task: TaskNode) -> dict:
        start_times[task_id] = time.monotonic()
        # Read/write contracts so ContractStore logic is exercised
        for name in task.contract_inputs:
            contract_store.read_contract(name)
        await asyncio.sleep(0.05)
        for name in task.contract_outputs:
            contract_store.write_contract(name, f"# {task_id}\n")
        return {"success": True}

    scheduler = DAGScheduler(
        dag, dag_run,
        persistence=persistence,
        task_executor=timing_executor,
    )
    result = await scheduler.run()
    assert all(s == "completed" for s in result.values())

    # Wave 1 tasks must start before wave 2 tasks
    assert start_times["init-project"] < start_times["create-users-table"]
    assert start_times["init-contracts"] < start_times["create-api-routes"]
    # Wave 2 tasks must start before wave 3
    assert start_times["create-users-table"] < start_times["create-user-model"]
    assert start_times["create-api-routes"] < start_times["create-user-model"]
    # Wave 3 must start before wave 4
    assert start_times["create-user-model"] < start_times["create-user-service"]
    assert start_times["create-user-model"] < start_times["create-user-tests"]


@pytest.mark.asyncio
async def test_dag_persist_and_resume(tmp_path, persistence):
    """Run DAG partway, inject failure, then resume from persistence."""
    dag = build_test_dag(str(tmp_path))
    contract_store = ContractStore(str(tmp_path))

    dag_run = DAGRun(
        id=dag.dag_id,
        project_id="test",
        total_tasks=dag.task_count,
    )
    await persistence.save_dag(dag, dag_run)

    # Executor that fails on create-user-model (wave 3)
    async def failing_executor(task_id: str, task: TaskNode) -> dict:
        for name in task.contract_inputs:
            contract_store.read_contract(name)
        await asyncio.sleep(0.01)
        for name in task.contract_outputs:
            contract_store.write_contract(name, f"# {task_id}\n")
        if task_id == "create-user-model":
            raise RuntimeError("Simulated failure on create-user-model")
        return {"success": True}

    scheduler1 = DAGScheduler(
        dag, dag_run,
        persistence=persistence,
        task_executor=failing_executor,
    )
    result1 = await scheduler1.run()

    # Waves 1-2 should be complete, wave 3 failed, wave 4 pending
    assert result1["init-project"] == "completed"
    assert result1["init-contracts"] == "completed"
    assert result1["create-users-table"] == "completed"
    assert result1["create-api-routes"] == "completed"
    assert result1["create-user-model"] == "failed"
    # Wave 4 tasks are blocked by the failed wave-3 task
    assert result1["create-user-service"] == "pending"
    assert result1["create-user-tests"] == "pending"

    # Resume: load from persistence, create new scheduler with working executor
    loaded = await persistence.load_dag(dag.dag_id)
    assert loaded is not None
    dag2, dag_run2 = loaded

    # The failing task was marked failed in persistence; mark_interrupted
    # will handle any 'running' tasks. We need to reset the failed task
    # so the resumed scheduler can retry it.
    assert persistence._db is not None
    await persistence._db.execute(
        """UPDATE task_executions SET status = 'pending', error_message = NULL
           WHERE dag_id = ? AND task_id = 'create-user-model'""",
        (dag.dag_id,),
    )
    await persistence._db.commit()

    # Non-failing executor for resume
    async def ok_executor(task_id: str, task: TaskNode) -> dict:
        for name in task.contract_inputs:
            contract_store.read_contract(name)
        await asyncio.sleep(0.01)
        for name in task.contract_outputs:
            contract_store.write_contract(name, f"# {task_id} resumed\n")
        return {"success": True}

    scheduler2 = DAGScheduler(
        dag2, dag_run2,
        persistence=persistence,
        task_executor=ok_executor,
    )
    result2 = await scheduler2.run()

    # All 7 should now be complete (4 already done + 3 new)
    assert all(s == "completed" for s in result2.values()), f"Resume result: {result2}"
    assert len(result2) == 7


@pytest.mark.asyncio
async def test_dag_concurrent_execution(tmp_path, persistence):
    """Verify wave 1 tasks (init-project, init-contracts) run concurrently."""
    dag = build_test_dag(str(tmp_path))
    contract_store = ContractStore(str(tmp_path))

    dag_run = DAGRun(
        id=dag.dag_id,
        project_id="test",
        total_tasks=dag.task_count,
    )
    await persistence.save_dag(dag, dag_run)

    timestamps: dict[str, dict[str, float]] = {}

    async def timed_executor(task_id: str, task: TaskNode) -> dict:
        timestamps[task_id] = {"start": time.monotonic()}
        for name in task.contract_inputs:
            contract_store.read_contract(name)
        await asyncio.sleep(0.05)
        for name in task.contract_outputs:
            contract_store.write_contract(name, f"# {task_id}\n")
        timestamps[task_id]["end"] = time.monotonic()
        return {"success": True}

    scheduler = DAGScheduler(
        dag, dag_run,
        persistence=persistence,
        task_executor=timed_executor,
    )
    result = await scheduler.run()
    assert all(s == "completed" for s in result.values())

    # Verify init-project and init-contracts had overlapping execution
    # Both should start before either ends (concurrent)
    ip = timestamps["init-project"]
    ic = timestamps["init-contracts"]
    assert ip["start"] < ic["end"], "init-project should start before init-contracts ends"
    assert ic["start"] < ip["end"], "init-contracts should start before init-project ends"
