"""Approval state machine for edit lifecycle management.

Idempotency note (V1): last_op_id provides last-operation-only idempotency.
This is sufficient for single-writer / low-concurrency V1. It does NOT provide
a full operation history or distinguish duplicate retries from racing actors.
"""
from __future__ import annotations
from datetime import datetime, timezone
from store.models import EditRecord, Event
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from store.protocol import SessionStore
    from agent.events import EventBus


class InvalidTransitionError(Exception):
    pass


_TRANSITIONS: dict[str, list[str]] = {
    "proposed": ["approved", "rejected"],
    "approved": ["applied"],
    "applied": ["committed"],
    "rejected": [],
    "committed": [],
}


class ApprovalManager:
    def __init__(self, store: SessionStore, event_bus: EventBus):
        self.store = store
        self.event_bus = event_bus

    def is_valid_transition(self, current: str, target: str) -> bool:
        return target in _TRANSITIONS.get(current, [])

    async def _resolve_project_id(self, run_id: str) -> str:
        """Look up project_id from the Run via store."""
        run = await self.store.get_run(run_id)
        return run.project_id if run else ""

    async def propose_edit(self, run_id: str, edit: EditRecord) -> EditRecord:
        edit.status = "proposed"
        edit.run_id = run_id
        created = await self.store.create_edit(edit)
        project_id = await self._resolve_project_id(run_id)
        await self.event_bus.emit(Event(
            project_id=project_id,
            run_id=run_id,
            type="approval",
            data={"event": "edit.proposed", "edit_id": created.id, "file_path": created.file_path},
        ))
        return created

    async def approve(self, edit_id: str, op_id: str) -> EditRecord:
        """Transition proposed → approved only. Does NOT apply."""
        edit = await self.store.get_edit(edit_id)
        if edit is None:
            raise ValueError(f"Edit {edit_id} not found")
        if edit.last_op_id == op_id:
            return edit  # idempotent no-op
        if not self.is_valid_transition(edit.status, "approved"):
            raise InvalidTransitionError(
                f"Cannot transition from '{edit.status}' to 'approved' for edit {edit_id}"
            )

        await self.store.update_edit_status(edit_id, "approved", last_op_id=op_id)
        edit = await self.store.get_edit(edit_id)

        project_id = await self._resolve_project_id(edit.run_id)
        await self.event_bus.emit(Event(
            project_id=project_id,
            run_id=edit.run_id,
            type="approval",
            data={"event": "edit.approved", "edit_id": edit_id, "status": "approved"},
        ))
        return edit

    async def reject(self, edit_id: str, op_id: str) -> EditRecord:
        """Transition proposed → rejected."""
        edit = await self.store.get_edit(edit_id)
        if edit is None:
            raise ValueError(f"Edit {edit_id} not found")
        if edit.last_op_id == op_id:
            return edit
        if not self.is_valid_transition(edit.status, "rejected"):
            raise InvalidTransitionError(
                f"Cannot transition from '{edit.status}' to 'rejected' for edit {edit_id}"
            )

        await self.store.update_edit_status(edit_id, "rejected", last_op_id=op_id)
        edit = await self.store.get_edit(edit_id)

        project_id = await self._resolve_project_id(edit.run_id)
        await self.event_bus.emit(Event(
            project_id=project_id,
            run_id=edit.run_id,
            type="approval",
            data={"event": "edit.rejected", "edit_id": edit_id, "status": "rejected"},
        ))
        return edit

    async def apply_edit(self, edit_id: str) -> EditRecord:
        """Transition approved → applied. Writes edit to filesystem.

        File write happens BEFORE status transition — if write fails, status stays approved.
        """
        edit = await self.store.get_edit(edit_id)
        if edit is None:
            raise ValueError(f"Edit {edit_id} not found")
        if not self.is_valid_transition(edit.status, "applied"):
            raise InvalidTransitionError(
                f"Cannot transition from '{edit.status}' to 'applied' for edit {edit_id}"
            )

        # Write to filesystem FIRST
        self._write_edit_to_file(edit)

        op_id = f"op_{edit_id}_apply"
        await self.store.update_edit_status(edit_id, "applied", last_op_id=op_id)
        edit = await self.store.get_edit(edit_id)

        project_id = await self._resolve_project_id(edit.run_id)
        await self.event_bus.emit(Event(
            project_id=project_id,
            run_id=edit.run_id,
            type="approval",
            data={"event": "edit.applied", "edit_id": edit_id, "file_path": edit.file_path, "status": "applied"},
        ))
        return edit

    @staticmethod
    def _write_edit_to_file(edit: EditRecord) -> None:
        """Apply edit to filesystem. Raises OSError on failure."""
        with open(edit.file_path, "r") as f:
            content = f.read()
        if edit.old_content is not None and edit.old_content in content:
            content = content.replace(edit.old_content, edit.new_content or "", 1)
        elif edit.new_content is not None:
            content = edit.new_content
        with open(edit.file_path, "w") as f:
            f.write(content)

    async def mark_committed(self, run_id: str, edit_ids: list[str]) -> None:
        """Transition applied → committed. Only emits for actually transitioned edits."""
        transitioned = []
        for edit_id in edit_ids:
            edit = await self.store.get_edit(edit_id)
            if edit and edit.status == "applied":
                await self.store.update_edit_status(edit_id, "committed", last_op_id=f"op_{edit_id}_commit")
                transitioned.append(edit_id)
        if transitioned:
            project_id = await self._resolve_project_id(run_id)
            await self.event_bus.emit(Event(
                project_id=project_id,
                run_id=run_id,
                type="approval",
                data={"event": "edit.committed", "edit_ids": transitioned},
            ))

    async def auto_approve_pending(self, run_id: str) -> list[EditRecord]:
        """Auto-approve all proposed edits. Does NOT auto-apply."""
        pending = await self.get_pending(run_id)
        approved = []
        for edit in pending:
            op_id = f"op_{edit.id}_approve"
            result = await self.approve(edit.id, op_id)
            approved.append(result)
        return approved

    async def get_pending(self, run_id: str) -> list[EditRecord]:
        """Get all edits with status == 'proposed' for a run."""
        return await self.store.get_edits(run_id, status="proposed")
