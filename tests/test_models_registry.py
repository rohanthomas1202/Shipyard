import pytest
from agent.models import MODEL_REGISTRY, get_model_for_tier, ModelConfig


def test_registry_has_three_models():
    assert len(MODEL_REGISTRY) == 3
    assert "o3" in MODEL_REGISTRY
    assert "gpt-4o" in MODEL_REGISTRY
    assert "gpt-4o-mini" in MODEL_REGISTRY


def test_model_config_has_required_fields():
    for model_id, config in MODEL_REGISTRY.items():
        assert isinstance(config, ModelConfig)
        assert config.id == model_id
        assert config.context_window > 0
        assert config.max_output > 0
        assert config.tier in ("reasoning", "general", "fast")
        assert config.timeout > 0
        assert isinstance(config.capabilities, list)


def test_get_model_for_tier_reasoning():
    model = get_model_for_tier("reasoning")
    assert model.id == "o3"


def test_get_model_for_tier_general():
    model = get_model_for_tier("general")
    assert model.id == "gpt-4o"


def test_get_model_for_tier_fast():
    model = get_model_for_tier("fast")
    assert model.id == "gpt-4o-mini"


def test_get_model_for_tier_invalid():
    with pytest.raises(ValueError, match="Unknown tier"):
        get_model_for_tier("unknown")


def test_escalation_order():
    fast = get_model_for_tier("fast")
    general = get_model_for_tier("general")
    reasoning = get_model_for_tier("reasoning")
    assert fast.timeout < general.timeout < reasoning.timeout
