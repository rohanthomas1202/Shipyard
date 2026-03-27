"""Thin helpers for emitting events from graph nodes.

Nodes call these functions with their config dict. If event_bus is not
in config (e.g. during tests), calls are silent no-ops.
"""
from store.models import Event


async def emit_status(config: dict, node: str, message: str) -> None:
    """Emit a P2 status event (buffered until node boundary flush)."""
    bus, project_id, run_id = _extract(config)
    if bus is None:
        return
    await bus.emit(Event(
        project_id=project_id,
        run_id=run_id,
        type="status",
        node=node,
        data={"message": message},
    ))


async def emit_node_event(config: dict, node: str, event_type: str, data: dict) -> None:
    """Emit an arbitrary event from a node."""
    bus, project_id, run_id = _extract(config)
    if bus is None:
        return
    await bus.emit(Event(
        project_id=project_id,
        run_id=run_id,
        type=event_type,
        node=node,
        data=data,
    ))


async def flush_node(config: dict) -> None:
    """Flush P2 events at node boundary."""
    bus, _, run_id = _extract(config)
    if bus is None:
        return
    await bus.flush_node_boundary(run_id)


def _extract(config: dict) -> tuple:
    """Extract event_bus, project_id, run_id from config. Returns (None, '', '') if missing."""
    c = config.get("configurable", {})
    bus = c.get("event_bus")
    project_id = c.get("project_id", "")
    run_id = c.get("run_id", "")
    return bus, project_id, run_id
