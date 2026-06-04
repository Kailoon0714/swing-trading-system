from __future__ import annotations

import argparse
from decimal import Decimal
from itertools import product
from pathlib import Path

import pandas as pd

from app.utils.config import settings
from backtests.momentum_backtest import BacktestConfig, load_benchmark_price_data, load_price_signal_data, run_backtest


def parse_decimal_grid(values: str) -> list[Decimal]:
    return [Decimal(item.strip()) for item in values.split(",") if item.strip()]


def parse_int_grid(values: str) -> list[int]:
    return [int(item.strip()) for item in values.split(",") if item.strip()]


def run_parameter_sweep(
    tickers: list[str],
    benchmark_tickers: list[str],
    initial_cash: Decimal,
    holding_days: list[int],
    stop_loss_pcts: list[Decimal],
    take_profit_pcts: list[Decimal],
    max_position_fractions: list[Decimal],
    cooldown_days: list[int],
    max_drawdown_stop_pcts: list[Decimal],
) -> pd.DataFrame:
    data = load_price_signal_data(tickers)
    benchmark_data = load_benchmark_price_data(benchmark_tickers)
    rows: list[dict[str, float | int | str]] = []

    for holding, stop_loss, take_profit, max_fraction, cooldown, drawdown_stop in product(
        holding_days,
        stop_loss_pcts,
        take_profit_pcts,
        max_position_fractions,
        cooldown_days,
        max_drawdown_stop_pcts,
    ):
        config = BacktestConfig(
            tickers=tickers,
            initial_cash=initial_cash,
            holding_days=holding,
            max_position_fraction=max_fraction,
            stop_loss_pct=stop_loss,
            take_profit_pct=take_profit,
            cooldown_days=cooldown,
            max_drawdown_stop_pct=drawdown_stop,
            benchmark_tickers=benchmark_tickers,
        )
        trades, _equity, metrics = run_backtest(data, config, benchmark_data)
        row = metrics.to_dict()
        row.update(
            {
                "holding_days": holding,
                "stop_loss_pct": float(stop_loss),
                "take_profit_pct": float(take_profit),
                "max_position_fraction": float(max_fraction),
                "cooldown_days": cooldown,
                "max_drawdown_stop_pct": float(drawdown_stop),
                "score": calculate_score(metrics),
                "stop_loss_exits": _count_exit_reason(trades, "STOP_LOSS"),
                "take_profit_exits": _count_exit_reason(trades, "TAKE_PROFIT"),
                "time_exits": _count_exit_reason(trades, "TIME_EXIT"),
            }
        )
        rows.append(row)

    results = pd.DataFrame(rows)
    if results.empty:
        return results
    return results.sort_values(
        ["score", "total_return_pct", "max_drawdown_pct", "profit_factor"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def calculate_score(metrics: pd.Series) -> float:
    total_return = float(metrics.get("total_return_pct", 0.0))
    max_drawdown = abs(float(metrics.get("max_drawdown_pct", 0.0)))
    profit_factor = float(metrics.get("profit_factor", 0.0))
    trades = float(metrics.get("trades", 0.0))
    fees = float(metrics.get("total_fees", 0.0))

    if pd.isna(profit_factor):
        profit_factor = 0.0
    return total_return - (0.75 * max_drawdown) + (5.0 * profit_factor) - (0.03 * trades) - (0.05 * fees)


def _count_exit_reason(trades: pd.DataFrame, reason: str) -> int:
    if trades.empty or "exit_reason" not in trades.columns:
        return 0
    return int((trades["exit_reason"] == reason).sum())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a parameter sweep over the fee-aware momentum backtest.")
    parser.add_argument("--tickers", nargs="*", default=settings.ticker_list)
    parser.add_argument("--benchmark-tickers", nargs="*", default=["SPY", "QQQ"])
    parser.add_argument("--initial-cash", type=Decimal, default=Decimal(str(settings.initial_capital_usd)))
    parser.add_argument("--holding-days", default="20,40,60,90,120")
    parser.add_argument("--stop-loss-pcts", default="0,0.04,0.08,0.12")
    parser.add_argument("--take-profit-pcts", default="0,0.08,0.12,0.20")
    parser.add_argument("--max-position-fractions", default="0.10,0.15,0.20")
    parser.add_argument("--cooldown-days", default="0,20,40")
    parser.add_argument("--max-drawdown-stop-pcts", default="0")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--output", default="reports/parameter_sweep.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = run_parameter_sweep(
        tickers=[ticker.upper() for ticker in args.tickers],
        benchmark_tickers=[ticker.upper() for ticker in args.benchmark_tickers],
        initial_cash=args.initial_cash,
        holding_days=parse_int_grid(args.holding_days),
        stop_loss_pcts=parse_decimal_grid(args.stop_loss_pcts),
        take_profit_pcts=parse_decimal_grid(args.take_profit_pcts),
        max_position_fractions=parse_decimal_grid(args.max_position_fractions),
        cooldown_days=parse_int_grid(args.cooldown_days),
        max_drawdown_stop_pcts=parse_decimal_grid(args.max_drawdown_stop_pcts),
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_path, index=False)

    display_columns = [
        "score",
        "holding_days",
        "stop_loss_pct",
        "take_profit_pct",
        "max_position_fraction",
        "cooldown_days",
        "max_drawdown_stop_pct",
        "final_equity",
        "total_return_pct",
        "benchmark_equal_weight_return_pct",
        "alpha_vs_equal_weight_pct",
        "max_drawdown_pct",
        "trades",
        "profit_factor",
        "total_fees",
        "guardrail_triggered",
        "stop_loss_exits",
        "take_profit_exits",
        "time_exits",
    ]
    print(f"\nSaved sweep results to {output_path}")
    print(f"\nTop {min(args.top, len(results))} parameter sets")
    print(results[display_columns].head(args.top).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
