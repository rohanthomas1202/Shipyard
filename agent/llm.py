from anthropic import AsyncAnthropic

client = AsyncAnthropic()

async def call_llm(system: str, user: str, model: str = "claude-sonnet-4-20250514") -> str:
    """Call Claude and return the text response."""
    response = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text
