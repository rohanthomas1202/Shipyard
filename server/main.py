import uuid
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agent.graph import build_graph

runs: dict[str, dict] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.graph = build_graph()
    yield

app = FastAPI(title="Shipyard Agent", lifespan=lifespan)

class InstructionRequest(BaseModel):
    instruction: str
    working_directory: str
    context: dict = {}

class InstructionResponse(BaseModel):
    run_id: str
    status: str

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/instruction", response_model=InstructionResponse)
async def submit_instruction(req: InstructionRequest):
    run_id = str(uuid.uuid4())[:8]
    runs[run_id] = {"status": "running", "result": None}

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
            result = await graph.ainvoke(initial_state)
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
            result = await graph.ainvoke(state)
            runs[run_id] = {
                "status": "completed" if result.get("error_state") is None else "failed",
                "result": result,
            }
        except Exception as e:
            runs[run_id] = {"status": "error", "result": str(e)}

    asyncio.create_task(execute())
    return {"run_id": run_id, "status": "running"}
