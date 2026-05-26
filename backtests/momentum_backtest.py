from __future__ import annotations

import pandas as pd


def simple_signal_return_summary(prices_with_signals: pd.DataFrame) -> pd.Series:
    frame = prices_with_signals.sort_values(["ticker", "trading_date"]).copy()
    frame["forward_return_5d"] = frame.groupby("ticker")["adjusted_close"].shift(-5) / frame["adjusted_close"] - 1
    buy_returns = frame.loc[frame["signal"] == "BUY", "forward_return_5d"].dropna()
    return pd.Series(
        {
            "signals": float(len(buy_returns)),
            "mean_5d_return": buy_returns.mean(),
            "win_rate": (buy_returns > 0).mean() if len(buy_returns) else 0.0,
        }
    )
