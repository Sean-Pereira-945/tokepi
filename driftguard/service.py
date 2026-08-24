from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field
from secrets import token_urlsafe
from typing import Any

from .config import get_database_url

# Default drift thresholds written to every newly created project policy
DEFAULT_POLICY: dict[str, float] = {
    "prompt_token_limit": 3000.0,
    "retrieval_score_floor": 0.5,
    "context_length_limit": 4000.0,
    "response_quality_floor": 0.8,
}


@dataclass
class Account:
    account_id: str
    name: str
    projects: dict[str, "Project"] = field(default_factory=dict)


@dataclass
class Project:
    project_id: str
    name: str
    environment: str = "prod"
    account_id: str = "default"
    api_key: str = ""
    alerts: list[dict[str, Any]] = field(default_factory=list)


class DriftGuardService:
    """SaaS service layer with account/project persistence and secure session binding."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or get_database_url()
        self.db_path = self._resolve_db_path(self.database_url)
        self.accounts: dict[str, Account] = {}
        self.projects: dict[str, Project] = {}
        self.sessions: dict[str, str] = {}
        self._ensure_parent_directory()
        self._connect()
        self._initialize_db()
        self._load_state()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_db_path(self, database_url: str) -> str:
        if not database_url.startswith("sqlite://"):
            return database_url
        if database_url in {"sqlite:///:memory:", "sqlite://"}:
            return ":memory:"
        path = database_url.replace("sqlite:///", "", 1)
        if not path:
            return "driftguard.db"
        if path.startswith("./"):
            return os.path.abspath(path)
        if not os.path.isabs(path):
            return os.path.abspath(path)
        return path

    def _ensure_parent_directory(self) -> None:
        if (
            self.database_url.startswith("postgresql")
            or self.database_url.startswith("postgres")
            or self.db_path == ":memory:"
        ):
            return
        directory = os.path.dirname(self.db_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    def _connect(self) -> None:
        if self.database_url.startswith("postgresql") or self.database_url.startswith("postgres"):
            try:
                import psycopg2
                import psycopg2.extras
                self.conn = psycopg2.connect(self.database_url, cursor_factory=psycopg2.extras.DictCursor)
                self.is_postgres = True
                return
            except Exception as exc:
                print(f"[DriftGuard] Warning: Failed to connect to PostgreSQL ({exc}). Falling back to local SQLite.")
                self.database_url = "sqlite:///./driftguard.db"
                self.db_path = self._resolve_db_path(self.database_url)
                self._ensure_parent_directory()

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.is_postgres = False

    def _initialize_db(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                account_id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                environment TEXT NOT NULL DEFAULT 'prod',
                account_id TEXT NOT NULL,
                api_key TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (account_id) REFERENCES accounts(account_id)
            )
            """
        )
        # Migrate: add api_key column to existing DBs that don't have it
        try:
            self.conn.execute("ALTER TABLE projects ADD COLUMN api_key TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # column already exists
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                saved_tokens REAL NOT NULL DEFAULT 0.0,
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                FOREIGN KEY (account_id) REFERENCES accounts(account_id)
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                prompt_tokens REAL,
                retrieval_score REAL,
                context_length REAL,
                response_quality REAL,
                environment TEXT,
                extra_json TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS policies (
                project_id TEXT PRIMARY KEY,
                prompt_token_limit REAL NOT NULL DEFAULT 3000.0,
                retrieval_score_floor REAL NOT NULL DEFAULT 0.5,
                context_length_limit REAL NOT NULL DEFAULT 4000.0,
                response_quality_floor REAL NOT NULL DEFAULT 0.8,
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                trace_id TEXT,
                agent_name TEXT,
                model TEXT,
                tool_name TEXT NOT NULL,
                tool_call_id TEXT,
                attempt INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL,
                error_type TEXT,
                error_message TEXT,
                prompt_tokens REAL,
                completion_tokens REAL,
                total_tokens REAL,
                duration_ms REAL,
                environment TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            )
            """
        )
        self.conn.commit()

    def _load_state(self) -> None:
        self.accounts = {}
        self.projects = {}
        self.sessions = {}

        for row in self.conn.execute("SELECT account_id, name FROM accounts"):
            self.accounts[row["account_id"]] = Account(
                account_id=row["account_id"], name=row["name"]
            )

        for row in self.conn.execute(
            "SELECT project_id, name, environment, account_id, api_key FROM projects"
        ):
            project = Project(
                project_id=row["project_id"],
                name=row["name"],
                environment=row["environment"],
                account_id=row["account_id"],
                api_key=row["api_key"] or "",
            )
            self.projects[row["project_id"]] = project
            self.accounts.setdefault(
                row["account_id"],
                Account(account_id=row["account_id"], name=row["account_id"]),
            ).projects[row["project_id"]] = project

        for row in self.conn.execute("SELECT token, account_id FROM sessions"):
            self.sessions[row["token"]] = row["account_id"]

        for project in self.projects.values():
            project.alerts = []
            for alert_row in self.conn.execute(
                "SELECT severity, message, saved_tokens FROM alerts WHERE project_id = ? ORDER BY id ASC",
                (project.project_id,),
            ):
                project.alerts.append(
                    {
                        "severity": alert_row["severity"],
                        "message": alert_row["message"],
                        "saved_tokens": float(alert_row["saved_tokens"]),
                    }
                )

    # ------------------------------------------------------------------
    # Account management
    # ------------------------------------------------------------------

    def create_account(self, account_id: str, name: str) -> Account:
        self.conn.execute(
            "INSERT OR REPLACE INTO accounts (account_id, name) VALUES (?, ?)",
            (account_id, name),
        )
        self.conn.commit()
        account = Account(account_id=account_id, name=name)
        self.accounts[account_id] = account
        return account

    def delete_account(self, account_id: str) -> None:
        """Delete an account and all associated projects, alerts, events, and sessions."""
        project_ids = [
            row["project_id"]
            for row in self.conn.execute(
                "SELECT project_id FROM projects WHERE account_id = ?", (account_id,)
            ).fetchall()
        ]
        for pid in project_ids:
            self._delete_project_data(pid)
        self.conn.execute("DELETE FROM projects WHERE account_id = ?", (account_id,))
        self.conn.execute("DELETE FROM sessions WHERE account_id = ?", (account_id,))
        self.conn.execute("DELETE FROM accounts WHERE account_id = ?", (account_id,))
        self.conn.commit()
        self.accounts.pop(account_id, None)
        for pid in project_ids:
            self.projects.pop(pid, None)

    def get_account(self, account_id: str) -> Account:
        account = self.accounts.get(account_id)
        if account is None:
            row = self.conn.execute(
                "SELECT account_id, name FROM accounts WHERE account_id = ?", (account_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Account {account_id} not found")
            account = Account(account_id=row["account_id"], name=row["name"])
            self.accounts[account_id] = account
        return account

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def create_session(self, account_id: str) -> str:
        if account_id not in self.accounts and account_id not in self.conn.execute(
            "SELECT account_id FROM accounts WHERE account_id = ?",
            (account_id,),
        ).fetchall():
            raise KeyError(f"Account {account_id} not found")
        token = token_urlsafe(24)
        self.conn.execute(
            "INSERT OR REPLACE INTO sessions (token, account_id) VALUES (?, ?)",
            (token, account_id),
        )
        self.conn.commit()
        self.sessions[token] = account_id
        return token

    def get_account_for_session(self, token: str) -> str:
        account_id = self.sessions.get(token)
        if account_id is None:
            row = self.conn.execute(
                "SELECT account_id FROM sessions WHERE token = ?", (token,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Session token {token} not found")
            account_id = row["account_id"]
            self.sessions[token] = account_id
        return account_id

    # ------------------------------------------------------------------
    # Project management
    # ------------------------------------------------------------------

    def create_project(
        self,
        project_id: str,
        name: str,
        environment: str = "prod",
        account_id: str = "default",
    ) -> Project:
        if account_id not in self.accounts:
            self.create_account(account_id, account_id)

        api_key = token_urlsafe(32)
        self.conn.execute(
            "INSERT OR REPLACE INTO projects (project_id, name, environment, account_id, api_key) VALUES (?, ?, ?, ?, ?)",
            (project_id, name, environment, account_id, api_key),
        )
        self.conn.commit()

        # Seed default policy for the new project
        self.conn.execute(
            """
            INSERT OR IGNORE INTO policies (project_id, prompt_token_limit, retrieval_score_floor, context_length_limit, response_quality_floor)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                project_id,
                DEFAULT_POLICY["prompt_token_limit"],
                DEFAULT_POLICY["retrieval_score_floor"],
                DEFAULT_POLICY["context_length_limit"],
                DEFAULT_POLICY["response_quality_floor"],
            ),
        )
        self.conn.commit()

        project = Project(
            project_id=project_id,
            name=name,
            environment=environment,
            account_id=account_id,
            api_key=api_key,
        )
        self.projects[project_id] = project
        self.accounts.setdefault(
            account_id, Account(account_id=account_id, name=account_id)
        ).projects[project_id] = project
        return project

    def get_project(self, project_id: str, account_id: str | None = None) -> Project:
        row = self.conn.execute(
            "SELECT project_id, name, environment, account_id, api_key FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Project {project_id} not found")
        project = self.projects.get(project_id)
        if project is None:
            project = Project(
                project_id=row["project_id"],
                name=row["name"],
                environment=row["environment"],
                account_id=row["account_id"],
                api_key=row["api_key"] or "",
            )
        if account_id is not None and project.account_id != account_id:
            raise KeyError(f"Project {project_id} not found for account {account_id}")
        if not project.alerts:
            project.alerts = []
            for alert_row in self.conn.execute(
                "SELECT severity, message, saved_tokens FROM alerts WHERE project_id = ? ORDER BY id ASC",
                (project_id,),
            ):
                project.alerts.append(
                    {
                        "severity": alert_row["severity"],
                        "message": alert_row["message"],
                        "saved_tokens": float(alert_row["saved_tokens"]),
                    }
                )
        self.projects[project_id] = project
        return project

    def list_projects(self, account_id: str | None = None) -> list[Project]:
        if account_id is None:
            rows = self.conn.execute(
                "SELECT project_id, name, environment, account_id, api_key FROM projects"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT project_id, name, environment, account_id, api_key FROM projects WHERE account_id = ?",
                (account_id,),
            ).fetchall()

        projects: list[Project] = []
        for row in rows:
            project = self.get_project(row["project_id"], account_id=account_id)
            projects.append(project)
        return projects

    def delete_project(self, project_id: str, account_id: str | None = None) -> None:
        """Delete a project and all associated alerts, events, and policy."""
        project = self.get_project(project_id, account_id=account_id)
        self._delete_project_data(project.project_id)
        self.conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        self.conn.commit()
        self.projects.pop(project_id, None)
        for account in self.accounts.values():
            account.projects.pop(project_id, None)

    def _delete_project_data(self, project_id: str) -> None:
        self.conn.execute("DELETE FROM alerts WHERE project_id = ?", (project_id,))
        self.conn.execute("DELETE FROM events WHERE project_id = ?", (project_id,))
        self.conn.execute("DELETE FROM policies WHERE project_id = ?", (project_id,))

    def get_project_by_api_key(self, api_key: str) -> Project:
        """Look up a project by its API key (used for SDK ingestion auth)."""
        row = self.conn.execute(
            "SELECT project_id FROM projects WHERE api_key = ?", (api_key,)
        ).fetchone()
        if row is None:
            raise KeyError("Invalid API key")
        return self.get_project(row["project_id"])

    # ------------------------------------------------------------------
    # Alert management
    # ------------------------------------------------------------------

    def add_alert(
        self, project_id: str, alert: dict[str, Any], account_id: str | None = None
    ) -> dict[str, Any]:
        project = self.get_project(project_id, account_id=account_id)
        self.conn.execute(
            "INSERT INTO alerts (project_id, severity, message, saved_tokens) VALUES (?, ?, ?, ?)",
            (
                project_id,
                alert["severity"],
                alert["message"],
                float(alert.get("saved_tokens", 0.0)),
            ),
        )
        self.conn.commit()
        alert_record = {
            "severity": alert["severity"],
            "message": alert["message"],
            "saved_tokens": float(alert.get("saved_tokens", 0.0)),
        }
        project.alerts.append(alert_record)
        return alert_record

    # ------------------------------------------------------------------
    # Event ingestion
    # ------------------------------------------------------------------

    def ingest_event(self, project_id: str, event: dict[str, Any]) -> dict[str, Any]:
        """Store a raw SDK telemetry event for a project."""
        import json

        known_keys = {
            "prompt_tokens",
            "retrieval_score",
            "context_length",
            "response_quality",
            "environment",
        }
        extra = {k: v for k, v in event.items() if k not in known_keys and k != "project"}
        self.conn.execute(
            """
            INSERT INTO events (project_id, prompt_tokens, retrieval_score, context_length, response_quality, environment, extra_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                event.get("prompt_tokens"),
                event.get("retrieval_score"),
                event.get("context_length"),
                event.get("response_quality"),
                event.get("environment"),
                json.dumps(extra) if extra else None,
            ),
        )
        self.conn.commit()
        return {"project_id": project_id, "status": "ingested"}

    def list_events(self, project_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Return the most recent telemetry events for a project."""
        rows = self.conn.execute(
            """
            SELECT id, prompt_tokens, retrieval_score, context_length, response_quality, environment, extra_json, created_at
            FROM events WHERE project_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            events.append(
                {
                    "id": row["id"],
                    "prompt_tokens": row["prompt_tokens"],
                    "retrieval_score": row["retrieval_score"],
                    "context_length": row["context_length"],
                    "response_quality": row["response_quality"],
                    "environment": row["environment"],
                    "created_at": row["created_at"],
                }
            )
        return events

    def ingest_agent_event(self, project_id: str, event: dict[str, Any]) -> dict[str, Any]:
        """Store one task/tool attempt for agent retry analysis."""
        self.conn.execute(
            """
            INSERT INTO agent_events (
                project_id, task_id, trace_id, agent_name, model, tool_name,
                tool_call_id, attempt, status, error_type, error_message,
                prompt_tokens, completion_tokens, total_tokens, duration_ms, environment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                event["task_id"],
                event.get("trace_id"),
                event.get("agent_name"),
                event.get("model"),
                event["tool_name"],
                event.get("tool_call_id"),
                event.get("attempt", 1),
                event["status"],
                event.get("error_type"),
                event.get("error_message"),
                event.get("prompt_tokens"),
                event.get("completion_tokens"),
                event.get("total_tokens"),
                event.get("duration_ms"),
                event.get("environment"),
            ),
        )
        self.conn.commit()
        return {"project_id": project_id, "status": "ingested"}

    def list_agent_events(self, project_id: str, limit: int = 200) -> list[dict[str, Any]]:
        """Return recent task/tool attempts for a project."""
        rows = self.conn.execute(
            """
            SELECT task_id, trace_id, agent_name, model, tool_name, tool_call_id,
                   attempt, status, error_type, error_message, prompt_tokens,
                   completion_tokens, total_tokens, duration_ms, environment, created_at
            FROM agent_events WHERE project_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Policy management
    # ------------------------------------------------------------------

    def get_policy(self, project_id: str) -> dict[str, float]:
        """Return the drift policy thresholds for a project."""
        row = self.conn.execute(
            "SELECT * FROM policies WHERE project_id = ?", (project_id,)
        ).fetchone()
        if row is None:
            return dict(DEFAULT_POLICY)
        return {
            "prompt_token_limit": float(row["prompt_token_limit"]),
            "retrieval_score_floor": float(row["retrieval_score_floor"]),
            "context_length_limit": float(row["context_length_limit"]),
            "response_quality_floor": float(row["response_quality_floor"]),
        }

    def upsert_policy(self, project_id: str, updates: dict[str, float]) -> dict[str, float]:
        """Create or update drift policy thresholds for a project."""
        current = self.get_policy(project_id)
        merged = {**current, **updates}
        self.conn.execute(
            """
            INSERT OR REPLACE INTO policies (project_id, prompt_token_limit, retrieval_score_floor, context_length_limit, response_quality_floor)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                project_id,
                merged["prompt_token_limit"],
                merged["retrieval_score_floor"],
                merged["context_length_limit"],
                merged["response_quality_floor"],
            ),
        )
        self.conn.commit()
        return merged
