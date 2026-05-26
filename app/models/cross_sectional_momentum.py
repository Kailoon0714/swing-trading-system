from __future__ import annotations

import pandas as pd


def rank_latest_momentum(features: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    latest_date = features["trading_date"].max()
    latest = features[features["trading_date"] == latest_date].copy()
    return latest.sort_values("momentum_score", ascending=False).head(top_n)
