import json
import os
from agent.prompts.planner import PLANNER_SYSTEM, PLANNER_USER
from agent.llm import call_llm
from agent.tracing import TraceLogger

tracer = TraceLogger()

async def planner_node(state: dict) -> dict:
    """Break the instruction into a concrete plan of steps."""
    working_dir = state["working_directory"]
    instruction = state.get("instruction", "")
    context = state.get("context", {})

    # Build context section
    context_section = ""
    if context.get("schema"):
        context_section += f"Relevant schema:\n{context['schema']}\n"
    if context.get("spec"):
        context_section += f"Spec:\n{context['spec']}\n"
    if context.get("files"):
        context_section += f"Relevant files: {', '.join(context['files'])}\n"

    # List top-level files
    try:
        entries = os.listdir(working_dir)
        file_listing = "\n".join(sorted(entries)[:50])
    except Exception:
        file_listing = "(unable to list files)"

    user_prompt = PLANNER_USER.format(
        working_directory=working_dir,
        instruction=instruction,
        context_section=context_section,
        file_listing=file_listing,
    )

    response = await call_llm(PLANNER_SYSTEM, user_prompt)

    try:
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        plan_data = json.loads(text)
        steps = plan_data.get("steps", [])
    except (json.JSONDecodeError, KeyError) as e:
        tracer.log("planner", {"error": str(e), "raw_response": response[:500]})
        # Fallback: treat the whole instruction as one step
        steps = [instruction]

    tracer.log("planner", {
        "instruction": instruction,
        "num_steps": len(steps),
        "steps": steps,
    })

    return {"plan": steps}
