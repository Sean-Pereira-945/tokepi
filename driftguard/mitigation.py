"""Rule-based recommendations for reducing prompt and response drift costs."""

from __future__ import annotations

from typing import Any


def recommend_mitigation(metrics: dict[str, Any]) -> dict[str, Any]:
    """Suggest automatic mitigation actions and compute expected token savings."""
    prompt_tokens = float(metrics.get("prompt_tokens", 0))
    context_length = float(metrics.get("context_length", 0))
    retrieval_score = float(metrics.get("retrieval_score", 1.0))
    response_quality = float(metrics.get("response_quality", 1.0))

    actions: list[str] = []
    root_cause_parts: list[str] = []

    token_savings_ratio = 0.0

    if prompt_tokens > 3000 or context_length > 4000:
        actions.append("compress_prompt_context")
        token_savings_ratio += 0.2
        root_cause_parts.append("prompt context inflation")

    if retrieval_score < 0.5:
        actions.append("trim_retrieval_results")
        token_savings_ratio += 0.15
        root_cause_parts.append("retrieval degradation")

    if response_quality < 0.8:
        actions.append("fallback_to_lower_cost_model")
        token_savings_ratio += 0.1
        root_cause_parts.append("trajectory quality degradation")

    if not actions:
        actions = ["no_action_required"]
        root_cause_parts = ["system remains within baseline operating bands"]

    recommended_action = actions[0]
    if recommended_action == "compress_prompt_context":
        recommended_action = "compress_prompt_context_and_reduce_context_window"
    elif recommended_action == "trim_retrieval_results":
        recommended_action = "trim_retrieval_results_and_prioritize_high_value_documents"
    elif recommended_action == "fallback_to_lower_cost_model":
        recommended_action = "fallback_to_lower_cost_model_for_non_critical_requests"

    return {
        "recommended_action": recommended_action,
        "actions": actions,
        "token_savings_ratio": round(min(0.6, token_savings_ratio), 3),
        "root_cause": "; ".join(root_cause_parts),
    }
