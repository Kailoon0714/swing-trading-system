from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"

    database_url: str | None = None
    supabase_url: str | None = None
    supabase_key: str | None = None

    default_tickers: str = "AAPL,MSFT,NVDA,SPY,QQQ"
    initial_capital_usd: float = 200.0
    max_position_fraction: float = 0.20
    max_open_positions: int = 3
    stop_loss_pct: float = 0.04
    take_profit_pct: float = 0.08
    min_order_quantity: float = 0.0001
    min_buy_notional_usd: float = 5.00
    max_fee_ratio: float = 0.03
    min_daily_volume: int = 100_000
    top_n_per_sector: int = 2

    momentum_lookback_days: int = 20
    volatility_lookback_days: int = 14
    buy_momentum_threshold: float = 0.08
    sell_momentum_threshold: float = -0.05
    max_volatility_threshold: float = 0.60

    @field_validator("default_tickers")
    @classmethod
    def normalize_tickers_csv(cls, value: str) -> str:
        return ",".join(item.strip().upper() for item in value.split(",") if item.strip())

    @property
    def ticker_list(self) -> list[str]:
        return [item for item in self.default_tickers.split(",") if item]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
