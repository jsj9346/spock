#!/usr/bin/env python3
"""
Unit Tests for BlacklistManager

Tests for dual-system blacklist (DB-based + file-based) across all markets.

Run:
    pytest tests/test_blacklist_manager.py -v
    python3 tests/test_blacklist_manager.py

Author: Spock Trading System
Created: 2025-10-17
"""

import unittest
import sys
import os
import json
import tempfile
from datetime import datetime, date, timedelta

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.blacklist_manager import BlacklistManager
from modules.db_manager_sqlite import SQLiteDatabaseManager
from init_db import DatabaseInitializer


class TestBlacklistManager(unittest.TestCase):
    """Test cases for BlacklistManager"""

    @classmethod
    def setUpClass(cls):
        """Setup test environment once"""
        # Use test database
        cls.test_db_path = "data/test_spock_blacklist.db"

        # Remove test DB if exists
        if os.path.exists(cls.test_db_path):
            os.remove(cls.test_db_path)

        # Create fresh test database using DatabaseInitializer
        print(f"\n📊 Initializing test database: {cls.test_db_path}")
        initializer = DatabaseInitializer(db_path=cls.test_db_path)
        initializer.initialize(reset=False, include_phase2=False)
        print(f"✅ Test database created: {cls.test_db_path}")

    def setUp(self):
        """Setup before each test"""
        # Create database manager instance (DB now exists)
        self.db = SQLiteDatabaseManager(db_path=self.test_db_path)

        # Create temporary blacklist file
        self.temp_blacklist_file = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False
        )
        self.temp_blacklist_path = self.temp_blacklist_file.name
        self.temp_blacklist_file.close()

        # Initialize blacklist manager
        self.blacklist = BlacklistManager(
            db_manager=self.db,
            config_path=self.temp_blacklist_path
        )

        # Insert test tickers
        self._insert_test_tickers()

    def tearDown(self):
        """Cleanup after each test"""
        # Remove temporary blacklist file
        if os.path.exists(self.temp_blacklist_path):
            os.remove(self.temp_blacklist_path)

    @classmethod
    def tearDownClass(cls):
        """Cleanup test environment"""
        # Remove test database
        if os.path.exists(cls.test_db_path):
            os.remove(cls.test_db_path)

    def _insert_test_tickers(self):
        """Insert test tickers into database"""
        test_tickers = [
            # Korea
            {'ticker': '005930', 'name': '삼성전자', 'region': 'KR', 'exchange': 'KOSPI', 'currency': 'KRW'},
            {'ticker': '000660', 'name': 'SK하이닉스', 'region': 'KR', 'exchange': 'KOSPI', 'currency': 'KRW'},
            # US
            {'ticker': 'AAPL', 'name': 'Apple Inc', 'region': 'US', 'exchange': 'NASDAQ', 'currency': 'USD'},
            {'ticker': 'TSLA', 'name': 'Tesla Inc', 'region': 'US', 'exchange': 'NASDAQ', 'currency': 'USD'},
            # China
            {'ticker': '600519.SS', 'name': 'Kweichow Moutai', 'region': 'CN', 'exchange': 'SSE', 'currency': 'CNY'},
            # Hong Kong
            {'ticker': '0700.HK', 'name': 'Tencent', 'region': 'HK', 'exchange': 'HKEX', 'currency': 'HKD'},
            # Japan
            {'ticker': '7203', 'name': 'Toyota', 'region': 'JP', 'exchange': 'TSE', 'currency': 'JPY'},
            # Vietnam
            {'ticker': 'VCB', 'name': 'Vietcombank', 'region': 'VN', 'exchange': 'HOSE', 'currency': 'VND'},
        ]

        for ticker_data in test_tickers:
            self.db.insert_ticker({
                'ticker': ticker_data['ticker'],
                'name': ticker_data['name'],
                'name_eng': ticker_data.get('name'),
                'exchange': ticker_data['exchange'],
                'region': ticker_data['region'],
                'currency': ticker_data['currency'],
                'asset_type': 'STOCK',
                'is_active': True,
                'created_at': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'data_source': 'test'
            })

    # ========================================
    # DB-BASED BLACKLIST TESTS
    # ========================================

    def test_01_deactivate_ticker_db(self):
        """Test DB-based ticker deactivation"""
        # Deactivate ticker
        result = self.blacklist.deactivate_ticker_db(
            ticker='005930',
            region='KR',
            reason='Test deactivation'
        )

        self.assertTrue(result)

        # Verify is_active=0
        db_blacklist = self.blacklist.get_db_blacklist(region='KR')
        self.assertIn('005930', db_blacklist['KR'])

    def test_02_reactivate_ticker_db(self):
        """Test DB-based ticker reactivation"""
        # Deactivate first
        self.blacklist.deactivate_ticker_db('005930', 'KR')

        # Reactivate
        result = self.blacklist.reactivate_ticker_db('005930', 'KR')

        self.assertTrue(result)

        # Verify is_active=1
        db_blacklist = self.blacklist.get_db_blacklist(region='KR')
        self.assertNotIn('005930', db_blacklist['KR'])

    def test_03_get_db_blacklist_single_region(self):
        """Test getting DB blacklist for single region"""
        # Deactivate multiple tickers
        self.blacklist.deactivate_ticker_db('005930', 'KR')
        self.blacklist.deactivate_ticker_db('000660', 'KR')

        # Get blacklist
        db_blacklist = self.blacklist.get_db_blacklist(region='KR')

        self.assertEqual(len(db_blacklist['KR']), 2)
        self.assertIn('005930', db_blacklist['KR'])
        self.assertIn('000660', db_blacklist['KR'])

    def test_04_get_db_blacklist_all_regions(self):
        """Test getting DB blacklist for all regions"""
        # Deactivate tickers in different regions
        self.blacklist.deactivate_ticker_db('005930', 'KR')
        self.blacklist.deactivate_ticker_db('AAPL', 'US')

        # Get blacklist
        db_blacklist = self.blacklist.get_db_blacklist()

        self.assertIn('005930', db_blacklist['KR'])
        self.assertIn('AAPL', db_blacklist['US'])

    # ========================================
    # FILE-BASED BLACKLIST TESTS
    # ========================================

    def test_05_add_to_file_blacklist(self):
        """Test adding ticker to file blacklist"""
        result = self.blacklist.add_to_file_blacklist(
            ticker='TSLA',
            region='US',
            reason='High volatility',
            added_by='user'
        )

        self.assertTrue(result)

        # Verify in file blacklist
        file_blacklist = self.blacklist.get_file_blacklist(region='US')
        self.assertIn('TSLA', file_blacklist['US'])

    def test_06_add_to_file_blacklist_with_expiry(self):
        """Test adding ticker with expiry date"""
        expire_date = (date.today() + timedelta(days=30)).strftime('%Y-%m-%d')

        result = self.blacklist.add_to_file_blacklist(
            ticker='TSLA',
            region='US',
            reason='Temporary exclusion',
            expire_date=expire_date
        )

        self.assertTrue(result)

        # Verify expiry date stored
        self.assertIn('TSLA', self.blacklist._file_blacklist['US'])
        self.assertEqual(
            self.blacklist._file_blacklist['US']['TSLA']['expire_date'],
            expire_date
        )

    def test_07_remove_from_file_blacklist(self):
        """Test removing ticker from file blacklist"""
        # Add first
        self.blacklist.add_to_file_blacklist(
            ticker='TSLA',
            region='US',
            reason='Test'
        )

        # Remove
        result = self.blacklist.remove_from_file_blacklist('TSLA', 'US')

        self.assertTrue(result)

        # Verify removed
        file_blacklist = self.blacklist.get_file_blacklist(region='US')
        self.assertNotIn('TSLA', file_blacklist['US'])

    def test_08_expired_entry_exclusion(self):
        """Test expired entries are excluded"""
        # Add entry with past expiry date
        expired_date = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')

        self.blacklist._file_blacklist['US']['TSLA'] = {
            'name': 'Tesla',
            'reason': 'Test',
            'added_date': '2025-01-01',
            'added_by': 'test',
            'expire_date': expired_date,
            'notes': None
        }

        # Get file blacklist (should exclude expired)
        file_blacklist = self.blacklist.get_file_blacklist(region='US', include_expired=False)

        self.assertNotIn('TSLA', file_blacklist['US'])

        # Get with expired included
        file_blacklist_all = self.blacklist.get_file_blacklist(region='US', include_expired=True)

        self.assertIn('TSLA', file_blacklist_all['US'])

    def test_09_cleanup_expired_entries(self):
        """Test automatic cleanup of expired entries"""
        # Add expired entry
        expired_date = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')

        self.blacklist._file_blacklist['US']['TSLA'] = {
            'name': 'Tesla',
            'reason': 'Test',
            'added_date': '2025-01-01',
            'added_by': 'test',
            'expire_date': expired_date,
            'notes': None
        }

        # Cleanup
        removed_count = self.blacklist.cleanup_expired_entries()

        self.assertEqual(removed_count, 1)
        self.assertNotIn('TSLA', self.blacklist._file_blacklist['US'])

    # ========================================
    # UNIFIED FILTERING TESTS
    # ========================================

    def test_10_is_blacklisted_db_only(self):
        """Test is_blacklisted() for DB blacklist"""
        # Deactivate in DB
        self.blacklist.deactivate_ticker_db('005930', 'KR')

        # Check blacklist status
        is_blacklisted = self.blacklist.is_blacklisted('005930', 'KR')

        self.assertTrue(is_blacklisted)

    def test_11_is_blacklisted_file_only(self):
        """Test is_blacklisted() for file blacklist"""
        # Add to file blacklist
        self.blacklist.add_to_file_blacklist(
            ticker='TSLA',
            region='US',
            reason='Test'
        )

        # Check blacklist status
        is_blacklisted = self.blacklist.is_blacklisted('TSLA', 'US')

        self.assertTrue(is_blacklisted)

    def test_12_is_blacklisted_both_systems(self):
        """Test is_blacklisted() when in both systems"""
        # Deactivate in DB
        self.blacklist.deactivate_ticker_db('005930', 'KR')

        # Add to file blacklist
        self.blacklist.add_to_file_blacklist(
            ticker='005930',
            region='KR',
            reason='Test'
        )

        # Check blacklist status
        is_blacklisted = self.blacklist.is_blacklisted('005930', 'KR')

        self.assertTrue(is_blacklisted)

    def test_13_is_blacklisted_not_blacklisted(self):
        """Test is_blacklisted() for non-blacklisted ticker"""
        is_blacklisted = self.blacklist.is_blacklisted('AAPL', 'US')

        self.assertFalse(is_blacklisted)

    def test_14_filter_blacklisted_tickers(self):
        """Test filtering blacklisted tickers from list"""
        # Setup: Blacklist some tickers
        self.blacklist.deactivate_ticker_db('005930', 'KR')  # DB
        self.blacklist.add_to_file_blacklist('000660', 'KR', 'Test')  # File

        # Test filtering
        tickers = ['005930', '000660', '035420']  # Only 035420 should pass
        filtered = self.blacklist.filter_blacklisted_tickers(tickers, 'KR')

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0], '035420')

    def test_15_get_combined_blacklist(self):
        """Test getting combined blacklist (DB + file)"""
        # Deactivate in DB
        self.blacklist.deactivate_ticker_db('005930', 'KR')

        # Add to file blacklist
        self.blacklist.add_to_file_blacklist('000660', 'KR', 'Test')

        # Get combined blacklist
        combined = self.blacklist.get_combined_blacklist(region='KR')

        self.assertEqual(len(combined['KR']), 2)
        self.assertIn('005930', combined['KR'])
        self.assertIn('000660', combined['KR'])

    # ========================================
    # TICKER FORMAT VALIDATION TESTS
    # ========================================

    def test_16_validate_ticker_format_kr(self):
        """Test KR ticker format validation"""
        # Valid
        self.assertTrue(self.blacklist._validate_ticker_format('005930', 'KR'))

        # Invalid
        self.assertFalse(self.blacklist._validate_ticker_format('AAPL', 'KR'))
        self.assertFalse(self.blacklist._validate_ticker_format('05930', 'KR'))  # 5 digits

    def test_17_validate_ticker_format_us(self):
        """Test US ticker format validation"""
        # Valid
        self.assertTrue(self.blacklist._validate_ticker_format('AAPL', 'US'))
        self.assertTrue(self.blacklist._validate_ticker_format('BRK.B', 'US'))

        # Invalid
        self.assertFalse(self.blacklist._validate_ticker_format('005930', 'US'))
        self.assertFalse(self.blacklist._validate_ticker_format('TOOLONG', 'US'))  # > 5 chars

    def test_18_validate_ticker_format_cn(self):
        """Test CN ticker format validation"""
        # Valid
        self.assertTrue(self.blacklist._validate_ticker_format('600519.SS', 'CN'))
        self.assertTrue(self.blacklist._validate_ticker_format('000001.SZ', 'CN'))

        # Invalid
        self.assertFalse(self.blacklist._validate_ticker_format('600519', 'CN'))  # Missing suffix
        self.assertFalse(self.blacklist._validate_ticker_format('600519.HK', 'CN'))  # Wrong suffix

    def test_19_validate_ticker_format_hk(self):
        """Test HK ticker format validation"""
        # Valid
        self.assertTrue(self.blacklist._validate_ticker_format('0700', 'HK'))
        self.assertTrue(self.blacklist._validate_ticker_format('0700.HK', 'HK'))
        self.assertTrue(self.blacklist._validate_ticker_format('09988', 'HK'))

        # Invalid
        self.assertFalse(self.blacklist._validate_ticker_format('AAPL', 'HK'))

    def test_20_validate_ticker_format_jp(self):
        """Test JP ticker format validation"""
        # Valid
        self.assertTrue(self.blacklist._validate_ticker_format('7203', 'JP'))

        # Invalid
        self.assertFalse(self.blacklist._validate_ticker_format('AAPL', 'JP'))
        self.assertFalse(self.blacklist._validate_ticker_format('720', 'JP'))  # 3 digits

    def test_21_validate_ticker_format_vn(self):
        """Test VN ticker format validation"""
        # Valid
        self.assertTrue(self.blacklist._validate_ticker_format('VCB', 'VN'))

        # Invalid
        self.assertFalse(self.blacklist._validate_ticker_format('AAPL', 'VN'))  # 4 chars
        self.assertFalse(self.blacklist._validate_ticker_format('VC', 'VN'))  # 2 chars

    # ========================================
    # SUMMARY & MAINTENANCE TESTS
    # ========================================

    def test_22_get_blacklist_summary(self):
        """Test getting blacklist summary"""
        # Setup blacklist data
        self.blacklist.deactivate_ticker_db('005930', 'KR')
        self.blacklist.add_to_file_blacklist('TSLA', 'US', 'Test')

        # Get summary
        summary = self.blacklist.get_blacklist_summary()

        self.assertEqual(summary['total_db_blacklist'], 1)
        self.assertEqual(summary['total_file_blacklist'], 1)
        self.assertEqual(summary['by_region']['KR']['db_blacklist'], 1)
        self.assertEqual(summary['by_region']['US']['file_blacklist'], 1)

    def test_23_multi_region_blacklist(self):
        """Test blacklist across multiple regions"""
        # Add tickers from different regions
        self.blacklist.deactivate_ticker_db('005930', 'KR')
        self.blacklist.deactivate_ticker_db('AAPL', 'US')
        self.blacklist.add_to_file_blacklist('600519.SS', 'CN', 'Test')

        # Get combined blacklist
        combined = self.blacklist.get_combined_blacklist()

        self.assertIn('005930', combined['KR'])
        self.assertIn('AAPL', combined['US'])
        self.assertIn('600519.SS', combined['CN'])

    def test_24_file_persistence(self):
        """Test blacklist file persistence"""
        # Add to file blacklist
        self.blacklist.add_to_file_blacklist('TSLA', 'US', 'Test')

        # Create new instance (should load from file)
        new_blacklist = BlacklistManager(
            db_manager=self.db,
            config_path=self.temp_blacklist_path
        )

        # Verify loaded correctly
        file_blacklist = new_blacklist.get_file_blacklist(region='US')
        self.assertIn('TSLA', file_blacklist['US'])

    def test_25_invalid_region_handling(self):
        """Test handling of invalid region codes"""
        # Invalid region should return False
        result = self.blacklist.add_to_file_blacklist(
            ticker='INVALID',
            region='XX',  # Invalid region
            reason='Test'
        )

        self.assertFalse(result)

    # ========================================
    # ERROR HANDLING TESTS
    # ========================================

    def test_26_missing_reason_handling(self):
        """Test rejection of blacklist entry without reason"""
        result = self.blacklist.add_to_file_blacklist(
            ticker='TSLA',
            region='US',
            reason=''  # Empty reason
        )

        self.assertFalse(result)

    def test_27_nonexistent_ticker_deactivation(self):
        """Test deactivation of non-existent ticker"""
        result = self.blacklist.deactivate_ticker_db(
            ticker='NONEXISTENT',
            region='KR'
        )

        self.assertFalse(result)

    def test_28_duplicate_file_blacklist_entry(self):
        """Test adding duplicate entry to file blacklist"""
        # Add entry
        self.blacklist.add_to_file_blacklist('TSLA', 'US', 'Reason 1')

        # Add duplicate (should overwrite)
        result = self.blacklist.add_to_file_blacklist('TSLA', 'US', 'Reason 2')

        self.assertTrue(result)

        # Verify updated
        self.assertEqual(
            self.blacklist._file_blacklist['US']['TSLA']['reason'],
            'Reason 2'
        )


def run_tests():
    """Run all tests"""
    unittest.main(verbosity=2)


if __name__ == '__main__':
    run_tests()
