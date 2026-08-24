"""Tests for the enhanced DriftGuardClient SDK:
- Offline check_drift uses default thresholds
- sync_metrics sends events via httpx (mocked)
- fetch_policy updates internal thresholds
- policy-aware check_drift uses server thresholds
"""
import pytest
import httpx
from unittest.mock import MagicMock, patch

from driftguard.client import DriftGuardClient, _DEFAULT_POLICY


# ---------------------------------------------------------------------------
# Offline behaviour (no base_url)
# ---------------------------------------------------------------------------

def test_check_drift_uses_default_thresholds_without_server():
    client = DriftGuardClient(api_key="test-key", project_name="test")
    client.capture_metrics(
        prompt_tokens=4200,
        retrieval_score=0.3,
        context_length=5000,
        response_quality=0.65,
    )
    result = client.check_drift()
    assert result["severity"] in {"warning", "critical"}
    assert isinstance(result["risk_score"], float)
    assert 0.0 <= result["risk_score"] <= 1.0


def test_check_drift_returns_stable_when_no_metrics():
    client = DriftGuardClient(api_key="test-key", project_name="test")
    result = client.check_drift()
    assert result["severity"] == "stable"
    assert result["risk_score"] == 0.0


def test_sync_metrics_raises_without_base_url():
    client = DriftGuardClient(api_key="test-key", project_name="test")
    client.capture_metrics(prompt_tokens=1000.0)
    with pytest.raises(RuntimeError, match="base_url"):
        client.sync_metrics("my-project")


def test_fetch_policy_raises_without_base_url():
    client = DriftGuardClient(api_key="test-key", project_name="test")
    with pytest.raises(RuntimeError, match="base_url"):
        client.fetch_policy("my-project")


# ---------------------------------------------------------------------------
# sync_metrics (mocked httpx)
# ---------------------------------------------------------------------------

def test_sync_metrics_posts_events_and_clears_queue():
    client = DriftGuardClient(
        api_key="proj-api-key",
        project_name="test",
        base_url="http://localhost:8000",
    )
    client.capture_metrics(prompt_tokens=1500.0, retrieval_score=0.8)
    client.capture_metrics(prompt_tokens=2000.0, retrieval_score=0.7)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_httpx:
        mock_http_instance = mock_httpx.return_value.__enter__.return_value
        mock_http_instance.post.return_value = mock_response

        result = client.sync_metrics("my-project")

    assert result["synced"] == 2
    assert len(result["errors"]) == 0
    assert len(client.metrics) == 0  # queue should be empty after successful sync


def test_sync_metrics_returns_zero_when_no_events():
    client = DriftGuardClient(
        api_key="key",
        project_name="test",
        base_url="http://localhost:8000",
    )
    result = client.sync_metrics("my-project")
    assert result["synced"] == 0
    assert result.get("skipped") is True


def test_sync_metrics_records_errors_on_http_failure():
    client = DriftGuardClient(
        api_key="key",
        project_name="test",
        base_url="http://localhost:8000",
    )
    client.capture_metrics(prompt_tokens=999.0)

    with patch("httpx.Client") as mock_httpx:
        mock_http_instance = mock_httpx.return_value.__enter__.return_value
        mock_http_instance.post.side_effect = httpx.ConnectError("connection refused")

        result = client.sync_metrics("my-project")

    assert result["synced"] == 0
    assert len(result["errors"]) == 1


# ---------------------------------------------------------------------------
# fetch_policy + policy-aware check_drift
# ---------------------------------------------------------------------------

def test_fetch_policy_updates_internal_thresholds():
    client = DriftGuardClient(
        api_key="key",
        project_name="test",
        base_url="http://localhost:8000",
    )

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "prompt_token_limit": 1000.0,      # much tighter than default 3000
        "retrieval_score_floor": 0.9,       # much tighter than default 0.5
        "context_length_limit": 2000.0,
        "response_quality_floor": 0.95,
    }

    with patch("httpx.Client") as mock_httpx:
        mock_http_instance = mock_httpx.return_value.__enter__.return_value
        mock_http_instance.get.return_value = mock_response

        policy = client.fetch_policy("my-project")

    assert policy["prompt_token_limit"] == 1000.0
    assert policy["retrieval_score_floor"] == 0.9


def test_check_drift_uses_server_policy_thresholds():
    """After fetch_policy, check_drift should flag metrics that pass default thresholds
    but fail tighter server-side thresholds."""
    client = DriftGuardClient(
        api_key="key",
        project_name="test",
        base_url="http://localhost:8000",
    )

    # Metrics that would be STABLE under defaults (prompt_tokens < 3000)
    client.capture_metrics(
        prompt_tokens=1200.0,   # below default 3000, but above tight server limit of 500
        retrieval_score=0.95,
        context_length=1500.0,
        response_quality=0.95,
    )

    # Without server policy — should be stable
    result_before = client.check_drift()
    assert result_before["severity"] == "stable"

    # Now inject a tight server policy — both prompt_tokens and context_length will breach
    with client._policy_lock:
        client._policy = {
            "prompt_token_limit": 500.0,    # 1200 > 500 → +0.25 risk
            "retrieval_score_floor": 0.5,
            "context_length_limit": 1000.0,  # 1500 > 1000 → +0.20 risk  (total 0.45 >= 0.4)
            "response_quality_floor": 0.8,
        }

    # Same metrics should now trigger a warning (0.25 + 0.20 = 0.45 >= 0.4)
    result_after = client.check_drift()
    assert result_after["severity"] in {"warning", "critical"}


def test_capture_metrics_returns_payload():
    client = DriftGuardClient(api_key="key", project_name="my-app", environment="staging")
    payload = client.capture_metrics(prompt_tokens=500.0, retrieval_score=0.9)
    assert payload["project"] == "my-app"
    assert payload["environment"] == "staging"
    assert payload["prompt_tokens"] == 500.0
    assert len(client.metrics) == 1


def test_sync_agent_events_posts_tool_attempts_and_clears_queue():
    client = DriftGuardClient(
        api_key="agent-key",
        project_name="coding-agent",
        base_url="http://localhost:8000",
    )
    client.capture_agent_event(
        task_id="fix-tests",
        tool_name="terminal",
        attempt=2,
        status="failed",
        total_tokens=2200,
    )

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    with patch("httpx.Client") as mock_httpx:
        mock_http_instance = mock_httpx.return_value.__enter__.return_value
        mock_http_instance.post.return_value = mock_response
        result = client.sync_agent_events("coding-agent")

    assert result["synced"] == 1
    assert not client.agent_events
    request = mock_http_instance.post.call_args
    assert request.args[0].endswith("/agent-events/coding-agent")
    assert request.kwargs["headers"]["X-API-Key"] == "agent-key"
