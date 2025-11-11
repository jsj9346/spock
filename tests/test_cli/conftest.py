"""
pytest configuration and fixtures for CLI tests
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime, date
import pandas as pd


# ==================== Async Fixtures ====================

@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ==================== Database Fixtures ====================

@pytest.fixture
def mock_db_manager():
    """Mock DatabaseManager for testing."""
    manager = Mock()
    manager.connect = AsyncMock()
    manager.disconnect = AsyncMock()
    manager.fetch = AsyncMock(return_value=[])
    manager.fetchval = AsyncMock(return_value=0)
    manager.fetchrow = AsyncMock(return_value=None)
    manager.execute = AsyncMock(return_value="SELECT 0")
    return manager


@pytest.fixture
def sample_ticker_data():
    """Sample ticker data for testing."""
    return [
        {
            'ticker': '005930',
            'name': '삼성전자',
            'region': 'KR',
            'exchange': 'KRX',
            'sector': 'Technology',
            'industry': 'Semiconductors'
        },
        {
            'ticker': '000660',
            'name': 'SK하이닉스',
            'region': 'KR',
            'exchange': 'KRX',
            'sector': 'Technology',
            'industry': 'Semiconductors'
        },
        {
            'ticker': '035720',
            'name': '카카오',
            'region': 'KR',
            'exchange': 'KRX',
            'sector': 'Technology',
            'industry': 'Internet Services'
        }
    ]


@pytest.fixture
def sample_fundamental_data():
    """Sample fundamental data for testing."""
    return [
        {
            'ticker': '005930',
            'date': date(2024, 12, 31),
            'per': 12.5,
            'pbr': 1.2,
            'dividend_yield': 2.5,
            'market_cap': 500000000000000,
            'ev_ebitda': 8.5
        },
        {
            'ticker': '000660',
            'date': date(2024, 12, 31),
            'per': 10.3,
            'pbr': 0.9,
            'dividend_yield': 1.8,
            'market_cap': 100000000000000,
            'ev_ebitda': 7.2
        }
    ]


# ==================== OHLCV Fixtures ====================

@pytest.fixture
def sample_ohlcv_data():
    """Sample OHLCV data for testing."""
    dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='B')
    return pd.DataFrame({
        'date': dates,
        'open': 60000 + (dates.day * 100),
        'high': 61000 + (dates.day * 100),
        'low': 59000 + (dates.day * 100),
        'close': 60500 + (dates.day * 100),
        'volume': 10000000 + (dates.day * 10000)
    })


@pytest.fixture
def sample_multi_ticker_ohlcv():
    """Sample multi-ticker OHLCV data for testing."""
    dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='B')
    return {
        '005930': pd.DataFrame({
            'date': dates,
            'open': 60000,
            'high': 61000,
            'low': 59000,
            'close': 60500,
            'volume': 10000000
        }),
        '000660': pd.DataFrame({
            'date': dates,
            'open': 100000,
            'high': 102000,
            'low': 98000,
            'close': 101000,
            'volume': 5000000
        })
    }


# ==================== vectorbt Fixtures ====================

@pytest.fixture
def mock_vectorbt_portfolio():
    """Mock vectorbt Portfolio for testing."""
    portfolio = Mock()
    portfolio.total_return = Mock(return_value=0.25)
    portfolio.sharpe_ratio = Mock(return_value=1.5)
    portfolio.max_drawdown = Mock(return_value=0.15)
    portfolio.total_trades = Mock(return_value=50)
    portfolio.win_rate = Mock(return_value=0.60)
    portfolio.profit_factor = Mock(return_value=1.8)
    portfolio.calmar_ratio = Mock(return_value=1.2)
    portfolio.sortino_ratio = Mock(return_value=1.8)
    portfolio.final_value = Mock(return_value=125000)
    portfolio.value = Mock(return_value=pd.Series([100000, 110000, 125000]))
    portfolio.returns = Mock(return_value=pd.Series([0.0, 0.10, 0.136]))
    return portfolio


# ==================== Chart Fixtures ====================

@pytest.fixture
def sample_backtest_results():
    """Sample backtest results for testing."""
    dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='B')
    return {
        'equity_curve': pd.Series(
            range(100000, 100000 + len(dates) * 100, 100),
            index=dates
        ),
        'returns': pd.Series(
            [0.001] * len(dates),
            index=dates
        ),
        'drawdown': pd.Series(
            [-0.05] * len(dates),
            index=dates
        ),
        'trades': pd.DataFrame({
            'entry_date': dates[:10],
            'exit_date': dates[10:20],
            'pnl': [1000, -500, 2000, -800, 1500, 3000, -1200, 2500, 1800, -600]
        })
    }


# ==================== Config Fixtures ====================

@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        'database': {
            'host': 'localhost',
            'port': 5432,
            'database': 'test_db',
            'user': 'test_user',
            'password': 'test_pass',
            'pool_min_size': 2,
            'pool_max_size': 10
        },
        'api': {
            'kis_appkey': 'test_appkey',
            'kis_appsecret': 'test_appsecret',
            'kis_base_url': 'https://test.api.com'
        },
        'cli': {
            'default_region': 'KR',
            'default_top': 20,
            'max_results': 1000,
            'cache_ttl': 300
        }
    }


# ==================== Cleanup Fixtures ====================

@pytest.fixture(autouse=True)
def cleanup():
    """Cleanup after each test."""
    yield
    # Cleanup code here if needed
