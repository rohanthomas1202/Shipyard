# Phase 2b: React Frontend — Frosted Glassmorphic IDE

## Overview

Phase 2b builds the web frontend for Shipyard — a Frosted Glassmorphic IDE that connects to the existing FastAPI + WebSocket backend. Built in two sub-phases: 2b-1 delivers a functional MVP (scaffold, shared infrastructure, Workspace Home), 2b-2 adds the rich experience (Diff Viewer, AI Streaming, Settings).

**Builds on:** Phase 2a (WebSocket event bus, approval state machine, Git integration — 216 backend tests passing)

**Commit rule:** Never include `Co-Authored-By` lines in commit messages.

---

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Framework | Vite + React + TypeScript | Fast builds, standard React DX |
| Styling | Tailwind CSS v4 | Design tokens from spec, utility-first |
| State management | React Context only | Single-user app, 2 contexts sufficient |
| Diff viewer | Custom HTML table | Matches glassmorphic design, no dependency |
| Dev serving | Vite dev server with proxy | Hot reload, proxies /api and /ws to FastAPI |
| Prod serving | FastAPI serves `web/dist/` static files | Single process, single port deployment |

---

## Sub-phase 2b-1: Scaffold + Shared Infrastructure + Workspace Home

### File Structure

```
web/
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── public/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── styles/
│   │   └── glass.css
│   ├── types/
│   │   └── index.ts
│   ├── lib/
│   │   └── api.ts
│   ├── context/
│   │   ├── WebSocketContext.tsx
│   │   └── ProjectContext.tsx
│   ├── hooks/
│   │   ├── useWebSocket.ts
│   │   └── useEvents.ts
│   └── components/
│       ├── layout/
│       │   ├── AppShell.tsx
│       │   └── MeshBackground.tsx
│       ├── explorer/
│       │   ├── FileTree.tsx
│       │   └── RunList.tsx
│       ├── home/
│       │   └── WorkspaceHome.tsx
│       └── agent/
│           └── AgentPanel.tsx
```

### Design System (`glass.css`)

CSS custom properties and utility classes extracted from the user's HTML mockups:

```css
:root {
  --color-primary: #6366F1;
  --color-background: #0F111A;
  --color-surface: rgba(30, 33, 43, 0.6);
  --color-border: rgba(255, 255, 255, 0.08);
  --color-text: #F8FAFC;
  --color-muted: #94A3B8;
  --font-ui: 'Plus Jakarta Sans', sans-serif;
  --font-code: 'JetBrains Mono', monospace;
  --radius-panel: 16px;
  --radius-element: 8px;
  --blur-heavy: blur(24px);
}

.glass-panel {
  background-color: var(--color-surface);
  backdrop-filter: var(--blur-heavy);
  border: 1px solid var(--color-border);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  border-radius: var(--radius-panel);
}
```

Fonts: Plus Jakarta Sans (UI) + JetBrains Mono (code), loaded via Google Fonts in `index.html`.

### WebSocket Client

#### `useWebSocket` Hook

Low-level hook managing the WebSocket lifecycle:

```typescript
function useWebSocket(projectId: string): {
  status: 'connecting' | 'connected' | 'disconnected';
  send: (data: object) => void;
  onMessage: (handler: (event: WSEvent) => void) => () => void;
}
```

Behaviors:
- Connects to `/ws/{projectId}` (proxied in dev, direct in prod)
- Auto-reconnect with exponential backoff: 1s, 2s, 4s, max 10s
- On reconnect: sends `{"action": "reconnect", "run_id": "...", "last_seq": N}`
- Heartbeat tracking: if 3 missed (45s), force reconnect
- Returns unsubscribe function from `onMessage`

#### `WebSocketContext`

Wraps `useWebSocket` and provides event distribution to components:

```typescript
interface WebSocketContextValue {
  status: 'connecting' | 'connected' | 'disconnected';
  subscribe: (eventType: string, handler: (event: WSEvent) => void) => () => void;
  send: (data: object) => void;
  snapshot: RunSnapshot | null;
}
```

Key design:
- Streaming tokens stored in `useRef` + local component state, NOT in Context (avoids re-rendering entire tree per token)
- `snapshot` stored in Context state (changes infrequently)
- `last_seq` tracked per run for reconnect cursor
- `subscribe` returns unsubscribe function for `useEffect` cleanup

#### `ProjectContext`

```typescript
interface ProjectContextValue {
  projects: Project[];
  currentProject: Project | null;
  runs: Run[];
  currentRun: Run | null;
  setCurrentProject: (project: Project) => void;
  submitInstruction: (instruction: string, workingDir: string, context?: object) => Promise<string>;
  refreshProjects: () => Promise<void>;
}
```

- Fetches projects from `GET /projects` on mount
- Creates projects via `POST /projects`
- Submits instructions via `POST /instruction`
- Polls `GET /status/{run_id}` as fallback when WebSocket is down
- `currentRun` tracks the active run for UI state

### API Client (`lib/api.ts`)

Thin fetch wrapper for all REST endpoints:

```typescript
const api = {
  // Projects
  getProjects: () => Promise<Project[]>,
  createProject: (name: string, path: string) => Promise<Project>,
  getProject: (id: string) => Promise<Project>,

  // Instructions
  submitInstruction: (instruction: string, workingDirectory: string, context?: object, projectId?: string) => Promise<{ run_id: string, status: string }>,
  getStatus: (runId: string) => Promise<RunStatus>,

  // Edits
  patchEdit: (runId: string, editId: string, action: 'approve' | 'reject', opId: string) => Promise<EditResponse>,

  // Git
  gitCommit: (runId: string, message?: string) => Promise<{ sha: string, message: string }>,
  gitPush: (runId: string) => Promise<{ branch: string, status: string }>,
  gitCreatePR: (runId: string, title?: string, body?: string, draft?: boolean) => Promise<{ number: number, html_url: string }>,
  gitMerge: (runId: string, prNumber: number, method?: string) => Promise<{ merged: boolean, sha: string }>,
}
```

Base URL: empty string (same origin in prod, proxied in dev).

### Components (2b-1)

#### AppShell

Root layout component:
- 3-column CSS grid: `grid-template-columns: 250px 1fr 300px`
- Full viewport: `h-screen w-screen p-4 gap-4`
- Renders: `<FileTree />` | `<CenterContent />` | `<AgentPanel />`
- Center content switches based on `currentRun` state

#### MeshBackground

Fixed-position animated background:
- Three `div` blobs with `filter: blur(120px)`, absolute positioned
- Colors: `#3B82F6`, `#8B5CF6`, `#EC4899`
- CSS `@keyframes float` animation (20s, ease-in-out, alternate)
- `z-index: -1`, behind all content

#### WorkspaceHome

Center panel empty state:
- Sparkle icon + "What are we building today?" heading
- Prompt `<textarea>` (600px max-width, glassmorphic styling)
- Bottom bar: attach button, model selector, send button
- Quick action pills: Create project, Open terminal, Settings
- Send button calls `submitInstruction()` from ProjectContext
- On submit: sets `currentRun`, UI shows "Running..." status indicator

#### AgentPanel

Right sidebar (basic for 2b-1):
- Welcome card with gradient decoration
- "New Chat" button
- Mode display: "Supervised" / "Autonomous" label (read-only in 2b-1)
- Recent contexts list (static placeholder or from conversations API)
- Bottom status: pulsing dot + "Agent Idle" / "Agent Working" (driven by WebSocket status + currentRun)

#### FileTree

Left sidebar:
- **Empty state:** folder icon, "No project selected", Open Folder / Clone Repository buttons
- **Active state:** nested tree of files from working directory (fetched or derived from run context)
- Modified files shown with yellow dot indicator
- Runs section below tree: list of recent runs with status badges

#### RunList

Sub-component of FileTree sidebar:
- Shows recent runs for current project
- Status badges: green (completed), blue (running), yellow (waiting_for_human), red (failed)
- Click sets `currentRun`

### Vite Config

```typescript
// vite.config.ts
export default defineConfig({
  plugins: [react()],
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

### Production Static Serving

Add to `server/main.py` (after all API routes):

```python
from fastapi.staticfiles import StaticFiles
import os

# Serve frontend in production (after all API routes)
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "web", "dist")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
```

---

## Sub-phase 2b-2: Diff Viewer + AI Streaming + Settings

### Additional Files

```
src/components/
├── editor/
│   ├── DiffViewer.tsx        # Full diff view with accept/reject
│   ├── DiffLine.tsx          # Single diff line (add/remove/context)
│   └── DiffHeader.tsx        # File header with action buttons
├── agent/
│   ├── StreamingText.tsx     # Token-by-token text display
│   ├── TypingIndicator.tsx   # 3 bouncing dots
│   ├── ActionBlock.tsx       # "Editing file..." with spinner
│   ├── StepTimeline.tsx      # Step progress (1-N with status)
│   └── AutonomyToggle.tsx    # Supervised ↔ Autonomous switch
├── git/
│   ├── CommitDialog.tsx      # Commit message editor
│   └── PRPanel.tsx           # PR creation/status
└── settings/
    ├── SettingsModal.tsx      # Modal overlay
    └── tabs/
        ├── GeneralTab.tsx
        ├── AIModelsTab.tsx
        ├── EnvironmentTab.tsx
        └── GitHubTab.tsx
```

### DiffViewer

Custom HTML table component:
- Dual line numbers (old/new) in left columns
- Syntax-highlighted code lines using static CSS classes (One Dark theme colors)
- Addition rows: `rgba(16, 185, 129, 0.15)` background, green left border
- Deletion rows: `rgba(239, 68, 68, 0.15)` background, red left border
- Hover highlight: `rgba(255, 255, 255, 0.03)`
- Sticky file header with Accept / Reject buttons
- Bottom bar: Commit & Push button, changeset summary

Data source: `diff` events from WebSocket, or `GET /runs/{id}/edits` for review

### AI Streaming

Full agent panel when a run is active:
- **StepTimeline:** horizontal progress showing plan steps (done/active/pending)
- **StreamingText:** displays tokens from `stream` events using `useRef` to avoid re-renders. Appends to a DOM element directly for performance.
- **TypingIndicator:** 3 bouncing indigo dots, shown while waiting for first token
- **ActionBlock:** "Editing src/auth.ts..." card with spinning border gradient
- **ChatBubble:** user messages (right-aligned, dark) and agent messages (left-aligned, indigo tint)

Token streaming approach:
```typescript
// In StreamingText component
const textRef = useRef<HTMLSpanElement>(null)

useEffect(() => {
  const unsub = subscribe('stream', (event) => {
    if (textRef.current) {
      textRef.current.textContent += event.data.token
    }
    if (event.data.done) {
      // Finalize — set state for persistence
    }
  })
  return unsub
}, [])
```

### AutonomyToggle

Toggle switch in agent panel:
- Visual: track with sliding thumb (CSS transition)
- Sends `{"action": "update_mode", "mode": "autonomous"}` via WebSocket
- Label updates: "Supervised" ↔ "Autonomous"

### SettingsModal

Centered modal (600px) with glassmorphic depth:
- Heavy backdrop blur over existing content
- Tabs: General | AI Models | Environment | GitHub
- **General:** project name, working directory
- **AI Models:** default model selector, autonomy mode default
- **Environment:** test command, build command, lint command
- **GitHub:** repo (owner/repo), PAT (password field), default reviewers, draft PR toggle
- Save button calls `PUT /projects/{id}` (needs to be added to backend)

### Git Components

- **CommitDialog:** shows generated commit message, editable textarea, Commit & Push button
- **PRPanel:** shows PR status after creation, link to GitHub

---

## TypeScript Types (`types/index.ts`)

```typescript
interface Project {
  id: string; name: string; path: string;
  github_repo: string | null; autonomy_mode: string;
  default_model: string;
}

interface Run {
  id: string; project_id: string; instruction: string;
  status: 'running' | 'completed' | 'failed' | 'error' | 'waiting_for_human';
}

interface WSEvent {
  type: string; run_id: string; seq: number;
  node: string | null; model: string | null;
  data: Record<string, any>; timestamp: number;
}

interface RunSnapshot {
  type: 'snapshot'; run_id: string; status: string;
  last_seq: number;
}

interface Edit {
  id: string; run_id: string; file_path: string;
  status: 'proposed' | 'approved' | 'rejected' | 'applied' | 'committed';
  old_content: string | null; new_content: string | null;
  anchor: string | null;
}
```

---

## Testing Strategy

- **No unit tests for React components in 2b-1** — the app is visual and connects to a real backend. Manual testing via browser is the primary validation.
- **Type safety** via TypeScript strict mode catches most issues at build time.
- **Build verification:** `vite build` must succeed without errors.
- **E2E tests (future):** Playwright tests can be added later against the running app.

---

## Deployment

### Development
```bash
# Terminal 1: backend
cd /Users/rohanthomas/Shipyard && uvicorn server.main:app --reload --port 8000

# Terminal 2: frontend
cd /Users/rohanthomas/Shipyard/web && npm run dev
```

### Production
```bash
cd /Users/rohanthomas/Shipyard/web && npm run build
cd /Users/rohanthomas/Shipyard && uvicorn server.main:app --host 0.0.0.0 --port $PORT
```

FastAPI serves `web/dist/` as static files. Single process, single port.

### Procfile (Railway)
```
web: cd web && npm run build && cd .. && uvicorn server.main:app --host 0.0.0.0 --port $PORT
```
