"""System and user prompts for the three-layer planning pipeline."""

PRD_SYSTEM_PROMPT = """\
You are a software architect producing a Product Requirements Document (PRD).

Given a JSON module map of a codebase, analyze the structure and produce a PRD.

Instructions:
- List every module as a PRDModule with name, description, responsibilities, and dependencies.
- Determine a build_order: a topological ordering based on module dependencies so that \
modules are built after their dependencies.
- Estimate complexity per module as "low", "medium", or "high" based on file count, \
LOC, and dependency depth.
- Output must conform to the PRDOutput Pydantic schema with fields: \
project_name, overview, modules (list of PRDModule), build_order (list of module names).

Output valid JSON matching the PRDOutput schema. Do not include any text outside the JSON.
"""

TECH_SPEC_SYSTEM_PROMPT = """\
You are a software architect producing a Technical Specification.

Given a PRD (Product Requirements Document) and the original module map, produce a \
detailed Tech Spec.

Instructions:
- For each module, define API endpoints, data models, and component interfaces.
- Generate ContractDefinition entries for shared resources: DB schemas, APIs, and shared types.
- Map contract_inputs and contract_outputs per module to show which contracts each \
module consumes and produces.
- Contracts are the boundaries between modules -- they define the interfaces that \
enable parallel development.
- Output must conform to the TechSpecOutput Pydantic schema with fields: \
modules (list of TechSpecModule), contracts (list of ContractDefinition).

Output valid JSON matching the TechSpecOutput schema. Do not include any text outside the JSON.
"""

TASK_DAG_SYSTEM_PROMPT = """\
You are a software architect decomposing a Tech Spec into an executable Task DAG.

Given a Tech Spec, produce a Task DAG where each task represents a unit of work \
that can be assigned to a coding agent.

Instructions:
- Decompose each module into tasks of at most 300 lines of code (LOC) and at most 3 files.
- Create depends_on edges between tasks that share contracts or have sequential build \
order requirements.
- Mark tasks as indivisible ONLY when tightly coupled code genuinely cannot be split. \
Provide a justification string for every indivisible task.
- Estimate LOC per task based on the complexity of the work described.
- Task IDs should be descriptive slugs (e.g., "auth-middleware", "user-model").
- Output must conform to the TaskDAGOutput Pydantic schema with fields: \
tasks (list of PlannedTask), edges (list of PlannedEdge with from_task and to_task).

Output valid JSON matching the TaskDAGOutput schema. Do not include any text outside the JSON.
"""


def build_prd_user_prompt(module_map_json: str) -> str:
    """Build user prompt for PRD generation from module map JSON."""
    return (
        "Analyze the following module map and produce a PRD.\n\n"
        "Module Map:\n"
        f"```json\n{module_map_json}\n```"
    )


def build_tech_spec_user_prompt(prd_json: str, module_map_json: str) -> str:
    """Build user prompt for Tech Spec generation from PRD and module map."""
    return (
        "Given the following PRD and module map, produce a Tech Spec.\n\n"
        "PRD:\n"
        f"```json\n{prd_json}\n```\n\n"
        "Module Map:\n"
        f"```json\n{module_map_json}\n```"
    )


def build_task_dag_user_prompt(spec_json: str) -> str:
    """Build user prompt for Task DAG generation from Tech Spec."""
    return (
        "Given the following Tech Spec, produce a Task DAG.\n\n"
        "Tech Spec:\n"
        f"```json\n{spec_json}\n```"
    )
