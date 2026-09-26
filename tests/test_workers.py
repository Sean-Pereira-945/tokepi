import pytest
from driftguard.workers import scrub_pii, RetentionWorker

def test_scrub_pii():
    text1 = "Contact me at test@example.com."
    assert scrub_pii(text1) == "Contact me at [EMAIL REDACTED]."
    
    text2 = "My SSN is 123-45-6789."
    assert scrub_pii(text2) == "My SSN is [SSN REDACTED]."
    
    text3 = "Card number 4111222233334444 please"
    assert scrub_pii(text3) == "Card number [CREDIT CARD REDACTED] please"

def test_retention_prune(monkeypatch):
    # Mock get_database_url to use a test SQLite db in memory
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    
    from driftguard.service import DriftGuardService
    service = DriftGuardService(database_url="sqlite:///:memory:")
    
    # Insert an old event directly
    service.conn.execute("INSERT INTO events (project_id, created_at) VALUES ('proj-1', datetime('now', '-40 days'))")
    service.conn.execute("INSERT INTO events (project_id, created_at) VALUES ('proj-1', datetime('now', '-10 days'))")
    service.conn.commit()
    
    # Run the worker to prune > 30 days
    worker = RetentionWorker(retention_days=30)
    worker.db_url = "sqlite:///:memory:"
    
    # In SQLite memory, connection is unique to the thread/object, so we must mock the connection to use the service's conn
    def mock_get_conn():
        return service.conn
    worker._get_connection = mock_get_conn
    
    worker.prune_old_telemetry()
    
    # Check what is left
    remaining = service.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert remaining == 1
