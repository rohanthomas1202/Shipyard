"""Tests for hybrid regex + LLM failure classification."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from agent.orchestrator.failure_classifier import (
    FailureClassifier,
    classify_regex,
    RETRY_BUDGETS,
    RETRY_STRATEGIES,
)


# ---------------------------------------------------------------------------
# classify_regex
# ---------------------------------------------------------------------------

def test_classify_regex_syntax_error():
    assert classify_regex("SyntaxError: invalid syntax") == "syntax"


def test_classify_regex_indentation_error():
    assert classify_regex("IndentationError: unexpected indent") == "syntax"


def test_classify_regex_ts_error():
    assert classify_regex("src/App.tsx(12,5): error TS2304: Cannot find name") == "syntax"


def test_classify_regex_test_failure():
    assert classify_regex("FAILED tests/test_foo.py::test_bar - AssertionError") == "test"


def test_classify_regex_pytest_summary():
    assert classify_regex("===== 2 failed, 3 passed in 1.2s =====\npytest 2 failed") == "test"


def test_classify_regex_import_error():
    assert classify_regex("ImportError: cannot import name 'Foo' from 'bar'") == "contract"


def test_classify_regex_module_not_found():
    assert classify_regex("ModuleNotFoundError: No module named 'baz'") == "contract"


def test_classify_regex_type_assignability():
    assert classify_regex("Type 'string' is not assignable to type 'number'") == "contract"


def test_classify_regex_recursion_error():
    assert classify_regex("RecursionError: maximum recursion depth exceeded") == "structural"


def test_classify_regex_circular_dependency():
    assert classify_regex("Error: circular dependency detected between A and B") == "structural"


def test_classify_regex_unrecognized():
    assert classify_regex("some random error message") is None


def test_classify_regex_empty_string():
    assert classify_regex("") is None


# ---------------------------------------------------------------------------
# RETRY_BUDGETS and RETRY_STRATEGIES
# ---------------------------------------------------------------------------

def test_retry_budgets():
    assert RETRY_BUDGETS == {"syntax": 3, "test": 2, "contract": 1, "structural": 1}


def test_retry_strategies():
    assert RETRY_STRATEGIES == {
        "syntax": "auto_fix",
        "test": "debug",
        "contract": "spec_update",
        "structural": "replan",
    }


# ---------------------------------------------------------------------------
# FailureClassifier.classify (async)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_uses_regex_first():
    classifier = FailureClassifier()
    result = await classifier.classify("SyntaxError: bad syntax")
    assert result == "syntax"


@pytest.mark.asyncio
async def test_classify_falls_back_to_llm():
    mock_router = MagicMock()
    mock_router.call = AsyncMock(return_value="test")
    classifier = FailureClassifier(router=mock_router)
    result = await classifier.classify("weird unknown error XYZ")
    assert result == "test"
    mock_router.call.assert_called_once()


@pytest.mark.asyncio
async def test_classify_defaults_structural_no_router():
    classifier = FailureClassifier(router=None)
    result = await classifier.classify("weird unknown error XYZ")
    assert result == "structural"


@pytest.mark.asyncio
async def test_classify_defaults_structural_on_unparseable_llm():
    mock_router = MagicMock()
    mock_router.call = AsyncMock(return_value="gibberish response")
    classifier = FailureClassifier(router=mock_router)
    result = await classifier.classify("weird unknown error XYZ")
    assert result == "structural"


# ---------------------------------------------------------------------------
# get_retry_budget / get_retry_strategy
# ---------------------------------------------------------------------------

def test_get_retry_budget():
    classifier = FailureClassifier()
    assert classifier.get_retry_budget("syntax") == 3
    assert classifier.get_retry_budget("test") == 2
    assert classifier.get_retry_budget("contract") == 1
    assert classifier.get_retry_budget("structural") == 1


def test_get_retry_strategy():
    classifier = FailureClassifier()
    assert classifier.get_retry_strategy("syntax") == "auto_fix"
    assert classifier.get_retry_strategy("test") == "debug"
    assert classifier.get_retry_strategy("contract") == "spec_update"
    assert classifier.get_retry_strategy("structural") == "replan"
