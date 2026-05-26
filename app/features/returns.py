from __future__ import annotations

import numpy as np
import pandas as pd


def add_log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    frame = prices.sort_values(["ticker", "trading_date"]).copy()
    previous_close = frame.groupby("ticker")["adjusted_close"].shift(1)
    frame["log_return"] = np.log(frame["adjusted_close"] / previous_close)
    return frame
