from driftguard.service import DriftGuardService


def test_service_persists_projects_and_alerts_across_instances(tmp_path):
    db_path = tmp_path / "driftguard.sqlite3"
    first = DriftGuardService(database_url=f"sqlite:///{db_path}")
    first.create_account("acct-persist", "Persist Co")
    first.create_project("p-100", "persisted-app", environment="prod", account_id="acct-persist")
    first.add_alert(
        "p-100",
        {"severity": "critical", "message": "retrieval drift detected", "saved_tokens": 0.44},
        account_id="acct-persist",
    )

    second = DriftGuardService(database_url=f"sqlite:///{db_path}")
    project = second.get_project("p-100", account_id="acct-persist")

    assert project.name == "persisted-app"
    assert project.environment == "prod"
    assert len(project.alerts) == 1
    assert project.alerts[0]["message"] == "retrieval drift detected"
