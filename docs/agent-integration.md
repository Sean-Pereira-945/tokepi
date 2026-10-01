# Integrating an AI agent

DriftGuard's agent diagnosis works from **agent events**. Each event records one
tool call made while working on a task. Given those events, DriftGuard does four
things:

- It finds tasks that are stuck retrying a failing tool.
- It names the blocking tool.
- It counts the tokens spent on failed and redundant attempts.
- It raises an alert when a task becomes blocked, and resolves the alert when
  the task recovers.

DriftGuard only sees what your agent reports. Something in the agent's execution
path has to emit the events: the decorator, the MCP adapter, or your own code.

## The event

| Field | Required | Meaning |
| --- | --- | --- |
| `task_id` | yes | Stable ID of the job, e.g. `fix-tests` or a ticket ID. Events are grouped by it. |
| `kind` | | `tool_call` (the default), `llm_call`, `prompt`, `response`, `session_start` or `session_end`. Only tool calls feed the diagnosis; every kind appears in Logs. |
| `tool_name` | tool calls | The tool called: `terminal`, `browser`, `search`, an MCP tool name, and so on. |
| `status` | tool calls | `success` or `failed`. `timeout` and `error` also count as failures. |
| `trace_id` | | One run of the task. The adapters generate it. |
| `attempt` | | Nth call of this tool in the run. The adapters fill it in. |
| `error_type`, `error_message` | | Exception class or error code, and the message. Messages are scrubbed for secrets and cut to 4,000 characters. |
| `input_hash` | | Fingerprint of the tool arguments. A successful call whose hash already succeeded in the task counts as **redundant**. |
| `prompt_tokens`, `completion_tokens`, `total_tokens` | | LLM tokens spent on this attempt. |
| `duration_ms`, `model`, `agent_name`, `environment`, `occurred_at` | | Context. `occurred_at` defaults to the capture time. |
| `input`, `output` | | Content previews, such as tool arguments and results or prompt text. Sent only with `capture_content=True`, and stored only if the project has content storage on. See [Storing inputs and outputs](#storing-inputs-and-outputs). |

## Option 1: Python agents (decorator)

Use this when you control the agent loop. It works with sync and async tools,
threads, and asyncio.

```python
from driftguard import DriftGuardClient
from driftguard.adapters import AgentContext, driftguard_tool

client = DriftGuardClient(api_key="dg_live_...", project_id="coding-agent",
                          base_url="https://driftguard.example.com")

@driftguard_tool("terminal")
def run(cmd: str) -> str:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"{cmd} exited with {result.returncode}: {result.stderr[-500:]}")
    return result.stdout

@driftguard_tool("fetch")
async def fetch(url: str) -> str: ...

with AgentContext(client, task_id="fix-tests", auto_sync=True) as ctx:
    response = anthropic_client.messages.create(...)
    ctx.record_llm_usage(response)   # attributed to the next tool call
    run("pytest -x")
```

- Outside an `AgentContext`, decorated tools run unchanged and emit nothing.
- An exception is recorded as `failed` and then re-raised. Your agent's own retry
  logic is unaffected.
- `record_llm_usage` understands OpenAI, Anthropic, and Gemini response objects
  or dicts. You can also pass token counts directly:
  `record_llm_usage(prompt_tokens=..., completion_tokens=...)`.
- `auto_sync=True` sends events when the context exits. For long runs, call
  `client.sync_agent_events_async()` periodically.
- Inside a context, `ctx.record_tool_call(tool_name, status, ...)` records a call
  that isn't wrapped by the decorator.
- `ctx.record_activity(kind, input=..., output=..., **fields)` logs non-tool
  activity for the task, so Logs tells the whole story:

  ```python
  with AgentContext(client, task_id="fix-tests") as ctx:
      ctx.record_activity("prompt", input=user_request)
      response = llm.messages.create(...)
      ctx.record_activity("llm_call", model="claude-opus", status="success",
                          prompt_tokens=response.usage.input_tokens)
      run_tests("tests/")
      ctx.record_activity("response", output=final_answer)
  ```

## Storing inputs and outputs

By default, DriftGuard records what happened: which tool ran, whether it
worked, the error, tokens and timing. It doesn't record the content: the
command, the file contents, the tool's output, or the prompt. Content is useful
in Logs, but it can contain code and data, so both sides have to opt in:

1. **The project** stores content only when content storage is on in Project
   Settings (or via `PATCH /projects/{id}` with `{"capture_content": true}`).
   Otherwise the server drops it.
2. **The SDK** sends content only when the client is created with
   `capture_content=True`:

   ```python
   client = DriftGuardClient(api_key="dg_live_...", project_id="coding-agent",
                             base_url="http://localhost:8000", capture_content=True)
   ```

With both on, decorated tools send their arguments as `input` and their return
value as `output`. The MCP adapter sends the tool arguments and the text of the
result. `record_activity` sends what you pass it. Non-string values are
serialised to JSON. The SDK and the server both cut each field to 2,000
characters, and the server redacts secrets, emails and card numbers before
storing it.

## Option 2: MCP tools

Use this when your agent calls tools through the Model Context Protocol.

With the official `mcp` Python SDK, wrap the client session:

```python
from driftguard.adapters import MCPMiddleware

middleware = MCPMiddleware(client, task_id="fix-tests")
session = middleware.instrument_session(session)   # a mcp.ClientSession
result = await session.call_tool("run_tests", {"path": "tests/"})
middleware.context.record_llm_usage(llm_response)   # optional token attribution
client.sync_agent_events()
```

In a gateway or proxy that sees raw JSON-RPC, pass each `tools/call` request and
its response through the middleware:

```python
middleware.intercept_response(request_json, response_json, duration_ms=elapsed)
```

Both JSON-RPC `error` responses and results with `isError: true` count as
failures.

## Option 3: any language, raw HTTP

Send events to `POST /agent-events/{project_id}/batch` with header
`X-API-Key: dg_live_...`:

```bash
curl -X POST https://driftguard.example.com/agent-events/coding-agent/batch \
  -H "X-API-Key: $DRIFTGUARD_KEY" -H "Content-Type: application/json" \
  -d '{"events":[{"task_id":"fix-tests","tool_name":"terminal","status":"failed",
       "error_type":"exit_1","error_message":"pytest exited with code 1","total_tokens":2200}]}'
```

The field reference is in [api.md](api.md#post-agent-eventsid).

## Option 4: Claude Code (hooks, no code)

Claude Code's hooks can report a whole session with no code changes. A small
script, [`integrations/claude_code/driftguard_hook.py`](../integrations/claude_code/driftguard_hook.py),
handles it:
- Each prompt becomes a task, and each tool call is a `tool_call` event of that
  task.
- Failed commands and edits show up in Agent Diagnosis.
- Prompts and turn endings appear in Logs.

Setup is a config file with the project key plus a hooks entry. See
[integrations/claude_code/README.md](../integrations/claude_code/README.md).

## Reading the diagnosis

```python
diagnosis = client.fetch_agent_diagnosis()
diagnosis["status"]          # "critical" if any task is blocked
diagnosis["blocking_tool"]   # tool of the most urgent task
diagnosis["wasted_tokens"]   # across all tasks in the window
for task in diagnosis["tasks"]:
    print(task["task_id"], task["status"], task["diagnosis"])
```

An agent can use this to stop itself. If its own task shows up as blocked, it
should stop retrying and escalate to a person. The algorithm is described in
[architecture.md](architecture.md#agent-diagnosis). Tune it per project with the
`blocked_after_failures` and `retry_window_minutes` policy settings.

## LLM drift telemetry from agents

Agent turns can also send the four drift metrics through
`client.capture_metrics(...)`. That's useful for catching context bloat in long
sessions. `check_drift()` returns actions such as `compress_prompt_context`.
DriftGuard only recommends these actions and never applies them. Your agent
decides whether to prune history or trim retrieval.

## What DriftGuard cannot observe

- **GitHub Copilot, Cursor, and other closed agents.** Their conversation
  history, internal tool loops, and token usage aren't exposed to third parties.
  DriftGuard can't intercept them.
- **VS Code.** The extension API can observe editor activity and can host your
  own chat participant (`@driftguard`). It can't read Copilot's private session.
  A DriftGuard VS Code extension could only report on tools it runs itself, or on
  MCP servers routed through the DriftGuard MCP adapter.
- **Tokens the host doesn't report.** Tool calls alone carry no token counts, so
  you must attach LLM usage, as `record_llm_usage` does.

For closed agents that support MCP, the practical route is a small MCP gateway
between the agent and its MCP servers that calls
`MCPMiddleware.intercept_response`. DriftGuard provides the middleware but not a
ready-made gateway yet; that's on the [roadmap](roadmap.md).
