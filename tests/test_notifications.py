from unittest.mock import MagicMock, patch

import httpx

from driftguard.server.notifications import Notifier


def test_disabled_without_destinations():
    notifier = Notifier()
    assert notifier.enabled is False
    assert notifier.dispatch("p", {"severity": "critical", "message": "x"}) is False


def test_only_critical_alerts_are_sent():
    notifier = Notifier(slack_webhook_url="https://hooks.slack.test/x")
    with patch("httpx.Client.post") as post:
        assert notifier.dispatch("p", {"severity": "warning", "message": "x"}) is False
        post.assert_not_called()


def test_slack_and_webhook_payloads():
    notifier = Notifier(slack_webhook_url="https://hooks.slack.test/x", alert_webhook_url="https://hooks.test/y")
    response = MagicMock()
    response.raise_for_status.return_value = None
    with patch("httpx.Client.post", return_value=response) as post:
        ok = notifier.dispatch("proj-1", {"severity": "critical", "message": "High drift", "environment": "staging"})
    assert ok is True
    slack, webhook = post.call_args_list
    assert "proj-1" in slack.kwargs["json"]["text"] and "staging" in slack.kwargs["json"]["text"]
    assert webhook.kwargs["json"]["alert"]["message"] == "High drift"


def test_delivery_failure_is_reported_not_raised():
    notifier = Notifier(alert_webhook_url="https://hooks.test/y")
    with patch("httpx.Client.post", side_effect=httpx.ConnectError("down")):
        assert notifier.dispatch("p", {"severity": "critical", "message": "x"}) is False


def test_notify_runs_in_background():
    notifier = Notifier(alert_webhook_url="https://hooks.test/y")
    with patch.object(notifier, "_executor") as executor:
        notifier.notify("p", {"severity": "critical", "message": "x"})
        notifier.notify("p", {"severity": "critical", "message": "x", "resolved": True})
        notifier.notify("p", {"severity": "warning", "message": "x"})
    executor.submit.assert_called_once()
