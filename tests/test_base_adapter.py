"""
Unit Tests for BaseMarketAdapter

Tests for abstract methods, shared utilities, and technical indicator calculations.

Run with: python -m pytest tests/test_base_adapter.py -v
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict
import sys
import os

# Add modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.market_adapters.base_adapter import BaseMarketAdapter


# ========================================
# MOCK DATABASE MANAGER
# ========================================

class MockDatabaseManager:
    """Mock database manager for testing"""

    def __init__(self):
        self.tickers = []
        self.last_update_times = {}
        self.deleted_count = 0
        self.inserted_tickers = []
        self.inserted_stock_details = []
        self.inserted_etf_details = []
        self.inserted_fundamentals = []
        self.ohlcv_data = []

    def get_last_update_time(self, region, asset_type):
        """Mock get_last_update_time"""
        key = f"{region}_{asset_type}"
        return self.last_update_times.get(key)

    def get_tickers(self, region, asset_type, is_active=True):
        """Mock get_tickers"""
        return [t for t in self.tickers
                if t['region'] == region and t['asset_type'] == asset_type]

    def delete_tickers(self, region, asset_type):
        """Mock delete_tickers"""
        original_count = len(self.tickers)
        self.tickers = [t for t in self.tickers
                       if not (t['region'] == region and t['asset_type'] == asset_type)]
        deleted = original_count - len(self.tickers)
        self.deleted_count = deleted
        return deleted

    def insert_ticker(self, ticker_data):
        """Mock insert_ticker"""
        self.inserted_tickers.append(ticker_data)
        self.tickers.append(ticker_data)
        return True

    def insert_stock_details(self, stock_data):
        """Mock insert_stock_details"""
        self.inserted_stock_details.append(stock_data)
        return True

    def insert_etf_details(self, etf_data):
        """Mock insert_etf_details"""
        self.inserted_etf_details.append(etf_data)
        return True

    def insert_ticker_fundamentals(self, fundamental_data):
        """Mock insert_ticker_fundamentals"""
        self.inserted_fundamentals.append(fundamental_data)
        return True

    def insert_ohlcv_bulk(self, ticker, ohlcv_df, timeframe):
        """Mock insert_ohlcv_bulk"""
        self.ohlcv_data.append({
            'ticker': ticker,
            'rows': len(ohlcv_df),
            'timeframe': timeframe
        })
        return len(ohlcv_df)

    def get_stock_tickers(self, region):
        """Mock get_stock_tickers"""
        return [t['ticker'] for t in self.tickers
                if t['region'] == region and t['asset_type'] == 'STOCK']

    def get_etf_tickers(self, region):
        """Mock get_etf_tickers"""
        return [t['ticker'] for t in self.tickers
                if t['region'] == region and t['asset_type'] == 'ETF']


# ========================================
# CONCRETE ADAPTER FOR TESTING
# ========================================

class TestAdapter(BaseMarketAdapter):
    """Concrete implementation of BaseMarketAdapter for testing"""

    def scan_stocks(self, force_refresh=False):
        """Test implementation"""
        return [
            {
                'ticker': '005930',
                'name': 'Samsung Electronics',
                'exchange': 'KOSPI',
                'market_tier': 'MAIN',
                'currency': 'KRW',
            }
        ]

    def scan_etfs(self, force_refresh=False):
        """Test implementation"""
        return [
            {
                'ticker': '229200',
                'name': 'KODEX 200',
                'exchange': 'KOSPI',
                'tracking_index': 'KOSPI 200',
                'currency': 'KRW',
            }
        ]

    def collect_stock_ohlcv(self, tickers=None, days=250):
        """Test implementation"""
        return len(tickers) if tickers else 0

    def collect_etf_ohlcv(self, tickers=None, days=250):
        """Test implementation"""
        return len(tickers) if tickers else 0


# ========================================
# FIXTURES
# ========================================

@pytest.fixture
def mock_db():
    """Fixture for mock database manager"""
    return MockDatabaseManager()


@pytest.fixture
def test_adapter(mock_db):
    """Fixture for test adapter"""
    return TestAdapter(mock_db, region_code='KR')


@pytest.fixture
def sample_ohlcv_df():
    """Fixture for sample OHLCV DataFrame"""
    dates = pd.date_range(start='2023-01-01', periods=250, freq='D')
    np.random.seed(42)

    df = pd.DataFrame({
        'date': dates,
        'open': 60000 + np.random.randn(250) * 1000,
        'high': 62000 + np.random.randn(250) * 1000,
        'low': 58000 + np.random.randn(250) * 1000,
        'close': 60000 + np.random.randn(250) * 1000,
        'volume': 10000000 + np.random.randint(-1000000, 1000000, 250),
    })

    return df


# ========================================
# TEST CASES
# ========================================

class TestAbstractMethods:
    """Test abstract method enforcement"""

    def test_cannot_instantiate_base_adapter(self):
        """BaseMarketAdapter cannot be instantiated directly"""
        with pytest.raises(TypeError) as exc_info:
            BaseMarketAdapter(None, 'KR')

        assert "Can't instantiate abstract class" in str(exc_info.value)

    def test_concrete_adapter_can_be_instantiated(self, mock_db):
        """Concrete adapter can be instantiated"""
        adapter = TestAdapter(mock_db, region_code='KR')
        assert adapter.region_code == 'KR'
        assert adapter.db == mock_db

    def test_abstract_methods_defined(self):
        """All abstract methods are properly defined"""
        abstract_methods = BaseMarketAdapter.__abstractmethods__
        expected = {'scan_stocks', 'scan_etfs', 'collect_stock_ohlcv', 'collect_etf_ohlcv'}
        assert abstract_methods == expected


class TestCacheOperations:
    """Test cache loading with TTL"""

    def test_cache_miss_no_data(self, test_adapter):
        """Cache miss when no data exists"""
        result = test_adapter._load_tickers_from_cache(asset_type='STOCK')
        assert result is None

    def test_cache_hit_within_ttl(self, test_adapter, mock_db):
        """Cache hit when data exists and within TTL"""
        # Setup: Add tickers with recent update time
        now = datetime.now()
        mock_db.last_update_times['KR_STOCK'] = now
        mock_db.tickers = [
            {'ticker': '005930', 'name': 'Samsung', 'region': 'KR', 'asset_type': 'STOCK'},
            {'ticker': '035720', 'name': 'Kakao', 'region': 'KR', 'asset_type': 'STOCK'},
        ]

        result = test_adapter._load_tickers_from_cache(asset_type='STOCK', ttl_hours=24)

        assert result is not None
        assert len(result) == 2
        assert result[0]['ticker'] == '005930'

    def test_cache_expired_beyond_ttl(self, test_adapter, mock_db):
        """Cache miss when data is expired (beyond TTL)"""
        # Setup: Add tickers with old update time
        old_time = datetime.now() - timedelta(hours=25)  # 25 hours ago (beyond 24h TTL)
        mock_db.last_update_times['KR_STOCK'] = old_time
        mock_db.tickers = [
            {'ticker': '005930', 'name': 'Samsung', 'region': 'KR', 'asset_type': 'STOCK'},
        ]

        result = test_adapter._load_tickers_from_cache(asset_type='STOCK', ttl_hours=24)

        assert result is None  # Cache expired

    def test_cache_custom_ttl(self, test_adapter, mock_db):
        """Custom TTL works correctly"""
        # Setup: Data is 10 hours old
        ten_hours_ago = datetime.now() - timedelta(hours=10)
        mock_db.last_update_times['KR_ETF'] = ten_hours_ago
        mock_db.tickers = [
            {'ticker': '229200', 'name': 'KODEX 200', 'region': 'KR', 'asset_type': 'ETF'},
        ]

        # Test with 12-hour TTL (should hit)
        result = test_adapter._load_tickers_from_cache(asset_type='ETF', ttl_hours=12)
        assert result is not None

        # Test with 8-hour TTL (should miss)
        result = test_adapter._load_tickers_from_cache(asset_type='ETF', ttl_hours=8)
        assert result is None


class TestDatabaseSaveOperations:
    """Test saving tickers to database"""

    def test_save_stocks_to_db(self, test_adapter, mock_db):
        """Save stock tickers to database"""
        stocks = [
            {
                'ticker': '005930',
                'name': '삼성전자',
                'name_eng': 'Samsung Electronics',
                'exchange': 'KOSPI',
                'market_tier': 'MAIN',
                'currency': 'KRW',
                'sector': 'Information Technology',
                'industry': 'Semiconductors',
                'is_preferred': False,
                'market_cap': 500000000000000,
                'close_price': 70000,
                'data_source': 'KRX Data API',
            }
        ]

        test_adapter._save_tickers_to_db(stocks, asset_type='STOCK')

        # Verify tickers table
        assert len(mock_db.inserted_tickers) == 1
        assert mock_db.inserted_tickers[0]['ticker'] == '005930'
        assert mock_db.inserted_tickers[0]['region'] == 'KR'
        assert mock_db.inserted_tickers[0]['asset_type'] == 'STOCK'

        # Verify stock_details table
        assert len(mock_db.inserted_stock_details) == 1
        assert mock_db.inserted_stock_details[0]['sector'] == 'Information Technology'

        # Verify ticker_fundamentals table
        assert len(mock_db.inserted_fundamentals) == 1
        assert mock_db.inserted_fundamentals[0]['market_cap'] == 500000000000000

    def test_save_etfs_to_db(self, test_adapter, mock_db):
        """Save ETF tickers to database"""
        etfs = [
            {
                'ticker': '229200',
                'name': 'KODEX 200',
                'exchange': 'KOSPI',
                'market_tier': 'MAIN',
                'currency': 'KRW',
                'issuer': '삼성자산운용',
                'tracking_index': 'KOSPI 200',
                'expense_ratio': 0.15,
                'data_source': 'KRX Data API',
            }
        ]

        test_adapter._save_tickers_to_db(etfs, asset_type='ETF')

        # Verify tickers table
        assert len(mock_db.inserted_tickers) == 1
        assert mock_db.inserted_tickers[0]['asset_type'] == 'ETF'

        # Verify etf_details table
        assert len(mock_db.inserted_etf_details) == 1
        assert mock_db.inserted_etf_details[0]['tracking_index'] == 'KOSPI 200'

    def test_delete_existing_tickers_before_insert(self, test_adapter, mock_db):
        """Existing tickers are deleted before new insert"""
        # Setup: Add existing tickers
        mock_db.tickers = [
            {'ticker': 'OLD001', 'region': 'KR', 'asset_type': 'STOCK'},
            {'ticker': 'OLD002', 'region': 'KR', 'asset_type': 'STOCK'},
        ]

        new_stocks = [
            {
                'ticker': '005930',
                'name': 'Samsung',
                'exchange': 'KOSPI',
                'currency': 'KRW',
                'data_source': 'Test',
            }
        ]

        test_adapter._save_tickers_to_db(new_stocks, asset_type='STOCK')

        # Verify old tickers were deleted
        assert mock_db.deleted_count == 2

        # Verify new ticker was inserted
        assert len(mock_db.inserted_tickers) == 1


class TestTechnicalIndicators:
    """Test technical indicator calculations"""

    def test_moving_averages(self, test_adapter, sample_ohlcv_df):
        """Calculate moving averages (MA5, MA20, MA60, MA120, MA200)"""
        result_df = test_adapter._calculate_technical_indicators(sample_ohlcv_df.copy())

        # Check all MA columns exist
        for period in [5, 20, 60, 120, 200]:
            col = f'ma{period}'
            assert col in result_df.columns, f"{col} not calculated"
            assert not result_df[col].isna().all(), f"{col} is all NaN"

        # Verify MA200 requires 200 rows
        assert result_df['ma200'].isna().sum() >= 199  # First 199 should be NaN

        # Verify MA5 requires only 5 rows
        assert result_df['ma5'].isna().sum() <= 4  # First 4 can be NaN

    def test_rsi(self, test_adapter, sample_ohlcv_df):
        """Calculate RSI-14"""
        result_df = test_adapter._calculate_technical_indicators(sample_ohlcv_df.copy())

        assert 'rsi_14' in result_df.columns
        assert not result_df['rsi_14'].isna().all()

        # RSI should be between 0 and 100
        valid_rsi = result_df['rsi_14'].dropna()
        assert (valid_rsi >= 0).all() and (valid_rsi <= 100).all()

    def test_macd(self, test_adapter, sample_ohlcv_df):
        """Calculate MACD (12, 26, 9)"""
        result_df = test_adapter._calculate_technical_indicators(sample_ohlcv_df.copy())

        assert 'macd' in result_df.columns
        assert 'macd_signal' in result_df.columns
        assert 'macd_hist' in result_df.columns

        # MACD histogram = MACD - Signal
        valid_rows = result_df.dropna(subset=['macd', 'macd_signal', 'macd_hist'])
        if len(valid_rows) > 0:
            calculated_hist = valid_rows['macd'] - valid_rows['macd_signal']
            assert np.allclose(calculated_hist, valid_rows['macd_hist'], atol=1e-5)

    def test_bollinger_bands(self, test_adapter, sample_ohlcv_df):
        """Calculate Bollinger Bands (20, 2.0)"""
        result_df = test_adapter._calculate_technical_indicators(sample_ohlcv_df.copy())

        assert 'bb_upper' in result_df.columns
        assert 'bb_middle' in result_df.columns
        assert 'bb_lower' in result_df.columns

        # Upper > Middle > Lower
        valid_rows = result_df.dropna(subset=['bb_upper', 'bb_middle', 'bb_lower'])
        if len(valid_rows) > 0:
            assert (valid_rows['bb_upper'] >= valid_rows['bb_middle']).all()
            assert (valid_rows['bb_middle'] >= valid_rows['bb_lower']).all()

    def test_atr(self, test_adapter, sample_ohlcv_df):
        """Calculate ATR-14"""
        result_df = test_adapter._calculate_technical_indicators(sample_ohlcv_df.copy())

        assert 'atr_14' in result_df.columns
        assert not result_df['atr_14'].isna().all()

        # ATR should be positive
        valid_atr = result_df['atr_14'].dropna()
        assert (valid_atr >= 0).all()

    def test_all_indicators_together(self, test_adapter, sample_ohlcv_df):
        """All indicators calculated without errors"""
        result_df = test_adapter._calculate_technical_indicators(sample_ohlcv_df.copy())

        # Check all expected columns exist
        expected_cols = [
            'ma5', 'ma20', 'ma60', 'ma120', 'ma200',
            'rsi_14',
            'macd', 'macd_signal', 'macd_hist',
            'bb_upper', 'bb_middle', 'bb_lower',
            'atr_14'
        ]

        for col in expected_cols:
            assert col in result_df.columns, f"Missing column: {col}"


class TestOptionalMethods:
    """Test optional methods with default implementations"""

    def test_collect_fundamentals_default(self, test_adapter):
        """Default collect_fundamentals returns 0"""
        result = test_adapter.collect_fundamentals()
        assert result == 0


class TestRegionCode:
    """Test region code handling"""

    def test_region_code_stored(self, mock_db):
        """Region code is stored correctly"""
        kr_adapter = TestAdapter(mock_db, region_code='KR')
        us_adapter = TestAdapter(mock_db, region_code='US')

        assert kr_adapter.region_code == 'KR'
        assert us_adapter.region_code == 'US'

    def test_region_code_used_in_cache(self, mock_db):
        """Region code is used in cache operations"""
        kr_adapter = TestAdapter(mock_db, region_code='KR')

        # Setup: KR data exists
        mock_db.last_update_times['KR_STOCK'] = datetime.now()
        mock_db.tickers = [
            {'ticker': '005930', 'region': 'KR', 'asset_type': 'STOCK'},
        ]

        # KR adapter should find data
        result = kr_adapter._load_tickers_from_cache(asset_type='STOCK')
        assert result is not None

        # US adapter should not find KR data
        us_adapter = TestAdapter(mock_db, region_code='US')
        result = us_adapter._load_tickers_from_cache(asset_type='STOCK')
        assert result is None or len(result) == 0


# ========================================
# TEST SUMMARY
# ========================================

def test_module_imports():
    """Test that all modules import correctly"""
    from modules.market_adapters import BaseMarketAdapter as BMA
    assert BMA is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
