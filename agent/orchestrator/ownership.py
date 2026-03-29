"""Module ownership enforcement via post-hoc diff validation."""
from dataclasses import dataclass

from agent.orchestrator.models import TaskNode
from agent.tools.shell import run_command_async


@dataclass
class OwnershipViolation:
    """A file modified outside the task's designated module."""

    file_path: str
    owning_module: str | None
    task_module: str
    reason: str


def build_ownership_map(tasks: list[TaskNode]) -> dict[str, str]:
    """Create a file-to-module mapping from task metadata.

    Each file listed in ``task.metadata["target_files"]`` is mapped to the
    task's module (from ``task.metadata["module"]``, falling back to
    ``task.label``).  Later tasks overwrite earlier mappings for shared files
    (last-writer-wins).
    """
    ownership: dict[str, str] = {}
    for task in tasks:
        module = task.metadata.get("module", task.label)
        for file_path in task.metadata.get("target_files", []):
            ownership[file_path] = module
    return ownership


class OwnershipValidator:
    """Validates that a task only modified files it owns.

    Uses ``git diff --name-only main...HEAD`` to detect changed files, then
    checks each against the ownership map.  Files not in the map are
    considered shared/unowned and are allowed.  Violations are returned for
    the scheduler to treat as task failure (soft enforcement per D-05).
    """

    def __init__(self, project_path: str, ownership_map: dict[str, str]) -> None:
        self.project_path = project_path
        self.ownership_map = ownership_map

    async def validate(
        self, task_id: str, task_module: str
    ) -> list[OwnershipViolation]:
        """Return ownership violations for the current diff."""
        result = await run_command_async(
            ["git", "diff", "--name-only", "main...HEAD"],
            cwd=self.project_path,
        )
        changed_files = [
            line.strip()
            for line in result["stdout"].splitlines()
            if line.strip()
        ]

        violations: list[OwnershipViolation] = []
        for file_path in changed_files:
            owner = self.ownership_map.get(file_path)
            if owner is not None and owner != task_module:
                violations.append(
                    OwnershipViolation(
                        file_path=file_path,
                        owning_module=owner,
                        task_module=task_module,
                        reason=f"File owned by {owner}, modified by {task_module} task",
                    )
                )
        return violations
