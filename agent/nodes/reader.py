"""Reader node: loads files into state with line-range and skeleton support."""
import os
from agent.node_events import emit_status, flush_node
from agent.tools.file_ops import read_file, content_hash
from agent.tracing import TraceLogger

tracer = TraceLogger()

_SKELETON_THRESHOLD = 200
_SKELETON_HEAD = 30
_SKELETON_TAIL = 10


def _read_with_range(file_path: str, start: int | None = None, end: int | None = None) -> str:
    """Read a file with optional line range. Large files get skeleton views.

    Args:
        file_path: Absolute path to the file.
        start: 0-indexed start line (inclusive). None for auto mode.
        end: 0-indexed end line (exclusive). None for auto mode.

    Returns:
        File content string, possibly truncated as skeleton or line range.
    """
    with open(file_path, "r") as f:
        lines = f.readlines()

    total = len(lines)

    # Explicit line range requested
    if start is not None and end is not None:
        actual_end = min(end, total)
        selected = lines[start:actual_end]
        prefix = f"[Lines {start + 1}-{actual_end} of {total}]\n"
        return prefix + "".join(selected)

    # Auto skeleton for large files
    if total > _SKELETON_THRESHOLD:
        omitted = total - _SKELETON_HEAD - _SKELETON_TAIL
        head = lines[:_SKELETON_HEAD]
        tail = lines[-_SKELETON_TAIL:]
        marker = f"\n... ({omitted} lines omitted) ...\n\n"
        prefix = f"[{total} lines total -- skeleton view]\n"
        return prefix + "".join(head) + marker + "".join(tail)

    # Small file: return in full
    return "".join(lines)


async def reader_node(state: dict, config: dict = None) -> dict:
    """Read files into file_buffer with skeleton/line-range support."""
    if config is None:
        config = {"configurable": {}}
    await emit_status(config, "reader", f"Reading files for step {state.get('current_step', 0) + 1}...")

    plan = state.get("plan", [])
    step = state.get("current_step", 0)
    working_dir = state["working_directory"]
    file_buffer = dict(state.get("file_buffer", {}))
    file_hashes = dict(state.get("file_hashes", {}))

    files_to_read = []
    line_ranges: dict[str, list[int]] = {}
    context = state.get("context", {})
    if context.get("files"):
        files_to_read.extend(context["files"])

    # Extract step entry (may be string or dict)
    step_entry = None
    step_line_range = None
    if step < len(plan):
        step_entry = plan[step]

    if isinstance(step_entry, dict):
        # Dict-style step: extract target_files and line_range
        for tf in step_entry.get("target_files", []):
            full = os.path.join(working_dir, tf) if not os.path.isabs(tf) else tf
            if os.path.exists(full):
                files_to_read.append(full)
        if step_entry.get("line_range") and len(step_entry["line_range"]) == 2:
            step_line_range = step_entry["line_range"]
            # Apply line_range to all target_files from this step
            for tf in step_entry.get("target_files", []):
                full = os.path.join(working_dir, tf) if not os.path.isabs(tf) else tf
                line_ranges[full] = step_line_range
    elif isinstance(step_entry, str):
        # String step: extract file paths from text
        for word in step_entry.split():
            word = word.strip("'\"`,")
            if "/" in word and "." in word.split("/")[-1]:
                full_path = os.path.join(working_dir, word) if not os.path.isabs(word) else word
                if os.path.exists(full_path):
                    files_to_read.append(full_path)

    for fpath in files_to_read:
        if not os.path.isabs(fpath):
            fpath = os.path.join(working_dir, fpath)
        if not os.path.exists(fpath):
            continue

        # Read full content for hashing
        with open(fpath, "r") as f:
            raw_content = f.read()
        file_hashes[fpath] = content_hash(raw_content)

        # Read with range/skeleton for the buffer
        lr = line_ranges.get(fpath)
        if lr:
            file_buffer[fpath] = _read_with_range(fpath, lr[0], lr[1])
        else:
            file_buffer[fpath] = _read_with_range(fpath)

        line_count = raw_content.count("\n") + 1
        tracer.log("reader", {"file": fpath, "lines": line_count})

    await flush_node(config)
    return {"file_buffer": file_buffer, "file_hashes": file_hashes}
