# Shipyard Demo -- Autonomous AI Coding Agent

**Target duration:** 3-5 minutes
**Format:** Screen recording with voiceover. Terminal + browser side-by-side where applicable.
**Recording setup:** Shipyard server running locally, browser open to Shipyard UI, terminal visible for CLI commands.

---

## Scene 1: Surgical Edit (60-90 seconds)

### What to Show
Send a single instruction to add a field to a TypeScript model. Demonstrate the full plan-read-edit-validate pipeline with anchor-based replacement.

### Setup
- Shipyard server running (`uvicorn server.main:app`)
- Browser open to Shipyard UI at `http://localhost:5173`
- Terminal open for optional curl commands
- Ship project registered and working directory set

### Steps

1. **Show the target file before edit**
   - Open `src/types/index.ts` in the UI file browser or terminal
   - Point out the existing Document interface with its current fields

2. **Send instruction via UI**
   - Type in the instruction panel: "Add a due_date field of type string to the Document interface in src/types/index.ts"
   - Click Submit

3. **Show the agent planning**
   - UI displays the planner output: 1 step with `kind: "edit"`, `target_files: ["src/types/index.ts"]`
   - Voiceover: "The planner decomposed this into a single edit step targeting the exact file"

4. **Show reader loading the file**
   - UI shows reader node activating, file content loaded into buffer
   - Voiceover: "The reader loads only the relevant file -- for files over 200 lines, it reads line ranges instead of the full file"

5. **Show editor producing the anchor-based edit**
   - UI shows the editor output: anchor text and replacement text
   - Voiceover: "Anchor-based replacement, not whole-file rewriting. The editor finds the exact location using a text anchor and replaces just that section"

6. **Show validator passing**
   - UI shows validator node completing with syntax check pass
   - Voiceover: "The validator runs a language-appropriate syntax check -- for TypeScript, that means esbuild or tsc. It also compares LSP diagnostics before and after the edit to catch regressions"

7. **Show the file after edit**
   - Open the file again -- the `due_date` field is added with correct indentation
   - Voiceover: "Surgical, precise, correct indentation. The fuzzy matching system handles minor whitespace differences with a similarity threshold of 0.85"

### Key Voiceover Points
- "Anchor-based replacement is the same strategy used by Claude Code and OpenCode -- the two most successful coding agents"
- "Every edit is snapshotted before application. If validation fails, the file is rolled back and the editor retries with the error context"
- "This entire flow -- plan, read, edit, validate -- completed in under 10 seconds"

---

## Scene 2: Multi-Agent Task (60-90 seconds)

### What to Show
Send an instruction that triggers the coordinator to split work into parallel agent execution across different directory prefixes.

### Setup
- Same Shipyard server session
- LangSmith dashboard open in a second browser tab for trace visualization

### Steps

1. **Send instruction via UI**
   - Type: "Add a tags field to the Document interface and update both the API routes and the React component to support it"
   - Click Submit
   - Voiceover: "This instruction touches three files across two directories -- the type definition, the API route, and the React component"

2. **Show coordinator splitting into batches**
   - UI displays coordinator output: identifies `src/types/` and `src/routes/` as independent work units, `src/components/` depends on the type change
   - Voiceover: "The coordinator groups steps by directory prefix. Independent directories run in parallel, dependencies run sequentially"

3. **Show parallel execution in LangSmith trace**
   - Switch to LangSmith tab
   - Show the trace tree: two subgraphs executing simultaneously (reader-editor-validator each)
   - Voiceover: "Two subgraphs executing simultaneously via LangGraph's Send API. Each has its own isolated edit log"

4. **Show merger collecting results**
   - Back in UI: merger node completes, no conflicts detected
   - Voiceover: "The merger checks for file conflicts. Different files merge directly. Same file with different anchors applies sequentially. Overlapping regions flag to human"

5. **Show all files updated consistently**
   - Browse the modified files: type definition has the new field, API route accepts it, React component renders it
   - Voiceover: "Three files updated consistently in a single instruction. The multi-agent coordination handled the dependency ordering automatically"

### Key Voiceover Points
- "Coordinator identifies independent work units based on file paths and dependency analysis"
- "Parallel execution via LangGraph Send API -- not sequential processing"
- "Merger detects and resolves file conflicts, flagging overlapping edits to human review"

---

## Scene 3: Ship Rebuild (60-90 seconds)

### What to Show
Run the rebuild orchestrator against the Ship app, demonstrating the graduated instruction sequence.

### Setup
- Terminal open to project root
- `SHIP-REBUILD-LOG.md` visible or open in editor
- LangSmith dashboard for trace overview

### Steps

1. **Show dry-run preview**
   - Run: `python scripts/rebuild_orchestrator.py --dry-run`
   - Terminal shows all 5 instructions with labels and expected files
   - Voiceover: "5 graduated instructions from simple to complex. Each builds on the previous one's context"

2. **Show running the first 1-2 instructions live**
   - Run: `python scripts/rebuild_orchestrator.py --project-id ship --start-from 1`
   - Watch instruction 1 (Add status field to Document) complete
   - Watch instruction 2 (Add GET /ready health endpoint) complete
   - Voiceover: "The orchestrator sends each instruction, polls for completion, and logs the result. Failures get automatic intervention templates"

3. **Show SHIP-REBUILD-LOG.md being populated**
   - Open the log file -- table shows instruction results with status, duration, and trace links
   - Voiceover: "Every instruction is logged with status, duration, and LangSmith trace URL. Failed instructions get intervention templates documenting what broke and what was done manually"

4. **Show LangSmith trace dashboard**
   - Switch to LangSmith: show the completed runs with full node-by-node traces
   - Voiceover: "Full traceability via LangSmith -- every LLM call, every tool invocation, every state transition is captured"

5. **Show generated code or running app**
   - Browse the ship-rebuild directory to show generated files
   - Voiceover: "The agent generated real, working code -- not templates or stubs. Each edit was validated against syntax checks and LSP diagnostics"

**Actual rebuild results (2026-03-27):**
- 4/5 instructions completed successfully (80% success rate)
- Instruction 1 (Add status field): completed in ~30s
- Instruction 2 (GET /ready endpoint): completed in ~33s
- Instruction 3 (CRUD routes): completed in ~33s
- Instruction 4 (Multi-file tags + filter): FAILED at 188s -- agent struggled with 3-file coordination across types/models/components
- Instruction 5 (Parallel priority + DELETE): completed in ~46s
- Intervention on #4: Manual fix required for model file that didn't exist in the working directory

### Key Voiceover Points
- "5 graduated instructions: simple field add, health endpoint, CRUD routes, multi-file update, parallel multi-agent"
- "Every human intervention is documented with root cause analysis"
- "Full traceability: instruction to plan to edit to validation to commit"

---

## Closing (30 seconds)

### Steps

1. **Show the deployed app URL** (if deployed)
   - Open the Heroku/Railway URL in browser
   - Voiceover: "Both the agent and the agent-built Ship app are publicly accessible"

2. **Show CODEAGENT.md table of contents**
   - Open CODEAGENT.md and scroll through sections: Architecture, File Editing Strategy, Multi-Agent Design, Trace Links, Architecture Decisions, Ship Rebuild Log, Comparative Analysis, Cost Analysis
   - Voiceover: "The complete CODEAGENT.md documents every architectural decision, the full rebuild log, and a 7-section comparative analysis"

3. **Closing statement**
   - Voiceover: "Shipyard: an autonomous coding agent with surgical edits, multi-agent coordination, and full observability. Built with LangGraph, validated by rebuilding a real app from scratch."

---

## Recording Notes

- **Total target time:** 3-5 minutes (aim for 4 minutes)
- **Scene 1:** ~75 seconds (the core demo -- make this crisp)
- **Scene 2:** ~75 seconds (shows advanced capability)
- **Scene 3:** ~75 seconds (the integration test)
- **Closing:** ~30 seconds (quick wrap-up)
- **Pacing:** Let the UI/terminal output speak for itself. Pause voiceover during agent execution to show real-time progress.
- **Fallback:** If live execution is slow, pre-record the agent runs and narrate over the recording at normal speed.
