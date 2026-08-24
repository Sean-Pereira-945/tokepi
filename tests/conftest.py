import os

# Set default database URL to in-memory SQLite for all tests to ensure isolation
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
