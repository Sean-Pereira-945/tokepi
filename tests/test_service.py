import pytest

from driftguard.service import DriftGuardService


def test_service_creates_project_and_alerts():
    service = DriftGuardService()
    project = service.create_project("p-1", "demo-app", environment="prod")

    alert = {"severity": "warning", "message": "retrieval drift detected", "saved_tokens": 0.18}
    service.add_alert(project.project_id, alert)

    saved = service.get_project(project.project_id)

    assert saved.name == "demo-app"
    assert len(saved.alerts) == 1
    assert saved.alerts[0]["message"] == "retrieval drift detected"


def test_service_isolates_projects_per_customer_account():
    service = DriftGuardService()
    service.create_account("acct-a", "Acme")
    service.create_account("acct-b", "Beta")

    service.create_project("p-1", "alpha-app", environment="prod", account_id="acct-a")
    service.create_project("p-2", "beta-app", environment="prod", account_id="acct-b")

    assert [project.project_id for project in service.list_projects(account_id="acct-a")] == ["p-1"]
    assert service.get_project("p-1", account_id="acct-a").name == "alpha-app"

    with pytest.raises(KeyError):
        service.get_project("p-1", account_id="acct-b")


def test_service_creates_and_validates_session_tokens():
    service = DriftGuardService()
    service.create_account("acct-s", "Session Co")

    token = service.create_session("acct-s")

    assert service.get_account_for_session(token) == "acct-s"
    with pytest.raises(KeyError):
        service.get_account_for_session("bad-token")
