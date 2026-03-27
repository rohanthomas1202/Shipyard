"""Parallel batch execution -- runs independent step groups as separate graph invocations."""
import asyncio
import logging
from agent.tracing import TraceLogger

logger = logging.getLogger(__name__)
tracer = TraceLogger()


async def run_parallel_batches(
    graph,
    batches: list[list[int]],
    base_state: dict,
    config: dict,
) -> list[dict]:
    """Run independent step-groups as separate graph invocations via asyncio.gather.

    Each batch gets its own copy of state with only the relevant plan steps.
    Returns list of result state dicts (one per batch). Exceptions are caught
    and returned as error dicts.
    """
    async def run_batch(indices: list[int]) -> dict:
        batch_state = dict(base_state)
        batch_state["plan"] = [base_state["plan"][i] for i in indices]
        batch_state["current_step"] = 0
        batch_state["edit_history"] = []
        batch_state["file_buffer"] = {}
        batch_state["file_hashes"] = {}
        batch_state["error_state"] = None
        batch_state["is_parallel"] = False
        batch_state["parallel_batches"] = []
        batch_state["sequential_first"] = []
        tracer.log("parallel_batch_start", {
            "indices": indices,
            "steps": len(indices),
        })
        return await graph.ainvoke(batch_state, config=config)

    results = await asyncio.gather(
        *[run_batch(indices) for indices in batches],
        return_exceptions=True,
    )

    processed = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error("Batch %d failed: %s", i, result)
            processed.append({
                "edit_history": [],
                "error_state": str(result),
                "file_buffer": {},
            })
        else:
            processed.append(result)

    tracer.log("parallel_batches_complete", {
        "batch_count": len(batches),
        "success_count": sum(1 for r in results if not isinstance(r, Exception)),
    })
    return processed
