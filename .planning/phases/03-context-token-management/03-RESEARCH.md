# Phase 3: Context & Token Management - Research

**Researched:** 2026-03-26
**Domain:** LLM prompt construction, token budgeting, usage tracking
**Confidence:** HIGH

## Summary

Phase 3 wires the existing `ContextAssembler` (agent/context.py) into all five LLM-calling nodes, adds line-range reads for large files, and implements per-run token usage tracking with cost estimation. The codebase is well-structured for this work: ContextAssembler already has ranked priority filling with budget tracking, every node follows the same `(state, config) -> dict` signature, and the OpenAI SDK returns usage stats on every response that are currently discarded.

The main integration challenge is that each node builds prompts differently (planner uses `.format()` templates, editor has complex error feedback assembly, reader does no LLM call). The ContextAssembler needs minor enhancements (system prompt awareness, line-range file content) but the core algorithm is sound. Token tracking requires changes in two places: `call_llm()` / `call_llm_structured()` must return usage alongside content, and the router must aggregate these per run via the state dict.

**Primary recommendation:** Modify `call_llm` and `call_llm_structured` to return `(content, usage_dict)` tuples, have the router accumulate usage into a `TokenTracker` dataclass, and refactor each node to build prompts via ContextAssembler while preserving their existing prompt templates as the system/user content sources.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CTX-01 | ContextAssembler wired into all LLM-calling nodes with token-budgeted prompt construction using ranked priorities | ContextAssembler exists at agent/context.py with working priority system. Nodes identified: planner, editor, validator (via router), refactor (no direct LLM call). Integration patterns documented below. |
| CTX-02 | Reader supports line-range reads for files >200 lines, loading only relevant sections | reader_node currently loads full files via `open().read()`. PlanStep already has `target_files` -- needs line range hints. ContextAssembler truncation provides a safety net. |
| LIFE-02 | Each LLM call tracks token usage (input/output) and aggregates cost per run, surfaced in traces and UI | `call_llm()` and `call_llm_structured()` receive full OpenAI response objects with `.usage.prompt_tokens` and `.usage.completion_tokens` but discard them. AgentState already has `model_usage: dict[str, int]` field. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **LLM Provider:** OpenAI (o3/gpt-4o/gpt-4o-mini) -- unlimited tokens, no budget constraint
- **Framework:** LangGraph 1.1.3 -- committed, not switching
- **File editing:** Anchor-based string replacement -- committed
- **Observability:** LangSmith tracing required
- **Runtime:** Python 3.11
- **Nodes access LLM via router only** -- never call LLM directly
- **Node signature:** `async def {name}_node(state: dict, config: RunnableConfig) -> dict:`
- **Flat state:** AgentState is a flat TypedDict, nodes return partial dicts merged into state
- **Two logging systems:** TraceLogger for agent nodes, stdlib logging for infrastructure
- **No Co-Authored-By lines in commits** (per user memory)

## Standard Stack

### Core (Already in Project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| openai | >=1.60.0 | LLM API client -- response.usage already available | Project dependency |
| langgraph | 1.1.3 | Agent graph orchestration | Project framework |
| pydantic | (via FastAPI) | Data models for TokenTracker | Already used for schemas |

### No New Dependencies Required

This phase requires zero new packages. Everything needed is already in the project:
- `ContextAssembler` exists at `agent/context.py`
- OpenAI SDK already returns usage stats
- `TraceLogger` already handles structured JSON traces
- `EventBus` already handles WebSocket event streaming
- `AgentState` already has `model_usage: dict[str, int]` field

## Architecture Patterns

### Current Prompt Construction (What Exists)

Each LLM-calling node builds prompts via string concatenation/formatting:

```
planner_node:  PLANNER_USER.format(instruction=..., context_section=..., file_listing=...)
editor_node:   EDITOR_USER.format(file_path=..., numbered_content=..., edit_instruction=..., ...)
validator_node: No direct LLM call (uses subprocess/LSP)
refactor_node:  No direct LLM call (uses ast-grep)
reader_node:    No LLM call (file I/O only)
```

Only **planner_node** and **editor_node** make LLM calls. The router (`ModelRouter.call()` and `.call_structured()`) is the single LLM gateway.

### Target Architecture

```
Node                    ContextAssembler                Router
  |                           |                           |
  |-- add_task(instruction) ->|                           |
  |-- add_file(path, content, priority) ->|               |
  |-- add_error(error) ------>|                           |
  |                           |                           |
  |<-- build() = user_prompt -|                           |
  |                                                       |
  |-- router.call(type, system, user_prompt) ------------>|
  |                                                       |
  |<-- (content, usage) ---------------------------------|
  |                                                       |
  |-- return {state_updates, token_usage} -->             |
```

### Pattern 1: ContextAssembler Integration in Nodes

**What:** Each LLM-calling node creates a ContextAssembler, populates it with task-specific content at appropriate priorities, and uses `.build()` as the user prompt.

**When to use:** Every node that calls `router.call()` or `router.call_structured()`.

**Example (editor_node):**
```python
from agent.context import ContextAssembler
from agent.models import MODEL_REGISTRY

# Resolve token budget from the model that will be used
model_config = router.resolve_model(task_type)
assembler = ContextAssembler(max_tokens=model_config.context_window)

# Priority 1: Task instruction
assembler.add_task(step_text, step=current_step, total_steps=len(plan))

# Priority 2: Working set (current file being edited)
assembler.add_file(file_path, numbered_content, priority="working")

# Priority 3: Error feedback (if retrying)
if error_feedback:
    assembler.add_error(error_feedback)

# Priority 4: Reference files (context spec, etc.)
if context.get("spec"):
    assembler.add_file("spec", context["spec"], priority="reference")

user_prompt = assembler.build()
```

### Pattern 2: Token Usage Return from LLM Calls

**What:** `call_llm()` and `call_llm_structured()` return usage alongside content. Router aggregates.

**Example:**
```python
# In agent/llm.py
from dataclasses import dataclass

@dataclass
class LLMResult:
    content: str
    usage: dict  # {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N}
    model: str

async def call_llm(...) -> LLMResult:
    response = await client.chat.completions.create(...)
    usage = {}
    if response.usage:
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }
    return LLMResult(
        content=response.choices[0].message.content or "",
        usage=usage,
        model=model,
    )
```

### Pattern 3: Per-Run Token Aggregation

**What:** A `TokenTracker` accumulates usage across all LLM calls in a run, stored in AgentState.

**Example:**
```python
# In agent/token_tracker.py
from dataclasses import dataclass, field

# Pricing per 1M tokens (input, output) -- March 2026
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "o3":          (2.00, 8.00),
    "gpt-4o":      (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}

@dataclass
class TokenTracker:
    calls: list[dict] = field(default_factory=list)

    def record(self, model: str, usage: dict):
        self.calls.append({"model": model, **usage})

    def totals(self) -> dict:
        prompt = sum(c.get("prompt_tokens", 0) for c in self.calls)
        completion = sum(c.get("completion_tokens", 0) for c in self.calls)
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
            "call_count": len(self.calls),
        }

    def estimated_cost(self) -> float:
        total = 0.0
        for call in self.calls:
            model = call.get("model", "gpt-4o")
            input_price, output_price = MODEL_PRICING.get(model, (2.50, 10.00))
            total += (call.get("prompt_tokens", 0) / 1_000_000) * input_price
            total += (call.get("completion_tokens", 0) / 1_000_000) * output_price
        return total
```

### Pattern 4: Line-Range File Reading

**What:** For files over 200 lines, load only relevant sections rather than the entire file.

**Approach:** The reader_node detects file size. If >200 lines, it stores a summary (first 20 lines + last 10 lines as a "skeleton") in the file_buffer. The editor_node can then request specific line ranges when it needs to edit. ContextAssembler already truncates over-budget files, providing a safety net.

```python
# In reader_node
def _read_with_range(file_path: str, start: int = None, end: int = None) -> str:
    with open(file_path, "r") as f:
        lines = f.readlines()

    if start is not None or end is not None:
        start = start or 0
        end = end or len(lines)
        selected = lines[start:end]
        prefix = f"[Lines {start+1}-{min(end, len(lines))} of {len(lines)}]\n"
        return prefix + "".join(selected)

    if len(lines) > 200:
        # Load skeleton: first 30 lines + last 10 lines
        skeleton = lines[:30] + [f"\n... ({len(lines) - 40} lines omitted) ...\n\n"] + lines[-10:]
        return f"[{len(lines)} lines total -- skeleton view]\n" + "".join(skeleton)

    return "".join(lines)
```

### Recommended File Changes

```
agent/
  context.py          # Minor enhancements to ContextAssembler
  llm.py              # Return LLMResult with usage stats
  token_tracker.py    # NEW: TokenTracker + MODEL_PRICING
  router.py           # Pass through usage from LLM calls
  state.py            # Add token_usage field to AgentState
  tracing.py          # Add token summary to trace entries
  nodes/
    planner.py        # Wire ContextAssembler, capture usage
    editor.py         # Wire ContextAssembler, capture usage
    reader.py         # Add line-range reading for large files
    reporter.py       # Emit final token summary event
```

### Anti-Patterns to Avoid

- **Don't refactor prompt templates:** Keep EDITOR_SYSTEM, PLANNER_SYSTEM, etc. as-is. ContextAssembler builds the *user* prompt, not the system prompt. System prompts are static and small.
- **Don't add ContextAssembler to nodes that don't call LLM:** reader_node, validator_node, refactor_node, and executor_node don't make LLM calls -- don't force ContextAssembler into them.
- **Don't break the router's return type silently:** The change from `str` to `LLMResult` must propagate to all callers in one pass, or use a backward-compatible approach (e.g., attach usage to the router instance).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token counting | Custom tokenizer | CHARS_PER_TOKEN=4 heuristic (already in context.py) | tiktoken adds a dependency for marginal accuracy gain; the 4 chars/token heuristic is standard for budget estimation |
| Usage tracking | Custom event aggregation | OpenAI response.usage field | Already computed server-side with exact counts |
| Cost estimation | API calls to OpenAI billing | Static MODEL_PRICING dict | Pricing changes rarely; a dict is simpler and offline |
| Prompt templating | Jinja2 or custom template engine | f-string + ContextAssembler.build() | Project already uses f-strings; adding a template engine is overengineering |

## Common Pitfalls

### Pitfall 1: Breaking Router Return Type

**What goes wrong:** Changing `call_llm()` from returning `str` to returning `LLMResult` breaks every caller that expects a string.
**Why it happens:** 5+ call sites (router.call, router.call_structured, direct test mocks).
**How to avoid:** Either (a) update all callers in one atomic change, or (b) have the router unwrap the LLMResult and accumulate usage internally, keeping the `str` return type for `router.call()`. Option (b) is safer.
**Warning signs:** Tests that mock `call_llm` will fail if the signature changes.

### Pitfall 2: Double-Counting Tokens on Escalation

**What goes wrong:** When ModelRouter escalates (first call fails, second succeeds), both calls' tokens should be counted.
**Why it happens:** The escalation try/except might skip recording the failed call's usage.
**How to avoid:** Record usage in a `finally` block or record before raising.
**Warning signs:** Token counts seem low for runs with escalation events.

### Pitfall 3: ContextAssembler Budget Mismatch

**What goes wrong:** ContextAssembler uses a token budget, but the actual model's context window varies (o3=200k, gpt-4o=128k). If budget is hardcoded, some nodes waste context or overflow.
**Why it happens:** The current default is `max_tokens=128_000` but planner uses o3 (200k).
**How to avoid:** Resolve the model via `router.resolve_model(task_type)` and pass `model_config.context_window` to ContextAssembler. Reserve headroom for output tokens (subtract `model_config.max_output`).
**Warning signs:** Prompts that should fit the context window getting truncated unnecessarily.

### Pitfall 4: Line-Range Reads Losing Edit Context

**What goes wrong:** If the reader loads only lines 50-80, the editor can't produce a valid anchor because it doesn't see surrounding code.
**Why it happens:** The relevant section might be adjacent to but not overlapping with the loaded range.
**How to avoid:** Use generous padding (+/- 20 lines around the target area). For edit steps, err on the side of loading more. The ContextAssembler truncation is the safety net, not the reader's line-range logic.
**Warning signs:** Anchor matching failures increase after enabling line-range reads.

### Pitfall 5: Forgetting Structured Output Usage

**What goes wrong:** `call_llm_structured()` uses `.parse()` which returns a `ParsedChatCompletion` -- the usage field is still on the response object, but you might extract only `.choices[0].message.parsed` and lose usage.
**Why it happens:** Current code: `return response.choices[0].message.parsed` discards the response object.
**How to avoid:** Capture `response.usage` before returning the parsed model.
**Warning signs:** Token counts missing for all structured output calls (editor simple edits, etc.).

## Code Examples

### Example 1: Modified call_llm with Usage

```python
# agent/llm.py
from dataclasses import dataclass

@dataclass
class LLMResult:
    content: str
    usage: dict
    model: str

@dataclass
class LLMStructuredResult:
    parsed: BaseModel
    usage: dict
    model: str

async def call_llm(
    system: str,
    user: str,
    model: str = "gpt-4o",
    max_tokens: int = 16_384,
    timeout: int = 60,
) -> LLMResult:
    client = _get_client()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_completion_tokens=max_tokens,
        timeout=timeout,
    )
    usage = {}
    if response.usage:
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }
    return LLMResult(
        content=response.choices[0].message.content or "",
        usage=usage,
        model=model,
    )
```

### Example 2: Router Accumulating Usage

```python
# In router.py -- option B: router accumulates, returns str
class ModelRouter:
    def __init__(self):
        self._usage_log: list[dict] = []

    def reset_usage(self):
        self._usage_log = []

    def get_usage_log(self) -> list[dict]:
        return list(self._usage_log)

    async def call(self, task_type: str, system: str, user: str) -> str:
        model = self.resolve_model(task_type)
        try:
            result = await call_llm(
                system=system, user=user,
                model=model.id, max_tokens=model.max_output, timeout=model.timeout,
            )
            self._usage_log.append({"model": result.model, **result.usage})
            return result.content
        except Exception:
            escalated = self.resolve_escalation(task_type)
            if escalated is None:
                raise
            result = await call_llm(
                system=system, user=user,
                model=escalated.id, max_tokens=escalated.max_output, timeout=escalated.timeout,
            )
            self._usage_log.append({"model": result.model, **result.usage})
            return result.content
```

### Example 3: Planner Node with ContextAssembler

```python
# agent/nodes/planner.py
from agent.context import ContextAssembler

async def planner_node(state: dict, config: RunnableConfig) -> dict:
    router = config["configurable"]["router"]
    instruction = state["instruction"]
    working_dir = state["working_directory"]
    context = state.get("context", {})

    model_config = router.resolve_model("plan")
    assembler = ContextAssembler(
        max_tokens=model_config.context_window - model_config.max_output
    )

    assembler.add_task(instruction)

    if context.get("spec"):
        assembler.add_file("spec", context["spec"], priority="working")
    if context.get("schema"):
        assembler.add_file("schema", context["schema"], priority="reference")

    file_listing = list_files(working_dir) if working_dir else ""
    if file_listing:
        assembler.add_file("file_listing", file_listing, priority="reference")

    user_prompt = PLANNER_USER.format(
        working_directory=working_dir,
        instruction=instruction,
        context_section=assembler.build(),
        file_listing="",  # Now handled by assembler
    )

    raw = await router.call("plan", PLANNER_SYSTEM, user_prompt)
    steps = parse_plan_steps(raw)
    tracer.log("planner", {"steps": len(steps), "instruction": instruction[:100]})
    return {"plan": [step.model_dump() for step in steps]}
```

### Example 4: Token Summary Event for UI

```python
# Emitted by reporter_node at end of run
from store.models import Event

token_summary = router.get_usage_summary()
# token_summary = {"prompt_tokens": 15234, "completion_tokens": 3421,
#                   "total_tokens": 18655, "estimated_cost": 0.072, "call_count": 5}

await event_bus.emit(Event(
    run_id=run_id,
    type="token_usage",
    payload=token_summary,
))

tracer.log("reporter", {"token_usage": token_summary})
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded context window | Model-specific budgets from MODEL_REGISTRY | Already in codebase | ContextAssembler should use MODEL_REGISTRY |
| Discard response.usage | Capture and aggregate | This phase | Enables cost visibility |
| Load full files always | Line-range reads for >200 lines | This phase | Token savings on large codebases |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 8.0 + pytest-asyncio >= 0.24.0 |
| Config file | pyproject.toml (assumed) |
| Quick run command | `python -m pytest tests/test_context.py tests/test_llm.py tests/test_router.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CTX-01 | ContextAssembler wired into planner_node | unit | `python -m pytest tests/test_context.py -x` | Exists (basic) |
| CTX-01 | ContextAssembler wired into editor_node | unit | `python -m pytest tests/test_editor_node.py -x` | Exists (needs update) |
| CTX-01 | Budget respects model context window | unit | `python -m pytest tests/test_context.py::test_model_budget -x` | Wave 0 |
| CTX-02 | Line-range reads for large files | unit | `python -m pytest tests/test_reader_node.py -x` | Wave 0 |
| LIFE-02 | LLM calls return usage stats | unit | `python -m pytest tests/test_llm.py -x` | Exists (needs update) |
| LIFE-02 | Router aggregates usage across calls | unit | `python -m pytest tests/test_router.py -x` | Exists (needs update) |
| LIFE-02 | Cost estimation accuracy | unit | `python -m pytest tests/test_token_tracker.py -x` | Wave 0 |
| LIFE-02 | Token summary emitted via EventBus | integration | `python -m pytest tests/test_event_bus.py -x` | Exists (needs update) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_context.py tests/test_llm.py tests/test_router.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_token_tracker.py` -- covers LIFE-02 cost estimation
- [ ] `tests/test_reader_node.py` -- covers CTX-02 line-range reads
- [ ] Update `tests/test_llm.py` -- mock response.usage field
- [ ] Update `tests/test_router.py` -- verify usage aggregation
- [ ] Update `tests/test_context.py` -- model-specific budget tests

## Open Questions

1. **ContextAssembler system prompt awareness**
   - What we know: Currently ContextAssembler only builds user prompt content. System prompts are separate static strings.
   - What's unclear: Should ContextAssembler account for system prompt size in its budget?
   - Recommendation: YES -- subtract estimated system prompt token count from budget. System prompts are small (~200-500 tokens) so a fixed 1000-token reservation is sufficient.

2. **Router return type strategy**
   - What we know: Changing `call_llm` return from `str` to `LLMResult` requires updating all callers.
   - What's unclear: Whether to change the router's external API or keep it returning `str` with internal accumulation.
   - Recommendation: Keep router returning `str` from `.call()` and `BaseModel` from `.call_structured()`. Accumulate usage internally in the router. Expose via `router.get_usage_log()`. This minimizes blast radius.

3. **Where to store token accumulation across the run**
   - What we know: AgentState has `model_usage: dict[str, int]` already. Router is passed via config.
   - What's unclear: Whether to use AgentState or the router instance for accumulation.
   - Recommendation: Use the router instance (it persists across the entire run via config["configurable"]["router"]). At reporter_node, extract the accumulated usage and emit it. No need to thread it through AgentState on every step.

## Sources

### Primary (HIGH confidence)
- `agent/context.py` -- Direct code inspection of ContextAssembler
- `agent/llm.py` -- Direct code inspection of call_llm / call_llm_structured
- `agent/router.py` -- Direct code inspection of ModelRouter
- `agent/models.py` -- MODEL_REGISTRY with context_window values
- `agent/state.py` -- AgentState TypedDict with model_usage field
- All node files -- Direct code inspection of prompt construction patterns

### Secondary (MEDIUM confidence)
- [OpenAI API Pricing](https://openai.com/api/pricing/) -- o3: $2/$8, gpt-4o: $2.50/$10, gpt-4o-mini: $0.15/$0.60 per 1M tokens
- [OpenAI Python SDK](https://github.com/openai/openai-python/discussions/2463) -- response.usage contains prompt_tokens, completion_tokens, total_tokens

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, everything exists in project
- Architecture: HIGH -- clear integration points, well-understood patterns
- Pitfalls: HIGH -- identified from direct code inspection of all affected files
- Token pricing: MEDIUM -- verified via web search March 2026, but prices can change

**Research date:** 2026-03-26
**Valid until:** 2026-04-26 (stable domain, pricing may shift)
