# Getting started

This page gets DriftGuard running and shows data on the dashboard. Pick **one**
of the three ways to start it, then pick a data source.

| I want to… | Use | Time |
| --- | --- | --- |
| See it working right now on Windows | [A. One click: `demo.bat`](#a-one-click-on-windows-demobat) | 2 min (first run ~5 min) |
| Run it from this repository and develop on it | [B. From source](#b-from-source-windows-macos-linux) | 10 min |
| Run it like production (PostgreSQL + Redis) | [C. Docker Compose](#c-docker-compose) | 10 min |

You need **Python 3.10+** for all three. You also need **Node.js 22** for A and
B, to build the dashboard once. For C you need **Docker**.

Once it's running, the dashboard is at **http://127.0.0.1:8000**. The API
documentation (Swagger) is at **http://127.0.0.1:8000/docs**.

---

## A. One click on Windows: `demo.bat`

Double-click `demo.bat` in the repository root. It:

1. creates `.venv` and installs DriftGuard into it (first run only),
2. builds the dashboard (first run only),
3. starts the server in its own window on port 8000. It uses the local SQLite
   file `driftguard-local.db`, never the database in `.env`,
4. opens the dashboard in your browser, and
5. runs the live demo script.

Sign in with **`demo@driftguard.local` / `driftguard-demo`** and pick the
**Live Demo** project. Press Enter in the script window to play each step.
[demo.md](demo.md) explains what each step shows.

To stop, close the window titled **DriftGuard server**. Your data stays in
`driftguard-local.db`. Run `demo.bat` again any time to restart.

---

## B. From source (Windows, macOS, Linux)

### 1. Install once

```bash
git clone https://github.com/Sean-Pereira-945/tokepi.git driftguard
cd driftguard

python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# macOS / Linux:         source .venv/bin/activate
pip install -e ".[server]"        # or ".[dev]" for tests, lint and Postgres/Redis drivers

cd frontend
npm ci
npm run build                     # writes the dashboard into driftguard/server/static/
cd ..
```

Skip `npm run build` and the server still runs, but `/` shows a short notice
instead of the dashboard. Run the build again whenever you change the
frontend.

### 2. Start the server

**Windows (PowerShell):**

```powershell
$env:DATABASE_URL = "sqlite:///./driftguard-local.db"
.venv\Scripts\driftguard-server --port 8000
```

**macOS / Linux:**

```bash
DATABASE_URL=sqlite:///./driftguard-local.db driftguard-server --port 8000
```

You should see `Uvicorn running on http://127.0.0.1:8000`. Check it with
http://127.0.0.1:8000/health, which returns `{"status":"ok","database":"ok",...}`.

> **Why set `DATABASE_URL`?** The server reads `.env` from the folder it runs in.
> If your `.env` points at a shared or remote database, setting `DATABASE_URL`
> keeps local work on a local SQLite file. It is created automatically, along
> with every table.

To stop it, press **Ctrl+C**. To start again, run the same command. Your data
is still there. **Restart after editing Python code**, or use `--reload`
while developing.

### 3. Create an account and a project

1. Open http://127.0.0.1:8000, click **Create one** under the sign-in form, and
   fill in your name, email and password.
2. Click **+** (New project) next to the project picker in the header. Give the project
   an ID (for example `my-agent`) and an environment.
3. **Copy the API key it shows (`dg_live_…`). It's shown only once.** If you
   lose it, use **Rotate API key** in Project Settings.

The project API key goes into whatever sends data. Your OpenAI or Anthropic
key never goes to DriftGuard.

Next, [send some data](#send-data).

---

## C. Docker Compose

```bash
git clone https://github.com/Sean-Pereira-945/tokepi.git driftguard && cd driftguard
cp .env.example .env
# In .env set:
#   DRIFTGUARD_SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(48))">
#   POSTGRES_PASSWORD=<a strong password>
docker compose up -d --build
```

This starts DriftGuard (two workers, dashboard included), PostgreSQL 16 and
Redis 7. Open http://localhost:8000 and create an account and a project as in
[B step 3](#3-create-an-account-and-a-project). Use `docker compose logs -f
driftguard` to watch it and `docker compose down` to stop it; your data stays
in the Docker volume. TLS, backups and scaling are covered in
[deployment.md](deployment.md).

---

## Send data

An empty project shows empty states. Pick any source below; you can use
several on the same server.

| Source | Good for | What it fills |
| --- | --- | --- |
| [1. Sample data](#1-sample-data-fills-every-view) | Exploring or presenting the dashboard | Every view |
| [2. Live demo script](#2-live-demo-script-a-story-in-four-steps) | A live walkthrough | Every view, step by step |
| [3. Claude Code](#3-claude-code-your-real-sessions-no-code) | Real data from your own coding sessions | Logs, Agent Diagnosis, Overview, Events, Analytics |
| [4. Your own app (SDK)](#4-your-own-app-python-sdk) | Real LLM apps and agents | Every view |

### 1. Sample data (fills every view)

Create an empty project, copy its key, and run:

```bash
python examples/seed_showcase.py --api-key dg_live_... --project-id showcase
```

This adds a week of realistic traffic. You get about 420 LLM requests over
three environments, with three drift episodes, and five agents whose tasks are
blocked, failing, recovered and healthy. Alerts and full Logs come with it.
Set the time range to **Last 7 days**. To also see inputs and outputs in Logs,
turn on **Content storage** in Project Settings **before** running it.

### 2. Live demo script (a story in four steps)

```bash
python examples/live_demo.py --email you@example.com --password '<your password>'
```

It creates (or recreates) the project `live-demo` and plays four steps:
normal traffic, drift, a stuck agent, and recovery. See [demo.md](demo.md).

### 3. Claude Code (your real sessions, no code)

The hook in [integrations/claude_code](../integrations/claude_code/README.md)
reports every prompt, tool call, failure and answer from a Claude Code session.
In short:

1. Create a project called `claude-code` and copy its key.
2. Create `.claude/driftguard.json` in the repository you use Claude Code in:
   ```json
   {"base_url": "http://127.0.0.1:8000", "project_id": "claude-code",
    "api_key": "dg_live_...", "capture_content": true}
   ```
3. Add the hooks to `.claude/settings.local.json`. The full snippet is in the
   integration README.
4. In the Policy view, raise the limits for Claude Code: prompt tokens
   **30000**, context **400000**. The defaults are sized for chat apps.
5. Start a new Claude Code session. Activity appears in **Logs** within seconds.

### 4. Your own app (Python SDK)

```bash
pip install driftguard        # the SDK needs only httpx
```

**LLM telemetry**, one event per model call:

```python
from driftguard import DriftGuardClient

client = DriftGuardClient(api_key="dg_live_...", project_id="my-agent",
                          environment="prod", base_url="http://127.0.0.1:8000")
client.fetch_policy()                     # use the project's thresholds locally

response = call_your_model(prompt)        # any provider
client.capture_metrics(
    prompt_tokens=response.usage.input_tokens,
    context_length=len(prompt) // 4,      # or your real context token count
    retrieval_score=0.87,                 # RAG relevance 0-1; leave out without RAG
    response_quality=0.92,                # your evaluator's score 0-1; leave out if none
)
print(client.check_drift())               # instant local verdict: severity, risk, actions
client.sync_metrics()                     # send the queued events
```

**Agent tool calls**, one event per call:

```python
from driftguard.adapters import AgentContext, driftguard_tool

@driftguard_tool("terminal")
def run_command(cmd: str) -> str:
    ...                                   # raise an exception on failure

with AgentContext(client, task_id="fix-tests", auto_sync=True) as run:
    response = llm.messages.create(...)
    run.record_llm_usage(response)        # its tokens go on the next tool call
    run_command("pytest -x")
```

When the same tool fails three times in a row in one task, DriftGuard marks the
task **blocked** and raises an alert that counts the wasted tokens. The alert
resolves itself once the tool succeeds. MCP tools, other languages, and
raw HTTP are covered in [agent-integration.md](agent-integration.md).

---

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `/` says "The dashboard has not been built" | Run `cd frontend && npm ci && npm run build`, then reload. |
| `address already in use` on port 8000 | A server is already running. Use it, stop it, or start this one with `--port 8001`. |
| The project picker doesn't list your project | You're signed in as a different account. Projects belong to the account that created them. Sign out and back in as the owner. |
| Data was sent but the dashboard is empty | Check the **time range** and **environment** filters in the header, then click **Refresh**. The sample data needs **Last 7 days**. |
| Retrieval or quality shows "—" or "Not reported by this source" | The source doesn't send that metric. Claude Code has no retrieval step and no answer grader, so DriftGuard leaves it blank instead of guessing. |
| Logs shows no inputs or outputs | Content storage is off. Turn it on in Project Settings. The sender must also allow it (`capture_content`). |
| `429 Too Many Requests` when signing in | The login limit is 10 per minute per IP. Wait a minute. |
| Claude Code activity isn't arriving | The server must be running when Claude Code works; events sent while it's down are dropped. Errors are written to `.claude/driftguard-hook.log`. Open `/hooks` in Claude Code once after editing the hook settings. |
| A Python change has no effect | Restart the server, or run it with `--reload`. |

Next: [how DriftGuard works](concepts.md) · [dashboard guide](dashboard.md) ·
[configuration](configuration.md)
