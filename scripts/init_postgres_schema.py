"""
Quant Investment Platform - PostgreSQL Schema Initialization

PostgreSQL + TimescaleDB schema creation for unlimited historical data retention.

Key Features:
- Hypertables for time-series data (ohlcv_data, factor_scores, ticker_fundamentals)
- Continuous aggregates (monthly, yearly OHLCV)
- Compression policies (10x storage savings)
- Optimized indexes for fast queries

Usage:
    python scripts/init_postgres_schema.py                    # Initialize schema
    python scripts/init_postgres_schema.py --drop             # Drop all tables first
    python scripts/init_postgres_schema.py --validate         # Validate schema only

Author: Quant Platform Development Team
Date: 2025-10-20
"""

import os
import sys
import argparse
import logging
from typing import Optional
from datetime import datetime

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class PostgresSchemaInitializer:
    """PostgreSQL + TimescaleDB schema initializer"""

    def __init__(self,
                 host: str = 'localhost',
                 port: int = 5432,
                 database: str = 'quant_platform',
                 user: Optional[str] = None,
                 password: Optional[str] = None):
        """
        Initialize schema creator

        Args:
            host: PostgreSQL host
            port: PostgreSQL port
            database: Database name
            user: Database user (defaults to env POSTGRES_USER or current user)
            password: Database password (defaults to env POSTGRES_PASSWORD)
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user or os.getenv('POSTGRES_USER', os.getenv('USER'))
        self.password = password or os.getenv('POSTGRES_PASSWORD', '')

        self.conn = None
        self.cursor = None

    def connect(self):
        """Connect to PostgreSQL database"""
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            self.cursor = self.conn.cursor()
            logger.info(f"✅ Connected to PostgreSQL: {self.database}@{self.host}:{self.port}")
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            raise

    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            logger.info("🔌 Connection closed")

    def execute_sql(self, sql_statement: str, description: str = ""):
        """
        Execute SQL statement with error handling

        Args:
            sql_statement: SQL to execute
            description: Human-readable description for logging
        """
        try:
            if description:
                logger.info(f"⚙️  {description}")
            self.cursor.execute(sql_statement)
            logger.info(f"✅ {description or 'SQL executed'}")
        except Exception as e:
            logger.error(f"❌ {description or 'SQL failed'}: {e}")
            raise

    def drop_all_tables(self):
        """Drop all tables (dangerous - use with caution)"""
        logger.warning("⚠️  Dropping all tables...")

        drop_statements = [
            "DROP MATERIALIZED VIEW IF EXISTS ohlcv_yearly CASCADE;",
            "DROP MATERIALIZED VIEW IF EXISTS ohlcv_monthly CASCADE;",
            "DROP TABLE IF EXISTS factor_scores CASCADE;",
            "DROP TABLE IF EXISTS portfolio_holdings CASCADE;",
            "DROP TABLE IF EXISTS backtest_results CASCADE;",
            "DROP TABLE IF EXISTS strategies CASCADE;",
            "DROP TABLE IF EXISTS ticker_fundamentals CASCADE;",
            "DROP TABLE IF EXISTS technical_analysis CASCADE;",
            "DROP TABLE IF EXISTS ohlcv_data CASCADE;",
            "DROP TABLE IF EXISTS etf_holdings CASCADE;",
            "DROP TABLE IF EXISTS etfs CASCADE;",
            "DROP TABLE IF EXISTS etf_details CASCADE;",
            "DROP TABLE IF EXISTS stock_details CASCADE;",
            "DROP TABLE IF EXISTS tickers CASCADE;",
        ]

        for stmt in drop_statements:
            try:
                self.cursor.execute(stmt)
            except Exception as e:
                logger.warning(f"Skip: {e}")

        logger.info("🗑️  All tables dropped")

    def create_tickers_table(self):
        """Create tickers master table (global ticker universe)"""
        sql_statement = """
        CREATE TABLE tickers (
            ticker VARCHAR(20) NOT NULL,
            region VARCHAR(2) NOT NULL,  -- KR, US, CN, HK, JP, VN

            -- Basic Information
            name TEXT NOT NULL,
            name_eng TEXT,
            exchange VARCHAR(20) NOT NULL,  -- KOSPI, NYSE, NASDAQ, etc.
            currency VARCHAR(3) NOT NULL DEFAULT 'KRW',
            asset_type VARCHAR(20) NOT NULL DEFAULT 'STOCK',  -- STOCK, ETF

            -- Dates
            listing_date DATE,
            delisting_date DATE,

            -- Status
            is_active BOOLEAN DEFAULT TRUE,
            lot_size INTEGER DEFAULT 1,

            -- Metadata
            created_at TIMESTAMPTZ DEFAULT NOW(),
            last_updated TIMESTAMPTZ DEFAULT NOW(),
            data_source VARCHAR(50),

            PRIMARY KEY (ticker, region)
        );

        -- Indexes
        CREATE INDEX idx_tickers_region ON tickers(region);
        CREATE INDEX idx_tickers_exchange ON tickers(exchange);
        CREATE INDEX idx_tickers_is_active ON tickers(is_active) WHERE is_active = TRUE;
        CREATE INDEX idx_tickers_asset_type ON tickers(asset_type);

        -- Comments
        COMMENT ON TABLE tickers IS 'Global ticker universe for all supported regions';
        COMMENT ON COLUMN tickers.region IS 'ISO 3166-1 alpha-2 country code (KR, US, CN, HK, JP, VN)';
        COMMENT ON COLUMN tickers.lot_size IS 'Minimum trading unit (1 for US, varies for HK/JP)';
        """

        self.execute_sql(sql_statement, "Creating tickers table")

    def create_stock_details_table(self):
        """Create stock_details table (stock-specific metadata)"""
        sql_statement = """
        CREATE TABLE stock_details (
            ticker VARCHAR(20) NOT NULL,
            region VARCHAR(2) NOT NULL,

            -- Sector & Industry
            sector TEXT,                          -- GICS sector
            sector_code VARCHAR(10),              -- GICS sector code
            industry TEXT,                        -- Industry classification
            industry_code VARCHAR(10),            -- Industry code

            -- Stock-specific
            is_spac BOOLEAN DEFAULT FALSE,        -- SPAC flag
            is_preferred BOOLEAN DEFAULT FALSE,   -- Preferred stock
            par_value INTEGER,                    -- Par value (KRW/USD)

            -- Metadata
            created_at TIMESTAMPTZ DEFAULT NOW(),
            last_updated TIMESTAMPTZ DEFAULT NOW(),

            PRIMARY KEY (ticker, region),
            FOREIGN KEY (ticker, region) REFERENCES tickers(ticker, region) ON DELETE CASCADE
        );

        -- Indexes
        CREATE INDEX idx_stock_details_sector ON stock_details(sector);
        CREATE INDEX idx_stock_details_industry ON stock_details(industry);

        -- Comments
        COMMENT ON TABLE stock_details IS 'Stock-specific metadata (sector, industry, SPAC flag)';
        """

        self.execute_sql(sql_statement, "Creating stock_details table")

    def create_etf_details_table(self):
        """Create etf_details table (ETF-specific metadata)"""
        sql_statement = """
        CREATE TABLE etf_details (
            ticker VARCHAR(20) NOT NULL,
            region VARCHAR(2) NOT NULL,

            -- Basic Info
            issuer TEXT,                          -- Fund manager
            inception_date DATE,                  -- Launch date
            underlying_asset_class TEXT,          -- Stock, Bond, Commodity, Mixed

            -- Tracking & Classification
            tracking_index TEXT NOT NULL,         -- KOSPI200, S&P500, etc.
            geographic_region TEXT,               -- KR, US, CN, GLOBAL
            sector_theme TEXT,                    -- Semiconductor, Bio, Battery
            fund_type TEXT,                       -- index, sector, thematic, commodity

            -- Size
            aum BIGINT,                           -- Assets Under Management
            listed_shares BIGINT,                 -- Outstanding shares
            underlying_asset_count INTEGER,       -- Number of holdings

            -- Costs (IMPORTANT)
            expense_ratio NUMERIC(5, 2) NOT NULL, -- Total expense ratio (%)
            ter NUMERIC(5, 2),                    -- TER (%)
            leverage_ratio VARCHAR(10),           -- 1x, 2x, -1x
            currency_hedged BOOLEAN,              -- Currency hedge flag

            -- Tracking Error
            tracking_error_20d NUMERIC(8, 4),
            tracking_error_60d NUMERIC(8, 4),
            tracking_error_120d NUMERIC(8, 4),
            tracking_error_250d NUMERIC(8, 4),

            -- Metadata
            created_at TIMESTAMPTZ DEFAULT NOW(),
            last_updated TIMESTAMPTZ DEFAULT NOW(),

            PRIMARY KEY (ticker, region),
            FOREIGN KEY (ticker, region) REFERENCES tickers(ticker, region) ON DELETE CASCADE
        );

        -- Indexes
        CREATE INDEX idx_etf_details_tracking_index ON etf_details(tracking_index);
        CREATE INDEX idx_etf_details_sector_theme ON etf_details(sector_theme);
        CREATE INDEX idx_etf_details_expense_ratio ON etf_details(expense_ratio);

        -- Comments
        COMMENT ON TABLE etf_details IS 'ETF-specific metadata (tracking index, expense ratio, AUM)';
        """

        self.execute_sql(sql_statement, "Creating etf_details table")

    def create_ohlcv_data_hypertable(self):
        """Create ohlcv_data hypertable (time-series optimized)"""

        # Step 1: Create regular table
        sql_create_table = """
        CREATE TABLE ohlcv_data (
            ticker VARCHAR(20) NOT NULL,
            region VARCHAR(2) NOT NULL,
            date DATE NOT NULL,
            timeframe VARCHAR(10) NOT NULL DEFAULT '1d',  -- 1d, 1w, 1m

            -- OHLCV
            open NUMERIC(18, 4),
            high NUMERIC(18, 4),
            low NUMERIC(18, 4),
            close NUMERIC(18, 4),
            volume BIGINT,

            -- Technical Indicators (from basic_scoring_modules.py)
            ma5 NUMERIC(18, 4),
            ma20 NUMERIC(18, 4),
            ma60 NUMERIC(18, 4),
            ma120 NUMERIC(18, 4),
            ma200 NUMERIC(18, 4),

            rsi_14 NUMERIC(8, 4),

            macd NUMERIC(18, 4),
            macd_signal NUMERIC(18, 4),
            macd_hist NUMERIC(18, 4),

            bb_upper NUMERIC(18, 4),
            bb_middle NUMERIC(18, 4),
            bb_lower NUMERIC(18, 4),

            atr_14 NUMERIC(18, 4),

            -- Metadata
            created_at TIMESTAMPTZ DEFAULT NOW(),

            PRIMARY KEY (ticker, region, date, timeframe)
        );
        """

        self.execute_sql(sql_create_table, "Creating ohlcv_data table")

        # Step 2: Convert to hypertable (partition by date)
        sql_hypertable = """
        SELECT create_hypertable('ohlcv_data', 'date',
            chunk_time_interval => INTERVAL '1 month',
            if_not_exists => TRUE
        );
        """

        self.execute_sql(sql_hypertable, "Converting ohlcv_data to hypertable")

        # Step 3: Create indexes
        sql_indexes = """
        CREATE INDEX idx_ohlcv_ticker_region ON ohlcv_data(ticker, region, date DESC);
        CREATE INDEX idx_ohlcv_date ON ohlcv_data(date DESC);
        CREATE INDEX idx_ohlcv_region ON ohlcv_data(region, date DESC);
        """

        self.execute_sql(sql_indexes, "Creating ohlcv_data indexes")

        # Step 4: Enable compression
        sql_compression = """
        ALTER TABLE ohlcv_data SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'ticker, region, timeframe',
            timescaledb.compress_orderby = 'date DESC'
        );
        """

        self.execute_sql(sql_compression, "Enabling compression on ohlcv_data")

        # Step 5: Add compression policy (compress data older than 1 year)
        sql_compression_policy = """
        SELECT add_compression_policy('ohlcv_data', INTERVAL '365 days');
        """

        self.execute_sql(sql_compression_policy, "Adding compression policy to ohlcv_data")

        # Step 6: Add comment
        sql_comment = """
        COMMENT ON TABLE ohlcv_data IS 'Daily/weekly/monthly OHLCV data with technical indicators (hypertable)';
        """

        self.execute_sql(sql_comment, "Adding comment to ohlcv_data")

    def create_factor_scores_hypertable(self):
        """Create factor_scores hypertable (multi-factor analysis)"""

        # Step 1: Create regular table
        sql_create_table = """
        CREATE TABLE factor_scores (
            ticker VARCHAR(20) NOT NULL,
            region VARCHAR(2) NOT NULL,
            date DATE NOT NULL,

            -- Factor names (value, momentum, quality, low_vol, size)
            factor_name VARCHAR(50) NOT NULL,

            -- Raw score and percentile rank (0-100)
            score NUMERIC(10, 4),
            percentile NUMERIC(5, 2),

            -- Metadata
            created_at TIMESTAMPTZ DEFAULT NOW(),

            PRIMARY KEY (ticker, region, date, factor_name)
        );
        """

        self.execute_sql(sql_create_table, "Creating factor_scores table")

        # Step 2: Convert to hypertable
        sql_hypertable = """
        SELECT create_hypertable('factor_scores', 'date',
            chunk_time_interval => INTERVAL '1 month',
            if_not_exists => TRUE
        );
        """

        self.execute_sql(sql_hypertable, "Converting factor_scores to hypertable")

        # Step 3: Create indexes
        sql_indexes = """
        CREATE INDEX idx_factor_scores_date ON factor_scores(date DESC);
        CREATE INDEX idx_factor_scores_ticker ON factor_scores(ticker, region, date DESC);
        CREATE INDEX idx_factor_scores_factor ON factor_scores(factor_name, date DESC);
        """

        self.execute_sql(sql_indexes, "Creating factor_scores indexes")

        # Step 4: Enable compression
        sql_compression = """
        ALTER TABLE factor_scores SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'ticker, region, factor_name',
            timescaledb.compress_orderby = 'date DESC'
        );
        """

        self.execute_sql(sql_compression, "Enabling compression on factor_scores")

        # Step 5: Add compression policy (compress data older than 180 days)
        sql_compression_policy = """
        SELECT add_compression_policy('factor_scores', INTERVAL '180 days');
        """

        self.execute_sql(sql_compression_policy, "Adding compression policy to factor_scores")

        # Step 6: Add comment
        sql_comment = """
        COMMENT ON TABLE factor_scores IS 'Daily factor scores for multi-factor analysis (Phase 2 - hypertable)';
        """

        self.execute_sql(sql_comment, "Adding comment to factor_scores")

    def create_continuous_aggregates(self):
        """Create continuous aggregates for pre-computed monthly/yearly OHLCV"""

        # Monthly aggregate
        sql_monthly = """
        CREATE MATERIALIZED VIEW ohlcv_monthly
        WITH (timescaledb.continuous) AS
        SELECT
            ticker,
            region,
            timeframe,
            time_bucket('1 month', date) AS month,

            -- OHLCV aggregation
            FIRST(open, date) AS open,
            MAX(high) AS high,
            MIN(low) AS low,
            LAST(close, date) AS close,
            SUM(volume) AS volume,

            -- Count
            COUNT(*) AS trading_days
        FROM ohlcv_data
        GROUP BY ticker, region, timeframe, month;
        """

        self.execute_sql(sql_monthly, "Creating ohlcv_monthly continuous aggregate")

        # Monthly refresh policy (update every night)
        sql_monthly_policy = """
        SELECT add_continuous_aggregate_policy('ohlcv_monthly',
            start_offset => INTERVAL '3 months',
            end_offset => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 day'
        );
        """

        self.execute_sql(sql_monthly_policy, "Adding refresh policy to ohlcv_monthly")

        # Yearly aggregate
        sql_yearly = """
        CREATE MATERIALIZED VIEW ohlcv_yearly
        WITH (timescaledb.continuous) AS
        SELECT
            ticker,
            region,
            timeframe,
            time_bucket('1 year', date) AS year,

            FIRST(open, date) AS open,
            MAX(high) AS high,
            MIN(low) AS low,
            LAST(close, date) AS close,
            SUM(volume) AS volume,
            COUNT(*) AS trading_days
        FROM ohlcv_data
        GROUP BY ticker, region, timeframe, year;
        """

        self.execute_sql(sql_yearly, "Creating ohlcv_yearly continuous aggregate")

        # Yearly refresh policy (adjusted for yearly buckets)
        sql_yearly_policy = """
        SELECT add_continuous_aggregate_policy('ohlcv_yearly',
            start_offset => INTERVAL '3 years',
            end_offset => INTERVAL '1 year',
            schedule_interval => INTERVAL '7 days'
        );
        """

        self.execute_sql(sql_yearly_policy, "Adding refresh policy to ohlcv_yearly")

        # Note: TimescaleDB continuous aggregates don't support COMMENT ON directly
        # They are special views managed by TimescaleDB extension
        logger.info("✅ Continuous aggregates created (comments skipped for TimescaleDB views)")

    def create_strategies_table(self):
        """Create strategies table (Phase 2 - backtesting)"""
        sql_statement = """
        CREATE TABLE strategies (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            factor_weights JSONB,  -- {"momentum": 0.4, "value": 0.3, "quality": 0.3}
            constraints JSONB,     -- {"max_position": 0.15, "max_sector": 0.4}
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );

        -- Comments
        COMMENT ON TABLE strategies IS 'Strategy definitions with factor weights and constraints (Phase 2)';
        """

        self.execute_sql(sql_statement, "Creating strategies table")

    def create_backtest_results_table(self):
        """Create backtest_results table (Phase 3 - backtesting)"""
        sql_statement = """
        CREATE TABLE backtest_results (
            id SERIAL PRIMARY KEY,
            strategy_id INTEGER REFERENCES strategies(id),
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            initial_capital NUMERIC(15, 2),
            final_capital NUMERIC(15, 2),
            total_return NUMERIC(10, 4),
            sharpe_ratio NUMERIC(10, 4),
            max_drawdown NUMERIC(10, 4),
            win_rate NUMERIC(5, 2),
            num_trades INTEGER,
            results_json JSONB,  -- Detailed results
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        -- Indexes
        CREATE INDEX idx_backtest_results_strategy ON backtest_results(strategy_id);
        CREATE INDEX idx_backtest_results_date ON backtest_results(start_date, end_date);

        -- Comments
        COMMENT ON TABLE backtest_results IS 'Backtesting results with performance metrics (Phase 3)';
        """

        self.execute_sql(sql_statement, "Creating backtest_results table")

    def create_portfolio_holdings_table(self):
        """Create portfolio_holdings table (Phase 4 - portfolio management)"""
        sql_statement = """
        CREATE TABLE portfolio_holdings (
            id BIGSERIAL PRIMARY KEY,
            strategy_id INTEGER REFERENCES strategies(id),
            ticker VARCHAR(20) NOT NULL,
            region VARCHAR(2) NOT NULL,
            date DATE NOT NULL,
            shares INTEGER,
            weight NUMERIC(10, 6),
            cost_basis NUMERIC(15, 4),
            market_value NUMERIC(15, 4),
            UNIQUE (strategy_id, ticker, region, date)
        );

        -- Indexes
        CREATE INDEX idx_holdings_strategy_date ON portfolio_holdings(strategy_id, date DESC);

        -- Comments
        COMMENT ON TABLE portfolio_holdings IS 'Portfolio holdings over time (Phase 4)';
        """

        self.execute_sql(sql_statement, "Creating portfolio_holdings table")

    def validate_schema(self):
        """Validate schema creation"""
        logger.info("🔍 Validating schema...")

        # Check tables
        self.cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = [row[0] for row in self.cursor.fetchall()]

        logger.info(f"✅ Created {len(tables)} tables:")
        for table in tables:
            logger.info(f"   - {table}")

        # Check hypertables
        self.cursor.execute("""
            SELECT hypertable_name
            FROM timescaledb_information.hypertables;
        """)
        hypertables = [row[0] for row in self.cursor.fetchall()]

        logger.info(f"✅ Created {len(hypertables)} hypertables:")
        for ht in hypertables:
            logger.info(f"   - {ht}")

        # Check continuous aggregates
        self.cursor.execute("""
            SELECT view_name
            FROM timescaledb_information.continuous_aggregates;
        """)
        caggs = [row[0] for row in self.cursor.fetchall()]

        logger.info(f"✅ Created {len(caggs)} continuous aggregates:")
        for cagg in caggs:
            logger.info(f"   - {cagg}")

        # Check compression
        self.cursor.execute("""
            SELECT hypertable_name, compression_enabled
            FROM timescaledb_information.hypertables;
        """)
        compression = self.cursor.fetchall()

        logger.info("✅ Compression status:")
        for ht_name, enabled in compression:
            status = "✓ enabled" if enabled else "✗ disabled"
            logger.info(f"   - {ht_name}: {status}")

        logger.info("🎉 Schema validation complete!")

    def initialize(self, drop_existing: bool = False):
        """
        Initialize PostgreSQL schema

        Args:
            drop_existing: Drop all tables before creating (DANGEROUS!)
        """
        try:
            self.connect()

            logger.info("=" * 60)
            logger.info("📊 PostgreSQL + TimescaleDB Schema Initialization")
            logger.info("=" * 60)

            # Drop existing tables (if requested)
            if drop_existing:
                self.drop_all_tables()

            # Core tables
            logger.info("\n=== Creating Core Tables ===")
            self.create_tickers_table()
            self.create_stock_details_table()
            self.create_etf_details_table()

            # Hypertables (time-series optimized)
            logger.info("\n=== Creating Hypertables ===")
            self.create_ohlcv_data_hypertable()
            self.create_factor_scores_hypertable()

            # Continuous aggregates (pre-computed views)
            logger.info("\n=== Creating Continuous Aggregates ===")
            self.create_continuous_aggregates()

            # Phase 2+ tables (future use)
            logger.info("\n=== Creating Future Phase Tables ===")
            self.create_strategies_table()
            self.create_backtest_results_table()
            self.create_portfolio_holdings_table()

            # Validation
            logger.info("\n=== Validation ===")
            self.validate_schema()

            logger.info("\n" + "=" * 60)
            logger.info("🎉 Schema initialization complete!")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            raise
        finally:
            self.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Initialize PostgreSQL schema for Quant Platform')
    parser.add_argument('--drop', action='store_true', help='Drop all tables before creating (DANGEROUS!)')
    parser.add_argument('--validate', action='store_true', help='Validate schema only (no creation)')
    parser.add_argument('--host', default='localhost', help='PostgreSQL host')
    parser.add_argument('--port', type=int, default=5432, help='PostgreSQL port')
    parser.add_argument('--database', default='quant_platform', help='Database name')
    parser.add_argument('--user', help='Database user')
    parser.add_argument('--password', help='Database password')

    args = parser.parse_args()

    # Create initializer
    initializer = PostgresSchemaInitializer(
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user,
        password=args.password
    )

    # Validate only
    if args.validate:
        initializer.connect()
        initializer.validate_schema()
        initializer.close()
        return

    # Initialize schema
    initializer.initialize(drop_existing=args.drop)


if __name__ == '__main__':
    main()
