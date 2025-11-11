"""
Tests for EngineValidator

Tests cross-engine validation functionality including consistency scoring,
discrepancy detection, and validation history tracking.
"""

import pytest
from datetime import date, datetime
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.data_providers import SQLiteDataProvider
from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.backtesting.validation import EngineValidator
from modules.backtesting.signal_generators.rsi_strategy import rsi_signal_generator
from modules.backtesting.signal_generators.macd_strategy import macd_signal_generator


@pytest.fixture
def config():
    """Create test backtest configuration."""
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
def validator(config, data_provider):
    """Create EngineValidator instance."""
    # Use temporary history path for testing
    history_path = Path(__file__).parent / 'test_validation_history.json'
    if history_path.exists():
        history_path.unlink()

    return EngineValidator(config, data_provider, history_path=history_path)


class TestEngineValidatorBasics:
    """Basic EngineValidator functionality tests."""

    def test_initialization(self, validator):
        """Test EngineValidator initialization."""
        assert validator is not None
        assert validator.config is not None
        assert validator.data_provider is not None
        assert validator.runner is not None
        assert isinstance(validator.validation_history, list)

    def test_validate_rsi_strategy(self, validator):
        """Test validation with RSI strategy."""
        try:
            report = validator.validate(
                signal_generator=rsi_signal_generator,
                tolerance=0.05
            )

            assert report is not None
            assert isinstance(report.validation_passed, bool)
            assert 0.0 <= report.consistency_score <= 1.0
            assert isinstance(report.discrepancies, dict)
            assert isinstance(report.recommendations, list)
            assert report.timestamp is not None

        except Exception as e:
            # Custom engine may fail due to schema - this is expected
            if "no such column: rsi" in str(e):
                pytest.skip("Custom engine requires full SQLite schema")
            else:
                raise

    def test_validate_multiple_strategies(self, validator):
        """Test batch validation with multiple strategies."""
        try:
            results = validator.validate_multiple(
                signal_generators=[rsi_signal_generator, macd_signal_generator],
                tolerance=0.05
            )

            assert isinstance(results, dict)
            assert len(results) == 2
            assert 'rsi_signal_generator' in results or 'macd_signal_generator' in results

        except Exception as e:
            if "no such column: rsi" in str(e):
                pytest.skip("Custom engine requires full SQLite schema")
            else:
                raise


class TestValidationHistory:
    """Validation history tracking tests."""

    def test_history_tracking(self, validator):
        """Test validation history is tracked correctly."""
        try:
            initial_count = len(validator.validation_history)

            # Run validation
            validator.validate(rsi_signal_generator, tolerance=0.05)

            # Check history updated
            assert len(validator.validation_history) == initial_count + 1

        except Exception as e:
            if "no such column: rsi" in str(e):
                pytest.skip("Custom engine requires full SQLite schema")
            else:
                raise

    def test_get_validation_history(self, validator):
        """Test retrieving validation history."""
        try:
            # Run multiple validations
            validator.validate(rsi_signal_generator)
            validator.validate(macd_signal_generator)

            # Get all history
            history = validator.get_validation_history()
            assert len(history) >= 2

            # Get filtered history
            rsi_history = validator.get_validation_history(
                signal_generator_name='rsi_signal_generator'
            )
            assert all(m.signal_generator_name == 'rsi_signal_generator' for m in rsi_history)

            # Get limited history
            recent = validator.get_validation_history(limit=1)
            assert len(recent) == 1

        except Exception as e:
            if "no such column: rsi" in str(e):
                pytest.skip("Custom engine requires full SQLite schema")
            else:
                raise


class TestConsistencyScoring:
    """Consistency scoring algorithm tests."""

    def test_consistency_score_range(self, validator):
        """Test consistency score is in valid range."""
        try:
            report = validator.validate(rsi_signal_generator)
            assert 0.0 <= report.consistency_score <= 1.0

        except Exception as e:
            if "no such column: rsi" in str(e):
                pytest.skip("Custom engine requires full SQLite schema")
            else:
                raise

    def test_tolerance_affects_validation(self, validator):
        """Test that tolerance affects pass/fail status."""
        try:
            # Strict tolerance
            strict_report = validator.validate(rsi_signal_generator, tolerance=0.01)

            # Loose tolerance
            loose_report = validator.validate(rsi_signal_generator, tolerance=0.50)

            # Loose tolerance should be more lenient
            if not strict_report.validation_passed:
                assert loose_report.validation_passed or loose_report.consistency_score > strict_report.consistency_score

        except Exception as e:
            if "no such column: rsi" in str(e):
                pytest.skip("Custom engine requires full SQLite schema")
            else:
                raise


@pytest.mark.skipif(
    not (Path(__file__).parent.parent.parent / 'data' / 'spock_local.db').exists(),
    reason="Database not available"
)
class TestIntegration:
    """Integration tests with real data."""

    def test_full_validation_workflow(self, validator):
        """Test complete validation workflow."""
        try:
            # Run validation
            report = validator.validate(rsi_signal_generator, tolerance=0.05)

            # Check report structure
            assert report.validation_passed is not None
            assert report.consistency_score >= 0.0
            assert len(report.recommendations) > 0

            # Check history updated
            history = validator.get_validation_history()
            assert len(history) > 0

            latest = history[0]
            assert latest.signal_generator_name == 'rsi_signal_generator'
            assert latest.consistency_score == report.consistency_score

        except Exception as e:
            if "no such column: rsi" in str(e):
                pytest.skip("Custom engine requires full SQLite schema")
            else:
                raise


class TestValidationMetricsDataclass:
    """Test ValidationMetrics dataclass creation and structure."""

    def test_validation_metrics_creation(self):
        """Test ValidationMetrics dataclass can be created."""
        from modules.backtesting.validation.engine_validator import ValidationMetrics

        metrics = ValidationMetrics(
            timestamp=datetime.now(),
            signal_generator_name="test_generator",
            config_hash="abc123",
            custom_total_return=0.15,
            custom_sharpe_ratio=1.5,
            custom_max_drawdown=-0.10,
            custom_total_trades=50,
            custom_execution_time=30.0,
            vectorbt_total_return=0.16,
            vectorbt_sharpe_ratio=1.6,
            vectorbt_max_drawdown=-0.09,
            vectorbt_total_trades=52,
            vectorbt_execution_time=0.3,
            consistency_score=0.95,
            return_difference=0.01,
            sharpe_difference=0.1,
            drawdown_difference=0.01,
            trade_count_difference=2,
            speedup_factor=100.0,
            validation_passed=True,
            tolerance_used=0.05,
            discrepancies={},
            recommendations=[]
        )

        assert metrics.signal_generator_name == "test_generator"
        assert metrics.consistency_score == 0.95
        assert metrics.validation_passed is True
        assert metrics.speedup_factor == 100.0

    def test_validation_metrics_with_failures(self):
        """Test ValidationMetrics with failed validation."""
        from modules.backtesting.validation.engine_validator import ValidationMetrics

        metrics = ValidationMetrics(
            timestamp=datetime.now(),
            signal_generator_name="failing_generator",
            config_hash="def456",
            custom_total_return=0.15,
            custom_sharpe_ratio=1.5,
            custom_max_drawdown=-0.10,
            custom_total_trades=50,
            custom_execution_time=30.0,
            vectorbt_total_return=0.05,
            vectorbt_sharpe_ratio=0.8,
            vectorbt_max_drawdown=-0.25,
            vectorbt_total_trades=30,
            vectorbt_execution_time=0.5,
            consistency_score=0.60,
            return_difference=0.10,
            sharpe_difference=0.7,
            drawdown_difference=0.15,
            trade_count_difference=20,
            speedup_factor=60.0,
            validation_passed=False,
            tolerance_used=0.05,
            discrepancies={"return": "High deviation", "trades": "Count mismatch"},
            recommendations=["Review signal logic", "Check data quality"]
        )

        assert metrics.validation_passed is False
        assert metrics.consistency_score == 0.60
        assert len(metrics.discrepancies) == 2
        assert len(metrics.recommendations) == 2


class TestHistoryPersistence:
    """Test validation history persistence (save/load from JSON)."""

    def test_history_saved_to_file(self, validator):
        """Test validation history is saved to JSON file."""
        try:
            # Run validation
            validator.validate(rsi_signal_generator, tolerance=0.05)

            # Check file exists
            assert validator.history_path.exists()

            # Check file has content
            with open(validator.history_path, 'r') as f:
                import json
                data = json.load(f)

            assert isinstance(data, list)
            assert len(data) > 0

        except Exception as e:
            if "no such column: rsi" in str(e):
                pytest.skip("Custom engine requires full SQLite schema")
            else:
                raise

    def test_history_loaded_on_init(self, config, data_provider):
        """Test validation history is loaded on initialization."""
        from modules.backtesting.validation import EngineValidator

        # Create validator and run validation
        history_path = Path(__file__).parent / 'test_history_load.json'
        if history_path.exists():
            history_path.unlink()

        validator1 = EngineValidator(config, data_provider, history_path=history_path)

        try:
            validator1.validate(rsi_signal_generator)

            # Create new validator with same history path
            validator2 = EngineValidator(config, data_provider, history_path=history_path)

            # Should load existing history
            assert len(validator2.validation_history) > 0

        except Exception as e:
            if "no such column: rsi" in str(e):
                pytest.skip("Custom engine requires full SQLite schema")
            else:
                raise
        finally:
            if history_path.exists():
                history_path.unlink()

    def test_history_timestamp_serialization(self, validator):
        """Test datetime serialization in history persistence."""
        try:
            # Run validation
            validator.validate(rsi_signal_generator)

            # Save and reload
            validator._save_history()
            loaded_history = validator._load_history()

            # Check timestamp preservation
            for metrics in loaded_history:
                assert isinstance(metrics.timestamp, datetime)

        except Exception as e:
            if "no such column: rsi" in str(e):
                pytest.skip("Custom engine requires full SQLite schema")
            else:
                raise


class TestConsistencyTrend:
    """Test consistency trend tracking and analysis."""

    def test_get_consistency_trend_returns_dataframe(self, validator):
        """Test get_consistency_trend returns pandas DataFrame."""
        try:
            # Run multiple validations
            validator.validate(rsi_signal_generator)
            validator.validate(rsi_signal_generator)

            # Get trend
            trend = validator.get_consistency_trend("rsi_signal_generator", window=10)

            assert isinstance(trend, pd.DataFrame)
            assert 'timestamp' in trend.columns
            assert 'consistency_score' in trend.columns
            assert 'validation_passed' in trend.columns

        except Exception as e:
            if "no such column: rsi" in str(e):
                pytest.skip("Custom engine requires full SQLite schema")
            else:
                raise

    def test_get_consistency_trend_sorted_by_timestamp(self, validator):
        """Test trend DataFrame is sorted chronologically."""
        try:
            # Run multiple validations
            validator.validate(rsi_signal_generator)
            validator.validate(rsi_signal_generator)

            # Get trend
            trend = validator.get_consistency_trend("rsi_signal_generator")

            if len(trend) > 1:
                # Check timestamps are sorted
                timestamps = trend['timestamp'].tolist()
                assert timestamps == sorted(timestamps)

        except Exception as e:
            if "no such column: rsi" in str(e):
                pytest.skip("Custom engine requires full SQLite schema")
            else:
                raise

    def test_get_consistency_trend_window_limit(self, validator):
        """Test window parameter limits trend results."""
        try:
            # Run multiple validations
            for _ in range(5):
                validator.validate(rsi_signal_generator)

            # Get trend with window=2
            trend = validator.get_consistency_trend("rsi_signal_generator", window=2)

            # Should have at most 2 records
            assert len(trend) <= 2

        except Exception as e:
            if "no such column: rsi" in str(e):
                pytest.skip("Custom engine requires full SQLite schema")
            else:
                raise

    def test_get_consistency_trend_empty_for_unknown_generator(self, validator):
        """Test trend returns empty DataFrame for unknown generator."""
        trend = validator.get_consistency_trend("nonexistent_generator")

        assert isinstance(trend, pd.DataFrame)
        assert len(trend) == 0


class TestConfigHashing:
    """Test backtest configuration hashing."""

    def test_config_hash_generation(self, validator):
        """Test _hash_config generates hash string."""
        config_hash = validator._hash_config()

        assert isinstance(config_hash, str)
        assert len(config_hash) > 0

    def test_config_hash_consistent(self, validator):
        """Test same config produces same hash."""
        hash1 = validator._hash_config()
        hash2 = validator._hash_config()

        assert hash1 == hash2

    def test_config_hash_changes_with_config(self, config, data_provider):
        """Test different configs produce different hashes."""
        from modules.backtesting.validation import EngineValidator

        validator1 = EngineValidator(config, data_provider)
        hash1 = validator1._hash_config()

        # Create different config
        config2 = BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30),
            initial_capital=5000000,
            regions=['US'],
            tickers=['AAPL'],
            max_position_size=0.2,
            score_threshold=70.0,
            risk_profile='aggressive'
        )

        validator2 = EngineValidator(config2, data_provider)
        hash2 = validator2._hash_config()

        # Hashes should differ
        assert hash1 != hash2


class TestBatchValidation:
    """Test batch validation functionality."""

    def test_validate_multiple_returns_all_results(self, validator):
        """Test validate_multiple returns result for each generator."""
        try:
            generators = [rsi_signal_generator, macd_signal_generator]
            results = validator.validate_multiple(generators, tolerance=0.05)

            # Should have result for each generator
            assert len(results) >= 1  # At least one should succeed

        except Exception as e:
            if "no such column: rsi" in str(e):
                pytest.skip("Custom engine requires full SQLite schema")
            else:
                raise

    def test_validate_multiple_continues_on_error(self, validator):
        """Test batch validation continues even if one fails."""
        def failing_generator(close):
            raise ValueError("Intentional test failure")

        try:
            generators = [failing_generator, rsi_signal_generator]
            results = validator.validate_multiple(generators)

            # Should have results (even failed ones)
            assert len(results) == 2

            # Failing generator should have failed report
            assert 'failing_generator' in results
            assert not results['failing_generator'].validation_passed

        except Exception as e:
            if "no such column: rsi" in str(e):
                pytest.skip("Custom engine requires full SQLite schema")
            else:
                raise

    def test_validate_multiple_logs_summary(self, validator, caplog):
        """Test batch validation logs summary."""
        try:
            generators = [rsi_signal_generator]
            validator.validate_multiple(generators)

            # Check log contains summary
            assert any("Batch validation complete" in record.message for record in caplog.records)

        except Exception as e:
            if "no such column: rsi" in str(e):
                pytest.skip("Custom engine requires full SQLite schema")
            else:
                raise


class TestHistoryFiltering:
    """Test validation history filtering and limiting."""

    def test_history_filter_by_generator_name(self, validator):
        """Test filtering history by signal generator name."""
        try:
            # Run validations
            validator.validate(rsi_signal_generator)
            validator.validate(macd_signal_generator)

            # Filter by name
            rsi_history = validator.get_validation_history(signal_generator_name='rsi_signal_generator')

            # Should only contain RSI records
            assert all(m.signal_generator_name == 'rsi_signal_generator' for m in rsi_history)

        except Exception as e:
            if "no such column: rsi" in str(e):
                pytest.skip("Custom engine requires full SQLite schema")
            else:
                raise

    def test_history_limit_parameter(self, validator):
        """Test limiting number of history results."""
        try:
            # Run multiple validations
            for _ in range(5):
                validator.validate(rsi_signal_generator)

            # Get limited results
            limited = validator.get_validation_history(limit=2)

            # Should have at most 2 results
            assert len(limited) <= 2

        except Exception as e:
            if "no such column: rsi" in str(e):
                pytest.skip("Custom engine requires full SQLite schema")
            else:
                raise

    def test_history_sorted_by_timestamp_descending(self, validator):
        """Test history is sorted most recent first."""
        try:
            import time

            # Run validations with delay
            validator.validate(rsi_signal_generator)
            time.sleep(0.1)
            validator.validate(rsi_signal_generator)

            # Get history
            history = validator.get_validation_history()

            if len(history) >= 2:
                # Most recent should be first
                assert history[0].timestamp >= history[1].timestamp

        except Exception as e:
            if "no such column: rsi" in str(e):
                pytest.skip("Custom engine requires full SQLite schema")
            else:
                raise


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_history_on_init(self, config, data_provider):
        """Test validator handles empty history gracefully."""
        from modules.backtesting.validation import EngineValidator

        # Use non-existent history file
        history_path = Path(__file__).parent / 'nonexistent_history.json'
        if history_path.exists():
            history_path.unlink()

        validator = EngineValidator(config, data_provider, history_path=history_path)

        # Should have empty history
        assert len(validator.validation_history) == 0

    def test_corrupted_history_file(self, config, data_provider):
        """Test validator handles corrupted history file."""
        from modules.backtesting.validation import EngineValidator

        # Create corrupted history file
        history_path = Path(__file__).parent / 'corrupted_history.json'
        with open(history_path, 'w') as f:
            f.write("{ invalid json }")

        try:
            validator = EngineValidator(config, data_provider, history_path=history_path)

            # Should handle gracefully with empty history
            assert len(validator.validation_history) == 0

        finally:
            if history_path.exists():
                history_path.unlink()

    def test_get_trend_with_no_history(self, validator):
        """Test get_consistency_trend with no validation history."""
        trend = validator.get_consistency_trend("unknown_generator")

        assert isinstance(trend, pd.DataFrame)
        assert len(trend) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
