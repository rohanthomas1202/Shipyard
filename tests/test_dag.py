"""Unit tests for TaskDAG — DAG construction, validation, and scheduling."""
import pytest
from agent.orchestrator.dag import TaskDAG


class TestTaskDAG:
    """Tests for the TaskDAG wrapper around NetworkX DiGraph."""

    def test_add_task(self):
        dag = TaskDAG()
        dag.add_task("t1", label="Test")
        assert dag.task_count == 1

    def test_add_dependency(self):
        dag = TaskDAG()
        dag.add_task("t1", label="First")
        dag.add_task("t2", label="Second")
        dag.add_dependency("t1", "t2")
        # t1 is a predecessor of t2
        assert "t1" in dag.get_ancestors("t2")

    def test_validate_acyclic(self):
        dag = TaskDAG()
        dag.add_task("a", label="A")
        dag.add_task("b", label="B")
        dag.add_task("c", label="C")
        dag.add_dependency("a", "b")
        dag.add_dependency("b", "c")
        assert dag.validate() is True

    def test_validate_cyclic(self):
        dag = TaskDAG()
        dag.add_task("a", label="A")
        dag.add_task("b", label="B")
        dag.add_dependency("a", "b")
        dag.add_dependency("b", "a")
        assert dag.validate() is False

    def test_get_ready_tasks_initial(self):
        dag = TaskDAG()
        dag.add_task("a", label="A")
        dag.add_task("b", label="B")
        dag.add_task("c", label="C")
        dag.add_dependency("a", "b")
        dag.add_dependency("b", "c")
        ready = dag.get_ready_tasks(set())
        assert ready == ["a"]

    def test_get_ready_tasks_after_completion(self):
        dag = TaskDAG()
        dag.add_task("a", label="A")
        dag.add_task("b", label="B")
        dag.add_task("c", label="C")
        dag.add_dependency("a", "b")
        dag.add_dependency("b", "c")
        ready = dag.get_ready_tasks({"a"})
        assert ready == ["b"]

    def test_get_ready_tasks_parallel(self):
        dag = TaskDAG()
        dag.add_task("a", label="A")
        dag.add_task("b", label="B")
        dag.add_task("c", label="C")
        dag.add_dependency("a", "c")
        dag.add_dependency("b", "c")
        ready = sorted(dag.get_ready_tasks(set()))
        assert ready == ["a", "b"]

    def test_get_execution_waves(self):
        dag = TaskDAG()
        dag.add_task("a", label="A")
        dag.add_task("b", label="B")
        dag.add_task("c", label="C")
        dag.add_dependency("a", "c")
        dag.add_dependency("b", "c")
        waves = dag.get_execution_waves()
        assert len(waves) == 2
        assert sorted(waves[0]) == ["a", "b"]
        assert waves[1] == ["c"]

    def test_get_ancestors(self):
        dag = TaskDAG()
        dag.add_task("a", label="A")
        dag.add_task("b", label="B")
        dag.add_task("c", label="C")
        dag.add_dependency("a", "b")
        dag.add_dependency("b", "c")
        assert dag.get_ancestors("c") == {"a", "b"}

    def test_task_count_and_edge_count(self):
        dag = TaskDAG()
        dag.add_task("a", label="A")
        dag.add_task("b", label="B")
        dag.add_dependency("a", "b")
        assert dag.task_count == 2
        assert dag.edge_count == 1

    def test_get_task(self):
        dag = TaskDAG()
        node = dag.add_task(
            "t1",
            label="Test Task",
            contract_inputs=["schema.sql"],
            contract_outputs=["api.yaml"],
        )
        retrieved = dag.get_task("t1")
        assert retrieved is not None
        assert retrieved.label == "Test Task"
        assert retrieved.contract_inputs == ["schema.sql"]
        assert retrieved.contract_outputs == ["api.yaml"]

    def test_get_task_missing(self):
        dag = TaskDAG()
        assert dag.get_task("nonexistent") is None

    def test_from_definition(self):
        tasks = [
            {"id": "t1", "label": "Task 1"},
            {"id": "t2", "label": "Task 2"},
            {"id": "t3", "label": "Task 3"},
        ]
        edges = [
            {"from_task": "t1", "to_task": "t3"},
            {"from_task": "t2", "to_task": "t3"},
        ]
        dag = TaskDAG.from_definition("test-dag", tasks, edges)
        assert dag.task_count == 3
        assert dag.edge_count == 2
        assert dag.validate() is True
        waves = dag.get_execution_waves()
        assert sorted(waves[0]) == ["t1", "t2"]
        assert waves[1] == ["t3"]
