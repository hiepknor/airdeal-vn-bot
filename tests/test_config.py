from app.config import Settings


def test_allowed_telegram_user_ids_is_public_when_empty():
    settings = Settings(TELEGRAM_BOT_TOKEN="test", TELEGRAM_ALLOWED_USER_IDS="")

    assert settings.allowed_telegram_user_ids is None


def test_allowed_telegram_user_ids_parses_comma_separated_ids():
    settings = Settings(TELEGRAM_BOT_TOKEN="test", TELEGRAM_ALLOWED_USER_IDS="123, 456")

    assert settings.allowed_telegram_user_ids == frozenset({123, 456})
