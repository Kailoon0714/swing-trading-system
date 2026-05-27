from __future__ import annotations

import pandas as pd

from app.utils.config import settings


def rank_sector_neutral_momentum(
    features: pd.DataFrame,
    top_n_per_sector: int | None = None,
    min_volume: int | None = None,
) -> pd.DataFrame:
    required = ["ticker", "trading_date", "momentum_score", "rolling_volatility_14d", "volume"]
    missing = [column for column in required if column not in features.columns]
    if missing:
        raise ValueError(f"Missing columns for sector-neutral momentum ranking: {missing}")

    top_n = settings.top_n_per_sector if top_n_per_sector is None else top_n_per_sector
    liquidity_floor = settings.min_daily_volume if min_volume is None else min_volume

    frame = features.copy()
    frame["sector"] = frame.get("sector", "Unknown")
    frame["industry"] = frame.get("industry", "Unknown")
    frame["sector"] = frame["sector"].fillna("Unknown")
    frame["industry"] = frame["industry"].fillna("Unknown")
    frame["liquidity_pass"] = frame["volume"].fillna(0) >= liquidity_floor

    eligible = frame.dropna(subset=["momentum_score", "rolling_volatility_14d"])
    eligible = eligible[
        (eligible["liquidity_pass"])
        & (eligible["momentum_score"] > settings.buy_momentum_threshold)
        & (eligible["rolling_volatility_14d"] < settings.max_volatility_threshold)
    ].copy()

    if eligible.empty:
        return eligible.assign(rank_in_sector=pd.Series(dtype="int64"))

    eligible["rank_in_sector"] = (
        eligible.groupby(["trading_date", "sector"])["momentum_score"]
        .rank(method="first", ascending=False)
        .astype("int64")
    )
    return eligible[eligible["rank_in_sector"] <= top_n].copy()


def rank_latest_momentum(features: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    latest_date = features["trading_date"].max()
    latest = rank_sector_neutral_momentum(features[features["trading_date"] == latest_date], top_n_per_sector=top_n)
    return latest.sort_values(["sector", "rank_in_sector", "momentum_score"], ascending=[True, True, False])
