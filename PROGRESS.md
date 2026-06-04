# Swing Trading System Progress Log

Last updated: 2026-05-27

## Current State

The repository has been upgraded from the initial PoC into v2.0 core infrastructure with a fee-aware, sector-neutral strategy/backtest layer.

GitHub repository:

```text
https://github.com/Kailoon0714/swing-trading-system
```

## Completed

### Phase 0 - Initial MVP Scaffold

- Created modular Python repository structure.
- Added Supabase/PostgreSQL schema.
- Added yfinance daily EOD extraction.
- Added cleaning, feature engineering, momentum signal generation.
- Added Streamlit dashboard scaffold.
- Added GitHub Actions daily pipeline.
- Added basic tests.

### Phase 1 - Core Infrastructure and ETL v2.0

- Upgraded database schema for production-style trading records.
- Added sector and industry metadata fields.
- Changed trade `quantity` to `NUMERIC(20, 8)` for fractional shares.
- Added multi-layer fee logging fields:
  - commission fee
  - platform fee
  - settlement fee
  - SEC fee
  - TAF fee
  - CAT fee
  - total fees
  - fee ratio
- Added SQLAlchemy pooled connection setup.
- Added strict Pydantic models:
  - `ActivePosition`
  - `ClosedTrade`
  - `FeeBreakdown`
  - `SizingDecision`
  - `PriceBar`
- Added memory-safe year-by-year yfinance chunking.
- Added optional `--tickers` mode.
- Added dynamic universe fallback from active tickers in Supabase.
- Added liquidity filter.
- Added Moomoo Malaysia US equity fee-aware reverse sizing engine.

GitHub commit:

```text
e11a3f7 Implement v2 core infrastructure overhaul
```

### Phase 2 - Strategy and Backtest v2.0

- Added sector-neutral momentum ranking.
- Added liquidity-aware signal generation.
- Added v2 signal model name:

```text
cross_sectional_momentum_v2
```

- Added volatility-scaled position sizing.
- Replaced simple integer-share backtest with fractional, fee-aware backtest.
- Added Moomoo fee friction into simulated trades.
- Added round-trip fee veto.
- Updated backtest query to prefer v2 signals over v1 signals.
- Updated tests for v2 liquidity requirements.

GitHub commit:

```text
e28f705 Implement v2 sector-neutral fee-aware strategy backtest
```

## Data Loaded

10 years of data loaded into Supabase for:

```text
AAPL
MSFT
NVDA
LITE
```

Latest successful 10-year pipeline result:

```text
Fetched 10072 liquid EOD rows
Pipeline generated 10072 price rows
Pipeline generated 10072 feature rows
Pipeline generated 4030 signal rows
Database load committed
```

Command:

```powershell
python -m app.pipeline --tickers AAPL MSFT NVDA LITE --period 10y
```

## Verification

Tests currently pass:

```powershell
python -m pytest -q
```

Result:

```text
2 passed
```

Compilation check passed:

```powershell
python -m compileall app backtests tests
```

## Latest Backtest Findings

### Phase 3 Risk-Exit Tests

Implemented close-based stop-loss/take-profit exits in the fee-aware backtest.

New CLI options:

```powershell
--stop-loss-pct
--take-profit-pct
```

Tested variants:

```powershell
python -m backtests.momentum_backtest --tickers AAPL MSFT NVDA LITE --initial-cash 200 --holding-days 60 --stop-loss-pct 0.04 --take-profit-pct 0.08
python -m backtests.momentum_backtest --tickers AAPL MSFT NVDA LITE --initial-cash 200 --holding-days 60 --stop-loss-pct 0.08 --take-profit-pct 0.12
python -m backtests.momentum_backtest --tickers AAPL MSFT NVDA LITE --initial-cash 200 --holding-days 90 --stop-loss-pct 0.08 --take-profit-pct 0.15
```

Results:

```text
60D hold, 4% stop, 8% take profit:
Final equity:      105.41
Total return:      -47.30%
Max drawdown:      -48.90%
Trades:            117
Total fees:        79.13

60D hold, 8% stop, 12% take profit:
Final equity:      114.27
Total return:      -42.87%
Max drawdown:      -51.53%
Trades:            116
Total fees:        78.43

90D hold, 8% stop, 15% take profit:
Final equity:      166.50
Total return:      -16.75%
Max drawdown:      -29.87%
Trades:            81
Total fees:        56.14
```

Interpretation:

- Tight stops did not improve the strategy for the current four-ticker universe.
- The 90-day, wider stop/take-profit test reduced drawdown but still lost money.
- The previous 60-day time-exit-only test remains the best observed result so far, but its drawdown is too high.
- Next optimization should reduce trade count and add parameter sweeps before any paper trading.

### Phase 3 Parameter Sweep

Added a parameter sweep runner:

```powershell
python -m backtests.parameter_sweep --tickers AAPL MSFT NVDA LITE --holding-days 40,60,90,120 --stop-loss-pcts 0,0.08,0.12 --take-profit-pcts 0,0.12,0.20 --max-position-fractions 0.10,0.15,0.20 --top 12
```

Output:

```text
reports/parameter_sweep.csv
```

Best observed parameter set:

```text
Holding days:          120
Stop loss:             0
Take profit:           0
Max position fraction: 0.20
Final equity:          367.76
Total return:          +83.88%
Max drawdown:          -23.25%
Trades:                61
Avg holding days:      120
Win rate:              60.66%
Profit factor:         2.53
Total fees:            41.52
```

Direct validation command:

```powershell
python -m backtests.momentum_backtest --tickers AAPL MSFT NVDA LITE --initial-cash 200 --holding-days 120 --stop-loss-pct 0 --take-profit-pct 0 --max-position-fraction 0.20 --show-trades 8
```

Interpretation:

- Longer holding periods materially reduce fee drag.
- For the current four-ticker universe, time exits beat close-based stop/take exits.
- Drawdown improved from roughly -45% in the prior 60-day best to roughly -23%.
- This is still not enough for live trading, but it is good enough to continue into trade-cooldown and portfolio guardrail work.

### Phase 3 Cooldown Tests

Added `--cooldown-days` to both the single backtest and parameter sweep runner.

Example commands:

```powershell
python -m backtests.momentum_backtest --tickers AAPL MSFT NVDA LITE --initial-cash 200 --holding-days 120 --stop-loss-pct 0 --take-profit-pct 0 --max-position-fraction 0.20 --cooldown-days 20
python -m backtests.momentum_backtest --tickers AAPL MSFT NVDA LITE --initial-cash 200 --holding-days 120 --stop-loss-pct 0 --take-profit-pct 0 --max-position-fraction 0.20 --cooldown-days 40
python -m backtests.parameter_sweep --tickers AAPL MSFT NVDA LITE --holding-days 90,120 --stop-loss-pcts 0 --take-profit-pcts 0,0.20 --max-position-fractions 0.10,0.15,0.20 --cooldown-days 0,20,40,60 --top 10 --output reports/parameter_sweep_cooldown.csv
```

Results:

```text
120D, no stop/take, 20D cooldown:
Final equity:      284.91
Total return:      +42.45%
Max drawdown:      -24.68%
Trades:            52
Total fees:        39.39

120D, no stop/take, 40D cooldown:
Final equity:      283.09
Total return:      +41.55%
Max drawdown:      -22.34%
Trades:            45
Total fees:        32.91
```

Interpretation:

- Cooldowns reduce trade count and total fees.
- For the current four-ticker universe, cooldowns reduce upside more than they improve drawdown.
- The best observed result remains 120D hold, no stop, no take profit, 20% max position fraction, no cooldown.
- Cooldowns may become more useful when the universe is larger and duplicate ticker churn is higher.

### Phase 3 Drawdown Guardrails and Market Benchmark

Added:

- `--max-drawdown-stop-pct`
- `--benchmark-tickers`
- SPY/QQQ benchmark comparison
- Guardrail-aware parameter sweep output

Loaded 10 years of benchmark data for:

```text
SPY
QQQ
```

Benchmark extraction command:

```powershell
python -m app.pipeline --tickers SPY QQQ --period 10y
```

Guardrail sweep command:

```powershell
python -m backtests.parameter_sweep --tickers AAPL MSFT NVDA LITE --benchmark-tickers SPY QQQ --holding-days 90,120 --stop-loss-pcts 0 --take-profit-pcts 0,0.20 --max-position-fractions 0.10,0.15,0.20 --cooldown-days 0,20,40 --max-drawdown-stop-pcts 0,0.20,0.30 --top 8 --output reports/parameter_sweep_guardrails.csv
```

Best observed strategy result still:

```text
Holding days:          120
Stop loss:             0
Take profit:           0
Cooldown days:         0
Max drawdown stop:     0
Max position fraction: 0.20
Final equity:          367.76
Total return:          +83.88%
Max drawdown:          -23.25%
Trades:                61
Profit factor:         2.53
Total fees:            41.52
Guardrail triggered:   False
```

Market benchmark over the same strategy trade window:

```text
Equal-weight SPY/QQQ return: +376.43%
Strategy alpha:              -292.55 percentage points
```

Interpretation:

- The strategy is profitable in isolation.
- It materially underperforms a passive SPY/QQQ benchmark over the same period.
- Drawdown guardrails did not improve the best-ranked result; the 20% guardrail triggered and cut return significantly.
- The current strategy should not move to paper trading until it can either outperform a benchmark or justify itself with meaningfully lower drawdown.

### Previous Best Time-Exit Result

Command:

```powershell
python -m backtests.momentum_backtest --tickers AAPL MSFT NVDA LITE --initial-cash 200 --holding-days 60 --show-trades 5
```

Result:

```text
Initial cash:      200.00
Final equity:      250.01
Total return:      +25.01%
Max drawdown:      -45.35%
Trades:            114
Avg holding days:  87.42
Win rate:          46.49%
Profit factor:     1.20
Total fees:        78.20
```

Interpretation:

- Strategy is not production-ready yet.
- 5-day and 20-day holding periods were fee-dragged and unprofitable.
- 60-day holding period turned positive but still has very high drawdown.
- Fees remain large relative to USD 200 initial capital.

## Important Commands

Run extraction:

```powershell
python -m app.pipeline --tickers AAPL MSFT NVDA LITE --period 10y
```

Run dynamic universe extraction:

```powershell
python -m app.pipeline --period 1mo
```

Run dashboard:

```powershell
python -m streamlit run app/dashboard/streamlit_app.py
```

Run backtest:

```powershell
python -m backtests.momentum_backtest --tickers AAPL MSFT NVDA LITE --initial-cash 200 --holding-days 60
```

Run tests:

```powershell
python -m pytest -q
```

## Next Recommended Work

### Phase 3 - Risk Optimization Continued

Priority:

1. Add max sector exposure limits.
2. Add dashboard tab for backtest metrics and trade history.
3. Add a larger dynamic universe before trusting optimization results.
4. Add benchmark-aware scoring to penalize underperformance.
5. Add rolling walk-forward validation to reduce overfitting risk.

### Phase 4 - Paper Trading

Only after Phase 3 improves drawdown:

1. Add paper portfolio state table.
2. Convert signals into paper orders.
3. Track open positions and realized PnL.
4. Show paper portfolio in Streamlit.

### Phase 5 - Broker Integration

Only after paper trading is stable:

1. Wire FutuOpenD connection.
2. Add dry-run broker adapter.
3. Add live order confirmation guardrails.
4. Keep live trading disabled by default.

## Current Risk Status

Live trading status:

```text
DISABLED
```

Reason:

```text
Backtest drawdown is still too high for a USD 200 micro-capital account.
```
