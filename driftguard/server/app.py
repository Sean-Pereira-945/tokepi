"""FastAPI application: auth, projects, ingestion, dashboard reads, and realtime alerts.

Create the app with :func:`create_app` (``uvicorn --factory driftguard.server.app:create_app``
or the ``driftguard-server`` command).

Access model:

* **Session token** (``Authorization: Bearer``) from ``/auth/login`` — full access to
  the account's projects, including policy changes, key rotation, and deletion.
* **Project API key** (``X-API-Key``) — ingestion plus read access to that one
  project's data. It cannot change policy or delete anything.
"""

from __future__ import annotations

import asyncio
import contextlib
import csv
import hashlib
import io
import json
import logging
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Annotated, Any

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from driftguard import __version__

from .notifications import Notifier
from .ratelimit import RateLimiter, build_rate_limiter
from .realtime import Broadcaster
from .retention import run_retention_loop
from .schemas import (
    AgentEventBatchRequest,
    AgentEventIngestRequest,
    AgentEventKind,
    AlertCreateRequest,
    AlertUpdateRequest,
    DeleteAccountRequest,
    Environment,
    EventBatchRequest,
    EventIngestRequest,
    ExportFormat,
    LoginRequest,
    Outcome,
    PolicyUpdateRequest,
    ProjectCreateRequest,
    ProjectUpdateRequest,
    RegisterRequest,
    Severity,
    TimeRange,
)
from .security import API_KEY_PREFIX
from .service import AuthError, ConflictError, DriftGuardService, NotFoundError
from .settings import Settings

logger = logging.getLogger(__name__)
DEFAULT_STATIC_DIR = Path(__file__).parent / "static"
WS_SUBPROTOCOL = "driftguard"
MAX_EXPORT_ROWS = 10_000
EXPORT_COLUMNS = (
    "id",
    "created_at",
    "kind",
    "environment",
    "agent_name",
    "model",
    "task_id",
    "trace_id",
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
    "input",
    "output",
)


def _export_csv(rows: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


_FALLBACK_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>DriftGuard</title></head>
<body style="font-family:system-ui;background:#000;color:#f4f4f5;padding:40px">
<h1>DriftGuard server is running</h1>
<p>The dashboard has not been built. Run <code>npm ci &amp;&amp; npm run build</code> in <code>frontend/</code>,
or use the API directly. See <a style="color:#28c7d9" href="/docs">/docs</a>.</p></body></html>"""


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_service(request: Request) -> DriftGuardService:
    return request.app.state.service


ServiceDep = Annotated[DriftGuardService, Depends(get_service)]


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit(scope: str) -> Callable[[Request], None]:
    """Dependency enforcing the configured per-minute limit for ``scope``."""

    def dependency(request: Request) -> None:
        settings: Settings = request.app.state.settings
        limiter: RateLimiter = request.app.state.rate_limiter
        if scope == "ingest":
            limit = settings.ingest_rate_limit_per_minute
            api_key = request.headers.get("x-api-key")
            key = f"ingest:{api_key[-12:]}" if api_key else f"ingest-ip:{_client_ip(request)}"
        elif scope == "login":
            limit, key = settings.login_rate_limit_per_minute, f"login:{_client_ip(request)}"
        else:
            # Signed-in callers get their own budget so users behind one NAT don't share a limit.
            credential = _bearer(request.headers.get("authorization")) or request.headers.get("x-api-key")
            if credential:
                key = "api:cred:" + hashlib.sha256(credential.encode()).hexdigest()[:24]
            else:
                key = f"api:ip:{_client_ip(request)}"
            limit = settings.rate_limit_per_minute
        if not limiter.allow(key, limit):
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded", headers={"Retry-After": "60"})

    return dependency


def _bearer(authorization: str | None) -> str | None:
    if authorization and authorization[:7].lower() == "bearer ":
        return authorization[7:].strip() or None
    return None


def current_account(service: ServiceDep, authorization: Annotated[str | None, Header()] = None) -> str:
    token = _bearer(authorization)
    if token is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Missing bearer token", headers={"WWW-Authenticate": "Bearer"}
        )
    try:
        return service.resolve_session(token)
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc), headers={"WWW-Authenticate": "Bearer"}) from exc


AccountDep = Annotated[str, Depends(current_account)]


def _project_from_key(service: DriftGuardService, api_key: str, project_id: str) -> dict[str, Any]:
    try:
        project = service.project_for_api_key(api_key)
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key") from exc
    if project["project_id"] != project_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "API key does not belong to this project")
    return project


def project_owner(project_id: str, service: ServiceDep, account_id: AccountDep) -> dict[str, Any]:
    """The project, if the session's account owns it."""
    try:
        return service.get_owned_project(project_id, account_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found") from exc


def project_reader(
    project_id: str,
    service: ServiceDep,
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """The project, via its API key or the owner's session."""
    if x_api_key:
        return _project_from_key(service, x_api_key, project_id)
    return project_owner(project_id, service, current_account(service, authorization))


def ingest_project(
    project_id: str, service: ServiceDep, x_api_key: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    """The project for SDK ingestion; requires its API key."""
    if not x_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-API-Key header")
    return _project_from_key(service, x_api_key, project_id)


def activity_filters(
    environment: Environment | None = None,
    time_range: TimeRange = "all",
    task_id: str | None = None,
    kind: AgentEventKind | None = None,
    tool_name: str | None = None,
    agent_name: str | None = None,
    outcome: Outcome | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> dict[str, Any]:
    """Query filters shared by the activity list and export."""
    return {
        "environment": environment,
        "time_range": time_range,
        "task_id": task_id,
        "kind": kind,
        "tool_name": tool_name,
        "agent_name": agent_name,
        "outcome": outcome,
        "search": q.strip() if q and q.strip() else None,
    }


ActivityFilters = Annotated[dict[str, Any], Depends(activity_filters)]


OwnerDep = Annotated[dict[str, Any], Depends(project_owner)]
ReaderDep = Annotated[dict[str, Any], Depends(project_reader)]
IngestDep = Annotated[dict[str, Any], Depends(ingest_project)]


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the DriftGuard FastAPI app. Reads the environment when ``settings`` is omitted."""
    settings = settings or Settings.from_env()
    service = DriftGuardService(
        settings.database_url,
        settings.secret_key,
        session_ttl_hours=settings.session_ttl_hours,
        scrub_pii=settings.scrub_pii,
        drift_alert_cooldown_minutes=settings.drift_alert_cooldown_minutes,
    )
    notifier = Notifier(settings.slack_webhook_url, settings.alert_webhook_url)
    broadcaster = Broadcaster(settings.redis_url)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await broadcaster.start()
        retention_task = None
        if settings.retention_days > 0:
            retention_task = asyncio.create_task(
                run_retention_loop(service, settings.retention_days, settings.retention_interval_hours)
            )
        try:
            yield
        finally:
            if retention_task:
                retention_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await retention_task
            broadcaster.stop()
            notifier.shutdown()
            service.engine.dispose()

    app = FastAPI(title="DriftGuard", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.service = service
    app.state.rate_limiter = build_rate_limiter(settings.redis_url)
    app.state.notifier = notifier
    app.state.broadcaster = broadcaster

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["Authorization", "Content-Type", "X-API-Key"],
        )

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Callable[[Request], Any]) -> Any:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if settings.is_production:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    def publish_alerts(project_id: str, changed: list[dict[str, Any]]) -> None:
        for alert in changed:
            notifier.notify(project_id, alert)
            action = "resolved" if alert["resolved"] else "created"
            broadcaster.publish(project_id, {"type": "alert", "action": action, "alert": alert})

    default_limit = [Depends(rate_limit("default"))]
    ingest_limit = [Depends(rate_limit("ingest"))]

    # -- Health ---------------------------------------------------------------

    @app.get("/health", tags=["meta"])
    def health() -> JSONResponse:
        try:
            service.ping()
        except Exception:
            logger.exception("Health check: database unreachable")
            return JSONResponse({"status": "error", "database": "unreachable", "version": __version__}, 503)
        return JSONResponse({"status": "ok", "database": "ok", "version": __version__})

    # -- Auth -----------------------------------------------------------------

    @app.get("/auth/config", tags=["auth"], dependencies=default_limit)
    def auth_config() -> dict[str, Any]:
        return {"allow_signup": settings.allow_signup, "version": __version__}

    @app.post("/auth/register", tags=["auth"], status_code=201, dependencies=[Depends(rate_limit("login"))])
    def register(body: RegisterRequest) -> dict[str, Any]:
        if not settings.allow_signup:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Sign-up is disabled on this server")
        try:
            account = service.register(body.name, body.email, body.password)
        except ConflictError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
        return {**account, **service.create_session(account["account_id"])}

    @app.post("/auth/login", tags=["auth"], dependencies=[Depends(rate_limit("login"))])
    def login(body: LoginRequest) -> dict[str, Any]:
        try:
            account = service.authenticate(body.email, body.password)
        except AuthError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
        return {**account, **service.create_session(account["account_id"])}

    @app.post(
        "/auth/logout",
        tags=["auth"],
        status_code=204,
        response_class=Response,
        response_model=None,
        dependencies=default_limit,
    )
    def logout(account_id: AccountDep, authorization: Annotated[str | None, Header()] = None) -> None:
        service.revoke_session(_bearer(authorization) or "")

    @app.get("/auth/me", tags=["auth"], dependencies=default_limit)
    def me(account_id: AccountDep) -> dict[str, Any]:
        return service.get_account(account_id)

    @app.delete(
        "/auth/me",
        tags=["auth"],
        status_code=204,
        response_class=Response,
        response_model=None,
        dependencies=[Depends(rate_limit("login"))],
    )
    def delete_me(body: DeleteAccountRequest, account_id: AccountDep) -> None:
        account = service.get_account(account_id)
        try:
            service.authenticate(account["email"] or "", body.password)
        except AuthError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Password is incorrect") from exc
        service.delete_account(account_id)

    # -- Projects ---------------------------------------------------------------

    @app.get("/projects", tags=["projects"], dependencies=default_limit)
    def list_projects(
        authorization: Annotated[str | None, Header()] = None,
        x_api_key: Annotated[str | None, Header()] = None,
    ) -> list[dict[str, Any]]:
        if x_api_key:
            try:
                return [service.project_for_api_key(x_api_key)]
            except AuthError as exc:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key") from exc
        return service.list_projects(current_account(service, authorization))

    @app.post("/projects", tags=["projects"], status_code=201, dependencies=default_limit)
    def create_project(body: ProjectCreateRequest, account_id: AccountDep) -> dict[str, Any]:
        try:
            project, api_key = service.create_project(account_id, body.project_id, body.name, body.environment)
        except ConflictError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
        return {**project, "api_key": api_key}

    @app.get("/projects/{project_id}", tags=["projects"], dependencies=default_limit)
    def get_project(project: ReaderDep) -> dict[str, Any]:
        return project

    @app.patch("/projects/{project_id}", tags=["projects"], dependencies=default_limit)
    def update_project(body: ProjectUpdateRequest, project: OwnerDep) -> dict[str, Any]:
        return service.update_project(project["project_id"], body.model_dump(exclude_none=True))

    @app.delete(
        "/projects/{project_id}",
        tags=["projects"],
        status_code=204,
        response_class=Response,
        response_model=None,
        dependencies=default_limit,
    )
    def delete_project(project: OwnerDep) -> None:
        service.delete_project(project["project_id"])

    @app.post("/projects/{project_id}/api-key", tags=["projects"], dependencies=default_limit)
    def rotate_api_key(project: OwnerDep) -> dict[str, Any]:
        updated, api_key = service.rotate_api_key(project["project_id"])
        return {**updated, "api_key": api_key}

    # -- Policy -----------------------------------------------------------------

    @app.get("/projects/{project_id}/policy", tags=["policy"], dependencies=default_limit)
    def get_policy(project: ReaderDep) -> dict[str, Any]:
        return service.get_policy(project["project_id"])

    @app.put("/projects/{project_id}/policy", tags=["policy"], dependencies=default_limit)
    def update_policy(body: PolicyUpdateRequest, project: OwnerDep) -> dict[str, Any]:
        return service.update_policy(project["project_id"], body.model_dump(exclude_none=True))

    # -- Dashboard reads ----------------------------------------------------------

    @app.get("/projects/{project_id}/summary", tags=["dashboard"], dependencies=default_limit)
    def summary(
        project: ReaderDep,
        environment: Environment | None = None,
        severity: Severity | None = None,
        time_range: TimeRange = "all",
    ) -> dict[str, Any]:
        return service.summary(project["project_id"], environment=environment, severity=severity, time_range=time_range)

    @app.get("/projects/{project_id}/events", tags=["dashboard"], dependencies=default_limit)
    def list_events(
        project: ReaderDep,
        environment: Environment | None = None,
        time_range: TimeRange = "all",
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
        before_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return service.list_events(
            project["project_id"], environment=environment, time_range=time_range, limit=limit, before_id=before_id
        )

    @app.post("/projects/{project_id}/events", tags=["dashboard"], dependencies=default_limit)
    def send_test_event(body: EventIngestRequest, project: OwnerDep) -> dict[str, Any]:
        """Record one event from the dashboard's Test Telemetry form."""
        results, new_alerts = service.ingest_events(project, [body.model_dump(exclude_none=True)])
        publish_alerts(project["project_id"], new_alerts)
        return {"project_id": project["project_id"], "status": "ingested", **results[0]}

    @app.get("/projects/{project_id}/alerts", tags=["alerts"], dependencies=default_limit)
    def list_alerts(
        project: ReaderDep,
        environment: Environment | None = None,
        severity: Severity | None = None,
        time_range: TimeRange = "all",
        resolved: bool | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 200,
    ) -> list[dict[str, Any]]:
        return service.list_alerts(
            project["project_id"],
            severity=severity,
            environment=environment,
            time_range=time_range,
            resolved=resolved,
            limit=limit,
        )

    @app.post("/projects/{project_id}/alerts", tags=["alerts"], status_code=201, dependencies=default_limit)
    def create_alert(body: AlertCreateRequest, project: OwnerDep) -> dict[str, Any]:
        alert = service.create_alert(
            project["project_id"],
            body.severity,
            body.message,
            saved_tokens=body.saved_tokens,
            environment=body.environment,
        )
        publish_alerts(project["project_id"], [alert])
        return alert

    @app.patch("/projects/{project_id}/alerts/{alert_id}", tags=["alerts"], dependencies=default_limit)
    def update_alert(alert_id: int, body: AlertUpdateRequest, project: OwnerDep) -> dict[str, Any]:
        try:
            alert = service.set_alert_resolved(project["project_id"], alert_id, body.resolved)
        except NotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found") from exc
        action = "resolved" if alert["resolved"] else "reopened"
        broadcaster.publish(project["project_id"], {"type": "alert", "action": action, "alert": alert})
        return alert

    @app.get("/projects/{project_id}/agent-events", tags=["agents"], dependencies=default_limit)
    def list_agent_events(
        project: ReaderDep,
        filters: ActivityFilters,
        before_id: int | None = None,
        limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    ) -> list[dict[str, Any]]:
        return service.list_agent_events(project["project_id"], before_id=before_id, limit=limit, **filters)

    @app.get("/projects/{project_id}/agent-events/export", tags=["agents"], dependencies=default_limit)
    def export_agent_events(project: ReaderDep, filters: ActivityFilters, format: ExportFormat = "csv") -> Response:
        rows = service.list_agent_events(project["project_id"], limit=MAX_EXPORT_ROWS, **filters)
        filename = f"driftguard-{project['project_id']}-activity.{format}"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        if format == "json":
            return Response(json.dumps(rows, indent=2), media_type="application/json", headers=headers)
        return PlainTextResponse(_export_csv(rows), media_type="text/csv", headers=headers)

    @app.get("/projects/{project_id}/agent-diagnosis", tags=["agents"], dependencies=default_limit)
    def agent_diagnosis(
        project: ReaderDep, environment: Environment | None = None, time_range: TimeRange = "all"
    ) -> dict[str, Any]:
        return service.diagnose(project["project_id"], environment=environment, time_range=time_range)

    # -- SDK ingestion ------------------------------------------------------------

    def _ingest_events(project: dict[str, Any], items: list[EventIngestRequest]) -> list[dict[str, Any]]:
        results, new_alerts = service.ingest_events(project, [i.model_dump(exclude_none=True) for i in items])
        publish_alerts(project["project_id"], new_alerts)
        return results

    def _ingest_agent(project: dict[str, Any], items: list[AgentEventIngestRequest]) -> int:
        count, changed = service.ingest_agent_events(project, [i.model_dump(exclude_none=True) for i in items])
        publish_alerts(project["project_id"], changed)
        # Tell open dashboards to refresh their activity views (the rows are fetched over HTTP).
        broadcaster.publish(project["project_id"], {"type": "activity", "count": count})
        return count

    @app.post("/events/{project_id}", tags=["ingest"], dependencies=ingest_limit)
    def ingest_event(body: EventIngestRequest, project: IngestDep) -> dict[str, Any]:
        result = _ingest_events(project, [body])[0]
        return {"project_id": project["project_id"], "status": "ingested", **result}

    @app.post("/events/{project_id}/batch", tags=["ingest"], dependencies=ingest_limit)
    def ingest_event_batch(body: EventBatchRequest, project: IngestDep) -> dict[str, Any]:
        results = _ingest_events(project, body.events)
        return {
            "project_id": project["project_id"],
            "ingested": len(results),
            "critical": sum(1 for r in results if r["severity"] == "critical"),
        }

    @app.post("/agent-events/{project_id}", tags=["ingest"], dependencies=ingest_limit)
    def ingest_agent_event(body: AgentEventIngestRequest, project: IngestDep) -> dict[str, Any]:
        _ingest_agent(project, [body])
        return {"project_id": project["project_id"], "status": "ingested"}

    @app.post("/agent-events/{project_id}/batch", tags=["ingest"], dependencies=ingest_limit)
    def ingest_agent_event_batch(body: AgentEventBatchRequest, project: IngestDep) -> dict[str, Any]:
        return {"project_id": project["project_id"], "ingested": _ingest_agent(project, body.events)}

    # -- Realtime -----------------------------------------------------------------

    @app.websocket("/ws/projects/{project_id}")
    async def realtime(
        websocket: WebSocket, project_id: str, token: str | None = None, api_key: str | None = None
    ) -> None:
        """Stream ``{"type": "alert", "alert": {...}}`` messages for a project.

        Preferred: pass the credential as a subprotocol, e.g. in a browser
        ``new WebSocket(url, ["driftguard", sessionToken])``; the server replies
        with the ``driftguard`` subprotocol. Credentials in subprotocols stay out
        of URL access logs. ``?token=`` and ``?api_key=`` query parameters are
        also accepted for simple clients.
        """
        subprotocols = [p.strip() for p in websocket.headers.get("sec-websocket-protocol", "").split(",")]
        accept_subprotocol = None
        if len(subprotocols) >= 2 and subprotocols[0] == WS_SUBPROTOCOL:
            accept_subprotocol = WS_SUBPROTOCOL
            credential = subprotocols[1]
            if credential.startswith(API_KEY_PREFIX):
                api_key = credential
            else:
                token = credential
        try:
            if api_key:
                await run_in_threadpool(_project_from_key, service, api_key, project_id)
            elif token:
                account_id = await run_in_threadpool(service.resolve_session, token)
                await run_in_threadpool(service.get_owned_project, project_id, account_id)
            else:
                raise AuthError("Missing credentials")
        except (AuthError, NotFoundError, HTTPException):
            # Accept first so browsers see close code 4401 instead of a failed handshake.
            await websocket.accept(subprotocol=accept_subprotocol)
            await websocket.close(code=4401)
            return
        await broadcaster.connect(project_id, websocket, subprotocol=accept_subprotocol)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            broadcaster.disconnect(project_id, websocket)

    # -- Dashboard ------------------------------------------------------------------

    static_dir = settings.static_dir or DEFAULT_STATIC_DIR
    if (static_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="dashboard")
    else:

        @app.get("/", include_in_schema=False)
        def dashboard_missing() -> HTMLResponse:
            return HTMLResponse(_FALLBACK_PAGE)

    return app
