"""
Test Consistency Monitor

Tests for real-time consistency monitoring between backtesting engines with
alerting and trend tracking.

Usage:
    PYTHONPATH=/Users/13ruce/spock python3 -m pytest \
        tests/backtesting/validation/test_consistency_monitor.py -v
"""

import pytest
from datetime import datetime, date
from pathlib import Path
from unittest.mock import Mock, patch

from modules.backtesting.validation.consistency_monitor import ConsistencyMonitor
from modules.backtesting.validation.engine_validator import ValidationMetrics
from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.data_providers import SQLiteDataProvider
from modules.db_manager_sqlite import SQLiteDatabaseManager


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="class")
def test_db_path():
    """Get test database path."""
    db_path = Path(__file__).parent.parent.parent.parent / 'data' / 'spock_local.db'
    if not db_path.exists():
        pytest.skip(f"Test database not found: {db_path}")
    return str(db_path)


@pytest.fixture
def sample_config():
    """Create sample backtest configuration."""
    return BacktestConfig(
        start_date=date(2024, 1, 1),
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
def monitor(sample_config, data_provider):
    """Create ConsistencyMonitor instance."""
    return ConsistencyMonitor(sample_config, data_provider)


def create_simple_signal_generator():
    """Create simple signal generator for testing."""
    def generator(close):
        import pandas as pd
        entries = pd.Series([True, False, True, False, True], index=close.index)
        exits = pd.Series([False, True, False, True, False], index=close.index)
        return entries, exits
    return generator


# ============================================================================
# Basic Functionality Tests
# ============================================================================

class TestConsistencyMonitorBasics:
    """Test basic ConsistencyMonitor functionality."""

    def test_initialization(self, monitor):
        """Test ConsistencyMonitor initialization."""
        assert monitor.config is not None
        assert monitor.data_provider is not None
        assert monitor.validator is not None
        assert monitor.alert_threshold == 0.90

    def test_initialization_custom_threshold(self, sample_config, data_provider):
        """Test initialization with custom alert threshold."""
        monitor = ConsistencyMonitor(sample_config, data_provider, alert_threshold=0.85)

        assert monitor.alert_threshold == 0.85

    def test_default_alert_threshold(self, monitor):
        """Test that default alert threshold is 90%."""
        assert monitor.alert_threshold == 0.90

    def test_validator_initialized(self, monitor):
        """Test that EngineValidator is properly initialized."""
        assert monitor.validator is not None
        assert monitor.validator.config == monitor.config
        assert monitor.validator.data_provider == monitor.data_provider


# ============================================================================
# Check Consistency Tests
# ============================================================================

class TestCheckConsistency:
    """Test check_consistency functionality."""

    @patch.object(ConsistencyMonitor, '_generate_message')
    def test_check_consistency_basic_structure(self, mock_message, monitor):
        """Test basic structure of consistency check result."""
        mock_message.return_value = "Test message"

        # Mock validator.validate to return controlled result
        mock_report = ValidationMetrics(
            signal_generator_name="test_generator",
            consistency_score=0.95,
            return_difference=0.02,
            trade_count_difference=5,
            speedup_factor=100.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        with patch.object(monitor.validator, 'validate', return_value=mock_report):
            signal_gen = create_simple_signal_generator()
            status = monitor.check_consistency(signal_gen)

        # Check status structure
        assert 'passed' in status
        assert 'consistency_score' in status
        assert 'validation_passed' in status
        assert 'message' in status
        assert 'timestamp' in status

    @patch.object(ConsistencyMonitor, '_generate_message')
    def test_check_consistency_passed(self, mock_message, monitor):
        """Test consistency check with passing score."""
        mock_message.return_value = "✅ Consistent"

        mock_report = ValidationMetrics(
            signal_generator_name="passing_generator",
            consistency_score=0.95,  # Above threshold
            return_difference=0.02,
            trade_count_difference=5,
            speedup_factor=100.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        with patch.object(monitor.validator, 'validate', return_value=mock_report):
            signal_gen = create_simple_signal_generator()
            status = monitor.check_consistency(signal_gen)

        assert status['passed'] is True
        assert status['consistency_score'] == 0.95
        assert status['validation_passed'] is True

    @patch.object(ConsistencyMonitor, '_generate_message')
    def test_check_consistency_failed(self, mock_message, monitor):
        """Test consistency check with failing score."""
        mock_message.return_value = "❌ Inconsistent"

        mock_report = ValidationMetrics(
            signal_generator_name="failing_generator",
            consistency_score=0.85,  # Below threshold (0.90)
            return_difference=0.10,
            trade_count_difference=20,
            speedup_factor=50.0,
            validation_passed=False,
            discrepancies={"metric": "value"},
            recommendations=["Fix issue"]
        )

        with patch.object(monitor.validator, 'validate', return_value=mock_report):
            signal_gen = create_simple_signal_generator()
            status = monitor.check_consistency(signal_gen)

        assert status['passed'] is False
        assert status['consistency_score'] == 0.85
        assert status['validation_passed'] is False

    @patch.object(ConsistencyMonitor, '_generate_message')
    def test_check_consistency_at_threshold(self, mock_message, monitor):
        """Test consistency check exactly at threshold."""
        mock_message.return_value = "✅ Consistent"

        mock_report = ValidationMetrics(
            signal_generator_name="threshold_generator",
            consistency_score=0.90,  # Exactly at threshold
            return_difference=0.05,
            trade_count_difference=10,
            speedup_factor=80.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        with patch.object(monitor.validator, 'validate', return_value=mock_report):
            signal_gen = create_simple_signal_generator()
            status = monitor.check_consistency(signal_gen)

        # At threshold should pass (>= comparison)
        assert status['passed'] is True

    def test_check_consistency_timestamp(self, monitor):
        """Test that consistency check includes timestamp."""
        mock_report = ValidationMetrics(
            signal_generator_name="timestamp_test",
            consistency_score=0.95,
            return_difference=0.02,
            trade_count_difference=5,
            speedup_factor=100.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        before = datetime.now()

        with patch.object(monitor.validator, 'validate', return_value=mock_report):
            signal_gen = create_simple_signal_generator()
            status = monitor.check_consistency(signal_gen)

        after = datetime.now()

        # Timestamp should be between before and after
        assert before <= status['timestamp'] <= after
        assert isinstance(status['timestamp'], datetime)


# ============================================================================
# Message Generation Tests
# ============================================================================

class TestMessageGeneration:
    """Test _generate_message functionality."""

    def test_generate_message_passed(self, monitor):
        """Test message generation for passed validation."""
        report = ValidationMetrics(
            signal_generator_name="test_strategy",
            consistency_score=0.95,
            return_difference=0.02,
            trade_count_difference=5,
            speedup_factor=100.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        message = monitor._generate_message(report)

        assert "✅" in message
        assert "Consistent" in message
        assert "95.0%" in message or "95%" in message

    def test_generate_message_failed(self, monitor):
        """Test message generation for failed validation."""
        report = ValidationMetrics(
            signal_generator_name="test_strategy",
            consistency_score=0.70,
            return_difference=0.15,
            trade_count_difference=20,
            speedup_factor=50.0,
            validation_passed=False,
            discrepancies={"metric": "value"},
            recommendations=["Fix issue"]
        )

        message = monitor._generate_message(report)

        assert "❌" in message
        assert "Inconsistent" in message
        assert "70.0%" in message or "70%" in message

    def test_generate_message_includes_score(self, monitor):
        """Test that message includes consistency score."""
        report = ValidationMetrics(
            signal_generator_name="test_strategy",
            consistency_score=0.8543,
            return_difference=0.10,
            trade_count_difference=15,
            speedup_factor=75.0,
            validation_passed=False,
            discrepancies={},
            recommendations=[]
        )

        message = monitor._generate_message(report)

        # Score should be formatted as percentage with 1 decimal
        assert "85.4%" in message


# ============================================================================
# Alert Threshold Tests
# ============================================================================

class TestAlertThreshold:
    """Test alert threshold behavior."""

    def test_custom_threshold_respected(self, sample_config, data_provider):
        """Test that custom alert threshold is respected."""
        monitor = ConsistencyMonitor(sample_config, data_provider, alert_threshold=0.85)

        mock_report = ValidationMetrics(
            signal_generator_name="test_generator",
            consistency_score=0.87,  # Between 0.85 and 0.90
            return_difference=0.05,
            trade_count_difference=10,
            speedup_factor=80.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        with patch.object(monitor.validator, 'validate', return_value=mock_report):
            signal_gen = create_simple_signal_generator()
            status = monitor.check_consistency(signal_gen)

        # Should pass with 0.85 threshold (0.87 >= 0.85)
        assert status['passed'] is True

    def test_strict_threshold(self, sample_config, data_provider):
        """Test with strict (high) alert threshold."""
        monitor = ConsistencyMonitor(sample_config, data_provider, alert_threshold=0.95)

        mock_report = ValidationMetrics(
            signal_generator_name="test_generator",
            consistency_score=0.92,  # Below strict threshold
            return_difference=0.03,
            trade_count_difference=7,
            speedup_factor=90.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        with patch.object(monitor.validator, 'validate', return_value=mock_report):
            signal_gen = create_simple_signal_generator()
            status = monitor.check_consistency(signal_gen)

        # Should fail with strict threshold (0.92 < 0.95)
        assert status['passed'] is False

    def test_lenient_threshold(self, sample_config, data_provider):
        """Test with lenient (low) alert threshold."""
        monitor = ConsistencyMonitor(sample_config, data_provider, alert_threshold=0.70)

        mock_report = ValidationMetrics(
            signal_generator_name="test_generator",
            consistency_score=0.75,  # Above lenient threshold
            return_difference=0.12,
            trade_count_difference=25,
            speedup_factor=60.0,
            validation_passed=False,
            discrepancies={},
            recommendations=[]
        )

        with patch.object(monitor.validator, 'validate', return_value=mock_report):
            signal_gen = create_simple_signal_generator()
            status = monitor.check_consistency(signal_gen)

        # Should pass with lenient threshold (0.75 >= 0.70)
        assert status['passed'] is True


# ============================================================================
# Logging Tests
# ============================================================================

class TestLogging:
    """Test logging behavior."""

    def test_warning_logged_on_failure(self, monitor, caplog):
        """Test that warning is logged when consistency check fails."""
        mock_report = ValidationMetrics(
            signal_generator_name="failing_generator",
            consistency_score=0.80,  # Below threshold
            return_difference=0.10,
            trade_count_difference=20,
            speedup_factor=50.0,
            validation_passed=False,
            discrepancies={},
            recommendations=[]
        )

        with patch.object(monitor.validator, 'validate', return_value=mock_report):
            signal_gen = create_simple_signal_generator()
            with caplog.at_level('WARNING'):
                status = monitor.check_consistency(signal_gen)

        # Warning should be logged
        assert any("Consistency alert" in record.message for record in caplog.records)

    def test_no_warning_on_pass(self, monitor, caplog):
        """Test that no warning is logged when consistency check passes."""
        mock_report = ValidationMetrics(
            signal_generator_name="passing_generator",
            consistency_score=0.95,  # Above threshold
            return_difference=0.02,
            trade_count_difference=5,
            speedup_factor=100.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        with patch.object(monitor.validator, 'validate', return_value=mock_report):
            signal_gen = create_simple_signal_generator()
            with caplog.at_level('WARNING'):
                status = monitor.check_consistency(signal_gen)

        # No warning should be logged
        assert not any("Consistency alert" in record.message for record in caplog.records)


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Test integration with EngineValidator."""

    def test_validator_integration(self, monitor):
        """Test that ConsistencyMonitor properly integrates with EngineValidator."""
        # Monitor should have validator initialized
        assert monitor.validator is not None

        # Validator should use same config and data provider
        assert monitor.validator.config == monitor.config
        assert monitor.validator.data_provider == monitor.data_provider

    def test_tolerance_parameter_passed(self, monitor):
        """Test that tolerance parameter is passed to validator."""
        mock_report = ValidationMetrics(
            signal_generator_name="test_generator",
            consistency_score=0.95,
            return_difference=0.02,
            trade_count_difference=5,
            speedup_factor=100.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        with patch.object(monitor.validator, 'validate', return_value=mock_report) as mock_validate:
            signal_gen = create_simple_signal_generator()
            status = monitor.check_consistency(signal_gen, tolerance=0.10)

            # Verify tolerance was passed
            mock_validate.assert_called_once()
            call_args = mock_validate.call_args
            assert call_args[1]['tolerance'] == 0.10


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_consistency_score(self, monitor):
        """Test handling of zero consistency score."""
        mock_report = ValidationMetrics(
            signal_generator_name="zero_consistency",
            consistency_score=0.0,
            return_difference=1.0,
            trade_count_difference=100,
            speedup_factor=1.0,
            validation_passed=False,
            discrepancies={},
            recommendations=[]
        )

        with patch.object(monitor.validator, 'validate', return_value=mock_report):
            signal_gen = create_simple_signal_generator()
            status = monitor.check_consistency(signal_gen)

        assert status['passed'] is False
        assert status['consistency_score'] == 0.0

    def test_perfect_consistency_score(self, monitor):
        """Test handling of perfect (1.0) consistency score."""
        mock_report = ValidationMetrics(
            signal_generator_name="perfect_consistency",
            consistency_score=1.0,
            return_difference=0.0,
            trade_count_difference=0,
            speedup_factor=100.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        with patch.object(monitor.validator, 'validate', return_value=mock_report):
            signal_gen = create_simple_signal_generator()
            status = monitor.check_consistency(signal_gen)

        assert status['passed'] is True
        assert status['consistency_score'] == 1.0

    def test_multiple_instances_independent(self, sample_config, data_provider):
        """Test that multiple monitor instances are independent."""
        monitor1 = ConsistencyMonitor(sample_config, data_provider, alert_threshold=0.85)
        monitor2 = ConsistencyMonitor(sample_config, data_provider, alert_threshold=0.95)

        # Each should have independent thresholds
        assert monitor1.alert_threshold == 0.85
        assert monitor2.alert_threshold == 0.95

        # Each should have independent validators
        assert monitor1.validator is not monitor2.validator
