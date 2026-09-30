"""Multi-worker behaviour through Redis. Opt in with ``DRIFTGUARD_TEST_REDIS_URL``."""

import os
import uuid
from dataclasses import replace

import pytest

REDIS_URL = os.getenv("DRIFTGUARD_TEST_REDIS_URL")
pytestmark = pytest.mark.skipif(not REDIS_URL, reason="set DRIFTGUARD_TEST_REDIS_URL to run Redis tests")


def test_rate_limit_is_shared_between_workers():
    from driftguard.server.ratelimit import RedisRateLimiter

    key = f"test-{uuid.uuid4().hex}"
    worker_a, worker_b = RedisRateLimiter(REDIS_URL), RedisRateLimiter(REDIS_URL)
    results = [worker_a.allow(key, 3), worker_b.allow(key, 3), worker_a.allow(key, 3), worker_b.allow(key, 3)]
    assert results == [True, True, True, False]


def test_alerts_fan_out_to_clients_on_other_workers(settings, tmp_path):
    from fastapi.testclient import TestClient
    from helpers import make_project, register

    from driftguard.server import create_app

    shared = replace(settings, database_url=f"sqlite:///{tmp_path / 'shared.db'}", redis_url=REDIS_URL)
    with TestClient(create_app(shared)) as worker_a, TestClient(create_app(shared)) as worker_b:
        account = register(worker_a)
        project = make_project(worker_a, account)
        pid = project["project_id"]
        with worker_b.websocket_connect(f"/ws/projects/{pid}?token={account['token']}") as ws:
            worker_a.post(
                f"/projects/{pid}/alerts",
                json={"severity": "critical", "message": "from worker A"},
                headers=account["headers"],
            )
            message = ws.receive_json()
    assert message["alert"]["message"] == "from worker A"
