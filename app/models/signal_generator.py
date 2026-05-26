from __future__ import annotations

import numpy as np
import pandas as pd

from app.utils.config import settings

MODEL_NAME = "cross_sectional_momentum_v1"


def generate_momentum_signals(features: pd.DataFrame) -> pd.DataFrame:
    required = ["ticker", "trading_date", "momentum_score", "rolling_volatility_14d"]
    missing = [column for column in required if column not in features.columns]
    if missing:
        raise ValueError(f"Missing feature columns for signal generation: {missing}")

    frame = features.dropna(subset=["momentum_score", "rolling_volatility_14d"]).copy()
    if frame.empty:
        return pd.DataFrame(
            columns=["ticker", "trading_date", "signal", "confidence", "model_name", "execution_status"]
        )

    buy_mask = (
        (frame["momentum_score"] > settings.buy_momentum_threshold)
        & (frame["rolling_volatility_14d"] < settings.max_volatility_threshold)
    )
    sell_mask = frame["momentum_score"] < settings.sell_momentum_threshold

    frame["signal"] = np.select([buy_mask, sell_mask], ["BUY", "SELL"], default="HOLD")
    frame = frame[frame["signal"] != "HOLD"].copy()
    if frame.empty:
        return pd.DataFrame(
            columns=["ticker", "trading_date", "signal", "confidence", "model_name", "execution_status"]
        )

    frame["confidence"] = _confidence_from_momentum(frame["momentum_score"])
    frame["model_name"] = MODEL_NAME
    frame["execution_status"] = "PENDING"
    return frame[["ticker", "trading_date", "signal", "confidence", "model_name", "execution_status"]]


def _confidence_from_momentum(momentum: pd.Series) -> pd.Series:
    clipped = momentum.abs().clip(lower=0.0, upper=0.25)
    return (clipped / 0.25).round(4)
