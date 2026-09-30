from helpers import make_project, register


def test_health_reports_database(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


def test_register_login_me_logout(client):
    account = register(client, name="Ada")
    assert account["account_id"].startswith("acct-")
    assert "password" not in client.get("/auth/me", headers=account["headers"]).text

    me = client.get("/auth/me", headers=account["headers"])
    assert me.status_code == 200 and me.json()["name"] == "Ada"

    login = client.post("/auth/login", json={"email": account["email"].upper(), "password": account["password"]})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401
    # Logging out one session does not end the others.
    assert client.get("/auth/me", headers=account["headers"]).status_code == 200


def test_duplicate_email_is_rejected(client):
    account = register(client)
    response = client.post("/auth/register", json={"name": "x", "email": account["email"], "password": "12345678"})
    assert response.status_code == 409


def test_wrong_password_and_unknown_email_fail_identically(client):
    account = register(client)
    wrong = client.post("/auth/login", json={"email": account["email"], "password": "nope-nope"})
    unknown = client.post("/auth/login", json={"email": "ghost@example.test", "password": "nope-nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_registration_validation(client):
    assert client.post("/auth/register", json={"name": "a", "email": "bad", "password": "12345678"}).status_code == 422
    assert client.post("/auth/register", json={"name": "a", "email": "a@b.co", "password": "short"}).status_code == 422
    assert (
        client.post("/auth/register", json={"name": " ", "email": "a@b.co", "password": "12345678"}).status_code == 422
    )


def test_requests_without_credentials_are_rejected(client):
    """v0.3 silently used a shared 'default' account; that fallback is gone."""
    assert client.get("/auth/me").status_code == 401
    assert client.get("/projects").status_code == 401
    assert client.post("/projects", json={"project_id": "p", "name": "p"}).status_code == 401
    assert client.get("/projects/anything/summary").status_code == 401


def test_invalid_and_forged_tokens_are_rejected(client):
    import jwt

    assert client.get("/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
    forged = jwt.encode(
        {"sub": "acct-x", "jti": "j", "exp": 9999999999}, "wrong-secret-of-sufficient-length-32b", algorithm="HS256"
    )
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_signup_can_be_disabled(settings):
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from driftguard.server import create_app

    with TestClient(create_app(replace(settings, allow_signup=False))) as client:
        assert client.get("/auth/config").json()["allow_signup"] is False
        response = client.post("/auth/register", json={"name": "a", "email": "a@b.co", "password": "12345678"})
        assert response.status_code == 403


def test_delete_account_removes_projects(client):
    account = register(client)
    project = make_project(client, account)
    bad = client.request("DELETE", "/auth/me", json={"password": "wrong-password"}, headers=account["headers"])
    assert bad.status_code == 403
    ok = client.request("DELETE", "/auth/me", json={"password": account["password"]}, headers=account["headers"])
    assert ok.status_code == 204
    assert client.get("/auth/me", headers=account["headers"]).status_code == 401
    assert client.get(f"/projects/{project['project_id']}/policy", headers=project["key_headers"]).status_code == 401


def test_login_is_rate_limited(settings):
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from driftguard.server import create_app

    with TestClient(create_app(replace(settings, login_rate_limit_per_minute=3))) as client:
        codes = [client.post("/auth/login", json={"email": "a@b.co", "password": "x"}).status_code for _ in range(4)]
    assert codes == [401, 401, 401, 429]


def test_api_rate_limit_is_per_session_not_per_ip(settings):
    """Two users behind the same IP each get their own API budget."""
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from driftguard.server import create_app

    with TestClient(create_app(replace(settings, rate_limit_per_minute=3))) as client:
        alice, bob = register(client), register(client)
        alice_codes = [client.get("/auth/me", headers=alice["headers"]).status_code for _ in range(4)]
        bob_code = client.get("/auth/me", headers=bob["headers"]).status_code
    assert alice_codes == [200, 200, 200, 429]
    assert bob_code == 200
