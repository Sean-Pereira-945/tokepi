"""Claude Code hook that reports a session's activity to DriftGuard.

Claude Code runs this script on hook events and passes the event as JSON on
stdin. Each of your prompts becomes one DriftGuard task:

* every tool call in that turn is a ``tool_call`` event of the task, so a tool
  that keeps failing shows up as a blocked task in Agent Diagnosis;
* when Claude finishes the turn, one ``response`` event sums it up: your prompt
  (input), Claude's answer (output), the turn's duration, and the tokens of
  every model call in the turn.

Each finished turn also sends LLM telemetry, one event per model call, with
its new input tokens and its full context size, so the Overview, Events and
Analytics views chart the session. Set ``"send_telemetry": false`` to skip it.

Session start and end events are off by default (they carry no duration or
tokens); set ``"session_events": true`` to send them.

Configuration is read from ``.claude/driftguard.json`` in the project (keep it
out of version control, it holds the project API key)::

    {"base_url": "http://127.0.0.1:8000", "project_id": "claude-code",
     "api_key": "dg_live_...", "capture_content": false, "session_events": false}

``capture_content`` sends prompt text, tool inputs and tool outputs (previews,
2,000 characters each). The server still stores them only if the project has
content storage on.

Tool calls also get a duration and token counts, read from the session
transcript Claude Code keeps (``transcript_path``). The duration runs from the
moment Claude issued the call to its result, including any wait for your
approval. The tokens are those of the model call that issued it: new input plus
output, without the cached context re-read on every turn. Each model call is
counted once, on its first tool call.

The script uses only the standard library, never blocks Claude Code, and never
fails it: errors are written to ``.claude/driftguard-hook.log`` and the script
exits 0.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PREVIEW_LIMIT = 2000
HTTP_TIMEOUT_SECONDS = 2.0
STATE_DIR_NAME = "driftguard-state"
# How much of the end of the transcript to search for the tool call (it was just written).
TRANSCRIPT_TAIL_BYTES = 1_000_000
# How much to read when summing a whole turn's model calls.
TURN_TAIL_BYTES = 8_000_000
# A turn start further back than this is treated as unknown rather than trusted.
MAX_TURN_MS = 6 * 3600 * 1000
# Model calls already counted, remembered per session so tokens are attributed once.
MAX_REMEMBERED_REQUESTS = 200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def preview(value: Any) -> str | None:
    """Short text form of a prompt, tool input or tool output."""
    if value is None:
        return None
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    return text if len(text) <= PREVIEW_LIMIT else text[:PREVIEW_LIMIT] + " …[truncated]"


def fingerprint(tool_name: str, tool_input: Any) -> str:
    encoded = json.dumps([tool_name, tool_input], sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()[:16]


def _error_text(payload: dict[str, Any]) -> str | None:
    """The error of a failed tool call, from whichever field the event carries."""
    error = payload.get("error")
    if isinstance(error, dict):
        error = error.get("message") or json.dumps(error, default=str)
    if error:
        return str(error)
    response = payload.get("tool_response")
    if isinstance(response, dict):
        for key in ("error", "stderr"):
            if response.get(key):
                return str(response[key])
    return None


def tool_output(response: Any) -> Any:
    """The useful part of a tool response: command output or file content rather than raw JSON."""
    if isinstance(response, dict):
        for key in ("stdout", "content", "result", "output", "message"):
            value = response.get(key)
            if isinstance(value, str) and value.strip():
                return value
        file = response.get("file")
        if isinstance(file, dict) and isinstance(file.get("content"), str):
            return file["content"]
        if response.get("filePath"):
            return f"updated {response['filePath']}"
    return response


def _response_failed(response: Any) -> bool:
    """Whether a PostToolUse response still describes a failure."""
    if not isinstance(response, dict):
        return False
    if response.get("is_error") or response.get("isError") or response.get("interrupted"):
        return True
    return response.get("success") is False


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def transcript_details(transcript_path: Any, tool_use_id: Any, now: datetime | None = None) -> dict[str, Any]:
    """Timing, model and token usage for one tool call, from the session transcript.

    Returns ``started_at``, ``duration_ms``, ``model``, ``request_id`` and
    ``usage`` (``prompt_tokens``/``completion_tokens``) when found, else ``{}``.
    """
    if not transcript_path or not tool_use_id:
        return {}
    path = Path(str(transcript_path))
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - TRANSCRIPT_TAIL_BYTES))
            lines = handle.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    for line in reversed(lines):
        if tool_use_id not in line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        message = entry.get("message")
        if entry.get("type") != "assistant" or not isinstance(message, dict):
            continue
        blocks = message.get("content")
        if not isinstance(blocks, list) or not any(
            isinstance(b, dict) and b.get("type") == "tool_use" and b.get("id") == tool_use_id for b in blocks
        ):
            continue
        details: dict[str, Any] = {}
        started = _parse_time(entry.get("timestamp"))
        if started is not None:
            elapsed = ((now or datetime.now(timezone.utc)) - started).total_seconds() * 1000
            if 0 <= elapsed <= 6 * 3600 * 1000:
                details["duration_ms"] = round(elapsed, 1)
        if message.get("model"):
            details["model"] = str(message["model"])[:128]
        usage = message.get("usage")
        if isinstance(usage, dict):
            prompt = int(usage.get("input_tokens") or 0) + int(usage.get("cache_creation_input_tokens") or 0)
            details["usage"] = {"prompt_tokens": prompt, "completion_tokens": int(usage.get("output_tokens") or 0)}
        details["request_id"] = entry.get("requestId") or message.get("id")
        return details
    return {}


def _read_tail(path: Path, size: int) -> list[str]:
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        handle.seek(max(0, handle.tell() - size))
        return handle.read().decode("utf-8", errors="replace").splitlines()


def _new_tokens(usage: dict[str, Any]) -> tuple[int, int]:
    """New input (uncached and cache-write) and output tokens of one model call."""
    prompt = int(usage.get("input_tokens") or 0) + int(usage.get("cache_creation_input_tokens") or 0)
    return prompt, int(usage.get("output_tokens") or 0)


def turn_summary(transcript_path: Any, since: datetime | None) -> dict[str, Any]:
    """The current turn from the transcript: when it started, the prompt, model, tokens and last answer.

    ``since`` is when the prompt was submitted (from the hook state). Without it,
    the turn starts at the last prompt typed by the user.
    """
    if not transcript_path:
        return {}
    try:
        lines = _read_tail(Path(str(transcript_path)), TURN_TAIL_BYTES)
    except OSError:
        return {}
    entries = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
    start_index = 0
    prompt = None
    if since is None:
        for index in range(len(entries) - 1, -1, -1):
            entry = entries[index]
            message = entry.get("message")
            if entry.get("type") != "user" or not isinstance(message, dict) or entry.get("isMeta"):
                continue
            text = message.get("content")
            # Typed prompts only: Claude Code also injects user-role messages (task
            # notifications, reminders, command output) that start with a tag.
            if isinstance(text, str) and text.strip() and not text.lstrip().startswith("<"):
                since, prompt, start_index = _parse_time(entry.get("timestamp")), text, index
                break
    if since is not None and (datetime.now(timezone.utc) - since).total_seconds() * 1000 > MAX_TURN_MS:
        return {}
    requests: dict[str, tuple[int, int]] = {}
    calls: dict[str, dict[str, Any]] = {}
    summary: dict[str, Any] = {}
    for entry in entries[start_index:]:
        message = entry.get("message")
        stamp = _parse_time(entry.get("timestamp"))
        if entry.get("type") != "assistant" or not isinstance(message, dict) or (since and stamp and stamp < since):
            continue
        if isinstance(message.get("usage"), dict):
            key = str(entry.get("requestId") or message.get("id") or len(requests))
            requests[key] = _new_tokens(message["usage"])
            usage = message["usage"]
            context = sum(
                int(usage.get(k) or 0)
                for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
            )
            calls.setdefault(
                key,
                {
                    "request_id": key,
                    "timestamp": entry.get("timestamp"),
                    "model": message.get("model"),
                    "prompt_tokens": requests[key][0],
                    "context_length": context,
                },
            )
        if message.get("model"):
            summary["model"] = str(message["model"])[:128]
        for block in message.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                summary["last_text"] = block["text"]
    if since is not None:
        summary["started_at"] = since
    if prompt is not None:
        summary["prompt"] = prompt
    if requests:
        summary["prompt_tokens"] = sum(p for p, _ in requests.values())
        summary["completion_tokens"] = sum(c for _, c in requests.values())
        summary["model_calls"] = len(requests)
        summary["calls"] = list(calls.values())
    return summary


def telemetry_events(turn: dict[str, Any], task_id: str) -> list[dict[str, Any]]:
    """One LLM telemetry event per model call in the turn, for the Overview and Events views.

    ``prompt_tokens`` is the new input of the call and ``context_length`` the full
    context it used (including cached context). Claude Code reports no retrieval
    or answer-quality score, so those metrics are left out rather than invented.
    """
    events = []
    for call in turn.get("calls") or []:
        metadata = {"source": "claude-code", "task_id": task_id[:128], "request_id": str(call["request_id"])[:128]}
        if call.get("model"):
            metadata["model"] = str(call["model"])[:128]
        event = {"prompt_tokens": call["prompt_tokens"], "context_length": call["context_length"], "metadata": metadata}
        if call.get("timestamp"):
            event["occurred_at"] = call["timestamp"]
        events.append(event)
    return events[-500:]


def build_events(
    payload: dict[str, Any],
    state: dict[str, Any],
    capture_content: bool,
    details: dict[str, Any] | None = None,
    *,
    session_events: bool = False,
    turn: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Turn one hook payload into DriftGuard agent events, updating ``state`` in place.

    ``state`` is per Claude Code session: the current task ID, the prompt
    counter, per-tool attempt counts, the model, and the model calls whose
    tokens were already counted. ``details`` comes from
    :func:`transcript_details` for tool calls, and ``turn`` from
    :func:`turn_summary` when Claude stops.
    """
    event_name = payload.get("hook_event_name")
    session_id = str(payload.get("session_id") or "session")
    base = {"agent_name": "claude-code", "trace_id": session_id, "occurred_at": _now()}
    if state.get("model"):
        base["model"] = state["model"]

    def content(event: dict[str, Any], *, input: Any = None, output: Any = None) -> dict[str, Any]:
        if capture_content:
            if (text := preview(input)) is not None:
                event["input"] = text
            if (text := preview(output)) is not None:
                event["output"] = text
        return event

    if event_name == "SessionStart":
        model = payload.get("model")
        if isinstance(model, dict):
            model = model.get("id") or model.get("display_name")
        if model:
            state["model"] = str(model)[:128]
            base["model"] = state["model"]
        state.setdefault("task_id", f"{session_id[:8]}-start")
        if not session_events:
            return []
        return [{**base, "task_id": state["task_id"], "kind": "session_start", "status": "info"}]

    if event_name == "UserPromptSubmit":
        # Nothing is sent yet: the turn is reported, complete, when Claude stops.
        state["prompts"] = int(state.get("prompts", 0)) + 1
        state["task_id"] = f"{session_id[:8]}-p{state['prompts']}"
        state["attempts"] = {}
        state["prompt"] = preview(payload.get("prompt"))
        state["turn_started"] = base["occurred_at"]
        return []

    task_id = state.setdefault("task_id", f"{session_id[:8]}-start")

    if event_name in {"PostToolUse", "PostToolUseFailure"}:
        tool_name = str(payload.get("tool_name") or "unknown_tool")[:128]
        attempts = state.setdefault("attempts", {})
        attempts[tool_name] = int(attempts.get(tool_name, 0)) + 1
        tool_input = payload.get("tool_input")
        response = payload.get("tool_response")
        failed = event_name == "PostToolUseFailure" or _response_failed(response)
        event: dict[str, Any] = {
            **base,
            "task_id": task_id,
            "tool_name": tool_name,
            "status": "failed" if failed else "success",
            "attempt": attempts[tool_name],
            "input_hash": fingerprint(tool_name, tool_input),
        }
        if payload.get("tool_use_id"):
            event["tool_call_id"] = str(payload["tool_use_id"])[:128]
        details = details or {}
        if "duration_ms" in details:
            event["duration_ms"] = details["duration_ms"]
        if details.get("model"):
            state["model"] = event["model"] = details["model"]
        counted = state.setdefault("counted_requests", [])
        request_id = details.get("request_id")
        if details.get("usage"):
            if request_id in counted:
                # Counted on an earlier tool call from the same model call.
                event.update(prompt_tokens=0, completion_tokens=0, total_tokens=0)
            else:
                usage = details["usage"]
                event.update(usage, total_tokens=usage["prompt_tokens"] + usage["completion_tokens"])
                if request_id:
                    counted.append(request_id)
                    del counted[:-MAX_REMEMBERED_REQUESTS]
        if failed:
            event["error_type"] = "interrupted" if payload.get("is_interrupt") else "tool_error"
            event["error_message"] = (_error_text(payload) or "Tool call failed")[:4000]
            return [content(event, input=tool_input, output=event["error_message"])]
        return [content(event, input=tool_input, output=tool_output(response))]

    if event_name == "Stop":
        turn = turn or {}
        event = {**base, "task_id": task_id, "kind": "response", "status": "success"}
        if turn.get("model"):
            state["model"] = event["model"] = turn["model"]
        started = _parse_time(state.get("turn_started")) or turn.get("started_at")
        if started is not None:
            elapsed = (_parse_time(base["occurred_at"]) - started).total_seconds() * 1000
            if 0 <= elapsed <= MAX_TURN_MS:
                event["duration_ms"] = round(elapsed, 1)
        if "prompt_tokens" in turn:
            event.update(
                prompt_tokens=turn["prompt_tokens"],
                completion_tokens=turn["completion_tokens"],
                total_tokens=turn["prompt_tokens"] + turn["completion_tokens"],
            )
        prompt = state.pop("prompt", None) or turn.get("prompt")
        state.pop("turn_started", None)
        return [content(event, input=prompt, output=payload.get("last_assistant_message") or turn.get("last_text"))]

    if event_name == "SessionEnd":
        if not session_events:
            return []
        return [{**base, "task_id": task_id, "kind": "session_end", "status": "info"}]

    return []


def send(config: dict[str, Any], events: list[dict[str, Any]], path: str = "agent-events") -> None:
    url = f"{str(config['base_url']).rstrip('/')}/{path}/{config['project_id']}/batch"
    request = urllib.request.Request(  # noqa: S310 - the URL comes from the user's own config file
        url,
        data=json.dumps({"events": events}).encode(),
        headers={"Content-Type": "application/json", "X-API-Key": str(config["api_key"])},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS):  # noqa: S310
        pass


def _project_dir(payload: dict[str, Any]) -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".")


def _log(claude_dir: Path, message: str) -> None:
    try:
        log = claude_dir / "driftguard-hook.log"
        if log.exists() and log.stat().st_size > 256_000:
            log.unlink()
        with log.open("a", encoding="utf-8") as handle:
            handle.write(f"{_now()} {message}\n")
    except OSError:
        pass


def main() -> None:
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    except (ValueError, OSError):
        return
    claude_dir = _project_dir(payload) / ".claude"
    config_path = claude_dir / "driftguard.json"
    if not config_path.is_file():
        return  # Not configured for this project: do nothing.
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if config.get("enabled") is False:
            return
        state_dir = claude_dir / STATE_DIR_NAME
        state_dir.mkdir(exist_ok=True)
        session = "".join(ch for ch in str(payload.get("session_id") or "session") if ch.isalnum() or ch in "-_")
        state_path = state_dir / f"{session[:64] or 'session'}.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
        details: dict[str, Any] = {}
        turn: dict[str, Any] = {}
        event_name = payload.get("hook_event_name")
        if event_name in {"PostToolUse", "PostToolUseFailure"}:
            details = transcript_details(payload.get("transcript_path"), payload.get("tool_use_id"))
        elif event_name == "Stop":
            turn = turn_summary(payload.get("transcript_path"), _parse_time(state.get("turn_started")))
        events = build_events(
            payload,
            state,
            bool(config.get("capture_content")),
            details,
            session_events=bool(config.get("session_events")),
            turn=turn,
        )
        state_path.write_text(json.dumps(state), encoding="utf-8")
        if payload.get("hook_event_name") == "SessionEnd":
            state_path.unlink(missing_ok=True)
        telemetry = telemetry_events(turn, events[0]["task_id"]) if turn and events else []
        if events:
            started = time.perf_counter()
            send(config, events)
            if telemetry and config.get("send_telemetry", True):
                send(config, telemetry, path="events")
            if (elapsed := time.perf_counter() - started) > 1:
                _log(claude_dir, f"slow send: {elapsed:.2f}s")
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        _log(claude_dir, f"DriftGuard unreachable ({exc}); event dropped")
    except Exception as exc:  # noqa: BLE001 - a hook must never break Claude Code
        _log(claude_dir, f"hook error: {exc!r}")


if __name__ == "__main__":
    main()
    sys.exit(0)
