from __future__ import annotations

from datetime import date

import pandas as pd

from app.models.signal_generator import generate_momentum_signals


def test_generate_momentum_buy_signal() -> None:
    features = pd.DataFrame(
        {
            "ticker": ["AAPL"],
            "trading_date": [date(2026, 1, 31)],
            "momentum_score": [0.10],
            "rolling_volatility_14d": [0.20],
        }
    )

    signals = generate_momentum_signals(features)

    assert len(signals) == 1
    assert signals.iloc[0]["signal"] == "BUY"
