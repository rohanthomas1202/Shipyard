"""Tests for the model router — routing, escalation, and usage tracking."""
import pytest
from unittest.mock import AsyncMock, patch
from pydantic import BaseModel

from agent.router import ModelRouter, ROUTING_POLICY
from agent.llm import LLMResult, LLMStructuredResult


class EditResponse(BaseModel):
    anchor: str
    replacement: str


def test_routing_policy_covers_all_task_types():
    expected_tasks = [
        "plan", "coordinate", "edit_complex", "edit_simple",
        "read", "validate", "merge", "summarize", "parse_results",
    ]
    for task in expected_tasks:
        assert task in ROUTING_POLICY, f"Missing policy for {task}"


def test_routing_policy_values_are_valid_tiers():
    valid_tiers = {"reasoning", "general", "fast"}
    for task, policy in ROUTING_POLICY.items():
        assert policy["tier"] in valid_tiers
        if policy.get("escalation"):
            assert policy["escalation"] in valid_tiers


def test_router_resolve_model():
    router = ModelRouter()
    model = router.resolve_model("plan")
    assert model.id == "o3"

    model = router.resolve_model("edit_simple")
    assert model.id == "gpt-4o"

    model = router.resolve_model("validate")
    assert model.id == "gpt-4o-mini"


def test_router_resolve_escalation():
    router = ModelRouter()
    escalated = router.resolve_escalation("edit_simple")
    assert escalated is not None
    assert escalated.id == "o3"

    escalated = router.resolve_escalation("validate")
    assert escalated is not None
    assert escalated.id == "gpt-4o"


def test_router_resolve_escalation_no_escalation():
    router = ModelRouter()
    escalated = router.resolve_escalation("plan")
    assert escalated is None


@pytest.mark.asyncio
async def test_router_call_routes_to_correct_model():
    router = ModelRouter()
    mock_result = LLMResult(
        content='{"result": "ok"}',
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        model="o3",
    )
    with patch("agent.router.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_result
        result = await router.call("plan", "system prompt", "user prompt")
        mock_llm.assert_called_once()
        call_kwargs = mock_llm.call_args
        assert call_kwargs.kwargs["model"] == "o3"
        assert result == '{"result": "ok"}'
        assert len(router.get_usage_log()) == 1
        assert router.get_usage_log()[0]["prompt_tokens"] == 100


@pytest.mark.asyncio
async def test_router_call_escalates_on_failure():
    router = ModelRouter()
    escalated_result = LLMResult(
        content='{"result": "ok"}',
        usage={"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300},
        model="o3",
    )
    with patch("agent.router.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = [Exception("timeout"), escalated_result]
        result = await router.call("edit_simple", "system", "user")
        assert mock_llm.call_count == 2
        second_call = mock_llm.call_args_list[1]
        assert second_call.kwargs["model"] == "o3"
        assert result == '{"result": "ok"}'
        # Only the successful escalated call should be recorded
        assert len(router.get_usage_log()) >= 1


@pytest.mark.asyncio
async def test_router_call_raises_after_failed_escalation():
    router = ModelRouter()
    with patch("agent.router.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = Exception("all models failed")
        with pytest.raises(Exception, match="all models failed"):
            await router.call("plan", "system", "user")
        assert mock_llm.call_count == 1


@pytest.mark.asyncio
async def test_router_usage_accumulates():
    router = ModelRouter()
    mock_result = LLMResult(
        content="response",
        usage={"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75},
        model="o3",
    )
    with patch("agent.router.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_result
        await router.call("plan", "sys", "usr")
        await router.call("plan", "sys", "usr")
        summary = router.get_usage_summary()
        assert summary["call_count"] == 2
        assert summary["prompt_tokens"] == 100
        assert summary["completion_tokens"] == 50
        assert "estimated_cost" in summary


@pytest.mark.asyncio
async def test_router_reset_usage():
    router = ModelRouter()
    mock_result = LLMResult(
        content="response",
        usage={"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75},
        model="o3",
    )
    with patch("agent.router.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_result
        await router.call("plan", "sys", "usr")
        assert len(router.get_usage_log()) == 1
        router.reset_usage()
        assert router.get_usage_log() == []


@pytest.mark.asyncio
async def test_router_call_structured_accumulates():
    router = ModelRouter()
    mock_result = LLMStructuredResult(
        parsed=EditResponse(anchor="foo", replacement="bar"),
        usage={"prompt_tokens": 80, "completion_tokens": 30, "total_tokens": 110},
        model="gpt-4o",
    )
    with patch("agent.router.call_llm_structured", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_result
        result = await router.call_structured("edit_simple", "sys", "usr", EditResponse)
        assert isinstance(result, EditResponse)
        assert result.anchor == "foo"
        assert len(router.get_usage_log()) == 1
        assert router.get_usage_log()[0]["prompt_tokens"] == 80
