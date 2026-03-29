"""Context pack assembly for scoped agent execution."""
import os
import re
from dataclasses import dataclass, field

from agent.orchestrator.models import TaskNode

MAX_CONTEXT_FILES = 5

_IMPORT_RE = re.compile(
    r"^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.MULTILINE
)


@dataclass
class ContextPack:
    """Scoped file set delivered to an agent before execution."""

    task_id: str
    primary_files: list[str] = field(default_factory=list)
    dependency_files: list[str] = field(default_factory=list)
    contracts: list[str] = field(default_factory=list)
    recent_changes: list[str] = field(default_factory=list)

    @property
    def all_files(self) -> list[str]:
        """Deduplicated file list, capped at MAX_CONTEXT_FILES. Priority: primary > deps > contracts."""
        seen: set[str] = set()
        result: list[str] = []
        for f in self.primary_files + self.dependency_files + self.contracts:
            if f not in seen:
                seen.add(f)
                result.append(f)
        return result[:MAX_CONTEXT_FILES]


def parse_python_imports(file_path: str, project_path: str) -> list[str]:
    """Parse Python imports from a file and resolve to project-relative file paths.

    Handles ``from X import Y`` and ``import X`` forms. Returns only paths
    that exist on disk within *project_path*.
    """
    try:
        with open(file_path, "r") as f:
            content = f.read()
    except (FileNotFoundError, OSError):
        return []

    resolved: list[str] = []
    for match in _IMPORT_RE.finditer(content):
        module = match.group(1) or match.group(2)
        # Convert dotted module path to file path
        rel = module.replace(".", os.sep) + ".py"
        abs_path = os.path.join(project_path, rel)
        if os.path.isfile(abs_path):
            # Store as forward-slash relative path for consistency
            resolved.append(rel.replace(os.sep, "/"))
    return resolved


class ContextPackAssembler:
    """Builds a :class:`ContextPack` from task metadata and import analysis."""

    def __init__(self, project_path: str) -> None:
        self.project_path = project_path

    def assemble(
        self,
        task: TaskNode,
        recent_changes: list[str] | None = None,
    ) -> ContextPack:
        """Assemble a context pack for *task*.

        Primary files come from ``task.metadata["target_files"]``. Transitive
        dependencies are discovered via lightweight Python import parsing.
        Contract files come from ``task.contract_inputs``.
        """
        primary_files: list[str] = list(task.metadata.get("target_files", []))
        contracts: list[str] = list(task.contract_inputs)

        # Discover transitive dependencies via import analysis
        dep_set: set[str] = set()
        primary_set = set(primary_files)
        for pf in primary_files:
            abs_pf = os.path.join(self.project_path, pf)
            for dep in parse_python_imports(abs_pf, self.project_path):
                if dep not in primary_set:
                    dep_set.add(dep)

        return ContextPack(
            task_id=task.id,
            primary_files=primary_files,
            dependency_files=sorted(dep_set),
            contracts=contracts,
            recent_changes=recent_changes or [],
        )
