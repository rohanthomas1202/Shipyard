# Shipyard — Test Steps

Detailed steps to run and test the Shipyard autonomous coding agent locally.

## Prerequisites

- Python 3.11+
- Node.js 20+ (for frontend and TypeScript language server)
- OpenAI API key with access to o3, gpt-4o, gpt-4o-mini
- Git

## 1. Environment Setup

```bash
# Clone the repo
git clone <repo-url> Shipyard
cd Shipyard

# Create and activate Python virtual environment
python3.11 -m venv .venv311
source .venv311/bin/activate

# Install Python dependencies
pip install -r requirements.txt
pip install langgraph-checkpoint-sqlite lsprotocol pygls

# Install frontend dependencies
cd web
npm install
cd ..

# Create .env file
cp .env.example .env
# Edit .env and set:
#   OPENAI_API_KEY=sk-...
#   LANGCHAIN_TRACING_V2=true          (optional, for LangSmith tracing)
#   LANGCHAIN_API_KEY=lsv2_pt_...      (optional, for LangSmith)
#   LANGCHAIN_PROJECT=shipyard         (optional)
```

## 2. Start the Backend Server

```bash
# Load env vars and start the server
set -a; source .env; set +a
python3.11 -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload

# Verify it's running
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

## 3. Start the Frontend (Development Mode)

```bash
# In a separate terminal
cd web
npm run dev
# Frontend runs at http://localhost:5173
# Proxies API requests to http://localhost:8000
```

## 4. Create a Test Project

```bash
# Register a project pointing to a working directory
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{"name":"My Test Project","path":"/path/to/your/project"}'
# Returns: {"id":"<project_id>", ...}
```

## 5. Send an Instruction (API)

```bash
# Simple edit instruction
curl -X POST http://localhost:8000/instruction \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "<project_id>",
    "instruction": "Add a hello() function to main.py that prints Hello World",
    "working_directory": "/path/to/your/project"
  }'
# Returns: {"run_id":"<run_id>"}

# Poll status
curl http://localhost:8000/status/<run_id>
# Returns: {"run_id":"...","status":"completed|running|error","result":"..."}
```

## 6. Send an Instruction (Web UI)

1. Open http://localhost:5173 in your browser
2. Select your project from the project picker
3. Type a natural language instruction in the input box
4. Watch the agent work in real-time via the step timeline
5. Review diffs in the diff viewer (supervised mode) or see completed edits (autonomous mode)

## 7. Run the Ship Rebuild (Integration Test)

This sends 5 graduated instructions to the agent targeting the ship-rebuild/ directory:

```bash
# Register Ship project
python3.11 scripts/register_ship_project.py

# Run the rebuild orchestrator
set -a; source .env; set +a
python3.11 scripts/rebuild_orchestrator.py --project-id <project_id> --timeout 300

# Dry run first (no API calls)
python3.11 scripts/rebuild_orchestrator.py --dry-run
```

### Expected Results

| Instruction | Difficulty | Expected |
|-------------|-----------|----------|
| 1. Add status field to Document | Simple | Completes in ~30s |
| 2. Add GET /ready health endpoint | Simple | Completes in ~30s |
| 3. Add documents CRUD routes | Medium | Completes in ~35s |
| 4. Add tags field + filter | Complex (3 files) | May need intervention |
| 5. Parallel: priority + DELETE | Multi-agent | Completes in ~45s |

Target: 80%+ success rate (4/5 or better).

## 8. Run Unit Tests

```bash
# All tests
python3.11 -m pytest tests/ -v

# Phase-specific tests
python3.11 -m pytest tests/test_file_ops.py -v          # Fuzzy matching, hashing
python3.11 -m pytest tests/test_llm.py -v               # LLM wrapper, structured outputs
python3.11 -m pytest tests/test_editor_node.py -v        # Editor with error feedback
python3.11 -m pytest tests/test_validator_node.py -v     # Validator, Python syntax, LSP
python3.11 -m pytest tests/test_graph.py -v              # Graph, circuit breaker
python3.11 -m pytest tests/test_token_tracker.py -v      # Token tracking
python3.11 -m pytest tests/test_reader_node.py -v        # Line-range reads
python3.11 -m pytest tests/test_context.py -v            # ContextAssembler
python3.11 -m pytest tests/test_checkpoint.py -v         # Crash recovery
python3.11 -m pytest tests/test_cancel.py -v             # Graceful cancellation
python3.11 -m pytest tests/test_parallel_execution.py -v # Multi-agent coordination
python3.11 -m pytest tests/test_ship_integration.py -v   # Ship rebuild integration
```

## 9. Test WebSocket Streaming

```python
# Python test client
import asyncio
import websockets
import json

async def test_ws():
    async with websockets.connect("ws://localhost:8000/ws/<project_id>") as ws:
        # Subscribe to a run
        await ws.send(json.dumps({"action": "subscribe", "run_id": "<run_id>"}))
        # Listen for events
        while True:
            msg = await ws.recv()
            event = json.loads(msg)
            print(f"[{event.get('type')}] {event.get('data', {}).get('content', '')[:100]}")

asyncio.run(test_ws())
```

## 10. Test Supervised Mode

1. Create a project with `autonomy_mode: "supervised"`
2. Send an instruction
3. The agent will pause at each edit for approval
4. In the web UI, click Approve or Reject on each diff
5. Or via API:
   ```bash
   # Approve an edit
   curl -X PATCH http://localhost:8000/runs/<run_id>/edits/<edit_id> \
     -H "Content-Type: application/json" \
     -d '{"action": "approve"}'
   ```

## 11. Test Crash Recovery

1. Start a run
2. While running, kill the server (`Ctrl+C` or `kill`)
3. Restart the server
4. The server should automatically resume interrupted runs from their last checkpoint

## 12. Test Cancellation

```bash
# Start a long-running instruction
curl -X POST http://localhost:8000/instruction \
  -H "Content-Type: application/json" \
  -d '{"project_id":"<id>","instruction":"Refactor all files to use TypeScript strict mode","working_directory":"/path"}'
# Returns run_id

# Cancel mid-execution
curl -X POST http://localhost:8000/runs/<run_id>/cancel
# Should return 200, status changes to "cancelled"
```

## Build for Production

```bash
# Build frontend
cd web && npm run build && cd ..

# Start production server (serves frontend from web/dist/)
python3.11 -m uvicorn server.main:app --host 0.0.0.0 --port $PORT
```

## Deployment (Heroku/Railway)

```bash
# Heroku
heroku create shipyard-agent
heroku config:set OPENAI_API_KEY=sk-...
git push heroku main

# Railway
railway login
railway link
railway up
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError: langgraph.checkpoint.sqlite` | `pip install langgraph-checkpoint-sqlite` |
| `ModuleNotFoundError: lsprotocol` | `pip install lsprotocol pygls` |
| `OPENAI_API_KEY not set` | `set -a; source .env; set +a` before starting server |
| `max_tokens unsupported` | Update agent/llm.py to use `max_completion_tokens` |
| WebSocket drops | Ensure all subprocess calls are async (Phase 2 fix) |
| Server crash loses runs | Checkpoint DB at `shipyard_checkpoints.db` enables auto-resume |
