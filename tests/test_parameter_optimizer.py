"""
Unit Tests for Parameter Optimizer

Purpose: Validate parameter optimization functionality including configuration,
         trial execution, and result analysis.

Test Coverage:
  - ParameterSpec validation
  - OptimizationConfig validation
  - OptimizationTrial and OptimizationResult
  - ParameterOptimizer base class
  - GridSearchOptimizer
  - Parameter importance calculation

Author: Spock Development Team
"""

import pytest
from datetime import date, datetime
from unittest.mock import Mock, MagicMock
import pandas as pd

from modules.backtesting.parameter_optimizer import (
    ParameterSpec,
    OptimizationConfig,
    OptimizationTrial,
    OptimizationResult,
    ParameterOptimizer,
)
from modules.backtesting.grid_search_optimizer import GridSearchOptimizer
from modules.backtesting.backtest_config import (
    BacktestConfig,
    BacktestResult,
    PerformanceMetrics,
    Trade,
)
from modules.db_manager_sqlite import SQLiteDatabaseManager


class TestParameterSpec:
    """Test ParameterSpec dataclass."""

    def test_valid_int_parameter(self):
        """Test valid integer parameter specification."""
        spec = ParameterSpec(
            type='int',
            min_value=1,
            max_value=10,
            step=1
        )
        assert spec.type == 'int'
        assert spec.min_value == 1
        assert spec.max_value == 10
        assert spec.step == 1

    def test_valid_float_parameter(self):
        """Test valid float parameter specification."""
        spec = ParameterSpec(
            type='float',
            min_value=0.0,
            max_value=1.0,
            step=0.1,
            log_scale=True
        )
        assert spec.type == 'float'
        assert spec.log_scale is True

    def test_valid_categorical_parameter(self):
        """Test valid categorical parameter specification."""
        spec = ParameterSpec(
            type='categorical',
            values=['low', 'medium', 'high']
        )
        assert spec.type == 'categorical'
        assert len(spec.values) == 3

    def test_invalid_parameter_type(self):
        """Test that invalid parameter type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid parameter type"):
            ParameterSpec(type='invalid')

    def test_categorical_without_values(self):
        """Test that categorical parameter without values raises ValueError."""
        with pytest.raises(ValueError, match="must have values"):
            ParameterSpec(type='categorical', values=None)

    def test_int_without_min_max(self):
        """Test that int parameter without min/max raises ValueError."""
        with pytest.raises(ValueError, match="must have min_value and max_value"):
            ParameterSpec(type='int', min_value=None, max_value=None)

    def test_invalid_range(self):
        """Test that invalid range (min >= max) raises ValueError."""
        with pytest.raises(ValueError, match="min_value must be less than max_value"):
            ParameterSpec(type='int', min_value=10, max_value=5)


class TestOptimizationConfig:
    """Test OptimizationConfig dataclass."""

    @pytest.fixture
    def base_config(self):
        """Create base backtest config for testing."""
        return BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            regions=['KR'],
            initial_capital=100_000_000,
        )

    @pytest.fixture
    def parameter_space(self):
        """Create sample parameter space."""
        return {
            'kelly_multiplier': ParameterSpec(
                type='float',
                min_value=0.25,
                max_value=1.0,
                step=0.25
            ),
            'score_threshold': ParameterSpec(
                type='int',
                min_value=60,
                max_value=80,
                step=5
            ),
        }

    def test_valid_config(self, parameter_space, base_config):
        """Test valid optimization configuration."""
        config = OptimizationConfig(
            parameter_space=parameter_space,
            objective='sharpe_ratio',
            maximize=True,
            train_start_date=date(2023, 1, 1),
            train_end_date=date(2023, 6, 30),
            validation_start_date=date(2023, 7, 1),
            validation_end_date=date(2023, 12, 31),
            max_trials=100,
            n_jobs=4,
            base_config=base_config,
        )
        assert config.objective == 'sharpe_ratio'
        assert config.maximize is True
        assert config.n_jobs == 4

    def test_empty_parameter_space(self, base_config):
        """Test that empty parameter space raises ValueError."""
        with pytest.raises(ValueError, match="parameter_space cannot be empty"):
            OptimizationConfig(
                parameter_space={},
                train_start_date=date(2023, 1, 1),
                train_end_date=date(2023, 6, 30),
                validation_start_date=date(2023, 7, 1),
                validation_end_date=date(2023, 12, 31),
                base_config=base_config,
            )

    def test_invalid_objective(self, parameter_space, base_config):
        """Test that invalid objective raises ValueError."""
        with pytest.raises(ValueError, match="Invalid objective"):
            OptimizationConfig(
                parameter_space=parameter_space,
                objective='invalid_metric',
                train_start_date=date(2023, 1, 1),
                train_end_date=date(2023, 6, 30),
                validation_start_date=date(2023, 7, 1),
                validation_end_date=date(2023, 12, 31),
                base_config=base_config,
            )

    def test_missing_train_dates(self, parameter_space, base_config):
        """Test that missing train dates raises ValueError."""
        with pytest.raises(ValueError, match="train_start_date and train_end_date are required"):
            OptimizationConfig(
                parameter_space=parameter_space,
                train_start_date=None,
                train_end_date=None,
                validation_start_date=date(2023, 7, 1),
                validation_end_date=date(2023, 12, 31),
                base_config=base_config,
            )

    def test_overlapping_train_validation(self, parameter_space, base_config):
        """Test that overlapping train/validation periods raises ValueError."""
        with pytest.raises(ValueError, match="Training period must end before validation"):
            OptimizationConfig(
                parameter_space=parameter_space,
                train_start_date=date(2023, 1, 1),
                train_end_date=date(2023, 12, 31),
                validation_start_date=date(2023, 6, 1),
                validation_end_date=date(2023, 12, 31),
                base_config=base_config,
            )


class TestOptimizationTrial:
    """Test OptimizationTrial dataclass."""

    def test_trial_creation(self):
        """Test optimization trial creation."""
        metrics = PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.15,
            cagr=0.15,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            calmar_ratio=1.2,
            max_drawdown=-0.10,
            max_drawdown_duration_days=30,
            std_returns=0.10,
            downside_deviation=0.08,
            total_trades=10,
            win_rate=0.60,
            profit_factor=2.0,
            avg_win_pct=0.05,
            avg_loss_pct=-0.03,
            avg_win_loss_ratio=1.67,
            avg_holding_period_days=15.0,
            kelly_accuracy=0.80,
        )

        trial = OptimizationTrial(
            parameters={'kelly_multiplier': 0.5, 'score_threshold': 70},
            data_split='train',
            objective_value=1.5,
            metrics=metrics,
            trades=[],
            equity_curve=pd.Series([100000, 105000, 110000]),
            trial_number=1,
        )

        assert trial.parameters['kelly_multiplier'] == 0.5
        assert trial.data_split == 'train'
        assert trial.objective_value == 1.5
        assert trial.trial_number == 1
        assert isinstance(trial.timestamp, datetime)


class TestOptimizationResult:
    """Test OptimizationResult dataclass."""

    def test_result_creation(self):
        """Test optimization result creation."""
        result = OptimizationResult(
            best_parameters={'kelly_multiplier': 0.5, 'score_threshold': 70},
            train_objective=1.5,
            validation_objective=1.4,
            test_objective=1.3,
            parameter_importance={'kelly_multiplier': 0.7, 'score_threshold': 0.3},
            execution_time_seconds=300.0,
            optimization_method='grid',
        )

        assert result.best_parameters['kelly_multiplier'] == 0.5
        assert result.train_objective == 1.5
        assert result.validation_objective == 1.4
        assert result.test_objective == 1.3
        assert result.execution_time_seconds == 300.0

    def test_result_to_dict(self):
        """Test conversion to dictionary."""
        result = OptimizationResult(
            best_parameters={'kelly_multiplier': 0.5},
            train_objective=1.5,
            validation_objective=1.4,
        )

        result_dict = result.to_dict()

        assert 'best_parameters' in result_dict
        assert 'train_objective' in result_dict
        assert 'validation_objective' in result_dict
        assert 'n_trials' in result_dict


class TestParameterOptimizerBase:
    """Test ParameterOptimizer base class."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database manager."""
        return Mock(spec=SQLiteDatabaseManager)

    @pytest.fixture
    def base_config(self):
        """Create base backtest config."""
        return BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            regions=['KR'],
            initial_capital=100_000_000,
        )

    @pytest.fixture
    def opt_config(self, base_config):
        """Create optimization config."""
        parameter_space = {
            'kelly_multiplier': ParameterSpec(
                type='float',
                min_value=0.5,
                max_value=1.0,
                step=0.5
            ),
        }

        return OptimizationConfig(
            parameter_space=parameter_space,
            objective='sharpe_ratio',
            train_start_date=date(2023, 1, 1),
            train_end_date=date(2023, 6, 30),
            validation_start_date=date(2023, 7, 1),
            validation_end_date=date(2023, 12, 31),
            base_config=base_config,
        )

    def test_optimizer_initialization(self, opt_config, mock_db):
        """Test optimizer initialization."""
        # Create concrete subclass for testing
        class TestOptimizer(ParameterOptimizer):
            def optimize(self):
                pass

        optimizer = TestOptimizer(opt_config, mock_db, optimization_method='test')

        assert optimizer.config == opt_config
        assert optimizer.db == mock_db
        assert optimizer.optimization_method == 'test'
        assert len(optimizer.trials) == 0
        assert optimizer.best_trial is None

    def test_create_trial_config_train(self, opt_config, mock_db):
        """Test trial config creation for training data."""
        class TestOptimizer(ParameterOptimizer):
            def optimize(self):
                pass

        optimizer = TestOptimizer(opt_config, mock_db)

        parameters = {'kelly_multiplier': 0.5, 'score_threshold': 70}
        trial_config = optimizer._create_trial_config(parameters, 'train')

        assert trial_config.start_date == opt_config.train_start_date
        assert trial_config.end_date == opt_config.train_end_date
        assert trial_config.kelly_multiplier == 0.5
        assert trial_config.score_threshold == 70

    def test_create_trial_config_validation(self, opt_config, mock_db):
        """Test trial config creation for validation data."""
        class TestOptimizer(ParameterOptimizer):
            def optimize(self):
                pass

        optimizer = TestOptimizer(opt_config, mock_db)

        parameters = {'kelly_multiplier': 0.75}
        trial_config = optimizer._create_trial_config(parameters, 'validation')

        assert trial_config.start_date == opt_config.validation_start_date
        assert trial_config.end_date == opt_config.validation_end_date

    def test_calculate_objective_sharpe(self, opt_config, mock_db):
        """Test objective calculation for Sharpe ratio."""
        class TestOptimizer(ParameterOptimizer):
            def optimize(self):
                pass

        optimizer = TestOptimizer(opt_config, mock_db)

        metrics = PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.15,
            cagr=0.15,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            calmar_ratio=1.2,
            max_drawdown=-0.10,
            max_drawdown_duration_days=30,
            std_returns=0.10,
            downside_deviation=0.08,
            total_trades=10,
            win_rate=0.60,
            profit_factor=2.0,
            avg_win_pct=0.05,
            avg_loss_pct=-0.03,
            avg_win_loss_ratio=1.67,
            avg_holding_period_days=15.0,
            kelly_accuracy=0.80,
        )

        result = BacktestResult(
            config=opt_config.base_config,
            metrics=metrics,
            trades=[],
            equity_curve=pd.Series([100000, 110000, 115000]),
            pattern_metrics={},
            execution_time_seconds=10.0,
        )

        objective = optimizer._calculate_objective(result)
        assert objective == 1.5  # Sharpe ratio

    def test_calculate_objective_minimize(self, opt_config, mock_db):
        """Test objective calculation with minimize=False."""
        opt_config.maximize = False

        class TestOptimizer(ParameterOptimizer):
            def optimize(self):
                pass

        optimizer = TestOptimizer(opt_config, mock_db)

        metrics = PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.15,
            cagr=0.15,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            calmar_ratio=1.2,
            max_drawdown=-0.10,
            max_drawdown_duration_days=30,
            std_returns=0.10,
            downside_deviation=0.08,
            total_trades=10,
            win_rate=0.60,
            profit_factor=2.0,
            avg_win_pct=0.05,
            avg_loss_pct=-0.03,
            avg_win_loss_ratio=1.67,
            avg_holding_period_days=15.0,
            kelly_accuracy=0.80,
        )

        result = BacktestResult(
            config=opt_config.base_config,
            metrics=metrics,
            trades=[],
            equity_curve=pd.Series([100000, 110000, 115000]),
            pattern_metrics={},
            execution_time_seconds=10.0,
        )

        objective = optimizer._calculate_objective(result)
        assert objective == -1.5  # Negative for minimization


class TestGridSearchOptimizer:
    """Test GridSearchOptimizer."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database manager."""
        return Mock(spec=SQLiteDatabaseManager)

    @pytest.fixture
    def base_config(self):
        """Create base backtest config."""
        return BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            regions=['KR'],
            initial_capital=100_000_000,
        )

    def test_parameter_grid_generation_float(self, mock_db, base_config):
        """Test parameter grid generation for float parameters."""
        parameter_space = {
            'kelly_multiplier': ParameterSpec(
                type='float',
                min_value=0.25,
                max_value=0.75,
                step=0.25
            ),
        }

        opt_config = OptimizationConfig(
            parameter_space=parameter_space,
            train_start_date=date(2023, 1, 1),
            train_end_date=date(2023, 6, 30),
            validation_start_date=date(2023, 7, 1),
            validation_end_date=date(2023, 12, 31),
            base_config=base_config,
        )

        optimizer = GridSearchOptimizer(opt_config, mock_db)
        param_grid = optimizer._generate_parameter_grid()

        assert len(param_grid) == 3  # 0.25, 0.5, 0.75
        assert param_grid[0]['kelly_multiplier'] == 0.25
        assert param_grid[1]['kelly_multiplier'] == 0.5
        assert param_grid[2]['kelly_multiplier'] == 0.75

    def test_parameter_grid_generation_int(self, mock_db, base_config):
        """Test parameter grid generation for int parameters."""
        parameter_space = {
            'score_threshold': ParameterSpec(
                type='int',
                min_value=60,
                max_value=70,
                step=5
            ),
        }

        opt_config = OptimizationConfig(
            parameter_space=parameter_space,
            train_start_date=date(2023, 1, 1),
            train_end_date=date(2023, 6, 30),
            validation_start_date=date(2023, 7, 1),
            validation_end_date=date(2023, 12, 31),
            base_config=base_config,
        )

        optimizer = GridSearchOptimizer(opt_config, mock_db)
        param_grid = optimizer._generate_parameter_grid()

        assert len(param_grid) == 3  # 60, 65, 70
        assert all(isinstance(p['score_threshold'], int) for p in param_grid)

    def test_parameter_grid_generation_categorical(self, mock_db, base_config):
        """Test parameter grid generation for categorical parameters."""
        parameter_space = {
            'risk_level': ParameterSpec(
                type='categorical',
                values=['low', 'medium', 'high']
            ),
        }

        opt_config = OptimizationConfig(
            parameter_space=parameter_space,
            train_start_date=date(2023, 1, 1),
            train_end_date=date(2023, 6, 30),
            validation_start_date=date(2023, 7, 1),
            validation_end_date=date(2023, 12, 31),
            base_config=base_config,
        )

        optimizer = GridSearchOptimizer(opt_config, mock_db)
        param_grid = optimizer._generate_parameter_grid()

        assert len(param_grid) == 3
        assert param_grid[0]['risk_level'] == 'low'
        assert param_grid[1]['risk_level'] == 'medium'
        assert param_grid[2]['risk_level'] == 'high'

    def test_parameter_grid_generation_multiple(self, mock_db, base_config):
        """Test parameter grid generation with multiple parameters."""
        parameter_space = {
            'kelly_multiplier': ParameterSpec(
                type='float',
                min_value=0.5,
                max_value=1.0,
                step=0.5
            ),
            'score_threshold': ParameterSpec(
                type='int',
                min_value=65,
                max_value=75,
                step=5
            ),
        }

        opt_config = OptimizationConfig(
            parameter_space=parameter_space,
            train_start_date=date(2023, 1, 1),
            train_end_date=date(2023, 6, 30),
            validation_start_date=date(2023, 7, 1),
            validation_end_date=date(2023, 12, 31),
            base_config=base_config,
        )

        optimizer = GridSearchOptimizer(opt_config, mock_db)
        param_grid = optimizer._generate_parameter_grid()

        # 2 kelly × 3 threshold = 6 combinations
        assert len(param_grid) == 6

        # Verify all combinations exist
        kelly_values = {p['kelly_multiplier'] for p in param_grid}
        threshold_values = {p['score_threshold'] for p in param_grid}

        assert kelly_values == {0.5, 1.0}
        assert threshold_values == {65, 70, 75}


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
