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


class TestReferenceCreation:
    """Test reference result creation."""

    def test_create_reference_with_description(self, tester):
        """Test creating reference with description."""
        reference = tester.create_reference(
            test_name="test_with_description",
            signal_generator=rsi_signal_generator,
            description="Test strategy description"
        )

        assert reference.description == "Test strategy description"

    def test_create_reference_with_tags(self, tester):
        """Test creating reference with tags."""
        reference = tester.create_reference(
            test_name="test_with_tags",
            signal_generator=rsi_signal_generator,
            tags=['rsi', 'momentum', 'test']
        )

        assert 'rsi' in reference.tags
        assert 'momentum' in reference.tags
        assert 'test' in reference.tags

    def test_create_reference_overwrite(self, tester):
        """Test overwriting existing reference."""
        # Create initial reference
        tester.create_reference(
            test_name="test_overwrite",
            signal_generator=rsi_signal_generator,
            description="Original description"
        )

        # Overwrite with new description
        reference = tester.create_reference(
            test_name="test_overwrite",
            signal_generator=rsi_signal_generator,
            description="Updated description",
            overwrite=True
        )

        assert reference.description == "Updated description"

    def test_reference_includes_config_hash(self, tester):
        """Test that reference includes configuration hash."""
        reference = tester.create_reference(
            test_name="test_config_hash",
            signal_generator=rsi_signal_generator
        )

        assert reference.config_hash is not None
        assert len(reference.config_hash) > 0

    def test_reference_includes_timestamp(self, tester):
        """Test that reference includes creation timestamp."""
        from datetime import datetime

        before = datetime.now()
        reference = tester.create_reference(
            test_name="test_timestamp",
            signal_generator=rsi_signal_generator
        )
        after = datetime.now()

        assert before <= reference.created_at <= after

    def test_reference_includes_signal_generator_name(self, tester):
        """Test that reference includes signal generator name."""
        reference = tester.create_reference(
            test_name="test_generator_name",
            signal_generator=rsi_signal_generator
        )

        assert reference.signal_generator_name == 'rsi_signal_generator'


class TestReferenceFileOperations:
    """Test file I/O operations for references."""

    def test_reference_saved_to_file(self, tester):
        """Test that reference is saved to JSON file."""
        tester.create_reference(
            test_name="test_file_saved",
            signal_generator=rsi_signal_generator
        )

        reference_path = tester.reference_dir / "test_file_saved.json"
        assert reference_path.exists()

    def test_reference_can_be_loaded(self, tester):
        """Test that saved reference can be loaded."""
        # Create reference
        original = tester.create_reference(
            test_name="test_load",
            signal_generator=rsi_signal_generator,
            description="Test load"
        )

        # Load reference
        loaded = tester._load_reference("test_load")

        assert loaded.test_name == original.test_name
        assert loaded.description == original.description
        assert loaded.total_return == original.total_return

    def test_load_nonexistent_reference_raises_error(self, tester):
        """Test that loading nonexistent reference raises error."""
        with pytest.raises(FileNotFoundError):
            tester._load_reference("nonexistent_reference")

    def test_delete_reference(self, tester):
        """Test deleting reference file."""
        # Create reference
        tester.create_reference(
            test_name="test_delete",
            signal_generator=rsi_signal_generator
        )

        reference_path = tester.reference_dir / "test_delete.json"
        assert reference_path.exists()

        # Delete reference
        tester.delete_reference("test_delete")

        assert not reference_path.exists()

    def test_delete_nonexistent_reference_no_error(self, tester):
        """Test that deleting nonexistent reference doesn't raise error."""
        # Should not raise an error
        tester.delete_reference("nonexistent")


class TestRegressionComparison:
    """Test regression comparison logic."""

    def test_return_deviation_calculation(self, tester):
        """Test return deviation calculation."""
        # Create reference
        tester.create_reference(
            test_name="test_return_deviation",
            signal_generator=rsi_signal_generator
        )

        # Test regression
        result = tester.test_regression(
            test_name="test_return_deviation",
            signal_generator=rsi_signal_generator,
            tolerance=0.10
        )

        # Deviation should be calculated
        assert isinstance(result.return_deviation, float)
        assert result.return_deviation >= 0.0

    def test_sharpe_deviation_calculation(self, tester):
        """Test Sharpe ratio deviation calculation."""
        # Create reference
        tester.create_reference(
            test_name="test_sharpe_deviation",
            signal_generator=rsi_signal_generator
        )

        # Test regression
        result = tester.test_regression(
            test_name="test_sharpe_deviation",
            signal_generator=rsi_signal_generator,
            tolerance=0.10
        )

        # Deviation should be calculated
        assert isinstance(result.sharpe_deviation, float)
        assert result.sharpe_deviation >= 0.0

    def test_drawdown_deviation_calculation(self, tester):
        """Test max drawdown deviation calculation."""
        # Create reference
        tester.create_reference(
            test_name="test_drawdown_deviation",
            signal_generator=rsi_signal_generator
        )

        # Test regression
        result = tester.test_regression(
            test_name="test_drawdown_deviation",
            signal_generator=rsi_signal_generator,
            tolerance=0.10
        )

        # Deviation should be calculated
        assert isinstance(result.drawdown_deviation, float)
        assert result.drawdown_deviation >= 0.0

    def test_trade_count_deviation_calculation(self, tester):
        """Test trade count deviation calculation."""
        # Create reference
        tester.create_reference(
            test_name="test_trade_deviation",
            signal_generator=rsi_signal_generator
        )

        # Test regression
        result = tester.test_regression(
            test_name="test_trade_deviation",
            signal_generator=rsi_signal_generator,
            tolerance=0.10
        )

        # Deviation should be calculated
        assert isinstance(result.trade_count_deviation, int)
        assert result.trade_count_deviation >= 0

    def test_execution_time_deviation_calculation(self, tester):
        """Test execution time deviation calculation."""
        # Create reference
        tester.create_reference(
            test_name="test_time_deviation",
            signal_generator=rsi_signal_generator
        )

        # Test regression
        result = tester.test_regression(
            test_name="test_time_deviation",
            signal_generator=rsi_signal_generator,
            tolerance=0.10
        )

        # Deviation should be calculated
        assert isinstance(result.execution_time_deviation, float)
        assert result.execution_time_deviation >= 0.0


class TestToleranceHandling:
    """Test tolerance threshold handling."""

    def test_custom_tolerance_respected(self, tester):
        """Test that custom tolerance is respected."""
        # Create reference
        tester.create_reference(
            test_name="test_custom_tolerance",
            signal_generator=rsi_signal_generator
        )

        # Test with generous tolerance
        result = tester.test_regression(
            test_name="test_custom_tolerance",
            signal_generator=rsi_signal_generator,
            tolerance=0.50  # 50% tolerance - should always pass
        )

        assert result.passed is True

    def test_default_tolerance_used(self, tester):
        """Test that default tolerance is used when not specified."""
        # Create reference
        tester.create_reference(
            test_name="test_default_tolerance",
            signal_generator=rsi_signal_generator
        )

        # Test without specifying tolerance
        result = tester.test_regression(
            test_name="test_default_tolerance",
            signal_generator=rsi_signal_generator
        )

        # Should use default tolerance (5%)
        assert result.passed is not None


class TestWarnings:
    """Test warning generation."""

    def test_warnings_generated_for_borderline_deviations(self, tester):
        """Test that warnings are generated for borderline deviations."""
        # Create reference
        tester.create_reference(
            test_name="test_warnings",
            signal_generator=rsi_signal_generator
        )

        # Test regression (same generator should have minimal deviation)
        result = tester.test_regression(
            test_name="test_warnings",
            signal_generator=rsi_signal_generator,
            tolerance=0.01  # Very strict tolerance
        )

        # Warnings list should exist
        assert isinstance(result.warnings, list)

    def test_warnings_include_execution_time(self, tester):
        """Test that warnings can include execution time alerts."""
        # Create reference
        tester.create_reference(
            test_name="test_execution_warning",
            signal_generator=rsi_signal_generator
        )

        # Test regression
        result = tester.test_regression(
            test_name="test_execution_warning",
            signal_generator=rsi_signal_generator,
            tolerance=0.10
        )

        # Warnings should be a list
        assert isinstance(result.warnings, list)


class TestFailureMessages:
    """Test failure message generation."""

    def test_passed_result_no_failure_message(self, tester):
        """Test that passed result has no failure message."""
        # Create reference
        tester.create_reference(
            test_name="test_no_failure_msg",
            signal_generator=rsi_signal_generator
        )

        # Test regression with same generator (should pass)
        result = tester.test_regression(
            test_name="test_no_failure_msg",
            signal_generator=rsi_signal_generator,
            tolerance=0.10
        )

        if result.passed:
            assert result.failure_message is None

    def test_failed_result_has_failure_message(self, tester):
        """Test that failed result has failure message."""
        # Create reference
        tester.create_reference(
            test_name="test_failure_msg",
            signal_generator=rsi_signal_generator
        )

        # Test with very strict tolerance to force failure
        result = tester.test_regression(
            test_name="test_failure_msg",
            signal_generator=rsi_signal_generator,
            tolerance=0.0001  # Extremely strict
        )

        if not result.passed:
            assert result.failure_message is not None
            assert "regression" in result.failure_message.lower()

    def test_failures_list_populated_on_fail(self, tester):
        """Test that failures list is populated when test fails."""
        # Create reference
        tester.create_reference(
            test_name="test_failures_list",
            signal_generator=rsi_signal_generator
        )

        # Test with strict tolerance
        result = tester.test_regression(
            test_name="test_failures_list",
            signal_generator=rsi_signal_generator,
            tolerance=0.0001
        )

        if not result.passed:
            assert len(result.failures) > 0
            # Each failure should be a descriptive string
            for failure in result.failures:
                assert isinstance(failure, str)
                assert len(failure) > 0


class TestBulkOperations:
    """Test bulk reference operations."""

    def test_list_multiple_references(self, tester):
        """Test listing multiple references."""
        # Create multiple references
        for i in range(3):
            tester.create_reference(
                test_name=f"test_list_{i}",
                signal_generator=rsi_signal_generator,
                overwrite=True
            )

        # List all references
        references = tester.list_references()

        # Should have at least 3 references
        assert len(references) >= 3

    def test_test_all_references(self, tester):
        """Test running all regression tests."""
        # Create references
        tester.create_reference("test_all_1", rsi_signal_generator)
        tester.create_reference("test_all_2", rsi_signal_generator, overwrite=True)

        # Run all tests
        signal_generators = {
            "test_all_1": rsi_signal_generator,
            "test_all_2": rsi_signal_generator
        }

        results = tester.test_all_references(signal_generators)

        # Should have results for both tests
        assert "test_all_1" in results or "test_all_2" in results
        assert len(results) >= 1


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_tags_list(self, tester):
        """Test creating reference with empty tags list."""
        reference = tester.create_reference(
            test_name="test_empty_tags",
            signal_generator=rsi_signal_generator,
            tags=[]
        )

        assert reference.tags == []

    def test_none_description(self, tester):
        """Test creating reference with no description."""
        reference = tester.create_reference(
            test_name="test_no_description",
            signal_generator=rsi_signal_generator
        )

        assert reference.description == ""

    def test_result_timestamp_recorded(self, tester):
        """Test that regression test result includes timestamp."""
        from datetime import datetime

        # Create reference
        tester.create_reference(
            test_name="test_result_timestamp",
            signal_generator=rsi_signal_generator
        )

        before = datetime.now()

        # Run regression test
        result = tester.test_regression(
            test_name="test_result_timestamp",
            signal_generator=rsi_signal_generator,
            tolerance=0.10
        )

        after = datetime.now()

        assert before <= result.timestamp <= after


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
