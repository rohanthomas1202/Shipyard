"""Planner node — decomposes instructions into typed PlanSteps.

Uses ContextAssembler for model-aware context budget management.
"""
from langgraph.types import RunnableConfig
from agent.context import ContextAssembler
from agent.node_events import emit_status, emit_node_event, flush_node
from agent.prompts.planner import PLANNER_SYSTEM, PLANNER_USER
from agent.steps import parse_plan_steps
from agent.tracing import TraceLogger
from agent.tools.file_ops import list_files

tracer = TraceLogger()


async def planner_node(state: dict, config: RunnableConfig) -> dict:
    await emit_status(config, "planner", "Planning edits...")

    router = config["configurable"]["router"]
    instruction = state["instruction"]
    working_dir = state["working_directory"]
    context = state.get("context", {})

    # Resolve model budget for context assembly
    model_config = router.resolve_model("plan")
    assembler = ContextAssembler(
        max_tokens=model_config.context_window - model_config.max_output,
    )

    # Add task instruction
    assembler.add_task(instruction)

    # Add context at appropriate priorities
    if context.get("spec"):
        assembler.add_file("spec", context["spec"], priority="working")
    if context.get("schema"):
        assembler.add_file("schema", context["schema"], priority="reference")
    if context.get("files"):
        assembler.add_file("key_files", ", ".join(context["files"]), priority="reference")

    # Add file listing as reference context
    file_listing = list_files(working_dir) if working_dir else ""
    if file_listing:
        assembler.add_file("file_listing", file_listing, priority="reference")

    context_section = assembler.build()

    user_prompt = PLANNER_USER.format(
        working_directory=working_dir,
        instruction=instruction,
        context_section=context_section,
        file_listing="",
    )

    raw = await router.call("plan", PLANNER_SYSTEM, user_prompt)
    steps = parse_plan_steps(raw)

    tracer.log("planner", {"steps": len(steps), "instruction": instruction[:100]})

    await emit_node_event(config, "planner", "plan_ready", {
        "steps": [{"kind": s.kind, "target_files": s.target_files, "label": s.acceptance_criteria or f"Step {i+1}"} for i, s in enumerate(steps)],
        "total_steps": len(steps),
    })
    await flush_node(config)
    return {
        "plan": [step.model_dump() for step in steps],
    }
