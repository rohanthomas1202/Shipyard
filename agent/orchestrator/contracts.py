"""File-based versioned contract store for inter-agent agreements."""
from __future__ import annotations

import difflib
from pathlib import Path

from agent.orchestrator.migration import generate_migration_doc


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

    def check_compatibility(self, name: str, new_content: str) -> dict:
        """Compare old vs new contract content. Returns compatibility report.

        Returns dict with keys:
        - compatible (bool): True if no breaking changes detected
        - diff (str): Unified diff output
        - changes (list[str]): All changed lines
        - breaking (list[str]): Human-readable breaking change descriptions
        """
        old_content = self.read_contract(name)
        if old_content is None:
            return {"compatible": True, "diff": "", "changes": [], "breaking": []}

        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"old/{name}", tofile=f"new/{name}",
        ))

        if not diff:
            return {"compatible": True, "diff": "", "changes": [], "breaking": []}

        removals = [
            l.rstrip() for l in diff
            if l.startswith('-') and not l.startswith('---')
        ]
        additions = [
            l.rstrip() for l in diff
            if l.startswith('+') and not l.startswith('+++')
        ]

        # Filter out removals whose content also appears in additions
        # (e.g. line reformatted or trailing-newline changed, not truly deleted)
        addition_contents = {a.lstrip('+').strip() for a in additions}
        true_removals = [
            r for r in removals
            if r.lstrip('-').strip() not in addition_contents
        ]

        breaking = self._detect_breaking_changes(name, true_removals)
        return {
            "compatible": len(breaking) == 0,
            "diff": "".join(diff),
            "changes": removals + additions,
            "breaking": breaking,
        }

    def _detect_breaking_changes(self, name: str, removals: list[str]) -> list[str]:
        """Detect structural breaking changes from removed lines.

        Looks for contract-type-specific indicators rather than flagging
        all removals (avoids false positives from whitespace/comments).
        """
        breaking: list[str] = []
        suffix = name.rsplit(".", 1)[-1] if "." in name else ""

        for line in removals:
            content = line.lstrip("-").strip()
            if not content or content.startswith("--") or content.startswith("#") or content.startswith("//"):
                continue  # Skip empty lines and comments

            if suffix == "sql":
                # Removed column, table, or constraint
                lower = content.lower()
                if any(kw in lower for kw in (
                    "create table", "alter table", "column",
                    "integer", "text", "real", "blob",
                    "varchar", "boolean", "timestamp",
                )):
                    breaking.append(f"SQL removal: {content}")
            elif suffix in ("yaml", "yml"):
                # Removed path/endpoint/key
                if ":" in content and not content.strip().startswith("#"):
                    breaking.append(f"YAML key removed: {content}")
            elif suffix == "ts":
                # Removed export/interface/type
                if any(kw in content for kw in ("export ", "interface ", "type ")):
                    breaking.append(f"TypeScript export removed: {content}")
            elif suffix == "json":
                # Removed key (line with "key":)
                stripped = content.strip().rstrip(",")
                if ":" in stripped and stripped.startswith('"'):
                    breaking.append(f"JSON key removed: {content}")

        return breaking

    def write_contract_safe(self, name: str, content: str) -> tuple[Path, dict]:
        """Write a contract with backward compatibility check.

        Returns (path, compatibility_report). If breaking changes detected,
        also writes a migration doc alongside the contract.
        """
        report = self.check_compatibility(name, content)
        path = self.write_contract(name, content)

        if not report["compatible"] and report["breaking"]:
            migration_name = name.rsplit(".", 1)[0] + ".migration.md"
            migration_content = generate_migration_doc(
                contract_name=name,
                contract_path=str(path),
                breaking_changes=report["breaking"],
            )
            self.write_contract(migration_name, migration_content)

        return path, report
