from datetime import datetime, timedelta, timezone

from driftguard.agent_analysis import analyze_agent_events

T0 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def ev(i, status, tool="terminal", task="fix-tests", minutes=None, tokens=1000, **extra):
    return {
        "id": i,
        "task_id": task,
        "tool_name": tool,
        "status": status,
        "total_tokens": tokens,
        "created_at": (T0 + timedelta(minutes=i if minutes is None else minutes)).isoformat(),
        **extra,
    }


def test_no_events_is_stable():
    result = analyze_agent_events([])
    assert result["status"] == "stable"
    assert result["tasks"] == []
    assert result["blocking_tool"] is None


def test_three_consecutive_failures_block_the_task():
    events = [
        ev(i, "failed", error_type="command_failed", error_message="pytest exited 1", tokens=2200) for i in range(1, 4)
    ]
    result = analyze_agent_events(events)
    assert result["status"] == "critical"
    assert result["task_blocked"] is True
    assert result["blocking_tool"] == "terminal"
    assert result["failure_count"] == 3
    assert result["repeated_attempts"] == 2
    assert result["wasted_tokens"] == 6600
    task = result["tasks"][0]
    assert task["status"] == "blocked"
    assert task["consecutive_failures"] == 3
    assert "terminal" in result["diagnosis"] and "pytest exited 1" in result["diagnosis"]


def test_fewer_failures_than_threshold_is_failing():
    result = analyze_agent_events([ev(1, "failed"), ev(2, "failed")])
    assert result["status"] == "warning"
    assert result["tasks"][0]["status"] == "failing"


def test_success_of_same_tool_means_recovered():
    events = [ev(1, "failed"), ev(2, "failed"), ev(3, "failed"), ev(4, "success")]
    result = analyze_agent_events(events)
    assert result["status"] == "stable"
    assert result["task_blocked"] is False
    assert result["tasks"][0]["status"] == "recovered"
    assert result["wasted_tokens"] == 3000  # the three failures


def test_success_of_other_tool_does_not_recover():
    events = [ev(1, "failed"), ev(2, "failed"), ev(3, "success", tool="editor"), ev(4, "failed")]
    task = analyze_agent_events(events)["tasks"][0]
    assert task["status"] == "blocked"
    assert task["blocking_tool"] == "terminal"


def test_events_are_replayed_in_time_order_regardless_of_input_order():
    events = [ev(4, "success"), ev(2, "failed"), ev(1, "failed"), ev(3, "failed")]
    assert analyze_agent_events(events)["tasks"][0]["status"] == "recovered"


def test_retry_window_breaks_failure_chains():
    events = [ev(1, "failed", minutes=0), ev(2, "failed", minutes=90), ev(3, "failed", minutes=180)]
    assert analyze_agent_events(events)["tasks"][0]["status"] == "failing"
    # Disabling the window (0) chains them again.
    assert analyze_agent_events(events, {"retry_window_minutes": 0})["tasks"][0]["status"] == "blocked"


def test_blocked_threshold_is_configurable():
    events = [ev(1, "failed"), ev(2, "failed")]
    assert analyze_agent_events(events, {"blocked_after_failures": 2})["status"] == "critical"


def test_redundant_successes_count_as_waste():
    events = [
        ev(1, "success", input_hash="abc"),
        ev(2, "success", input_hash="abc"),
        ev(3, "success", input_hash="xyz"),
    ]
    result = analyze_agent_events(events)
    assert result["redundant_attempts"] == 1
    assert result["wasted_tokens"] == 1000
    assert result["status"] == "stable"


def test_tasks_are_ordered_by_urgency():
    events = [
        ev(1, "success", task="ok-task"),
        ev(2, "failed", task="bad-task"),
        ev(3, "failed", task="bad-task"),
        ev(4, "failed", task="bad-task"),
        ev(5, "failed", task="meh-task"),
    ]
    result = analyze_agent_events(events)
    assert [t["task_id"] for t in result["tasks"]] == ["bad-task", "meh-task", "ok-task"]
    assert result["blocked_tasks"] == 1 and result["failing_tasks"] == 1


def test_recommendation_uses_error_signature():
    events = [ev(i, "timeout", tool="browser", error_type="TimeoutError") for i in range(1, 4)]
    assert "timing out" in analyze_agent_events(events)["recommendation"]


def test_token_fallback_to_prompt_plus_completion():
    event = ev(1, "failed", tokens=None)
    event.pop("total_tokens")
    event.update(prompt_tokens=300, completion_tokens=200)
    assert analyze_agent_events([event])["wasted_tokens"] == 500
