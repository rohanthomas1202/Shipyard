"""Static import/require edge extraction for TypeScript and JavaScript files."""

import re
from pathlib import Path


_TS_IMPORT_RE = re.compile(
    r"""(?:import\s+.*?\s+from\s+['"]([^'"]+)['"]|"""
    r"""require\s*\(\s*['"]([^'"]+)['"]\s*\))""",
    re.MULTILINE,
)

_EXTENSIONS = [".ts", ".tsx", ".js", ".jsx"]


def _resolve_import(source_file: Path, target: str, project_root: Path) -> Path | None:
    """Resolve a relative import to an absolute file path with extension fallback."""
    base = source_file.parent / target
    # Exact match
    if base.is_file():
        return base.resolve()
    # Extension fallback: .ts, .tsx, .js, .jsx
    for ext in _EXTENSIONS:
        candidate = base.with_suffix(ext) if not base.suffix else base
        if ext != base.suffix:
            candidate = Path(str(base) + ext)
        if candidate.is_file():
            return candidate.resolve()
    # Index file fallback: target/index.ts etc.
    for ext in _EXTENSIONS:
        candidate = base / f"index{ext}"
        if candidate.is_file():
            return candidate.resolve()
    return None


def extract_imports(file_path: Path, project_root: Path) -> list[str]:
    """Extract resolved relative import paths from a source file.

    Returns list of resolved file paths (relative to project_root) for
    relative imports only. External packages (no leading '.') are ignored.
    Per D-03: deterministic static analysis, no LLM inference.
    """
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    results: list[str] = []
    for match in _TS_IMPORT_RE.finditer(content):
        target = match.group(1) or match.group(2)
        if not target.startswith("."):
            continue
        resolved = _resolve_import(file_path, target, project_root)
        if resolved is None:
            continue
        try:
            rel = resolved.relative_to(project_root.resolve())
            results.append(str(rel))
        except ValueError:
            pass
    return results
