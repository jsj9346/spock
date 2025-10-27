"""
Migration Validation Test Suite

Comprehensive tests to validate SQLite to PostgreSQL migration success:
- Schema integrity (tables, columns, constraints)
- Data completeness (row counts, foreign keys)
- Data quality (NULL handling, data types, indexes)
- Performance (query speed, connection pooling)
"""

import pytest
import psycopg2
from datetime import datetime, date
from modules.db_manager_postgres import PostgresDatabaseManager


class TestMigrationSchemaIntegrity:
    """Test PostgreSQL schema integrity after migration"""

    @pytest.fixture(scope="class")
    def pg_manager(self):
        """PostgreSQL database manager fixture"""
        manager = PostgresDatabaseManager()
        yield manager
        manager.close()

    def test_all_tables_exist(self, pg_manager):
        """Verify all expected tables exist"""
        expected_tables = [
            'tickers', 'stock_details', 'etf_details', 'etf_holdings',
            'ohlcv_data', 'technical_analysis', 'ticker_fundamentals',
            'trades', 'portfolio', 'market_sentiment',
            'global_market_indices', 'exchange_rate_history'
        ]

        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
        """

        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            actual_tables = {row[0] for row in cursor.fetchall()}

        for table in expected_tables:
            assert table in actual_tables, f"Table {table} not found in PostgreSQL"

    def test_tickers_schema(self, pg_manager):
        """Verify tickers table schema"""
        query = """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'tickers'
            ORDER BY ordinal_position
        """

        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            columns = {row[0]: {'type': row[1], 'nullable': row[2]}
                      for row in cursor.fetchall()}

        # Check required columns
        assert 'ticker' in columns
        assert 'region' in columns
        assert 'name' in columns
        assert 'sector' in columns
        assert 'market_cap' in columns

        # Check NOT NULL constraints
        assert columns['ticker']['nullable'] == 'NO'
        assert columns['region']['nullable'] == 'NO'

    def test_ohlcv_data_hypertable(self, pg_manager):
        """Verify ohlcv_data is a TimescaleDB hypertable"""
        query = """
            SELECT h.table_name, h.associated_schema_name, d.time_column_name
            FROM _timescaledb_catalog.hypertable h
            LEFT JOIN _timescaledb_catalog.dimension d ON h.id = d.hypertable_id
            WHERE h.table_name = 'ohlcv_data'
        """

        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            result = cursor.fetchone()

        assert result is not None, "ohlcv_data is not a hypertable"
        assert result[2] == 'date', f"Time column should be 'date', got {result[2]}"

    def test_foreign_key_constraints(self, pg_manager):
        """Verify foreign key constraints exist"""
        query = """
            SELECT
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = 'public'
        """

        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            fk_constraints = cursor.fetchall()

        # Should have multiple foreign key constraints
        assert len(fk_constraints) >= 5, f"Expected at least 5 FK constraints, found {len(fk_constraints)}"

        # Verify specific constraints
        fk_map = {(row[0], row[1]): row[2] for row in fk_constraints}

        # stock_details → tickers
        assert ('stock_details', 'ticker') in fk_map
        assert fk_map[('stock_details', 'ticker')] == 'tickers'

        # etf_details → tickers
        assert ('etf_details', 'ticker') in fk_map
        assert fk_map[('etf_details', 'ticker')] == 'tickers'

    def test_indexes_created(self, pg_manager):
        """Verify indexes are created on key columns"""
        query = """
            SELECT
                tablename,
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND tablename IN ('tickers', 'ohlcv_data', 'stock_details')
        """

        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            indexes = cursor.fetchall()

        assert len(indexes) > 0, "No indexes found"

        # Convert to set of index names
        index_names = {row[1] for row in indexes}

        # Check for important indexes
        tickers_pkey_exists = any('tickers' in idx and 'pkey' in idx for idx in index_names)
        assert tickers_pkey_exists, "Primary key index on tickers not found"


class TestMigrationDataCompleteness:
    """Test data migration completeness"""

    @pytest.fixture(scope="class")
    def pg_manager(self):
        """PostgreSQL database manager fixture"""
        manager = PostgresDatabaseManager()
        yield manager
        manager.close()

    def test_tickers_count(self, pg_manager):
        """Verify tickers migrated successfully"""
        query = "SELECT COUNT(*) FROM tickers"

        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            count = cursor.fetchone()[0]

        # Should have migrated 18,661 tickers
        assert count == 18661, f"Expected 18,661 tickers, found {count}"

    def test_ohlcv_data_count(self, pg_manager):
        """Verify OHLCV data migrated successfully"""
        query = "SELECT COUNT(*) FROM ohlcv_data"

        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            count = cursor.fetchone()[0]

        # Should have migrated 926,325 OHLCV records
        assert count == 926325, f"Expected 926,325 OHLCV records, found {count}"

    def test_stock_details_count(self, pg_manager):
        """Verify stock details migrated successfully"""
        query = "SELECT COUNT(*) FROM stock_details"

        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            count = cursor.fetchone()[0]

        # Should have migrated 17,600 stock details (after orphan cleanup)
        assert count == 17600, f"Expected 17,600 stock details, found {count}"

    def test_etf_details_count(self, pg_manager):
        """Verify ETF details migrated successfully"""
        query = "SELECT COUNT(*) FROM etf_details"

        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            count = cursor.fetchone()[0]

        # Should have migrated 893 ETF details (after orphan cleanup)
        assert count == 893, f"Expected 893 ETF details, found {count}"

    def test_region_distribution(self, pg_manager):
        """Verify region distribution in tickers"""
        query = """
            SELECT region, COUNT(*) as count
            FROM tickers
            GROUP BY region
            ORDER BY count DESC
        """

        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            regions = {row[0]: row[1] for row in cursor.fetchall()}

        # Verify expected regions exist
        expected_regions = ['US', 'JP', 'CN', 'HK', 'KR', 'VN']
        for region in expected_regions:
            assert region in regions, f"Region {region} not found"

        # Verify counts match migration results
        assert regions['US'] == 6532, f"Expected 6,532 US tickers, found {regions['US']}"
        assert regions['JP'] == 4036, f"Expected 4,036 JP tickers, found {regions['JP']}"
        assert regions['CN'] == 3450, f"Expected 3,450 CN tickers, found {regions['CN']}"
        assert regions['HK'] == 2722, f"Expected 2,722 HK tickers, found {regions['HK']}"
        assert regions['KR'] == 1364, f"Expected 1,364 KR tickers, found {regions['KR']}"
        assert regions['VN'] == 557, f"Expected 557 VN tickers, found {regions['VN']}"

    def test_no_orphaned_stock_details(self, pg_manager):
        """Verify no orphaned stock_details records"""
        query = """
            SELECT COUNT(*)
            FROM stock_details sd
            WHERE NOT EXISTS (
                SELECT 1 FROM tickers t
                WHERE t.ticker = sd.ticker AND t.region = sd.region
            )
        """

        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            orphans = cursor.fetchone()[0]

        assert orphans == 0, f"Found {orphans} orphaned stock_details records"

    def test_no_orphaned_etf_details(self, pg_manager):
        """Verify no orphaned etf_details records"""
        query = """
            SELECT COUNT(*)
            FROM etf_details ed
            WHERE NOT EXISTS (
                SELECT 1 FROM tickers t
                WHERE t.ticker = ed.ticker AND t.region = ed.region
            )
        """

        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            orphans = cursor.fetchone()[0]

        assert orphans == 0, f"Found {orphans} orphaned etf_details records"


class TestMigrationDataQuality:
    """Test data quality after migration"""

    @pytest.fixture(scope="class")
    def pg_manager(self):
        """PostgreSQL database manager fixture"""
        manager = PostgresDatabaseManager()
        yield manager
        manager.close()

    def test_no_null_required_fields_tickers(self, pg_manager):
        """Verify no NULL values in required ticker fields"""
        query = """
            SELECT
                COUNT(*) as total,
                COUNT(ticker) as has_ticker,
                COUNT(region) as has_region,
                COUNT(name) as has_name
            FROM tickers
        """

        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            result = cursor.fetchone()

        total, has_ticker, has_region, has_name = result
        assert has_ticker == total, f"Found NULL tickers: {total - has_ticker}"
        assert has_region == total, f"Found NULL regions: {total - has_region}"
        assert has_name == total, f"Found NULL names: {total - has_name}"

    def test_no_null_required_fields_ohlcv(self, pg_manager):
        """Verify no NULL values in required OHLCV fields"""
        query = """
            SELECT
                COUNT(*) as total,
                COUNT(ticker) as has_ticker,
                COUNT(region) as has_region,
                COUNT(date) as has_date,
                COUNT(close) as has_close
            FROM ohlcv_data
        """

        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            result = cursor.fetchone()

        total, has_ticker, has_region, has_date, has_close = result
        assert has_ticker == total, f"Found NULL tickers: {total - has_ticker}"
        assert has_region == total, f"Found NULL regions: {total - has_region}"
        assert has_date == total, f"Found NULL dates: {total - has_date}"
        assert has_close == total, f"Found NULL close prices: {total - has_close}"

    def test_data_type_conversion_booleans(self, pg_manager):
        """Verify SQLite 0/1 converted to PostgreSQL TRUE/FALSE"""
        query = """
            SELECT is_active
            FROM tickers
            WHERE is_active IS NOT NULL
            LIMIT 10
        """

        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()

        # Check that all boolean values are actual booleans
        for row in results:
            assert isinstance(row[0], bool), f"Expected boolean, got {type(row[0])}"

    def test_data_type_conversion_timestamps(self, pg_manager):
        """Verify timestamp conversion"""
        query = """
            SELECT created_at, last_updated
            FROM tickers
            WHERE created_at IS NOT NULL
            LIMIT 10
        """

        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()

        # Check that timestamps are proper datetime objects
        for row in results:
            if row[0]:
                assert isinstance(row[0], datetime), f"Expected datetime, got {type(row[0])}"

    def test_ohlcv_price_ranges(self, pg_manager):
        """Verify OHLCV prices are within reasonable ranges"""
        query = """
            SELECT
                MIN(open) as min_open,
                MAX(open) as max_open,
                MIN(high) as min_high,
                MAX(high) as max_high,
                MIN(low) as min_low,
                MAX(low) as max_low,
                MIN(close) as min_close,
                MAX(close) as max_close,
                MIN(volume) as min_volume
            FROM ohlcv_data
        """

        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            result = cursor.fetchone()

        min_open, max_open, min_high, max_high, min_low, max_low, min_close, max_close, min_volume = result

        # Prices should be positive
        assert min_open > 0, f"Invalid min_open: {min_open}"
        assert min_high > 0, f"Invalid min_high: {min_high}"
        assert min_low > 0, f"Invalid min_low: {min_low}"
        assert min_close > 0, f"Invalid min_close: {min_close}"

        # Volume should be non-negative
        assert min_volume >= 0, f"Invalid min_volume: {min_volume}"

    def test_ohlcv_high_low_relationship(self, pg_manager):
        """Verify high >= low for all OHLCV records"""
        query = """
            SELECT COUNT(*)
            FROM ohlcv_data
            WHERE high < low
        """

        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            invalid_count = cursor.fetchone()[0]

        assert invalid_count == 0, f"Found {invalid_count} records with high < low"


class TestMigrationPerformance:
    """Test database performance after migration"""

    @pytest.fixture(scope="class")
    def pg_manager(self):
        """PostgreSQL database manager fixture"""
        manager = PostgresDatabaseManager()
        yield manager
        manager.close()

    def test_ticker_query_performance(self, pg_manager):
        """Verify ticker queries execute quickly"""
        import time

        query = "SELECT * FROM tickers WHERE region = 'KR' LIMIT 100"

        start = time.time()
        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
        elapsed = time.time() - start

        assert len(results) <= 100
        assert elapsed < 0.5, f"Query took {elapsed:.2f}s, expected < 0.5s"

    def test_ohlcv_query_performance(self, pg_manager):
        """Verify OHLCV queries execute quickly with TimescaleDB"""
        import time

        query = """
            SELECT * FROM ohlcv_data
            WHERE ticker = '005930' AND region = 'KR'
            AND date >= '2024-01-01'
            ORDER BY date DESC
            LIMIT 100
        """

        start = time.time()
        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
        elapsed = time.time() - start

        assert elapsed < 0.5, f"Query took {elapsed:.2f}s, expected < 0.5s"

    def test_connection_pool_efficiency(self, pg_manager):
        """Verify connection pool is working efficiently"""
        import time

        # Get 10 connections in sequence
        start = time.time()
        for _ in range(10):
            with pg_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
        elapsed = time.time() - start

        # Should be fast with connection pooling
        assert elapsed < 1.0, f"10 queries took {elapsed:.2f}s, expected < 1.0s"

    def test_bulk_insert_performance(self, pg_manager):
        """Verify bulk insert performance"""
        import time

        # Create test data
        test_tickers = [
            {
                'ticker': f'TEST{i:04d}',
                'region': 'US',
                'name': f'Test Company {i}',
                'sector': 'Technology',
                'market_cap': 1000000000 * (i + 1)
            }
            for i in range(100)
        ]

        start = time.time()
        for ticker_data in test_tickers:
            pg_manager.insert_ticker(ticker_data)
        elapsed = time.time() - start

        # Should insert 100 tickers in < 5 seconds
        assert elapsed < 5.0, f"Bulk insert took {elapsed:.2f}s, expected < 5.0s"

        # Cleanup
        with pg_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tickers WHERE ticker LIKE 'TEST%'")
            conn.commit()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
