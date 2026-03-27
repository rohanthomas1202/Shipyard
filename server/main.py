import os
import uuid
import asyncio
import logging
import pathlib
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Literal as TypingLiteral
from agent.graph import build_graph
from agent.router import ModelRouter
from agent.events import EventBus
from agent.approval import ApprovalManager, InvalidTransitionError
from store.sqlite import SQLiteSessionStore
from agent.git import GitManager
from agent.github import GitHubClient
from store.models import Project, Run, GitOperation
from server.websocket import ConnectionManager


runs: dict[str, dict] = {}

_IGNORED_NAMES = {
    ".git", "node_modules", "__pycache__", ".venv", ".mypy_cache",
    ".tox", ".pytest_cache", ".ruff_cache", "__pypackages__",
    ".next", ".nuxt", "dist", "build", ".DS_Store",
}

_EXT_TO_LANG: dict[str, str] = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "scss", ".less": "less",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".md": "markdown", ".mdx": "markdown",
    ".sql": "sql", ".sh": "shell", ".bash": "shell",
    ".rs": "rust", ".go": "go", ".java": "java",
    ".rb": "ruby", ".php": "php", ".swift": "swift",
    ".kt": "kotlin", ".c": "c", ".cpp": "cpp", ".h": "c",
    ".xml": "xml", ".svg": "xml", ".toml": "toml",
    ".ini": "ini", ".cfg": "ini", ".env": "shell",
    ".txt": "plaintext", ".log": "plaintext",
    ".dockerfile": "dockerfile",
}

_BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".bmp",
    ".pdf", ".zip", ".tar", ".gz", ".woff", ".woff2", ".ttf",
    ".eot", ".mp3", ".mp4", ".wav", ".avi", ".mov", ".pyc", ".so", ".dll",
}


def _rollback_edits(run_id: str) -> None:
    """Roll back in-progress edits for a cancelled run using snapshots."""
    run_entry = runs.get(run_id, {})
    result = run_entry.get("result")
    if not isinstance(result, dict):
        return
    edit_history = result.get("edit_history", [])
    for entry in edit_history:
        snapshot = entry.get("snapshot")
        file_path = entry.get("file_path")
        if snapshot and file_path:
            try:
                with open(file_path, "w") as f:
                    f.write(snapshot)
                logger.info("Rolled back %s during cancellation", file_path)
            except OSError:
                logger.exception("Failed to rollback %s", file_path)


DB_PATH = os.environ.get("SHIPYARD_DB_PATH", "shipyard.db")

HEARTBEAT_INTERVAL = 15
logger = logging.getLogger(__name__)


async def _resume_from_checkpoint(run_id: str) -> None:
    """Resume a single interrupted run from its last LangGraph checkpoint."""
    store = app.state.store
    router = app.state.router
    graph = app.state.graph

    run = await store.get_run(run_id)
    if run is None:
        logger.warning("Cannot resume run %s: not found in store", run_id)
        return

    runs[run_id] = {"status": "running", "result": None}
    try:
        config = {
            "configurable": {
                "store": store,
                "router": router,
                "approval_manager": app.state.approval_manager,
                "run_id": run_id,
                "thread_id": run_id,
            },
            "tags": [f"run_id:{run_id}"],
        }
        task = asyncio.current_task()
        if task:
            runs[run_id]["task"] = task
        result = await graph.ainvoke(None, config=config)
        if result.get("error_state") is None:
            runs[run_id] = {"status": "completed", "result": result}
            run.status = "completed"
        else:
            runs[run_id] = {"status": "failed", "result": result}
            run.status = "failed"

        # Capture LangSmith trace link
        from agent.tracing import share_trace_link
        trace_url = await share_trace_link(run_id)
        if trace_url:
            runs[run_id]["trace_url"] = trace_url
            run.trace_url = trace_url

        await store.update_run(run)
    except asyncio.CancelledError:
        _rollback_edits(run_id)
        runs[run_id] = {"status": "cancelled", "result": "Cancelled by user"}
        run.status = "cancelled"
        await store.update_run(run)
        logger.info("Run %s cancelled by user (checkpoint resume)", run_id)
    except Exception as e:
        logger.exception("Failed to resume run %s", run_id)
        runs[run_id] = {"status": "error", "result": str(e)}
        run.status = "error"
        await store.update_run(run)


async def _resume_interrupted_runs() -> None:
    """Find runs with status 'running' in DB (interrupted by crash) and resume them."""
    store = app.state.store
    interrupted = await store.list_runs_by_status("running")
    if not interrupted:
        return
    logger.info("Found %d interrupted runs to resume", len(interrupted))
    for run in interrupted:
        logger.info("Resuming interrupted run %s", run.id)
        asyncio.create_task(_resume_from_checkpoint(run.id))


@asynccontextmanager
async def lifespan(app: FastAPI):
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    store = SQLiteSessionStore(DB_PATH)
    await store.initialize()

    event_bus = EventBus(store)
    conn_manager = ConnectionManager(event_bus)

    async def send_callback(event):
        await conn_manager.send_to_subscribed(event)
    event_bus.set_send_callback(send_callback)
    event_bus.start_batcher()

    approval_manager = ApprovalManager(store=store, event_bus=event_bus)
    conn_manager.set_approval_manager(approval_manager)

    async with AsyncSqliteSaver.from_conn_string("shipyard_checkpoints.db") as checkpointer:
        await checkpointer.setup()

        app.state.store = store
        app.state.router = ModelRouter()
        app.state.graph = build_graph(checkpointer=checkpointer)
        app.state.checkpointer = checkpointer
        app.state.event_bus = event_bus
        app.state.conn_manager = conn_manager
        app.state.approval_manager = approval_manager

        heartbeat_task = asyncio.create_task(_heartbeat_loop(conn_manager))
        asyncio.create_task(_resume_interrupted_runs())
        yield
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
    await event_bus.shutdown()
    await store.close()


async def _heartbeat_loop(conn_manager: ConnectionManager) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        try:
            await conn_manager.broadcast_heartbeat()
        except Exception:
            logger.exception("Error in heartbeat loop")


app = FastAPI(title="Shipyard Agent", lifespan=lifespan)


class InstructionRequest(BaseModel):
    instruction: str
    working_directory: str
    context: dict = {}
    project_id: str | None = None


class InstructionResponse(BaseModel):
    run_id: str
    status: str


class CreateProjectRequest(BaseModel):
    name: str
    path: str


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


class EditActionRequest(BaseModel):
    action: TypingLiteral["approve", "reject"]
    op_id: str


def project_response(project: Project) -> dict:
    return project.model_dump(exclude={"github_pat"})


async def _resume_run(run_id: str) -> None:
    if run_id not in runs:
        return
    if runs[run_id].get("status") != "waiting_for_human":
        return
    store = app.state.store
    router = app.state.router
    runs[run_id]["status"] = "running"
    try:
        graph = app.state.graph
        state = runs[run_id].get("result", {})
        if isinstance(state, str):
            state = {}
        state["error_state"] = None
        state["waiting_for_human"] = False
        state["invalidated_files"] = []
        from agent.tools.lsp_manager import LspManager
        working_dir = state.get("working_directory", "")
        async with LspManager(working_dir, {}) as lsp_mgr:
            config = {
                "configurable": {
                    "store": store,
                    "router": router,
                    "approval_manager": app.state.approval_manager,
                    "run_id": run_id,
                    "lsp_manager": lsp_mgr,
                    "thread_id": run_id,
                },
                "tags": [f"run_id:{run_id}"],
            }
            task = asyncio.current_task()
            if task:
                runs[run_id]["task"] = task
            result = await graph.ainvoke(state, config=config)
            if result.get("waiting_for_human"):
                runs[run_id] = {"status": "waiting_for_human", "result": result}
            elif result.get("error_state") is None:
                runs[run_id] = {"status": "completed", "result": result}
            else:
                runs[run_id] = {"status": "failed", "result": result}

            # Capture LangSmith trace link
            from agent.tracing import share_trace_link
            trace_url = await share_trace_link(run_id)
            if trace_url:
                runs[run_id]["trace_url"] = trace_url
    except asyncio.CancelledError:
        _rollback_edits(run_id)
        runs[run_id] = {"status": "cancelled", "result": "Cancelled by user"}
        logger.info("Run %s cancelled by user (resume)", run_id)
    except Exception as e:
        runs[run_id] = {"status": "error", "result": str(e)}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/instruction", response_model=InstructionResponse)
async def submit_instruction(req: InstructionRequest):
    store: SQLiteSessionStore = app.state.store
    router: ModelRouter = app.state.router

    run_id = str(uuid.uuid4())[:8]
    runs[run_id] = {"status": "running", "result": None}

    # Persist Run to store
    project_id = req.project_id or "default"
    db_run = Run(
        id=run_id,
        project_id=project_id,
        instruction=req.instruction,
        status="running",
        context=req.context,
    )
    try:
        await store.create_run(db_run)
    except Exception:
        pass  # store may not have the project; proceed anyway

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
                "ast_available": {},
                "invalidated_files": [],
            }
            from agent.tools.lsp_manager import LspManager
            async with LspManager(req.working_directory, {}) as lsp_mgr:
                config = {
                    "configurable": {
                        "store": store,
                        "router": router,
                        "approval_manager": app.state.approval_manager,
                        "run_id": run_id,
                        "lsp_manager": lsp_mgr,
                        "thread_id": run_id,
                    },
                    "tags": [f"run_id:{run_id}"],
                }
                result = await graph.ainvoke(initial_state, config=config)
                if result.get("waiting_for_human"):
                    runs[run_id] = {"status": "waiting_for_human", "result": result}
                elif result.get("error_state") is None:
                    runs[run_id] = {"status": "completed", "result": result}
                else:
                    runs[run_id] = {"status": "failed", "result": result}

                # Capture LangSmith trace link
                from agent.tracing import share_trace_link
                trace_url = await share_trace_link(run_id)
                if trace_url:
                    runs[run_id]["trace_url"] = trace_url
                    try:
                        db_run_obj = await store.get_run(run_id)
                        if db_run_obj:
                            db_run_obj.trace_url = trace_url
                            await store.update_run(db_run_obj)
                    except Exception:
                        logger.exception("Failed to persist trace_url for run %s", run_id)
        except asyncio.CancelledError:
            _rollback_edits(run_id)
            runs[run_id] = {"status": "cancelled", "result": "Cancelled by user"}
            logger.info("Run %s cancelled by user", run_id)
            try:
                db_run = await store.get_run(run_id)
                if db_run:
                    db_run.status = "cancelled"
                    await store.update_run(db_run)
            except Exception:
                logger.exception("Failed to update cancelled run %s in store", run_id)
        except Exception as e:
            runs[run_id] = {"status": "error", "result": str(e)}

    task = asyncio.create_task(execute())
    runs[run_id]["task"] = task
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
        "trace_url": run.get("trace_url"),
    }


@app.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    """Cancel a running agent run."""
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")
    run_entry = runs[run_id]
    if run_entry["status"] not in ("running",):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel run in state: {run_entry['status']}",
        )
    run_entry["status"] = "cancelling"
    task = run_entry.get("task")
    if task and not task.done():
        task.cancel()
    return {"run_id": run_id, "status": "cancelling"}


@app.post("/instruction/{run_id}")
async def continue_run(run_id: str, req: InstructionRequest):
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")
    store: SQLiteSessionStore = app.state.store
    router: ModelRouter = app.state.router
    runs[run_id]["status"] = "running"

    async def execute():
        try:
            graph = app.state.graph
            state = runs[run_id].get("result", {})
            if isinstance(state, str):
                state = {}
            state["instruction"] = req.instruction
            state["context"] = req.context
            state["error_state"] = None
            from agent.tools.lsp_manager import LspManager
            working_dir = state.get("working_directory", req.working_directory)
            async with LspManager(working_dir, {}) as lsp_mgr:
                config = {
                    "configurable": {
                        "store": store,
                        "router": router,
                        "approval_manager": app.state.approval_manager,
                        "run_id": run_id,
                        "lsp_manager": lsp_mgr,
                        "thread_id": run_id,
                    },
                    "tags": [f"run_id:{run_id}"],
                }
                result = await graph.ainvoke(state, config=config)
                if result.get("waiting_for_human"):
                    runs[run_id] = {"status": "waiting_for_human", "result": result}
                elif result.get("error_state") is None:
                    runs[run_id] = {"status": "completed", "result": result}
                else:
                    runs[run_id] = {"status": "failed", "result": result}

                # Capture LangSmith trace link
                from agent.tracing import share_trace_link
                trace_url = await share_trace_link(run_id)
                if trace_url:
                    runs[run_id]["trace_url"] = trace_url
        except asyncio.CancelledError:
            _rollback_edits(run_id)
            runs[run_id] = {"status": "cancelled", "result": "Cancelled by user"}
            logger.info("Run %s cancelled by user (continue)", run_id)
        except Exception as e:
            runs[run_id] = {"status": "error", "result": str(e)}

    task = asyncio.create_task(execute())
    runs[run_id]["task"] = task
    return {"run_id": run_id, "status": "running"}


@app.get("/browse")
async def browse_directory(project_id: str, path: str = ""):
    """List files and directories at the given path within a project root."""
    store: SQLiteSessionStore = app.state.store
    project = await store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    project_root = pathlib.Path(project.path).resolve()
    target = (project_root / path).resolve()

    if not target.is_relative_to(project_root):
        raise HTTPException(status_code=403, detail="Path traversal not allowed")
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {path}")

    dir_entries = []
    file_entries = []
    try:
        for entry in sorted(target.iterdir(), key=lambda e: e.name.lower()):
            if entry.name.startswith('.') or entry.name in _IGNORED_NAMES:
                continue
            rel_path = str(entry.relative_to(project_root).as_posix())
            try:
                if entry.is_dir():
                    try:
                        has_kids = any(
                            c for c in entry.iterdir()
                            if not c.name.startswith('.') and c.name not in _IGNORED_NAMES
                        )
                    except (PermissionError, OSError):
                        has_kids = False
                    dir_entries.append({
                        "name": entry.name,
                        "path": rel_path,
                        "is_dir": True,
                        "has_children": has_kids,
                    })
                else:
                    try:
                        size = entry.stat().st_size
                    except (PermissionError, OSError):
                        size = 0
                    file_entries.append({
                        "name": entry.name,
                        "path": rel_path,
                        "is_dir": False,
                        "size": size,
                    })
            except (PermissionError, OSError):
                continue
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {path}")

    entries = dir_entries + file_entries
    return {
        "current": str(target.relative_to(project_root)),
        "entries": entries,
    }


@app.get("/files")
async def read_file(project_id: str, path: str):
    """Read file content with language detection. Validates path is within project root."""
    store: SQLiteSessionStore = app.state.store
    project = await store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

    project_root = pathlib.Path(project.path).resolve()
    target = (project_root / path).resolve()

    if not target.is_relative_to(project_root):
        raise HTTPException(status_code=403, detail="Path traversal not allowed")
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    if target.is_dir():
        raise HTTPException(status_code=400, detail=f"Path is a directory: {path}")

    ext = target.suffix.lower()
    size = target.stat().st_size

    if ext in _BINARY_EXTS:
        return {"content": None, "language": "binary", "size": size, "binary": True, "path": path}

    # Detect language from extension, fallback based on filename
    language = _EXT_TO_LANG.get(ext, "plaintext")
    if target.name == "Dockerfile":
        language = "dockerfile"
    elif target.name == "Makefile":
        language = "makefile"
    elif target.name == "Procfile":
        language = "yaml"

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {"content": None, "language": "binary", "size": size, "binary": True, "path": path}

    return {"content": content, "language": language, "size": size, "binary": False, "path": path}


@app.get("/projects")
async def list_projects():
    store: SQLiteSessionStore = app.state.store
    projects = await store.list_projects()
    return [project_response(p) for p in projects]


@app.post("/projects", status_code=201)
async def create_project(req: CreateProjectRequest):
    store: SQLiteSessionStore = app.state.store
    project = Project(name=req.name, path=req.path)
    created = await store.create_project(project)
    return project_response(created)


@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    store: SQLiteSessionStore = app.state.store
    project = await store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project_response(project)


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


@app.patch("/runs/{run_id}/edits/{edit_id}")
async def patch_edit(run_id: str, edit_id: str, req: EditActionRequest):
    approval_manager: ApprovalManager = app.state.approval_manager
    store: SQLiteSessionStore = app.state.store

    # Ownership check
    edit = await store.get_edit(edit_id)
    if edit is None or edit.run_id != run_id:
        raise HTTPException(status_code=404, detail="Edit not found for this run")

    try:
        if req.action == "approve":
            result = await approval_manager.approve(edit_id, req.op_id)
            result = await approval_manager.apply_edit(edit_id)
            # Resume graph if waiting
            asyncio.create_task(_resume_run(run_id))
        else:
            result = await approval_manager.reject(edit_id, req.op_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Edit not found")
    except InvalidTransitionError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply edit: {e}")

    return {"edit_id": edit_id, "run_id": run_id, "status": result.status}


class BatchActionRequest(BaseModel):
    action: str


@app.patch("/runs/{run_id}/batches/{batch_id}")
async def patch_batch(run_id: str, batch_id: str, req: BatchActionRequest):
    approval_manager: ApprovalManager = app.state.approval_manager

    try:
        if req.action == "approve":
            op_id = f"op_batch_{batch_id}_approve"
            result = await approval_manager.approve_batch(batch_id, op_id)
            asyncio.create_task(_resume_run(run_id))
            return {"batch_id": batch_id, "action": "approved", "edit_count": len(result)}
        elif req.action == "reject":
            op_id = f"op_batch_{batch_id}_reject"
            result = await approval_manager.reject_batch(batch_id, op_id)
            asyncio.create_task(_resume_run(run_id))
            return {"batch_id": batch_id, "action": "rejected", "edit_count": len(result)}
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/runs/{run_id}/edits")
async def get_run_edits(run_id: str, status: str | None = None):
    store: SQLiteSessionStore = app.state.store
    edits = await store.get_edits(run_id, status=status)
    return [e.model_dump() for e in edits]


class GitCommitRequest(BaseModel):
    message: str | None = None


class GitPRRequest(BaseModel):
    title: str | None = None
    body: str | None = None
    draft: bool = False


class GitMergeRequest(BaseModel):
    pr_number: int
    method: str = "squash"


def _get_run_result(run_id: str) -> dict:
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")
    return runs[run_id].get("result", {})


def config_get_project_id(result: dict) -> str:
    """Extract project_id from run result context."""
    if isinstance(result, dict):
        ctx = result.get("context", {})
        return ctx.get("project_id", "")
    return ""


@app.post("/runs/{run_id}/git/commit")
async def git_commit(run_id: str, req: GitCommitRequest):
    store = app.state.store
    result = _get_run_result(run_id)
    working_dir = result.get("working_directory", "")
    if not working_dir:
        raise HTTPException(status_code=400, detail="No working directory")

    gm = GitManager(working_dir)
    message = req.message or f"feat: edits from Shipyard run {run_id[:8]}"

    # Stage applied edits
    applied = await store.get_edits(run_id, status="applied")
    files = list(set(e.file_path for e in applied))
    if not files:
        raise HTTPException(status_code=400, detail="No applied edits to commit")

    try:
        await gm.stage_files(files)
        sha = await gm.commit(message)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await store.log_git_op(GitOperation(run_id=run_id, type="commit", commit_sha=sha, status="ok"))
    return {"sha": sha, "message": message}


@app.post("/runs/{run_id}/git/push")
async def git_push(run_id: str):
    result = _get_run_result(run_id)
    working_dir = result.get("working_directory", "")
    if not working_dir:
        raise HTTPException(status_code=400, detail="No working directory")

    gm = GitManager(working_dir)
    try:
        branch = await gm.get_current_branch()
        await gm.push(branch)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"branch": branch, "status": "pushed"}


@app.post("/runs/{run_id}/git/pr")
async def git_create_pr(run_id: str, req: GitPRRequest):
    store = app.state.store
    result = _get_run_result(run_id)

    # Get GitHub config from project
    project_id = config_get_project_id(result)
    project = await store.get_project(project_id) if project_id else None
    if not project or not project.github_repo or not project.github_pat:
        raise HTTPException(status_code=400, detail="GitHub not configured for this project")

    working_dir = result.get("working_directory", "")
    gm = GitManager(working_dir)
    branch = await gm.get_current_branch()

    title = req.title or f"Shipyard: {result.get('instruction', 'edits')[:60]}"
    body = req.body or f"Automated PR from Shipyard run {run_id}"

    gh = GitHubClient(repo=project.github_repo, token=project.github_pat)
    try:
        pr_data = await gh.create_pr(branch=branch, title=title, body=body, draft=req.draft)
    finally:
        await gh.close()

    await store.log_git_op(GitOperation(run_id=run_id, type="pr_create", branch=branch, pr_url=pr_data["html_url"], pr_number=pr_data["number"], status="ok"))
    return pr_data


@app.post("/runs/{run_id}/git/merge")
async def git_merge_pr(run_id: str, req: GitMergeRequest):
    store = app.state.store
    result = _get_run_result(run_id)

    project_id = config_get_project_id(result)
    project = await store.get_project(project_id) if project_id else None
    if not project or not project.github_repo or not project.github_pat:
        raise HTTPException(status_code=400, detail="GitHub not configured")

    gh = GitHubClient(repo=project.github_repo, token=project.github_pat)
    try:
        merge_data = await gh.merge_pr(req.pr_number, method=req.method)
    finally:
        await gh.close()

    await store.log_git_op(GitOperation(run_id=run_id, type="pr_merge", pr_number=req.pr_number, status="ok"))
    return merge_data


@app.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    store: SQLiteSessionStore = app.state.store
    conn_manager: ConnectionManager = app.state.conn_manager
    project = await store.get_project(project_id)
    if project is None:
        await websocket.close(code=4004, reason="Project not found")
        return
    await websocket.accept()
    await conn_manager.connect(websocket, project_id)
    try:
        while True:
            data = await websocket.receive_json()
            await conn_manager.handle_client_message(websocket, data)
    except WebSocketDisconnect:
        await conn_manager.disconnect(websocket)
    except Exception:
        logger.exception("WebSocket error for project %s", project_id)
        await conn_manager.disconnect(websocket)


# --- Production static file serving ---
# Must be AFTER all API routes. Serves the built React frontend.
from fastapi.staticfiles import StaticFiles

_frontend_dir = os.path.join(os.path.dirname(__file__), "..", "web", "dist")
if os.path.isdir(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
