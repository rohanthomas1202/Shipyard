"""Tests for the LLM wrapper — verifies LLMResult and LLMStructuredResult."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import BaseModel

from agent.llm import LLMResult, LLMStructuredResult


class EditResponse(BaseModel):
    anchor: str
    replacement: str


def _make_mock_response(content="test response", prompt_tokens=100,
                        completion_tokens=50, total_tokens=150):
    """Build a mock OpenAI response with usage stats."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    mock_response.usage = MagicMock(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )
    return mock_response


@pytest.mark.asyncio
async def test_call_llm_forwards_params():
    mock_response = _make_mock_response()
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("agent.llm._get_client", return_value=mock_client):
        from agent.llm import call_llm
        result = await call_llm(
            system="sys prompt",
            user="user prompt",
            model="gpt-4o",
            max_tokens=1000,
            timeout=30,
        )
        assert isinstance(result, LLMResult)
        assert result.content == "test response"
        assert result.usage["prompt_tokens"] == 100
        assert result.usage["completion_tokens"] == 50
        assert result.usage["total_tokens"] == 150
        assert result.model == "gpt-4o"
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o"
        assert call_kwargs["max_tokens"] == 1000


@pytest.mark.asyncio
async def test_call_llm_no_usage():
    """When response.usage is None, result.usage should be empty dict."""
    mock_response = _make_mock_response()
    mock_response.usage = None
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("agent.llm._get_client", return_value=mock_client):
        from agent.llm import call_llm
        result = await call_llm(system="sys", user="user")
        assert isinstance(result, LLMResult)
        assert result.usage == {}


@pytest.mark.asyncio
async def test_call_llm_structured_returns_result():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.parsed = EditResponse(anchor="foo", replacement="bar")
    mock_response.usage = MagicMock(
        prompt_tokens=80, completion_tokens=30, total_tokens=110,
    )
    mock_client = AsyncMock()
    mock_client.beta.chat.completions.parse.return_value = mock_response

    with patch("agent.llm._get_client", return_value=mock_client):
        from agent.llm import call_llm_structured
        result = await call_llm_structured(
            system="sys",
            user="user",
            response_model=EditResponse,
            model="gpt-4o",
        )
        assert isinstance(result, LLMStructuredResult)
        assert isinstance(result.parsed, EditResponse)
        assert result.parsed.anchor == "foo"
        assert result.usage["prompt_tokens"] == 80
        assert result.model == "gpt-4o"
