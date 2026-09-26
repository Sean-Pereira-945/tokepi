import pytest
from unittest.mock import patch, MagicMock
from driftguard.notifications import dispatcher, NotificationDispatcher

def test_notify_critical_alert():
    # Setup a fresh dispatcher with a dummy webhook
    test_dispatcher = NotificationDispatcher(webhook_url="http://dummy.com")
    
    # Test skipping non-critical alerts
    alert_warning = {"severity": "warning", "message": "Test"}
    assert test_dispatcher.dispatch_alert("proj-1", alert_warning) is False

    # Test dispatching a critical alert
    alert_critical = {"severity": "critical", "message": "High drift"}
    
    with patch("httpx.Client.post") as mock_post:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = test_dispatcher.dispatch_alert("proj-1", alert_critical)
        
        assert result is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["json"]["text"] == "🚨 *DriftGuard Critical Alert* 🚨\n*Project:* `proj-1`\n*Environment:* `prod`\n*Message:* High drift\n"

def test_notify_no_webhook():
    test_dispatcher = NotificationDispatcher(webhook_url=None)
    alert_critical = {"severity": "critical", "message": "High drift"}
    assert test_dispatcher.dispatch_alert("proj-1", alert_critical) is False
