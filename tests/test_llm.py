import pytest
from unittest.mock import AsyncMock, patch, MagicMock


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
