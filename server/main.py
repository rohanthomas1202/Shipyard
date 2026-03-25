import os
import uuid
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agent.graph import build_graph
from agent.router import ModelRouter
from store.sqlite import SQLiteSessionStore
from store.models import Project, Run


runs: dict[str, dict] = {}

DB_PATH = os.environ.get("SHIPYARD_DB_PATH", "shipyard.db")


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = SQLiteSessionStore(DB_PATH)
    await store.initialize()
    app.state.store = store
    app.state.router = ModelRouter()
    app.state.graph = build_graph()
    yield
    await store.close()


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
            runs[run_id] = {
                "status": "completed" if result.get("error_state") is None else "failed",
                "result": result,
            }
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
            runs[run_id] = {
                "status": "completed" if result.get("error_state") is None else "failed",
                "result": result,
            }
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
