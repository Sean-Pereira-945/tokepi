"""Test helpers for creating accounts and projects through the API."""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

_counter = itertools.count()


def register(client: TestClient, name: str = "Test User", password: str = "correct-horse") -> dict[str, Any]:
    """Register a fresh account; returns the response plus ready-to-use headers."""
    email = f"user{next(_counter)}@example.test"
    response = client.post("/auth/register", json={"name": name, "email": email, "password": password})
    assert response.status_code == 201, response.text
    data = response.json()
    return {**data, "email": email, "password": password, "headers": {"Authorization": f"Bearer {data['token']}"}}


def make_project(
    client: TestClient, account: dict[str, Any], project_id: str | None = None, environment: str = "prod"
) -> dict[str, Any]:
    """Create a project for ``account``; returns it with ``api_key`` and key headers."""
    project_id = project_id or f"proj-{next(_counter)}"
    response = client.post(
        "/projects",
        json={"project_id": project_id, "name": f"Project {project_id}", "environment": environment},
        headers=account["headers"],
    )
    assert response.status_code == 201, response.text
    data = response.json()
    return {**data, "key_headers": {"X-API-Key": data["api_key"]}}
