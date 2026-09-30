def ingest(client, project, **metrics):
    response = client.post(f"/events/{project['project_id']}", json=metrics, headers=project["key_headers"])
    assert response.status_code == 200, response.text


def agent_event(client, project, **event):
    body = {"task_id": "fix-tests", "tool_name": "terminal", "status": "failed", "total_tokens": 2200, **event}
    response = client.post(f"/agent-events/{project['project_id']}", json=body, headers=project["key_headers"])
    assert response.status_code == 200, response.text


def test_summary_aggregates_and_violation_rates(client, project):
    ingest(client, project, prompt_tokens=1000, context_length=2000, retrieval_score=0.8, response_quality=0.9)
    ingest(client, project, prompt_tokens=5000, context_length=2000, retrieval_score=0.4, response_quality=0.9)
    summary = client.get(f"/projects/{project['project_id']}/summary", headers=project["key_headers"]).json()
    assert summary["total_events"] == 2
    assert summary["averages"]["prompt_tokens"] == 3000
    assert summary["averages"]["retrieval_score"] == 0.6
    assert summary["violation_rates"]["prompt_token_limit"] == 0.5
    assert summary["violation_rates"]["response_quality_floor"] == 0.0
    assert summary["events_by_severity"] == {"stable": 1, "warning": 1}
    assert summary["top_root_causes"][0]["count"] == 1
    assert summary["last_updated"].endswith("Z")
    assert summary["filters"] == {"environment": "all", "severity": "all", "time_range": "all"}


def test_empty_summary_has_no_invented_numbers(client, project):
    summary = client.get(f"/projects/{project['project_id']}/summary", headers=project["key_headers"]).json()
    assert summary["total_events"] == 0
    assert summary["averages"]["retrieval_score"] is None
    assert summary["status"] == "stable"
    assert summary["last_updated"] is None


def test_environment_filter(client, project):
    ingest(client, project, prompt_tokens=1, environment="prod")
    ingest(client, project, prompt_tokens=2, environment="staging")
    pid, h = project["project_id"], project["key_headers"]
    staging = client.get(f"/projects/{pid}/events?environment=staging", headers=h).json()
    assert [e["prompt_tokens"] for e in staging] == [2]
    assert client.get(f"/projects/{pid}/summary?environment=staging", headers=h).json()["total_events"] == 1


def test_filter_values_are_validated(client, project):
    pid, h = project["project_id"], project["key_headers"]
    for query in ("environment=production", "severity=info", "time_range=year"):
        assert client.get(f"/projects/{pid}/summary?{query}", headers=h).status_code == 422, query


def test_event_pagination(client, project):
    for i in range(5):
        ingest(client, project, prompt_tokens=i)
    pid, h = project["project_id"], project["key_headers"]
    page1 = client.get(f"/projects/{pid}/events?limit=2", headers=h).json()
    page2 = client.get(f"/projects/{pid}/events?limit=2&before_id={page1[-1]['id']}", headers=h).json()
    assert [e["prompt_tokens"] for e in page1 + page2] == [4, 3, 2, 1]
    assert client.get(f"/projects/{pid}/events?limit=9999", headers=h).status_code == 422


def test_manual_alert_lifecycle(client, account, project):
    pid = project["project_id"]
    created = client.post(
        f"/projects/{pid}/alerts",
        json={"severity": "warning", "message": "check retrieval", "saved_tokens": 120},
        headers=account["headers"],
    )
    assert created.status_code == 201
    alert = created.json()
    assert alert["source"] == "manual" and alert["resolved"] is False and alert["environment"] == "prod"

    summary = client.get(f"/projects/{pid}/summary", headers=account["headers"]).json()
    assert (summary["open_alerts"], summary["warning_alerts"], summary["saved_tokens"]) == (1, 1, 120)

    resolved = client.patch(
        f"/projects/{pid}/alerts/{alert['id']}", json={"resolved": True}, headers=account["headers"]
    ).json()
    assert resolved["resolved"] is True and resolved["resolved_at"]
    assert client.get(f"/projects/{pid}/summary", headers=account["headers"]).json()["open_alerts"] == 0
    assert client.get(f"/projects/{pid}/alerts?resolved=false", headers=account["headers"]).json() == []
    assert (
        client.patch(f"/projects/{pid}/alerts/99999", json={"resolved": True}, headers=account["headers"]).status_code
        == 404
    )


def test_alert_validation(client, account, project):
    pid, h = project["project_id"], account["headers"]
    assert (
        client.post(f"/projects/{pid}/alerts", json={"severity": "unknown", "message": "x"}, headers=h).status_code
        == 422
    )
    assert (
        client.post(
            f"/projects/{pid}/alerts", json={"severity": "warning", "message": "x", "saved_tokens": -1}, headers=h
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/projects/{pid}/alerts", json={"severity": "warning", "message": "x"}, headers=project["key_headers"]
        ).status_code
        == 401
    )


def test_agent_diagnosis_end_to_end(client, project):
    for attempt in range(1, 4):
        agent_event(
            client, project, attempt=attempt, error_type="command_failed", error_message="pytest exited with code 1"
        )
    diagnosis = client.get(f"/projects/{project['project_id']}/agent-diagnosis", headers=project["key_headers"]).json()
    assert diagnosis["status"] == "critical" and diagnosis["task_blocked"] is True
    assert diagnosis["blocking_tool"] == "terminal"
    assert (diagnosis["failure_count"], diagnosis["repeated_attempts"], diagnosis["wasted_tokens"]) == (3, 2, 6600)
    assert diagnosis["tasks"][0]["task_id"] == "fix-tests"


def test_blocked_task_raises_alert_and_recovery_resolves_it(client, project):
    pid, h = project["project_id"], project["key_headers"]
    for _ in range(3):
        agent_event(client, project)
    agent_event(client, project)  # a fourth failure must not duplicate the alert
    alerts = client.get(f"/projects/{pid}/alerts?resolved=false", headers=h).json()
    assert len(alerts) == 1
    assert alerts[0]["source"] == "agent" and alerts[0]["task_id"] == "fix-tests"
    assert alerts[0]["saved_tokens"] == 8800

    agent_event(client, project, status="success", total_tokens=500)
    assert client.get(f"/projects/{pid}/alerts?resolved=false", headers=h).json() == []
    assert client.get(f"/projects/{pid}/alerts?resolved=true", headers=h).json()[0]["task_id"] == "fix-tests"


def test_agent_batch_and_task_filter(client, project):
    pid, h = project["project_id"], project["key_headers"]
    events = [{"task_id": f"task-{i % 2}", "tool_name": "browser", "status": "success"} for i in range(6)]
    assert client.post(f"/agent-events/{pid}/batch", json={"events": events}, headers=h).json()["ingested"] == 6
    assert len(client.get(f"/projects/{pid}/agent-events?task_id=task-1", headers=h).json()) == 3


def test_blocked_threshold_follows_project_policy(client, account, project):
    pid = project["project_id"]
    client.put(f"/projects/{pid}/policy", json={"blocked_after_failures": 5}, headers=account["headers"])
    for _ in range(3):
        agent_event(client, project)
    diagnosis = client.get(f"/projects/{pid}/agent-diagnosis", headers=account["headers"]).json()
    assert diagnosis["status"] == "warning"
    assert client.get(f"/projects/{pid}/alerts", headers=account["headers"]).json() == []


def test_security_headers_and_fallback_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "DriftGuard server is running" in response.text
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_built_dashboard_is_served(settings, tmp_path):
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from driftguard.server import create_app

    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html><title>DriftGuard</title></html>")
    (static / "assets" / "app.js").write_text("console.log(1)")
    with TestClient(create_app(replace(settings, static_dir=static))) as client:
        assert "<title>DriftGuard</title>" in client.get("/").text
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/health").json()["status"] == "ok"
