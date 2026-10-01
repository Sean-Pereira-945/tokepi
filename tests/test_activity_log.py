"""Activity log: event kinds, opt-in content capture, filters, paging, and export."""

from __future__ import annotations

import csv
import io

from tests.helpers import make_project, register


def post_batch(client, project, events):
    response = client.post(
        f"/agent-events/{project['project_id']}/batch", json={"events": events}, headers=project["key_headers"]
    )
    assert response.status_code == 200, response.text
    return response.json()


def list_activity(client, project, **params):
    response = client.get(
        f"/projects/{project['project_id']}/agent-events", params=params, headers=project["key_headers"]
    )
    assert response.status_code == 200, response.text
    return response.json()


def enable_capture(client, account, project, enabled=True):
    response = client.patch(
        f"/projects/{project['project_id']}", json={"capture_content": enabled}, headers=account["headers"]
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_projects_default_to_no_content_capture(client, project):
    assert project["capture_content"] is False
    post_batch(
        client,
        project,
        [{"task_id": "t", "tool_name": "terminal", "status": "success", "input": "ls -la", "output": "total 0"}],
    )
    [event] = list_activity(client, project)
    assert event["input"] is None and event["output"] is None
    assert event["kind"] == "tool_call"


def test_content_is_stored_scrubbed_and_truncated_once_enabled(client, account, project):
    assert enable_capture(client, account, project)["capture_content"] is True
    post_batch(
        client,
        project,
        [
            {
                "task_id": "t",
                "tool_name": "terminal",
                "status": "success",
                "input": "export OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz123456",
                "output": "x" * 5000,
            }
        ],
    )
    [event] = list_activity(client, project)
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in event["input"]
    assert "REDACTED" in event["input"]
    assert event["output"].endswith("…[truncated]")
    assert len(event["output"]) < 2100


def test_only_the_owner_can_change_project_settings(client, account, project):
    pid = project["project_id"]
    assert client.patch(
        f"/projects/{pid}", json={"capture_content": True}, headers=project["key_headers"]
    ).status_code in {
        401,
        403,
    }
    stranger = register(client)
    assert (
        client.patch(f"/projects/{pid}", json={"capture_content": True}, headers=stranger["headers"]).status_code == 404
    )
    assert client.patch(f"/projects/{pid}", json={"unknown": 1}, headers=account["headers"]).status_code == 422
    renamed = client.patch(f"/projects/{pid}", json={"name": "Renamed"}, headers=account["headers"]).json()
    assert renamed["name"] == "Renamed" and renamed["capture_content"] is False


def test_non_tool_activity_is_logged_but_ignored_by_diagnosis(client, project):
    post_batch(
        client,
        project,
        [
            {"task_id": "t", "kind": "prompt", "input": "fix the tests"},
            {"task_id": "t", "kind": "session_start"},
            {"task_id": "t", "tool_name": "terminal", "status": "failed"},
        ],
    )
    kinds = [e["kind"] for e in list_activity(client, project)]
    assert sorted(kinds) == ["prompt", "session_start", "tool_call"]
    prompt = list_activity(client, project, kind="prompt")[0]
    assert prompt["tool_name"] == "" and prompt["status"] == "info"

    diagnosis = client.get(f"/projects/{project['project_id']}/agent-diagnosis", headers=project["key_headers"]).json()
    assert diagnosis["task_count"] == 1
    assert diagnosis["tasks"][0]["failed_attempts"] == 1


def test_tool_calls_still_require_tool_name_and_status(client, project):
    response = client.post(
        f"/agent-events/{project['project_id']}", json={"task_id": "t"}, headers=project["key_headers"]
    )
    assert response.status_code == 422
    assert "tool_name and status are required" in response.text


def test_filters_search_and_paging(client, account, project):
    enable_capture(client, account, project)
    post_batch(
        client,
        project,
        [
            {
                "task_id": "a",
                "tool_name": "terminal",
                "status": "failed",
                "agent_name": "coder",
                "error_message": "Exit 1",
            },
            {"task_id": "a", "tool_name": "terminal", "status": "success", "agent_name": "coder"},
            {"task_id": "b", "tool_name": "editor", "status": "ok", "agent_name": "writer", "input": "README_50%_done"},
            {"task_id": "b", "kind": "llm_call", "model": "gpt-x", "status": "success"},
        ],
    )
    assert [e["status"] for e in list_activity(client, project, outcome="failed")] == ["failed"]
    assert len(list_activity(client, project, outcome="success")) == 3
    assert {e["task_id"] for e in list_activity(client, project, tool_name="terminal")} == {"a"}
    assert len(list_activity(client, project, agent_name="writer")) == 1
    assert len(list_activity(client, project, q="exit 1")) == 1  # case-insensitive error search
    assert len(list_activity(client, project, q="50%_")) == 1  # wildcards are matched literally
    assert len(list_activity(client, project, q="GPT-X")) == 1
    assert list_activity(client, project, q="   ") == list_activity(client, project)

    first_page = list_activity(client, project, limit=3)
    rest = list_activity(client, project, limit=3, before_id=first_page[-1]["id"])
    assert len(first_page) == 3 and len(rest) == 1
    assert rest[0]["id"] < first_page[-1]["id"]


def test_export_csv_and_json_use_the_same_filters(client, account, project):
    enable_capture(client, account, project)
    post_batch(
        client,
        project,
        [
            {"task_id": "a", "tool_name": "terminal", "status": "failed", "input": "pytest, -q"},
            {"task_id": "b", "tool_name": "editor", "status": "success"},
        ],
    )
    pid = project["project_id"]
    response = client.get(f"/projects/{pid}/agent-events/export?outcome=failed", headers=account["headers"])
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert f"driftguard-{pid}-activity.csv" in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 1
    assert rows[0]["task_id"] == "a" and rows[0]["input"] == "pytest, -q"

    data = client.get(f"/projects/{pid}/agent-events/export?format=json", headers=account["headers"]).json()
    assert {row["task_id"] for row in data} == {"a", "b"}


def test_other_accounts_cannot_read_or_export_activity(client, project):
    stranger = register(client)
    pid = project["project_id"]
    assert client.get(f"/projects/{pid}/agent-events", headers=stranger["headers"]).status_code == 404
    assert client.get(f"/projects/{pid}/agent-events/export", headers=stranger["headers"]).status_code == 404
    other = make_project(client, stranger)
    assert client.get(f"/projects/{pid}/agent-events/export", headers=other["key_headers"]).status_code in {401, 403}


def test_summary_totals_agent_activity_from_the_same_rows(client, account, project):
    post_batch(
        client,
        project,
        [
            {"task_id": "a", "tool_name": "Bash", "status": "failed", "total_tokens": 100, "duration_ms": 1000},
            {"task_id": "a", "tool_name": "Bash", "status": "success", "total_tokens": 50, "duration_ms": 3000},
            # Task a finished: its response holds the whole turn's tokens (more than its tool calls).
            {"task_id": "a", "kind": "response", "status": "success", "total_tokens": 400, "duration_ms": 9000},
            # Task b is still running: only its tool calls count.
            {"task_id": "b", "tool_name": "Read", "status": "success", "total_tokens": 70, "duration_ms": 500},
        ],
    )
    summary = client.get(f"/projects/{project['project_id']}/summary", headers=account["headers"]).json()
    activity = summary["agent_activity"]
    assert activity["events"] == 4 and activity["tool_calls"] == 3 and activity["failed_tool_calls"] == 1
    assert activity["failure_rate"] == round(1 / 3, 4)
    assert (activity["tasks"], activity["turns"]) == (2, 1)
    assert activity["total_tokens"] == 400 + 70
    assert activity["avg_tool_duration_ms"] == 1500.0
    assert summary["last_updated"] == activity["last_activity"]


def test_summary_agent_activity_is_empty_without_agent_events(client, account, project):
    activity = client.get(f"/projects/{project['project_id']}/summary", headers=account["headers"]).json()[
        "agent_activity"
    ]
    assert activity["events"] == 0 and activity["failure_rate"] is None and activity["avg_tool_duration_ms"] is None
