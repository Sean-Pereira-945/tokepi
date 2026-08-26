import os

import pytest

# Set default database URL to in-memory SQLite for all tests to ensure isolation
os.environ["DATABASE_URL"] = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Keep rate-limit state from leaking between independent tests."""
    from driftguard import middleware

    middleware._default_limiter._hits.clear()
    middleware._ingestion_limiter._hits.clear()
    yield
    middleware._default_limiter._hits.clear()
    middleware._ingestion_limiter._hits.clear()
