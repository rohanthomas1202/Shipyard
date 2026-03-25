"""Policy-based model router with tier resolution and auto-escalation."""
from agent.models import get_model_for_tier, ModelConfig
from agent.llm import call_llm

ROUTING_POLICY: dict[str, dict] = {
    "plan":           {"tier": "reasoning"},
    "coordinate":     {"tier": "reasoning"},
    "edit_complex":   {"tier": "reasoning"},
    "edit_simple":    {"tier": "general", "escalation": "reasoning"},
    "read":           {"tier": "general"},
    "validate":       {"tier": "fast",    "escalation": "general"},
    "merge":          {"tier": "general", "escalation": "reasoning"},
    "summarize":      {"tier": "general"},
    "parse_results":  {"tier": "general", "escalation": "reasoning"},
}


class ModelRouter:
    """Routes LLM calls to the optimal model based on task type."""

    def resolve_model(self, task_type: str) -> ModelConfig:
        policy = ROUTING_POLICY[task_type]
        return get_model_for_tier(policy["tier"])

    def resolve_escalation(self, task_type: str) -> ModelConfig | None:
        policy = ROUTING_POLICY[task_type]
        esc_tier = policy.get("escalation")
        if esc_tier is None:
            return None
        return get_model_for_tier(esc_tier)

    async def call(
        self,
        task_type: str,
        system: str,
        user: str,
    ) -> str:
        model = self.resolve_model(task_type)
        try:
            return await call_llm(
                system=system,
                user=user,
                model=model.id,
                max_tokens=model.max_output,
                timeout=model.timeout,
            )
        except Exception:
            escalated = self.resolve_escalation(task_type)
            if escalated is None:
                raise
            return await call_llm(
                system=system,
                user=user,
                model=escalated.id,
                max_tokens=escalated.max_output,
                timeout=escalated.timeout,
            )
