"""Tests for module ownership enforcement via post-hoc diff validation."""
import pytest
from unittest.mock import AsyncMock, patch

from agent.orchestrator.ownership import (
    OwnershipViolation,
    OwnershipValidator,
    build_ownership_map,
)
from agent.orchestrator.models import TaskNode


# ---------------------------------------------------------------------------
# build_ownership_map tests
# ---------------------------------------------------------------------------

def test_build_ownership_map_from_tasks():
    """build_ownership_map maps each target file to its task's module."""
    tasks = [
        TaskNode(
            id="t1", dag_id="d1", label="auth-module",
            metadata={"target_files": ["auth/login.py", "auth/tokens.py"], "module": "auth"},
        ),
        TaskNode(
            id="t2", dag_id="d1", label="api-module",
            metadata={"target_files": ["api/routes.py"], "module": "api"},
        ),
    ]
    omap = build_ownership_map(tasks)
    assert omap["auth/login.py"] == "auth"
    assert omap["auth/tokens.py"] == "auth"
    assert omap["api/routes.py"] == "api"


def test_build_ownership_map_uses_label_fallback():
    """build_ownership_map falls back to task.label when module not in metadata."""
    tasks = [
        TaskNode(
            id="t1", dag_id="d1", label="my-label",
            metadata={"target_files": ["src/app.py"]},
        ),
    ]
    omap = build_ownership_map(tasks)
    assert omap["src/app.py"] == "my-label"


def test_ownership_violation_fields():
    """OwnershipViolation has all required fields."""
    v = OwnershipViolation(
        file_path="auth/login.py",
        owning_module="auth",
        task_module="api",
        reason="File owned by auth, modified by api task",
    )
    assert v.file_path == "auth/login.py"
    assert v.owning_module == "auth"
    assert v.task_module == "api"
    assert "auth" in v.reason


# ---------------------------------------------------------------------------
# OwnershipValidator tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_no_violations():
    """validate returns empty list when all changed files belong to task's module."""
    omap = {"auth/login.py": "auth", "auth/tokens.py": "auth"}
    validator = OwnershipValidator("/fake/project", omap)

    with patch("agent.orchestrator.ownership.run_command_async", new_callable=AsyncMock) as mock_cmd:
        mock_cmd.return_value = {"stdout": "auth/login.py\n", "stderr": "", "exit_code": 0}
        violations = await validator.validate("t1", "auth")

    assert violations == []


@pytest.mark.asyncio
async def test_validate_with_violations():
    """validate returns violations for files owned by other modules."""
    omap = {"auth/login.py": "auth", "api/routes.py": "api"}
    validator = OwnershipValidator("/fake/project", omap)

    with patch("agent.orchestrator.ownership.run_command_async", new_callable=AsyncMock) as mock_cmd:
        mock_cmd.return_value = {
            "stdout": "auth/login.py\napi/routes.py\n",
            "stderr": "",
            "exit_code": 0,
        }
        violations = await validator.validate("t1", "auth")

    assert len(violations) == 1
    assert violations[0].file_path == "api/routes.py"
    assert violations[0].owning_module == "api"
    assert violations[0].task_module == "auth"


@pytest.mark.asyncio
async def test_validate_ignores_unowned_files():
    """validate ignores files not in the ownership map (shared/config)."""
    omap = {"auth/login.py": "auth"}
    validator = OwnershipValidator("/fake/project", omap)

    with patch("agent.orchestrator.ownership.run_command_async", new_callable=AsyncMock) as mock_cmd:
        mock_cmd.return_value = {
            "stdout": "auth/login.py\nconfig.yaml\nREADME.md\n",
            "stderr": "",
            "exit_code": 0,
        }
        violations = await validator.validate("t1", "auth")

    assert violations == []


@pytest.mark.asyncio
async def test_validate_empty_diff():
    """validate handles empty diff (no changes)."""
    omap = {"auth/login.py": "auth"}
    validator = OwnershipValidator("/fake/project", omap)

    with patch("agent.orchestrator.ownership.run_command_async", new_callable=AsyncMock) as mock_cmd:
        mock_cmd.return_value = {"stdout": "", "stderr": "", "exit_code": 0}
        violations = await validator.validate("t1", "auth")

    assert violations == []


@pytest.mark.asyncio
async def test_validate_git_command_called_correctly():
    """validate calls git diff with correct arguments."""
    omap = {}
    validator = OwnershipValidator("/fake/project", omap)

    with patch("agent.orchestrator.ownership.run_command_async", new_callable=AsyncMock) as mock_cmd:
        mock_cmd.return_value = {"stdout": "", "stderr": "", "exit_code": 0}
        await validator.validate("t1", "auth")

    mock_cmd.assert_called_once_with(
        ["git", "diff", "--name-only", "main...HEAD"],
        cwd="/fake/project",
    )
