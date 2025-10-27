"""
Unit Tests for PostgreSQL Database Manager

Tests connection pooling, ticker management, OHLCV operations,
and conversion helpers.

Author: Quant Platform Development Team
Date: 2025-10-20
"""

import pytest
import pandas as pd
from datetime import datetime, date, timedelta
import sys
import os
from psycopg2 import extras

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_postgres import PostgresDatabaseManager


@pytest.fixture(scope='module')
def db_manager():
    """Create database manager for testing"""
    manager = PostgresDatabaseManager(
        host='localhost',
        port=5432,
        database='quant_platform',
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD', ''),
        pool_min_conn=2,
        pool_max_conn=5
    )
    yield manager
    manager.close_pool()


@pytest.fixture(scope='function')
def clean_test_data(db_manager):
    """Clean up test data before and after each test"""
    test_tickers = ['TEST001', 'TEST002', 'TEST003', 'TEST004', 'TEST005', 'AAPL', '005930']

    # Clean before test
    for ticker in test_tickers:
        try:
            # Delete from all related tables first
            db_manager._execute_query(
                "DELETE FROM ohlcv_data WHERE ticker = %s AND region = %s",
                (ticker, 'KR'),
                commit=True
            )
        except:
            pass
        try:
            # Then delete ticker (CASCADE will handle other tables)
            db_manager._execute_query(
                "DELETE FROM tickers WHERE ticker = %s AND region = %s",
                (ticker, 'KR'),
                commit=True
            )
        except:
            pass

    yield

    # Clean after test
    for ticker in test_tickers:
        try:
            db_manager._execute_query(
                "DELETE FROM ohlcv_data WHERE ticker = %s AND region = %s",
                (ticker, 'KR'),
                commit=True
            )
        except:
            pass
        try:
            db_manager._execute_query(
                "DELETE FROM tickers WHERE ticker = %s AND region = %s",
                (ticker, 'KR'),
                commit=True
            )
        except:
            pass


class TestConnectionPool:
    """Test connection pool functionality"""

    def test_pool_creation(self, db_manager):
        """Test connection pool is created successfully"""
        assert db_manager.pool is not None
        assert db_manager.pool.minconn == 2
        assert db_manager.pool.maxconn == 5
        assert db_manager.host == 'localhost'
        assert db_manager.port == 5432
        assert db_manager.database == 'quant_platform'

    def test_connection_acquire_release(self, db_manager):
        """Test connection acquire and release"""
        with db_manager._get_connection() as conn:
            assert conn is not None
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("SELECT 1 AS test")
            result = cursor.fetchone()
            assert result['test'] == 1
            cursor.close()

    def test_connection_context_manager(self, db_manager):
        """Test PostgresConnection context manager"""
        with db_manager._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("SELECT version()")
            result = cursor.fetchone()
            assert result is not None
            assert 'PostgreSQL' in result['version']
            cursor.close()

    def test_connection_test(self, db_manager):
        """Test connection test method"""
        result = db_manager.test_connection()
        assert result is True

    def test_pool_close(self):
        """Test pool closure"""
        temp_manager = PostgresDatabaseManager(pool_min_conn=1, pool_max_conn=2)
        temp_manager.close_pool()
        # Pool should be closed
        assert temp_manager.pool is not None  # Pool object exists but connections closed


class TestHelperMethods:
    """Test helper methods"""

    def test_convert_boolean_true(self, db_manager):
        """Test boolean conversion for true values"""
        assert db_manager._convert_boolean(True) is True
        assert db_manager._convert_boolean(1) is True
        assert db_manager._convert_boolean('1') is True
        assert db_manager._convert_boolean('true') is True
        assert db_manager._convert_boolean('True') is True
        assert db_manager._convert_boolean('yes') is True

    def test_convert_boolean_false(self, db_manager):
        """Test boolean conversion for false values"""
        assert db_manager._convert_boolean(False) is False
        assert db_manager._convert_boolean(0) is False
        assert db_manager._convert_boolean('0') is False
        assert db_manager._convert_boolean('false') is False

    def test_convert_boolean_none(self, db_manager):
        """Test boolean conversion for None"""
        assert db_manager._convert_boolean(None) is None

    def test_convert_datetime(self, db_manager):
        """Test datetime conversion"""
        now = datetime.now()
        result = db_manager._convert_datetime(now)
        assert isinstance(result, str)
        assert 'T' in result  # ISO format contains 'T'

        today = date.today()
        result = db_manager._convert_datetime(today)
        assert isinstance(result, str)

        result = db_manager._convert_datetime(None)
        assert result is None

    def test_infer_region_kr(self, db_manager):
        """Test region inference for Korean tickers"""
        assert db_manager._infer_region('005930') == 'KR'
        assert db_manager._infer_region('035720') == 'KR'

    def test_infer_region_us(self, db_manager):
        """Test region inference for US tickers"""
        assert db_manager._infer_region('AAPL') == 'US'
        assert db_manager._infer_region('GOOGL') == 'US'

    def test_infer_region_hk(self, db_manager):
        """Test region inference for Hong Kong tickers"""
        assert db_manager._infer_region('00700') == 'HK'
        assert db_manager._infer_region('03690') == 'HK'


class TestTickerManagement:
    """Test ticker management methods"""

    def test_insert_ticker_new(self, db_manager, clean_test_data):
        """Test inserting new ticker"""
        ticker_data = {
            'ticker': 'TEST001',
            'name': 'Test Company 1',
            'name_eng': 'Test Company One',
            'exchange': 'KOSPI',
            'region': 'KR',
            'currency': 'KRW',
            'asset_type': 'STOCK',
            'is_active': True,
            'data_source': 'Unit Test'
        }
        result = db_manager.insert_ticker(ticker_data)
        assert result is True

        # Verify insertion
        ticker = db_manager.get_ticker('TEST001', 'KR')
        assert ticker is not None
        assert ticker['name'] == 'Test Company 1'
        assert ticker['exchange'] == 'KOSPI'
        assert ticker['is_active'] is True

    def test_insert_ticker_update(self, db_manager, clean_test_data):
        """Test updating existing ticker (ON CONFLICT)"""
        # Insert initial data
        ticker_data = {
            'ticker': 'TEST002',
            'name': 'Test Company 2',
            'exchange': 'KOSDAQ',
            'region': 'KR',
            'asset_type': 'STOCK',
            'is_active': True
        }
        db_manager.insert_ticker(ticker_data)

        # Update with new data
        ticker_data['name'] = 'Test Company 2 Updated'
        ticker_data['is_active'] = False
        result = db_manager.insert_ticker(ticker_data)
        assert result is True

        # Verify update
        ticker = db_manager.get_ticker('TEST002', 'KR')
        assert ticker is not None
        assert 'Updated' in ticker['name']
        assert ticker['is_active'] is False

    def test_get_ticker(self, db_manager, clean_test_data):
        """Test getting ticker by composite key"""
        # Insert test data
        ticker_data = {
            'ticker': 'AAPL',
            'name': 'Apple Inc.',
            'exchange': 'NASDAQ',
            'region': 'US',
            'asset_type': 'STOCK',
            'is_active': True
        }
        db_manager.insert_ticker(ticker_data)

        # Get ticker
        ticker = db_manager.get_ticker('AAPL', 'US')
        assert ticker is not None
        assert ticker['name'] == 'Apple Inc.'
        assert ticker['region'] == 'US'

    def test_get_ticker_legacy(self, db_manager, clean_test_data):
        """Test legacy get_ticker with explicit region"""
        # Insert test data
        ticker_data = {
            'ticker': 'TEST001',
            'name': 'Test Company',
            'exchange': 'KOSPI',
            'region': 'KR',
            'asset_type': 'STOCK',
            'is_active': True
        }
        db_manager.insert_ticker(ticker_data)

        # Get ticker with explicit region (legacy method supports optional region)
        ticker = db_manager.get_ticker_legacy('TEST001', 'KR')
        assert ticker is not None
        assert ticker['name'] == 'Test Company'

        # Test with proper KR ticker format (6 digits) for auto-inference
        ticker_data2 = {
            'ticker': '005930',
            'name': 'Samsung Electronics',
            'exchange': 'KOSPI',
            'region': 'KR',
            'asset_type': 'STOCK',
            'is_active': True
        }
        db_manager.insert_ticker(ticker_data2)

        # This should infer region='KR' from 6-digit format
        ticker2 = db_manager.get_ticker_legacy('005930')
        assert ticker2 is not None
        assert ticker2['name'] == 'Samsung Electronics'

    def test_get_tickers_by_region(self, db_manager, clean_test_data):
        """Test getting tickers by region"""
        # Insert test data
        for i in range(3):
            ticker_data = {
                'ticker': f'TEST00{i+1}',
                'name': f'Test Company {i+1}',
                'exchange': 'KOSPI',
                'region': 'KR',
                'asset_type': 'STOCK',
                'is_active': True
            }
            db_manager.insert_ticker(ticker_data)

        # Get tickers
        tickers = db_manager.get_tickers('KR', asset_type='STOCK')
        assert len(tickers) >= 3

        # Check if test tickers are in results
        ticker_codes = [t['ticker'] for t in tickers]
        assert 'TEST001' in ticker_codes

    def test_get_tickers_with_filters(self, db_manager, clean_test_data):
        """Test getting tickers with multiple filters"""
        # Insert active and inactive tickers
        db_manager.insert_ticker({
            'ticker': 'TEST001',
            'name': 'Active Stock',
            'exchange': 'KOSPI',
            'region': 'KR',
            'asset_type': 'STOCK',
            'is_active': True
        })
        db_manager.insert_ticker({
            'ticker': 'TEST002',
            'name': 'Inactive Stock',
            'exchange': 'KOSPI',
            'region': 'KR',
            'asset_type': 'STOCK',
            'is_active': False
        })

        # Get active tickers only
        active_tickers = db_manager.get_tickers('KR', asset_type='STOCK', is_active=True)
        active_codes = [t['ticker'] for t in active_tickers]
        assert 'TEST001' in active_codes
        assert 'TEST002' not in active_codes

    def test_update_ticker(self, db_manager, clean_test_data):
        """Test updating ticker fields"""
        # Insert initial data
        db_manager.insert_ticker({
            'ticker': 'TEST001',
            'name': 'Original Name',
            'exchange': 'KOSPI',
            'region': 'KR',
            'asset_type': 'STOCK',
            'is_active': True
        })

        # Update ticker
        result = db_manager.update_ticker('TEST001', 'KR', {
            'name': 'Updated Name',
            'is_active': False
        })
        assert result is True

        # Verify update
        ticker = db_manager.get_ticker('TEST001', 'KR')
        assert ticker['name'] == 'Updated Name'
        assert ticker['is_active'] is False

    def test_delete_ticker(self, db_manager, clean_test_data):
        """Test deleting ticker"""
        # Insert test data
        db_manager.insert_ticker({
            'ticker': 'TEST001',
            'name': 'To Be Deleted',
            'exchange': 'KOSPI',
            'region': 'KR',
            'asset_type': 'STOCK',
            'is_active': True
        })

        # Delete ticker
        result = db_manager.delete_ticker('TEST001', 'KR')
        assert result is True

        # Verify deletion
        ticker = db_manager.get_ticker('TEST001', 'KR')
        assert ticker is None

    def test_count_tickers(self, db_manager, clean_test_data):
        """Test counting tickers"""
        # Insert test data
        for i in range(5):
            db_manager.insert_ticker({
                'ticker': f'TEST00{i+1}',
                'name': f'Test Company {i+1}',
                'exchange': 'KOSPI',
                'region': 'KR',
                'asset_type': 'STOCK',
                'is_active': True
            })

        # Count tickers
        count = db_manager.count_tickers('KR', asset_type='STOCK')
        assert count >= 5


class TestOHLCVData:
    """Test OHLCV data methods"""

    def test_insert_ohlcv_single(self, db_manager, clean_test_data):
        """Test inserting single OHLCV record"""
        # Insert test ticker
        db_manager.insert_ticker({
            'ticker': 'TEST001',
            'name': 'Test Company',
            'exchange': 'KOSPI',
            'region': 'KR',
            'asset_type': 'STOCK',
            'is_active': True
        })

        # Insert OHLCV
        result = db_manager.insert_ohlcv(
            ticker='TEST001',
            region='KR',
            timeframe='D',
            date_str='2024-01-01',
            open_price=10000,
            high=10500,
            low=9500,
            close=10200,
            volume=1000000
        )
        assert result is True

        # Verify insertion
        latest = db_manager.get_latest_ohlcv('TEST001', region='KR')
        assert latest is not None
        assert latest['close'] == 10200

    def test_bulk_insert_ohlcv(self, db_manager, clean_test_data):
        """Test bulk insert using COPY command"""
        # Insert test ticker
        db_manager.insert_ticker({
            'ticker': 'TEST001',
            'name': 'Test Company',
            'exchange': 'KOSPI',
            'region': 'KR',
            'asset_type': 'STOCK',
            'is_active': True
        })

        # Create sample OHLCV data
        dates = pd.date_range('2024-01-01', periods=100)
        df = pd.DataFrame({
            'date': dates,
            'open': 10000,
            'high': 10500,
            'low': 9500,
            'close': 10200,
            'volume': 1000000
        })

        # Bulk insert
        count = db_manager.insert_ohlcv_bulk('TEST001', df, timeframe='D', region='KR')
        assert count == 100

        # Verify insertion
        result_df = db_manager.get_ohlcv_data('TEST001', timeframe='D', region='KR')
        assert len(result_df) >= 100

    def test_get_ohlcv_data(self, db_manager, clean_test_data):
        """Test getting OHLCV data with date range"""
        # Insert test ticker
        db_manager.insert_ticker({
            'ticker': 'TEST001',
            'name': 'Test Company',
            'exchange': 'KOSPI',
            'region': 'KR',
            'asset_type': 'STOCK',
            'is_active': True
        })

        # Insert OHLCV data
        dates = pd.date_range('2024-01-01', periods=30)
        df = pd.DataFrame({
            'date': dates,
            'open': 10000,
            'high': 10500,
            'low': 9500,
            'close': 10200,
            'volume': 1000000
        })
        db_manager.insert_ohlcv_bulk('TEST001', df, region='KR')

        # Get data with date range
        result_df = db_manager.get_ohlcv_data(
            'TEST001',
            start_date='2024-01-10',
            end_date='2024-01-20',
            region='KR'
        )
        assert 8 <= len(result_df) <= 12  # Should get ~11 days

    def test_get_latest_ohlcv(self, db_manager, clean_test_data):
        """Test getting latest OHLCV record"""
        # Insert test ticker
        db_manager.insert_ticker({
            'ticker': 'TEST001',
            'name': 'Test Company',
            'exchange': 'KOSPI',
            'region': 'KR',
            'asset_type': 'STOCK',
            'is_active': True
        })

        # Insert OHLCV data
        dates = pd.date_range('2024-01-01', periods=10)
        df = pd.DataFrame({
            'date': dates,
            'open': 10000,
            'high': 10500,
            'low': 9500,
            'close': 10200,
            'volume': 1000000
        })
        db_manager.insert_ohlcv_bulk('TEST001', df, region='KR')

        # Get latest
        latest = db_manager.get_latest_ohlcv('TEST001', region='KR')
        assert latest is not None
        # Latest date should be last date in series
        assert str(latest['date']).startswith('2024-01-10')


class TestBulkOperations:
    """Test generic bulk insert operations"""

    def test_bulk_insert_generic(self, db_manager, clean_test_data):
        """Test generic bulk insert using COPY"""
        # Insert test tickers first
        for i in range(5):
            db_manager.insert_ticker({
                'ticker': f'TEST00{i+1}',
                'name': f'Test Company {i+1}',
                'exchange': 'KOSPI',
                'region': 'KR',
                'asset_type': 'STOCK',
                'is_active': True
            })

        # Create OHLCV DataFrame for bulk insert
        data = []
        for i in range(5):
            for j in range(10):
                data.append({
                    'ticker': f'TEST00{i+1}',
                    'region': 'KR',
                    'timeframe': 'D',
                    'date': pd.Timestamp('2024-01-01') + pd.Timedelta(days=j),
                    'open': 10000,
                    'high': 10500,
                    'low': 9500,
                    'close': 10200,
                    'volume': 1000000,
                    'created_at': datetime.now()
                })

        df = pd.DataFrame(data)
        columns = ['ticker', 'region', 'timeframe', 'date',
                   'open', 'high', 'low', 'close', 'volume', 'created_at']

        # Bulk insert
        count = db_manager.bulk_insert_generic('ohlcv_data', df, columns)
        assert count == 50  # 5 tickers × 10 days


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v', '--tb=short'])
