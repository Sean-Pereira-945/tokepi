from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def get_database_url() -> str:
    """Read the configured database URL from the environment, defaulting to a local SQLite database.

    Set DATABASE_URL in a .env file for persistent SaaS state; otherwise we use the repo-local SQLite file.
    """
    return os.getenv("DATABASE_URL", "sqlite:///./driftguard.db")


def get_rate_limit() -> int:
    """Maximum number of requests per minute per client IP.

    Set RATE_LIMIT_PER_MINUTE in the environment to override the default of 60.
    """
    try:
        return int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    except ValueError:
        return 60


def get_api_secret() -> str:
    """Secret key used for session token signing.

    Set API_SECRET in the environment. Falls back to a development default — always
    override this in production.
    """
    return os.getenv("API_SECRET", "driftguard-dev-secret-change-in-production")
