"""Register the ship-rebuild directory as a Shipyard project.

Creates a project entry via the Shipyard REST API so the agent can accept
instructions targeting the ship-rebuild/ workspace.  After creation the
script PUTs configuration (build/test/lint commands, autonomy mode) so
the rebuild can run without approval gates.

Usage:
    python scripts/register_ship_project.py              # register against localhost:8000
    python scripts/register_ship_project.py --dry-run    # print payloads without sending
    python scripts/register_ship_project.py --host 0.0.0.0:9000
"""

import argparse
import json
import os
import sys

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]


def _ship_rebuild_path() -> str:
    """Return the absolute path to ship-rebuild/ relative to the repo root."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(repo_root, "ship-rebuild")


def _create_payload() -> dict:
    return {
        "name": "Ship",
        "path": _ship_rebuild_path(),
    }


def _update_payload() -> dict:
    return {
        "test_command": "pnpm test",
        "build_command": "pnpm build",
        "lint_command": "pnpm lint",
        "autonomy_mode": "autonomous",
        "default_model": "gpt-4o",
    }


def _dry_run() -> None:
    """Print the request bodies without sending any HTTP requests."""
    create = _create_payload()
    update = _update_payload()
    print("POST /projects")
    print(json.dumps(create, indent=2))
    print()
    print("PUT /projects/{project_id}")
    print(json.dumps(update, indent=2))


def _register(host: str) -> None:
    """Register the project and configure it via the Shipyard API."""
    if httpx is None:
        print("ERROR: httpx is required. Install with: pip install httpx", file=sys.stderr)
        sys.exit(1)

    base = f"http://{host}"
    create = _create_payload()

    print(f"Creating project at {base}/projects ...")
    resp = httpx.post(f"{base}/projects", json=create, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    project_id = data["id"]
    print(f"Created project: {project_id}")

    update = _update_payload()
    print(f"Updating project config at {base}/projects/{project_id} ...")
    resp = httpx.put(f"{base}/projects/{project_id}", json=update, timeout=10)
    resp.raise_for_status()
    print("Project configured successfully.")

    # Print project_id for downstream scripts
    print(f"\nproject_id={project_id}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Register ship-rebuild as a Shipyard project"
    )
    parser.add_argument(
        "--host",
        default="localhost:8000",
        help="Shipyard API host:port (default: localhost:8000)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print request bodies without sending HTTP requests",
    )
    args = parser.parse_args()

    if args.dry_run:
        _dry_run()
    else:
        _register(args.host)


if __name__ == "__main__":
    main()
