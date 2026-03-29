"""Observability metrics: decision trace construction and failure heatmap aggregation."""
from __future__ import annotations

from agent.orchestrator.models import DecisionTrace

_TRUNCATE_LIMIT = 2000


def build_decision_trace(
    task_id: str,
    dag_id: str,
    error_message: str,
    *,
    error_category: str = "structural",
    llm_prompt: str | None = None,
    llm_response: str | None = None,
    files_read: list[str] | None = None,
    final_state: dict | None = None,
    module_name: str | None = None,
) -> DecisionTrace:
    """Build a DecisionTrace, truncating LLM context to avoid bloat."""
    return DecisionTrace(
        task_id=task_id,
        dag_id=dag_id,
        error_message=error_message,
        error_category=error_category,
        llm_prompt=llm_prompt[:_TRUNCATE_LIMIT] if llm_prompt else None,
        llm_response=llm_response[:_TRUNCATE_LIMIT] if llm_response else None,
        files_read=files_read or [],
        final_state=final_state or {},
        module_name=module_name,
    )


def aggregate_heatmap(
    traces: list[DecisionTrace],
) -> dict[str, dict[str, int]]:
    """Aggregate failure traces into module x error_category counts.

    Returns: {"module_name": {"syntax": 2, "test": 1, ...}, ...}
    Traces with module_name=None are grouped under "unknown".
    """
    heatmap: dict[str, dict[str, int]] = {}
    for trace in traces:
        module = trace.module_name or "unknown"
        if module not in heatmap:
            heatmap[module] = {}
        cat = trace.error_category
        heatmap[module][cat] = heatmap[module].get(cat, 0) + 1
    return heatmap
