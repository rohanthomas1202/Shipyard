import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agent.github import GitHubClient


@pytest.fixture
def mock_client():
    """GitHubClient with mocked httpx."""
    with patch("agent.github.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        MockClient.return_value = instance
        client = GitHubClient(repo="owner/repo", token="fake-token")
        client._client = instance
        yield client, instance


@pytest.mark.asyncio
async def test_create_pr(mock_client):
    client, http = mock_client
    pr_response = MagicMock()
    pr_response.json.return_value = {"number": 42, "html_url": "https://github.com/owner/repo/pull/42"}
    pr_response.raise_for_status = MagicMock()
    http.post.return_value = pr_response

    result = await client.create_pr("feature/test", "Add feature", "Description")
    assert result["number"] == 42
    assert result["html_url"] == "https://github.com/owner/repo/pull/42"
    assert set(result.keys()) == {"number", "html_url"}


@pytest.mark.asyncio
async def test_create_pr_with_reviewers_best_effort(mock_client):
    client, http = mock_client
    pr_response = MagicMock()
    pr_response.json.return_value = {"number": 1, "html_url": "https://example.com/1"}
    pr_response.raise_for_status = MagicMock()

    reviewer_response = MagicMock()
    reviewer_response.raise_for_status.side_effect = Exception("reviewer failed")

    http.post.side_effect = [pr_response, reviewer_response]
    # Should not raise despite reviewer failure
    result = await client.create_pr("branch", "title", "body", reviewers=["alice"])
    assert result["number"] == 1


@pytest.mark.asyncio
async def test_get_review_comments(mock_client):
    client, http = mock_client
    response = MagicMock()
    response.json.return_value = [{"id": 1, "body": "LGTM"}, {"id": 2, "body": "Fix this"}]
    response.raise_for_status = MagicMock()
    http.get.return_value = response

    comments = await client.get_review_comments(42)
    assert len(comments) == 2
    assert comments[0]["body"] == "LGTM"


@pytest.mark.asyncio
async def test_merge_pr(mock_client):
    client, http = mock_client
    response = MagicMock()
    response.json.return_value = {"merged": True, "sha": "abc123"}
    response.raise_for_status = MagicMock()
    http.put.return_value = response

    result = await client.merge_pr(42, method="squash")
    assert result["merged"] is True
    assert result["sha"] == "abc123"
    assert set(result.keys()) == {"merged", "sha"}


@pytest.mark.asyncio
async def test_close(mock_client):
    client, http = mock_client
    await client.close()
    http.aclose.assert_called_once()
