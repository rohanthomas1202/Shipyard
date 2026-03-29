"""PRD generation layer (Layer 1) of the planning pipeline."""
from agent.analyzer.models import ModuleMap
from agent.planner_v2.models import PRDOutput
from agent.planner_v2.prompts import PRD_SYSTEM_PROMPT, build_prd_user_prompt
from agent.router import ModelRouter


async def generate_prd(module_map: ModuleMap, router: ModelRouter) -> PRDOutput:
    """Generate a PRD from a ModuleMap.

    Per D-05: Single LLM call using o3 (plan_prd task type).
    Per D-07: Uses reasoning tier for planning.
    Per D-08: PRD stored as markdown (caller handles persistence).
    """
    module_map_json = module_map.model_dump_json(indent=2)
    user_prompt = build_prd_user_prompt(module_map_json)
    prd: PRDOutput = await router.call_structured(
        "plan_prd",
        PRD_SYSTEM_PROMPT,
        user_prompt,
        response_model=PRDOutput,
    )
    return prd


def render_prd_markdown(prd: PRDOutput) -> str:
    """Render a PRD to markdown for git-tracked storage per D-08."""
    lines = [
        f"# PRD: {prd.project_name}\n",
        f"\n## Overview\n\n{prd.overview}\n",
        "\n## Modules\n",
    ]
    for mod in prd.modules:
        lines.append(f"\n### {mod.name}\n")
        lines.append(f"\n{mod.description}\n")
        lines.append(f"\n**Complexity:** {mod.estimated_complexity}\n")
        if mod.responsibilities:
            lines.append("\n**Responsibilities:**\n")
            for r in mod.responsibilities:
                lines.append(f"- {r}\n")
        if mod.depends_on:
            lines.append(f"\n**Depends on:** {', '.join(mod.depends_on)}\n")
    if prd.build_order:
        lines.append(f"\n## Build Order\n\n{' -> '.join(prd.build_order)}\n")
    return "".join(lines)
