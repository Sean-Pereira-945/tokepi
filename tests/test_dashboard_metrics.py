"""Regression coverage for the dashboard metrics/filter contract."""

from fastapi.testclient import TestClient

from driftguard.routes import app


client = TestClient(app)


def make_project(project_id: str, environment: str = "prod") -> dict:
    response = client.post(
        "/projects",
        json={
            "project_id": project_id,
            "name": f"Metrics {project_id}",
            "environment": environment,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def add_event(project_id: str, api_key: str, environment: str, prompt_tokens: float) -> None:
    response = client.post(
        f"/events/{project_id}",
        json={
            "prompt_tokens": prompt_tokens,
            "retrieval_score": 0.8,
            "context_length": 2200,
            "response_quality": 0.9,
            "environment": environment,
        },
        headers={"X-API-Key": api_key},
    )
    assert response.status_code == 200, response.text


def test_metrics_returns_authoritative_count_and_averages():
    project = make_project("metrics-authoritative")
    for index in range(3):
        add_event(project["project_id"], project["api_key"], "prod", 1000 + index * 100)

    response = client.get(
        f"/projects/{project['project_id']}/metrics",
        headers={"X-API-Key": project["api_key"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_events"] == 3
    assert payload["retrieval_score"] == 0.8
    assert payload["response_quality"] == 0.9
    assert payload["filters"] == {"environment": "all", "severity": "all", "time_range": "all"}
    assert payload["last_updated"]


def test_environment_filter_applies_to_events_and_metrics():
    project = make_project("metrics-environments")
    add_event(project["project_id"], project["api_key"], "prod", 1000)
    add_event(project["project_id"], project["api_key"], "staging", 2000)

    events = client.get(
        f"/events/{project['project_id']}?environment=staging",
        headers={"X-API-Key": project["api_key"]},
    )
    metrics = client.get(
        f"/projects/{project['project_id']}/metrics?environment=staging",
        headers={"X-API-Key": project["api_key"]},
    )

    assert events.status_code == 200
    assert len(events.json()) == 1
    assert events.json()[0]["environment"] == "staging"
    assert metrics.status_code == 200
    assert metrics.json()["total_events"] == 1
    assert metrics.json()["filters"]["environment"] == "staging"


def test_alert_severity_filter_and_alert_metadata():
    project = make_project("metrics-alerts")
    for severity, saved_tokens in (("warning", 100.0), ("critical", 250.0)):
        response = client.post(
            "/alerts",
            json={
                "project_id": project["project_id"],
                "severity": severity,
                "message": f"{severity} alert",
                "saved_tokens": saved_tokens,
                "environment": "prod",
            },
        )
        assert response.status_code == 200, response.text

    alerts = client.get(
        f"/alerts/{project['project_id']}?severity=critical",
        headers={"X-API-Key": project["api_key"]},
    )
    metrics = client.get(
        f"/projects/{project['project_id']}/metrics?severity=critical",
        headers={"X-API-Key": project["api_key"]},
    )

    assert alerts.status_code == 200
    assert len(alerts.json()) == 1
    assert alerts.json()[0]["severity"] == "critical"
    assert metrics.status_code == 200
    assert metrics.json()["alert_count"] == 1
    assert metrics.json()["critical_count"] == 1
    assert metrics.json()["warning_count"] == 0
    assert metrics.json()["saved_tokens"] == 250.0


def test_summary_remains_backward_compatible_and_supports_filters():
    project = make_project("metrics-summary")
    add_event(project["project_id"], project["api_key"], "prod", 1200)

    response = client.get(
        f"/projects/{project['project_id']}/summary?environment=prod&time_range=24h",
        headers={"X-API-Key": project["api_key"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == project["project_id"]
    assert payload["aggregates"]["total_events"] == 1
    assert payload["aggregates"]["filters"]["time_range"] == "24h"


def test_metrics_rejects_unknown_filter_values():
    project = make_project("metrics-validation")
    for query in ("environment=production", "severity=info", "time_range=year"):
        response = client.get(
            f"/projects/{project['project_id']}/metrics?{query}",
            headers={"X-API-Key": project["api_key"]},
        )
        assert response.status_code == 422, response.text
