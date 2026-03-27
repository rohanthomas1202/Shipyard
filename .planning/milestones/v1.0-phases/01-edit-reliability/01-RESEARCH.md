# Phase 1: Edit Reliability - Research

**Researched:** 2026-03-26
**Domain:** Fuzzy anchor matching, structured LLM outputs, error feedback, indentation preservation, file freshness
**Confidence:** HIGH

## Summary

Phase 1 addresses the most impactful failure mode in Shipyard: edits failing because the LLM-generated anchor does not exactly match file content. The current `edit_file()` in `file_ops.py` uses a bare `str.replace()` with zero tolerance for whitespace differences, trailing spaces, or indentation mismatches. When an anchor fails, the retry loop in `should_continue()` sends the editor back through `reader_node` but provides no information about *why* the anchor failed -- `error_state` is a flat string that says "Anchor not found" without showing what was actually in the file at the expected location.

The fix is a layered fallback chain in `edit_file()` (exact -> whitespace-normalized -> fuzzy via `difflib.SequenceMatcher`), structured LLM outputs via `client.chat.completions.parse()` with Pydantic models to eliminate JSON parse failures, actionable error feedback that includes the failed anchor, the closest match found, and the similarity score, indentation preservation that detects and applies surrounding whitespace patterns, and file freshness checking via `hashlib.sha256` content hashes stored alongside `file_buffer`.

All changes are contained in 4-5 existing files with no new external dependencies. `difflib` and `hashlib` are Python stdlib. The OpenAI SDK already installed (v2.26.0) natively supports `client.chat.completions.parse()` with Pydantic models for structured outputs.

**Primary recommendation:** Implement the fuzzy matching fallback chain in `edit_file()` first -- it is the highest-impact, lowest-risk change and unblocks testing of all other Phase 1 features.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None -- all implementation choices are at Claude's discretion (infrastructure phase).

### Claude's Discretion
All implementation choices are at Claude's discretion. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key constraints from research:
- Fuzzy matching should cascade: exact -> whitespace-normalized -> fuzzy Levenshtein (threshold ~0.85)
- Error feedback must include: which anchor failed, what was found instead, similarity score
- Indentation detection must handle tabs vs spaces, nesting level
- File freshness via content hash (hashlib), not timestamps
- OpenAI structured outputs with `strict: True` and `response_format` on all LLM calls

### Deferred Ideas (OUT OF SCOPE)
None -- infrastructure phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EDIT-01 | Layered anchor matching with fuzzy fallbacks (exact -> whitespace-normalized -> fuzzy Levenshtein) | `difflib.SequenceMatcher` in stdlib; threshold 0.85; fallback chain pattern from Aider/RooCode |
| EDIT-02 | Actionable error feedback when anchor matching fails (which anchor, what was found instead, similarity score) | New `EditError` dataclass; `EDITOR_USER` prompt template needs `{previous_error}` field; `error_state` needs structure |
| EDIT-03 | Preserve indentation style when applying replacements (tabs vs spaces, indentation level) | Detect indent from first line of anchor context; apply delta to replacement lines |
| EDIT-04 | File freshness via content checksums before applying edits, re-read if changed | `hashlib.sha256` on `file_buffer` entries; new `file_hashes: dict[str, str]` in AgentState |
| VALID-01 | Validator feeds specific error details into retry prompt | Validator already produces error strings; need structured error with file, line, message, score |
| INFRA-03 | All LLM calls use OpenAI structured outputs with strict: true | `AsyncOpenAI.chat.completions.parse()` with Pydantic BaseModel as `response_format`; SDK 2.26.0 already installed |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `difflib` | stdlib | Fuzzy string matching via `SequenceMatcher` | Built-in, no dependency; `ratio()` returns 0-1 similarity score; used by Aider for same purpose |
| `hashlib` | stdlib | Content hashing for file freshness | Built-in SHA-256; fast, deterministic; no external dependency |
| `openai` | 2.26.0 (installed) | Structured outputs via `parse()` | Already installed; `chat.completions.parse()` accepts Pydantic models directly |
| `pydantic` | transitive (via FastAPI) | Schema definitions for structured outputs | Already available; `BaseModel` subclasses become `response_format` schemas |
| `re` | stdlib | Whitespace normalization in matching | Standard regex for collapsing whitespace patterns |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `textwrap` | stdlib | Indentation detection/manipulation | `textwrap.dedent()` for normalizing indentation during matching |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `difflib.SequenceMatcher` | `python-Levenshtein` (C ext) | Faster for large strings but adds a compiled dependency; `difflib` is sufficient for anchor-sized strings (3-20 lines) |
| Content hash (`hashlib.sha256`) | File mtime timestamps | Timestamps are unreliable across git operations, editor saves, and CI; content hash is deterministic |
| `openai.parse()` | Manual `response_format={"type":"json_object"}` | `json_object` mode only guarantees valid JSON, not schema compliance; `parse()` with strict mode guarantees schema match |

**No new dependencies required.** Everything is stdlib or already installed.

## Architecture Patterns

### Recommended Project Structure
No new files needed. Changes go into existing modules:
```
agent/
  tools/
    file_ops.py          # Fuzzy matching chain, indentation preservation, file hash
  nodes/
    editor.py            # Structured output call, error feedback in prompt, freshness check
    validator.py          # Structured error output (already mostly done)
  prompts/
    editor.py            # Add {previous_error} template field
  llm.py                 # Add call_llm_structured() using parse()
  state.py               # Add file_hashes field to AgentState
  schemas.py             # NEW: Pydantic models for structured LLM outputs (EditResponse, etc.)
```

### Pattern 1: Fuzzy Matching Fallback Chain
**What:** Three-tier anchor matching in `edit_file()`: exact match -> whitespace-normalized match -> fuzzy `SequenceMatcher` match
**When to use:** Every call to `edit_file()` -- the chain is transparent, falling through only when needed
**Example:**
```python
# In agent/tools/file_ops.py
import re
from difflib import SequenceMatcher

FUZZY_THRESHOLD = 0.85

def _normalize_whitespace(text: str) -> str:
    """Collapse all whitespace runs to single spaces, strip lines."""
    return re.sub(r'\s+', ' ', text).strip()

def _find_fuzzy_match(content: str, anchor: str, threshold: float = FUZZY_THRESHOLD) -> tuple[str | None, float]:
    """Find the best fuzzy match for anchor in content. Returns (matched_text, score)."""
    anchor_lines = anchor.count('\n') + 1
    content_lines = content.split('\n')
    best_match = None
    best_score = 0.0

    for i in range(len(content_lines) - anchor_lines + 1):
        candidate = '\n'.join(content_lines[i:i + anchor_lines])
        score = SequenceMatcher(None, anchor, candidate).ratio()
        if score > best_score:
            best_score = score
            best_match = candidate

    if best_score >= threshold:
        return best_match, best_score
    return None, best_score

def edit_file(path: str, anchor: str, replacement: str) -> dict:
    """Edit file with layered matching: exact -> whitespace-normalized -> fuzzy."""
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        return {"success": False, "snapshot": None, "error": f"File not found: {path}"}

    # Layer 1: Exact match
    count = content.count(anchor)
    if count == 1:
        snapshot = content
        new_content = content.replace(anchor, replacement, 1)
        with open(path, "w") as f:
            f.write(new_content)
        return {"success": True, "snapshot": snapshot, "error": None, "match_type": "exact"}
    if count > 1:
        return {"success": False, "snapshot": None,
                "error": f"Anchor not unique in {path} (found {count} occurrences)"}

    # Layer 2: Whitespace-normalized match
    norm_anchor = _normalize_whitespace(anchor)
    for line_start in range(content.count('\n') + 1):
        # Slide window of same line count
        lines = content.split('\n')
        anchor_line_count = anchor.count('\n') + 1
        for i in range(len(lines) - anchor_line_count + 1):
            candidate = '\n'.join(lines[i:i + anchor_line_count])
            if _normalize_whitespace(candidate) == norm_anchor:
                snapshot = content
                new_content = content.replace(candidate, replacement, 1)
                with open(path, "w") as f:
                    f.write(new_content)
                return {"success": True, "snapshot": snapshot, "error": None,
                        "match_type": "whitespace_normalized"}
        break  # Only need one pass

    # Layer 3: Fuzzy match
    matched_text, score = _find_fuzzy_match(content, anchor)
    if matched_text is not None:
        snapshot = content
        new_content = content.replace(matched_text, replacement, 1)
        with open(path, "w") as f:
            f.write(new_content)
        return {"success": True, "snapshot": snapshot, "error": None,
                "match_type": "fuzzy", "fuzzy_score": score}

    # All layers failed -- return diagnostic info
    _, best_score = _find_fuzzy_match(content, anchor, threshold=0.0)
    return {
        "success": False,
        "snapshot": None,
        "error": f"Anchor not found in {path}",
        "best_score": best_score,
        "anchor_preview": anchor[:200],
    }
```

### Pattern 2: Structured LLM Output via parse()
**What:** Replace `call_llm()` string return with `call_llm_structured()` that returns a parsed Pydantic model
**When to use:** All LLM calls that expect structured JSON (editor, planner)
**Example:**
```python
# In agent/llm.py
from pydantic import BaseModel

async def call_llm_structured(
    system: str,
    user: str,
    response_model: type[BaseModel],
    model: str = "gpt-4o",
    max_tokens: int = 16_384,
    timeout: int = 60,
) -> BaseModel:
    """Call OpenAI with structured output. Returns parsed Pydantic model."""
    client = _get_client()
    response = await client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format=response_model,
        max_completion_tokens=max_tokens,
        timeout=timeout,
    )
    return response.choices[0].message.parsed

# In agent/schemas.py (NEW)
from pydantic import BaseModel

class EditResponse(BaseModel):
    anchor: str
    replacement: str
```

### Pattern 3: Error Feedback in Retry Prompt
**What:** When `error_state` is set, include structured error details in the editor's next prompt
**When to use:** On every retry (when `error_state` is not None and editor is re-entered)
**Example:**
```python
# In agent/prompts/editor.py -- add to EDITOR_USER template
EDITOR_USER = """File: {file_path}

Content:
{numbered_content}

Instruction: {edit_instruction}

{context_section}

{error_feedback}

Respond with the JSON object containing "anchor" and "replacement"."""

# Error feedback format (populated when retrying):
ERROR_FEEDBACK_TEMPLATE = """PREVIOUS ATTEMPT FAILED:
- Anchor tried: ```{failed_anchor}```
- Error: {error_message}
- Best match found (score {score}): ```{best_match}```
- DO NOT repeat the same anchor. Use the actual file content shown above."""
```

### Pattern 4: File Freshness via Content Hash
**What:** Hash file content on read, check hash before edit, re-read if stale
**When to use:** In `editor_node` before calling `edit_file()`
**Example:**
```python
# In agent/tools/file_ops.py
import hashlib

def content_hash(content: str) -> str:
    """SHA-256 hash of file content (first 16 hex chars)."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]

# In editor_node: before applying edit
stored_hash = state.get("file_hashes", {}).get(file_path)
current_content = _read_raw(file_path)
current_hash = content_hash(current_content)
if stored_hash and stored_hash != current_hash:
    # File changed since last read -- update buffer and re-read
    file_buffer[file_path] = current_content
    content = current_content  # Use fresh content for edit
```

### Pattern 5: Indentation Preservation
**What:** Detect the indentation style of the anchor's location and apply it to the replacement
**When to use:** After fuzzy/normalized matching (replacement may have different indentation)
**Example:**
```python
def _detect_indent(line: str) -> tuple[str, int]:
    """Detect indent character and level from a line."""
    stripped = line.lstrip()
    indent = line[:len(line) - len(stripped)]
    if '\t' in indent:
        return '\t', indent.count('\t')
    return ' ', len(indent)

def _adjust_replacement_indent(anchor: str, replacement: str, content: str) -> str:
    """Adjust replacement to match the indentation context of the anchor in content."""
    anchor_start = content.find(anchor)
    if anchor_start == -1:
        return replacement

    # Find the line containing the anchor start
    line_start = content.rfind('\n', 0, anchor_start) + 1
    context_line = content[line_start:anchor_start + len(anchor.split('\n')[0])]
    char, base_level = _detect_indent(context_line)

    # Detect replacement's base indent
    rep_lines = replacement.split('\n')
    if not rep_lines:
        return replacement

    rep_char, rep_base = _detect_indent(rep_lines[0])

    # If indentation already matches, no adjustment needed
    if char == rep_char and base_level == rep_base:
        return replacement

    # Re-indent replacement to match context
    adjusted = []
    for line in rep_lines:
        if not line.strip():
            adjusted.append(line)
            continue
        _, line_level = _detect_indent(line)
        relative = line_level - rep_base
        new_indent = char * (base_level + relative)
        adjusted.append(new_indent + line.lstrip())
    return '\n'.join(adjusted)
```

### Anti-Patterns to Avoid
- **Whole-file rewriting:** Never replace entire file content as a fallback. The anchor-based strategy is committed. If all matching layers fail, return an error with diagnostics.
- **Regex-based anchor matching:** Regex is fragile with special characters in code. Use `SequenceMatcher` for fuzzy matching.
- **Modifying `error_state` type to a dict directly:** The `AgentState` TypedDict declares `error_state: Optional[str]`. Store structured error info in a *new* state field (e.g., `last_edit_error: dict`) or serialize to JSON string to maintain backward compatibility with `should_continue()`.
- **Lowering fuzzy threshold below 0.8:** At threshold < 0.8, fuzzy matches produce false positives (matching the wrong code block). Start at 0.85, only lower after empirical testing.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy string matching | Custom Levenshtein implementation | `difflib.SequenceMatcher` | Stdlib, battle-tested, returns ratio + matching blocks |
| JSON schema enforcement | Manual JSON parsing + validation | OpenAI `parse()` + Pydantic | Server-side schema enforcement guarantees compliance; zero parse failures |
| Content hashing | Custom hash function | `hashlib.sha256` | Stdlib, fast, collision-resistant |
| Whitespace normalization | Custom char-by-char normalization | `re.sub(r'\s+', ' ', text)` | One-liner, handles all whitespace types |
| Indentation detection | Manual character counting | `textwrap.dedent()` + `line.lstrip()` delta | Stdlib handles edge cases (mixed tabs/spaces) |

**Key insight:** Every component in this phase uses Python stdlib. The only non-stdlib change is using the already-installed OpenAI SDK's `parse()` method instead of manual JSON extraction.

## Common Pitfalls

### Pitfall 1: Fuzzy Match False Positives
**What goes wrong:** Fuzzy matching at a low threshold matches the wrong code block, applying the replacement to the wrong location. The edit passes syntax validation but is semantically wrong.
**Why it happens:** Code files have many structurally similar blocks (e.g., multiple function signatures, import groups, similar if/else branches).
**How to avoid:** Start with threshold 0.85 (not 0.7). Require that fuzzy-matched text has the same line count as the anchor. Log every fuzzy match with its score for post-hoc analysis. Consider requiring exact match for the first and last lines of the anchor.
**Warning signs:** `match_type: "fuzzy"` appearing frequently in traces; semantic errors after edits that passed syntax checks.

### Pitfall 2: Structured Output Breaking Existing Tests
**What goes wrong:** Changing `call_llm()` signature or return type breaks all existing tests that mock `router.call()` to return a raw JSON string.
**Why it happens:** `router.call()` currently returns `str`. Changing it to return a Pydantic model changes the contract for all callers.
**How to avoid:** Add `call_llm_structured()` as a NEW method alongside existing `call_llm()`. Add `call_structured()` to `ModelRouter` alongside `call()`. Migrate callers incrementally -- editor first, then others in later phases.
**Warning signs:** Test failures in `test_editor_node.py`, `test_graph.py` after modifying `llm.py`.

### Pitfall 3: AgentState Schema Change Breaking Graph
**What goes wrong:** Adding `file_hashes` to `AgentState` TypedDict without providing a default causes `KeyError` in nodes that access it from existing graph state.
**Why it happens:** LangGraph state is a TypedDict. Existing runs and test fixtures do not include the new field.
**How to avoid:** Always use `.get("file_hashes", {})` when accessing the new field. Update test fixtures to include the field. TypedDict fields without `Optional` or `NotRequired` will cause type-checking issues but not runtime errors (TypedDict is not enforced at runtime).
**Warning signs:** `KeyError: 'file_hashes'` in tests or during graph execution.

### Pitfall 4: Error Feedback Template Injection
**What goes wrong:** The `{previous_error}` field in the editor prompt contains file content that includes curly braces, breaking Python's `str.format()`.
**Why it happens:** `EDITOR_USER.format(...)` will fail if error feedback contains `{` or `}` characters (common in JSON, TypeScript, Python code).
**How to avoid:** Use a two-stage approach: build the error feedback string first, then insert it. Or switch to `string.Template` or manual concatenation for the error section. Simplest: just use string concatenation for the error block rather than putting it inside the format template.
**Warning signs:** `KeyError` or `IndexError` during prompt formatting when the error feedback contains braces.

### Pitfall 5: o3 Model Does Not Support Structured Outputs
**What goes wrong:** The `o3` reasoning model may not support `response_format` with strict JSON schema. The call throws an error or returns unstructured text.
**Why it happens:** OpenAI reasoning models (o1, o3) have historically had limited support for structured outputs and system messages.
**How to avoid:** Check the model capabilities before using `parse()`. For reasoning-tier models, fall back to the current `call_llm()` + manual JSON parsing. Or test empirically with o3 -- as of early 2025, o3-mini supports structured outputs, o3 full support varies.
**Warning signs:** `openai.BadRequestError` when using `parse()` with o3 model.

## Code Examples

### Current edit_file() (exact match only)
```python
# agent/tools/file_ops.py lines 15-30
def edit_file(path: str, anchor: str, replacement: str) -> dict:
    # ... reads file ...
    count = content.count(anchor)
    if count == 0:
        return {"success": False, "snapshot": None, "error": f"Anchor not found in {path}"}
    if count > 1:
        return {"success": False, "snapshot": None, "error": f"Anchor not unique in {path} (found {count} occurrences)"}
    new_content = content.replace(anchor, replacement, 1)
    # ... writes file ...
```

### Current editor_node JSON parsing (brittle)
```python
# agent/nodes/editor.py lines 110-124
# Parse JSON response -- strip markdown fences if present
cleaned = raw.strip()
if cleaned.startswith("```"):
    lines = cleaned.split("\n")
    lines = [l for l in lines if not l.strip().startswith("```")]
    cleaned = "\n".join(lines)

try:
    data = json.loads(cleaned)
    anchor = data["anchor"]
    replacement = data["replacement"]
except (json.JSONDecodeError, KeyError) as e:
    return {"error_state": f"Editor output parse error: {e}"}
```
This entire block goes away with structured outputs -- `parse()` returns a typed Pydantic object directly.

### Current error_state usage (opaque string)
```python
# agent/graph.py line 31-34
if error:
    if _retry_count(state) >= 3:
        return "reporter"
    return "reader"
```
Error is checked for truthiness only. The editor never sees *what* the error was. The fix: pass error details through state into the editor prompt template.

### Current EDITOR_USER template (no error feedback)
```python
# agent/prompts/editor.py lines 20-29
EDITOR_USER = """File: {file_path}
Content:
{numbered_content}
Instruction: {edit_instruction}
{context_section}
Respond with the JSON object containing "anchor" and "replacement"."""
```
No `{previous_error}` or `{error_feedback}` field exists. Retries see the exact same prompt.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `json_object` response format | `json_schema` with `strict: true` via `parse()` | OpenAI SDK 1.40+ (mid-2024) | Eliminates all JSON parse failures; server enforces schema |
| Manual JSON fence stripping | Pydantic model as `response_format` | OpenAI SDK 1.40+ | No markdown fences, no partial JSON, guaranteed structure |
| `str.replace()` exact match | Layered fuzzy fallback (Aider pattern) | Aider 0.30+ (2024) | Recovers 10-30% of failed edits from whitespace mismatches |
| Flat string `error_state` | Structured error with context for retry | Standard in production agents | Retry success rate increases dramatically with error context |

**Deprecated/outdated:**
- `response_format={"type": "json_object"}`: Still works but provides no schema enforcement. Use `parse()` with Pydantic model instead.
- OpenAI SDK 1.x patterns: Project is already on SDK 2.26.0, so `parse()` is available directly (not in `beta`).

## Open Questions

1. **o3 structured output support**
   - What we know: o3-mini supports structured outputs as of early 2025. Full o3 support is model-version dependent.
   - What's unclear: Whether the specific o3 version used by this project supports `response_format` with strict JSON schema.
   - Recommendation: Test empirically. If o3 does not support `parse()`, keep the manual JSON parsing path as fallback for reasoning-tier calls. The `edit_complex` task type uses reasoning tier.

2. **Fuzzy threshold calibration**
   - What we know: Research recommends 0.85. Aider uses a similar threshold.
   - What's unclear: The optimal threshold for Shipyard's specific LLM output patterns (gpt-4o vs o3 produce different anchor styles).
   - Recommendation: Start at 0.85. Log all fuzzy matches with scores. Adjust after collecting data from real runs.

3. **error_state type compatibility**
   - What we know: `error_state: Optional[str]` in AgentState. `should_continue()` checks truthiness. Validator sets it to formatted strings.
   - What's unclear: Whether changing to `Optional[dict]` would break any other consumers.
   - Recommendation: Keep `error_state` as `Optional[str]` for backward compatibility. Add a separate `last_edit_error: Optional[dict]` field for structured error info that the editor prompt can consume. Or serialize error dict to JSON string in `error_state`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio |
| Config file | pyproject.toml (no `[tool.pytest]` section -- uses defaults) |
| Quick run command | `python -m pytest tests/test_file_ops.py tests/test_editor_node.py tests/test_validator_node.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q --ignore=tests/test_lsp_integration.py` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EDIT-01 | Fuzzy matching fallback chain (exact -> whitespace -> fuzzy) | unit | `python -m pytest tests/test_file_ops.py -x -k "fuzzy or whitespace or normalize"` | Needs new tests in existing file |
| EDIT-02 | Error feedback with anchor, best match, score in retry prompt | unit + integration | `python -m pytest tests/test_editor_node.py -x -k "error_feedback or retry"` | Needs new tests in existing file |
| EDIT-03 | Indentation preservation (tabs vs spaces, nesting) | unit | `python -m pytest tests/test_file_ops.py -x -k "indent"` | Needs new tests in existing file |
| EDIT-04 | File freshness via content hash, re-read on change | unit + integration | `python -m pytest tests/test_editor_node.py -x -k "fresh or hash or stale"` | Needs new tests in existing file |
| VALID-01 | Validator feeds structured error details into retry prompt | unit | `python -m pytest tests/test_validator_node.py -x -k "error_detail or structured"` | Needs new tests in existing file |
| INFRA-03 | Structured outputs via parse(), zero JSON parse failures | unit | `python -m pytest tests/test_llm.py -x -k "structured or parse"` | Needs new tests in existing file |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_file_ops.py tests/test_editor_node.py tests/test_validator_node.py tests/test_llm.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q --ignore=tests/test_lsp_integration.py`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_file_ops.py` -- add tests for fuzzy matching, whitespace normalization, indentation preservation, content hashing (EDIT-01, EDIT-03, EDIT-04)
- [ ] `tests/test_editor_node.py` -- add tests for error feedback in retry, freshness check, structured output parsing (EDIT-02, EDIT-04, INFRA-03)
- [ ] `tests/test_validator_node.py` -- add tests for structured error output format (VALID-01)
- [ ] `tests/test_llm.py` -- add tests for `call_llm_structured()` with Pydantic model (INFRA-03)
- [ ] `agent/schemas.py` -- NEW file for Pydantic response models (INFRA-03)

## Sources

### Primary (HIGH confidence)
- OpenAI Structured Outputs docs (https://developers.openai.com/api/docs/guides/structured-outputs) -- `parse()` API, `strict: true`, Pydantic model as response_format
- Python stdlib `difflib.SequenceMatcher` docs -- `ratio()` method, sliding window matching
- Python stdlib `hashlib` docs -- SHA-256 content hashing
- Codebase audit: `agent/tools/file_ops.py`, `agent/nodes/editor.py`, `agent/nodes/validator.py`, `agent/llm.py`, `agent/state.py`, `agent/graph.py`
- OpenAI SDK 2.26.0 installed (verified via `pip show openai`) -- `AsyncOpenAI.chat.completions.parse()` confirmed available

### Secondary (MEDIUM confidence)
- Project research SUMMARY.md -- fuzzy threshold 0.85, Aider/RooCode pattern analysis, layered matching approach
- Aider edit format docs (https://aider.chat/docs/more/edit-formats.html) -- fuzzy matching cascade pattern

### Tertiary (LOW confidence)
- o3 structured output support -- needs empirical validation; model capability may vary by version

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all stdlib or already-installed packages; verified versions
- Architecture: HIGH -- patterns are well-established (Aider, RooCode); code locations identified precisely in codebase
- Pitfalls: HIGH -- derived from direct codebase audit; each pitfall maps to specific code lines
- Structured outputs: MEDIUM -- SDK method verified available; o3 model support needs testing

**Research date:** 2026-03-26
**Valid until:** 2026-04-26 (stable domain, stdlib-only changes)
