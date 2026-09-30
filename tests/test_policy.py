from driftguard.policy import DEFAULT_POLICY, evaluate_drift, recommend_mitigation


def test_healthy_metrics_are_stable():
    result = evaluate_drift(
        {"prompt_tokens": 1000, "context_length": 2000, "retrieval_score": 0.9, "response_quality": 0.95}
    )
    assert result["severity"] == "stable"
    assert result["risk_score"] == 0.0
    assert result["violations"] == []
    assert result["actions"] == ["no_action_required"]


def test_all_rules_violated_is_critical_and_capped():
    result = evaluate_drift(
        {"prompt_tokens": 5000, "context_length": 6000, "retrieval_score": 0.2, "response_quality": 0.5}
    )
    assert result["severity"] == "critical"
    assert result["risk_score"] == 1.0
    assert set(result["violations"]) == {
        "prompt_token_limit",
        "context_length_limit",
        "retrieval_score_floor",
        "response_quality_floor",
    }
    assert result["recommendation"] == "compress_prompt_context_and_reduce_context_window"


def test_warning_band():
    # prompt (0.25) + context (0.2) = 0.45 -> warning
    result = evaluate_drift({"prompt_tokens": 3500, "context_length": 4500})
    assert result["severity"] == "warning"
    assert result["risk_score"] == 0.45


def test_missing_metrics_do_not_trigger_rules():
    assert evaluate_drift({})["severity"] == "stable"
    assert evaluate_drift({"retrieval_score": None, "prompt_tokens": None})["severity"] == "stable"


def test_custom_policy_changes_both_severity_and_actions():
    metrics = {"prompt_tokens": 1200, "context_length": 1500}
    assert evaluate_drift(metrics)["severity"] == "stable"
    tight = {"prompt_token_limit": 500, "context_length_limit": 1000}
    result = evaluate_drift(metrics, tight)
    assert result["severity"] == "warning"
    # The mitigation recommender must honour the same custom thresholds.
    assert "compress_prompt_context" in recommend_mitigation(metrics, tight)["actions"]
    assert recommend_mitigation(metrics)["actions"] == ["no_action_required"]


def test_recommend_mitigation_savings_ratio_is_bounded():
    plan = recommend_mitigation({"prompt_tokens": 9000, "retrieval_score": 0.1, "response_quality": 0.1})
    assert 0 < plan["token_savings_ratio"] <= 0.6
    assert "retrieval degradation" in plan["root_cause"]


def test_default_policy_includes_agent_settings():
    assert DEFAULT_POLICY["blocked_after_failures"] == 3
    assert DEFAULT_POLICY["retry_window_minutes"] == 60
