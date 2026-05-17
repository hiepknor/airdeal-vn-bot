import pytest

from app import main


def test_webhook_config_requires_url(monkeypatch):
    monkeypatch.setattr(main.settings, "telegram_webhook_url", None)
    monkeypatch.setattr(main.settings, "telegram_webhook_secret", "secret_123")

    with pytest.raises(RuntimeError, match="TELEGRAM_WEBHOOK_URL required"):
        main._webhook_config()


def test_webhook_config_requires_secret(monkeypatch):
    monkeypatch.setattr(main.settings, "telegram_webhook_url", "https://example.com/webhook")
    monkeypatch.setattr(main.settings, "telegram_webhook_secret", None)

    with pytest.raises(RuntimeError, match="TELEGRAM_WEBHOOK_SECRET required"):
        main._webhook_config()


def test_webhook_config_returns_normalized_secret(monkeypatch):
    monkeypatch.setattr(main.settings, "telegram_webhook_url", "https://example.com/webhook")
    monkeypatch.setattr(main.settings, "telegram_webhook_secret", " secret_123 ")

    assert main._webhook_config() == ("https://example.com/webhook", "secret_123")
