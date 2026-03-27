import re

from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes.receive import receive_instruction_node
from agent.nodes.planner import planner_node
from agent.nodes.reader import reader_node
from agent.nodes.editor import editor_node
from agent.nodes.executor import executor_node
from agent.nodes.validator import validator_node
from agent.nodes.coordinator import coordinator_node
from agent.nodes.merger import merger_node
from agent.nodes.reporter import reporter_node


def _normalize_error(msg: str) -> str:
    """Strip line/col numbers and paths for error dedup comparison."""
    normalized = re.sub(r'[Ll]ine \d+', 'Line N', msg)
    normalized = re.sub(r'col \d+|column \d+|offset \d+', 'col N', normalized)
    normalized = re.sub(r'/[^\s:]+/', '/', normalized)
    return normalized.strip()


def _has_repeated_error(state: dict, threshold: int = 2) -> bool:
    """Check if the same normalized error has occurred threshold+ times for current step."""
    history = state.get("validation_error_history", [])
    current_step = state.get("current_step", 0)
    lve = state.get("last_validation_error")
    if not lve:
        return False

    current_normalized = _normalize_error(lve.get("error_message", ""))
    count = 0
    for entry in history:
        if entry.get("step") == current_step and entry.get("normalized_error") == current_normalized:
            count += 1
    return count >= threshold


def _retry_count(state: dict) -> int:
    count = 0
    for entry in reversed(state.get("edit_history", [])):
        if entry.get("error"):
            count += 1
        else:
            break
    return count


def should_continue(state: dict) -> str:
    error = state.get("error_state")
    plan = state.get("plan", [])
    step = state.get("current_step", 0)

    if error:
        if _retry_count(state) >= 3:
            return "reporter"
        if _has_repeated_error(state, threshold=2):
            return "advance" if step + 1 < len(plan) else "reporter"
        return "reader"

    if step + 1 < len(plan):
        return "advance"
    return "reporter"


def advance_step(state: dict) -> dict:
    return {"current_step": state["current_step"] + 1}


def classify_step(state: dict) -> str:
    """Route to the correct node based on PlanStep.kind."""
    plan = state.get("plan", [])
    idx = state.get("current_step", 0)

    if idx >= len(plan):
        return "reporter"

    step = plan[idx]

    # Typed step (dict with "kind" field)
    if isinstance(step, dict) and "kind" in step:
        kind = step["kind"]
        if kind in ("exec", "test"):
            return "executor"
        if kind == "read":
            return "reader_only"
        if kind == "edit":
            return "reader_then_edit"
        if kind == "git":
            return "reporter"  # git_ops deferred to Phase 2
        return "reader_then_edit"

    # Fallback: legacy string-based step (backward compat)
    if isinstance(step, str):
        step_lower = step.lower()
        if any(kw in step_lower for kw in ["run", "execute", "test", "build", "install"]):
            return "executor"
        if any(kw in step_lower for kw in ["read", "understand", "examine", "check"]):
            return "reader_only"

    return "reader_then_edit"


def after_reader(state: dict) -> str:
    plan = state.get("plan", [])
    step = state.get("current_step", 0)
    if step >= len(plan):
        return "advance"
    step_text = plan[step].lower()
    if any(kw in step_text for kw in ["read ", "understand", "examine", "check "]):
        return "advance"
    return "editor"


def _build_graph_nodes(graph: StateGraph):
    graph.add_node("receive", receive_instruction_node)
    graph.add_node("planner", planner_node)
    graph.add_node("coordinator", coordinator_node)
    graph.add_node("reader", reader_node)
    graph.add_node("editor", editor_node)
    graph.add_node("executor", executor_node)
    graph.add_node("validator", validator_node)
    graph.add_node("merger", merger_node)
    graph.add_node("reporter", reporter_node)
    graph.add_node("advance", advance_step)
    graph.add_node("classify", lambda s: {})

    graph.set_entry_point("receive")

    graph.add_edge("receive", "planner")
    graph.add_edge("planner", "coordinator")
    graph.add_edge("coordinator", "classify")

    graph.add_conditional_edges("classify", classify_step, {
        "executor": "executor",
        "reader_only": "reader",
        "reader_then_edit": "reader",
        "reporter": "reporter",
    })

    graph.add_conditional_edges("reader", after_reader, {
        "editor": "editor",
        "advance": "advance",
    })

    graph.add_edge("editor", "validator")

    graph.add_conditional_edges("executor", should_continue, {
        "reader": "reader",
        "advance": "advance",
        "reporter": "reporter",
    })

    graph.add_conditional_edges("validator", should_continue, {
        "reader": "reader",
        "advance": "advance",
        "reporter": "reporter",
    })

    graph.add_edge("advance", "classify")
    graph.add_edge("reporter", END)


def build_graph():
    graph = StateGraph(AgentState)
    _build_graph_nodes(graph)
    return graph.compile()
