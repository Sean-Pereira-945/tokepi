"""The Claude Code hook integration: payload mapping, transcript reading, and delivery."""

from __future__ import annotations

import importlib.util
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parents[1] / "integrations" / "claude_code" / "driftguard_hook.py"
spec = importlib.util.spec_from_file_location("driftguard_hook", HOOK_PATH)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def run(payload, state, capture=False, **kwargs):
    return hook.build_events({"session_id": "abcdef1234567890", **payload}, state, capture, **kwargs)


def iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


def write_transcript(path, entries):
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def assistant(request_id, timestamp, usage, blocks, model="claude-opus-5-5"):
    return {
        "type": "assistant",
        "timestamp": timestamp,
        "requestId": request_id,
        "message": {"model": model, "usage": usage, "content": blocks},
    }


USAGE = {
    "input_tokens": 12,
    "cache_creation_input_tokens": 3000,
    "cache_read_input_tokens": 450000,
    "output_tokens": 800,
}


def test_a_prompt_starts_a_task_and_its_tools_belong_to_it():
    state = {}
    assert run({"hook_event_name": "SessionStart", "model": "claude-opus"}, state) == []  # session events are off
    assert state["model"] == "claude-opus"
    assert run({"hook_event_name": "UserPromptSubmit", "prompt": "fix the tests"}, state) == []
    assert state["task_id"] == "abcdef12-p1" and state["prompt"] == "fix the tests"

    [tool] = run(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_use_id": "t1",
            "tool_response": {"stdout": "a.py\nb.py", "stderr": ""},
        },
        state,
    )
    assert (tool["task_id"], tool["tool_name"], tool["status"], tool["attempt"]) == (
        "abcdef12-p1",
        "Bash",
        "success",
        1,
    )
    assert tool["tool_call_id"] == "t1" and tool["agent_name"] == "claude-code" and tool["model"] == "claude-opus"
    assert "kind" not in tool  # tool calls use the server default

    run({"hook_event_name": "UserPromptSubmit", "prompt": "next"}, state)
    [tool] = run({"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}}, state)
    assert tool["task_id"] == "abcdef12-p2" and tool["attempt"] == 1  # attempts restart with each task


def test_session_events_can_be_turned_on():
    state = {}
    [start] = run({"hook_event_name": "SessionStart"}, state, session_events=True)
    [end] = run({"hook_event_name": "SessionEnd"}, state, session_events=True)
    assert (start["kind"], end["kind"]) == ("session_start", "session_end")
    assert run({"hook_event_name": "SessionEnd"}, state) == []


def test_failures_carry_the_error_and_count_attempts():
    state = {}
    run({"hook_event_name": "UserPromptSubmit", "prompt": "x"}, state)
    for attempt in (1, 2, 3):
        [event] = run(
            {
                "hook_event_name": "PostToolUseFailure",
                "tool_name": "Bash",
                "tool_input": {"command": "pytest"},
                "error": "Exit code 1: 2 failed",
            },
            state,
            capture=True,
        )
        assert event["status"] == "failed" and event["attempt"] == attempt
    assert event["error_type"] == "tool_error" and event["error_message"] == "Exit code 1: 2 failed"
    assert event["output"] == "Exit code 1: 2 failed"
    [interrupted] = run(
        {"hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "tool_input": {}, "is_interrupt": True}, state
    )
    assert interrupted["error_type"] == "interrupted" and interrupted["error_message"] == "Tool call failed"


def test_error_responses_reported_as_post_tool_use_count_as_failures():
    [event] = run(
        {"hook_event_name": "PostToolUse", "tool_name": "mcp__x", "tool_response": {"isError": True, "error": "boom"}},
        {},
    )
    assert event["status"] == "failed" and event["error_message"] == "boom"


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({"stdout": "12 passed", "stderr": ""}, "12 passed"),
        ({"type": "text", "file": {"filePath": "a.py", "content": "print(1)"}}, "print(1)"),
        ({"filePath": "a.py", "structuredPatch": []}, "updated a.py"),
        ("plain text", "plain text"),
    ],
)
def test_tool_output_prefers_the_readable_part(response, expected):
    assert hook.tool_output(response) == expected


def test_content_is_sent_only_when_configured():
    state = {}
    run({"hook_event_name": "UserPromptSubmit", "prompt": "fix it"}, state)
    [tool] = run(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "Read",
            "tool_input": {"file_path": "a.py"},
            "tool_response": {"file": {"content": "x" * 5000}},
        },
        state,
        capture=True,
    )
    assert tool["input"] == '{"file_path": "a.py"}'
    assert tool["output"].endswith("…[truncated]")
    [quiet] = run({"hook_event_name": "PostToolUse", "tool_name": "Read", "tool_input": {}}, state)
    assert "input" not in quiet and "output" not in quiet


def test_the_turn_is_reported_complete_when_claude_stops(tmp_path):
    started = datetime.now(timezone.utc) - timedelta(seconds=30)
    small = {"input_tokens": 100, "output_tokens": 50}
    transcript = tmp_path / "session.jsonl"
    write_transcript(
        transcript,
        [
            assistant("req_old", iso(started - timedelta(minutes=5)), USAGE, [{"type": "text", "text": "old turn"}]),
            {"type": "user", "timestamp": iso(started), "message": {"content": "add a test"}},
            assistant("req_1", iso(started + timedelta(seconds=2)), USAGE, [{"type": "tool_use", "id": "t1"}]),
            assistant("req_2", iso(started + timedelta(seconds=9)), small, []),
            assistant("req_2", iso(started + timedelta(seconds=9)), small, [{"type": "text", "text": "Added it."}]),
        ],
    )
    state = {"task_id": "abcdef12-p1", "prompt": "add a test", "turn_started": iso(started)}
    turn = hook.turn_summary(transcript, started)
    assert turn["model_calls"] == 2  # duplicated entries of one model call count once; the old turn is excluded
    assert (turn["prompt_tokens"], turn["completion_tokens"]) == (3012 + 100, 800 + 50)
    assert turn["last_text"] == "Added it."

    [event] = run({"hook_event_name": "Stop", "last_assistant_message": "Added it."}, state, capture=True, turn=turn)
    assert (event["kind"], event["status"], event["task_id"]) == ("response", "success", "abcdef12-p1")
    assert (event["input"], event["output"], event["model"]) == ("add a test", "Added it.", "claude-opus-5-5")
    assert event["total_tokens"] == 3962
    assert 29_000 <= event["duration_ms"] <= 60_000
    assert "prompt" not in state and "turn_started" not in state


def test_turn_falls_back_to_the_transcript_for_the_prompt(tmp_path):
    started = datetime.now(timezone.utc) - timedelta(seconds=5)
    transcript = tmp_path / "session.jsonl"
    write_transcript(
        transcript,
        [
            {"type": "user", "timestamp": iso(started), "message": {"content": "hooks were added mid-turn"}},
            assistant("req_1", iso(started + timedelta(seconds=1)), USAGE, [{"type": "text", "text": "ok"}]),
        ],
    )
    turn = hook.turn_summary(transcript, None)
    assert turn["prompt"] == "hooks were added mid-turn" and turn["started_at"] == started
    [event] = run({"hook_event_name": "Stop"}, {}, capture=True, turn=turn)
    assert event["input"] == "hooks were added mid-turn" and event["output"] == "ok"
    assert event["duration_ms"] >= 4000
    assert hook.turn_summary(tmp_path / "missing.jsonl", None) == {}


def test_tool_duration_tokens_and_model_come_from_the_transcript(tmp_path):
    transcript = tmp_path / "session.jsonl"
    write_transcript(
        transcript,
        [
            {"type": "user", "message": {"content": "hi"}},
            assistant("req_1", "2026-10-01T06:00:00.000Z", USAGE, [{"type": "tool_use", "id": "toolu_a"}]),
            assistant("req_1", "2026-10-01T06:00:00.500Z", USAGE, [{"type": "tool_use", "id": "toolu_b"}]),
        ],
    )
    now = datetime(2026, 10, 1, 6, 0, 2, 250000, tzinfo=timezone.utc)
    details = hook.transcript_details(transcript, "toolu_a", now=now)
    assert details["duration_ms"] == 2250.0
    assert details["model"] == "claude-opus-5-5" and details["request_id"] == "req_1"
    # Cached context re-reads are left out: new input (12 + 3000) plus output.
    assert details["usage"] == {"prompt_tokens": 3012, "completion_tokens": 800}
    assert hook.transcript_details(transcript, "toolu_missing") == {}
    assert hook.transcript_details(tmp_path / "nope.jsonl", "toolu_a") == {}

    state = {}
    payload = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {}}
    [first] = run(payload, state, details=details)
    assert (first["total_tokens"], first["duration_ms"], first["model"]) == (3812, 2250.0, "claude-opus-5-5")
    # A second tool call from the same model call: its tokens were already counted, so 0.
    [second] = run(payload, state, details=hook.transcript_details(transcript, "toolu_b", now=now))
    assert (second["prompt_tokens"], second["completion_tokens"], second["total_tokens"]) == (0, 0, 0)
    assert second["duration_ms"] == 1750.0


def test_unknown_events_send_nothing():
    assert run({"hook_event_name": "Notification"}, {}) == []


def test_hook_delivers_events_to_a_real_server(client, account, project, tmp_path, monkeypatch):
    """Run main() end to end, posting through the test server."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    config = {"base_url": "http://testserver", "project_id": project["project_id"], "api_key": project["api_key"]}
    (claude_dir / "driftguard.json").write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    def fake_send(cfg, events, path="agent-events"):
        response = client.post(
            f"/{path}/{cfg['project_id']}/batch", json={"events": events}, headers={"X-API-Key": cfg["api_key"]}
        )
        assert response.status_code == 200, response.text

    monkeypatch.setattr(hook, "send", fake_send)

    def fire(payload):
        stdin = io.TextIOWrapper(io.BytesIO(json.dumps({"session_id": "sess-1", **payload}).encode()))
        monkeypatch.setattr("sys.stdin", stdin)
        hook.main()

    fire({"hook_event_name": "UserPromptSubmit", "prompt": "run the tests"})
    for _ in range(3):
        fire({"hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "tool_input": {"command": "pytest"}})
    fire({"hook_event_name": "Stop", "last_assistant_message": "The tests keep failing."})

    pid = project["project_id"]
    diagnosis = client.get(f"/projects/{pid}/agent-diagnosis", headers=account["headers"]).json()
    assert diagnosis["blocked_tasks"] == 1 and diagnosis["blocking_tool"] == "Bash"
    events = client.get(f"/projects/{pid}/agent-events", headers=account["headers"]).json()
    assert [e["kind"] for e in events] == ["response", "tool_call", "tool_call", "tool_call"]
    assert events[0]["status"] == "success" and events[0]["duration_ms"] is not None
    assert json.loads((claude_dir / "driftguard-state" / "sess-1.json").read_text())["task_id"] == "sess-1-p1"


def test_hook_is_silent_without_config_or_server(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b'{"hook_event_name": "Stop"}')))
    hook.main()  # no .claude/driftguard.json: nothing happens
    assert not (tmp_path / ".claude").exists()

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "driftguard.json").write_text(
        json.dumps({"base_url": "http://127.0.0.1:9", "project_id": "p", "api_key": "k"}), encoding="utf-8"
    )
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b'{"hook_event_name": "Stop"}')))
    hook.main()  # unreachable server: logged, not raised
    assert "unreachable" in (claude_dir / "driftguard-hook.log").read_text(encoding="utf-8")


@pytest.mark.parametrize("bad_stdin", [b"", b"not json"])
def test_hook_ignores_bad_input(bad_stdin, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(bad_stdin)))
    hook.main()


def test_turn_fallback_skips_injected_messages_and_stale_starts(tmp_path):
    now = datetime.now(timezone.utc)
    transcript = tmp_path / "session.jsonl"
    write_transcript(
        transcript,
        [
            {"type": "user", "timestamp": iso(now - timedelta(seconds=20)), "message": {"content": "real prompt"}},
            assistant("req_1", iso(now - timedelta(seconds=15)), USAGE, [{"type": "text", "text": "ok"}]),
            {
                "type": "user",
                "timestamp": iso(now - timedelta(seconds=10)),
                "message": {"content": "<task-notification>x"},
            },
            {
                "type": "user",
                "timestamp": iso(now - timedelta(seconds=9)),
                "isMeta": True,
                "message": {"content": "meta"},
            },
        ],
    )
    turn = hook.turn_summary(transcript, None)
    assert turn["prompt"] == "real prompt" and turn["model_calls"] == 1

    stale = tmp_path / "stale.jsonl"
    write_transcript(
        stale, [{"type": "user", "timestamp": iso(now - timedelta(hours=8)), "message": {"content": "old"}}]
    )
    assert hook.turn_summary(stale, None) == {}


def test_each_model_call_in_a_turn_becomes_llm_telemetry(tmp_path, client, project):
    started = datetime.now(timezone.utc) - timedelta(seconds=30)
    transcript = tmp_path / "session.jsonl"
    write_transcript(
        transcript,
        [
            {"type": "user", "timestamp": iso(started), "message": {"content": "go"}},
            assistant("req_1", iso(started + timedelta(seconds=2)), USAGE, [{"type": "tool_use", "id": "t1"}]),
            assistant("req_2", iso(started + timedelta(seconds=9)), {"input_tokens": 100, "output_tokens": 50}, []),
        ],
    )
    events = hook.telemetry_events(hook.turn_summary(transcript, started), "sess-p1")
    assert [(e["prompt_tokens"], e["context_length"]) for e in events] == [(3012, 453012), (100, 100)]
    assert events[0]["metadata"] == {
        "source": "claude-code",
        "task_id": "sess-p1",
        "request_id": "req_1",
        "model": "claude-opus-5-5",
    }
    assert "retrieval_score" not in events[0] and "response_quality" not in events[0]
    response = client.post(
        f"/events/{project['project_id']}/batch", json={"events": events}, headers=project["key_headers"]
    )
    assert response.status_code == 200 and response.json()["ingested"] == 2
