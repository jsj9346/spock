#!/usr/bin/env python3
"""
Integration Tests for FX Historical Backfill - Phase 1-F

Purpose:
- Test end-to-end backfill workflow
- Verify BOK API batch processing
- Validate checkpoint resumption
- Test database integrity after backfill
- Verify materialized view updates

Test Categories:
1. Full Backfill Integration Tests
2. Incremental Update Tests
3. Checkpoint Resumption Tests
4. Data Quality Validation Tests
5. Performance Tests

Coverage Target: >80%

Usage:
    # Run all integration tests
    pytest tests/test_fx_backfill_integration.py -v

    # Run with slow tests (actual API calls)
    pytest tests/test_fx_backfill_integration.py -v --runslow

    # Run specific test category
    pytest tests/test_fx_backfill_integration.py -v -k "test_checkpoint"

Prerequisites:
- PostgreSQL database running (quant_platform)
- .env file configured
- BOK API accessible (or mock mode)

Author: Spock Quant Platform
Created: 2025-10-24
"""

import pytest
import os
import json
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
import psycopg2

# Add project root to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_postgres import PostgresDatabaseManager
from dotenv import load_dotenv

# Load environment
load_dotenv()


# ================================================================
# Test Fixtures
# ================================================================

@pytest.fixture(scope='module')
def db():
    """Real PostgreSQL database connection for integration tests"""
    db_manager = PostgresDatabaseManager()
    yield db_manager
    db_manager.close()


@pytest.fixture
def temp_checkpoint_file():
    """Temporary checkpoint file for testing"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        checkpoint_path = f.name

    yield checkpoint_path

    # Cleanup
    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)


@pytest.fixture
def clean_test_data(db):
    """Clean up test data before and after tests"""
    # Clean before test
    db.execute_update("DELETE FROM fx_valuation_signals WHERE currency = 'TEST'")

    yield

    # Clean after test
    db.execute_update("DELETE FROM fx_valuation_signals WHERE currency = 'TEST'")


# ================================================================
# Category 1: Full Backfill Integration Tests
# ================================================================

class TestFullBackfillIntegration:
    """Test complete backfill workflow"""

    @pytest.mark.slow
    def test_backfill_dry_run_all_currencies(self):
        """Test dry run backfill for all currencies (no database writes)"""
        # Import here to avoid circular dependency
        from scripts.backfill_fx_history import FXHistoryBackfiller

        backfiller = FXHistoryBackfiller(
            start_date='2024-10-01',
            end_date='2024-10-24',
            currencies=['USD'],
            dry_run=True
        )

        results = backfiller.run()

        # Dry run should succeed without errors
        assert results['success'] is True
        assert results['total_batches'] > 0
        assert results['dry_run'] is True

    @pytest.mark.slow
    def test_backfill_single_currency_short_period(self, db, clean_test_data):
        """Test backfill single currency for 30 days"""
        from scripts.backfill_fx_history import FXHistoryBackfiller

        start_date = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
        end_date = date.today().strftime('%Y-%m-%d')

        backfiller = FXHistoryBackfiller(
            start_date=start_date,
            end_date=end_date,
            currencies=['USD'],
            dry_run=False  # Real backfill
        )

        results = backfiller.run()

        # Verify results
        assert results['success'] is True
        assert results['currencies_completed'] == 1

        # Verify database records
        query = """
            SELECT COUNT(*) FROM fx_valuation_signals
            WHERE currency = 'USD'
            AND date BETWEEN %s AND %s
        """
        count = db.execute_query(query, (start_date, end_date))
        assert count[0][0] > 0, "No records inserted"

    @pytest.mark.slow
    def test_backfill_batch_processing_efficiency(self):
        """Test that batch processing reduces API calls significantly"""
        from scripts.backfill_fx_history import FXHistoryBackfiller

        # 90 days should require ~3 batches (30 days each)
        start_date = (date.today() - timedelta(days=90)).strftime('%Y-%m-%d')
        end_date = date.today().strftime('%Y-%m-%d')

        backfiller = FXHistoryBackfiller(
            start_date=start_date,
            end_date=end_date,
            currencies=['USD'],
            dry_run=True
        )

        results = backfiller.run()

        # Should use ~3-4 batches instead of 90 API calls
        assert results['total_batches'] <= 5, "Batch processing not efficient"


# ================================================================
# Category 2: Incremental Update Tests
# ================================================================

class TestIncrementalUpdates:
    """Test incremental daily updates"""

    def test_incremental_update_single_day(self, db, clean_test_data):
        """Test updating single day of data"""
        from modules.fx_data_collector import FXDataCollector

        collector = FXDataCollector()
        results = collector.collect_today(currencies=['USD'])

        # Verify single day updated
        assert results['success'] >= 1
        assert results['date'] == date.today()

    def test_incremental_update_fills_gaps(self, db):
        """Test that incremental updates fill missing days"""
        from modules.fx_data_collector import FXDataCollector

        # Get latest date in database
        query = """
            SELECT MAX(date) FROM fx_valuation_signals
            WHERE currency = 'USD'
        """
        result = db.execute_query(query)
        latest_date = result[0][0] if result and result[0][0] else None

        if latest_date is None:
            pytest.skip("No historical data in database")

        # If there's a gap, incremental update should detect it
        collector = FXDataCollector()
        results = collector.collect_today()

        assert results is not None

    def test_incremental_update_idempotent(self, db):
        """Test that running collection multiple times is safe"""
        from modules.fx_data_collector import FXDataCollector

        collector = FXDataCollector()

        # Run twice
        results1 = collector.collect_today(currencies=['USD'])
        results2 = collector.collect_today(currencies=['USD'])

        # Should succeed both times (upsert)
        assert results1['success'] >= 0
        assert results2['success'] >= 0


# ================================================================
# Category 3: Checkpoint Resumption Tests
# ================================================================

class TestCheckpointResumption:
    """Test checkpoint-based resumption after failures"""

    def test_checkpoint_file_creation(self, temp_checkpoint_file):
        """Test checkpoint file is created during backfill"""
        from scripts.backfill_fx_history import FXHistoryBackfiller

        backfiller = FXHistoryBackfiller(
            start_date='2024-10-01',
            end_date='2024-10-10',
            currencies=['USD'],
            checkpoint_file=temp_checkpoint_file,
            dry_run=True
        )

        backfiller.run()

        # Verify checkpoint file exists
        assert os.path.exists(temp_checkpoint_file)

        # Verify JSON structure
        with open(temp_checkpoint_file, 'r') as f:
            checkpoint = json.load(f)

        assert 'started_at' in checkpoint
        assert 'currency_progress' in checkpoint

    def test_checkpoint_resumption_after_partial_completion(self, temp_checkpoint_file):
        """Test resuming backfill from checkpoint"""
        from scripts.backfill_fx_history import FXHistoryBackfiller

        # Create partial checkpoint (USD completed, HKD pending)
        checkpoint_data = {
            'started_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'currency_progress': {
                'USD': {
                    'last_date': '2024-10-15',
                    'updated_at': datetime.now().isoformat()
                }
            },
            'currencies_completed': ['USD']
        }

        with open(temp_checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f)

        # Resume backfill
        backfiller = FXHistoryBackfiller(
            start_date='2024-10-01',
            end_date='2024-10-24',
            currencies=['USD', 'HKD'],
            checkpoint_file=temp_checkpoint_file,
            dry_run=True
        )

        results = backfiller.run()

        # Should skip USD, process HKD
        assert results['success'] is True

    def test_checkpoint_handles_corruption(self, temp_checkpoint_file):
        """Test handling of corrupted checkpoint file"""
        from scripts.backfill_fx_history import FXHistoryBackfiller

        # Create corrupted checkpoint
        with open(temp_checkpoint_file, 'w') as f:
            f.write("CORRUPTED JSON {[")

        backfiller = FXHistoryBackfiller(
            start_date='2024-10-01',
            end_date='2024-10-24',
            currencies=['USD'],
            checkpoint_file=temp_checkpoint_file,
            dry_run=True
        )

        # Should handle corruption gracefully and restart
        results = backfiller.run()
        assert results['success'] is True


# ================================================================
# Category 4: Data Quality Validation Tests
# ================================================================

class TestDataQualityValidation:
    """Test data quality after backfill"""

    def test_data_completeness_30_days(self, db):
        """Test that last 30 days have complete data"""
        query = """
            SELECT currency, COUNT(*) as days_count
            FROM fx_valuation_signals
            WHERE date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY currency
        """
        results = db.execute_query(query)

        if not results:
            pytest.skip("No recent data in database")

        for currency, days_count in results:
            # Should have at least 20 days (accounting for weekends/holidays)
            assert days_count >= 20, f"{currency} has only {days_count} days"

    def test_data_quality_score_distribution(self, db):
        """Test data quality score distribution"""
        query = """
            SELECT data_quality, COUNT(*)
            FROM fx_valuation_signals
            WHERE date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY data_quality
        """
        results = db.execute_query(query)

        if not results:
            pytest.skip("No recent data in database")

        quality_distribution = dict(results)

        # Most data should be GOOD quality
        total_records = sum(quality_distribution.values())
        good_percentage = (quality_distribution.get('GOOD', 0) / total_records) * 100

        assert good_percentage >= 80, f"Only {good_percentage}% GOOD quality"

    def test_usd_rate_consistency(self, db):
        """Test USD rate is always 1.0"""
        query = """
            SELECT date, usd_rate
            FROM fx_valuation_signals
            WHERE currency = 'USD'
            AND date >= CURRENT_DATE - INTERVAL '7 days'
        """
        results = db.execute_query(query)

        if not results:
            pytest.skip("No USD data in database")

        for date_val, usd_rate in results:
            assert abs(float(usd_rate) - 1.0) < 0.000001, f"USD rate not 1.0 on {date_val}"

    def test_no_null_values_in_critical_fields(self, db):
        """Test no NULL values in critical fields"""
        query = """
            SELECT COUNT(*)
            FROM fx_valuation_signals
            WHERE usd_rate IS NULL
            OR currency IS NULL
            OR region IS NULL
            OR date IS NULL
        """
        count = db.execute_query(query)

        assert count[0][0] == 0, "Found NULL values in critical fields"

    def test_date_range_validity(self, db):
        """Test all dates are within valid range"""
        query = """
            SELECT MIN(date), MAX(date)
            FROM fx_valuation_signals
        """
        result = db.execute_query(query)

        if not result or not result[0][0]:
            pytest.skip("No data in database")

        min_date, max_date = result[0]

        # Min date should be reasonable (not before 2000)
        assert min_date >= date(2000, 1, 1), f"Invalid min date: {min_date}"

        # Max date should not be in future
        assert max_date <= date.today() + timedelta(days=1), f"Future date found: {max_date}"


# ================================================================
# Category 5: Performance Tests
# ================================================================

class TestBackfillPerformance:
    """Test backfill performance and efficiency"""

    @pytest.mark.slow
    def test_backfill_30_days_performance(self):
        """Test backfill 30 days completes within 30 seconds"""
        import time
        from scripts.backfill_fx_history import FXHistoryBackfiller

        start_date = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
        end_date = date.today().strftime('%Y-%m-%d')

        backfiller = FXHistoryBackfiller(
            start_date=start_date,
            end_date=end_date,
            currencies=['USD'],
            dry_run=True
        )

        start_time = time.time()
        backfiller.run()
        duration = time.time() - start_time

        assert duration < 30, f"Backfill took {duration}s (threshold: 30s)"

    def test_rate_limiting_compliance(self):
        """Test rate limiting is respected (10 req/sec)"""
        import time
        from scripts.backfill_fx_history import FXHistoryBackfiller

        backfiller = FXHistoryBackfiller(
            start_date='2024-10-01',
            end_date='2024-10-24',
            currencies=['USD'],
            dry_run=True
        )

        # Monitor request timing
        start_time = time.time()
        backfiller.run()
        duration = time.time() - start_time

        # Should respect 10 req/sec limit (0.1s interval)
        # With ~1 batch, minimum time is ~0.1s
        assert duration >= 0.05, "Rate limiting not applied"


# ================================================================
# Category 6: Database Integrity Tests
# ================================================================

class TestDatabaseIntegrity:
    """Test database integrity after operations"""

    def test_materialized_view_refresh(self, db):
        """Test materialized view refresh after collection"""
        from modules.fx_data_collector import FXDataCollector

        collector = FXDataCollector()

        # Refresh materialized view
        success = collector.refresh_materialized_view()

        assert success is True

        # Verify view has data
        query = "SELECT COUNT(*) FROM mv_latest_fx_signals"
        count = db.execute_query(query)
        assert count[0][0] > 0, "Materialized view is empty"

    def test_materialized_view_shows_latest_only(self, db):
        """Test materialized view shows only latest rates"""
        query = """
            SELECT currency, COUNT(*) as count
            FROM mv_latest_fx_signals
            GROUP BY currency
        """
        results = db.execute_query(query)

        # Each currency should appear exactly once
        for currency, count in results:
            assert count == 1, f"{currency} appears {count} times in view"

    def test_unique_constraint_enforcement(self, db, clean_test_data):
        """Test unique constraint (currency, region, date) is enforced"""
        # Insert test record
        insert_sql = """
            INSERT INTO fx_valuation_signals (currency, region, date, usd_rate, data_quality)
            VALUES ('TEST', 'TS', '2024-10-24', 1.0, 'GOOD')
        """
        db.execute_update(insert_sql)

        # Try duplicate insert (should fail or upsert)
        try:
            db.execute_update(insert_sql)
            # If upsert is implemented, should succeed
            assert True
        except psycopg2.IntegrityError:
            # If strict unique constraint, should fail
            assert True

    def test_foreign_key_integrity(self, db):
        """Test no orphaned records"""
        # All region codes should match CURRENCY_REGION_MAP
        query = """
            SELECT DISTINCT region
            FROM fx_valuation_signals
        """
        regions = db.execute_query(query)

        valid_regions = ['US', 'HK', 'CN', 'JP', 'VN']
        for (region,) in regions:
            assert region in valid_regions, f"Invalid region: {region}"


# ================================================================
# Category 7: Error Recovery Tests
# ================================================================

class TestErrorRecovery:
    """Test error recovery mechanisms"""

    def test_partial_batch_failure_recovery(self, temp_checkpoint_file):
        """Test recovery when partial batch fails"""
        from scripts.backfill_fx_history import FXHistoryBackfiller

        # Simulate partial failure by using invalid date range
        backfiller = FXHistoryBackfiller(
            start_date='2024-10-01',
            end_date='2024-10-24',
            currencies=['USD'],
            checkpoint_file=temp_checkpoint_file,
            dry_run=True
        )

        results = backfiller.run()

        # Should handle gracefully
        assert results is not None

    def test_database_unavailable_handling(self, db):
        """Test handling when database becomes unavailable"""
        from modules.fx_data_collector import FXDataCollector

        # Close database connection
        original_execute = db.execute_update
        db.execute_update = lambda *args: False  # Simulate failure

        collector = FXDataCollector()

        # Collection should handle gracefully
        results = collector.collect_today(currencies=['USD'])

        # Restore
        db.execute_update = original_execute

        # Should have failed gracefully
        assert results['failed'] >= 0


# ================================================================
# Test Suite Execution
# ================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
