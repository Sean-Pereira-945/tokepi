# Development

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"            # SDK + server + Postgres/Redis drivers + research + tools
cd frontend && npm install && cd ..
```

## Running locally

```bash
driftguard-server --reload         # API on http://127.0.0.1:8000 (SQLite ./driftguard.db)
cd frontend && npm run dev         # dashboard on http://localhost:5173, API calls proxied to :8000
```

To have the Python server host the dashboard at `:8000`, run `npm run build`,
which writes to `driftguard/server/static/`. That folder is gitignored.

## Repository layout

```text
driftguard/            installable package
  client.py            SDK client
  policy.py            drift thresholds and scoring (shared by SDK and server)
  agent_analysis.py    agent diagnosis algorithm
  adapters/            Python decorator, MCP middleware, provider usage extraction
  server/              FastAPI app, schema, service, auth, realtime, retention
frontend/              React dashboard source (builds into driftguard/server/static)
research/              Phase 1 synthetic drift prototypes and their tests
tests/                 SDK and server tests
docs/                  documentation
```

## Tests

```bash
pytest                              # everything, on in-memory SQLite (~20 s)
pytest tests/test_agent_analysis.py -q
```

Run the same suite against real PostgreSQL and Redis, which is what CI does:

```bash
docker run -d --rm --name dg-pg -e POSTGRES_USER=driftguard -e POSTGRES_PASSWORD=driftguard \
  -e POSTGRES_DB=driftguard_test -p 55432:5432 postgres:16-alpine
docker run -d --rm --name dg-redis -p 56379:6379 redis:7-alpine

DRIFTGUARD_TEST_DATABASE_URL=postgresql://driftguard:driftguard@localhost:55432/driftguard_test \
DRIFTGUARD_TEST_REDIS_URL=redis://localhost:56379/0 pytest tests
```

`DRIFTGUARD_TEST_DATABASE_URL` drops and recreates the schema before each test,
so point it only at a throwaway database. The Redis tests are skipped unless
`DRIFTGUARD_TEST_REDIS_URL` is set.

## Quality checks

```bash
ruff check . && ruff format --check .
bandit -c pyproject.toml -r driftguard
pip-audit --skip-editable
cd frontend && npm run lint && npm run build
```

## Continuous integration

| Workflow | Runs | What it does |
| --- | --- | --- |
| `ci.yml` | push to `main`, pull requests | ruff; pytest on Python 3.10–3.13; the server suite against PostgreSQL 16 and Redis 7; dashboard type-check and build |
| `security.yml` | push, pull requests, weekly | bandit, pip-audit, `npm audit`. Any finding fails the job. |
| `release.yml` | tag `v*` | runs CI, checks that the tag matches `pyproject.toml`, builds the dashboard and wheel, checks that the wheel contains the dashboard, publishes to PyPI with trusted publishing |

## Releasing

1. Bump `version` in `pyproject.toml`, `__version__` in
   `driftguard/__init__.py`, and `version` in `frontend/package.json`.
2. Add a section to `CHANGELOG.md`.
3. Commit, then `git tag v0.4.0 && git push origin v0.4.0`.

## Conventions

- Server code uses SQLAlchemy Core, not the ORM. All queries go through
  `DriftGuardService`, and each method opens its own transaction.
- Nothing is cached in process memory, so workers can scale horizontally.
- Any behaviour change updates the matching page in `docs/` and gets an entry
  in `CHANGELOG.md` in the same change.
- Only mark something done in `docs/roadmap.md` once the code path is wired up
  and tested.
