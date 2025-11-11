# tests/mcp_server/test_optimization_adapter.py
"""
Unit tests for OptimizationAdapter

Tests the MCP adapter for walk-forward optimization operations, validating
parameter grid handling, caching, result formatting, and error handling.

Usage:
    pytest tests/mcp_server/test_optimization_adapter.py -v
"""

import pytest
from datetime import date
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from dataclasses import dataclass

from mcp_server.adapters.optimization_adapter import OptimizationAdapter
from mcp_server.config import Config
from mcp_server.utils.errors import (
    ValidationError,
    DataNotFoundError,
    DatabaseError,
    SpockMCPError,
)


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
def adapter(mock_config):
    """Create OptimizationAdapter with mocked dependencies"""
    with patch('mcp_server.adapters.optimization_adapter.PostgresDatabaseManager'):
        with patch('mcp_server.adapters.optimization_adapter.PostgresDataProvider'):
            adapter = OptimizationAdapter(mock_config)
            return adapter


@pytest.fixture
def mock_walk_forward_result():
    """Mock WalkForwardResult"""
    from dataclasses import dataclass, field
    from typing import Dict, List, Any

    @dataclass
    class MockWindow:
        window_id: int
        train_start: date
        train_end: date
        test_start: date
        test_end: date

    @dataclass
    class MockResult:
        best_params: Dict[str, Any]
        all_results: List[Dict]
        windows: List[MockWindow]
        in_sample_performance: Dict[str, float]
        out_of_sample_performance: Dict[str, float]
        degradation_pct: float
        robustness_score: float
        overfitting_detected: bool

    return MockResult(
        best_params={"rsi_period": 14, "oversold": 30, "overbought": 70},
        all_results=[
            {
                "window_id": 0,
                "best_params": {"rsi_period": 14},
                "train_score": 1.85,
                "test_score": 1.65,
                "degradation": 0.108
            }
        ],
        windows=[
            MockWindow(
                window_id=0,
                train_start=date(2022, 1, 1),
                train_end=date(2023, 1, 1),
                test_start=date(2023, 1, 2),
                test_end=date(2023, 4, 2)
            )
        ],
        in_sample_performance={"mean": 1.85, "std": 0.15, "min": 1.65, "max": 2.05},
        out_of_sample_performance={"mean": 1.65, "std": 0.22, "min": 1.42, "max": 1.88},
        degradation_pct=0.108,
        robustness_score=0.78,
        overfitting_detected=False
    )


# ============================================================================
# Test: Initialization
# ============================================================================

class TestOptimizationAdapterInitialization:
    """Test suite for adapter initialization"""

    def test_init_with_config(self, mock_config):
        """Test initialization with provided config"""
        with patch('mcp_server.adapters.optimization_adapter.PostgresDatabaseManager'):
            with patch('mcp_server.adapters.optimization_adapter.PostgresDataProvider'):
                adapter = OptimizationAdapter(mock_config)
                assert adapter.config == mock_config
                assert adapter._result_cache == {}

    def test_init_without_config(self):
        """Test initialization with default config"""
        with patch('mcp_server.adapters.optimization_adapter.Config.from_env') as mock_from_env:
            with patch('mcp_server.adapters.optimization_adapter.PostgresDatabaseManager'):
                with patch('mcp_server.adapters.optimization_adapter.PostgresDataProvider'):
                    mock_from_env.return_value = Mock(spec=Config)
                    adapter = OptimizationAdapter()
                    assert adapter.config is not None
                    mock_from_env.assert_called_once()


# ============================================================================
# Test: Input Validation
# ============================================================================

class TestOptimizationAdapterValidation:
    """Test suite for input validation"""

    @pytest.mark.asyncio
    async def test_invalid_metric(self, adapter):
        """Test validation of invalid metric"""
        with pytest.raises(ValidationError) as exc_info:
            await adapter.optimize_strategy(
                strategy_type="momentum",
                tickers=["005930"],
                start_date="2022-01-01",
                end_date="2024-12-31",
                region="KR",
                metric="invalid_metric"
            )

        error_dict = exc_info.value.to_dict()
        assert error_dict["error_code"] == "VALIDATION_ERROR"
        assert "invalid_metric" in str(error_dict)

    @pytest.mark.asyncio
    async def test_invalid_param_grid_format(self, adapter):
        """Test validation of invalid param_grid format"""
        with pytest.raises(ValidationError) as exc_info:
            await adapter.optimize_strategy(
                strategy_type="momentum",
                tickers=["005930"],
                start_date="2022-01-01",
                end_date="2024-12-31",
                region="KR",
                param_grid={"rsi_period": 14}  # Should be list, not scalar
            )

        error_dict = exc_info.value.to_dict()
        assert "param_grid" in error_dict["message"].lower()


# ============================================================================
# Test: Successful Optimization
# ============================================================================

class TestOptimizationAdapterExecution:
    """Test suite for optimization execution"""

    @pytest.mark.asyncio
    async def test_successful_optimization(self, adapter, mock_walk_forward_result):
        """Test successful walk-forward optimization"""
        with patch('mcp_server.adapters.optimization_adapter.WalkForwardOptimizer') as mock_optimizer_cls:
            mock_optimizer = mock_optimizer_cls.return_value
            mock_optimizer.optimize = Mock(return_value=mock_walk_forward_result)

            result = await adapter.optimize_strategy(
                strategy_type="momentum",
                tickers=["005930"],
                start_date="2022-01-01",
                end_date="2024-12-31",
                region="KR",
                param_grid={"rsi_period": [10, 14, 20]},
                train_period_days=252,
                test_period_days=63,
                metric="sharpe_ratio"
            )

            assert result["success"] is True
            assert result["strategy_type"] == "momentum"
            assert result["optimization"]["best_params"]["rsi_period"] == 14
            assert result["validation"]["robustness_score"] == 0.78
            assert result["validation"]["overfitting_detected"] is False
            assert "GOOD" in result["validation"]["recommendation"]

    @pytest.mark.asyncio
    async def test_optimization_with_default_param_grid(self, adapter, mock_walk_forward_result):
        """Test optimization uses default param_grid when none provided"""
        with patch('mcp_server.adapters.optimization_adapter.WalkForwardOptimizer') as mock_optimizer_cls:
            mock_optimizer = mock_optimizer_cls.return_value
            mock_optimizer.optimize = Mock(return_value=mock_walk_forward_result)

            result = await adapter.optimize_strategy(
                strategy_type="momentum",
                tickers=["005930"],
                start_date="2022-01-01",
                end_date="2024-12-31",
                region="KR"
            )

            assert result["success"] is True
            # Optimizer should have been called with default grid
            mock_optimizer.optimize.assert_called_once()


# ============================================================================
# Test: Caching Behavior
# ============================================================================

class TestOptimizationAdapterCaching:
    """Test suite for result caching"""

    @pytest.mark.asyncio
    async def test_result_caching(self, adapter, mock_walk_forward_result):
        """Test that optimization results are cached"""
        with patch('mcp_server.adapters.optimization_adapter.WalkForwardOptimizer') as mock_optimizer_cls:
            mock_optimizer = mock_optimizer_cls.return_value
            mock_optimizer.optimize = Mock(return_value=mock_walk_forward_result)

            # First call
            result1 = await adapter.optimize_strategy(
                strategy_type="momentum",
                tickers=["005930"],
                start_date="2022-01-01",
                end_date="2024-12-31",
                region="KR",
                param_grid={"rsi_period": [10, 14, 20]}
            )

            # Second call with same parameters
            result2 = await adapter.optimize_strategy(
                strategy_type="momentum",
                tickers=["005930"],
                start_date="2022-01-01",
                end_date="2024-12-31",
                region="KR",
                param_grid={"rsi_period": [10, 14, 20]}
            )

            assert result1 == result2
            # Optimizer should only be called once
            assert mock_optimizer.optimize.call_count == 1


# ============================================================================
# Test: Error Handling
# ============================================================================

class TestOptimizationAdapterErrorHandling:
    """Test suite for error handling"""

    @pytest.mark.asyncio
    async def test_database_error_propagation(self, adapter):
        """Test DatabaseError is propagated correctly"""
        with patch('mcp_server.adapters.optimization_adapter.WalkForwardOptimizer') as mock_optimizer_cls:
            mock_optimizer_cls.side_effect = DatabaseError(
                "Database connection failed",
                {"host": "localhost"}
            )

            with pytest.raises(DatabaseError):
                await adapter.optimize_strategy(
                    strategy_type="momentum",
                    tickers=["005930"],
                    start_date="2022-01-01",
                    end_date="2024-12-31",
                    region="KR"
                )

    @pytest.mark.asyncio
    async def test_generic_exception_handling(self, adapter):
        """Test generic exceptions are wrapped in SpockMCPError"""
        with patch('mcp_server.adapters.optimization_adapter.WalkForwardOptimizer') as mock_optimizer_cls:
            mock_optimizer_cls.side_effect = Exception("Unexpected error")

            with pytest.raises(SpockMCPError) as exc_info:
                await adapter.optimize_strategy(
                    strategy_type="momentum",
                    tickers=["005930"],
                    start_date="2022-01-01",
                    end_date="2024-12-31",
                    region="KR"
                )

            error_dict = exc_info.value.to_dict()
            assert "Optimization execution failed" in error_dict["message"]


# ============================================================================
# Test: Helper Methods
# ============================================================================

class TestOptimizationAdapterHelpers:
    """Test suite for helper methods"""

    def test_get_default_param_grid_momentum(self, adapter):
        """Test default param grid for momentum strategy"""
        grid = adapter._get_default_param_grid("momentum")
        assert "rsi_period" in grid
        assert isinstance(grid["rsi_period"], list)
        assert len(grid["rsi_period"]) > 0

    def test_get_default_param_grid_value(self, adapter):
        """Test default param grid for value strategy"""
        grid = adapter._get_default_param_grid("value")
        assert "pe_threshold" in grid
        assert isinstance(grid["pe_threshold"], list)

    def test_get_recommendation_good(self, adapter, mock_walk_forward_result):
        """Test recommendation for good robustness"""
        mock_walk_forward_result.robustness_score = 0.75
        mock_walk_forward_result.overfitting_detected = False

        recommendation = adapter._get_recommendation(mock_walk_forward_result)
        assert "GOOD" in recommendation
        assert "recommended" in recommendation.lower()

    def test_get_recommendation_overfitting(self, adapter, mock_walk_forward_result):
        """Test recommendation when overfitting detected"""
        mock_walk_forward_result.overfitting_detected = True

        recommendation = adapter._get_recommendation(mock_walk_forward_result)
        assert "CAUTION" in recommendation
        assert "overfitting" in recommendation.lower()

    def test_cache_key_generation(self, adapter):
        """Test cache key generation is consistent"""
        key1 = adapter._get_cache_key(
            "momentum", ["005930"], "2022-01-01", "2024-12-31", "KR",
            {"rsi_period": [10, 14, 20]}, 252, 63, "sharpe_ratio", False
        )

        key2 = adapter._get_cache_key(
            "momentum", ["005930"], "2022-01-01", "2024-12-31", "KR",
            {"rsi_period": [10, 14, 20]}, 252, 63, "sharpe_ratio", False
        )

        assert key1 == key2
        assert len(key1) == 32  # MD5 hash length
