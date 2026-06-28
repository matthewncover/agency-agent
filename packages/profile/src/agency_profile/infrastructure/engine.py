from sqlalchemy import Engine, create_engine


def normalize_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def make_engine(database_url: str) -> Engine:
    return create_engine(normalize_url(database_url), future=True)
