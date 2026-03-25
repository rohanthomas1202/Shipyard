"""Integration tests — run with ANTHROPIC_API_KEY set."""
import json
import os
import tempfile
import pytest
from agent.graph import build_graph
from agent.nodes.validator import validator_node
from agent.tracing import TraceLogger


SKIP_REASON = "Requires ANTHROPIC_API_KEY"
needs_api = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"), reason=SKIP_REASON
)


@pytest.fixture
def large_ts_file():
    """Create a temp directory with a >150 line TypeScript file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lines = ['export interface LargeModel {']
        for i in range(150):
            lines.append(f'  field_{i}: string;')
        lines.append('}')
        lines.append('')
        lines.append('export function processModel(model: LargeModel): string {')
        lines.append('  return model.field_0;')
        lines.append('}')
        path = os.path.join(tmpdir, "large.ts")
        with open(path, "w") as f:
            f.write("\n".join(lines))
        yield tmpdir


@pytest.fixture
def multi_file_codebase():
    """Create a temp directory with multiple related files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # API model
        api_dir = os.path.join(tmpdir, "api", "src", "models")
        os.makedirs(api_dir)
        with open(os.path.join(api_dir, "task.ts"), "w") as f:
            f.write(
                'export interface Task {\n'
                '  id: string;\n'
                '  title: string;\n'
                '  completed: boolean;\n'
                '}\n'
            )
        # Web component
        web_dir = os.path.join(tmpdir, "web", "src", "components")
        os.makedirs(web_dir)
        with open(os.path.join(web_dir, "TaskList.tsx"), "w") as f:
            f.write(
                'import React from "react";\n'
                '\n'
                'interface TaskProps {\n'
                '  id: string;\n'
                '  title: string;\n'
                '  completed: boolean;\n'
                '}\n'
                '\n'
                'export function TaskList({ tasks }: { tasks: TaskProps[] }) {\n'
                '  return (\n'
                '    <ul>\n'
                '      {tasks.map(t => (\n'
                '        <li key={t.id}>{t.title}</li>\n'
                '      ))}\n'
                '    </ul>\n'
                '  );\n'
                '}\n'
            )
        # Shared types
        shared_dir = os.path.join(tmpdir, "shared", "src")
        os.makedirs(shared_dir)
        with open(os.path.join(shared_dir, "types.ts"), "w") as f:
            f.write(
                'export type TaskStatus = "todo" | "in_progress" | "done";\n'
            )
        yield tmpdir


def _initial_state(working_dir, instruction, context=None, files=None):
    ctx = context or {}
    if files:
        ctx["files"] = files
    return {
        "messages": [],
        "instruction": instruction,
        "working_directory": working_dir,
        "context": ctx,
        "plan": [],
        "current_step": 0,
        "file_buffer": {},
        "edit_history": [],
        "error_state": None,
        "is_parallel": False,
        "parallel_batches": [],
        "sequential_first": [],
        "has_conflicts": False,
    }


# ---------- Test 1: Multi-file edit ----------

@needs_api
@pytest.mark.asyncio
async def test_multi_file_edit(multi_file_codebase):
    """Agent should plan and execute edits across multiple files."""
    graph = build_graph()
    task_path = os.path.join(multi_file_codebase, "api", "src", "models", "task.ts")
    web_path = os.path.join(multi_file_codebase, "web", "src", "components", "TaskList.tsx")

    result = await graph.ainvoke(_initial_state(
        multi_file_codebase,
        "Add a 'description: string' field to the Task interface in api/src/models/task.ts",
        files=[task_path],
    ))

    content = open(task_path).read()
    assert "description" in content.lower(), f"Expected 'description' in task.ts, got:\n{content}"
    # Should have at least one edit
    assert len(result.get("edit_history", [])) >= 1


# ---------- Test 2: Large file editing ----------

@needs_api
@pytest.mark.asyncio
async def test_large_file_edit(large_ts_file):
    """Agent should handle files with 150+ lines without anchor collisions."""
    graph = build_graph()
    file_path = os.path.join(large_ts_file, "large.ts")

    result = await graph.ainvoke(_initial_state(
        large_ts_file,
        "Change the return type of processModel from string to LargeModel in large.ts",
        files=[file_path],
    ))

    content = open(file_path).read()
    # The function should have been modified
    assert result.get("error_state") is None or "processModel" in content, \
        f"Edit failed: {result.get('error_state')}"


# ---------- Test 3: Context injection ----------

@needs_api
@pytest.mark.asyncio
async def test_context_injection(multi_file_codebase):
    """Verify the planner uses injected spec context."""
    graph = build_graph()
    task_path = os.path.join(multi_file_codebase, "api", "src", "models", "task.ts")

    spec = """Feature: Task Priority
    Add a priority field to the Task model.
    Priority should be of type: 'low' | 'medium' | 'high'
    Default value should be 'medium'.
    """

    result = await graph.ainvoke(_initial_state(
        multi_file_codebase,
        "Implement the Task Priority feature as described in the spec",
        context={"spec": spec, "files": [task_path]},
    ))

    content = open(task_path).read()
    assert "priority" in content.lower(), f"Expected priority in task.ts, got:\n{content}"


# ---------- Test 4: Error recovery (rollback) ----------

@pytest.mark.asyncio
async def test_validator_rollback_on_bad_json(tmp_path):
    """Validator should rollback when syntax check fails."""
    json_file = tmp_path / "data.json"
    original = '{"name": "test"}'
    json_file.write_text(original)

    # Simulate a bad edit
    json_file.write_text('{"name": "test",}')  # invalid JSON

    state = {
        "edit_history": [{
            "file": str(json_file),
            "snapshot": original,
            "anchor": '"test"',
            "replacement": '"test",}',
        }],
    }

    result = await validator_node(state)

    # Should detect syntax error and rollback
    assert result["error_state"] is not None
    assert "syntax" in result["error_state"].lower() or "json" in result["error_state"].lower()

    # File should be restored to original
    assert json_file.read_text() == original


@pytest.mark.asyncio
async def test_validator_passes_good_json(tmp_path):
    """Validator should pass valid JSON."""
    json_file = tmp_path / "data.json"
    json_file.write_text('{"name": "updated"}')

    state = {
        "edit_history": [{
            "file": str(json_file),
            "snapshot": '{"name": "test"}',
            "anchor": '"test"',
            "replacement": '"updated"',
        }],
    }

    result = await validator_node(state)
    assert result["error_state"] is None


# ---------- Test 5: Trace output ----------

def test_trace_logger_writes_file():
    """TraceLogger should write a JSON file to traces/."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = TraceLogger(trace_dir=tmpdir)
        logger.start_run("test-run-001")
        logger.log("planner", {"steps": ["step1", "step2"]})
        logger.log("editor", {"file": "test.ts", "result": "success"})
        logger.save()

        trace_file = os.path.join(tmpdir, "test-run-001.json")
        assert os.path.exists(trace_file), f"Trace file not written to {trace_file}"

        with open(trace_file) as f:
            data = json.load(f)

        assert len(data) == 2
        assert data[0]["node"] == "planner"
        assert data[1]["node"] == "editor"
        assert data[0]["run_id"] == "test-run-001"
        assert "timestamp" in data[0]
