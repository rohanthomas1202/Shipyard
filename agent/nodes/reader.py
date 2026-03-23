import os
from agent.tools.file_ops import read_file
from agent.tracing import TraceLogger

tracer = TraceLogger()

def reader_node(state: dict) -> dict:
    plan = state.get("plan", [])
    step = state.get("current_step", 0)
    working_dir = state["working_directory"]
    file_buffer = dict(state.get("file_buffer", {}))

    files_to_read = []
    context = state.get("context", {})
    if context.get("files"):
        files_to_read.extend(context["files"])

    if step < len(plan):
        step_text = plan[step]
        for word in step_text.split():
            word = word.strip("'\"`,")
            if "/" in word and "." in word.split("/")[-1]:
                full_path = os.path.join(working_dir, word) if not os.path.isabs(word) else word
                if os.path.exists(full_path):
                    files_to_read.append(full_path)

    for fpath in files_to_read:
        if not os.path.isabs(fpath):
            fpath = os.path.join(working_dir, fpath)
        if os.path.exists(fpath):
            with open(fpath, "r") as f:
                file_buffer[fpath] = f.read()
            tracer.log("reader", {"file": fpath, "lines": file_buffer[fpath].count("\n") + 1})

    return {"file_buffer": file_buffer}
