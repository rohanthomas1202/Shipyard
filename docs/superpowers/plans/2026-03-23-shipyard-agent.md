# Shipyard Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an autonomous coding agent that runs in a persistent loop, makes surgical file edits via anchor-based replacement, coordinates multiple sub-agents, accepts injected context, and can rebuild the Ship app.

**Architecture:** Single LangGraph StateGraph with FastAPI server wrapper. Nodes handle planning, file reading, anchor-based editing, validation, multi-agent coordination (via subgraphs + Send API), and error recovery. SQLite-backed checkpointing for persistence. LangSmith for tracing.

**Tech Stack:** Python 3.12+, LangGraph, Anthropic SDK (Claude), FastAPI, SQLite (checkpointing), LangSmith (tracing), pytest

---

## File Structure

```
shipyard/
├── pyproject.toml              # Project config, dependencies
├── README.md                   # Setup guide, architecture overview
├── PRESEARCH.md                # (already exists)
├── CODEAGENT.md                # Submission template (filled incrementally)
├── agent/
│   ├── __init__.py
│   ├── state.py                # AgentState TypedDict + multi-agent fields
│   ├── llm.py                  # Shared call_llm utility (single Anthropic client)
│   ├── graph.py                # StateGraph definition, node wiring, conditional edges
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── receive.py          # receive_instruction node
│   │   ├── planner.py          # planner node — breaks instruction into steps
│   │   ├── reader.py           # reader node — reads files into state
│   │   ├── editor.py           # editor node — anchor-based surgical edits
│   │   ├── executor.py         # executor node — runs shell commands
│   │   ├── validator.py        # validator node — checks edits, runs syntax checks
│   │   ├── coordinator.py      # coordinator node — multi-agent fan-out
│   │   ├── merger.py           # merger node — collects subgraph outputs
│   │   └── reporter.py         # reporter node — summarizes results
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── file_ops.py         # read_file, edit_file, create_file, delete_file, list_files
│   │   ├── search.py           # search_content (grep-like)
│   │   └── shell.py            # run_command
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── planner.py          # System/user prompts for planner
│   │   ├── editor.py           # System/user prompts for editor
│   │   └── coordinator.py      # System/user prompts for coordinator
│   └── tracing.py              # Local JSON trace logger (supplements LangSmith)
├── server/
│   ├── __init__.py
│   └── main.py                 # FastAPI app — POST /instruction, GET /status, POST /instruction/{run_id}
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Shared fixtures (temp directories, sample files)
│   ├── test_state.py           # AgentState schema tests
│   ├── test_file_ops.py        # File operation tool tests
│   ├── test_search.py          # Search tool tests
│   ├── test_shell.py           # Shell tool tests
│   ├── test_editor_node.py     # Editor node tests (anchor logic)
│   ├── test_validator_node.py  # Validator node tests
│   ├── test_graph.py           # Integration: full graph run
│   ├── test_multiagent.py      # Multi-agent coordination tests
│   └── test_server.py          # FastAPI endpoint tests
├── traces/                     # Local JSON trace output directory
└── .env.example                # Template for env vars (ANTHROPIC_API_KEY, LANGSMITH, etc.)
```

---

## Task 1: Project Setup & State Schema

**Files:**
- Create: `pyproject.toml`
- Create: `agent/__init__.py`
- Create: `agent/state.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_state.py`
- Create: `.env.example`

- [ ] **Step 1: Initialize the Python project**

```toml
# pyproject.toml
[project]
name = "shipyard"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "langgraph>=0.4.0",
    "langchain-anthropic>=0.3.0",
    "langchain-core>=0.3.0",
    "anthropic>=0.42.0",
    "fastapi>=0.115.0",
    "uvicorn>=0.34.0",
    "httpx>=0.28.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24.0",
    "pytest-httpx>=0.35.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["agent", "server"]
```

- [ ] **Step 2: Create .env.example**

```bash
# .env.example
ANTHROPIC_API_KEY=sk-ant-...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls-...
LANGCHAIN_PROJECT=shipyard
```

- [ ] **Step 3: Install dependencies**

Run: `cd /Users/rohanthomas/Shipyard && pip install -e ".[dev]"`
Expected: All packages install successfully

- [ ] **Step 4: Write the failing test for AgentState**

```python
# tests/test_state.py
from agent.state import AgentState

def test_agent_state_has_required_fields():
    state = AgentState(
        messages=[],
        instruction="test instruction",
        working_directory="/tmp/test",
        context={},
        plan=[],
        current_step=0,
        file_buffer={},
        edit_history=[],
        error_state=None,
        is_parallel=False,
        parallel_batches=[],
        sequential_first=[],
        has_conflicts=False,
    )
    assert state["instruction"] == "test instruction"
    assert state["working_directory"] == "/tmp/test"
    assert state["messages"] == []
    assert state["context"] == {}
    assert state["plan"] == []
    assert state["current_step"] == 0
    assert state["file_buffer"] == {}
    assert state["edit_history"] == []
    assert state["error_state"] is None
    assert state["is_parallel"] is False
    assert state["parallel_batches"] == []
```

- [ ] **Step 5: Run test to verify it fails**

Run: `cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent'`

- [ ] **Step 6: Write AgentState**

```python
# agent/__init__.py
# Shipyard agent package

# agent/state.py
from typing import Annotated, Optional, TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    instruction: str
    working_directory: str
    context: dict
    plan: list[str]
    current_step: int
    file_buffer: dict[str, str]
    edit_history: list[dict]
    error_state: Optional[str]
    # Multi-agent coordination fields
    is_parallel: bool
    parallel_batches: list[list[int]]
    sequential_first: list[int]
    has_conflicts: bool
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_state.py -v`
Expected: PASS

- [ ] **Step 8: Create conftest with shared fixtures**

```python
# tests/__init__.py
# tests package

# tests/conftest.py
import os
import tempfile
import pytest

@pytest.fixture
def tmp_codebase():
    """Create a temporary directory with sample files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a sample TypeScript file
        ts_file = os.path.join(tmpdir, "sample.ts")
        with open(ts_file, "w") as f:
            f.write(
                'export interface Issue {\n'
                '  id: string;\n'
                '  title: string;\n'
                '  description: string;\n'
                '  status: "open" | "closed";\n'
                '}\n'
            )
        # Create a sample JSON file
        json_file = os.path.join(tmpdir, "config.json")
        with open(json_file, "w") as f:
            f.write('{\n  "port": 3000,\n  "host": "localhost"\n}\n')
        # Create a nested directory
        nested = os.path.join(tmpdir, "src", "models")
        os.makedirs(nested)
        model_file = os.path.join(nested, "user.ts")
        with open(model_file, "w") as f:
            f.write(
                'export interface User {\n'
                '  id: string;\n'
                '  name: string;\n'
                '  email: string;\n'
                '}\n'
            )
        yield tmpdir
```

- [ ] **Step 9: Commit**

```bash
git init
git add pyproject.toml .env.example agent/ tests/
git commit -m "feat: project setup with AgentState schema and test fixtures"
```

---

## Task 2: File Operation Tools

**Files:**
- Create: `agent/tools/__init__.py`
- Create: `agent/tools/file_ops.py`
- Create: `agent/tools/search.py`
- Create: `agent/tools/shell.py`
- Create: `tests/test_file_ops.py`
- Create: `tests/test_search.py`
- Create: `tests/test_shell.py`

- [ ] **Step 1: Write failing tests for read_file**

```python
# tests/test_file_ops.py
import os
from agent.tools.file_ops import read_file, edit_file, create_file, delete_file, list_files

def test_read_file_returns_content_with_line_numbers(tmp_codebase):
    result = read_file(os.path.join(tmp_codebase, "sample.ts"))
    assert "1: export interface Issue {" in result
    assert "2:   id: string;" in result

def test_read_file_nonexistent_returns_error(tmp_codebase):
    result = read_file(os.path.join(tmp_codebase, "nope.ts"))
    assert "Error" in result or "not found" in result.lower()

def test_edit_file_replaces_anchor(tmp_codebase):
    path = os.path.join(tmp_codebase, "sample.ts")
    anchor = '  description: string;\n  status: "open" | "closed";'
    replacement = '  description: string;\n  due_date: string;\n  status: "open" | "closed";'
    result = edit_file(path, anchor, replacement)
    assert result["success"] is True
    content = open(path).read()
    assert "due_date: string;" in content
    assert result["snapshot"] is not None

def test_edit_file_anchor_not_found(tmp_codebase):
    path = os.path.join(tmp_codebase, "sample.ts")
    result = edit_file(path, "this anchor does not exist", "replacement")
    assert result["success"] is False
    assert "not found" in result["error"].lower()

def test_edit_file_anchor_not_unique(tmp_codebase):
    path = os.path.join(tmp_codebase, "sample.ts")
    # "string;" appears multiple times
    result = edit_file(path, "string;", "number;")
    assert result["success"] is False
    assert "not unique" in result["error"].lower() or "multiple" in result["error"].lower()

def test_create_file(tmp_codebase):
    path = os.path.join(tmp_codebase, "new_file.ts")
    result = create_file(path, "export const x = 1;\n")
    assert result["success"] is True
    assert os.path.exists(path)
    assert open(path).read() == "export const x = 1;\n"

def test_create_file_already_exists(tmp_codebase):
    path = os.path.join(tmp_codebase, "sample.ts")
    result = create_file(path, "overwrite")
    assert result["success"] is False
    assert "exists" in result["error"].lower()

def test_delete_file(tmp_codebase):
    path = os.path.join(tmp_codebase, "sample.ts")
    result = delete_file(path)
    assert result["success"] is True
    assert not os.path.exists(path)

def test_list_files(tmp_codebase):
    result = list_files(tmp_codebase, "*.ts")
    assert "sample.ts" in result
    assert "user.ts" in result

def test_list_files_with_pattern(tmp_codebase):
    result = list_files(tmp_codebase, "*.json")
    assert "config.json" in result
    assert "sample.ts" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_file_ops.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement file_ops.py**

```python
# agent/tools/__init__.py
# Tools package

# agent/tools/file_ops.py
import os
import glob as globlib

def read_file(path: str) -> str:
    """Read a file and return contents with line numbers."""
    try:
        with open(path, "r") as f:
            lines = f.readlines()
        numbered = [f"{i+1}: {line.rstrip()}" for i, line in enumerate(lines)]
        return "\n".join(numbered)
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error reading {path}: {e}"

def edit_file(path: str, anchor: str, replacement: str) -> dict:
    """Anchor-based surgical edit. Returns {success, snapshot, error}."""
    try:
        with open(path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        return {"success": False, "snapshot": None, "error": f"File not found: {path}"}

    count = content.count(anchor)
    if count == 0:
        return {"success": False, "snapshot": None, "error": f"Anchor not found in {path}"}
    if count > 1:
        return {
            "success": False,
            "snapshot": None,
            "error": f"Anchor not unique in {path} (found {count} occurrences). Provide a longer anchor.",
        }

    snapshot = content
    new_content = content.replace(anchor, replacement, 1)

    with open(path, "w") as f:
        f.write(new_content)

    return {"success": True, "snapshot": snapshot, "error": None}

def create_file(path: str, content: str) -> dict:
    """Create a new file. Fails if file already exists."""
    if os.path.exists(path):
        return {"success": False, "error": f"File already exists: {path}"}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    return {"success": True, "error": None}

def delete_file(path: str) -> dict:
    """Delete a file."""
    try:
        os.remove(path)
        return {"success": True, "error": None}
    except FileNotFoundError:
        return {"success": False, "error": f"File not found: {path}"}

def list_files(directory: str, pattern: str = "*") -> str:
    """List files matching a glob pattern recursively."""
    matches = globlib.glob(os.path.join(directory, "**", pattern), recursive=True)
    relative = [os.path.relpath(m, directory) for m in matches if os.path.isfile(m)]
    return "\n".join(sorted(relative)) if relative else "No files found."
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_file_ops.py -v`
Expected: All PASS

- [ ] **Step 5: Write failing tests for search**

```python
# tests/test_search.py
from agent.tools.search import search_content

def test_search_finds_matching_lines(tmp_codebase):
    result = search_content("interface", tmp_codebase)
    assert "sample.ts" in result
    assert "user.ts" in result

def test_search_returns_line_numbers(tmp_codebase):
    result = search_content("email", tmp_codebase)
    assert "user.ts" in result
    assert "email" in result

def test_search_no_matches(tmp_codebase):
    result = search_content("zzzznotfound", tmp_codebase)
    assert "no matches" in result.lower() or result.strip() == ""
```

- [ ] **Step 6: Implement search.py**

```python
# agent/tools/search.py
import os
import re

def search_content(pattern: str, directory: str, file_glob: str = "*") -> str:
    """Search file contents for a regex pattern. Returns matching lines with file paths and line numbers."""
    results = []
    for root, _dirs, files in os.walk(directory):
        for fname in files:
            if file_glob != "*" and not fname.endswith(file_glob.lstrip("*")):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r") as f:
                    for i, line in enumerate(f, 1):
                        if re.search(pattern, line):
                            rel = os.path.relpath(fpath, directory)
                            results.append(f"{rel}:{i}: {line.rstrip()}")
            except (UnicodeDecodeError, PermissionError):
                continue
    if not results:
        return "No matches found."
    return "\n".join(results)
```

- [ ] **Step 7: Run search tests**

Run: `cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_search.py -v`
Expected: All PASS

- [ ] **Step 8: Write failing tests for shell**

```python
# tests/test_shell.py
from agent.tools.shell import run_command

def test_run_command_success(tmp_codebase):
    result = run_command("echo hello", cwd=tmp_codebase)
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]

def test_run_command_failure(tmp_codebase):
    result = run_command("false", cwd=tmp_codebase)
    assert result["exit_code"] != 0

def test_run_command_captures_stderr(tmp_codebase):
    result = run_command("echo error >&2", cwd=tmp_codebase)
    assert "error" in result["stderr"]

def test_run_command_timeout(tmp_codebase):
    result = run_command("sleep 10", cwd=tmp_codebase, timeout=1)
    assert result["exit_code"] != 0
    assert "timeout" in result["stderr"].lower() or "timed out" in result["stderr"].lower()
```

- [ ] **Step 9: Implement shell.py**

```python
# agent/tools/shell.py
import subprocess

def run_command(command: str, cwd: str = ".", timeout: int = 60) -> dict:
    """Run a shell command and return stdout, stderr, exit_code."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "exit_code": -1,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
        }
```

- [ ] **Step 10: Run all tool tests**

Run: `cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_file_ops.py tests/test_search.py tests/test_shell.py -v`
Expected: All PASS

- [ ] **Step 11: Commit**

```bash
git add agent/tools/ tests/test_file_ops.py tests/test_search.py tests/test_shell.py
git commit -m "feat: file operations, search, and shell tools with full test coverage"
```

---

## Task 3: Editor Node with Anchor-Based Editing

**Files:**
- Create: `agent/prompts/__init__.py`
- Create: `agent/prompts/editor.py`
- Create: `agent/nodes/__init__.py`
- Create: `agent/nodes/editor.py`
- Create: `agent/nodes/validator.py`
- Create: `agent/tracing.py`
- Create: `tests/test_editor_node.py`
- Create: `tests/test_validator_node.py`

- [ ] **Step 1: Create shared LLM utility**

```python
# agent/llm.py
from anthropic import AsyncAnthropic

client = AsyncAnthropic()

async def call_llm(system: str, user: str, model: str = "claude-sonnet-4-20250514") -> str:
    """Call Claude and return the text response."""
    response = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text
```

- [ ] **Step 2: Write the local trace logger**

```python
# agent/tracing.py
import json
import os
from datetime import datetime, timezone

class TraceLogger:
    def __init__(self, trace_dir: str = "traces"):
        self.trace_dir = trace_dir
        os.makedirs(trace_dir, exist_ok=True)
        self.run_id: str | None = None
        self.entries: list[dict] = []

    def start_run(self, run_id: str):
        self.run_id = run_id
        self.entries = []

    def log(self, node: str, data: dict):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "node": node,
            "data": data,
        }
        self.entries.append(entry)

    def save(self):
        if not self.run_id:
            return
        path = os.path.join(self.trace_dir, f"{self.run_id}.json")
        with open(path, "w") as f:
            json.dump(self.entries, f, indent=2)

    def get_entries(self) -> list[dict]:
        return self.entries
```

- [ ] **Step 2: Write editor prompts**

```python
# agent/prompts/__init__.py
# Prompts package

# agent/prompts/editor.py
EDITOR_SYSTEM = """You are a surgical code editor. You make precise, targeted edits to files.

You will receive:
1. The full content of the file to edit (with line numbers)
2. An instruction describing what change to make

You must respond with a JSON object containing:
- "anchor": A unique string from the file that identifies exactly where to make the edit. Must appear exactly once in the file. Include 2-3 lines of surrounding context to ensure uniqueness.
- "replacement": The string that should replace the anchor. Include the same surrounding context lines, modified as needed.

Rules:
- The anchor MUST be an exact substring of the file content (including whitespace and newlines)
- The anchor MUST appear exactly once in the file
- Keep changes minimal — only modify what the instruction requires
- Preserve indentation and coding style
- Do NOT add unrelated changes

Respond with ONLY the JSON object, no other text."""

EDITOR_USER = """File: {file_path}

Content:
{file_content}

Instruction: {edit_instruction}

{context_section}

Respond with the JSON object containing "anchor" and "replacement"."""
```

- [ ] **Step 3: Write failing tests for editor node**

```python
# tests/test_editor_node.py
import json
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from agent.nodes.editor import editor_node
from agent.state import AgentState

@pytest.fixture
def sample_state(tmp_codebase):
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    content = open(ts_path).read()
    return AgentState(
        messages=[],
        instruction="Add a due_date field to the Issue interface",
        working_directory=tmp_codebase,
        context={},
        plan=["Add due_date field to Issue interface in sample.ts"],
        current_step=0,
        file_buffer={ts_path: content},
        edit_history=[],
        error_state=None,
    )

@pytest.mark.asyncio
async def test_editor_node_successful_edit(sample_state, tmp_codebase):
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    mock_response = json.dumps({
        "anchor": '  description: string;\n  status: "open" | "closed";',
        "replacement": '  description: string;\n  due_date: string;\n  status: "open" | "closed";',
    })

    with patch("agent.llm.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_response
        result = await editor_node(sample_state)

    assert result["error_state"] is None
    assert len(result["edit_history"]) == 1
    assert result["edit_history"][0]["file"] == ts_path
    content = open(ts_path).read()
    assert "due_date: string;" in content

@pytest.mark.asyncio
async def test_editor_node_anchor_not_found(sample_state):
    mock_response = json.dumps({
        "anchor": "this does not exist in the file",
        "replacement": "whatever",
    })

    with patch("agent.llm.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_response
        result = await editor_node(sample_state)

    assert result["error_state"] is not None
    assert "not found" in result["error_state"].lower()
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_editor_node.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 5: Implement the editor node**

```python
# agent/nodes/__init__.py
# Nodes package

# agent/nodes/editor.py
import json
import os
from agent.prompts.editor import EDITOR_SYSTEM, EDITOR_USER
from agent.tools.file_ops import edit_file, read_file
from agent.llm import call_llm
from agent.tracing import TraceLogger

tracer = TraceLogger()

async def editor_node(state: dict) -> dict:
    """Perform an anchor-based surgical edit on a file."""
    plan = state["plan"]
    step = state["current_step"]
    instruction = plan[step] if step < len(plan) else state["instruction"]
    working_dir = state["working_directory"]

    # Determine which file to edit from the file_buffer
    # Use the first file in the buffer (reader should have populated the right one)
    file_buffer = state["file_buffer"]
    if not file_buffer:
        return {**state, "error_state": "No files in buffer. Run reader first."}

    file_path = list(file_buffer.keys())[0]
    file_content = file_buffer[file_path]

    # Build context section
    context_section = ""
    if state.get("context"):
        ctx = state["context"]
        if ctx.get("schema"):
            context_section += f"\nRelevant schema:\n{ctx['schema']}\n"
        if ctx.get("spec"):
            context_section += f"\nSpec:\n{ctx['spec']}\n"

    # Call LLM to get anchor and replacement
    numbered_content = "\n".join(
        f"{i+1}: {line}" for i, line in enumerate(file_content.split("\n"))
    )
    user_prompt = EDITOR_USER.format(
        file_path=file_path,
        file_content=numbered_content,
        edit_instruction=instruction,
        context_section=context_section,
    )

    response = await call_llm(EDITOR_SYSTEM, user_prompt)

    # Parse the response
    try:
        # Handle markdown code blocks
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        edit_data = json.loads(text)
        anchor = edit_data["anchor"]
        replacement = edit_data["replacement"]
    except (json.JSONDecodeError, KeyError) as e:
        return {
            "error_state": f"Failed to parse editor response: {e}\nResponse: {response[:500]}",
            "edit_history": state["edit_history"],
        }

    # Apply the edit
    result = edit_file(file_path, anchor, replacement)

    if not result["success"]:
        tracer.log("editor", {
            "file": file_path,
            "anchor": anchor[:100],
            "result": "failed",
            "error": result["error"],
        })
        return {
            "error_state": result["error"],
            "edit_history": state["edit_history"],
        }

    # Success — update state
    edit_entry = {
        "file": file_path,
        "anchor": anchor,
        "replacement": replacement,
        "snapshot": result["snapshot"],
    }
    new_history = state["edit_history"] + [edit_entry]

    # Update file buffer with new content
    new_content = open(file_path).read()
    new_buffer = {**file_buffer, file_path: new_content}

    tracer.log("editor", {
        "file": file_path,
        "anchor": anchor[:100],
        "result": "success",
    })

    return {
        "error_state": None,
        "edit_history": new_history,
        "file_buffer": new_buffer,
    }
```

- [ ] **Step 6: Run editor tests**

Run: `cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_editor_node.py -v`
Expected: All PASS

- [ ] **Step 7: Write failing tests for validator node**

```python
# tests/test_validator_node.py
import os
import pytest
from agent.nodes.validator import validator_node

@pytest.fixture
def valid_edit_state(tmp_codebase):
    ts_path = os.path.join(tmp_codebase, "sample.ts")
    return {
        "messages": [],
        "instruction": "Add due_date",
        "working_directory": tmp_codebase,
        "context": {},
        "plan": ["Add due_date"],
        "current_step": 0,
        "file_buffer": {ts_path: open(ts_path).read()},
        "edit_history": [{"file": ts_path, "snapshot": open(ts_path).read()}],
        "error_state": None,
    }

def test_validator_passes_valid_file(valid_edit_state, tmp_codebase):
    result = validator_node(valid_edit_state)
    assert result["error_state"] is None

def test_validator_catches_invalid_json(tmp_codebase):
    json_path = os.path.join(tmp_codebase, "config.json")
    # Break the JSON
    with open(json_path, "w") as f:
        f.write('{"port": 3000,}')  # trailing comma = invalid
    state = {
        "messages": [],
        "instruction": "test",
        "working_directory": tmp_codebase,
        "context": {},
        "plan": [],
        "current_step": 0,
        "file_buffer": {json_path: open(json_path).read()},
        "edit_history": [{"file": json_path, "snapshot": '{"port": 3000}'}],
        "error_state": None,
    }
    result = validator_node(state)
    assert result["error_state"] is not None
```

- [ ] **Step 8: Implement validator node**

```python
# agent/nodes/validator.py
import json
import os
import subprocess
from agent.tracing import TraceLogger

tracer = TraceLogger()

def _syntax_check(file_path: str) -> dict:
    """Run a language-appropriate syntax check."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".json":
        try:
            with open(file_path) as f:
                json.load(f)
            return {"valid": True, "error": None}
        except json.JSONDecodeError as e:
            return {"valid": False, "error": str(e)}

    if ext in (".ts", ".tsx"):
        # Try esbuild for fast syntax check, fall back to tsc
        result = subprocess.run(
            ["npx", "esbuild", "--bundle", "--write=false", file_path],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return {"valid": False, "error": result.stderr[:500]}
        return {"valid": True, "error": None}

    if ext in (".js", ".jsx"):
        result = subprocess.run(
            ["node", "--check", file_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return {"valid": False, "error": result.stderr[:500]}
        return {"valid": True, "error": None}

    if ext in (".yaml", ".yml"):
        try:
            import yaml
            with open(file_path) as f:
                yaml.safe_load(f)
            return {"valid": True, "error": None}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    # For .md, .sh, .css — skip syntax check
    return {"valid": True, "error": None}

def _rollback(edit_entry: dict):
    """Restore a file from its snapshot."""
    with open(edit_entry["file"], "w") as f:
        f.write(edit_entry["snapshot"])

def validator_node(state: dict) -> dict:
    """Validate the most recent edit. Rollback if syntax check fails."""
    edit_history = state["edit_history"]
    if not edit_history:
        return {"error_state": None}

    last_edit = edit_history[-1]
    file_path = last_edit["file"]

    check = _syntax_check(file_path)

    tracer.log("validator", {
        "file": file_path,
        "syntax_valid": check["valid"],
        "error": check["error"],
    })

    if not check["valid"]:
        _rollback(last_edit)
        return {
            "error_state": f"Syntax check failed for {file_path}: {check['error']}. Edit rolled back.",
        }

    return {"error_state": None}
```

- [ ] **Step 9: Run validator tests**

Run: `cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_validator_node.py -v`
Expected: All PASS

- [ ] **Step 10: Commit**

```bash
git add agent/nodes/ agent/prompts/ agent/tracing.py tests/test_editor_node.py tests/test_validator_node.py
git commit -m "feat: editor node with anchor-based editing, validator with syntax checks, trace logging"
```

---

## Task 4: Core Graph (Persistent Loop)

**Files:**
- Create: `agent/nodes/receive.py`
- Create: `agent/nodes/planner.py`
- Create: `agent/nodes/executor.py`
- Create: `agent/nodes/reporter.py`
- Create: `agent/nodes/reader.py`
- Create: `agent/prompts/planner.py`
- Create: `agent/graph.py`
- Create: `tests/test_graph.py`

- [ ] **Step 1: Write planner prompts**

```python
# agent/prompts/planner.py
PLANNER_SYSTEM = """You are a coding task planner. Given an instruction and optional context, break the work into a sequence of concrete steps.

Each step should be a single, specific action like:
- "Read file api/src/routes/issues.ts to understand the current structure"
- "Edit api/src/models/issue.ts to add due_date column"
- "Run tests with: pnpm test"

Output a JSON object:
- "steps": A list of step strings, in execution order
- "parallel_groups": Optional. Groups of step indices that can run in parallel. e.g. [[2,3]] means steps 2 and 3 can run together.
- "files_to_read": List of file paths to read before starting

Respond with ONLY the JSON object."""

PLANNER_USER = """Working directory: {working_directory}

Instruction: {instruction}

{context_section}

Available files (top-level):
{file_listing}

Respond with the JSON plan."""
```

- [ ] **Step 2: Implement receive, planner, reader, executor, reporter nodes**

```python
# agent/nodes/receive.py
from agent.tracing import TraceLogger

tracer = TraceLogger()

def receive_instruction_node(state: dict) -> dict:
    """Entry point — accepts instruction and optional context."""
    tracer.log("receive_instruction", {
        "instruction": state.get("instruction", ""),
        "has_context": bool(state.get("context")),
    })
    return {
        "current_step": 0,
        "error_state": None,
    }
```

```python
# agent/nodes/reader.py
import os
from agent.tools.file_ops import read_file
from agent.tracing import TraceLogger

tracer = TraceLogger()

def reader_node(state: dict) -> dict:
    """Read files into the file_buffer."""
    plan = state.get("plan", [])
    step = state.get("current_step", 0)
    working_dir = state["working_directory"]
    file_buffer = dict(state.get("file_buffer", {}))

    # Determine files to read from context hints or plan step
    files_to_read = []

    # Check context for file hints
    context = state.get("context", {})
    if context.get("files"):
        files_to_read.extend(context["files"])

    # If no hints, try to extract file paths from the current plan step
    if step < len(plan):
        step_text = plan[step]
        # Simple heuristic: look for paths with extensions
        for word in step_text.split():
            word = word.strip("'\"`,")
            if "/" in word and "." in word.split("/")[-1]:
                full_path = os.path.join(working_dir, word) if not os.path.isabs(word) else word
                if os.path.exists(full_path):
                    files_to_read.append(full_path)

    # Read each file into the buffer
    for fpath in files_to_read:
        if not os.path.isabs(fpath):
            fpath = os.path.join(working_dir, fpath)
        if os.path.exists(fpath):
            with open(fpath, "r") as f:
                file_buffer[fpath] = f.read()
            tracer.log("reader", {"file": fpath, "lines": file_buffer[fpath].count("\n") + 1})

    return {"file_buffer": file_buffer}
```

```python
# agent/nodes/executor.py
from agent.tools.shell import run_command
from agent.tracing import TraceLogger

tracer = TraceLogger()

def executor_node(state: dict) -> dict:
    """Run a shell command from the current plan step."""
    plan = state.get("plan", [])
    step = state.get("current_step", 0)
    working_dir = state["working_directory"]

    if step >= len(plan):
        return {"error_state": None}

    step_text = plan[step]

    # Extract command — look for text after "Run:" or "run:" or the whole step
    command = step_text
    for prefix in ["Run:", "run:", "Execute:", "execute:"]:
        if prefix in step_text:
            command = step_text.split(prefix, 1)[1].strip()
            break

    result = run_command(command, cwd=working_dir)

    tracer.log("executor", {
        "command": command,
        "exit_code": result["exit_code"],
        "stdout_preview": result["stdout"][:200],
        "stderr_preview": result["stderr"][:200],
    })

    if result["exit_code"] != 0:
        return {
            "error_state": f"Command failed (exit {result['exit_code']}): {result['stderr'][:500]}",
        }

    return {"error_state": None}
```

```python
# agent/nodes/reporter.py
from agent.tracing import TraceLogger

tracer = TraceLogger()

def reporter_node(state: dict) -> dict:
    """Summarize what was done and surface errors."""
    edit_history = state.get("edit_history", [])
    error_state = state.get("error_state")
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)

    # Determine status
    if error_state is None:
        status = "completed"
    elif current_step < len(plan):
        status = "waiting_for_human"  # Paused mid-plan due to errors
    else:
        status = "failed"

    summary = {
        "steps_completed": current_step,
        "total_steps": len(plan),
        "edits_made": len(edit_history),
        "files_edited": list(set(e["file"] for e in edit_history)),
        "error": error_state,
        "status": status,
    }

    tracer.log("reporter", summary)
    tracer.save()

    return {"error_state": error_state}
```

- [ ] **Step 3: Implement planner node**

```python
# agent/nodes/planner.py
import json
from agent.prompts.planner import PLANNER_SYSTEM, PLANNER_USER
from agent.tools.file_ops import list_files
from agent.llm import call_llm
from agent.tracing import TraceLogger

tracer = TraceLogger()

async def planner_node(state: dict) -> dict:
    """Break an instruction into a step-by-step plan."""
    instruction = state["instruction"]
    working_dir = state["working_directory"]
    context = state.get("context", {})

    # Build context section
    context_section = ""
    if context.get("spec"):
        context_section += f"\nSpec:\n{context['spec']}\n"
    if context.get("schema"):
        context_section += f"\nSchema:\n{context['schema']}\n"
    if context.get("previous_output"):
        context_section += f"\nPrevious output:\n{context['previous_output']}\n"

    # Get top-level file listing
    file_listing = list_files(working_dir, "*")

    user_prompt = PLANNER_USER.format(
        working_directory=working_dir,
        instruction=instruction,
        context_section=context_section,
        file_listing=file_listing[:2000],  # Truncate if too long
    )

    response = await call_llm(PLANNER_SYSTEM, user_prompt)

    try:
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        plan_data = json.loads(text)
        steps = plan_data["steps"]
        files_to_read = plan_data.get("files_to_read", [])
    except (json.JSONDecodeError, KeyError) as e:
        tracer.log("planner", {"error": f"Failed to parse: {e}"})
        return {
            "plan": [instruction],  # Fallback: treat the whole instruction as one step
            "error_state": f"Planner parse error: {e}",
        }

    # Pre-populate file buffer with hinted files
    file_buffer = dict(state.get("file_buffer", {}))
    import os
    for fpath in files_to_read:
        if not os.path.isabs(fpath):
            fpath = os.path.join(working_dir, fpath)
        if os.path.exists(fpath):
            with open(fpath) as f:
                file_buffer[fpath] = f.read()

    tracer.log("planner", {"steps": steps, "files_to_read": files_to_read})

    return {
        "plan": steps,
        "current_step": 0,
        "file_buffer": file_buffer,
    }
```

- [ ] **Step 4: Wire up the StateGraph**

```python
# agent/graph.py
from langgraph.graph import StateGraph, END, Send
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from agent.state import AgentState
from agent.nodes.receive import receive_instruction_node
from agent.nodes.planner import planner_node
from agent.nodes.reader import reader_node
from agent.nodes.editor import editor_node
from agent.nodes.executor import executor_node
from agent.nodes.validator import validator_node
from agent.nodes.coordinator import coordinator_node
from agent.nodes.merger import merger_node
from agent.nodes.reporter import reporter_node

def _retry_count(state: dict) -> int:
    """Count consecutive errors in edit_history."""
    count = 0
    for entry in reversed(state.get("edit_history", [])):
        if entry.get("error"):
            count += 1
        else:
            break
    return count

def should_continue(state: dict) -> str:
    """Decide next node after validator or executor."""
    error = state.get("error_state")
    plan = state.get("plan", [])
    step = state.get("current_step", 0)

    if error:
        if _retry_count(state) >= 3:
            return "reporter"  # Surface to human (waiting_for_human)
        return "reader"  # Retry

    if step + 1 < len(plan):
        return "advance"
    return "reporter"

def advance_step(state: dict) -> dict:
    return {"current_step": state["current_step"] + 1}

def classify_step(state: dict) -> str:
    """Route current step to the right node."""
    plan = state.get("plan", [])
    step = state.get("current_step", 0)
    if step >= len(plan):
        return "reporter"

    step_text = plan[step].lower()
    if any(kw in step_text for kw in ["run ", "execute", "test", "build", "install"]):
        return "executor"
    if any(kw in step_text for kw in ["read ", "understand", "examine", "check "]):
        return "reader_only"
    return "reader_then_edit"

def after_reader(state: dict) -> str:
    """Route after reader: edit or advance (read-only step)."""
    plan = state.get("plan", [])
    step = state.get("current_step", 0)
    if step >= len(plan):
        return "advance"
    step_text = plan[step].lower()
    if any(kw in step_text for kw in ["read ", "understand", "examine", "check "]):
        return "advance"  # Read-only step — skip editor
    return "editor"

def after_planner(state: dict) -> str | list[Send]:
    """After planning, check if coordinator flags parallel work."""
    if state.get("is_parallel") and state.get("parallel_batches"):
        # Fan out via Send API — each batch gets its own subgraph invocation
        sends = []
        for batch in state["parallel_batches"]:
            batch_plan = [state["plan"][i] for i in batch if i < len(state["plan"])]
            sends.append(Send("subgraph_worker", {
                **state,
                "plan": batch_plan,
                "current_step": 0,
                "edit_history": [],
                "is_parallel": False,
                "parallel_batches": [],
            }))
        return sends
    return "classify"

def _build_graph_nodes(graph: StateGraph):
    """Shared graph construction — avoids duplication."""
    graph.add_node("receive", receive_instruction_node)
    graph.add_node("planner", planner_node)
    graph.add_node("coordinator", coordinator_node)
    graph.add_node("reader", reader_node)
    graph.add_node("editor", editor_node)
    graph.add_node("executor", executor_node)
    graph.add_node("validator", validator_node)
    graph.add_node("merger", merger_node)
    graph.add_node("reporter", reporter_node)
    graph.add_node("advance", advance_step)
    graph.add_node("classify", lambda s: {})  # Passthrough for routing

    # Subgraph worker: runs reader→editor→validator loop sequentially for a batch
    async def subgraph_worker(state: dict) -> dict:
        """Execute a batch of plan steps: reader → editor → validator per step."""
        plan = state.get("plan", [])
        all_edits = list(state.get("edit_history", []))
        file_buffer = dict(state.get("file_buffer", {}))

        for i in range(len(plan)):
            step_state = {**state, "current_step": i, "file_buffer": file_buffer, "edit_history": all_edits}
            # Read
            read_result = reader_node(step_state)
            file_buffer.update(read_result.get("file_buffer", {}))
            step_state["file_buffer"] = file_buffer
            # Edit
            edit_result = await editor_node(step_state)
            if edit_result.get("error_state"):
                return {"edit_history": all_edits, "error_state": edit_result["error_state"]}
            all_edits = edit_result.get("edit_history", all_edits)
            file_buffer.update(edit_result.get("file_buffer", {}))
            # Validate
            val_state = {**step_state, "edit_history": all_edits}
            val_result = validator_node(val_state)
            if val_result.get("error_state"):
                return {"edit_history": all_edits, "error_state": val_result["error_state"]}

        return {"edit_history": all_edits, "file_buffer": file_buffer, "error_state": None}

    graph.add_node("subgraph_worker", subgraph_worker)

    graph.set_entry_point("receive")

    # receive → planner → coordinator → after_planner (parallel or sequential)
    graph.add_edge("receive", "planner")
    graph.add_edge("planner", "coordinator")
    graph.add_conditional_edges("coordinator", after_planner, {
        "classify": "classify",
        # Send objects route to subgraph_worker automatically
    })

    # classify → route to correct node
    graph.add_conditional_edges("classify", classify_step, {
        "executor": "executor",
        "reader_only": "reader",
        "reader_then_edit": "reader",
        "reporter": "reporter",
    })

    # reader → after_reader (edit or advance based on step type)
    graph.add_conditional_edges("reader", after_reader, {
        "editor": "editor",
        "advance": "advance",
    })

    # editor → validator
    graph.add_edge("editor", "validator")

    # subgraph_worker → merger (collects parallel results)
    graph.add_edge("subgraph_worker", "merger")
    graph.add_edge("merger", "reporter")

    # executor → should_continue
    graph.add_conditional_edges("executor", should_continue, {
        "reader": "reader",
        "advance": "advance",
        "reporter": "reporter",
    })

    # validator → should_continue
    graph.add_conditional_edges("validator", should_continue, {
        "reader": "reader",
        "advance": "advance",
        "reporter": "reporter",
    })

    # advance → classify next step
    graph.add_edge("advance", "classify")

    # reporter → END
    graph.add_edge("reporter", END)

def build_graph():
    """Build the Shipyard agent graph (no persistence)."""
    graph = StateGraph(AgentState)
    _build_graph_nodes(graph)
    return graph.compile()

async def build_persistent_graph(db_path: str = "shipyard_state.db"):
    """Build graph with SQLite checkpointing for persistent loop."""
    graph = StateGraph(AgentState)
    _build_graph_nodes(graph)
    async with AsyncSqliteSaver.from_conn_string(db_path) as checkpointer:
        return graph.compile(checkpointer=checkpointer)
```

- [ ] **Step 5: Write integration test for the graph**

```python
# tests/test_graph.py
import pytest
from agent.graph import build_graph

def test_graph_compiles():
    """Verify the graph compiles without errors."""
    graph = build_graph()
    assert graph is not None

def test_graph_has_expected_nodes():
    graph = build_graph()
    # Graph should have all our nodes
    node_names = set(graph.get_graph().nodes.keys())
    expected = {"receive", "planner", "coordinator", "reader", "editor", "executor", "validator", "merger", "reporter", "advance", "classify"}
    # LangGraph adds __start__ and __end__
    assert expected.issubset(node_names)
```

- [ ] **Step 6: Run graph tests**

Run: `cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_graph.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add agent/nodes/ agent/prompts/ agent/graph.py tests/test_graph.py
git commit -m "feat: core agent graph with planner, reader, editor, executor, validator, reporter nodes"
```

---

## Task 5: FastAPI Server (Persistent Loop)

**Files:**
- Create: `server/__init__.py`
- Create: `server/main.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write failing tests for the server**

```python
# tests/test_server.py
import json
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from server.main import app

@pytest.mark.asyncio
async def test_health_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_submit_instruction():
    """Test instruction submission (mocks the graph execution)."""
    mock_result = {
        "error_state": None,
        "edit_history": [],
        "plan": ["test"],
        "current_step": 1,
    }
    with patch("server.main.app.state") as mock_state:
        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = mock_result
        mock_state.graph = mock_graph

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/instruction", json={
                "instruction": "Read the README",
                "working_directory": "/tmp",
                "context": {},
            })
            assert response.status_code == 200
            data = response.json()
            assert "run_id" in data

@pytest.mark.asyncio
async def test_get_status_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/status/nonexistent")
        assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_server.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the FastAPI server**

```python
# server/__init__.py
# Server package

# server/main.py
import uuid
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agent.graph import build_graph

# Store for run state
runs: dict[str, dict] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: build the graph once
    app.state.graph = build_graph()
    yield
    # Shutdown: cleanup

app = FastAPI(title="Shipyard Agent", lifespan=lifespan)

class InstructionRequest(BaseModel):
    instruction: str
    working_directory: str
    context: dict = {}

class InstructionResponse(BaseModel):
    run_id: str
    status: str

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/instruction", response_model=InstructionResponse)
async def submit_instruction(req: InstructionRequest):
    run_id = str(uuid.uuid4())[:8]
    runs[run_id] = {"status": "running", "result": None}

    # Run graph in background
    async def execute():
        try:
            graph = app.state.graph
            initial_state = {
                "messages": [],
                "instruction": req.instruction,
                "working_directory": req.working_directory,
                "context": req.context,
                "plan": [],
                "current_step": 0,
                "file_buffer": {},
                "edit_history": [],
                "error_state": None,
                "is_parallel": False,
                "parallel_batches": [],
                "sequential_first": [],
                "has_conflicts": False,
            }
            result = await graph.ainvoke(initial_state)
            runs[run_id] = {
                "status": "completed" if result.get("error_state") is None else "failed",
                "result": result,
            }
        except Exception as e:
            runs[run_id] = {"status": "error", "result": str(e)}

    asyncio.create_task(execute())
    return InstructionResponse(run_id=run_id, status="running")

@app.get("/status/{run_id}")
async def get_status(run_id: str):
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")
    run = runs[run_id]
    return {
        "run_id": run_id,
        "status": run["status"],
        "result": run.get("result"),
    }

@app.post("/instruction/{run_id}")
async def continue_run(run_id: str, req: InstructionRequest):
    """Continue a paused run with human input."""
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")
    # Update instruction and re-run
    runs[run_id]["status"] = "running"

    async def execute():
        try:
            graph = app.state.graph
            state = runs[run_id].get("result", {})
            state["instruction"] = req.instruction
            state["context"] = req.context
            state["error_state"] = None
            result = await graph.ainvoke(state)
            runs[run_id] = {
                "status": "completed" if result.get("error_state") is None else "failed",
                "result": result,
            }
        except Exception as e:
            runs[run_id] = {"status": "error", "result": str(e)}

    asyncio.create_task(execute())
    return {"run_id": run_id, "status": "running"}
```

- [ ] **Step 4: Run server tests**

Run: `cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_server.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add server/ tests/test_server.py
git commit -m "feat: FastAPI server with POST /instruction, GET /status, POST /instruction/{run_id}"
```

---

## Task 6: Multi-Agent Coordination

**Files:**
- Create: `agent/nodes/coordinator.py`
- Create: `agent/nodes/merger.py`
- Create: `agent/prompts/coordinator.py`
- Create: `tests/test_multiagent.py`

- [ ] **Step 1: Write coordinator prompts**

```python
# agent/prompts/coordinator.py
COORDINATOR_SYSTEM = """You are a task coordinator. Given a list of steps with dependency markers, decide which steps can run in parallel.

Output a JSON object:
- "parallel_batches": A list of batches. Each batch is a list of step indices that can run concurrently.
- "sequential": A list of step indices that must run one at a time, in order.

Steps that modify the same file or depend on each other must be sequential.
Steps that modify different files/directories can be parallel.

Respond with ONLY the JSON object."""

COORDINATOR_USER = """Steps:
{steps}

Working directory structure:
{structure}

Respond with the JSON coordination plan."""
```

- [ ] **Step 2: Write failing tests for coordinator**

```python
# tests/test_multiagent.py
import pytest
from agent.nodes.coordinator import coordinator_node
from agent.nodes.merger import merger_node

def test_coordinator_identifies_parallel_tasks():
    state = {
        "messages": [],
        "instruction": "Update API and Web",
        "working_directory": "/tmp",
        "context": {},
        "plan": [
            "Edit api/src/routes/issues.ts to add endpoint",
            "Edit web/src/pages/Issues.tsx to add form field",
        ],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
    }
    # Coordinator should recognize these as parallelizable (different directories)
    result = coordinator_node(state)
    assert result["is_parallel"] is True
    assert "parallel_batches" in result
    assert len(result["parallel_batches"]) == 2  # api batch + web batch

def test_merger_no_conflicts():
    state = {
        "edit_history": [
            {"file": "api/route.ts", "anchor": "a", "replacement": "b", "snapshot": "old"},
            {"file": "web/page.tsx", "anchor": "c", "replacement": "d", "snapshot": "old2"},
        ],
    }
    result = merger_node(state)
    assert result["has_conflicts"] is False

def test_merger_detects_same_file_conflict():
    state = {
        "edit_history": [
            {"file": "shared/types.ts", "anchor": "a", "replacement": "b", "snapshot": "old"},
            {"file": "shared/types.ts", "anchor": "c", "replacement": "d", "snapshot": "old"},
        ],
    }
    result = merger_node(state)
    assert result["has_conflicts"] is True
```

- [ ] **Step 3: Implement coordinator node**

```python
# agent/nodes/coordinator.py
from agent.tracing import TraceLogger

tracer = TraceLogger()

def coordinator_node(state: dict) -> dict:
    """Decide whether to fan out to parallel subgraphs or run sequentially."""
    plan = state.get("plan", [])

    if len(plan) < 2:
        return {"is_parallel": False, "batches": []}

    # Simple heuristic: group steps by directory prefix
    # Steps targeting different top-level dirs (api/, web/, shared/) can parallelize
    dir_groups: dict[str, list[int]] = {}
    for i, step in enumerate(plan):
        step_lower = step.lower()
        if "api/" in step_lower:
            dir_groups.setdefault("api", []).append(i)
        elif "web/" in step_lower:
            dir_groups.setdefault("web", []).append(i)
        elif "shared/" in step_lower:
            dir_groups.setdefault("shared", []).append(i)
        else:
            dir_groups.setdefault("other", []).append(i)

    # shared/ must run first (both api and web depend on it)
    sequential = dir_groups.pop("shared", [])
    other = dir_groups.pop("other", [])

    # Remaining groups can run in parallel
    parallel_batch = []
    for group_steps in dir_groups.values():
        if group_steps:
            parallel_batch.append(group_steps)

    is_parallel = len(parallel_batch) > 1

    tracer.log("coordinator", {
        "is_parallel": is_parallel,
        "sequential": sequential + other,
        "parallel_batch": parallel_batch,
    })

    return {
        "is_parallel": is_parallel,
        "parallel_batches": parallel_batch,
        "sequential_first": sequential + other,
    }
```

- [ ] **Step 4: Implement merger node**

```python
# agent/nodes/merger.py
from agent.tracing import TraceLogger

tracer = TraceLogger()

def merger_node(state: dict) -> dict:
    """Merge outputs from parallel subgraphs.

    LangGraph's Send API collects subgraph results into the parent state
    via the state reducer (add_messages pattern). The edit_history from
    each subgraph is already merged into state by the time merger runs.
    Merger's job is to detect file conflicts in the combined history.
    """
    edit_history = state.get("edit_history", [])
    all_files = [e["file"] for e in edit_history]
    has_conflicts = False

    seen_files = set()
    for f in all_files:
        if f in seen_files:
            has_conflicts = True
            break
        seen_files.add(f)

    tracer.log("merger", {
        "total_edits": len(edit_history),
        "files": list(seen_files),
        "has_conflicts": has_conflicts,
    })

    return {"has_conflicts": has_conflicts}
```

- [ ] **Step 5: Run multi-agent tests**

Run: `cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_multiagent.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add agent/nodes/coordinator.py agent/nodes/merger.py agent/prompts/coordinator.py tests/test_multiagent.py
git commit -m "feat: multi-agent coordination with directory-based parallelization and merger"
```

---

## Task 7: End-to-End Integration & CODEAGENT.md

**Files:**
- Create: `CODEAGENT.md`
- Modify: `tests/test_graph.py` (add e2e test)

- [ ] **Step 1: Write an end-to-end integration test**

```python
# Append to tests/test_graph.py

@pytest.mark.asyncio
@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="Requires API key")
async def test_end_to_end_edit(tmp_codebase):
    """Full integration: instruct the agent to add a field, verify it works."""
    from agent.graph import build_graph

    graph = build_graph()
    result = await graph.ainvoke({
        "messages": [],
        "instruction": "Add a 'priority: string;' field to the Issue interface in sample.ts",
        "working_directory": tmp_codebase,
        "context": {"files": [os.path.join(tmp_codebase, "sample.ts")]},
        "plan": [],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
    })

    # Check the file was edited
    content = open(os.path.join(tmp_codebase, "sample.ts")).read()
    assert "priority: string;" in content or "priority" in content
    assert result.get("error_state") is None
```

- [ ] **Step 2: Run e2e test (requires ANTHROPIC_API_KEY)**

Run: `cd /Users/rohanthomas/Shipyard && python -m pytest tests/test_graph.py::test_end_to_end_edit -v`
Expected: PASS (if API key is set)

- [ ] **Step 3: Create CODEAGENT.md template**

```markdown
# CODEAGENT.md

## Agent Architecture (MVP)

Shipyard uses a single LangGraph StateGraph with the following nodes wired in sequence:

`receive_instruction → planner → [reader → editor → validator] (loop per step) → reporter`

**State:** `AgentState` TypedDict with messages, instruction, working_directory, context, plan, current_step, file_buffer, edit_history, error_state.

**Entry condition:** POST /instruction with instruction + optional context
**Normal exit:** All plan steps completed, validator passes on each
**Error exit:** 3 consecutive failures on same step → reporter surfaces to human

**Loop design:** FastAPI server keeps the graph alive. SQLite checkpointer persists state. New instructions create or continue threads.

## File Editing Strategy (MVP)

**Strategy:** Anchor-based replacement (same pattern as Claude Code and OpenCode)

**Mechanism:**
1. Reader loads target file into file_buffer
2. Editor LLM produces (anchor, replacement) JSON
3. Agent validates anchor uniqueness: `file_content.count(anchor) == 1`
4. Snapshot saved to edit_history
5. `content.replace(anchor, replacement, 1)` applied
6. Validator runs language-appropriate syntax check
7. If syntax fails → rollback from snapshot, retry with error context (max 3)

**When it gets the location wrong:** Validator detects intent mismatch, rollback triggers, reader re-runs to find correct file.

## Multi-Agent Design (MVP)

**Orchestration:** Coordinator node groups plan steps by directory prefix (api/, web/, shared/). Steps targeting different directories run as parallel subgraphs via LangGraph Send API. shared/ always runs first (dependency).

**Communication:** Subgraphs don't communicate directly. Each writes to isolated edit_log. Merger collects all logs and checks for file conflicts.

**Conflict resolution:** Different files → merge directly. Same file, different anchors → apply sequentially. Overlapping regions → flag to human.

## Trace Links (MVP)

- Trace 1 (normal run): [link to LangSmith trace]
- Trace 2 (error/recovery path): [link to LangSmith trace]

## Architecture Decisions (Final Submission)

_To be filled after Ship rebuild._

## Ship Rebuild Log (Final Submission)

_To be filled during Ship rebuild._

## Comparative Analysis (Final Submission)

_To be filled after Ship rebuild._

## Cost Analysis (Final Submission)

| Item | Amount |
|------|--------|
| Claude API — input tokens | |
| Claude API — output tokens | |
| Total invocations during development | |
| Total development spend | |

| 100 Users | 1,000 Users | 10,000 Users |
|-----------|-------------|--------------|
| $___/month | $___/month | $___/month |

**Assumptions:**
- Average agent invocations per user per day:
- Average tokens per invocation (input / output):
- Cost per invocation:
```

- [ ] **Step 4: Write README.md**

```markdown
# Shipyard — Autonomous Coding Agent

An AI coding agent that makes surgical file edits, coordinates multiple sub-agents, and accepts injected context.

## Setup

```bash
# Clone and install
git clone <repo-url>
cd Shipyard
pip install -e ".[dev]"

# Set environment variables
cp .env.example .env
# Edit .env with your API keys

# Run tests
python -m pytest tests/ -v

# Start the server
uvicorn server.main:app --reload --port 8000
```

## Usage

```bash
# Submit an instruction
curl -X POST http://localhost:8000/instruction \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "Add a due_date field to the Issue model",
    "working_directory": "/path/to/ship",
    "context": {"files": ["api/src/models/issue.ts"]}
  }'

# Check status
curl http://localhost:8000/status/<run_id>
```

## Architecture

See [PRESEARCH.md](PRESEARCH.md) for full architecture design and [CODEAGENT.md](CODEAGENT.md) for implementation details.

**Stack:** Python 3.12+, LangGraph, Claude (Anthropic SDK), FastAPI, LangSmith

**File editing:** Anchor-based replacement — find a unique string, replace it. No line numbers, no AST parsing.

**Multi-agent:** Directory-based parallelization via LangGraph subgraphs. api/ and web/ edits run concurrently.
```

- [ ] **Step 5: Run full test suite**

Run: `cd /Users/rohanthomas/Shipyard && python -m pytest tests/ -v --ignore=tests/test_graph.py`
Expected: All unit tests PASS (e2e test requires API key)

- [ ] **Step 6: Commit**

```bash
git add CODEAGENT.md README.md tests/test_graph.py
git commit -m "feat: CODEAGENT.md template, README, end-to-end integration test"
```

---

## Summary

| Task | What It Delivers | Tests |
|------|-----------------|-------|
| 1. Project Setup | AgentState, deps, fixtures | test_state.py |
| 2. File Tools | read, edit, search, shell | test_file_ops, test_search, test_shell |
| 3. Editor Node | Anchor-based editing + validation + rollback | test_editor_node, test_validator_node |
| 4. Core Graph | Full LangGraph StateGraph wiring | test_graph |
| 5. FastAPI Server | Persistent loop, 3 endpoints | test_server |
| 6. Multi-Agent | Coordinator + merger | test_multiagent |
| 7. Integration | E2E test, CODEAGENT.md, README | test_graph (e2e) |

After Task 7, the MVP requirements are met: persistent loop, surgical editing, context injection, tracing, PRESEARCH.md, CODEAGENT.md, accessible via GitHub.
