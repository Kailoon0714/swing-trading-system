from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"

    database_url: str | None = None
    supabase_url: str | None = None
    supabase_key: str | None = None

    default_tickers: list[str] = Field(default_factory=lambda: ["AAPL", "MSFT", "NVDA", "SPY", "QQQ"])
    initial_capital_usd: float = 200.0
    max_position_fraction: float = 0.20
    max_open_positions: int = 3
    stop_loss_pct: float = 0.04
    take_profit_pct: float = 0.08

    momentum_lookback_days: int = 20
    volatility_lookback_days: int = 14
    buy_momentum_threshold: float = 0.08
    sell_momentum_threshold: float = -0.05
    max_volatility_threshold: float = 0.60

    @field_validator("default_tickers", mode="before")
    @classmethod
    def parse_tickers(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [item.strip().upper() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip().upper() for item in value if str(item).strip()]
        return ["AAPL", "MSFT", "NVDA", "SPY", "QQQ"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
