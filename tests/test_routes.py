from fastapi.testclient import TestClient

from driftguard.routes import app


client = TestClient(app)


def test_routes_health_and_create_project_work():
    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"

    create_response = client.post(
        "/projects",
        json={"project_id": "proj-1", "name": "demo-project", "environment": "prod"},
    )
    assert create_response.status_code == 200
    assert create_response.json()["project_id"] == "proj-1"


def test_routes_alert_flow_commits_to_project():
    client.post(
        "/projects",
        json={"project_id": "proj-2", "name": "alert-project", "environment": "staging"},
    )

    alert_response = client.post(
        "/alerts",
        json={
            "project_id": "proj-2",
            "severity": "critical",
            "message": "retrieval drift detected",
            "saved_tokens": 0.28,
        },
    )
    assert alert_response.status_code == 200
    assert alert_response.json()["message"] == "retrieval drift detected"

    project_response = client.get("/projects/proj-2")
    assert project_response.status_code == 200
    assert len(project_response.json()["alerts"]) == 1


def test_routes_dashboard_summary_returns_product_overview():
    client.post(
        "/projects",
        json={"project_id": "proj-3", "name": "dashboard-project", "environment": "prod"},
    )

    client.post(
        "/alerts",
        json={
            "project_id": "proj-3",
            "severity": "warning",
            "message": "prompt inflation detected",
            "saved_tokens": 0.2,
        },
    )

    summary_response = client.get("/projects/proj-3/summary")
    assert summary_response.status_code == 200
    payload = summary_response.json()
    assert payload["project_id"] == "proj-3"
    assert payload["environment"] == "prod"
    assert payload["alert_count"] == 1
    assert payload["status"] in {"warning", "critical", "stable"}
    assert payload["estimated_token_savings"] == 0.2
    assert "prompt" in payload["root_cause_summary"].lower()


def test_routes_enforce_account_scoped_project_access():
    service = __import__("driftguard.routes", fromlist=["service"]).service
    service.create_account("acct-c", "Customer C")
    service.create_account("acct-d", "Customer D")
    token = service.create_session("acct-c")
    other_token = service.create_session("acct-d")

    client.post(
        "/projects",
        json={"project_id": "proj-4", "name": "secure-project", "environment": "prod"},
        headers={"Authorization": f"Bearer {token}"},
    )

    list_response = client.get("/projects", headers={"Authorization": f"Bearer {token}"})
    assert list_response.status_code == 200
    assert [item["project_id"] for item in list_response.json()] == ["proj-4"]

    denied_response = client.get(
        "/projects/proj-4",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert denied_response.status_code == 401

    other_response = client.get(
        "/projects/proj-4",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert other_response.status_code == 404
