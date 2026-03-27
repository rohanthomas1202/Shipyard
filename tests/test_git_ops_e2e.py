"""Integration tests for automatic git_ops triggering after reporter."""
import os
import pytest
import pytest_asyncio
from agent.graph import after_reporter, classify_step, build_graph
from agent.nodes.git_ops import git_ops_node
from agent.tools.shell import run_command_async


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def git_repo(tmp_path):
    """Create a temp git repo with an initial commit."""
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    await run_command_async(["git", "init"], cwd=repo)
    await run_command_async(["git", "config", "user.email", "test@test.com"], cwd=repo)
    await run_command_async(["git", "config", "user.name", "Test"], cwd=repo)
    with open(os.path.join(repo, "README.md"), "w") as f:
        f.write("# Test\n")
    await run_command_async(["git", "add", "."], cwd=repo)
    await run_command_async(["git", "commit", "-m", "initial"], cwd=repo)
    return repo


# ---------------------------------------------------------------------------
# Test 1: after_reporter routes to auto_git when edits exist
# ---------------------------------------------------------------------------

def test_git_ops_runs_after_reporter_when_edits_exist():
    state = {
        "edit_history": [
            {"file": "src/app.ts", "anchor": "old", "replacement": "new"}
        ],
    }
    result = after_reporter(state)
    assert result == "auto_git"


# ---------------------------------------------------------------------------
# Test 2: after_reporter routes to end when no edits
# ---------------------------------------------------------------------------

def test_git_ops_skipped_when_no_edits():
    state = {"edit_history": []}
    result = after_reporter(state)
    assert result == "end"

    # Also test missing key
    result2 = after_reporter({})
    assert result2 == "end"


# ---------------------------------------------------------------------------
# Test 3: plan-step git routes to git_ops (which goes to advance)
# ---------------------------------------------------------------------------

def test_git_ops_plan_step_routes_to_git_ops():
    state = {
        "plan": [{"kind": "git", "instruction": "commit changes"}],
        "current_step": 0,
    }
    result = classify_step(state)
    assert result == "git_ops"


def test_graph_has_git_ops_to_advance_edge():
    """Verify the compiled graph has git_ops -> advance edge (not git_ops -> reporter)."""
    graph = build_graph()
    graph_data = graph.get_graph()
    node_names = set(graph_data.nodes.keys())
    assert "git_ops" in node_names
    assert "auto_git" in node_names

    # Check edges: git_ops should connect to advance
    git_ops_targets = set()
    for edge in graph_data.edges:
        if edge.source == "git_ops":
            git_ops_targets.add(edge.target)
    assert "advance" in git_ops_targets, f"git_ops targets: {git_ops_targets}"

    # Check edges: auto_git should connect to __end__
    auto_git_targets = set()
    for edge in graph_data.edges:
        if edge.source == "auto_git":
            auto_git_targets.add(edge.target)
    assert "__end__" in auto_git_targets, f"auto_git targets: {auto_git_targets}"


# ---------------------------------------------------------------------------
# Test 4: git_ops_node resolves project_id from state context
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_git_ops_node_resolves_project_id_from_context(git_repo):
    """git_ops_node should work when project_id is in state context, not config."""
    # Create a file to edit
    target = os.path.join(git_repo, "app.ts")
    with open(target, "w") as f:
        f.write("console.log('hello');")

    state = {
        "working_directory": git_repo,
        "instruction": "add logging",
        "edit_history": [{"file": "app.ts", "anchor": "old", "replacement": "new"}],
        "context": {"project_id": "my-test-project"},
    }
    # Config has NO project_id -- should fall back to state context
    config = {"configurable": {"run_id": "run-123"}}

    result = await git_ops_node(state, config)
    assert result.get("error_state") is None
    assert "branch" in result
    assert "my-test-project" in result["branch"]


@pytest.mark.asyncio
async def test_git_ops_node_skips_when_no_edits(git_repo):
    """git_ops_node should return cleanly when edit_history is empty."""
    state = {
        "working_directory": git_repo,
        "instruction": "nothing",
        "edit_history": [],
        "context": {},
    }
    result = await git_ops_node(state)
    assert result.get("error_state") is None
