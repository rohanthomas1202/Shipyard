# Sub-phase 2b-2: Rich UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add DiffViewer, AI streaming, settings, git components, keyboard shortcuts, error handling, and responsive layout to the Shipyard IDE frontend.

**Architecture:** React components connecting to existing WebSocket/Project contexts from 2b-1. StreamingText uses useRef for DOM updates to avoid Context re-renders. DiffViewer is a custom HTML table. SettingsModal is a portal-based overlay.

**Tech Stack:** React 18, TypeScript, Tailwind CSS v4

**Spec:** `docs/superpowers/specs/2026-03-25-phase2b-frontend-design.md` (Sub-phase 2b-2)

**Demo:** `demo/index.html` — visual reference for all screens

**Prerequisite:** Sub-phase 2b-1 must be complete.

**Commit rule:** Never include `Co-Authored-By` lines in commit messages.

---

## File Structure

### New Files
- `web/src/components/editor/DiffLine.tsx` — Single diff row (addition/deletion/context)
- `web/src/components/editor/DiffHeader.tsx` — Sticky file header with Accept/Reject buttons
- `web/src/components/editor/DiffViewer.tsx` — Full diff table with Commit & Push footer
- `web/src/components/agent/TypingIndicator.tsx` — 3 bouncing dots animation
- `web/src/components/agent/ActionBlock.tsx` — "Editing file..." card with spinning border
- `web/src/components/agent/StreamingText.tsx` — Token-by-token display via useRef
- `web/src/components/agent/StepTimeline.tsx` — Horizontal step progress indicator
- `web/src/components/agent/ChatBubble.tsx` — User/agent message bubbles
- `web/src/components/agent/AutonomyToggle.tsx` — Supervised/Autonomous toggle switch
- `web/src/components/settings/SettingsModal.tsx` — Glassmorphic modal overlay with tabs
- `web/src/components/settings/tabs/GeneralTab.tsx` — Project name, working directory
- `web/src/components/settings/tabs/AIModelsTab.tsx` — Model selector, autonomy default
- `web/src/components/settings/tabs/EnvironmentTab.tsx` — Test/build/lint commands
- `web/src/components/settings/tabs/GitHubTab.tsx` — Repo, PAT, reviewers, draft toggle
- `web/src/components/git/CommitDialog.tsx` — Commit message editor + push button
- `web/src/components/git/PRPanel.tsx` — PR creation and status display
- `web/src/hooks/useHotkeys.ts` — Thin keydown event wrapper
- `web/src/components/layout/ErrorBoundary.tsx` — React error boundary
- `web/src/components/shared/ErrorBanner.tsx` — Inline error display with auto-dismiss

### Modified Files
- `web/src/components/layout/AppShell.tsx` — Add collapsible sidebars, wire DiffViewer into center panel, wrap children in ErrorBoundary
- `web/src/components/agent/AgentPanel.tsx` — Integrate streaming UI, AutonomyToggle, settings button
- `web/src/components/home/WorkspaceHome.tsx` — Wire settings button to open modal
- `web/src/App.tsx` — Wrap AppShell in ErrorBoundary, add SettingsModal portal

---

## Design Tokens Reference

All components use these values from `glass.css` (defined in 2b-1):

| Token | Value |
|---|---|
| Background | `#0F111A` |
| Surface | `rgba(30, 33, 43, 0.6)` + `backdrop-filter: blur(24px)` |
| Primary | `#6366F1` |
| Text Primary | `#F8FAFC` |
| Text Muted | `#94A3B8` |
| Error | `#EF4444` |
| Success | `#10B981` |
| Border | `rgba(255, 255, 255, 0.08)` |
| Diff Add BG | `rgba(16, 185, 129, 0.15)` |
| Diff Add Border | `rgba(16, 185, 129, 0.8)` |
| Diff Remove BG | `rgba(239, 68, 68, 0.15)` |
| Diff Remove Border | `rgba(239, 68, 68, 0.8)` |
| Panel Radius | `16px` |
| Element Radius | `8px` |
| Font UI | `Plus Jakarta Sans` |
| Font Code | `JetBrains Mono` |

---

## Task 1: DiffViewer Components

**Files:**
- Create: `web/src/components/editor/DiffLine.tsx`
- Create: `web/src/components/editor/DiffHeader.tsx`
- Create: `web/src/components/editor/DiffViewer.tsx`
- Modify: `web/src/components/layout/AppShell.tsx`

**Verification:** `npm run build` succeeds. Browser shows diff table when navigating to a run with pending edits.

- [ ] **Step 1: Create DiffLine component**

```typescript
// web/src/components/editor/DiffLine.tsx
//
// Single row in the diff table. Receives:
//   type: 'addition' | 'deletion' | 'context'
//   oldLineNum: number | null
//   newLineNum: number | null
//   content: string (raw code text)
//
// Styling per type:
//   addition: bg-[rgba(16,185,129,0.15)], border-l-[3px] border-[rgba(16,185,129,0.8)], text-text (full opacity)
//   deletion: bg-[rgba(239,68,68,0.15)], border-l-[3px] border-[rgba(239,68,68,0.8)], text-red-400/90
//   context:  no bg, text-text/80
//
// Structure: <tr> with 3 <td> cells:
//   td1: old line number (centered, text-muted/40, select-none, border-r border-border, w-[50px])
//   td2: new line number (same styling as td1)
//   td3: code content (pl-4, whitespace-pre, font-code text-[13px] leading-[1.7])
//
// Hover: .diff-row:hover { background-color: rgba(255, 255, 255, 0.03); }
//   — apply className="diff-row" to context rows (already defined in glass.css from 2b-1)
//
// Line numbers: show number when present, empty string when null
//   addition rows: oldLineNum is null (empty td1), newLineNum shows in green (text-emerald-400/80)
//   deletion rows: newLineNum is null (empty td2), oldLineNum shows in red (text-red-400/70)
//
// Export as default: export default function DiffLine(...)
```

- [ ] **Step 2: Create DiffHeader component**

```typescript
// web/src/components/editor/DiffHeader.tsx
//
// Sticky header bar above each file's diff. Receives:
//   filePath: string (e.g. "src/auth.ts")
//   stepLabel: string (e.g. "Refactoring Auth Flow — Step 2/5")
//   editId: string (for approve/reject API calls)
//   runId: string
//   onApprove: () => void
//   onReject: () => void
//   isLoading: boolean (disables buttons, shows spinner on active button)
//
// Layout: flex row, items-center, justify-between, border-b border-border,
//   px-6, h-[56px], bg-surface/50, backdrop-blur-md, sticky top-0 z-10
//
// Left side:
//   - Icon container: rounded-lg bg-white/10 w-8 h-8 flex items-center justify-center text-primary
//     containing a code_blocks icon (use inline SVG or text "{ }" fallback)
//   - File info div:
//     h2: text-[15px] font-semibold leading-tight font-code text-text — shows filePath
//     p: text-muted text-[11px] font-medium uppercase tracking-wider — shows stepLabel
//
// Right side: flex gap-3
//   - Reject button: rounded-lg h-8 px-4 bg-transparent border border-border
//     hover:bg-white/5 text-text text-[13px] font-semibold transition-colors
//     Shows "Reject", disabled when isLoading
//   - Accept button: rounded-lg h-8 px-4 bg-primary hover:bg-primary/90 text-white
//     text-[13px] font-semibold shadow-[0_0_15px_rgba(99,102,241,0.4)] transition-all
//     Shows checkmark icon + "Accept", disabled when isLoading
//     When isLoading and this was clicked: show spinner instead of checkmark
//
// Both buttons call their respective handlers on click.
```

- [ ] **Step 3: Create DiffViewer component**

```typescript
// web/src/components/editor/DiffViewer.tsx
//
// Full diff viewer that shows one or more file diffs with a bottom action bar.
//
// Props:
//   edits: Edit[] (from types/index.ts — the pending edits for current run)
//   runId: string
//   onEditAction: (editId: string, action: 'approve' | 'reject') => Promise<void>
//
// State:
//   loadingEditId: string | null — which edit is currently being approved/rejected
//   error: string | null — API error message
//
// Structure:
//   Outer: flex flex-col, glass-panel rounded-2xl, overflow-hidden, full height
//
//   For each edit in edits:
//     <DiffHeader
//       filePath={edit.file_path}
//       stepLabel={`Step ${edit.step}`}
//       editId={edit.id}
//       runId={runId}
//       onApprove={() => handleAction(edit.id, 'approve')}
//       onReject={() => handleAction(edit.id, 'reject')}
//       isLoading={loadingEditId === edit.id}
//     />
//     <div className="flex-1 overflow-auto font-code text-[13px] leading-[1.7]">
//       <table className="w-full text-left border-collapse">
//         <colgroup>
//           <col className="w-[50px]" />
//           <col className="w-[50px]" />
//           <col />
//         </colgroup>
//         <tbody>
//           {parseDiffLines(edit).map(line => <DiffLine key={...} {...line} />)}
//         </tbody>
//       </table>
//     </div>
//
//   Bottom action bar:
//     flex items-center gap-3 px-6 py-3 border-t border-border bg-surface/50 backdrop-blur-md
//     - "Commit & Push" button: flex items-center gap-2 px-4 py-2 rounded-lg bg-primary
//       text-white text-xs font-semibold shadow-[0_0_15px_rgba(99,102,241,0.3)]
//       hover:bg-primary/90 transition-all
//       Clicking opens CommitDialog (emit via callback prop or local state)
//     - Changeset summary: text-muted text-xs — "N files changed, X additions, Y deletions"
//     - Right side: "Approve All" button: px-3 py-1.5 rounded-lg border border-border
//       text-xs font-medium text-muted hover:text-text hover:bg-surface-hover
//
// Diff parsing helper (inline in file):
//   parseDiffLines(edit: Edit): DiffLineData[]
//   Compares edit.old_content and edit.new_content line by line:
//   1. Split both into lines
//   2. Use a simple LCS or line-by-line comparison:
//      - Lines only in old: deletion
//      - Lines only in new: addition
//      - Lines in both (same): context
//   3. Return array of { type, oldLineNum, newLineNum, content }
//   For MVP, a simple sequential diff (walk both arrays) is sufficient.
//   Context lines get both line numbers. Additions get only newLineNum. Deletions get only oldLineNum.
//
// Error display: if error is set, show <ErrorBanner message={error} onDismiss={() => setError(null)} />
//   above the bottom bar.
//
// handleAction function:
//   async (editId, action) => {
//     setLoadingEditId(editId)
//     setError(null)
//     try { await onEditAction(editId, action) }
//     catch (e) { setError(e instanceof Error ? e.message : 'Action failed') }
//     finally { setLoadingEditId(null) }
//   }
```

- [ ] **Step 4: Wire DiffViewer into AppShell center panel**

```typescript
// web/src/components/layout/AppShell.tsx — MODIFY
//
// Import DiffViewer at top:
//   import DiffViewer from '../editor/DiffViewer'
//
// The center panel currently shows WorkspaceHome or a placeholder.
// Add logic: when currentRun exists AND there are pending edits, show DiffViewer.
//
// In the center content area, update the conditional rendering:
//   const { currentRun } = useProject()  // from ProjectContext
//   const [pendingEdits, setPendingEdits] = useState<Edit[]>([])
//
//   useEffect — when currentRun changes:
//     if currentRun, fetch edits via api.getEdits(currentRun.id, 'proposed')
//     setPendingEdits(result)
//
//   Also subscribe to WebSocket 'edit' events to refresh the edits list.
//
//   Rendering logic:
//     if (!currentRun) → <WorkspaceHome />
//     else if (pendingEdits.length > 0) → <DiffViewer edits={pendingEdits} runId={currentRun.id} onEditAction={handleEditAction} />
//     else → streaming/agent view (Task 2)
//
//   handleEditAction:
//     async (editId, action) => {
//       const opId = crypto.randomUUID()
//       await api.patchEdit(currentRun.id, editId, action, opId)
//       // Refresh edits
//       const updated = await api.getEdits(currentRun.id, 'proposed')
//       setPendingEdits(updated)
//     }
```

- [ ] **Step 5: Verify build and test in browser**

```bash
cd /Users/rohanthomas/Shipyard/web && npm run build
# Must succeed with no TypeScript errors.
# Open browser to localhost:5173, verify:
#   - DiffViewer renders when a run has pending edits
#   - Diff table shows additions (green), deletions (red), context lines
#   - Accept/Reject buttons are clickable
#   - Bottom bar shows Commit & Push button
```

- [ ] **Step 6: Commit**

```bash
cd /Users/rohanthomas/Shipyard
git add web/src/components/editor/DiffLine.tsx web/src/components/editor/DiffHeader.tsx web/src/components/editor/DiffViewer.tsx web/src/components/layout/AppShell.tsx
git commit -m "feat: DiffViewer with DiffLine, DiffHeader, accept/reject, commit footer"
```

---

## Task 2: AI Streaming Components

**Files:**
- Create: `web/src/components/agent/TypingIndicator.tsx`
- Create: `web/src/components/agent/ActionBlock.tsx`
- Create: `web/src/components/agent/StreamingText.tsx`
- Create: `web/src/components/agent/StepTimeline.tsx`
- Create: `web/src/components/agent/ChatBubble.tsx`
- Modify: `web/src/components/agent/AgentPanel.tsx`

**Verification:** `npm run build` succeeds. Browser shows streaming UI when a run is active.

- [ ] **Step 1: Create TypingIndicator component**

```typescript
// web/src/components/agent/TypingIndicator.tsx
//
// 3 bouncing dots shown while waiting for first token from agent.
//
// No props needed.
//
// Structure:
//   <div className="flex items-center gap-1.5 px-4 py-3">
//     {[0, 1, 2].map(i => (
//       <div
//         key={i}
//         className="w-2 h-2 rounded-full bg-primary"
//         style={{
//           animation: 'bounce-dot 1.4s infinite ease-in-out both',
//           animationDelay: `${i * 0.16}s`,
//         }}
//       />
//     ))}
//   </div>
//
// The bounce-dot keyframes are already defined in glass.css:
//   @keyframes bounce-dot {
//     0%, 80%, 100% { transform: translateY(0); }
//     40% { transform: translateY(-6px); }
//   }
//
// If not in glass.css yet, add them. They should be there from 2b-1.
//
// Export default.
```

- [ ] **Step 2: Create ActionBlock component**

```typescript
// web/src/components/agent/ActionBlock.tsx
//
// Shows "Editing src/auth.ts..." card with a spinning icon while agent is working on a file.
//
// Props:
//   action: string (e.g. "Editing")
//   filePath: string (e.g. "src/auth.ts")
//   description?: string (e.g. "Replacing jwt.verify with jose jwtVerify")
//
// Structure:
//   <div className="bg-black/40 border border-border rounded-lg p-3 flex items-center gap-3 relative overflow-hidden">
//     {/* Spinning icon */}
//     <svg className="w-[18px] h-[18px] text-primary animate-spin" ...>
//       — use a simple circular arrow/sync SVG icon
//       — or use: <span className="text-[18px] text-primary animate-spin inline-block">&#x21BB;</span>
//     </svg>
//     <div>
//       <p className="text-xs font-code text-text">{action} {filePath}</p>
//       {description && <p className="text-[11px] text-muted">{description}</p>}
//     </div>
//   </div>
//
// The spinning border gradient from the demo (conic-gradient ::before pseudo-element)
// can be added via CSS class "action-block" if defined in glass.css. Add these to glass.css
// if not already present:
//
//   @keyframes spin-border {
//     0% { transform: rotate(0deg); }
//     100% { transform: rotate(360deg); }
//   }
//   .action-block { position: relative; overflow: hidden; }
//   .action-block::before {
//     content: '';
//     position: absolute;
//     inset: -2px;
//     background: conic-gradient(from 0deg, transparent, #6366F1, transparent);
//     animation: spin-border 3s linear infinite;
//     border-radius: 8px;
//     z-index: -1;
//   }
//
// Apply className="action-block" to the outer div if using this effect.
//
// Export default.
```

- [ ] **Step 3: Create StreamingText component**

```typescript
// web/src/components/agent/StreamingText.tsx
//
// Displays token-by-token streaming text from the agent via WebSocket.
// Uses useRef for direct DOM manipulation to avoid React re-renders per token.
//
// Props:
//   runId: string
//   onComplete?: (fullText: string) => void — called when stream is done
//
// Implementation:
//   const textRef = useRef<HTMLSpanElement>(null)
//   const fullTextRef = useRef<string>('')
//   const { subscribe } = useWebSocket()  // from WebSocketContext
//
//   useEffect(() => {
//     const unsub = subscribe('stream', (event: WSEvent) => {
//       if (event.run_id !== runId) return
//       if (textRef.current && event.data.token) {
//         fullTextRef.current += event.data.token
//         textRef.current.textContent = fullTextRef.current
//       }
//       if (event.data.done) {
//         onComplete?.(fullTextRef.current)
//       }
//     })
//     return unsub
//   }, [runId, subscribe, onComplete])
//
// Structure:
//   <div className="text-sm leading-relaxed">
//     <span ref={textRef} />
//     <span className="stream-cursor" />
//   </div>
//
// The stream-cursor class (blinking pipe) is defined in glass.css:
//   .stream-cursor::after {
//     content: '|';
//     color: #6366F1;
//     animation: blink 1s infinite;
//     font-weight: bold;
//   }
//
// When onComplete fires, hide the cursor by conditionally removing the stream-cursor span.
// Use a local state: const [isDone, setIsDone] = useState(false)
// In the onComplete callback: setIsDone(true)
// Render cursor span only when !isDone.
//
// Export default.
```

- [ ] **Step 4: Create StepTimeline component**

```typescript
// web/src/components/agent/StepTimeline.tsx
//
// Horizontal step progress bar showing plan steps with status.
//
// Props:
//   steps: Array<{ label: string; status: 'done' | 'active' | 'pending' }>
//
// Structure:
//   <div className="flex items-center gap-3 mb-6">
//     {steps.map((step, i) => (
//       <React.Fragment key={i}>
//         {i > 0 && (
//           // Connector line between steps
//           <div className={`flex-1 h-[1px] ${
//             step.status === 'done' || steps[i-1].status === 'done'
//               ? 'bg-success/30'   // green line for completed connections
//               : 'bg-border'       // dim line for pending
//           }`} />
//         )}
//         <div className="flex items-center gap-2">
//           {/* Step circle */}
//           <div className={`w-6 h-6 rounded-full flex items-center justify-center ${
//             step.status === 'done'
//               ? 'bg-success/20 border border-success/40'
//               : step.status === 'active'
//               ? 'bg-primary/20 border border-primary/40 animate-pulse'
//               : 'bg-surface border border-border'
//           }`}>
//             {step.status === 'done' ? (
//               // Checkmark SVG or unicode check
//               <span className="text-[14px] text-success">&#x2713;</span>
//             ) : step.status === 'active' ? (
//               // Active icon — pencil or spinning
//               <span className="text-[14px] text-primary">&#x270E;</span>
//             ) : (
//               // Pending — step number
//               <span className="text-[10px] text-muted font-bold">{i + 1}</span>
//             )}
//           </div>
//           {/* Step label */}
//           <span className={`text-xs ${
//             step.status === 'active' ? 'text-primary font-medium' : 'text-muted'
//           }`}>
//             {step.label}
//           </span>
//         </div>
//       </React.Fragment>
//     ))}
//   </div>
//
// Export default.
```

- [ ] **Step 5: Create ChatBubble component**

```typescript
// web/src/components/agent/ChatBubble.tsx
//
// Message bubble for user or agent messages in the streaming view.
//
// Props:
//   role: 'user' | 'agent'
//   children: React.ReactNode (message content)
//   timestamp?: string
//
// Structure:
//   <div className={`flex ${role === 'user' ? 'justify-end' : 'justify-start'} mb-3`}>
//     <div className={`max-w-[85%] rounded-2xl p-4 text-sm leading-relaxed ${
//       role === 'user'
//         ? 'bg-surface border border-border text-text'
//         : 'bg-primary/10 border border-primary/20 text-text'
//     }`}>
//       {children}
//       {timestamp && (
//         <p className="text-[10px] text-muted mt-2">{timestamp}</p>
//       )}
//     </div>
//   </div>
//
// Export default.
```

- [ ] **Step 6: Update AgentPanel with streaming UI**

```typescript
// web/src/components/agent/AgentPanel.tsx — MODIFY
//
// Import all new streaming components at top:
//   import TypingIndicator from './TypingIndicator'
//   import ActionBlock from './ActionBlock'
//   import StreamingText from './StreamingText'
//   import StepTimeline from './StepTimeline'
//   import ChatBubble from './ChatBubble'
//
// The AgentPanel from 2b-1 shows a welcome card and status bar.
// When a run is active (currentRun exists and status is 'running'), show the streaming UI instead.
//
// Add state:
//   const [isStreaming, setIsStreaming] = useState(false)
//   const [activeFile, setActiveFile] = useState<string | null>(null)
//   const [steps, setSteps] = useState<StepData[]>([])
//
// Subscribe to WebSocket events:
//   'stream' events: setIsStreaming(true) on first token
//   'step' events: update steps array with step status
//   'file' events: setActiveFile(event.data.path) when action is 'write'
//   'status' events: update run status
//
// Conditional rendering in the scrollable area:
//   if (currentRun && currentRun.status === 'running'):
//     - Show StepTimeline at top
//     - Show ChatBubble with user's instruction (role='user')
//     - If isStreaming: show ChatBubble (role='agent') containing <StreamingText runId={currentRun.id} />
//     - Else: show <TypingIndicator />
//     - If activeFile: show <ActionBlock action="Editing" filePath={activeFile} />
//   else:
//     - Show existing welcome card, recent contexts, etc.
//
// The streaming screen header matches the demo:
//   - "Agent Working" heading with sparkle icon
//   - "Step N of M — Editing file.ts" subtitle
//   - Model badge (e.g., "o3") on the right
//   - Stop button (red) on the right
//
// Add the header above the scrollable area, inside the panel but below the
// existing "AI Agent" header bar. Only show when run is active.
//
// Progress bar at bottom (above status indicator):
//   Show when run is active:
//   <div className="px-6 py-3 border-t border-border bg-surface/50">
//     <div className="flex items-center justify-between text-xs text-muted mb-2">
//       <span>Step {current}/{total}: {currentStepLabel}</span>
//       <span>{Math.round(current/total*100)}%</span>
//     </div>
//     <div className="h-1 bg-white/5 rounded-full overflow-hidden">
//       <div className="h-full bg-gradient-to-r from-primary to-purple-500 rounded-full transition-all duration-1000"
//            style={{ width: `${current/total*100}%` }} />
//     </div>
//   </div>
```

- [ ] **Step 7: Verify build and test in browser**

```bash
cd /Users/rohanthomas/Shipyard/web && npm run build
# Must succeed.
# Browser verification:
#   - When no run active: welcome card, recent contexts shown in AgentPanel
#   - When run is active: streaming UI with StepTimeline, TypingIndicator, then StreamingText
#   - ActionBlock appears when agent is editing a file
#   - Progress bar at bottom updates with step count
```

- [ ] **Step 8: Commit**

```bash
cd /Users/rohanthomas/Shipyard
git add web/src/components/agent/TypingIndicator.tsx web/src/components/agent/ActionBlock.tsx web/src/components/agent/StreamingText.tsx web/src/components/agent/StepTimeline.tsx web/src/components/agent/ChatBubble.tsx web/src/components/agent/AgentPanel.tsx
git commit -m "feat: AI streaming components — TypingIndicator, ActionBlock, StreamingText, StepTimeline, ChatBubble"
```

---

## Task 3: AutonomyToggle

**Files:**
- Create: `web/src/components/agent/AutonomyToggle.tsx`
- Modify: `web/src/components/agent/AgentPanel.tsx`

**Verification:** `npm run build` succeeds. Toggle switches between Supervised/Autonomous and calls PUT API.

- [ ] **Step 1: Create AutonomyToggle component**

```typescript
// web/src/components/agent/AutonomyToggle.tsx
//
// Toggle switch for supervised/autonomous mode.
// Calls PUT /projects/{id} with { autonomy_mode: ... } via REST (not WebSocket).
//
// Props:
//   projectId: string
//   initialMode: 'supervised' | 'autonomous'
//   onModeChange?: (mode: 'supervised' | 'autonomous') => void
//
// State:
//   mode: 'supervised' | 'autonomous' — initialized from initialMode
//   isUpdating: boolean — true while API call is in flight
//
// Toggle handler:
//   async function handleToggle() {
//     const newMode = mode === 'supervised' ? 'autonomous' : 'supervised'
//     setIsUpdating(true)
//     try {
//       await api.updateProject(projectId, { autonomy_mode: newMode })
//       setMode(newMode)
//       onModeChange?.(newMode)
//     } catch (e) {
//       // Revert — don't change mode on failure
//       console.error('Failed to update mode:', e)
//     } finally {
//       setIsUpdating(false)
//     }
//   }
//
// Structure (matches demo toggle):
//   <div className="flex items-center justify-between px-1">
//     <span className="text-xs font-medium text-muted">Mode</span>
//     <div className="flex items-center gap-2">
//       <span className="text-xs text-muted">
//         {mode === 'supervised' ? 'Supervised' : 'Autonomous'}
//       </span>
//       <button
//         onClick={handleToggle}
//         disabled={isUpdating}
//         className={`relative w-[36px] h-[20px] rounded-[10px] transition-colors cursor-pointer ${
//           mode === 'autonomous' ? 'bg-primary' : 'bg-white/10'
//         } ${isUpdating ? 'opacity-50 cursor-not-allowed' : ''}`}
//         aria-label={`Switch to ${mode === 'supervised' ? 'autonomous' : 'supervised'} mode`}
//       >
//         <div className={`absolute top-[2px] w-[16px] h-[16px] rounded-full bg-white transition-[left] ${
//           mode === 'autonomous' ? 'left-[18px]' : 'left-[2px]'
//         }`} />
//       </button>
//     </div>
//   </div>
//
// Export default.
```

- [ ] **Step 2: Wire AutonomyToggle into AgentPanel**

```typescript
// web/src/components/agent/AgentPanel.tsx — MODIFY
//
// Import:
//   import AutonomyToggle from './AutonomyToggle'
//
// In the scrollable area, after the welcome card (when no run is active),
// replace the static "Mode: Supervised" label with:
//
//   {currentProject && (
//     <AutonomyToggle
//       projectId={currentProject.id}
//       initialMode={(currentProject.autonomy_mode as 'supervised' | 'autonomous') || 'supervised'}
//       onModeChange={(mode) => {
//         // Update ProjectContext's currentProject locally
//         // This avoids a full refetch
//       }}
//     />
//   )}
//
// This replaces the read-only mode display from 2b-1 with the interactive toggle.
```

- [ ] **Step 3: Verify build and commit**

```bash
cd /Users/rohanthomas/Shipyard/web && npm run build
# Verify toggle renders, clicking it changes label and calls API.

cd /Users/rohanthomas/Shipyard
git add web/src/components/agent/AutonomyToggle.tsx web/src/components/agent/AgentPanel.tsx
git commit -m "feat: AutonomyToggle — supervised/autonomous switch with PUT /projects/{id}"
```

---

## Task 4: Settings Modal

**Files:**
- Create: `web/src/components/settings/tabs/GeneralTab.tsx`
- Create: `web/src/components/settings/tabs/AIModelsTab.tsx`
- Create: `web/src/components/settings/tabs/EnvironmentTab.tsx`
- Create: `web/src/components/settings/tabs/GitHubTab.tsx`
- Create: `web/src/components/settings/SettingsModal.tsx`
- Modify: `web/src/components/home/WorkspaceHome.tsx`
- Modify: `web/src/components/agent/AgentPanel.tsx`
- Modify: `web/src/App.tsx`

**Verification:** `npm run build` succeeds. Modal opens from Settings buttons, tabs switch, Save calls API.

- [ ] **Step 1: Create GeneralTab**

```typescript
// web/src/components/settings/tabs/GeneralTab.tsx
//
// Project name and working directory fields.
//
// Props:
//   values: { name: string; path: string }
//   onChange: (field: string, value: string) => void
//
// Structure:
//   <div className="space-y-5">
//     <div>
//       <label className="text-xs font-semibold text-muted uppercase tracking-wider mb-2 block">
//         Project Name
//       </label>
//       <input
//         type="text"
//         value={values.name}
//         onChange={(e) => onChange('name', e.target.value)}
//         className="w-full h-10 px-3 rounded-lg bg-black/30 border border-border text-sm text-text
//                    placeholder:text-muted/50 focus:border-primary/50 focus:ring-1 focus:ring-primary/50
//                    transition-all outline-none"
//       />
//     </div>
//     <div>
//       <label className="text-xs font-semibold text-muted uppercase tracking-wider mb-2 block">
//         Working Directory
//       </label>
//       <input
//         type="text"
//         value={values.path}
//         onChange={(e) => onChange('path', e.target.value)}
//         className="w-full h-10 px-3 rounded-lg bg-black/30 border border-border text-sm font-code text-text
//                    placeholder:text-muted/50 focus:border-primary/50 focus:ring-1 focus:ring-primary/50
//                    transition-all outline-none"
//       />
//     </div>
//   </div>
//
// Export default.
```

- [ ] **Step 2: Create AIModelsTab**

```typescript
// web/src/components/settings/tabs/AIModelsTab.tsx
//
// Model selector and default autonomy mode.
//
// Props:
//   values: { default_model: string; autonomy_mode: string }
//   onChange: (field: string, value: string) => void
//
// Structure:
//   <div className="space-y-5">
//     <div>
//       <label ...>Default Model</label>
//       <select
//         value={values.default_model}
//         onChange={(e) => onChange('default_model', e.target.value)}
//         className="w-full h-10 px-3 rounded-lg bg-black/30 border border-border text-sm text-text
//                    focus:border-primary/50 focus:ring-1 focus:ring-primary/50 transition-all
//                    appearance-none outline-none"
//       >
//         <option value="o3">o3 (Reasoning)</option>
//         <option value="gpt-4o">GPT-4o (General)</option>
//         <option value="gpt-4o-mini">GPT-4o-mini (Fast)</option>
//       </select>
//     </div>
//     <div>
//       <label ...>Autonomy Mode</label>
//       <select
//         value={values.autonomy_mode}
//         onChange={(e) => onChange('autonomy_mode', e.target.value)}
//         className={same as above}
//       >
//         <option value="supervised">Supervised (review each edit)</option>
//         <option value="autonomous">Autonomous (auto-apply, review at end)</option>
//       </select>
//     </div>
//   </div>
//
// Export default.
```

- [ ] **Step 3: Create EnvironmentTab**

```typescript
// web/src/components/settings/tabs/EnvironmentTab.tsx
//
// Test command, build command, lint command fields.
//
// Props:
//   values: { test_command: string; build_command: string; lint_command: string }
//   onChange: (field: string, value: string) => void
//
// Structure: 3 input fields, same styling pattern as GeneralTab.
//   - Test Command (placeholder: "npm test")
//   - Build Command (placeholder: "npm run build")
//   - Lint Command (placeholder: "npm run lint")
//
// All inputs use font-code class for monospace display.
//
// Export default.
```

- [ ] **Step 4: Create GitHubTab**

```typescript
// web/src/components/settings/tabs/GitHubTab.tsx
//
// GitHub repo, PAT, default reviewers, draft PR toggle.
//
// Props:
//   values: { github_repo: string; github_pat: string; default_reviewers: string; draft_pr: boolean }
//   onChange: (field: string, value: string | boolean) => void
//
// Structure:
//   <div className="space-y-5">
//     <div>
//       <label ...>Repository</label>
//       <input type="text" placeholder="owner/repo" ... />
//       <p className="text-[11px] text-muted mt-1.5">GitHub repository in owner/repo format</p>
//     </div>
//     <div>
//       <label ...>Personal Access Token</label>
//       <input type="password" placeholder="ghp_..." ... />
//       <p className="text-[11px] text-muted mt-1.5">Token with repo scope for PR creation</p>
//     </div>
//     <div>
//       <label ...>Default Reviewers</label>
//       <input type="text" placeholder="username1, username2" ... />
//       <p className="text-[11px] text-muted mt-1.5">Comma-separated GitHub usernames</p>
//     </div>
//     <div className="flex items-center justify-between">
//       <div>
//         <label className="text-xs font-semibold text-muted uppercase tracking-wider block">
//           Draft PRs
//         </label>
//         <p className="text-[11px] text-muted mt-0.5">Create PRs as drafts by default</p>
//       </div>
//       {/* Simple checkbox toggle */}
//       <button
//         onClick={() => onChange('draft_pr', !values.draft_pr)}
//         className={`relative w-[36px] h-[20px] rounded-[10px] transition-colors ${
//           values.draft_pr ? 'bg-primary' : 'bg-white/10'
//         }`}
//       >
//         <div className={`absolute top-[2px] w-[16px] h-[16px] rounded-full bg-white transition-[left] ${
//           values.draft_pr ? 'left-[18px]' : 'left-[2px]'
//         }`} />
//       </button>
//     </div>
//   </div>
//
// Export default.
```

- [ ] **Step 5: Create SettingsModal**

```typescript
// web/src/components/settings/SettingsModal.tsx
//
// Centered modal overlay with 4 tabs, rendered via React portal.
//
// Props:
//   isOpen: boolean
//   onClose: () => void
//   project: Project | null (from ProjectContext)
//
// State:
//   activeTab: 'general' | 'ai' | 'environment' | 'github' — default 'general'
//   formData: object — initialized from project props, local copy for editing
//   isSaving: boolean
//   error: string | null
//
// Initialize formData from project when modal opens (useEffect on isOpen + project).
//
// Save handler:
//   async function handleSave() {
//     if (!project) return
//     setIsSaving(true)
//     setError(null)
//     try {
//       await api.updateProject(project.id, formData)
//       onClose()
//     } catch (e) {
//       setError(e instanceof Error ? e.message : 'Failed to save')
//     } finally {
//       setIsSaving(false)
//     }
//   }
//
// onChange handler for all tabs:
//   function handleChange(field: string, value: string | boolean) {
//     setFormData(prev => ({ ...prev, [field]: value }))
//   }
//
// Render via createPortal to document.body:
//
//   if (!isOpen) return null
//
//   return createPortal(
//     <div
//       className="fixed inset-0 bg-black/60 backdrop-blur-[8px] z-50 flex items-center justify-center"
//       onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
//     >
//       <div className="glass-panel rounded-2xl w-[600px] max-h-[80vh] overflow-hidden"
//            style={{ background: 'rgba(20, 22, 30, 0.85)', backdropFilter: 'blur(32px)' }}>
//
//         {/* Header */}
//         <div className="flex items-center justify-between px-6 py-4 border-b border-border">
//           <h2 className="text-lg font-bold text-text">Project Settings</h2>
//           <button onClick={onClose} className="p-1 rounded-lg hover:bg-surface-hover text-muted transition-colors">
//             ✕
//           </button>
//         </div>
//
//         {/* Tabs */}
//         <div className="flex border-b border-border px-6">
//           {(['general', 'ai', 'environment', 'github'] as const).map(tab => (
//             <button
//               key={tab}
//               onClick={() => setActiveTab(tab)}
//               className={`px-4 py-3 text-sm font-medium transition-colors ${
//                 activeTab === tab
//                   ? 'text-text font-semibold border-b-2 border-primary'
//                   : 'text-muted hover:text-text'
//               }`}
//             >
//               {tab === 'general' ? 'General' : tab === 'ai' ? 'AI Models' : tab === 'environment' ? 'Environment' : 'GitHub'}
//             </button>
//           ))}
//         </div>
//
//         {/* Tab content */}
//         <div className="p-6 overflow-y-auto max-h-[60vh]">
//           {activeTab === 'general' && <GeneralTab values={formData} onChange={handleChange} />}
//           {activeTab === 'ai' && <AIModelsTab values={formData} onChange={handleChange} />}
//           {activeTab === 'environment' && <EnvironmentTab values={formData} onChange={handleChange} />}
//           {activeTab === 'github' && <GitHubTab values={formData} onChange={handleChange} />}
//
//           {/* Error banner */}
//           {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
//
//           {/* Save button */}
//           <div className="pt-5 border-t border-border mt-5 flex justify-end">
//             <button
//               onClick={handleSave}
//               disabled={isSaving}
//               className="px-6 py-2 rounded-lg bg-primary text-white text-sm font-semibold
//                          hover:bg-primary/90 shadow-[0_0_15px_rgba(99,102,241,0.3)] transition-all
//                          disabled:opacity-50 disabled:cursor-not-allowed"
//             >
//               {isSaving ? 'Saving...' : 'Save'}
//             </button>
//           </div>
//         </div>
//       </div>
//     </div>,
//     document.body
//   )
//
// Export default.
```

- [ ] **Step 6: Wire Settings buttons to open modal**

```typescript
// Modify: web/src/App.tsx
//
// Add state: const [settingsOpen, setSettingsOpen] = useState(false)
// Add: <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} project={currentProject} />
// Pass setSettingsOpen down to AppShell (or use a simple context/callback prop).
//
// Modify: web/src/components/home/WorkspaceHome.tsx
//   The "Workspace settings" quick action pill should call onOpenSettings() prop.
//
// Modify: web/src/components/agent/AgentPanel.tsx
//   The tune/settings button in the header bar should call onOpenSettings() prop.
//
// Wire the props through AppShell, passing onOpenSettings={() => setSettingsOpen(true)}
// to both WorkspaceHome and AgentPanel.
```

- [ ] **Step 7: Verify build and commit**

```bash
cd /Users/rohanthomas/Shipyard/web && npm run build
# Verify: Settings button opens modal, tabs switch, form fields editable, Save calls API.

cd /Users/rohanthomas/Shipyard
git add web/src/components/settings/ web/src/App.tsx web/src/components/home/WorkspaceHome.tsx web/src/components/agent/AgentPanel.tsx
git commit -m "feat: SettingsModal with General, AI Models, Environment, GitHub tabs"
```

---

## Task 5: Git Components

**Files:**
- Create: `web/src/components/git/CommitDialog.tsx`
- Create: `web/src/components/git/PRPanel.tsx`
- Modify: `web/src/components/editor/DiffViewer.tsx`

**Verification:** `npm run build` succeeds. Commit & Push button opens CommitDialog. PR creation works.

- [ ] **Step 1: Create CommitDialog component**

```typescript
// web/src/components/git/CommitDialog.tsx
//
// Commit message editor with Commit and Push buttons.
// Shown when user clicks "Commit & Push" in the DiffViewer footer.
//
// Props:
//   runId: string
//   isOpen: boolean
//   onClose: () => void
//   onCommitComplete?: (sha: string) => void
//
// State:
//   message: string — editable commit message (pre-filled with a default)
//   phase: 'idle' | 'committing' | 'pushing' | 'done' | 'error'
//   error: string | null
//   result: { sha?: string; branch?: string } | null
//
// On open (useEffect when isOpen becomes true):
//   Pre-fill message with "feat: apply agent edits" or fetch from API if available.
//
// Commit & Push handler:
//   async function handleCommitAndPush() {
//     setPhase('committing')
//     setError(null)
//     try {
//       const commitResult = await api.gitCommit(runId, message)
//       setPhase('pushing')
//       const pushResult = await api.gitPush(runId)
//       setResult({ sha: commitResult.sha, branch: pushResult.branch })
//       setPhase('done')
//       onCommitComplete?.(commitResult.sha)
//     } catch (e) {
//       setError(e instanceof Error ? e.message : 'Git operation failed')
//       setPhase('error')
//     }
//   }
//
// Structure: rendered as a small inline panel (not a full modal) below the DiffViewer footer,
// or as a slide-up card overlaying the bottom of DiffViewer.
//
//   <div className="glass-panel rounded-xl p-4 space-y-4">
//     <h3 className="text-sm font-semibold text-text">Commit Changes</h3>
//     <textarea
//       value={message}
//       onChange={(e) => setMessage(e.target.value)}
//       className="w-full h-24 px-3 py-2 rounded-lg bg-black/30 border border-border text-sm font-code
//                  text-text placeholder:text-muted/50 resize-none focus:border-primary/50
//                  focus:ring-1 focus:ring-primary/50 transition-all outline-none"
//       placeholder="Commit message..."
//     />
//     {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
//     {phase === 'done' && result && (
//       <div className="text-xs text-success">
//         Committed {result.sha?.slice(0, 7)} and pushed to {result.branch}
//       </div>
//     )}
//     <div className="flex justify-end gap-3">
//       <button onClick={onClose}
//         className="px-4 py-2 rounded-lg border border-border text-xs font-semibold text-muted
//                    hover:text-text hover:bg-surface-hover transition-colors">
//         Cancel
//       </button>
//       <button
//         onClick={handleCommitAndPush}
//         disabled={phase === 'committing' || phase === 'pushing' || !message.trim()}
//         className="px-4 py-2 rounded-lg bg-primary text-white text-xs font-semibold
//                    shadow-[0_0_15px_rgba(99,102,241,0.3)] hover:bg-primary/90 transition-all
//                    disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
//       >
//         {phase === 'committing' ? 'Committing...' : phase === 'pushing' ? 'Pushing...' : 'Commit & Push'}
//       </button>
//     </div>
//   </div>
//
// Export default.
```

- [ ] **Step 2: Create PRPanel component**

```typescript
// web/src/components/git/PRPanel.tsx
//
// PR creation form and status display. Shown after a successful push,
// or accessible from the DiffViewer footer.
//
// Props:
//   runId: string
//   isOpen: boolean
//   onClose: () => void
//
// State:
//   title: string — PR title
//   body: string — PR description
//   draft: boolean — create as draft
//   phase: 'idle' | 'creating' | 'done' | 'error'
//   error: string | null
//   result: { number?: number; html_url?: string } | null
//
// Create PR handler:
//   async function handleCreatePR() {
//     setPhase('creating')
//     setError(null)
//     try {
//       const pr = await api.gitCreatePR(runId, title, body, draft)
//       setResult(pr)
//       setPhase('done')
//     } catch (e) {
//       setError(e instanceof Error ? e.message : 'Failed to create PR')
//       setPhase('error')
//     }
//   }
//
// Structure:
//   <div className="glass-panel rounded-xl p-4 space-y-4">
//     <h3 className="text-sm font-semibold text-text">Create Pull Request</h3>
//     <input type="text" value={title} onChange={...}
//       placeholder="PR title"
//       className={standard input classes} />
//     <textarea value={body} onChange={...}
//       placeholder="Description (optional)"
//       className={standard textarea classes, h-20} />
//     <div className="flex items-center gap-2">
//       {/* Draft toggle — reuse toggle pattern from AutonomyToggle */}
//       <button onClick={() => setDraft(!draft)} className={toggle classes}>
//         <div className={thumb classes} />
//       </button>
//       <span className="text-xs text-muted">Draft PR</span>
//     </div>
//     {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
//     {phase === 'done' && result && (
//       <div className="text-xs text-success flex items-center gap-2">
//         PR #{result.number} created
//         <a href={result.html_url} target="_blank" rel="noopener noreferrer"
//            className="text-primary underline">View on GitHub</a>
//       </div>
//     )}
//     <div className="flex justify-end gap-3">
//       <button onClick={onClose} className={cancel button classes}>Cancel</button>
//       <button onClick={handleCreatePR} disabled={phase === 'creating' || !title.trim()}
//         className={primary button classes}>
//         {phase === 'creating' ? 'Creating...' : 'Create PR'}
//       </button>
//     </div>
//   </div>
//
// Export default.
```

- [ ] **Step 3: Wire CommitDialog and PRPanel into DiffViewer**

```typescript
// web/src/components/editor/DiffViewer.tsx — MODIFY
//
// Import:
//   import CommitDialog from '../git/CommitDialog'
//   import PRPanel from '../git/PRPanel'
//
// Add state:
//   const [showCommit, setShowCommit] = useState(false)
//   const [showPR, setShowPR] = useState(false)
//
// The "Commit & Push" button in the bottom bar onClick:
//   () => setShowCommit(true)
//
// Below the bottom bar, conditionally render:
//   {showCommit && (
//     <CommitDialog
//       runId={runId}
//       isOpen={showCommit}
//       onClose={() => setShowCommit(false)}
//       onCommitComplete={() => {
//         setShowCommit(false)
//         setShowPR(true)  // Offer PR creation after push
//       }}
//     />
//   )}
//   {showPR && (
//     <PRPanel runId={runId} isOpen={showPR} onClose={() => setShowPR(false)} />
//   )}
```

- [ ] **Step 4: Verify build and commit**

```bash
cd /Users/rohanthomas/Shipyard/web && npm run build

cd /Users/rohanthomas/Shipyard
git add web/src/components/git/CommitDialog.tsx web/src/components/git/PRPanel.tsx web/src/components/editor/DiffViewer.tsx
git commit -m "feat: CommitDialog and PRPanel — git commit, push, and PR creation UI"
```

---

## Task 6: Keyboard Shortcuts

**Files:**
- Create: `web/src/hooks/useHotkeys.ts`
- Modify: `web/src/components/home/WorkspaceHome.tsx`
- Modify: `web/src/components/settings/SettingsModal.tsx`
- Modify: `web/src/components/editor/DiffViewer.tsx`
- Modify: `web/src/App.tsx`

**Verification:** `npm run build` succeeds. All shortcuts work in browser.

- [ ] **Step 1: Create useHotkeys hook**

```typescript
// web/src/hooks/useHotkeys.ts
//
// Thin wrapper around keydown events. No external dependencies.
//
// Signature:
//   function useHotkeys(
//     shortcuts: Array<{
//       key: string           // e.g. 'Enter', 'Escape', 'p', 'a', 'r'
//       ctrlOrMeta?: boolean  // true = requires Ctrl (Windows/Linux) or Cmd (Mac)
//       shift?: boolean       // true = requires Shift
//       handler: (e: KeyboardEvent) => void
//       enabled?: boolean     // default true; allows conditional activation
//     }>
//   ): void
//
// Implementation:
//   useEffect(() => {
//     function handleKeyDown(e: KeyboardEvent) {
//       for (const shortcut of shortcuts) {
//         if (shortcut.enabled === false) continue
//         const keyMatch = e.key === shortcut.key
//         const metaMatch = shortcut.ctrlOrMeta ? (e.metaKey || e.ctrlKey) : true
//         const shiftMatch = shortcut.shift ? e.shiftKey : true
//         // Avoid firing when ctrlOrMeta is not required but user is pressing it
//         // Only check positive requirements, not negative
//         if (keyMatch && metaMatch && shiftMatch) {
//           e.preventDefault()
//           shortcut.handler(e)
//           return  // only handle first match
//         }
//       }
//     }
//     window.addEventListener('keydown', handleKeyDown)
//     return () => window.removeEventListener('keydown', handleKeyDown)
//   }, [shortcuts])
//
// Export default.
//
// IMPORTANT: The shortcuts array should be memoized by the caller (useMemo)
// to avoid re-registering listeners on every render.
```

- [ ] **Step 2: Wire keyboard shortcuts into components**

```typescript
// web/src/components/home/WorkspaceHome.tsx — MODIFY
// Add: useHotkeys for Cmd+Enter to submit instruction (when textarea is focused).
// The handler calls the existing submit function.
//
// web/src/components/settings/SettingsModal.tsx — MODIFY
// Add: useHotkeys for Escape to close modal (enabled only when isOpen is true).
//
// web/src/components/editor/DiffViewer.tsx — MODIFY
// Add: useHotkeys for:
//   Cmd+Shift+A → approve current edit (call onEditAction with first pending edit)
//   Cmd+Shift+R → reject current edit
//
// web/src/App.tsx — MODIFY
// Add: useHotkeys for:
//   Cmd+Shift+P → focus the instruction textarea
//     Handler: document.querySelector('#prompt-input')?.focus()
//     (Add id="prompt-input" to the textarea in WorkspaceHome if not already present)
```

- [ ] **Step 3: Verify build and commit**

```bash
cd /Users/rohanthomas/Shipyard/web && npm run build

cd /Users/rohanthomas/Shipyard
git add web/src/hooks/useHotkeys.ts web/src/components/home/WorkspaceHome.tsx web/src/components/settings/SettingsModal.tsx web/src/components/editor/DiffViewer.tsx web/src/App.tsx
git commit -m "feat: keyboard shortcuts — Cmd+Enter submit, Escape close, Cmd+Shift+P focus, Cmd+Shift+A/R approve/reject"
```

---

## Task 7: Error Handling

**Files:**
- Create: `web/src/components/layout/ErrorBoundary.tsx`
- Create: `web/src/components/shared/ErrorBanner.tsx`
- Modify: `web/src/App.tsx`

**Verification:** `npm run build` succeeds. ErrorBoundary catches crashes. ErrorBanner shows inline errors.

- [ ] **Step 1: Create ErrorBanner component**

```typescript
// web/src/components/shared/ErrorBanner.tsx
//
// Inline error display that auto-dismisses after 8 seconds.
//
// Props:
//   message: string
//   onDismiss: () => void
//
// Implementation:
//   useEffect(() => {
//     const timer = setTimeout(onDismiss, 8000)
//     return () => clearTimeout(timer)
//   }, [onDismiss])
//
// Structure:
//   <div
//     className="flex items-center gap-3 px-4 py-3 rounded-lg border-l-[3px] border-error
//                bg-error/15 text-sm text-text cursor-pointer transition-opacity"
//     onClick={onDismiss}
//     role="alert"
//   >
//     <span className="text-error text-[16px]">&#x26A0;</span>
//     <span className="flex-1">{message}</span>
//     <button className="text-muted hover:text-text transition-colors text-xs">
//       Dismiss
//     </button>
//   </div>
//
// Export default.
```

- [ ] **Step 2: Create ErrorBoundary component**

```typescript
// web/src/components/layout/ErrorBoundary.tsx
//
// React class component error boundary. Catches render errors in children.
//
// State:
//   hasError: boolean
//   error: Error | null
//
// static getDerivedStateFromError(error):
//   return { hasError: true, error }
//
// componentDidCatch(error, info):
//   console.error('ErrorBoundary caught:', error, info)
//
// Fallback UI:
//   <div className="flex flex-col items-center justify-center h-full p-8 text-center">
//     <div className="glass-panel rounded-2xl p-8 max-w-md">
//       <div className="w-12 h-12 rounded-full bg-error/20 border border-error/30
//                       flex items-center justify-center mx-auto mb-4">
//         <span className="text-error text-2xl">!</span>
//       </div>
//       <h2 className="text-lg font-bold text-text mb-2">Something went wrong</h2>
//       <p className="text-sm text-muted mb-4">
//         {this.state.error?.message || 'An unexpected error occurred'}
//       </p>
//       <button
//         onClick={() => window.location.reload()}
//         className="px-6 py-2 rounded-lg bg-primary text-white text-sm font-semibold
//                    hover:bg-primary/90 transition-all"
//       >
//         Reload
//       </button>
//     </div>
//   </div>
//
// Normal render: return this.props.children
//
// Note: must be a class component — React hooks do not support error boundaries.
//
// Export default.
```

- [ ] **Step 3: Wire ErrorBoundary into App.tsx**

```typescript
// web/src/App.tsx — MODIFY
//
// Import ErrorBoundary.
//
// Wrap the AppShell (or its children) in ErrorBoundary:
//
//   <ErrorBoundary>
//     <AppShell ... />
//   </ErrorBoundary>
//
// This prevents a crash in any panel from taking down the entire app.
// The ErrorBoundary should be inside the context providers (WebSocketProvider,
// ProjectProvider) so that context is still available if only a child crashes.
```

- [ ] **Step 4: Verify build and commit**

```bash
cd /Users/rohanthomas/Shipyard/web && npm run build

cd /Users/rohanthomas/Shipyard
git add web/src/components/shared/ErrorBanner.tsx web/src/components/layout/ErrorBoundary.tsx web/src/App.tsx
git commit -m "feat: ErrorBoundary and ErrorBanner — crash recovery and inline error display"
```

---

## Task 8: Layout Responsiveness

**Files:**
- Modify: `web/src/components/layout/AppShell.tsx`
- Modify: `web/src/styles/glass.css`

**Verification:** `npm run build` succeeds. Sidebars collapse at medium/small viewpoints.

- [ ] **Step 1: Add responsive CSS to glass.css**

```css
/* web/src/styles/glass.css — APPEND
 *
 * Add these responsive utilities and animations:
 */

/* Sidebar collapse transition */
.sidebar-collapsible {
  transition: width 0.3s ease, min-width 0.3s ease, padding 0.3s ease, opacity 0.3s ease;
  overflow: hidden;
}

.sidebar-collapsed {
  width: 48px !important;
  min-width: 48px !important;
}

.sidebar-hidden {
  width: 0 !important;
  min-width: 0 !important;
  padding: 0 !important;
  border: none !important;
  opacity: 0;
  pointer-events: none;
}

/* Collapse toggle button */
.collapse-toggle {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  z-index: 20;
  width: 20px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0 8px 8px 0;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-left: none;
  cursor: pointer;
  transition: opacity 0.2s;
  opacity: 0;
}

.collapse-toggle:hover,
.group:hover .collapse-toggle {
  opacity: 1;
}

/* Responsive grid overrides */
@media (max-width: 1200px) {
  .app-grid {
    grid-template-columns: 48px 1fr 0 !important;
  }
}

@media (max-width: 900px) {
  .app-grid {
    grid-template-columns: 1fr !important;
  }
}
```

- [ ] **Step 2: Update AppShell with collapsible sidebars**

```typescript
// web/src/components/layout/AppShell.tsx — MODIFY
//
// Add state for sidebar collapse, persisted to localStorage:
//
//   const [leftCollapsed, setLeftCollapsed] = useState(() =>
//     localStorage.getItem('shipyard:leftCollapsed') === 'true'
//   )
//   const [rightCollapsed, setRightCollapsed] = useState(() =>
//     localStorage.getItem('shipyard:rightCollapsed') === 'true'
//   )
//
//   useEffect(() => {
//     localStorage.setItem('shipyard:leftCollapsed', String(leftCollapsed))
//   }, [leftCollapsed])
//   useEffect(() => {
//     localStorage.setItem('shipyard:rightCollapsed', String(rightCollapsed))
//   }, [rightCollapsed])
//
// Update the grid container:
//   <div
//     className="grid h-full w-full gap-4 app-grid"
//     style={{
//       gridTemplateColumns: `${leftCollapsed ? '48px' : '250px'} 1fr ${rightCollapsed ? '0px' : '300px'}`,
//       transition: 'grid-template-columns 0.3s ease',
//     }}
//   >
//
// Left sidebar wrapper:
//   <aside className={`glass-panel rounded-2xl flex flex-col h-full overflow-hidden sidebar-collapsible
//     ${leftCollapsed ? 'sidebar-collapsed' : ''} relative group`}>
//     {/* Collapse toggle on right edge */}
//     <button
//       onClick={() => setLeftCollapsed(!leftCollapsed)}
//       className="collapse-toggle -right-[20px]"
//       aria-label={leftCollapsed ? 'Expand file tree' : 'Collapse file tree'}
//     >
//       {leftCollapsed ? '>' : '<'}
//     </button>
//     {/* Only show full content when not collapsed */}
//     {!leftCollapsed && <FileTree ... />}
//     {leftCollapsed && (
//       // Icon-only rail: just the Explorer icon
//       <div className="flex flex-col items-center py-3 gap-2">
//         <span className="text-muted text-[16px]">&#x1F4C1;</span>
//       </div>
//     )}
//   </aside>
//
// Right sidebar wrapper:
//   <aside className={`glass-panel rounded-2xl flex flex-col h-full overflow-hidden sidebar-collapsible
//     ${rightCollapsed ? 'sidebar-hidden' : ''}`}>
//     <AgentPanel ... />
//   </aside>
//
// Add a toggle button in the top bar of center panel to show/hide right sidebar:
//   <button onClick={() => setRightCollapsed(!rightCollapsed)}
//     className="p-1.5 rounded hover:bg-surface-hover text-muted transition-colors">
//     {rightCollapsed ? 'Show Agent' : 'Hide Agent'}
//   </button>
```

- [ ] **Step 3: Verify build and commit**

```bash
cd /Users/rohanthomas/Shipyard/web && npm run build
# Verify: resize browser window — sidebars collapse at breakpoints.
# Click collapse toggles — sidebars animate closed/open.
# Refresh page — collapse state persisted.

cd /Users/rohanthomas/Shipyard
git add web/src/components/layout/AppShell.tsx web/src/styles/glass.css
git commit -m "feat: responsive layout — collapsible sidebars with localStorage persistence"
```

---

## Task 9: Build Verification

**Files:** None created — verification only.

- [ ] **Step 1: Run production build**

```bash
cd /Users/rohanthomas/Shipyard/web && npm run build
# Must complete with 0 errors, 0 TypeScript errors.
# Output goes to web/dist/.
```

- [ ] **Step 2: Manual browser verification checklist**

```
Start dev server: cd web && npm run dev

Verify each screen:

[ ] Home screen:
    - Prompt textarea visible, glassmorphic styling
    - Quick action pills (Create project, Open terminal, Settings)
    - Settings pill opens SettingsModal
    - Cmd+Enter submits instruction
    - Cmd+Shift+P focuses textarea

[ ] DiffViewer:
    - Shows when run has pending edits
    - Dual line numbers (old/new)
    - Green addition rows, red deletion rows, neutral context rows
    - Accept/Reject buttons in sticky header
    - Cmd+Shift+A approves, Cmd+Shift+R rejects
    - Bottom bar: Commit & Push, changeset summary, Approve All
    - Commit & Push opens CommitDialog

[ ] AI Streaming:
    - StepTimeline shows at top with done/active/pending steps
    - TypingIndicator (3 bouncing dots) while waiting
    - StreamingText shows tokens as they arrive
    - ActionBlock shows "Editing file..." with spinner
    - ChatBubble for user and agent messages
    - Progress bar at bottom with percentage

[ ] AgentPanel:
    - Welcome card when idle
    - AutonomyToggle switches between Supervised/Autonomous
    - Settings button opens modal
    - Status indicator at bottom (Idle/Working)

[ ] SettingsModal:
    - Opens from Settings buttons (Home + AgentPanel)
    - 4 tabs: General, AI Models, Environment, GitHub
    - Form fields editable
    - Save calls PUT /projects/{id}
    - Escape closes modal
    - Click outside closes modal

[ ] CommitDialog + PRPanel:
    - Commit message editable
    - Commit & Push shows progress states
    - After push, PR creation form shown
    - Draft toggle works
    - PR link shown after creation

[ ] Error Handling:
    - ErrorBanner shows on API failure, auto-dismisses after 8s
    - ErrorBoundary catches crashes, shows reload button

[ ] Responsiveness:
    - Sidebars collapse at <1200px width
    - Collapse toggles work manually
    - Collapse state persists across reload
```

- [ ] **Step 3: Final commit if any fixes needed**

```bash
# Only if Step 2 revealed issues that needed fixing:
cd /Users/rohanthomas/Shipyard
git add -A
git commit -m "fix: browser verification fixes for rich UI components"
```

---

## Summary

| Task | Components | Files Created | Files Modified |
|------|-----------|---------------|----------------|
| 1. DiffViewer | DiffLine, DiffHeader, DiffViewer | 3 | 1 (AppShell) |
| 2. AI Streaming | TypingIndicator, ActionBlock, StreamingText, StepTimeline, ChatBubble | 5 | 1 (AgentPanel) |
| 3. AutonomyToggle | AutonomyToggle | 1 | 1 (AgentPanel) |
| 4. Settings Modal | SettingsModal, GeneralTab, AIModelsTab, EnvironmentTab, GitHubTab | 5 | 3 (App, WorkspaceHome, AgentPanel) |
| 5. Git Components | CommitDialog, PRPanel | 2 | 1 (DiffViewer) |
| 6. Keyboard Shortcuts | useHotkeys | 1 | 4 (WorkspaceHome, SettingsModal, DiffViewer, App) |
| 7. Error Handling | ErrorBoundary, ErrorBanner | 2 | 1 (App) |
| 8. Layout Responsiveness | — | 0 | 2 (AppShell, glass.css) |
| 9. Build Verification | — | 0 | 0 |
| **Total** | **19 components + 1 hook** | **19** | **~8 unique files** |
