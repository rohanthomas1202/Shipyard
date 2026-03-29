"""Integration tests for the codebase analyzer with mocked LLM calls."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from agent.analyzer.analyzer import analyze_codebase
from agent.analyzer.enrichment import ModuleSummary
from agent.analyzer.models import ModuleMap
from agent.router import ModelRouter

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "ship_fixture"


def _make_mock_router() -> ModelRouter:
    """Create a ModelRouter with mocked call_structured that returns ModuleSummary."""
    router = ModelRouter.__new__(ModelRouter)
    router.call_structured = AsyncMock(
        side_effect=lambda task_type, system, user, response_model: ModuleSummary(
            purpose=f"Test summary for module",
            public_api=["func1"],
        )
    )
    return router


# ---------------------------------------------------------------------------
# ANLZ-01: Module map from fixture
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_module_map_from_fixture():
    """analyze_codebase(enrich=False) produces a 5-module ModuleMap from ship_fixture."""
    router = _make_mock_router()
    module_map = await analyze_codebase(FIXTURE_ROOT, router=router, enrich=False)

    module_names = {m.name for m in module_map.modules}
    assert len(module_map.modules) == 5, f"Expected 5 modules, got {len(module_map.modules)}: {module_names}"
    assert module_names == {"components", "middleware", "models", "routes", "types"}
    assert len(module_map.edges) >= 5, f"Expected >=5 edges, got {len(module_map.edges)}"
    assert module_map.total_files >= 8, f"Expected >=8 files, got {module_map.total_files}"
    assert module_map.total_loc > 0, f"Expected total_loc > 0, got {module_map.total_loc}"


# ---------------------------------------------------------------------------
# ANLZ-02: Module enrichment with mocked LLM
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_module_enrichment():
    """analyze_codebase(enrich=True) enriches every module with LLM summary."""
    router = _make_mock_router()
    module_map = await analyze_codebase(FIXTURE_ROOT, router=router, enrich=True)

    # Every module should have a non-empty summary
    for mod in module_map.modules:
        assert mod.summary, f"Module {mod.name} has empty summary"

    # One call_structured per module (5 modules)
    assert router.call_structured.call_count == 5, (
        f"Expected 5 LLM calls, got {router.call_structured.call_count}"
    )

    # Every call should use the analyze_enrich task type
    for call in router.call_structured.call_args_list:
        assert call.args[0] == "analyze_enrich" or call.kwargs.get("task_type") == "analyze_enrich", (
            f"Expected task_type 'analyze_enrich', got {call}"
        )


# ---------------------------------------------------------------------------
# No enrichment pass
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_without_enrichment():
    """analyze_codebase(enrich=False) returns valid ModuleMap with empty summaries."""
    router = _make_mock_router()
    module_map = await analyze_codebase(FIXTURE_ROOT, router=router, enrich=False)

    # All modules should have empty summary (no LLM called)
    for mod in module_map.modules:
        assert mod.summary == "", f"Module {mod.name} has non-empty summary: {mod.summary}"

    # Valid structure
    assert len(module_map.modules) > 0
    assert len(module_map.edges) > 0

    # Router should not have been called
    router.call_structured.assert_not_called()


# ---------------------------------------------------------------------------
# JSON round-trip serialization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_module_map_serialization():
    """ModuleMap serializes to JSON and deserializes back identically."""
    router = _make_mock_router()
    original = await analyze_codebase(FIXTURE_ROOT, router=router, enrich=False)

    json_str = original.model_dump_json()

    # Write to temp file, read back, deserialize
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(json_str)
        tmp_path = f.name

    restored_json = Path(tmp_path).read_text()
    restored = ModuleMap.model_validate_json(restored_json)
    assert original == restored


# ---------------------------------------------------------------------------
# Dependency edge correctness
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dependency_edges_correct():
    """Dependency edges match expected cross-module imports in ship_fixture."""
    router = _make_mock_router()
    module_map = await analyze_codebase(FIXTURE_ROOT, router=router, enrich=False)

    edge_pairs = {(e.source, e.target) for e in module_map.edges}

    expected_edges = [
        ("models", "types"),
        ("routes", "models"),
        ("routes", "types"),
        ("components", "types"),
        ("middleware", "models"),
    ]

    for src, tgt in expected_edges:
        assert (src, tgt) in edge_pairs, f"Missing edge {src} -> {tgt} in {edge_pairs}"
