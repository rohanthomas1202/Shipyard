"""Tests for DAG persistence and crash recovery."""
import pytest
import pytest_asyncio
import aiosqlite

from agent.orchestrator.dag import TaskDAG
from agent.orchestrator.models import DAGRun
from agent.orchestrator.persistence import DAGPersistence


@pytest_asyncio.fixture
async def db_path(tmp_path):
    """Return a temporary SQLite database path."""
    return str(tmp_path / "test_dag.db")


@pytest_asyncio.fixture
async def persistence(db_path):
    """Create and initialize a DAGPersistence instance."""
    p = DAGPersistence(db_path)
    await p.initialize()
    yield p
    await p.close()


def _make_dag_and_run() -> tuple[TaskDAG, DAGRun]:
    """Create a 3-task DAG (a->b->c) with a DAGRun."""
    dag = TaskDAG(dag_id="test-dag-1")
    dag.add_task("a", label="Task A")
    dag.add_task("b", label="Task B")
    dag.add_task("c", label="Task C")
    dag.add_dependency("a", "b")
    dag.add_dependency("b", "c")

    dag_run = DAGRun(
        id="test-dag-1",
        project_id="proj-1",
        max_concurrency=5,
        total_tasks=3,
    )
    return dag, dag_run


# ---------------------------------------------------------------------------
# test_save_and_load_dag
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_and_load_dag(persistence):
    dag, dag_run = _make_dag_and_run()
    await persistence.save_dag(dag, dag_run)

    result = await persistence.load_dag("test-dag-1")
    assert result is not None
    loaded_dag, loaded_run = result

    assert loaded_dag.task_count == 3
    assert loaded_dag.edge_count == 2


# ---------------------------------------------------------------------------
# test_save_and_load_dag_run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_and_load_dag_run(persistence):
    dag, dag_run = _make_dag_and_run()
    await persistence.save_dag(dag, dag_run)

    result = await persistence.load_dag("test-dag-1")
    assert result is not None
    _, loaded_run = result

    assert loaded_run.id == "test-dag-1"
    assert loaded_run.project_id == "proj-1"
    assert loaded_run.max_concurrency == 5
    assert loaded_run.total_tasks == 3
    assert loaded_run.status == "pending"


# ---------------------------------------------------------------------------
# test_update_task_status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_task_status(persistence):
    dag, dag_run = _make_dag_and_run()
    await persistence.save_dag(dag, dag_run)

    await persistence.update_task_status("test-dag-1", "a", "running")

    # Verify by loading completed (should be empty since it's running, not completed)
    completed = await persistence.load_completed_tasks("test-dag-1")
    assert "a" not in completed

    # Now mark it completed
    await persistence.update_task_status("test-dag-1", "a", "completed")
    completed = await persistence.load_completed_tasks("test-dag-1")
    assert "a" in completed


# ---------------------------------------------------------------------------
# test_mark_running_as_failed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_running_as_failed(persistence):
    dag, dag_run = _make_dag_and_run()
    await persistence.save_dag(dag, dag_run)

    # Set two tasks to "running" directly
    await persistence.update_task_status("test-dag-1", "a", "running")
    await persistence.update_task_status("test-dag-1", "b", "running")

    count = await persistence.mark_interrupted("test-dag-1")
    assert count == 2

    # Verify they are now failed
    completed = await persistence.load_completed_tasks("test-dag-1")
    assert "a" not in completed
    assert "b" not in completed


# ---------------------------------------------------------------------------
# test_load_completed_tasks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_load_completed_tasks(persistence):
    dag, dag_run = _make_dag_and_run()
    await persistence.save_dag(dag, dag_run)

    await persistence.update_task_status("test-dag-1", "a", "completed")
    await persistence.update_task_status("test-dag-1", "b", "completed")

    completed = await persistence.load_completed_tasks("test-dag-1")
    assert completed == {"a", "b"}
