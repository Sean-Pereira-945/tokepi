# Quickstart

This guide takes about ten minutes. By the end you'll have a DriftGuard server
running, a project and API key, telemetry and agent events flowing in, and a
blocked-task diagnosis on the dashboard.

## 1. Run the server

Pick one option.

**With Docker (PostgreSQL + Redis, production-like):**

```bash
git clone https://github.com/Sean-Pereira-945/tokepi.git driftguard && cd driftguard
cp .env.example .env
# In .env, set DRIFTGUARD_SECRET_KEY (python -c "import secrets; print(secrets.token_urlsafe(48))")
# and add a POSTGRES_PASSWORD line.
docker compose up -d --build
```

**Locally with Python (SQLite):**

```bash
pip install "driftguard[server]"
driftguard-server            # http://127.0.0.1:8000
```

The dashboard is served only if it was built into the package. Release wheels and
the Docker image include it. From a source checkout, build it once with
`cd frontend && npm ci && npm run build`. Without it, `/` shows a short notice,
and the API and its docs at `/docs` still work.

## 2. Create an account and a project

Open `http://localhost:8000`, create an account, then click **New project**.
Copy the API key it shows. **It's shown only once.** If you lose it, rotate it in
Project Settings.

You can do the same with the API:

```bash
TOKEN=$(curl -s -X POST localhost:8000/auth/register -H 'Content-Type: application/json' \
  -d '{"name":"Ada","email":"ada@example.com","password":"correct-horse"}' | jq -r .token)

curl -s -X POST localhost:8000/projects -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"project_id":"coding-agent","name":"Coding Agent","environment":"prod"}'
# -> {..., "api_key": "dg_live_..."}
```

The project API key goes in your application. Your LLM provider key never goes
to DriftGuard.

## 3. Send LLM telemetry

```bash
pip install driftguard   # the SDK needs only httpx
```

```python
from driftguard import DriftGuardClient

client = DriftGuardClient(
    api_key="dg_live_...",
    project_id="coding-agent",
    environment="prod",
    base_url="http://localhost:8000",
)
client.fetch_policy()  # use the project's thresholds locally

response = call_your_model(prompt)  # OpenAI, Anthropic, Gemini, Ollama, ...
client.capture_metrics(
    prompt_tokens=response.usage.input_tokens,
    context_length=len(prompt) // 4,  # or your real context token count
    retrieval_score=0.87,             # your RAG relevance score; 1.0 without RAG
    response_quality=0.92,            # your evaluator's score
)

print(client.check_drift())  # offline: severity, risk_score, actions, root_cause
client.sync_metrics()        # send queued events in batches
```

The server scores every event again against the project policy. A critical
event raises a drift alert.

## 4. Instrument an agent's tools

```python
from driftguard.adapters import AgentContext, driftguard_tool

@driftguard_tool("terminal")
def run_command(cmd: str) -> str:
    ...  # raise on failure

with AgentContext(client, task_id="fix-tests", auto_sync=True) as run:
    for step in agent_loop():
        response = llm.messages.create(...)
        run.record_llm_usage(response)  # tokens are attached to the next tool call
        run_command(step.command)
```

Every tool call becomes an agent event with task ID, attempt, status, error,
duration, and tokens. After three failures in a row of the same tool on a task,
DriftGuard marks the task **blocked**. It raises an alert with the wasted tokens
and resolves the alert when the tool later succeeds. The threshold and the retry
window are set in the project policy.

For MCP tools, other runtimes, and raw events, see
[agent-integration.md](agent-integration.md).

## 5. Watch it

- **Dashboard.** The Overview, Agent Diagnosis, Events, and Alerts views update
  live over a WebSocket.
- **SDK.** `client.fetch_agent_diagnosis()` returns the same diagnosis as the
  dashboard.
- **Notifications.** Set `DRIFTGUARD_SLACK_WEBHOOK` or `DRIFTGUARD_ALERT_WEBHOOK`
  to get critical alerts pushed to you.

Next: [configuration.md](configuration.md), [deployment.md](deployment.md),
[api.md](api.md).
