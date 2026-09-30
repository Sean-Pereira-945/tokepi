"""Deliver critical alerts to Slack and to a generic JSON webhook, off the request path."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class Notifier:
    """Send critical alerts to the configured destinations.

    :meth:`notify` returns immediately; delivery runs on a small thread pool so a
    slow webhook never delays an API response.
    """

    def __init__(
        self, slack_webhook_url: str | None = None, alert_webhook_url: str | None = None, timeout: float = 5.0
    ) -> None:
        self.slack_webhook_url = slack_webhook_url
        self.alert_webhook_url = alert_webhook_url
        self.timeout = timeout
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="driftguard-notify")

    @property
    def enabled(self) -> bool:
        return bool(self.slack_webhook_url or self.alert_webhook_url)

    def notify(self, project_id: str, alert: Mapping[str, Any]) -> None:
        """Queue delivery of a critical, unresolved alert."""
        if self.enabled and alert.get("severity") == "critical" and not alert.get("resolved"):
            self._executor.submit(self.dispatch, project_id, dict(alert))

    def dispatch(self, project_id: str, alert: Mapping[str, Any]) -> bool:
        """Deliver an alert synchronously. Returns True if every destination accepted it."""
        if not self.enabled or alert.get("severity") != "critical":
            return False
        ok = True
        with httpx.Client(timeout=self.timeout) as http:
            if self.slack_webhook_url:
                text = (
                    ":rotating_light: *DriftGuard critical alert*\n"
                    f"*Project:* `{project_id}`  *Environment:* `{alert.get('environment') or 'prod'}`\n"
                    f"{alert.get('message', 'Critical alert')}"
                )
                ok &= self._post(http, self.slack_webhook_url, {"text": text})
            if self.alert_webhook_url:
                ok &= self._post(http, self.alert_webhook_url, {"project_id": project_id, "alert": dict(alert)})
        return ok

    @staticmethod
    def _post(http: httpx.Client, url: str, payload: dict[str, Any]) -> bool:
        try:
            http.post(url, json=payload).raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.error("Alert notification to %s failed: %s", url.split("?")[0], exc)
            return False

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
