"""LLM-based module enrichment for semantic understanding."""

from pydantic import BaseModel, Field

from agent.analyzer.models import ModuleInfo
from agent.router import ModelRouter


class ModuleSummary(BaseModel):
    """LLM-generated module summary for enrichment pass."""
    purpose: str = Field(description="1-sentence summary of module purpose")
    public_api: list[str] = Field(default_factory=list, description="Exported functions/classes")


ENRICHMENT_SYSTEM_PROMPT = (
    "You are a codebase analyzer. Given a module's files and their contents, "
    "produce a concise summary of the module's purpose and list its public API "
    "(exported functions, classes, and interfaces). Be precise and factual."
)


def _build_enrichment_prompt(module: ModuleInfo, file_contents: dict[str, str]) -> str:
    """Build user prompt with module files for LLM enrichment."""
    parts = [f"Module: {module.name}\nPath: {module.path}\n\nFiles:\n"]
    for fi in module.files:
        content = file_contents.get(fi.path, "")
        # Truncate to first 100 lines to stay within context budget
        lines = content.splitlines()[:100]
        truncated = "\n".join(lines)
        parts.append(f"\n--- {fi.path} ({fi.loc} LOC) ---\n{truncated}\n")
    return "".join(parts)


async def enrich_module(
    module: ModuleInfo,
    file_contents: dict[str, str],
    router: ModelRouter,
) -> ModuleInfo:
    """Enrich a module with LLM-generated summary and public API.

    Per D-01: LLM reads each module to enrich with semantic understanding.
    Per D-02: Lean summary (1-sentence + public API list).
    Uses router.call_structured() with analyze_enrich task type.
    """
    user_prompt = _build_enrichment_prompt(module, file_contents)
    summary: ModuleSummary = await router.call_structured(
        "analyze_enrich",
        ENRICHMENT_SYSTEM_PROMPT,
        user_prompt,
        response_model=ModuleSummary,
    )
    # Update module with enrichment data
    enriched = module.model_copy(update={
        "summary": summary.purpose,
    })
    # Merge LLM-detected exports with statically-detected ones
    existing_exports = set()
    for fi in enriched.files:
        existing_exports.update(fi.exports)
    return enriched
