from driftguard.analytics import build_project_snapshot


def test_project_snapshot_reports_health_and_root_cause_summary():
    alerts = [
        {"severity": "critical", "message": "retrieval drift detected", "saved_tokens": 0.4},
        {"severity": "warning", "message": "prompt inflation detected", "saved_tokens": 0.2},
    ]

    snapshot = build_project_snapshot("proj-a", alerts, environment="prod")

    assert snapshot["project_id"] == "proj-a"
    assert snapshot["environment"] == "prod"
    assert snapshot["alert_count"] == 2
    assert snapshot["critical_count"] == 1
    assert snapshot["warning_count"] == 1
    assert snapshot["status"] == "critical"
    assert snapshot["estimated_token_savings"] == 0.6
    assert "retrieval" in snapshot["root_cause_summary"] or "prompt" in snapshot["root_cause_summary"]
