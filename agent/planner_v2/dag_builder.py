"""Task DAG generation layer (Layer 3) of the planning pipeline."""
from agent.planner_v2.models import TechSpecOutput, TaskDAGOutput
from agent.planner_v2.prompts import TASK_DAG_SYSTEM_PROMPT, build_task_dag_user_prompt
from agent.orchestrator.dag import TaskDAG
from agent.router import ModelRouter


async def generate_task_dag(spec: TechSpecOutput, router: ModelRouter) -> TaskDAGOutput:
    """Generate a Task DAG from a Tech Spec.

    Per D-05: Single LLM call using o3 (plan_dag task type).
    Per D-09: Tasks bounded to <=300 LOC and <=3 files (validation in validation.py).
    Per D-10: LLM estimates LOC per task.
    """
    spec_json = spec.model_dump_json(indent=2)
    user_prompt = build_task_dag_user_prompt(spec_json)
    dag_output: TaskDAGOutput = await router.call_structured(
        "plan_dag",
        TASK_DAG_SYSTEM_PROMPT,
        user_prompt,
        response_model=TaskDAGOutput,
    )
    return dag_output


def build_orchestrator_dag(dag_output: TaskDAGOutput, dag_id: str) -> TaskDAG:
    """Convert a TaskDAGOutput into a Phase 12 TaskDAG for the orchestrator.

    Uses TaskDAG.from_definition() per research recommendation.
    Copies task dicts to avoid pop("id") mutation pitfall.
    """
    task_dicts = [
        {
            "id": t.id,
            "label": t.label,
            "description": t.description,
            "task_type": t.task_type,
            "contract_inputs": t.contract_inputs,
            "contract_outputs": t.contract_outputs,
            "metadata": {
                "estimated_loc": t.estimated_loc,
                "target_files": t.target_files,
                "indivisible": t.indivisible,
                "indivisible_justification": t.indivisible_justification,
            },
        }
        for t in dag_output.tasks
    ]
    edge_dicts = [{"from_task": e.from_task, "to_task": e.to_task} for e in dag_output.edges]
    return TaskDAG.from_definition(dag_id=dag_id, tasks=task_dicts, edges=edge_dicts)
