import pytest
from unittest.mock import AsyncMock, patch
from agent.router import ModelRouter, ROUTING_POLICY
from agent.schemas import EditResponse


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
    with patch("agent.router.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = '{"result": "ok"}'
        result = await router.call("plan", "system prompt", "user prompt")
        mock_llm.assert_called_once()
        call_kwargs = mock_llm.call_args
        assert call_kwargs.kwargs["model"] == "o3"
        assert result == '{"result": "ok"}'


@pytest.mark.asyncio
async def test_router_call_escalates_on_failure():
    router = ModelRouter()
    with patch("agent.router.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = [Exception("timeout"), '{"result": "ok"}']
        result = await router.call("edit_simple", "system", "user")
        assert mock_llm.call_count == 2
        second_call = mock_llm.call_args_list[1]
        assert second_call.kwargs["model"] == "o3"
        assert result == '{"result": "ok"}'


@pytest.mark.asyncio
async def test_router_call_raises_after_failed_escalation():
    router = ModelRouter()
    with patch("agent.router.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = Exception("all models failed")
        with pytest.raises(Exception, match="all models failed"):
            await router.call("plan", "system", "user")
        assert mock_llm.call_count == 1


@pytest.mark.asyncio
async def test_router_call_structured_routes_correctly():
    router = ModelRouter()
    expected = EditResponse(anchor="a", replacement="b")
    with patch("agent.router.call_llm_structured", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = expected
        result = await router.call_structured(
            "edit_simple", "sys", "usr", EditResponse,
        )
        assert isinstance(result, EditResponse)
        assert result is expected
        mock_llm.assert_called_once()
        call_kwargs = mock_llm.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o"
        assert call_kwargs["response_model"] == EditResponse


@pytest.mark.asyncio
async def test_router_call_structured_escalates_on_error():
    router = ModelRouter()
    expected = EditResponse(anchor="x", replacement="y")
    with patch("agent.router.call_llm_structured", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = [Exception("timeout"), expected]
        result = await router.call_structured(
            "edit_simple", "sys", "usr", EditResponse,
        )
        assert mock_llm.call_count == 2
        second_call = mock_llm.call_args_list[1]
        assert second_call.kwargs["model"] == "o3"
        assert isinstance(result, EditResponse)
