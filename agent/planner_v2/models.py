"""Pydantic models for the three-layer planning pipeline (PRD, Tech Spec, Task DAG)."""
from pydantic import BaseModel, Field


# --- PRD Layer (Layer 1) ---

class PRDModule(BaseModel):
    """A buildable module unit in the PRD."""
    name: str
    description: str
    responsibilities: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    estimated_complexity: str = "medium"  # "low" | "medium" | "high"


class PRDOutput(BaseModel):
    """Structured PRD output from Layer 1."""
    project_name: str
    overview: str
    modules: list[PRDModule] = Field(default_factory=list)
    build_order: list[str] = Field(default_factory=list)


# --- Tech Spec Layer (Layer 2) ---

class ContractDefinition(BaseModel):
    """A contract (DB schema, API, shared type) defined in the Tech Spec."""
    name: str
    contract_type: str  # "db_schema" | "api" | "shared_types"
    content: str  # The actual contract content (SQL, OpenAPI YAML, TypeScript)


class TechSpecModule(BaseModel):
    """Technical specification for a single module."""
    name: str
    api_endpoints: list[str] = Field(default_factory=list)
    data_models: list[str] = Field(default_factory=list)
    component_interfaces: list[str] = Field(default_factory=list)
    contract_inputs: list[str] = Field(default_factory=list)
    contract_outputs: list[str] = Field(default_factory=list)


class TechSpecOutput(BaseModel):
    """Structured Tech Spec output from Layer 2."""
    modules: list[TechSpecModule] = Field(default_factory=list)
    contracts: list[ContractDefinition] = Field(default_factory=list)


# --- Task DAG Layer (Layer 3) ---

class PlannedTask(BaseModel):
    """A single task in the generated DAG."""
    id: str
    label: str
    description: str
    target_files: list[str] = Field(default_factory=list)
    estimated_loc: int = Field(default=100)
    task_type: str = "agent"
    contract_inputs: list[str] = Field(default_factory=list)
    contract_outputs: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    indivisible: bool = False
    indivisible_justification: str | None = None


class PlannedEdge(BaseModel):
    """Dependency edge in the generated DAG."""
    from_task: str
    to_task: str


class TaskDAGOutput(BaseModel):
    """Complete Task DAG from Planner Layer 3."""
    tasks: list[PlannedTask] = Field(default_factory=list)
    edges: list[PlannedEdge] = Field(default_factory=list)


# --- Pipeline Result ---

class PipelineResult(BaseModel):
    """Full output of the three-layer planning pipeline."""
    prd: PRDOutput
    spec: TechSpecOutput
    dag: TaskDAGOutput
    estimated_total_tokens: int = 0
    validation_warnings: list[str] = Field(default_factory=list)
