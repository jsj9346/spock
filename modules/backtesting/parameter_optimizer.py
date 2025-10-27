"""
Parameter Optimizer

Purpose: Automated parameter tuning for trading strategies using optimization algorithms.

Key Features:
  - Grid search for exhaustive parameter exploration
  - Bayesian optimization for efficient exploration (optional)
  - Train/validation/test splitting to prevent overfitting
  - Parallel execution with ThreadPoolExecutor
  - Parameter importance analysis
  - Progress tracking and early stopping

Design Philosophy:
  - Prevent overfitting through proper validation methodology
  - Reproducible optimization runs (fixed random seed)
  - Pluggable optimization methods
  - Evidence-based parameter selection

Author: Spock Development Team
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import time
import json
import numpy as np
import pandas as pd

from .backtest_config import BacktestConfig, BacktestResult, Trade, PerformanceMetrics
from .backtest_engine import BacktestEngine
from modules.db_manager_sqlite import SQLiteDatabaseManager


logger = logging.getLogger(__name__)


# ============================================================================
# Parameter Specification
# ============================================================================

@dataclass
class ParameterSpec:
    """
    Parameter specification for optimization.

    Attributes:
        type: Parameter type ('int', 'float', 'categorical')
        values: List of values for categorical parameters
        min_value: Minimum value for int/float parameters
        max_value: Maximum value for int/float parameters
        step: Step size for grid search (int/float parameters)
        log_scale: Use log scale for Bayesian optimization (float only)
    """
    type: str  # 'int', 'float', 'categorical'
    values: Optional[List] = None  # For categorical
    min_value: Optional[float] = None  # For int/float
    max_value: Optional[float] = None  # For int/float
    step: Optional[float] = None  # For grid search
    log_scale: bool = False  # For Bayesian optimization

    def __post_init__(self):
        """Validate parameter specification."""
        if self.type not in ['int', 'float', 'categorical']:
            raise ValueError(f"Invalid parameter type: {self.type}")

        if self.type == 'categorical':
            if self.values is None or len(self.values) == 0:
                raise ValueError("Categorical parameter must have values")
        elif self.type in ['int', 'float']:
            if self.min_value is None or self.max_value is None:
                raise ValueError(f"{self.type} parameter must have min_value and max_value")
            if self.min_value >= self.max_value:
                raise ValueError("min_value must be less than max_value")


# ============================================================================
# Optimization Configuration
# ============================================================================

@dataclass
class OptimizationConfig:
    """
    Configuration for parameter optimization.

    Attributes:
        parameter_space: Dictionary of parameter names to ParameterSpec
        objective: Optimization objective ('sharpe_ratio', 'total_return', etc.)
        maximize: Whether to maximize objective (True) or minimize (False)
        train_start_date: Training data start date
        train_end_date: Training data end date
        validation_start_date: Validation data start date
        validation_end_date: Validation data end date
        test_start_date: Test data start date (optional)
        test_end_date: Test data end date (optional)
        max_trials: Maximum number of optimization trials
        n_jobs: Number of parallel workers
        random_seed: Random seed for reproducibility
        early_stopping_patience: Stop if no improvement for N trials (optional)
        base_config: Base backtest configuration
    """
    parameter_space: Dict[str, ParameterSpec]
    objective: str = "sharpe_ratio"
    maximize: bool = True
    train_start_date: date = None
    train_end_date: date = None
    validation_start_date: date = None
    validation_end_date: date = None
    test_start_date: Optional[date] = None
    test_end_date: Optional[date] = None
    max_trials: int = 100
    n_jobs: int = 4
    random_seed: int = 42
    early_stopping_patience: Optional[int] = None
    base_config: BacktestConfig = None

    def __post_init__(self):
        """Validate optimization configuration."""
        if not self.parameter_space:
            raise ValueError("parameter_space cannot be empty")

        valid_objectives = [
            'sharpe_ratio', 'sortino_ratio', 'calmar_ratio',
            'total_return', 'annualized_return', 'profit_factor'
        ]
        if self.objective not in valid_objectives:
            raise ValueError(f"Invalid objective: {self.objective}. Must be one of {valid_objectives}")

        if self.train_start_date is None or self.train_end_date is None:
            raise ValueError("train_start_date and train_end_date are required")

        if self.validation_start_date is None or self.validation_end_date is None:
            raise ValueError("validation_start_date and validation_end_date are required")

        if self.train_end_date >= self.validation_start_date:
            raise ValueError("Training period must end before validation period starts")

        if self.base_config is None:
            raise ValueError("base_config is required")


# ============================================================================
# Optimization Results
# ============================================================================

@dataclass
class OptimizationTrial:
    """
    Single optimization trial result.

    Attributes:
        parameters: Parameter values tested in this trial
        data_split: Data split used ('train', 'validation', 'test')
        objective_value: Objective function value
        metrics: Complete performance metrics from backtest
        trades: List of trades executed
        equity_curve: Portfolio value over time
        trial_number: Trial number in optimization sequence
        timestamp: When trial was executed
    """
    parameters: Dict[str, Any]
    data_split: str  # 'train', 'validation', 'test'
    objective_value: float
    metrics: PerformanceMetrics
    trades: List[Trade]
    equity_curve: pd.Series
    trial_number: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class OptimizationResult:
    """
    Complete optimization results.

    Attributes:
        best_parameters: Best parameter values found
        train_objective: Objective value on training data
        validation_objective: Objective value on validation data
        test_objective: Objective value on test data (optional)
        all_trials: List of all optimization trials
        parameter_importance: Parameter importance scores (0-1)
        execution_time_seconds: Total optimization time
        optimization_method: Optimization method used ('grid', 'bayesian', etc.)
    """
    best_parameters: Dict[str, Any]
    train_objective: float
    validation_objective: float
    test_objective: Optional[float] = None
    all_trials: List[OptimizationTrial] = field(default_factory=list)
    parameter_importance: Dict[str, float] = field(default_factory=dict)
    execution_time_seconds: float = 0.0
    optimization_method: str = 'grid'

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'best_parameters': self.best_parameters,
            'train_objective': self.train_objective,
            'validation_objective': self.validation_objective,
            'test_objective': self.test_objective,
            'n_trials': len(self.all_trials),
            'parameter_importance': self.parameter_importance,
            'execution_time_seconds': self.execution_time_seconds,
            'optimization_method': self.optimization_method,
        }


# ============================================================================
# Parameter Optimizer Base Class
# ============================================================================

class ParameterOptimizer(ABC):
    """
    Base class for parameter optimization.

    Attributes:
        config: Optimization configuration
        db: Database manager
        optimization_method: Optimization method ('grid', 'bayesian', etc.)
        trials: List of completed trials
        best_trial: Best trial found so far
    """

    def __init__(
        self,
        config: OptimizationConfig,
        db: SQLiteDatabaseManager,
        optimization_method: str = 'grid'
    ):
        """
        Initialize parameter optimizer.

        Args:
            config: Optimization configuration
            db: Database manager
            optimization_method: Optimization method identifier
        """
        self.config = config
        self.db = db
        self.optimization_method = optimization_method

        # Trial tracking
        self.trials: List[OptimizationTrial] = []
        self.best_trial: Optional[OptimizationTrial] = None

        # Progress tracking
        self.start_time: Optional[float] = None
        self.total_trials: int = 0
        self.completed_trials: int = 0

        # Set random seed for reproducibility
        np.random.seed(config.random_seed)

        logger.info(f"ParameterOptimizer initialized: method={optimization_method}, objective={config.objective}")

    @abstractmethod
    def optimize(self) -> OptimizationResult:
        """
        Run optimization and return results.

        Returns:
            OptimizationResult with best parameters and analysis
        """
        raise NotImplementedError("Subclass must implement optimize()")

    def _run_single_trial(
        self,
        parameters: Dict[str, Any],
        data_split: str = 'train'
    ) -> OptimizationTrial:
        """
        Run a single backtest trial with given parameters.

        Args:
            parameters: Parameter values to test
            data_split: Data split to use ('train', 'validation', 'test')

        Returns:
            OptimizationTrial with results
        """
        # Create backtest config with trial parameters
        trial_config = self._create_trial_config(parameters, data_split)

        # Run backtest
        engine = BacktestEngine(trial_config, self.db)
        result = engine.run()

        # Extract objective value
        objective_value = self._calculate_objective(result)

        # Create trial record
        trial = OptimizationTrial(
            parameters=parameters.copy(),
            data_split=data_split,
            objective_value=objective_value,
            metrics=result.metrics,
            trades=result.trades,
            equity_curve=result.equity_curve,
            trial_number=self.completed_trials + 1,
        )

        return trial

    def _create_trial_config(
        self,
        parameters: Dict[str, Any],
        data_split: str
    ) -> BacktestConfig:
        """
        Create BacktestConfig for trial with parameter overrides.

        Args:
            parameters: Parameter values to override
            data_split: Data split ('train', 'validation', 'test')

        Returns:
            BacktestConfig with parameters applied
        """
        # Get date range for data split
        if data_split == 'train':
            start_date = self.config.train_start_date
            end_date = self.config.train_end_date
        elif data_split == 'validation':
            start_date = self.config.validation_start_date
            end_date = self.config.validation_end_date
        elif data_split == 'test':
            if self.config.test_start_date is None:
                raise ValueError("Test dates not configured")
            start_date = self.config.test_start_date
            end_date = self.config.test_end_date
        else:
            raise ValueError(f"Invalid data_split: {data_split}")

        # Create new config with parameter overrides
        trial_config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            regions=self.config.base_config.regions,
            tickers=self.config.base_config.tickers,
            initial_capital=self.config.base_config.initial_capital,
            commission_rate=self.config.base_config.commission_rate,
            slippage_bps=self.config.base_config.slippage_bps,
            cash_reserve=self.config.base_config.cash_reserve,
            **parameters  # Apply parameter overrides
        )

        return trial_config

    def _calculate_objective(self, result: BacktestResult) -> float:
        """
        Calculate objective function value from backtest result.

        Args:
            result: Backtest result

        Returns:
            Objective value (higher is better if maximize=True)
        """
        objective_map = {
            'sharpe_ratio': result.metrics.sharpe_ratio,
            'sortino_ratio': result.metrics.sortino_ratio,
            'calmar_ratio': result.metrics.calmar_ratio,
            'total_return': result.metrics.total_return,
            'annualized_return': result.metrics.annualized_return,
            'profit_factor': result.metrics.profit_factor,
        }

        if self.config.objective not in objective_map:
            raise ValueError(f"Unknown objective: {self.config.objective}")

        value = objective_map[self.config.objective]

        # Apply maximize/minimize
        return value if self.config.maximize else -value

    def _validate_best_trial(self) -> OptimizationTrial:
        """
        Run validation on best trial parameters.

        Returns:
            OptimizationTrial with validation results
        """
        if self.best_trial is None:
            raise ValueError("No best trial found")

        logger.info(f"Validating best trial: {self.best_trial.parameters}")

        validation_trial = self._run_single_trial(
            parameters=self.best_trial.parameters,
            data_split='validation'
        )

        return validation_trial

    def _log_progress(self):
        """Log optimization progress."""
        if self.start_time is None:
            return

        elapsed = time.time() - self.start_time
        progress_pct = (self.completed_trials / self.total_trials * 100) if self.total_trials > 0 else 0
        trials_per_sec = self.completed_trials / elapsed if elapsed > 0 else 0
        eta_seconds = (self.total_trials - self.completed_trials) / trials_per_sec if trials_per_sec > 0 else 0

        logger.info(
            f"Progress: {self.completed_trials}/{self.total_trials} trials ({progress_pct:.1f}%), "
            f"best={self.best_trial.objective_value:.4f}, "
            f"eta={eta_seconds/60:.1f}min"
        )

    def save_results(self, result: OptimizationResult, filepath: str):
        """
        Save optimization results to JSON file.

        Args:
            result: Optimization result
            filepath: Output file path
        """
        result_dict = result.to_dict()

        with open(filepath, 'w') as f:
            json.dump(result_dict, f, indent=2, default=str)

        logger.info(f"Results saved to: {filepath}")

    def _calculate_parameter_importance(self) -> Dict[str, float]:
        """
        Calculate parameter importance using variance-based analysis.

        Returns:
            Dictionary of parameter names to importance scores (0-1)
        """
        if len(self.trials) < 2:
            return {name: 0.0 for name in self.config.parameter_space.keys()}

        param_names = list(self.config.parameter_space.keys())
        importance = {}

        # Calculate total variance
        objective_values = [t.objective_value for t in self.trials]
        total_variance = np.var(objective_values)

        if total_variance == 0:
            return {name: 0.0 for name in param_names}

        # Calculate variance explained by each parameter
        for param_name in param_names:
            # Group trials by parameter value
            param_groups = {}
            for trial in self.trials:
                value = trial.parameters[param_name]
                if value not in param_groups:
                    param_groups[value] = []
                param_groups[value].append(trial.objective_value)

            # Calculate between-group variance
            group_means = [np.mean(values) for values in param_groups.values()]
            between_variance = np.var(group_means) if len(group_means) > 1 else 0

            # Importance is ratio of between-group to total variance
            importance[param_name] = between_variance / total_variance

        # Normalize to sum to 1
        total_importance = sum(importance.values())
        if total_importance > 0:
            importance = {k: v / total_importance for k, v in importance.items()}

        return importance
