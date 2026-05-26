# US Equity Swing-Trading Pipeline

Automated, modular swing-trading pipeline for US equities using Python, Supabase PostgreSQL, GitHub Actions, quantitative signals, Moomoo/Futu OpenAPI, and Streamlit.

This repository is intentionally built in incremental slices so AI coding agents can extend it safely.

## Current MVP Slice

- Supabase/PostgreSQL schema
- Typed environment config
- yfinance EOD price fetcher
- OHLCV cleaner
- SQLAlchemy upsert loader
- Feature engineering for log returns, rolling volatility, and momentum
- Momentum signal generator
- Daily pipeline CLI
- Streamlit dashboard scaffold
- GitHub Actions scheduled workflow

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Fill in `.env` with your Supabase/PostgreSQL connection details.

## Run The Daily Pipeline

```powershell
python -m app.pipeline --tickers AAPL MSFT NVDA SPY QQQ --period 1y
```

Use `--dry-run` to verify fetching, cleaning, feature generation, and signal generation without writing to the database:

```powershell
python -m app.pipeline --tickers AAPL MSFT NVDA --period 6mo --dry-run
```

## Run Dashboard

```powershell
streamlit run app/dashboard/streamlit_app.py
```

## Build Order

1. Database schema
2. ETL pipeline
3. Feature engineering
4. Signal generation
5. Backtesting
6. Dashboard
7. Broker execution

## Safety Notes

This project is for research and automation scaffolding. Start with paper trading only. Do not enable live trading until order sizing, stops, broker permissions, and failure handling are independently verified.
