import pytest

from app.bot.middleware.webhook_auth import normalize_webhook_secret, verify_telegram_webhook_secret


def test_normalize_webhook_secret_rejects_missing_secret():
    with pytest.raises(ValueError, match="TELEGRAM_WEBHOOK_SECRET required"):
        normalize_webhook_secret(None)


def test_normalize_webhook_secret_rejects_invalid_token_chars():
    with pytest.raises(ValueError, match="1-256 chars"):
        normalize_webhook_secret("bad secret")


def test_verify_telegram_webhook_secret_requires_matching_header():
    assert verify_telegram_webhook_secret("secret_123", "secret_123") is True
    assert verify_telegram_webhook_secret("wrong", "secret_123") is False
    assert verify_telegram_webhook_secret(None, "secret_123") is False
