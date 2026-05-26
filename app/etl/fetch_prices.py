from __future__ import annotations

import pandas as pd
import yfinance as yf

from app.utils.helpers import normalize_ticker
from app.utils.logger import get_logger

logger = get_logger(__name__)


def fetch_eod_prices(tickers: list[str], period: str = "1y") -> pd.DataFrame:
    normalized = [normalize_ticker(ticker) for ticker in tickers]
    logger.info("Fetching EOD prices from yfinance for {}", ", ".join(normalized))

    raw = yf.download(
        tickers=normalized,
        period=period,
        interval="1d",
        auto_adjust=False,
        group_by="ticker",
        progress=False,
        threads=True,
    )

    if raw.empty:
        raise ValueError("yfinance returned no price data")

    frames: list[pd.DataFrame] = []
    for ticker in normalized:
        if len(normalized) == 1:
            ticker_frame = raw.copy()
        else:
            if ticker not in raw.columns.get_level_values(0):
                logger.warning("Ticker {} missing from yfinance response", ticker)
                continue
            ticker_frame = raw[ticker].copy()

        ticker_frame = ticker_frame.reset_index()
        ticker_frame["ticker"] = ticker
        frames.append(ticker_frame)

    if not frames:
        raise ValueError("No ticker data could be normalized from yfinance response")

    return pd.concat(frames, ignore_index=True)
