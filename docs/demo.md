# Giving a demo

A five-minute live demo: the dashboard sits on screen while a script plays a
small story: normal traffic, drift, an agent stuck in a retry loop, and its
recovery. Each step appears on the dashboard as it happens.

## One click on Windows

Double-click `demo.bat` in the repo root, or run it from a terminal. It:

1. creates `.venv` and installs the server if it's missing,
2. builds the dashboard if it hasn't been built,
3. starts the server in its own window on port 8000 against the local SQLite
   file `driftguard-local.db` (it ignores the database in `.env`), or reuses a
   server already running there,
4. opens the dashboard in your browser, and
5. runs the demo script, which creates the account
   `demo@driftguard.local` / `driftguard-demo` on first use.

Sign in with that account, select **Live Demo**, and press Enter in the script
window to move through the steps. Close the server window when you're done.

## Before the audience arrives (manual setup)

1. Build the dashboard once (skip if you installed a release wheel):

   ```bash
   cd frontend && npm ci && npm run build && cd ..
   ```

2. Start the server on a throwaway SQLite database, so the demo never touches
   real data:

   ```bash
   DATABASE_URL=sqlite:///./driftguard-demo.db driftguard-server --port 8000
   ```

3. Open http://127.0.0.1:8000 and create an account (for example
   `demo@example.com`). Keep the browser open.

4. In a second terminal, start the script. It logs in, recreates a project
   called `live-demo`, and waits:

   ```bash
   python examples/live_demo.py --email demo@example.com --password '<your password>'
   ```

5. In the dashboard, pick the **Live Demo** project.

## The script, step by step

Before each step, the script prints what it will do and which view to watch; press
Enter to run it. Agent Diagnosis stays empty until step 3, because no agent
events are sent before then.

| Step | What the script does | What to point at on the dashboard |
| --- | --- | --- |
| 1. Normal traffic | Sends 20 healthy LLM calls | Overview: low risk scores, no alerts |
| 2. Drift | Sends 6 calls with large prompts, low retrieval and low quality | A **critical drift alert** pops up live, with a root cause and recommendation |
| 3. Stuck agent | A coding agent's `run_tests` tool fails 3 times in a row | Agent Diagnosis: task `fix-login-bug` is **blocked**; an agent alert shows the tokens wasted on retries |
| 4. Recovery | The same tool succeeds | The task shows **recovered** and its alert **resolves itself** |

Run it again to reset: it deletes and recreates `live-demo` each time. The
script creates the account if it doesn't exist. Use `--no-pause` to run
straight through, `--base-url` if the server isn't on port 8000, and
`--project` if another account already owns the `live-demo` ID (project IDs
are unique across the server).

## A full dashboard to browse

The live script tells a short story. For a dashboard that's full in every view,
create an empty project, copy its API key, and run:

```bash
python examples/seed_showcase.py --api-key dg_live_... --project-id showcase
```

It adds a week of sample data:
- About 420 LLM requests across prod, staging and dev, from four models, with
  three drift episodes that build from warnings to critical.
- Five agents, with tasks that are blocked, failing, recovered and healthy, and
  calls that repeat input that already succeeded (redundant).
- Open and resolved alerts.
- Logs where every row is filled in. Each tool call has its command, output or
  error, duration and tokens. Each finished task ends with a response row
  holding the prompt, the answer, the task's duration and its tokens.

Turn on content storage for the project first if you want Logs to show inputs
and outputs. Set the time range to **Last 7 days** to see all of it.

## Presenting the project (10–15 minutes)

A running order that works for a class or a review. Open the dashboard before
you start, with the **Showcase** project loaded and **Last 7 days** selected.

| Min | Show | Say |
| ---: | --- | --- |
| 0–2 | [The architecture diagram](images/architecture.png) | The problem (quiet drift, stuck agents), and the three parts: sources, server, dashboard. |
| 2–4 | **Overview** | Status, open alerts, tokens at stake, and the agent activity row. Every number is a query over stored events. |
| 4–6 | **Agent Diagnosis** | A blocked task: which tool, how many tries, the wasted tokens and the advice. Open a task to show each attempt. |
| 6–7 | **Alerts** | Agent alerts resolve themselves when the task recovers. Drift alerts carry a root cause and a fix. |
| 7–9 | **Events** and **Analytics** | How one LLM call is scored: rules → risk → severity ([worked examples](concepts.md#how-a-telemetry-event-is-scored)). |
| 9–11 | **Logs**, switching to the **Claude Code** project | This is real data: the Claude Code session that built the project, with each command, its duration and its tokens. |
| 11–13 | Live: `demo.bat` or `live_demo.py` | Play steps 2–4. Show a drift alert popping up, then an agent blocking and recovering live. |
| 13–15 | Questions | Limits: it sees only what's reported, it recommends rather than acts, and quality needs an evaluator. |

For the explanations themselves, use [How DriftGuard works](concepts.md),
which ends with a 60-second summary you can read out.

**Remote audience:** share your screen (simplest and safest). Exposing your
local server to the internet means anyone with the link can reach the sign-in
page, so don't do it with real data in it.

## Talking points

- **The problem:** LLM apps degrade quietly (prompts grow, retrieval gets
  worse, answers get worse). Agents burn tokens retrying a tool that will
  never succeed.
- **How it plugs in:** the SDK needs only `httpx`. For agents, it's one
  decorator (`@driftguard_tool`) and a context block. Show
  [`examples/live_demo.py`](../examples/live_demo.py): the instrumentation is
  about five lines.
- **Privacy:** by default only metrics and tool outcomes are stored. Prompts,
  commands and outputs are kept only if a project turns on content storage,
  and they're scrubbed of secrets and PII first. Model API keys never reach
  DriftGuard.
- **Deployment:** it's self-hosted, from a single SQLite process up to Docker
  Compose with PostgreSQL and Redis ([deployment.md](deployment.md)).

## Showing it on another machine

With Docker, the whole stack is one command ([quickstart.md](quickstart.md)):
`docker compose up -d --build`. Then point the script at it with `--base-url`.
