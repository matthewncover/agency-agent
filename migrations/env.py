import os

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
target_metadata = None  # raw-SQL revisions; no autogenerate


def _url() -> str:
    chosen = config.get_main_option("sqlalchemy.url") or os.environ.get(
        "DATABASE_URL", "postgresql://agency:agency@localhost:5432/agency"
    )
    if chosen.startswith("postgresql://"):
        chosen = chosen.replace("postgresql://", "postgresql+psycopg://", 1)
    return chosen


def run_migrations_offline() -> None:
    context.configure(
        url=_url(), literal_binds=True, dialect_opts={"paramstyle": "named"}
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    config.set_main_option("sqlalchemy.url", _url())
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
