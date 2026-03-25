# Phase 1: Core Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the Shipyard backend from Anthropic Claude to OpenAI with a policy-based model router, deterministic context assembly, typed plan steps, and SQLite persistence — producing a fully testable backend before any UI work begins.

**Architecture:** Replace `agent/llm.py` (single Anthropic call) with a model capability registry + policy-based router that resolves task types to model tiers. Add a context assembly pipeline that ranks and deduplicates content before each LLM call. Replace in-memory state with SQLite via a Protocol-based SessionStore. Migrate all nodes from string-based plan steps to typed `PlanStep` objects.

**Tech Stack:** Python 3.11, OpenAI SDK, LangGraph 1.1.3, FastAPI, aiosqlite, Pydantic v2, pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-24-shipyard-v2-design.md` (Sections 2, 5, 6)

**Commit rule:** Never include `Co-Authored-By` lines in commit messages.

---

## File Structure

### New Files
- `agent/models.py` — Model capability registry (config-driven model definitions)
- `agent/router.py` — Policy-based model router with tier resolution and escalation
- `agent/context.py` — Deterministic context assembly pipeline
- `agent/steps.py` — PlanStep Pydantic model and step utilities
- `store/__init__.py` — Package init
- `store/protocol.py` — SessionStore Protocol definition
- `store/models.py` — Pydantic models (Project, Run, Event, Edit, etc.)
- `store/sqlite.py` — SQLiteSessionStore implementation
- `tests/test_models_registry.py` — Model registry tests
- `tests/test_router.py` — Router routing + escalation tests
- `tests/test_context.py` — Context assembly tests
- `tests/test_steps.py` — PlanStep schema tests
- `tests/test_store.py` — SQLite store tests

### Modified Files
- `agent/llm.py` — Replace Anthropic with thin OpenAI wrapper (called by router)
- `agent/state.py` — Add typed PlanStep list, context assembly fields
- `agent/graph.py` — Update classify_step to use PlanStep.kind, wire new nodes
- `agent/nodes/planner.py` — Output PlanStep objects, assign complexity
- `agent/nodes/editor.py` — Use router instead of call_llm, accept context assembly
- `agent/nodes/validator.py` — Multi-layer validation (syntax + lint + typecheck)
- `agent/nodes/receive.py` — Load project context from store
- `agent/nodes/reporter.py` — Record model usage stats, persist to store
- `agent/prompts/planner.py` — Updated prompt for typed step output
- `agent/prompts/editor.py` — Updated prompt (no token budget references)
- `server/main.py` — Inject store + router via LangGraph config, add project/run endpoints
- `requirements.txt` — Swap anthropic for openai, add aiosqlite
- `pyproject.toml` — Update dependencies
- `.env.example` — OPENAI_API_KEY instead of ANTHROPIC_API_KEY

---

## Task 1: Dependency Migration

**Files:**
- Modify: `requirements.txt`
- Modify: `pyproject.toml`
- Modify: `.env.example`

- [ ] **Step 1: Update requirements.txt**

```txt
langgraph==1.1.3
langchain-openai>=0.3.0
langchain-core==1.2.21
openai>=1.60.0
fastapi>=0.115.0
uvicorn>=0.34.0
httpx>=0.28.0
pyyaml>=6.0
aiosqlite>=0.20.0
```

- [ ] **Step 2: Update pyproject.toml dependencies**

Replace the `dependencies` list in `pyproject.toml` to match requirements.txt. Remove `anthropic` and `langchain-anthropic`. Add `openai`, `langchain-openai`, `aiosqlite`.

- [ ] **Step 3: Update .env.example**

```env
OPENAI_API_KEY=your-openai-api-key-here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-api-key-here
LANGCHAIN_PROJECT=shipyard
```

- [ ] **Step 4: Install new dependencies**

Run: `pip install -r requirements.txt`
Expected: All packages install successfully

- [ ] **Step 5: Commit**

```bash
git add requirements.txt pyproject.toml .env.example
git commit -m "chore: migrate dependencies from Anthropic to OpenAI"
```

---

## Task 2: Model Capability Registry

**Files:**
- Create: `agent/models.py`
- Test: `tests/test_models_registry.py`

- [ ] **Step 1: Write failing tests for model registry**

```python
# tests/test_models_registry.py
import pytest
from agent.models import MODEL_REGISTRY, get_model_for_tier, ModelConfig


def test_registry_has_three_models():
    assert len(MODEL_REGISTRY) == 3
    assert "o3" in MODEL_REGISTRY
    assert "gpt-4o" in MODEL_REGISTRY
    assert "gpt-4o-mini" in MODEL_REGISTRY


def test_model_config_has_required_fields():
    for model_id, config in MODEL_REGISTRY.items():
        assert isinstance(config, ModelConfig)
        assert config.id == model_id
        assert config.context_window > 0
        assert config.max_output > 0
        assert config.tier in ("reasoning", "general", "fast")
        assert config.timeout > 0
        assert isinstance(config.capabilities, list)


def test_get_model_for_tier_reasoning():
    model = get_model_for_tier("reasoning")
    assert model.id == "o3"


def test_get_model_for_tier_general():
    model = get_model_for_tier("general")
    assert model.id == "gpt-4o"


def test_get_model_for_tier_fast():
    model = get_model_for_tier("fast")
    assert model.id == "gpt-4o-mini"


def test_get_model_for_tier_invalid():
    with pytest.raises(ValueError, match="Unknown tier"):
        get_model_for_tier("unknown")


def test_escalation_order():
    fast = get_model_for_tier("fast")
    general = get_model_for_tier("general")
    reasoning = get_model_for_tier("reasoning")
    assert fast.timeout < general.timeout < reasoning.timeout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent.models'`

- [ ] **Step 3: Implement model registry**

```python
# agent/models.py
"""Model capability registry — config-driven, not hardcoded to specific model names."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelConfig:
    id: str
    context_window: int
    max_output: int
    tier: str  # "reasoning" | "general" | "fast"
    timeout: int  # seconds
    capabilities: list[str] = field(default_factory=list)


MODEL_REGISTRY: dict[str, ModelConfig] = {
    "o3": ModelConfig(
        id="o3",
        context_window=200_000,
        max_output=100_000,
        tier="reasoning",
        timeout=120,
        capabilities=["planning", "complex_edit", "conflict_resolution"],
    ),
    "gpt-4o": ModelConfig(
        id="gpt-4o",
        context_window=128_000,
        max_output=16_384,
        tier="general",
        timeout=60,
        capabilities=["edit", "read", "summarize", "merge"],
    ),
    "gpt-4o-mini": ModelConfig(
        id="gpt-4o-mini",
        context_window=128_000,
        max_output=16_384,
        tier="fast",
        timeout=30,
        capabilities=["classify", "validate", "syntax_check"],
    ),
}


def get_model_for_tier(tier: str) -> ModelConfig:
    """Resolve a tier name to the best available model."""
    for config in MODEL_REGISTRY.values():
        if config.tier == tier:
            return config
    raise ValueError(f"Unknown tier: {tier}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models_registry.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agent/models.py tests/test_models_registry.py
git commit -m "feat: add model capability registry with tier resolution"
```

---

## Task 3: OpenAI LLM Wrapper

**Files:**
- Modify: `agent/llm.py`

- [ ] **Step 1: Rewrite llm.py for OpenAI**

Replace the entire contents of `agent/llm.py`:

```python
# agent/llm.py
"""Thin OpenAI wrapper — called by the router, not by nodes directly."""
import os
from openai import AsyncOpenAI

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _client


async def call_llm(
    system: str,
    user: str,
    model: str = "gpt-4o",
    max_tokens: int = 16_384,
    timeout: int = 60,
) -> str:
    """Call OpenAI chat completions. Returns the assistant message content."""
    client = _get_client()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        timeout=timeout,
    )
    return response.choices[0].message.content or ""
```

- [ ] **Step 2: Verify existing tests still compile**

Run: `pytest tests/test_graph.py -v --collect-only`
Expected: Tests collected (they won't run without API key, but import should work)

- [ ] **Step 3: Commit**

```bash
git add agent/llm.py
git commit -m "feat: replace Anthropic LLM wrapper with OpenAI"
```

---

## Task 4: Policy-Based Model Router

**Files:**
- Create: `agent/router.py`
- Test: `tests/test_router.py`

- [ ] **Step 1: Write failing tests for router**

```python
# tests/test_router.py
import pytest
from unittest.mock import AsyncMock, patch
from agent.router import ModelRouter, ROUTING_POLICY


def test_routing_policy_covers_all_task_types():
    expected_tasks = [
        "plan", "coordinate", "edit_complex", "edit_simple",
        "read", "validate", "merge", "summarize", "parse_results",
    ]
    for task in expected_tasks:
        assert task in ROUTING_POLICY, f"Missing policy for {task}"


def test_routing_policy_values_are_valid_tiers():
    valid_tiers = {"reasoning", "general", "fast"}
    for task, policy in ROUTING_POLICY.items():
        assert policy["tier"] in valid_tiers
        if policy.get("escalation"):
            assert policy["escalation"] in valid_tiers


def test_router_resolve_model():
    router = ModelRouter()
    model = router.resolve_model("plan")
    assert model.id == "o3"

    model = router.resolve_model("edit_simple")
    assert model.id == "gpt-4o"

    model = router.resolve_model("validate")
    assert model.id == "gpt-4o-mini"


def test_router_resolve_escalation():
    router = ModelRouter()
    escalated = router.resolve_escalation("edit_simple")
    assert escalated is not None
    assert escalated.id == "o3"  # general → reasoning

    escalated = router.resolve_escalation("validate")
    assert escalated is not None
    assert escalated.id == "gpt-4o"  # fast → general


def test_router_resolve_escalation_no_escalation():
    router = ModelRouter()
    escalated = router.resolve_escalation("plan")
    assert escalated is None  # reasoning has no escalation


@pytest.mark.asyncio
async def test_router_call_routes_to_correct_model():
    router = ModelRouter()
    with patch("agent.router.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = '{"result": "ok"}'
        result = await router.call("plan", "system prompt", "user prompt")
        mock_llm.assert_called_once()
        call_kwargs = mock_llm.call_args
        assert call_kwargs.kwargs["model"] == "o3"
        assert result == '{"result": "ok"}'


@pytest.mark.asyncio
async def test_router_call_escalates_on_failure():
    router = ModelRouter()
    with patch("agent.router.call_llm", new_callable=AsyncMock) as mock_llm:
        # First call fails, second succeeds
        mock_llm.side_effect = [Exception("timeout"), '{"result": "ok"}']
        result = await router.call("edit_simple", "system", "user")
        assert mock_llm.call_count == 2
        # Second call should use escalated model
        second_call = mock_llm.call_args_list[1]
        assert second_call.kwargs["model"] == "o3"
        assert result == '{"result": "ok"}'


@pytest.mark.asyncio
async def test_router_call_raises_after_failed_escalation():
    router = ModelRouter()
    with patch("agent.router.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = Exception("all models failed")
        with pytest.raises(Exception, match="all models failed"):
            await router.call("plan", "system", "user")
        # plan has no escalation, so only 1 call
        assert mock_llm.call_count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent.router'`

- [ ] **Step 3: Implement router**

```python
# agent/router.py
"""Policy-based model router with tier resolution and auto-escalation."""
from agent.models import get_model_for_tier, ModelConfig
from agent.llm import call_llm

# Task type → tier mapping. Escalation tier is used on failure.
ROUTING_POLICY: dict[str, dict] = {
    "plan":           {"tier": "reasoning"},
    "coordinate":     {"tier": "reasoning"},
    "edit_complex":   {"tier": "reasoning"},
    "edit_simple":    {"tier": "general", "escalation": "reasoning"},
    "read":           {"tier": "general"},
    "validate":       {"tier": "fast",    "escalation": "general"},
    "merge":          {"tier": "general", "escalation": "reasoning"},
    "summarize":      {"tier": "general"},
    "parse_results":  {"tier": "general", "escalation": "reasoning"},
}


class ModelRouter:
    """Routes LLM calls to the optimal model based on task type."""

    def resolve_model(self, task_type: str) -> ModelConfig:
        """Look up tier for task, resolve to best available model."""
        policy = ROUTING_POLICY[task_type]
        return get_model_for_tier(policy["tier"])

    def resolve_escalation(self, task_type: str) -> ModelConfig | None:
        """Get the escalation model for a task type, or None."""
        policy = ROUTING_POLICY[task_type]
        esc_tier = policy.get("escalation")
        if esc_tier is None:
            return None
        return get_model_for_tier(esc_tier)

    async def call(
        self,
        task_type: str,
        system: str,
        user: str,
    ) -> str:
        """Route to appropriate model. Auto-escalate on failure."""
        model = self.resolve_model(task_type)
        try:
            return await call_llm(
                system=system,
                user=user,
                model=model.id,
                max_tokens=model.max_output,
                timeout=model.timeout,
            )
        except Exception:
            escalated = self.resolve_escalation(task_type)
            if escalated is None:
                raise
            return await call_llm(
                system=system,
                user=user,
                model=escalated.id,
                max_tokens=escalated.max_output,
                timeout=escalated.timeout,
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_router.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agent/router.py tests/test_router.py
git commit -m "feat: add policy-based model router with auto-escalation"
```

---

## Task 5: Typed Plan Steps

**Files:**
- Create: `agent/steps.py`
- Test: `tests/test_steps.py`

- [ ] **Step 1: Write failing tests for PlanStep**

```python
# tests/test_steps.py
import pytest
import json
from agent.steps import PlanStep, parse_plan_steps


def test_plan_step_creation():
    step = PlanStep(
        id="step-1",
        kind="edit",
        target_files=["src/auth.ts"],
        complexity="simple",
    )
    assert step.id == "step-1"
    assert step.kind == "edit"
    assert step.target_files == ["src/auth.ts"]
    assert step.complexity == "simple"
    assert step.depends_on == []
    assert step.command is None
    assert step.acceptance_criteria == []


def test_plan_step_valid_kinds():
    for kind in ("read", "edit", "exec", "test", "git"):
        step = PlanStep(id="s", kind=kind, complexity="simple")
        assert step.kind == kind


def test_plan_step_invalid_kind():
    with pytest.raises(ValueError):
        PlanStep(id="s", kind="invalid", complexity="simple")


def test_plan_step_valid_complexities():
    for c in ("simple", "complex"):
        step = PlanStep(id="s", kind="read", complexity=c)
        assert step.complexity == c


def test_plan_step_invalid_complexity():
    with pytest.raises(ValueError):
        PlanStep(id="s", kind="read", complexity="medium")


def test_parse_plan_steps_from_json():
    raw = json.dumps([
        {"id": "1", "kind": "read", "target_files": ["a.ts"], "complexity": "simple"},
        {"id": "2", "kind": "edit", "target_files": ["a.ts"], "complexity": "complex", "depends_on": ["1"]},
    ])
    steps = parse_plan_steps(raw)
    assert len(steps) == 2
    assert steps[0].kind == "read"
    assert steps[1].depends_on == ["1"]


def test_parse_plan_steps_fallback_on_invalid_json():
    """If LLM returns garbage, wrap as a single exec step."""
    steps = parse_plan_steps("just do the thing")
    assert len(steps) == 1
    assert steps[0].kind == "exec"
    assert steps[0].complexity == "complex"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_steps.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent.steps'`

- [ ] **Step 3: Implement PlanStep**

```python
# agent/steps.py
"""Typed plan step schema and parsing utilities."""
import json
from pydantic import BaseModel, field_validator
from typing import Literal


class PlanStep(BaseModel):
    id: str
    kind: Literal["read", "edit", "exec", "test", "git"]
    target_files: list[str] = []
    command: str | None = None
    acceptance_criteria: list[str] = []
    complexity: Literal["simple", "complex"]
    depends_on: list[str] = []

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        allowed = {"read", "edit", "exec", "test", "git"}
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

    # Fallback: treat as single step
    return [PlanStep(
        id="fallback-1",
        kind="exec",
        command=raw.strip(),
        complexity="complex",
    )]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_steps.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agent/steps.py tests/test_steps.py
git commit -m "feat: add typed PlanStep schema with parsing and validation"
```

---

## Task 6: Store Models (Pydantic)

**Files:**
- Create: `store/__init__.py`
- Create: `store/models.py`

- [ ] **Step 1: Create store package**

```python
# store/__init__.py
```

- [ ] **Step 2: Implement Pydantic models**

```python
# store/models.py
"""Pydantic models for persistence layer."""
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any
import uuid


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class Project(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str
    path: str
    github_repo: str | None = None
    github_pat: str | None = None
    default_model: str = "gpt-4o"
    autonomy_mode: str = "supervised"
    test_command: str | None = None
    build_command: str | None = None
    lint_command: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Run(BaseModel):
    id: str = Field(default_factory=_new_id)
    project_id: str
    instruction: str
    status: str = "running"
    branch: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    plan: list[dict] = Field(default_factory=list)
    model_usage: dict[str, int] = Field(default_factory=dict)
    total_tokens: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


class Event(BaseModel):
    id: str = Field(default_factory=_new_id)
    run_id: str
    type: str
    node: str | None = None
    model: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())


class EditRecord(BaseModel):
    id: str = Field(default_factory=_new_id)
    run_id: str
    file_path: str
    step: int = 0
    anchor: str | None = None
    old_content: str | None = None
    new_content: str | None = None
    status: str = "proposed"
    approved_at: datetime | None = None


class Conversation(BaseModel):
    id: str = Field(default_factory=_new_id)
    project_id: str
    title: str | None = None
    messages: list[dict] = Field(default_factory=list)
    model: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class GitOperation(BaseModel):
    id: str = Field(default_factory=_new_id)
    run_id: str
    type: str  # commit | push | pr_create | pr_merge | pr_comment
    branch: str | None = None
    commit_sha: str | None = None
    pr_url: str | None = None
    pr_number: int | None = None
    status: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 3: Verify models instantiate**

Run: `python -c "from store.models import Project, Run, Event; p = Project(name='test', path='/tmp'); print(p.id, p.name)"`
Expected: Prints a hex ID and "test"

- [ ] **Step 4: Commit**

```bash
git add store/__init__.py store/models.py
git commit -m "feat: add Pydantic models for persistence layer"
```

---

## Task 7: SessionStore Protocol

**Files:**
- Create: `store/protocol.py`

- [ ] **Step 1: Implement Protocol**

```python
# store/protocol.py
"""SessionStore Protocol — thin interface for swappable backends."""
from typing import Protocol, runtime_checkable
from store.models import Project, Run, Event, EditRecord, Conversation, GitOperation


@runtime_checkable
class SessionStore(Protocol):
    async def create_project(self, project: Project) -> Project: ...
    async def get_project(self, project_id: str) -> Project | None: ...
    async def list_projects(self) -> list[Project]: ...
    async def update_project(self, project: Project) -> Project: ...

    async def create_run(self, run: Run) -> Run: ...
    async def get_run(self, run_id: str) -> Run | None: ...
    async def update_run(self, run: Run) -> Run: ...
    async def list_runs(self, project_id: str) -> list[Run]: ...

    async def append_event(self, event: Event) -> None: ...
    async def replay_events(self, run_id: str, after_id: str | None = None) -> list[Event]: ...

    async def create_edit(self, edit: EditRecord) -> EditRecord: ...
    async def get_edits(self, run_id: str) -> list[EditRecord]: ...
    async def update_edit_status(self, edit_id: str, status: str) -> None: ...

    async def create_conversation(self, conv: Conversation) -> Conversation: ...
    async def get_conversations(self, project_id: str) -> list[Conversation]: ...

    async def log_git_op(self, op: GitOperation) -> None: ...
```

- [ ] **Step 2: Commit**

```bash
git add store/protocol.py
git commit -m "feat: add SessionStore Protocol interface"
```

---

## Task 8: SQLite Store Implementation

**Files:**
- Create: `store/sqlite.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_store.py
import pytest
import pytest_asyncio
from store.sqlite import SQLiteSessionStore
from store.models import Project, Run, Event, EditRecord


@pytest_asyncio.fixture
async def store(tmp_path):
    db_path = str(tmp_path / "test.db")
    s = SQLiteSessionStore(db_path)
    await s.initialize()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_create_and_get_project(store):
    project = Project(name="test-project", path="/tmp/test")
    created = await store.create_project(project)
    assert created.id == project.id

    fetched = await store.get_project(project.id)
    assert fetched is not None
    assert fetched.name == "test-project"
    assert fetched.path == "/tmp/test"


@pytest.mark.asyncio
async def test_list_projects(store):
    await store.create_project(Project(name="p1", path="/a"))
    await store.create_project(Project(name="p2", path="/b"))
    projects = await store.list_projects()
    assert len(projects) == 2


@pytest.mark.asyncio
async def test_create_and_get_run(store):
    project = Project(name="p", path="/tmp")
    await store.create_project(project)

    run = Run(project_id=project.id, instruction="do stuff")
    created = await store.create_run(run)
    assert created.status == "running"

    fetched = await store.get_run(run.id)
    assert fetched is not None
    assert fetched.instruction == "do stuff"


@pytest.mark.asyncio
async def test_update_run_status(store):
    project = Project(name="p", path="/tmp")
    await store.create_project(project)

    run = Run(project_id=project.id, instruction="test")
    await store.create_run(run)

    run.status = "completed"
    await store.update_run(run)

    fetched = await store.get_run(run.id)
    assert fetched.status == "completed"


@pytest.mark.asyncio
async def test_append_and_replay_events(store):
    e1 = Event(run_id="r1", type="status", node="planner", data={"step": 1})
    e2 = Event(run_id="r1", type="diff", node="editor", data={"file": "a.ts"})
    e3 = Event(run_id="r1", type="status", node="validator", data={"step": 2})

    await store.append_event(e1)
    await store.append_event(e2)
    await store.append_event(e3)

    events = await store.replay_events("r1")
    assert len(events) == 3
    assert events[0].type == "status"
    assert events[2].node == "validator"


@pytest.mark.asyncio
async def test_replay_events_after_cursor(store):
    e1 = Event(run_id="r1", type="status", data={"a": 1})
    e2 = Event(run_id="r1", type="diff", data={"b": 2})
    await store.append_event(e1)
    await store.append_event(e2)

    events = await store.replay_events("r1", after_id=e1.id)
    assert len(events) == 1
    assert events[0].id == e2.id


@pytest.mark.asyncio
async def test_create_and_get_edits(store):
    edit = EditRecord(run_id="r1", file_path="a.ts", step=0, status="proposed")
    await store.create_edit(edit)

    edits = await store.get_edits("r1")
    assert len(edits) == 1
    assert edits[0].file_path == "a.ts"


@pytest.mark.asyncio
async def test_update_edit_status(store):
    edit = EditRecord(run_id="r1", file_path="a.ts")
    await store.create_edit(edit)

    await store.update_edit_status(edit.id, "approved")

    edits = await store.get_edits("r1")
    assert edits[0].status == "approved"


@pytest.mark.asyncio
async def test_get_project_returns_none_for_missing(store):
    result = await store.get_project("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_get_run_returns_none_for_missing(store):
    result = await store.get_run("nonexistent")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'store.sqlite'`

- [ ] **Step 3: Implement SQLiteSessionStore**

```python
# store/sqlite.py
"""SQLite implementation of SessionStore."""
import aiosqlite
import json
from store.models import Project, Run, Event, EditRecord, Conversation, GitOperation


class SQLiteSessionStore:
    def __init__(self, db_path: str = "shipyard.db"):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self):
        """Create tables if they don't exist."""
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA)
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()

    # --- Projects ---

    async def create_project(self, project: Project) -> Project:
        await self._db.execute(
            "INSERT INTO projects (id, name, path, github_repo, github_pat, default_model, autonomy_mode, test_command, build_command, lint_command) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (project.id, project.name, project.path, project.github_repo, project.github_pat, project.default_model, project.autonomy_mode, project.test_command, project.build_command, project.lint_command),
        )
        await self._db.commit()
        return project

    async def get_project(self, project_id: str) -> Project | None:
        cursor = await self._db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return Project(**dict(row))

    async def list_projects(self) -> list[Project]:
        cursor = await self._db.execute("SELECT * FROM projects ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [Project(**dict(r)) for r in rows]

    async def update_project(self, project: Project) -> Project:
        await self._db.execute(
            "UPDATE projects SET name=?, path=?, github_repo=?, github_pat=?, default_model=?, autonomy_mode=?, test_command=?, build_command=?, lint_command=? WHERE id=?",
            (project.name, project.path, project.github_repo, project.github_pat, project.default_model, project.autonomy_mode, project.test_command, project.build_command, project.lint_command, project.id),
        )
        await self._db.commit()
        return project

    # --- Runs ---

    async def create_run(self, run: Run) -> Run:
        await self._db.execute(
            "INSERT INTO runs (id, project_id, instruction, status, branch, context, plan, model_usage, total_tokens) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run.id, run.project_id, run.instruction, run.status, run.branch, json.dumps(run.context), json.dumps(run.plan), json.dumps(run.model_usage), run.total_tokens),
        )
        await self._db.commit()
        return run

    async def get_run(self, run_id: str) -> Run | None:
        cursor = await self._db.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        d = dict(row)
        d["context"] = json.loads(d["context"]) if d["context"] else {}
        d["plan"] = json.loads(d["plan"]) if d["plan"] else []
        d["model_usage"] = json.loads(d["model_usage"]) if d["model_usage"] else {}
        return Run(**d)

    async def update_run(self, run: Run) -> Run:
        await self._db.execute(
            "UPDATE runs SET status=?, branch=?, plan=?, model_usage=?, total_tokens=?, completed_at=? WHERE id=?",
            (run.status, run.branch, json.dumps(run.plan), json.dumps(run.model_usage), run.total_tokens, run.completed_at, run.id),
        )
        await self._db.commit()
        return run

    async def list_runs(self, project_id: str) -> list[Run]:
        cursor = await self._db.execute("SELECT * FROM runs WHERE project_id = ? ORDER BY created_at DESC", (project_id,))
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["context"] = json.loads(d["context"]) if d["context"] else {}
            d["plan"] = json.loads(d["plan"]) if d["plan"] else []
            d["model_usage"] = json.loads(d["model_usage"]) if d["model_usage"] else {}
            result.append(Run(**d))
        return result

    # --- Events ---

    async def append_event(self, event: Event) -> None:
        await self._db.execute(
            "INSERT INTO events (id, run_id, type, node, model, data, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (event.id, event.run_id, event.type, event.node, event.model, json.dumps(event.data), event.timestamp),
        )
        await self._db.commit()

    async def replay_events(self, run_id: str, after_id: str | None = None) -> list[Event]:
        if after_id:
            cursor = await self._db.execute(
                "SELECT * FROM events WHERE run_id = ? AND timestamp > (SELECT timestamp FROM events WHERE id = ?) ORDER BY timestamp",
                (run_id, after_id),
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM events WHERE run_id = ? ORDER BY timestamp",
                (run_id,),
            )
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["data"] = json.loads(d["data"]) if d["data"] else {}
            result.append(Event(**d))
        return result

    # --- Edits ---

    async def create_edit(self, edit: EditRecord) -> EditRecord:
        await self._db.execute(
            "INSERT INTO edits (id, run_id, file_path, step, anchor, old_content, new_content, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (edit.id, edit.run_id, edit.file_path, edit.step, edit.anchor, edit.old_content, edit.new_content, edit.status),
        )
        await self._db.commit()
        return edit

    async def get_edits(self, run_id: str) -> list[EditRecord]:
        cursor = await self._db.execute("SELECT * FROM edits WHERE run_id = ? ORDER BY step", (run_id,))
        rows = await cursor.fetchall()
        return [EditRecord(**dict(r)) for r in rows]

    async def update_edit_status(self, edit_id: str, status: str) -> None:
        await self._db.execute("UPDATE edits SET status = ? WHERE id = ?", (status, edit_id))
        await self._db.commit()

    # --- Conversations ---

    async def create_conversation(self, conv: Conversation) -> Conversation:
        await self._db.execute(
            "INSERT INTO conversations (id, project_id, title, messages, model) VALUES (?, ?, ?, ?, ?)",
            (conv.id, conv.project_id, conv.title, json.dumps(conv.messages), conv.model),
        )
        await self._db.commit()
        return conv

    async def get_conversations(self, project_id: str) -> list[Conversation]:
        cursor = await self._db.execute("SELECT * FROM conversations WHERE project_id = ? ORDER BY updated_at DESC", (project_id,))
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["messages"] = json.loads(d["messages"]) if d["messages"] else []
            result.append(Conversation(**d))
        return result

    # --- Git Operations ---

    async def log_git_op(self, op: GitOperation) -> None:
        await self._db.execute(
            "INSERT INTO git_operations (id, run_id, type, branch, commit_sha, pr_url, pr_number, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (op.id, op.run_id, op.type, op.branch, op.commit_sha, op.pr_url, op.pr_number, op.status),
        )
        await self._db.commit()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    github_repo TEXT,
    github_pat TEXT,
    default_model TEXT DEFAULT 'gpt-4o',
    autonomy_mode TEXT DEFAULT 'supervised',
    test_command TEXT,
    build_command TEXT,
    lint_command TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    instruction TEXT NOT NULL,
    status TEXT DEFAULT 'running',
    branch TEXT,
    context TEXT,
    plan TEXT,
    model_usage TEXT,
    total_tokens INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES runs(id),
    type TEXT NOT NULL,
    node TEXT,
    model TEXT,
    data TEXT,
    timestamp REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_replay ON events(run_id, timestamp);

CREATE TABLE IF NOT EXISTS edits (
    id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES runs(id),
    file_path TEXT NOT NULL,
    step INTEGER DEFAULT 0,
    anchor TEXT,
    old_content TEXT,
    new_content TEXT,
    status TEXT DEFAULT 'proposed',
    approved_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    title TEXT,
    messages TEXT,
    model TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS git_operations (
    id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES runs(id),
    type TEXT NOT NULL,
    branch TEXT,
    commit_sha TEXT,
    pr_url TEXT,
    pr_number INTEGER,
    status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_store.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add store/sqlite.py tests/test_store.py
git commit -m "feat: add SQLite SessionStore implementation"
```

---

## Task 9: Context Assembly Pipeline

**Files:**
- Create: `agent/context.py`
- Test: `tests/test_context.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_context.py
import pytest
from agent.context import ContextAssembler


def test_assembler_includes_task_context():
    assembler = ContextAssembler(max_tokens=10000)
    assembler.add_task("Edit auth.ts", step=2, total_steps=5)
    result = assembler.build()
    assert "Edit auth.ts" in result
    assert "Step 2/5" in result


def test_assembler_includes_working_set():
    assembler = ContextAssembler(max_tokens=10000)
    assembler.add_file("src/auth.ts", "export function verify() {}")
    result = assembler.build()
    assert "src/auth.ts" in result
    assert "export function verify" in result


def test_assembler_deduplicates_files():
    assembler = ContextAssembler(max_tokens=10000)
    assembler.add_file("src/auth.ts", "content")
    assembler.add_file("src/auth.ts", "content")
    result = assembler.build()
    assert result.count("src/auth.ts") == 1


def test_assembler_includes_error_context():
    assembler = ContextAssembler(max_tokens=10000)
    assembler.add_error("TypeError: x is not a function\n  at line 42")
    result = assembler.build()
    assert "TypeError" in result


def test_assembler_respects_max_tokens():
    assembler = ContextAssembler(max_tokens=100)
    assembler.add_file("big.ts", "x" * 10000)
    result = assembler.build()
    # Result should be truncated to fit
    assert len(result) < 10000


def test_assembler_prioritizes_working_set():
    """Working set files should always be included, reference set evicted first."""
    assembler = ContextAssembler(max_tokens=200)
    assembler.add_file("current.ts", "important", priority="working")
    assembler.add_file("reference.ts", "y" * 5000, priority="reference")
    result = assembler.build()
    assert "current.ts" in result
    assert "important" in result


def test_assembler_empty():
    assembler = ContextAssembler(max_tokens=10000)
    result = assembler.build()
    assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_context.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent.context'`

- [ ] **Step 3: Implement context assembler**

```python
# agent/context.py
"""Deterministic context assembly pipeline.

Fills the model's context window using a ranked priority system:
1. Task context (always included)
2. Working set (highest priority files — current edit target, errors)
3. Reference set (plan files, imports, dependencies)
4. Execution evidence (test failures, lint output)
5. Conversation memory (evicted first)
"""

# Rough chars-per-token estimate for context budgeting
CHARS_PER_TOKEN = 4


class ContextAssembler:
    def __init__(self, max_tokens: int = 128_000):
        self.max_chars = max_tokens * CHARS_PER_TOKEN
        self._task: str = ""
        self._files: dict[str, tuple[str, str]] = {}  # path → (content, priority)
        self._errors: list[str] = []

    def add_task(self, instruction: str, step: int = 0, total_steps: int = 0):
        if total_steps > 0:
            self._task = f"[Step {step}/{total_steps}] {instruction}"
        else:
            self._task = instruction

    def add_file(self, path: str, content: str, priority: str = "working"):
        """Add a file. priority: 'working' (kept) or 'reference' (evicted first)."""
        if path not in self._files:
            self._files[path] = (content, priority)

    def add_error(self, error: str):
        self._errors.append(error)

    def build(self) -> str:
        """Assemble context, fitting within max_chars budget."""
        sections: list[str] = []
        budget = self.max_chars

        # 1. Task context (always included)
        if self._task:
            task_section = f"## Task\n{self._task}"
            sections.append(task_section)
            budget -= len(task_section)

        # 2. Errors (high priority)
        if self._errors:
            error_section = "## Errors\n" + "\n---\n".join(self._errors)
            if len(error_section) <= budget:
                sections.append(error_section)
                budget -= len(error_section)

        # 3. Working set files (kept first)
        working_files = {p: c for p, (c, pri) in self._files.items() if pri == "working"}
        for path, content in working_files.items():
            file_section = f"## File: {path}\n```\n{content}\n```"
            if len(file_section) <= budget:
                sections.append(file_section)
                budget -= len(file_section)
            else:
                # Truncate content to fit
                avail = budget - len(f"## File: {path}\n```\n\n```\n[truncated]")
                if avail > 100:
                    sections.append(f"## File: {path}\n```\n{content[:avail]}\n```\n[truncated]")
                    budget = 0

        # 4. Reference set files (evicted first if over budget)
        ref_files = {p: c for p, (c, pri) in self._files.items() if pri == "reference"}
        for path, content in ref_files.items():
            file_section = f"## File: {path}\n```\n{content}\n```"
            if len(file_section) <= budget:
                sections.append(file_section)
                budget -= len(file_section)

        return "\n\n".join(sections) if sections else ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_context.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agent/context.py tests/test_context.py
git commit -m "feat: add deterministic context assembly pipeline"
```

---

## Task 10: Update AgentState for Typed Steps

**Files:**
- Modify: `agent/state.py`

- [ ] **Step 1: Update state to use PlanStep**

Update `agent/state.py` to change `plan` from `list[str]` to `list[dict]` (serialized PlanStep objects). This keeps backward compat with LangGraph's TypedDict while supporting typed steps.

```python
# agent/state.py
"""Agent state schema for LangGraph."""
from typing import Annotated, Optional, TypedDict
from langgraph.graph import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    instruction: str
    working_directory: str
    context: dict
    plan: list[dict]          # list of PlanStep.model_dump() dicts
    current_step: int
    file_buffer: dict[str, str]
    edit_history: list[dict]
    error_state: Optional[str]
    # Multi-agent coordination
    is_parallel: bool
    parallel_batches: list[list[int]]
    sequential_first: list[int]
    has_conflicts: bool
    # V2 additions
    model_usage: dict[str, int]  # model_id → token count
```

- [ ] **Step 2: Verify existing state tests still pass**

Run: `pytest tests/test_state.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add agent/state.py
git commit -m "feat: update AgentState for typed plan steps and model usage"
```

---

## Task 11: Update Planner Node for Typed Steps

**Files:**
- Modify: `agent/nodes/planner.py`
- Modify: `agent/prompts/planner.py`

- [ ] **Step 1: Update planner prompt to request PlanStep JSON**

Update `agent/prompts/planner.py` to instruct the LLM to output a JSON array of `PlanStep` objects with `id`, `kind`, `target_files`, `complexity`, `command`, and `depends_on` fields.

- [ ] **Step 2: Update planner node to use router and parse typed steps**

Update `agent/nodes/planner.py`:
- Import `ModelRouter` and `parse_plan_steps` from `agent.steps`
- Get router from `config["configurable"]["router"]`
- Call `router.call("plan", system, user)` instead of `call_llm(system, user)`
- Parse response with `parse_plan_steps()`
- Store `[step.model_dump() for step in steps]` in state `plan`

- [ ] **Step 3: Verify graph still compiles**

Run: `pytest tests/test_graph.py::test_graph_compiles -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add agent/nodes/planner.py agent/prompts/planner.py
git commit -m "feat: update planner to output typed PlanStep objects via router"
```

---

## Task 12: Update Graph Routing for Typed Steps

**Files:**
- Modify: `agent/graph.py`

- [ ] **Step 1: Update classify_step to use PlanStep.kind**

Replace the keyword-matching `classify_step` function in `agent/graph.py` with one that reads `plan[current_step]["kind"]` and routes to the appropriate node:
- `"exec"` or `"test"` → `"executor"`
- `"read"` → `"reader_only"`
- `"edit"` → `"reader_then_edit"`
- `"git"` → `"reporter"` (git_ops not yet implemented, skip for Phase 1)
- fallback → `"reader_then_edit"`

Keep the existing fallback to keyword matching for backward compat with any string-based steps.

- [ ] **Step 2: Run existing graph tests**

Run: `pytest tests/test_graph.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add agent/graph.py
git commit -m "feat: update graph routing to use typed PlanStep.kind"
```

---

## Task 13: Update Editor Node to Use Router

**Files:**
- Modify: `agent/nodes/editor.py`
- Modify: `agent/prompts/editor.py`

- [ ] **Step 1: Update editor to use router**

Update `agent/nodes/editor.py`:
- Get router from `config["configurable"]["router"]`
- Read current step's complexity from `state["plan"][state["current_step"]]`
- Call `router.call("edit_simple" or "edit_complex", system, user)` based on complexity
- Remove direct `call_llm` import

- [ ] **Step 2: Update editor prompt to remove token budget references**

Update `agent/prompts/editor.py` — remove any references to token budgets or truncation. The prompt should instruct the LLM to use full file context.

- [ ] **Step 3: Run editor tests**

Run: `pytest tests/test_editor_node.py -v`
Expected: PASS (tests mock the LLM call)

- [ ] **Step 4: Commit**

```bash
git add agent/nodes/editor.py agent/prompts/editor.py
git commit -m "feat: update editor node to use policy-based router"
```

---

## Task 14: Update Remaining Nodes to Use Router

**Files:**
- Modify: `agent/nodes/receive.py`
- Modify: `agent/nodes/reporter.py`
- Modify: `agent/nodes/validator.py`

- [ ] **Step 1: Update receive node**

Update `agent/nodes/receive.py` to initialize `model_usage: {}` in the state.

- [ ] **Step 2: Update reporter node**

Update `agent/nodes/reporter.py` to include `model_usage` from state in the summary output.

- [ ] **Step 3: Update validator for multi-layer checks**

Update `agent/nodes/validator.py`:
- After syntax check passes, attempt lint check if `lint_command` is available in context
- After lint passes, attempt typecheck if file is `.ts`/`.tsx` and `tsc` is available
- Log which validation layers ran in the trace

- [ ] **Step 4: Run all tests**

Run: `pytest tests/ -v --ignore=tests/test_integration.py`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add agent/nodes/receive.py agent/nodes/reporter.py agent/nodes/validator.py
git commit -m "feat: update remaining nodes for router + multi-layer validation"
```

---

## Task 15: Wire Store into Server

**Files:**
- Modify: `server/main.py`

- [ ] **Step 1: Update server to initialize store and router**

Update `server/main.py`:
- In the lifespan context manager, initialize `SQLiteSessionStore` and `ModelRouter`
- Pass them into graph invocations via `config={"configurable": {"store": store, "router": router}}`
- Add new endpoints:
  - `GET /projects` — list all projects
  - `POST /projects` — create a project
  - `GET /projects/{id}` — get project
- Update `POST /instruction` to create a Run in the store and update its status on completion

- [ ] **Step 2: Run server tests**

Run: `pytest tests/test_server.py -v`
Expected: PASS (existing tests still work)

- [ ] **Step 3: Commit**

```bash
git add server/main.py
git commit -m "feat: wire SQLite store and model router into FastAPI server"
```

---

## Task 16: Integration Smoke Test

**Files:**
- No new files — verify the full stack works

- [ ] **Step 1: Start the server**

Run: `OPENAI_API_KEY=your-key uvicorn server.main:app --port 8000`
Expected: Server starts, SQLite DB created

- [ ] **Step 2: Create a project**

Run: `curl -X POST http://localhost:8000/projects -H 'Content-Type: application/json' -d '{"name": "test", "path": "/tmp/test"}'`
Expected: Returns JSON with project ID

- [ ] **Step 3: Submit an instruction**

Run: `curl -X POST http://localhost:8000/instruction -H 'Content-Type: application/json' -d '{"instruction": "Read the file and summarize it", "working_directory": "/tmp/test"}'`
Expected: Returns `{"run_id": "...", "status": "running"}`

- [ ] **Step 4: Check that model routing works**

Verify in server logs or traces that OpenAI models are being called (not Anthropic).

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: Phase 1 complete — core migration to OpenAI with store and router"
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | Dependency migration | — |
| 2 | Model capability registry | 7 tests |
| 3 | OpenAI LLM wrapper | — |
| 4 | Policy-based router | 8 tests |
| 5 | Typed PlanStep schema | 7 tests |
| 6 | Store Pydantic models | — |
| 7 | SessionStore Protocol | — |
| 8 | SQLite store | 10 tests |
| 9 | Context assembly pipeline | 7 tests |
| 10 | Update AgentState | existing tests |
| 11 | Update planner node | existing tests |
| 12 | Update graph routing | existing tests |
| 13 | Update editor node | existing tests |
| 14 | Update remaining nodes | existing tests |
| 15 | Wire store into server | existing tests |
| 16 | Integration smoke test | manual |

**Total new tests: 39**
**Total tasks: 16**
**Estimated commits: 16**

---

## Addendum: Implementation Notes for Tasks 3, 11-15

This addendum provides the complete code that the prose-only tasks reference. The agentic worker MUST read this section alongside the tasks above.

### Deferred to Phase 2

The following spec items are intentionally NOT implemented in Phase 1:
- `test_runner` node (new)
- `parse_results` node (new)
- `git_ops` node (new)
- Parallel execution via LangGraph `Send` API
- Validation layers 3-5 (typecheck, targeted test, full build)
- WebSocket event bus
- Web frontend

### Task 3 Addendum: LLM Wrapper Test

Add this test file alongside the wrapper rewrite:

```python
# tests/test_llm.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_call_llm_forwards_params():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "test response"

    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("agent.llm._get_client", return_value=mock_client):
        from agent.llm import call_llm
        result = await call_llm(
            system="sys prompt",
            user="user prompt",
            model="gpt-4o",
            max_tokens=1000,
            timeout=30,
        )
        assert result == "test response"
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o"
        assert call_kwargs["max_tokens"] == 1000
```

Commit alongside Task 3: `git add agent/llm.py tests/test_llm.py`

### Task 10 Addendum: Update test_state.py

After updating `agent/state.py`, also update `tests/test_state.py` to include the new `model_usage` field in all state constructions:

```python
# Add to all AgentState constructions in test_state.py:
"model_usage": {},
```

### Task 11 Addendum: Complete Planner Code

**Updated `agent/prompts/planner.py`:**

```python
PLANNER_SYSTEM = """You are a coding task planner. Break the user's instruction into concrete, ordered steps.

Output a JSON array of step objects. Each step MUST have:
- "id": unique string identifier (e.g., "step-1", "step-2")
- "kind": one of "read", "edit", "exec", "test"
- "target_files": array of file paths this step touches (empty for exec/test)
- "complexity": "simple" (single file, localized change) or "complex" (multi-file, architecture changes)
- "depends_on": array of step IDs that must complete before this step (empty if none)
- "command": shell command string (only for exec/test steps, null otherwise)
- "acceptance_criteria": array of strings describing how to verify success

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

**Updated `agent/nodes/planner.py`:**

```python
# agent/nodes/planner.py
from agent.prompts.planner import PLANNER_SYSTEM, PLANNER_USER
from agent.steps import parse_plan_steps
from agent.tracing import TraceLogger
from agent.tools.file_ops import list_files

tracer = TraceLogger()


async def planner_node(state: dict, config: dict) -> dict:
    router = config["configurable"]["router"]
    instruction = state["instruction"]
    working_dir = state["working_directory"]
    context = state.get("context", {})

    # Build context section
    context_parts = []
    if context.get("spec"):
        context_parts.append(f"Spec:\n{context['spec']}")
    if context.get("schema"):
        context_parts.append(f"Schema:\n{context['schema']}")
    if context.get("files"):
        context_parts.append(f"Key files:\n{', '.join(context['files'])}")
    context_section = "\n\n".join(context_parts) if context_parts else "No additional context."

    # Get file listing
    file_listing = list_files(working_dir) if working_dir else ""

    user_prompt = PLANNER_USER.format(
        working_directory=working_dir,
        instruction=instruction,
        context_section=context_section,
        file_listing=f"Files in project:\n{file_listing}" if file_listing else "",
    )

    raw = await router.call("plan", PLANNER_SYSTEM, user_prompt)
    steps = parse_plan_steps(raw)

    tracer.log("planner", {"steps": len(steps), "instruction": instruction[:100]})

    return {
        "plan": [step.model_dump() for step in steps],
    }
```

### Task 12 Addendum: Complete classify_step Code

```python
# Replace classify_step in agent/graph.py
def classify_step(state: dict) -> str:
    """Route to the correct node based on PlanStep.kind."""
    plan = state.get("plan", [])
    idx = state.get("current_step", 0)

    if idx >= len(plan):
        return "reporter"

    step = plan[idx]

    # Typed step (dict with "kind" field)
    if isinstance(step, dict) and "kind" in step:
        kind = step["kind"]
        if kind in ("exec", "test"):
            return "executor"
        if kind == "read":
            return "reader_only"
        if kind == "edit":
            return "reader_then_edit"
        if kind == "git":
            return "reporter"  # git_ops deferred to Phase 2
        return "reader_then_edit"

    # Fallback: legacy string-based step (backward compat)
    if isinstance(step, str):
        step_lower = step.lower()
        if any(kw in step_lower for kw in ["run", "execute", "test", "build", "install"]):
            return "executor"
        if any(kw in step_lower for kw in ["read", "understand", "examine", "check"]):
            return "reader_only"

    return "reader_then_edit"
```

### Task 13 Addendum: Complete Editor Code + Updated Tests

**Updated `agent/nodes/editor.py`:**

```python
# agent/nodes/editor.py
import json
from agent.prompts.editor import EDITOR_SYSTEM, EDITOR_USER
from agent.tools.file_ops import read_file, edit_file
from agent.tracing import TraceLogger

tracer = TraceLogger()


async def editor_node(state: dict, config: dict) -> dict:
    router = config["configurable"]["router"]
    file_buffer = state.get("file_buffer", {})
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)

    if not file_buffer:
        return {"error_state": "No files in buffer to edit"}

    file_path = list(file_buffer.keys())[0]
    content = file_buffer[file_path]

    # Determine complexity from typed step
    complexity = "simple"
    if current_step < len(plan):
        step = plan[current_step]
        if isinstance(step, dict):
            complexity = step.get("complexity", "simple")

    task_type = "edit_complex" if complexity == "complex" else "edit_simple"

    # Number the lines for the LLM
    lines = content.split("\n")
    numbered = "\n".join(f"{i+1}: {line}" for i, line in enumerate(lines))

    # Build instruction from step
    step_text = ""
    if current_step < len(plan):
        step = plan[current_step]
        step_text = step if isinstance(step, str) else step.get("id", "edit")

    context = state.get("context", {})
    context_section = ""
    if context.get("spec"):
        context_section = f"Spec: {context['spec']}"

    user_prompt = EDITOR_USER.format(
        file_path=file_path,
        numbered_content=numbered,
        edit_instruction=step_text,
        context_section=context_section,
    )

    raw = await router.call(task_type, EDITOR_SYSTEM, user_prompt)

    # Parse JSON response
    try:
        data = json.loads(raw)
        anchor = data["anchor"]
        replacement = data["replacement"]
    except (json.JSONDecodeError, KeyError) as e:
        return {"error_state": f"Editor output parse error: {e}"}

    # Apply edit
    result = edit_file(file_path, anchor, replacement)
    if result.get("error"):
        tracer.log("editor", {"file": file_path, "error": result["error"]})
        return {
            "error_state": result["error"],
            "edit_history": state.get("edit_history", []) + [
                {"file": file_path, "error": result["error"]}
            ],
        }

    tracer.log("editor", {"file": file_path, "anchor": anchor[:50], "model": task_type})

    # Update file buffer with new content
    updated_content = read_file(file_path)
    return {
        "file_buffer": {**file_buffer, file_path: updated_content},
        "edit_history": state.get("edit_history", []) + [
            {"file": file_path, "old": anchor, "new": replacement, "snapshot": result.get("snapshot")}
        ],
        "error_state": None,
    }
```

**Updated `tests/test_editor_node.py` — mock router instead of call_llm:**

The key change is that tests must now provide a `config` dict with a mock router:

```python
# In test_editor_node.py, update the mock setup:
# OLD: @patch("agent.nodes.editor.call_llm", new_callable=AsyncMock)
# NEW:
from unittest.mock import AsyncMock, MagicMock

def make_config_with_mock_router(return_value):
    mock_router = MagicMock()
    mock_router.call = AsyncMock(return_value=return_value)
    return {"configurable": {"router": mock_router}}

# Then in each test, pass config:
# result = await editor_node(state, config=make_config_with_mock_router('{"anchor":"...","replacement":"..."}'))
```

### Task 14 Addendum: Complete Node Code

**Updated `agent/nodes/receive.py`:**

```python
# agent/nodes/receive.py
from agent.tracing import TraceLogger

tracer = TraceLogger()


def receive_instruction_node(state: dict) -> dict:
    tracer.log("receive", {"instruction": state.get("instruction", "")[:100]})
    return {
        "current_step": 0,
        "error_state": None,
        "model_usage": {},
    }
```

**Updated `agent/nodes/reporter.py` — add model_usage to summary:**

Add `"model_usage": state.get("model_usage", {})` to the summary dict in the reporter node.

### Task 15 Addendum: Complete Server Code + Updated Tests

**Updated `server/main.py` key changes:**

```python
# In lifespan:
from store.sqlite import SQLiteSessionStore
from agent.router import ModelRouter

@asynccontextmanager
async def lifespan(app: FastAPI):
    store = SQLiteSessionStore("shipyard.db")
    await store.initialize()
    router = ModelRouter()
    app.state.graph = build_graph()
    app.state.store = store
    app.state.router = router
    yield
    await store.close()

# In POST /instruction, pass config:
config = {"configurable": {"store": request.app.state.store, "router": request.app.state.router}}
result = await app.state.graph.ainvoke(initial_state, config=config)
```

**Updated `tests/test_server.py` — use tmp database:**

```python
# tests/test_server.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from server.main import app


@pytest_asyncio.fixture
async def client(tmp_path):
    """Use a temp SQLite database for tests."""
    db_path = str(tmp_path / "test.db")
    with patch("server.main.SQLiteSessionStore") as MockStore:
        mock_store = AsyncMock()
        MockStore.return_value = mock_store
        mock_store.initialize = AsyncMock()
        mock_store.close = AsyncMock()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

### pyproject.toml Addendum

Add `"store"` to the packages list:
```toml
[tool.hatch.build.targets.wheel]
packages = ["agent", "server", "store"]
```

### datetime.utcnow Fix

In `store/models.py`, replace all `datetime.utcnow` with:
```python
from datetime import datetime, timezone

# Use everywhere instead of datetime.utcnow():
datetime.now(timezone.utc)
```
