import pytest
from helpers import make_project, register
from starlette.websockets import WebSocketDisconnect


def test_websocket_requires_credentials(client, project):
    pid = project["project_id"]
    for query in ("", "?token=garbage", "?api_key=dg_live_nope"):
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(f"/ws/projects/{pid}{query}") as ws:
                ws.receive_json()
        assert exc.value.code == 4401


def test_websocket_rejects_other_accounts(client, project):
    other = register(client)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/projects/{project['project_id']}?token={other['token']}") as ws:
            ws.receive_json()


def test_alerts_are_pushed_to_connected_clients(client, account):
    project = make_project(client, account)
    pid = project["project_id"]
    with client.websocket_connect(f"/ws/projects/{pid}?token={account['token']}") as ws:
        client.post(
            f"/projects/{pid}/alerts", json={"severity": "critical", "message": "live!"}, headers=account["headers"]
        )
        message = ws.receive_json()
    assert message["type"] == "alert"
    assert message["alert"]["message"] == "live!"


def test_agent_blocked_alert_is_pushed_via_api_key_socket(client, project):
    pid = project["project_id"]
    with client.websocket_connect(f"/ws/projects/{pid}?api_key={project['api_key']}") as ws:
        for _ in range(3):
            client.post(
                f"/agent-events/{pid}",
                json={"task_id": "t", "tool_name": "terminal", "status": "failed"},
                headers=project["key_headers"],
            )
        # Every ingest announces new activity; the third one also raises the alert.
        messages = [ws.receive_json() for _ in range(4)]
    assert [m["type"] for m in messages] == ["activity", "activity", "alert", "activity"]
    assert messages[0]["count"] == 1
    alert = messages[2]["alert"]
    assert alert["source"] == "agent"
    assert "terminal" in alert["message"]


def test_subprotocol_auth_keeps_credentials_out_of_the_url(client, account):
    project = make_project(client, account)
    pid = project["project_id"]
    with client.websocket_connect(f"/ws/projects/{pid}", subprotocols=["driftguard", account["token"]]) as ws:
        assert ws.accepted_subprotocol == "driftguard"
        client.post(
            f"/projects/{pid}/alerts",
            json={"severity": "warning", "message": "via subprotocol"},
            headers=account["headers"],
        )
        assert ws.receive_json()["alert"]["message"] == "via subprotocol"


def test_subprotocol_accepts_api_keys_and_rejects_bad_credentials(client, project):
    pid = project["project_id"]
    with client.websocket_connect(f"/ws/projects/{pid}", subprotocols=["driftguard", project["api_key"]]) as ws:
        assert ws.accepted_subprotocol == "driftguard"
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/projects/{pid}", subprotocols=["driftguard", "not-a-token"]) as ws:
            ws.receive_json()
    assert exc.value.code == 4401


def test_messages_carry_an_action(client, account):
    project = make_project(client, account)
    pid = project["project_id"]
    with client.websocket_connect(f"/ws/projects/{pid}", subprotocols=["driftguard", account["token"]]) as ws:
        alert = client.post(
            f"/projects/{pid}/alerts", json={"severity": "critical", "message": "x"}, headers=account["headers"]
        ).json()
        assert ws.receive_json()["action"] == "created"
        client.patch(f"/projects/{pid}/alerts/{alert['id']}", json={"resolved": True}, headers=account["headers"])
        assert ws.receive_json()["action"] == "resolved"
        client.patch(f"/projects/{pid}/alerts/{alert['id']}", json={"resolved": False}, headers=account["headers"])
        assert ws.receive_json()["action"] == "reopened"
