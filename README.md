<div align="center">

# Shipyard

**Autonomous AI Coding Agent**

An API-driven coding agent that breaks down instructions into multi-step plans, makes surgical file edits, and coordinates parallel sub-agents — all with human approval gates.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.1-1C3C3C?logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

</div>

---

## Why Shipyard?

Most AI coding tools work as chat assistants — they suggest code, you copy-paste it. Shipyard is different. It's a **persistent, stateful agent** that:

- **Plans before it edits** — breaks instructions into typed steps with complexity markers
- **Edits surgically** — uses anchor-based string replacement, not line numbers or AST parsing
- **Runs in parallel** — groups edits by directory and executes independent changes concurrently
- **Asks before applying** — optional human approval gates for supervised workflows
- **Recovers from errors** — automatic rollback on syntax failures with retry (up to 3 attempts)
- **Streams everything** — real-time WebSocket events with reconnection replay

---

## Table of Contents

- [Quick Start](#quick-start)
- [Usage](#usage)
- [Architecture](#architecture)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Deployment](#deployment)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

---

## Quick Start

### Prerequisites

- Python 3.11+
- An [OpenAI](https://platform.openai.com/api-keys) or [Anthropic](https://console.anthropic.com/) API key
- (Optional) [LangSmith](https://smith.langchain.com/) API key for tracing

### Install

```bash
git clone https://github.com/rohanthomas1202/Shipyard.git
cd Shipyard
pip install -e ".[dev]"
```

### Configure

```bash
cp .env.example .env
```

Edit `.env` with your keys:

```env
OPENAI_API_KEY=sk-...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2-...
LANGCHAIN_PROJECT=shipyard
```

### Run

```bash
uvicorn server.main:app --reload --port 8000
```

Verify it's running:

```bash
curl http://localhost:8000/health
```

---

## Usage

### Submit an instruction

```bash
curl -X POST http://localhost:8000/instruction \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "Add a due_date field to the Issue model",
    "working_directory": "/path/to/project",
    "context": {"files": ["api/src/models/issue.ts"]}
  }'
```

Returns a `run_id` to track progress.

### Check status

```bash
curl http://localhost:8000/status/<run_id>
```

### Stream events via WebSocket

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/<project_id>");
ws.onmessage = (event) => console.log(JSON.parse(event.data));
```

### Approve or reject edits (supervised mode)

```bash
# Approve
curl -X PATCH http://localhost:8000/runs/<run_id>/edits/<edit_id> \
  -H "Content-Type: application/json" \
  -d '{"status": "approved"}'

# Reject
curl -X PATCH http://localhost:8000/runs/<run_id>/edits/<edit_id> \
  -H "Content-Type: application/json" \
  -d '{"status": "rejected"}'
```

---

## Architecture

```
Instruction
    │
    ▼
┌──────────┐     ┌──────────┐     ┌───────────┐
│ Receive  │────▶│ Planner  │────▶│Coordinator│
└──────────┘     └──────────┘     └─────┬─────┘
                                        │
                          ┌─────────────┼─────────────┐
                          ▼             ▼             ▼
                     ┌────────┐   ┌────────┐   ┌────────┐
                     │ Reader │   │ Reader │   │ Reader │
                     └───┬────┘   └───┬────┘   └───┬────┘
                         ▼            ▼            ▼
                     ┌────────┐   ┌────────┐   ┌────────┐
                     │ Editor │   │ Editor │   │ Editor │
                     └───┬────┘   └───┬────┘   └───┬────┘
                         ▼            ▼            ▼
                     ┌─────────┐  ┌─────────┐  ┌─────────┐
                     │Validator│  │Validator│  │Validator│
                     └────┬────┘  └────┬────┘  └────┬────┘
                          │            │            │
                          └─────────┬──┘────────────┘
                                    ▼
                              ┌──────────┐
                              │  Merger  │
                              └────┬─────┘
                                   ▼
                              ┌──────────┐
                              │ Reporter │
                              └──────────┘
```

### Key Design Decisions

| Decision | Approach | Why |
|---|---|---|
| **File editing** | Anchor-based replacement | No line-number drift, no AST dependency — works on any language |
| **Parallelism** | Directory-based grouping | `api/` and `web/` edits never conflict, so they run concurrently |
| **Validation** | Language-specific syntax checks | esbuild for TS, `json.load` for JSON, `yaml.safe_load` for YAML |
| **Model routing** | Policy-based with escalation | Planning uses stronger models, validation uses faster ones |
| **Persistence** | SQLite via aiosqlite | Zero-config, async-friendly, good enough for single-node |

### Tech Stack

| Layer | Technology |
|---|---|
| **Orchestration** | [LangGraph](https://langchain-ai.github.io/langgraph/) — state machine for agent workflows |
| **LLM** | Claude (Anthropic SDK) / OpenAI — with intelligent model routing |
| **API** | [FastAPI](https://fastapi.tiangolo.com) — REST + WebSocket endpoints |
| **Persistence** | SQLite via [aiosqlite](https://github.com/omnilib/aiosqlite) |
| **Tracing** | [LangSmith](https://smith.langchain.com/) — optional observability |
| **Testing** | pytest + pytest-asyncio |

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/instruction` | Submit a new coding instruction |
| `GET` | `/status/{run_id}` | Get run status and result |
| `POST` | `/instruction/{run_id}` | Continue a paused run |
| `GET` | `/projects` | List all projects |
| `POST` | `/projects` | Create a new project |
| `PATCH` | `/runs/{run_id}/edits/{edit_id}` | Approve or reject an edit |
| `WebSocket` | `/ws/{project_id}` | Real-time event stream |

---

## Project Structure

```
shipyard/
├── agent/                # Core agent logic
│   ├── nodes/            # LangGraph nodes (planner, editor, validator, etc.)
│   ├── tools/            # File ops, shell execution, code search
│   ├── prompts/          # System/user prompts for LLM calls
│   ├── graph.py          # StateGraph with conditional routing
│   ├── router.py         # Policy-based model routing
│   ├── events.py         # EventBus + TokenBatcher for streaming
│   ├── approval.py       # Edit approval state machine
│   └── state.py          # AgentState TypedDict
├── server/               # FastAPI application
│   ├── main.py           # HTTP + WebSocket endpoints
│   └── websocket.py      # ConnectionManager
├── store/                # Persistence layer
│   ├── models.py         # Pydantic models (Project, Run, Edit, Event)
│   ├── sqlite.py         # SQLiteSessionStore
│   └── protocol.py       # Store interface
├── tests/                # Unit + integration tests
├── traces/               # Example execution traces
├── .env.example          # Environment template
├── pyproject.toml        # Project config
└── Procfile              # PaaS deployment
```

---

## Testing

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run a specific test file
python3 -m pytest tests/test_approval.py -v

# Run with coverage
python3 -m pytest tests/ --cov=agent --cov=server --cov=store
```

---

## Deployment

Shipyard includes a `Procfile` for Heroku-style platforms:

```bash
web: uvicorn server.main:app --host 0.0.0.0 --port $PORT
```

---

## Documentation

| Document | Description |
|---|---|
| [PRESEARCH.md](PRESEARCH.md) | Architecture research — file editing strategies, agent patterns |
| [CODEAGENT.md](CODEAGENT.md) | Implementation details — MVP state diagram, trace analysis |
| [traces/](traces/) | Example JSON traces of agent runs |

---

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/my-feature`)
3. Write tests for your changes
4. Ensure all tests pass (`python3 -m pytest tests/ -v`)
5. Commit your changes
6. Push to your branch and open a Pull Request

---

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
