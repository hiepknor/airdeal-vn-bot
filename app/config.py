from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    telegram_mode: str = Field("polling", alias="TELEGRAM_MODE")
    telegram_webhook_url: str | None = Field(None, alias="TELEGRAM_WEBHOOK_URL")
    telegram_webhook_secret: str | None = Field(None, alias="TELEGRAM_WEBHOOK_SECRET")
    telegram_allowed_user_ids: str | None = Field(None, alias="TELEGRAM_ALLOWED_USER_IDS")

    database_url: str = Field("sqlite+aiosqlite:///./data/airdeal.db", alias="DATABASE_URL")

    traveloka_affiliate_id: str | None = Field(None, alias="TRAVELOKA_AFFILIATE_ID")
    trip_affiliate_id: str | None = Field(None, alias="TRIP_AFFILIATE_ID")

    # Provider flags
    atadi_api_key: str | None = Field(None, alias="ATADI_API_KEY")
    atadi_enabled: bool = Field(False, alias="ATADI_ENABLED")
    atadi_web_enabled: bool = Field(True, alias="ATADI_WEB_ENABLED")   # Playwright scraper
    atadi_use_cloak: bool = Field(False, alias="ATADI_USE_CLOAK")     # dùng CloakBrowser thay Playwright
    fast_flights_enabled: bool = Field(True, alias="FAST_FLIGHTS_ENABLED")

    price_scan_interval_minutes: int = Field(60, alias="PRICE_SCAN_INTERVAL_MINUTES")
    search_cache_ttl_minutes: int = Field(30, alias="SEARCH_CACHE_TTL_MINUTES")
    max_alerts_per_user_per_day: int = Field(10, alias="MAX_ALERTS_PER_USER_PER_DAY")
    rate_limit_per_minute: int = Field(20, alias="RATE_LIMIT_PER_MINUTE")

    log_level: str = Field("INFO", alias="LOG_LEVEL")
    http_port: int = Field(8080, alias="HTTP_PORT")

    @property
    def sqlite_path(self) -> str:
        return self.database_url.split("///", 1)[-1]

    @property
    def allowed_telegram_user_ids(self) -> frozenset[int] | None:
        if not self.telegram_allowed_user_ids:
            return None
        user_ids = {
            int(raw_id.strip())
            for raw_id in self.telegram_allowed_user_ids.split(",")
            if raw_id.strip()
        }
        return frozenset(user_ids) or None


settings = Settings()  # type: ignore[call-arg]
