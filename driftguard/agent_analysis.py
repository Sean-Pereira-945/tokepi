"""Analysis helpers for failed, repeated, and token-wasting agent attempts."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _event_tokens(event: dict[str, Any]) -> float:
    """Calculate an event's token total, preferring an explicit total."""
    total_tokens = event.get("total_tokens")
    if total_tokens is not None:
        return float(total_tokens)
    return float(event.get("prompt_tokens", 0) or 0) + float(
        event.get("completion_tokens", 0) or 0
    )


def analyze_agent_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize failed and repeated agent-tool attempts for a project."""
    failures = [
        event
        for event in events
        if str(event.get("status", "")).lower() in {"failed", "error", "timeout"}
    ]
    failure_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in failures:
        group_key = (
            str(event.get("task_id", "unknown-task")),
            str(event.get("tool_name", "unknown-tool")),
            str(event.get("error_type", "unknown-error")),
        )
        failure_groups[group_key].append(event)

    wasted_tokens = sum(_event_tokens(event) for event in failures)
    repeated_attempts = sum(max(0, len(group) - 1) for group in failure_groups.values())
    tool_counts: dict[str, int] = defaultdict(int)
    for event in failures:
        tool_counts[str(event.get("tool_name", "unknown-tool"))] += 1

    if not failures:
        return {
            "status": "stable",
            "task_blocked": False,
            "failure_count": 0,
            "repeated_attempts": 0,
            "wasted_tokens": 0.0,
            "blocking_tool": None,
            "diagnosis": "No failed agent tool attempts recorded.",
            "recommendation": "Continue monitoring task and tool events.",
        }

    blocking_tool = max(tool_counts, key=tool_counts.get)
    latest_failure = failures[0]
    error_message = str(latest_failure.get("error_message", "tool execution failed"))
    task_blocked = repeated_attempts > 0 or len(failures) >= 3
    severity = "critical" if task_blocked else "warning"
    diagnosis = (
        f"The {blocking_tool} tool failed {tool_counts[blocking_tool]} time(s). "
        f"Latest error: {error_message}"
    )
    recommendation = (
        f"Stop repeating {blocking_tool}, inspect the first failing result, and fix the tool or input."
    )

    return {
        "status": severity,
        "task_blocked": task_blocked,
        "failure_count": len(failures),
        "repeated_attempts": repeated_attempts,
        "wasted_tokens": round(wasted_tokens, 3),
        "blocking_tool": blocking_tool,
        "diagnosis": diagnosis,
        "recommendation": recommendation,
    }
