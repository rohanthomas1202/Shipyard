# Technology Stack: Hardening Recommendations

**Project:** Shipyard (Autonomous AI Coding Agent)
**Researched:** 2026-03-26
**Focus:** Production reliability hardening for existing stack

## Current Stack (Keep As-Is)

These are committed decisions. No changes recommended -- they are solid choices.

| Technology | Current | Purpose | Verdict |
|------------|---------|---------|---------|
| LangGraph | 1.1.3 | Agent orchestration | Keep. Latest is 1.1.0 (Mar 2026) -- you're actually ahead or on a patch release. Stable, production-proven with 300+ enterprise customers via LangSmith. |
| FastAPI | >=0.115.0 | HTTP/WS server | Keep. Pin to >=0.130.0 for SSE streaming support and recent bug fixes. Latest is 0.135.2. |
| React 19 | 19.2.4 | Frontend | Keep. No frontend changes needed for backend hardening. |
| OpenAI SDK | >=1.60.0 | LLM calls | **Upgrade -- see below.** |
| aiosqlite | >=0.20.0 | Async SQLite | Keep, but add WAL mode configuration. |
| pygls | >=2.0.0 | LSP client | Keep. Stable for TypeScript diagnostic diffing. |
| ast-grep-py | >=0.30.0 | Structural rewrites | Keep. Niche but solid for refactor node. |
| LangChain Core | 1.2.21 | LangChain abstractions | Keep pinned. Transitive dependency of LangGraph. |

## Upgrades to Existing Dependencies

### OpenAI Python SDK: Upgrade to >=1.80.0
**Confidence:** HIGH (PyPI verified)

Current pin `>=1.60.0` is dangerously loose. Latest is 2.30.0 (Mar 25, 2026), but the 2.x line introduced the Responses API which replaces Chat Completions patterns. Since you use the Chat Completions API throughout `agent/llm.py`, stay on the 1.x line for now.

**Action:** Pin `openai>=1.80.0,<2.0.0` to get structured output improvements and bug fixes while avoiding the Responses API migration. The 2.x migration to Responses API (`text.format` replacing `response_format`) is a future milestone, not a hardening task.

**Why 1.80.0 floor:** Structured output Pydantic integration matured around 1.70-1.80, including `response_format` with `strict: true` for guaranteed schema compliance. This is critical for reliable plan/edit output parsing.

### FastAPI: Pin floor to >=0.130.0
**Confidence:** MEDIUM (WebSearch verified, not Context7)

Recent versions added Server-Sent Events support and streaming JSON Lines, which could improve WebSocket reliability. More importantly, bug fixes in the 0.120-0.135 range addressed WebSocket lifecycle issues relevant to your reconnect/replay system.

## New Dependencies to Add

### 1. tenacity >=9.1.0 -- Retry with Backoff
**Confidence:** HIGH (PyPI verified, latest 9.1.4 released Feb 2026)
**Why:** Your agent makes LLM calls, file I/O, LSP calls, and git operations -- all flaky. Tenacity provides decorator-based retry with exponential backoff, jitter, and per-exception retry policies. It is THE standard Python retry library (8k+ GitHub stars, actively maintained).

**Use for:**
- LLM API calls (rate limits, transient 500s): `@retry(wait=wait_exponential(multiplier=1, max=30), stop=stop_after_attempt(3), retry=retry_if_exception_type(openai.RateLimitError))`
- LSP server communication (process crashes): retry with shorter backoff
- Git operations (lock contention): retry with fixed wait

**Why not build your own:** You already have ad-hoc retry logic scattered across nodes. Tenacity standardizes it with composable wait/stop/retry strategies and proper jitter to prevent thundering herd.

```bash
pip install "tenacity>=9.1.0"
```

### 2. structlog >=25.1.0 -- Structured Logging
**Confidence:** HIGH (PyPI verified, latest 25.5.0)
**Why:** Agent runs are multi-step, async, and span multiple nodes. Python's stdlib `logging` produces unstructured text that is nearly impossible to debug in production. structlog produces JSON logs with bound context (run_id, node_name, step_index) that flow through the entire call chain.

**Use for:**
- Bind `run_id` and `node_name` at the start of each graph node execution
- Async-safe logging via `await logger.ainfo()` methods
- JSON output in production, pretty-printed in development
- Correlating LangSmith traces with application logs

**Why structlog over loguru:** structlog integrates with stdlib logging (FastAPI/uvicorn already use it), supports async natively, and produces machine-parseable JSON. Loguru is prettier but fights the stdlib integration.

```bash
pip install "structlog>=25.1.0"
```

### 3. langgraph-checkpoint-sqlite >=3.0.0 -- Graph Checkpointing
**Confidence:** HIGH (PyPI verified, latest 3.0.3, Jan 2026)
**Why:** Your agent has no checkpoint persistence between process restarts. If uvicorn crashes mid-run, the entire run is lost. LangGraph's checkpoint system saves graph state after every node execution, enabling:
- Resume after crash (process restart picks up from last completed node)
- Time-travel debugging (replay from any previous state)
- Human-in-the-loop resume (approval gates survive server restarts)

You already use SQLite via aiosqlite, so this is a natural fit. The async `AsyncSqliteSaver` is fine for your single-user, single-process deployment (the "not for production" warning is about high-concurrency multi-writer scenarios, not your use case).

```bash
pip install "langgraph-checkpoint-sqlite>=3.0.0"
```

### 4. pytest-timeout >=2.3.0 -- Test Timeout Guards
**Confidence:** HIGH (PyPI verified)
**Why:** Agent tests involve LLM calls, LSP server startup, and async graph execution. Without timeouts, a hanging test blocks CI forever. pytest-timeout terminates tests that exceed their time limit and prints a stack dump for debugging.

**Use for:**
- Unit tests: 10s timeout (no external calls if properly mocked)
- Integration tests: 60s timeout (LSP startup, real file I/O)
- E2E tests: 120s timeout (full graph execution)

```bash
pip install "pytest-timeout>=2.3.0"
```

## Libraries Evaluated and Rejected

| Library | Category | Why Not |
|---------|----------|---------|
| **PydanticAI** | Agent framework | You already have LangGraph. PydanticAI is a competing agent framework, not a complementary library. Use Pydantic models directly with OpenAI structured outputs instead. |
| **aiobreaker / pybreaker** | Circuit breaker | Overkill for single-user agent. Circuit breakers protect services from cascading failures across many callers. Your agent is the only caller. Tenacity retry with `stop_after_attempt` achieves the same effect simpler. |
| **loguru** | Logging | Fights stdlib logging integration. FastAPI/uvicorn use stdlib. structlog bridges both worlds. |
| **langgraph-checkpoint-postgres** | Checkpointing | You deploy single-process with SQLite. Adding Postgres for checkpointing alone is unnecessary infrastructure complexity. |
| **Sentry SDK** | Error tracking | Useful at scale, but for a single-user demo-target agent, structlog + LangSmith provides sufficient observability. Add Sentry only if deploying to Railway/Heroku for multi-day uptime. |
| **OpenAI Agents SDK** | Agent framework | Competing framework. You're committed to LangGraph. |
| **Responses API migration** | API pattern | The new `text.format` replacing `response_format` is a 2.x SDK change. Not a hardening task -- it's a migration that introduces risk. Defer until post-demo. |

## Configuration Changes (No New Dependencies)

### SQLite WAL Mode
**Confidence:** HIGH (SQLite official docs)
**Why:** WAL (Write-Ahead Logging) mode allows concurrent reads during writes, which matters when WebSocket handlers read run status while the agent writes events. Without WAL, readers block on writers and vice versa, causing the "hanging status updates" symptom.

**Implementation:** Add `PRAGMA journal_mode=WAL;` immediately after opening each database connection in `store/sqlite.py`. Also add `PRAGMA busy_timeout=5000;` to wait 5 seconds on lock contention instead of failing immediately.

### OpenAI Structured Outputs
**Confidence:** HIGH (OpenAI official docs)
**Why:** Your planner and editor nodes parse LLM output into typed structures. Using `response_format={"type": "json_schema", "json_schema": {...}, "strict": True}` guarantees the LLM output matches your schema, eliminating parse failures. This is available in the 1.x SDK with `openai>=1.60.0` but requires explicit opt-in per call.

**Implementation:** Define Pydantic models for PlanStep, EditInstruction, and ValidationResult. Pass their JSON schemas as `response_format` with `strict: True`. The SDK will auto-deserialize.

### LangSmith Trace Annotations
**Confidence:** HIGH (LangSmith docs)
**Why:** You already have `LANGCHAIN_TRACING_V2=true` configured. But raw traces without annotations are hard to navigate. Adding `run_name`, `tags`, and `metadata` to each node execution makes traces filterable and debuggable.

**Implementation:** Use `langsmith.trace()` context manager or LangGraph's built-in `config={"run_name": "editor_node", "tags": ["edit", run_id]}` on each node invocation.

## Recommended pyproject.toml Dependencies Section

```toml
[project]
dependencies = [
    # Agent orchestration (pinned -- committed architecture)
    "langgraph==1.1.3",
    "langchain-openai>=0.3.0",
    "langchain-core==1.2.21",

    # LLM provider (pin below 2.0 to avoid Responses API migration)
    "openai>=1.80.0,<2.0.0",

    # Server
    "fastapi>=0.130.0",
    "uvicorn>=0.34.0",
    "httpx>=0.28.0",

    # Persistence
    "aiosqlite>=0.20.0",
    "langgraph-checkpoint-sqlite>=3.0.0",

    # Code intelligence
    "ast-grep-py>=0.30.0",
    "pygls>=2.0.0",

    # Reliability
    "tenacity>=9.1.0",
    "structlog>=25.1.0",

    # Config
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24.0",
    "pytest-httpx>=0.35.0",
    "pytest-timeout>=2.3.0",
]
```

## Installation

```bash
# From project root
pip install -e ".[dev]"
```

## Stack Hardening Priority Order

This is the order in which these changes deliver reliability value:

1. **SQLite WAL mode + busy_timeout** -- Zero new dependencies, immediate concurrency improvement
2. **tenacity for LLM retry** -- Eliminates the most common runtime failure (transient API errors)
3. **OpenAI structured outputs** -- Eliminates parse failures in planner/editor output
4. **structlog** -- Makes debugging possible when things still go wrong
5. **langgraph-checkpoint-sqlite** -- Enables crash recovery and run resumption
6. **pytest-timeout** -- Prevents CI from hanging, enforces test discipline

## Confidence Assessment

| Recommendation | Confidence | Basis |
|---------------|------------|-------|
| Keep LangGraph 1.1.3 | HIGH | PyPI version verified, stable GA release |
| OpenAI SDK <2.0.0 pin | HIGH | Responses API migration confirmed as breaking change |
| tenacity | HIGH | PyPI verified (9.1.4), de facto standard |
| structlog | HIGH | PyPI verified (25.5.0), async support confirmed |
| langgraph-checkpoint-sqlite | HIGH | PyPI verified (3.0.3), official LangGraph package |
| SQLite WAL mode | HIGH | SQLite official documentation |
| Structured outputs via strict mode | HIGH | OpenAI official documentation |
| FastAPI >=0.130.0 | MEDIUM | Version improvements inferred from release notes, not individually verified |
| pytest-timeout | HIGH | PyPI verified, standard pytest plugin |

## Sources

- [LangGraph PyPI](https://pypi.org/project/langgraph/)
- [LangGraph Checkpoint SQLite PyPI](https://pypi.org/project/langgraph-checkpoint-sqlite/)
- [OpenAI Python SDK PyPI](https://pypi.org/project/openai/)
- [OpenAI Structured Outputs docs](https://platform.openai.com/docs/guides/structured-outputs)
- [OpenAI Responses API Migration Guide](https://platform.openai.com/docs/guides/migrate-to-responses)
- [Tenacity PyPI](https://pypi.org/project/tenacity/)
- [structlog docs](https://www.structlog.org/en/stable/)
- [FastAPI PyPI](https://pypi.org/project/fastapi/)
- [SQLite WAL Mode docs](https://www.sqlite.org/wal.html)
- [LangSmith Observability](https://www.langchain.com/langsmith/observability)
- [LangGraph Production Best Practices](https://blogs.versalence.ai/production-ai-agents-langgraph-complete-guide-2025)
- [Agent Error Handling Patterns](https://sparkco.ai/blog/advanced-error-handling-strategies-in-langgraph-applications)
- [pytest-timeout PyPI](https://pypi.org/project/pytest-timeout/)
