"""Coordinator node -- decides parallel vs sequential execution and executes parallel batches."""
from langgraph.types import RunnableConfig
import logging
from agent.tracing import TraceLogger

logger = logging.getLogger(__name__)
tracer = TraceLogger()


def _step_to_text(step) -> str:
    """Extract text representation from a step (dict or string)."""
    if isinstance(step, dict):
        files = step.get("target_files", [])
        if files:
            return files[0].lower()
        return step.get("id", "").lower()
    return str(step).lower()


def coordinator_node(state: dict) -> dict:
    """Decide whether to fan out to parallel subgraphs or run sequentially.
    Refactor steps are always placed in sequential_first (never parallelized)."""
    plan = state.get("plan", [])

    if len(plan) < 2:
        return {"is_parallel": False, "parallel_batches": [], "sequential_first": []}

    refactor_indices: list[int] = []
    other_indices: list[int] = []
    for i, step in enumerate(plan):
        if isinstance(step, dict) and step.get("kind") == "refactor":
            refactor_indices.append(i)
        else:
            other_indices.append(i)

    dir_groups: dict[str, list[int]] = {}
    for i in other_indices:
        step_text = _step_to_text(plan[i])
        if "api/" in step_text:
            dir_groups.setdefault("api", []).append(i)
        elif "web/" in step_text:
            dir_groups.setdefault("web", []).append(i)
        elif "shared/" in step_text:
            dir_groups.setdefault("shared", []).append(i)
        else:
            dir_groups.setdefault("other", []).append(i)

    sequential = dir_groups.pop("shared", [])
    other = dir_groups.pop("other", [])
    parallel_batch = []
    for group_steps in dir_groups.values():
        if group_steps:
            parallel_batch.append(group_steps)

    sequential_first = refactor_indices + sequential + other
    is_parallel = len(parallel_batch) > 1

    tracer.log("coordinator", {
        "is_parallel": is_parallel,
        "sequential": sequential_first,
        "parallel_batch": parallel_batch,
        "refactor_steps": refactor_indices,
    })

    return {
        "is_parallel": is_parallel,
        "parallel_batches": parallel_batch,
        "sequential_first": sequential_first,
    }


async def parallel_executor_node(state: dict, config: RunnableConfig) -> dict:
    """Execute parallel batches using separate graph invocations."""
    from agent.parallel import run_parallel_batches
    from agent.graph import build_graph
    from agent.nodes.merger import merge_batch_results

    batches = state.get("parallel_batches", [])
    if not batches:
        return {}

    # Build a sub-graph without checkpointer for batch execution
    sub_graph = build_graph(checkpointer=None)
    results = await run_parallel_batches(sub_graph, batches, state, config)

    # Merge results
    merged = merge_batch_results(results)
    return merged
