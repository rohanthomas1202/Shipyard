import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import ValidationError

from agent.schemas import EditResponse, ValidatorFeedback


# ---------------------------------------------------------------------------
# Existing call_llm tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_call_llm_forwards_params():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "test response"

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
        assert result == "test response"
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o"
        assert call_kwargs["max_tokens"] == 1000


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

def test_edit_response_schema():
    resp = EditResponse(anchor="foo", replacement="bar")
    assert resp.anchor == "foo"
    assert resp.replacement == "bar"
    with pytest.raises(ValidationError):
        EditResponse()


def test_validator_feedback_schema():
    fb = ValidatorFeedback(file_path="f.py", error_message="err")
    assert fb.file_path == "f.py"
    assert fb.error_message == "err"
    assert fb.line is None
    assert fb.suggestion is None

    fb2 = ValidatorFeedback(file_path="a.py", error_message="bad", line=10, suggestion="fix it")
    assert fb2.line == 10
    assert fb2.suggestion == "fix it"


# ---------------------------------------------------------------------------
# call_llm_structured tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_call_llm_structured_returns_pydantic_model():
    expected = EditResponse(anchor="def hello", replacement="def hello_world")
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.parsed = expected

    mock_client = AsyncMock()
    mock_client.chat.completions.parse.return_value = mock_response

    with patch("agent.llm._get_client", return_value=mock_client):
        from agent.llm import call_llm_structured
        result = await call_llm_structured(
            system="sys",
            user="usr",
            response_model=EditResponse,
        )
        assert isinstance(result, EditResponse)
        assert result.anchor == "def hello"
        assert result.replacement == "def hello_world"


@pytest.mark.asyncio
async def test_call_llm_structured_forwards_model_param():
    expected = EditResponse(anchor="a", replacement="b")
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.parsed = expected

    mock_client = AsyncMock()
    mock_client.chat.completions.parse.return_value = mock_response

    with patch("agent.llm._get_client", return_value=mock_client):
        from agent.llm import call_llm_structured
        await call_llm_structured(
            system="sys",
            user="usr",
            response_model=EditResponse,
            model="gpt-4o",
        )
        mock_client.chat.completions.parse.assert_called_once()
        call_kwargs = mock_client.chat.completions.parse.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o"
        assert call_kwargs["response_format"] == EditResponse


@pytest.mark.asyncio
async def test_call_llm_structured_timeout_param():
    expected = EditResponse(anchor="a", replacement="b")
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.parsed = expected

    mock_client = AsyncMock()
    mock_client.chat.completions.parse.return_value = mock_response

    with patch("agent.llm._get_client", return_value=mock_client):
        from agent.llm import call_llm_structured
        await call_llm_structured(
            system="sys",
            user="usr",
            response_model=EditResponse,
            timeout=30,
        )
        call_kwargs = mock_client.chat.completions.parse.call_args.kwargs
        assert call_kwargs["timeout"] == 30


@pytest.mark.asyncio
async def test_existing_call_llm_still_works():
    """Verify original call_llm is unchanged and functional."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "hello"

    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("agent.llm._get_client", return_value=mock_client):
        from agent.llm import call_llm
        result = await call_llm(system="s", user="u")
        assert result == "hello"
        mock_client.chat.completions.create.assert_called_once()
