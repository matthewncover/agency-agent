import os

import psycopg
import pytest


@pytest.mark.integration
def test_postgres_reachable():
    url = os.environ.get(
        "DATABASE_URL", "postgresql://agency:agency@localhost:5432/agency"
    )
    with psycopg.connect(url) as conn:
        assert conn.execute("SELECT 1").fetchone()[0] == 1
