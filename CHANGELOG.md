# Changelog

All notable changes to DriftGuard are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[semantic versioning](https://semver.org/) (pre-1.0: minor versions may break).

## [0.4.0] - unreleased

A rebuild of the foundation. v0.3 described several features as done that
didn't work: authentication, PostgreSQL, live alerts, and retention. This
release implements them, with tests.

### Security
- **Removed the unauthenticated `default` account.** v0.3 let any request with
  no token act as a shared account, so anyone could list, read, and change
  those projects.
- **Real authentication.** Email and password accounts, with passwords hashed by
  scrypt. `POST /auth/register`, `/auth/login`, `/auth/logout`, `GET /auth/me`,
  and `DELETE /auth/me`. v0.3's `POST /auth/session?account_id=` handed out a
  token to anyone who knew an account ID.
- Sessions are revocable. Each JWT's `jti` is stored, so logout and account
  deletion invalidate it.
- **Project API keys are hashed**, shown once, and can be rotated
  (`POST /projects/{id}/api-key`). Existing plaintext keys are hashed on first
  start. Keys now have a `dg_live_` prefix.
- **Fixed project takeover.** v0.3 used `INSERT OR REPLACE`, so creating a
  project with another account's ID overwrote it. Creating an existing ID now
  returns `409`.
- A project API key can no longer change policy. Policy changes, deletion, key
  rotation, and alert changes need the owner's session.
- The WebSocket requires a session token or API key, sent as a subprotocol so
  it stays out of URL access logs.
- Production refuses to start without a strong `DRIFTGUARD_SECRET_KEY`.
- Rate limits: separate limits for login (per IP), the API (per session or
  key, 300/min), and ingestion (per key). The
  Redis limiter is atomic and uses wall-clock time; v0.3 used
  `time.monotonic()`, which isn't comparable across processes.
- Scrubbing now covers API keys and tokens (OpenAI, Anthropic, GitHub, AWS,
  Google, Slack, bearer, private keys). Card numbers need a valid Luhn checksum,
  so ordinary long numbers are no longer redacted.
- Security headers on every response, and HSTS in production.
- Upgraded to FastAPI 0.14x and Starlette 1.x. Starlette 0.38 had published
  advisories.

### Added
- `driftguard.server`: an app factory (`create_app`) and a working
  `driftguard-server` command. The old entry point pointed at an ASGI object and
  couldn't run.
- **Automatic alerts.**
  - Critical telemetry raises a `drift` alert, at most one per root cause per
    cooldown.
  - A blocked agent task raises one `agent` alert. Its wasted-token figure keeps
    updating, and the alert resolves itself when the task recovers.
  - Alerts have `id`, `source`, `task_id`, `root_cause`, and
    `resolved`/`resolved_at`.
  - `PATCH /projects/{id}/alerts/{alert_id}` resolves or reopens an alert.
- **Server-side scoring.** Each ingested event stores `risk_score`, `severity`,
  `root_cause`, and `recommendation`.
- **Batch ingestion:** `POST /events/{id}/batch` and
  `POST /agent-events/{id}/batch`, up to 500 events each.
- Events accept `occurred_at` and `metadata`. Agent events accept `input_hash`.
- `GET /projects/{id}/summary` rewritten: SQL aggregates, `violation_rates`,
  `events_by_severity`, `top_root_causes`, and open-alert totals.
- `GET /projects/{id}/agent-events` with a `task_id` filter. Event lists page
  with `before_id`.
- Realtime alerts at `WS /ws/projects/{id}` with an `action` field (`created`,
  `resolved`, `reopened`), fanned out across workers through Redis.
- Slack and generic webhook notifications, delivered on a background thread.
- A scheduled retention job (`DRIFTGUARD_RETENTION_DAYS`). It prunes telemetry,
  agent events, resolved alerts, and expired sessions. v0.3 had the code but
  never ran it.
- **Agent diagnosis v2.**
  - Per-task results in `tasks`.
  - Recovery detection: a later success of the same tool.
  - Policy settings `blocked_after_failures` and `retry_window_minutes`.
  - Redundant-call detection.
  - Recommendations based on the error type.
- **Adapters.**
  - `@driftguard_tool` supports async functions. `AgentContext` uses
    contextvars and supports `async with` and `auto_sync`.
  - `record_llm_usage()` attributes model tokens to tool calls.
  - `usage_from_response()` reads OpenAI, Anthropic, and Gemini responses.
  - `MCPMiddleware.instrument_session()` wraps an MCP `ClientSession`.
  - Inputs are fingerprinted automatically.
- **SDK.**
  - Batched sync; failed batches stay queued in order (v0.3 could drop or
    duplicate events).
  - A bounded queue and client-side `occurred_at` timestamps.
  - An optional `project_id` default, plus `flush()` and
    `sync_agent_events_async()`.
- **Dashboard** moved into `frontend/` from the separate `Design-` repo,
  rebranded to DriftGuard, and rebuilt against the real API.
- Schema setup is safe when several workers start at once (a PostgreSQL
  advisory lock; retried on SQLite).
- The server closes its database connection pool on shutdown.
- Docker: a multi-stage, non-root image that bundles the dashboard, with a
  healthcheck. Compose uses healthchecks, and Postgres and Redis are no longer
  exposed on the host.
- CI: ruff, pytest on Python 3.10–3.13, the full server suite on PostgreSQL 16
  and Redis 7, the dashboard build, and security scans that fail on findings.
  Releases check that the wheel bundles the dashboard.
- `examples/live_demo.py` and [docs/demo.md](docs/demo.md): a step-by-step live
  demo covering drift, a blocked agent, and automatic recovery.
  `demo.bat` starts the whole demo on Windows in one step.
- Docs: new API reference, architecture, configuration, deployment,
  development, and roadmap pages. `DESIGN.md` moved to `docs/design-system.md`. All existing docs were rewritten to match the
  code. A `LICENSE` file was added (MIT, as `pyproject.toml` already declared).

### Changed
- **Package extras.** `pip install driftguard` now installs only `httpx`. The
  server needs `driftguard[server]`; add `[postgres]` and `[redis]` as needed,
  or `[all]`. NumPy and pandas are no longer dependencies.
- **Persistence rewritten** on SQLAlchemy Core. PostgreSQL works; v0.3 used
  SQLite-only SQL and silently fell back to a local SQLite file. There are no
  in-memory caches, so it's safe with several workers. Filtering happens in SQL.
- `recommend_mitigation` and `check_drift` use the project policy's thresholds;
  v0.3 compared against hardcoded values.
- Root cause text: "trajectory quality degradation" is now "response quality
  degradation".
- The policy returns `blocked_after_failures` as an integer (`3`, not `3.0`),
  matching what `PUT /projects/{id}/policy` accepts.
- `.env.example` lists every server variable, including the `driftguard-server`
  defaults `DRIFTGUARD_HOST`, `PORT` and `DRIFTGUARD_WORKERS`.
- Configuration uses `DRIFTGUARD_*` names. `JWT_SECRET`, `API_SECRET`, and
  `RATE_LIMIT_PER_MINUTE` still work but are deprecated.
- The research prototypes (`data`, `detector`, `benchmark`, `experiment`,
  `reporting`, and the demo API) moved to `research/`.

### Removed / breaking
- These routes are gone:
  - `POST /accounts` → use `/auth/register`
  - `POST /auth/session` → use `/auth/login`
  - `GET /accounts/me` → use `/auth/me`
  - `POST /alerts` → use `POST /projects/{id}/alerts`
  - `GET /alerts/{id}` → use `GET /projects/{id}/alerts`
  - `GET /events/{id}` → use `GET /projects/{id}/events`
  - `/projects/{id}/metrics` and `/projects/{id}/dashboard` → use
    `/projects/{id}/summary`
  - `WS /ws/alerts/{id}` → use `WS /ws/projects/{id}`
- `driftguard.routes`, `driftguard.service`, `driftguard.middleware`,
  `driftguard.config`, `driftguard.workers`, and `driftguard.notifications` moved
  under `driftguard.server`. `driftguard.analytics` and
  `driftguard.dashboard_data` were removed; `/summary` replaces them.
- `driftguard.compute_drift_scores` was removed from the public API. It was the
  synthetic research detector and now lives in `research.detector`. Use
  `driftguard.evaluate_drift` for LLM telemetry.
- `capture_metrics` no longer adds a `project` key to the payload.
- `requirements.txt` was removed; `pyproject.toml` is the single source of
  dependencies.
- The legacy static dashboard (`static/dashboard.js`, `styles.css`) and the
  1,200-line embedded HTML dashboard in `api.py` were removed.

## [0.3.0] - 2026-08

- The SDK client, FastAPI server, project API keys, agent event ingestion, and
  the first blocking-tool diagnosis.
