"""Several workers initialising the schema at once must not fail."""

import os
from concurrent.futures import ThreadPoolExecutor

import pytest

pytest.importorskip("sqlalchemy")

from driftguard.server.db import init_db, make_engine, metadata


def test_parallel_init_db(tmp_path):
    url = os.getenv("DRIFTGUARD_TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'race.db'}"
    reset = make_engine(url)
    metadata.drop_all(reset)
    reset.dispose()

    def start_worker(_):
        engine = make_engine(url)
        try:
            init_db(engine)
        finally:
            engine.dispose()

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(start_worker, range(6)))
