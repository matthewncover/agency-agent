from agency_profile.infrastructure.engine import make_engine

from goal_bot.config import get_settings
from goal_bot.server import build_ingestion_server


def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    mcp = build_ingestion_server(engine)
    mcp.run()  # FastMCP default transport = stdio (what Claude Desktop uses)


if __name__ == "__main__":
    main()
