from __future__ import annotations

import hmac
import re

TELEGRAM_SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"  # noqa: S105

_SECRET_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{1,256}$")


def normalize_webhook_secret(secret: str | None) -> str:
    if not secret:
        raise ValueError("TELEGRAM_WEBHOOK_SECRET required in webhook mode")

    normalized = secret.strip()
    if not _SECRET_TOKEN_RE.fullmatch(normalized):
        raise ValueError(
            "TELEGRAM_WEBHOOK_SECRET must be 1-256 chars using A-Z, a-z, 0-9, _ or -"
        )
    return normalized


def verify_telegram_webhook_secret(header_value: str | None, expected_secret: str) -> bool:
    expected = normalize_webhook_secret(expected_secret)
    if header_value is None:
        return False
    return hmac.compare_digest(header_value, expected)
