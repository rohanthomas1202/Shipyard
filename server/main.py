import os
import uuid
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Literal as TypingLiteral
from agent.graph import build_graph
from agent.router import ModelRouter
from agent.events import EventBus
from agent.approval import ApprovalManager, InvalidTransitionError
from store.sqlite import SQLiteSessionStore
from store.models import Project, Run
from server.websocket import ConnectionManager


runs: dict[str, dict] = {}

DB_PATH = os.environ.get("SHIPYARD_DB_PATH", "shipyard.db")

HEARTBEAT_INTERVAL = 15
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
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

    app.state.store = store
    app.state.router = ModelRouter()
    app.state.graph = build_graph()
    app.state.event_bus = event_bus
    app.state.conn_manager = conn_manager
    app.state.approval_manager = approval_manager

    heartbeat_task = asyncio.create_task(_heartbeat_loop(conn_manager))
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


class EditActionRequest(BaseModel):
    action: TypingLiteral["approve", "reject"]
    op_id: str


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
        config = {"configurable": {"store": store, "router": router}}
        result = await graph.ainvoke(state, config=config)
        if result.get("waiting_for_human"):
            runs[run_id] = {"status": "waiting_for_human", "result": result}
        elif result.get("error_state") is None:
            runs[run_id] = {"status": "completed", "result": result}
        else:
            runs[run_id] = {"status": "failed", "result": result}
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
            }
            config = {"configurable": {"store": store, "router": router}}
            result = await graph.ainvoke(initial_state, config=config)
            if result.get("waiting_for_human"):
                runs[run_id] = {"status": "waiting_for_human", "result": result}
            elif result.get("error_state") is None:
                runs[run_id] = {"status": "completed", "result": result}
            else:
                runs[run_id] = {"status": "failed", "result": result}
        except Exception as e:
            runs[run_id] = {"status": "error", "result": str(e)}

    asyncio.create_task(execute())
    return InstructionResponse(run_id=run_id, status="running")


@app.get("/status/{run_id}")
async def get_status(run_id: str):
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="Run not found")
    run = runs[run_id]
    return {"run_id": run_id, "status": run["status"], "result": run.get("result")}


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
            config = {"configurable": {"store": store, "router": router}}
            result = await graph.ainvoke(state, config=config)
            if result.get("waiting_for_human"):
                runs[run_id] = {"status": "waiting_for_human", "result": result}
            elif result.get("error_state") is None:
                runs[run_id] = {"status": "completed", "result": result}
            else:
                runs[run_id] = {"status": "failed", "result": result}
        except Exception as e:
            runs[run_id] = {"status": "error", "result": str(e)}

    asyncio.create_task(execute())
    return {"run_id": run_id, "status": "running"}


@app.get("/projects")
async def list_projects():
    store: SQLiteSessionStore = app.state.store
    projects = await store.list_projects()
    return [p.model_dump() for p in projects]


@app.post("/projects", status_code=201)
async def create_project(req: CreateProjectRequest):
    store: SQLiteSessionStore = app.state.store
    project = Project(name=req.name, path=req.path)
    created = await store.create_project(project)
    return created.model_dump()


@app.get("/projects/{project_id}")
async def get_project(project_id: str):
    store: SQLiteSessionStore = app.state.store
    project = await store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.model_dump()


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
