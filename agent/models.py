"""Model capability registry — config-driven, not hardcoded to specific model names."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelConfig:
    id: str
    context_window: int
    max_output: int
    tier: str  # "reasoning" | "general" | "fast"
    timeout: int  # seconds
    capabilities: list[str] = field(default_factory=list)


MODEL_REGISTRY: dict[str, ModelConfig] = {
    "o3": ModelConfig(
        id="o3",
        context_window=200_000,
        max_output=100_000,
        tier="reasoning",
        timeout=120,
        capabilities=["planning", "complex_edit", "conflict_resolution"],
    ),
    "gpt-4o": ModelConfig(
        id="gpt-4o",
        context_window=128_000,
        max_output=16_384,
        tier="general",
        timeout=60,
        capabilities=["edit", "read", "summarize", "merge"],
    ),
    "gpt-4o-mini": ModelConfig(
        id="gpt-4o-mini",
        context_window=128_000,
        max_output=16_384,
        tier="fast",
        timeout=30,
        capabilities=["classify", "validate", "syntax_check"],
    ),
}


def get_model_for_tier(tier: str) -> ModelConfig:
    """Resolve a tier name to the best available model."""
    for config in MODEL_REGISTRY.values():
        if config.tier == tier:
            return config
    raise ValueError(f"Unknown tier: {tier}")
