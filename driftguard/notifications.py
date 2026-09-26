import os
import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Configured globally via environment variables for the SaaS instance
SLACK_WEBHOOK_URL = os.environ.get("DRIFTGUARD_SLACK_WEBHOOK")

class NotificationDispatcher:
    """Dispatches critical drift alerts to external systems like Slack."""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or SLACK_WEBHOOK_URL

    def dispatch_alert(self, project_id: str, alert: Dict[str, Any]) -> bool:
        """Send an alert notification if it is critical and a webhook is configured."""
        if not self.webhook_url:
            return False
            
        if alert.get("severity") != "critical":
            return False
            
        message = alert.get("message", "Unknown critical alert")
        environment = alert.get("environment", "prod")
        
        payload = {
            "text": f"🚨 *DriftGuard Critical Alert* 🚨\n"
                    f"*Project:* `{project_id}`\n"
                    f"*Environment:* `{environment}`\n"
                    f"*Message:* {message}\n"
        }
        
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.post(self.webhook_url, json=payload)
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to dispatch Slack notification: {e}")
            return False

# Global instance
dispatcher = NotificationDispatcher()

def notify_critical_alert(project_id: str, alert: Dict[str, Any]):
    """Fire-and-forget helper to dispatch alerts."""
    return dispatcher.dispatch_alert(project_id, alert)
