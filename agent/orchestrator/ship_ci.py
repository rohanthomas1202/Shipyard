"""Ship-specific CI pipeline for Express/React/Prisma apps."""
from agent.orchestrator.ci_runner import CIStage

SHIP_CI_PIPELINE: list[CIStage] = [
    CIStage("typecheck", ["npx", "tsc", "--noEmit"], timeout=60),
    CIStage("lint", ["npx", "eslint", "src/", "--max-warnings=0"], timeout=60),
    CIStage("test", ["npm", "test", "--", "--watchAll=false"], timeout=180),
    CIStage("build", ["npm", "run", "build"], timeout=120),
]
