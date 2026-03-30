"""Integration tests for the Ship rebuild pipeline scripts.

Validates that orchestration and deployment scripts import correctly
and that pipeline modules are properly wired together.
Covers SHIP-05 (deploy scripts work).
"""
import importlib
import inspect
import os

import pytest


def test_rebuild_script_imports():
    """Verify scripts.ship_rebuild imports and exposes expected functions."""
    import scripts.ship_rebuild as mod

    assert hasattr(mod, "run_rebuild"), "Missing run_rebuild function"
    assert hasattr(mod, "clone_repo"), "Missing clone_repo function"
    assert hasattr(mod, "init_output_repo"), "Missing init_output_repo function"
    assert hasattr(mod, "main"), "Missing main function"


def test_deploy_script_imports():
    """Verify scripts.deploy_railway imports and exposes expected functions."""
    import scripts.deploy_railway as mod

    assert hasattr(mod, "run_deploy"), "Missing run_deploy function"
    assert hasattr(mod, "check_auth"), "Missing check_auth function"
    assert hasattr(mod, "deploy"), "Missing deploy function"
    assert hasattr(mod, "verify_health"), "Missing verify_health function"
    assert hasattr(mod, "main"), "Missing main function"


def test_ship_ci_pipeline_structure():
    """Verify SHIP_CI_PIPELINE has 4 stages with correct names."""
    from agent.orchestrator.ship_ci import SHIP_CI_PIPELINE

    assert len(SHIP_CI_PIPELINE) == 4, f"Expected 4 stages, got {len(SHIP_CI_PIPELINE)}"
    names = [s.name for s in SHIP_CI_PIPELINE]
    assert names == ["typecheck", "lint", "test", "build"], f"Unexpected stage names: {names}"
    # First stage command should use tsc (TypeScript, not Python)
    assert "tsc" in " ".join(SHIP_CI_PIPELINE[0].command), (
        f"First stage should use tsc: {SHIP_CI_PIPELINE[0].command}"
    )


def test_ship_executor_callable():
    """Verify build_agent_executor is a regular callable (not a coroutine)."""
    from agent.orchestrator.ship_executor import build_agent_executor

    assert callable(build_agent_executor), "build_agent_executor should be callable"
    assert not inspect.iscoroutinefunction(build_agent_executor), (
        "build_agent_executor should not be a coroutine function"
    )


def test_env_template_exists():
    """Verify railway_template.env exists with required variables."""
    template_path = os.path.join(
        os.path.dirname(__file__), "..", "scripts", "railway_template.env"
    )
    assert os.path.isfile(template_path), f"Template not found: {template_path}"
    with open(template_path) as f:
        content = f.read()
    assert "DATABASE_URL" in content, "Template missing DATABASE_URL"
    assert "NODE_ENV" in content, "Template missing NODE_ENV"
    # Count non-comment, non-empty lines
    meaningful_lines = [
        line for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert len(meaningful_lines) >= 5, (
        f"Expected at least 5 env vars, got {len(meaningful_lines)}"
    )


def test_rebuild_script_constants():
    """Verify ship_rebuild exports expected constants."""
    from scripts.ship_rebuild import DEFAULT_SHIP_REPO, DEFAULT_OUTPUT_DIR

    assert "github.com" in DEFAULT_SHIP_REPO, (
        f"DEFAULT_SHIP_REPO should reference github.com: {DEFAULT_SHIP_REPO}"
    )
    assert isinstance(DEFAULT_OUTPUT_DIR, str), "DEFAULT_OUTPUT_DIR should be a string"
    assert DEFAULT_OUTPUT_DIR.startswith("/"), (
        f"DEFAULT_OUTPUT_DIR should be an absolute path: {DEFAULT_OUTPUT_DIR}"
    )
