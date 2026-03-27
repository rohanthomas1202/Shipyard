# Fly.io Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy Shipyard to Fly.io with a multi-stage Docker build, persistent volume, and all runtime dependencies (Python 3.11, Node.js, typescript-language-server, git).

**Architecture:** Multi-stage Dockerfile builds the React frontend in a Node stage and assembles the Python runtime with Node.js for LSP support in the final stage. Fly.io hosts a single machine with a persistent volume at `/data` for SQLite and workspace files.

**Tech Stack:** Docker, Fly.io, Python 3.11, Node.js 20, uvicorn, FastAPI

---

### Task 1: Create `.dockerignore`

**Files:**
- Create: `.dockerignore`

- [ ] **Step 1: Create `.dockerignore`**

```
.git
.gitignore
node_modules
__pycache__
*.pyc
.env
shipyard.db
traces/
.claude/
ship-rebuild/
tests/
.planning/
docs/
.venv/
*.egg-info/
.pytest_cache/
web/node_modules
```

- [ ] **Step 2: Verify the file exists and has correct content**

Run: `cat .dockerignore | head -20`
Expected: The file contents listed above.

- [ ] **Step 3: Commit**

```bash
git add .dockerignore
git commit -m "chore: add .dockerignore for Fly.io deployment"
```

---

### Task 2: Create `Dockerfile`

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Create the multi-stage Dockerfile**

```dockerfile
# Stage 1: Build React frontend
FROM node:20-slim AS frontend

WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Python runtime with Node.js for typescript-language-server
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
       | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
       > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# typescript-language-server (required for LSP validation)
RUN npm install -g typescript typescript-language-server

# Python dependencies
WORKDIR /app
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application source
COPY agent/ agent/
COPY server/ server/
COPY store/ store/

# Frontend build output
COPY --from=frontend /build/web/dist web/dist

# Create data directory (volume mount point)
RUN mkdir -p /data/workspaces

EXPOSE 8080

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 2: Verify the Dockerfile is syntactically valid**

Run: `docker build --check . 2>&1 | head -5` (if Docker is available) or just review the file:
Run: `head -50 Dockerfile`
Expected: The Dockerfile content from step 1.

- [ ] **Step 3: Commit**

```bash
git add Dockerfile
git commit -m "feat: add multi-stage Dockerfile for Fly.io deployment"
```

---

### Task 3: Create `fly.toml`

**Files:**
- Create: `fly.toml`

- [ ] **Step 1: Create the Fly.io configuration**

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

[env]
  SHIPYARD_DB_PATH = "/data/shipyard.db"
```

Note: `SHIPYARD_DB_PATH` is set as a non-secret env var here since its value is not sensitive. Secrets (`OPENAI_API_KEY`, `LANGCHAIN_API_KEY`, etc.) are set separately via `fly secrets set`.

- [ ] **Step 2: Verify the file**

Run: `cat fly.toml`
Expected: The toml content from step 1.

- [ ] **Step 3: Commit**

```bash
git add fly.toml
git commit -m "feat: add fly.toml for Fly.io deployment config"
```

---

### Task 4: Local Docker Build Smoke Test

**Files:** None (verification only)

- [ ] **Step 1: Build the Docker image locally**

Run: `docker build -t shipyard-local .`
Expected: Build completes successfully. Both stages run without errors. Final image contains Python, Node.js, typescript-language-server, git, and the app source.

- [ ] **Step 2: Verify runtime dependencies are present in the image**

Run: `docker run --rm shipyard-local python --version`
Expected: `Python 3.11.x`

Run: `docker run --rm shipyard-local node --version`
Expected: `v20.x.x`

Run: `docker run --rm shipyard-local typescript-language-server --version`
Expected: A version number (e.g., `4.x.x`)

Run: `docker run --rm shipyard-local git --version`
Expected: `git version 2.x.x`

- [ ] **Step 3: Verify the app starts**

Run: `docker run --rm -p 8080:8080 -e OPENAI_API_KEY=test -e SHIPYARD_DB_PATH=/data/shipyard.db -v /tmp/shipyard-data:/data shipyard-local &`
Wait 3 seconds, then:
Run: `curl -s http://localhost:8080/health`
Expected: A JSON response (health check endpoint).

Stop the container after verification.

- [ ] **Step 4: Verify frontend is served**

Run: `curl -s http://localhost:8080/ | head -5`
Expected: HTML content from the React SPA (should contain `<div id="root">` or similar).

Stop any running container after this check.

---

### Task 5: Deploy to Fly.io

This task requires the user to have `flyctl` installed and authenticated.

- [ ] **Step 1: Launch the Fly.io app**

Run: `fly launch --no-deploy`
This reads `fly.toml`, creates the app and volume on Fly.io. Choose "Yes" to use the existing `fly.toml` config. Skip deploying for now — we set secrets first.

- [ ] **Step 2: Set secrets**

Run (user fills in real values):
```bash
fly secrets set \
  OPENAI_API_KEY=<your-key> \
  LANGCHAIN_API_KEY=<your-key> \
  LANGCHAIN_TRACING_V2=true \
  LANGCHAIN_PROJECT=shipyard
```

- [ ] **Step 3: Deploy**

Run: `fly deploy`
Expected: Remote Docker build succeeds, machine starts, health checks pass.

- [ ] **Step 4: Verify the deployment**

Run: `fly status`
Expected: One machine running in `sjc` region.

Run: `fly open`
Expected: Browser opens to `https://shipyard-demo.fly.dev` showing the React UI.

- [ ] **Step 5: Pre-stage the demo repo**

Run: `fly ssh console`
Then inside the machine:
```bash
mkdir -p /data/workspaces
cd /data/workspaces
git clone <demo-repo-url> <project-id>
```

- [ ] **Step 6: Commit any final adjustments**

If any tweaks were needed during deployment, commit them:
```bash
git add -A
git commit -m "fix: deployment adjustments from first Fly.io deploy"
```
