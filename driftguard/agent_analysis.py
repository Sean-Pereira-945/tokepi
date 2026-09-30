"""Diagnosis of failed, repeated, and token-wasting agent tool attempts.

Events are grouped by ``task_id`` and replayed in time order. For each task the
analyzer tracks runs of consecutive failures per tool:

* a later success of the same tool closes the run, so the task is ``recovered``;
* failures further apart than ``retry_window_minutes`` start a new run;
* an open run of at least ``blocked_after_failures`` failures marks the task
  ``blocked``, a shorter open run marks it ``failing``.

Wasted tokens are the tokens of every failed attempt plus the tokens of redundant
attempts: a successful call whose ``(tool_name, input_hash)`` already succeeded
earlier in the same task.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from .policy import DEFAULT_POLICY

FAILED_STATUSES = frozenset({"failed", "failure", "error", "timeout"})
SUCCESS_STATUSES = frozenset({"success", "succeeded", "ok", "completed"})

_STATUS_ORDER = {"blocked": 0, "failing": 1, "recovered": 2, "healthy": 3}
_SEVERITY = {"blocked": "critical", "failing": "warning", "recovered": "stable", "healthy": "stable"}

# Ordered (keywords, advice) pairs matched against the error type and message.
_ERROR_ADVICE: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("timeout", "timed out", "deadline"),
        "The tool is timing out. Check that it is reachable, "
        "raise its timeout, or split the request into smaller steps.",
    ),
    (
        ("permission", "forbidden", "unauthorized", "401", "403", "access denied"),
        "The tool is rejecting credentials or permissions. Fix access before letting the agent retry.",
    ),
    (
        ("not found", "notfound", "404", "no such file", "enoent", "modulenotfound"),
        "The tool cannot find its target. Verify the path, resource name, or installed dependency.",
    ),
    (
        ("rate limit", "ratelimit", "429", "too many requests"),
        "The tool is rate limited. Back off between attempts instead of retrying immediately.",
    ),
    (
        ("syntax", "parse", "invalid json", "validation", "schema"),
        "The agent is sending malformed input. Inspect the arguments of the first failed call.",
    ),
)


def _event_tokens(event: Mapping[str, Any]) -> float:
    """Return an event's token total, preferring an explicit ``total_tokens``."""
    total = event.get("total_tokens")
    if total is not None:
        return float(total)
    return float(event.get("prompt_tokens") or 0) + float(event.get("completion_tokens") or 0)


def _as_datetime(value: Any) -> datetime | None:
    """Parse a timestamp (datetime or ISO string) into an aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _iso(value: datetime | None) -> str | None:
    """Format a datetime as an ISO 8601 UTC string."""
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if value else None


def _advice(error_type: str | None, error_message: str | None, tool: str) -> str:
    """Pick a recommendation for a failing tool from its error signature."""
    haystack = f"{error_type or ''} {error_message or ''}".lower()
    for keywords, advice in _ERROR_ADVICE:
        if any(keyword in haystack for keyword in keywords):
            return advice
    return f"Stop retrying {tool}, inspect the first failing result, and fix the tool or its input."


def _analyze_task(
    task_id: str, events: list[Mapping[str, Any]], blocked_after: int, window_seconds: float
) -> dict[str, Any]:
    """Replay one task's events in order and summarize its failure state."""
    runs: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    succeeded_inputs: set[tuple[str, str]] = set()
    failed = repeated = redundant = 0
    wasted = total_tokens = 0.0
    last_failure: Mapping[str, Any] | None = None
    tools: list[str] = []

    for event in events:
        tool = str(event.get("tool_name") or "unknown-tool")
        if tool not in tools:
            tools.append(tool)
        status = str(event.get("status") or "").lower()
        tokens = _event_tokens(event)
        total_tokens += tokens

        if status in FAILED_STATUSES:
            failed += 1
            wasted += tokens
            last_failure = event
            run = runs[tool]
            if run and window_seconds > 0:
                previous, current = _as_datetime(run[-1].get("created_at")), _as_datetime(event.get("created_at"))
                if previous and current and (current - previous).total_seconds() > window_seconds:
                    run.clear()
            if run:
                repeated += 1
            run.append(event)
        elif status in SUCCESS_STATUSES:
            input_hash = event.get("input_hash")
            if input_hash:
                key = (tool, str(input_hash))
                if key in succeeded_inputs:
                    redundant += 1
                    wasted += tokens
                succeeded_inputs.add(key)
            runs[tool].clear()

    open_runs = {tool: run for tool, run in runs.items() if run}
    blocking_tool: str | None = None
    consecutive = 0
    if open_runs:
        # Longest open run wins; ties go to the run that failed most recently.
        blocking_tool = max(
            open_runs,
            key=lambda t: (
                len(open_runs[t]),
                _as_datetime(open_runs[t][-1].get("created_at")) or datetime.min.replace(tzinfo=timezone.utc),
            ),
        )
        consecutive = len(open_runs[blocking_tool])
        status = "blocked" if consecutive >= blocked_after else "failing"
        last_failure = open_runs[blocking_tool][-1]
    elif failed:
        status = "recovered"
    else:
        status = "healthy"

    last_error_type = last_failure.get("error_type") if last_failure else None
    last_error = last_failure.get("error_message") if last_failure else None
    times = [t for t in (_as_datetime(e.get("created_at")) for e in events) if t]

    if status in {"blocked", "failing"}:
        diagnosis = (
            f"The {blocking_tool} tool failed {consecutive} time(s) in a row on task {task_id}; "
            f"{wasted:,.0f} tokens were spent on failed or redundant attempts."
        )
        if last_error:
            diagnosis += f" Latest error: {last_error}"
        recommendation = _advice(last_error_type, last_error, blocking_tool or "the tool")
    elif status == "recovered":
        diagnosis = (
            f"Task {task_id} recovered after {failed} failed attempt(s); "
            f"{wasted:,.0f} tokens were spent on failed or redundant attempts."
        )
        recommendation = "No action needed now. Review the failed attempts to prevent the retry loop."
    else:
        diagnosis = f"Task {task_id} has no failed tool attempts."
        if redundant:
            diagnosis += f" {redundant} redundant call(s) repeated an input that had already succeeded."
        recommendation = "Cache or deduplicate identical tool calls." if redundant else "Continue monitoring."

    latest = events[-1]
    return {
        "task_id": task_id,
        "trace_id": latest.get("trace_id"),
        "agent_name": latest.get("agent_name"),
        "environment": latest.get("environment"),
        "status": status,
        "severity": _SEVERITY[status],
        "blocking_tool": blocking_tool,
        "consecutive_failures": consecutive,
        "failed_attempts": failed,
        "repeated_attempts": repeated,
        "redundant_attempts": redundant,
        "attempts": len(events),
        "wasted_tokens": round(wasted, 3),
        "total_tokens": round(total_tokens, 3),
        "tools": tools,
        "last_error_type": last_error_type,
        "last_error": last_error,
        "first_seen": _iso(min(times)) if times else None,
        "last_seen": _iso(max(times)) if times else None,
        "diagnosis": diagnosis,
        "recommendation": recommendation,
    }


def _sort_key(event: Mapping[str, Any]) -> tuple[datetime, int]:
    """Order events by timestamp, then by storage id for identical timestamps."""
    created = _as_datetime(event.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc)
    return created, int(event.get("id") or 0)


def analyze_agent_events(
    events: Iterable[Mapping[str, Any]], policy: Mapping[str, float] | None = None
) -> dict[str, Any]:
    """Summarize failed and repeated agent tool attempts across all tasks.

    ``events`` may arrive in any order. ``policy`` supplies
    ``blocked_after_failures`` and ``retry_window_minutes`` (defaults from
    :data:`driftguard.policy.DEFAULT_POLICY`).

    The top-level keys describe the most urgent task; ``tasks`` lists every task,
    most urgent first.
    """
    limits = {**DEFAULT_POLICY, **(policy or {})}
    blocked_after = max(1, int(limits["blocked_after_failures"]))
    window_seconds = max(0.0, float(limits["retry_window_minutes"]) * 60)

    by_task: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for event in events:
        by_task[str(event.get("task_id") or "unknown-task")].append(event)

    tasks = [
        _analyze_task(task_id, sorted(task_events, key=_sort_key), blocked_after, window_seconds)
        for task_id, task_events in by_task.items()
    ]
    tasks.sort(key=lambda t: (_STATUS_ORDER[t["status"]], _neg_time(t["last_seen"])))

    failure_count = sum(t["failed_attempts"] for t in tasks)
    wasted_tokens = round(sum(t["wasted_tokens"] for t in tasks), 3)
    blocked = [t for t in tasks if t["status"] == "blocked"]
    failing = [t for t in tasks if t["status"] == "failing"]
    top = tasks[0] if tasks and tasks[0]["status"] in {"blocked", "failing"} else None

    if top:
        diagnosis, recommendation = top["diagnosis"], top["recommendation"]
    elif failure_count:
        diagnosis = (
            f"{len(tasks)} task(s) recovered after tool failures; "
            f"{wasted_tokens:,.0f} tokens were spent on failed or redundant attempts."
        )
        recommendation = "Review recovered tasks to prevent repeat retry loops."
    else:
        diagnosis = "No failed agent tool attempts recorded."
        recommendation = "Continue monitoring task and tool events."

    return {
        "status": "critical" if blocked else "warning" if failing else "stable",
        "task_blocked": bool(blocked),
        "blocked_tasks": len(blocked),
        "failing_tasks": len(failing),
        "task_count": len(tasks),
        "failure_count": failure_count,
        "repeated_attempts": sum(t["repeated_attempts"] for t in tasks),
        "redundant_attempts": sum(t["redundant_attempts"] for t in tasks),
        "wasted_tokens": wasted_tokens,
        "blocking_tool": top["blocking_tool"] if top else None,
        "diagnosis": diagnosis,
        "recommendation": recommendation,
        "tasks": tasks,
    }


def _neg_time(value: str | None) -> float:
    """Sort helper: most recent ``last_seen`` first."""
    parsed = _as_datetime(value)
    return -parsed.timestamp() if parsed else 0.0
