import os

import pytest
from agency_profile.infrastructure.engine import make_engine, normalize_url
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

BASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://agency:agency@localhost:5432/agency"
)
TEST_DB = "agency_test"


def _test_url() -> str:
    head, _ = BASE_URL.rsplit("/", 1)
    return f"{head}/{TEST_DB}"


@pytest.fixture(scope="session")
def migrated_engine():
    admin = create_engine(
        normalize_url(BASE_URL), isolation_level="AUTOCOMMIT", future=True
    )
    with admin.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
        c.execute(text(f"CREATE DATABASE {TEST_DB}"))
    admin.dispose()

    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", normalize_url(_test_url()))
    command.upgrade(cfg, "head")

    engine = make_engine(_test_url())
    yield engine
    engine.dispose()
