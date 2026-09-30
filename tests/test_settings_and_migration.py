import sqlite3
import time

import pytest

pytest.importorskip("sqlalchemy")

from driftguard.server.db import normalize_database_url
from driftguard.server.ratelimit import MemoryRateLimiter
from driftguard.server.security import hash_api_key
from driftguard.server.service import DriftGuardService
from driftguard.server.settings import DEV_SECRET_KEY, Settings

SECRET = "x" * 40


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db/dg")
    monkeypatch.setenv("DRIFTGUARD_SECRET_KEY", SECRET)
    monkeypatch.setenv("DRIFTGUARD_CORS_ORIGINS", "https://a.test, https://b.test")
    monkeypatch.setenv("DRIFTGUARD_ALLOW_SIGNUP", "false")
    settings = Settings.from_env(load_dotenv_file=False)
    assert settings.database_url == "postgresql://u:p@db/dg"
    assert settings.cors_origins == ("https://a.test", "https://b.test")
    assert settings.allow_signup is False


def test_legacy_secret_variable_still_works(monkeypatch):
    monkeypatch.delenv("DRIFTGUARD_SECRET_KEY", raising=False)
    monkeypatch.setenv("JWT_SECRET", SECRET)
    assert Settings.from_env(load_dotenv_file=False).secret_key == SECRET


def test_production_requires_a_real_secret(monkeypatch):
    monkeypatch.setenv("DRIFTGUARD_ENV", "production")
    monkeypatch.delenv("DRIFTGUARD_SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("API_SECRET", raising=False)
    with pytest.raises(ValueError, match="DRIFTGUARD_SECRET_KEY"):
        Settings.from_env(load_dotenv_file=False)
    with pytest.raises(ValueError):
        Settings(environment="production", secret_key="short").validate()
    Settings(environment="production", secret_key=SECRET).validate()
    assert Settings().secret_key == DEV_SECRET_KEY


def test_invalid_settings_are_rejected():
    with pytest.raises(ValueError):
        Settings(environment="staging-ish").validate()


def test_postgres_urls_use_psycopg3():
    assert normalize_database_url("postgres://u@h/db") == "postgresql+psycopg://u@h/db"
    assert normalize_database_url("postgresql://u@h/db") == "postgresql+psycopg://u@h/db"
    assert normalize_database_url("postgresql+psycopg2://u@h/db") == "postgresql+psycopg2://u@h/db"
    assert normalize_database_url("sqlite:///x.db") == "sqlite:///x.db"


def test_memory_rate_limiter_window():
    limiter = MemoryRateLimiter()
    assert [limiter.allow("k", 2, window_seconds=0.2) for _ in range(3)] == [True, True, False]
    assert limiter.allow("other", 2, window_seconds=0.2) is True
    time.sleep(0.25)
    assert limiter.allow("k", 2, window_seconds=0.2) is True


def test_upgrades_a_v03_database(tmp_path):
    """A database written by v0.3 keeps its data, gains new columns, and loses plaintext keys."""
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE accounts (account_id TEXT PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE projects (project_id TEXT PRIMARY KEY, name TEXT NOT NULL,
            environment TEXT NOT NULL DEFAULT 'prod', account_id TEXT NOT NULL, api_key TEXT NOT NULL DEFAULT '');
        CREATE TABLE alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL, severity TEXT NOT NULL,
            message TEXT NOT NULL, saved_tokens REAL NOT NULL DEFAULT 0.0, environment TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE sessions (token TEXT PRIMARY KEY, account_id TEXT NOT NULL);
        CREATE TABLE events (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL, prompt_tokens REAL,
            retrieval_score REAL, context_length REAL, response_quality REAL, environment TEXT, extra_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE policies (project_id TEXT PRIMARY KEY, prompt_token_limit REAL NOT NULL DEFAULT 3000.0,
            retrieval_score_floor REAL NOT NULL DEFAULT 0.5, context_length_limit REAL NOT NULL DEFAULT 4000.0,
            response_quality_floor REAL NOT NULL DEFAULT 0.8);
        CREATE TABLE agent_events (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
            task_id TEXT NOT NULL, trace_id TEXT, agent_name TEXT, model TEXT, tool_name TEXT NOT NULL,
            tool_call_id TEXT, attempt INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL, error_type TEXT,
            error_message TEXT, prompt_tokens REAL, completion_tokens REAL, total_tokens REAL, duration_ms REAL,
            environment TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')));
        INSERT INTO accounts VALUES ('default', 'Default account');
        INSERT INTO projects VALUES ('legacy', 'Legacy App', 'prod', 'default', 'old-plaintext-key');
        INSERT INTO alerts (project_id, severity, message, saved_tokens) VALUES ('legacy', 'warning', 'old', 1.5);
        INSERT INTO events (project_id, prompt_tokens) VALUES ('legacy', 1234);
        INSERT INTO policies (project_id, prompt_token_limit) VALUES ('legacy', 2500);
    """)
    conn.commit()
    conn.close()

    service = DriftGuardService(f"sqlite:///{path}", SECRET)
    project = service.project_for_api_key("old-plaintext-key")
    assert project["project_id"] == "legacy"
    assert service.get_policy("legacy")["prompt_token_limit"] == 2500
    assert service.get_policy("legacy")["blocked_after_failures"] == 3
    assert service.list_alerts("legacy")[0]["resolved"] is False
    assert service.list_events("legacy")[0]["prompt_tokens"] == 1234
    assert service.list_events("legacy")[0]["created_at"].endswith("Z")
    service.ingest_events(project, [{"prompt_tokens": 9000}])
    assert service.summary("legacy")["total_events"] == 2

    raw = sqlite3.connect(path)
    assert raw.execute("SELECT api_key, api_key_hash FROM projects").fetchone() == (
        "",
        hash_api_key("old-plaintext-key"),
    )
    raw.close()
    # Running the migration again is a no-op.
    DriftGuardService(f"sqlite:///{path}", SECRET)
