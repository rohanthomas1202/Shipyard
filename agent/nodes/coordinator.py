from agent.tracing import TraceLogger

tracer = TraceLogger()

def coordinator_node(state: dict) -> dict:
    """Decide whether to fan out to parallel subgraphs or run sequentially.
    Stub — full implementation in Task 6."""
    plan = state.get("plan", [])

    if len(plan) < 2:
        return {"is_parallel": False, "parallel_batches": [], "sequential_first": []}

    dir_groups: dict[str, list[int]] = {}
    for i, step in enumerate(plan):
        step_lower = step.lower()
        if "api/" in step_lower:
            dir_groups.setdefault("api", []).append(i)
        elif "web/" in step_lower:
            dir_groups.setdefault("web", []).append(i)
        elif "shared/" in step_lower:
            dir_groups.setdefault("shared", []).append(i)
        else:
            dir_groups.setdefault("other", []).append(i)

    sequential = dir_groups.pop("shared", [])
    other = dir_groups.pop("other", [])
    parallel_batch = []
    for group_steps in dir_groups.values():
        if group_steps:
            parallel_batch.append(group_steps)

    is_parallel = len(parallel_batch) > 1

    tracer.log("coordinator", {
        "is_parallel": is_parallel,
        "sequential": sequential + other,
        "parallel_batch": parallel_batch,
    })

    return {
        "is_parallel": is_parallel,
        "parallel_batches": parallel_batch,
        "sequential_first": sequential + other,
    }
