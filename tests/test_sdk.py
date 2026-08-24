from driftguard.client import DriftGuardClient
from driftguard.mitigation import recommend_mitigation


def test_client_detects_drift_and_generates_recommendations():
    client = DriftGuardClient(api_key="demo-key", project_name="demo-app", environment="prod")
    client.capture_metrics(
        prompt_tokens=4200,
        retrieval_score=0.32,
        context_length=5200,
        response_quality=0.68,
    )

    result = client.check_drift()

    assert result["severity"] in {"warning", "critical"}
    assert "recommendation" in result
    assert "actions" in result
    assert isinstance(result["actions"], list)


def test_mitigation_policy_reduces_token_load_for_high_risk_cases():
    plan = recommend_mitigation({
        "prompt_tokens": 5000,
        "context_length": 6000,
        "retrieval_score": 0.28,
        "response_quality": 0.7,
    })

    assert plan["token_savings_ratio"] > 0
    assert plan["recommended_action"]
    assert "root_cause" in plan
