from unittest.mock import MagicMock, patch

import httpx
import pytest

from driftguard.client import BATCH_SIZE, DriftGuardClient
from driftguard.policy import DEFAULT_POLICY


def make_client(**kwargs):
    return DriftGuardClient(api_key="dg_live_test", project_name="app", base_url="http://dg.test", **kwargs)


def mock_http(post=None, get=None):
    patcher = patch("httpx.Client")
    mocked = patcher.start()
    http = mocked.return_value.__enter__.return_value
    if post is not None:
        http.post.side_effect = post
    if get is not None:
        http.get.return_value = get
    return patcher, http


def ok_response(json_body=None):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = json_body
    return response


def test_capture_metrics_records_environment_and_timestamp():
    client = DriftGuardClient(api_key="k", project_name="my-app", environment="staging")
    payload = client.capture_metrics(prompt_tokens=500.0)
    assert payload["environment"] == "staging"
    assert payload["occurred_at"].endswith("Z")
    assert "project" not in payload
    assert len(client.metrics) == 1


def test_check_drift_without_metrics_is_stable():
    assert DriftGuardClient(api_key="k").check_drift()["severity"] == "stable"


def test_check_drift_is_policy_aware():
    client = make_client()
    client.capture_metrics(prompt_tokens=1200, context_length=1500, retrieval_score=0.95, response_quality=0.95)
    assert client.check_drift()["severity"] == "stable"
    with patch.object(client, "_get", return_value={"prompt_token_limit": 500, "context_length_limit": 1000}):
        policy = client.fetch_policy("p1")
    assert policy["prompt_token_limit"] == 500
    assert policy["retrieval_score_floor"] == DEFAULT_POLICY["retrieval_score_floor"]
    result = client.check_drift()
    assert result["severity"] == "warning"
    assert "compress_prompt_context" in result["actions"]


def test_sync_requires_base_url_and_project():
    client = DriftGuardClient(api_key="k")
    client.capture_metrics(prompt_tokens=1)
    with pytest.raises(RuntimeError, match="base_url"):
        client.sync_metrics("p1")
    with pytest.raises(ValueError, match="project_id"):
        make_client().sync_metrics()


def test_sync_empty_queue_is_skipped():
    assert make_client().sync_metrics("p1") == {"synced": 0, "skipped": True}


def test_sync_sends_batches_with_api_key_and_clears_queue():
    client = make_client(project_id="p1")
    for i in range(BATCH_SIZE + 5):
        client.capture_metrics(prompt_tokens=i)
    patcher, http = mock_http(post=lambda *a, **k: ok_response())
    try:
        result = client.sync_metrics()
    finally:
        patcher.stop()
    assert result == {"synced": BATCH_SIZE + 5, "errors": []}
    assert http.post.call_count == 2
    url = http.post.call_args_list[0].args[0]
    assert url == "http://dg.test/events/p1/batch"
    assert http.post.call_args_list[0].kwargs["headers"] == {"X-API-Key": "dg_live_test"}
    assert len(http.post.call_args_list[0].kwargs["json"]["events"]) == BATCH_SIZE
    assert client.metrics == []


def test_failed_batches_stay_queued_in_order():
    client = make_client(project_id="p1")
    for i in range(BATCH_SIZE + 2):
        client.capture_metrics(prompt_tokens=i)

    def post(url, json, headers):
        if json["events"][0]["prompt_tokens"] == 0:
            raise httpx.ConnectError("down")
        return ok_response()

    patcher, _ = mock_http(post=post)
    try:
        result = client.sync_metrics()
    finally:
        patcher.stop()
    assert result["synced"] == 2
    assert len(result["errors"]) == 1
    assert [m["prompt_tokens"] for m in client.metrics] == list(range(BATCH_SIZE))


def test_sync_agent_events_uses_agent_endpoint():
    client = make_client()
    event = client.capture_agent_event(task_id="t", tool_name="terminal", status="failed")
    assert event["agent_name"] == "app"
    patcher, http = mock_http(post=lambda *a, **k: ok_response())
    try:
        assert client.sync_agent_events("p1")["synced"] == 1
    finally:
        patcher.stop()
    assert http.post.call_args.args[0] == "http://dg.test/agent-events/p1/batch"
    assert client.agent_events == []


def test_queue_is_bounded():
    client = DriftGuardClient(api_key="k", max_queue=3)
    for i in range(5):
        client.capture_metrics(prompt_tokens=i)
    assert [m["prompt_tokens"] for m in client.metrics] == [2, 3, 4]


def test_fetch_agent_diagnosis_uses_api_key():
    client = make_client()
    patcher, http = mock_http(get=ok_response({"status": "stable"}))
    try:
        assert client.fetch_agent_diagnosis("p1") == {"status": "stable"}
    finally:
        patcher.stop()
    assert http.get.call_args.args[0] == "http://dg.test/projects/p1/agent-diagnosis"


def test_sdk_import_does_not_pull_in_server_dependencies():
    import subprocess
    import sys

    code = (
        "import sys, driftguard, driftguard.adapters; "
        "bad = [m for m in ('fastapi', 'sqlalchemy', 'jwt', 'numpy') if m in sys.modules]; "
        "print(bad); sys.exit(1 if bad else 0)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
