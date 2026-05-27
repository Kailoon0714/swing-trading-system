CREATE TABLE IF NOT EXISTS assets (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) UNIQUE NOT NULL,
    company_name TEXT,
    sector TEXT DEFAULT 'Unknown',
    industry TEXT DEFAULT 'Unknown',
    exchange TEXT,
    currency VARCHAR(10) DEFAULT 'USD',
    is_active BOOLEAN DEFAULT TRUE,
    min_daily_volume BIGINT DEFAULT 100000,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_prices (
    id BIGSERIAL PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    trading_date DATE NOT NULL,
    open NUMERIC(18, 6),
    high NUMERIC(18, 6),
    low NUMERIC(18, 6),
    close NUMERIC(18, 6),
    adjusted_close NUMERIC(18, 6),
    volume BIGINT,
    dollar_volume NUMERIC(24, 6),
    data_vendor TEXT DEFAULT 'yfinance',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(asset_id, trading_date)
);

CREATE TABLE IF NOT EXISTS model_features (
    id BIGSERIAL PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    trading_date DATE NOT NULL,
    log_return NUMERIC(18, 10),
    rolling_volatility_14d NUMERIC(18, 10),
    momentum_score NUMERIC(18, 10),
    average_volume_20d BIGINT,
    liquidity_pass BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(asset_id, trading_date)
);

CREATE TABLE IF NOT EXISTS model_signals (
    id BIGSERIAL PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    trading_date DATE NOT NULL,
    signal VARCHAR(10) NOT NULL CHECK (signal IN ('BUY', 'SELL', 'HOLD')),
    confidence NUMERIC(10, 6),
    model_name TEXT NOT NULL,
    sector TEXT,
    industry TEXT,
    rank_in_sector INTEGER,
    execution_status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(asset_id, trading_date, model_name)
);

CREATE TABLE IF NOT EXISTS trades (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT REFERENCES model_signals(id) ON DELETE SET NULL,
    ticker VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity NUMERIC(20, 8) NOT NULL,
    execution_price NUMERIC(18, 6),
    gross_notional NUMERIC(18, 6),
    net_notional NUMERIC(18, 6),
    commission_fee NUMERIC(18, 6) DEFAULT 0,
    platform_fee NUMERIC(18, 6) DEFAULT 0,
    settlement_fee NUMERIC(18, 6) DEFAULT 0,
    sec_fee NUMERIC(18, 6) DEFAULT 0,
    taf_fee NUMERIC(18, 6) DEFAULT 0,
    cat_fee NUMERIC(18, 6) DEFAULT 0,
    total_fees NUMERIC(18, 6) DEFAULT 0,
    fee_ratio NUMERIC(10, 6),
    broker_order_id TEXT,
    status TEXT,
    execution_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE assets ADD COLUMN IF NOT EXISTS exchange TEXT;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS currency VARCHAR(10) DEFAULT 'USD';
ALTER TABLE assets ADD COLUMN IF NOT EXISTS min_daily_volume BIGINT DEFAULT 100000;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE assets ALTER COLUMN ticker TYPE VARCHAR(20);
ALTER TABLE assets ALTER COLUMN sector SET DEFAULT 'Unknown';
ALTER TABLE assets ALTER COLUMN industry SET DEFAULT 'Unknown';

ALTER TABLE daily_prices ADD COLUMN IF NOT EXISTS dollar_volume NUMERIC(24, 6);
ALTER TABLE daily_prices ADD COLUMN IF NOT EXISTS data_vendor TEXT DEFAULT 'yfinance';
ALTER TABLE daily_prices ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

ALTER TABLE model_features ADD COLUMN IF NOT EXISTS average_volume_20d BIGINT;
ALTER TABLE model_features ADD COLUMN IF NOT EXISTS liquidity_pass BOOLEAN DEFAULT TRUE;
ALTER TABLE model_features ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

ALTER TABLE model_signals ADD COLUMN IF NOT EXISTS sector TEXT;
ALTER TABLE model_signals ADD COLUMN IF NOT EXISTS industry TEXT;
ALTER TABLE model_signals ADD COLUMN IF NOT EXISTS rank_in_sector INTEGER;
ALTER TABLE model_signals ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

DO $$
DECLARE
    constraint_name TEXT;
BEGIN
    SELECT tc.constraint_name
    INTO constraint_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
    WHERE tc.table_name = 'trades'
        AND tc.constraint_type = 'FOREIGN KEY'
        AND kcu.column_name = 'signal_id'
    LIMIT 1;

    IF constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE trades DROP CONSTRAINT %I', constraint_name);
    END IF;
END $$;

ALTER TABLE trades ALTER COLUMN quantity TYPE NUMERIC(20, 8) USING quantity::NUMERIC;
ALTER TABLE trades ALTER COLUMN signal_id TYPE BIGINT USING signal_id::BIGINT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS gross_notional NUMERIC(18, 6);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS net_notional NUMERIC(18, 6);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS commission_fee NUMERIC(18, 6) DEFAULT 0;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS platform_fee NUMERIC(18, 6) DEFAULT 0;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS settlement_fee NUMERIC(18, 6) DEFAULT 0;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS sec_fee NUMERIC(18, 6) DEFAULT 0;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS taf_fee NUMERIC(18, 6) DEFAULT 0;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS cat_fee NUMERIC(18, 6) DEFAULT 0;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS total_fees NUMERIC(18, 6) DEFAULT 0;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS fee_ratio NUMERIC(10, 6);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_name = 'trades'
            AND constraint_name = 'trades_signal_id_fkey'
    ) THEN
        ALTER TABLE trades
        ADD CONSTRAINT trades_signal_id_fkey
        FOREIGN KEY (signal_id) REFERENCES model_signals(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_assets_active ON assets(is_active, ticker);
CREATE INDEX IF NOT EXISTS idx_assets_sector_industry ON assets(sector, industry);
CREATE INDEX IF NOT EXISTS idx_daily_prices_asset_date ON daily_prices(asset_id, trading_date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_prices_date ON daily_prices(trading_date DESC);
CREATE INDEX IF NOT EXISTS idx_model_features_asset_date ON model_features(asset_id, trading_date DESC);
CREATE INDEX IF NOT EXISTS idx_model_signals_status ON model_signals(execution_status, trading_date DESC);
CREATE INDEX IF NOT EXISTS idx_model_signals_asset_date ON model_signals(asset_id, trading_date DESC);
CREATE INDEX IF NOT EXISTS idx_trades_ticker_time ON trades(ticker, execution_time DESC);
