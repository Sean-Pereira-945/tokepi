from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import func, select

from driftguard.server.db import agent_events, alerts, events
from driftguard.server.retention import scrub_pii


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Contact me at test@example.com.", "Contact me at [EMAIL REDACTED]."),
        ("My SSN is 123-45-6789.", "My SSN is [SSN REDACTED]."),
        ("Card 4111 1111 1111 1111 please", "Card [CREDIT CARD REDACTED] please"),
        ("OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz0123", "OPENAI_API_KEY=[API KEY REDACTED]"),
        ("token ghp_abcdefghijklmnopqrstuvwxyz0123456789", "token [GITHUB TOKEN REDACTED]"),
        ("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig", "Authorization: Bearer [TOKEN REDACTED]"),
        ("aws AKIAABCDEFGHIJKLMNOP done", "aws [AWS KEY REDACTED] done"),
    ],
)
def test_scrub_pii_redacts(text, expected):
    assert scrub_pii(text) == expected


def test_scrub_pii_keeps_ordinary_numbers():
    text = "processed 1234567890123 tokens in run 20260930"  # not Luhn-valid
    assert scrub_pii(text) == text
    assert scrub_pii("") == ""


def test_prune_removes_old_rows_only(app, project):
    service = app.state.service
    pid = project["project_id"]
    old = datetime.now(timezone.utc) - timedelta(days=40)
    recent = datetime.now(timezone.utc) - timedelta(days=5)
    with service.engine.begin() as conn:
        conn.execute(
            events.insert(), [{"project_id": pid, "created_at": old}, {"project_id": pid, "created_at": recent}]
        )
        conn.execute(
            agent_events.insert(),
            [
                {"project_id": pid, "task_id": "t", "tool_name": "x", "status": "failed", "created_at": old},
            ],
        )
        conn.execute(
            alerts.insert(),
            [
                {
                    "project_id": pid,
                    "severity": "warning",
                    "message": "old resolved",
                    "resolved": True,
                    "created_at": old,
                },
                {"project_id": pid, "severity": "warning", "message": "old open", "resolved": False, "created_at": old},
            ],
        )

    assert service.prune(30) == {"events": 1, "agent_events": 1, "alerts": 1}
    with service.engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(events)).scalar() == 1
        # Unresolved alerts are kept regardless of age.
        assert conn.execute(select(alerts.c.message)).scalars().all() == ["old open"]


def test_retention_loop_runs_on_startup(settings):
    import time
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from driftguard.server import create_app

    app = create_app(replace(settings, retention_days=30, retention_interval_hours=24))
    calls = []
    app.state.service.prune = lambda days: calls.append(days) or {}
    with TestClient(app):
        for _ in range(50):
            if calls:
                break
            time.sleep(0.02)
    assert calls == [30]
