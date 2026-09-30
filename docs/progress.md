# Progress report: 0.4.0 foundation rebuild

Date: 2026-09-30. Branch: `refactor/foundation`, committed and pushed to GitHub
(not merged into `main` yet).

For the full list of changes, see [CHANGELOG.md](../CHANGELOG.md). For the
long-term plan, see [roadmap.md](roadmap.md).

## Finished and verified

| Area | What was done | How it was verified |
| --- | --- | --- |
| Repo organisation | Research code moved to `research/`; server code moved to `driftguard/server/`; the frontend moved from `.frontend_source/` into `frontend/`. Dead code removed: the old static dashboard, the embedded HTML dashboard, `analytics.py`, `dashboard_data.py`, `requirements.txt`. | Every test suite passes |
| SDK | httpx-only; batched sync that keeps failed batches queued; bounded queue; client timestamps; policy-aware `check_drift` | `tests/test_client.py`, plus an end-to-end run against a real server |
| Agent diagnosis | Per-task status: blocked, failing, recovered, healthy. Configurable retry window and block threshold. Redundant-call detection and error-specific advice. | `tests/test_agent_analysis.py` |
| Adapters | Async `@driftguard_tool`, `AgentContext` on contextvars, LLM token attribution, MCP session wrapper | `tests/test_adapters.py` |
| Auth and security | Email/password accounts, revocable sessions, hashed and rotatable API keys, no shared `default` account, project-takeover fix, per-session rate limits, WebSocket auth via subprotocol, secret and PII scrubbing | `test_auth.py`, `test_projects.py`, `test_realtime.py`, bandit clean, pip-audit clean, npm audit clean |
| Persistence | SQLAlchemy Core on SQLite and PostgreSQL; automatic migration from 0.3; startup safe with several workers | Full suite on PostgreSQL 16; v0.3 upgrade test; concurrent-startup test |
| Alerts | Automatic drift and agent alerts; auto-resolve on recovery; Slack and webhook delivery; live WebSocket push, shared across workers through Redis | `test_dashboard.py`, `test_realtime.py`, `test_redis.py` (real Redis) |
| Retention | Scheduled pruning at startup and on an interval | `test_retention.py` |
| Dashboard | Rebuilt against the real API and rebranded DriftGuard (no mock data), dark design system, sign-in, every view from the brief | `npm run lint`/`build` pass; 18-step headless browser run; screenshots reviewed |
| Packaging and deploy | Extras (`server`, `postgres`, `redis`, `all`), working `driftguard-server`, wheel bundles the dashboard, multi-stage non-root Docker image, compose with healthchecks | Wheel contents checked; `docker compose up` on a clean volume came up healthy with 2 workers and no errors |
| CI | New `ci.yml` (lint, Python 3.10–3.13, Postgres + Redis, dashboard build); `security.yml` fails on findings; `release.yml` checks tag and wheel | Written but **not run on GitHub yet** |
| Live demo | `examples/live_demo.py` plays drift, a blocked agent and recovery step by step; guide in `docs/demo.md` | Run end to end against the local server: agent alert fired and auto-resolved, drift alert raised |
| Docs | New pages: api, architecture, configuration, deployment, development, dashboard, agent-integration, quickstart, roadmap, design-system; README and CHANGELOG | Code examples checked against a running server |

Last test run: **135 passed** on SQLite, and **129 passed** on PostgreSQL + Redis.
Lint, bandit, pip-audit and `npm audit` are all clean.

### Fixed after the first review pass
These came from the dashboard agent's feedback and from testing the compose stack:
- API rate limits are now per session or API key (300/min), not per IP, so
  users behind one NAT don't share a budget.
- `blocked_after_failures` is returned as an integer.
- WebSocket alert messages carry `action` (`created`, `resolved`, `reopened`);
  the dashboard only notifies on `created`.
- Schema setup no longer crashes a worker when several start at once (found on
  a fresh `docker compose up`).
- The server releases its database pool on shutdown.

### Docs audit
- Every route in the app is documented in `api.md`, and every documented route
  exists (checked automatically).
- Every environment variable the server reads is in `configuration.md` and
  `.env.example`.
- All relative links in the docs resolve.

## What still needs to be done

### Before merging (owner decisions or quick tasks)
1. **Open a PR and merge.** The branch is pushed in logical commits. The first CI
   run on GitHub will be the first real check of the workflow files.
2. **Repo name.** The GitHub repo is still called `tokepi`, and `pyproject.toml`
   URLs point there. Rename the repo to `DriftGuard` if you want the name to
   match, then update the URLs.
3. **LICENSE.** An MIT `LICENSE` file was added to match what `pyproject.toml`
   already declared. Confirm that's the licence you want.
4. **PyPI trusted publishing.** Set up the `pypi` environment in GitHub before
   tagging `v0.4.0`.
5. **Your local `.env` needs a decision.**
   - **Database:** its `DATABASE_URL` points at a remote PostgreSQL database.
     The first 0.4 start migrates that database in place: it adds columns and
     replaces plaintext API keys with hashes, which can't be undone. Back it up
     before pointing 0.4 at it, or keep using a local SQLite file for
     development.
   - **Variable names:** it uses `API_SECRET` and `RATE_LIMIT_PER_MINUTE`. Those
     still work but log deprecation warnings. Rename them to
     `DRIFTGUARD_SECRET_KEY` and `DRIFTGUARD_RATE_LIMIT_PER_MINUTE`.

## Running it locally right now

Double-click `demo.bat`, or start the server by hand against the local
database `driftguard-local.db` (gitignored), overriding the `.env` database:

```bash
DATABASE_URL=sqlite:///./driftguard-local.db .venv/Scripts/driftguard-server.exe --port 8000
```

It was seeded with demo data: 40 telemetry events, and three agent tasks (one
blocked, one recovered, one healthy). Sign in with `demo@driftguard.local` /
`driftguard-demo`. These credentials are for this local file only; delete the
file to start clean.

### Giving a demo
On Windows, double-click `demo.bat`: it starts the server, opens the dashboard
and runs the script. Or run it by hand:
Run `python examples/live_demo.py --email demo@driftguard.local --password driftguard-demo`
against the running server and select the **Live Demo** project. The full
walkthrough and talking points are in [demo.md](demo.md).

### Open request
- **Role-based agents** (critic, designer and developer, each with restricted
  tools, coordinating on changes). Not started: the first step was cancelled.
  Waiting on whether you want it.

### Small follow-ups found during the work
- Frontend has no unit tests yet. Only type-checking and the manual browser run
  cover it.
- There's no "restore default policy" endpoint. The Policy view's Reset only
  discards unsaved edits.
- The open-alerts badge counts only alerts inside the current time and
  environment filter; there's no unfiltered count endpoint.
- The dashboard has no account-deletion screen. The API supports it
  (`DELETE /auth/me`).
- The test client prints a Starlette deprecation warning about `httpx`. It's
  harmless.
- Password reset and email verification need an email provider.

### Next features (from [roadmap.md](roadmap.md))
- Standalone MCP gateway, so closed agents that support MCP can be observed
- LangChain/LangGraph, OpenAI Agents SDK, and Claude Agent SDK adapters; a JS/TS SDK
- Trace waterfall view, per-project notification settings, latency metric,
  cost from provider pricing
- Teams and roles, Alembic migrations, secret-store integration, Helm chart,
  OpenTelemetry export
