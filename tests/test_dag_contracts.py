"""Integration tests for contract read/write flow during DAG task execution (CNTR-02)."""
import asyncio

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

@pytest.fixture
def contract_store(tmp_path):
    return ContractStore(str(tmp_path))


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
async def test_agent_contract_flow(tmp_path, contract_store, persistence):
    """Task executor reads contract before execution (gets None or previous content),
    writes contract after execution, and the next task reads the updated contract."""
    # Build a simple 2-task DAG: writer -> reader
    dag = TaskDAG(dag_id="contract-flow")
    dag.add_task(
        "writer",
        label="Write schema",
        contract_outputs=["db/schema.sql"],
    )
    dag.add_task(
        "reader",
        label="Read schema",
        contract_inputs=["db/schema.sql"],
    )
    dag.add_dependency("writer", "reader")

    dag_run = DAGRun(
        id="contract-flow",
        project_id="test",
        total_tasks=2,
    )
    await persistence.save_dag(dag, dag_run)

    # Custom executor that records what was read
    read_log: dict[str, str | None] = {}

    async def tracking_executor(task_id: str, task: TaskNode) -> dict:
        for name in task.contract_inputs:
            read_log[f"{task_id}:{name}"] = contract_store.read_contract(name)
        await asyncio.sleep(0.01)
        for name in task.contract_outputs:
            contract_store.write_contract(name, f"-- written by {task_id}\n")
        return {"success": True}

    scheduler = DAGScheduler(
        dag, dag_run,
        persistence=persistence,
        task_executor=tracking_executor,
    )
    result = await scheduler.run()

    assert result["writer"] == "completed"
    assert result["reader"] == "completed"
    # Reader should have read content written by writer
    assert read_log["reader:db/schema.sql"] == "-- written by writer\n"


@pytest.mark.asyncio
async def test_contract_accumulation(tmp_path, contract_store, persistence):
    """After full test DAG run, contracts for db/schema.sql and api/openapi.yaml
    should exist with content from task writes."""
    dag = build_test_dag(str(tmp_path))
    dag_run = DAGRun(
        id=dag.dag_id,
        project_id="test",
        total_tasks=dag.task_count,
    )
    await persistence.save_dag(dag, dag_run)

    executor = build_test_task_executor(contract_store)
    scheduler = DAGScheduler(
        dag, dag_run,
        persistence=persistence,
        task_executor=executor,
    )
    result = await scheduler.run()

    # All tasks should complete
    assert all(s == "completed" for s in result.values()), f"Not all completed: {result}"

    # Both contract files should exist with content
    schema = contract_store.read_contract("db/schema.sql")
    assert schema is not None, "db/schema.sql should exist after DAG run"
    assert "CREATE TABLE" in schema

    openapi = contract_store.read_contract("api/openapi.yaml")
    assert openapi is not None, "api/openapi.yaml should exist after DAG run"
    assert "openapi" in openapi

    # list_contracts should include both
    contracts = contract_store.list_contracts()
    assert "db/schema.sql" in contracts
    assert "api/openapi.yaml" in contracts
