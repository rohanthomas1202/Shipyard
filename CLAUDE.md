<!-- GSD:project-start source:PROJECT.md -->
## Project

**Shipyard**

Shipyard is an autonomous AI coding agent that takes natural language instructions and plans, edits, validates, and commits code changes across multiple files without human intervention. Built as a Python/LangGraph agent with a FastAPI server and React frontend, it targets developers who want to automate multi-file code changes with surgical precision and full observability. This is a Gauntlet AI project — the agent must prove itself by rebuilding the Ship app from scratch.

**Core Value:** The agent must reliably complete real coding tasks end-to-end — from instruction to committed code — without producing broken edits, missing errors, or crashing mid-run.

### Constraints

- **LLM Provider:** OpenAI (o3/gpt-4o/gpt-4o-mini) — unlimited tokens available, no budget constraint
- **Deployment:** Heroku/Railway PaaS — single-process uvicorn, SQLite file DB, static frontend from web/dist/
- **Runtime:** Python 3.11 + Node.js — pinned in runtime.txt
- **Framework:** LangGraph 1.1.3 — committed, not switching
- **File editing:** Anchor-based string replacement — committed, not switching (per PDF: "switching strategies mid-week is a planning failure")
- **Observability:** LangSmith tracing required — env vars already configured
- **Demo target:** Ship app rebuild must work flawlessly for the demo video
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.11 - Backend agent, API server, data store (`agent/`, `server/`, `store/`)
- TypeScript ~5.9.3 - Frontend web application (`web/src/`)
- SQL (SQLite dialect) - Database schema defined inline in `store/sqlite.py`
## Runtime
- Python 3.11 (pinned in `runtime.txt`)
- Node.js (version not pinned; required for Vite dev server and frontend build)
- pip with `pyproject.toml` (hatchling build backend)
- Lockfile: `requirements.txt` (pinned subset, not a full lock)
- npm for frontend (`web/package-lock.json` present)
## Frameworks
- FastAPI >=0.115.0 - HTTP API server (`server/main.py`)
- LangGraph 1.1.3 - Agent orchestration graph (`agent/graph.py`)
- React 19.2.4 - Frontend UI (`web/src/`)
- Tailwind CSS 4.2.2 - Styling (`web/package.json`)
- pytest >=8.0 - Python test runner (dev dependency)
- pytest-asyncio >=0.24.0 - Async test support (dev dependency)
- pytest-httpx >=0.35.0 - HTTP mocking for httpx (dev dependency)
- Playwright >=1.58.2 - E2E browser tests (`web/package.json` devDependencies)
- Vite 8.0.1 - Frontend dev server and bundler (`web/vite.config.ts`)
- @vitejs/plugin-react 6.0.1 - React Fast Refresh in Vite
- @tailwindcss/vite 4.2.2 - Tailwind CSS Vite plugin
- Hatchling - Python build backend (`pyproject.toml`)
- ESLint 9.39.4 - Frontend linting with `eslint-plugin-react-hooks` and `eslint-plugin-react-refresh`
## Key Dependencies
- `openai` >=1.60.0 - OpenAI API client, used via `agent/llm.py`
- `langgraph` 1.1.3 - Stateful agent graph execution (`agent/graph.py`)
- `langchain-openai` >=0.3.0 - LangChain OpenAI integration (declared but direct usage is through `openai` SDK)
- `langchain-core` 1.2.21 - LangChain core abstractions
- `uvicorn` >=0.34.0 - ASGI server (`Procfile`: `uvicorn server.main:app`)
- `httpx` >=0.28.0 - Async HTTP client for GitHub API (`agent/github.py`)
- `aiosqlite` >=0.20.0 - Async SQLite driver (`store/sqlite.py`)
- `pyyaml` >=6.0 - YAML parsing (used in agent prompts/config)
- `pydantic` (transitive via FastAPI) - Data models (`store/models.py`, request/response models)
- `ast-grep-py` >=0.30.0 - AST-based structural search and replace (`agent/tools/ast_ops.py`)
- `pygls` >=2.0.0 - Language Server Protocol client (`agent/tools/lsp_client.py`)
- `lsprotocol` (transitive via pygls) - LSP type definitions
## Configuration
- `.env` file present at project root (contains secrets - not committed)
- `.env.example` documents required variables
- Key env vars: `OPENAI_API_KEY`, `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`
- `SHIPYARD_DB_PATH` - SQLite database path (defaults to `shipyard.db`) set in `server/main.py`
- `pyproject.toml` - Python project metadata and dependencies
- `web/vite.config.ts` - Vite configuration with API proxy to `localhost:8000`
- `web/tsconfig.json` - TypeScript config (references `tsconfig.app.json` and `tsconfig.node.json`)
- `Procfile` - Production startup: `uvicorn server.main:app --host 0.0.0.0 --port $PORT`
- Routes `/browse`, `/health`, `/projects`, `/instruction`, `/status`, `/runs` to `http://localhost:8000`
- WebSocket `/ws` proxied to `ws://localhost:8000`
## Platform Requirements
- Python 3.11+
- Node.js (for frontend dev and `typescript-language-server`)
- SQLite (bundled with Python)
- `typescript-language-server` binary on PATH (for LSP validation features)
- Single-process deployment via Procfile (`uvicorn`)
- Static frontend served from `web/dist/` by FastAPI (`server/main.py` lines 533-537)
- SQLite file-based database (`shipyard.db`)
- No containerization files detected (no Dockerfile, docker-compose)
## Model Configuration
- `o3` - Reasoning tier: planning, complex edits, conflict resolution (200k context, 120s timeout)
- `gpt-4o` - General tier: editing, reading, summarizing, merging (128k context, 60s timeout)
- `gpt-4o-mini` - Fast tier: classification, validation, syntax checks (128k context, 30s timeout)
- Tasks routed by type to model tiers with automatic escalation on failure
- e.g., `edit_simple` uses `general` tier, escalates to `reasoning` on error
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Use `snake_case.py` for all module files: `file_ops.py`, `lsp_manager.py`, `ast_ops.py`
- Node files named after their graph role: `editor.py`, `validator.py`, `planner.py`
- Test files use `test_` prefix: `test_editor_node.py`, `test_store.py`
- Use `snake_case` for all functions: `editor_node()`, `run_command_async()`, `parse_plan_steps()`
- Private/internal helpers prefixed with underscore: `_detect_language()`, `_syntax_check()`, `_rollback()`, `_get_client()`
- Async node entry points follow `{name}_node` convention: `editor_node()`, `validator_node()`, `planner_node()`, `reader_node()`
- Use `PascalCase`: `ModelRouter`, `TraceLogger`, `ApprovalManager`, `EventBus`, `TokenBatcher`
- Pydantic models: `PascalCase` nouns: `Project`, `Run`, `Event`, `EditRecord`, `PlanStep`, `ModelConfig`
- Custom exceptions: `PascalCase` with `Error` suffix: `InvalidTransitionError`
- Constants: `UPPER_SNAKE_CASE`: `ROUTING_POLICY`, `MODEL_REGISTRY`, `HEARTBEAT_INTERVAL`, `DB_PATH`
- Module-level singletons: lowercase: `tracer = TraceLogger()`, `logger = logging.getLogger(__name__)`
- Private module constants: prefixed underscore: `_TRANSITIONS`, `_P0_TYPES`, `_NO_PERSIST_TYPES`
- React components: `PascalCase.tsx`: `AgentPanel.tsx`, `StepTimeline.tsx`, `AppShell.tsx`
- Non-component modules: `camelCase.ts`: `api.ts`, `useHotkeys.ts`, `useWebSocket.ts`
- Type definition files: `index.ts` barrel in `types/` directory
- Functions: `camelCase`: `submitInstruction()`, `healthCheck()`, `getProjects()`
- React components: `PascalCase` named exports: `export function AgentPanel()`
- Hooks: `use` prefix: `useWebSocketContext()`, `useProjectContext()`, `useHotkeys()`
- Interfaces: `PascalCase` nouns: `Project`, `Run`, `WSEvent`, `Edit`, `RunStatus`
## Code Style
- No `.prettierrc` or formatting tool configured explicitly
- Python: 4-space indentation
- TypeScript/React: 2-space indentation
- Python line length: ~100 characters (not enforced by config)
- No trailing commas enforced in Python; optional in TypeScript
- Python: No `.flake8`, `ruff.toml`, or `pyproject.toml` linting section detected
- TypeScript: ESLint 9 with `eslint-plugin-react-hooks` and `eslint-plugin-react-refresh` in `web/package.json`
- Lint command: `npm run lint` in `web/`
## Import Organization
- Prefer `from X import Y` over `import X` for internal modules
- Some late/inline imports for optional dependencies: `from agent.tools.ast_ops import validate_anchor` inside try/except
- TYPE_CHECKING guard for circular imports: `if TYPE_CHECKING:` in `agent/approval.py`
- No TypeScript path aliases configured (relative paths used throughout)
## Type Usage
- Modern Python 3.11+ syntax used throughout: `str | None`, `dict[str, str]`, `list[str]`
- No `from __future__ import annotations` except in `agent/approval.py` and `agent/events.py`
- Function signatures fully typed in public APIs: `async def call_llm(system: str, user: str, model: str = "gpt-4o") -> str:`
- Internal helpers typed: `def _detect_language(file_path: str) -> str | None:`
- TypedDict for LangGraph state: `class AgentState(TypedDict)` in `agent/state.py`
- Pydantic models for persistence: `class Project(BaseModel)` in `store/models.py`
- Dataclasses for config: `@dataclass(frozen=True) class ModelConfig` in `agent/models.py`
- `Literal` types for constrained strings: `Literal["read", "edit", "exec", "test", "git", "refactor"]`
- Interfaces for all API types in `web/src/types/index.ts`
- Union literal types: `status: 'running' | 'completed' | 'failed' | 'error' | 'waiting_for_human'`
- Generic function typing: `async function request<T>(url: string, options?: RequestInit): Promise<T>`
- No `any` types in examined code (clean typing)
## Error Handling
## Logging
- Two approaches coexist:
- TraceLogger writes structured JSON to `traces/` directory (file-based, not stdout)
- Standard logger used for infrastructure (server, event bus); TraceLogger for agent node tracing
- Ad-hoc `logging.getLogger("shipyard.editor")` inline usage in `agent/nodes/editor.py` (inconsistent)
- Use `logging.getLogger(__name__)` for server/infrastructure code
- Use `TraceLogger.log(node_name, data_dict)` for agent graph node instrumentation
- TraceLogger entries are structured dicts with timestamp, run_id, node, and data
## Comments
- Required at top of every Python module: triple-quoted docstring explaining purpose
- Example from `agent/approval.py`:
- Used for section headers within long functions: `# --- ast-grep enhancement ---`
- Used for design decisions: `# File write happens BEFORE status transition`
- Comment separators in test files: `# ---------------------------------------------------------------------------`
- Used on public/complex functions: `"""Run a language-appropriate syntax check (synchronous)."""`
- Not used on simple/obvious helpers
## Function Design
- Signature: `async def {name}_node(state: dict, config: RunnableConfig) -> dict:`
- Accept graph state dict, return partial state update dict
- Access dependencies via `config["configurable"]` (dependency injection pattern)
- Never call LLM directly; always go through `router.call(task_type, system, user)`
- Signature: plain functions returning dict with `success`/`error` keys
- Synchronous by default; async variants have `_async` suffix: `run_command()` vs `run_command_async()`
- Located in `agent/tools/`
- Use Pydantic `BaseModel` for request/response schemas
- Access shared state via `app.state.{resource}`
- Background tasks via `asyncio.create_task()`
## Module Design
- No `__all__` declarations used
- No barrel `__init__.py` re-exports (init files are empty or minimal)
- Direct imports from specific modules: `from agent.nodes.editor import editor_node`
- LangGraph `config["configurable"]` dict carries runtime dependencies (router, store, approval_manager, lsp_manager)
- FastAPI `app.state` carries server-scoped singletons
- No DI framework; manual wiring in `server/main.py` lifespan
- Graph state is a flat TypedDict (`AgentState` in `agent/state.py`)
- Nodes return partial dicts that get merged into state
- No nested state objects; everything is top-level keys
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- LangGraph `StateGraph` orchestrates an AI coding agent through plan-read-edit-validate cycles
- FastAPI server exposes REST endpoints and WebSocket for real-time event streaming
- SQLite persistence layer with a Protocol-based interface for swappable backends
- Human-in-the-loop approval gates for edit review (supervised mode)
- OpenAI GPT models with tiered routing (reasoning/general/fast) and auto-escalation
- AST-aware code editing via ast-grep-py with LSP diagnostic validation
## Layers
- Purpose: React SPA providing IDE-like UI for interacting with the agent
- Location: `web/src/`
- Contains: React components, context providers, hooks, API client
- Depends on: FastAPI server (REST + WebSocket)
- Used by: End users via browser
- Purpose: HTTP REST endpoints and WebSocket gateway for the frontend
- Location: `server/main.py`, `server/websocket.py`
- Contains: FastAPI routes, WebSocket connection manager, request/response models
- Depends on: Agent graph, Store, EventBus, ApprovalManager
- Used by: Web frontend
- Purpose: LangGraph state machine that plans, reads, edits, validates, and commits code
- Location: `agent/graph.py`, `agent/state.py`, `agent/router.py`
- Contains: Graph definition, state schema, model routing policy
- Depends on: Agent nodes, LLM client, tools
- Used by: Server layer (invoked via `graph.ainvoke()`)
- Purpose: Individual graph nodes implementing each step of the agent workflow
- Location: `agent/nodes/`
- Contains: 10 node functions: receive, planner, coordinator, reader, editor, executor, validator, merger, reporter, git_ops, refactor
- Depends on: Tools, prompts, router, approval manager
- Used by: Agent graph
- Purpose: Low-level operations for file I/O, shell execution, AST operations, LSP communication
- Location: `agent/tools/`
- Contains: `file_ops.py`, `shell.py`, `ast_ops.py`, `lsp_client.py`, `lsp_manager.py`, `search.py`
- Depends on: External binaries (git, esbuild, typescript-language-server), ast-grep-py, pygls
- Used by: Agent nodes
- Purpose: Data persistence for projects, runs, events, edits, git operations
- Location: `store/`
- Contains: Protocol interface, Pydantic models, SQLite implementation
- Depends on: aiosqlite
- Used by: Server, agent nodes, approval manager, event bus
- Purpose: Approval workflow, event streaming, LLM client, tracing
- Location: `agent/approval.py`, `agent/events.py`, `agent/llm.py`, `agent/tracing.py`
- Contains: ApprovalManager state machine, EventBus with priority routing, OpenAI wrapper, JSON trace logger
- Depends on: Store
- Used by: All layers
## Data Flow
- **Agent State:** `AgentState` TypedDict flows through LangGraph nodes. Each node returns a partial dict merged into state. Key fields: `plan`, `current_step`, `file_buffer`, `edit_history`, `error_state`
- **Run State (Server):** In-memory `runs` dict maps `run_id` to `{status, result}`. The `result` is the full `AgentState` dict after graph execution, enabling run resumption
- **Persistent State:** SQLite stores projects, runs, events (with seq ordering), edits (with status state machine), conversations, git operations
- **Frontend State:** React Context providers for project selection (`ProjectContext`) and WebSocket connection (`WebSocketContext`). Event distribution via type-based pub/sub pattern
## Key Abstractions
- Purpose: Structured representation of each step the agent will execute
- Definition: `agent/steps.py` - `PlanStep` Pydantic model
- Fields: `id`, `kind` (read/edit/exec/test/git/refactor), `target_files`, `command`, `acceptance_criteria`, `complexity`, `depends_on`, `pattern`, `refactor_replacement`, `language`, `scope`
- Pattern: LLM outputs JSON array of PlanStep objects, parsed by `parse_plan_steps()` with fallback
- Purpose: Tracks a single code edit through its lifecycle
- Definition: `store/models.py` - `EditRecord` Pydantic model
- States: proposed -> approved -> applied -> committed (or proposed -> rejected)
- Pattern: State machine managed by `ApprovalManager` in `agent/approval.py`
- Purpose: Routes LLM calls to appropriate model tier based on task type
- Definition: `agent/router.py` - `ModelRouter` class
- Pattern: `ROUTING_POLICY` maps task types (plan, edit_simple, validate, etc.) to tiers (reasoning, general, fast). Auto-escalation on failure
- Models: o3 (reasoning), gpt-4o (general), gpt-4o-mini (fast)
- Purpose: Central event dispatch with priority-based routing and batching
- Definition: `agent/events.py` - `EventBus` class
- Pattern: Events classified as P0 (immediate), P1 (batched at 50ms), P2 (node boundary flush). Sequence numbers per run for replay ordering
- Purpose: Abstract interface for data persistence, enabling backend swaps
- Definition: `store/protocol.py` - `SessionStore` Protocol class
- Implementation: `store/sqlite.py` - `SQLiteSessionStore`
- Pattern: Python Protocol (structural typing) with async methods
- Purpose: Manages LSP server processes for semantic validation
- Definition: `agent/tools/lsp_manager.py` - `LspManager` class
- Pattern: Async context manager, injected into graph run config. Two-layer client: `LspConnection` (transport) + `LspDiagnosticClient` (high-level diagnostics with timeout/retry)
## Entry Points
- Location: `server/main.py`
- Triggers: `uvicorn server.main:app` (see `Procfile`)
- Responsibilities: Initializes SQLite store, EventBus, ConnectionManager, ApprovalManager, builds LangGraph. Serves REST API and WebSocket. In production, mounts React static files from `web/dist/`
- Location: `web/src/main.tsx`
- Triggers: Vite dev server or static build
- Responsibilities: Renders App component with ErrorBoundary, WebSocketProvider, ProjectProvider, AppShell
## Error Handling
- **Graph-level retry:** `should_continue()` in `agent/graph.py` checks `error_state` and retries up to 3 times (returns to reader node), then routes to reporter
- **Edit rollback:** `validator_node` rolls back files from snapshots stored in `edit_history` when syntax/LSP checks fail
- **Refactor rollback:** `refactor_node` captures pre-edit snapshots and rolls back all files on exception
- **LLM escalation:** `ModelRouter.call()` catches exceptions and escalates to higher-tier model if configured
- **Git stash/unstash:** `GitManager.ensure_branch()` stashes dirty working tree before branch creation
- **LSP degraded mode:** Validator falls back to subprocess syntax checks when LSP is unavailable or times out
- **Approval idempotency:** `last_op_id` field on EditRecord prevents duplicate approvals
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
