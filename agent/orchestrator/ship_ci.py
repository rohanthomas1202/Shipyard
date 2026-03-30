"""Ship-specific CI pipeline for Express/React/Prisma pnpm monorepo apps."""
from agent.orchestrator.ci_runner import CIStage

SHIP_CI_PIPELINE: list[CIStage] = [
    CIStage("typecheck", ["pnpm", "exec", "tsc", "--noEmit", "-p", "api/tsconfig.json"], timeout=120),
    CIStage("lint", ["pnpm", "exec", "eslint", "api/src/", "web/src/", "--max-warnings=0"], timeout=60),
    CIStage("test", ["pnpm", "run", "--filter", "api", "test", "--", "--watchAll=false"], timeout=180),
    CIStage("build", ["pnpm", "run", "--filter", "web", "build"], timeout=120),
]
