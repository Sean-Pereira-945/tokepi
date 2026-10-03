# Setting up DriftGuard on your laptop

This guide takes a teammate from a fresh laptop to a running DriftGuard with
data on the dashboard. It takes about 15 minutes, mostly waiting for
installs. Each step has commands for **Windows (PowerShell)** and
**macOS / Linux**.

Once it's running, [How DriftGuard works](docs/concepts.md) explains the
project, and the [dashboard guide](docs/dashboard.md) explains each screen.

---

## 1. Install the tools (once)

| Tool | Version | Check with | Get it |
| --- | --- | --- | --- |
| Git | any recent | `git --version` | https://git-scm.com/downloads |
| Python | **3.10 or newer** | `python --version` (macOS/Linux: `python3 --version`) | https://www.python.org/downloads/. On Windows, tick **"Add python.exe to PATH"** in the installer. |
| Node.js | **22** (LTS) | `node --version` | https://nodejs.org/ |

Restart your terminal after installing, so the new commands are found.

You also need read access to the GitHub repo
(https://github.com/Sean-Pereira-945/tokepi). If `git clone` asks you to log
in or says *not found*, ask Sean to add you as a collaborator.

---

## 2. Get the code

```bash
git clone https://github.com/Sean-Pereira-945/tokepi.git DriftGuard
cd DriftGuard
```

Stay on `main`. It has everything that's been merged.

---

## 3. Install the Python side

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

If PowerShell says *running scripts is disabled*, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then activate
again.

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

`[dev]` installs the server, the test tools, and the PostgreSQL and Redis
drivers. Your prompt now starts with `(.venv)`. **Activate the environment
the same way in every new terminal** before running DriftGuard commands.

---

## 4. Build the dashboard

```bash
cd frontend
npm ci
npm run build
cd ..
```

This writes the dashboard into `driftguard/server/static/`, so the Python
server can serve it. Run `npm run build` again whenever you pull frontend
changes.

---

## 5. Start the server

You don't need a `.env` file. Without one, DriftGuard uses a local SQLite file
and safe development defaults.

> **Don't copy anyone else's `.env`.** Sean's points at the team's production
> database. Starting 0.4 against it changes that database permanently. Each of
> us develops on our own local SQLite file.

**Windows (PowerShell):**

```powershell
$env:DATABASE_URL = "sqlite:///./driftguard-local.db"
driftguard-server --port 8000
```

**macOS / Linux:**

```bash
DATABASE_URL=sqlite:///./driftguard-local.db driftguard-server --port 8000
```

You should see `Uvicorn running on http://127.0.0.1:8000`. Leave this
terminal open; **Ctrl+C** stops the server. Your data stays in
`driftguard-local.db`, which git ignores.

Check it: http://127.0.0.1:8000/health should return `{"status":"ok", ...}`.

**Windows shortcut:** instead of steps 3–5 you can double-click `demo.bat`.
It creates `.venv`, builds the dashboard, starts the server, opens the browser
and runs a scripted demo. It installs only the server, not the `[dev]` tools,
so run step 3 later if you want to run tests.

---

## 6. Create your account and a project

1. Open **http://127.0.0.1:8000**.
2. Click **Create one** under the sign-in form, and register with any email
   and password. The account lives only in your local database.
3. Click **+** next to the project picker in the header. Enter **Project ID**
   `showcase`, **Name** `Showcase` and **Default environment** `prod`.
4. **Copy the API key it shows (`dg_live_…`).** It's shown only once.
5. Open **Project Settings** and turn on **Content storage**, so Logs can show
   commands and outputs.

---

## 7. Fill it with sample data

In a **second** terminal, activate `.venv` (step 3), then run:

```bash
python examples/seed_showcase.py --api-key dg_live_PASTE_YOUR_KEY --project-id showcase
```

Back in the browser, set the time range to **Last 7 days**. Every view now
has data: drift episodes, blocked and recovered agent tasks, alerts and full
logs.

To see a story play out live instead, run the demo script. It creates its
own `live-demo` project:

```bash
python examples/live_demo.py --email YOUR_EMAIL --password YOUR_PASSWORD
```

Pick **Live Demo** in the project picker and press Enter in the terminal to
go through the four steps. [docs/demo.md](docs/demo.md) explains them.

---

## 8. (Optional) Log your own Claude Code sessions

If you use Claude Code in this repo, it can report its activity to your local
DriftGuard.

1. In the dashboard, create a project with the ID `claude-code`, copy its key,
   and turn on **Content storage**.
2. In **Policy**, set the prompt token limit to **30000** and the context
   length limit to **400000**, then save. The defaults are sized for chat
   apps.
3. Create `.claude/driftguard.json`. Git ignores it, so your key stays local.

   ```json
   {
     "base_url": "http://127.0.0.1:8000",
     "project_id": "claude-code",
     "api_key": "dg_live_PASTE_YOUR_KEY",
     "capture_content": true
   }
   ```

4. Create `.claude/settings.local.json`; git ignores it too. Use the Python
   path for your system:
   - Windows: `$CLAUDE_PROJECT_DIR/.venv/Scripts/python.exe`
   - macOS / Linux: `$CLAUDE_PROJECT_DIR/.venv/bin/python`

   ```json
   {
     "hooks": {
       "UserPromptSubmit":   [{ "hooks": [{ "type": "command", "shell": "bash", "timeout": 5, "command": "\"$CLAUDE_PROJECT_DIR/.venv/Scripts/python.exe\" \"$CLAUDE_PROJECT_DIR/integrations/claude_code/driftguard_hook.py\" 2>/dev/null || true" }] }],
       "PostToolUse":        [{ "matcher": "*", "hooks": [{ "type": "command", "shell": "bash", "timeout": 5, "command": "\"$CLAUDE_PROJECT_DIR/.venv/Scripts/python.exe\" \"$CLAUDE_PROJECT_DIR/integrations/claude_code/driftguard_hook.py\" 2>/dev/null || true" }] }],
       "PostToolUseFailure": [{ "matcher": "*", "hooks": [{ "type": "command", "shell": "bash", "timeout": 5, "command": "\"$CLAUDE_PROJECT_DIR/.venv/Scripts/python.exe\" \"$CLAUDE_PROJECT_DIR/integrations/claude_code/driftguard_hook.py\" 2>/dev/null || true" }] }],
       "Stop":               [{ "hooks": [{ "type": "command", "shell": "bash", "timeout": 5, "command": "\"$CLAUDE_PROJECT_DIR/.venv/Scripts/python.exe\" \"$CLAUDE_PROJECT_DIR/integrations/claude_code/driftguard_hook.py\" 2>/dev/null || true" }] }]
     }
   }
   ```

   On macOS/Linux, replace each `.venv/Scripts/python.exe` with
   `.venv/bin/python`.

5. Start a new Claude Code session. Its prompts, tool calls and answers appear
   under **Logs** in the `claude-code` project while the server is running.

More detail is in
[integrations/claude_code/README.md](integrations/claude_code/README.md).

---

## 9. Working on the code

**Run the checks** (with `.venv` active):

```bash
pytest                                   # about 170 tests, ~25 s
ruff check . && ruff format --check .
cd frontend && npm run lint && cd ..
```

**Frontend with hot reload:** keep the server running on port 8000, then in
another terminal:

```bash
cd frontend
npm run dev                              # http://localhost:5173, API calls go to :8000
```

**Python changes** need a server restart (Ctrl+C, then start it again), or
start it with `--reload` while you work.

**Team conventions:**
- Branch off `main` for each change, and open a pull request. Merge with
  **"Create a merge commit"** or **"Rebase and merge"**, not squash.
- Update the matching page in `docs/` and add a line to `CHANGELOG.md` in the
  same change.
- Never commit `.env`, `*.db` files, or anything in `.claude/` with a key in
  it. They're gitignored; keep them that way.

The full developer guide is [docs/development.md](docs/development.md).

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `python` or `npm` is not recognized | Reinstall with "Add to PATH" ticked, then open a new terminal. On macOS/Linux use `python3`. |
| `driftguard-server` is not recognized | `.venv` isn't active. Activate it (step 3). |
| `/` says "The dashboard has not been built" | Run step 4. |
| `address already in use` on port 8000 | A server is already running. Stop it, or use `--port 8001` and open that port instead. |
| The dashboard is empty after seeding | Set the time range to **Last 7 days**, check the environment is **All**, and click **Refresh**. |
| My project isn't in the picker | You're signed in as a different account. Projects belong to the account that created them. |
| `429 Too Many Requests` when signing in | The limit is 10 sign-ins per minute. Wait a minute. |
| `npm ci` fails | Check `node --version` is 22. Delete `frontend/node_modules` and try again. |
| I want to see a teammate's data | Each laptop has its own database. To share data, the team needs one shared server; see [docs/deployment.md](docs/deployment.md). |

Still stuck? Ask in the team chat with the exact error message.
