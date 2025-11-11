# tests/mcp_server/test_backtest_adapter.py
"""
Unit tests for BacktestAdapter

Tests the MCP adapter for backtest operations, validating input handling,
caching, result formatting, and error handling.

Usage:
    pytest tests/mcp_server/test_backtest_adapter.py -v
"""

import pytest
from datetime import date
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from dataclasses import dataclass

from mcp_server.adapters.backtest_adapter import BacktestAdapter
from mcp_server.config import Config
from mcp_server.utils.errors import (
    ValidationError,
    DataNotFoundError,
    DatabaseError,
    SpockMCPError,
)
from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.backtest_runner import BacktestRunner


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_config():
    """Mock MCP configuration"""
    config = Mock(spec=Config)
    config.postgres_host = "localhost"
    config.postgres_port = 5432
    config.postgres_db = "test_db"
    config.postgres_user = "test_user"
    config.postgres_password = "test_pass"
    return config


@pytest.fixture
def mock_db_manager():
    """Mock PostgresDatabaseManager"""
    with patch('mcp_server.adapters.backtest_adapter.PostgresDatabaseManager') as mock:
        yield mock.return_value


@pytest.fixture
def mock_data_provider():
    """Mock PostgresDataProvider"""
    with patch('mcp_server.adapters.backtest_adapter.PostgresDataProvider') as mock:
        yield mock.return_value


@pytest.fixture
def mock_backtest_runner():
    """Mock BacktestRunner"""
    with patch('mcp_server.adapters.backtest_adapter.BacktestRunner') as mock:
        runner = mock.return_value
        runner.run = Mock()
        yield runner


@pytest.fixture
def adapter(mock_config, mock_db_manager, mock_data_provider):
    """Create BacktestAdapter with mocked dependencies"""
    with patch('mcp_server.adapters.backtest_adapter.PostgresDatabaseManager', return_value=mock_db_manager):
        with patch('mcp_server.adapters.backtest_adapter.PostgresDataProvider', return_value=mock_data_provider):
            adapter = BacktestAdapter(mock_config)
            return adapter


# ============================================================================
# Test: Initialization
# ============================================================================

class TestBacktestAdapterInitialization:
    """Test suite for adapter initialization"""

    def test_init_with_config(self, mock_config):
        """Test initialization with provided config"""
        with patch('mcp_server.adapters.backtest_adapter.PostgresDatabaseManager'):
            with patch('mcp_server.adapters.backtest_adapter.PostgresDataProvider'):
                adapter = BacktestAdapter(mock_config)
                assert adapter.config == mock_config
                assert adapter._runner_cache == {}

    def test_init_without_config(self):
        """Test initialization with default config"""
        with patch('mcp_server.adapters.backtest_adapter.Config.from_env') as mock_from_env:
            with patch('mcp_server.adapters.backtest_adapter.PostgresDatabaseManager'):
                with patch('mcp_server.adapters.backtest_adapter.PostgresDataProvider'):
                    mock_from_env.return_value = Mock(spec=Config)
                    adapter = BacktestAdapter()
                    assert adapter.config is not None
                    mock_from_env.assert_called_once()


# ============================================================================
# Test: Input Validation
# ============================================================================

class TestBacktestAdapterValidation:
    """Test suite for input validation"""

    @pytest.mark.asyncio
    async def test_invalid_date_format(self, adapter):
        """Test validation of invalid date format"""
        with pytest.raises(ValueError):
            await adapter.run_backtest(
                strategy_type="momentum",
                tickers=["005930"],
                start_date="2024/01/01",  # Invalid format
                end_date="2024-12-31",
                region="KR"
            )

    @pytest.mark.asyncio
    async def test_invalid_engine(self, adapter):
        """Test validation of invalid engine type"""
        with pytest.raises(ValidationError) as exc_info:
            await adapter.run_backtest(
                strategy_type="momentum",
                tickers=["005930"],
                start_date="2024-01-01",
                end_date="2024-12-31",
                region="KR",
                engine="invalid_engine"
            )

        error_dict = exc_info.value.to_dict()
        assert error_dict["error_code"] == "VALIDATION_ERROR"
        assert "invalid_engine" in str(error_dict)

    @pytest.mark.asyncio
    async def test_vectorbt_not_available(self, adapter):
        """Test error when vectorbt engine requested but not available"""
        with patch('mcp_server.adapters.backtest_adapter.VECTORBT_AVAILABLE', False):
            with pytest.raises(ValidationError) as exc_info:
                await adapter.run_backtest(
                    strategy_type="momentum",
                    tickers=["005930"],
                    start_date="2024-01-01",
                    end_date="2024-12-31",
                    region="KR",
                    engine="vectorbt"
                )

            error_dict = exc_info.value.to_dict()
            assert "vectorbt engine not available" in error_dict["message"]


# ============================================================================
# Test: Successful Backtest Execution
# ============================================================================

class TestBacktestAdapterExecution:
    """Test suite for backtest execution"""

    @pytest.mark.asyncio
    async def test_successful_vectorbt_backtest(self, adapter, mock_backtest_runner):
        """Test successful backtest with vectorbt engine"""
        # Mock result
        mock_result = Mock()
        mock_result.total_return = 0.45
        mock_result.annual_return = 0.35
        mock_result.sharpe_ratio = 1.65
        mock_result.sortino_ratio = 2.10
        mock_result.calmar_ratio = 1.85
        mock_result.max_drawdown = -0.12
        mock_result.max_drawdown_duration = 45
        mock_result.total_trades = 125
        mock_result.win_rate = 0.583
        mock_result.avg_win = 0.048
        mock_result.avg_loss = -0.032
        mock_result.profit_factor = 1.85
        mock_result.execution_time = 0.85
        mock_result.start_date = date(2024, 1, 1)
        mock_result.end_date = date(2024, 12, 31)
        mock_result.initial_capital = 100_000_000

        with patch.object(adapter, '_runner_cache', {}):
            with patch('mcp_server.adapters.backtest_adapter.BacktestRunner') as mock_runner_cls:
                mock_runner_cls.return_value.run.return_value = mock_result

                result = await adapter.run_backtest(
                    strategy_type="momentum",
                    tickers=["005930"],
                    start_date="2024-01-01",
                    end_date="2024-12-31",
                    region="KR",
                    engine="vectorbt"
                )

                assert result["success"] is True
                assert result["engine"] == "vectorbt"
                assert result["performance"]["total_return"] == 0.45
                assert result["performance"]["sharpe_ratio"] == 1.65
                assert result["trades"]["total_trades"] == 125
                assert result["trades"]["win_rate"] == 0.583

    @pytest.mark.asyncio
    async def test_successful_custom_backtest(self, adapter):
        """Test successful backtest with custom engine"""
        # Mock result with metrics dataclass
        mock_metrics = Mock()
        mock_metrics.total_return = 0.38
        mock_metrics.annualized_return = 0.30
        mock_metrics.cagr = 0.29
        mock_metrics.sharpe_ratio = 1.52
        mock_metrics.sortino_ratio = 1.95
        mock_metrics.calmar_ratio = 1.72
        mock_metrics.max_drawdown = -0.14
        mock_metrics.max_drawdown_duration_days = 52
        mock_metrics.total_trades = 105
        mock_metrics.win_rate = 0.565
        mock_metrics.profit_factor = 1.75
        mock_metrics.avg_win_pct = 0.045
        mock_metrics.avg_loss_pct = -0.028
        mock_metrics.avg_win_loss_ratio = 1.61
        mock_metrics.avg_holding_period_days = 18.5

        mock_result = Mock()
        mock_result.metrics = mock_metrics
        mock_result.execution_time_seconds = 2.5
        mock_result.final_portfolio_value = 138_000_000
        mock_result.total_profit = 38_000_000
        mock_result.config = Mock()
        mock_result.config.start_date = date(2024, 1, 1)
        mock_result.config.end_date = date(2024, 12, 31)
        mock_result.config.initial_capital = 100_000_000

        with patch.object(adapter, '_runner_cache', {}):
            with patch('mcp_server.adapters.backtest_adapter.BacktestRunner') as mock_runner_cls:
                mock_runner_cls.return_value.run.return_value = mock_result

                result = await adapter.run_backtest(
                    strategy_type="value",
                    tickers=["005930", "000660"],
                    start_date="2024-01-01",
                    end_date="2024-12-31",
                    region="KR",
                    engine="custom"
                )

                assert result["success"] is True
                assert result["engine"] == "custom"
                assert result["performance"]["total_return"] == 0.38
                assert result["performance"]["sharpe_ratio"] == 1.52
                assert result["trades"]["total_trades"] == 105
                assert result["final_value"] == 138_000_000
                assert result["total_profit"] == 38_000_000


# ============================================================================
# Test: Caching Behavior
# ============================================================================

class TestBacktestAdapterCaching:
    """Test suite for runner caching"""

    @pytest.mark.asyncio
    async def test_runner_caching(self, adapter):
        """Test that BacktestRunner is cached by config"""
        mock_result = Mock()
        mock_result.total_return = 0.45
        mock_result.annual_return = 0.35
        mock_result.sharpe_ratio = 1.65
        mock_result.sortino_ratio = 2.10
        mock_result.calmar_ratio = 1.85
        mock_result.max_drawdown = -0.12
        mock_result.max_drawdown_duration = 45
        mock_result.total_trades = 125
        mock_result.win_rate = 0.583
        mock_result.avg_win = 0.048
        mock_result.avg_loss = -0.032
        mock_result.profit_factor = 1.85
        mock_result.execution_time = 0.85
        mock_result.start_date = date(2024, 1, 1)
        mock_result.end_date = date(2024, 12, 31)
        mock_result.initial_capital = 100_000_000

        with patch('mcp_server.adapters.backtest_adapter.BacktestRunner') as mock_runner_cls:
            mock_runner_cls.return_value.run.return_value = mock_result

            # First call
            await adapter.run_backtest(
                strategy_type="momentum",
                tickers=["005930"],
                start_date="2024-01-01",
                end_date="2024-12-31",
                region="KR"
            )

            # Second call with same config
            await adapter.run_backtest(
                strategy_type="momentum",
                tickers=["005930"],
                start_date="2024-01-01",
                end_date="2024-12-31",
                region="KR"
            )

            # Runner should only be created once
            assert mock_runner_cls.call_count == 1


# ============================================================================
# Test: Error Handling
# ============================================================================

class TestBacktestAdapterErrorHandling:
    """Test suite for error handling"""

    @pytest.mark.asyncio
    async def test_database_error_propagation(self, adapter):
        """Test DatabaseError is propagated correctly"""
        with patch('mcp_server.adapters.backtest_adapter.BacktestRunner') as mock_runner_cls:
            mock_runner_cls.side_effect = DatabaseError(
                "Database connection failed",
                {"host": "localhost"}
            )

            with pytest.raises(DatabaseError):
                await adapter.run_backtest(
                    strategy_type="momentum",
                    tickers=["005930"],
                    start_date="2024-01-01",
                    end_date="2024-12-31",
                    region="KR"
                )

    @pytest.mark.asyncio
    async def test_generic_exception_handling(self, adapter):
        """Test generic exceptions are wrapped in SpockMCPError"""
        with patch('mcp_server.adapters.backtest_adapter.BacktestRunner') as mock_runner_cls:
            mock_runner_cls.side_effect = Exception("Unexpected error")

            with pytest.raises(SpockMCPError) as exc_info:
                await adapter.run_backtest(
                    strategy_type="momentum",
                    tickers=["005930"],
                    start_date="2024-01-01",
                    end_date="2024-12-31",
                    region="KR"
                )

            error_dict = exc_info.value.to_dict()
            assert "Backtest execution failed" in error_dict["message"]


# ============================================================================
# Test: Signal Generator Placeholder
# ============================================================================

class TestBacktestAdapterSignalGenerator:
    """Test suite for signal generator factory"""

    def test_placeholder_signal_generator(self, adapter):
        """Test placeholder signal generator returns 0 (hold)"""
        generator = adapter._create_signal_generator("momentum", {})
        signal = generator({})
        assert signal == 0  # Placeholder always returns hold

    def test_signal_generator_logs_warning(self, adapter, caplog):
        """Test placeholder signal generator logs warning"""
        import logging
        caplog.set_level(logging.WARNING)

        adapter._create_signal_generator("momentum", {})

        assert any("placeholder" in record.message.lower() for record in caplog.records)


# ============================================================================
# Test: Result Formatting
# ============================================================================

class TestBacktestAdapterFormatting:
    """Test suite for result formatting"""

    def test_format_vectorbt_result(self, adapter):
        """Test formatting of vectorbt result"""
        mock_result = Mock()
        mock_result.total_return = 0.45
        mock_result.annual_return = 0.35
        mock_result.sharpe_ratio = 1.65
        mock_result.sortino_ratio = 2.10
        mock_result.calmar_ratio = 1.85
        mock_result.max_drawdown = -0.12
        mock_result.max_drawdown_duration = 45
        mock_result.total_trades = 125
        mock_result.win_rate = 0.583
        mock_result.avg_win = 0.048
        mock_result.avg_loss = -0.032
        mock_result.profit_factor = 1.85
        mock_result.execution_time = 0.85
        mock_result.start_date = date(2024, 1, 1)
        mock_result.end_date = date(2024, 12, 31)
        mock_result.initial_capital = 100_000_000

        formatted = adapter._format_result(mock_result, "vectorbt")

        assert formatted["success"] is True
        assert formatted["engine"] == "vectorbt"
        assert "performance" in formatted
        assert "trades" in formatted
        assert "execution" in formatted
        assert formatted["performance"]["total_return"] == 0.45
        assert formatted["execution"]["start_date"] == "2024-01-01"

    def test_format_custom_result(self, adapter):
        """Test formatting of custom engine result"""
        mock_metrics = Mock()
        mock_metrics.total_return = 0.38
        mock_metrics.annualized_return = 0.30
        mock_metrics.cagr = 0.29
        mock_metrics.sharpe_ratio = 1.52
        mock_metrics.sortino_ratio = 1.95
        mock_metrics.calmar_ratio = 1.72
        mock_metrics.max_drawdown = -0.14
        mock_metrics.max_drawdown_duration_days = 52
        mock_metrics.total_trades = 105
        mock_metrics.win_rate = 0.565
        mock_metrics.profit_factor = 1.75
        mock_metrics.avg_win_pct = 0.045
        mock_metrics.avg_loss_pct = -0.028
        mock_metrics.avg_win_loss_ratio = 1.61
        mock_metrics.avg_holding_period_days = 18.5

        mock_result = Mock()
        mock_result.metrics = mock_metrics
        mock_result.execution_time_seconds = 2.5
        mock_result.final_portfolio_value = 138_000_000
        mock_result.total_profit = 38_000_000
        mock_result.config = Mock()
        mock_result.config.start_date = date(2024, 1, 1)
        mock_result.config.end_date = date(2024, 12, 31)
        mock_result.config.initial_capital = 100_000_000

        formatted = adapter._format_result(mock_result, "custom")

        assert formatted["success"] is True
        assert formatted["engine"] == "custom"
        assert "performance" in formatted
        assert "trades" in formatted
        assert "execution" in formatted
        assert "final_value" in formatted
        assert "total_profit" in formatted
        assert formatted["performance"]["total_return"] == 0.38
        assert formatted["final_value"] == 138_000_000
