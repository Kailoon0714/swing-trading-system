from __future__ import annotations

import numpy as np
import pandas as pd

from app.models.cross_sectional_momentum import rank_sector_neutral_momentum
from app.utils.config import settings

MODEL_NAME = "cross_sectional_momentum_v2"
SIGNAL_COLUMNS = [
    "ticker",
    "trading_date",
    "signal",
    "confidence",
    "model_name",
    "execution_status",
    "sector",
    "industry",
    "rank_in_sector",
]


def generate_momentum_signals(features: pd.DataFrame) -> pd.DataFrame:
    required = ["ticker", "trading_date", "momentum_score", "rolling_volatility_14d", "volume"]
    missing = [column for column in required if column not in features.columns]
    if missing:
        raise ValueError(f"Missing feature columns for signal generation: {missing}")

    frame = features.copy()
    frame["sector"] = frame.get("sector", "Unknown")
    frame["industry"] = frame.get("industry", "Unknown")
    frame["liquidity_pass"] = frame["volume"].fillna(0) >= settings.min_daily_volume

    buys = rank_sector_neutral_momentum(frame)
    buys["signal"] = "BUY"

    sells = frame[
        frame["momentum_score"].notna()
        & (frame["momentum_score"] < settings.sell_momentum_threshold)
        & frame["liquidity_pass"]
    ].copy()
    sells["signal"] = "SELL"
    sells["rank_in_sector"] = pd.NA

    signals = pd.concat([buys, sells], ignore_index=True)
    if signals.empty:
        return pd.DataFrame(columns=SIGNAL_COLUMNS)

    signals["confidence"] = _confidence_from_momentum(signals["momentum_score"])
    signals["model_name"] = MODEL_NAME
    signals["execution_status"] = "PENDING"
    signals["sector"] = signals["sector"].fillna("Unknown")
    signals["industry"] = signals["industry"].fillna("Unknown")
    return signals[SIGNAL_COLUMNS].sort_values(["trading_date", "ticker", "signal"]).reset_index(drop=True)


def _confidence_from_momentum(momentum: pd.Series) -> pd.Series:
    clipped = momentum.abs().clip(lower=0.0, upper=0.25)
    return np.minimum(clipped / 0.25, 1.0).round(4)
