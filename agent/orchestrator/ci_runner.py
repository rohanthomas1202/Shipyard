"""Local CI pipeline with stage-level tracking."""
import os
import time
from dataclasses import dataclass, field

from agent.tools.shell import run_command_async


@dataclass
class CIStage:
    name: str
    command: list[str]
    timeout: int = 120
    cwd_suffix: str = ""


@dataclass
class CIStageResult:
    name: str
    passed: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0


@dataclass
class CIPipelineResult:
    stages: list[CIStageResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(s.passed for s in self.stages)

    @property
    def first_failure(self) -> CIStageResult | None:
        return next((s for s in self.stages if not s.passed), None)

    @property
    def error_output(self) -> str:
        fail = self.first_failure
        if fail is None:
            return ""
        return fail.stderr if fail.stderr else fail.stdout


DEFAULT_PIPELINE: list[CIStage] = [
    CIStage("typecheck", ["python3", "-m", "py_compile"], timeout=30),
    CIStage("lint", ["npm", "run", "lint"], timeout=60, cwd_suffix="web/"),
    CIStage("test", ["python3", "-m", "pytest", "--tb=short", "-x", "-q"], timeout=180),
    CIStage("build", ["npm", "run", "build"], timeout=120, cwd_suffix="web/"),
]


class CIRunner:
    def __init__(self, project_path: str, pipeline: list[CIStage] | None = None):
        self._project_path = project_path
        self._pipeline = pipeline if pipeline is not None else DEFAULT_PIPELINE

    async def run_pipeline(self) -> CIPipelineResult:
        results: list[CIStageResult] = []
        for stage in self._pipeline:
            cwd = (
                os.path.join(self._project_path, stage.cwd_suffix)
                if stage.cwd_suffix
                else self._project_path
            )
            start = time.monotonic()
            result = await run_command_async(
                stage.command, cwd=cwd, timeout=stage.timeout
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            passed = result["exit_code"] == 0
            stage_result = CIStageResult(
                name=stage.name,
                passed=passed,
                exit_code=result["exit_code"],
                stdout=result["stdout"],
                stderr=result["stderr"],
                duration_ms=duration_ms,
            )
            results.append(stage_result)
            if not passed:
                break
        return CIPipelineResult(stages=results)
