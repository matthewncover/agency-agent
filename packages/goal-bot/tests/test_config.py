from goal_bot.config import get_settings


def test_settings_default_database_url():
    assert get_settings().database_url.startswith("postgresql://")
