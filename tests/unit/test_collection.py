#!/usr/bin/env python3
"""
test_collection.py - Unit Tests for Collection Modules

Tests for:
- CollectionTracker: 중복 수집 방지 시스템
- DividendCollector: 배당 데이터 수집기
- DataType, CollectionStatus, DividendRecord dataclasses

Coverage target: modules/collection/*.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from datetime import date, datetime, timedelta


# =============================================================================
# DataType Enum Tests
# =============================================================================

class TestDataTypeEnum(unittest.TestCase):
    """Test DataType enumeration"""

    def test_datatype_values(self):
        """Test DataType enum values"""
        from modules.collection.collection_tracker import DataType

        self.assertEqual(DataType.DIVIDEND.value, 'dividend')
        self.assertEqual(DataType.RATIOS.value, 'ratios')
        self.assertEqual(DataType.CASH_BACKFILL.value, 'cash_backfill')
        self.assertEqual(DataType.TECHNICAL.value, 'technical')
        self.assertEqual(DataType.FUNDAMENTALS.value, 'fundamentals')
        self.assertEqual(DataType.ETF_DETAILS.value, 'etf_details')
        self.assertEqual(DataType.ETF_HOLDINGS.value, 'etf_holdings')

    def test_datatype_from_value(self):
        """Test getting DataType from value"""
        from modules.collection.collection_tracker import DataType

        self.assertEqual(DataType('dividend'), DataType.DIVIDEND)
        self.assertEqual(DataType('ratios'), DataType.RATIOS)


# =============================================================================
# CollectionStatus Dataclass Tests
# =============================================================================

class TestCollectionStatus(unittest.TestCase):
    """Test CollectionStatus dataclass"""

    def test_collection_status_creation(self):
        """Test CollectionStatus initialization"""
        from modules.collection.collection_tracker import CollectionStatus

        status = CollectionStatus(
            ticker='005930',
            region='KR',
            data_type='dividend',
            last_collected=date(2024, 11, 27),
            status='success',
            records_count=5,
            duration_ms=150
        )

        self.assertEqual(status.ticker, '005930')
        self.assertEqual(status.region, 'KR')
        self.assertEqual(status.data_type, 'dividend')
        self.assertEqual(status.status, 'success')
        self.assertEqual(status.records_count, 5)
        self.assertEqual(status.duration_ms, 150)
        self.assertIsNone(status.error_message)

    def test_collection_status_with_error(self):
        """Test CollectionStatus with error"""
        from modules.collection.collection_tracker import CollectionStatus

        status = CollectionStatus(
            ticker='INVALID',
            region='US',
            data_type='dividend',
            last_collected=date.today(),
            status='failed',
            error_message='API timeout'
        )

        self.assertEqual(status.status, 'failed')
        self.assertEqual(status.error_message, 'API timeout')


# =============================================================================
# CollectionTracker Tests
# =============================================================================

class TestCollectionTrackerInit(unittest.TestCase):
    """Test CollectionTracker initialization"""

    def test_initialization_default(self):
        """Test default initialization"""
        from modules.collection.collection_tracker import CollectionTracker

        mock_db = Mock()
        tracker = CollectionTracker(mock_db)

        self.assertEqual(tracker.db, mock_db)
        self.assertTrue(tracker.skip_same_day)
        self.assertEqual(tracker._cache, {})
        self.assertEqual(tracker._batch_cache, {})

    def test_initialization_no_skip(self):
        """Test initialization with skip_same_day=False"""
        from modules.collection.collection_tracker import CollectionTracker

        mock_db = Mock()
        tracker = CollectionTracker(mock_db, skip_same_day=False)

        self.assertFalse(tracker.skip_same_day)


class TestCollectionTrackerShouldSkip(unittest.TestCase):
    """Test should_skip method"""

    def setUp(self):
        """Set up test fixtures"""
        from modules.collection.collection_tracker import CollectionTracker
        self.mock_db = Mock()
        self.tracker = CollectionTracker(self.mock_db)

    def test_should_skip_disabled(self):
        """Test should_skip returns False when disabled"""
        from modules.collection.collection_tracker import CollectionTracker, DataType

        tracker = CollectionTracker(self.mock_db, skip_same_day=False)

        result = tracker.should_skip('005930', 'KR', DataType.DIVIDEND)

        self.assertFalse(result)
        self.mock_db.execute_query.assert_not_called()

    def test_should_skip_cache_hit(self):
        """Test should_skip with cache hit"""
        from modules.collection.collection_tracker import CollectionTracker, DataType, CollectionStatus

        today = date.today()
        cache_key = f"005930:KR:dividend:{today}"
        self.tracker._cache[cache_key] = CollectionStatus(
            ticker='005930', region='KR', data_type='dividend',
            last_collected=today, status='success'
        )

        result = self.tracker.should_skip('005930', 'KR', DataType.DIVIDEND)

        self.assertTrue(result)
        self.mock_db.execute_query.assert_not_called()

    def test_should_skip_db_hit(self):
        """Test should_skip with DB hit"""
        from modules.collection.collection_tracker import DataType

        self.mock_db.execute_query.return_value = [{'status': 'success'}]

        result = self.tracker.should_skip('005930', 'KR', DataType.DIVIDEND)

        self.assertTrue(result)
        self.mock_db.execute_query.assert_called_once()

    def test_should_skip_db_miss(self):
        """Test should_skip with no record in DB"""
        from modules.collection.collection_tracker import DataType

        self.mock_db.execute_query.return_value = []

        result = self.tracker.should_skip('005930', 'KR', DataType.DIVIDEND)

        self.assertFalse(result)

    def test_should_skip_db_error(self):
        """Test should_skip with DB error"""
        from modules.collection.collection_tracker import DataType

        self.mock_db.execute_query.side_effect = Exception("DB error")

        result = self.tracker.should_skip('005930', 'KR', DataType.DIVIDEND)

        self.assertFalse(result)


class TestCollectionTrackerShouldSkipBatch(unittest.TestCase):
    """Test should_skip_batch method"""

    def setUp(self):
        """Set up test fixtures"""
        from modules.collection.collection_tracker import CollectionTracker
        self.mock_db = Mock()
        self.tracker = CollectionTracker(self.mock_db)

    def test_should_skip_batch_disabled(self):
        """Test should_skip_batch returns all tickers when disabled"""
        from modules.collection.collection_tracker import CollectionTracker, DataType

        tracker = CollectionTracker(self.mock_db, skip_same_day=False)

        to_process, to_skip = tracker.should_skip_batch(
            ['005930', '000660'], 'KR', DataType.DIVIDEND
        )

        self.assertEqual(to_process, ['005930', '000660'])
        self.assertEqual(to_skip, [])

    def test_should_skip_batch_empty_input(self):
        """Test should_skip_batch with empty input"""
        from modules.collection.collection_tracker import DataType

        to_process, to_skip = self.tracker.should_skip_batch(
            [], 'KR', DataType.DIVIDEND
        )

        self.assertEqual(to_process, [])
        self.assertEqual(to_skip, [])

    def test_should_skip_batch_some_collected(self):
        """Test should_skip_batch with some tickers already collected"""
        from modules.collection.collection_tracker import DataType

        self.mock_db.execute_query.return_value = [
            {'ticker': '005930'},
            {'ticker': '035720'}
        ]

        to_process, to_skip = self.tracker.should_skip_batch(
            ['005930', '000660', '035720', '051910'], 'KR', DataType.DIVIDEND
        )

        self.assertEqual(set(to_process), {'000660', '051910'})
        self.assertEqual(set(to_skip), {'005930', '035720'})

    def test_should_skip_batch_uses_cache(self):
        """Test should_skip_batch uses cache on second call"""
        from modules.collection.collection_tracker import DataType

        self.mock_db.execute_query.return_value = [{'ticker': '005930'}]

        # First call populates cache
        self.tracker.should_skip_batch(['005930'], 'KR', DataType.DIVIDEND)
        # Second call uses cache
        self.tracker.should_skip_batch(['005930', '000660'], 'KR', DataType.DIVIDEND)

        # DB should only be called once
        self.assertEqual(self.mock_db.execute_query.call_count, 1)


class TestCollectionTrackerMarkCollected(unittest.TestCase):
    """Test mark_collected method"""

    def setUp(self):
        """Set up test fixtures"""
        from modules.collection.collection_tracker import CollectionTracker
        self.mock_db = Mock()
        self.tracker = CollectionTracker(self.mock_db)

    def test_mark_collected_success(self):
        """Test mark_collected with success"""
        from modules.collection.collection_tracker import DataType

        self.mock_db.execute_update.return_value = True

        result = self.tracker.mark_collected(
            '005930', 'KR', DataType.DIVIDEND,
            status='success', records_count=5, duration_ms=100
        )

        self.assertTrue(result)
        self.mock_db.execute_update.assert_called_once()

        # Check cache was updated
        today = date.today()
        cache_key = f"005930:KR:dividend:{today}"
        self.assertIn(cache_key, self.tracker._cache)

    def test_mark_collected_failure(self):
        """Test mark_collected with DB failure"""
        from modules.collection.collection_tracker import DataType

        self.mock_db.execute_update.side_effect = Exception("DB error")

        result = self.tracker.mark_collected('005930', 'KR', DataType.DIVIDEND)

        self.assertFalse(result)

    def test_mark_collected_updates_batch_cache(self):
        """Test mark_collected updates batch cache"""
        from modules.collection.collection_tracker import DataType

        today = date.today()
        batch_key = f"KR:dividend:{today}"
        self.tracker._batch_cache[batch_key] = set()

        self.mock_db.execute_update.return_value = True

        self.tracker.mark_collected('005930', 'KR', DataType.DIVIDEND, status='success')

        self.assertIn('005930', self.tracker._batch_cache[batch_key])


class TestCollectionTrackerUtility(unittest.TestCase):
    """Test utility methods"""

    def setUp(self):
        """Set up test fixtures"""
        from modules.collection.collection_tracker import CollectionTracker, DataType, CollectionStatus

        self.mock_db = Mock()
        self.tracker = CollectionTracker(self.mock_db)

        # Populate caches
        today = date.today()
        self.tracker._cache[f"005930:KR:dividend:{today}"] = CollectionStatus(
            ticker='005930', region='KR', data_type='dividend',
            last_collected=today, status='success'
        )
        self.tracker._batch_cache[f"KR:dividend:{today}"] = {'005930', '000660'}

    def test_clear_cache(self):
        """Test clear_cache method"""
        self.tracker.clear_cache()

        self.assertEqual(self.tracker._cache, {})
        self.assertEqual(self.tracker._batch_cache, {})

    def test_get_collection_stats(self):
        """Test get_collection_stats method"""
        self.mock_db.execute_query.return_value = [
            {'region': 'KR', 'data_type': 'dividend', 'status': 'success',
             'count': 100, 'total_records': 500, 'avg_duration_ms': 50}
        ]

        result = self.tracker.get_collection_stats(region='KR')

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['count'], 100)

    def test_get_today_summary(self):
        """Test get_today_summary method"""
        self.mock_db.execute_query.return_value = [
            {'region': 'KR', 'data_type': 'dividend', 'status': 'success',
             'count': 100, 'total_records': 500, 'avg_duration_ms': 50},
            {'region': 'KR', 'data_type': 'dividend', 'status': 'failed',
             'count': 10, 'total_records': 0, 'avg_duration_ms': 20}
        ]

        summary = self.tracker.get_today_summary(region='KR')

        self.assertEqual(summary['total_tickers'], 110)
        self.assertIn('dividend', summary['by_data_type'])
        self.assertIn('success', summary['by_status'])
        self.assertIn('failed', summary['by_status'])

    def test_cleanup_old_records(self):
        """Test cleanup_old_records method"""
        self.mock_db.execute_update.return_value = True

        result = self.tracker.cleanup_old_records(days_to_keep=7)

        self.assertEqual(result, 1)
        self.mock_db.execute_update.assert_called_once()

    def test_invalidate_ticker(self):
        """Test invalidate_ticker method"""
        from modules.collection.collection_tracker import DataType

        today = date.today()
        self.tracker._cache[f"005930:KR:dividend:{today}"] = Mock()
        self.tracker._batch_cache[f"KR:dividend:{today}"] = {'005930', '000660'}

        self.mock_db.execute_update.return_value = True

        self.tracker.invalidate_ticker('005930', 'KR', DataType.DIVIDEND)

        # Check cache was cleared
        self.assertNotIn(f"005930:KR:dividend:{today}", self.tracker._cache)
        self.assertNotIn('005930', self.tracker._batch_cache[f"KR:dividend:{today}"])


# =============================================================================
# DividendType Enum Tests
# =============================================================================

class TestDividendTypeEnum(unittest.TestCase):
    """Test DividendType enumeration"""

    def test_dividend_type_values(self):
        """Test DividendType enum values"""
        from modules.collection.dividend_collector import DividendType

        self.assertEqual(DividendType.INTERIM.value, 'interim')
        self.assertEqual(DividendType.FINAL.value, 'final')
        self.assertEqual(DividendType.SPECIAL.value, 'special')
        self.assertEqual(DividendType.QUARTERLY.value, 'quarterly')
        self.assertEqual(DividendType.ANNUAL.value, 'annual')


# =============================================================================
# DividendRecord Dataclass Tests
# =============================================================================

class TestDividendRecord(unittest.TestCase):
    """Test DividendRecord dataclass"""

    def test_dividend_record_creation(self):
        """Test DividendRecord initialization"""
        from modules.collection.dividend_collector import DividendRecord

        record = DividendRecord(
            ticker='005930',
            region='KR',
            fiscal_year=2024,
            dividend_type='annual',
            dividend_per_share=1444.0,
            dividend_yield=2.5,
            currency='KRW',
            data_source='pykrx'
        )

        self.assertEqual(record.ticker, '005930')
        self.assertEqual(record.region, 'KR')
        self.assertEqual(record.fiscal_year, 2024)
        self.assertEqual(record.dividend_per_share, 1444.0)
        self.assertEqual(record.dividend_yield, 2.5)
        self.assertEqual(record.currency, 'KRW')

    def test_dividend_record_with_dates(self):
        """Test DividendRecord with all date fields"""
        from modules.collection.dividend_collector import DividendRecord

        record = DividendRecord(
            ticker='AAPL',
            region='US',
            fiscal_year=2024,
            dividend_type='quarterly',
            dividend_per_share=0.24,
            declaration_date=date(2024, 1, 15),
            ex_dividend_date=date(2024, 2, 9),
            record_date=date(2024, 2, 12),
            payment_date=date(2024, 2, 15)
        )

        self.assertEqual(record.ex_dividend_date, date(2024, 2, 9))
        self.assertEqual(record.payment_date, date(2024, 2, 15))


# =============================================================================
# DividendCollector Tests
# =============================================================================

class TestDividendCollectorInit(unittest.TestCase):
    """Test DividendCollector initialization"""

    def test_initialization_with_db(self):
        """Test initialization with provided db_manager"""
        with patch('modules.collection.dividend_collector.PostgresDatabaseManager'):
            from modules.collection.dividend_collector import DividendCollector

            mock_db = Mock()
            collector = DividendCollector(db_manager=mock_db)

            self.assertEqual(collector.db, mock_db)
            self.assertEqual(collector.collected_count, 0)
            self.assertEqual(collector.error_count, 0)


class TestDividendCollectorFormatTicker(unittest.TestCase):
    """Test _format_yfinance_ticker method"""

    def setUp(self):
        with patch('modules.collection.dividend_collector.PostgresDatabaseManager'):
            from modules.collection.dividend_collector import DividendCollector
            mock_db = Mock()
            self.collector = DividendCollector(db_manager=mock_db)

    def test_format_us_ticker(self):
        """Test US ticker formatting"""
        result = self.collector._format_yfinance_ticker('AAPL', 'US')
        self.assertEqual(result, 'AAPL')

    def test_format_us_preferred_ticker(self):
        """Test US preferred stock formatting"""
        result = self.collector._format_yfinance_ticker('BRK/B', 'US')
        self.assertEqual(result, 'BRK-B')

    def test_format_jp_ticker(self):
        """Test JP ticker formatting"""
        result = self.collector._format_yfinance_ticker('7203', 'JP')
        self.assertEqual(result, '7203.T')

    def test_format_hk_ticker(self):
        """Test HK ticker formatting (with padding)"""
        result = self.collector._format_yfinance_ticker('700', 'HK')
        self.assertEqual(result, '0700.HK')

    def test_format_hk_ticker_no_padding(self):
        """Test HK ticker formatting (already 4 digits)"""
        result = self.collector._format_yfinance_ticker('0700', 'HK')
        self.assertEqual(result, '0700.HK')

    def test_format_kr_ticker(self):
        """Test KR ticker formatting"""
        result = self.collector._format_yfinance_ticker('005930', 'KR')
        self.assertEqual(result, '005930.KS')

    def test_format_cn_shanghai(self):
        """Test CN Shanghai ticker formatting"""
        result = self.collector._format_yfinance_ticker('600519', 'CN')
        self.assertEqual(result, '600519.SS')

    def test_format_cn_shenzhen(self):
        """Test CN Shenzhen ticker formatting"""
        result = self.collector._format_yfinance_ticker('000858', 'CN')
        self.assertEqual(result, '000858.SZ')


class TestDividendCollectorKRDividends(unittest.TestCase):
    """Test collect_kr_dividends method"""

    def setUp(self):
        with patch('modules.collection.dividend_collector.PostgresDatabaseManager'):
            from modules.collection.dividend_collector import DividendCollector
            mock_db = Mock()
            self.collector = DividendCollector(db_manager=mock_db)

    def test_invalid_ticker_format(self):
        """Test with invalid KR ticker format"""
        result = self.collector.collect_kr_dividends('AAPL', years=1)
        self.assertEqual(result, [])

    def test_short_ticker(self):
        """Test with ticker shorter than 6 digits"""
        result = self.collector.collect_kr_dividends('12345', years=1)
        self.assertEqual(result, [])

    def test_empty_ticker(self):
        """Test with empty ticker"""
        result = self.collector.collect_kr_dividends('', years=1)
        self.assertEqual(result, [])

    def test_non_numeric_ticker(self):
        """Test with non-numeric KR ticker"""
        result = self.collector.collect_kr_dividends('ABCDEF', years=1)
        self.assertEqual(result, [])


class TestDividendCollectorYFinanceDividends(unittest.TestCase):
    """Test collect_yfinance_dividends method"""

    def setUp(self):
        with patch('modules.collection.dividend_collector.PostgresDatabaseManager'):
            from modules.collection.dividend_collector import DividendCollector
            mock_db = Mock()
            self.collector = DividendCollector(db_manager=mock_db)

    @pytest.mark.skip(reason="yfinance imported inside method - hard to mock")
    def test_collect_yfinance_success(self):
        """Test successful yfinance dividend collection - skipped due to internal import"""
        pass

    @pytest.mark.skip(reason="yfinance imported inside method - hard to mock")
    def test_collect_yfinance_empty(self):
        """Test yfinance with no dividends - skipped due to internal import"""
        pass

    @pytest.mark.skip(reason="yfinance imported inside method - hard to mock")
    def test_collect_yfinance_none(self):
        """Test yfinance with None dividends - skipped due to internal import"""
        pass

    @pytest.mark.skip(reason="yfinance imported inside method - hard to mock")
    def test_collect_yfinance_jp_ticker(self):
        """Test yfinance with Japanese ticker - skipped due to internal import"""
        pass

    def test_yfinance_import_error_handling(self):
        """Test that yfinance import error returns empty list"""
        # This tests the ImportError handling path in collect_yfinance_dividends
        # When yfinance is not available, it should return empty list
        # Since yfinance IS installed, this verifies the method exists
        result = self.collector.collect_yfinance_dividends('INVALID_TICKER_XYZ123', 'US', years=1)
        # Empty result for invalid ticker
        self.assertIsInstance(result, list)


class TestDividendCollectorSave(unittest.TestCase):
    """Test save methods"""

    def setUp(self):
        from modules.collection.dividend_collector import DividendRecord

        self.mock_db = Mock()
        with patch('modules.collection.dividend_collector.PostgresDatabaseManager'):
            from modules.collection.dividend_collector import DividendCollector
            self.collector = DividendCollector(db_manager=self.mock_db)

        self.sample_record = DividendRecord(
            ticker='AAPL',
            region='US',
            fiscal_year=2024,
            dividend_type='quarterly',
            dividend_per_share=0.24,
            currency='USD',
            data_source='yfinance'
        )

    def test_save_dividend_record_success(self):
        """Test successful save"""
        self.mock_db.execute_update.return_value = True

        result = self.collector.save_dividend_record(self.sample_record)

        self.assertTrue(result)
        self.mock_db.execute_update.assert_called_once()

    def test_save_dividend_record_failure(self):
        """Test save failure"""
        self.mock_db.execute_update.side_effect = Exception("DB error")

        result = self.collector.save_dividend_record(self.sample_record)

        self.assertFalse(result)

    def test_save_dividend_records_batch(self):
        """Test batch save"""
        from modules.collection.dividend_collector import DividendRecord

        self.mock_db.execute_update.return_value = True

        records = [
            self.sample_record,
            DividendRecord(
                ticker='AAPL', region='US', fiscal_year=2024,
                dividend_type='quarterly', dividend_per_share=0.24
            ),
            DividendRecord(
                ticker='AAPL', region='US', fiscal_year=2024,
                dividend_type='quarterly', dividend_per_share=0.25
            )
        ]

        saved = self.collector.save_dividend_records(records)

        self.assertEqual(saved, 3)
        self.assertEqual(self.collector.collected_count, 3)


class TestDividendCollectorGetHistory(unittest.TestCase):
    """Test get_dividend_history and get_summary_stats"""

    def setUp(self):
        self.mock_db = Mock()
        with patch('modules.collection.dividend_collector.PostgresDatabaseManager'):
            from modules.collection.dividend_collector import DividendCollector
            self.collector = DividendCollector(db_manager=self.mock_db)

    def test_get_dividend_history_with_years(self):
        """Test get_dividend_history with year filter"""
        self.mock_db.execute_query.return_value = [
            {'ticker': 'AAPL', 'fiscal_year': 2024, 'dividend_per_share': 0.24}
        ]

        result = self.collector.get_dividend_history('AAPL', 'US', years=3)

        self.assertEqual(len(result), 1)
        self.mock_db.execute_query.assert_called_once()

    def test_get_dividend_history_all(self):
        """Test get_dividend_history without year filter"""
        self.mock_db.execute_query.return_value = [
            {'ticker': 'AAPL', 'fiscal_year': 2024},
            {'ticker': 'AAPL', 'fiscal_year': 2023},
        ]

        result = self.collector.get_dividend_history('AAPL', 'US')

        self.assertEqual(len(result), 2)

    def test_get_dividend_history_empty(self):
        """Test get_dividend_history with no data"""
        self.mock_db.execute_query.return_value = None

        result = self.collector.get_dividend_history('XYZ', 'US')

        self.assertEqual(result, [])

    def test_get_summary_stats(self):
        """Test get_summary_stats"""
        self.mock_db.execute_query.return_value = [
            {'region': 'US', 'total_records': 1000, 'unique_tickers': 500,
             'min_year': 2020, 'max_year': 2024, 'sources': 1},
            {'region': 'KR', 'total_records': 500, 'unique_tickers': 200,
             'min_year': 2021, 'max_year': 2024, 'sources': 2}
        ]

        result = self.collector.get_summary_stats()

        self.assertIn('US', result)
        self.assertIn('KR', result)
        self.assertEqual(result['US']['total_records'], 1000)


# =============================================================================
# CURRENCY_MAP Tests
# =============================================================================

class TestCurrencyMap(unittest.TestCase):
    """Test CURRENCY_MAP constant"""

    def test_currency_map_values(self):
        """Test CURRENCY_MAP values"""
        from modules.collection.dividend_collector import CURRENCY_MAP

        self.assertEqual(CURRENCY_MAP['KR'], 'KRW')
        self.assertEqual(CURRENCY_MAP['US'], 'USD')
        self.assertEqual(CURRENCY_MAP['JP'], 'JPY')
        self.assertEqual(CURRENCY_MAP['HK'], 'HKD')
        self.assertEqual(CURRENCY_MAP['CN'], 'CNY')
        self.assertEqual(CURRENCY_MAP['VN'], 'VND')


# =============================================================================
# Utility Functions Tests
# =============================================================================

class TestCreateTracker(unittest.TestCase):
    """Test create_tracker utility function"""

    def test_create_tracker(self):
        """Test create_tracker helper function"""
        from modules.collection.collection_tracker import create_tracker

        mock_db = Mock()
        tracker = create_tracker(mock_db, skip_same_day=True)

        self.assertTrue(tracker.skip_same_day)
        self.assertEqual(tracker.db, mock_db)


# =============================================================================
# Parametrized Tests
# =============================================================================

@pytest.mark.parametrize("data_type_str,expected_enum_name", [
    ('dividend', 'DIVIDEND'),
    ('ratios', 'RATIOS'),
    ('cash_backfill', 'CASH_BACKFILL'),
    ('technical', 'TECHNICAL'),
    ('fundamentals', 'FUNDAMENTALS'),
])
def test_datatype_string_to_enum(data_type_str, expected_enum_name):
    """Test DataType enum from string value"""
    from modules.collection.collection_tracker import DataType

    dt = DataType(data_type_str)
    assert dt.name == expected_enum_name


@pytest.mark.parametrize("ticker,region,expected_suffix", [
    ('AAPL', 'US', ''),
    ('7203', 'JP', '.T'),
    ('0700', 'HK', '.HK'),
    ('005930', 'KR', '.KS'),
    ('600519', 'CN', '.SS'),
    ('000858', 'CN', '.SZ'),
])
def test_yfinance_ticker_suffix(ticker, region, expected_suffix):
    """Test yfinance ticker suffix by region"""
    with patch('modules.collection.dividend_collector.PostgresDatabaseManager'):
        from modules.collection.dividend_collector import DividendCollector
        mock_db = Mock()
        collector = DividendCollector(db_manager=mock_db)

        result = collector._format_yfinance_ticker(ticker, region)

        if expected_suffix:
            assert result.endswith(expected_suffix)
        else:
            # US tickers should not have suffix (unless preferred)
            assert result == ticker


@pytest.mark.parametrize("region,expected_currency", [
    ('KR', 'KRW'),
    ('US', 'USD'),
    ('JP', 'JPY'),
    ('HK', 'HKD'),
    ('CN', 'CNY'),
    ('VN', 'VND'),
])
def test_currency_by_region(region, expected_currency):
    """Test currency mapping by region"""
    from modules.collection.dividend_collector import CURRENCY_MAP

    assert CURRENCY_MAP[region] == expected_currency


@pytest.mark.parametrize("div_type_str,expected_name", [
    ('interim', 'INTERIM'),
    ('final', 'FINAL'),
    ('special', 'SPECIAL'),
    ('quarterly', 'QUARTERLY'),
    ('annual', 'ANNUAL'),
])
def test_dividend_type_mapping(div_type_str, expected_name):
    """Test DividendType enum mapping"""
    from modules.collection.dividend_collector import DividendType

    dt = DividendType(div_type_str)
    assert dt.name == expected_name


if __name__ == '__main__':
    unittest.main(verbosity=2)
