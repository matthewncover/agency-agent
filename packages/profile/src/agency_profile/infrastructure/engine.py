from sqlalchemy import Engine, create_engine


def normalize_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def make_engine(database_url: str) -> Engine:
    # pool_pre_ping: the bot idles overnight, so pooled connections can be
    # killed under it (Postgres restarts / maintenance → AdminShutdown on the
    # first morning query). Ping-and-replace on checkout instead of crashing
    # someone's morning fire.
    return create_engine(normalize_url(database_url), future=True, pool_pre_ping=True)
