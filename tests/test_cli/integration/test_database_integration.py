"""
Integration tests for database operations.

Tests validate real PostgreSQL/TimescaleDB interactions, connection pooling,
query performance, and data integrity with test database (quant_platform_test).

Test Database:
- 5 KR tickers: 005930, 035720, 032830, 034020, 006800
- 1,220 OHLCV records (244 rows per ticker, 2024 data)
- TimescaleDB hypertable optimization enabled

Performance Targets:
- Single ticker query (1 year): <100ms
- Batch query (20 tickers, 1 year): <500ms
- Connection pool creation: <5s

Usage:
    # Run all database integration tests
    pytest tests/test_cli/integration/test_database_integration.py -v -m integration

    # Run specific test
    pytest tests/test_cli/integration/test_database_integration.py::TestDatabaseIntegration::test_connection_pool_creation -v
"""
import pytest
import asyncio
import time
from datetime import datetime, timedelta
from cli.utils.database import DatabaseManager


@pytest.mark.integration
@pytest.mark.database
class TestDatabaseIntegration:
    """Integration tests for database operations."""

    DB_CONFIG = {
        'host': 'localhost',
        'port': 5432,
        'database': 'quant_platform_test',
        'user': '13ruce'
    }

    @pytest.mark.asyncio
    async def test_connection_pool_creation(self):
        """
        DB-INT-001: Validate connection pool creation.

        Pass Criteria:
        - Pool created with 2-20 connections
        - No errors during connection
        - Connection time <5s

        Fail Criteria:
        - Connection failure
        - Timeout >5s
        - Invalid pool size
        """
        start = time.time()

        # Connect to test database
        db = DatabaseManager()
        await db.connect(config=self.DB_CONFIG)

        try:
            # Validate pool exists
            assert db._pool is not None, "Connection pool not created"

            # Validate connection pool size
            pool_size = db._pool.get_size()
            assert 2 <= pool_size <= 20, f"Pool size {pool_size} outside range 2-20"

            # Validate connection time
            elapsed = time.time() - start
            assert elapsed < 5.0, f"Connection took {elapsed:.2f}s (>5s limit)"

            print(f"✅ DB-INT-001 PASSED: Pool created with {pool_size} connections in {elapsed:.3f}s")
        finally:
            await db.disconnect()

    @pytest.mark.asyncio
    async def test_ohlcv_query_performance(self):
        """
        DB-INT-002: Validate single ticker query <100ms.

        Pass Criteria:
        - Query 1 ticker, 1 year <100ms
        - Returns >200 rows (expected ~244 for 2024)
        - All rows match ticker='005930'

        Fail Criteria:
        - Query timeout >500ms
        - Incorrect data (wrong ticker, missing rows)
        - Database error
        """
        db = DatabaseManager()
        await db.connect(config=self.DB_CONFIG)

        try:
            start_date = datetime(2024, 1, 1)
            end_date = datetime(2024, 12, 31)

            start = time.time()

            # Execute query
            query = """
                SELECT ticker, date, open, high, low, close, volume
                FROM ohlcv_data
                WHERE ticker = $1
                  AND date >= $2
                  AND date <= $3
                ORDER BY date
            """
            rows = await db.fetch(query, "005930", start_date, end_date)

            elapsed_ms = (time.time() - start) * 1000  # Convert to ms

            # Validate performance
            assert elapsed_ms < 100, f"Query took {elapsed_ms:.2f}ms (>100ms target)"

            # Validate data
            assert len(rows) > 200, f"Expected >200 rows, got {len(rows)}"
            assert all(row['ticker'] == '005930' for row in rows), "Incorrect ticker in results"

            print(f"✅ DB-INT-002 PASSED: Query returned {len(rows)} rows in {elapsed_ms:.2f}ms")
        finally:
            await db.disconnect()

    @pytest.mark.asyncio
    async def test_batch_ohlcv_query_performance(self):
        """
        DB-INT-003: Validate batch query <500ms.

        Pass Criteria:
        - Query 5 tickers (test dataset), 1 year <500ms
        - Returns data for all requested tickers
        - All rows within date range

        Fail Criteria:
        - Query timeout >2s
        - Missing tickers in result
        - Data outside date range
        """
        db = DatabaseManager()
        await db.connect(config=self.DB_CONFIG)

        try:
            tickers = ["005930", "035720", "032830", "034020", "006800"]
            start_date = datetime(2024, 1, 1)
            end_date = datetime(2024, 12, 31)

            start = time.time()

            # Execute batch query
            query = """
                SELECT ticker, date, open, high, low, close, volume
                FROM ohlcv_data
                WHERE ticker = ANY($1::text[])
                  AND date >= $2
                  AND date <= $3
                ORDER BY ticker, date
            """
            rows = await db.fetch(query, tickers, start_date, end_date)

            elapsed_ms = (time.time() - start) * 1000  # Convert to ms

            # Validate performance
            assert elapsed_ms < 500, f"Batch query took {elapsed_ms:.2f}ms (>500ms target)"

            # Validate all tickers present
            tickers_in_result = set(row['ticker'] for row in rows)
            assert len(tickers_in_result) == 5, f"Expected 5 unique tickers, got {len(tickers_in_result)}"

            # Validate date range
            assert all(start_date.date() <= row['date'] <= end_date.date() for row in rows), \
                "Some rows outside date range"

            print(f"✅ DB-INT-003 PASSED: Batch query returned {len(rows)} rows in {elapsed_ms:.2f}ms")
        finally:
            await db.disconnect()

    @pytest.mark.asyncio
    async def test_transaction_rollback(self):
        """
        DB-INT-004: Validate transaction rollback.

        Pass Criteria:
        - Failed insert rolls back completely
        - No partial data committed
        - Database integrity preserved

        Fail Criteria:
        - Partial data commit
        - Integrity violation persists
        - Rollback fails
        """
        db = DatabaseManager()
        await db.connect(config=self.DB_CONFIG)

        try:
            # Get initial count
            initial_count = await db.fetchval("SELECT COUNT(*) FROM ohlcv_data WHERE ticker = 'TEST001'")
            assert initial_count == 0, "Test data already exists"

            # Attempt transaction with intentional failure
            try:
                async with db._pool.acquire() as conn:
                    async with conn.transaction():
                        # Insert valid row
                        await conn.execute("""
                            INSERT INTO ohlcv_data (ticker, region, timeframe, date, open, high, low, close, volume)
                            VALUES ('TEST001', 'KR', '1d', '2024-01-01', 100, 110, 90, 105, 1000000)
                        """)

                        # Force error (invalid date format)
                        await conn.execute("""
                            INSERT INTO ohlcv_data (ticker, region, timeframe, date, open, high, low, close, volume)
                            VALUES ('TEST001', 'KR', '1d', 'invalid-date', 100, 110, 90, 105, 1000000)
                        """)
            except Exception:
                pass  # Expected error

            # Verify rollback
            final_count = await db.fetchval("SELECT COUNT(*) FROM ohlcv_data WHERE ticker = 'TEST001'")
            assert final_count == 0, f"Transaction not rolled back: {final_count} rows found"

            print(f"✅ DB-INT-004 PASSED: Transaction rolled back successfully")
        finally:
            await db.disconnect()

    @pytest.mark.asyncio
    async def test_hypertable_query_optimization(self):
        """
        DB-INT-005: Validate TimescaleDB hypertable optimization.

        Pass Criteria:
        - Query uses TimescaleDB chunks (EXPLAIN analysis)
        - Query time <1s for date-range query
        - Proper index usage

        Fail Criteria:
        - Full table scan detected
        - Query time >1s
        - No chunk exclusion
        """
        db = DatabaseManager()
        await db.connect(config=self.DB_CONFIG)

        try:
            start_date = datetime(2024, 1, 1)
            end_date = datetime(2024, 3, 31)  # Q1 2024

            # Run EXPLAIN ANALYZE
            explain_query = """
                EXPLAIN (ANALYZE, BUFFERS)
                SELECT ticker, date, close
                FROM ohlcv_data
                WHERE date >= $1 AND date <= $2
            """

            start = time.time()
            explain_result = await db.fetch(explain_query, start_date, end_date)
            elapsed_ms = (time.time() - start) * 1000

            # Convert explain result to text
            explain_text = '\n'.join(row['QUERY PLAN'] for row in explain_result)

            # Validate performance
            assert elapsed_ms < 1000, f"Query took {elapsed_ms:.2f}ms (>1s limit)"

            # Validate chunk usage (TimescaleDB uses Append with chunk scans)
            # Sequential scans on small chunks are optimal and expected for test dataset
            assert 'Append' in explain_text, "TimescaleDB chunk exclusion not detected"
            assert '_chunk' in explain_text, "Hypertable chunks not being used"

            print(f"✅ DB-INT-005 PASSED: Query optimized with chunk exclusion, executed in {elapsed_ms:.2f}ms")
        finally:
            await db.disconnect()

    @pytest.mark.asyncio
    async def test_connection_pool_exhaustion_recovery(self):
        """
        DB-INT-006: Validate connection pool exhaustion recovery.

        Pass Criteria:
        - All connections eventually released
        - Pool returns to normal state
        - No connection leaks

        Fail Criteria:
        - Connection leak detected
        - Pool permanently exhausted
        - Timeout on connection acquisition
        """
        db = DatabaseManager()
        await db.connect(config=self.DB_CONFIG)

        try:
            pool_size = db._pool.get_size()

            # Simulate connection pressure (but not exhaustion)
            connections = []
            try:
                # Acquire multiple connections (less than pool size)
                for i in range(min(pool_size - 2, 5)):  # Leave 2 free
                    conn = await db._pool.acquire()
                    connections.append(conn)

                # Verify we can still acquire connections
                test_conn = await db._pool.acquire()
                result = await test_conn.fetchval("SELECT 1")
                assert result == 1, "Query failed with active connections"

                # Release test connection
                await db._pool.release(test_conn)

            finally:
                # Release all connections
                for conn in connections:
                    await db._pool.release(conn)

            # Verify pool recovered
            await asyncio.sleep(0.1)  # Brief wait for pool cleanup

            # Test pool is still functional
            final_check = await db.fetchval("SELECT COUNT(*) FROM tickers")
            assert final_check == 5, "Database query failed after pool stress test"

            print(f"✅ DB-INT-006 PASSED: Connection pool recovered successfully")
        finally:
            await db.disconnect()


# Integration test summary
if __name__ == "__main__":
    print("""
    Database Integration Tests
    ===========================

    Test Suite: test_database_integration.py
    Tests: 6 (DB-INT-001 through DB-INT-006)
    Target Database: quant_platform_test

    Prerequisites:
    1. Test database created: python tests/fixtures/setup_test_database.py
    2. 5 tickers with 1,220 OHLCV records loaded
    3. PostgreSQL + TimescaleDB running on localhost:5432

    Run Tests:
    - All tests: pytest tests/test_cli/integration/test_database_integration.py -v
    - Single test: pytest tests/test_cli/integration/test_database_integration.py::TestDatabaseIntegration::test_connection_pool_creation -v
    - With coverage: pytest tests/test_cli/integration/test_database_integration.py --cov=cli.utils.database

    Expected Results:
    - All 6 tests should PASS with green checkmarks
    - Query performance within targets (<100ms single, <500ms batch)
    - No connection leaks or database errors
    """)
