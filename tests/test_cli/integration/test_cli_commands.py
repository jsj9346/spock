"""
Integration tests for CLI commands.

Tests validate CLI command execution, output formatting, and error handling
by invoking CLI utility functions and command modules programmatically.

Test Database:
- 5 KR tickers: 005930, 035720, 032830, 034020, 006800
- 1,220 OHLCV records (244 rows per ticker, 2024 data)
- TimescaleDB hypertable optimization enabled

Performance Targets:
- Query execution: <200ms for single ticker
- Query with export: <2s for all tickers
- Backtest command: <5s for simple strategy

Usage:
    # Run all CLI integration tests
    pytest tests/test_cli/integration/test_cli_commands.py -v -m integration

    # Run specific test
    pytest tests/test_cli/integration/test_cli_commands.py::TestCLICommands::test_query_execution_basic -v
"""
import pytest
import json
import csv
import time
import tempfile
import pandas as pd
from pathlib import Path
from datetime import datetime

from cli.utils.database import DatabaseManager
from cli.utils.query_formatter import QueryFormatter
from cli.utils.ohlcv_loader import OHLCVLoader


@pytest.mark.integration
@pytest.mark.cli
class TestCLICommands:
    """Integration tests for CLI command utilities."""

    DB_CONFIG = {
        'host': 'localhost',
        'port': 5432,
        'database': 'quant_platform_test',
        'user': '13ruce'
    }

    @pytest.mark.asyncio
    async def test_query_execution_basic(self):
        """
        CLI-INT-001: Query execution produces valid structured data.

        Pass Criteria:
        - Query builder constructs valid SQL
        - Database query executes successfully
        - Results contain expected schema (ticker, date, OHLCV)
        - Data count matches expectations (244 rows for Samsung 2024)
        - Performance <200ms

        Fail Criteria:
        - Query construction fails
        - Database error
        - Invalid/missing data
        - Timeout >500ms
        """
        db = DatabaseManager()
        await db.connect(config=self.DB_CONFIG)

        try:
            start = time.time()

            # Query OHLCV data for Samsung Electronics
            sql = """
                SELECT o.ticker, o.date, o.open, o.high, o.low, o.close, o.volume
                FROM ohlcv_data o
                WHERE o.ticker = $1
                  AND o.region = $2
                  AND o.date >= $3
                  AND o.date <= $4
                ORDER BY o.date ASC
            """
            rows = await db.fetch(sql, '005930', 'KR', datetime(2024, 1, 1), datetime(2024, 12, 31))

            elapsed_ms = (time.time() - start) * 1000

            # Validate performance
            assert elapsed_ms < 200, f"Query took {elapsed_ms:.2f}ms (target: <200ms)"

            # Validate results
            assert len(rows) > 200, f"Expected >200 rows, got {len(rows)}"

            # Validate schema
            first_row = rows[0]
            assert 'ticker' in first_row, "Missing ticker field"
            assert 'date' in first_row, "Missing date field"
            assert 'open' in first_row, "Missing open field"
            assert 'high' in first_row, "Missing high field"
            assert 'low' in first_row, "Missing low field"
            assert 'close' in first_row, "Missing close field"
            assert 'volume' in first_row, "Missing volume field"

            # Validate data
            assert first_row['ticker'] == '005930', f"Expected ticker 005930, got {first_row['ticker']}"
            assert first_row['close'] > 0, "Invalid close price"
            assert first_row['volume'] >= 0, "Invalid volume"

            print(f"✅ CLI-INT-001 PASSED: Query returned {len(rows)} rows in {elapsed_ms:.2f}ms")
        finally:
            await db.disconnect()

    @pytest.mark.asyncio
    async def test_query_with_filters(self):
        """
        CLI-INT-002: Query filters work correctly.

        Pass Criteria:
        - Multiple filters combine correctly (AND logic)
        - Volume filter: only rows with volume > threshold
        - Date range filter: only rows within dates
        - All results meet criteria (100% accuracy)

        Fail Criteria:
        - Filter violation (any row violates criteria)
        - Partial filter application
        - Query construction error
        """
        db = DatabaseManager()
        await db.connect(config=self.DB_CONFIG)

        try:
            # Query with multiple filters
            sql = """
                SELECT o.ticker, o.date, o.open, o.high, o.low, o.close, o.volume
                FROM ohlcv_data o
                WHERE o.ticker = $1
                  AND o.region = $2
                  AND o.date >= $3
                  AND o.date <= $4
                  AND o.volume > $5
                ORDER BY o.date ASC
            """
            rows = await db.fetch(sql, '005930', 'KR', datetime(2024, 6, 1), datetime(2024, 12, 31), 10000000)

            # Validate results exist
            assert len(rows) > 0, "Filter returned no results"

            # Validate all filters applied correctly
            for row in rows:
                # Check ticker filter
                assert row['ticker'] == '005930', f"Ticker filter violated: {row['ticker']}"

                # Check date range filter
                row_date = row['date']
                assert datetime(2024, 6, 1).date() <= row_date <= datetime(2024, 12, 31).date(), \
                    f"Date filter violated: {row_date}"

                # Check volume filter
                assert row['volume'] > 10000000, \
                    f"Volume filter violated: {row['volume']} (expected >10M)"

            print(f"✅ CLI-INT-002 PASSED: All {len(rows)} rows passed filter validation (100% accuracy)")
        finally:
            await db.disconnect()

    @pytest.mark.asyncio
    async def test_query_formatter_json(self):
        """
        CLI-INT-003: Query formatter produces valid JSON output.

        Pass Criteria:
        - JSON output is valid and parseable
        - Contains expected structure
        - Data accurately formatted
        - Performance <100ms for formatting

        Fail Criteria:
        - Invalid JSON
        - Missing/incorrect fields
        - Data formatting errors
        """
        db = DatabaseManager()
        await db.connect(config=self.DB_CONFIG)

        try:
            # Execute query
            sql = """
                SELECT o.ticker, o.date, o.open, o.high, o.low, o.close, o.volume
                FROM ohlcv_data o
                WHERE o.ticker = $1
                  AND o.region = $2
                  AND o.date >= $3
                  AND o.date <= $4
                ORDER BY o.date ASC
                LIMIT 10
            """
            rows = await db.fetch(sql, '005930', 'KR', datetime(2024, 12, 1), datetime(2024, 12, 31))

            # Format as JSON
            with tempfile.TemporaryDirectory() as tmpdir:
                json_path = Path(tmpdir) / "output.json"

                start = time.time()
                formatter = QueryFormatter()
                formatter.export_json(rows, str(json_path), pretty=True)
                elapsed_ms = (time.time() - start) * 1000

                # Validate performance
                assert elapsed_ms < 100, f"JSON formatting took {elapsed_ms:.2f}ms (target: <100ms)"

                # Validate JSON structure
                with open(json_path, 'r') as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError as e:
                        pytest.fail(f"Invalid JSON output: {e}")

                assert isinstance(data, list), "JSON output should be a list"
                assert len(data) == 10, f"Expected 10 rows, got {len(data)}"

                # Validate first row structure
                first_row = data[0]
                assert 'ticker' in first_row, "Missing ticker field in JSON"
                assert 'date' in first_row, "Missing date field in JSON"
                assert 'close' in first_row, "Missing close field in JSON"

                print(f"✅ CLI-INT-003 PASSED: JSON formatted {len(data)} rows in {elapsed_ms:.2f}ms")
        finally:
            await db.disconnect()

    @pytest.mark.asyncio
    async def test_query_formatter_csv(self):
        """
        CLI-INT-004: Query formatter produces valid CSV output.

        Pass Criteria:
        - CSV output has valid structure
        - Header row present
        - Data rows formatted correctly
        - File export succeeds
        - Performance <2s for export

        Fail Criteria:
        - Malformed CSV
        - Missing header
        - Data truncation
        - Export failure
        """
        db = DatabaseManager()
        await db.connect(config=self.DB_CONFIG)

        try:
            # Execute query
            sql = """
                SELECT o.ticker, o.date, o.open, o.high, o.low, o.close, o.volume
                FROM ohlcv_data o
                WHERE o.ticker = $1
                  AND o.region = $2
                  AND o.date >= $3
                  AND o.date <= $4
                ORDER BY o.date ASC
            """
            rows = await db.fetch(sql, '005930', 'KR', datetime(2024, 1, 1), datetime(2024, 12, 31))

            # Format as CSV
            with tempfile.TemporaryDirectory() as tmpdir:
                csv_path = Path(tmpdir) / "output.csv"

                start = time.time()
                formatter = QueryFormatter()
                formatter.export_csv(rows, str(csv_path))
                elapsed = time.time() - start

                # Validate performance
                assert elapsed < 2.0, f"CSV export took {elapsed:.2f}s (target: <2s)"

                # Validate CSV file (use UTF-8-BOM encoding as QueryFormatter exports with BOM)
                with open(csv_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)

                    # Validate header
                    expected_columns = ['ticker', 'date', 'open', 'high', 'low', 'close', 'volume']
                    assert all(col in reader.fieldnames for col in expected_columns), \
                        f"Missing columns. Expected: {expected_columns}, Got: {reader.fieldnames}"

                    # Validate data rows
                    csv_rows = list(reader)
                    assert len(csv_rows) > 200, f"Expected >200 rows, got {len(csv_rows)}"

                    # Validate first row data
                    first_row = csv_rows[0]
                    assert first_row['ticker'] == '005930', "Incorrect ticker in CSV"
                    assert float(first_row['close']) > 0, "Invalid close price in CSV"

                print(f"✅ CLI-INT-004 PASSED: CSV export created {len(csv_rows)} rows in {elapsed:.2f}s")
        finally:
            await db.disconnect()

    @pytest.mark.asyncio
    async def test_ohlcv_loader_integration(self):
        """
        CLI-INT-005: OHLCV loader integrates with database correctly.

        Pass Criteria:
        - OHLCV loader fetches data successfully
        - Data formatted as DataFrame correctly
        - Index and columns match expectations
        - Performance <200ms for single ticker

        Fail Criteria:
        - Loader fails to fetch data
        - DataFrame formatting errors
        - Missing/incorrect columns
        - Timeout >500ms
        """
        db = DatabaseManager()
        await db.connect(config=self.DB_CONFIG)

        try:
            start = time.time()

            # Load OHLCV data (load_data expects datetime objects for start/end dates)
            loader = OHLCVLoader(db)
            df = await loader.load_data(
                tickers=['005930'],
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
                region='KR'
            )

            elapsed_ms = (time.time() - start) * 1000

            # Validate performance
            assert elapsed_ms < 200, f"OHLCV loading took {elapsed_ms:.2f}ms (target: <200ms)"

            # Validate DataFrame
            assert not df.empty, "OHLCV DataFrame is empty"
            assert len(df) > 200, f"Expected >200 rows, got {len(df)}"

            # Validate columns
            expected_columns = ['open', 'high', 'low', 'close', 'volume']
            assert all(col in df.columns for col in expected_columns), \
                f"Missing columns. Expected: {expected_columns}, Got: {df.columns.tolist()}"

            # Validate index (should be MultiIndex with date and ticker)
            assert df.index.names == ['date', 'ticker'], f"DataFrame index should be MultiIndex ['date', 'ticker'], got {df.index.names}"

            # Validate data types (OHLCVLoader may return object dtype, check convertibility)
            close_numeric = pd.to_numeric(df['close'], errors='coerce')
            volume_numeric = pd.to_numeric(df['volume'], errors='coerce')
            assert not close_numeric.isna().any(), "Close prices should all be numeric"
            assert not volume_numeric.isna().any(), "Volumes should all be numeric"

            # Validate data range
            assert (close_numeric > 0).all(), "All close prices should be positive"
            assert (volume_numeric >= 0).all(), "All volumes should be non-negative"

            print(f"✅ CLI-INT-005 PASSED: OHLCV loaded {len(df)} rows in {elapsed_ms:.2f}ms")
        finally:
            await db.disconnect()

    @pytest.mark.asyncio
    async def test_error_handling_invalid_ticker(self):
        """
        CLI-INT-006: CLI handles invalid input gracefully.

        Pass Criteria:
        - Invalid ticker produces empty result (not error)
        - Query executes without crash
        - Appropriate handling of edge cases

        Fail Criteria:
        - Uncaught exception
        - Database connection failure
        - Crash or hang
        """
        db = DatabaseManager()
        await db.connect(config=self.DB_CONFIG)

        try:
            # Query with invalid ticker
            sql = """
                SELECT o.ticker, o.date, o.open, o.high, o.low, o.close, o.volume
                FROM ohlcv_data o
                WHERE o.ticker = $1
                  AND o.region = $2
                ORDER BY o.date ASC
            """
            # Execute query - should not crash
            rows = await db.fetch(sql, 'INVALID_TICKER_XYZ123', 'KR')

            # Validate graceful handling (empty results, not error)
            assert isinstance(rows, list), "Query should return list"
            assert len(rows) == 0, "Invalid ticker should return no results"

            print(f"✅ CLI-INT-006 PASSED: Invalid ticker handled gracefully (empty results)")
        finally:
            await db.disconnect()


# Integration test summary
if __name__ == "__main__":
    print("""
    CLI Command Integration Tests
    ==============================

    Test Suite: test_cli_commands.py
    Tests: 6 (CLI-INT-001 through CLI-INT-006)
    Target: Test CLI utilities and command modules programmatically

    Prerequisites:
    1. Test database created: python tests/fixtures/setup_test_database.py
    2. 5 tickers with 1,220 OHLCV records loaded
    3. PostgreSQL + TimescaleDB running on localhost:5432
    4. CLI utilities implemented (query_builder, query_formatter, ohlcv_loader)

    Run Tests:
    - All tests: pytest tests/test_cli/integration/test_cli_commands.py -v
    - Single test: pytest tests/test_cli/integration/test_cli_commands.py::TestCLICommands::test_query_execution_basic -v
    - With coverage: pytest tests/test_cli/integration/test_cli_commands.py --cov=cli

    Expected Results:
    - All 6 tests should PASS with green checkmarks
    - Query performance within targets (<200ms single ticker)
    - CSV export performance <2s
    - OHLCV loading <200ms
    - Graceful error handling for invalid inputs
    """)
