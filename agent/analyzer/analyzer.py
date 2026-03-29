"""Top-level codebase analyzer orchestrating discovery and enrichment."""

from pathlib import Path

from agent.analyzer.models import ModuleMap
from agent.analyzer.discovery import discover_modules
from agent.analyzer.enrichment import enrich_module
from agent.router import ModelRouter


async def analyze_codebase(
    project_path: str | Path,
    router: ModelRouter,
    src_dir: str = "src",
    enrich: bool = True,
) -> ModuleMap:
    """Analyze a codebase and produce a ModuleMap with dependency graph.

    Per D-01: Hybrid discovery -- directory scan then LLM enrichment.
    Per D-04: Returns single ModuleMap (serializable to JSON).

    Args:
        project_path: Root directory of the project to analyze.
        router: ModelRouter for LLM calls during enrichment.
        src_dir: Subdirectory containing source code (default: "src").
        enrich: Whether to run LLM enrichment pass (default: True).
                Set to False for deterministic-only analysis.

    Returns:
        ModuleMap with modules, dependency edges, and (if enrich=True) summaries.
    """
    root = Path(project_path).resolve()

    # Pass 1: Deterministic directory discovery + import edge extraction
    module_map = discover_modules(root, src_dir=src_dir)

    if not enrich:
        return module_map

    # Pass 2: LLM enrichment for each module (per D-02 lean map)
    enriched_modules = []
    for module in module_map.modules:
        # Read file contents for enrichment prompt
        file_contents: dict[str, str] = {}
        for fi in module.files:
            file_path = root / fi.path
            if file_path.is_file():
                file_contents[fi.path] = file_path.read_text(
                    encoding="utf-8", errors="ignore"
                )
        enriched = await enrich_module(module, file_contents, router)
        enriched_modules.append(enriched)

    return module_map.model_copy(update={"modules": enriched_modules})
