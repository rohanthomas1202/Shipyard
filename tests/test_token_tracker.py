"""Tests for TokenTracker cost estimation and usage aggregation."""
from agent.token_tracker import TokenTracker, MODEL_PRICING


def test_record_and_totals():
    tracker = TokenTracker()
    tracker.record("gpt-4o", {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
    tracker.record("gpt-4o", {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300})
    totals = tracker.totals()
    assert totals["prompt_tokens"] == 300
    assert totals["completion_tokens"] == 150
    assert totals["total_tokens"] == 450
    assert totals["call_count"] == 2


def test_estimated_cost_gpt4o():
    tracker = TokenTracker()
    tracker.record("gpt-4o", {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000})
    cost = tracker.estimated_cost()
    # gpt-4o: $2.50/1M input + $10.00/1M output = $12.50
    assert abs(cost - 12.50) < 0.001


def test_estimated_cost_mixed_models():
    tracker = TokenTracker()
    # o3: 500k input ($1.00) + 200k output ($1.60) = $2.60
    tracker.record("o3", {"prompt_tokens": 500_000, "completion_tokens": 200_000})
    # gpt-4o-mini: 1M input ($0.15) + 500k output ($0.30) = $0.45
    tracker.record("gpt-4o-mini", {"prompt_tokens": 1_000_000, "completion_tokens": 500_000})
    cost = tracker.estimated_cost()
    assert abs(cost - 3.05) < 0.001


def test_estimated_cost_unknown_model():
    """Unknown models fall back to gpt-4o pricing."""
    tracker = TokenTracker()
    tracker.record("unknown-model", {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000})
    cost = tracker.estimated_cost()
    # Should use gpt-4o rates: $2.50 + $10.00 = $12.50
    assert abs(cost - 12.50) < 0.001


def test_model_pricing_has_expected_entries():
    assert "o3" in MODEL_PRICING
    assert "gpt-4o" in MODEL_PRICING
    assert "gpt-4o-mini" in MODEL_PRICING
