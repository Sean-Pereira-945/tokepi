"""Thread-aware SDK client for capturing, evaluating, and syncing telemetry."""

from __future__ import annotations

import threading
from typing import Any

import httpx

from .mitigation import recommend_mitigation

# Default drift thresholds — used when no server policy is available
_DEFAULT_POLICY: dict[str, float] = {
    "prompt_token_limit": 3000.0,
    "retrieval_score_floor": 0.5,
    "context_length_limit": 4000.0,
    "response_quality_floor": 0.8,
}


class DriftGuardClient:
    """Developer-facing SDK for sending app telemetry and evaluating drift risk.

    Args:
        api_key: Project API key obtained from the DriftGuard dashboard.
        project_name: Logical project name (used for local labelling only).
        environment: Deployment environment label (e.g. ``"prod"``, ``"staging"``).
        base_url: Optional URL of the hosted DriftGuard SaaS backend.  When set,
            :meth:`sync_metrics` will POST events to the backend and
            :meth:`fetch_policy` will pull server-side drift thresholds.
        timeout: HTTP request timeout in seconds (default 10).
    """

    def __init__(
        self,
        api_key: str,
        project_name: str,
        environment: str = "prod",
        base_url: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        """Initialize local telemetry queues, backend settings, and policy defaults."""
        self.api_key = api_key
        self.project_name = project_name
        self.environment = environment
        self.base_url = base_url.rstrip("/") if base_url else None
        self.timeout = timeout
        self.metrics: list[dict[str, Any]] = []
        self.agent_events: list[dict[str, Any]] = []
        self._policy: dict[str, float] = dict(_DEFAULT_POLICY)
        self._policy_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Telemetry capture
    # ------------------------------------------------------------------

    def capture_metrics(self, **metrics: Any) -> dict[str, Any]:
        """Record a single telemetry event locally.

        Returns the full payload that was captured (including project and environment
        labels).  Call :meth:`sync_metrics` afterwards to ship events to the backend.
        """
        payload: dict[str, Any] = {
            "project": self.project_name,
            "environment": self.environment,
            **metrics,
        }
        self.metrics.append(payload)
        return payload

    # ------------------------------------------------------------------
    # Backend sync
    # ------------------------------------------------------------------

    def capture_agent_event(self, **event: Any) -> dict[str, Any]:
        """Queue one agent task/tool attempt for retry and failure analysis."""
        payload = {
            "agent_name": self.project_name,
            "environment": self.environment,
            **event,
        }
        self.agent_events.append(payload)
        return payload

    def sync_agent_events(self, project_id: str) -> dict[str, Any]:
        """Send queued agent task/tool attempts to the DriftGuard backend."""
        if not self.base_url:
            raise RuntimeError(
                "base_url is not configured. Pass base_url=<server> to DriftGuardClient."
            )
        if not self.agent_events:
            return {"synced": 0, "skipped": True}

        synced = 0
        errors: list[str] = []
        headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}
        with httpx.Client(timeout=self.timeout) as http:
            for event in self.agent_events:
                try:
                    response = http.post(
                        f"{self.base_url}/agent-events/{project_id}",
                        json=event,
                        headers=headers,
                    )
                    response.raise_for_status()
                    synced += 1
                except httpx.HTTPError as exc:
                    errors.append(str(exc))

        if synced == len(self.agent_events):
            self.agent_events.clear()
        elif synced > 0:
            self.agent_events = self.agent_events[synced:]
        return {"synced": synced, "errors": errors}

    def fetch_agent_diagnosis(self, project_id: str) -> dict[str, Any]:
        """Fetch the latest failed-tool and retry diagnosis for a project."""
        if not self.base_url:
            raise RuntimeError(
                "base_url is not configured. Pass base_url=<server> to DriftGuardClient."
            )
        headers = {"X-API-Key": self.api_key}
        with httpx.Client(timeout=self.timeout) as http:
            response = http.get(
                f"{self.base_url}/projects/{project_id}/agent-diagnosis",
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    def sync_metrics(self, project_id: str) -> dict[str, Any]:
        """POST all locally captured metrics to the DriftGuard SaaS backend.

        Args:
            project_id: The project ID registered in the SaaS backend.

        Returns:
            A dict with ``"synced"`` count and any ``"error"`` message.

        Raises:
            RuntimeError: If ``base_url`` was not configured.
        """
        if not self.base_url:
            raise RuntimeError(
                "base_url is not configured.  Pass base_url=<server> to DriftGuardClient."
            )

        if not self.metrics:
            return {"synced": 0, "skipped": True}

        synced = 0
        errors: list[str] = []
        headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}

        with httpx.Client(timeout=self.timeout) as http:
            for event in self.metrics:
                try:
                    response = http.post(
                        f"{self.base_url}/events/{project_id}",
                        json=event,
                        headers=headers,
                    )
                    response.raise_for_status()
                    synced += 1
                except httpx.HTTPError as exc:
                    errors.append(str(exc))

        # Clear successfully synced metrics
        if synced == len(self.metrics):
            self.metrics.clear()
        elif synced > 0:
            self.metrics = self.metrics[synced:]

        return {"synced": synced, "errors": errors}

    def sync_metrics_async(self, project_id: str) -> None:
        """Fire-and-forget background sync.  Does not block the calling thread."""
        thread = threading.Thread(
            target=self.sync_metrics, args=(project_id,), daemon=True
        )
        thread.start()

    # ------------------------------------------------------------------
    # Server-side policy
    # ------------------------------------------------------------------

    def fetch_policy(self, project_id: str) -> dict[str, float]:
        """Pull drift thresholds from the SaaS backend for this project.

        Updates the internal policy cache used by :meth:`check_drift`.

        Returns:
            The active policy dict (merged with local defaults for any missing keys).

        Raises:
            RuntimeError: If ``base_url`` was not configured.
        """
        if not self.base_url:
            raise RuntimeError(
                "base_url is not configured.  Pass base_url=<server> to DriftGuardClient."
            )

        headers = {"X-API-Key": self.api_key}
        with httpx.Client(timeout=self.timeout) as http:
            response = http.get(
                f"{self.base_url}/projects/{project_id}/policy",
                headers=headers,
            )
            response.raise_for_status()
            server_policy: dict[str, Any] = response.json()

        with self._policy_lock:
            self._policy = {**_DEFAULT_POLICY, **server_policy}

        return dict(self._policy)

    # ------------------------------------------------------------------
    # Drift evaluation
    # ------------------------------------------------------------------

    def check_drift(self) -> dict[str, Any]:
        """Evaluate drift risk from the most recently captured metric payload.

        Uses server-fetched thresholds when available (set via :meth:`fetch_policy`),
        otherwise falls back to the built-in defaults.

        Returns:
            A dict with ``severity``, ``risk_score``, ``recommendation``,
            ``actions``, and ``root_cause``.
        """
        if not self.metrics:
            return {
                "severity": "stable",
                "recommendation": "No telemetry yet.",
                "actions": [],
                "risk_score": 0.0,
                "root_cause": "",
            }

        latest = self.metrics[-1]
        risk_score = 0.0

        with self._policy_lock:
            policy = dict(self._policy)

        prompt_tokens = float(latest.get("prompt_tokens", 0))
        retrieval_score = float(latest.get("retrieval_score", 1.0))
        context_length = float(latest.get("context_length", 0))
        response_quality = float(latest.get("response_quality", 1.0))

        if prompt_tokens > policy["prompt_token_limit"]:
            risk_score += 0.25
        if retrieval_score < policy["retrieval_score_floor"]:
            risk_score += 0.35
        if context_length > policy["context_length_limit"]:
            risk_score += 0.2
        if response_quality < policy["response_quality_floor"]:
            risk_score += 0.2

        risk_score = min(1.0, risk_score)

        severity = "stable"
        if risk_score >= 0.75:
            severity = "critical"
        elif risk_score >= 0.4:
            severity = "warning"

        mitigation = recommend_mitigation(latest)
        return {
            "severity": severity,
            "risk_score": round(risk_score, 3),
            "recommendation": mitigation["recommended_action"],
            "actions": mitigation["actions"],
            "root_cause": mitigation["root_cause"],
        }
