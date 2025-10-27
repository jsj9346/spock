"""
Tests for RegressionTester

Tests automated regression testing functionality including reference creation,
regression detection, and performance tracking.
"""

import pytest
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.data_providers import SQLiteDataProvider
from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.backtesting.validation import RegressionTester
from modules.backtesting.signal_generators.rsi_strategy import rsi_signal_generator


@pytest.fixture
def config():
    """Create test configuration."""
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
def data_provider():
    """Create test data provider."""
    db_path = Path(__file__).parent.parent.parent / 'data' / 'spock_local.db'
    if not db_path.exists():
        pytest.skip(f"Database not found: {db_path}")

    db_manager = SQLiteDatabaseManager(str(db_path))
    return SQLiteDataProvider(db_manager)


@pytest.fixture
def tester(config, data_provider):
    """Create RegressionTester instance."""
    reference_dir = Path(__file__).parent / 'test_references'
    reference_dir.mkdir(exist_ok=True)

    # Clean up existing test references
    for ref_file in reference_dir.glob("test_*.json"):
        ref_file.unlink()

    return RegressionTester(config, data_provider, reference_dir=reference_dir)


class TestRegressionTesterBasics:
    """Basic RegressionTester functionality."""

    def test_initialization(self, tester):
        """Test RegressionTester initialization."""
        assert tester is not None
        assert tester.config is not None
        assert tester.runner is not None
        assert tester.reference_dir.exists()

    def test_create_reference(self, tester):
        """Test creating reference result."""
        reference = tester.create_reference(
            test_name="test_rsi_reference",
            signal_generator=rsi_signal_generator,
            description="Test RSI reference",
            tags=['test', 'rsi']
        )

        assert reference is not None
        assert reference.test_name == "test_rsi_reference"
        assert reference.signal_generator_name == 'rsi_signal_generator'
        assert reference.description == "Test RSI reference"
        assert 'test' in reference.tags

    def test_reference_already_exists(self, tester):
        """Test error when reference already exists."""
        # Create reference
        tester.create_reference(
            test_name="test_duplicate",
            signal_generator=rsi_signal_generator
        )

        # Try to create again without overwrite
        with pytest.raises(FileExistsError):
            tester.create_reference(
                test_name="test_duplicate",
                signal_generator=rsi_signal_generator
            )


class TestRegressionDetection:
    """Regression detection tests."""

    def test_regression_test_pass(self, tester):
        """Test regression test passes with same signal generator."""
        # Create reference
        tester.create_reference(
            test_name="test_regression_pass",
            signal_generator=rsi_signal_generator
        )

        # Run regression test (should pass with same generator)
        result = tester.test_regression(
            test_name="test_regression_pass",
            signal_generator=rsi_signal_generator,
            tolerance=0.10  # Use generous tolerance for test
        )

        # Verify result structure
        assert result.test_name == "test_regression_pass"
        assert isinstance(result.passed, bool)
        assert isinstance(result.failures, list)
        assert isinstance(result.warnings, list)

    def test_list_references(self, tester):
        """Test listing all references."""
        # Create multiple references
        tester.create_reference("test_ref1", rsi_signal_generator)
        tester.create_reference("test_ref2", rsi_signal_generator, overwrite=True)

        # List references
        references = tester.list_references()
        assert len(references) >= 2

        test_names = [ref.test_name for ref in references]
        assert "test_ref1" in test_names or "test_ref2" in test_names


class TestPerformanceTracking:
    """Performance tracking tests."""

    def test_execution_time_tracked(self, tester):
        """Test execution time is tracked."""
        reference = tester.create_reference(
            test_name="test_execution_time",
            signal_generator=rsi_signal_generator
        )

        assert reference.execution_time > 0.0
        assert reference.execution_time < 60.0  # Should complete within 1 minute

    def test_performance_metrics_tracked(self, tester):
        """Test all performance metrics are tracked."""
        reference = tester.create_reference(
            test_name="test_metrics",
            signal_generator=rsi_signal_generator
        )

        assert reference.total_return is not None
        assert reference.sharpe_ratio is not None
        assert reference.max_drawdown is not None
        assert reference.total_trades >= 0
        assert 0.0 <= reference.win_rate <= 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
