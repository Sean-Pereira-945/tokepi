"""Shared fixtures: an isolated server per test and authenticated helpers.

Tests use in-memory SQLite. Set ``DRIFTGUARD_TEST_DATABASE_URL`` (for example
``postgresql://driftguard:driftguard@localhost:5432/driftguard_test``) to run the
same suite against PostgreSQL; the schema is dropped before each test.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import pytest
from helpers import make_project, register

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

TEST_DATABASE_URL = os.getenv("DRIFTGUARD_TEST_DATABASE_URL", "sqlite://")


def _reset_database(url: str) -> None:
    from driftguard.server.db import make_engine, metadata

    engine = make_engine(url)
    metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def settings(tmp_path: Any) -> Any:
    pytest.importorskip("fastapi")
    from driftguard.server import Settings

    if not TEST_DATABASE_URL.startswith("sqlite"):
        _reset_database(TEST_DATABASE_URL)
    return Settings(
        database_url=TEST_DATABASE_URL,
        secret_key="test-secret-key-that-is-long-enough-for-tests",
        environment="test",
        retention_days=0,
        static_dir=tmp_path / "no-dashboard",
    )


@pytest.fixture
def app(settings: Any) -> Iterator[Any]:
    from driftguard.server import create_app

    application = create_app(settings)
    yield application
    application.state.service.engine.dispose()


@pytest.fixture
def client(app: Any) -> Iterator[TestClient]:
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def account(client: TestClient) -> dict[str, Any]:
    return register(client)


@pytest.fixture
def project(client: TestClient, account: dict[str, Any]) -> dict[str, Any]:
    return make_project(client, account)
