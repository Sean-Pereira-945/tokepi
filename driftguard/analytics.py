"""Project-level alert aggregation used by the hosted dashboard."""

from __future__ import annotations

from typing import Any


def build_project_snapshot(project_id: str, alerts: list[dict[str, Any]], environment: str = "prod") -> dict[str, Any]:
    """Build a product-facing analytics snapshot for a project's current health."""
    if not alerts:
        return {
            "project_id": project_id,
            "environment": environment,
            "status": "stable",
            "alert_count": 0,
            "critical_count": 0,
            "warning_count": 0,
            "estimated_token_savings": 0.0,
            "root_cause_summary": "No active drift signals detected.",
        }

    critical = sum(1 for alert in alerts if str(alert.get("severity", "")).lower() == "critical")
    warning = sum(1 for alert in alerts if str(alert.get("severity", "")).lower() == "warning")
    savings = round(sum(float(alert.get("saved_tokens", 0.0)) for alert in alerts), 3)
    cause_points = list({
        part.strip()
        for alert in alerts
        for part in str(alert.get("message", "")).split(" ")
        if len(part) > 3
    })[:5]

    return {
        "project_id": project_id,
        "environment": environment,
        "status": "critical" if critical > 0 else "warning" if warning > 0 else "stable",
        "alert_count": len(alerts),
        "critical_count": critical,
        "warning_count": warning,
        "estimated_token_savings": savings,
        "root_cause_summary": ", ".join(cause_points) if cause_points else "No root cause signals available.",
    }
