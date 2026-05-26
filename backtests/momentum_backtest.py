from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sqlalchemy import text

from app.db.connection import get_engine
from app.utils.config import settings


@dataclass(frozen=True)
class BacktestConfig:
    tickers: list[str]
    initial_cash: float
    holding_days: int
    max_position_fraction: float
    trade_cost_bps: float


def load_price_signal_data(tickers: list[str]) -> pd.DataFrame:
    query = text(
        """
        SELECT
            a.ticker,
            p.trading_date,
            p.adjusted_close,
            s.signal,
            s.confidence
        FROM daily_prices p
        JOIN assets a ON a.id = p.asset_id
        LEFT JOIN model_signals s
            ON s.asset_id = p.asset_id
            AND s.trading_date = p.trading_date
            AND s.model_name = 'cross_sectional_momentum_v1'
        WHERE a.ticker = ANY(:tickers)
        ORDER BY a.ticker, p.trading_date;
        """
    )
    return pd.read_sql(query, get_engine(), params={"tickers": tickers})


def run_backtest(data: pd.DataFrame, config: BacktestConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    frame = data.copy()
    frame["trading_date"] = pd.to_datetime(frame["trading_date"])
    frame["adjusted_close"] = pd.to_numeric(frame["adjusted_close"], errors="coerce")
    frame = frame.dropna(subset=["ticker", "trading_date", "adjusted_close"])
    frame = frame.sort_values(["trading_date", "ticker"]).reset_index(drop=True)

    price_lookup = {
        ticker: group.sort_values("trading_date").reset_index(drop=True)
        for ticker, group in frame.groupby("ticker")
    }

    cash = config.initial_cash
    open_positions: list[dict[str, object]] = []
    trades: list[dict[str, object]] = []
    equity_rows: list[dict[str, object]] = []

    for current_date, day_rows in frame.groupby("trading_date"):
        open_positions, closed_trades, cash = close_due_positions(open_positions, price_lookup, current_date, cash)
        trades.extend(closed_trades)

        day_signals = day_rows[day_rows["signal"] == "BUY"].sort_values("confidence", ascending=False)
        for signal in day_signals.itertuples(index=False):
            if any(position["ticker"] == signal.ticker for position in open_positions):
                continue

            entry_price = float(signal.adjusted_close)
            max_notional = cash * config.max_position_fraction
            quantity = int(max_notional // entry_price)
            if quantity < 1:
                continue

            entry_cost = quantity * entry_price * (1 + config.trade_cost_bps / 10_000)
            if entry_cost > cash:
                continue

            cash -= entry_cost
            open_positions.append(
                {
                    "ticker": signal.ticker,
                    "entry_date": current_date,
                    "entry_price": entry_price,
                    "quantity": quantity,
                    "confidence": float(signal.confidence) if pd.notna(signal.confidence) else np.nan,
                    "exit_after_rows": config.holding_days,
                }
            )

        equity = cash + mark_to_market(open_positions, price_lookup, current_date)
        equity_rows.append({"trading_date": current_date, "equity": equity, "cash": cash, "open_positions": len(open_positions)})

    if not frame.empty:
        final_date = frame["trading_date"].max()
        open_positions, closed_trades, cash = close_due_positions(
            open_positions,
            price_lookup,
            final_date,
            cash,
            force=True,
        )
        trades.extend(closed_trades)

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_rows)
    metrics = calculate_metrics(trades_df, equity_df, config.initial_cash)
    return trades_df, equity_df, metrics


def close_due_positions(
    open_positions: list[dict[str, object]],
    price_lookup: dict[str, pd.DataFrame],
    current_date: pd.Timestamp,
    cash: float,
    force: bool = False,
) -> tuple[list[dict[str, object]], list[dict[str, object]], float]:
    still_open: list[dict[str, object]] = []
    closed: list[dict[str, object]] = []

    for position in open_positions:
        ticker = str(position["ticker"])
        prices = price_lookup[ticker]
        entry_idx = prices.index[prices["trading_date"] == position["entry_date"]]
        current_idx = prices.index[prices["trading_date"] == current_date]
        if len(entry_idx) == 0 or len(current_idx) == 0:
            still_open.append(position)
            continue

        held_rows = int(current_idx[0] - entry_idx[0])
        should_close = force or held_rows >= int(position["exit_after_rows"])
        if not should_close:
            still_open.append(position)
            continue

        exit_price = float(prices.loc[current_idx[0], "adjusted_close"])
        quantity = int(position["quantity"])
        proceeds = quantity * exit_price
        cash += proceeds
        pnl = quantity * (exit_price - float(position["entry_price"]))
        closed.append(
            {
                "ticker": ticker,
                "entry_date": position["entry_date"],
                "exit_date": current_date,
                "holding_days": held_rows,
                "entry_price": float(position["entry_price"]),
                "exit_price": exit_price,
                "quantity": quantity,
                "pnl": pnl,
                "return_pct": exit_price / float(position["entry_price"]) - 1,
                "confidence": position["confidence"],
            }
        )

    return still_open, closed, cash


def mark_to_market(
    open_positions: list[dict[str, object]],
    price_lookup: dict[str, pd.DataFrame],
    current_date: pd.Timestamp,
) -> float:
    total = 0.0
    for position in open_positions:
        ticker = str(position["ticker"])
        prices = price_lookup[ticker]
        matching = prices[prices["trading_date"] <= current_date]
        if matching.empty:
            continue
        total += int(position["quantity"]) * float(matching.iloc[-1]["adjusted_close"])
    return total


def calculate_metrics(trades: pd.DataFrame, equity: pd.DataFrame, initial_cash: float) -> pd.Series:
    if equity.empty:
        return pd.Series(dtype=float)

    final_equity = float(equity.iloc[-1]["equity"])
    total_return = final_equity / initial_cash - 1
    daily_returns = equity["equity"].pct_change().dropna()
    sharpe = np.nan
    if daily_returns.std() > 0:
        sharpe = daily_returns.mean() / daily_returns.std() * np.sqrt(252)

    rolling_peak = equity["equity"].cummax()
    drawdown = equity["equity"] / rolling_peak - 1
    max_drawdown = float(drawdown.min())

    if trades.empty:
        win_rate = 0.0
        profit_factor = np.nan
        avg_holding_days = np.nan
    else:
        win_rate = float((trades["pnl"] > 0).mean())
        gross_profit = float(trades.loc[trades["pnl"] > 0, "pnl"].sum())
        gross_loss = abs(float(trades.loc[trades["pnl"] < 0, "pnl"].sum()))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf
        avg_holding_days = float(trades["holding_days"].mean())

    return pd.Series(
        {
            "initial_cash": initial_cash,
            "final_equity": final_equity,
            "total_return_pct": total_return * 100,
            "max_drawdown_pct": max_drawdown * 100,
            "sharpe_ratio": sharpe,
            "trades": float(len(trades)),
            "avg_holding_days": avg_holding_days,
            "win_rate_pct": win_rate * 100,
            "profit_factor": profit_factor,
        }
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest momentum BUY signals from Supabase.")
    parser.add_argument("--tickers", nargs="*", default=settings.ticker_list)
    parser.add_argument("--initial-cash", type=float, default=settings.initial_capital_usd)
    parser.add_argument("--holding-days", type=int, default=5)
    parser.add_argument("--max-position-fraction", type=float, default=settings.max_position_fraction)
    parser.add_argument("--trade-cost-bps", type=float, default=5.0)
    parser.add_argument("--show-trades", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = BacktestConfig(
        tickers=[ticker.upper() for ticker in args.tickers],
        initial_cash=args.initial_cash,
        holding_days=args.holding_days,
        max_position_fraction=args.max_position_fraction,
        trade_cost_bps=args.trade_cost_bps,
    )
    data = load_price_signal_data(config.tickers)
    trades, equity, metrics = run_backtest(data, config)

    print("\nBacktest metrics")
    print(metrics.round(4).to_string())

    if trades.empty:
        print("\nNo trades were generated. Try a longer extraction period or lower signal thresholds.")
    else:
        print(f"\nLatest {min(args.show_trades, len(trades))} trades")
        print(trades.tail(args.show_trades).round(4).to_string(index=False))

    if not equity.empty:
        print("\nLatest equity")
        print(equity.tail(5).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
