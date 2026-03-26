# agent/llm.py
"""Thin OpenAI wrapper — called by the router, not by nodes directly."""
import os
from openai import AsyncOpenAI
from pydantic import BaseModel

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _client


async def call_llm(
    system: str,
    user: str,
    model: str = "gpt-4o",
    max_tokens: int = 16_384,
    timeout: int = 60,
) -> str:
    """Call OpenAI chat completions. Returns the assistant message content."""
    client = _get_client()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
        timeout=timeout,
    )
    return response.choices[0].message.content or ""


async def call_llm_structured(
    system: str,
    user: str,
    response_model: type[BaseModel],
    model: str = "gpt-4o",
    max_tokens: int = 16_384,
    timeout: int = 60,
) -> BaseModel:
    """Call OpenAI with structured output. Returns parsed Pydantic model.

    Uses client.chat.completions.parse() which enforces the schema
    server-side, eliminating JSON parse failures. This is the non-beta
    path available in OpenAI SDK >= 2.x (project uses 2.29.0).
    """
    client = _get_client()
    response = await client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format=response_model,
        max_completion_tokens=max_tokens,
        timeout=timeout,
    )
    return response.choices[0].message.parsed
