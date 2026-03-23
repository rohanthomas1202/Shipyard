# Shipyard — Autonomous Coding Agent

An AI coding agent that makes surgical file edits, coordinates multiple sub-agents, and accepts injected context.

## Setup

```bash
git clone <repo-url>
cd Shipyard
pip install -e ".[dev]"
cp .env.example .env
# Edit .env with your API keys
```

## Run Tests

```bash
python3 -m pytest tests/ -v
```

## Start the Server

```bash
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

**Stack:** Python 3.11+, LangGraph, Claude (Anthropic SDK), FastAPI, LangSmith

**File editing:** Anchor-based replacement — find a unique string, replace it. No line numbers, no AST parsing.

**Multi-agent:** Directory-based parallelization via LangGraph. api/ and web/ edits can run concurrently.
