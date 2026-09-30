"""Request validation models for the DriftGuard API."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_BATCH_SIZE = 500
MAX_ERROR_MESSAGE = 4000

Environment = Literal["prod", "staging", "dev", "test"]
Severity = Literal["stable", "warning", "critical"]
TimeRange = Literal["15m", "1h", "24h", "7d", "30d", "all"]

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ProjectId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
Score = Annotated[float, Field(ge=0.0, le=1.0)]
NonNegative = Annotated[float, Field(ge=0.0)]
MetadataValue = str | int | float | bool | None


def _trimmed(value: str, field: str, max_length: int) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field} must not be empty")
    if len(value) > max_length:
        raise ValueError(f"{field} must be {max_length} characters or fewer")
    return value


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str = Field(min_length=8, max_length=256)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _trimmed(v, "name", 128)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if len(v) > 320 or not _EMAIL_RE.match(v):
            raise ValueError("email must be a valid email address")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str = Field(max_length=256)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return v.strip().lower()


class DeleteAccountRequest(BaseModel):
    password: str = Field(max_length=256)


# ---------------------------------------------------------------------------
# Projects, policy, alerts
# ---------------------------------------------------------------------------


class ProjectCreateRequest(BaseModel):
    project_id: ProjectId
    name: str
    environment: Environment = "prod"

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _trimmed(v, "name", 128)


class PolicyUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_token_limit: float | None = Field(default=None, gt=0)
    retrieval_score_floor: Score | None = None
    context_length_limit: float | None = Field(default=None, gt=0)
    response_quality_floor: Score | None = None
    blocked_after_failures: int | None = Field(default=None, ge=1, le=100)
    retry_window_minutes: float | None = Field(default=None, ge=0, le=10080)


class AlertCreateRequest(BaseModel):
    severity: Severity
    message: str
    saved_tokens: NonNegative = 0.0
    environment: Environment | None = None

    @field_validator("message")
    @classmethod
    def _message(cls, v: str) -> str:
        return _trimmed(v, "message", 2000)


class AlertUpdateRequest(BaseModel):
    resolved: bool


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


class EventIngestRequest(BaseModel):
    """One LLM request's normalized telemetry."""

    prompt_tokens: NonNegative | None = None
    retrieval_score: Score | None = None
    context_length: NonNegative | None = None
    response_quality: Score | None = None
    environment: Environment | None = None
    occurred_at: datetime | None = None
    metadata: dict[str, MetadataValue] | None = None

    @field_validator("metadata")
    @classmethod
    def _metadata(cls, v: dict[str, MetadataValue] | None) -> dict[str, MetadataValue] | None:
        if v is None:
            return v
        if len(v) > 32:
            raise ValueError("metadata may have at most 32 keys")
        for key, value in v.items():
            if len(key) > 64 or (isinstance(value, str) and len(value) > 512):
                raise ValueError("metadata keys must be <= 64 chars and string values <= 512 chars")
        return v


class EventBatchRequest(BaseModel):
    events: list[EventIngestRequest] = Field(min_length=1, max_length=MAX_BATCH_SIZE)


class AgentEventIngestRequest(BaseModel):
    """One agent task or tool attempt."""

    task_id: str
    tool_name: str
    status: str
    trace_id: str | None = Field(default=None, max_length=128)
    agent_name: str | None = Field(default=None, max_length=128)
    model: str | None = Field(default=None, max_length=128)
    tool_call_id: str | None = Field(default=None, max_length=128)
    attempt: int = Field(default=1, ge=1)
    error_type: str | None = Field(default=None, max_length=128)
    error_message: str | None = None
    input_hash: str | None = Field(default=None, max_length=64)
    prompt_tokens: NonNegative | None = None
    completion_tokens: NonNegative | None = None
    total_tokens: NonNegative | None = None
    duration_ms: NonNegative | None = None
    environment: Environment | None = None
    occurred_at: datetime | None = None

    @field_validator("task_id", "tool_name")
    @classmethod
    def _required(cls, v: str) -> str:
        return _trimmed(v, "value", 128)

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        return _trimmed(v, "status", 32).lower()

    @field_validator("error_message")
    @classmethod
    def _truncate(cls, v: str | None) -> str | None:
        """Keep the start of long tracebacks instead of rejecting the event."""
        if v is not None and len(v) > MAX_ERROR_MESSAGE:
            return v[:MAX_ERROR_MESSAGE] + " …[truncated]"
        return v


class AgentEventBatchRequest(BaseModel):
    events: list[AgentEventIngestRequest] = Field(min_length=1, max_length=MAX_BATCH_SIZE)
