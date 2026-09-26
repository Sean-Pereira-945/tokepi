import time
import logging
import re
from datetime import datetime, timezone
import sqlite3

from driftguard.config import get_database_url

logger = logging.getLogger(__name__)

# Basic PII regex for common formats like email and SSN
# This is a naive heuristic for demonstration purposes
PII_PATTERNS = [
    (re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-]+'), '[EMAIL REDACTED]'),
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '[SSN REDACTED]'),
    (re.compile(r'\b(?:\d[ -]*?){13,16}\b'), '[CREDIT CARD REDACTED]')
]

def scrub_pii(text: str) -> str:
    """Scrub common PII from a given string using regex heuristics."""
    if not text:
        return text
    scrubbed = text
    for pattern, replacement in PII_PATTERNS:
        scrubbed = pattern.sub(replacement, scrubbed)
    return scrubbed


class RetentionWorker:
    """Background worker to clean up old telemetry and scrub PII."""
    
    def __init__(self, retention_days: int = 30):
        self.retention_days = retention_days
        self.db_url = get_database_url()
        self._is_postgres = self.db_url.startswith("postgres")

    def _get_connection(self):
        """Get a raw connection to the database."""
        if self._is_postgres:
            import psycopg2
            conn = psycopg2.connect(self.db_url)
            conn.autocommit = True
            return conn
        else:
            path = self.db_url.replace("sqlite:///", "")
            return sqlite3.connect(path if path else "driftguard.db")

    def prune_old_telemetry(self):
        """Delete telemetry older than the retention period."""
        logger.info(f"Starting retention prune (older than {self.retention_days} days)")
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Use appropriate date subtraction syntax
            if self._is_postgres:
                cutoff_clause = f"created_at < NOW() - INTERVAL '{self.retention_days} days'"
            else:
                cutoff_clause = f"created_at < datetime('now', '-{self.retention_days} days')"
                
            cursor.execute(f"DELETE FROM events WHERE {cutoff_clause}")
            events_deleted = cursor.rowcount
            
            cursor.execute(f"DELETE FROM agent_events WHERE {cutoff_clause}")
            agent_events_deleted = cursor.rowcount
            
            if not self._is_postgres:
                conn.commit()
                
            logger.info(f"Pruned {events_deleted} events and {agent_events_deleted} agent_events.")
            
        except Exception as e:
            logger.error(f"Failed to prune telemetry: {e}")
        finally:
            if 'conn' in locals() and self.db_url != "sqlite:///:memory:":
                conn.close()

def run_worker_loop(interval_hours: int = 24, retention_days: int = 30):
    """Run the retention worker in an infinite loop."""
    worker = RetentionWorker(retention_days=retention_days)
    while True:
        worker.prune_old_telemetry()
        time.sleep(interval_hours * 3600)
