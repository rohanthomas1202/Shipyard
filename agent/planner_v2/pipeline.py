"""Sequential three-layer planning pipeline with validation gates."""
from agent.analyzer.models import ModuleMap
from agent.planner_v2.models import PipelineResult
from agent.planner_v2.prd import generate_prd
from agent.planner_v2.tech_spec import generate_tech_spec
from agent.planner_v2.dag_builder import generate_task_dag
from agent.planner_v2.validation import (
    validate_prd, validate_tech_spec, validate_task_dag, estimate_cost,
)
from agent.router import ModelRouter


class PlanValidationError(Exception):
    """Raised when a pipeline validation gate fails."""

    def __init__(self, layer: str, errors: list):
        self.layer = layer
        self.errors = errors
        messages = [f"[{e.severity}] {e.field}: {e.message}" for e in errors]
        super().__init__(f"{layer} validation failed:\n" + "\n".join(messages))


async def run_pipeline(
    module_map: ModuleMap,
    router: ModelRouter,
) -> PipelineResult:
    """Execute PRD -> Tech Spec -> Task DAG with validation gates.

    Per D-05: Sequential single-pass pipeline, one LLM call per layer.
    Per D-06: Structural validation only between layers.

    Raises PlanValidationError if any validation gate fails.
    """
    # Layer 1: PRD from module map (PLAN-01)
    prd = await generate_prd(module_map, router)
    prd_errors = validate_prd(prd, module_map)
    if any(e.severity == "error" for e in prd_errors):
        raise PlanValidationError("PRD", [e for e in prd_errors if e.severity == "error"])
    prd_warnings = [e.message for e in prd_errors if e.severity == "warning"]

    # Layer 2: Tech Spec from PRD (PLAN-02)
    spec = await generate_tech_spec(prd, module_map, router)
    spec_errors = validate_tech_spec(spec, prd)
    if any(e.severity == "error" for e in spec_errors):
        raise PlanValidationError("Tech Spec", [e for e in spec_errors if e.severity == "error"])
    spec_warnings = [e.message for e in spec_errors if e.severity == "warning"]

    # Layer 3: Task DAG from Tech Spec (PLAN-03)
    dag = await generate_task_dag(spec, router)
    dag_errors = validate_task_dag(dag, spec)
    if any(e.severity == "error" for e in dag_errors):
        raise PlanValidationError("Task DAG", [e for e in dag_errors if e.severity == "error"])
    dag_warnings = [e.message for e in dag_errors if e.severity == "warning"]

    # Cost estimation (PLAN-04)
    total_tokens = estimate_cost(dag)

    return PipelineResult(
        prd=prd,
        spec=spec,
        dag=dag,
        estimated_total_tokens=total_tokens,
        validation_warnings=prd_warnings + spec_warnings + dag_warnings,
    )
