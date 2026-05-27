from __future__ import annotations

import argparse
from datetime import date

from app.etl.clean_prices import clean_price_frame
from app.etl.fetch_prices import fetch_eod_prices
from app.etl.load_to_db import load_pipeline_outputs
from app.features.momentum import add_momentum_score
from app.features.returns import add_log_returns
from app.features.volatility import add_rolling_volatility
from app.models.signal_generator import generate_momentum_signals
from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def run_daily_pipeline(tickers: list[str] | None, period: str, dry_run: bool = False) -> None:
    if tickers:
        logger.info("Starting daily pipeline with explicit universe of {} tickers", len(tickers))
    else:
        logger.info("Starting daily pipeline with dynamic active database universe")
    raw_prices = fetch_eod_prices(tickers=tickers, period=period)
    prices = clean_price_frame(raw_prices)

    features = add_log_returns(prices)
    features = add_rolling_volatility(
        features,
        lookback_days=settings.volatility_lookback_days,
    )
    features = add_momentum_score(
        features,
        lookback_days=settings.momentum_lookback_days,
    )
    signals = generate_momentum_signals(features)

    logger.info(
        "Pipeline generated {} price rows, {} feature rows, and {} signal rows",
        len(prices),
        len(features),
        len(signals),
    )

    if dry_run:
        logger.info("Dry run enabled; skipping database writes")
        if not signals.empty:
            logger.info("Latest signals:\n{}", signals.tail(10).to_string(index=False))
        return

    load_pipeline_outputs(prices=prices, features=features, signals=signals)
    logger.info("Daily pipeline finished for {}", date.today().isoformat())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the US equity swing-trading daily pipeline.")
    parser.add_argument("--tickers", nargs="*", default=None)
    parser.add_argument("--period", default="1y", help="yfinance period such as 6mo, 1y, 5y")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing to the database")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_daily_pipeline(tickers=args.tickers, period=args.period, dry_run=args.dry_run)
