from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from app.features.momentum import add_momentum_score
from app.features.returns import add_log_returns
from app.features.volatility import add_rolling_volatility


def test_feature_columns_are_added() -> None:
    start = date(2026, 1, 1)
    prices = pd.DataFrame(
        {
            "ticker": ["AAPL"] * 30,
            "trading_date": [start + timedelta(days=index) for index in range(30)],
            "open": range(100, 130),
            "high": range(101, 131),
            "low": range(99, 129),
            "close": range(100, 130),
            "adjusted_close": range(100, 130),
            "volume": [1_000_000] * 30,
        }
    )

    features = add_log_returns(prices)
    features = add_rolling_volatility(features, lookback_days=14)
    features = add_momentum_score(features, lookback_days=20)

    assert "log_return" in features.columns
    assert "rolling_volatility_14d" in features.columns
    assert "momentum_score" in features.columns
    assert features["momentum_score"].notna().sum() == 10
