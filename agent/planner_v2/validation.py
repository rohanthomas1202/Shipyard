"""Structural validation gates for the three-layer planning pipeline."""
from pydantic import BaseModel, Field

from agent.planner_v2.models import PRDOutput, TechSpecOutput, TaskDAGOutput
from agent.orchestrator.dag import TaskDAG
from agent.analyzer.models import ModuleMap


class ValidationError(BaseModel):
    """A validation error or warning."""
    field: str
    message: str
    severity: str = "error"  # "error" | "warning"


TOKENS_PER_LOC = 50  # Estimated tokens per LOC of generated code


def validate_prd(prd: PRDOutput, module_map: ModuleMap) -> list[ValidationError]:
    """Validate PRD against module map. Per D-06: structural only."""
    errors: list[ValidationError] = []
    prd_module_names = {m.name for m in prd.modules}
    map_module_names = {m.name for m in module_map.modules}

    # Check every module map module is covered
    for name in map_module_names:
        if name not in prd_module_names:
            errors.append(ValidationError(
                field="modules",
                message=f"Module '{name}' from module map not covered in PRD",
            ))

    # Check dependency references are valid
    for mod in prd.modules:
        for dep in mod.depends_on:
            if dep not in prd_module_names:
                errors.append(ValidationError(
                    field=f"modules.{mod.name}.depends_on",
                    message=f"References unknown module: {dep}",
                ))
    return errors


def validate_tech_spec(spec: TechSpecOutput, prd: PRDOutput) -> list[ValidationError]:
    """Validate Tech Spec against PRD. Per D-06: structural only."""
    errors: list[ValidationError] = []
    contract_names = {c.name for c in spec.contracts}

    # Check contract references in modules
    for mod in spec.modules:
        for ci in mod.contract_inputs:
            if ci not in contract_names:
                errors.append(ValidationError(
                    field=f"modules.{mod.name}.contract_inputs",
                    message=f"References unknown contract: {ci}",
                ))
        for co in mod.contract_outputs:
            if co not in contract_names:
                errors.append(ValidationError(
                    field=f"modules.{mod.name}.contract_outputs",
                    message=f"References unknown contract: {co}",
                ))
    return errors


def validate_task_dag(
    dag_output: TaskDAGOutput,
    spec: TechSpecOutput,
) -> list[ValidationError]:
    """Validate Task DAG. Per D-06 and D-09: structural validation with bounds."""
    errors: list[ValidationError] = []

    # 1. Check LOC bounds (D-09)
    for task in dag_output.tasks:
        if task.estimated_loc > 300 and not task.indivisible:
            errors.append(ValidationError(
                field=f"tasks.{task.id}.estimated_loc",
                message=f"Task exceeds 300 LOC ({task.estimated_loc}) "
                        f"without indivisible flag",
            ))
        if len(task.target_files) > 3 and not task.indivisible:
            errors.append(ValidationError(
                field=f"tasks.{task.id}.target_files",
                message=f"Task touches {len(task.target_files)} files "
                        f"(max 3) without indivisible flag",
            ))

    # 2. Check DAG is acyclic using TaskDAG.from_definition()
    if dag_output.tasks:
        task_dicts = [
            {
                "id": t.id,
                "label": t.label,
                "description": t.description,
                "task_type": t.task_type,
                "contract_inputs": t.contract_inputs,
                "contract_outputs": t.contract_outputs,
            }
            for t in dag_output.tasks
        ]
        edge_dicts = [e.model_dump() for e in dag_output.edges]
        dag = TaskDAG.from_definition(
            dag_id="validation-check",
            tasks=task_dicts,
            edges=edge_dicts,
        )
        if not dag.validate():
            errors.append(ValidationError(
                field="edges",
                message="Task DAG contains dependency cycles",
            ))

    # 3. Check contract references
    spec_contracts = {c.name for c in spec.contracts}
    for task in dag_output.tasks:
        for ci in task.contract_inputs:
            if ci not in spec_contracts:
                errors.append(ValidationError(
                    field=f"tasks.{task.id}.contract_inputs",
                    message=f"References unknown contract: {ci}",
                ))

    return errors


def estimate_cost(dag_output: TaskDAGOutput) -> int:
    """Estimate total tokens for executing the Task DAG.

    Formula: sum(task.estimated_loc * TOKENS_PER_LOC) per D-10 and research.
    Reports estimated tokens, not dollars (unlimited budget per project constraints).
    """
    return sum(t.estimated_loc * TOKENS_PER_LOC for t in dag_output.tasks)
