"""Hybrid regex + LLM failure classification with tiered retry budgets."""
import re
from typing import Any, Literal

FailureCategory = Literal["syntax", "test", "contract", "structural"]

_PATTERNS: list[tuple[str, FailureCategory]] = [
    # Syntax errors
    (r"SyntaxError:", "syntax"),
    (r"IndentationError:", "syntax"),
    (r"TabError:", "syntax"),
    (r"TS\d+:", "syntax"),
    (r"error TS\d+", "syntax"),
    (r"Unexpected token", "syntax"),
    (r"unterminated string", "syntax"),
    # Test failures
    (r"FAILED tests/", "test"),
    (r"AssertionError", "test"),
    (r"pytest.*\d+ failed", "test"),
    (r"FAIL\s+.*\.test\.", "test"),
    (r"expected .* to equal", "test"),
    # Contract violations
    (r"ImportError:", "contract"),
    (r"ModuleNotFoundError:", "contract"),
    (r"Cannot find module", "contract"),
    (r"is not assignable to type", "contract"),
    (r"Property .* does not exist on type", "contract"),
    # Structural
    (r"RecursionError:", "structural"),
    (r"maximum call stack", "structural"),
    (r"circular dependency", "structural"),
]

RETRY_BUDGETS: dict[str, int] = {
    "syntax": 3,
    "test": 2,
    "contract": 1,
    "structural": 1,
}

RETRY_STRATEGIES: dict[str, str] = {
    "syntax": "auto_fix",
    "test": "debug",
    "contract": "spec_update",
    "structural": "replan",
}

_VALID_CATEGORIES = {"syntax", "test", "contract", "structural"}

_CLASSIFY_SYSTEM_PROMPT = (
    "Classify the following error output into exactly one category: "
    "syntax, test, contract, or structural. "
    "Respond with only the category name, nothing else."
)


def classify_regex(error_output: str) -> FailureCategory | None:
    """Return the first matching failure category, or None if unrecognized."""
    for pattern, category in _PATTERNS:
        if re.search(pattern, error_output, re.IGNORECASE):
            return category
    return None


class FailureClassifier:
    """Classifies CI failures via regex patterns first, LLM fallback second."""

    def __init__(self, router: Any | None = None):
        self._router = router

    async def classify(self, error_output: str) -> FailureCategory:
        """Classify error output into a failure category."""
        result = classify_regex(error_output)
        if result is not None:
            return result

        if self._router is not None:
            try:
                llm_response = await self._router.call(
                    "classify_error",
                    _CLASSIFY_SYSTEM_PROMPT,
                    error_output[:2000],
                )
                cleaned = llm_response.strip().lower()
                if cleaned in _VALID_CATEGORIES:
                    return cleaned  # type: ignore[return-value]
            except Exception:
                pass

        return "structural"

    def get_retry_budget(self, category: FailureCategory) -> int:
        """Return the retry budget for a failure category."""
        return RETRY_BUDGETS[category]

    def get_retry_strategy(self, category: FailureCategory) -> str:
        """Return the retry strategy for a failure category."""
        return RETRY_STRATEGIES[category]
