"""Developer SDK for capturing telemetry, evaluating drift, and syncing to a DriftGuard server."""

from __future__ import annotations

import logging
import threading
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

import httpx

from .policy import DEFAULT_POLICY, evaluate_drift

logger = logging.getLogger(__name__)

# Server-side batch limit (see driftguard.server.schemas.MAX_BATCH_SIZE).
BATCH_SIZE = 500


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class DriftGuardClient:
    """Capture LLM and agent telemetry locally and ship it to a DriftGuard server.

    Args:
        api_key: The project API key returned when the project was created
            (``dg_live_...``). Never pass an LLM provider key here.
        project_name: Label for this application. Used as the default
            ``agent_name`` on agent events.
        environment: Deployment label: ``prod``, ``staging``, ``dev``, or ``test``.
        base_url: URL of the DriftGuard server. Required for sync and fetch calls;
            :meth:`check_drift` works offline without it.
        timeout: HTTP timeout in seconds.
        project_id: Default project ID for sync and fetch calls, so they can be
            called without arguments.
        max_queue: Maximum queued events per queue. When full, the oldest event
            is dropped and a warning is logged.
    """

    def __init__(
        self,
        api_key: str,
        project_name: str | None = None,
        environment: str = "prod",
        base_url: str | None = None,
        timeout: float = 10.0,
        project_id: str | None = None,
        max_queue: int = 10_000,
    ) -> None:
        self.api_key = api_key
        self.project_name = project_name or project_id or "driftguard-app"
        self.environment = environment
        self.base_url = base_url.rstrip("/") if base_url else None
        self.timeout = timeout
        self.project_id = project_id
        self.max_queue = max_queue
        self.metrics: list[dict[str, Any]] = []
        self.agent_events: list[dict[str, Any]] = []
        self._queue_lock = threading.Lock()
        self._policy: dict[str, float] = dict(DEFAULT_POLICY)
        self._policy_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    def _enqueue(self, queue: list[dict[str, Any]], payload: dict[str, Any]) -> None:
        """Append to a queue under the lock, dropping the oldest item when full."""
        with self._queue_lock:
            if len(queue) >= self.max_queue:
                queue.pop(0)
                logger.warning("DriftGuard queue full (%d); dropped the oldest event", self.max_queue)
            queue.append(payload)

    def capture_metrics(self, **metrics: Any) -> dict[str, Any]:
        """Queue one LLM telemetry event.

        Pass any of ``prompt_tokens``, ``context_length``, ``retrieval_score`` and
        ``response_quality``. The capture time is recorded as ``occurred_at`` so
        delayed syncs keep accurate timestamps. Returns the queued payload.
        """
        payload: dict[str, Any] = {
            "environment": self.environment,
            "occurred_at": _utc_now_iso(),
            **metrics,
        }
        self._enqueue(self.metrics, payload)
        return payload

    def capture_agent_event(self, **event: Any) -> dict[str, Any]:
        """Queue one agent task/tool attempt for retry and failure analysis.

        Required fields: ``task_id``, ``tool_name``, ``status``. Optional:
        ``trace_id``, ``tool_call_id``, ``attempt``, ``error_type``,
        ``error_message``, ``prompt_tokens``, ``completion_tokens``,
        ``total_tokens``, ``duration_ms``, ``model``, ``input_hash``.
        """
        payload = {
            "agent_name": self.project_name,
            "environment": self.environment,
            "occurred_at": _utc_now_iso(),
            **event,
        }
        self._enqueue(self.agent_events, payload)
        return payload

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    def _require_base_url(self) -> str:
        if not self.base_url:
            raise RuntimeError("base_url is not configured. Pass base_url=<server> to DriftGuardClient.")
        return self.base_url

    def _resolve_project(self, project_id: str | None) -> str:
        resolved = project_id or self.project_id
        if not resolved:
            raise ValueError("project_id is required (pass it here or to DriftGuardClient).")
        return resolved

    def _sync_queue(self, queue: list[dict[str, Any]], path: str) -> dict[str, Any]:
        """Send a queue in batches. Events from failed batches stay queued."""
        base_url = self._require_base_url()
        with self._queue_lock:
            pending = list(queue)
            queue.clear()
        if not pending:
            return {"synced": 0, "skipped": True}

        synced = 0
        errors: list[str] = []
        failed: list[dict[str, Any]] = []
        headers = {"X-API-Key": self.api_key}
        with httpx.Client(timeout=self.timeout) as http:
            for start in range(0, len(pending), BATCH_SIZE):
                batch = pending[start : start + BATCH_SIZE]
                try:
                    response = http.post(f"{base_url}{path}", json={"events": batch}, headers=headers)
                    response.raise_for_status()
                    synced += len(batch)
                except httpx.HTTPError as exc:
                    errors.append(str(exc))
                    failed.extend(batch)

        if failed:
            with self._queue_lock:
                queue[:0] = failed[-self.max_queue :]
        return {"synced": synced, "errors": errors}

    def sync_metrics(self, project_id: str | None = None) -> dict[str, Any]:
        """Send queued telemetry to the server. Returns ``{"synced", "errors"}``."""
        pid = self._resolve_project(project_id)
        return self._sync_queue(self.metrics, f"/events/{pid}/batch")

    def sync_agent_events(self, project_id: str | None = None) -> dict[str, Any]:
        """Send queued agent attempts to the server. Returns ``{"synced", "errors"}``."""
        pid = self._resolve_project(project_id)
        return self._sync_queue(self.agent_events, f"/agent-events/{pid}/batch")

    def flush(self, project_id: str | None = None) -> dict[str, Any]:
        """Sync both queues and return both results."""
        return {"metrics": self.sync_metrics(project_id), "agent_events": self.sync_agent_events(project_id)}

    def _in_background(self, target: Any, project_id: str | None) -> threading.Thread:
        pid = self._resolve_project(project_id)
        thread = threading.Thread(target=target, args=(pid,), daemon=True)
        thread.start()
        return thread

    def sync_metrics_async(self, project_id: str | None = None) -> threading.Thread:
        """Sync telemetry on a daemon thread without blocking the caller."""
        return self._in_background(self.sync_metrics, project_id)

    def sync_agent_events_async(self, project_id: str | None = None) -> threading.Thread:
        """Sync agent attempts on a daemon thread without blocking the caller."""
        return self._in_background(self.sync_agent_events, project_id)

    # ------------------------------------------------------------------
    # Server reads
    # ------------------------------------------------------------------

    def _get(self, path: str) -> Any:
        base_url = self._require_base_url()
        with httpx.Client(timeout=self.timeout) as http:
            response = http.get(f"{base_url}{path}", headers={"X-API-Key": self.api_key})
            response.raise_for_status()
            return response.json()

    def fetch_policy(self, project_id: str | None = None) -> dict[str, float]:
        """Pull the project's thresholds and use them for :meth:`check_drift`."""
        server_policy: Mapping[str, Any] = self._get(f"/projects/{self._resolve_project(project_id)}/policy")
        with self._policy_lock:
            self._policy = {**DEFAULT_POLICY, **{k: float(v) for k, v in server_policy.items()}}
            return dict(self._policy)

    def fetch_agent_diagnosis(self, project_id: str | None = None) -> dict[str, Any]:
        """Fetch the failed-tool and retry diagnosis for the project."""
        return self._get(f"/projects/{self._resolve_project(project_id)}/agent-diagnosis")

    # ------------------------------------------------------------------
    # Local evaluation
    # ------------------------------------------------------------------

    @property
    def policy(self) -> dict[str, float]:
        """The thresholds :meth:`check_drift` currently uses."""
        with self._policy_lock:
            return dict(self._policy)

    def check_drift(self) -> dict[str, Any]:
        """Score the most recently captured metrics against the active policy.

        Works offline. Returns ``severity``, ``risk_score``, ``violations``,
        ``recommendation``, ``actions``, and ``root_cause``.
        """
        with self._queue_lock:
            latest = self.metrics[-1] if self.metrics else None
        if latest is None:
            return {
                "severity": "stable",
                "risk_score": 0.0,
                "violations": [],
                "recommendation": "no_telemetry_yet",
                "actions": [],
                "root_cause": "",
            }
        result = evaluate_drift(latest, self.policy)
        result.pop("token_savings_ratio", None)
        return result
