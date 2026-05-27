from __future__ import annotations

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.connection import get_session_factory
from app.db.models import Asset, DailyPrice, ModelFeature, ModelSignal
from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_or_create_assets(session: Session, tickers: list[str]) -> dict[str, int]:
    existing = session.execute(select(Asset).where(Asset.ticker.in_(tickers))).scalars().all()
    asset_ids = {asset.ticker: asset.id for asset in existing}

    for ticker in tickers:
        if ticker not in asset_ids:
            asset = Asset(ticker=ticker)
            session.add(asset)
            session.flush()
            asset_ids[ticker] = asset.id

    return asset_ids


def load_pipeline_outputs(prices: pd.DataFrame, features: pd.DataFrame, signals: pd.DataFrame) -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        tickers = sorted(set(prices["ticker"].unique()))
        asset_ids = get_or_create_assets(session, tickers)

        _upsert_prices(session, prices, asset_ids)
        _upsert_features(session, features, asset_ids)
        _upsert_signals(session, signals, asset_ids)

        session.commit()
        logger.info("Database load committed")


def _upsert_prices(session: Session, prices: pd.DataFrame, asset_ids: dict[str, int]) -> None:
    rows = [
        {
            "asset_id": asset_ids[row.ticker],
            "trading_date": row.trading_date,
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "adjusted_close": row.adjusted_close,
            "volume": int(row.volume) if pd.notna(row.volume) else None,
            "dollar_volume": _nullable_float(row.adjusted_close * row.volume),
            "data_vendor": "yfinance",
        }
        for row in prices.itertuples(index=False)
    ]
    if not rows:
        return

    statement = insert(DailyPrice).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=["asset_id", "trading_date"],
        set_={
            "open": statement.excluded.open,
            "high": statement.excluded.high,
            "low": statement.excluded.low,
            "close": statement.excluded.close,
            "adjusted_close": statement.excluded.adjusted_close,
            "volume": statement.excluded.volume,
            "dollar_volume": statement.excluded.dollar_volume,
            "data_vendor": statement.excluded.data_vendor,
        },
    )
    session.execute(statement)


def _upsert_features(session: Session, features: pd.DataFrame, asset_ids: dict[str, int]) -> None:
    rows = [
        {
            "asset_id": asset_ids[row.ticker],
            "trading_date": row.trading_date,
            "log_return": _nullable_float(row.log_return),
            "rolling_volatility_14d": _nullable_float(row.rolling_volatility_14d),
            "momentum_score": _nullable_float(row.momentum_score),
            "average_volume_20d": int(row.average_volume_20d) if hasattr(row, "average_volume_20d") and pd.notna(row.average_volume_20d) else None,
            "liquidity_pass": bool(row.volume >= 100_000) if hasattr(row, "volume") and pd.notna(row.volume) else False,
        }
        for row in features.itertuples(index=False)
    ]
    if not rows:
        return

    statement = insert(ModelFeature).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=["asset_id", "trading_date"],
        set_={
            "log_return": statement.excluded.log_return,
            "rolling_volatility_14d": statement.excluded.rolling_volatility_14d,
            "momentum_score": statement.excluded.momentum_score,
            "average_volume_20d": statement.excluded.average_volume_20d,
            "liquidity_pass": statement.excluded.liquidity_pass,
        },
    )
    session.execute(statement)


def _upsert_signals(session: Session, signals: pd.DataFrame, asset_ids: dict[str, int]) -> None:
    rows = [
        {
            "asset_id": asset_ids[row.ticker],
            "trading_date": row.trading_date,
            "signal": row.signal,
            "confidence": _nullable_float(row.confidence),
            "model_name": row.model_name,
            "execution_status": row.execution_status,
            "sector": getattr(row, "sector", "Unknown"),
            "industry": getattr(row, "industry", "Unknown"),
            "rank_in_sector": int(row.rank_in_sector) if hasattr(row, "rank_in_sector") and pd.notna(row.rank_in_sector) else None,
        }
        for row in signals.itertuples(index=False)
    ]
    if not rows:
        return

    statement = insert(ModelSignal).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=["asset_id", "trading_date", "model_name"],
        set_={
            "signal": statement.excluded.signal,
            "confidence": statement.excluded.confidence,
            "execution_status": statement.excluded.execution_status,
            "sector": statement.excluded.sector,
            "industry": statement.excluded.industry,
            "rank_in_sector": statement.excluded.rank_in_sector,
        },
    )
    session.execute(statement)


def _nullable_float(value: object) -> float | None:
    if pd.isna(value):
        return None
    return float(value)
