from __future__ import annotations

import argparse
from decimal import Decimal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from app.db.connection import get_engine
from app.db.models import ClosedTrade, FeeBreakdown
from app.etl.fetch_prices import calculate_fee_inclusive_quantity, calculate_moomoo_fee_breakdown
from app.utils.config import settings


class BacktestConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tickers: list[str]
    initial_cash: Decimal
    holding_days: int
    max_position_fraction: Decimal
    stop_loss_pct: Decimal
    take_profit_pct: Decimal
    cooldown_days: int = 0
    max_drawdown_stop_pct: Decimal = Decimal("0")
    benchmark_tickers: list[str] = ["SPY", "QQQ"]


def load_price_signal_data(tickers: list[str]) -> pd.DataFrame:
    query = text(
        """
        WITH ranked_signals AS (
            SELECT
                s.*,
                ROW_NUMBER() OVER (
                    PARTITION BY s.asset_id, s.trading_date
                    ORDER BY CASE
                        WHEN s.model_name = 'cross_sectional_momentum_v2' THEN 1
                        WHEN s.model_name = 'cross_sectional_momentum_v1' THEN 2
                        ELSE 3
                    END
                ) AS model_priority
            FROM model_signals s
            WHERE s.model_name IN ('cross_sectional_momentum_v2', 'cross_sectional_momentum_v1')
        )
        SELECT
            a.ticker,
            COALESCE(s.sector, a.sector, 'Unknown') AS sector,
            COALESCE(s.industry, a.industry, 'Unknown') AS industry,
            p.trading_date,
            p.adjusted_close,
            p.volume,
            f.rolling_volatility_14d,
            s.id AS signal_id,
            s.signal,
            s.confidence,
            s.rank_in_sector
        FROM daily_prices p
        JOIN assets a ON a.id = p.asset_id
        LEFT JOIN model_features f
            ON f.asset_id = p.asset_id
            AND f.trading_date = p.trading_date
        LEFT JOIN ranked_signals s
            ON s.asset_id = p.asset_id
            AND s.trading_date = p.trading_date
            AND s.model_priority = 1
        WHERE a.ticker = ANY(:tickers)
        ORDER BY a.ticker, p.trading_date;
        """
    )
    return pd.read_sql(query, get_engine(), params={"tickers": tickers})


def load_benchmark_price_data(tickers: list[str]) -> pd.DataFrame:
    if not tickers:
        return pd.DataFrame()
    query = text(
        """
        SELECT
            a.ticker,
            p.trading_date,
            p.adjusted_close
        FROM daily_prices p
        JOIN assets a ON a.id = p.asset_id
        WHERE a.ticker = ANY(:tickers)
        ORDER BY a.ticker, p.trading_date;
        """
    )
    return pd.read_sql(query, get_engine(), params={"tickers": tickers})


def run_backtest(
    data: pd.DataFrame,
    config: BacktestConfig,
    benchmark_data: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    frame = prepare_backtest_frame(data, config)
    trades_source = build_trade_source(frame, config)
    trades = materialize_closed_trades(trades_source)
    trades_df = closed_trades_to_frame(trades)
    equity = build_equity_curve(frame, trades_df, config.initial_cash)
    trades_df, equity = apply_drawdown_guardrail(frame, trades_df, equity, config)
    metrics = calculate_metrics(trades_df, equity, config.initial_cash, frame, benchmark_data)
    return trades_df, equity, metrics


def prepare_backtest_frame(data: pd.DataFrame, config: BacktestConfig) -> pd.DataFrame:
    frame = data.copy()
    frame["trading_date"] = pd.to_datetime(frame["trading_date"])
    numeric_columns = ["adjusted_close", "volume", "rolling_volatility_14d", "confidence"]
    frame[numeric_columns] = frame[numeric_columns].apply(pd.to_numeric, errors="coerce")
    frame = frame.dropna(subset=["ticker", "trading_date", "adjusted_close"])
    frame = frame.sort_values(["ticker", "trading_date"]).reset_index(drop=True)
    frame["price_row_number"] = frame.groupby("ticker").cumcount()
    add_risk_managed_exits(frame, config)
    return frame


def add_risk_managed_exits(frame: pd.DataFrame, config: BacktestConfig) -> None:
    horizons = range(1, config.holding_days + 1)
    future_close = pd.concat(
        [frame.groupby("ticker")["adjusted_close"].shift(-h).rename(h) for h in horizons],
        axis=1,
    )
    future_dates = pd.concat(
        [frame.groupby("ticker")["trading_date"].shift(-h).rename(h) for h in horizons],
        axis=1,
    )

    entry = frame["adjusted_close"].to_numpy(dtype=float)[:, None]
    stop_level = entry * (1 - float(config.stop_loss_pct))
    take_level = entry * (1 + float(config.take_profit_pct))
    price_matrix = future_close.to_numpy(dtype=float)

    if config.stop_loss_pct > 0:
        stop_hits = price_matrix <= stop_level
    else:
        stop_hits = np.zeros_like(price_matrix, dtype=bool)

    if config.take_profit_pct > 0:
        take_hits = price_matrix >= take_level
    else:
        take_hits = np.zeros_like(price_matrix, dtype=bool)
    any_stop = stop_hits.any(axis=1)
    any_take = take_hits.any(axis=1)

    no_hit_value = config.holding_days + 1
    first_stop = np.where(any_stop, stop_hits.argmax(axis=1) + 1, no_hit_value)
    first_take = np.where(any_take, take_hits.argmax(axis=1) + 1, no_hit_value)
    first_exit = np.minimum(np.minimum(first_stop, first_take), config.holding_days)

    reason = np.where(
        first_stop <= first_take,
        "STOP_LOSS",
        "TAKE_PROFIT",
    )
    reason = np.where((first_stop == no_hit_value) & (first_take == no_hit_value), "TIME_EXIT", reason)

    exit_price = np.full(len(frame), np.nan)
    exit_date = pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns]")
    for step in horizons:
        mask = first_exit == step
        exit_price[mask] = future_close.loc[mask, step]
        exit_date.loc[mask] = future_dates.loc[mask, step]

    frame["exit_step"] = first_exit
    frame["exit_reason"] = reason
    frame["exit_date"] = exit_date
    frame["exit_price"] = exit_price


def build_trade_source(frame: pd.DataFrame, config: BacktestConfig) -> pd.DataFrame:
    signals = frame[
        (frame["signal"] == "BUY")
        & frame["exit_price"].notna()
        & frame["rolling_volatility_14d"].notna()
        & (frame["rolling_volatility_14d"] > 0)
    ].copy()
    if signals.empty:
        return signals

    signals["holding_bucket"] = (signals["price_row_number"] // config.holding_days).astype(int)
    cooldown_window = max(1, config.holding_days + config.cooldown_days)
    signals["cooldown_bucket"] = (signals["price_row_number"] // cooldown_window).astype(int)
    signals = (
        signals.sort_values(["ticker", "cooldown_bucket", "confidence"], ascending=[True, True, False])
        .drop_duplicates(subset=["ticker", "cooldown_bucket"], keep="first")
        .sort_values(["trading_date", "confidence"], ascending=[True, False])
        .groupby("trading_date", group_keys=False)
        .head(settings.max_open_positions)
        .copy()
    )
    if signals.empty:
        return signals

    signals["inverse_volatility"] = 1 / signals["rolling_volatility_14d"]
    inverse_sum = signals.groupby("trading_date")["inverse_volatility"].transform("sum")
    signals["scaled_fraction"] = float(config.max_position_fraction)
    signals["scaled_fraction"] = signals["scaled_fraction"] * signals["inverse_volatility"] / inverse_sum

    sizing = [
        calculate_fee_inclusive_quantity(
            current_cash=config.initial_cash,
            price=row.adjusted_close,
            side="BUY",
            max_position_fraction=row.scaled_fraction,
        )
        for row in signals.itertuples(index=False)
    ]
    signals["approved"] = [decision.approved for decision in sizing]
    signals["quantity"] = [float(decision.quantity) for decision in sizing]
    signals["buy_fees"] = [float(decision.fee_breakdown.total_fees) for decision in sizing]
    signals["gross_budget"] = [float(decision.gross_budget) for decision in sizing]
    signals["net_budget"] = [float(decision.net_budget) for decision in sizing]
    signals["fee_ratio"] = [float(decision.fee_ratio) for decision in sizing]
    signals["veto_reason"] = [decision.veto_reason for decision in sizing]
    signals = signals[signals["approved"]].copy()
    if signals.empty:
        return signals

    round_trip_fee_ratios: list[float] = []
    for row in signals.itertuples(index=False):
        quantity = Decimal(str(row.quantity))
        sell_notional = quantity * Decimal(str(row.exit_price))
        sell_fees = calculate_moomoo_fee_breakdown("SELL", sell_notional, quantity)
        round_trip_fees = Decimal(str(row.buy_fees)) + sell_fees.total_fees
        gross_entry = quantity * Decimal(str(row.adjusted_close))
        round_trip_fee_ratios.append(float(round_trip_fees / gross_entry if gross_entry > 0 else Decimal("1")))

    signals["round_trip_fee_ratio"] = round_trip_fee_ratios
    signals = signals[signals["round_trip_fee_ratio"] <= float(settings.max_fee_ratio)].copy()
    return signals


def materialize_closed_trades(trade_source: pd.DataFrame) -> list[ClosedTrade]:
    if trade_source.empty:
        return []

    records: list[ClosedTrade] = []
    for row in trade_source.itertuples(index=False):
        quantity = Decimal(str(row.quantity))
        entry_price = Decimal(str(row.adjusted_close))
        exit_price = Decimal(str(row.exit_price))
        gross_sell = quantity * exit_price
        sell_fees = calculate_moomoo_fee_breakdown("SELL", gross_sell, quantity)
        combined_fees = FeeBreakdown(
            mode="fractional" if quantity < Decimal("1") else "standard",
            commission_fee=Decimal("0"),
            platform_fee=Decimal(str(row.buy_fees)) + sell_fees.platform_fee,
            settlement_fee=sell_fees.settlement_fee,
            sec_fee=sell_fees.sec_fee,
            taf_fee=sell_fees.taf_fee,
            cat_fee=sell_fees.cat_fee,
        )
        pnl = quantity * (exit_price - entry_price) - combined_fees.total_fees
        records.append(
            ClosedTrade(
                ticker=row.ticker,
                side="BUY",
                entry_date=row.trading_date.date(),
                exit_date=row.exit_date.date(),
                exit_reason=row.exit_reason,
                holding_trading_days=int(row.exit_step),
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                gross_notional=quantity * entry_price,
                net_notional=Decimal(str(row.net_budget)),
                fees=combined_fees,
                pnl=pnl,
                return_pct=pnl / (quantity * entry_price),
            )
        )
    return records


def closed_trades_to_frame(trades: list[ClosedTrade]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame()
    frame = pd.DataFrame([trade.model_dump(mode="json") for trade in trades])
    frame["entry_date"] = pd.to_datetime(frame["entry_date"])
    frame["exit_date"] = pd.to_datetime(frame["exit_date"])
    numeric_columns = ["entry_price", "exit_price", "quantity", "gross_notional", "net_notional", "pnl", "return_pct"]
    frame[numeric_columns] = frame[numeric_columns].apply(pd.to_numeric, errors="coerce")
    frame["total_fees"] = frame["fees"].map(lambda value: float(value["total_fees"]))
    frame["holding_calendar_days"] = (frame["exit_date"] - frame["entry_date"]).dt.days
    return frame


def build_equity_curve(frame: pd.DataFrame, trades: pd.DataFrame, initial_cash: Decimal) -> pd.DataFrame:
    dates = pd.DataFrame({"trading_date": sorted(frame["trading_date"].dropna().unique())})
    if dates.empty:
        return dates.assign(equity=float(initial_cash), cash=float(initial_cash), open_positions=0)
    if trades.empty:
        return dates.assign(equity=float(initial_cash), cash=float(initial_cash), open_positions=0)

    pnl_by_exit = trades.groupby("exit_date", as_index=False)["pnl"].sum().rename(columns={"exit_date": "trading_date"})
    entries = trades.groupby("entry_date", as_index=False).size().rename(columns={"entry_date": "trading_date", "size": "entries"})
    exits = trades.groupby("exit_date", as_index=False).size().rename(columns={"exit_date": "trading_date", "size": "exits"})

    equity = dates.merge(pnl_by_exit, on="trading_date", how="left").merge(entries, on="trading_date", how="left").merge(exits, on="trading_date", how="left")
    equity[["pnl", "entries", "exits"]] = equity[["pnl", "entries", "exits"]].fillna(0)
    equity["equity"] = float(initial_cash) + equity["pnl"].cumsum()
    equity["cash"] = equity["equity"]
    equity["open_positions"] = (equity["entries"].cumsum() - equity["exits"].cumsum()).astype(int)
    return equity[["trading_date", "equity", "cash", "open_positions"]]


def apply_drawdown_guardrail(
    frame: pd.DataFrame,
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    config: BacktestConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if trades.empty or equity.empty or config.max_drawdown_stop_pct <= 0:
        return trades, equity

    drawdown = equity["equity"] / equity["equity"].cummax() - 1
    breach = equity.loc[drawdown <= -float(config.max_drawdown_stop_pct), "trading_date"]
    if breach.empty:
        equity["guardrail_triggered"] = False
        return trades, equity

    breach_date = breach.iloc[0]
    filtered_trades = trades[trades["entry_date"] <= breach_date].copy()
    guarded_equity = build_equity_curve(frame, filtered_trades, config.initial_cash)
    guarded_equity["guardrail_triggered"] = guarded_equity["trading_date"] >= breach_date
    return filtered_trades, guarded_equity


def calculate_metrics(
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    initial_cash: Decimal,
    frame: pd.DataFrame | None = None,
    benchmark_frame: pd.DataFrame | None = None,
) -> pd.Series:
    if equity.empty:
        return pd.Series(dtype=float)

    initial = float(initial_cash)
    final_equity = float(equity.iloc[-1]["equity"])
    daily_returns = equity["equity"].pct_change().dropna()
    sharpe = np.nan if daily_returns.std() == 0 else daily_returns.mean() / daily_returns.std() * np.sqrt(252)
    drawdown = equity["equity"] / equity["equity"].cummax() - 1

    if trades.empty:
        win_rate = 0.0
        profit_factor = np.nan
        avg_holding_days = np.nan
        total_fees = 0.0
    else:
        win_rate = float((trades["pnl"] > 0).mean())
        gross_profit = float(trades.loc[trades["pnl"] > 0, "pnl"].sum())
        gross_loss = abs(float(trades.loc[trades["pnl"] < 0, "pnl"].sum()))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf
        avg_holding_days = float(trades["holding_trading_days"].mean())
        total_fees = float(trades["total_fees"].sum())

    benchmark_return = calculate_equal_weight_benchmark_return(benchmark_frame, trades)
    if pd.isna(benchmark_return):
        benchmark_return = calculate_equal_weight_benchmark_return(frame, trades)
    total_return = (final_equity / initial - 1) * 100
    guardrail_triggered = bool(equity.get("guardrail_triggered", pd.Series([False])).any())

    return pd.Series(
        {
            "initial_cash": initial,
            "final_equity": final_equity,
            "total_return_pct": total_return,
            "benchmark_equal_weight_return_pct": benchmark_return,
            "alpha_vs_equal_weight_pct": total_return - benchmark_return if not pd.isna(benchmark_return) else np.nan,
            "max_drawdown_pct": float(drawdown.min()) * 100,
            "sharpe_ratio": sharpe,
            "trades": float(len(trades)),
            "avg_holding_days": avg_holding_days,
            "win_rate_pct": win_rate * 100,
            "profit_factor": profit_factor,
            "total_fees": total_fees,
            "guardrail_triggered": guardrail_triggered,
        }
    )


def calculate_equal_weight_benchmark_return(frame: pd.DataFrame | None, trades: pd.DataFrame) -> float:
    if frame is None or frame.empty:
        return np.nan

    benchmark_frame = frame.copy()
    benchmark_frame["trading_date"] = pd.to_datetime(benchmark_frame["trading_date"])
    if not trades.empty:
        start_date = pd.Timestamp(trades["entry_date"].min())
        end_date = pd.Timestamp(trades["exit_date"].max())
        benchmark_frame = benchmark_frame[
            (benchmark_frame["trading_date"] >= start_date) & (benchmark_frame["trading_date"] <= end_date)
        ]
        if benchmark_frame.empty:
            benchmark_frame = frame.copy()
            benchmark_frame["trading_date"] = pd.to_datetime(benchmark_frame["trading_date"])

    prices = (
        benchmark_frame.dropna(subset=["ticker", "trading_date", "adjusted_close"])
        .sort_values(["ticker", "trading_date"])
        .groupby("ticker")
        .agg(start_price=("adjusted_close", "first"), end_price=("adjusted_close", "last"))
    )
    if prices.empty:
        return np.nan

    returns = prices["end_price"] / prices["start_price"] - 1
    return float(returns.mean() * 100)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fee-aware vectorized backtest for momentum BUY signals from Supabase.")
    parser.add_argument("--tickers", nargs="*", default=settings.ticker_list)
    parser.add_argument("--initial-cash", type=Decimal, default=Decimal(str(settings.initial_capital_usd)))
    parser.add_argument("--holding-days", type=int, default=5)
    parser.add_argument("--max-position-fraction", type=Decimal, default=Decimal(str(settings.max_position_fraction)))
    parser.add_argument("--stop-loss-pct", type=Decimal, default=Decimal(str(settings.stop_loss_pct)))
    parser.add_argument("--take-profit-pct", type=Decimal, default=Decimal(str(settings.take_profit_pct)))
    parser.add_argument("--cooldown-days", type=int, default=0)
    parser.add_argument("--max-drawdown-stop-pct", type=Decimal, default=Decimal("0"))
    parser.add_argument("--benchmark-tickers", nargs="*", default=["SPY", "QQQ"])
    parser.add_argument("--show-trades", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = BacktestConfig(
        tickers=[ticker.upper() for ticker in args.tickers],
        initial_cash=args.initial_cash,
        holding_days=args.holding_days,
        max_position_fraction=args.max_position_fraction,
        stop_loss_pct=args.stop_loss_pct,
        take_profit_pct=args.take_profit_pct,
        cooldown_days=args.cooldown_days,
        max_drawdown_stop_pct=args.max_drawdown_stop_pct,
        benchmark_tickers=[ticker.upper() for ticker in args.benchmark_tickers],
    )
    data = load_price_signal_data(config.tickers)
    benchmark_data = load_benchmark_price_data(config.benchmark_tickers)
    trades, equity, metrics = run_backtest(data, config, benchmark_data)

    print("\nBacktest metrics")
    print(metrics.round(4).to_string())

    if trades.empty:
        print("\nNo trades were generated. Try refreshing v2 signals or lowering thresholds.")
    else:
        columns = [
            "ticker",
            "entry_date",
            "exit_date",
            "exit_reason",
            "holding_trading_days",
            "holding_calendar_days",
            "entry_price",
            "exit_price",
            "quantity",
            "pnl",
            "return_pct",
            "total_fees",
        ]
        print(f"\nLatest {min(args.show_trades, len(trades))} trades")
        print(trades[columns].tail(args.show_trades).round(4).to_string(index=False))

    if not equity.empty:
        print("\nLatest equity")
        print(equity.tail(5).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
