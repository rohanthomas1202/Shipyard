# Sub-phase 2b-1: Frontend MVP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a working React frontend MVP with Frosted Glassmorphic IDE design, WebSocket connection, and Workspace Home screen.

**Architecture:** Vite + React + TypeScript app in `web/` with Tailwind v4 for styling. Two React Contexts (WebSocket + Project) manage state. Connects to existing FastAPI backend via WebSocket proxy in dev, static file serving in prod.

**Tech Stack:** Vite, React 18, TypeScript, Tailwind CSS v4, Google Fonts (Plus Jakarta Sans, JetBrains Mono)

**Spec:** `docs/superpowers/specs/2026-03-25-phase2b-frontend-design.md` (Sub-phase 2b-1)

---

## Task 1: Required Backend Changes

**Goal:** Add missing endpoints and harden existing ones before building the frontend.

**Why first:** The frontend depends on `PUT /projects`, `GET /runs/{id}/edits`, expanded snapshots, and `github_pat` exclusion. Without these, the frontend can't function.

### 1a. Add `project_response` helper and apply to existing endpoints

**File: `server/main.py`**

Add this helper function after the `EditActionRequest` class definition (around line 93):

```python
def project_response(project) -> dict:
    """Serialize a Project, excluding github_pat from the response."""
    return project.model_dump(exclude={"github_pat"})
```

Then update the three existing project endpoints:

**`list_projects`** — change the return line:

```python
@app.get("/projects")
async def list_projects():
    store: SQLiteSessionStore = app.state.store
    projects = await store.list_projects()
    return [project_response(p) for p in projects]
```

**`create_project`** — change the return line:

```python
@app.post("/projects", status_code=201)
async def create_project(req: CreateProjectRequest):
    store: SQLiteSessionStore = app.state.store
    project = Project(name=req.name, path=req.path)
    created = await store.create_project(project)
    return project_response(created)
```

**`get_project`** — change the return line:

```python
@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    store: SQLiteSessionStore = app.state.store
    project = await store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project_response(project)
```

### 1b. Add `PUT /projects/{project_id}` endpoint

**File: `server/main.py`**

Add the request model near the other request models (after `CreateProjectRequest`):

```python
class UpdateProjectRequest(BaseModel):
    name: str | None = None
    path: str | None = None
    github_repo: str | None = None
    github_pat: str | None = None
    default_model: str | None = None
    autonomy_mode: str | None = None
    test_command: str | None = None
    build_command: str | None = None
    lint_command: str | None = None
```

Add the endpoint after `get_project`:

```python
@app.put("/projects/{project_id}")
async def update_project(project_id: str, req: UpdateProjectRequest):
    store: SQLiteSessionStore = app.state.store
    project = await store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    for field, value in req.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    updated = await store.update_project(project)
    return project_response(updated)
```

### 1c. Add `GET /runs/{run_id}/edits` endpoint

**File: `server/main.py`**

Add after the `patch_edit` endpoint:

```python
@app.get("/runs/{run_id}/edits")
async def get_run_edits(run_id: str, status: str | None = None):
    store: SQLiteSessionStore = app.state.store
    edits = await store.get_edits(run_id, status=status)
    return [e.model_dump() for e in edits]
```

### 1d. Expand `get_snapshot` in EventBus

**File: `agent/events.py`**

Replace the existing `get_snapshot` method:

```python
async def get_snapshot(self, run_id: str) -> dict:
    """Build snapshot from durable store state. Works after restart."""
    last_seq = await self.store.get_max_seq(run_id)
    run = await self.store.get_run(run_id)
    pending = await self.store.get_edits(run_id, status="proposed") if run else []
    return {
        "type": "snapshot",
        "run_id": run_id,
        "status": run.status if run else "unknown",
        "last_seq": last_seq,
        "active_node": None,
        "current_step": 0,
        "total_steps": 0,
        "pending_approvals": [e.id for e in pending],
        "current_branch": run.branch if run else None,
        "autonomy_mode": "supervised",
    }
```

### 1e. Add tests for new endpoints

**File: `tests/test_backend_frontend_endpoints.py`**

```python
"""Tests for backend endpoints required by the frontend (Phase 2b-1)."""
import pytest
from httpx import AsyncClient, ASGITransport
from server.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_create_project_excludes_github_pat(client):
    resp = await client.post("/projects", json={"name": "test-proj", "path": "/tmp/test"})
    assert resp.status_code == 201
    data = resp.json()
    assert "github_pat" not in data
    assert data["name"] == "test-proj"


@pytest.mark.asyncio
async def test_list_projects_excludes_github_pat(client):
    await client.post("/projects", json={"name": "list-test", "path": "/tmp/list"})
    resp = await client.get("/projects")
    assert resp.status_code == 200
    for p in resp.json():
        assert "github_pat" not in p


@pytest.mark.asyncio
async def test_get_project_excludes_github_pat(client):
    create = await client.post("/projects", json={"name": "get-test", "path": "/tmp/get"})
    pid = create.json()["id"]
    resp = await client.get(f"/projects/{pid}")
    assert resp.status_code == 200
    assert "github_pat" not in resp.json()


@pytest.mark.asyncio
async def test_update_project(client):
    create = await client.post("/projects", json={"name": "update-test", "path": "/tmp/up"})
    pid = create.json()["id"]
    resp = await client.put(f"/projects/{pid}", json={"name": "updated-name", "autonomy_mode": "autonomous"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "updated-name"
    assert data["autonomy_mode"] == "autonomous"
    assert "github_pat" not in data


@pytest.mark.asyncio
async def test_update_project_not_found(client):
    resp = await client.put("/projects/nonexistent", json={"name": "x"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_run_edits(client):
    # Create a project and run first
    create = await client.post("/projects", json={"name": "edits-test", "path": "/tmp/edits"})
    pid = create.json()["id"]
    run_resp = await client.post("/instruction", json={
        "instruction": "test",
        "working_directory": "/tmp/edits",
        "project_id": pid,
    })
    rid = run_resp.json()["run_id"]
    # GET edits — may be empty but should not 500
    resp = await client.get(f"/runs/{rid}/edits")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_run_edits_with_status_filter(client):
    create = await client.post("/projects", json={"name": "edits-filter", "path": "/tmp/ef"})
    pid = create.json()["id"]
    run_resp = await client.post("/instruction", json={
        "instruction": "test",
        "working_directory": "/tmp/ef",
        "project_id": pid,
    })
    rid = run_resp.json()["run_id"]
    resp = await client.get(f"/runs/{rid}/edits?status=proposed")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

### Verification

```bash
cd /Users/rohanthomas/Shipyard
python -m pytest tests/test_backend_frontend_endpoints.py -v
python -m pytest tests/ -v  # all tests still pass
```

---

## Task 2: Scaffold Vite + React + TypeScript Project

**Goal:** Create the `web/` directory with Vite, React, TypeScript, and Tailwind v4 configured.

### 2a. Scaffold with Vite

```bash
cd /Users/rohanthomas/Shipyard
npm create vite@latest web -- --template react-ts
cd web
npm install
```

### 2b. Install Tailwind v4

```bash
cd /Users/rohanthomas/Shipyard/web
npm install tailwindcss @tailwindcss/vite
```

### 2c. Clean up scaffolded files

Delete the Vite default files we don't need:

```bash
cd /Users/rohanthomas/Shipyard/web
rm -f src/App.css src/index.css src/assets/react.svg public/vite.svg
```

### 2d. Create directory structure

```bash
cd /Users/rohanthomas/Shipyard/web
mkdir -p src/styles src/types src/lib src/context src/hooks
mkdir -p src/components/layout src/components/explorer src/components/home src/components/agent
```

### 2e. Configure `vite.config.ts`

**File: `web/vite.config.ts`**

Replace the scaffolded file entirely:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/health': 'http://localhost:8000',
      '/projects': 'http://localhost:8000',
      '/instruction': 'http://localhost:8000',
      '/status': 'http://localhost:8000',
      '/runs': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
  build: {
    outDir: 'dist',
  },
})
```

### 2f. Update `index.html` with Google Fonts

**File: `web/index.html`**

Replace entirely:

```html
<!DOCTYPE html>
<html lang="en" class="dark">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Shipyard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
      rel="stylesheet"
    />
  </head>
  <body class="h-screen w-screen antialiased selection:bg-primary/30">
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

### 2g. Create `glass.css` design system

**File: `web/src/styles/glass.css`**

```css
@import "tailwindcss";

@theme {
  --color-primary: #6366F1;
  --color-background: #0F111A;
  --color-surface: rgba(30, 33, 43, 0.6);
  --color-surface-hover: rgba(255, 255, 255, 0.05);
  --color-border: rgba(255, 255, 255, 0.08);
  --color-text: #F8FAFC;
  --color-muted: #94A3B8;
  --color-error: #EF4444;
  --color-success: #10B981;
  --color-warning: #F59E0B;
  --font-ui: 'Plus Jakarta Sans', sans-serif;
  --font-code: 'JetBrains Mono', monospace;
  --radius-panel: 16px;
  --radius-element: 8px;
}

:root {
  --blur-heavy: blur(24px);
}

body {
  font-family: var(--font-ui);
  background-color: var(--color-background);
  color: var(--color-text);
  overflow: hidden;
}

.glass-panel {
  background-color: var(--color-surface);
  backdrop-filter: var(--blur-heavy);
  -webkit-backdrop-filter: var(--blur-heavy);
  border: 1px solid var(--color-border);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  border-radius: var(--radius-panel);
}

/* Scrollbar styling */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(148, 163, 184, 0.2); border-radius: 4px; }

/* Mesh background blobs */
@keyframes float {
  0% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(50px, -50px) scale(1.1); }
  66% { transform: translate(-30px, 40px) scale(0.9); }
  100% { transform: translate(0, 0) scale(1); }
}

/* Status indicator pulse */
@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* Stream cursor blink */
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.stream-cursor::after {
  content: '|';
  color: var(--color-primary);
  animation: blink 1s infinite;
  font-weight: bold;
}
```

### 2h. Update `main.tsx`

**File: `web/src/main.tsx`**

Replace entirely:

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles/glass.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

### 2i. Stub `App.tsx`

**File: `web/src/App.tsx`**

Replace entirely (will be updated in Task 6):

```tsx
export default function App() {
  return (
    <div className="h-screen w-screen flex items-center justify-center">
      <h1 className="text-2xl font-bold text-text">Shipyard</h1>
    </div>
  )
}
```

### Verification

```bash
cd /Users/rohanthomas/Shipyard/web
npm run dev &
# Visit http://localhost:5173 — should show "Shipyard" centered on dark background
# Kill the dev server
npm run build
# Should complete without errors
```

---

## Task 3: TypeScript Types + API Client

**Goal:** Define all shared types and create a fetch-based API client.

### 3a. TypeScript types

**File: `web/src/types/index.ts`**

```typescript
export interface Project {
  id: string;
  name: string;
  path: string;
  github_repo: string | null;
  autonomy_mode: string;
  default_model: string;
  test_command: string | null;
  build_command: string | null;
  lint_command: string | null;
  created_at: string;
  updated_at: string;
  // github_pat intentionally omitted — never sent to frontend
}

export interface Run {
  id: string;
  project_id: string;
  instruction: string;
  status: 'running' | 'completed' | 'failed' | 'error' | 'waiting_for_human';
  plan: Record<string, unknown>[];
  branch: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface WSEvent {
  type: string;
  run_id: string;
  seq: number;
  node: string | null;
  model: string | null;
  data: Record<string, unknown>;
  timestamp: number;
}

export interface RunSnapshot {
  type: 'snapshot';
  run_id: string;
  status: string;
  active_node: string | null;
  current_step: number;
  total_steps: number;
  pending_approvals: string[];
  current_branch: string | null;
  autonomy_mode: 'supervised' | 'autonomous';
  last_seq: number;
}

export interface Edit {
  id: string;
  run_id: string;
  file_path: string;
  step: number;
  status: 'proposed' | 'approved' | 'rejected' | 'applied' | 'committed';
  old_content: string | null;
  new_content: string | null;
  anchor: string | null;
}

export interface ApiError {
  detail: string;
}

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected';
```

### 3b. API client

**File: `web/src/lib/api.ts`**

```typescript
import type { Project, Edit } from '../types'

const BASE = ''

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`
    try {
      const body = await resp.json()
      if (body.detail) detail = body.detail
    } catch {
      // ignore parse errors
    }
    throw new Error(detail)
  }
  return resp.json()
}

export const api = {
  // Health
  healthCheck: () =>
    request<{ status: string }>('/health'),

  // Projects
  getProjects: () =>
    request<Project[]>('/projects'),

  createProject: (name: string, path: string) =>
    request<Project>('/projects', {
      method: 'POST',
      body: JSON.stringify({ name, path }),
    }),

  getProject: (id: string) =>
    request<Project>(`/projects/${id}`),

  updateProject: (id: string, updates: Partial<Project>) =>
    request<Project>(`/projects/${id}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    }),

  // Instructions
  submitInstruction: (
    instruction: string,
    workingDirectory: string,
    context?: Record<string, unknown>,
    projectId?: string,
  ) =>
    request<{ run_id: string; status: string }>('/instruction', {
      method: 'POST',
      body: JSON.stringify({
        instruction,
        working_directory: workingDirectory,
        context: context ?? {},
        project_id: projectId ?? null,
      }),
    }),

  resumeRun: (
    runId: string,
    instruction: string,
    workingDirectory: string,
  ) =>
    request<{ run_id: string; status: string }>(`/instruction/${runId}`, {
      method: 'POST',
      body: JSON.stringify({
        instruction,
        working_directory: workingDirectory,
      }),
    }),

  getStatus: (runId: string) =>
    request<{ run_id: string; status: string; result: unknown }>(`/status/${runId}`),

  // Edits
  getEdits: (runId: string, status?: string) => {
    const params = status ? `?status=${status}` : ''
    return request<Edit[]>(`/runs/${runId}/edits${params}`)
  },

  patchEdit: (runId: string, editId: string, action: 'approve' | 'reject', opId: string) =>
    request<{ edit_id: string; run_id: string; status: string }>(
      `/runs/${runId}/edits/${editId}`,
      {
        method: 'PATCH',
        body: JSON.stringify({ action, op_id: opId }),
      },
    ),

  // Git
  gitCommit: (runId: string, message?: string) =>
    request<{ sha: string; message: string }>(`/runs/${runId}/git/commit`, {
      method: 'POST',
      body: JSON.stringify({ message: message ?? null }),
    }),

  gitPush: (runId: string) =>
    request<{ branch: string; status: string }>(`/runs/${runId}/git/push`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  gitCreatePR: (runId: string, title?: string, body?: string, draft?: boolean) =>
    request<{ number: number; html_url: string }>(`/runs/${runId}/git/pr`, {
      method: 'POST',
      body: JSON.stringify({ title: title ?? null, body: body ?? null, draft: draft ?? false }),
    }),

  gitMerge: (runId: string, prNumber: number, method?: string) =>
    request<{ merged: boolean; sha: string }>(`/runs/${runId}/git/merge`, {
      method: 'POST',
      body: JSON.stringify({ pr_number: prNumber, method: method ?? 'squash' }),
    }),
}
```

### Verification

```bash
cd /Users/rohanthomas/Shipyard/web
npx tsc --noEmit
# Should complete with no type errors
```

---

## Task 4: WebSocket Hook + Context

**Goal:** Create `useWebSocket` hook and `WebSocketContext` for real-time event distribution.

### 4a. `useWebSocket` hook

**File: `web/src/hooks/useWebSocket.ts`**

```typescript
import { useEffect, useRef, useCallback, useState } from 'react'
import type { ConnectionStatus, WSEvent } from '../types'

const MAX_BACKOFF = 10_000
const HEARTBEAT_TIMEOUT = 45_000 // 3 missed heartbeats at 15s interval

interface UseWebSocketReturn {
  status: ConnectionStatus
  send: (data: object) => void
  onMessage: (handler: (event: WSEvent) => void) => () => void
}

export function useWebSocket(projectId: string | null): UseWebSocketReturn {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected')
  const wsRef = useRef<WebSocket | null>(null)
  const handlersRef = useRef<Set<(event: WSEvent) => void>>(new Set())
  const backoffRef = useRef(1000)
  const heartbeatTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)

  const resetHeartbeat = useCallback(() => {
    if (heartbeatTimerRef.current) clearTimeout(heartbeatTimerRef.current)
    heartbeatTimerRef.current = setTimeout(() => {
      // 3 missed heartbeats — force reconnect
      if (wsRef.current) {
        wsRef.current.close()
      }
    }, HEARTBEAT_TIMEOUT)
  }, [])

  const connect = useCallback(() => {
    if (!projectId || !mountedRef.current) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const url = `${protocol}//${host}/ws/${projectId}`

    setStatus('connecting')
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) { ws.close(); return }
      setStatus('connected')
      backoffRef.current = 1000
      resetHeartbeat()
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WSEvent
        // Heartbeat resets the timeout
        if (data.type === 'heartbeat') {
          resetHeartbeat()
          return
        }
        handlersRef.current.forEach((handler) => handler(data))
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = () => {
      if (!mountedRef.current) return
      setStatus('disconnected')
      if (heartbeatTimerRef.current) clearTimeout(heartbeatTimerRef.current)
      // Auto-reconnect with exponential backoff
      const delay = backoffRef.current
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF)
      reconnectTimerRef.current = setTimeout(() => {
        if (mountedRef.current) connect()
      }, delay)
    }

    ws.onerror = () => {
      // onclose will fire after onerror
    }
  }, [projectId, resetHeartbeat])

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      if (heartbeatTimerRef.current) clearTimeout(heartbeatTimerRef.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [connect])

  const send = useCallback((data: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  const onMessage = useCallback((handler: (event: WSEvent) => void) => {
    handlersRef.current.add(handler)
    return () => { handlersRef.current.delete(handler) }
  }, [])

  return { status, send, onMessage }
}
```

### 4b. `WebSocketContext`

**File: `web/src/context/WebSocketContext.tsx`**

```tsx
import {
  createContext,
  useContext,
  useCallback,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useWebSocket } from '../hooks/useWebSocket'
import type { ConnectionStatus, WSEvent, RunSnapshot } from '../types'

interface WebSocketContextValue {
  status: ConnectionStatus
  subscribe: (eventType: string, handler: (event: WSEvent) => void) => () => void
  send: (data: object) => void
  snapshot: RunSnapshot | null
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null)

interface WebSocketProviderProps {
  projectId: string | null
  children: ReactNode
}

export function WebSocketProvider({ projectId, children }: WebSocketProviderProps) {
  const { status, send, onMessage } = useWebSocket(projectId)
  const [snapshot, setSnapshot] = useState<RunSnapshot | null>(null)
  const subscribersRef = useRef<Map<string, Set<(event: WSEvent) => void>>>(new Map())
  const lastSeqRef = useRef<Map<string, number>>(new Map())

  // Register the master handler once
  const masterRegistered = useRef(false)
  if (!masterRegistered.current) {
    masterRegistered.current = true
    onMessage((event: WSEvent) => {
      // Track seq per run_id
      if (event.run_id && typeof event.seq === 'number') {
        lastSeqRef.current.set(event.run_id, event.seq)
      }

      // Handle snapshots
      if (event.type === 'snapshot') {
        setSnapshot(event as unknown as RunSnapshot)
        return
      }

      // Dispatch to type-specific subscribers
      const handlers = subscribersRef.current.get(event.type)
      if (handlers) {
        handlers.forEach((handler) => handler(event))
      }

      // Also dispatch to wildcard subscribers
      const wildcardHandlers = subscribersRef.current.get('*')
      if (wildcardHandlers) {
        wildcardHandlers.forEach((handler) => handler(event))
      }
    })
  }

  const subscribe = useCallback(
    (eventType: string, handler: (event: WSEvent) => void) => {
      if (!subscribersRef.current.has(eventType)) {
        subscribersRef.current.set(eventType, new Set())
      }
      subscribersRef.current.get(eventType)!.add(handler)
      return () => {
        subscribersRef.current.get(eventType)?.delete(handler)
      }
    },
    [],
  )

  const getLastSeq = useCallback((runId: string) => {
    return lastSeqRef.current.get(runId) ?? 0
  }, [])

  const sendWithReconnect = useCallback(
    (data: object) => {
      send(data)
    },
    [send],
  )

  return (
    <WebSocketContext.Provider
      value={{ status, subscribe, send: sendWithReconnect, snapshot }}
    >
      {children}
    </WebSocketContext.Provider>
  )
}

export function useWS(): WebSocketContextValue {
  const ctx = useContext(WebSocketContext)
  if (!ctx) throw new Error('useWS must be used within WebSocketProvider')
  return ctx
}
```

### Verification

```bash
cd /Users/rohanthomas/Shipyard/web
npx tsc --noEmit
```

---

## Task 5: Project Context

**Goal:** Create `ProjectContext` to manage project and run state, and wire it to the API client and WebSocket.

**File: `web/src/context/ProjectContext.tsx`**

```tsx
import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from 'react'
import { api } from '../lib/api'
import { useWS } from './WebSocketContext'
import type { Project, Run } from '../types'

interface ProjectContextValue {
  projects: Project[]
  currentProject: Project | null
  runs: Run[]
  currentRun: Run | null
  loading: boolean
  error: string | null
  setCurrentProject: (project: Project) => void
  setCurrentRun: (run: Run | null) => void
  submitInstruction: (instruction: string, workingDir: string, context?: Record<string, unknown>) => Promise<string>
  refreshProjects: () => Promise<void>
}

const ProjectContext = createContext<ProjectContextValue | null>(null)

interface ProjectProviderProps {
  children: ReactNode
}

export function ProjectProvider({ children }: ProjectProviderProps) {
  const [projects, setProjects] = useState<Project[]>([])
  const [currentProject, setCurrentProject] = useState<Project | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [currentRun, setCurrentRun] = useState<Run | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { send, subscribe, status: wsStatus } = useWS()

  const refreshProjects = useCallback(async () => {
    try {
      setLoading(true)
      const data = await api.getProjects()
      setProjects(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch projects')
    } finally {
      setLoading(false)
    }
  }, [])

  // Fetch projects on mount
  useEffect(() => {
    refreshProjects()
  }, [refreshProjects])

  // Subscribe to status updates via WebSocket
  useEffect(() => {
    const unsub = subscribe('status', (event) => {
      if (currentRun && event.run_id === currentRun.id) {
        const newStatus = event.data.status as Run['status']
        setCurrentRun((prev) => prev ? { ...prev, status: newStatus } : null)
      }
    })
    return unsub
  }, [subscribe, currentRun])

  // Poll status as fallback when WebSocket is disconnected
  useEffect(() => {
    if (wsStatus === 'connected' || !currentRun) return
    if (currentRun.status !== 'running') return

    const interval = setInterval(async () => {
      try {
        const data = await api.getStatus(currentRun.id)
        setCurrentRun((prev) => prev ? { ...prev, status: data.status as Run['status'] } : null)
      } catch {
        // ignore polling errors
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [wsStatus, currentRun])

  const submitInstruction = useCallback(
    async (instruction: string, workingDir: string, context?: Record<string, unknown>) => {
      setError(null)
      try {
        const result = await api.submitInstruction(
          instruction,
          workingDir,
          context,
          currentProject?.id,
        )

        const newRun: Run = {
          id: result.run_id,
          project_id: currentProject?.id ?? 'default',
          instruction,
          status: 'running',
          plan: [],
          branch: null,
          created_at: new Date().toISOString(),
          completed_at: null,
        }

        setCurrentRun(newRun)
        setRuns((prev) => [newRun, ...prev])

        // Subscribe to run events via WebSocket
        send({ action: 'subscribe', run_id: result.run_id })

        return result.run_id
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'Failed to submit instruction'
        setError(msg)
        throw e
      }
    },
    [currentProject, send],
  )

  return (
    <ProjectContext.Provider
      value={{
        projects,
        currentProject,
        runs,
        currentRun,
        loading,
        error,
        setCurrentProject,
        setCurrentRun,
        submitInstruction,
        refreshProjects,
      }}
    >
      {children}
    </ProjectContext.Provider>
  )
}

export function useProject(): ProjectContextValue {
  const ctx = useContext(ProjectContext)
  if (!ctx) throw new Error('useProject must be used within ProjectProvider')
  return ctx
}
```

### Verification

```bash
cd /Users/rohanthomas/Shipyard/web
npx tsc --noEmit
```

---

## Task 6: Layout Components (MeshBackground + AppShell + App wiring)

**Goal:** Create the animated background, the 3-column IDE layout shell, and wire up App.tsx with providers.

### 6a. MeshBackground

**File: `web/src/components/layout/MeshBackground.tsx`**

```tsx
export default function MeshBackground() {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden bg-background">
      {/* Blue blob — top-left */}
      <div
        className="absolute -top-[100px] -left-[100px] w-[600px] h-[600px] rounded-full opacity-50"
        style={{
          background: '#3B82F6',
          filter: 'blur(120px)',
          animation: 'float 20s infinite ease-in-out alternate',
        }}
      />
      {/* Purple blob — bottom-right */}
      <div
        className="absolute -bottom-[50px] -right-[50px] w-[500px] h-[500px] rounded-full opacity-50"
        style={{
          background: '#8B5CF6',
          filter: 'blur(120px)',
          animation: 'float 20s infinite ease-in-out alternate',
          animationDelay: '-5s',
        }}
      />
      {/* Pink blob — center */}
      <div
        className="absolute top-[40%] left-[40%] w-[400px] h-[400px] rounded-full opacity-30"
        style={{
          background: '#EC4899',
          filter: 'blur(120px)',
          animation: 'float 20s infinite ease-in-out alternate',
          animationDelay: '-10s',
        }}
      />
    </div>
  )
}
```

### 6b. AppShell

**File: `web/src/components/layout/AppShell.tsx`**

```tsx
import { useProject } from '../../context/ProjectContext'
import FileTree from '../explorer/FileTree'
import RunList from '../explorer/RunList'
import WorkspaceHome from '../home/WorkspaceHome'
import AgentPanel from '../agent/AgentPanel'

export default function AppShell() {
  const { currentRun } = useProject()

  return (
    <div className="h-full w-full p-4 box-border">
      <div
        className="grid h-full w-full gap-4"
        style={{ gridTemplateColumns: '250px 1fr 300px' }}
      >
        {/* Left sidebar: File Explorer */}
        <aside className="glass-panel rounded-2xl flex flex-col h-full overflow-hidden">
          <div className="px-4 py-3 border-b border-border flex items-center justify-between shrink-0">
            <h2 className="text-xs font-bold tracking-wider uppercase text-muted">
              Explorer
            </h2>
          </div>
          <div className="flex-1 overflow-y-auto">
            <FileTree />
          </div>
          <RunList />
        </aside>

        {/* Center: Content area */}
        <main className="flex flex-col h-full relative overflow-hidden">
          {/* Top status bar */}
          <div className="h-10 flex items-center justify-end px-4 shrink-0">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface border border-border text-xs font-medium text-muted">
              <span className="w-2 h-2 rounded-full bg-success shadow-[0_0_8px_rgba(34,197,94,0.6)]" />
              Local Environment Active
            </div>
          </div>

          {/* Main content */}
          <div className="flex-1 flex flex-col items-center justify-center">
            {currentRun ? (
              <div className="flex flex-col items-center gap-4 text-muted">
                <div className="w-12 h-12 rounded-full bg-primary/20 border border-primary/30 flex items-center justify-center animate-pulse">
                  <svg className="w-6 h-6 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <p className="text-sm font-medium text-text">
                  Run <span className="font-code text-primary">{currentRun.id}</span> — {currentRun.status}
                </p>
                <p className="text-xs text-muted max-w-md text-center truncate">
                  {currentRun.instruction}
                </p>
              </div>
            ) : (
              <WorkspaceHome />
            )}
          </div>
        </main>

        {/* Right sidebar: Agent Panel */}
        <AgentPanel />
      </div>
    </div>
  )
}
```

### 6c. Error Boundary

**File: `web/src/components/layout/ErrorBoundary.tsx`**

```tsx
import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="h-screen w-screen flex items-center justify-center">
          <div className="glass-panel rounded-2xl p-8 max-w-md text-center">
            <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-error/20 border border-error/30 flex items-center justify-center">
              <svg className="w-6 h-6 text-error" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h2 className="text-lg font-bold text-text mb-2">Something went wrong</h2>
            <p className="text-sm text-muted mb-6">
              {this.state.error?.message ?? 'An unexpected error occurred.'}
            </p>
            <button
              onClick={() => window.location.reload()}
              className="px-6 py-2 rounded-lg bg-primary text-white text-sm font-semibold hover:bg-primary/90 transition-colors"
            >
              Reload
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
```

### 6d. Update `App.tsx` to wire everything together

**File: `web/src/App.tsx`**

Replace entirely:

```tsx
import { useState } from 'react'
import { WebSocketProvider } from './context/WebSocketContext'
import { ProjectProvider } from './context/ProjectContext'
import MeshBackground from './components/layout/MeshBackground'
import AppShell from './components/layout/AppShell'
import ErrorBoundary from './components/layout/ErrorBoundary'

export default function App() {
  // In the MVP, projectId is null until a project is selected.
  // The WebSocket connects when a projectId is provided.
  const [projectId] = useState<string | null>(null)

  return (
    <ErrorBoundary>
      <WebSocketProvider projectId={projectId}>
        <ProjectProvider>
          <MeshBackground />
          <AppShell />
        </ProjectProvider>
      </WebSocketProvider>
    </ErrorBoundary>
  )
}
```

### Verification

```bash
cd /Users/rohanthomas/Shipyard/web
npx tsc --noEmit
npm run build
```

---

## Task 7: Workspace Home

**Goal:** Create the centered home screen with prompt input, quick actions, and send functionality.

**File: `web/src/components/home/WorkspaceHome.tsx`**

```tsx
import { useState, useRef, useCallback } from 'react'
import { useProject } from '../../context/ProjectContext'

export default function WorkspaceHome() {
  const { submitInstruction, currentProject, error: contextError } = useProject()
  const [instruction, setInstruction] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSubmit = useCallback(async () => {
    const text = instruction.trim()
    if (!text || submitting) return

    setError(null)
    setSubmitting(true)
    try {
      const workingDir = currentProject?.path ?? '/tmp'
      await submitInstruction(text, workingDir)
      setInstruction('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      setSubmitting(false)
    }
  }, [instruction, submitting, currentProject, submitInstruction])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault()
        handleSubmit()
      }
    },
    [handleSubmit],
  )

  const displayError = error ?? contextError

  return (
    <div className="max-w-[600px] w-full flex flex-col items-center px-4">
      {/* Header */}
      <div className="mb-8 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-surface border border-border shadow-[0_8px_32px_rgba(0,0,0,0.4)] mb-6">
          <svg className="w-8 h-8 text-primary" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2L9.19 8.63L2 9.24l5.46 4.73L5.82 21L12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2zm0 3.7l1.71 4.04 4.38.38-3.32 2.88 1 4.28L12 14.91l-3.77 2.37 1-4.28-3.32-2.88 4.38-.38L12 5.7z" />
          </svg>
        </div>
        <h1 className="text-3xl font-bold text-text mb-3 tracking-tight">
          What are we building today?
        </h1>
        <p className="text-muted text-sm">
          Start by describing your task, or open a file to begin editing.
        </p>
      </div>

      {/* Error banner */}
      {displayError && (
        <div
          className="w-full mb-4 px-4 py-3 rounded-xl border-l-4 border-error text-sm text-text cursor-pointer"
          style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)' }}
          onClick={() => setError(null)}
        >
          {displayError}
        </div>
      )}

      {/* Prompt input */}
      <div className="w-full glass-panel rounded-2xl p-2 flex flex-col shadow-[0_16px_40px_rgba(0,0,0,0.5)] border-t border-t-white/10 transition-all focus-within:shadow-[0_0_30px_rgba(99,102,241,0.15)] relative overflow-hidden group">
        {/* Top glow line */}
        <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-white/20 to-transparent opacity-0 group-focus-within:opacity-100 transition-opacity" />

        <textarea
          ref={textareaRef}
          className="w-full min-h-[80px] bg-transparent border-none text-text text-sm placeholder:text-muted/60 resize-none focus:ring-0 focus:outline-none p-3 font-ui"
          placeholder="Ask the AI agent... e.g., 'Refactor auth flow' or 'Create a new dashboard component'"
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={submitting}
        />

        {/* Bottom bar */}
        <div className="flex items-center justify-between px-2 pb-1 pt-2 border-t border-border/50 mt-1">
          <div className="flex items-center gap-1">
            {/* Attach button */}
            <button className="p-1.5 rounded hover:bg-surface-hover text-muted hover:text-text transition-colors">
              <svg className="w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
              </svg>
            </button>
            {/* Model selector */}
            <button className="p-1.5 rounded hover:bg-surface-hover text-muted hover:text-text transition-colors flex items-center gap-1.5 text-xs font-medium">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              gpt-4o
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          </div>

          {/* Send button */}
          <button
            onClick={handleSubmit}
            disabled={submitting || !instruction.trim()}
            className="h-8 w-8 flex items-center justify-center rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors shadow-[0_0_15px_rgba(99,102,241,0.4)] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? (
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              <svg className="w-[18px] h-[18px]" fill="currentColor" viewBox="0 0 24 24">
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Quick actions */}
      <div className="mt-8 flex gap-3 flex-wrap justify-center">
        <button className="px-4 py-2 rounded-full glass-panel text-xs font-medium text-muted hover:text-text transition-all flex items-center gap-2">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          Create new project
        </button>
        <button className="px-4 py-2 rounded-full glass-panel text-xs font-medium text-muted hover:text-text transition-all flex items-center gap-2">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          Open terminal
        </button>
        <button className="px-4 py-2 rounded-full glass-panel text-xs font-medium text-muted hover:text-text transition-all flex items-center gap-2">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          Workspace settings
        </button>
      </div>
    </div>
  )
}
```

### Verification

```bash
cd /Users/rohanthomas/Shipyard/web
npx tsc --noEmit
npm run build
```

---

## Task 8: Agent Panel

**Goal:** Create the right sidebar with welcome card, mode display, recent contexts, and connection status.

**File: `web/src/components/agent/AgentPanel.tsx`**

```tsx
import { useWS } from '../../context/WebSocketContext'
import { useProject } from '../../context/ProjectContext'

export default function AgentPanel() {
  const { status } = useWS()
  const { currentRun } = useProject()

  const isWorking = currentRun?.status === 'running'
  const statusLabel = isWorking ? 'Agent Working' : 'Agent Idle'
  const dotColor = status === 'disconnected'
    ? 'bg-warning'
    : isWorking
      ? 'bg-warning'
      : 'bg-primary'
  const statusSubtext = status === 'disconnected'
    ? 'Disconnected — reconnecting...'
    : undefined

  return (
    <aside className="glass-panel rounded-2xl flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <svg className="w-[18px] h-[18px] text-primary" fill="currentColor" viewBox="0 0 24 24">
            <path d="M20 9V7c0-1.1-.9-2-2-2h-3c0-1.66-1.34-3-3-3S9 3.34 9 5H6c-1.1 0-2 .9-2 2v2c-1.66 0-3 1.34-3 3s1.34 3 3 3v4c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2v-4c1.66 0 3-1.34 3-3s-1.34-3-3-3zM7.5 11.5c0-.83.67-1.5 1.5-1.5s1.5.67 1.5 1.5S9.83 13 9 13s-1.5-.67-1.5-1.5zM16 17H8v-2h8v2zm-1-4c-.83 0-1.5-.67-1.5-1.5S14.17 10 15 10s1.5.67 1.5 1.5S15.83 13 15 13z" />
          </svg>
          <h2 className="text-sm font-bold text-text">AI Agent</h2>
        </div>
        <button className="p-1 rounded hover:bg-surface-hover text-muted transition-colors">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
          </svg>
        </button>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {/* Welcome card */}
        <div className="p-4 rounded-xl border border-border bg-surface/40 relative overflow-hidden">
          <div className="absolute -top-10 -right-10 w-24 h-24 bg-primary/20 blur-[20px] rounded-full" />
          <p className="text-sm text-text font-medium mb-2 relative z-10">
            Welcome to your workspace.
          </p>
          <p className="text-xs text-muted leading-relaxed relative z-10 mb-4">
            I'm ready to help you write, refactor, and understand your code.
            Just ask me anything in the prompt box.
          </p>
          <button className="w-full flex items-center justify-center gap-2 h-8 rounded-lg bg-primary/10 text-primary border border-primary/20 hover:bg-primary/20 transition-colors text-xs font-semibold relative z-10">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            New Chat
          </button>
        </div>

        {/* Mode display */}
        <div className="flex items-center justify-between px-1">
          <span className="text-xs font-medium text-muted">Mode</span>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted">Supervised</span>
            <div className="w-9 h-5 rounded-full bg-white/10 relative cursor-not-allowed opacity-60">
              <div className="w-4 h-4 rounded-full bg-white absolute top-0.5 left-0.5 transition-all" />
            </div>
          </div>
        </div>

        {/* Recent contexts */}
        <div className="flex flex-col gap-2">
          <h3 className="text-xs font-bold uppercase text-muted tracking-wider px-1 mb-1">
            Recent Contexts
          </h3>
          {[
            { title: 'Fix layout bug in header', time: 'Yesterday', count: 4 },
            { title: 'Optimize database query', time: '2 days ago', count: 12 },
            { title: 'Setup initial project structure', time: 'Last week', count: 24 },
          ].map((item) => (
            <button
              key={item.title}
              className="w-full flex items-start gap-3 p-2.5 rounded-xl hover:bg-surface-hover transition-colors text-left group"
            >
              <svg className="w-4 h-4 text-muted mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              <div className="flex-1 overflow-hidden">
                <p className="text-sm text-text font-medium truncate group-hover:text-primary transition-colors">
                  {item.title}
                </p>
                <p className="text-xs text-muted truncate">
                  {item.time} &bull; {item.count} messages
                </p>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Status indicator */}
      <div className="px-4 py-3 border-t border-border/50 flex items-center gap-2">
        <div className="relative flex h-2 w-2">
          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${dotColor} opacity-75`} />
          <span className={`relative inline-flex rounded-full h-2 w-2 ${dotColor}`} />
        </div>
        <div className="flex flex-col">
          <span className="text-xs text-muted">{statusLabel}</span>
          {statusSubtext && (
            <span className="text-[10px] text-warning">{statusSubtext}</span>
          )}
        </div>
      </div>
    </aside>
  )
}
```

### Verification

```bash
cd /Users/rohanthomas/Shipyard/web
npx tsc --noEmit
npm run build
```

---

## Task 9: File Tree + Run List

**Goal:** Create the left sidebar components — FileTree with empty/active states, and RunList with status badges.

### 9a. FileTree

**File: `web/src/components/explorer/FileTree.tsx`**

```tsx
import { useEffect, useState, useCallback } from 'react'
import { useProject } from '../../context/ProjectContext'
import { useWS } from '../../context/WebSocketContext'

interface FileEntry {
  path: string
  action: 'read' | 'write'
}

export default function FileTree() {
  const { currentProject, currentRun } = useProject()
  const { subscribe } = useWS()
  const [files, setFiles] = useState<FileEntry[]>([])

  // Accumulate file events from WebSocket
  useEffect(() => {
    const unsub = subscribe('file', (event) => {
      const path = event.data.path as string
      const action = event.data.action as 'read' | 'write'
      if (!path) return
      setFiles((prev) => {
        const existing = prev.find((f) => f.path === path)
        if (existing) {
          // Upgrade read -> write if needed
          if (action === 'write' && existing.action === 'read') {
            return prev.map((f) => (f.path === path ? { ...f, action: 'write' } : f))
          }
          return prev
        }
        return [...prev, { path, action }]
      })
    })
    return unsub
  }, [subscribe])

  // Reset files when run changes
  useEffect(() => {
    setFiles([])
  }, [currentRun?.id])

  const hasProject = !!currentProject || !!currentRun

  if (!hasProject || files.length === 0) {
    return <EmptyState />
  }

  return <ActiveTree files={files} />
}

function EmptyState() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-4 h-full">
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="w-12 h-12 rounded-full bg-surface border border-border flex items-center justify-center text-muted">
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z" />
          </svg>
        </div>
        <div>
          <p className="text-text text-sm font-semibold mb-1">No project selected</p>
          <p className="text-muted text-xs leading-relaxed max-w-[180px]">
            Open a folder or repository to start working.
          </p>
        </div>
        <button className="mt-2 flex items-center justify-center h-8 px-4 rounded-lg bg-surface hover:bg-surface-hover border border-border text-xs font-semibold text-text transition-colors w-full">
          Open Folder
        </button>
        <button className="flex items-center justify-center h-8 px-4 rounded-lg bg-transparent hover:bg-surface-hover text-xs font-semibold text-muted transition-colors w-full">
          Clone Repository
        </button>
      </div>
    </div>
  )
}

function ActiveTree({ files }: { files: FileEntry[] }) {
  // Group files by directory for display
  const sortedFiles = [...files].sort((a, b) => a.path.localeCompare(b.path))

  return (
    <div className="py-2">
      {sortedFiles.map((file) => {
        const parts = file.path.split('/')
        const filename = parts[parts.length - 1]
        const depth = Math.min(parts.length - 1, 4)
        const paddingLeft = 16 + depth * 16

        return (
          <div
            key={file.path}
            className="pr-4 py-1.5 flex items-center gap-2 text-sm cursor-pointer hover:bg-white/5"
            style={{ paddingLeft }}
            title={file.path}
          >
            <svg className="w-4 h-4 text-[#3178C6] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span className="truncate text-text">{filename}</span>
            {file.action === 'write' && (
              <span className="ml-auto w-2 h-2 rounded-full bg-warning shrink-0" />
            )}
          </div>
        )
      })}
    </div>
  )
}
```

### 9b. RunList

**File: `web/src/components/explorer/RunList.tsx`**

```tsx
import { useProject } from '../../context/ProjectContext'
import type { Run } from '../../types'

const STATUS_COLORS: Record<string, string> = {
  completed: 'bg-success',
  running: 'bg-primary',
  waiting_for_human: 'bg-warning',
  failed: 'bg-error',
  error: 'bg-error',
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export default function RunList() {
  const { runs, currentRun, setCurrentRun } = useProject()

  if (runs.length === 0) return null

  return (
    <div className="mx-4 py-4 border-t border-border shrink-0">
      <h3 className="text-xs font-bold uppercase text-muted tracking-wider mb-3">
        Runs
      </h3>
      <div className="space-y-2 max-h-[200px] overflow-y-auto">
        {runs.slice(0, 10).map((run) => (
          <RunCard
            key={run.id}
            run={run}
            isActive={currentRun?.id === run.id}
            onSelect={() => setCurrentRun(run)}
          />
        ))}
      </div>
    </div>
  )
}

function RunCard({
  run,
  isActive,
  onSelect,
}: {
  run: Run
  isActive: boolean
  onSelect: () => void
}) {
  const dotColor = STATUS_COLORS[run.status] ?? 'bg-muted'
  const bgClass = isActive ? 'bg-surface border-primary/30' : 'bg-surface/50 border-border'

  return (
    <div
      className={`${bgClass} border rounded-lg p-2.5 cursor-pointer hover:bg-surface-hover transition-colors`}
      onClick={onSelect}
    >
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${dotColor} shrink-0`} />
        <span className={`text-xs font-medium ${isActive ? 'text-text' : 'text-muted'}`}>
          Run #{run.id.slice(0, 4)}
        </span>
        <span className="text-[10px] text-muted ml-auto">
          {timeAgo(run.created_at)}
        </span>
      </div>
      <p className="text-[10px] text-muted mt-1 truncate">{run.instruction}</p>
    </div>
  )
}
```

### Verification

```bash
cd /Users/rohanthomas/Shipyard/web
npx tsc --noEmit
npm run build
```

---

## Task 10: Production Static Serving + Build Verification

**Goal:** Configure FastAPI to serve the built frontend in production, verify the full build pipeline.

### 10a. Add static file serving to `server/main.py`

Add these imports at the top of `server/main.py` (merge with existing imports):

```python
from fastapi.staticfiles import StaticFiles
```

Add this block at the **very end** of `server/main.py`, after all route definitions and the websocket endpoint:

```python
# Serve frontend in production (after all API routes)
_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "web", "dist")
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
```

**Important:** This must be the last thing in the file. FastAPI `mount` with `"/"` is a catch-all — any route mounted after it will be shadowed. Since all API routes are registered before this, they take precedence.

### 10b. Build and verify

```bash
cd /Users/rohanthomas/Shipyard/web
npm run build
# Should output: dist/ directory with index.html + assets

ls dist/
# Should show: index.html, assets/
```

### 10c. Full-stack smoke test

```bash
cd /Users/rohanthomas/Shipyard

# Build frontend
cd web && npm run build && cd ..

# Start backend (serves both API and static frontend)
uvicorn server.main:app --port 8000 &
SERVER_PID=$!
sleep 2

# Test API still works
curl -s http://localhost:8000/health
# Should return: {"status":"ok"}

# Test frontend is served
curl -s http://localhost:8000/ | head -5
# Should show <!DOCTYPE html> with Shipyard title

# Clean up
kill $SERVER_PID
```

### 10d. Run all backend tests to confirm nothing is broken

```bash
cd /Users/rohanthomas/Shipyard
python -m pytest tests/ -v
# All existing tests + new frontend endpoint tests should pass
```

### Verification

The full build pipeline works:
1. `npm run build` in `web/` produces `web/dist/`
2. FastAPI serves `web/dist/` at `/` while keeping all API routes functional
3. All backend tests pass
4. Opening `http://localhost:8000` in a browser shows the Frosted Glassmorphic IDE with:
   - Animated mesh background (blue, purple, pink blobs)
   - Left sidebar with "No project selected" empty state
   - Center area with "What are we building today?" prompt
   - Right sidebar with welcome card and status indicator

---

## Summary of All Files

### Backend changes (Task 1)
| File | Action |
|---|---|
| `server/main.py` | Add `project_response` helper, `UpdateProjectRequest`, `PUT /projects/{id}`, `GET /runs/{id}/edits`, static file mount |
| `agent/events.py` | Expand `get_snapshot` with additional fields |
| `tests/test_backend_frontend_endpoints.py` | New test file for frontend-required endpoints |

### Frontend files (Tasks 2-9)
| File | Purpose |
|---|---|
| `web/index.html` | Entry HTML with Google Fonts |
| `web/vite.config.ts` | Vite config with proxy + Tailwind v4 |
| `web/package.json` | (scaffolded by Vite) |
| `web/tsconfig.json` | (scaffolded by Vite) |
| `web/src/main.tsx` | React entry point |
| `web/src/App.tsx` | Root component with providers |
| `web/src/styles/glass.css` | Tailwind v4 @theme tokens + glass utilities |
| `web/src/types/index.ts` | TypeScript interfaces |
| `web/src/lib/api.ts` | REST API client |
| `web/src/hooks/useWebSocket.ts` | WebSocket lifecycle hook |
| `web/src/context/WebSocketContext.tsx` | WebSocket event distribution context |
| `web/src/context/ProjectContext.tsx` | Project + run state management |
| `web/src/components/layout/MeshBackground.tsx` | Animated gradient background |
| `web/src/components/layout/AppShell.tsx` | 3-column IDE grid layout |
| `web/src/components/layout/ErrorBoundary.tsx` | React error boundary |
| `web/src/components/home/WorkspaceHome.tsx` | Home screen with prompt input |
| `web/src/components/agent/AgentPanel.tsx` | Right sidebar agent panel |
| `web/src/components/explorer/FileTree.tsx` | File tree with empty/active states |
| `web/src/components/explorer/RunList.tsx` | Run list with status badges |
