# ast-grep Phase 2: Refactor Node — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add codebase-wide structural refactoring via ast-grep YAML rules, with a new `refactor_node`, batch approval on `ApprovalManager`, and graph routing.

**Architecture:** The planner emits `kind: "refactor"` steps with pattern/replacement/language/scope. The coordinator routes these to `sequential_first` (never parallel). A new `refactor_node` executes ast-grep rules via `apply_rule()`, stores full-file snapshots for best-effort batch rollback, and integrates with the existing approval flow for supervised mode. A new `PATCH /runs/{run_id}/batches/{batch_id}` endpoint handles batch approval.

**Tech Stack:** Python 3.11+, ast-grep-py, pydantic, pytest, pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-25-ast-grep-lsp-integration-design.md` (Sections 1c, 4, 5)

**Prerequisite:** Phase 1 complete (ast_ops.py with validate_anchor, structural_replace, detect_languages).

**Commit rule:** Never include `Co-Authored-By` lines in commit messages.

---

## File Structure

### New Files
- `agent/nodes/refactor.py` — refactor_node: dry-run, apply, batch rollback, approval integration
- `tests/test_refactor_node.py` — unit and integration tests for refactor_node

### Modified Files
- `agent/tools/ast_ops.py` — add `apply_rule()` and `RefactorResult` dataclass
- `agent/steps.py` — add `"refactor"` to PlanStep.kind, add optional refactor fields
- `agent/prompts/planner.py` — add refactor step documentation to planner prompt
- `agent/nodes/coordinator.py` — handle typed dict steps, route refactors to sequential_first
- `agent/graph.py` — add refactor_node, add `"refactor"` to classify_step routing
- `agent/approval.py` — add `propose_batch()`, `approve_batch()`, `reject_batch()` methods
- `store/models.py` — add `batch_id` field to EditRecord
- `server/main.py` — add `PATCH /runs/{run_id}/batches/{batch_id}` endpoint
- `tests/test_steps.py` — add tests for refactor kind
- `tests/test_ast_ops.py` — add tests for apply_rule
- `tests/test_approval.py` — add tests for batch methods
- `tests/test_graph.py` — add test for refactor routing

---

## Task 1: Add apply_rule to ast_ops.py

**Files:**
- Modify: `agent/tools/ast_ops.py`
- Modify: `tests/test_ast_ops.py`

- [ ] **Step 1: Write failing tests for apply_rule**

Add to `tests/test_ast_ops.py`:

```python
class TestApplyRule:
    """Test codebase-wide structural refactoring via ast-grep rules."""

    def test_dry_run_finds_matches(self, tmp_path):
        from agent.tools.ast_ops import apply_rule
        (tmp_path / "a.ts").write_text("const x = oldFunc(1);\n")
        (tmp_path / "b.ts").write_text("const y = oldFunc(2);\nconst z = oldFunc(3);\n")
        rule = {"pattern": "oldFunc($ARG)", "fix": "newFunc($ARG)", "language": "typescript"}
        results = apply_rule(rule, str(tmp_path), dry_run=True)
        assert len(results) == 2  # two files matched
        total_matches = sum(r.match_count for r in results)
        assert total_matches == 3  # three occurrences total
        # Dry run: files should NOT be modified
        assert (tmp_path / "a.ts").read_text() == "const x = oldFunc(1);\n"

    def test_apply_modifies_files(self, tmp_path):
        from agent.tools.ast_ops import apply_rule
        (tmp_path / "a.ts").write_text("const x = oldFunc(1);\n")
        rule = {"pattern": "oldFunc($ARG)", "fix": "newFunc($ARG)", "language": "typescript"}
        results = apply_rule(rule, str(tmp_path), dry_run=False)
        assert len(results) == 1
        assert results[0].match_count == 1
        assert "newFunc(1)" in (tmp_path / "a.ts").read_text()

    def test_apply_returns_old_and_new_content(self, tmp_path):
        from agent.tools.ast_ops import apply_rule
        original = "const x = oldFunc(1);\n"
        (tmp_path / "a.ts").write_text(original)
        rule = {"pattern": "oldFunc($ARG)", "fix": "newFunc($ARG)", "language": "typescript"}
        results = apply_rule(rule, str(tmp_path), dry_run=False)
        assert results[0].old_content == original
        assert "newFunc(1)" in results[0].new_content

    def test_no_matches_returns_empty(self, tmp_path):
        from agent.tools.ast_ops import apply_rule
        (tmp_path / "a.ts").write_text("const x = 1;\n")
        rule = {"pattern": "nonExistent($ARG)", "fix": "replacement($ARG)", "language": "typescript"}
        results = apply_rule(rule, str(tmp_path), dry_run=True)
        assert len(results) == 0

    def test_respects_scope_exclusions(self, tmp_path):
        from agent.tools.ast_ops import apply_rule
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.ts").write_text("const x = oldFunc(1);\n")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "b.ts").write_text("const y = oldFunc(2);\n")
        rule = {"pattern": "oldFunc($ARG)", "fix": "newFunc($ARG)", "language": "typescript"}
        results = apply_rule(rule, str(tmp_path), dry_run=True)
        # Should only find src/a.ts, not node_modules/b.ts
        assert len(results) == 1
        assert "src" in results[0].file_path

    def test_unsupported_language_returns_empty(self, tmp_path):
        from agent.tools.ast_ops import apply_rule
        (tmp_path / "a.xyz").write_text("content")
        rule = {"pattern": "x", "fix": "y", "language": "nonexistent_xyz"}
        results = apply_rule(rule, str(tmp_path), dry_run=True)
        assert len(results) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_ast_ops.py::TestApplyRule -v`
Expected: FAIL — `apply_rule` not defined.

- [ ] **Step 3: Implement apply_rule**

Add `RefactorResult` dataclass and `apply_rule` function to `agent/tools/ast_ops.py`:

```python
@dataclass
class RefactorResult:
    """Result of applying a refactor rule to a single file."""
    file_path: str
    old_content: str
    new_content: str
    match_count: int


# Default directories to exclude from refactoring scope
_SCOPE_EXCLUSIONS = {"node_modules", ".git", "__pycache__", "dist", "build", ".venv", "target"}


def apply_rule(rule: dict, scope: str, dry_run: bool = True) -> list[RefactorResult]:
    """Apply an ast-grep structural rule across files in a directory scope.

    Args:
        rule: dict with 'pattern', 'fix', and 'language' keys.
        scope: directory path to search within.
        dry_run: if True, collect matches without modifying files.

    Returns:
        List of RefactorResult for each file with matches.
    """
    if not AST_GREP_AVAILABLE:
        return []

    pattern = rule.get("pattern", "")
    fix = rule.get("fix", "")
    language = rule.get("language", "")

    if not pattern or not language:
        return []

    # Verify language is supported
    if not _probe_grammar(language):
        return []

    # Get language file extensions
    lang_exts = {ext for ext, lang in _EXT_TO_LANGUAGE.items() if lang == language}
    if not lang_exts:
        return []

    # Collect matching files
    results: list[RefactorResult] = []
    for dirpath, dirnames, filenames in os.walk(scope):
        dirnames[:] = [d for d in dirnames if d not in _SCOPE_EXCLUSIONS]
        for filename in filenames:
            _, ext = os.path.splitext(filename)
            if ext.lower() not in lang_exts:
                continue

            file_path = os.path.join(dirpath, filename)
            try:
                with open(file_path, "r") as f:
                    content = f.read()
            except (OSError, UnicodeDecodeError):
                continue

            # Parse and find matches
            try:
                root = SgRoot(content, language)
            except BaseException:
                continue

            tree_root = root.root()
            matches = tree_root.find_all(pattern)
            match_list = list(matches)

            if not match_list:
                continue

            # Compute replacement content
            new_content = content
            if fix:
                # Apply replacements in reverse order to preserve positions
                edits = []
                for match in match_list:
                    replaced = match.replace(fix)
                    start = match.range().start.index
                    end = match.range().end.index
                    edits.append((start, end, replaced))

                # Sort by start position descending
                edits.sort(key=lambda e: e[0], reverse=True)
                for start, end, replaced in edits:
                    new_content = new_content[:start] + replaced + new_content[end:]

            results.append(RefactorResult(
                file_path=file_path,
                old_content=content,
                new_content=new_content,
                match_count=len(match_list),
            ))

            # Apply if not dry run
            if not dry_run and new_content != content:
                with open(file_path, "w") as f:
                    f.write(new_content)

    return results
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_ast_ops.py::TestApplyRule -v`
Expected: All PASS.

- [ ] **Step 5: Run all ast_ops tests for regressions**

Run: `.venv/bin/pytest tests/test_ast_ops.py -v`
Expected: All pass (29 existing + 6 new = 35).

- [ ] **Step 6: Commit**

```bash
git add agent/tools/ast_ops.py tests/test_ast_ops.py
git commit -m "feat: add apply_rule for codebase-wide structural refactoring"
```

---

## Task 2: Extend PlanStep with Refactor Kind

**Files:**
- Modify: `agent/steps.py`
- Modify: `tests/test_steps.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_steps.py`:

```python
def test_plan_step_accepts_refactor_kind():
    from agent.steps import PlanStep
    step = PlanStep(
        id="refactor-1",
        kind="refactor",
        complexity="complex",
        pattern="oldFunc($ARG)",
        refactor_replacement="newFunc($ARG)",
        language="typescript",
        scope="web/src/",
    )
    assert step.kind == "refactor"
    assert step.pattern == "oldFunc($ARG)"
    assert step.refactor_replacement == "newFunc($ARG)"
    assert step.language == "typescript"
    assert step.scope == "web/src/"


def test_parse_plan_steps_with_refactor():
    from agent.steps import parse_plan_steps
    import json
    raw = json.dumps([{
        "id": "refactor-1",
        "kind": "refactor",
        "complexity": "complex",
        "pattern": "oldFunc($ARG)",
        "refactor_replacement": "newFunc($ARG)",
        "language": "typescript",
        "scope": "web/src/",
    }])
    steps = parse_plan_steps(raw)
    assert len(steps) == 1
    assert steps[0].kind == "refactor"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_steps.py -v -k "refactor"`
Expected: FAIL — "refactor" not in allowed kinds.

- [ ] **Step 3: Update PlanStep**

Modify `agent/steps.py`:

```python
"""Typed plan step schema and parsing utilities."""
import json
from pydantic import BaseModel, field_validator
from typing import Literal


class PlanStep(BaseModel):
    id: str
    kind: Literal["read", "edit", "exec", "test", "git", "refactor"]
    target_files: list[str] = []
    command: str | None = None
    acceptance_criteria: list[str] = []
    complexity: Literal["simple", "complex"]
    depends_on: list[str] = []
    # Refactor-specific fields
    pattern: str | None = None
    refactor_replacement: str | None = None
    language: str | None = None
    scope: str | None = None

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        allowed = {"read", "edit", "exec", "test", "git", "refactor"}
        if v not in allowed:
            raise ValueError(f"kind must be one of {allowed}, got '{v}'")
        return v

    @field_validator("complexity")
    @classmethod
    def validate_complexity(cls, v: str) -> str:
        allowed = {"simple", "complex"}
        if v not in allowed:
            raise ValueError(f"complexity must be one of {allowed}, got '{v}'")
        return v


def parse_plan_steps(raw: str) -> list[PlanStep]:
    """Parse LLM output into typed PlanStep objects. Fallback on parse failure."""
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [PlanStep(**item) for item in data]
        if isinstance(data, dict) and "steps" in data:
            return [PlanStep(**item) for item in data["steps"]]
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    return [PlanStep(
        id="fallback-1",
        kind="exec",
        command=raw.strip(),
        complexity="complex",
    )]
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_steps.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/steps.py tests/test_steps.py
git commit -m "feat: add refactor kind to PlanStep with pattern/replacement fields"
```

---

## Task 3: Update Planner Prompt

**Files:**
- Modify: `agent/prompts/planner.py`

- [ ] **Step 1: Update the planner system prompt**

Add `"refactor"` to the kind list and add documentation. Update `agent/prompts/planner.py`:

```python
PLANNER_SYSTEM = """You are a coding task planner. Break the user's instruction into concrete, ordered steps.

Output a JSON array of step objects. Each step MUST have:
- "id": unique string identifier (e.g., "step-1", "step-2")
- "kind": one of "read", "edit", "exec", "test", "git", "refactor"
- "target_files": array of file paths this step touches (empty for exec/test)
- "complexity": "simple" (single file, localized change) or "complex" (multi-file, architecture changes)
- "depends_on": array of step IDs that must complete before this step (empty if none)
- "command": shell command string (only for exec/test steps, null otherwise)
- "acceptance_criteria": array of strings describing how to verify success

For "refactor" steps, also include:
- "pattern": ast-grep pattern to match (e.g., "oldFunc($ARG)")
- "refactor_replacement": replacement template (e.g., "newFunc($ARG)")
- "language": programming language (e.g., "typescript", "python")
- "scope": directory scope to search within (e.g., "web/src/")

When to emit "refactor" vs "edit":
- "edit": change specific code in 1-3 known files
- "refactor": apply a structural pattern across many files (rename symbol, migrate API, update import paths)
Heuristic: if the instruction mentions "all files", "everywhere", "across the codebase", or names a pattern rather than a specific file location, emit a "refactor" step.

Classification rules for complexity:
- "simple": single file, change within one function or code block
- "complex": multiple files, changes to type signatures used across files, touching >3 functions

Output ONLY the JSON array, no other text."""

PLANNER_USER = """Working directory: {working_directory}

Instruction: {instruction}

{context_section}

{file_listing}

Output the step array as JSON:"""
```

- [ ] **Step 2: Commit**

```bash
git add agent/prompts/planner.py
git commit -m "feat: add refactor step documentation to planner prompt"
```

---

## Task 4: Update Coordinator for Typed Steps and Sequential Refactors

**Files:**
- Modify: `agent/nodes/coordinator.py`
- Modify: `tests/test_ast_ops.py` (add coordinator tests)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_ast_ops.py`:

```python
class TestCoordinatorRefactorRouting:
    """Test that coordinator routes refactor steps to sequential_first."""

    def test_refactor_steps_go_to_sequential(self):
        from agent.nodes.coordinator import coordinator_node
        state = {
            "plan": [
                {"id": "step-1", "kind": "edit", "target_files": ["web/a.ts"], "complexity": "simple"},
                {"id": "step-2", "kind": "refactor", "pattern": "old($A)", "refactor_replacement": "new($A)", "language": "typescript", "scope": "web/", "complexity": "complex"},
                {"id": "step-3", "kind": "edit", "target_files": ["api/b.py"], "complexity": "simple"},
            ],
        }
        result = coordinator_node(state)
        # Refactor step (index 1) must be in sequential_first
        assert 1 in result["sequential_first"]
        # Refactor step must NOT be in any parallel batch
        for batch in result.get("parallel_batches", []):
            assert 1 not in batch

    def test_dict_steps_handled(self):
        from agent.nodes.coordinator import coordinator_node
        state = {
            "plan": [
                {"id": "step-1", "kind": "edit", "target_files": ["web/a.ts"], "complexity": "simple"},
                {"id": "step-2", "kind": "edit", "target_files": ["api/b.py"], "complexity": "simple"},
            ],
        }
        result = coordinator_node(state)
        # Should not crash on dict steps
        assert "is_parallel" in result

    def test_legacy_string_steps_still_work(self):
        from agent.nodes.coordinator import coordinator_node
        state = {
            "plan": ["Edit web/a.ts", "Edit api/b.py"],
        }
        result = coordinator_node(state)
        assert "is_parallel" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_ast_ops.py::TestCoordinatorRefactorRouting -v`
Expected: FAIL — coordinator crashes on dict steps.

- [ ] **Step 3: Update coordinator_node**

Modify `agent/nodes/coordinator.py`:

```python
from agent.tracing import TraceLogger

tracer = TraceLogger()


def _step_to_text(step) -> str:
    """Extract text representation from a step (dict or string)."""
    if isinstance(step, dict):
        # Use target_files for directory grouping
        files = step.get("target_files", [])
        if files:
            return files[0].lower()
        return step.get("id", "").lower()
    return str(step).lower()


def coordinator_node(state: dict) -> dict:
    """Decide whether to fan out to parallel subgraphs or run sequentially.
    Refactor steps are always placed in sequential_first (never parallelized)."""
    plan = state.get("plan", [])

    if len(plan) < 2:
        return {"is_parallel": False, "parallel_batches": [], "sequential_first": []}

    # Separate refactor steps (always sequential) from others
    refactor_indices: list[int] = []
    other_indices: list[int] = []
    for i, step in enumerate(plan):
        if isinstance(step, dict) and step.get("kind") == "refactor":
            refactor_indices.append(i)
        else:
            other_indices.append(i)

    # Group non-refactor steps by directory for potential parallelism
    dir_groups: dict[str, list[int]] = {}
    for i in other_indices:
        step_text = _step_to_text(plan[i])
        if "api/" in step_text:
            dir_groups.setdefault("api", []).append(i)
        elif "web/" in step_text:
            dir_groups.setdefault("web", []).append(i)
        elif "shared/" in step_text:
            dir_groups.setdefault("shared", []).append(i)
        else:
            dir_groups.setdefault("other", []).append(i)

    sequential = dir_groups.pop("shared", [])
    other = dir_groups.pop("other", [])
    parallel_batch = []
    for group_steps in dir_groups.values():
        if group_steps:
            parallel_batch.append(group_steps)

    # Refactor steps always sequential
    sequential_first = refactor_indices + sequential + other
    is_parallel = len(parallel_batch) > 1

    tracer.log("coordinator", {
        "is_parallel": is_parallel,
        "sequential": sequential_first,
        "parallel_batch": parallel_batch,
        "refactor_steps": refactor_indices,
    })

    return {
        "is_parallel": is_parallel,
        "parallel_batches": parallel_batch,
        "sequential_first": sequential_first,
    }
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_ast_ops.py::TestCoordinatorRefactorRouting -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/nodes/coordinator.py tests/test_ast_ops.py
git commit -m "feat: coordinator handles typed steps, routes refactors to sequential"
```

---

## Task 5: Add batch_id to EditRecord

**Files:**
- Modify: `store/models.py`

- [ ] **Step 1: Add batch_id field**

Add `batch_id: str | None = None` to `EditRecord` in `store/models.py`:

```python
class EditRecord(BaseModel):
    id: str = Field(default_factory=_new_id)
    run_id: str
    file_path: str
    step: int = 0
    anchor: str | None = None
    old_content: str | None = None
    new_content: str | None = None
    status: EDIT_STATUSES = "proposed"
    approved_at: datetime | None = None
    last_op_id: str | None = None
    batch_id: str | None = None  # Groups refactor edits for batch approval/rollback
```

- [ ] **Step 2: Run existing model tests for regressions**

Run: `.venv/bin/pytest tests/ -v -k "model" --timeout=30`
Expected: All PASS — `batch_id` has a default of `None` so existing code is unaffected.

- [ ] **Step 3: Commit**

```bash
git add store/models.py
git commit -m "feat: add batch_id to EditRecord for refactor batch grouping"
```

---

## Task 6: Batch Approval Methods on ApprovalManager

**Files:**
- Modify: `agent/approval.py`
- Modify: `tests/test_approval.py`

- [ ] **Step 1: Write failing tests for batch methods**

Add to `tests/test_approval.py`:

```python
class TestBatchApproval:
    """Test batch propose/approve/reject for refactor operations.

    Uses the existing fixtures from test_approval.py: `manager` (ApprovalManager),
    `project_and_run` (creates Project + Run in store for valid run_id lookup).
    """

    @pytest.mark.asyncio
    async def test_propose_batch(self, manager, project_and_run):
        _, run = project_and_run
        records = [
            EditRecord(run_id=run.id, file_path="/tmp/a.ts", old_content="old1", new_content="new1"),
            EditRecord(run_id=run.id, file_path="/tmp/b.ts", old_content="old2", new_content="new2"),
        ]
        result = await manager.propose_batch(run.id, records, "batch-1")
        assert len(result) == 2
        assert all(r.status == "proposed" for r in result)
        assert all(r.batch_id == "batch-1" for r in result)

    @pytest.mark.asyncio
    async def test_approve_batch(self, manager, project_and_run):
        _, run = project_and_run
        records = [
            EditRecord(run_id=run.id, file_path="/tmp/a.ts", old_content="old1", new_content="new1"),
            EditRecord(run_id=run.id, file_path="/tmp/b.ts", old_content="old2", new_content="new2"),
        ]
        await manager.propose_batch(run.id, records, "batch-2")
        approved = await manager.approve_batch("batch-2", "op-approve-1")
        assert len(approved) == 2
        assert all(r.status == "approved" for r in approved)

    @pytest.mark.asyncio
    async def test_reject_batch(self, manager, project_and_run):
        _, run = project_and_run
        records = [
            EditRecord(run_id=run.id, file_path="/tmp/a.ts", old_content="old1", new_content="new1"),
        ]
        await manager.propose_batch(run.id, records, "batch-3")
        rejected = await manager.reject_batch("batch-3", "op-reject-1")
        assert len(rejected) == 1
        assert rejected[0].status == "rejected"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_approval.py::TestBatchApproval -v`
Expected: FAIL — `propose_batch` not defined.

- [ ] **Step 3: Implement batch methods**

Modify `agent/approval.py`. First, update `__init__` to add the batch registry:

```python
    def __init__(self, store: SessionStore, event_bus: EventBus):
        self.store = store
        self.event_bus = event_bus
        self._batch_registry: dict[str, str] = {}  # batch_id → run_id
```

Then add these methods at the end of the class:

```python
    async def propose_batch(self, run_id: str, records: list[EditRecord], batch_id: str) -> list[EditRecord]:
        """Propose a batch of edits for approval. All share the same batch_id."""
        self._batch_registry[batch_id] = run_id
        created = []
        for record in records:
            record.status = "proposed"
            record.run_id = run_id
            record.batch_id = batch_id
            result = await self.store.create_edit(record)
            created.append(result)
        if created:
            project_id = await self._resolve_project_id(run_id)
            await self.event_bus.emit(Event(
                project_id=project_id,
                run_id=run_id,
                type="approval",
                data={
                    "event": "batch.proposed",
                    "batch_id": batch_id,
                    "edit_ids": [r.id for r in created],
                    "file_count": len(created),
                },
            ))
        return created

    async def approve_batch(self, batch_id: str, op_id: str) -> list[EditRecord]:
        """Approve all proposed edits in a batch."""
        approved = []
        all_edits = await self._get_batch_edits(batch_id)
        for edit in all_edits:
            if edit.status == "proposed":
                result = await self.approve(edit.id, f"{op_id}_{edit.id}")
                approved.append(result)
        return approved

    async def reject_batch(self, batch_id: str, op_id: str) -> list[EditRecord]:
        """Reject all proposed edits in a batch."""
        rejected = []
        all_edits = await self._get_batch_edits(batch_id)
        for edit in all_edits:
            if edit.status == "proposed":
                result = await self.reject(edit.id, f"{op_id}_{edit.id}")
                rejected.append(result)
        return rejected

    async def _get_batch_edits(self, batch_id: str) -> list[EditRecord]:
        """Get all edits in a batch. Uses in-memory registry to find the run_id."""
        run_id = self._batch_registry.get(batch_id)
        if not run_id:
            return []
        all_edits = await self.store.get_edits(run_id)
        return [e for e in all_edits if e.batch_id == batch_id]
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest tests/test_approval.py -v`
Expected: All PASS (existing + new batch tests).

- [ ] **Step 5: Commit**

```bash
git add agent/approval.py tests/test_approval.py
git commit -m "feat: add batch propose/approve/reject to ApprovalManager"
```

---

## Task 7: Add classify_step Routing for Refactor

**Files:**
- Modify: `agent/graph.py`
- Modify: `tests/test_graph.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_graph.py`:

```python
def test_classify_step_routes_refactor():
    from agent.graph import classify_step
    state = {
        "plan": [{"kind": "refactor", "pattern": "old($A)", "refactor_replacement": "new($A)", "language": "typescript"}],
        "current_step": 0,
    }
    result = classify_step(state)
    assert result == "refactor"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_graph.py -v -k "refactor"`
Expected: FAIL — classify_step returns `"reader_then_edit"` for unknown kinds.

- [ ] **Step 3: Update classify_step and graph construction**

In `agent/graph.py`:

1. Add the refactor import and routing:

```python
from agent.nodes.refactor import refactor_node
```

2. In `classify_step`, add before the `return "reader_then_edit"` fallback:
```python
        if kind == "refactor":
            return "refactor"
```

3. In `_build_graph_nodes`, add:
```python
    graph.add_node("refactor", refactor_node)
```

4. In the conditional edges map for classify, add:
```python
        "refactor": "refactor",
```

5. Add edge from refactor to validator (syntax-level validation via existing validator; LSP semantic validation is deferred to Phase 3):
```python
    graph.add_edge("refactor", "validator")
```

6. Also fix `after_reader` to handle dict steps (currently calls `.lower()` on plan[step] which crashes on dicts):
```python
def after_reader(state: dict) -> str:
    plan = state.get("plan", [])
    step = state.get("current_step", 0)
    if step >= len(plan):
        return "advance"
    step_entry = plan[step]
    if isinstance(step_entry, dict):
        kind = step_entry.get("kind", "edit")
        if kind == "read":
            return "advance"
        return "editor"
    step_text = step_entry.lower()
    if any(kw in step_text for kw in ["read ", "understand", "examine", "check "]):
        return "advance"
    return "editor"
```

- [ ] **Step 4: Create stub refactor_node**

Create `agent/nodes/refactor.py` with a minimal stub so the graph compiles:

```python
"""Refactor node — codebase-wide structural transformations via ast-grep.

Full implementation in Task 8. This stub allows the graph to compile.
"""
from agent.tracing import TraceLogger

tracer = TraceLogger()


async def refactor_node(state: dict, config: dict) -> dict:
    """Placeholder — will be implemented in Task 8."""
    return {"error_state": "Refactor node not yet implemented"}
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests/test_graph.py -v`
Expected: All PASS (existing + new refactor routing test).

- [ ] **Step 6: Commit**

```bash
git add agent/graph.py agent/nodes/refactor.py tests/test_graph.py
git commit -m "feat: add refactor routing to graph classify_step"
```

---

## Task 8: Implement refactor_node

**Files:**
- Modify: `agent/nodes/refactor.py`
- Create: `tests/test_refactor_node.py`

This is the core task — the full refactor node with dry-run, apply, snapshot, rollback, and approval integration.

- [ ] **Step 1: Write tests**

Create `tests/test_refactor_node.py`:

```python
"""Tests for agent/nodes/refactor.py — codebase-wide refactoring."""
import json
import os
import pytest
import subprocess
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def refactor_state(tmp_path):
    """Create a temp project with files to refactor."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.ts").write_text("const x = oldFunc(1);\nexport default x;\n")
    (tmp_path / "src" / "b.ts").write_text("const y = oldFunc(2);\nconst z = oldFunc(3);\n")
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)

    return {
        "plan": [{
            "id": "refactor-1",
            "kind": "refactor",
            "pattern": "oldFunc($ARG)",
            "refactor_replacement": "newFunc($ARG)",
            "language": "typescript",
            "scope": str(tmp_path / "src"),
            "complexity": "complex",
        }],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
        "working_directory": str(tmp_path),
        "ast_available": {"typescript": True},
    }


@pytest.mark.asyncio
async def test_refactor_node_autonomous_applies(refactor_state, tmp_path):
    """Refactor without approval_manager applies immediately."""
    from agent.nodes.refactor import refactor_node
    config = {"configurable": {}}
    result = await refactor_node(refactor_state, config)

    assert result["error_state"] is None
    # Files should be modified
    assert "newFunc(1)" in (tmp_path / "src" / "a.ts").read_text()
    assert "newFunc(2)" in (tmp_path / "src" / "b.ts").read_text()
    # Edit history should have entries with batch_id
    assert len(result["edit_history"]) >= 2
    batch_ids = {e.get("batch_id") for e in result["edit_history"]}
    assert len(batch_ids) == 1  # all same batch_id
    assert None not in batch_ids


@pytest.mark.asyncio
async def test_refactor_node_no_matches(tmp_path):
    """Refactor with no matches returns informational message."""
    from agent.nodes.refactor import refactor_node
    (tmp_path / "a.ts").write_text("const x = 1;\n")
    state = {
        "plan": [{
            "id": "refactor-1",
            "kind": "refactor",
            "pattern": "nonExistent($ARG)",
            "refactor_replacement": "replacement($ARG)",
            "language": "typescript",
            "scope": str(tmp_path),
            "complexity": "complex",
        }],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
        "working_directory": str(tmp_path),
        "ast_available": {"typescript": True},
    }
    config = {"configurable": {}}
    result = await refactor_node(state, config)
    assert result["error_state"] is None  # informational, not an error


@pytest.mark.asyncio
async def test_refactor_node_updates_file_buffer(refactor_state, tmp_path):
    """Refactor should update file_buffer with post-refactor content."""
    from agent.nodes.refactor import refactor_node
    config = {"configurable": {}}
    result = await refactor_node(refactor_state, config)
    # file_buffer should contain the modified files
    file_buffer = result.get("file_buffer", {})
    assert len(file_buffer) >= 2
    for path, content in file_buffer.items():
        assert "newFunc" in content


@pytest.mark.asyncio
async def test_refactor_rollback_on_apply_failure(tmp_path):
    """If apply fails partway, already-written files should be rolled back."""
    from agent.nodes.refactor import refactor_node
    (tmp_path / "a.ts").write_text("const x = oldFunc(1);\n")
    # Create a read-only file that will fail to write
    (tmp_path / "b.ts").write_text("const y = oldFunc(2);\n")
    os.chmod(str(tmp_path / "b.ts"), 0o444)

    state = {
        "plan": [{
            "id": "refactor-1",
            "kind": "refactor",
            "pattern": "oldFunc($ARG)",
            "refactor_replacement": "newFunc($ARG)",
            "language": "typescript",
            "scope": str(tmp_path),
            "complexity": "complex",
        }],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
        "working_directory": str(tmp_path),
        "ast_available": {"typescript": True},
    }
    config = {"configurable": {}}
    result = await refactor_node(state, config)

    # Should report an error
    assert result["error_state"] is not None
    # a.ts should be rolled back to original
    assert "oldFunc(1)" in (tmp_path / "a.ts").read_text()

    # Clean up permissions
    os.chmod(str(tmp_path / "b.ts"), 0o644)
```

- [ ] **Step 2: Implement refactor_node**

Replace the stub in `agent/nodes/refactor.py`:

```python
"""Refactor node — codebase-wide structural transformations via ast-grep.

Handles dry-run, apply, snapshot-based rollback, and approval integration.
Refactor steps are always sequential (never parallelized by the coordinator).
"""
from __future__ import annotations

import uuid
from agent.tracing import TraceLogger
from agent.tools.ast_ops import apply_rule

tracer = TraceLogger()


async def refactor_node(state: dict, config: dict) -> dict:
    """Execute a codebase-wide refactoring step.

    Flow:
    1. Extract refactor params from current plan step
    2. Dry-run to collect matches
    3. If supervised + approval_manager: propose batch and wait
    4. Apply changes, store snapshots
    5. Update file_buffer
    6. Record in edit_history with batch_id
    """
    approval_manager = config["configurable"].get("approval_manager")
    supervised = config["configurable"].get("supervised", False)
    run_id = config["configurable"].get("run_id", "")

    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    file_buffer = state.get("file_buffer", {})
    edit_history = state.get("edit_history", [])

    if current_step >= len(plan):
        return {"error_state": None}

    step = plan[current_step]
    if not isinstance(step, dict) or step.get("kind") != "refactor":
        return {"error_state": "Expected refactor step"}

    pattern = step.get("pattern", "")
    replacement = step.get("refactor_replacement", "")
    language = step.get("language", "")
    scope = step.get("scope", state.get("working_directory", ""))

    if not pattern or not language:
        return {"error_state": "Refactor step missing pattern or language"}

    batch_id = uuid.uuid4().hex[:12]
    rule = {"pattern": pattern, "fix": replacement, "language": language}

    # Check if we're resuming after approval (graph was paused for human)
    # Look for a pending batch in edit_history
    existing_batch_id = _find_pending_batch(edit_history)
    if existing_batch_id:
        # Resuming after approval — use the existing batch_id and skip to apply
        batch_id = existing_batch_id
        tracer.log("refactor", {"batch_id": batch_id, "status": "resuming_after_approval"})
        # Fall through to the apply step below (approval_manager check will be skipped
        # because supervised=False on resume, or approval already happened)

    # Step 1: Dry-run to see what would change
    dry_results = apply_rule(rule, scope, dry_run=True)

    if not dry_results:
        tracer.log("refactor", {"batch_id": batch_id, "matches": 0, "status": "no_matches"})
        return {"error_state": None}  # informational, not an error

    total_matches = sum(r.match_count for r in dry_results)
    tracer.log("refactor", {
        "batch_id": batch_id,
        "files_matched": len(dry_results),
        "total_matches": total_matches,
        "scope": scope,
    })

    # Step 2: If supervised with approval_manager, propose batch and wait
    if approval_manager is not None and supervised:
        from store.models import EditRecord
        records = []
        for dr in dry_results:
            records.append(EditRecord(
                run_id=run_id,
                file_path=dr.file_path,
                old_content=dr.old_content,
                new_content=dr.new_content,
                batch_id=batch_id,
            ))
        await approval_manager.propose_batch(run_id, records, batch_id)
        return {
            "waiting_for_human": True,
            "batch_id": batch_id,
            "edit_history": edit_history + [
                {"file": dr.file_path, "batch_id": batch_id, "status": "proposed"}
                for dr in dry_results
            ],
            "error_state": None,
        }

    # Step 3: Capture snapshots from dry-run BEFORE applying (for reliable rollback)
    snapshots: dict[str, str] = {r.file_path: r.old_content for r in dry_results}
    new_edit_history = list(edit_history)
    new_file_buffer = dict(file_buffer)

    try:
        results = apply_rule(rule, scope, dry_run=False)
        for r in results:
            new_file_buffer[r.file_path] = r.new_content
            new_edit_history.append({
                "file": r.file_path,
                "old": pattern,
                "new": replacement,
                "snapshot": snapshots.get(r.file_path, r.old_content),
                "batch_id": batch_id,
            })
    except Exception as e:
        # Partial failure — rollback ALL files using dry-run snapshots
        _rollback_snapshots(snapshots)
        tracer.log("refactor", {"batch_id": batch_id, "error": str(e), "rolled_back": list(snapshots.keys())})
        return {"error_state": f"Refactor failed: {e}. Rolled back {len(snapshots)} files."}

    tracer.log("refactor", {
        "batch_id": batch_id,
        "files_changed": len(results),
        "total_matches": sum(r.match_count for r in results),
        "status": "applied",
    })

    return {
        "file_buffer": new_file_buffer,
        "edit_history": new_edit_history,
        "error_state": None,
    }


def _rollback_snapshots(snapshots: dict[str, str]) -> None:
    """Best-effort rollback: restore files from snapshots."""
    for file_path, original_content in snapshots.items():
        try:
            with open(file_path, "w") as f:
                f.write(original_content)
        except OSError:
            pass  # best-effort — log but don't crash


def _find_pending_batch(edit_history: list[dict]) -> str | None:
    """Find a batch_id from a pending refactor in edit_history.

    When the graph resumes after human approval, the edit_history contains
    entries with status="proposed" and a batch_id from the previous invocation.
    """
    for entry in edit_history:
        if entry.get("status") == "proposed" and entry.get("batch_id"):
            return entry["batch_id"]
    return None
```

- [ ] **Step 3: Run tests**

Run: `.venv/bin/pytest tests/test_refactor_node.py -v`
Expected: All PASS.

- [ ] **Step 4: Run full test suite**

Run: `.venv/bin/pytest tests/test_ast_ops.py tests/test_refactor_node.py tests/test_graph.py tests/test_editor_node.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/nodes/refactor.py tests/test_refactor_node.py
git commit -m "feat: implement refactor_node with dry-run, apply, and rollback"
```

---

## Task 9: Batch Approval HTTP Endpoint

**Files:**
- Modify: `server/main.py`

- [ ] **Step 1: Add the batch endpoint**

Add after the existing `PATCH /runs/{run_id}/edits/{edit_id}` endpoint in `server/main.py`:

```python
class BatchActionRequest(BaseModel):
    action: Literal["approve", "reject"]


@app.patch("/runs/{run_id}/batches/{batch_id}")
async def patch_batch(run_id: str, batch_id: str, req: BatchActionRequest):
    approval_manager: ApprovalManager = app.state.approval_manager

    try:
        if req.action == "approve":
            op_id = f"op_batch_{batch_id}_approve"
            result = await approval_manager.approve_batch(batch_id, op_id)
            # Resume the run after batch approval
            asyncio.create_task(_resume_run(run_id))
            return {"batch_id": batch_id, "action": "approved", "edit_count": len(result)}
        elif req.action == "reject":
            op_id = f"op_batch_{batch_id}_reject"
            result = await approval_manager.reject_batch(batch_id, op_id)
            asyncio.create_task(_resume_run(run_id))
            return {"batch_id": batch_id, "action": "rejected", "edit_count": len(result)}
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 2: Update execute() and _resume_run to inject approval_manager and run_id**

In `server/main.py`, update the `config` dict in both `execute()` and `_resume_run()`:

```python
# In execute() — around line 187:
config = {
    "configurable": {
        "store": store,
        "router": router,
        "approval_manager": app.state.approval_manager,
        "run_id": run_id,
        "supervised": project.autonomy_mode == "supervised" if project else False,
    }
}

# In _resume_run() — around line 128:
config = {
    "configurable": {
        "store": store,
        "router": router,
        "approval_manager": app.state.approval_manager,
        "run_id": run_id,
        "supervised": False,  # resumed runs have already been approved
    }
}
```

This is required for the refactor_node's supervised flow to work — it reads `approval_manager` and `run_id` from config.

- [ ] **Step 3: Add BatchActionRequest import**

Make sure `Literal` is imported from `typing` at the top of `server/main.py`. `BaseModel` should already be imported.

- [ ] **Step 3: Run server tests for regressions**

Run: `.venv/bin/pytest tests/test_server.py -v --timeout=30`
Expected: All PASS.

- [ ] **Step 4: Commit**

```bash
git add server/main.py
git commit -m "feat: add PATCH /runs/{run_id}/batches/{batch_id} endpoint"
```

---

## Task 10: End-to-End Integration Test

**Files:**
- Modify: `tests/test_refactor_node.py`

- [ ] **Step 1: Add full-flow integration test**

Add to `tests/test_refactor_node.py`:

```python
@pytest.mark.asyncio
async def test_full_refactor_flow_through_graph_routing(tmp_path):
    """Test that classify_step routes to refactor_node and it executes."""
    from agent.graph import classify_step

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.ts").write_text("const x = oldFunc(1);\n")

    # Verify routing
    state = {
        "plan": [{
            "id": "refactor-1",
            "kind": "refactor",
            "pattern": "oldFunc($ARG)",
            "refactor_replacement": "newFunc($ARG)",
            "language": "typescript",
            "scope": str(tmp_path / "src"),
            "complexity": "complex",
        }],
        "current_step": 0,
    }
    assert classify_step(state) == "refactor"

    # Verify coordinator puts refactor in sequential
    from agent.nodes.coordinator import coordinator_node
    coord_state = {
        "plan": [
            state["plan"][0],
            {"id": "step-2", "kind": "edit", "target_files": ["web/b.ts"], "complexity": "simple"},
        ],
    }
    coord_result = coordinator_node(coord_state)
    assert 0 in coord_result["sequential_first"]

    # Verify refactor node applies
    from agent.nodes.refactor import refactor_node
    full_state = {
        **state,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
        "working_directory": str(tmp_path),
        "ast_available": {"typescript": True},
    }
    config = {"configurable": {}}
    result = await refactor_node(full_state, config)
    assert result["error_state"] is None
    assert "newFunc(1)" in (tmp_path / "src" / "a.ts").read_text()
```

- [ ] **Step 2: Run integration test**

Run: `.venv/bin/pytest tests/test_refactor_node.py -v`
Expected: All PASS.

- [ ] **Step 3: Run full test suite**

Run: `.venv/bin/pytest tests/ -v --timeout=60 -k "ast_ops or refactor or graph or steps or editor or coordinator"`
Expected: All PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_refactor_node.py
git commit -m "test: add end-to-end refactor flow integration test"
```

---

## Task 11: Final Verification

- [ ] **Step 1: Run all Phase 2 related tests**

Run: `.venv/bin/pytest tests/test_ast_ops.py tests/test_refactor_node.py tests/test_steps.py tests/test_graph.py tests/test_approval.py tests/test_editor_node.py -v`
Expected: All PASS.

- [ ] **Step 2: Verify import chain**

Run:
```bash
.venv/bin/python -c "
from agent.tools.ast_ops import apply_rule, RefactorResult
from agent.nodes.refactor import refactor_node
from agent.steps import PlanStep
from agent.graph import classify_step, build_graph
from agent.nodes.coordinator import coordinator_node
print('All imports successful')
step = PlanStep(id='r1', kind='refactor', complexity='complex', pattern='old(\$A)', refactor_replacement='new(\$A)', language='typescript', scope='src/')
print(f'PlanStep refactor: {step.kind}, pattern={step.pattern}')
"
```
Expected: "All imports successful" and PlanStep details.

- [ ] **Step 3: Verify graph compiles**

Run:
```bash
.venv/bin/python -c "
from agent.graph import build_graph
graph = build_graph()
print(f'Graph compiled with {len(graph.nodes)} nodes')
"
```
Expected: Graph compiled with N nodes (should be 12 — the original 11 + refactor).

- [ ] **Step 4: Final commit if any cleanup needed**

```bash
git status
# If clean, skip. If changes, commit.
```
