from __future__ import annotations

import numpy as np
import pandas as pd


def add_rolling_volatility(features: pd.DataFrame, lookback_days: int = 14) -> pd.DataFrame:
    frame = features.sort_values(["ticker", "trading_date"]).copy()
    column_name = "rolling_volatility_14d"
    frame[column_name] = (
        frame.groupby("ticker")["log_return"]
        .rolling(window=lookback_days, min_periods=lookback_days)
        .std()
        .reset_index(level=0, drop=True)
        * np.sqrt(252)
    )
    return frame
