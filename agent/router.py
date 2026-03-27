"""Policy-based model router with tier resolution, auto-escalation, and usage tracking."""
from pydantic import BaseModel

from agent.models import get_model_for_tier, ModelConfig
from agent.llm import call_llm, call_llm_structured, LLMResult, LLMStructuredResult
from agent.token_tracker import TokenTracker

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

    def __init__(self) -> None:
        self._tracker = TokenTracker()

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
        """Route an LLM call and return the text content (str)."""
        model = self.resolve_model(task_type)
        try:
            result: LLMResult = await call_llm(
                system=system,
                user=user,
                model=model.id,
                max_tokens=model.max_output,
                timeout=model.timeout,
            )
            self._tracker.record(result.model, result.usage)
            return result.content
        except Exception:
            escalated = self.resolve_escalation(task_type)
            if escalated is None:
                raise
            result = await call_llm(
                system=system,
                user=user,
                model=escalated.id,
                max_tokens=escalated.max_output,
                timeout=escalated.timeout,
            )
            self._tracker.record(result.model, result.usage)
            return result.content

    async def call_structured(
        self,
        task_type: str,
        system: str,
        user: str,
        response_model: type[BaseModel],
    ) -> BaseModel:
        """Route a structured LLM call and return the parsed model (BaseModel)."""
        model = self.resolve_model(task_type)
        try:
            result: LLMStructuredResult = await call_llm_structured(
                system=system,
                user=user,
                response_model=response_model,
                model=model.id,
                max_tokens=model.max_output,
                timeout=model.timeout,
            )
            self._tracker.record(result.model, result.usage)
            return result.parsed
        except Exception:
            escalated = self.resolve_escalation(task_type)
            if escalated is None:
                raise
            result = await call_llm_structured(
                system=system,
                user=user,
                response_model=response_model,
                model=escalated.id,
                max_tokens=escalated.max_output,
                timeout=escalated.timeout,
            )
            self._tracker.record(result.model, result.usage)
            return result.parsed

    def reset_usage(self) -> None:
        """Clear all accumulated usage data."""
        self._tracker = TokenTracker()

    def get_usage_log(self) -> list[dict]:
        """Return the raw list of per-call usage entries."""
        return self._tracker.calls

    def get_usage_summary(self) -> dict:
        """Return aggregated totals with estimated cost."""
        return {**self._tracker.totals(), "estimated_cost": self._tracker.estimated_cost()}
