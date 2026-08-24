"""Tests for the new routes added in v0.3.0:
- Account registration
- Auth session creation
- Event ingestion (API key auth)
- Event listing
- Policy CRUD
- Project deletion
- Input validation rejection
"""
from fastapi.testclient import TestClient

from driftguard.routes import app, service

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(project_id: str, name: str = "test-app", env: str = "prod") -> dict:
    """Create a project and return the full response JSON (includes api_key)."""
    resp = client.post(
        "/projects",
        json={"project_id": project_id, "name": name, "environment": env},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Account management
# ---------------------------------------------------------------------------

def test_create_account_returns_token():
    resp = client.post("/accounts", json={"name": "Acme Corp"})
    assert resp.status_code == 200
    data = resp.json()
    assert "account_id" in data
    assert data["account_id"].startswith("acct-")
    assert "token" in data
    assert len(data["token"]) > 0


def test_get_current_account_requires_valid_token():
    # No auth → falls back to default account, which exists
    resp = client.get("/accounts/me")
    assert resp.status_code == 200
    assert resp.json()["account_id"] == "default"


def test_get_current_account_with_bad_token_returns_401():
    resp = client.get("/accounts/me", headers={"Authorization": "Bearer bad-token"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Auth / session
# ---------------------------------------------------------------------------

def test_create_session_for_existing_account():
    service.create_account("acct-sess-test", "Session Test Co")
    resp = client.post("/auth/session?account_id=acct-sess-test")
    assert resp.status_code == 200
    assert "token" in resp.json()


def test_create_session_for_missing_account_returns_404():
    resp = client.post("/auth/session?account_id=no-such-account")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Project creation — validation
# ---------------------------------------------------------------------------

def test_invalid_project_id_rejected():
    resp = client.post(
        "/projects",
        json={"project_id": "bad id with spaces!", "name": "test", "environment": "prod"},
    )
    assert resp.status_code == 422


def test_invalid_environment_rejected():
    resp = client.post(
        "/projects",
        json={"project_id": "p-env-test", "name": "test", "environment": "production"},
    )
    assert resp.status_code == 422


def test_empty_name_rejected():
    resp = client.post(
        "/projects",
        json={"project_id": "p-name-test", "name": "   ", "environment": "prod"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Event ingestion
# ---------------------------------------------------------------------------

def test_event_ingestion_with_valid_api_key():
    proj = _make_project("p-ingest-1", "ingest-app")
    api_key = proj["api_key"]

    resp = client.post(
        f"/events/{proj['project_id']}",
        json={
            "prompt_tokens": 1200.0,
            "retrieval_score": 0.75,
            "context_length": 3000.0,
            "response_quality": 0.9,
            "environment": "prod",
        },
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ingested"
    assert data["project_id"] == proj["project_id"]


def test_event_ingestion_rejects_missing_api_key():
    proj = _make_project("p-ingest-2", "ingest-app2")
    resp = client.post(
        f"/events/{proj['project_id']}",
        json={"prompt_tokens": 500.0},
    )
    assert resp.status_code == 401


def test_event_ingestion_rejects_wrong_project_api_key():
    proj_a = _make_project("p-ingest-3", "app-a")
    proj_b = _make_project("p-ingest-4", "app-b")
    resp = client.post(
        f"/events/{proj_b['project_id']}",
        json={"prompt_tokens": 500.0},
        headers={"X-API-Key": proj_a["api_key"]},
    )
    assert resp.status_code == 403


def test_dashboard_event_ingestion_uses_account_session():
    proj = _make_project("p-dashboard-ingest", "dashboard-app")
    resp = client.post(
        f"/projects/{proj['project_id']}/events",
        json={"prompt_tokens": 900.0, "environment": "prod"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ingested"


def test_project_api_key_scopes_dashboard_data():
    project_a = _make_project("p-key-dashboard-a", "key-dashboard-a")
    project_b = _make_project("p-key-dashboard-b", "key-dashboard-b")
    api_key = project_a["api_key"]

    event_response = client.post(
        f"/events/{project_a['project_id']}",
        json={"prompt_tokens": 1200.0},
        headers={"X-API-Key": api_key},
    )
    assert event_response.status_code == 200

    own_events = client.get(
        f"/events/{project_a['project_id']}",
        headers={"X-API-Key": api_key},
    )
    assert own_events.status_code == 200
    assert len(own_events.json()) == 1

    other_events = client.get(
        f"/events/{project_b['project_id']}",
        headers={"X-API-Key": api_key},
    )
    assert other_events.status_code == 403

    scoped_projects = client.get("/projects", headers={"X-API-Key": api_key})
    assert scoped_projects.status_code == 200
    assert [item["project_id"] for item in scoped_projects.json()] == [project_a["project_id"]]


def test_agent_diagnosis_identifies_repeated_tool_failure_and_wasted_tokens():
    project = _make_project("p-agent-diagnosis", "agent-diagnosis")
    api_key = project["api_key"]
    event = {
        "task_id": "fix-tests",
        "trace_id": "trace-1",
        "agent_name": "coding-agent",
        "tool_name": "terminal",
        "status": "failed",
        "attempt": 1,
        "error_type": "command_failed",
        "error_message": "pytest exited with code 1",
        "total_tokens": 2200,
    }

    for attempt in range(1, 4):
        event["attempt"] = attempt
        response = client.post(
            f"/agent-events/{project['project_id']}",
            json=event,
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200

    diagnosis = client.get(
        f"/projects/{project['project_id']}/agent-diagnosis",
        headers={"X-API-Key": api_key},
    )
    assert diagnosis.status_code == 200
    payload = diagnosis.json()
    assert payload["status"] == "critical"
    assert payload["task_blocked"] is True
    assert payload["blocking_tool"] == "terminal"
    assert payload["failure_count"] == 3
    assert payload["repeated_attempts"] == 2
    assert payload["wasted_tokens"] == 6600.0
    assert "terminal" in payload["diagnosis"]


def test_event_ingestion_score_validation():
    proj = _make_project("p-ingest-5", "ingest-app5")
    resp = client.post(
        f"/events/{proj['project_id']}",
        json={"retrieval_score": 1.5},   # > 1.0 — invalid
        headers={"X-API-Key": proj["api_key"]},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Event listing
# ---------------------------------------------------------------------------

def test_list_events_returns_ingested_events():
    proj = _make_project("p-list-events", "list-events-app")
    api_key = proj["api_key"]

    # Ingest 3 events
    for i in range(3):
        client.post(
            f"/events/{proj['project_id']}",
            json={"prompt_tokens": float(1000 + i * 500), "retrieval_score": 0.8},
            headers={"X-API-Key": api_key},
        )

    resp = client.get(f"/events/{proj['project_id']}")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 3


def test_list_events_limit_clamped():
    proj = _make_project("p-list-limit", "limit-app")
    resp = client.get(f"/events/{proj['project_id']}?limit=9999")
    assert resp.status_code == 200  # no crash — clamped to 100 internally


# ---------------------------------------------------------------------------
# Policy management
# ---------------------------------------------------------------------------

def test_get_default_policy():
    proj = _make_project("p-policy-default", "policy-app")
    resp = client.get(f"/projects/{proj['project_id']}/policy")
    assert resp.status_code == 200
    policy = resp.json()
    assert policy["prompt_token_limit"] == 3000.0
    assert policy["retrieval_score_floor"] == 0.5


def test_update_policy_and_fetch():
    proj = _make_project("p-policy-update", "policy-app2")
    resp = client.put(
        f"/projects/{proj['project_id']}/policy",
        json={"prompt_token_limit": 2000.0, "retrieval_score_floor": 0.65},
    )
    assert resp.status_code == 200
    policy = resp.json()
    assert policy["prompt_token_limit"] == 2000.0
    assert policy["retrieval_score_floor"] == 0.65
    # Other fields should remain at defaults
    assert policy["context_length_limit"] == 4000.0


def test_policy_floor_validation():
    proj = _make_project("p-policy-val", "policy-val-app")
    resp = client.put(
        f"/projects/{proj['project_id']}/policy",
        json={"retrieval_score_floor": 1.5},  # > 1.0 — invalid
    )
    assert resp.status_code == 422


def test_sdk_can_fetch_policy_via_api_key():
    proj = _make_project("p-policy-sdk", "sdk-policy-app")
    resp = client.get(
        f"/projects/{proj['project_id']}/policy",
        headers={"X-API-Key": proj["api_key"]},
    )
    assert resp.status_code == 200
    assert "prompt_token_limit" in resp.json()


# ---------------------------------------------------------------------------
# Project deletion
# ---------------------------------------------------------------------------

def test_delete_project_removes_it():
    proj = _make_project("p-delete-me", "delete-app")
    resp = client.delete(f"/projects/{proj['project_id']}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

    get_resp = client.get(f"/projects/{proj['project_id']}")
    assert get_resp.status_code == 404


def test_delete_nonexistent_project_returns_404():
    resp = client.delete("/projects/does-not-exist")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Alert validation
# ---------------------------------------------------------------------------

def test_alert_invalid_severity_rejected():
    _make_project("p-alert-val")
    resp = client.post(
        "/alerts",
        json={
            "project_id": "p-alert-val",
            "severity": "unknown",
            "message": "test",
            "saved_tokens": 0.1,
        },
    )
    assert resp.status_code == 422


def test_alert_negative_saved_tokens_rejected():
    _make_project("p-alert-tokens")
    resp = client.post(
        "/alerts",
        json={
            "project_id": "p-alert-tokens",
            "severity": "warning",
            "message": "test",
            "saved_tokens": -0.5,
        },
    )
    assert resp.status_code == 422


def test_dashboard_root_serves_html():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "DriftGuard" in resp.text
    assert "<html" in resp.text

