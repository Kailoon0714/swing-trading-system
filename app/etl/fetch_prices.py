from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_DOWN

import pandas as pd
import yfinance as yf

from app.db.connection import fetch_active_universe
from app.db.models import FeeBreakdown, SizingDecision
from app.utils.config import settings
from app.utils.helpers import normalize_ticker
from app.utils.logger import get_logger

logger = get_logger(__name__)

PERIOD_TO_DAYS = {
    "1d": 1,
    "5d": 5,
    "1mo": 31,
    "3mo": 93,
    "6mo": 186,
    "1y": 366,
    "2y": 366 * 2,
    "5y": 366 * 5,
    "10y": 366 * 10,
}

MIN_ORDER_QUANTITY = Decimal("0.0001")
MIN_BUY_NOTIONAL = Decimal("5.00")
MAX_FEE_RATIO = Decimal("0.03")


def fetch_eod_prices(
    tickers: list[str] | None = None,
    period: str = "1y",
    min_volume: int | None = None,
    chunk_years: int = 1,
) -> pd.DataFrame:
    """Fetch daily OHLCV bars with dynamic universe fallback and chunked downloads.

    The public return schema is intentionally compatible with the existing cleaner:
    Date, Open, High, Low, Close, Adj Close, Volume, ticker.
    """

    resolved_tickers = resolve_tickers(tickers)
    liquidity_floor = settings.min_daily_volume if min_volume is None else min_volume

    logger.info(
        "Fetching EOD prices for {} tickers, period={}, liquidity_floor={}",
        len(resolved_tickers),
        period,
        liquidity_floor,
    )

    frames: list[pd.DataFrame] = []
    for chunk_start, chunk_end in iter_date_chunks(period=period, chunk_years=chunk_years):
        chunk = _download_price_chunk(resolved_tickers, chunk_start, chunk_end)
        if chunk.empty:
            logger.warning("No yfinance data returned for {} to {}", chunk_start, chunk_end)
            continue

        chunk = apply_liquidity_filter(chunk, min_volume=liquidity_floor)
        if not chunk.empty:
            frames.append(chunk)

    if not frames:
        raise ValueError("No price data survived fetching and liquidity filtering")

    prices = pd.concat(frames, ignore_index=True)
    prices = prices.drop_duplicates(subset=["ticker", "Date"], keep="last")
    prices = prices.sort_values(["ticker", "Date"]).reset_index(drop=True)
    logger.info("Fetched {} liquid EOD rows", len(prices))
    return prices


def resolve_tickers(tickers: list[str] | None = None) -> list[str]:
    if tickers:
        resolved = sorted({normalize_ticker(ticker) for ticker in tickers if ticker.strip()})
        logger.info("Using explicit ticker universe with {} symbols", len(resolved))
        return resolved

    resolved = fetch_active_universe()
    if not resolved:
        raise ValueError("No explicit tickers provided and no active database universe found")

    logger.info("Using dynamic database universe with {} symbols", len(resolved))
    return resolved


def iter_date_chunks(period: str, chunk_years: int = 1, today: date | None = None) -> Iterator[tuple[date, date]]:
    if chunk_years < 1:
        raise ValueError("chunk_years must be >= 1")

    end_date = today or date.today()
    start_date = _period_start_date(period, end_date)
    chunk_days = 366 * chunk_years

    cursor = start_date
    while cursor <= end_date:
        chunk_end = min(cursor + timedelta(days=chunk_days), end_date + timedelta(days=1))
        yield cursor, chunk_end
        cursor = chunk_end


def apply_liquidity_filter(prices: pd.DataFrame, min_volume: int | None = None) -> pd.DataFrame:
    if prices.empty:
        return prices

    liquidity_floor = settings.min_daily_volume if min_volume is None else min_volume
    frame = prices.copy()
    frame["Volume"] = pd.to_numeric(frame["Volume"], errors="coerce").fillna(0).astype("int64")
    before = len(frame)
    frame = frame[frame["Volume"] >= liquidity_floor]
    removed = before - len(frame)
    if removed:
        logger.info("Liquidity filter removed {} rows below {} shares/day", removed, liquidity_floor)
    return frame.reset_index(drop=True)


def calculate_moomoo_fee_breakdown(
    side: str,
    transaction_amount: Decimal,
    quantity: Decimal,
) -> FeeBreakdown:
    side = side.upper()
    if side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")
    if transaction_amount < 0 or quantity < 0:
        raise ValueError("transaction_amount and quantity must be non-negative")

    is_fractional = quantity < Decimal("1")
    if is_fractional:
        platform_fee = min(transaction_amount * Decimal("0.0099"), Decimal("0.99"))
        return FeeBreakdown(
            mode="fractional",
            commission_fee=Decimal("0"),
            platform_fee=_money(platform_fee),
            settlement_fee=Decimal("0"),
            sec_fee=Decimal("0"),
            taf_fee=Decimal("0"),
            cat_fee=Decimal("0"),
        )

    commission_fee = transaction_amount * Decimal("0.0003")
    platform_fee = Decimal("0.99")
    settlement_fee = min(Decimal("0.003") * quantity, transaction_amount * Decimal("0.01"))
    cat_fee = Decimal("0.000003") * quantity
    sec_fee = Decimal("0")
    taf_fee = Decimal("0")

    if side == "SELL":
        sec_fee = max(transaction_amount * Decimal("0.0000206"), Decimal("0.01"))
        taf_fee = min(max(Decimal("0.000195") * quantity, Decimal("0.01")), Decimal("9.79"))

    return FeeBreakdown(
        mode="standard",
        commission_fee=_money(commission_fee),
        platform_fee=_money(platform_fee),
        settlement_fee=_money(settlement_fee),
        sec_fee=_money(sec_fee),
        taf_fee=_money(taf_fee),
        cat_fee=_money(cat_fee),
    )


def calculate_fee_inclusive_quantity(
    current_cash: Decimal | float | str,
    price: Decimal | float | str,
    side: str = "BUY",
    max_position_fraction: Decimal | float | str | None = None,
) -> SizingDecision:
    cash = _decimal(current_cash)
    execution_price = _decimal(price)
    side = side.upper()
    allocation_fraction = (
        _decimal(max_position_fraction) if max_position_fraction is not None else _decimal(settings.max_position_fraction)
    )
    gross_budget = _money(cash * allocation_fraction)

    if execution_price <= 0:
        return _rejected(side, "fractional", gross_budget, Decimal("0"), execution_price, "invalid_price")
    if side == "BUY" and gross_budget < MIN_BUY_NOTIONAL:
        return _rejected(side, "fractional", gross_budget, Decimal("0"), execution_price, "below_min_buy_notional")

    estimated_quantity = gross_budget / execution_price
    mode = "fractional" if estimated_quantity < Decimal("1") else "standard"
    fees = calculate_moomoo_fee_breakdown(side=side, transaction_amount=gross_budget, quantity=estimated_quantity)
    net_budget = max(gross_budget - fees.total_fees, Decimal("0"))
    quantity = _quantity(net_budget / execution_price)

    fees = calculate_moomoo_fee_breakdown(side=side, transaction_amount=net_budget, quantity=quantity)
    net_budget = max(gross_budget - fees.total_fees, Decimal("0"))
    quantity = _quantity(net_budget / execution_price)
    fee_ratio = fees.total_fees / gross_budget if gross_budget > 0 else Decimal("1")

    veto_reason = None
    approved = True
    if quantity < MIN_ORDER_QUANTITY:
        approved = False
        veto_reason = "below_min_order_quantity"
    elif side == "BUY" and net_budget < MIN_BUY_NOTIONAL:
        approved = False
        veto_reason = "below_min_buy_notional_after_fees"
    elif fee_ratio > MAX_FEE_RATIO:
        approved = False
        veto_reason = "fee_ratio_exceeds_3_percent"

    return SizingDecision(
        approved=approved,
        side=side,  # type: ignore[arg-type]
        mode=fees.mode,
        gross_budget=gross_budget,
        net_budget=_money(net_budget),
        price=execution_price,
        quantity=quantity if approved else Decimal("0"),
        fee_breakdown=fees,
        fee_ratio=fee_ratio.quantize(Decimal("0.000001")),
        veto_reason=veto_reason,
    )


def _download_price_chunk(tickers: list[str], start_date: date, end_date: date) -> pd.DataFrame:
    logger.info("Downloading yfinance chunk {} to {}", start_date, end_date)
    raw = yf.download(
        tickers=tickers,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        interval="1d",
        auto_adjust=False,
        group_by="ticker",
        progress=False,
        threads=True,
    )

    if raw.empty:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for ticker in tickers:
        ticker_frame = _extract_ticker_frame(raw, ticker, len(tickers))
        if ticker_frame.empty:
            logger.warning("Ticker {} missing from yfinance chunk {} to {}", ticker, start_date, end_date)
            continue

        ticker_frame = ticker_frame.reset_index()
        ticker_frame["ticker"] = ticker
        frames.append(ticker_frame)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _extract_ticker_frame(raw: pd.DataFrame, ticker: str, ticker_count: int) -> pd.DataFrame:
    if ticker_count == 1:
        return raw.copy()
    if not isinstance(raw.columns, pd.MultiIndex):
        return pd.DataFrame()
    if ticker not in raw.columns.get_level_values(0):
        return pd.DataFrame()
    return raw[ticker].copy()


def _period_start_date(period: str, end_date: date) -> date:
    normalized = period.lower().strip()
    if normalized == "ytd":
        return date(end_date.year, 1, 1)
    if normalized == "max":
        return date(1970, 1, 1)
    if normalized not in PERIOD_TO_DAYS:
        raise ValueError(f"Unsupported period '{period}'. Use one of {sorted([*PERIOD_TO_DAYS, 'ytd', 'max'])}")
    return end_date - timedelta(days=PERIOD_TO_DAYS[normalized])


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"))


def _quantity(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_DOWN)


def _decimal(value: Decimal | float | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _rejected(
    side: str,
    mode: str,
    gross_budget: Decimal,
    net_budget: Decimal,
    price: Decimal,
    reason: str,
) -> SizingDecision:
    fees = FeeBreakdown(mode=mode)  # type: ignore[arg-type]
    return SizingDecision(
        approved=False,
        side=side,  # type: ignore[arg-type]
        mode=mode,  # type: ignore[arg-type]
        gross_budget=gross_budget,
        net_budget=net_budget,
        price=price if price > 0 else Decimal("0.000001"),
        quantity=Decimal("0"),
        fee_breakdown=fees,
        fee_ratio=Decimal("1"),
        veto_reason=reason,
    )
