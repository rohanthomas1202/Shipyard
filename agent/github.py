"""GitHubClient — GitHub REST API operations via httpx."""
from __future__ import annotations
import httpx


class GitHubClient:
    def __init__(self, repo: str, token: str):
        self.repo = repo
        self._client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )

    async def create_pr(self, branch: str, title: str, body: str,
                        draft: bool = False, reviewers: list[str] | None = None) -> dict:
        resp = await self._client.post(
            f"/repos/{self.repo}/pulls",
            json={"head": branch, "base": "main", "title": title, "body": body, "draft": draft},
        )
        resp.raise_for_status()
        pr_data = resp.json()

        if reviewers:
            try:
                reviewer_resp = await self._client.post(
                    f"/repos/{self.repo}/pulls/{pr_data['number']}/requested_reviewers",
                    json={"reviewers": reviewers},
                )
                reviewer_resp.raise_for_status()
            except Exception:
                pass  # best-effort

        return {"number": pr_data.get("number"), "html_url": pr_data.get("html_url")}

    async def get_review_comments(self, pr_number: int, since: str | None = None) -> list[dict]:
        params = {}
        if since:
            params["since"] = since
        resp = await self._client.get(
            f"/repos/{self.repo}/pulls/{pr_number}/comments",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    async def merge_pr(self, pr_number: int, method: str = "squash") -> dict:
        resp = await self._client.put(
            f"/repos/{self.repo}/pulls/{pr_number}/merge",
            json={"merge_method": method},
        )
        resp.raise_for_status()
        data = resp.json()
        return {"merged": data.get("merged", False), "sha": data.get("sha", "")}

    async def close(self):
        await self._client.aclose()
