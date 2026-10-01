# Claude Code integration

Reports a Claude Code session's activity to DriftGuard through
[Claude Code hooks](https://docs.claude.com/en/docs/claude-code/hooks), with
no code changes and nothing to install beyond Python.

| Claude Code event | DriftGuard event |
| --- | --- |
| `UserPromptSubmit` | Starts a new **task** (`<session>-p<n>`). Nothing is sent yet. |
| `PostToolUse` | A `tool_call` with status `success` (`failed` if the response is an error) |
| `PostToolUseFailure` | A `tool_call` with status `failed` and the error |
| `Stop` | One `response` for the whole turn: your prompt (input), Claude's answer (output), the turn's duration, and the tokens of every model call in it |
| `SessionStart`, `SessionEnd` | `session_start` and `session_end`, only with `"session_events": true` |

Every row has its status, model, duration and tokens.
- Tool calls take their duration and tokens from the session transcript.
- The output is the command's output, the file's content, or the error.
- A tool call that shares a model call with the one before it shows 0 tokens,
  because that model call was already counted.
- **Attempt** applies only to tool calls, so it's empty on response rows.

Each finished turn also sends **LLM telemetry**: one event per model call, with
its new input tokens (`prompt_tokens`) and the full context it used
(`context_length`, including cached context). The model and task go in
metadata. That data feeds the Overview cards, the timeline, Events and
Analytics. Claude Code has no retrieval or answer-quality score, so those are
left out, not invented. Set `"send_telemetry": false` to skip it.

The default policy limits (3,000 prompt tokens, 4,000 context) are meant for
chat requests. For a Claude Code project, raise them in the Policy view, for
example to 30,000 new tokens per call and 400,000 context. Then a warning means
real context bloat.

Every tool call belongs to the task of the prompt that caused it. Agent
Diagnosis therefore shows when Claude keeps retrying a failing tool, such as a
test command or an edit that won't apply. The task is marked **blocked** and an
agent alert fires. The alert resolves itself once the tool succeeds. Logs shows
the whole session.

## Setup

1. **Run a DriftGuard server** (see [docs/quickstart.md](../../docs/quickstart.md)),
   and create a project for Claude Code. Copy its API key.
2. **Create `.claude/driftguard.json`** in the repository you use Claude Code in.
   It holds the key, so keep it out of version control:

   ```json
   {
     "base_url": "http://127.0.0.1:8000",
     "project_id": "claude-code",
     "api_key": "dg_live_...",
     "capture_content": true
   }
   ```

   `"session_events": true` also sends session start and end. They have no
   duration or tokens, so they're off by default.
   `capture_content` lets the hook send prompt text and tool inputs and outputs,
   each cut to 2,000 characters. The server stores them only if the project has
   content storage turned on in Project Settings. Set `"enabled": false` to pause
   reporting without removing the hooks.
3. **Add the hooks** to `.claude/settings.local.json` (personal) or
   `.claude/settings.json` (shared with the team). Point `command` at a Python
   3.10+ interpreter and at this script:

   ```json
   {
     "hooks": {
       "UserPromptSubmit": [{"hooks": [{"type": "command", "shell": "bash", "timeout": 5,
         "command": "python \"$CLAUDE_PROJECT_DIR/integrations/claude_code/driftguard_hook.py\" 2>/dev/null || true"}]}],
       "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "shell": "bash", "timeout": 5,
         "command": "python \"$CLAUDE_PROJECT_DIR/integrations/claude_code/driftguard_hook.py\" 2>/dev/null || true"}]}]
     }
   }
   ```

   Add the same entry for `PostToolUseFailure`, `Stop`, `SessionStart` and
   `SessionEnd` to get the full picture. In another repository, use the
   script's absolute path.
4. Start a new Claude Code session, or open `/hooks` once so the hooks load.

## Behaviour and limits

- **It never gets in Claude's way.** The script uses only the standard library
  and gives up on the server after 2 seconds. It always exits 0. If the server is
  down, events are dropped and a line goes to `.claude/driftguard-hook.log`.
  Each call adds about 0.3 s, mostly Python start-up.
- **State** (the current task and attempt counts) is kept per session in
  `.claude/driftguard-state/` and removed when the session ends.
- **Duration, tokens and model come from the session transcript**, since
  hooks don't receive them.
  - The duration runs from Claude issuing the call to the result, including
    any wait for your approval.
  - Tokens are those of the model call that issued the tool: new input plus
    output. The cached context Claude re-reads every turn is left out, so
    wasted-token figures reflect new work rather than cache reads.
  - When one model call issues several tools, its tokens go on the first.
- **It sees tool calls, not reasoning.** It shows what Claude did and whether it
  worked, not whether the final answer was right.
