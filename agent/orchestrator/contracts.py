"""File-based versioned contract store for inter-agent agreements."""
from __future__ import annotations

from pathlib import Path


class ContractStore:
    """Read, write, and list contract files from a contracts/ directory.

    Contracts are versioned specification files (.sql, .yaml, .ts, .json)
    that define inter-agent agreements such as DB schemas, API definitions,
    shared TypeScript types, and design system tokens.
    """

    CONTRACT_TYPES: dict[str, str] = {
        ".sql": "DB schema",
        ".yaml": "API definition (OpenAPI)",
        ".ts": "Shared TypeScript types",
        ".json": "Design system / config",
    }

    def __init__(self, project_path: str) -> None:
        self._base = Path(project_path) / "contracts"

    def read_contract(self, name: str) -> str | None:
        """Read a contract file by relative path. Returns None if missing."""
        path = self._base / name
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    def write_contract(self, name: str, content: str) -> Path:
        """Write a contract file, creating parent directories as needed."""
        path = self._base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path.resolve()

    def list_contracts(self) -> list[str]:
        """Return relative paths of all contract files in the store."""
        if not self._base.is_dir():
            return []
        return sorted(
            str(p.relative_to(self._base))
            for p in self._base.rglob("*")
            if p.is_file()
        )

    def contract_exists(self, name: str) -> bool:
        """Return whether a contract file exists."""
        return (self._base / name).is_file()
