from datetime import datetime, timedelta, timezone

CRITICAL = {"prompt_tokens": 5000, "context_length": 6000, "retrieval_score": 0.2, "response_quality": 0.5}


def test_single_event_is_scored_on_ingest(client, project):
    pid = project["project_id"]
    response = client.post(f"/events/{pid}", json=CRITICAL, headers=project["key_headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ingested" and body["severity"] == "critical" and body["risk_score"] == 1.0
    stored = client.get(f"/projects/{pid}/events", headers=project["key_headers"]).json()[0]
    assert stored["severity"] == "critical"
    assert "retrieval degradation" in stored["root_cause"]


def test_ingest_requires_matching_api_key(client, account, project):
    pid = project["project_id"]
    assert client.post(f"/events/{pid}", json={"prompt_tokens": 1}).status_code == 401
    assert (
        client.post(f"/events/{pid}", json={"prompt_tokens": 1}, headers={"X-API-Key": "dg_live_invalid"}).status_code
        == 401
    )
    assert client.post(f"/events/{pid}", json={"prompt_tokens": 1}, headers=account["headers"]).status_code == 401


def test_batch_ingest(client, project):
    pid = project["project_id"]
    events = [{"prompt_tokens": 100 * i, "retrieval_score": 0.9} for i in range(10)] + [CRITICAL]
    response = client.post(f"/events/{pid}/batch", json={"events": events}, headers=project["key_headers"])
    assert response.json() == {"project_id": pid, "ingested": 11, "critical": 1}
    assert len(client.get(f"/projects/{pid}/events?limit=500", headers=project["key_headers"]).json()) == 11


def test_batch_limits(client, project):
    pid = project["project_id"]
    h = project["key_headers"]
    assert client.post(f"/events/{pid}/batch", json={"events": []}, headers=h).status_code == 422
    assert client.post(f"/events/{pid}/batch", json={"events": [{}] * 501}, headers=h).status_code == 422


def test_event_validation(client, project):
    pid = project["project_id"]
    h = project["key_headers"]
    for bad in (
        {"retrieval_score": 1.5},
        {"prompt_tokens": -1},
        {"environment": "production"},
        {"metadata": {f"k{i}": i for i in range(40)}},
    ):
        assert client.post(f"/events/{pid}", json=bad, headers=h).status_code == 422, bad


def test_critical_drift_raises_one_alert_per_cooldown(client, project):
    pid = project["project_id"]
    for _ in range(3):
        client.post(f"/events/{pid}", json=CRITICAL, headers=project["key_headers"])
    alerts = client.get(f"/projects/{pid}/alerts", headers=project["key_headers"]).json()
    assert len(alerts) == 1
    assert alerts[0]["source"] == "drift" and alerts[0]["severity"] == "critical"
    assert alerts[0]["saved_tokens"] > 0


def test_occurred_at_is_kept_but_future_times_are_clamped(client, project):
    pid = project["project_id"]
    past = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    client.post(f"/events/{pid}", json={"prompt_tokens": 1, "occurred_at": past}, headers=project["key_headers"])
    client.post(f"/events/{pid}", json={"prompt_tokens": 2, "occurred_at": future}, headers=project["key_headers"])
    last_hour = client.get(f"/projects/{pid}/events?time_range=1h", headers=project["key_headers"]).json()
    assert [e["prompt_tokens"] for e in last_hour] == [2]
    assert datetime.fromisoformat(last_hour[0]["created_at"].replace("Z", "+00:00")) <= datetime.now(timezone.utc)


def test_metadata_is_stored_and_scrubbed(client, project):
    pid = project["project_id"]
    client.post(
        f"/events/{pid}",
        json={"prompt_tokens": 1, "metadata": {"model": "gpt-x", "user": "a@b.com"}},
        headers=project["key_headers"],
    )
    event = client.get(f"/projects/{pid}/events", headers=project["key_headers"]).json()[0]
    assert event["metadata"] == {"model": "gpt-x", "user": "[EMAIL REDACTED]"}


def test_agent_error_messages_are_scrubbed_and_truncated(client, project):
    pid = project["project_id"]
    secret = "sk-" + "a" * 40
    client.post(
        f"/agent-events/{pid}",
        json={
            "task_id": "t",
            "tool_name": "terminal",
            "status": "FAILED",
            "error_message": f"auth failed with {secret} " + "x" * 5000,
        },
        headers=project["key_headers"],
    )
    event = client.get(f"/projects/{pid}/agent-events", headers=project["key_headers"]).json()[0]
    assert secret not in event["error_message"]
    assert "[API KEY REDACTED]" in event["error_message"]
    assert event["error_message"].endswith("[truncated]")
    assert event["status"] == "failed"


def test_dashboard_test_event_requires_session(client, account, project):
    pid = project["project_id"]
    assert client.post(f"/projects/{pid}/events", json=CRITICAL, headers=project["key_headers"]).status_code == 401
    response = client.post(f"/projects/{pid}/events", json=CRITICAL, headers=account["headers"])
    assert response.status_code == 200 and response.json()["severity"] == "critical"


def test_ingest_is_rate_limited_per_key(settings):
    from dataclasses import replace

    from fastapi.testclient import TestClient
    from helpers import make_project, register

    from driftguard.server import create_app

    with TestClient(create_app(replace(settings, ingest_rate_limit_per_minute=2))) as client:
        account = register(client)
        a, b = make_project(client, account), make_project(client, account)
        codes = [
            client.post(f"/events/{a['project_id']}", json={}, headers=a["key_headers"]).status_code for _ in range(3)
        ]
        other = client.post(f"/events/{b['project_id']}", json={}, headers=b["key_headers"]).status_code
    assert codes == [200, 200, 429]
    assert other == 200
