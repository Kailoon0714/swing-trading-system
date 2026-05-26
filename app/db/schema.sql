CREATE TABLE IF NOT EXISTS assets (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) UNIQUE NOT NULL,
    company_name TEXT,
    sector TEXT,
    industry TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_prices (
    id BIGSERIAL PRIMARY KEY,
    asset_id INTEGER REFERENCES assets(id),
    trading_date DATE NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    adjusted_close NUMERIC,
    volume BIGINT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(asset_id, trading_date)
);

CREATE TABLE IF NOT EXISTS model_features (
    id BIGSERIAL PRIMARY KEY,
    asset_id INTEGER REFERENCES assets(id),
    trading_date DATE NOT NULL,
    log_return NUMERIC,
    rolling_volatility_14d NUMERIC,
    momentum_score NUMERIC,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(asset_id, trading_date)
);

CREATE TABLE IF NOT EXISTS model_signals (
    id BIGSERIAL PRIMARY KEY,
    asset_id INTEGER REFERENCES assets(id),
    trading_date DATE NOT NULL,
    signal VARCHAR(10) NOT NULL,
    confidence NUMERIC,
    model_name TEXT NOT NULL,
    execution_status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(asset_id, trading_date, model_name)
);

CREATE TABLE IF NOT EXISTS trades (
    id BIGSERIAL PRIMARY KEY,
    signal_id INTEGER REFERENCES model_signals(id),
    ticker VARCHAR(10),
    side VARCHAR(10),
    quantity INTEGER,
    execution_price NUMERIC,
    execution_time TIMESTAMP,
    broker_order_id TEXT,
    status TEXT
);

CREATE INDEX IF NOT EXISTS idx_daily_prices_asset_date ON daily_prices(asset_id, trading_date DESC);
CREATE INDEX IF NOT EXISTS idx_model_features_asset_date ON model_features(asset_id, trading_date DESC);
CREATE INDEX IF NOT EXISTS idx_model_signals_status ON model_signals(execution_status, trading_date DESC);
