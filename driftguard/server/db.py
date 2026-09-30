"""Database schema and engine setup (SQLAlchemy Core; SQLite and PostgreSQL).

``init_db`` creates missing tables, adds columns introduced after v0.3 to existing
databases, and hashes plaintext API keys left by v0.3.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    event,
    false,
    inspect,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

from .security import api_key_hint, hash_api_key

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Store UTC timestamps; always return timezone-aware UTC datetimes.

    SQLite has no timezone type, so values are stored naive in UTC there.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


metadata = MetaData()

accounts = Table(
    "accounts",
    metadata,
    Column("account_id", String(64), primary_key=True),
    Column("name", String(128), nullable=False),
    Column("email", String(320)),
    Column("password_hash", String(255)),
    Column("created_at", UTCDateTime, default=utcnow),
    Index("ix_accounts_email", "email", unique=True),
)

projects = Table(
    "projects",
    metadata,
    Column("project_id", String(64), primary_key=True),
    Column("account_id", String(64), ForeignKey("accounts.account_id"), nullable=False),
    Column("name", String(128), nullable=False),
    Column("environment", String(16), nullable=False, server_default="prod"),
    Column("api_key_hash", String(64)),
    Column("api_key_hint", String(16)),
    Column("created_at", UTCDateTime, default=utcnow),
    Index("ix_projects_account", "account_id"),
    Index("ix_projects_api_key_hash", "api_key_hash", unique=True),
)

auth_sessions = Table(
    "auth_sessions",
    metadata,
    Column("jti", String(64), primary_key=True),
    Column("account_id", String(64), ForeignKey("accounts.account_id"), nullable=False),
    Column("created_at", UTCDateTime, default=utcnow, nullable=False),
    Column("expires_at", UTCDateTime, nullable=False),
    Column("revoked_at", UTCDateTime),
    Index("ix_auth_sessions_account", "account_id"),
)

policies = Table(
    "policies",
    metadata,
    Column("project_id", String(64), ForeignKey("projects.project_id"), primary_key=True),
    Column("prompt_token_limit", Float),
    Column("retrieval_score_floor", Float),
    Column("context_length_limit", Float),
    Column("response_quality_floor", Float),
    Column("blocked_after_failures", Float),
    Column("retry_window_minutes", Float),
)

alerts = Table(
    "alerts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("project_id", String(64), ForeignKey("projects.project_id"), nullable=False),
    Column("severity", String(16), nullable=False),
    Column("message", Text, nullable=False),
    Column("saved_tokens", Float, nullable=False, server_default="0"),
    Column("environment", String(16)),
    Column("source", String(16), server_default="manual"),
    Column("task_id", String(128)),
    Column("root_cause", Text),
    Column("resolved", Boolean, nullable=False, server_default=false()),
    Column("resolved_at", UTCDateTime),
    Column("created_at", UTCDateTime, default=utcnow),
    Index("ix_alerts_project_created", "project_id", "created_at"),
)

events = Table(
    "events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("project_id", String(64), ForeignKey("projects.project_id"), nullable=False),
    Column("prompt_tokens", Float),
    Column("retrieval_score", Float),
    Column("context_length", Float),
    Column("response_quality", Float),
    Column("environment", String(16)),
    Column("risk_score", Float),
    Column("severity", String(16)),
    Column("root_cause", Text),
    Column("recommendation", String(128)),
    Column("extra_json", Text),
    Column("created_at", UTCDateTime, default=utcnow),
    Index("ix_events_project_created", "project_id", "created_at"),
)

agent_events = Table(
    "agent_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("project_id", String(64), ForeignKey("projects.project_id"), nullable=False),
    Column("task_id", String(128), nullable=False),
    Column("trace_id", String(128)),
    Column("agent_name", String(128)),
    Column("model", String(128)),
    Column("tool_name", String(128), nullable=False),
    Column("tool_call_id", String(128)),
    Column("attempt", Integer, nullable=False, server_default="1"),
    Column("status", String(32), nullable=False),
    Column("error_type", String(128)),
    Column("error_message", Text),
    Column("input_hash", String(64)),
    Column("prompt_tokens", Float),
    Column("completion_tokens", Float),
    Column("total_tokens", Float),
    Column("duration_ms", Float),
    Column("environment", String(16)),
    Column("created_at", UTCDateTime, default=utcnow),
    Index("ix_agent_events_project_created", "project_id", "created_at"),
    Index("ix_agent_events_project_task", "project_id", "task_id"),
)


def normalize_database_url(url: str) -> str:
    """Map ``postgres://`` and driverless ``postgresql://`` URLs to the psycopg 3 driver."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def make_engine(database_url: str) -> Engine:
    """Create an engine with pooling suited to the backend."""
    url = normalize_database_url(database_url)
    if url.startswith("sqlite"):
        in_memory = url in {"sqlite://", "sqlite:///:memory:"} or ":memory:" in url
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False, "timeout": 30},
            poolclass=StaticPool if in_memory else None,
        )

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            if not in_memory:
                cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        return engine
    return create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20)


def _add_missing_columns(engine: Engine) -> None:
    """Add columns that exist in the schema but not in an older database."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table in metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            present = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue
                ddl = f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type.compile(engine.dialect)}"
                if column.server_default is not None:
                    default = column.server_default.arg
                    compiled = default if isinstance(default, str) else default.compile(dialect=engine.dialect)
                    ddl += f" DEFAULT {compiled if not isinstance(default, str) else repr(default)}"
                conn.execute(text(ddl))
                logger.info("Migrated: added %s.%s", table.name, column.name)


def _hash_legacy_api_keys(engine: Engine) -> None:
    """Replace v0.3 plaintext ``projects.api_key`` values with hashes."""
    columns = {col["name"] for col in inspect(engine).get_columns("projects")}
    if "api_key" not in columns:
        return
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT project_id, api_key FROM projects WHERE api_key_hash IS NULL AND api_key <> ''")
        ).all()
        for project_id, api_key in rows:
            conn.execute(
                text("UPDATE projects SET api_key_hash = :h, api_key_hint = :hint, api_key = '' WHERE project_id = :p"),
                {"h": hash_api_key(api_key), "hint": api_key_hint(api_key), "p": project_id},
            )
        if rows:
            logger.info("Migrated: hashed %d legacy plaintext API key(s)", len(rows))


_SCHEMA_LOCK_ID = 7_314_051_922  # arbitrary constant for pg_advisory_lock


def init_db(engine: Engine) -> None:
    """Create or upgrade the schema in place.

    Several workers start at once, so PostgreSQL setup runs under an advisory
    lock; on SQLite a lost race is retried.
    """
    if engine.dialect.name == "postgresql":
        with engine.connect() as lock:
            lock.execute(text("SELECT pg_advisory_lock(:id)"), {"id": _SCHEMA_LOCK_ID})
            try:
                _init_schema(engine)
            finally:
                lock.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": _SCHEMA_LOCK_ID})
                lock.commit()
        return
    for attempt in range(5):
        try:
            _init_schema(engine)
            return
        except OperationalError:
            if attempt == 4:
                raise
            time.sleep(0.2 * (attempt + 1))


def _init_schema(engine: Engine) -> None:
    metadata.create_all(engine)
    _add_missing_columns(engine)
    _hash_legacy_api_keys(engine)
    with engine.begin() as conn:
        for table in metadata.sorted_tables:
            for index in table.indexes:
                index.create(conn, checkfirst=True)
