"""Event bus and token batcher for real-time streaming."""
from __future__ import annotations
import asyncio
import logging
from typing import Any, Callable, Awaitable

from store.models import Event

logger = logging.getLogger(__name__)


class TokenBatcher:
    """Buffers items and flushes them at a fixed interval."""

    def __init__(self, flush_interval: float = 0.05):
        self.flush_interval = flush_interval
        self._buffer: list[Any] = []
        self._task: asyncio.Task | None = None
        self._on_flush: Callable[[list[Any]], Awaitable[None]] | None = None
        self._running = False

    def start(self, on_flush: Callable[[list[Any]], Awaitable[None]]) -> None:
        if self._running:
            return  # idempotent
        self._on_flush = on_flush
        self._running = True
        self._task = asyncio.create_task(self._flush_loop())

    def add(self, item: Any) -> None:
        self._buffer.append(item)

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._buffer and self._on_flush is not None:
            items = list(self._buffer)
            self._buffer.clear()
            try:
                await self._on_flush(items)
            except Exception:
                logger.exception("TokenBatcher final flush failed")

    async def _flush_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.flush_interval)
            if self._buffer and self._on_flush is not None:
                items = list(self._buffer)
                self._buffer.clear()
                try:
                    await self._on_flush(items)
                except Exception:
                    logger.exception("TokenBatcher flush failed")


_P0_TYPES = frozenset({"approval", "error", "stop", "review"})
_P1_TYPES = frozenset({"stream", "diff", "git"})
_NO_PERSIST_TYPES = frozenset({"stream"})


class EventBus:
    """Central event bus with priority-based routing.

    P0 (approval, error, stop, review): send immediately, persist.
    P1 (stream, diff, git): buffer in batcher, persist non-stream.
    P2 (status, file, exec, ...): persist and send at node boundaries.
    """

    def __init__(self, store: Any):
        self.store = store
        self._send_callback: Callable[[Event], Awaitable[None]] | None = None
        self._batcher = TokenBatcher(flush_interval=0.05)
        self._seq_counters: dict[str, int] = {}
        self._p2_queue: dict[str, list[Event]] = {}  # per-run

    def set_send_callback(self, callback: Callable[[Event], Awaitable[None]]) -> None:
        self._send_callback = callback

    def start_batcher(self) -> None:
        self._batcher.start(self._flush_batch)

    async def _flush_batch(self, items: list[Event]) -> None:
        if self._send_callback is not None:
            for event in items:
                await self._send_callback(event)

    async def emit(self, event: Event) -> None:
        run_id = event.run_id
        if run_id not in self._seq_counters:
            max_seq = await self.store.get_max_seq(run_id)
            self._seq_counters[run_id] = max_seq + 1
        event.seq = self._seq_counters[run_id]
        self._seq_counters[run_id] += 1

        if event.type not in _NO_PERSIST_TYPES:
            await self.store.append_event(event)

        if event.type in _P0_TYPES:
            if self._send_callback is not None:
                await self._send_callback(event)
        elif event.type in _P1_TYPES:
            self._batcher.add(event)
        else:
            self._p2_queue.setdefault(event.run_id, []).append(event)

    async def flush_node_boundary(self, run_id: str) -> None:
        events = self._p2_queue.pop(run_id, [])
        if self._send_callback is not None:
            for event in events:
                await self._send_callback(event)

    async def replay(self, run_id: str, after_seq: int = 0) -> list[Event]:
        return await self.store.replay_events(run_id, after_seq=after_seq)

    async def get_snapshot(self, run_id: str) -> dict:
        """Build snapshot from durable store state. Works after restart."""
        last_seq = await self.store.get_max_seq(run_id)
        run = await self.store.get_run(run_id)
        pending = await self.store.get_edits(run_id, status="proposed") if run else []
        return {
            "type": "snapshot",
            "run_id": run_id,
            "status": run.status if run else "unknown",
            "last_seq": last_seq,
            "active_node": None,
            "current_step": 0,
            "total_steps": 0,
            "pending_approvals": [e.id for e in pending],
            "current_branch": run.branch if run else None,
            "autonomy_mode": "supervised",
        }

    async def shutdown(self) -> None:
        await self._batcher.stop()
