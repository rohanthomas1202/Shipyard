"""WebSocket ConnectionManager for real-time event streaming."""
from __future__ import annotations
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from store.models import Event
from agent.events import EventBus

logger = logging.getLogger(__name__)


@dataclass
class WebSocketState:
    ws: Any
    project_id: str
    subscribed_runs: set[str] = field(default_factory=set)
    last_seq: dict[str, int] = field(default_factory=dict)
    connected_at: float = field(default_factory=time.time)


def _event_payload(event: Event) -> dict:
    """Build the JSON payload for sending an event over WebSocket."""
    return {
        "type": event.type,
        "run_id": event.run_id,
        "seq": event.seq,
        "timestamp": event.timestamp,
        "data": event.data,
        "node": event.node,
        "model": event.model,
    }


class ConnectionManager:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._connections: dict[str, list[WebSocketState]] = {}
        self._ws_to_project: dict[int, str] = {}
        self._stop_callback: Callable[[str], Awaitable[None]] | None = None
        self._approve_callback: Callable[[str, str, str], Awaitable[None]] | None = None
        self._reject_callback: Callable[[str, str, str], Awaitable[None]] | None = None

    def set_stop_callback(self, callback: Callable[[str], Awaitable[None]]) -> None:
        self._stop_callback = callback

    def set_approve_callback(self, callback: Callable[[str, str, str], Awaitable[None]]) -> None:
        self._approve_callback = callback

    def set_reject_callback(self, callback: Callable[[str, str, str], Awaitable[None]]) -> None:
        self._reject_callback = callback

    async def connect(self, ws: Any, project_id: str) -> WebSocketState:
        state = WebSocketState(ws=ws, project_id=project_id)
        self._connections.setdefault(project_id, []).append(state)
        self._ws_to_project[id(ws)] = project_id
        return state

    async def disconnect(self, ws: Any) -> None:
        ws_id = id(ws)
        project_id = self._ws_to_project.pop(ws_id, None)
        if project_id and project_id in self._connections:
            self._connections[project_id] = [
                s for s in self._connections[project_id] if s.ws is not ws
            ]
            if not self._connections[project_id]:
                del self._connections[project_id]

    async def send_to_subscribed(self, event: Event) -> None:
        """Send event to clients subscribed to event.run_id. Reads project_id from event."""
        project_id = event.project_id
        states = self._connections.get(project_id, [])
        payload = _event_payload(event)
        dead = []
        for state in states:
            if event.run_id in state.subscribed_runs:
                try:
                    await state.ws.send_json(payload)
                    state.last_seq[event.run_id] = event.seq
                except Exception:
                    logger.warning("Failed to send to WebSocket, removing connection")
                    dead.append(state)
        for state in dead:
            await self.disconnect(state.ws)

    async def handle_client_message(self, ws: Any, data: dict) -> None:
        action = data.get("action")
        state = self._find_state(ws)
        if state is None:
            return

        if action == "subscribe":
            run_id = data.get("run_id")
            if run_id:
                state.subscribed_runs.add(run_id)

        elif action == "reconnect":
            run_id = data.get("run_id")
            last_seq = data.get("last_seq", 0)
            if run_id:
                state.subscribed_runs.add(run_id)
                # Send snapshot FIRST
                snapshot = await self.event_bus.get_snapshot(run_id)
                try:
                    await ws.send_json(snapshot)
                except Exception:
                    return
                # Then replay durable events
                events = await self.event_bus.replay(run_id, after_seq=last_seq)
                for event in events:
                    try:
                        await ws.send_json(_event_payload(event))
                    except Exception:
                        break

        elif action == "approve":
            run_id = data.get("run_id")
            edit_id = data.get("edit_id", "")
            op_id = data.get("op_id", "")
            if self._approve_callback and run_id and edit_id and op_id:
                await self._approve_callback(run_id, edit_id, op_id)

        elif action == "reject":
            run_id = data.get("run_id")
            edit_id = data.get("edit_id", "")
            op_id = data.get("op_id", "")
            if self._reject_callback and run_id and edit_id and op_id:
                await self._reject_callback(run_id, edit_id, op_id)

        elif action == "stop":
            run_id = data.get("run_id")
            if self._stop_callback and run_id:
                await self._stop_callback(run_id)

    async def broadcast_heartbeat(self) -> None:
        payload = {"type": "heartbeat", "timestamp": time.time()}
        dead = []
        for project_id, states in self._connections.items():
            for state in states:
                try:
                    await state.ws.send_json(payload)
                except Exception:
                    dead.append(state)
        for state in dead:
            await self.disconnect(state.ws)

    def _find_state(self, ws: Any) -> WebSocketState | None:
        ws_id = id(ws)
        project_id = self._ws_to_project.get(ws_id)
        if project_id is None:
            return None
        for state in self._connections.get(project_id, []):
            if state.ws is ws:
                return state
        return None
