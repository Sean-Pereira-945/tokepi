# DriftGuard — Developer Quickstart

DriftGuard is an observability SDK for LLM applications and AI coding agents. Its
long-term purpose is to detect repeated failed tool requests, explain which tool is
blocking an agent task, and quantify wasted tokens. This quickstart covers the live
telemetry foundation; full agent retry analysis requires an adapter that can observe
the agent and its tools.

---

## 1. Install

```bash
pip install driftguard
```

---

## 2. Start the backend server

The DriftGuard SaaS backend is a FastAPI application you can run locally or deploy to any server.

```bash
# Install server dependencies
pip install "driftguard[dev]"

# Copy and configure the environment
cp .env.example .env
# Edit .env — set DATABASE_URL and API_SECRET

# Run the server
uvicorn driftguard.routes:app --reload --host 0.0.0.0 --port 8000
```

The dashboard is available at **http://localhost:8000** (served by `driftguard.routes`).
The SaaS API is served from the same base URL.

---

## 3. Register an account

```bash
curl -X POST http://localhost:8000/accounts \
  -H "Content-Type: application/json" \
  -d '{"name": "My Team"}'
```

Response:
```json
{
  "account_id": "acct-abc123def456",
  "name": "My Team",
  "token": "your-bearer-token"
}
```

Save the `token` — you'll use it as `Authorization: Bearer <token>` for management calls.

---

## 4. Create a project

```bash
curl -X POST http://localhost:8000/projects \
  -H "Authorization: Bearer <your-bearer-token>" \
  -H "Content-Type: application/json" \
  -d '{"project_id": "my-ai-app", "name": "My AI App", "environment": "prod"}'
```

Response includes:
```json
{
  "project_id": "my-ai-app",
  "api_key": "your-project-api-key",
  ...
}
```

Save the `api_key` — this authenticates SDK calls from your application.

The same project API key can be entered in the dashboard's **DRIFTGUARD API KEY**
field. This restricts the dashboard to that project's telemetry, alerts, summaries,
events, and policy. Do not enter a Gemini/OpenAI/Anthropic provider key here; keep
provider credentials in your application.

---

## 5. Integrate the SDK

```python
from driftguard.client import DriftGuardClient

client = DriftGuardClient(
    api_key="your-project-api-key",
    project_name="My AI App",
    environment="prod",
    base_url="http://localhost:8000",  # your DriftGuard server URL
)

# Capture metrics after each LLM call
client.capture_metrics(
    prompt_tokens=4200,
    retrieval_score=0.32,
    context_length=5200,
    response_quality=0.68,
)

# Evaluate drift locally using server-fetched or default thresholds
result = client.check_drift()
print(result)
# {
#   "severity": "critical",
#   "risk_score": 0.8,
#   "recommendation": "compress_prompt_context_and_reduce_context_window",
#   "actions": ["compress_prompt_context", "trim_retrieval_results"],
#   "root_cause": "prompt context inflation; retrieval degradation"
# }

# Sync all captured events to the backend database
client.sync_metrics("my-ai-app")

# Pull server-configured thresholds (updates local check_drift thresholds)
client.fetch_policy("my-ai-app")
```

## 6. Use DriftGuard with any LLM provider

DriftGuard does not call your model and does not depend on a provider SDK. Keep your
existing Gemini, OpenAI, Anthropic, Ollama, or custom model call, then send the
normalized signals below after each response:

```python
response = your_llm_call(prompt)  # Gemini, OpenAI, Anthropic, local model, etc.

client.capture_metrics(
  prompt_tokens=response.usage.input_tokens,
  context_length=len(prompt),
  retrieval_score=0.87,       # Your RAG/evaluation signal, or 1.0 without RAG
  response_quality=0.92,      # Your evaluator or application quality signal
)
client.sync_metrics("my-ai-app")
```

For Gemini, map `response.usage_metadata.prompt_token_count` to
`prompt_tokens` and `response.usage_metadata.total_token_count` to
`context_length` when those fields are available. The same four metric names are
the only integration contract; provider-specific response objects stay in your app.

## 7. Agent and tool monitoring boundary

The current SDK can be called after an agent turn, but it does not automatically
see GitHub Copilot's private conversation, tool calls, retries, or provider token
accounting. To deliver the full DriftGuard product goal, place an adapter or tool
gateway between the agent and its tools and emit events containing:

```json
{
  "task_id": "implement-login",
  "trace_id": "task-123",
  "agent_name": "coding-agent",
  "tool_name": "terminal",
  "tool_call_id": "call-42",
  "attempt": 3,
  "status": "failed",
  "error_type": "command_failed",
  "error_message": "pytest exited with code 1",
  "prompt_tokens": 1800,
  "completion_tokens": 400,
  "total_tokens": 2200
}
```

The planned analyzer will group events by task, detect repeated failed or
redundant attempts, calculate wasted tokens, identify the failing tool, and publish
a developer-facing blocked-task diagnosis. That analyzer and event schema are the
now implemented for the `agent-events` API and `DriftGuardClient` agent methods.
An adapter still needs to emit the events; automatic Copilot interception is not
implemented.

```python
client.capture_agent_event(
  task_id="fix-tests",
  trace_id="trace-1",
  tool_name="terminal",
  attempt=3,
  status="failed",
  error_type="command_failed",
  error_message="pytest exited with code 1",
  total_tokens=2200,
)
client.sync_agent_events("my-ai-app")
diagnosis = client.fetch_agent_diagnosis("my-ai-app")
print(diagnosis["diagnosis"])
```

---

## 8. Configure drift thresholds

Thresholds can be updated via the **Drift Policy** page in the dashboard, or directly via API:

```bash
curl -X PUT http://localhost:8000/projects/my-ai-app/policy \
  -H "Authorization: Bearer <your-bearer-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt_token_limit": 2500,
    "retrieval_score_floor": 0.6,
    "context_length_limit": 3500,
    "response_quality_floor": 0.85
  }'
```

---

## 9. Create alerts manually

The SDK automatically surfaces severity via `check_drift()`. You can also write alerts directly:

```bash
curl -X POST http://localhost:8000/alerts \
  -H "Authorization: Bearer <your-bearer-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "my-ai-app",
    "severity": "critical",
    "message": "Retrieval score dropped below 0.4 for 5 consecutive requests",
    "saved_tokens": 0.35
  }'
```

---

## 10. View the dashboard

Open **http://localhost:8000** (served by `driftguard.routes`) for the live dashboard:

- **Overview** — health score, drift index, KPIs, timeline chart
- **Telemetry Events** — table of all synced SDK events
- **Alerts** — live alert feed with severity and token savings
- **Drift Policy** — in-browser threshold editor
- **API Keys** — per-project SDK integration snippet

---

## API Reference (quick)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/accounts` | None | Register account → returns token |
| `POST` | `/auth/session` | None | Create token for existing account |
| `GET` | `/accounts/me` | Bearer | Current account info |
| `POST` | `/projects` | Bearer | Create project → returns api_key |
| `GET` | `/projects` | Bearer | List your projects |
| `GET` | `/projects/{id}` | Bearer | Project detail + alerts |
| `DELETE` | `/projects/{id}` | Bearer | Delete project |
| `GET` | `/projects/{id}/summary` | Bearer | Dashboard summary (health, savings, root cause) |
| `GET` | `/projects/{id}/policy` | Bearer or X-API-Key | Fetch drift thresholds |
| `PUT` | `/projects/{id}/policy` | Bearer | Update drift thresholds |
| `POST` | `/events/{id}` | X-API-Key | Ingest SDK telemetry event |
| `GET` | `/events/{id}` | Bearer | List recent events (max 100) |
| `POST` | `/agent-events/{id}` | X-API-Key | Ingest an agent/tool attempt |
| `GET` | `/projects/{id}/agent-diagnosis` | Bearer or X-API-Key | Diagnose failed tools and retry waste |
| `POST` | `/alerts` | Bearer | Create a drift alert |

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./driftguard.db` | Database connection string |
| `API_SECRET` | `driftguard-dev-secret-…` | Token signing secret — **always override in prod** |
| `RATE_LIMIT_PER_MINUTE` | `60` | Max API requests per IP per minute |

---

## Deploying to production

1. Set a strong `API_SECRET` environment variable
2. Set `DATABASE_URL` to a managed PostgreSQL connection string
3. Run behind a reverse proxy (nginx, Caddy) with TLS
4. Deploy with `uvicorn driftguard.routes:app --workers 4 --host 0.0.0.0 --port 8000`

---

## Publishing a new release

```bash
git tag v0.3.0
git push origin v0.3.0
```

The GitHub Actions workflow (`.github/workflows/release.yml`) will run all tests and
automatically publish to PyPI when the tag is pushed.
