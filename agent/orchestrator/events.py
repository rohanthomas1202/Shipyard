"""Task lifecycle event type constants for DAG orchestration."""

TASK_STARTED = "task_started"
TASK_COMPLETED = "task_completed"
TASK_FAILED = "task_failed"

DAG_STARTED = "dag_started"
DAG_COMPLETED = "dag_completed"
DAG_FAILED = "dag_failed"

CONTRACT_UPDATE_REQUESTED = "contract_update_requested"

PROGRESS_UPDATE = "progress_update"
DECISION_TRACE = "decision_trace"

TASK_LIFECYCLE_EVENTS = frozenset({
    TASK_STARTED,
    TASK_COMPLETED,
    TASK_FAILED,
    DAG_STARTED,
    DAG_COMPLETED,
    DAG_FAILED,
    CONTRACT_UPDATE_REQUESTED,
    PROGRESS_UPDATE,
    DECISION_TRACE,
})
