from __future__ import annotations

import pandas as pd


def add_momentum_score(features: pd.DataFrame, lookback_days: int = 20) -> pd.DataFrame:
    frame = features.sort_values(["ticker", "trading_date"]).copy()
    lookback_close = frame.groupby("ticker")["adjusted_close"].shift(lookback_days)
    frame["momentum_score"] = frame["adjusted_close"] / lookback_close - 1
    return frame
