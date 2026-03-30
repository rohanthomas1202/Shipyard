"""Real task executor bridging DAG TaskNodes to the LangGraph agent graph."""
import logging
from collections.abc import Awaitable, Callable

from agent.graph import build_graph
from agent.orchestrator.models import TaskNode
from agent.router import ModelRouter

logger = logging.getLogger(__name__)


def build_agent_executor(
    output_dir: str, router: ModelRouter
) -> Callable[[str, TaskNode], Awaitable[dict]]:
    """Build an async executor that invokes the LangGraph agent graph per task.

    Compiles the graph once and returns a closure that maps
    (task_id, TaskNode) -> result dict via graph.ainvoke().
    """
    graph = build_graph()

    async def execute(task_id: str, task: TaskNode) -> dict:
        """Execute a single DAG task through the LangGraph agent graph."""
        logger.info("Executing task %s: %s", task_id, task.label)

        # Build instruction from task description
        instruction = task.description or task.label

        # Append context pack contents if available
        context_pack = task.metadata.get("context_pack")
        if context_pack:
            instruction += f"\n\nContext:\n{context_pack}"

        # Construct full AgentState
        state = {
            "messages": [],
            "instruction": instruction,
            "working_directory": output_dir,
            "context": {},
            "plan": [],
            "current_step": 0,
            "file_buffer": {},
            "file_hashes": {},
            "edit_history": [],
            "error_state": None,
            "last_validation_error": None,
            "validation_error_history": [],
            "is_parallel": False,
            "parallel_batches": [],
            "sequential_first": [],
            "has_conflicts": False,
            "parallel_results": [],
            "model_usage": {},
            "autonomy_mode": "autonomous",
            "ast_available": {},
            "invalidated_files": [],
        }

        config = {
            "configurable": {
                "router": router,
                "run_id": task_id,
                "thread_id": task_id,
            },
            "tags": [f"task:{task_id}"],
        }

        result = await graph.ainvoke(state, config=config)

        if result.get("error_state"):
            raise RuntimeError(result["error_state"])

        edits = len(result.get("edit_history", []))
        logger.info("Task %s completed: %d edits", task_id, edits)
        return {"success": True, "edits": edits}

    return execute
