"""Tech Spec generation layer (Layer 2) of the planning pipeline."""
from agent.analyzer.models import ModuleMap
from agent.planner_v2.models import PRDOutput, TechSpecOutput
from agent.planner_v2.prompts import TECH_SPEC_SYSTEM_PROMPT, build_tech_spec_user_prompt
from agent.router import ModelRouter


async def generate_tech_spec(
    prd: PRDOutput,
    module_map: ModuleMap,
    router: ModelRouter,
) -> TechSpecOutput:
    """Generate a Tech Spec from a PRD and ModuleMap.

    Per D-05: Single LLM call using o3 (plan_spec task type).
    Per D-07: Uses reasoning tier for planning.
    """
    prd_json = prd.model_dump_json(indent=2)
    module_map_json = module_map.model_dump_json(indent=2)
    user_prompt = build_tech_spec_user_prompt(prd_json, module_map_json)
    spec: TechSpecOutput = await router.call_structured(
        "plan_spec",
        TECH_SPEC_SYSTEM_PROMPT,
        user_prompt,
        response_model=TechSpecOutput,
    )
    return spec


def render_tech_spec_markdown(spec: TechSpecOutput) -> str:
    """Render a Tech Spec to markdown for git-tracked storage per D-08."""
    lines = ["# Tech Spec\n"]
    lines.append("\n## Modules\n")
    for mod in spec.modules:
        lines.append(f"\n### {mod.name}\n")
        if mod.api_endpoints:
            lines.append("\n**API Endpoints:**\n")
            for ep in mod.api_endpoints:
                lines.append(f"- {ep}\n")
        if mod.data_models:
            lines.append("\n**Data Models:**\n")
            for dm in mod.data_models:
                lines.append(f"- {dm}\n")
        if mod.component_interfaces:
            lines.append("\n**Component Interfaces:**\n")
            for ci in mod.component_interfaces:
                lines.append(f"- {ci}\n")
        if mod.contract_inputs:
            lines.append(f"\n**Contract Inputs:** {', '.join(mod.contract_inputs)}\n")
        if mod.contract_outputs:
            lines.append(f"\n**Contract Outputs:** {', '.join(mod.contract_outputs)}\n")
    if spec.contracts:
        lines.append("\n## Contracts\n")
        for c in spec.contracts:
            lines.append(f"\n### {c.name} ({c.contract_type})\n")
            lines.append(f"\n```\n{c.content}\n```\n")
    return "".join(lines)
