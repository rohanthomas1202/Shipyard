from agent.prompts.planner import PLANNER_SYSTEM, PLANNER_USER
from agent.steps import parse_plan_steps
from agent.tracing import TraceLogger
from agent.tools.file_ops import list_files

tracer = TraceLogger()


async def planner_node(state: dict, config: dict) -> dict:
    router = config["configurable"]["router"]
    instruction = state["instruction"]
    working_dir = state["working_directory"]
    context = state.get("context", {})

    context_parts = []
    if context.get("spec"):
        context_parts.append(f"Spec:\n{context['spec']}")
    if context.get("schema"):
        context_parts.append(f"Schema:\n{context['schema']}")
    if context.get("files"):
        context_parts.append(f"Key files:\n{', '.join(context['files'])}")
    context_section = "\n\n".join(context_parts) if context_parts else "No additional context."

    file_listing = list_files(working_dir) if working_dir else ""

    user_prompt = PLANNER_USER.format(
        working_directory=working_dir,
        instruction=instruction,
        context_section=context_section,
        file_listing=f"Files in project:\n{file_listing}" if file_listing else "",
    )

    raw = await router.call("plan", PLANNER_SYSTEM, user_prompt)
    steps = parse_plan_steps(raw)

    tracer.log("planner", {"steps": len(steps), "instruction": instruction[:100]})

    return {
        "plan": [step.model_dump() for step in steps],
    }
