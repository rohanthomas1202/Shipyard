# Phase 13: Analyzer + Planner Agents - Research

**Researched:** 2026-03-29
**Domain:** Codebase analysis, LLM-driven planning pipelines, DAG construction
**Confidence:** HIGH

## Summary

Phase 13 builds two new agent modules: an **Analyzer** that parses a codebase into a structured module map with dependency graph, and a **Planner** that decomposes that map through a three-layer pipeline (PRD -> Tech Spec -> Task DAG) into bounded, executable tasks. Both integrate with the Phase 12 orchestrator foundation (TaskDAG, ContractStore, DAGScheduler).

The core technical challenge is reliable structured LLM output parsing at each pipeline stage. The project already has `call_llm_structured` (OpenAI structured outputs via Pydantic models) in `agent/llm.py` and `ModelRouter.call_structured()` in `agent/router.py` -- these should be used for all three Planner layers rather than raw JSON parsing with fallbacks. The Analyzer's import-edge discovery is deterministic (static analysis), while module enrichment uses LLM summarization.

**Primary recommendation:** Use Pydantic models with `call_structured` for all LLM output (module summaries, PRDs, Tech Specs, Task DAG), leveraging OpenAI's native structured output to eliminate parsing failures. Build the fixture first, then Analyzer, then Planner pipeline, testing each layer independently.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: Hybrid discovery -- directory-based for initial module structure, then LLM reads each module to enrich with semantic understanding (purpose, public API, inter-module dependencies)
- D-02: Tiered module map -- lean map (name, file list, exports, dependency edges, 1-sentence summary) for all modules, with rich detail (function signatures, class hierarchies, LOC counts) only for modules the Planner flags as complex. Two-pass approach.
- D-03: Import edges only for dependency graph -- static import/require analysis. Module A imports from module B = directed edge. Deterministic, no LLM inference for edges.
- D-04: Single JSON output file (module-map.json) containing all modules, edges, and summaries. Fits in context for most codebases, easy to pass to Planner as one file.
- D-05: Sequential single-pass pipeline -- PRD from module map -> Tech Spec from PRD -> Task DAG from Tech Spec. One LLM call per layer. Validation gate at each transition.
- D-06: Structural validation only between layers -- check DAG is acyclic, tasks reference valid contracts, every module is covered, LOC/file bounds met. Automated, no LLM review pass.
- D-07: o3 for all three layers (PRD, Tech Spec, Task DAG). Planning is the highest-reasoning task.
- D-08: PRDs and Tech Specs stored as git-tracked markdown files in a plans/ directory alongside contracts/.
- D-09: Hard enforcement with escape hatch -- validation rejects any task exceeding <=300 LOC / <=3 files, but Planner can mark specific tasks as "indivisible" with justification.
- D-10: LLM estimation for LOC per task -- o3 estimates LOC based on Tech Spec description.
- D-11: Fixture subset, not real Ship repo -- a minimal Ship-like fixture with 5-10 files.
- D-12: No Ship repo clone needed for Phase 13.

### Claude's Discretion
- Analyzer prompt engineering (how to instruct o3 for module summarization)
- Module map JSON schema design
- PRD and Tech Spec markdown template structure
- How the Planner invokes the Analyzer's enrichment pass for complex modules
- Validation error message format and reporting
- Cost estimation formula for the validation gate

### Deferred Ideas (OUT OF SCOPE)
- Failure classification system A/B/C/D routing errors to handlers (Phase 15)
- Module ownership model preventing cross-agent conflicts (Phase 15)
- Contract backward compatibility checks and migration strategy (Phase 14)
- DAG visualization in frontend (Phase 14)
- Using Shipyard's own codebase as a secondary test target
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ANLZ-01 | Analyzer agent parses a codebase and outputs a module map with dependency graph | Hybrid discovery (D-01, D-03) + static import analysis + NetworkX DiGraph for dependency edges. Module map stored as JSON (D-04). |
| ANLZ-02 | Analyzer generates per-module summaries for context pack assembly | LLM enrichment pass (D-02) using `call_structured` with Pydantic models for summary schema. ContextAssembler reuse for token budget. |
| PLAN-01 | Planner generates PRDs from module map, decomposing into buildable units | First pipeline layer. o3 call (D-07) producing structured PRD. Stored as markdown in plans/ (D-08). |
| PLAN-02 | Planner generates Tech Specs from PRDs (API contracts, DB schema, component interfaces) | Second pipeline layer. o3 call producing Tech Spec with contract definitions. Validation gate between PRD->Spec (D-06). |
| PLAN-03 | Planner generates a Task DAG from Tech Specs with <=300 LOC / <=3 files per task | Third pipeline layer. Output must produce TaskNode/TaskEdge objects compatible with orchestrator models. Hard bounds (D-09) with escape hatch. |
| PLAN-04 | Plan validation detects dependency cycles, validates contract completeness, estimates cost before execution | Structural validation (D-06) using NetworkX cycle detection, contract reference checking, and token-based cost estimation. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| networkx | 3.6.1 | Dependency graph construction and cycle detection | Already used in Phase 12 TaskDAG. Provides `is_directed_acyclic_graph()`, `topological_generations()`. |
| pydantic | 2.12.5 | Structured output models for all pipeline stages | Already used throughout project. Enables `call_llm_structured()` with OpenAI structured outputs. |
| openai | >=1.60.0 | LLM calls via `agent/llm.py` | Project standard. Structured output via `beta.chat.completions.parse()`. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pathlib | stdlib | Directory traversal for module discovery | File system scanning in Analyzer |
| re | stdlib | Import statement regex parsing | Static import edge extraction |
| json | stdlib | Module map serialization | Writing module-map.json output |

### No New Dependencies Needed

The phase requires no new pip packages. All functionality can be built with existing dependencies (networkx, pydantic, openai via agent/llm.py).

## Architecture Patterns

### Recommended Project Structure
```
agent/
  analyzer/
    __init__.py
    discovery.py        # Directory scanning, file listing per module
    imports.py          # Static import/require edge extraction
    enrichment.py       # LLM module summarization
    models.py           # ModuleInfo, ModuleMap, DependencyEdge Pydantic models
    analyzer.py         # Top-level analyze() orchestrator function
  planner_v2/
    __init__.py
    pipeline.py         # Sequential PRD -> Spec -> DAG pipeline
    prd.py              # PRD generation layer
    tech_spec.py        # Tech Spec generation layer
    dag_builder.py      # Task DAG construction layer
    validation.py       # Structural validation gates
    models.py           # PRDOutput, TechSpecOutput, TaskDAGOutput Pydantic models
    prompts.py          # System/user prompts for all three layers
tests/
  fixtures/
    ship_fixture/       # 5-10 file Ship-like fixture (extends existing ship_sample_project)
  test_analyzer.py
  test_analyzer_imports.py
  test_planner_pipeline.py
  test_planner_validation.py
plans/                  # Output directory for PRD and Tech Spec markdown (per D-08)
```

### Pattern 1: Structured LLM Output via Pydantic

**What:** Use `router.call_structured(task_type, system, user, response_model)` for all pipeline layers instead of raw JSON parsing.

**When to use:** Every LLM call in both Analyzer and Planner.

**Example:**
```python
# Source: agent/llm.py line 69-91 (existing call_llm_structured)
from pydantic import BaseModel, Field

class ModuleSummary(BaseModel):
    """LLM-generated module summary for enrichment pass."""
    purpose: str = Field(description="1-sentence summary of module purpose")
    public_api: list[str] = Field(description="Exported functions/classes")
    semantic_dependencies: list[str] = Field(description="Modules this depends on semantically")

# In enrichment.py:
summary = await router.call_structured(
    "analyze_enrich",
    ENRICHMENT_SYSTEM_PROMPT,
    user_prompt_with_file_contents,
    response_model=ModuleSummary,
)
```

### Pattern 2: Static Import Edge Extraction

**What:** Regex-based parsing of import/require statements to build deterministic dependency edges (D-03).

**When to use:** Analyzer dependency graph construction. No LLM involvement.

**Example:**
```python
import re
from pathlib import Path

# TypeScript/JavaScript import patterns
_TS_IMPORT_RE = re.compile(
    r"""(?:import\s+.*?\s+from\s+['"]([^'"]+)['"]|"""
    r"""require\s*\(\s*['"]([^'"]+)['"]\s*\))""",
    re.MULTILINE,
)

def extract_imports(file_path: Path, project_root: Path) -> list[str]:
    """Extract relative import targets from a source file."""
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    imports = []
    for match in _TS_IMPORT_RE.finditer(content):
        target = match.group(1) or match.group(2)
        if target.startswith("."):  # Relative import = internal dependency
            resolved = (file_path.parent / target).resolve()
            try:
                rel = resolved.relative_to(project_root)
                imports.append(str(rel))
            except ValueError:
                pass
    return imports
```

### Pattern 3: Sequential Pipeline with Validation Gates

**What:** Each pipeline layer produces output, validates it structurally, then feeds to the next layer (D-05, D-06).

**When to use:** The three-layer Planner pipeline.

**Example:**
```python
async def run_pipeline(module_map: ModuleMap, router: ModelRouter) -> PipelineResult:
    """Execute PRD -> Tech Spec -> Task DAG with validation gates."""
    # Layer 1: PRD
    prd = await generate_prd(module_map, router)
    prd_errors = validate_prd(prd, module_map)
    if prd_errors:
        raise PlanValidationError("PRD validation failed", prd_errors)

    # Layer 2: Tech Spec
    spec = await generate_tech_spec(prd, module_map, router)
    spec_errors = validate_tech_spec(spec, prd)
    if spec_errors:
        raise PlanValidationError("Tech Spec validation failed", spec_errors)

    # Layer 3: Task DAG
    task_dag = await generate_task_dag(spec, router)
    dag_errors = validate_task_dag(task_dag, spec)
    if dag_errors:
        raise PlanValidationError("Task DAG validation failed", dag_errors)

    return PipelineResult(prd=prd, spec=spec, dag=task_dag)
```

### Pattern 4: TaskDAG.from_definition() Integration

**What:** Planner's Task DAG output produces dicts compatible with `TaskDAG.from_definition()` (Phase 12).

**When to use:** Converting LLM Task DAG output into the orchestrator's TaskDAG.

**Example:**
```python
# Source: agent/orchestrator/dag.py line 94-115
# LLM produces task list and edge list; we feed directly to from_definition()
from agent.orchestrator.dag import TaskDAG

dag = TaskDAG.from_definition(
    dag_id=f"plan-{project_id}",
    tasks=[t.model_dump() for t in task_dag_output.tasks],
    edges=[e.model_dump() for e in task_dag_output.edges],
)
assert dag.validate(), "Generated DAG has cycles"
```

**IMPORTANT:** `from_definition()` calls `t.pop("id")` -- the task dicts must have `"id"` as a key that gets consumed. Task dicts map to `add_task()` kwargs: `label`, `description`, `task_type`, `contract_inputs`, `contract_outputs`, `metadata`.

### Anti-Patterns to Avoid
- **Raw JSON parsing with string manipulation:** Use `call_llm_structured()` with Pydantic models instead. The existing `parse_plan_steps()` pattern with JSON fallback is fragile -- structured outputs are more reliable.
- **LLM-inferred dependency edges:** Decision D-03 locks this to static import analysis only. Do not use LLM to guess dependencies.
- **Modifying existing `planner_node`:** The Planner v2 is a NEW module (`agent/planner_v2/`). The existing `agent/nodes/planner.py` handles single-instruction decomposition and must not be changed.
- **Complex module detection in Analyzer:** The enrichment pass should be simple -- read files, summarize with LLM. The "complex module" second pass (D-02) should be triggered by the Planner requesting it, not pre-computed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cycle detection | Custom graph traversal | `networkx.is_directed_acyclic_graph()` | Already in TaskDAG.validate(). Edge cases (self-loops, multi-component) handled. |
| Topological ordering | BFS/DFS sort | `networkx.topological_generations()` | Already in TaskDAG.get_execution_waves(). |
| LLM output parsing | Custom JSON extraction with regex | `call_llm_structured()` + Pydantic models | OpenAI structured outputs guarantee schema compliance. |
| Token counting | Character counting | `ContextAssembler` (agent/context.py) | Already handles 4 chars/token estimation with budget management. |
| Contract file I/O | Raw file read/write | `ContractStore` (agent/orchestrator/contracts.py) | Already handles path resolution, directory creation, listing. |
| DAG construction | Custom graph building | `TaskDAG.from_definition()` | Already validates and constructs from dict lists. |

**Key insight:** Phase 12 built the orchestrator foundation specifically for Phase 13 to consume. Every DAG/contract operation should go through the Phase 12 APIs, not bypass them.

## Common Pitfalls

### Pitfall 1: Import Resolution Ambiguity
**What goes wrong:** TypeScript/JavaScript imports can omit file extensions (`.ts`, `.tsx`, `.js`), use index files (`./models` -> `./models/index.ts`), or use path aliases (`@/components`).
**Why it happens:** Node.js/TypeScript module resolution is complex with multiple fallback strategies.
**How to avoid:** For the fixture (D-11), keep imports explicit with extensions. For the Analyzer, implement a resolution order: exact match -> + `.ts` -> + `.tsx` -> + `/index.ts`. Ignore path aliases for Phase 13 (they require tsconfig parsing).
**Warning signs:** Missing edges in dependency graph for modules that clearly depend on each other.

### Pitfall 2: Module Boundary Detection
**What goes wrong:** Treating every file as a module produces a flat, useless graph. Treating only top-level directories as modules loses granularity.
**Why it happens:** "Module" is semantically ambiguous -- could be a file, directory, or logical grouping.
**How to avoid:** Define module = top-level directory under `src/` (or project root for non-src layouts). Each module contains files. Dependency edges connect modules, not individual files. For the fixture, this means ~4-5 modules (routes, models, components, types, etc.).
**Warning signs:** Module map has either 1 module (too coarse) or N modules where N = file count (too fine).

### Pitfall 3: LLM Context Window Overflow on Large Codebases
**What goes wrong:** Passing entire module contents to LLM for enrichment exceeds context window.
**Why it happens:** Some modules may have many large files.
**How to avoid:** Use `ContextAssembler` for token budget management. For enrichment, pass file names + first 50 lines of each file + export signatures, not full content. The lean map (D-02) is designed to stay small.
**Warning signs:** OpenAI API errors about context length, or truncated responses.

### Pitfall 4: TaskDAG.from_definition() Mutates Input
**What goes wrong:** `from_definition()` calls `t.pop("id")` on the task dicts, mutating the input list.
**Why it happens:** The factory method destructively removes the "id" key to pass remaining keys as kwargs.
**How to avoid:** Pass copies of the task dicts: `[{**t} for t in task_dicts]` or use `model_dump()` which creates fresh dicts each call.
**Warning signs:** KeyError on "id" when reusing task dicts after DAG construction.

### Pitfall 5: Cost Estimation Without Token Tracking
**What goes wrong:** Cost estimation (PLAN-04) reports meaningless numbers.
**Why it happens:** No clear formula for "estimated cost" of executing a Task DAG.
**How to avoid:** Use a simple formula: `estimated_cost = sum(task.estimated_loc * COST_PER_LOC)` where COST_PER_LOC accounts for typical LLM token usage per LOC of generated code. Report as estimated tokens, not dollars (project has unlimited budget).
**Warning signs:** Cost estimate is always 0 or always the same number regardless of DAG size.

### Pitfall 6: PRD/Tech Spec Markdown Not Machine-Parseable
**What goes wrong:** PRDs and Tech Specs stored as free-form markdown that the next pipeline layer can't reliably extract structured data from.
**Why it happens:** Markdown is human-readable but not structured.
**How to avoid:** Use `call_llm_structured()` to generate the structured Pydantic model first, then render to markdown for storage. The structured model feeds forward in the pipeline; the markdown is for human consumption and git history.
**Warning signs:** Planner Layer 2 fails to parse Layer 1's markdown output.

## Code Examples

### Module Map Pydantic Models (Recommended Schema)
```python
# agent/analyzer/models.py
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
    summary: str = ""  # 1-sentence LLM-generated summary
    dependencies: list[str] = Field(default_factory=list)  # module names this imports from


class DependencyEdge(BaseModel):
    """Directed edge: source module imports from target module."""
    source: str  # module name
    target: str  # module name
    import_count: int = 1  # number of import statements


class ModuleMap(BaseModel):
    """Complete module map output -- single JSON file (D-04)."""
    project_path: str
    modules: list[ModuleInfo] = Field(default_factory=list)
    edges: list[DependencyEdge] = Field(default_factory=list)
    total_files: int = 0
    total_loc: int = 0
```

### Routing Policy Additions
```python
# New entries for agent/router.py ROUTING_POLICY
"analyze_enrich":  {"tier": "general"},       # Module summarization (gpt-4o sufficient)
"plan_prd":        {"tier": "reasoning"},      # PRD generation (D-07: o3)
"plan_spec":       {"tier": "reasoning"},      # Tech Spec generation (D-07: o3)
"plan_dag":        {"tier": "reasoning"},      # Task DAG generation (D-07: o3)
"plan_validate":   {"tier": "fast"},           # Structural validation checks
```

Note: D-07 says o3 for all three planning layers. The current reasoning tier resolves to `gpt-5.4` in `MODEL_REGISTRY` (agent/models.py). This is fine -- the routing tier abstraction handles model name changes.

### Task DAG Output Model (Planner Layer 3)
```python
# agent/planner_v2/models.py
from pydantic import BaseModel, Field


class PlannedTask(BaseModel):
    """A single task in the generated DAG."""
    id: str
    label: str
    description: str
    target_files: list[str] = Field(default_factory=list, max_length=3)
    estimated_loc: int = Field(le=300)
    contract_inputs: list[str] = Field(default_factory=list)
    contract_outputs: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    indivisible: bool = False
    indivisible_justification: str | None = None


class PlannedEdge(BaseModel):
    """Dependency edge in the generated DAG."""
    from_task: str
    to_task: str


class TaskDAGOutput(BaseModel):
    """Complete Task DAG from Planner Layer 3."""
    tasks: list[PlannedTask]
    edges: list[PlannedEdge]
```

### Validation Gate Implementation
```python
# agent/planner_v2/validation.py
from agent.orchestrator.dag import TaskDAG


class ValidationError(BaseModel):
    field: str
    message: str
    severity: str = "error"  # "error" | "warning"


def validate_task_dag(output: TaskDAGOutput, spec: TechSpecOutput) -> list[ValidationError]:
    """Structural validation for Task DAG (D-06)."""
    errors: list[ValidationError] = []

    # 1. Check LOC bounds (D-09)
    for task in output.tasks:
        if task.estimated_loc > 300 and not task.indivisible:
            errors.append(ValidationError(
                field=f"tasks.{task.id}.estimated_loc",
                message=f"Task exceeds 300 LOC ({task.estimated_loc}) without indivisible flag",
            ))
        if len(task.target_files) > 3 and not task.indivisible:
            errors.append(ValidationError(
                field=f"tasks.{task.id}.target_files",
                message=f"Task touches {len(task.target_files)} files (max 3) without indivisible flag",
            ))

    # 2. Check DAG is acyclic
    dag = TaskDAG.from_definition(
        dag_id="validation",
        tasks=[{**t.model_dump()} for t in output.tasks],  # Copy to avoid pop mutation
        edges=[e.model_dump() for e in output.edges],
    )
    if not dag.validate():
        errors.append(ValidationError(
            field="edges",
            message="Task DAG contains dependency cycles",
            severity="error",
        ))

    # 3. Check contract references exist in spec
    spec_contracts = {c.name for c in spec.contracts}
    for task in output.tasks:
        for ci in task.contract_inputs:
            if ci not in spec_contracts:
                errors.append(ValidationError(
                    field=f"tasks.{task.id}.contract_inputs",
                    message=f"References unknown contract: {ci}",
                ))

    return errors
```

### Fixture Structure (D-11)
```
tests/fixtures/ship_fixture/
  package.json
  tsconfig.json
  prisma/
    schema.prisma           # Prisma schema with User, Document models
  src/
    types/
      index.ts              # Shared TypeScript interfaces
    models/
      user.ts               # User model with Prisma client usage
      document.ts           # Document model (existing)
    routes/
      health.ts             # Health check route (existing)
      users.ts              # User CRUD routes importing from models + types
    components/
      DocumentList.tsx       # React component (existing)
      UserProfile.tsx        # React component importing from types
    middleware/
      auth.ts               # Express middleware importing from models
```

This fixture gives: 5 modules (types, models, routes, components, middleware), cross-module imports (routes->models->types, components->types, middleware->models), and mimics Ship patterns per D-11.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Raw JSON LLM output + regex parsing | OpenAI Structured Outputs + Pydantic | OpenAI August 2024 | Eliminates parsing failures, guarantees schema compliance |
| Single monolithic planning prompt | Multi-layer pipeline (PRD->Spec->DAG) | Industry standard 2024+ | Better decomposition, validation gates between layers |
| LLM-inferred code dependencies | Static import analysis | Decision D-03 | Deterministic, reproducible dependency graphs |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio |
| Config file | pyproject.toml (implicit) |
| Quick run command | `python -m pytest tests/test_analyzer.py tests/test_planner_pipeline.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ANLZ-01 | Analyzer outputs module map with dependency graph from fixture | integration | `python -m pytest tests/test_analyzer.py::test_module_map_from_fixture -x` | Wave 0 |
| ANLZ-02 | Analyzer generates per-module summaries | unit | `python -m pytest tests/test_analyzer.py::test_module_enrichment -x` | Wave 0 |
| PLAN-01 | Planner generates PRD from module map | unit | `python -m pytest tests/test_planner_pipeline.py::test_prd_generation -x` | Wave 0 |
| PLAN-02 | Planner generates Tech Spec from PRD | unit | `python -m pytest tests/test_planner_pipeline.py::test_tech_spec_generation -x` | Wave 0 |
| PLAN-03 | Planner generates Task DAG with bounded tasks | unit | `python -m pytest tests/test_planner_pipeline.py::test_task_dag_bounds -x` | Wave 0 |
| PLAN-04 | Validation detects cycles, incomplete contracts, reports cost | unit | `python -m pytest tests/test_planner_validation.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_analyzer.py tests/test_planner_pipeline.py tests/test_planner_validation.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before verification

### Wave 0 Gaps
- [ ] `tests/test_analyzer.py` -- covers ANLZ-01, ANLZ-02
- [ ] `tests/test_analyzer_imports.py` -- covers import edge extraction (deterministic, no LLM)
- [ ] `tests/test_planner_pipeline.py` -- covers PLAN-01, PLAN-02, PLAN-03
- [ ] `tests/test_planner_validation.py` -- covers PLAN-04
- [ ] `tests/fixtures/ship_fixture/` -- expanded Ship-like fixture with 5-10 files

### Testing Strategy: LLM Mocking

Tests that involve LLM calls should mock `ModelRouter.call_structured()` to return pre-built Pydantic models. This makes tests deterministic and fast without requiring API keys.

```python
# Pattern for mocking structured LLM calls in tests
from unittest.mock import AsyncMock, patch

async def test_prd_generation():
    mock_router = AsyncMock()
    mock_router.call_structured.return_value = PRDOutput(
        modules=[PRDModule(name="users", description="User management", ...)],
        ...
    )
    result = await generate_prd(sample_module_map, mock_router)
    assert len(result.modules) > 0
```

## Open Questions

1. **Module granularity for non-src layouts**
   - What we know: D-11 fixture uses `src/` layout. Ship app likely uses `src/` too.
   - What's unclear: How to handle projects without a `src/` directory (multiple entry points, monorepo).
   - Recommendation: Default to top-level directories. Configurable `module_roots` parameter for edge cases. Not needed for Phase 13 (fixture only).

2. **Enrichment pass trigger mechanism**
   - What we know: D-02 says rich detail only for modules the Planner flags as complex.
   - What's unclear: When exactly does the Planner request enrichment -- before PRD generation, or between layers?
   - Recommendation: Implement enrichment as a callable function in Analyzer that Planner Layer 1 (PRD) invokes when it determines a module needs deeper understanding. Pre-compute lean summaries for all modules; rich detail on demand.

3. **Cost estimation units**
   - What we know: PLAN-04 requires cost estimation before execution.
   - What's unclear: What unit -- tokens, dollars, or abstract "complexity points"?
   - Recommendation: Report estimated total tokens (sum of estimated_loc * avg_tokens_per_loc_edit). Since budget is unlimited, this is informational only. A simple formula: `total_estimated_tokens = sum(task.estimated_loc * 50)` where 50 tokens/LOC covers reading context + generating code.

## Project Constraints (from CLAUDE.md)

- **LLM Provider:** OpenAI only (o3/gpt-4o/gpt-4o-mini). All LLM calls through `ModelRouter`.
- **Framework:** LangGraph 1.1.3. New modules are standalone async functions, not new LangGraph nodes (unless integration requires it later).
- **Naming:** snake_case.py for modules, PascalCase for classes, test_ prefix for tests.
- **Module docstrings:** Required at top of every Python module.
- **Type hints:** Full Python 3.11+ typing (str | None, list[str]).
- **LLM calls:** Always through `router.call()` or `router.call_structured()`, never direct.
- **Pydantic models:** For all data structures.
- **No new dependencies** unless absolutely required.
- **Testing:** pytest with pytest-asyncio for async tests.

## Sources

### Primary (HIGH confidence)
- `agent/orchestrator/models.py` -- TaskNode, TaskEdge, DAGRun models (read directly)
- `agent/orchestrator/dag.py` -- TaskDAG class with from_definition() factory (read directly)
- `agent/orchestrator/contracts.py` -- ContractStore API (read directly)
- `agent/router.py` -- ModelRouter with ROUTING_POLICY and call_structured() (read directly)
- `agent/llm.py` -- call_llm_structured() implementation (read directly)
- `agent/context.py` -- ContextAssembler with token budget (read directly)
- `agent/steps.py` -- PlanStep model and parse_plan_steps() pattern (read directly)
- `agent/models.py` -- MODEL_REGISTRY with tier definitions (read directly)
- `tests/test_dag.py` -- Test patterns for DAG operations (read directly)
- `tests/conftest.py` -- Fixture patterns (read directly)

### Secondary (MEDIUM confidence)
- Phase 12 CONTEXT.md decisions -- DAG design rationale
- Existing `tests/fixtures/ship_sample_project/` -- baseline fixture structure

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all existing libraries verified in codebase
- Architecture: HIGH -- builds directly on Phase 12 APIs, patterns established
- Pitfalls: HIGH -- identified from direct code reading (from_definition mutation, import resolution)
- Validation: HIGH -- test infrastructure exists, patterns established

**Research date:** 2026-03-29
**Valid until:** 2026-04-28 (stable -- internal codebase, no external API changes expected)
