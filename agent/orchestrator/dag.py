"""NetworkX DiGraph wrapper for task dependency scheduling."""
from __future__ import annotations

import networkx as nx

from agent.orchestrator.models import TaskNode, _new_id


class TaskDAG:
    """Directed acyclic graph of tasks with dependency-aware scheduling.

    Wraps NetworkX DiGraph to provide task addition, dependency tracking,
    cycle detection, topological ordering, and ready-task queries.
    """

    def __init__(self, dag_id: str = "") -> None:
        self.dag_id = dag_id or _new_id()
        self._graph: nx.DiGraph = nx.DiGraph()

    # -- Mutation ----------------------------------------------------------

    def add_task(
        self,
        task_id: str,
        *,
        label: str = "",
        description: str | None = None,
        task_type: str = "agent",
        contract_inputs: list[str] | None = None,
        contract_outputs: list[str] | None = None,
        metadata: dict | None = None,
    ) -> TaskNode:
        """Add a task node to the DAG and return the created TaskNode."""
        node = TaskNode(
            id=task_id,
            dag_id=self.dag_id,
            label=label,
            description=description,
            task_type=task_type,
            contract_inputs=contract_inputs or [],
            contract_outputs=contract_outputs or [],
            metadata=metadata or {},
        )
        self._graph.add_node(task_id, data=node)
        return node

    def add_dependency(self, from_task: str, to_task: str) -> None:
        """Add a directed edge: from_task must complete before to_task."""
        self._graph.add_edge(from_task, to_task)

    # -- Queries -----------------------------------------------------------

    def validate(self) -> bool:
        """Return True if the graph is a valid DAG (no cycles)."""
        return nx.is_directed_acyclic_graph(self._graph)

    def get_ready_tasks(self, completed: set[str]) -> list[str]:
        """Return task IDs whose predecessors are all completed and are not themselves done."""
        ready: list[str] = []
        for node in self._graph.nodes:
            if node in completed:
                continue
            predecessors = set(self._graph.predecessors(node))
            if predecessors <= completed:
                ready.append(node)
        return ready

    def get_execution_waves(self) -> list[list[str]]:
        """Return tasks grouped into topological generations (parallel waves)."""
        return [list(gen) for gen in nx.topological_generations(self._graph)]

    def get_ancestors(self, task_id: str) -> set[str]:
        """Return all ancestor task IDs (transitive predecessors)."""
        return nx.ancestors(self._graph, task_id)

    def get_task(self, task_id: str) -> TaskNode | None:
        """Return the TaskNode for a given ID, or None if not found."""
        if task_id not in self._graph.nodes:
            return None
        return self._graph.nodes[task_id].get("data")

    # -- Properties --------------------------------------------------------

    @property
    def task_count(self) -> int:
        return len(self._graph.nodes)

    @property
    def edge_count(self) -> int:
        return len(self._graph.edges)

    # -- Factory -----------------------------------------------------------

    @classmethod
    def from_definition(
        cls,
        dag_id: str,
        tasks: list[dict],
        edges: list[dict],
    ) -> TaskDAG:
        """Build a TaskDAG from a JSON-like structure.

        Args:
            dag_id: Identifier for this DAG.
            tasks: List of dicts with at least 'id' key, plus optional
                   'label', 'description', 'task_type', etc.
            edges: List of dicts with 'from_task' and 'to_task' keys.
        """
        dag = cls(dag_id=dag_id)
        for t in tasks:
            task_id = t.pop("id")
            dag.add_task(task_id, **t)
        for e in edges:
            dag.add_dependency(e["from_task"], e["to_task"])
        return dag
