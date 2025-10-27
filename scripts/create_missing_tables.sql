-- Create Missing Tables from Spock SQLite
-- Tables: technical_analysis, trades, portfolio, market_sentiment

-- ===========================================================================
-- technical_analysis: LayeredScoringEngine results (Spock-specific)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS technical_analysis (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL DEFAULT 'KR',
    analysis_date DATE NOT NULL,

    -- Weinstein Stage Analysis
    stage INTEGER,
    stage_confidence DECIMAL(10, 4),

    -- LayeredScoringEngine (100-point system)
    layer1_macro_score DECIMAL(10, 4),
    layer2_structural_score DECIMAL(10, 4),
    layer3_micro_score DECIMAL(10, 4),
    total_score DECIMAL(10, 4),

    -- Signals
    signal VARCHAR(20),  -- BUY, WATCH, AVOID
    signal_strength DECIMAL(10, 4),

    -- GPT-4 Analysis (optional)
    gpt_pattern TEXT,
    gpt_confidence DECIMAL(10, 4),
    gpt_analysis TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE (ticker, region, analysis_date),
    FOREIGN KEY (ticker, region) REFERENCES tickers(ticker, region) ON DELETE CASCADE
);

CREATE INDEX idx_ta_ticker_date ON technical_analysis(ticker, analysis_date DESC);
CREATE INDEX idx_ta_signal ON technical_analysis(signal);
CREATE INDEX idx_ta_score ON technical_analysis(total_score DESC);

COMMENT ON TABLE technical_analysis IS 'LayeredScoringEngine analysis results (Spock legacy)';

-- ===========================================================================
-- trades: Historical trade records
-- ===========================================================================
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL DEFAULT 'KR',

    side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    order_type VARCHAR(10) NOT NULL CHECK (order_type IN ('MARKET', 'LIMIT')),

    quantity INTEGER NOT NULL,
    price DECIMAL(15, 4) NOT NULL,
    amount DECIMAL(15, 4) NOT NULL,

    fee DECIMAL(10, 4) DEFAULT 0,
    tax DECIMAL(10, 4) DEFAULT 0,

    order_no VARCHAR(50),
    execution_no VARCHAR(50),

    order_time TIMESTAMP WITH TIME ZONE NOT NULL,
    execution_time TIMESTAMP WITH TIME ZONE,

    reason TEXT,

    -- Additional fields for trade tracking
    entry_price DECIMAL(15, 4),
    exit_price DECIMAL(15, 4),
    entry_timestamp TIMESTAMP WITH TIME ZONE,
    exit_timestamp TIMESTAMP WITH TIME ZONE,
    trade_status VARCHAR(20) DEFAULT 'OPEN' CHECK (trade_status IN ('OPEN', 'CLOSED', 'PARTIAL')),
    sector VARCHAR(50),
    position_size_percent DECIMAL(10, 4),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    FOREIGN KEY (ticker, region) REFERENCES tickers(ticker, region) ON DELETE CASCADE
);

CREATE INDEX idx_trades_ticker ON trades(ticker);
CREATE INDEX idx_trades_ticker_region ON trades(ticker, region);
CREATE INDEX idx_trades_execution_time ON trades(execution_time DESC);
CREATE INDEX idx_trades_status ON trades(trade_status);
CREATE INDEX idx_trades_ticker_region_status ON trades(ticker, region, trade_status);
CREATE INDEX idx_trades_entry_timestamp ON trades(entry_timestamp DESC);
CREATE INDEX idx_trades_exit_timestamp ON trades(exit_timestamp DESC);

COMMENT ON TABLE trades IS 'Historical trade execution records';

-- ===========================================================================
-- portfolio: Current portfolio holdings (Spock live trading)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS portfolio (
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL DEFAULT 'KR',

    quantity INTEGER NOT NULL,
    avg_price DECIMAL(15, 4) NOT NULL,
    current_price DECIMAL(15, 4),

    market_value DECIMAL(15, 4),
    unrealized_pnl DECIMAL(15, 4),
    unrealized_pnl_pct DECIMAL(10, 4),

    stop_loss_price DECIMAL(15, 4),
    profit_target_price DECIMAL(15, 4),

    entry_date DATE NOT NULL,
    entry_score DECIMAL(10, 4),

    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    PRIMARY KEY (ticker, region),
    FOREIGN KEY (ticker, region) REFERENCES tickers(ticker, region) ON DELETE CASCADE
);

CREATE INDEX idx_portfolio_region ON portfolio(region);
CREATE INDEX idx_portfolio_entry_date ON portfolio(entry_date DESC);
CREATE INDEX idx_portfolio_unrealized_pnl ON portfolio(unrealized_pnl DESC);

COMMENT ON TABLE portfolio IS 'Current portfolio positions (Spock live trading)';

-- ===========================================================================
-- market_sentiment: Market-wide sentiment indicators
-- ===========================================================================
CREATE TABLE IF NOT EXISTS market_sentiment (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,

    vix DECIMAL(10, 4),
    fear_greed_index DECIMAL(10, 4),

    kospi_index DECIMAL(10, 2),
    kosdaq_index DECIMAL(10, 2),

    foreign_net_buying BIGINT,
    institution_net_buying BIGINT,

    usd_krw DECIMAL(10, 4),
    jpy_krw DECIMAL(10, 4),

    oil_price DECIMAL(10, 4),
    gold_price DECIMAL(10, 4),

    market_regime VARCHAR(50),
    sentiment_score DECIMAL(10, 4),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sentiment_date ON market_sentiment(date DESC);
CREATE INDEX idx_sentiment_regime ON market_sentiment(market_regime);

COMMENT ON TABLE market_sentiment IS 'Daily market sentiment and macro indicators';

-- ===========================================================================
-- Summary
-- ===========================================================================
-- 4 tables created:
-- 1. technical_analysis - LayeredScoringEngine results (Spock legacy)
-- 2. trades - Trade execution history
-- 3. portfolio - Live portfolio positions (Spock)
-- 4. market_sentiment - Market sentiment indicators
