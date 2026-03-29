"""Tests for local CI pipeline runner."""
import pytest
from unittest.mock import AsyncMock, patch

from agent.orchestrator.ci_runner import (
    CIRunner,
    CIStage,
    CIStageResult,
    CIPipelineResult,
    DEFAULT_PIPELINE,
)


# ---------------------------------------------------------------------------
# CIPipelineResult properties
# ---------------------------------------------------------------------------

def test_pipeline_result_passed_all_pass():
    result = CIPipelineResult(stages=[
        CIStageResult(name="typecheck", passed=True, exit_code=0),
        CIStageResult(name="lint", passed=True, exit_code=0),
        CIStageResult(name="test", passed=True, exit_code=0),
        CIStageResult(name="build", passed=True, exit_code=0),
    ])
    assert result.passed is True


def test_pipeline_result_passed_one_fail():
    result = CIPipelineResult(stages=[
        CIStageResult(name="typecheck", passed=True, exit_code=0),
        CIStageResult(name="lint", passed=False, exit_code=1, stderr="lint error"),
    ])
    assert result.passed is False


def test_pipeline_result_first_failure():
    result = CIPipelineResult(stages=[
        CIStageResult(name="typecheck", passed=True, exit_code=0),
        CIStageResult(name="lint", passed=False, exit_code=1, stderr="lint err"),
    ])
    failure = result.first_failure
    assert failure is not None
    assert failure.name == "lint"


def test_pipeline_result_first_failure_none_when_all_pass():
    result = CIPipelineResult(stages=[
        CIStageResult(name="typecheck", passed=True, exit_code=0),
    ])
    assert result.first_failure is None


def test_pipeline_result_error_output_from_stderr():
    result = CIPipelineResult(stages=[
        CIStageResult(name="test", passed=False, exit_code=1, stderr="AssertionError", stdout="collected 5 items"),
    ])
    assert result.error_output == "AssertionError"


def test_pipeline_result_error_output_falls_back_to_stdout():
    result = CIPipelineResult(stages=[
        CIStageResult(name="test", passed=False, exit_code=1, stderr="", stdout="FAILED tests/foo.py"),
    ])
    assert result.error_output == "FAILED tests/foo.py"


def test_pipeline_result_error_output_empty_when_all_pass():
    result = CIPipelineResult(stages=[
        CIStageResult(name="typecheck", passed=True, exit_code=0),
    ])
    assert result.error_output == ""


# ---------------------------------------------------------------------------
# DEFAULT_PIPELINE constant
# ---------------------------------------------------------------------------

def test_default_pipeline_has_four_stages():
    assert len(DEFAULT_PIPELINE) == 4
    names = [s.name for s in DEFAULT_PIPELINE]
    assert names == ["typecheck", "lint", "test", "build"]


# ---------------------------------------------------------------------------
# CIRunner.run_pipeline
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_pipeline_all_pass():
    mock_result = {"stdout": "ok", "stderr": "", "exit_code": 0}
    with patch("agent.orchestrator.ci_runner.run_command_async", new_callable=AsyncMock, return_value=mock_result):
        runner = CIRunner("/tmp/project")
        result = await runner.run_pipeline()
    assert result.passed is True
    assert len(result.stages) == 4
    assert all(s.passed for s in result.stages)


@pytest.mark.asyncio
async def test_run_pipeline_stops_on_first_failure():
    call_count = 0

    async def mock_cmd(argv, cwd=".", timeout=60):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            return {"stdout": "", "stderr": "lint error", "exit_code": 1}
        return {"stdout": "ok", "stderr": "", "exit_code": 0}

    with patch("agent.orchestrator.ci_runner.run_command_async", side_effect=mock_cmd):
        runner = CIRunner("/tmp/project")
        result = await runner.run_pipeline()
    assert result.passed is False
    assert len(result.stages) == 2
    assert result.stages[0].passed is True
    assert result.stages[1].passed is False
    assert result.first_failure.name == "lint"


@pytest.mark.asyncio
async def test_run_pipeline_timeout():
    async def mock_cmd(argv, cwd=".", timeout=60):
        return {"stdout": "", "stderr": "Command timed out", "exit_code": -1}

    with patch("agent.orchestrator.ci_runner.run_command_async", side_effect=mock_cmd):
        runner = CIRunner("/tmp/project")
        result = await runner.run_pipeline()
    assert result.passed is False
    assert len(result.stages) == 1
    assert result.stages[0].exit_code == -1


@pytest.mark.asyncio
async def test_run_pipeline_cwd_suffix():
    calls = []

    async def mock_cmd(argv, cwd=".", timeout=60):
        calls.append(cwd)
        return {"stdout": "ok", "stderr": "", "exit_code": 0}

    pipeline = [
        CIStage("backend", ["pytest"], timeout=30),
        CIStage("frontend", ["npm", "run", "build"], timeout=60, cwd_suffix="web/"),
    ]
    with patch("agent.orchestrator.ci_runner.run_command_async", side_effect=mock_cmd):
        runner = CIRunner("/tmp/project", pipeline=pipeline)
        await runner.run_pipeline()
    assert calls[0] == "/tmp/project"
    assert calls[1] == "/tmp/project/web/"


@pytest.mark.asyncio
async def test_run_pipeline_stage_has_duration():
    async def mock_cmd(argv, cwd=".", timeout=60):
        return {"stdout": "", "stderr": "", "exit_code": 0}

    pipeline = [CIStage("quick", ["echo"], timeout=5)]
    with patch("agent.orchestrator.ci_runner.run_command_async", side_effect=mock_cmd):
        runner = CIRunner("/tmp/project", pipeline=pipeline)
        result = await runner.run_pipeline()
    assert result.stages[0].duration_ms >= 0
