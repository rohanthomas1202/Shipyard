# agent/llm.py
"""Thin OpenAI wrapper — called by the router, not by nodes directly."""
import os
from dataclasses import dataclass
from openai import AsyncOpenAI
from pydantic import BaseModel


@dataclass
class LLMResult:
    """Result from a plain text LLM call."""
    content: str
    usage: dict
    model: str


@dataclass
class LLMStructuredResult:
    """Result from a structured (parsed) LLM call."""
    parsed: BaseModel
    usage: dict
    model: str


_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _client


def _extract_usage(response) -> dict:
    """Extract usage dict from an OpenAI response, handling None gracefully."""
    if response.usage is None:
        return {}
    return {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }


async def call_llm(
    system: str,
    user: str,
    model: str = "gpt-4o",
    max_tokens: int = 16_384,
    timeout: int = 60,
) -> LLMResult:
    """Call OpenAI chat completions. Returns LLMResult with content, usage, and model."""
    client = _get_client()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_completion_tokens=max_tokens,
        timeout=timeout,
    )
    content = response.choices[0].message.content or ""
    usage = _extract_usage(response)
    return LLMResult(content=content, usage=usage, model=model)


async def call_llm_structured(
    system: str,
    user: str,
    response_model: type[BaseModel],
    model: str = "gpt-4o",
    max_tokens: int = 16_384,
    timeout: int = 60,
) -> LLMStructuredResult:
    """Call OpenAI with structured output parsing. Returns LLMStructuredResult."""
    client = _get_client()
    response = await client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format=response_model,
        max_completion_tokens=max_tokens,
        timeout=timeout,
    )
    parsed = response.choices[0].message.parsed
    usage = _extract_usage(response)
    return LLMStructuredResult(parsed=parsed, usage=usage, model=model)
