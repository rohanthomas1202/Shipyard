"""Migration document generation for breaking contract changes."""
from __future__ import annotations

from datetime import datetime, timezone

MIGRATION_TEMPLATE = """# Migration: {contract_name}

**Generated:** {timestamp}
**Contract:** {contract_path}

## What Broke

{breaking_changes}

## Why

{explanation}

## Migration Steps

{steps}

## Verification

- [ ] All consuming agents updated
- [ ] Tests pass with new contract
- [ ] No runtime errors referencing old schema
"""


def generate_migration_doc(
    contract_name: str,
    contract_path: str,
    breaking_changes: list[str],
) -> str:
    """Generate a migration document for breaking contract changes.

    Args:
        contract_name: Relative name of the contract file.
        contract_path: Full path to the contract file.
        breaking_changes: List of human-readable breaking change descriptions.

    Returns:
        Markdown string ready to write to disk.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    changes_md = "\n".join(f"- {c}" for c in breaking_changes)
    explanation = (
        "The new contract version removes or modifies fields/endpoints/types "
        "that existing consumers depend on. All downstream agents must be updated "
        "before this contract is activated."
    )
    steps = (
        "1. Review each breaking change listed above\n"
        "2. Update all agents that consume this contract\n"
        "3. Run tests to verify no regressions\n"
        "4. Deploy updated agents before activating new contract"
    )
    return MIGRATION_TEMPLATE.format(
        contract_name=contract_name,
        timestamp=timestamp,
        contract_path=contract_path,
        breaking_changes=changes_md,
        explanation=explanation,
        steps=steps,
    )
