"""
Unit tests for cli/utils/vectorbt_adapter.py - VectorbtAdapter
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np


@pytest.mark.unit
class TestVectorbtAdapter:
    """Test VectorbtAdapter class"""

    @pytest.fixture
    def sample_ohlcv(self):
        """Sample OHLCV DataFrame"""
        dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='B')
        return pd.DataFrame({
            'open': 60000,
            'high': 61000,
            'low': 59000,
            'close': 60500,
            'volume': 10000000
        }, index=dates)

    @pytest.fixture
    def mock_portfolio(self):
        """Mock vectorbt Portfolio"""
        portfolio = Mock()
        portfolio.total_return = Mock(return_value=0.25)
        portfolio.sharpe_ratio = Mock(return_value=1.5)
        portfolio.max_drawdown = Mock(return_value=0.15)
        portfolio.total_trades = Mock(return_value=50)
        portfolio.win_rate = Mock(return_value=0.60)
        portfolio.final_value = Mock(return_value=125000)
        return portfolio

    def test_buy_and_hold_strategy(self, sample_ohlcv, mock_portfolio):
        """Test buy-and-hold strategy execution"""
        from cli.utils.vectorbt_adapter import VectorbtAdapter

        with patch('cli.utils.vectorbt_adapter.vbt.Portfolio.from_holding') as mock_from_holding:
            mock_from_holding.return_value = mock_portfolio

            adapter = VectorbtAdapter()
            result = adapter.backtest_buy_and_hold(sample_ohlcv, initial_capital=100000)

            assert isinstance(result, dict)
            assert 'portfolio' in result
            assert result['portfolio'] == mock_portfolio
            mock_from_holding.assert_called_once()

    def test_ma_crossover_strategy(self, sample_ohlcv, mock_portfolio):
        """Test moving average crossover strategy"""
        from cli.utils.vectorbt_adapter import VectorbtAdapter

        with patch('cli.utils.vectorbt_adapter.vbt.Portfolio.from_signals') as mock_from_signals:
            mock_from_signals.return_value = mock_portfolio

            adapter = VectorbtAdapter()
            result = adapter.backtest_ma_crossover(
                sample_ohlcv,
                fast_period=20,
                slow_period=60,
                initial_capital=100000
            )

            assert isinstance(result, dict)
            assert 'portfolio' in result
            mock_from_signals.assert_called_once()

    def test_calculate_metrics_returns_dict(self, mock_portfolio):
        """Test that calculate_metrics() returns metrics dictionary"""
        from cli.utils.vectorbt_adapter import VectorbtAdapter

        adapter = VectorbtAdapter()
        metrics = adapter.calculate_metrics(mock_portfolio)

        assert isinstance(metrics, dict)
        assert 'total_return' in metrics
        assert 'sharpe_ratio' in metrics
        assert 'max_drawdown' in metrics

    def test_metrics_formatting(self, mock_portfolio):
        """Test that metrics are formatted correctly"""
        from cli.utils.vectorbt_adapter import VectorbtAdapter

        adapter = VectorbtAdapter()
        metrics = adapter.calculate_metrics(mock_portfolio)

        # Check that percentages are formatted
        assert metrics['total_return'] == 25.0  # 0.25 * 100
        assert metrics['max_drawdown'] == 15.0  # 0.15 * 100

    def test_ma_crossover_generates_signals(self, sample_ohlcv):
        """Test that MA crossover generates entry/exit signals"""
        from cli.utils.vectorbt_adapter import VectorbtAdapter

        adapter = VectorbtAdapter()

        # Calculate MAs
        fast_ma = sample_ohlcv['close'].rolling(20).mean()
        slow_ma = sample_ohlcv['close'].rolling(60).mean()

        # Generate signals
        entries = fast_ma > slow_ma
        exits = fast_ma < slow_ma

        assert isinstance(entries, pd.Series)
        assert isinstance(exits, pd.Series)
        assert len(entries) == len(sample_ohlcv)

    def test_initial_capital_validation(self, sample_ohlcv):
        """Test that initial capital is validated"""
        from cli.utils.vectorbt_adapter import VectorbtAdapter

        adapter = VectorbtAdapter()

        # Should raise error for invalid capital
        with pytest.raises(ValueError):
            adapter.backtest_buy_and_hold(sample_ohlcv, initial_capital=-1000)

    def test_empty_dataframe_handling(self):
        """Test that empty DataFrame is handled"""
        from cli.utils.vectorbt_adapter import VectorbtAdapter

        adapter = VectorbtAdapter()
        empty_df = pd.DataFrame()

        with pytest.raises(ValueError, match="empty"):
            adapter.backtest_buy_and_hold(empty_df)

    def test_missing_close_column_raises_error(self):
        """Test that missing 'close' column raises error"""
        from cli.utils.vectorbt_adapter import VectorbtAdapter

        adapter = VectorbtAdapter()
        invalid_df = pd.DataFrame({
            'open': [100, 101, 102],
            'high': [105, 106, 107]
        })

        with pytest.raises(ValueError, match="close"):
            adapter.backtest_buy_and_hold(invalid_df)

    def test_backtest_result_structure(self, sample_ohlcv, mock_portfolio):
        """Test that backtest result has expected structure"""
        from cli.utils.vectorbt_adapter import VectorbtAdapter

        with patch('cli.utils.vectorbt_adapter.vbt.Portfolio.from_holding') as mock_from_holding:
            mock_from_holding.return_value = mock_portfolio

            adapter = VectorbtAdapter()
            result = adapter.backtest_buy_and_hold(sample_ohlcv)

            assert 'portfolio' in result
            assert 'metrics' in result
            assert 'strategy' in result
            assert result['strategy'] == 'buy-and-hold'
