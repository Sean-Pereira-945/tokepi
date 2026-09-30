# Configuration

The server reads its settings from environment variables. It also loads a
`.env` file from the working directory if there is one.
[`.env.example`](../.env.example) lists every variable. In development, every
variable is optional.

## Core

| Variable | Default | Description |
| --- | --- | --- |
| `DRIFTGUARD_ENV` | `development` | One of `development`, `production`, `test`. `production` requires a strong secret key and turns on HSTS. |
| `DRIFTGUARD_SECRET_KEY` | dev placeholder | Signs session tokens. Production needs at least 32 random characters. Changing it signs everyone out. |
| `DATABASE_URL` | `sqlite:///./driftguard.db` | SQLite or PostgreSQL. `postgres://` and `postgresql://` URLs use psycopg 3, which needs the `[postgres]` extra. |
| `REDIS_URL` | unset | Shares rate limits and realtime alerts across workers. Needs the `[redis]` extra. **Required with more than one worker.** |

## Accounts

| Variable | Default | Description |
| --- | --- | --- |
| `DRIFTGUARD_ALLOW_SIGNUP` | `true` | Set to `false` to close registration after you create your own account. |
| `DRIFTGUARD_SESSION_TTL_HOURS` | `168` | How long a session lasts (7 days). |

## Rate limits (requests per minute)

| Variable | Default | Applies to |
| --- | --- | --- |
| `DRIFTGUARD_RATE_LIMIT_PER_MINUTE` | `300` | API calls, per session token or API key (per client IP when unauthenticated) |
| `DRIFTGUARD_INGEST_RATE_LIMIT_PER_MINUTE` | `600` | `/events` and `/agent-events`, per API key. A batch counts as one request. |
| `DRIFTGUARD_LOGIN_RATE_LIMIT_PER_MINUTE` | `10` | Login, register, and account deletion, per client IP |

Behind a reverse proxy, start the server with `--proxy-headers`. Otherwise every
client shares the proxy's IP. The Docker image does this by default.

## Data handling

| Variable | Default | Description |
| --- | --- | --- |
| `DRIFTGUARD_RETENTION_DAYS` | `30` | Telemetry, agent events, and **resolved** alerts older than this are deleted. `0` turns pruning off. Open alerts are never pruned. |
| `DRIFTGUARD_RETENTION_INTERVAL_HOURS` | `6` | How often the prune job runs. It also runs once at startup. |
| `DRIFTGUARD_SCRUB_PII` | `true` | Redact credentials, emails, SSNs, and card numbers from error messages, alert text, and metadata before they're stored. |
| `DRIFTGUARD_DRIFT_ALERT_COOLDOWN_MINUTES` | `15` | Minimum gap before another drift alert is raised for the same root cause and environment while one is still open. |

## Notifications

Critical alerts are posted in the background. A slow webhook never delays
ingestion.

| Variable | Payload |
| --- | --- |
| `DRIFTGUARD_SLACK_WEBHOOK` | Slack incoming-webhook message with the project, environment, and alert text. |
| `DRIFTGUARD_ALERT_WEBHOOK` | `{"project_id": "...", "alert": {...alert object...}}` as JSON. |

## Serving

| Variable | Default | Description |
| --- | --- | --- |
| `DRIFTGUARD_CORS_ORIGINS` | unset | Comma-separated origins allowed to call the API from browser code on another origin. The dashboard itself is same-origin and doesn't need this. |
| `DRIFTGUARD_STATIC_DIR` | packaged build | Serve the dashboard from another directory. |
| `DRIFTGUARD_HOST`, `PORT`, `DRIFTGUARD_WORKERS` | `127.0.0.1`, `8000`, `1` | Defaults for the `driftguard-server` command. |

## `driftguard-server` options

```text
driftguard-server [--host HOST] [--port PORT] [--workers N] [--reload] [--proxy-headers]
```

The command wraps `uvicorn driftguard.server.app:create_app --factory`. You can
run uvicorn or gunicorn directly with the same factory.

## Policy (per project)

Drift thresholds and agent-diagnosis settings are stored per project, not in the
environment. Change them in the dashboard's **Policy** view or with
`PUT /projects/{id}/policy`. Defaults:

| Setting | Default |
| --- | ---: |
| `prompt_token_limit` | 3000 |
| `context_length_limit` | 4000 |
| `retrieval_score_floor` | 0.5 |
| `response_quality_floor` | 0.8 |
| `blocked_after_failures` | 3 |
| `retry_window_minutes` | 60 |

## Deprecated names

These still work, but they log a deprecation warning.

| Old | New |
| --- | --- |
| `JWT_SECRET`, `API_SECRET` | `DRIFTGUARD_SECRET_KEY` |
| `RATE_LIMIT_PER_MINUTE` | `DRIFTGUARD_RATE_LIMIT_PER_MINUTE` |
