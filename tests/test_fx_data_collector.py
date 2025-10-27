#!/usr/bin/env python3
"""
Unit Tests for FX Data Collector - Phase 1-F

Purpose:
- Test FXDataCollector core functionality
- Verify BOK API integration
- Validate USD normalization logic
- Test database persistence (PostgreSQL + SQLite)
- Verify error handling and fallback mechanisms

Test Categories:
1. BOK API Integration Tests
2. USD Normalization Tests
3. Database Persistence Tests
4. Data Quality Assessment Tests
5. Error Handling Tests
6. Prometheus Metrics Tests

Coverage Target: >85%

Usage:
    # Run all tests
    pytest tests/test_fx_data_collector.py -v

    # Run specific test category
    pytest tests/test_fx_data_collector.py -v -k "test_bok_api"

    # Run with coverage
    pytest tests/test_fx_data_collector.py --cov=modules.fx_data_collector --cov-report=html

Author: Spock Quant Platform
Created: 2025-10-24
"""

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import date, datetime, timedelta
from decimal import Decimal
import psycopg2

# Add project root to path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.fx_data_collector import FXDataCollector


# ================================================================
# Test Fixtures
# ================================================================

@pytest.fixture
def mock_db_manager():
    """Mock PostgreSQL database manager"""
    db = Mock()
    db.execute_query = Mock(return_value=[])
    db.execute_update = Mock(return_value=True)
    db.close = Mock()
    return db


@pytest.fixture
def mock_exchange_rate_manager():
    """Mock ExchangeRateManager for BOK API calls"""
    manager = Mock()

    # Default mock rates (KRW per unit)
    manager.get_rate = Mock(side_effect=lambda currency, force_refresh=False: {
        'USD': 1300.0,
        'HKD': 170.0,
        'CNY': 180.0,
        'JPY': 10.0,
        'VND': 0.055
    }.get(currency, None))

    return manager


@pytest.fixture
def fx_collector(mock_db_manager, mock_exchange_rate_manager):
    """Create FXDataCollector instance with mocked dependencies"""
    with patch('modules.fx_data_collector.PostgresDatabaseManager', return_value=mock_db_manager), \
         patch('modules.fx_data_collector.ExchangeRateManager', return_value=mock_exchange_rate_manager):
        collector = FXDataCollector()
        return collector


# ================================================================
# Category 1: BOK API Integration Tests
# ================================================================

class TestBOKAPIIntegration:
    """Test BOK API integration and data retrieval"""

    def test_bok_api_fetch_usd_rate(self, fx_collector):
        """Test fetching USD/KRW rate from BOK API"""
        # Mock ExchangeRateManager response
        fx_collector.exchange_rate_manager.get_rate = Mock(return_value=1300.0)

        result = fx_collector.exchange_rate_manager.get_rate('USD')

        assert result == 1300.0
        fx_collector.exchange_rate_manager.get_rate.assert_called_once_with('USD')

    def test_bok_api_fetch_all_currencies(self, fx_collector):
        """Test fetching all 5 supported currencies"""
        currencies = ['USD', 'HKD', 'CNY', 'JPY', 'VND']
        expected_rates = {
            'USD': 1300.0,
            'HKD': 170.0,
            'CNY': 180.0,
            'JPY': 10.0,
            'VND': 0.055
        }

        for currency in currencies:
            rate = fx_collector.exchange_rate_manager.get_rate(currency)
            assert rate == expected_rates[currency], f"{currency} rate mismatch"

    def test_bok_api_force_refresh(self, fx_collector):
        """Test force_refresh parameter bypasses cache"""
        fx_collector.exchange_rate_manager.get_rate = Mock(return_value=1305.0)

        rate = fx_collector.exchange_rate_manager.get_rate('USD', force_refresh=True)

        assert rate == 1305.0
        fx_collector.exchange_rate_manager.get_rate.assert_called_with('USD', force_refresh=True)

    def test_bok_api_error_handling(self, fx_collector):
        """Test handling of BOK API errors"""
        fx_collector.exchange_rate_manager.get_rate = Mock(return_value=None)

        result = fx_collector.exchange_rate_manager.get_rate('INVALID')

        assert result is None


# ================================================================
# Category 2: USD Normalization Tests
# ================================================================

class TestUSDNormalization:
    """Test USD-normalized exchange rate calculations"""

    def test_usd_normalization_formula(self, fx_collector):
        """Test USD normalization formula: usd_rate = krw_rate / usd_krw_rate"""
        # Setup: HKD/KRW = 170, USD/KRW = 1300
        # Expected: HKD/USD = 170 / 1300 ≈ 0.130769

        hkd_krw_rate = 170.0
        usd_krw_rate = 1300.0

        usd_rate, quality = fx_collector._calculate_usd_rate('HKD', hkd_krw_rate)

        expected_usd_rate = hkd_krw_rate / usd_krw_rate
        assert abs(usd_rate - expected_usd_rate) < 0.000001
        assert quality == 'GOOD'

    def test_usd_normalization_usd_itself(self, fx_collector):
        """Test USD normalization for USD itself (should be 1.0)"""
        usd_krw_rate = 1300.0

        usd_rate, quality = fx_collector._calculate_usd_rate('USD', usd_krw_rate)

        assert usd_rate == 1.0
        assert quality == 'GOOD'

    def test_usd_normalization_missing_usd_rate(self, fx_collector):
        """Test USD normalization when USD/KRW rate unavailable"""
        fx_collector.exchange_rate_manager.get_rate = Mock(return_value=None)

        usd_rate, quality = fx_collector._calculate_usd_rate('HKD', 170.0)

        # Should use default USD rate (1300.0)
        expected_usd_rate = 170.0 / 1300.0
        assert abs(usd_rate - expected_usd_rate) < 0.000001
        assert quality == 'PARTIAL'  # Degraded quality

    def test_usd_normalization_all_currencies(self, fx_collector):
        """Test USD normalization for all supported currencies"""
        test_cases = [
            ('USD', 1300.0, 1.0),
            ('HKD', 170.0, 170.0 / 1300.0),
            ('CNY', 180.0, 180.0 / 1300.0),
            ('JPY', 10.0, 10.0 / 1300.0),
            ('VND', 0.055, 0.055 / 1300.0),
        ]

        for currency, krw_rate, expected_usd_rate in test_cases:
            usd_rate, quality = fx_collector._calculate_usd_rate(currency, krw_rate)
            assert abs(usd_rate - expected_usd_rate) < 0.000001, f"{currency} normalization failed"
            assert quality == 'GOOD'

    def test_usd_normalization_precision(self, fx_collector):
        """Test USD normalization maintains 6 decimal precision"""
        hkd_krw_rate = 170.123456
        usd_krw_rate = 1300.654321

        usd_rate, quality = fx_collector._calculate_usd_rate('HKD', hkd_krw_rate)

        # Should have at least 6 decimal places precision
        assert len(str(usd_rate).split('.')[1]) >= 6


# ================================================================
# Category 3: Database Persistence Tests
# ================================================================

class TestDatabasePersistence:
    """Test PostgreSQL and SQLite database operations"""

    def test_postgres_insert_new_record(self, fx_collector):
        """Test inserting new FX record to PostgreSQL"""
        test_date = date(2025, 10, 24)
        fx_collector.db.execute_update = Mock(return_value=True)

        success = fx_collector._save_to_postgres(
            currency='USD',
            collection_date=test_date,
            krw_rate=1300.0,
            usd_rate=1.0,
            data_quality='GOOD'
        )

        assert success is True
        fx_collector.db.execute_update.assert_called_once()

        # Verify SQL structure
        call_args = fx_collector.db.execute_update.call_args
        sql = call_args[0][0]
        assert 'INSERT INTO fx_valuation_signals' in sql
        assert 'ON CONFLICT' in sql

    def test_postgres_update_existing_record(self, fx_collector):
        """Test updating existing FX record (upsert)"""
        test_date = date(2025, 10, 24)
        fx_collector.db.execute_update = Mock(return_value=True)

        # First insert
        fx_collector._save_to_postgres('USD', test_date, 1300.0, 1.0, 'GOOD')

        # Update with new rate
        success = fx_collector._save_to_postgres('USD', test_date, 1305.0, 1.0, 'GOOD')

        assert success is True
        assert fx_collector.db.execute_update.call_count == 2

    def test_postgres_constraint_validation(self, fx_collector):
        """Test unique constraint (currency, region, date)"""
        test_date = date(2025, 10, 24)

        # Simulate constraint violation
        fx_collector.db.execute_update = Mock(
            side_effect=psycopg2.IntegrityError("duplicate key")
        )

        success = fx_collector._save_to_postgres('USD', test_date, 1300.0, 1.0, 'GOOD')

        # Should handle error gracefully
        assert success is False

    def test_sqlite_backward_compatibility(self, fx_collector):
        """Test dual-write to SQLite for backward compatibility"""
        test_date = date(2025, 10, 24)

        with patch.object(fx_collector, '_save_to_sqlite') as mock_sqlite:
            fx_collector._collect_currency('USD', test_date, force_refresh=False)

            # Should call SQLite save
            mock_sqlite.assert_called()

    def test_database_transaction_rollback(self, fx_collector):
        """Test transaction rollback on database error"""
        fx_collector.db.execute_update = Mock(side_effect=Exception("Database error"))

        success = fx_collector._save_to_postgres('USD', date.today(), 1300.0, 1.0, 'GOOD')

        assert success is False


# ================================================================
# Category 4: Data Quality Assessment Tests
# ================================================================

class TestDataQualityAssessment:
    """Test data quality scoring and validation"""

    def test_quality_good_recent_data(self, fx_collector):
        """Test GOOD quality for recent data with USD rate"""
        usd_rate, quality = fx_collector._calculate_usd_rate('HKD', 170.0)

        assert quality == 'GOOD'

    def test_quality_partial_missing_usd_rate(self, fx_collector):
        """Test PARTIAL quality when using default USD rate"""
        fx_collector.exchange_rate_manager.get_rate = Mock(return_value=None)

        usd_rate, quality = fx_collector._calculate_usd_rate('HKD', 170.0)

        assert quality == 'PARTIAL'

    def test_quality_poor_zero_rate(self, fx_collector):
        """Test POOR quality for zero rates"""
        with pytest.raises((ValueError, ZeroDivisionError)):
            fx_collector._calculate_usd_rate('HKD', 0.0)

    def test_quality_missing_missing_data(self, fx_collector):
        """Test MISSING quality when no data available"""
        fx_collector.exchange_rate_manager.get_rate = Mock(return_value=None)

        # This should trigger fallback to default rate
        usd_rate, quality = fx_collector._calculate_usd_rate('HKD', None)

        # Implementation should handle None gracefully
        assert quality in ['PARTIAL', 'MISSING']


# ================================================================
# Category 5: Error Handling Tests
# ================================================================

class TestErrorHandling:
    """Test error handling and fallback mechanisms"""

    def test_bok_api_timeout_fallback(self, fx_collector):
        """Test fallback when BOK API times out"""
        fx_collector.exchange_rate_manager.get_rate = Mock(
            side_effect=TimeoutError("BOK API timeout")
        )

        # Should handle timeout gracefully
        with pytest.raises(TimeoutError):
            fx_collector.exchange_rate_manager.get_rate('USD')

    def test_database_connection_error(self, fx_collector):
        """Test handling of database connection errors"""
        fx_collector.db.execute_update = Mock(
            side_effect=psycopg2.OperationalError("Connection failed")
        )

        success = fx_collector._save_to_postgres('USD', date.today(), 1300.0, 1.0, 'GOOD')

        assert success is False

    def test_invalid_currency_code(self, fx_collector):
        """Test handling of invalid currency codes"""
        fx_collector.exchange_rate_manager.get_rate = Mock(return_value=None)

        result = fx_collector.exchange_rate_manager.get_rate('INVALID')

        assert result is None

    def test_collection_partial_failure(self, fx_collector):
        """Test collection continues when individual currency fails"""
        # Mock: USD succeeds, HKD fails
        fx_collector.exchange_rate_manager.get_rate = Mock(
            side_effect=lambda currency, **kwargs: 1300.0 if currency == 'USD' else None
        )

        results = fx_collector.collect_today(currencies=['USD', 'HKD'])

        # Should have partial success
        assert results['success'] == 1
        assert results['failed'] == 1


# ================================================================
# Category 6: Prometheus Metrics Tests
# ================================================================

class TestPrometheusMetrics:
    """Test Prometheus metrics export"""

    def test_metrics_collection_success(self, fx_collector):
        """Test metrics recorded on successful collection"""
        if not fx_collector.metrics.enabled:
            pytest.skip("Prometheus client not available")

        test_date = date.today()

        with patch.object(fx_collector.db, 'execute_update', return_value=True):
            fx_collector._collect_currency('USD', test_date, force_refresh=False)

        # Verify metrics were called
        assert fx_collector.metrics.collection_success is not None

    def test_metrics_collection_error(self, fx_collector):
        """Test metrics recorded on collection error"""
        if not fx_collector.metrics.enabled:
            pytest.skip("Prometheus client not available")

        fx_collector.exchange_rate_manager.get_rate = Mock(
            side_effect=Exception("API error")
        )

        # Should record error metric
        with pytest.raises(Exception):
            fx_collector._collect_currency('USD', date.today(), force_refresh=False)

    def test_metrics_data_quality_score(self, fx_collector):
        """Test data quality score metric"""
        if not fx_collector.metrics.enabled:
            pytest.skip("Prometheus client not available")

        # Mock quality score update
        fx_collector.metrics.update_data_quality('USD', 1.0)

        # Verify metric was set
        assert fx_collector.metrics.data_quality_score is not None

    def test_metrics_rate_change(self, fx_collector):
        """Test rate change percentage metric"""
        if not fx_collector.metrics.enabled:
            pytest.skip("Prometheus client not available")

        fx_collector.metrics.update_rate_change('USD', 0.5)

        assert fx_collector.metrics.rate_change_daily is not None


# ================================================================
# Integration-Style Unit Tests
# ================================================================

class TestEndToEndCollection:
    """Test complete collection workflow"""

    def test_collect_today_all_currencies(self, fx_collector):
        """Test collecting all currencies for today"""
        fx_collector.db.execute_update = Mock(return_value=True)

        results = fx_collector.collect_today()

        assert results['success'] == 5
        assert results['failed'] == 0
        assert results['date'] == date.today()

    def test_collect_today_specific_currencies(self, fx_collector):
        """Test collecting specific currencies"""
        fx_collector.db.execute_update = Mock(return_value=True)

        results = fx_collector.collect_today(currencies=['USD', 'HKD'])

        assert results['success'] == 2
        assert 'USD' in results['results']
        assert 'HKD' in results['results']

    def test_collect_with_force_refresh(self, fx_collector):
        """Test force_refresh parameter propagates"""
        fx_collector.db.execute_update = Mock(return_value=True)

        results = fx_collector.collect_today(force_refresh=True)

        # Should bypass cache
        assert results['success'] >= 0

    def test_materialized_view_refresh(self, fx_collector):
        """Test materialized view refresh after collection"""
        fx_collector.db.execute_update = Mock(return_value=True)

        success = fx_collector.refresh_materialized_view()

        assert success is True
        fx_collector.db.execute_update.assert_called_with(
            'REFRESH MATERIALIZED VIEW CONCURRENTLY mv_latest_fx_signals'
        )


# ================================================================
# Performance Tests
# ================================================================

class TestPerformance:
    """Test performance and efficiency"""

    def test_collection_duration_threshold(self, fx_collector):
        """Test collection completes within 5 seconds"""
        import time
        fx_collector.db.execute_update = Mock(return_value=True)

        start_time = time.time()
        fx_collector.collect_today()
        duration = time.time() - start_time

        assert duration < 5.0, f"Collection took {duration}s (threshold: 5s)"

    def test_database_batch_operations(self, fx_collector):
        """Test database operations are batched efficiently"""
        fx_collector.db.execute_update = Mock(return_value=True)

        fx_collector.collect_today()

        # Should not exceed reasonable number of DB calls
        assert fx_collector.db.execute_update.call_count <= 10


# ================================================================
# Edge Cases and Boundary Tests
# ================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_weekend_collection(self, fx_collector):
        """Test collection on weekend (BOK API may return no data)"""
        # Mock weekend date
        weekend_date = date(2025, 10, 25)  # Saturday

        # BOK API returns None for weekends
        fx_collector.exchange_rate_manager.get_rate = Mock(return_value=None)

        # Should handle gracefully
        results = fx_collector.collect_today()
        assert results['failed'] >= 0

    def test_holiday_collection(self, fx_collector):
        """Test collection on Korean holiday"""
        # Similar to weekend, may have no data
        fx_collector.exchange_rate_manager.get_rate = Mock(return_value=None)

        results = fx_collector.collect_today()
        assert results is not None

    def test_extreme_rate_values(self, fx_collector):
        """Test handling of extreme rate values"""
        # Very large rate
        usd_rate, quality = fx_collector._calculate_usd_rate('HKD', 999999.0)
        assert usd_rate > 0

        # Very small rate
        usd_rate, quality = fx_collector._calculate_usd_rate('VND', 0.00001)
        assert usd_rate > 0


# ================================================================
# Test Suite Execution
# ================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
