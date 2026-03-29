"""Pydantic models for the codebase analyzer module map."""

from pydantic import BaseModel, Field


class FileInfo(BaseModel):
    """A single source file within a module."""
    path: str
    loc: int = 0
    exports: list[str] = Field(default_factory=list)


class ModuleInfo(BaseModel):
    """A module in the codebase -- directory-level grouping."""
    name: str
    path: str
    files: list[FileInfo] = Field(default_factory=list)
    summary: str = ""
    dependencies: list[str] = Field(default_factory=list)


class DependencyEdge(BaseModel):
    """Directed edge: source module imports from target module."""
    source: str
    target: str
    import_count: int = 1


class ModuleMap(BaseModel):
    """Complete module map output -- single JSON file (D-04)."""
    project_path: str
    modules: list[ModuleInfo] = Field(default_factory=list)
    edges: list[DependencyEdge] = Field(default_factory=list)
    total_files: int = 0
    total_loc: int = 0
