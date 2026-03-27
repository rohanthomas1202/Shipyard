# Shipyard Deployment Design — Fly.io

**Date:** 2026-03-26
**Goal:** Deploy Shipyard to a stable public URL for demo purposes using Fly.io with Docker.

## Context

Shipyard is a single-process Python/FastAPI app that:
- Serves a React SPA from `web/dist/`
- Uses SQLite for persistence (`SHIPYARD_DB_PATH`)
- Streams events to the frontend via WebSocket
- Requires a writable filesystem for agent file editing during runs
- Requires Node.js + `typescript-language-server` + `git` at runtime for LSP validation

## Platform Choice: Fly.io

Fly.io was chosen over Railway and VPS options because it provides:
- Full Docker control for complex runtime dependencies
- Persistent volumes for SQLite + working file edits
- Native WebSocket proxy support
- Auto-sleep/wake for cost efficiency between demo sessions
- Zero ops burden (no nginx, systemd, SSL management)
- Instant rollback via `fly deploy --image <previous>`

## Architecture

```
Internet
  │
  ▼
Fly.io Edge (TLS termination, WebSocket proxy)
  │
  ▼
Single Fly Machine (shared-cpu-1x, 512MB)
  ├── uvicorn server.main:app  (port 8080)
  │     ├── FastAPI REST API
  │     ├── WebSocket /ws endpoint
  │     └── Static files from web/dist/
  └── /data/  (persistent volume)
        ├── shipyard.db
        └── workspaces/<project-id>/  (cloned repos)
```

## Dockerfile (Multi-Stage)

### Stage 1: Frontend Build
- Base: `node:20-slim`
- Install dependencies: `npm ci` in `web/`
- Build: `npm run build` produces `web/dist/`

### Stage 2: Runtime
- Base: `python:3.11-slim`
- System packages: `git`, `curl`
- Install Node.js 20 via NodeSource (required for `typescript-language-server`)
- Install global npm packages: `typescript`, `typescript-language-server`
- Install Python app: `pip install .` (reads `pyproject.toml`)
- Copy from stage 1: `web/dist/`
- Copy app source: `agent/`, `server/`, `store/`, `pyproject.toml`
- Entrypoint: `uvicorn server.main:app --host 0.0.0.0 --port 8080`

### .dockerignore
Exclude: `.git/`, `node_modules/`, `__pycache__/`, `.env`, `shipyard.db`, `traces/`, `.claude/`, `ship-rebuild/`, `tests/`, `.planning/`

## Fly.io Configuration (`fly.toml`)

```toml
app = "shipyard-demo"
primary_region = "sjc"

[build]
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 8080
  force_https = true
  auto_start_machines = true
  auto_stop_machines = true

[mounts]
  source = "shipyard_data"
  destination = "/data"
```

- **Region:** `sjc` (San Jose) — low latency for west coast demo
- **Auto-stop:** Machine sleeps when idle, wakes on first request (~3s cold start)
- **Persistent volume:** Mounted at `/data`, survives deploys and restarts

## Secrets & Environment

Set via `fly secrets set` (encrypted at rest, injected as env vars):

| Variable | Value |
|---|---|
| `OPENAI_API_KEY` | User's OpenAI key |
| `LANGCHAIN_API_KEY` | User's LangSmith key |
| `LANGCHAIN_TRACING_V2` | `true` |
| `LANGCHAIN_PROJECT` | `shipyard` |
| `SHIPYARD_DB_PATH` | `/data/shipyard.db` |

No other configuration required.

## Working Directory Strategy

Agent runs need a writable directory to clone and edit repos.

**Volume layout:**
```
/data/
  shipyard.db
  workspaces/
    <project-id>/    # one git clone per project
```

**For the demo:** Pre-clone the target repo via `fly ssh console` into `/data/workspaces/` before the demo. This avoids clone latency and GitHub auth complexity during the live demo.

The volume and directory structure also support runtime cloning for future use.

## Files to Create/Modify

| File | Action | Purpose |
|---|---|---|
| `Dockerfile` | Create | Multi-stage build (frontend + runtime) |
| `fly.toml` | Create | Fly.io app configuration |
| `.dockerignore` | Create | Exclude unnecessary files from Docker build |

No application code changes are required. `SHIPYARD_DB_PATH` is already configurable via env var, and the static file serving already looks for `web/dist/` relative to the server module.

## Deploy Workflow

### One-time setup
1. Install Fly CLI: `brew install flyctl`
2. Authenticate: `fly auth login`
3. Launch app: `fly launch` (creates app + volume from `fly.toml`)
4. Set secrets: `fly secrets set OPENAI_API_KEY=xxx ...`

### Each deploy
1. `fly deploy` — builds image, pushes, swaps to new version
2. Persistent volume is preserved across deploys

### Pre-demo prep
1. `fly ssh console` — SSH into the machine
2. Clone target repo into `/data/workspaces/`
3. Verify app at `https://shipyard-demo.fly.dev`

### Rollback
- `fly releases list` → `fly deploy --image <previous-image>`

## Success Criteria

- App accessible at `https://shipyard-demo.fly.dev`
- React UI loads and connects via WebSocket
- Agent can receive instructions, plan, read, edit, validate, and commit code
- LSP validation works (typescript-language-server responds)
- SQLite DB persists across deploys
- File edits persist within a run on the persistent volume
