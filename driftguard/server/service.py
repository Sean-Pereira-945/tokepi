"""Persistence and business logic for accounts, projects, telemetry, alerts, and diagnosis.

Every method opens its own transaction, so one service instance is safe to share
across threads and server workers. No state is cached in memory.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from sqlalchemy import and_, case, delete, func, insert, or_, select, update
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.exc import IntegrityError

from driftguard.agent_analysis import FAILED_STATUSES, SUCCESS_STATUSES, analyze_agent_events
from driftguard.policy import DEFAULT_POLICY, evaluate_drift

from . import db
from .db import accounts, agent_events, alerts, auth_sessions, events, policies, projects, utcnow
from .retention import scrub_pii
from .security import (
    api_key_hint,
    create_session_token,
    decode_session_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)

TIME_RANGES: dict[str, timedelta | None] = {
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "all": None,
}
POLICY_FIELDS = tuple(DEFAULT_POLICY)
# Clock skew tolerated for client-supplied ``occurred_at`` timestamps.
_MAX_FUTURE_SKEW = timedelta(minutes=5)


class NotFoundError(LookupError):
    """The requested record does not exist or is not visible to the caller."""


class ConflictError(ValueError):
    """The record already exists."""


class AuthError(PermissionError):
    """Credentials or tokens are missing, invalid, or expired."""


def iso(value: datetime | None) -> str | None:
    """Format a UTC datetime as ISO 8601 with a ``Z`` suffix."""
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if value else None


def _cutoff(time_range: str) -> datetime | None:
    delta = TIME_RANGES[time_range]
    return utcnow() - delta if delta else None


def _event_time(value: datetime | None) -> datetime:
    """Use a client timestamp when plausible, otherwise the server clock."""
    now = utcnow()
    if value is None:
        return now
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return now if value > now + _MAX_FUTURE_SKEW else value


def _project_dict(row: RowMapping) -> dict[str, Any]:
    return {
        "project_id": row["project_id"],
        "account_id": row["account_id"],
        "name": row["name"],
        "environment": row["environment"],
        "api_key_hint": row["api_key_hint"],
        "capture_content": bool(row["capture_content"]),
        "created_at": iso(row["created_at"]),
    }


def _alert_dict(row: RowMapping) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "severity": row["severity"],
        "message": row["message"],
        "saved_tokens": float(row["saved_tokens"] or 0.0),
        "environment": row["environment"],
        "source": row["source"] or "manual",
        "task_id": row["task_id"],
        "root_cause": row["root_cause"],
        "resolved": bool(row["resolved"]),
        "resolved_at": iso(row["resolved_at"]),
        "created_at": iso(row["created_at"]),
    }


def _event_dict(row: RowMapping) -> dict[str, Any]:
    return {
        "id": row["id"],
        "prompt_tokens": row["prompt_tokens"],
        "retrieval_score": row["retrieval_score"],
        "context_length": row["context_length"],
        "response_quality": row["response_quality"],
        "environment": row["environment"],
        "risk_score": row["risk_score"],
        "severity": row["severity"],
        "root_cause": row["root_cause"],
        "recommendation": row["recommendation"],
        "metadata": json.loads(row["extra_json"]) if row["extra_json"] else None,
        "created_at": iso(row["created_at"]),
    }


_AGENT_COLUMNS = (
    "id",
    "task_id",
    "kind",
    "trace_id",
    "agent_name",
    "model",
    "tool_name",
    "tool_call_id",
    "attempt",
    "status",
    "error_type",
    "error_message",
    "input_hash",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "duration_ms",
    "environment",
)


def _agent_dict(row: RowMapping) -> dict[str, Any]:
    data = {name: row[name] for name in _AGENT_COLUMNS}
    data["kind"] = data["kind"] or "tool_call"
    data["input"] = row["input_text"]
    data["output"] = row["output_text"]
    data["created_at"] = iso(row["created_at"])
    return data


class DriftGuardService:
    """Data access and domain rules for the DriftGuard server."""

    def __init__(
        self,
        engine: Engine | str,
        secret_key: str,
        *,
        session_ttl_hours: int = 168,
        scrub_pii: bool = True,
        drift_alert_cooldown_minutes: int = 15,
    ) -> None:
        self.engine = db.make_engine(engine) if isinstance(engine, str) else engine
        self.secret_key = secret_key
        self.session_ttl_hours = session_ttl_hours
        self.scrub_pii = scrub_pii
        self.drift_alert_cooldown = timedelta(minutes=drift_alert_cooldown_minutes)
        db.init_db(self.engine)

    def ping(self) -> None:
        """Raise if the database is unreachable."""
        with self.engine.connect() as conn:
            conn.execute(select(1))

    def _clean(self, value: str | None) -> str | None:
        return scrub_pii(value) if self.scrub_pii and value else value

    # ------------------------------------------------------------------
    # Accounts and sessions
    # ------------------------------------------------------------------

    def register(self, name: str, email: str, password: str) -> dict[str, Any]:
        """Create an account with a hashed password."""
        account_id = f"acct-{secrets.token_hex(6)}"
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    insert(accounts).values(
                        account_id=account_id,
                        name=name,
                        email=email.lower(),
                        password_hash=hash_password(password),
                        created_at=utcnow(),
                    )
                )
        except IntegrityError as exc:
            raise ConflictError("An account with this email already exists") from exc
        return self.get_account(account_id)

    def authenticate(self, email: str, password: str) -> dict[str, Any]:
        """Return the account for valid credentials or raise :class:`AuthError`."""
        with self.engine.connect() as conn:
            row = conn.execute(select(accounts).where(accounts.c.email == email.lower())).mappings().first()
        if not verify_password(password, row["password_hash"] if row else None) or row is None:
            raise AuthError("Invalid email or password")
        return {"account_id": row["account_id"], "name": row["name"], "email": row["email"]}

    def get_account(self, account_id: str) -> dict[str, Any]:
        with self.engine.connect() as conn:
            row = conn.execute(select(accounts).where(accounts.c.account_id == account_id)).mappings().first()
        if row is None:
            raise NotFoundError("Account not found")
        return {
            "account_id": row["account_id"],
            "name": row["name"],
            "email": row["email"],
            "created_at": iso(row["created_at"]),
        }

    def create_session(self, account_id: str) -> dict[str, Any]:
        """Issue a session token for an existing account."""
        self.get_account(account_id)
        token, jti, expires_at = create_session_token(account_id, self.secret_key, self.session_ttl_hours)
        with self.engine.begin() as conn:
            conn.execute(
                insert(auth_sessions).values(jti=jti, account_id=account_id, created_at=utcnow(), expires_at=expires_at)
            )
        return {"token": token, "expires_at": iso(expires_at)}

    def resolve_session(self, token: str) -> str:
        """Return the account ID for a live session token or raise :class:`AuthError`."""
        try:
            account_id, jti = decode_session_token(token, self.secret_key)
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("Session expired") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthError("Invalid session token") from exc
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    select(auth_sessions.c.account_id, auth_sessions.c.revoked_at, auth_sessions.c.expires_at).where(
                        auth_sessions.c.jti == jti
                    )
                )
                .mappings()
                .first()
            )
        if row is None or row["account_id"] != account_id or row["revoked_at"] is not None:
            raise AuthError("Session is no longer valid")
        if row["expires_at"] <= utcnow():
            raise AuthError("Session expired")
        return account_id

    def revoke_session(self, token: str) -> None:
        """Invalidate a session token (logout)."""
        try:
            _, jti = decode_session_token(token, self.secret_key)
        except jwt.InvalidTokenError:
            return
        with self.engine.begin() as conn:
            conn.execute(update(auth_sessions).where(auth_sessions.c.jti == jti).values(revoked_at=utcnow()))

    def delete_account(self, account_id: str) -> None:
        """Delete an account, its sessions, and all of its projects' data."""
        with self.engine.begin() as conn:
            project_ids = (
                conn.execute(select(projects.c.project_id).where(projects.c.account_id == account_id)).scalars().all()
            )
            for project_id in project_ids:
                self._delete_project_rows(conn, project_id)
            conn.execute(delete(auth_sessions).where(auth_sessions.c.account_id == account_id))
            conn.execute(delete(accounts).where(accounts.c.account_id == account_id))

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def create_project(
        self, account_id: str, project_id: str, name: str, environment: str = "prod"
    ) -> tuple[dict[str, Any], str]:
        """Create a project. Returns the project and its API key (shown only once)."""
        api_key = generate_api_key()
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    insert(projects).values(
                        project_id=project_id,
                        account_id=account_id,
                        name=name,
                        environment=environment,
                        api_key_hash=hash_api_key(api_key),
                        api_key_hint=api_key_hint(api_key),
                        created_at=utcnow(),
                    )
                )
                conn.execute(insert(policies).values(project_id=project_id, **DEFAULT_POLICY))
        except IntegrityError as exc:
            raise ConflictError(f"Project ID {project_id!r} is already taken") from exc
        return self.get_project(project_id), api_key

    def get_project(self, project_id: str) -> dict[str, Any]:
        with self.engine.connect() as conn:
            row = conn.execute(select(projects).where(projects.c.project_id == project_id)).mappings().first()
        if row is None:
            raise NotFoundError("Project not found")
        return _project_dict(row)

    def get_owned_project(self, project_id: str, account_id: str) -> dict[str, Any]:
        """Return a project only if ``account_id`` owns it (otherwise not found)."""
        project = self.get_project(project_id)
        if project["account_id"] != account_id:
            raise NotFoundError("Project not found")
        return project

    def list_projects(self, account_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    select(projects).where(projects.c.account_id == account_id).order_by(projects.c.created_at)
                )
                .mappings()
                .all()
            )
        return [_project_dict(row) for row in rows]

    def update_project(self, project_id: str, updates: Mapping[str, Any]) -> dict[str, Any]:
        """Change a project's name or content-capture setting."""
        values = {key: value for key, value in updates.items() if key in {"name", "capture_content"}}
        if values:
            with self.engine.begin() as conn:
                conn.execute(update(projects).where(projects.c.project_id == project_id).values(**values))
        return self.get_project(project_id)

    def project_for_api_key(self, api_key: str) -> dict[str, Any]:
        """Resolve a project API key or raise :class:`AuthError`."""
        with self.engine.connect() as conn:
            row = (
                conn.execute(select(projects).where(projects.c.api_key_hash == hash_api_key(api_key)))
                .mappings()
                .first()
            )
        if row is None:
            raise AuthError("Invalid API key")
        return _project_dict(row)

    def rotate_api_key(self, project_id: str) -> tuple[dict[str, Any], str]:
        """Replace a project's API key. The old key stops working immediately."""
        api_key = generate_api_key()
        with self.engine.begin() as conn:
            result = conn.execute(
                update(projects)
                .where(projects.c.project_id == project_id)
                .values(api_key_hash=hash_api_key(api_key), api_key_hint=api_key_hint(api_key))
            )
        if result.rowcount == 0:
            raise NotFoundError("Project not found")
        return self.get_project(project_id), api_key

    @staticmethod
    def _delete_project_rows(conn: Connection, project_id: str) -> None:
        for table in (alerts, events, agent_events, policies):
            conn.execute(delete(table).where(table.c.project_id == project_id))
        conn.execute(delete(projects).where(projects.c.project_id == project_id))

    def delete_project(self, project_id: str) -> None:
        """Delete a project and all of its telemetry, alerts, and policy."""
        with self.engine.begin() as conn:
            self._delete_project_rows(conn, project_id)

    # ------------------------------------------------------------------
    # Policy
    # ------------------------------------------------------------------

    def get_policy(self, project_id: str, conn: Connection | None = None) -> dict[str, float]:
        """Return the project's thresholds, filling unset values with defaults."""
        query = select(policies).where(policies.c.project_id == project_id)
        if conn is None:
            with self.engine.connect() as own:
                row = own.execute(query).mappings().first()
        else:
            row = conn.execute(query).mappings().first()
        policy = dict(DEFAULT_POLICY)
        if row:
            policy.update({key: float(row[key]) for key in POLICY_FIELDS if row[key] is not None})
        policy["blocked_after_failures"] = int(policy["blocked_after_failures"])
        return policy

    def update_policy(self, project_id: str, updates: Mapping[str, float]) -> dict[str, float]:
        """Merge ``updates`` into the project's policy."""
        merged = {**self.get_policy(project_id), **{k: float(v) for k, v in updates.items() if k in POLICY_FIELDS}}
        with self.engine.begin() as conn:
            result = conn.execute(update(policies).where(policies.c.project_id == project_id).values(**merged))
            if result.rowcount == 0:
                conn.execute(insert(policies).values(project_id=project_id, **merged))
        merged["blocked_after_failures"] = int(merged["blocked_after_failures"])
        return merged

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def _insert_alert(self, conn: Connection, project_id: str, **values: Any) -> dict[str, Any]:
        values.setdefault("created_at", utcnow())
        values["message"] = self._clean(values["message"])
        alert_id = conn.execute(insert(alerts).values(project_id=project_id, **values)).inserted_primary_key[0]
        row = conn.execute(select(alerts).where(alerts.c.id == alert_id)).mappings().one()
        return _alert_dict(row)

    def create_alert(
        self,
        project_id: str,
        severity: str,
        message: str,
        *,
        saved_tokens: float = 0.0,
        environment: str | None = None,
        source: str = "manual",
        task_id: str | None = None,
        root_cause: str | None = None,
    ) -> dict[str, Any]:
        project = self.get_project(project_id)
        with self.engine.begin() as conn:
            return self._insert_alert(
                conn,
                project_id,
                severity=severity,
                message=message,
                saved_tokens=saved_tokens,
                environment=environment or project["environment"],
                source=source,
                task_id=task_id,
                root_cause=root_cause,
            )

    def list_alerts(
        self,
        project_id: str,
        *,
        severity: str | None = None,
        environment: str | None = None,
        time_range: str = "all",
        resolved: bool | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        query = select(alerts).where(alerts.c.project_id == project_id)
        if severity:
            query = query.where(alerts.c.severity == severity)
        if environment:
            query = query.where(alerts.c.environment == environment)
        if resolved is not None:
            query = query.where(alerts.c.resolved == resolved)
        if (cutoff := _cutoff(time_range)) is not None:
            query = query.where(alerts.c.created_at >= cutoff)
        with self.engine.connect() as conn:
            rows = conn.execute(query.order_by(alerts.c.id.desc()).limit(limit)).mappings().all()
        return [_alert_dict(row) for row in rows]

    def set_alert_resolved(self, project_id: str, alert_id: int, resolved: bool) -> dict[str, Any]:
        with self.engine.begin() as conn:
            result = conn.execute(
                update(alerts)
                .where(and_(alerts.c.id == alert_id, alerts.c.project_id == project_id))
                .values(resolved=resolved, resolved_at=utcnow() if resolved else None)
            )
            if result.rowcount == 0:
                raise NotFoundError("Alert not found")
            return _alert_dict(conn.execute(select(alerts).where(alerts.c.id == alert_id)).mappings().one())

    # ------------------------------------------------------------------
    # LLM telemetry
    # ------------------------------------------------------------------

    def ingest_events(
        self, project: Mapping[str, Any], batch: Iterable[Mapping[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Score and store telemetry events.

        Returns ``(results, new_alerts)``: one drift evaluation per event, and any
        alerts raised for critical drift (at most one per root cause per cooldown).
        """
        project_id = project["project_id"]
        results: list[dict[str, Any]] = []
        new_alerts: list[dict[str, Any]] = []
        with self.engine.begin() as conn:
            policy = self.get_policy(project_id, conn)
            rows = []
            evaluations = []
            for item in batch:
                evaluation = evaluate_drift(item, policy)
                evaluations.append(evaluation)
                metadata = item.get("metadata")
                if metadata and self.scrub_pii:
                    metadata = {k: scrub_pii(v) if isinstance(v, str) else v for k, v in metadata.items()}
                rows.append(
                    {
                        "project_id": project_id,
                        "prompt_tokens": item.get("prompt_tokens"),
                        "retrieval_score": item.get("retrieval_score"),
                        "context_length": item.get("context_length"),
                        "response_quality": item.get("response_quality"),
                        "environment": item.get("environment") or project["environment"],
                        "risk_score": evaluation["risk_score"],
                        "severity": evaluation["severity"],
                        "root_cause": evaluation["root_cause"],
                        "recommendation": evaluation["recommendation"],
                        "extra_json": json.dumps(metadata) if metadata else None,
                        "created_at": _event_time(item.get("occurred_at")),
                    }
                )
                results.append(
                    {
                        key: evaluation[key]
                        for key in ("severity", "risk_score", "recommendation", "actions", "root_cause")
                    }
                )
            if rows:
                conn.execute(insert(events), rows)
            for row, evaluation in zip(rows, evaluations, strict=True):
                if evaluation["severity"] == "critical":
                    alert = self._maybe_drift_alert(conn, project_id, row, evaluation)
                    if alert:
                        new_alerts.append(alert)
        return results, new_alerts

    def _maybe_drift_alert(
        self, conn: Connection, project_id: str, row: Mapping[str, Any], evaluation: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        """Raise a drift alert unless an open one for the same cause is recent."""
        recent = conn.execute(
            select(alerts.c.id)
            .where(
                and_(
                    alerts.c.project_id == project_id,
                    alerts.c.source == "drift",
                    alerts.c.resolved == False,  # noqa: E712 - SQL expression
                    alerts.c.environment == row["environment"],
                    alerts.c.root_cause == evaluation["root_cause"],
                    alerts.c.created_at >= utcnow() - self.drift_alert_cooldown,
                )
            )
            .limit(1)
        ).first()
        if recent:
            return None
        prompt_tokens = float(row["prompt_tokens"] or 0)
        return self._insert_alert(
            conn,
            project_id,
            severity="critical",
            message=f"Critical drift: {evaluation['root_cause']}. Recommended: {evaluation['recommendation']}.",
            saved_tokens=round(prompt_tokens * evaluation.get("token_savings_ratio", 0.0), 3),
            environment=row["environment"],
            source="drift",
            root_cause=evaluation["root_cause"],
        )

    def list_events(
        self,
        project_id: str,
        *,
        environment: str | None = None,
        time_range: str = "all",
        limit: int = 100,
        before_id: int | None = None,
    ) -> list[dict[str, Any]]:
        query = select(events).where(events.c.project_id == project_id)
        if environment:
            query = query.where(events.c.environment == environment)
        if (cutoff := _cutoff(time_range)) is not None:
            query = query.where(events.c.created_at >= cutoff)
        if before_id is not None:
            query = query.where(events.c.id < before_id)
        with self.engine.connect() as conn:
            rows = conn.execute(query.order_by(events.c.id.desc()).limit(limit)).mappings().all()
        return [_event_dict(row) for row in rows]

    def summary(
        self, project_id: str, *, environment: str | None = None, severity: str | None = None, time_range: str = "all"
    ) -> dict[str, Any]:
        """Aggregate telemetry, agent activity and alerts for the dashboard overview."""
        policy = self.get_policy(project_id)
        cutoff = _cutoff(time_range)
        event_filter = [events.c.project_id == project_id]
        if environment:
            event_filter.append(events.c.environment == environment)
        if cutoff is not None:
            event_filter.append(events.c.created_at >= cutoff)

        def rate(condition: Any) -> Any:
            return func.avg(case((condition, 1.0), else_=0.0))

        with self.engine.connect() as conn:
            stats = (
                conn.execute(
                    select(
                        func.count().label("total"),
                        func.avg(events.c.prompt_tokens).label("prompt_tokens"),
                        func.avg(events.c.context_length).label("context_length"),
                        func.avg(events.c.retrieval_score).label("retrieval_score"),
                        func.avg(events.c.response_quality).label("response_quality"),
                        func.avg(events.c.risk_score).label("risk_score"),
                        func.max(events.c.created_at).label("last_event"),
                        rate(events.c.prompt_tokens > policy["prompt_token_limit"]).label("prompt_rate"),
                        rate(events.c.context_length > policy["context_length_limit"]).label("context_rate"),
                        rate(events.c.retrieval_score < policy["retrieval_score_floor"]).label("retrieval_rate"),
                        rate(events.c.response_quality < policy["response_quality_floor"]).label("quality_rate"),
                    ).where(*event_filter)
                )
                .mappings()
                .one()
            )
            by_severity = dict(
                conn.execute(
                    select(events.c.severity, func.count()).where(*event_filter).group_by(events.c.severity)
                ).all()
            )
            causes = conn.execute(
                select(events.c.root_cause, func.count().label("n"))
                .where(*event_filter, events.c.severity != "stable", events.c.root_cause.is_not(None))
                .group_by(events.c.root_cause)
                .order_by(func.count().desc())
                .limit(5)
            ).all()
            activity = self._agent_activity(conn, project_id, environment, cutoff)

        open_alerts = self.list_alerts(
            project_id, severity=severity, environment=environment, time_range=time_range, resolved=False
        )
        critical = sum(1 for a in open_alerts if a["severity"] == "critical")
        warning = sum(1 for a in open_alerts if a["severity"] == "warning")
        saved = round(sum(a["saved_tokens"] for a in open_alerts), 3)
        last_alert = max((a["created_at"] for a in open_alerts if a["created_at"]), default=None)
        last_event = iso(stats["last_event"])
        last_activity = activity["last_activity"]

        def rounded(value: Any, digits: int = 4) -> float | None:
            return round(float(value), digits) if value is not None else None

        return {
            "project_id": project_id,
            "status": "critical" if critical else "warning" if warning else "stable",
            "total_events": int(stats["total"] or 0),
            "events_by_severity": {k or "unscored": int(v) for k, v in by_severity.items()},
            "averages": {
                "prompt_tokens": rounded(stats["prompt_tokens"], 1),
                "context_length": rounded(stats["context_length"], 1),
                "retrieval_score": rounded(stats["retrieval_score"]),
                "response_quality": rounded(stats["response_quality"]),
                "risk_score": rounded(stats["risk_score"]),
            },
            "violation_rates": {
                "prompt_token_limit": rounded(stats["prompt_rate"]) or 0.0,
                "context_length_limit": rounded(stats["context_rate"]) or 0.0,
                "retrieval_score_floor": rounded(stats["retrieval_rate"]) or 0.0,
                "response_quality_floor": rounded(stats["quality_rate"]) or 0.0,
            },
            "top_root_causes": [{"root_cause": cause, "count": int(n)} for cause, n in causes],
            "open_alerts": len(open_alerts),
            "critical_alerts": critical,
            "warning_alerts": warning,
            "saved_tokens": saved,
            "agent_activity": activity,
            "last_updated": max(filter(None, (last_event, last_alert, last_activity)), default=None),
            "policy": policy,
            "filters": {"environment": environment or "all", "severity": severity or "all", "time_range": time_range},
        }

    @staticmethod
    def _agent_activity(
        conn: Connection, project_id: str, environment: str | None, cutoff: datetime | None
    ) -> dict[str, Any]:
        """Totals over agent events: the same rows the activity log lists."""
        c = agent_events.c
        where = [c.project_id == project_id]
        if environment:
            where.append(c.environment == environment)
        if cutoff is not None:
            where.append(c.created_at >= cutoff)
        is_tool = c.kind == "tool_call"
        row = (
            conn.execute(
                select(
                    func.count().label("events"),
                    func.sum(case((is_tool, 1), else_=0)).label("tool_calls"),
                    func.sum(case((and_(is_tool, c.status.in_(FAILED_STATUSES)), 1), else_=0)).label("failed"),
                    func.sum(case((c.kind == "response", 1), else_=0)).label("turns"),
                    func.count(func.distinct(c.task_id)).label("tasks"),
                    func.avg(case((is_tool, c.duration_ms), else_=None)).label("avg_duration"),
                    func.max(c.created_at).label("last"),
                ).where(*where)
            )
            .mappings()
            .one()
        )
        # A finished task's response row holds the tokens of every model call in it; an
        # unfinished task has only its tool calls, which carry their model calls' tokens.
        per_task = conn.execute(
            select(
                func.sum(case((is_tool, c.total_tokens), else_=0)),
                func.sum(case((c.kind == "response", c.total_tokens), else_=0)),
            )
            .where(*where)
            .group_by(c.task_id)
        ).all()
        tokens = sum(float(turn or 0) or float(tool or 0) for tool, turn in per_task)
        tool_calls = int(row["tool_calls"] or 0)
        failed = int(row["failed"] or 0)
        return {
            "events": int(row["events"] or 0),
            "tool_calls": tool_calls,
            "failed_tool_calls": failed,
            "failure_rate": round(failed / tool_calls, 4) if tool_calls else None,
            "turns": int(row["turns"] or 0),
            "tasks": int(row["tasks"] or 0),
            "total_tokens": int(tokens),
            "avg_tool_duration_ms": round(float(row["avg_duration"]), 1) if row["avg_duration"] is not None else None,
            "last_activity": iso(row["last"]),
        }

    # ------------------------------------------------------------------
    # Agent events and diagnosis
    # ------------------------------------------------------------------

    def ingest_agent_events(
        self, project: Mapping[str, Any], batch: Iterable[Mapping[str, Any]]
    ) -> tuple[int, list[dict[str, Any]]]:
        """Store agent attempts and update per-task alerts.

        Returns ``(count, changed_alerts)`` where ``changed_alerts`` are alerts that
        were raised for newly blocked tasks or auto-resolved for recovered ones.
        """
        project_id = project["project_id"]
        capture = bool(project.get("capture_content"))
        rows = []
        for item in batch:
            row = {key: item.get(key) for key in _AGENT_COLUMNS if key != "id"}
            row.update(
                project_id=project_id,
                kind=item.get("kind") or "tool_call",
                tool_name=item.get("tool_name") or "",
                status=item.get("status") or "info",
                attempt=item.get("attempt") or 1,
                error_message=self._clean(item.get("error_message")),
                environment=item.get("environment") or project["environment"],
                # Content is dropped unless the project owner opted in.
                input_text=self._clean(item.get("input")) if capture else None,
                output_text=self._clean(item.get("output")) if capture else None,
                created_at=_event_time(item.get("occurred_at")),
            )
            rows.append(row)
        if not rows:
            return 0, []
        tool_task_ids = {r["task_id"] for r in rows if r["kind"] == "tool_call"}
        with self.engine.begin() as conn:
            conn.execute(insert(agent_events), rows)
            changed = self._update_task_alerts(conn, project_id, tool_task_ids) if tool_task_ids else []
        return len(rows), changed

    def _update_task_alerts(self, conn: Connection, project_id: str, task_ids: set[str]) -> list[dict[str, Any]]:
        policy = self.get_policy(project_id, conn)
        window_start = utcnow() - timedelta(minutes=max(policy["retry_window_minutes"], 1) * 4)
        task_rows = (
            conn.execute(
                select(agent_events)
                .where(
                    and_(
                        agent_events.c.project_id == project_id,
                        agent_events.c.task_id.in_(task_ids),
                        agent_events.c.kind == "tool_call",
                        agent_events.c.created_at >= window_start,
                    )
                )
                .order_by(agent_events.c.id.desc())
                .limit(5000)
            )
            .mappings()
            .all()
        )
        diagnosis = analyze_agent_events([_agent_dict(row) for row in task_rows], policy)

        changed: list[dict[str, Any]] = []
        for task in diagnosis["tasks"]:
            open_alert = (
                conn.execute(
                    select(alerts).where(
                        and_(
                            alerts.c.project_id == project_id,
                            alerts.c.source == "agent",
                            alerts.c.task_id == task["task_id"],
                            alerts.c.resolved == False,  # noqa: E712
                        )
                    )
                )
                .mappings()
                .first()
            )
            if task["status"] == "blocked" and open_alert is None:
                changed.append(
                    self._insert_alert(
                        conn,
                        project_id,
                        severity="critical",
                        message=task["diagnosis"],
                        saved_tokens=task["wasted_tokens"],
                        environment=task["environment"],
                        source="agent",
                        task_id=task["task_id"],
                        root_cause=f"blocking tool: {task['blocking_tool']}",
                    )
                )
            elif task["status"] == "blocked" and open_alert is not None:
                # Still blocked: keep the open alert's waste figure current without re-notifying.
                conn.execute(
                    update(alerts)
                    .where(alerts.c.id == open_alert["id"])
                    .values(
                        message=self._clean(task["diagnosis"]),
                        saved_tokens=task["wasted_tokens"],
                        root_cause=f"blocking tool: {task['blocking_tool']}",
                    )
                )
            elif task["status"] in {"recovered", "healthy"} and open_alert is not None:
                conn.execute(
                    update(alerts).where(alerts.c.id == open_alert["id"]).values(resolved=True, resolved_at=utcnow())
                )
                changed.append(
                    _alert_dict(conn.execute(select(alerts).where(alerts.c.id == open_alert["id"])).mappings().one())
                )
        return changed

    def list_agent_events(
        self,
        project_id: str,
        *,
        environment: str | None = None,
        time_range: str = "all",
        task_id: str | None = None,
        kind: str | None = None,
        tool_name: str | None = None,
        agent_name: str | None = None,
        outcome: str | None = None,
        search: str | None = None,
        before_id: int | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Agent activity, newest first. Filters combine with AND.

        ``outcome`` is ``success`` or ``failed`` (the status groups the diagnosis
        uses); ``search`` matches task, tool, agent, model, error text and stored
        content, case-insensitively.
        """
        c = agent_events.c
        query = select(agent_events).where(c.project_id == project_id)
        if environment:
            query = query.where(c.environment == environment)
        if task_id:
            query = query.where(c.task_id == task_id)
        if kind:
            query = query.where(c.kind == kind)
        if tool_name:
            query = query.where(c.tool_name == tool_name)
        if agent_name:
            query = query.where(c.agent_name == agent_name)
        if outcome == "success":
            query = query.where(c.status.in_(SUCCESS_STATUSES))
        elif outcome == "failed":
            query = query.where(c.status.in_(FAILED_STATUSES))
        if search:
            searchable = (
                c.task_id,
                c.tool_name,
                c.agent_name,
                c.model,
                c.error_type,
                c.error_message,
                c.input_text,
                c.output_text,
            )
            query = query.where(or_(*(col.icontains(search, autoescape=True) for col in searchable)))
        if before_id is not None:
            query = query.where(c.id < before_id)
        if (cutoff := _cutoff(time_range)) is not None:
            query = query.where(c.created_at >= cutoff)
        with self.engine.connect() as conn:
            rows = conn.execute(query.order_by(c.id.desc()).limit(limit)).mappings().all()
        return [_agent_dict(row) for row in rows]

    def diagnose(self, project_id: str, *, environment: str | None = None, time_range: str = "all") -> dict[str, Any]:
        """Run the failed-tool diagnosis over recent tool calls (other activity kinds are ignored)."""
        recent = self.list_agent_events(
            project_id, environment=environment, time_range=time_range, kind="tool_call", limit=5000
        )
        return analyze_agent_events(recent, self.get_policy(project_id))

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------

    def prune(self, retention_days: int) -> dict[str, int]:
        """Delete telemetry and resolved alerts older than ``retention_days``."""
        cutoff = utcnow() - timedelta(days=retention_days)
        with self.engine.begin() as conn:
            removed_events = conn.execute(delete(events).where(events.c.created_at < cutoff)).rowcount
            removed_agent = conn.execute(delete(agent_events).where(agent_events.c.created_at < cutoff)).rowcount
            removed_alerts = conn.execute(
                delete(alerts).where(and_(alerts.c.created_at < cutoff, alerts.c.resolved == True))  # noqa: E712
            ).rowcount
            conn.execute(delete(auth_sessions).where(auth_sessions.c.expires_at < utcnow()))
        return {"events": removed_events, "agent_events": removed_agent, "alerts": removed_alerts}
