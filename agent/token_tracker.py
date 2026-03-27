"""Per-run token usage tracking with cost estimation.

Accumulates token counts from LLM calls and computes estimated cost
using per-model pricing rates.
"""
from dataclasses import dataclass, field


# Per-1M-token rates: (input_cost, output_cost)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "o3": (2.00, 8.00),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}


@dataclass
class TokenTracker:
    """Tracks token usage across multiple LLM calls within a run."""

    calls: list[dict] = field(default_factory=list)

    def record(self, model: str, usage: dict) -> None:
        """Record a single LLM call's token usage."""
        self.calls.append({"model": model, **usage})

    def totals(self) -> dict:
        """Aggregate token counts across all recorded calls."""
        prompt = sum(c.get("prompt_tokens", 0) for c in self.calls)
        completion = sum(c.get("completion_tokens", 0) for c in self.calls)
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
            "call_count": len(self.calls),
        }

    def estimated_cost(self) -> float:
        """Compute estimated cost in USD from recorded usage."""
        total = 0.0
        for call in self.calls:
            model = call.get("model", "gpt-4o")
            input_rate, output_rate = MODEL_PRICING.get(
                model, MODEL_PRICING["gpt-4o"]
            )
            prompt_tokens = call.get("prompt_tokens", 0)
            completion_tokens = call.get("completion_tokens", 0)
            total += (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000
        return total
