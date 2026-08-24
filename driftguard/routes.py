from __future__ import annotations

import re
from typing import Any, Annotated

from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator, model_validator

from .analytics import build_project_snapshot
from .agent_analysis import analyze_agent_events
from .config import get_database_url
from .dashboard_data import build_dashboard_summary
from .middleware import build_api_key_dependency, rate_limit_default, rate_limit_ingestion
from .service import DEFAULT_POLICY, DriftGuardService

app = FastAPI(title="DriftGuard SaaS API", version="0.3.0")

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

service = DriftGuardService(database_url=get_database_url())
require_valid_api_key = build_api_key_dependency(service)

_PROJECT_ID_RE = re.compile(r"^[a-zA-Z0-9\-_]{1,64}$")


@app.get("/", response_class=HTMLResponse, response_model=None, dependencies=[Depends(rate_limit_default)])
def get_dashboard() -> Any:
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<html><body><h1>DriftGuard API Operational</h1></body></html>")




# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def require_account_from_token(authorization: str | None = Header(default=None)) -> str:
    if authorization is None:
        if "default" not in service.accounts:
            service.create_account("default", "Default account")
        return "default"

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        return service.get_account_for_session(token)
    except KeyError as exc:
        raise HTTPException(status_code=401, detail="Invalid session token") from exc


def resolve_project_access(
    project_id: str,
    account_id: str,
    x_api_key: str | None = None,
):
    """Resolve a project by its API key or the authenticated account session."""
    if x_api_key:
        try:
            project = service.get_project_by_api_key(x_api_key)
        except KeyError as exc:
            raise HTTPException(status_code=401, detail="Invalid project API key") from exc
        if project.project_id != project_id:
            raise HTTPException(status_code=403, detail="API key does not belong to this project")
        return project
    try:
        return service.get_project(project_id, account_id=account_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class AccountCreateRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        if len(v) > 128:
            raise ValueError("name must be 128 characters or fewer")
        return v


class ProjectCreateRequest(BaseModel):
    project_id: str
    name: str
    environment: str = "prod"
    account_id: str = "default"

    @field_validator("project_id")
    @classmethod
    def valid_project_id(cls, v: str) -> str:
        if not _PROJECT_ID_RE.match(v):
            raise ValueError(
                "project_id must be 1–64 alphanumeric characters, hyphens, or underscores"
            )
        return v

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        if len(v) > 128:
            raise ValueError("name must be 128 characters or fewer")
        return v

    @field_validator("environment")
    @classmethod
    def valid_environment(cls, v: str) -> str:
        allowed = {"prod", "staging", "dev", "test"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {sorted(allowed)}")
        return v


class AlertCreateRequest(BaseModel):
    severity: str
    message: str
    saved_tokens: float = 0.0
    project_id: str
    account_id: str | None = None

    @field_validator("severity")
    @classmethod
    def valid_severity(cls, v: str) -> str:
        if v not in {"warning", "critical", "stable"}:
            raise ValueError("severity must be 'warning', 'critical', or 'stable'")
        return v

    @field_validator("saved_tokens")
    @classmethod
    def non_negative_tokens(cls, v: float) -> float:
        if v < 0:
            raise ValueError("saved_tokens must be >= 0.0")
        return v

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be empty")
        return v


class EventIngestRequest(BaseModel):
    prompt_tokens: float | None = None
    retrieval_score: float | None = None
    context_length: float | None = None
    response_quality: float | None = None
    environment: str | None = None

    @field_validator("retrieval_score", "response_quality")
    @classmethod
    def score_in_range(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("Score values must be between 0.0 and 1.0")
        return v

    @field_validator("prompt_tokens", "context_length")
    @classmethod
    def non_negative(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("Value must be >= 0")
        return v


class AgentEventIngestRequest(BaseModel):
    task_id: str
    trace_id: str | None = None
    agent_name: str | None = None
    model: str | None = None
    tool_name: str
    tool_call_id: str | None = None
    attempt: int = 1
    status: str
    error_type: str | None = None
    error_message: str | None = None
    prompt_tokens: float | None = None
    completion_tokens: float | None = None
    total_tokens: float | None = None
    duration_ms: float | None = None
    environment: str | None = None

    @field_validator("task_id", "tool_name", "status")
    @classmethod
    def required_text(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @field_validator("attempt")
    @classmethod
    def positive_attempt(cls, v: int) -> int:
        if v < 1:
            raise ValueError("attempt must be >= 1")
        return v

    @field_validator("prompt_tokens", "completion_tokens", "total_tokens", "duration_ms")
    @classmethod
    def non_negative_agent_values(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("value must be >= 0")
        return v

class PolicyUpdateRequest(BaseModel):
    prompt_token_limit: float | None = None
    retrieval_score_floor: float | None = None
    context_length_limit: float | None = None
    response_quality_floor: float | None = None

    @field_validator("retrieval_score_floor", "response_quality_floor")
    @classmethod
    def floor_in_range(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("Floor values must be between 0.0 and 1.0")
        return v

    @field_validator("prompt_token_limit", "context_length_limit")
    @classmethod
    def limit_positive(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("Limit values must be > 0")
        return v


# ---------------------------------------------------------------------------
# Routes — Health
# ---------------------------------------------------------------------------

@app.get("/health", dependencies=[Depends(rate_limit_default)])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "driftguard-saas", "version": "0.3.0"}


# ---------------------------------------------------------------------------
# Routes — Account management
# ---------------------------------------------------------------------------

@app.post("/accounts", dependencies=[Depends(rate_limit_default)])
def create_account(request: AccountCreateRequest) -> dict[str, str]:
    """Register a new account.  Returns the account_id and a session token."""
    import uuid
    account_id = f"acct-{uuid.uuid4().hex[:12]}"
    service.create_account(account_id, request.name)
    token = service.create_session(account_id)
    return {
        "account_id": account_id,
        "name": request.name,
        "token": token,
    }


@app.get("/accounts/me", dependencies=[Depends(rate_limit_default)])
def get_current_account(
    account_id: str = Depends(require_account_from_token),
) -> dict[str, str]:
    """Return details about the currently authenticated account."""
    try:
        account = service.get_account(account_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"account_id": account.account_id, "name": account.name}


# ---------------------------------------------------------------------------
# Routes — Auth
# ---------------------------------------------------------------------------

@app.post("/auth/session", dependencies=[Depends(rate_limit_default)])
def create_session(account_id: str) -> dict[str, str]:
    """Create a new session token for an existing account."""
    try:
        token = service.create_session(account_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"account_id": account_id, "token": token}


# ---------------------------------------------------------------------------
# Routes — Projects
# ---------------------------------------------------------------------------

@app.post("/projects", dependencies=[Depends(rate_limit_default)])
def create_project(
    request: ProjectCreateRequest,
    account_id: str = Depends(require_account_from_token),
) -> dict[str, str]:
    project = service.create_project(
        request.project_id,
        request.name,
        environment=request.environment,
        account_id=account_id,
    )
    return {
        "project_id": project.project_id,
        "name": project.name,
        "environment": project.environment,
        "account_id": project.account_id,
        "api_key": project.api_key,
    }


@app.get("/projects", dependencies=[Depends(rate_limit_default)])
def list_projects(
    x_api_key: str | None = Header(default=None),
    account_id: str = Depends(require_account_from_token),
) -> list[dict[str, str]]:
    if x_api_key:
        try:
            projects = [service.get_project_by_api_key(x_api_key)]
        except KeyError as exc:
            raise HTTPException(status_code=401, detail="Invalid project API key") from exc
    else:
        projects = service.list_projects(account_id=account_id)
    return [
        {
            "project_id": p.project_id,
            "name": p.name,
            "environment": p.environment,
            "account_id": p.account_id,
        }
        for p in projects
    ]


@app.get("/projects/{project_id}", dependencies=[Depends(rate_limit_default)])
def get_project(
    project_id: str,
    account_id: str = Depends(require_account_from_token),
) -> dict[str, object]:
    try:
        project = service.get_project(project_id, account_id=account_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "project_id": project.project_id,
        "name": project.name,
        "environment": project.environment,
        "account_id": project.account_id,
        "alerts": project.alerts,
    }


@app.delete("/projects/{project_id}", dependencies=[Depends(rate_limit_default)])
def delete_project(
    project_id: str,
    account_id: str = Depends(require_account_from_token),
) -> dict[str, str]:
    try:
        service.delete_project(project_id, account_id=account_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted", "project_id": project_id}


@app.get("/projects/{project_id}/summary", dependencies=[Depends(rate_limit_default)])
def get_project_summary(
    project_id: str,
    x_api_key: str | None = Header(default=None),
    account_id: str = Depends(require_account_from_token),
) -> dict[str, object]:
    project = resolve_project_access(project_id, account_id, x_api_key)

    project_snapshot = build_project_snapshot(
        project.project_id, project.alerts, environment=project.environment
    )
    dashboard_summary = build_dashboard_summary(project.project_id, project.alerts)

    payload = {
        **project_snapshot,
        **dashboard_summary,
        "environment": project.environment,
        "account_id": project.account_id,
        "project_id": project.project_id,
    }
    return payload


@app.get("/projects/{project_id}/dashboard", dependencies=[Depends(rate_limit_default)])
def get_project_dashboard_alias(
    project_id: str,
    account_id: str = Depends(require_account_from_token),
) -> dict[str, object]:
    return get_project_summary(project_id, account_id=account_id)


# ---------------------------------------------------------------------------
# Routes — Alerts
# ---------------------------------------------------------------------------

@app.post("/alerts", dependencies=[Depends(rate_limit_default)])
def create_alert(
    request: AlertCreateRequest,
    account_id: str = Depends(require_account_from_token),
) -> dict[str, object]:
    try:
        alert = service.add_alert(
            request.project_id,
            {
                "severity": request.severity,
                "message": request.message,
                "saved_tokens": request.saved_tokens,
            },
            account_id=account_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return alert


@app.get("/alerts/{project_id}", dependencies=[Depends(rate_limit_default)])
def get_alerts_for_project(
    project_id: str,
    x_api_key: str | None = Header(default=None),
    account_id: str = Depends(require_account_from_token),
) -> list[dict[str, Any]]:
    project = resolve_project_access(project_id, account_id, x_api_key)
    return project.alerts


# ---------------------------------------------------------------------------
# Routes — Telemetry event ingestion (SDK → backend)
# ---------------------------------------------------------------------------

@app.post(
    "/events/{project_id}",
    dependencies=[Depends(rate_limit_ingestion)],
)
def ingest_event(
    project_id: str,
    request: EventIngestRequest,
    api_project_id: str = Depends(require_valid_api_key),
) -> dict[str, Any]:
    """Ingest a telemetry event from the SDK.

    Authenticated via ``X-API-Key`` header containing the project's API key.
    The key must belong to the project identified in the URL path.
    """
    if api_project_id != project_id:
        raise HTTPException(
            status_code=403,
            detail="API key does not belong to this project",
        )
    result = service.ingest_event(project_id, request.model_dump(exclude_none=True))
    return result


@app.post(
    "/projects/{project_id}/events",
    dependencies=[Depends(rate_limit_default)],
)
def ingest_dashboard_event(
    project_id: str,
    request: EventIngestRequest,
    x_api_key: str | None = Header(default=None),
    account_id: str = Depends(require_account_from_token),
) -> dict[str, Any]:
    """Ingest a test event from the authenticated dashboard."""
    resolve_project_access(project_id, account_id, x_api_key)
    return service.ingest_event(project_id, request.model_dump(exclude_none=True))


@app.get("/events/{project_id}", dependencies=[Depends(rate_limit_default)])
def list_events(
    project_id: str,
    limit: int = 100,
    x_api_key: str | None = Header(default=None),
    account_id: str = Depends(require_account_from_token),
) -> list[dict[str, Any]]:
    """Return recent telemetry events for a project (up to 100 most recent)."""
    resolve_project_access(project_id, account_id, x_api_key)
    clamped_limit = max(1, min(limit, 100))
    return service.list_events(project_id, limit=clamped_limit)


@app.post(
    "/agent-events/{project_id}",
    dependencies=[Depends(rate_limit_ingestion)],
)
def ingest_agent_event(
    project_id: str,
    request: AgentEventIngestRequest,
    api_project_id: str = Depends(require_valid_api_key),
) -> dict[str, Any]:
    """Ingest one task/tool attempt from an agent adapter."""
    if api_project_id != project_id:
        raise HTTPException(status_code=403, detail="API key does not belong to this project")
    return service.ingest_agent_event(project_id, request.model_dump(exclude_none=True))


@app.get("/projects/{project_id}/agent-diagnosis", dependencies=[Depends(rate_limit_default)])
def get_agent_diagnosis(
    project_id: str,
    x_api_key: str | None = Header(default=None),
    account_id: str = Depends(require_account_from_token),
) -> dict[str, Any]:
    """Analyze recent agent attempts and identify retry waste and blocked tools."""
    resolve_project_access(project_id, account_id, x_api_key)
    events = service.list_agent_events(project_id)
    return analyze_agent_events(events)


# ---------------------------------------------------------------------------
# Routes — Policy management
# ---------------------------------------------------------------------------

@app.get("/projects/{project_id}/policy", dependencies=[Depends(rate_limit_default)])
def get_policy(
    project_id: str,
    x_api_key: str | None = Header(default=None),
    account_id: str = Depends(require_account_from_token),
) -> dict[str, float]:
    """Fetch drift policy thresholds for a project.

    Accepts either a session bearer token (dashboard use) or an X-API-Key header
    (SDK use), so the SDK can pull thresholds without a user session.
    """
    resolve_project_access(project_id, account_id, x_api_key)

    return service.get_policy(project_id)


@app.put("/projects/{project_id}/policy", dependencies=[Depends(rate_limit_default)])
def update_policy(
    project_id: str,
    request: PolicyUpdateRequest,
    x_api_key: str | None = Header(default=None),
    account_id: str = Depends(require_account_from_token),
) -> dict[str, float]:
    """Update drift policy thresholds for a project."""
    resolve_project_access(project_id, account_id, x_api_key)

    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    return service.upsert_policy(project_id, updates)
