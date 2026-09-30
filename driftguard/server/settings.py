"""Server configuration loaded from environment variables (and an optional ``.env`` file)."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Development-only default; Settings.validate() rejects it in production.
DEV_SECRET_KEY = "driftguard-insecure-development-secret-change-me"  # noqa: S105  # nosec B105
_ENVIRONMENTS = {"development", "production", "test"}


def _env(name: str, *legacy: str, default: str | None = None) -> str | None:
    """Read ``name``, falling back to deprecated variable names."""
    value = os.getenv(name)
    if value not in (None, ""):
        return value
    for old in legacy:
        value = os.getenv(old)
        if value not in (None, ""):
            logger.warning("Environment variable %s is deprecated; use %s", old, name)
            return value
    return default


def _int(name: str, default: int, *legacy: str) -> int:
    raw = _env(name, *legacy)
    try:
        return int(raw) if raw is not None else default
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def _float(name: str, default: float) -> float:
    raw = _env(name)
    try:
        return float(raw) if raw is not None else default
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc


def _bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the DriftGuard server.

    Build it with :meth:`from_env` in production, or construct it directly in tests.
    See ``.env.example`` for every variable.
    """

    database_url: str = "sqlite:///./driftguard.db"
    secret_key: str = DEV_SECRET_KEY
    environment: str = "development"
    session_ttl_hours: int = 168
    allow_signup: bool = True
    rate_limit_per_minute: int = 300
    ingest_rate_limit_per_minute: int = 600
    login_rate_limit_per_minute: int = 10
    redis_url: str | None = None
    retention_days: int = 30
    retention_interval_hours: float = 6.0
    scrub_pii: bool = True
    slack_webhook_url: str | None = None
    alert_webhook_url: str | None = None
    drift_alert_cooldown_minutes: int = 15
    cors_origins: tuple[str, ...] = field(default_factory=tuple)
    static_dir: Path | None = None

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @classmethod
    def from_env(cls, load_dotenv_file: bool = True) -> Settings:
        """Read settings from the process environment."""
        if load_dotenv_file:
            try:
                from dotenv import load_dotenv
            except ImportError:  # pragma: no cover - python-dotenv ships with the server extra
                pass
            else:
                load_dotenv()

        cors = _env("DRIFTGUARD_CORS_ORIGINS", default="") or ""
        static_dir = _env("DRIFTGUARD_STATIC_DIR")
        settings = cls(
            database_url=_env("DATABASE_URL", default=cls.database_url) or cls.database_url,
            secret_key=_env("DRIFTGUARD_SECRET_KEY", "JWT_SECRET", "API_SECRET", default=DEV_SECRET_KEY)
            or DEV_SECRET_KEY,
            environment=(_env("DRIFTGUARD_ENV", default="development") or "development").lower(),
            session_ttl_hours=_int("DRIFTGUARD_SESSION_TTL_HOURS", cls.session_ttl_hours),
            allow_signup=_bool("DRIFTGUARD_ALLOW_SIGNUP", cls.allow_signup),
            rate_limit_per_minute=_int(
                "DRIFTGUARD_RATE_LIMIT_PER_MINUTE", cls.rate_limit_per_minute, "RATE_LIMIT_PER_MINUTE"
            ),
            ingest_rate_limit_per_minute=_int(
                "DRIFTGUARD_INGEST_RATE_LIMIT_PER_MINUTE", cls.ingest_rate_limit_per_minute
            ),
            login_rate_limit_per_minute=_int("DRIFTGUARD_LOGIN_RATE_LIMIT_PER_MINUTE", cls.login_rate_limit_per_minute),
            redis_url=_env("REDIS_URL"),
            retention_days=_int("DRIFTGUARD_RETENTION_DAYS", cls.retention_days),
            retention_interval_hours=_float("DRIFTGUARD_RETENTION_INTERVAL_HOURS", cls.retention_interval_hours),
            scrub_pii=_bool("DRIFTGUARD_SCRUB_PII", cls.scrub_pii),
            slack_webhook_url=_env("DRIFTGUARD_SLACK_WEBHOOK"),
            alert_webhook_url=_env("DRIFTGUARD_ALERT_WEBHOOK"),
            drift_alert_cooldown_minutes=_int(
                "DRIFTGUARD_DRIFT_ALERT_COOLDOWN_MINUTES", cls.drift_alert_cooldown_minutes
            ),
            cors_origins=tuple(origin.strip() for origin in cors.split(",") if origin.strip()),
            static_dir=Path(static_dir) if static_dir else None,
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        """Reject unsafe or impossible configuration before the server starts."""
        if self.environment not in _ENVIRONMENTS:
            raise ValueError(f"DRIFTGUARD_ENV must be one of {sorted(_ENVIRONMENTS)}, got {self.environment!r}")
        if self.is_production:
            if self.secret_key == DEV_SECRET_KEY or len(self.secret_key) < 32:
                raise ValueError(
                    "DRIFTGUARD_SECRET_KEY must be set to a random value of at least 32 characters in "
                    'production. Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
                )
        elif self.secret_key == DEV_SECRET_KEY:
            logger.warning("Using the built-in development secret key. Set DRIFTGUARD_SECRET_KEY before deploying.")
        if self.session_ttl_hours < 1:
            raise ValueError("DRIFTGUARD_SESSION_TTL_HOURS must be at least 1")
        if self.retention_days < 0:
            raise ValueError("DRIFTGUARD_RETENTION_DAYS must be 0 (disabled) or positive")
