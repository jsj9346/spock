"""
Integration Tests for BacktestAdapter

Tests the integration between BacktestAdapter, SignalGeneratorFactory,
and BacktestRunner with signal generators.

Author: Spock MCP Server
Date: 2025-10-31
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import date

from mcp_server.adapters.backtest_adapter import BacktestAdapter
from mcp_server.strategies import SignalGeneratorFactory
from mcp_server.utils.errors import ValidationError, SpockMCPError


class TestBacktestAdapterIntegration:
    """Integration tests for BacktestAdapter with signal generators."""

    @pytest.fixture
    def mock_data_provider(self):
        """Create mock data provider."""
        provider = Mock()
        provider.get_ohlcv = AsyncMock(return_value=Mock())
        return provider

    @pytest.fixture
    def mock_runner(self):
        """Create mock backtest runner."""
        runner = Mock()
        runner.run = Mock(return_value={
            'config': Mock(start_date=date(2024, 1, 1), end_date=date(2024, 12, 31), initial_capital=100_000_000),
            'metrics': Mock(
                total_return=0.25,
                sharpe_ratio=1.5,
                max_drawdown=0.10,
                total_trades=50,
                win_rate=0.60
            ),
            'trades': [Mock()] * 50,
            'equity_curve': [],
            'pattern_metrics': {},
            'region_metrics': {},
            'execution_time_seconds': 2.5,
            'final_portfolio_value': 125_000_000,
            'total_profit': 25_000_000,
            'execution_time': 2.5
        })
        return runner

    @pytest.mark.asyncio
    async def test_backtest_adapter_uses_signal_generator_factory(self, mock_runner):
        """Test that BacktestAdapter uses SignalGeneratorFactory."""
        adapter = BacktestAdapter()

        # Patch BacktestRunner initialization
        with patch('mcp_server.adapters.backtest_adapter.BacktestRunner', return_value=mock_runner):
            # Patch SignalGeneratorFactory to verify it's called
            with patch.object(SignalGeneratorFactory, 'create') as mock_create:
                mock_create.return_value = Mock()

                try:
                    await adapter.run_backtest(
                        strategy_type="momentum",
                        tickers=["005930"],
                        start_date="2024-01-01",
                        end_date="2024-12-31",
                        region="KR",
                        engine="custom"
                    )
                except Exception:
                    pass  # Ignore other errors, we only care about factory call

                # Verify SignalGeneratorFactory was called
                mock_create.assert_called_once_with(
                    strategy_type="momentum",
                    parameters={}
                )

    @pytest.mark.asyncio
    async def test_backtest_adapter_passes_parameters_to_factory(self, mock_runner):
        """Test that parameters are passed to signal generator factory."""
        adapter = BacktestAdapter()

        custom_params = {
            "rsi_period": 10,
            "ma_fast": 15,
            "ma_slow": 30
        }

        with patch('mcp_server.adapters.backtest_adapter.BacktestRunner', return_value=mock_runner):
            with patch.object(SignalGeneratorFactory, 'create') as mock_create:
                mock_create.return_value = Mock()

                try:
                    await adapter.run_backtest(
                        strategy_type="momentum",
                        tickers=["005930"],
                        start_date="2024-01-01",
                        end_date="2024-12-31",
                        region="KR",
                        engine="custom",
                        parameters=custom_params
                    )
                except Exception:
                    pass

                # Verify parameters were passed
                mock_create.assert_called_once_with(
                    strategy_type="momentum",
                    parameters=custom_params
                )

    @pytest.mark.asyncio
    async def test_backtest_adapter_error_context_includes_traceback(self):
        """Test that error handling includes full traceback."""
        adapter = BacktestAdapter()

        # Force an error by using invalid strategy
        with pytest.raises(SpockMCPError) as exc_info:
            await adapter.run_backtest(
                strategy_type="invalid_strategy",
                tickers=["005930"],
                start_date="2024-01-01",
                end_date="2024-12-31",
                region="KR",
                engine="vectorbt"
            )

        # Verify error details includes full context
        error = exc_info.value
        assert "exception_type" in error.details
        assert "exception_message" in error.details
        assert "traceback" in error.details
        assert error.details["strategy"] == "invalid_strategy"
        assert error.details["engine"] == "vectorbt"

    @pytest.mark.asyncio
    async def test_backtest_adapter_validates_engine_availability(self):
        """Test that adapter validates vectorbt availability."""
        adapter = BacktestAdapter()

        # Patch VECTORBT_AVAILABLE to False
        with patch('mcp_server.adapters.backtest_adapter.VECTORBT_AVAILABLE', False):
            with pytest.raises(ValidationError) as exc_info:
                await adapter.run_backtest(
                    strategy_type="momentum",
                    tickers=["005930"],
                    start_date="2024-01-01",
                    end_date="2024-12-31",
                    region="KR",
                    engine="vectorbt"  # Should fail
                )

            assert "vectorbt engine not available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_backtest_adapter_all_strategies_work(self, mock_runner):
        """Test that all registered strategies can be used."""
        adapter = BacktestAdapter()

        strategies = ["momentum", "value", "momentum_value"]

        for strategy_type in strategies:
            with patch('mcp_server.adapters.backtest_adapter.BacktestRunner', return_value=mock_runner):
                try:
                    result = await adapter.run_backtest(
                        strategy_type=strategy_type,
                        tickers=["005930"],
                        start_date="2024-01-01",
                        end_date="2024-12-31",
                        region="KR",
                        engine="custom"
                    )

                    # Verify result structure
                    assert result["success"] == True
                    assert result["engine"] == "custom"
                    assert "performance" in result
                    assert "trades" in result
                except Exception as e:
                    pytest.fail(f"Strategy {strategy_type} failed: {e}")


class TestBacktestAdapterErrorHandling:
    """Test error handling improvements in BacktestAdapter."""

    @pytest.mark.asyncio
    async def test_error_includes_exception_type(self):
        """Test that errors include exception type."""
        adapter = BacktestAdapter()

        with pytest.raises(SpockMCPError) as exc_info:
            await adapter.run_backtest(
                strategy_type="invalid",
                tickers=["005930"],
                start_date="2024-01-01",
                end_date="2024-12-31",
                region="KR",
                engine="vectorbt"
            )

        # Error message should include exception type
        assert "ValueError" in exc_info.value.message or "Unknown strategy type" in exc_info.value.message
        assert "exception_type" in exc_info.value.details

    @pytest.mark.asyncio
    async def test_error_preserves_original_message(self):
        """Test that original exception message is preserved."""
        adapter = BacktestAdapter()

        with pytest.raises(SpockMCPError) as exc_info:
            await adapter.run_backtest(
                strategy_type="invalid_strategy",
                tickers=["005930"],
                start_date="2024-01-01",
                end_date="2024-12-31",
                region="KR",
                engine="vectorbt"
            )

        # Original error message should be in details
        assert exc_info.value.details["exception_message"] != str(exc_info.value.details)
        assert "strategy" in exc_info.value.details


class TestSignalGeneratorFactoryIntegration:
    """Test that signal generator factory integrates correctly."""

    def test_all_registered_strategies_are_valid(self):
        """Verify all registered strategies can be created."""
        strategies = SignalGeneratorFactory.list_strategies()

        for strategy in strategies:
            # Should not raise
            gen = SignalGeneratorFactory.create(strategy, {})
            assert gen is not None
            assert callable(gen)

    def test_factory_creates_vectorbt_compatible_generators(self):
        """Test that factory creates generators compatible with vectorbt."""
        import pandas as pd

        prices = pd.Series(
            [100, 101, 102, 103, 104],
            index=pd.date_range("2024-01-01", periods=5)
        )

        for strategy in SignalGeneratorFactory.list_strategies():
            gen = SignalGeneratorFactory.create(strategy, {})

            # Should work with vectorbt-style call
            entries, exits = gen(prices)

            # Verify output format
            assert isinstance(entries, pd.Series)
            assert isinstance(exits, pd.Series)
            assert entries.dtype == bool
            assert exits.dtype == bool
