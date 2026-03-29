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

CI_STARTED = "ci_started"
CI_PASSED = "ci_passed"
CI_FAILED = "ci_failed"
OWNERSHIP_VIOLATION = "ownership_violation"
TASK_REQUEUED = "task_requeued"

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
    CI_STARTED,
    CI_PASSED,
    CI_FAILED,
    OWNERSHIP_VIOLATION,
    TASK_REQUEUED,
})
