# DriftGuard HTTP API reference

This page covers every server endpoint in DriftGuard 0.4. A running server also
serves interactive OpenAPI docs at `/docs` and the raw schema at
`/openapi.json`.

All request and response bodies are JSON. Timestamps are ISO 8601 UTC strings
ending in `Z`. Unknown query values return `422`.

## Authentication

There are two credentials. Each one grants different access.

| Credential | Header | Obtained from | Grants |
| --- | --- | --- | --- |
| **Session token** | `Authorization: Bearer <token>` | `POST /auth/register` or `POST /auth/login` | Everything for the account's own projects. This is the only credential that can change policy, rotate keys, resolve alerts, or delete. |
| **Project API key** | `X-API-Key: dg_live_...` | `POST /projects` (shown once) or key rotation | Ingestion for that one project, plus read access to its data. |

- A request with no credentials gets `401`. There is no shared default account.
- A session token for another account's project gets `404`, so projects can't be
  discovered by guessing IDs.
- An API key used on a different project gets `403`.
- Sessions last `DRIFTGUARD_SESSION_TTL_HOURS` (7 days by default) and end at
  logout.
- API keys are stored as SHA-256 hashes. A lost key can't be recovered, only
  rotated.

## Rate limits

Every limit is a sliding window of one minute. When Redis is configured
(`REDIS_URL`), all server workers share the same counters. Over the limit, the
server returns `429` with `Retry-After: 60`.

| Scope | Default | Keyed by |
| --- | --- | --- |
| API reads and writes | 300/min | session token or API key (client IP if neither) |
| SDK ingestion (`/events`, `/agent-events`) | 600/min | API key |
| Login, register, delete account | 10/min | client IP |

A batch request counts as one request.

## Errors

Errors use FastAPI's shape: `{"detail": "message"}`. Validation errors (`422`)
return `detail` as a list of `{loc, msg, type}` objects.

---

## Meta

### `GET /health`
Checks that the server and its database are reachable. No auth. Returns `200`
with `{"status": "ok", "database": "ok", "version": "0.4.0"}`, or `503` if the
database is unreachable.

### `GET /auth/config`
Public server settings for the dashboard: `{"allow_signup": true, "version": "0.4.0"}`.

## Auth

### `POST /auth/register` → `201`
```json
{"name": "Ada", "email": "ada@example.com", "password": "at-least-8-chars"}
```
Returns the account and a session:
```json
{
  "account_id": "acct-4c468fb8e915",
  "name": "Ada",
  "email": "ada@example.com",
  "created_at": "2026-09-30T04:13:48.546959Z",
  "token": "eyJhbGciOi...",
  "expires_at": "2026-10-07T04:13:48.549391Z"
}
```
Returns `409` if the email is taken, and `403` if the server sets
`DRIFTGUARD_ALLOW_SIGNUP=false`.

### `POST /auth/login`
Body `{"email", "password"}`. Returns the same shape as register. A wrong password
and an unknown email both return the same `401`.

### `POST /auth/logout` → `204`
Revokes the session token used for the call. Other sessions stay valid.

### `GET /auth/me`
`{"account_id", "name", "email", "created_at"}`.

### `DELETE /auth/me` → `204`
Body `{"password": "..."}`. Permanently deletes the account, every project, and
all of their telemetry, alerts, and sessions. A wrong password returns `403`.

## Projects

A project is one monitored application. Its ID appears in every URL. IDs are 1–64
characters from letters, digits, `-` and `_`, and they're unique across the whole
server.

### `GET /projects`
With a session token, lists the account's projects. With an API key, returns just
that key's project.

```json
[{"project_id": "coding-agent", "account_id": "acct-…", "name": "Coding Agent",
  "environment": "prod", "api_key_hint": "dg_live_i4BK", "created_at": "…"}]
```

### `POST /projects` → `201` *(session)*
```json
{"project_id": "coding-agent", "name": "Coding Agent", "environment": "prod"}
```
`environment` is one of `prod`, `staging`, `dev`, `test`. The response is the
project plus `"api_key": "dg_live_…"`. **The key is shown only in this response.**
Returns `409` if the ID is already taken.

### `GET /projects/{id}` *(session or key)*
Returns the project object without the key.

### `DELETE /projects/{id}` → `204` *(session)*
Deletes the project and all of its events, agent events, alerts, and policy.

### `POST /projects/{id}/api-key` *(session)*
Issues a new key and returns the project with `api_key`. The old key stops working
immediately.

## Policy

### `GET /projects/{id}/policy` *(session or key)*
```json
{
  "prompt_token_limit": 3000.0,
  "retrieval_score_floor": 0.5,
  "context_length_limit": 4000.0,
  "response_quality_floor": 0.8,
  "blocked_after_failures": 3,
  "retry_window_minutes": 60.0
}
```

### `PUT /projects/{id}/policy` *(session)*
Send any subset of the fields above. Unknown fields return `422`. Constraints:
limits `> 0`; floors between 0 and 1; `blocked_after_failures` 1–100;
`retry_window_minutes` 0–10080 (0 turns off the window). Returns the merged policy.

## SDK ingestion *(API key)*

### `POST /events/{id}`
Sends one LLM request's telemetry. Every field is optional.

```json
{
  "prompt_tokens": 5200,
  "context_length": 6100,
  "retrieval_score": 0.31,
  "response_quality": 0.62,
  "environment": "prod",
  "occurred_at": "2026-09-30T04:13:48Z",
  "metadata": {"model": "claude-x", "request_id": "r-42"}
}
```

- Scores must be between 0 and 1. Token and length values must be `>= 0`.
- `occurred_at` defaults to the server time. Timestamps more than 5 minutes in
  the future are replaced with the server time.
- `metadata` takes at most 32 keys with scalar values. String values are
  scrubbed for PII.

The server scores the event against the project policy and stores the score. The
response:

```json
{"project_id": "coding-agent", "status": "ingested", "severity": "critical", "risk_score": 1.0,
 "recommendation": "compress_prompt_context_and_reduce_context_window",
 "actions": ["compress_prompt_context", "trim_retrieval_results", "fallback_to_lower_cost_model"],
 "root_cause": "prompt context inflation; retrieval degradation; response quality degradation"}
```

A `critical` event also raises a drift alert (`source: "drift"`). While an
unresolved drift alert with the same root cause and environment is newer than
`DRIFTGUARD_DRIFT_ALERT_COOLDOWN_MINUTES` (15 by default), no new one is created.

### `POST /events/{id}/batch`
Body `{"events": [ ...1–500 events... ]}`. Returns
`{"project_id", "ingested": 11, "critical": 1}`. The SDK always uses this
endpoint.

### `POST /agent-events/{id}`
Sends one agent tool attempt:

```json
{
  "task_id": "fix-tests",
  "tool_name": "terminal",
  "status": "failed",
  "trace_id": "run-1",
  "agent_name": "coding-agent",
  "model": "claude-x",
  "tool_call_id": "call-42",
  "attempt": 3,
  "error_type": "command_failed",
  "error_message": "pytest exited with code 1",
  "input_hash": "9f2c1a…",
  "prompt_tokens": 1800,
  "completion_tokens": 400,
  "total_tokens": 2200,
  "duration_ms": 5120,
  "environment": "prod",
  "occurred_at": "2026-09-30T04:13:48Z"
}
```

- `task_id`, `tool_name` and `status` are required.
- `status` is lowercased. The diagnosis treats `failed`, `failure`, `error` and
  `timeout` as failures, and `success`, `succeeded`, `ok` and `completed` as
  successes.
- `error_message` is scrubbed for secrets and PII, and cut to 4,000 characters.
- `input_hash` is a fingerprint of the tool's arguments. It lets DriftGuard spot
  redundant calls that repeat input which already succeeded.

After each ingest, the server re-diagnoses the affected tasks:

- If a task becomes **blocked**, the server raises one alert for it
  (`source: "agent"`, `task_id`).
- While the task stays blocked, the alert's `saved_tokens` and message keep
  updating.
- When the task recovers, the server resolves the alert.

### `POST /agent-events/{id}/batch`
Body `{"events": [ ...1–500... ]}` → `{"project_id", "ingested": n}`.

## Dashboard reads

The read endpoints accept these filters as query parameters:

- `environment`: `prod`, `staging`, `dev` or `test`
- `severity`: `stable`, `warning` or `critical`
- `time_range`: `15m`, `1h`, `24h`, `7d`, `30d` or `all` (the default)

### `GET /projects/{id}/summary` *(session or key)*
Overview numbers. Filters: `environment`, `severity` (applies to alerts), `time_range`.

```json
{
  "project_id": "coding-agent",
  "status": "critical",
  "total_events": 1,
  "events_by_severity": {"critical": 1},
  "averages": {"prompt_tokens": 5200.0, "context_length": 6100.0, "retrieval_score": 0.31,
               "response_quality": 0.62, "risk_score": 1.0},
  "violation_rates": {"prompt_token_limit": 1.0, "context_length_limit": 1.0,
                      "retrieval_score_floor": 1.0, "response_quality_floor": 1.0},
  "top_root_causes": [{"root_cause": "prompt context inflation; …", "count": 1}],
  "open_alerts": 2, "critical_alerts": 2, "warning_alerts": 0,
  "saved_tokens": 8940.0,
  "last_updated": "2026-09-30T04:13:48.601517Z",
  "policy": {"prompt_token_limit": 3000.0, "…": "…"},
  "filters": {"environment": "all", "severity": "all", "time_range": "all"}
}
```

- `status` reflects **open** alerts only.
- `averages` values are `null` when there are no events.
- `violation_rates` gives the share of events in the window that broke each rule
  in the current policy.
- `saved_tokens` adds up the tokens at stake across open alerts. For drift alerts
  that's the estimated tokens a mitigation would save. For agent alerts it's the
  tokens already wasted on retries.

### `GET /projects/{id}/events` *(session or key)*
Filters: `environment`, `time_range`, `limit` (1–500, default 100), and
`before_id`. Pass the last `id` you received as `before_id` to get the next page.
Results are newest first. Each item has the ingested fields plus `id`,
`risk_score`, `severity`, `root_cause`, `recommendation`, `metadata` and
`created_at`.

### `POST /projects/{id}/events` *(session)*
The dashboard's **Test Telemetry** form. It takes the same body as
`POST /events/{id}` and returns the same response.

### `GET /projects/{id}/alerts` *(session or key)*
Filters: `environment`, `severity`, `time_range`, `resolved` (`true`/`false`),
and `limit` (1–500, default 200). Results are newest first.

```json
{
  "id": 2, "project_id": "coding-agent", "severity": "critical",
  "message": "The terminal tool failed 3 time(s) in a row on task fix-tests; 6,600 tokens were spent on failed or redundant attempts. Latest error: pytest exited with code 1",
  "saved_tokens": 6600.0, "environment": "prod",
  "source": "agent", "task_id": "fix-tests", "root_cause": "blocking tool: terminal",
  "resolved": false, "resolved_at": null, "created_at": "2026-09-30T04:13:48.601517Z"
}
```

`source` is one of:

- `manual`: created through the API
- `drift`: raised by a critical telemetry event
- `agent`: raised by a blocked task

### `POST /projects/{id}/alerts` → `201` *(session)*
Body `{"severity", "message", "saved_tokens"?, "environment"?}`. Creates a
`manual` alert.

### `PATCH /projects/{id}/alerts/{alert_id}` *(session)*
Body `{"resolved": true}` resolves the alert. `false` reopens it. Returns the
alert.

### `GET /projects/{id}/agent-events` *(session or key)*
Filters: `environment`, `time_range`, `task_id`, and `limit` (1–1000, default
200). Results are newest first.

### `GET /projects/{id}/agent-diagnosis` *(session or key)*
Filters: `environment`, `time_range`. The top-level fields describe the most
urgent task, and `tasks` lists every task in the window, most urgent first. The
algorithm is described in [architecture.md](architecture.md#agent-diagnosis).

```json
{
  "status": "critical", "task_blocked": true, "blocked_tasks": 1, "failing_tasks": 0,
  "task_count": 1, "failure_count": 3, "repeated_attempts": 2, "redundant_attempts": 0,
  "wasted_tokens": 6600.0, "blocking_tool": "terminal",
  "diagnosis": "The terminal tool failed 3 time(s) in a row on task fix-tests; …",
  "recommendation": "Stop retrying terminal, inspect the first failing result, and fix the tool or its input.",
  "tasks": [{
    "task_id": "fix-tests", "trace_id": "run-1", "agent_name": null, "environment": "prod",
    "status": "blocked", "severity": "critical", "blocking_tool": "terminal",
    "consecutive_failures": 3, "failed_attempts": 3, "repeated_attempts": 2,
    "redundant_attempts": 0, "attempts": 3, "wasted_tokens": 6600.0, "total_tokens": 6600.0,
    "tools": ["terminal"], "last_error_type": "command_failed",
    "last_error": "pytest exited with code 1",
    "first_seen": "…", "last_seen": "…", "diagnosis": "…", "recommendation": "…"
  }]
}
```

A task's `status` is one of:

- `blocked`: an open run of failures at or above `blocked_after_failures`
- `failing`: an open run of failures below that threshold
- `recovered`: it failed earlier, but the same tool later succeeded
- `healthy`: no failures

## Realtime

### `WS /ws/projects/{id}`
Streams one message whenever an alert is created, resolved, or reopened:

```json
{"type": "alert", "action": "created", "alert": { "...alert object..." }}
```

`action` is `created`, `resolved` (by a user or by task recovery), or `reopened`.

**Authentication.** Pass the session token or project API key as the second
WebSocket subprotocol. The server replies with the `driftguard` subprotocol.

```js
new WebSocket(`wss://${host}/ws/projects/${id}`, ["driftguard", sessionToken]);
```

Clients that can't set subprotocols may use `?token=<session>` or
`?api_key=<key>` instead. Those values then appear in URL access logs, so prefer
the subprotocol.

Bad credentials close the socket with code `4401`; treat that as signed out
and don't reconnect. Messages sent by the client are ignored. With Redis
configured, alerts created on any worker reach clients connected to every
worker.
