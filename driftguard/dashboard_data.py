from __future__ import annotations

from typing import Any


def build_dashboard_summary(project_id: str, alerts: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a simple summary payload for a hosted dashboard."""
    if not alerts:
        return {
            "project_id": project_id,
            "alert_count": 0,
            "critical_alerts": 0,
            "warning_alerts": 0,
            "estimated_savings": 0.0,
            "status": "stable",
            "summary": "No active drift alerts detected.",
        }

    critical_alerts = sum(1 for alert in alerts if str(alert.get("severity", "")).lower() == "critical")
    warning_alerts = sum(1 for alert in alerts if str(alert.get("severity", "")).lower() == "warning")
    estimated_savings = round(sum(float(alert.get("saved_tokens", 0.0)) for alert in alerts), 3)

    return {
        "project_id": project_id,
        "alert_count": len(alerts),
        "critical_alerts": critical_alerts,
        "warning_alerts": warning_alerts,
        "estimated_savings": estimated_savings,
        "status": "critical" if critical_alerts else "warning" if warning_alerts else "stable",
        "summary": (
            "Active drift monitoring detected. "
            f"{critical_alerts} critical alerts and {warning_alerts} warnings are currently visible."
        ),
    }
