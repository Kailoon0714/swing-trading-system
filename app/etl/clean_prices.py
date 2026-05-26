from __future__ import annotations

import pandas as pd


PRICE_COLUMNS = {
    "Date": "trading_date",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adjusted_close",
    "Volume": "volume",
}


def clean_price_frame(prices: pd.DataFrame) -> pd.DataFrame:
    cleaned = prices.rename(columns=PRICE_COLUMNS).copy()
    expected = ["ticker", "trading_date", "open", "high", "low", "close", "adjusted_close", "volume"]
    missing = [column for column in expected if column not in cleaned.columns]
    if missing:
        raise ValueError(f"Missing expected price columns: {missing}")

    cleaned = cleaned[expected]
    cleaned["ticker"] = cleaned["ticker"].astype(str).str.upper().str.strip()
    cleaned["trading_date"] = pd.to_datetime(cleaned["trading_date"]).dt.date

    numeric_columns = ["open", "high", "low", "close", "adjusted_close", "volume"]
    for column in numeric_columns:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")

    cleaned = cleaned.dropna(subset=["ticker", "trading_date", "close", "adjusted_close"])
    cleaned = cleaned[cleaned["volume"].fillna(0) >= 0]
    cleaned = cleaned.drop_duplicates(subset=["ticker", "trading_date"], keep="last")
    cleaned = cleaned.sort_values(["ticker", "trading_date"]).reset_index(drop=True)
    return cleaned
