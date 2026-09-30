from helpers import make_project, register


def test_create_project_returns_key_once(client, account):
    project = make_project(client, account, project_id="shop-bot")
    assert project["api_key"].startswith("dg_live_")
    assert project["api_key_hint"] == project["api_key"][:12]
    fetched = client.get("/projects/shop-bot", headers=account["headers"]).json()
    assert "api_key" not in fetched
    assert fetched["api_key_hint"] == project["api_key_hint"]


def test_project_ids_cannot_be_taken_over(client, account):
    """v0.3 used INSERT OR REPLACE, letting anyone overwrite another account's project."""
    make_project(client, account, project_id="owned")
    attacker = register(client)
    response = client.post("/projects", json={"project_id": "owned", "name": "mine now"}, headers=attacker["headers"])
    assert response.status_code == 409
    assert client.get("/projects/owned", headers=account["headers"]).json()["name"] == "Project owned"


def test_projects_are_isolated_between_accounts(client, account):
    make_project(client, account, project_id="a-proj")
    other = register(client)
    assert [p["project_id"] for p in client.get("/projects", headers=account["headers"]).json()] == ["a-proj"]
    assert client.get("/projects", headers=other["headers"]).json() == []
    for path in (
        "/projects/a-proj",
        "/projects/a-proj/summary",
        "/projects/a-proj/events",
        "/projects/a-proj/alerts",
        "/projects/a-proj/policy",
        "/projects/a-proj/agent-diagnosis",
    ):
        assert client.get(path, headers=other["headers"]).status_code == 404, path
    assert client.delete("/projects/a-proj", headers=other["headers"]).status_code == 404


def test_project_validation(client, account):
    h = account["headers"]
    assert client.post("/projects", json={"project_id": "bad id!", "name": "x"}, headers=h).status_code == 422
    assert (
        client.post(
            "/projects", json={"project_id": "ok", "name": "x", "environment": "production"}, headers=h
        ).status_code
        == 422
    )
    assert client.post("/projects", json={"project_id": "ok", "name": "  "}, headers=h).status_code == 422


def test_api_key_scopes_reads_to_its_project(client, account):
    a = make_project(client, account)
    b = make_project(client, account)
    assert client.get(f"/projects/{a['project_id']}/events", headers=a["key_headers"]).status_code == 200
    assert client.get(f"/projects/{b['project_id']}/events", headers=a["key_headers"]).status_code == 403
    listed = client.get("/projects", headers=a["key_headers"]).json()
    assert [p["project_id"] for p in listed] == [a["project_id"]]
    assert client.get("/projects", headers={"X-API-Key": "dg_live_nope"}).status_code == 401


def test_api_key_cannot_manage_the_project(client, project):
    pid = project["project_id"]
    assert (
        client.put(
            f"/projects/{pid}/policy", json={"prompt_token_limit": 1}, headers=project["key_headers"]
        ).status_code
        == 401
    )
    assert client.delete(f"/projects/{pid}", headers=project["key_headers"]).status_code == 401
    assert client.post(f"/projects/{pid}/api-key", headers=project["key_headers"]).status_code == 401


def test_rotate_api_key_invalidates_old_key(client, account, project):
    pid = project["project_id"]
    rotated = client.post(f"/projects/{pid}/api-key", headers=account["headers"]).json()
    assert rotated["api_key"] != project["api_key"]
    old = client.post(f"/events/{pid}", json={"prompt_tokens": 1}, headers=project["key_headers"])
    new = client.post(f"/events/{pid}", json={"prompt_tokens": 1}, headers={"X-API-Key": rotated["api_key"]})
    assert old.status_code == 401
    assert new.status_code == 200


def test_delete_project_removes_all_data(client, account, project):
    pid = project["project_id"]
    client.post(f"/events/{pid}", json={"prompt_tokens": 1}, headers=project["key_headers"])
    client.post(
        f"/agent-events/{pid}",
        json={"task_id": "t", "tool_name": "x", "status": "failed"},
        headers=project["key_headers"],
    )
    assert client.delete(f"/projects/{pid}", headers=account["headers"]).status_code == 204
    assert client.get(f"/projects/{pid}", headers=account["headers"]).status_code == 404
    # Re-creating the ID starts clean: no orphaned agent events (a v0.3 bug).
    make_project(client, account, project_id=pid)
    diagnosis = client.get(f"/projects/{pid}/agent-diagnosis", headers=account["headers"]).json()
    assert diagnosis["task_count"] == 0


def test_policy_defaults_and_updates(client, account, project):
    pid = project["project_id"]
    policy = client.get(f"/projects/{pid}/policy", headers=project["key_headers"]).json()
    assert policy["prompt_token_limit"] == 3000 and policy["blocked_after_failures"] == 3
    updated = client.put(
        f"/projects/{pid}/policy",
        json={"prompt_token_limit": 2000, "blocked_after_failures": 5},
        headers=account["headers"],
    ).json()
    assert updated["prompt_token_limit"] == 2000
    assert updated["blocked_after_failures"] == 5
    assert updated["context_length_limit"] == 4000
    for bad in ({"retrieval_score_floor": 1.5}, {"prompt_token_limit": 0}, {"unknown_field": 1}):
        assert client.put(f"/projects/{pid}/policy", json=bad, headers=account["headers"]).status_code == 422


def test_blocked_after_failures_is_an_integer(client, account, project):
    pid = project["project_id"]
    assert client.get(f"/projects/{pid}/policy", headers=account["headers"]).json()["blocked_after_failures"] == 3
    body = client.put(f"/projects/{pid}/policy", json={"blocked_after_failures": 4}, headers=account["headers"]).json()
    assert isinstance(body["blocked_after_failures"], int)
