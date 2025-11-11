#!/usr/bin/env python3
"""
PostgreSQL Test Fixtures for Value Factor Integration Tests

Provides pytest fixtures for temporary PostgreSQL database instances
with pre-populated schema and test data factories.

Dependencies:
- pytest-postgresql: Manages temporary PostgreSQL instances
- faker: Generates realistic test data
- psycopg2: PostgreSQL adapter

Usage:
    @pytest.fixture
    def test_with_db(postgres_test_db):
        # postgres_test_db is a temporary database with schema
        db_manager = postgres_test_db
        # Run tests...
"""

import pytest
import psycopg2
from psycopg2 import extras
from faker import Faker
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
import random
import logging

logger = logging.getLogger(__name__)

# Initialize Faker for realistic test data
fake = Faker()
Faker.seed(42)  # Deterministic test data


# ============================================================================
# pytest-postgresql Fixtures
# ============================================================================

# Use pytest-postgresql's built-in fixtures
# These are automatically available when pytest-postgresql is installed


# ============================================================================
# Database Schema Fixtures
# ============================================================================

@pytest.fixture
def postgres_test_db(postgresql):
    """
    PostgreSQL test database with schema initialized

    Creates tables needed for value factor tests:
    - tickers: Stock registry
    - ticker_fundamentals: Financial data (DART, pykrx)
    - factor_scores: Pre-calculated factor scores
    - ohlcv_data: Price and volume data

    Returns:
        MockPostgresDatabaseManager: Test database manager with same interface as production
    """
    # Get connection info from pytest-postgresql fixture
    conn_info = {
        'host': postgresql.info.host,
        'port': postgresql.info.port,
        'database': postgresql.info.dbname,
        'user': postgresql.info.user,
        'password': postgresql.info.password or ''
    }

    # Create database manager
    db_manager = MockPostgresDatabaseManager(**conn_info)

    # Initialize schema
    _create_test_schema(db_manager)

    logger.info(f"✅ Test database initialized: {conn_info['database']}")
    logger.info(f"   Host: {conn_info['host']}:{conn_info['port']}")

    yield db_manager

    # Cleanup after test
    db_manager.close_pool()


def _create_test_schema(db_manager):
    """Create test database schema (simplified version of production schema)"""

    # 1. Tickers table
    db_manager.execute_update("""
        CREATE TABLE IF NOT EXISTS tickers (
            ticker VARCHAR(20) NOT NULL,
            region VARCHAR(10) NOT NULL DEFAULT 'KR',
            name VARCHAR(255),
            market VARCHAR(50),
            sector VARCHAR(100),
            industry VARCHAR(100),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (ticker, region)
        )
    """, ())

    # 2. Ticker fundamentals table
    db_manager.execute_update("""
        CREATE TABLE IF NOT EXISTS ticker_fundamentals (
            ticker VARCHAR(20) NOT NULL,
            region VARCHAR(10) NOT NULL DEFAULT 'KR',
            date DATE NOT NULL,
            fiscal_year INTEGER,
            period_type VARCHAR(20),
            data_source VARCHAR(50),

            -- DART fundamentals (semi-annual)
            revenue NUMERIC(20, 2),
            operating_income NUMERIC(20, 2),
            net_income NUMERIC(20, 2),
            total_assets NUMERIC(20, 2),
            total_liabilities NUMERIC(20, 2),
            total_equity NUMERIC(20, 2),
            current_assets NUMERIC(20, 2),
            current_liabilities NUMERIC(20, 2),
            ebitda NUMERIC(20, 2),

            -- pykrx fundamentals (daily)
            per NUMERIC(10, 4),
            pbr NUMERIC(10, 4),
            dividend_yield NUMERIC(10, 4),
            market_cap NUMERIC(20, 2),
            shares_outstanding NUMERIC(20, 0),

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (ticker, region, date, period_type, data_source)
        )
    """, ())

    # 3. Factor scores table
    db_manager.execute_update("""
        CREATE TABLE IF NOT EXISTS factor_scores (
            ticker VARCHAR(20) NOT NULL,
            region VARCHAR(10) NOT NULL DEFAULT 'KR',
            factor_name VARCHAR(100) NOT NULL,
            date DATE NOT NULL,
            score NUMERIC(10, 6),
            percentile NUMERIC(5, 2),
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (ticker, region, factor_name, date)
        )
    """, ())

    # 4. OHLCV data table (simplified - no hypertable in tests)
    db_manager.execute_update("""
        CREATE TABLE IF NOT EXISTS ohlcv_data (
            ticker VARCHAR(20) NOT NULL,
            region VARCHAR(10) NOT NULL DEFAULT 'KR',
            date DATE NOT NULL,
            timeframe VARCHAR(10) DEFAULT '1d',
            open NUMERIC(15, 2),
            high NUMERIC(15, 2),
            low NUMERIC(15, 2),
            close NUMERIC(15, 2),
            volume BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (ticker, region, date, timeframe)
        )
    """, ())

    logger.info("✅ Test schema created successfully")


# ============================================================================
# Factory Fixtures (Data Generators)
# ============================================================================

@pytest.fixture
def ticker_factory(postgres_test_db):
    """
    Factory fixture for creating test tickers

    Usage:
        ticker = ticker_factory(ticker='005930', name='Samsung Electronics', sector='Technology')
    """
    def _create_ticker(
        ticker: str,
        region: str = 'KR',
        name: Optional[str] = None,
        market: str = 'KOSPI',
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        is_active: bool = True
    ) -> Dict:
        """Create test ticker"""

        # Generate realistic data if not provided
        if not name:
            name = f"{fake.company()} Corp"
        if not sector:
            sector = random.choice(['Technology', 'Finance', 'Healthcare', 'Consumer', 'Industrial'])
        if not industry:
            industry = f"{sector} {random.choice(['Products', 'Services', 'Manufacturing'])}"

        query = """
            INSERT INTO tickers (ticker, region, name, market, sector, industry, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker, region) DO UPDATE SET
                name = EXCLUDED.name,
                market = EXCLUDED.market,
                sector = EXCLUDED.sector,
                industry = EXCLUDED.industry,
                is_active = EXCLUDED.is_active,
                updated_at = CURRENT_TIMESTAMP
        """

        postgres_test_db.execute_update(query, (ticker, region, name, market, sector, industry, is_active))

        return {
            'ticker': ticker,
            'region': region,
            'name': name,
            'market': market,
            'sector': sector,
            'industry': industry,
            'is_active': is_active
        }

    return _create_ticker


@pytest.fixture
def fundamentals_factory(postgres_test_db):
    """
    Factory fixture for creating test fundamentals

    Usage:
        # DART fundamentals (semi-annual)
        fundamentals_factory(ticker='005930', date='2024-03-31',
                            period_type='SEMI-ANNUAL', data_source='DART',
                            revenue=100000000000, ebitda=20000000000)

        # pykrx fundamentals (daily)
        fundamentals_factory(ticker='005930', date='2024-03-29',
                            period_type='DAILY', data_source='pykrx',
                            dividend_yield=2.5, per=15.0, pbr=1.2)
    """
    def _create_fundamentals(
        ticker: str,
        date: str,
        region: str = 'KR',
        fiscal_year: Optional[int] = None,
        period_type: str = 'DAILY',
        data_source: str = 'pykrx',
        **kwargs
    ) -> Dict:
        """Create test fundamentals"""

        # Default values based on data source
        if data_source == 'DART':
            defaults = {
                'revenue': random.randint(10000000000, 100000000000),
                'operating_income': random.randint(1000000000, 10000000000),
                'net_income': random.randint(500000000, 8000000000),
                'total_assets': random.randint(50000000000, 500000000000),
                'total_liabilities': random.randint(20000000000, 300000000000),
                'total_equity': random.randint(30000000000, 200000000000),
                'current_assets': random.randint(10000000000, 100000000000),
                'current_liabilities': random.randint(5000000000, 50000000000),
                'ebitda': random.randint(2000000000, 15000000000)
            }
        else:  # pykrx
            defaults = {
                'per': round(random.uniform(5.0, 30.0), 2),
                'pbr': round(random.uniform(0.5, 3.0), 2),
                'dividend_yield': round(random.uniform(0.0, 5.0), 2),
                'market_cap': random.randint(1000000000000, 500000000000000),
                'shares_outstanding': random.randint(100000000, 10000000000)
            }

        # Merge defaults with provided kwargs
        data = {**defaults, **kwargs}

        # Build INSERT query dynamically
        columns = ['ticker', 'region', 'date', 'fiscal_year', 'period_type', 'data_source']
        values = [ticker, region, date, fiscal_year, period_type, data_source]

        for key, value in data.items():
            columns.append(key)
            values.append(value)

        placeholders = ', '.join(['%s'] * len(values))
        columns_str = ', '.join(columns)

        query = f"""
            INSERT INTO ticker_fundamentals ({columns_str})
            VALUES ({placeholders})
            ON CONFLICT (ticker, region, date, period_type, data_source) DO UPDATE SET
                {', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col not in ['ticker', 'region', 'date', 'period_type', 'data_source']])}
        """

        postgres_test_db.execute_update(query, tuple(values))

        return {
            'ticker': ticker,
            'region': region,
            'date': date,
            'period_type': period_type,
            'data_source': data_source,
            **data
        }

    return _create_fundamentals


@pytest.fixture
def factor_score_factory(postgres_test_db):
    """
    Factory fixture for creating test factor scores

    Usage:
        factor_score_factory(ticker='005930', factor_name='Dividend_Yield',
                            score=-2.5, percentile=75.0)
    """
    def _create_factor_score(
        ticker: str,
        factor_name: str,
        date: Optional[str] = None,
        region: str = 'KR',
        score: Optional[float] = None,
        percentile: Optional[float] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create test factor score"""

        # Generate realistic data if not provided
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        if score is None:
            score = round(random.uniform(-5.0, 5.0), 4)
        if percentile is None:
            percentile = round(random.uniform(0.0, 100.0), 2)

        query = """
            INSERT INTO factor_scores (ticker, region, factor_name, date, score, percentile, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker, region, factor_name, date) DO UPDATE SET
                score = EXCLUDED.score,
                percentile = EXCLUDED.percentile,
                metadata = EXCLUDED.metadata
        """

        import json
        metadata_json = json.dumps(metadata) if metadata else None

        postgres_test_db.execute_update(query, (ticker, region, factor_name, date, score, percentile, metadata_json))

        return {
            'ticker': ticker,
            'region': region,
            'factor_name': factor_name,
            'date': date,
            'score': score,
            'percentile': percentile,
            'metadata': metadata
        }

    return _create_factor_score


@pytest.fixture
def ohlcv_factory(postgres_test_db):
    """
    Factory fixture for creating test OHLCV data

    Usage:
        # Single day
        ohlcv_factory(ticker='005930', date='2024-03-29', close=75000, volume=10000000)

        # Date range
        ohlcv_factory(ticker='005930', start_date='2024-01-01', end_date='2024-03-31')
    """
    def _create_ohlcv(
        ticker: str,
        region: str = 'KR',
        date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        timeframe: str = '1d',
        base_price: float = 50000,
        volatility: float = 0.02,
        volume_base: int = 10000000
    ) -> List[Dict]:
        """Create test OHLCV data"""

        # Single day mode
        if date and not start_date:
            open_price = round(base_price * (1 + random.uniform(-volatility, volatility)), 2)
            close_price = round(base_price * (1 + random.uniform(-volatility, volatility)), 2)
            high_price = round(max(open_price, close_price) * (1 + random.uniform(0, volatility)), 2)
            low_price = round(min(open_price, close_price) * (1 - random.uniform(0, volatility)), 2)
            volume = int(volume_base * random.uniform(0.5, 2.0))

            query = """
                INSERT INTO ohlcv_data (ticker, region, date, timeframe, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, region, date, timeframe) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume
            """

            postgres_test_db.execute_update(query, (ticker, region, date, timeframe, open_price, high_price, low_price, close_price, volume))

            return [{
                'ticker': ticker,
                'region': region,
                'date': date,
                'timeframe': timeframe,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume
            }]

        # Date range mode
        elif start_date and end_date:
            from datetime import datetime, timedelta
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')

            results = []
            current_date = start
            current_price = base_price

            while current_date <= end:
                # Skip weekends (simplified)
                if current_date.weekday() < 5:
                    # Simulate price movement (random walk)
                    current_price *= (1 + random.uniform(-volatility, volatility))

                    open_price = round(current_price * (1 + random.uniform(-volatility/2, volatility/2)), 2)
                    close_price = round(current_price * (1 + random.uniform(-volatility/2, volatility/2)), 2)
                    high_price = round(max(open_price, close_price) * (1 + random.uniform(0, volatility/2)), 2)
                    low_price = round(min(open_price, close_price) * (1 - random.uniform(0, volatility/2)), 2)
                    volume = int(volume_base * random.uniform(0.5, 2.0))

                    date_str = current_date.strftime('%Y-%m-%d')

                    query = """
                        INSERT INTO ohlcv_data (ticker, region, date, timeframe, open, high, low, close, volume)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (ticker, region, date, timeframe) DO UPDATE SET
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume
                    """

                    postgres_test_db.execute_update(query, (ticker, region, date_str, timeframe, open_price, high_price, low_price, close_price, volume))

                    results.append({
                        'ticker': ticker,
                        'region': region,
                        'date': date_str,
                        'timeframe': timeframe,
                        'open': open_price,
                        'high': high_price,
                        'low': low_price,
                        'close': close_price,
                        'volume': volume
                    })

                    current_price = close_price

                current_date += timedelta(days=1)

            return results

        else:
            raise ValueError("Must provide either 'date' or both 'start_date' and 'end_date'")

    return _create_ohlcv


# ============================================================================
# Mock Database Manager (Production Interface)
# ============================================================================

class MockPostgresDatabaseManager:
    """
    Mock PostgreSQL Database Manager for testing

    Provides same interface as production PostgresDatabaseManager
    but connects to temporary test database.
    """

    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password

        # Create connection pool
        self.conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )

        logger.info(f"✅ Mock PostgreSQL connection created: {database}")

    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """
        Execute SELECT query (returns all rows)

        Args:
            query: SQL SELECT query
            params: Query parameters

        Returns:
            List of dictionaries (rows)
        """
        cursor = self.conn.cursor(cursor_factory=extras.RealDictCursor)
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            return [dict(row) for row in results] if results else []
        finally:
            cursor.close()

    def execute_update(self, query: str, params: tuple = None) -> bool:
        """
        Execute INSERT/UPDATE/DELETE query

        Args:
            query: SQL INSERT/UPDATE/DELETE query
            params: Query parameters

        Returns:
            True if successful, False otherwise
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(query, params)
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            logger.error(f"❌ Execute update failed: {e}")
            return False
        finally:
            cursor.close()

    def close_pool(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("🔒 Mock PostgreSQL connection closed")
