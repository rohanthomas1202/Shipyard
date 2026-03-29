"""Directory-based module discovery for codebase analysis."""

import re
from pathlib import Path

from agent.analyzer.models import FileInfo, ModuleInfo, ModuleMap, DependencyEdge
from agent.analyzer.imports import extract_imports

_SOURCE_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".py"}


def _count_lines(path: Path) -> int:
    """Count non-empty lines in a file."""
    try:
        return sum(
            1 for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip()
        )
    except Exception:
        return 0


def _extract_exports(path: Path) -> list[str]:
    """Extract exported names from a TypeScript/JavaScript file."""
    content = path.read_text(encoding="utf-8", errors="ignore")
    exports: list[str] = []
    for match in re.finditer(
        r'export\s+(?:async\s+)?(?:function|class|const|let|var|interface|type|enum)\s+(\w+)',
        content,
    ):
        exports.append(match.group(1))
    for match in re.finditer(
        r'export\s+default\s+(?:function|class)\s+(\w+)', content
    ):
        exports.append(match.group(1))
    if re.search(r'export\s+default\s+', content) and not re.search(
        r'export\s+default\s+(?:function|class)\s+\w+', content
    ):
        exports.append("default")
    return exports


def discover_modules(project_root: str | Path, src_dir: str = "src") -> ModuleMap:
    """Scan a project directory and build a ModuleMap with dependency edges.

    Per D-01: directory-based for initial module structure.
    Per D-03: import edges from static import analysis only.
    Per D-04: returns a single ModuleMap object (serializable to JSON).

    Module = top-level directory under src_dir. Each module contains files.
    Dependency edges connect modules, not individual files.
    """
    root = Path(project_root).resolve()
    src = root / src_dir
    if not src.is_dir():
        return ModuleMap(project_path=str(root))

    # Discover modules (top-level directories under src/)
    modules: dict[str, ModuleInfo] = {}
    for child in sorted(src.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        files: list[FileInfo] = []
        for f in sorted(child.rglob("*")):
            if f.is_file() and f.suffix in _SOURCE_EXTENSIONS:
                files.append(FileInfo(
                    path=str(f.relative_to(root)),
                    loc=_count_lines(f),
                    exports=_extract_exports(f),
                ))
        if files:
            modules[child.name] = ModuleInfo(
                name=child.name,
                path=str(child.relative_to(root)),
                files=files,
            )

    # Build file-to-module lookup
    file_to_module: dict[str, str] = {}
    for mod_name, mod in modules.items():
        for fi in mod.files:
            file_to_module[fi.path] = mod_name

    # Extract import edges per D-03
    edge_counts: dict[tuple[str, str], int] = {}
    for mod_name, mod in modules.items():
        for fi in mod.files:
            file_path = root / fi.path
            imported_paths = extract_imports(file_path, root)
            for imp_path in imported_paths:
                target_module = file_to_module.get(imp_path)
                if target_module and target_module != mod_name:
                    key = (mod_name, target_module)
                    edge_counts[key] = edge_counts.get(key, 0) + 1
                    if target_module not in mod.dependencies:
                        mod.dependencies.append(target_module)

    edges = [
        DependencyEdge(source=src_mod, target=tgt_mod, import_count=count)
        for (src_mod, tgt_mod), count in sorted(edge_counts.items())
    ]

    total_files = sum(len(m.files) for m in modules.values())
    total_loc = sum(fi.loc for m in modules.values() for fi in m.files)

    return ModuleMap(
        project_path=str(root),
        modules=list(modules.values()),
        edges=edges,
        total_files=total_files,
        total_loc=total_loc,
    )
