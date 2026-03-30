"""Automated Railway deployment for rebuilt Ship app.

Per D-06: Fully automated -- provisions DB/secrets, deploys, verifies health.
Per D-07: Secrets managed through Railway environment variables.
"""

import argparse
import asyncio
import logging
import os
import sys
import time

# Ensure project root is on sys.path so `agent.*` imports resolve
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import httpx

from agent.tools.shell import run_command_async

logger = logging.getLogger(__name__)

HEALTH_CHECK_TIMEOUT = 300  # 5 minutes
HEALTH_CHECK_INTERVAL = 10  # seconds
DEFAULT_ENV_TEMPLATE = "scripts/railway_template.env"


async def check_auth() -> None:
    """Verify Railway CLI is authenticated."""
    result = await run_command_async(["railway", "whoami"], timeout=10)
    if result["exit_code"] != 0:
        raise RuntimeError(
            "Railway CLI not authenticated. Run 'railway login' first."
        )
    logger.info("Railway authenticated as: %s", result["stdout"].strip())


async def init_project(project_dir: str) -> None:
    """Initialize or link a Railway project."""
    result = await run_command_async(
        ["railway", "init"], cwd=project_dir, timeout=30
    )
    if result["exit_code"] != 0 and "already linked" not in result["stderr"]:
        raise RuntimeError(f"Railway init failed: {result['stderr']}")
    logger.info("Railway project initialized in %s", project_dir)


async def provision_postgres(project_dir: str) -> None:
    """Add PostgreSQL addon to Railway project."""
    result = await run_command_async(
        ["railway", "add", "--plugin", "postgresql"],
        cwd=project_dir,
        timeout=60,
    )
    if result["exit_code"] != 0:
        logger.warning(
            "Postgres addon may already exist: %s", result["stderr"]
        )
    else:
        logger.info("Postgres addon provisioned")


async def set_env_vars(project_dir: str, env_template: str) -> int:
    """Set Railway environment variables from template file."""
    with open(env_template) as f:
        lines = f.readlines()

    count = 0
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key = line.split("=", 1)[0]
        await run_command_async(
            ["railway", "variable", "set", line],
            cwd=project_dir,
            timeout=15,
        )
        count += 1
        logger.info("Set variable: %s", key)

    logger.info("Set %d environment variables", count)
    return count


async def deploy(project_dir: str) -> None:
    """Deploy the project to Railway."""
    result = await run_command_async(
        ["railway", "up", "--detach", "--ci"],
        cwd=project_dir,
        timeout=300,
    )
    if result["exit_code"] != 0:
        raise RuntimeError(f"Deploy failed: {result['stderr']}")
    logger.info("Deploy initiated")


async def generate_domain(project_dir: str) -> str:
    """Generate a public Railway domain."""
    result = await run_command_async(
        ["railway", "domain"], cwd=project_dir, timeout=30
    )
    domain = result["stdout"].strip()
    if not domain:
        raise RuntimeError("Failed to generate Railway domain")
    logger.info("Public domain: %s", domain)
    return domain


async def verify_health(url: str) -> bool:
    """Poll health endpoint until success or timeout."""
    deadline = time.monotonic() + HEALTH_CHECK_TIMEOUT
    while time.monotonic() < deadline:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://{url}/health", timeout=10
                )
                if resp.status_code == 200:
                    logger.info("Health check passed")
                    return True
        except Exception:
            pass
        logger.info(
            "Health check pending... retrying in %ds", HEALTH_CHECK_INTERVAL
        )
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)
    return False


async def run_deploy(project_dir: str, env_template: str) -> str:
    """Execute full Railway deployment pipeline."""
    print("Deploying rebuilt Ship to Railway...")
    await check_auth()
    await init_project(project_dir)
    await provision_postgres(project_dir)
    count = await set_env_vars(project_dir, env_template)
    logger.info("Provisioned %d env vars", count)
    await deploy(project_dir)
    domain = await generate_domain(project_dir)
    print(f"Verifying health at https://{domain}/health ...")
    healthy = await verify_health(domain)
    if healthy:
        print(f"Ship deployed successfully: https://{domain}")
        return domain
    raise RuntimeError(
        f"Deployed but health check failed after 5 minutes: {domain}"
    )


def main() -> None:
    """CLI entry point for Railway deployment."""
    parser = argparse.ArgumentParser(
        description="Deploy rebuilt Ship app to Railway"
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Path to rebuilt Ship project directory",
    )
    parser.add_argument(
        "--env-template",
        default=DEFAULT_ENV_TEMPLATE,
        help="Path to Railway env template",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING"],
        help="Logging level",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    try:
        domain = asyncio.run(run_deploy(args.project_dir, args.env_template))
        print(f"Final domain: {domain}")
        sys.exit(0)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
