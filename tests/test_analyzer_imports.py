"""Tests for the analyzer import parser and module discovery."""

from pathlib import Path

from agent.analyzer.imports import extract_imports
from agent.analyzer.discovery import discover_modules
from agent.analyzer.models import ModuleMap

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "ship_fixture"


# ---------------------------------------------------------------------------
# extract_imports tests
# ---------------------------------------------------------------------------

def test_extract_imports_relative():
    """users.ts imports from ../models/user and ../types."""
    file_path = FIXTURE_ROOT / "src" / "routes" / "users.ts"
    results = extract_imports(file_path, FIXTURE_ROOT)
    # Normalize to forward slashes for cross-platform
    normalized = [r.replace("\\", "/") for r in results]
    assert any("src/models/user.ts" in r for r in normalized), f"Expected models/user.ts in {normalized}"
    assert any("src/types/index.ts" in r for r in normalized), f"Expected types/index.ts in {normalized}"


def test_extract_imports_ignores_external():
    """health.ts only imports express -- external packages are ignored."""
    file_path = FIXTURE_ROOT / "src" / "routes" / "health.ts"
    results = extract_imports(file_path, FIXTURE_ROOT)
    assert len(results) == 0, f"Expected no relative imports, got {results}"


# ---------------------------------------------------------------------------
# discover_modules tests
# ---------------------------------------------------------------------------

def test_discover_modules_finds_five_modules():
    """Ship fixture has exactly 5 modules under src/."""
    module_map = discover_modules(FIXTURE_ROOT)
    module_names = {m.name for m in module_map.modules}
    assert len(module_map.modules) == 5, f"Expected 5 modules, got {len(module_map.modules)}: {module_names}"
    assert module_names == {"components", "middleware", "models", "routes", "types"}


def test_discover_modules_edges():
    """Verify cross-module dependency edges exist and no self-edges."""
    module_map = discover_modules(FIXTURE_ROOT)
    edge_pairs = {(e.source, e.target) for e in module_map.edges}

    # Expected edges based on fixture imports
    assert ("models", "types") in edge_pairs, f"Missing models->types edge in {edge_pairs}"
    assert ("routes", "models") in edge_pairs, f"Missing routes->models edge in {edge_pairs}"
    assert ("routes", "types") in edge_pairs, f"Missing routes->types edge in {edge_pairs}"
    assert ("components", "types") in edge_pairs, f"Missing components->types edge in {edge_pairs}"
    assert ("middleware", "models") in edge_pairs, f"Missing middleware->models edge in {edge_pairs}"

    # No self-edges
    for e in module_map.edges:
        assert e.source != e.target, f"Self-edge found: {e.source} -> {e.target}"


def test_module_map_json_roundtrip():
    """ModuleMap serializes to JSON and deserializes back identically."""
    original = discover_modules(FIXTURE_ROOT)
    json_str = original.model_dump_json()
    restored = ModuleMap.model_validate_json(json_str)
    assert original == restored


def test_file_info_has_loc():
    """Files in the types module should have non-zero line counts."""
    module_map = discover_modules(FIXTURE_ROOT)
    types_mod = next(m for m in module_map.modules if m.name == "types")
    for fi in types_mod.files:
        assert fi.loc > 0, f"File {fi.path} has loc=0"
