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

### Phase 3 - Risk Optimization

Priority:

1. Add stop-loss and take-profit exits to the backtest.
2. Add max drawdown guardrails.
3. Add max sector exposure limits.
4. Add trade cooldown rules to reduce fee churn.
5. Parameter sweep holding periods, thresholds, and volume floors.
6. Export backtest results to CSV for inspection.
7. Add dashboard tab for backtest metrics and trade history.

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
