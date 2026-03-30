"""End-to-end Ship rebuild orchestration script.

Chains: clone -> analyze -> plan -> execute via the Phases 12-15 pipeline.
Per D-03: Full analyze-then-execute pipeline.
Per D-04: Output is a fresh git repo (clean slate).
"""
import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path when running as a script
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from agent.analyzer.analyzer import analyze_codebase
from agent.planner_v2.pipeline import run_pipeline
from agent.planner_v2.dag_builder import build_orchestrator_dag
from agent.orchestrator.scheduler import DAGScheduler
from agent.orchestrator.models import DAGRun
from agent.orchestrator.branch_manager import BranchManager
from agent.orchestrator.ci_runner import CIRunner
from agent.orchestrator.failure_classifier import FailureClassifier
from agent.orchestrator.context_packs import ContextPackAssembler
from agent.orchestrator.ownership import OwnershipValidator, build_ownership_map
from agent.orchestrator.ship_executor import build_agent_executor
from agent.orchestrator.ship_ci import SHIP_CI_PIPELINE
from agent.router import ModelRouter
from agent.tools.shell import run_command_async

DEFAULT_SHIP_REPO = "https://github.com/gauntlet-ai/ship.git"
DEFAULT_OUTPUT_DIR = "/tmp/ship-rebuilt"
DEFAULT_CLONE_DIR = "/tmp/ship-source"
DEFAULT_MAX_CONCURRENCY = 10

logger = logging.getLogger(__name__)


async def verify_repo_url(repo_url: str) -> None:
    """Fail fast if the Ship repo URL is unreachable."""
    result = await run_command_async(
        ["git", "ls-remote", "--exit-code", repo_url, "HEAD"], timeout=30
    )
    if result["exit_code"] != 0:
        raise RuntimeError(
            f"Ship repo URL is unreachable: {repo_url}. "
            "Verify the URL exists and you have access."
        )
    logger.info("Repo URL verified: %s", repo_url)


async def clone_repo(repo_url: str, clone_dir: str) -> None:
    """Clone the Ship repo (shallow) into clone_dir."""
    if os.path.isdir(clone_dir):
        logger.info("Clone dir exists, reusing: %s", clone_dir)
        return
    result = await run_command_async(
        ["git", "clone", "--depth=1", repo_url, clone_dir], timeout=120
    )
    if result["exit_code"] != 0:
        raise RuntimeError(
            f"git clone failed: {result['stderr']}"
        )
    logger.info("Cloned %s -> %s", repo_url, clone_dir)


async def init_output_repo(output_dir: str) -> None:
    """Initialize a fresh git repo in output_dir with an empty initial commit."""
    os.makedirs(output_dir, exist_ok=True)
    await run_command_async(["git", "init"], cwd=output_dir)
    await run_command_async(
        ["git", "commit", "--allow-empty", "-m", "Initial commit"],
        cwd=output_dir,
    )
    logger.info("Initialized fresh output repo: %s", output_dir)


async def install_dependencies(output_dir: str) -> None:
    """Run npm install in the output directory (mandatory, no escape hatch)."""
    if not os.path.isfile(os.path.join(output_dir, "package.json")):
        raise RuntimeError(
            f"No package.json found in {output_dir} -- "
            "rebuild may have failed to generate it"
        )
    result = await run_command_async(
        ["npm", "install"], cwd=output_dir, timeout=120
    )
    if result["exit_code"] != 0:
        raise RuntimeError(
            f"npm install failed in {output_dir}: {result['stderr']}"
        )
    logger.info("npm install completed in %s", output_dir)


async def run_rebuild(
    repo_url: str,
    clone_dir: str,
    output_dir: str,
    max_concurrency: int,
) -> dict[str, str]:
    """Execute the full Ship rebuild pipeline: clone -> analyze -> plan -> execute."""
    print("Starting Ship rebuild: clone -> analyze -> plan -> execute")

    # Fail fast if repo URL is bad
    await verify_repo_url(repo_url)

    await clone_repo(repo_url, clone_dir)
    await init_output_repo(output_dir)

    router = ModelRouter()

    # Phase 12: Analyze
    print("Analyzing Ship codebase...")
    logger.info("Analyzing Ship codebase...")
    module_map = await analyze_codebase(clone_dir, router)
    logger.info("Analyzed %d modules", len(module_map.modules))

    # Phase 13: Plan
    print("Generating task DAG...")
    logger.info("Generating task DAG...")
    pipeline_result = await run_pipeline(module_map, router)
    logger.info("Generated %d tasks", len(pipeline_result.dag.tasks))
    print(f"Estimated tokens: {pipeline_result.estimated_total_tokens:,}")
    for w in pipeline_result.validation_warnings:
        logger.warning("Plan warning: %s", w)

    # Phase 14+15: Execute
    dag = build_orchestrator_dag(pipeline_result.dag, dag_id="ship-rebuild")
    dag_run = DAGRun(
        id="ship-rebuild",
        project_id="ship",
        total_tasks=dag.task_count,
    )

    task_nodes = [
        dag.get_task(tid)
        for tid in dag._graph.nodes
        if dag.get_task(tid)
    ]
    ownership_map = build_ownership_map(task_nodes)

    scheduler = DAGScheduler(
        dag,
        dag_run,
        task_executor=build_agent_executor(output_dir, router),
        max_concurrency=max_concurrency,
        project_path=output_dir,
        branch_manager=BranchManager(output_dir),
        ci_runner=CIRunner(output_dir, pipeline=SHIP_CI_PIPELINE),
        failure_classifier=FailureClassifier(router),
        context_assembler=ContextPackAssembler(output_dir),
        ownership_validator=OwnershipValidator(output_dir, ownership_map),
    )

    results = await scheduler.run()

    # Mandatory npm install after rebuild
    await install_dependencies(output_dir)

    # Summary
    completed = sum(1 for s in results.values() if s == "completed")
    failed = sum(1 for s in results.values() if s == "failed")
    skipped = sum(
        1 for s in results.values() if s not in ("completed", "failed")
    )
    print(
        f"Rebuild complete: {completed}/{dag.task_count} tasks succeeded, "
        f"{failed} failed"
    )
    if skipped:
        print(f"  ({skipped} skipped)")

    return results


def main() -> None:
    """CLI entry point for the Ship rebuild script."""
    parser = argparse.ArgumentParser(
        description="Rebuild the Ship app from scratch using the Shipyard agent pipeline."
    )
    parser.add_argument(
        "--repo-url",
        default=DEFAULT_SHIP_REPO,
        help=f"Ship GitHub repo URL (default: {DEFAULT_SHIP_REPO})",
    )
    parser.add_argument(
        "--clone-dir",
        default=DEFAULT_CLONE_DIR,
        help=f"Directory to clone Ship source into (default: {DEFAULT_CLONE_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for the rebuilt Ship app (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--max-concurrency",
        default=DEFAULT_MAX_CONCURRENCY,
        type=int,
        help=f"Maximum concurrent agent tasks (default: {DEFAULT_MAX_CONCURRENCY})",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    results = asyncio.run(
        run_rebuild(args.repo_url, args.clone_dir, args.output_dir, args.max_concurrency)
    )

    sys.exit(0 if all(s == "completed" for s in results.values()) else 1)


if __name__ == "__main__":
    main()
