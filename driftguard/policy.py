"""Drift policy thresholds and the rule-based evaluator shared by the SDK and server.

Both :meth:`driftguard.DriftGuardClient.check_drift` and server-side ingestion call
:func:`evaluate_drift`, so a metric payload always receives the same severity no
matter where it is scored.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Default thresholds written to every new project policy.
DEFAULT_POLICY: dict[str, float] = {
    "prompt_token_limit": 3000.0,  # nosec B105
    "retrieval_score_floor": 0.5,
    "context_length_limit": 4000.0,
    "response_quality_floor": 0.8,
    # Agent diagnosis: consecutive failures of one tool before a task counts as blocked.
    "blocked_after_failures": 3,
    # Agent diagnosis: failures further apart than this are not treated as one retry loop.
    "retry_window_minutes": 60.0,
}

# Risk added when each rule is violated. The total is capped at 1.0.
RISK_WEIGHTS: dict[str, float] = {
    "prompt_token_limit": 0.25,  # nosec B105
    "retrieval_score_floor": 0.35,
    "context_length_limit": 0.2,
    "response_quality_floor": 0.2,
}

WARNING_RISK = 0.4
CRITICAL_RISK = 0.75

_RECOMMENDATIONS = {
    "compress_prompt_context": "compress_prompt_context_and_reduce_context_window",
    "trim_retrieval_results": "trim_retrieval_results_and_prioritize_high_value_documents",
    "fallback_to_lower_cost_model": "fallback_to_lower_cost_model_for_non_critical_requests",
    "no_action_required": "no_action_required",
}


def _num(metrics: Mapping[str, Any], key: str, default: float) -> float:
    """Read a numeric metric, treating a missing or null value as ``default``."""
    value = metrics.get(key)
    return default if value is None else float(value)


def recommend_mitigation(metrics: Mapping[str, Any], policy: Mapping[str, float] | None = None) -> dict[str, Any]:
    """Suggest mitigation actions for one metric payload under ``policy``.

    Returns the recommended action, every triggered action, an estimated token
    savings ratio, and a human-readable root cause.
    """
    limits = {**DEFAULT_POLICY, **(policy or {})}
    prompt_tokens = _num(metrics, "prompt_tokens", 0.0)
    context_length = _num(metrics, "context_length", 0.0)
    retrieval_score = _num(metrics, "retrieval_score", 1.0)
    response_quality = _num(metrics, "response_quality", 1.0)

    actions: list[str] = []
    causes: list[str] = []
    savings_ratio = 0.0

    if prompt_tokens > limits["prompt_token_limit"] or context_length > limits["context_length_limit"]:
        actions.append("compress_prompt_context")
        causes.append("prompt context inflation")
        savings_ratio += 0.2
    if retrieval_score < limits["retrieval_score_floor"]:
        actions.append("trim_retrieval_results")
        causes.append("retrieval degradation")
        savings_ratio += 0.15
    if response_quality < limits["response_quality_floor"]:
        actions.append("fallback_to_lower_cost_model")
        causes.append("response quality degradation")
        savings_ratio += 0.1

    if not actions:
        actions = ["no_action_required"]
        causes = ["within policy thresholds"]

    return {
        "recommended_action": _RECOMMENDATIONS[actions[0]],
        "actions": actions,
        "token_savings_ratio": round(min(0.6, savings_ratio), 3),
        "root_cause": "; ".join(causes),
    }


def evaluate_drift(metrics: Mapping[str, Any], policy: Mapping[str, float] | None = None) -> dict[str, Any]:
    """Score one metric payload against ``policy``.

    Returns ``severity`` (``stable``/``warning``/``critical``), ``risk_score`` in
    ``[0, 1]``, the violated rules, and the mitigation recommendation.
    """
    limits = {**DEFAULT_POLICY, **(policy or {})}
    violations: list[str] = []
    if _num(metrics, "prompt_tokens", 0.0) > limits["prompt_token_limit"]:
        violations.append("prompt_token_limit")
    if _num(metrics, "retrieval_score", 1.0) < limits["retrieval_score_floor"]:
        violations.append("retrieval_score_floor")
    if _num(metrics, "context_length", 0.0) > limits["context_length_limit"]:
        violations.append("context_length_limit")
    if _num(metrics, "response_quality", 1.0) < limits["response_quality_floor"]:
        violations.append("response_quality_floor")

    risk_score = min(1.0, sum(RISK_WEIGHTS[rule] for rule in violations))
    if risk_score >= CRITICAL_RISK:
        severity = "critical"
    elif risk_score >= WARNING_RISK:
        severity = "warning"
    else:
        severity = "stable"

    mitigation = recommend_mitigation(metrics, limits)
    return {
        "severity": severity,
        "risk_score": round(risk_score, 3),
        "violations": violations,
        "recommendation": mitigation["recommended_action"],
        "actions": mitigation["actions"],
        "root_cause": mitigation["root_cause"],
        "token_savings_ratio": mitigation["token_savings_ratio"],
    }
