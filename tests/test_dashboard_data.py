from driftguard.dashboard_data import build_dashboard_summary


def test_dashboard_summary_produces_alert_metrics():
    alerts = [
        {"severity": "critical", "saved_tokens": 0.32},
        {"severity": "warning", "saved_tokens": 0.18},
    ]

    summary = build_dashboard_summary("proj-1", alerts)

    assert summary["project_id"] == "proj-1"
    assert summary["alert_count"] == 2
    assert summary["critical_alerts"] == 1
    assert summary["warning_alerts"] == 1
    assert summary["status"] == "critical"
    assert summary["estimated_savings"] == 0.5
