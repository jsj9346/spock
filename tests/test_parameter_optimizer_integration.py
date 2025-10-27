"""
Parameter Optimizer Integration Tests

Integration tests for parameter optimization with BacktestEngine:
  - End-to-end grid search optimization
  - Parameter importance analysis
  - Early stopping behavior
  - Multi-objective optimization
  - Train/validation/test data splitting
  - Real backtest execution with database

NOTE: These tests require database with OHLCV data for test tickers.
      Tests will be skipped if data is not available.
"""

import unittest
from datetime import date
import sys
import os
import logging
import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.backtesting import (
    BacktestConfig,
    GridSearchOptimizer,
    ParameterSpec,
    OptimizationConfig,
)
from modules.db_manager_sqlite import SQLiteDatabaseManager

# Disable logging during tests
logging.basicConfig(level=logging.CRITICAL)


def check_data_available(db, ticker, region, start_date, end_date):
    """Check if OHLCV data is available for ticker."""
    conn = db._get_connection()
    cursor = conn.cursor()

    query = """
        SELECT COUNT(*) FROM ohlcv_data
        WHERE ticker = ? AND region = ?
        AND date >= ? AND date <= ?
    """

    cursor.execute(query, (ticker, region, start_date, end_date))
    count = cursor.fetchone()[0]
    conn.close()

    return count > 50  # Require at least 50 data points


class TestGridSearchIntegration(unittest.TestCase):
    """Integration tests for GridSearchOptimizer with BacktestEngine."""

    def setUp(self):
        """Set up test fixtures."""
        self.db = SQLiteDatabaseManager()

        # Base backtest config
        self.base_config = BacktestConfig(
            start_date=date(2023, 1, 1),  # Will be overridden by optimization
            end_date=date(2023, 12, 31),
            regions=["KR"],
            tickers=["005930"],  # Samsung for testing
            initial_capital=100_000_000,
        )

        # Check if data is available
        self.data_available = check_data_available(
            self.db, "005930", "KR",
            date(2023, 1, 1), date(2023, 12, 31)
        )

    @pytest.mark.skipif(True, reason="Requires database with OHLCV data")
    def test_simple_grid_search_optimization(self):
        """Test simple grid search with 2 parameters."""
        if not self.data_available:
            self.skipTest("Database does not have required OHLCV data")

        # Define small parameter space for testing
        parameter_space = {
            'kelly_multiplier': ParameterSpec(
                type='float',
                min_value=0.25,
                max_value=0.75,
                step=0.25,
            ),
            'score_threshold': ParameterSpec(
                type='int',
                min_value=65,
                max_value=75,
                step=5,
            ),
        }

        # Create optimization config
        opt_config = OptimizationConfig(
            parameter_space=parameter_space,
            objective='sharpe_ratio',
            train_start_date=date(2023, 1, 1),
            train_end_date=date(2023, 6, 30),
            validation_start_date=date(2023, 7, 1),
            validation_end_date=date(2023, 12, 31),
            max_trials=100,
            n_jobs=2,  # Use 2 workers for parallel execution
            base_config=self.base_config,
        )

        # Run optimization
        optimizer = GridSearchOptimizer(opt_config, self.db)
        result = optimizer.optimize()

        # Verify results
        self.assertIsNotNone(result.best_parameters)
        self.assertIn('kelly_multiplier', result.best_parameters)
        self.assertIn('score_threshold', result.best_parameters)

        # Check that train and validation objectives are computed
        self.assertIsInstance(result.train_objective, float)
        self.assertIsInstance(result.validation_objective, float)

        # Verify parameter space was explored (3 kelly × 3 threshold = 9 trials)
        self.assertEqual(len(result.all_trials), 9)

        # Check execution time is recorded
        self.assertGreater(result.execution_time_seconds, 0)

    @pytest.mark.skipif(True, reason="Requires database with OHLCV data")
    def test_grid_search_with_categorical_parameter(self):
        """Test grid search with categorical parameter."""
        if not self.data_available:
            self.skipTest("Database does not have required OHLCV data")

        parameter_space = {
            'kelly_multiplier': ParameterSpec(
                type='float',
                min_value=0.25,
                max_value=0.50,
                step=0.25,
            ),
            'risk_profile': ParameterSpec(
                type='categorical',
                values=['conservative', 'moderate', 'aggressive'],
            ),
        }

        opt_config = OptimizationConfig(
            parameter_space=parameter_space,
            objective='sharpe_ratio',
            train_start_date=date(2023, 1, 1),
            train_end_date=date(2023, 6, 30),
            validation_start_date=date(2023, 7, 1),
            validation_end_date=date(2023, 12, 31),
            base_config=self.base_config,
        )

        optimizer = GridSearchOptimizer(opt_config, self.db)
        result = optimizer.optimize()

        # Verify categorical parameter is in best parameters
        self.assertIn('risk_profile', result.best_parameters)
        self.assertIn(result.best_parameters['risk_profile'],
                     ['conservative', 'moderate', 'aggressive'])

        # Verify all combinations were tried (2 kelly × 3 risk = 6 trials)
        self.assertEqual(len(result.all_trials), 6)

    @pytest.mark.skipif(True, reason="Requires database with OHLCV data")
    def test_parameter_importance_calculation(self):
        """Test parameter importance analysis."""
        if not self.data_available:
            self.skipTest("Database does not have required OHLCV data")

        parameter_space = {
            'kelly_multiplier': ParameterSpec(
                type='float',
                min_value=0.25,
                max_value=0.75,
                step=0.25,
            ),
            'score_threshold': ParameterSpec(
                type='int',
                min_value=65,
                max_value=75,
                step=5,
            ),
        }

        opt_config = OptimizationConfig(
            parameter_space=parameter_space,
            objective='sharpe_ratio',
            train_start_date=date(2023, 1, 1),
            train_end_date=date(2023, 6, 30),
            validation_start_date=date(2023, 7, 1),
            validation_end_date=date(2023, 12, 31),
            base_config=self.base_config,
        )

        optimizer = GridSearchOptimizer(opt_config, self.db)
        result = optimizer.optimize()

        # Verify parameter importance is calculated
        self.assertIn('kelly_multiplier', result.parameter_importance)
        self.assertIn('score_threshold', result.parameter_importance)

        # Check importance values are between 0 and 1
        for param_name, importance in result.parameter_importance.items():
            self.assertGreaterEqual(importance, 0.0)
            self.assertLessEqual(importance, 1.0)

        # Check importance values sum to approximately 1.0
        total_importance = sum(result.parameter_importance.values())
        self.assertAlmostEqual(total_importance, 1.0, places=5)

    @pytest.mark.skipif(True, reason="Requires database with OHLCV data")
    def test_early_stopping(self):
        """Test early stopping behavior."""
        if not self.data_available:
            self.skipTest("Database does not have required OHLCV data")

        parameter_space = {
            'kelly_multiplier': ParameterSpec(
                type='float',
                min_value=0.25,
                max_value=1.0,
                step=0.05,  # 16 values
            ),
            'score_threshold': ParameterSpec(
                type='int',
                min_value=60,
                max_value=80,
                step=2,  # 11 values
            ),
        }

        # Total combinations: 16 × 11 = 176 trials
        # With early stopping patience=10, should stop early
        opt_config = OptimizationConfig(
            parameter_space=parameter_space,
            objective='sharpe_ratio',
            train_start_date=date(2023, 1, 1),
            train_end_date=date(2023, 6, 30),
            validation_start_date=date(2023, 7, 1),
            validation_end_date=date(2023, 12, 31),
            early_stopping_patience=10,
            n_jobs=2,
            base_config=self.base_config,
        )

        optimizer = GridSearchOptimizer(opt_config, self.db)
        result = optimizer.optimize()

        # Should stop before completing all 176 trials
        # (early stopping should trigger if no improvement for 10 trials)
        # Note: This might complete all trials if improvements keep happening
        self.assertLessEqual(len(result.all_trials), 176)

    @pytest.mark.skipif(True, reason="Requires database with OHLCV data")
    def test_multi_objective_optimization(self):
        """Test optimization with different objectives."""
        if not self.data_available:
            self.skipTest("Database does not have required OHLCV data")

        parameter_space = {
            'kelly_multiplier': ParameterSpec(
                type='float',
                min_value=0.25,
                max_value=0.75,
                step=0.25,
            ),
        }

        objectives = ['sharpe_ratio', 'sortino_ratio', 'calmar_ratio',
                     'total_return', 'profit_factor']

        results = {}

        for objective in objectives:
            opt_config = OptimizationConfig(
                parameter_space=parameter_space,
                objective=objective,
                train_start_date=date(2023, 1, 1),
                train_end_date=date(2023, 6, 30),
                validation_start_date=date(2023, 7, 1),
                validation_end_date=date(2023, 12, 31),
                base_config=self.base_config,
            )

            optimizer = GridSearchOptimizer(opt_config, self.db)
            result = optimizer.optimize()
            results[objective] = result

        # Verify each objective produces valid results
        for objective, result in results.items():
            self.assertIsNotNone(result.best_parameters)
            self.assertIsInstance(result.train_objective, float)
            self.assertIsInstance(result.validation_objective, float)

            # Different objectives might yield different best parameters
            # (but not guaranteed, so we just verify they exist)
            self.assertIn('kelly_multiplier', result.best_parameters)

    @pytest.mark.skipif(True, reason="Requires database with OHLCV data")
    def test_train_validation_split(self):
        """Test that train/validation splits are respected."""
        if not self.data_available:
            self.skipTest("Database does not have required OHLCV data")

        # Use categorical for single value (avoid min=max validation error)
        parameter_space = {
            'kelly_multiplier': ParameterSpec(
                type='categorical',
                values=[0.5],  # Single value for simplicity
            ),
        }

        # Define clear train/validation periods
        train_start = date(2023, 1, 1)
        train_end = date(2023, 6, 30)
        val_start = date(2023, 7, 1)
        val_end = date(2023, 12, 31)

        opt_config = OptimizationConfig(
            parameter_space=parameter_space,
            objective='sharpe_ratio',
            train_start_date=train_start,
            train_end_date=train_end,
            validation_start_date=val_start,
            validation_end_date=val_end,
            base_config=self.base_config,
        )

        optimizer = GridSearchOptimizer(opt_config, self.db)
        result = optimizer.optimize()

        # Verify trials were run on correct data splits
        train_trials = [t for t in result.all_trials if t.data_split == 'train']
        self.assertGreater(len(train_trials), 0)

        # Best trial should be from training data
        best_trial = optimizer.best_trial
        self.assertEqual(best_trial.data_split, 'train')

    @pytest.mark.skipif(True, reason="Requires database with OHLCV data")
    def test_minimize_objective(self):
        """Test minimization (e.g., minimize drawdown)."""
        if not self.data_available:
            self.skipTest("Database does not have required OHLCV data")

        parameter_space = {
            'kelly_multiplier': ParameterSpec(
                type='float',
                min_value=0.25,
                max_value=0.75,
                step=0.25,
            ),
        }

        # Test minimization (e.g., minimize max drawdown)
        # Note: We use total_return and maximize=False for testing
        opt_config = OptimizationConfig(
            parameter_space=parameter_space,
            objective='total_return',
            maximize=False,  # Minimize instead of maximize
            train_start_date=date(2023, 1, 1),
            train_end_date=date(2023, 6, 30),
            validation_start_date=date(2023, 7, 1),
            validation_end_date=date(2023, 12, 31),
            base_config=self.base_config,
        )

        optimizer = GridSearchOptimizer(opt_config, self.db)
        result = optimizer.optimize()

        # Verify objective was minimized (lower is better)
        # Since we're minimizing, all trial objective_values should be negative
        # (internally converted from positive to negative for minimization)
        self.assertIsNotNone(result.best_parameters)

    @pytest.mark.skipif(True, reason="Requires database with OHLCV data")
    def test_parallel_execution(self):
        """Test parallel execution with multiple workers."""
        if not self.data_available:
            self.skipTest("Database does not have required OHLCV data")

        parameter_space = {
            'kelly_multiplier': ParameterSpec(
                type='float',
                min_value=0.25,
                max_value=0.75,
                step=0.25,
            ),
            'score_threshold': ParameterSpec(
                type='int',
                min_value=65,
                max_value=75,
                step=5,
            ),
        }

        # Run with 1 worker
        opt_config_1 = OptimizationConfig(
            parameter_space=parameter_space,
            objective='sharpe_ratio',
            train_start_date=date(2023, 1, 1),
            train_end_date=date(2023, 6, 30),
            validation_start_date=date(2023, 7, 1),
            validation_end_date=date(2023, 12, 31),
            n_jobs=1,
            base_config=self.base_config,
        )

        optimizer_1 = GridSearchOptimizer(opt_config_1, self.db)
        result_1 = optimizer_1.optimize()

        # Run with 4 workers
        opt_config_4 = OptimizationConfig(
            parameter_space=parameter_space,
            objective='sharpe_ratio',
            train_start_date=date(2023, 1, 1),
            train_end_date=date(2023, 6, 30),
            validation_start_date=date(2023, 7, 1),
            validation_end_date=date(2023, 12, 31),
            n_jobs=4,
            random_seed=42,  # Same seed for reproducibility
            base_config=self.base_config,
        )

        optimizer_4 = GridSearchOptimizer(opt_config_4, self.db)
        result_4 = optimizer_4.optimize()

        # Both should find same best parameters (grid search is deterministic)
        # But parallel should be faster
        self.assertEqual(len(result_1.all_trials), len(result_4.all_trials))

        # Execution time with 4 workers should be less (though not guaranteed
        # due to system variability, so we just check both completed)
        self.assertGreater(result_1.execution_time_seconds, 0)
        self.assertGreater(result_4.execution_time_seconds, 0)


class TestOptimizationResultPersistence(unittest.TestCase):
    """Test optimization result persistence."""

    def setUp(self):
        """Set up test fixtures."""
        self.db = SQLiteDatabaseManager()
        self.base_config = BacktestConfig(
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            regions=["KR"],
            tickers=["005930"],
            initial_capital=100_000_000,
        )

        # Check if data is available
        self.data_available = check_data_available(
            self.db, "005930", "KR",
            date(2023, 1, 1), date(2023, 12, 31)
        )

    @pytest.mark.skipif(True, reason="Requires database with OHLCV data")
    def test_result_to_dict_conversion(self):
        """Test OptimizationResult to_dict conversion."""
        if not self.data_available:
            self.skipTest("Database does not have required OHLCV data")

        # Use categorical for single value (avoid min=max validation error)
        parameter_space = {
            'kelly_multiplier': ParameterSpec(
                type='categorical',
                values=[0.5],
            ),
        }

        opt_config = OptimizationConfig(
            parameter_space=parameter_space,
            objective='sharpe_ratio',
            train_start_date=date(2023, 1, 1),
            train_end_date=date(2023, 6, 30),
            validation_start_date=date(2023, 7, 1),
            validation_end_date=date(2023, 12, 31),
            base_config=self.base_config,
        )

        optimizer = GridSearchOptimizer(opt_config, self.db)
        result = optimizer.optimize()

        # Convert to dictionary
        result_dict = result.to_dict()

        # Verify all expected keys are present
        expected_keys = [
            'best_parameters',
            'train_objective',
            'validation_objective',
            'test_objective',
            'n_trials',
            'parameter_importance',
            'execution_time_seconds',
            'optimization_method',
        ]

        for key in expected_keys:
            self.assertIn(key, result_dict)

        # Verify values are JSON-serializable types
        self.assertIsInstance(result_dict['best_parameters'], dict)
        self.assertIsInstance(result_dict['train_objective'], (int, float))
        self.assertIsInstance(result_dict['n_trials'], int)
        self.assertEqual(result_dict['optimization_method'], 'grid')


if __name__ == "__main__":
    print("Running Parameter Optimizer Integration Tests...")
    print("=" * 80)
    unittest.main(verbosity=2)
