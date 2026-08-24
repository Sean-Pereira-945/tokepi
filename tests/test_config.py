import os

from driftguard.config import get_database_url


def test_database_url_reads_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/driftguard")
    assert get_database_url() == "postgresql://user:pass@localhost:5432/driftguard"


def test_database_url_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert get_database_url() == "sqlite:///./driftguard.db"

