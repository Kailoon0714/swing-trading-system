from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text

from app.db.connection import get_engine


st.set_page_config(page_title="Swing Trading Dashboard", layout="wide")
st.title("US Equity Swing Trading")


@st.cache_data(ttl=300)
def load_table(query: str) -> pd.DataFrame:
    engine = get_engine()
    return pd.read_sql(text(query), engine)


latest_prices_query = """
SELECT a.ticker, p.trading_date, p.close, p.adjusted_close, p.volume
FROM daily_prices p
JOIN assets a ON a.id = p.asset_id
WHERE p.trading_date >= CURRENT_DATE - INTERVAL '120 days'
ORDER BY p.trading_date DESC, a.ticker;
"""

latest_signals_query = """
SELECT a.ticker, s.trading_date, s.signal, s.confidence, s.model_name, s.execution_status, s.created_at
FROM model_signals s
JOIN assets a ON a.id = s.asset_id
ORDER BY s.trading_date DESC, s.created_at DESC
LIMIT 100;
"""

try:
    prices = load_table(latest_prices_query)
    signals = load_table(latest_signals_query)
except Exception as exc:
    st.error(f"Dashboard could not connect to the database: {exc}")
    st.stop()

left, right = st.columns([2, 1])

with left:
    tickers = sorted(prices["ticker"].unique()) if not prices.empty else []
    selected = st.selectbox("Ticker", tickers)
    chart_data = prices[prices["ticker"] == selected].sort_values("trading_date") if selected else pd.DataFrame()
    if not chart_data.empty:
        st.plotly_chart(
            px.line(chart_data, x="trading_date", y="adjusted_close", title=f"{selected} Adjusted Close"),
            use_container_width=True,
        )

with right:
    st.metric("Tracked Tickers", len(prices["ticker"].unique()) if not prices.empty else 0)
    st.metric("Recent Signals", len(signals))
    pending = int((signals["execution_status"] == "PENDING").sum()) if not signals.empty else 0
    st.metric("Pending Execution", pending)

st.subheader("Latest Signals")
st.dataframe(signals, use_container_width=True, hide_index=True)
