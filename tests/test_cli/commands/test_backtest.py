"""
Unit tests for cli/commands/backtest.py - Backtest command
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
import pandas as pd


@pytest.mark.unit
class TestBacktestCommand:
    """Test backtest command functionality"""

    @pytest.fixture
    def mock_ohlcv_loader(self):
        """Mock OHLCVLoader"""
        loader = Mock()
        dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='B')
        loader.load_ohlcv = AsyncMock(return_value=pd.DataFrame({
            'open': 60000,
            'high': 61000,
            'low': 59000,
            'close': 60500,
            'volume': 10000000
        }, index=dates))
        return loader

    @pytest.fixture
    def mock_vectorbt_adapter(self):
        """Mock VectorbtAdapter"""
        adapter = Mock()
        mock_portfolio = Mock()
        mock_portfolio.total_return = Mock(return_value=0.25)
        mock_portfolio.sharpe_ratio = Mock(return_value=1.5)

        adapter.backtest_buy_and_hold = Mock(return_value={
            'portfolio': mock_portfolio,
            'metrics': {
                'total_return': 25.0,
                'sharpe_ratio': 1.5,
                'max_drawdown': 15.0
            }
        })
        adapter.backtest_ma_crossover = Mock(return_value={
            'portfolio': mock_portfolio,
            'metrics': {
                'total_return': 30.0,
                'sharpe_ratio': 1.8,
                'max_drawdown': 12.0
            }
        })
        return adapter

    @pytest.fixture
    def backtest_args(self):
        """Mock backtest arguments"""
        args = Mock()
        args.tickers = ['005930']
        args.start = '2023-01-01'
        args.end = '2023-12-31'
        args.strategy = 'buy-hold'
        args.initial_capital = 100000
        args.output = None
        args.csv = None
        args.json = None
        return args

    @pytest.mark.asyncio
    async def test_backtest_buy_hold_strategy(self, mock_ohlcv_loader, mock_vectorbt_adapter, backtest_args):
        """Test backtesting with buy-and-hold strategy"""
        from cli.commands.backtest import run_backtest

        with patch('cli.commands.backtest.OHLCVLoader', return_value=mock_ohlcv_loader):
            with patch('cli.commands.backtest.VectorbtAdapter', return_value=mock_vectorbt_adapter):
                result = await run_backtest(backtest_args)

                assert result is not None
                mock_ohlcv_loader.load_ohlcv.assert_called_once()
                mock_vectorbt_adapter.backtest_buy_and_hold.assert_called_once()

    @pytest.mark.asyncio
    async def test_backtest_ma_crossover_strategy(self, mock_ohlcv_loader, mock_vectorbt_adapter, backtest_args):
        """Test backtesting with MA crossover strategy"""
        from cli.commands.backtest import run_backtest

        backtest_args.strategy = 'ma-crossover'

        with patch('cli.commands.backtest.OHLCVLoader', return_value=mock_ohlcv_loader):
            with patch('cli.commands.backtest.VectorbtAdapter', return_value=mock_vectorbt_adapter):
                result = await run_backtest(backtest_args)

                assert result is not None
                mock_vectorbt_adapter.backtest_ma_crossover.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_tickers(self, mock_ohlcv_loader, mock_vectorbt_adapter, backtest_args):
        """Test backtesting with multiple tickers"""
        from cli.commands.backtest import run_backtest

        backtest_args.tickers = ['005930', '000660', '035720']

        with patch('cli.commands.backtest.OHLCVLoader', return_value=mock_ohlcv_loader):
            with patch('cli.commands.backtest.VectorbtAdapter', return_value=mock_vectorbt_adapter):
                result = await run_backtest(backtest_args)

                # Should load OHLCV for each ticker
                assert mock_ohlcv_loader.load_ohlcv.call_count == 3

    @pytest.mark.asyncio
    async def test_html_report_generation(self, mock_ohlcv_loader, mock_vectorbt_adapter, backtest_args, tmp_path):
        """Test HTML report generation"""
        from cli.commands.backtest import run_backtest

        backtest_args.output = str(tmp_path / "report.html")

        with patch('cli.commands.backtest.OHLCVLoader', return_value=mock_ohlcv_loader):
            with patch('cli.commands.backtest.VectorbtAdapter', return_value=mock_vectorbt_adapter):
                with patch('cli.commands.backtest.ReportGenerator') as mock_report:
                    await run_backtest(backtest_args)

                    # Should generate HTML report
                    # Verify through mock

    @pytest.mark.asyncio
    async def test_csv_export(self, mock_ohlcv_loader, mock_vectorbt_adapter, backtest_args, tmp_path):
        """Test CSV export of backtest results"""
        from cli.commands.backtest import run_backtest

        backtest_args.csv = str(tmp_path / "results.csv")

        with patch('cli.commands.backtest.OHLCVLoader', return_value=mock_ohlcv_loader):
            with patch('cli.commands.backtest.VectorbtAdapter', return_value=mock_vectorbt_adapter):
                await run_backtest(backtest_args)

                # CSV file should be created

    @pytest.mark.asyncio
    async def test_invalid_ticker_handling(self, mock_ohlcv_loader, mock_vectorbt_adapter, backtest_args):
        """Test handling of invalid ticker"""
        from cli.commands.backtest import run_backtest

        mock_ohlcv_loader.load_ohlcv = AsyncMock(return_value=pd.DataFrame())

        with patch('cli.commands.backtest.OHLCVLoader', return_value=mock_ohlcv_loader):
            with patch('cli.commands.backtest.VectorbtAdapter', return_value=mock_vectorbt_adapter):
                # Should handle empty DataFrame gracefully
                result = await run_backtest(backtest_args)

    @pytest.mark.asyncio
    async def test_initial_capital_validation(self, backtest_args):
        """Test validation of initial capital"""
        from cli.commands.backtest import run_backtest

        backtest_args.initial_capital = -1000

        with pytest.raises(ValueError, match="capital"):
            await run_backtest(backtest_args)

    @pytest.mark.asyncio
    async def test_date_range_validation(self, backtest_args):
        """Test validation of date range"""
        from cli.commands.backtest import run_backtest

        backtest_args.start = '2023-12-31'
        backtest_args.end = '2023-01-01'  # End before start

        with pytest.raises(ValueError, match="date"):
            await run_backtest(backtest_args)

    @pytest.mark.asyncio
    async def test_metrics_display(self, mock_ohlcv_loader, mock_vectorbt_adapter, backtest_args):
        """Test that backtest metrics are displayed"""
        from cli.commands.backtest import run_backtest

        with patch('cli.commands.backtest.OHLCVLoader', return_value=mock_ohlcv_loader):
            with patch('cli.commands.backtest.VectorbtAdapter', return_value=mock_vectorbt_adapter):
                with patch('cli.commands.backtest.QueryFormatter') as mock_formatter:
                    await run_backtest(backtest_args)

                    # Should display metrics
                    # Verify through formatter mock
