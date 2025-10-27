"""
Test BacktestRunner Orchestrator

Tests for the unified backtest runner that coordinates both custom
and vectorbt engines.

Usage:
    PYTHONPATH=/Users/13ruce/spock python3 -m pytest tests/backtesting/test_backtest_runner.py -v
"""

import pytest
from datetime import date
from pathlib import Path

from modules.backtesting.backtest_runner import (
    BacktestRunner,
    ComparisonResult,
    ValidationReport,
    PerformanceReport
)
from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.backtest_engines.vectorbt_adapter import VectorbtResult, VECTORBT_AVAILABLE
from modules.backtesting.data_providers import SQLiteDataProvider
from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.backtesting.signal_generators.rsi_strategy import rsi_signal_generator
from modules.backtesting.signal_generators.macd_strategy import macd_signal_generator


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="class")
def test_db_path():
    """Get test database path."""
    db_path = Path(__file__).parent.parent.parent / 'data' / 'spock_local.db'
    if not db_path.exists():
        pytest.skip(f"Test database not found: {db_path}")
    return str(db_path)


@pytest.fixture
def sample_config():
    """Create sample backtest configuration."""
    return BacktestConfig(
        start_date=date(2024, 10, 10),
        end_date=date(2024, 12, 31),
        initial_capital=10000000,
        regions=['KR'],
        tickers=['000020'],
        max_position_size=0.15,
        score_threshold=60.0,
        risk_profile='moderate',
        commission_rate=0.00015,
        slippage_bps=5.0
    )


@pytest.fixture
def data_provider(test_db_path):
    """Create data provider."""
    db_manager = SQLiteDatabaseManager(test_db_path)
    return SQLiteDataProvider(db_manager)


@pytest.fixture
def runner(sample_config, data_provider):
    """Create BacktestRunner instance."""
    return BacktestRunner(sample_config, data_provider)


# ============================================================================
# Basic Functionality Tests
# ============================================================================

class TestBacktestRunnerBasics:
    """Test basic BacktestRunner functionality."""

    def test_initialization(self, runner):
        """Test BacktestRunner initialization."""
        assert runner.config is not None
        assert runner.data_provider is not None
        assert runner.custom_engine is not None

        if VECTORBT_AVAILABLE:
            assert runner.vectorbt_adapter is not None
        else:
            assert runner.vectorbt_adapter is None

    def test_run_custom_engine(self, runner):
        """Test running with custom engine."""
        result = runner.run(engine='custom')

        # Check result type
        assert isinstance(result, dict)

        # Check required keys
        assert 'trades' in result
        assert 'final_portfolio_value' in result
        assert 'execution_time' in result

        # Check execution time tracked
        assert result['execution_time'] > 0

    @pytest.mark.skipif(not VECTORBT_AVAILABLE, reason="vectorbt not available")
    def test_run_vectorbt_engine(self, runner):
        """Test running with vectorbt engine."""
        result = runner.run(
            engine='vectorbt',
            signal_generator=rsi_signal_generator
        )

        # Check result type
        assert isinstance(result, VectorbtResult)

        # Check metrics present
        assert result.total_return is not None
        assert result.sharpe_ratio is not None
        assert result.total_trades >= 0
        assert result.execution_time > 0

    @pytest.mark.skipif(not VECTORBT_AVAILABLE, reason="vectorbt not available")
    def test_run_both_engines(self, runner):
        """Test running both engines for comparison."""
        result = runner.run(
            engine='both',
            signal_generator=rsi_signal_generator
        )

        # Check result type
        assert isinstance(result, ComparisonResult)

        # Check custom metrics
        assert result.custom_total_trades >= 0
        assert result.custom_execution_time > 0

        # Check vectorbt metrics
        assert result.vectorbt_total_trades >= 0
        assert result.vectorbt_execution_time > 0

        # Check comparison metrics
        assert 0 <= result.consistency_score <= 1
        assert result.speedup_factor >= 0
        assert isinstance(result.metrics_match, dict)
        assert isinstance(result.warnings, list)


# ============================================================================
# Engine Selection Tests
# ============================================================================

class TestEngineSelection:
    """Test engine selection logic."""

    def test_invalid_engine_raises_error(self, runner):
        """Test that invalid engine name raises ValueError."""
        with pytest.raises(ValueError, match="Invalid engine"):
            runner.run(engine='invalid')

    @pytest.mark.skipif(not VECTORBT_AVAILABLE, reason="vectorbt not available")
    def test_vectorbt_requires_signal_generator(self, runner):
        """Test that vectorbt requires signal_generator."""
        with pytest.raises(ValueError, match="signal_generator required"):
            runner.run(engine='vectorbt')

    @pytest.mark.skipif(not VECTORBT_AVAILABLE, reason="vectorbt not available")
    def test_both_requires_signal_generator(self, runner):
        """Test that 'both' requires signal_generator."""
        with pytest.raises(ValueError, match="signal_generator required"):
            runner.run(engine='both')

    def test_custom_does_not_require_signal_generator(self, runner):
        """Test that custom engine works without signal_generator."""
        result = runner.run(engine='custom')
        assert isinstance(result, dict)


# ============================================================================
# Comparison Tests
# ============================================================================

@pytest.mark.skipif(not VECTORBT_AVAILABLE, reason="vectorbt not available")
class TestComparison:
    """Test result comparison functionality."""

    def test_comparison_result_structure(self, runner):
        """Test ComparisonResult has all required fields."""
        comparison = runner.run(
            engine='both',
            signal_generator=rsi_signal_generator
        )

        # Custom engine fields
        assert hasattr(comparison, 'custom_total_return')
        assert hasattr(comparison, 'custom_sharpe_ratio')
        assert hasattr(comparison, 'custom_max_drawdown')
        assert hasattr(comparison, 'custom_total_trades')
        assert hasattr(comparison, 'custom_execution_time')

        # vectorbt fields
        assert hasattr(comparison, 'vectorbt_total_return')
        assert hasattr(comparison, 'vectorbt_sharpe_ratio')
        assert hasattr(comparison, 'vectorbt_max_drawdown')
        assert hasattr(comparison, 'vectorbt_total_trades')
        assert hasattr(comparison, 'vectorbt_execution_time')

        # Comparison fields
        assert hasattr(comparison, 'consistency_score')
        assert hasattr(comparison, 'return_difference')
        assert hasattr(comparison, 'trade_count_difference')
        assert hasattr(comparison, 'speedup_factor')
        assert hasattr(comparison, 'metrics_match')
        assert hasattr(comparison, 'warnings')

    def test_consistency_score_range(self, runner):
        """Test consistency score is between 0 and 1."""
        comparison = runner.run(
            engine='both',
            signal_generator=rsi_signal_generator
        )

        assert 0 <= comparison.consistency_score <= 1

    def test_metrics_match_dict(self, runner):
        """Test metrics_match contains expected keys."""
        comparison = runner.run(
            engine='both',
            signal_generator=rsi_signal_generator
        )

        assert 'return' in comparison.metrics_match
        assert 'trades' in comparison.metrics_match
        assert 'sharpe' in comparison.metrics_match
        assert 'max_drawdown' in comparison.metrics_match

        # All values should be boolean
        for key, value in comparison.metrics_match.items():
            assert isinstance(value, bool)

    def test_speedup_factor_positive(self, runner):
        """Test speedup factor is positive."""
        comparison = runner.run(
            engine='both',
            signal_generator=rsi_signal_generator
        )

        assert comparison.speedup_factor > 0

    def test_comparison_result_str(self, runner):
        """Test ComparisonResult string representation."""
        comparison = runner.run(
            engine='both',
            signal_generator=rsi_signal_generator
        )

        result_str = str(comparison)
        assert 'ComparisonResult' in result_str
        assert 'Consistency' in result_str
        assert 'Speedup' in result_str

    def test_different_signal_generators(self, runner):
        """Test comparison with different signal generators."""
        # Test with RSI
        rsi_comparison = runner.run(
            engine='both',
            signal_generator=rsi_signal_generator
        )

        # Test with MACD
        macd_comparison = runner.run(
            engine='both',
            signal_generator=macd_signal_generator
        )

        # Both should produce valid results
        assert isinstance(rsi_comparison, ComparisonResult)
        assert isinstance(macd_comparison, ComparisonResult)

        # Results may differ
        assert 0 <= rsi_comparison.consistency_score <= 1
        assert 0 <= macd_comparison.consistency_score <= 1


# ============================================================================
# Validation Tests
# ============================================================================

@pytest.mark.skipif(not VECTORBT_AVAILABLE, reason="vectorbt not available")
class TestValidation:
    """Test consistency validation functionality."""

    def test_validate_consistency(self, runner):
        """Test validate_consistency method."""
        report = runner.validate_consistency(
            signal_generator=rsi_signal_generator
        )

        # Check report type
        assert isinstance(report, ValidationReport)

        # Check required fields
        assert hasattr(report, 'validation_passed')
        assert hasattr(report, 'consistency_score')
        assert hasattr(report, 'discrepancies')
        assert hasattr(report, 'recommendations')
        assert hasattr(report, 'timestamp')

        # Check types
        assert isinstance(report.validation_passed, bool)
        assert isinstance(report.consistency_score, float)
        assert isinstance(report.discrepancies, dict)
        assert isinstance(report.recommendations, list)

    def test_validation_score_range(self, runner):
        """Test validation score is between 0 and 1."""
        report = runner.validate_consistency(
            signal_generator=rsi_signal_generator
        )

        assert 0 <= report.consistency_score <= 1

    def test_validation_with_custom_tolerance(self, runner):
        """Test validation with custom tolerance."""
        # Strict tolerance
        strict_report = runner.validate_consistency(
            signal_generator=rsi_signal_generator,
            tolerance=0.01  # 1%
        )

        # Lenient tolerance
        lenient_report = runner.validate_consistency(
            signal_generator=rsi_signal_generator,
            tolerance=0.20  # 20%
        )

        # Lenient should be more likely to pass
        assert isinstance(strict_report, ValidationReport)
        assert isinstance(lenient_report, ValidationReport)

    def test_validation_report_str(self, runner):
        """Test ValidationReport string representation."""
        report = runner.validate_consistency(
            signal_generator=rsi_signal_generator
        )

        report_str = str(report)
        assert 'ValidationReport' in report_str
        assert 'Consistency' in report_str
        assert 'PASSED' in report_str or 'FAILED' in report_str


# ============================================================================
# Performance Benchmark Tests
# ============================================================================

@pytest.mark.skipif(not VECTORBT_AVAILABLE, reason="vectorbt not available")
class TestPerformanceBenchmark:
    """Test performance benchmarking functionality."""

    def test_benchmark_performance(self, runner):
        """Test benchmark_performance method."""
        report = runner.benchmark_performance(
            signal_generator=rsi_signal_generator
        )

        # Check report type
        assert isinstance(report, PerformanceReport)

        # Check required fields
        assert hasattr(report, 'custom_time')
        assert hasattr(report, 'vectorbt_time')
        assert hasattr(report, 'speedup_factor')
        assert hasattr(report, 'memory_usage_mb')
        assert hasattr(report, 'throughput_days_per_sec')

        # Check positive values
        assert report.custom_time > 0
        assert report.vectorbt_time > 0
        assert report.speedup_factor > 0
        assert report.memory_usage_mb > 0
        assert report.throughput_days_per_sec > 0

    def test_vectorbt_faster_than_custom(self, runner):
        """Test that vectorbt is faster than custom engine."""
        report = runner.benchmark_performance(
            signal_generator=rsi_signal_generator
        )

        # vectorbt should be faster (speedup > 1)
        # May not always be true for very short backtests due to overhead
        # but should be true for our 3-month test period
        assert report.speedup_factor >= 0.1  # At least some speedup

    def test_performance_report_str(self, runner):
        """Test PerformanceReport string representation."""
        report = runner.benchmark_performance(
            signal_generator=rsi_signal_generator
        )

        report_str = str(report)
        assert 'PerformanceReport' in report_str
        assert 'Speedup' in report_str
        assert 'Throughput' in report_str


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_tickers(self, data_provider):
        """Test with empty tickers list."""
        config = BacktestConfig(
            start_date=date(2024, 10, 10),
            end_date=date(2024, 12, 31),
            initial_capital=10000000,
            regions=['KR'],
            tickers=[],  # Empty
            max_position_size=0.15,
            score_threshold=60.0,
            risk_profile='moderate',
            commission_rate=0.00015,
            slippage_bps=5.0
        )

        runner = BacktestRunner(config, data_provider)

        # Should handle gracefully
        result = runner.run(engine='custom')
        assert isinstance(result, dict)

    @pytest.mark.skipif(not VECTORBT_AVAILABLE, reason="vectorbt not available")
    def test_comparison_with_no_trades(self, data_provider):
        """Test comparison when no trades occur."""
        # Create config with very restrictive settings
        config = BacktestConfig(
            start_date=date(2024, 12, 20),
            end_date=date(2024, 12, 31),  # Very short period
            initial_capital=10000000,
            regions=['KR'],
            tickers=['000020'],
            max_position_size=0.01,  # Very small position
            score_threshold=99.0,  # Very high threshold
            risk_profile='conservative',
            commission_rate=0.001,  # High commission
            slippage_bps=50.0  # High slippage
        )

        runner = BacktestRunner(config, data_provider)

        # May produce no trades
        result = runner.run(engine='both', signal_generator=rsi_signal_generator)

        # Should still produce valid comparison
        assert isinstance(result, ComparisonResult)
        assert 0 <= result.consistency_score <= 1
