# Spock Backtesting Module - Advanced Features Design

**Version**: 1.0
**Date**: 2025-10-17
**Author**: Spock Development Team
**Status**: Design Phase

## Executive Summary

This document specifies the design for two advanced features to enhance the Spock backtesting module:

1. **ParameterOptimizer**: Automated parameter tuning using grid search and Bayesian optimization
2. **TransactionCostModel**: Realistic transaction cost modeling including slippage and market impact

These features will enable power users to:
- Systematically optimize strategy parameters for maximum risk-adjusted returns
- Model realistic trading costs for accurate backtest performance estimation
- Prevent overfitting through proper validation methodologies
- Make informed decisions about strategy deployment

---

## Table of Contents

1. [Requirements Analysis](#1-requirements-analysis)
2. [ParameterOptimizer Design](#2-parameteroptimizer-design)
3. [TransactionCostModel Design](#3-transactioncostmodel-design)
4. [Integration Architecture](#4-integration-architecture)
5. [Implementation Roadmap](#5-implementation-roadmap)
6. [Testing Strategy](#6-testing-strategy)
7. [Performance Considerations](#7-performance-considerations)

---

## 1. Requirements Analysis

### 1.1 Business Requirements

**ParameterOptimizer**:
- BR1: Systematically find optimal strategy parameters
- BR2: Prevent overfitting through train/validation/test splits
- BR3: Support multiple optimization objectives (Sharpe ratio, total return, max drawdown)
- BR4: Provide visualization of parameter sensitivity
- BR5: Export optimization results for reproducibility

**TransactionCostModel**:
- BR6: Model realistic trading costs (commission, slippage, market impact)
- BR7: Support different cost models for different markets and order sizes
- BR8: Provide pre-configured models for Korean, US, and other markets
- BR9: Allow custom cost model definition
- BR10: Track cost metrics separately in backtest results

### 1.2 Technical Requirements

**ParameterOptimizer**:
- TR1: Support grid search for exhaustive exploration
- TR2: Support Bayesian optimization for efficient exploration
- TR3: Parallel execution of backtest runs
- TR4: Progress tracking and early stopping
- TR5: Walk-forward optimization support

**TransactionCostModel**:
- TR6: Pluggable cost model architecture
- TR7: Time-dependent cost modeling (market open/close volatility)
- TR8: Order size-dependent market impact
- TR9: Configurable slippage models (fixed, linear, sqrt)
- TR10: Integration with PortfolioSimulator

### 1.3 Constraints

- C1: Must maintain event-driven architecture (no look-ahead bias)
- C2: Must work with existing BacktestEngine without breaking changes
- C3: Optimization runs must be reproducible
- C4: Memory usage must scale reasonably with parameter space size
- C5: Support both single-region and multi-region backtests

---

## 2. ParameterOptimizer Design

### 2.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     ParameterOptimizer                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐ │
│  │  Grid Search   │  │    Bayesian    │  │  Walk-Forward    │ │
│  │    Engine      │  │  Optimization  │  │   Optimizer      │ │
│  └────────┬───────┘  └───────┬────────┘  └────────┬─────────┘ │
│           │                   │                     │            │
│           └───────────────────┴─────────────────────┘            │
│                              │                                   │
│                   ┌──────────▼──────────┐                       │
│                   │  Optimization Core  │                       │
│                   │  - Objective calc   │                       │
│                   │  - Validation split │                       │
│                   │  - Result tracking  │                       │
│                   └──────────┬──────────┘                       │
│                              │                                   │
│           ┌──────────────────┴──────────────────┐              │
│           ▼                                      ▼               │
│  ┌────────────────┐                   ┌────────────────┐       │
│  │ BacktestEngine │◄──────────────────│ ParallelRunner │       │
│  │   (existing)   │                   │  (ThreadPool)  │       │
│  └────────────────┘                   └────────────────┘       │
│           │                                      │               │
│           ▼                                      ▼               │
│  ┌────────────────────────────────────────────────────────┐   │
│  │            OptimizationResult                           │   │
│  │  - Best parameters                                      │   │
│  │  - All trials history                                   │   │
│  │  - Parameter sensitivity analysis                       │   │
│  │  - Validation metrics                                   │   │
│  └────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Core Classes

#### 2.2.1 ParameterOptimizer (Base Class)

```python
@dataclass
class OptimizationConfig:
    """Configuration for parameter optimization."""

    # Parameter space definition
    parameter_space: Dict[str, ParameterSpec]

    # Optimization objective
    objective: str = "sharpe_ratio"  # sharpe_ratio, total_return, calmar_ratio
    maximize: bool = True

    # Data splitting
    train_start_date: date
    train_end_date: date
    validation_start_date: date
    validation_end_date: date
    test_start_date: Optional[date] = None
    test_end_date: Optional[date] = None

    # Execution settings
    max_trials: int = 100
    n_jobs: int = 4  # Parallel workers
    random_seed: int = 42
    early_stopping_patience: Optional[int] = None

    # Base backtest config
    base_config: BacktestConfig

    # Walk-forward settings (optional)
    walk_forward_enabled: bool = False
    walk_forward_window_days: int = 180
    walk_forward_step_days: int = 30


@dataclass
class ParameterSpec:
    """Parameter specification for optimization."""

    type: str  # int, float, categorical
    values: Optional[List] = None  # For categorical
    min_value: Optional[float] = None  # For int/float
    max_value: Optional[float] = None  # For int/float
    step: Optional[float] = None  # For grid search
    log_scale: bool = False  # For Bayesian optimization


class ParameterOptimizer:
    """
    Base class for parameter optimization.

    Attributes:
        config: Optimization configuration
        db: Database manager
        optimization_method: 'grid', 'bayesian', 'walk_forward'
    """

    def __init__(
        self,
        config: OptimizationConfig,
        db: SQLiteDatabaseManager,
        optimization_method: str = 'grid'
    ):
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
            data_split: 'train', 'validation', or 'test'

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
            parameters=parameters,
            data_split=data_split,
            objective_value=objective_value,
            metrics=result.metrics,
            trades=result.trades,
            equity_curve=result.equity_curve,
        )

        return trial

    def _create_trial_config(
        self,
        parameters: Dict[str, Any],
        data_split: str
    ) -> BacktestConfig:
        """Create BacktestConfig for trial with parameter overrides."""
        # Get date range for data split
        if data_split == 'train':
            start_date = self.config.train_start_date
            end_date = self.config.train_end_date
        elif data_split == 'validation':
            start_date = self.config.validation_start_date
            end_date = self.config.validation_end_date
        elif data_split == 'test':
            start_date = self.config.test_start_date
            end_date = self.config.test_end_date
        else:
            raise ValueError(f"Invalid data_split: {data_split}")

        # Create config with parameter overrides
        trial_config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            regions=self.config.base_config.regions,
            tickers=self.config.base_config.tickers,
            initial_capital=self.config.base_config.initial_capital,
            **parameters  # Override with trial parameters
        )

        return trial_config

    def _calculate_objective(self, result: BacktestResult) -> float:
        """Calculate objective function value from backtest result."""
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
        """Run validation on best trial parameters."""
        if self.best_trial is None:
            raise ValueError("No best trial found")

        validation_trial = self._run_single_trial(
            parameters=self.best_trial.parameters,
            data_split='validation'
        )

        return validation_trial

    def save_results(self, result: OptimizationResult, filepath: str):
        """Save optimization results to file."""
        import json

        result_dict = {
            'optimization_method': self.optimization_method,
            'objective': self.config.objective,
            'best_parameters': result.best_parameters,
            'train_objective': result.train_objective,
            'validation_objective': result.validation_objective,
            'test_objective': result.test_objective,
            'n_trials': len(self.trials),
            'execution_time_seconds': result.execution_time_seconds,
            'parameter_importance': result.parameter_importance,
        }

        with open(filepath, 'w') as f:
            json.dump(result_dict, f, indent=2, default=str)
```

#### 2.2.2 GridSearchOptimizer

```python
class GridSearchOptimizer(ParameterOptimizer):
    """
    Grid search optimizer for exhaustive parameter exploration.

    Grid search tests all combinations of parameter values.
    Best for small parameter spaces (<1000 combinations).
    """

    def __init__(self, config: OptimizationConfig, db: SQLiteDatabaseManager):
        super().__init__(config, db, optimization_method='grid')

    def optimize(self) -> OptimizationResult:
        """
        Run grid search optimization.

        Returns:
            OptimizationResult with best parameters
        """
        self.start_time = time.time()

        # Generate parameter grid
        param_grid = self._generate_parameter_grid()
        self.total_trials = len(param_grid)

        logger.info(f"Grid search: {self.total_trials} parameter combinations")

        # Run trials in parallel
        with ThreadPoolExecutor(max_workers=self.config.n_jobs) as executor:
            futures = [
                executor.submit(self._run_single_trial, params, 'train')
                for params in param_grid
            ]

            for future in as_completed(futures):
                trial = future.result()
                self.trials.append(trial)
                self.completed_trials += 1

                # Update best trial
                if self.best_trial is None or \
                   trial.objective_value > self.best_trial.objective_value:
                    self.best_trial = trial

                # Progress logging
                if self.completed_trials % 10 == 0:
                    self._log_progress()

        # Validate best parameters
        validation_trial = self._validate_best_trial()

        # Create result
        execution_time = time.time() - self.start_time
        result = OptimizationResult(
            best_parameters=self.best_trial.parameters,
            train_objective=self.best_trial.objective_value,
            validation_objective=validation_trial.objective_value,
            all_trials=self.trials,
            parameter_importance=self._calculate_parameter_importance(),
            execution_time_seconds=execution_time,
        )

        return result

    def _generate_parameter_grid(self) -> List[Dict[str, Any]]:
        """Generate all parameter combinations for grid search."""
        from itertools import product

        # Extract parameter values
        param_names = []
        param_values = []

        for param_name, param_spec in self.config.parameter_space.items():
            param_names.append(param_name)

            if param_spec.type == 'categorical':
                param_values.append(param_spec.values)
            elif param_spec.type in ['int', 'float']:
                # Generate grid points
                if param_spec.step is None:
                    raise ValueError(f"step required for {param_name}")

                values = []
                current = param_spec.min_value
                while current <= param_spec.max_value:
                    values.append(current)
                    current += param_spec.step

                param_values.append(values)
            else:
                raise ValueError(f"Unknown parameter type: {param_spec.type}")

        # Generate all combinations
        param_grid = []
        for combination in product(*param_values):
            params = dict(zip(param_names, combination))
            param_grid.append(params)

        return param_grid

    def _calculate_parameter_importance(self) -> Dict[str, float]:
        """
        Calculate parameter importance using variance-based analysis.

        Returns:
            Dictionary of parameter names to importance scores (0-1)
        """
        import numpy as np

        # Extract data
        param_names = list(self.config.parameter_space.keys())

        # Calculate variance explained by each parameter
        importance = {}
        total_variance = np.var([t.objective_value for t in self.trials])

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
            between_variance = np.var(group_means)

            # Importance is ratio of between-group to total variance
            importance[param_name] = between_variance / total_variance if total_variance > 0 else 0

        # Normalize to sum to 1
        total_importance = sum(importance.values())
        if total_importance > 0:
            importance = {k: v / total_importance for k, v in importance.items()}

        return importance
```

#### 2.2.3 BayesianOptimizer

```python
class BayesianOptimizer(ParameterOptimizer):
    """
    Bayesian optimization using Gaussian Process.

    Bayesian optimization efficiently explores parameter space
    by modeling the objective function and selecting promising
    points to evaluate next.

    Best for large parameter spaces (>1000 combinations) or
    expensive objective functions.

    Note: Requires scikit-optimize (skopt) library.
    """

    def __init__(self, config: OptimizationConfig, db: SQLiteDatabaseManager):
        super().__init__(config, db, optimization_method='bayesian')

        try:
            from skopt import gp_minimize
            from skopt.space import Real, Integer, Categorical
            self.gp_minimize = gp_minimize
            self.space_classes = (Real, Integer, Categorical)
        except ImportError:
            raise ImportError(
                "scikit-optimize required for Bayesian optimization. "
                "Install with: pip install scikit-optimize"
            )

    def optimize(self) -> OptimizationResult:
        """
        Run Bayesian optimization.

        Returns:
            OptimizationResult with best parameters
        """
        self.start_time = time.time()

        # Create search space
        search_space = self._create_search_space()
        param_names = list(self.config.parameter_space.keys())

        # Define objective function wrapper
        def objective_func(param_values):
            params = dict(zip(param_names, param_values))
            trial = self._run_single_trial(params, 'train')
            self.trials.append(trial)

            # Update best trial
            if self.best_trial is None or \
               trial.objective_value > self.best_trial.objective_value:
                self.best_trial = trial

            # Progress logging
            self.completed_trials += 1
            if self.completed_trials % 5 == 0:
                self._log_progress()

            # Return negative for minimization
            return -trial.objective_value

        # Run Bayesian optimization
        logger.info(f"Bayesian optimization: {self.config.max_trials} trials")

        result_skopt = self.gp_minimize(
            objective_func,
            search_space,
            n_calls=self.config.max_trials,
            random_state=self.config.random_seed,
            n_jobs=1,  # Sequential execution (parallel handled by skopt)
            verbose=False,
        )

        # Validate best parameters
        validation_trial = self._validate_best_trial()

        # Create result
        execution_time = time.time() - self.start_time
        result = OptimizationResult(
            best_parameters=self.best_trial.parameters,
            train_objective=self.best_trial.objective_value,
            validation_objective=validation_trial.objective_value,
            all_trials=self.trials,
            parameter_importance=self._calculate_parameter_importance_bayesian(),
            execution_time_seconds=execution_time,
        )

        return result

    def _create_search_space(self):
        """Create skopt search space from parameter specs."""
        from skopt.space import Real, Integer, Categorical

        search_space = []

        for param_name, param_spec in self.config.parameter_space.items():
            if param_spec.type == 'int':
                dim = Integer(
                    param_spec.min_value,
                    param_spec.max_value,
                    name=param_name
                )
            elif param_spec.type == 'float':
                if param_spec.log_scale:
                    dim = Real(
                        param_spec.min_value,
                        param_spec.max_value,
                        prior='log-uniform',
                        name=param_name
                    )
                else:
                    dim = Real(
                        param_spec.min_value,
                        param_spec.max_value,
                        name=param_name
                    )
            elif param_spec.type == 'categorical':
                dim = Categorical(param_spec.values, name=param_name)
            else:
                raise ValueError(f"Unknown parameter type: {param_spec.type}")

            search_space.append(dim)

        return search_space

    def _calculate_parameter_importance_bayesian(self) -> Dict[str, float]:
        """
        Calculate parameter importance using Gaussian Process model.

        Returns:
            Dictionary of parameter names to importance scores
        """
        # Simplified implementation - use variance analysis
        return self._calculate_parameter_importance()
```

#### 2.2.4 OptimizationResult

```python
@dataclass
class OptimizationTrial:
    """Single optimization trial result."""

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
    """Complete optimization results."""

    # Best parameters and objectives
    best_parameters: Dict[str, Any]
    train_objective: float
    validation_objective: float
    test_objective: Optional[float] = None

    # All trials
    all_trials: List[OptimizationTrial] = field(default_factory=list)

    # Parameter analysis
    parameter_importance: Dict[str, float] = field(default_factory=dict)
    parameter_sensitivity: Optional[Dict[str, pd.DataFrame]] = None

    # Execution metadata
    execution_time_seconds: float = 0.0
    optimization_method: str = 'grid'

    def plot_optimization_history(self, filepath: str):
        """Plot objective value vs trial number."""
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 6))

        trial_numbers = range(1, len(self.all_trials) + 1)
        objectives = [t.objective_value for t in self.all_trials]

        # Plot all trials
        ax.scatter(trial_numbers, objectives, alpha=0.5, label='All Trials')

        # Plot best so far
        best_so_far = []
        current_best = float('-inf')
        for obj in objectives:
            current_best = max(current_best, obj)
            best_so_far.append(current_best)

        ax.plot(trial_numbers, best_so_far, 'r-', linewidth=2, label='Best So Far')

        ax.set_xlabel('Trial Number')
        ax.set_ylabel('Objective Value')
        ax.set_title('Optimization Progress')
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(filepath)
        plt.close()

    def plot_parameter_importance(self, filepath: str):
        """Plot parameter importance bar chart."""
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 6))

        params = list(self.parameter_importance.keys())
        importance = list(self.parameter_importance.values())

        ax.barh(params, importance)
        ax.set_xlabel('Importance')
        ax.set_title('Parameter Importance')
        ax.grid(True, alpha=0.3, axis='x')

        plt.tight_layout()
        plt.savefig(filepath)
        plt.close()
```

### 2.3 Usage Example

```python
# Example: Optimize Kelly multiplier and score threshold
from datetime import date
from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.backtesting import BacktestConfig, ParameterOptimizer
from modules.backtesting.parameter_optimizer import (
    OptimizationConfig, ParameterSpec, GridSearchOptimizer
)

# Initialize database
db = SQLiteDatabaseManager()

# Define parameter space
parameter_space = {
    'kelly_multiplier': ParameterSpec(
        type='float',
        min_value=0.25,
        max_value=1.0,
        step=0.25  # Test 0.25, 0.5, 0.75, 1.0
    ),
    'score_threshold': ParameterSpec(
        type='int',
        min_value=60,
        max_value=80,
        step=5  # Test 60, 65, 70, 75, 80
    ),
    'stop_loss_min': ParameterSpec(
        type='float',
        min_value=0.03,
        max_value=0.08,
        step=0.01
    ),
}

# Create base backtest config
base_config = BacktestConfig(
    start_date=date(2023, 1, 1),
    end_date=date(2023, 12, 31),
    regions=['KR'],
    initial_capital=100_000_000,
)

# Create optimization config
opt_config = OptimizationConfig(
    parameter_space=parameter_space,
    objective='sharpe_ratio',
    maximize=True,
    train_start_date=date(2023, 1, 1),
    train_end_date=date(2023, 8, 31),
    validation_start_date=date(2023, 9, 1),
    validation_end_date=date(2023, 12, 31),
    max_trials=100,
    n_jobs=4,
    base_config=base_config,
)

# Run optimization
optimizer = GridSearchOptimizer(opt_config, db)
result = optimizer.optimize()

# Print results
print(f"Best parameters: {result.best_parameters}")
print(f"Train Sharpe: {result.train_objective:.2f}")
print(f"Validation Sharpe: {result.validation_objective:.2f}")
print(f"Parameter importance: {result.parameter_importance}")

# Save results
optimizer.save_results(result, 'optimization_results.json')
result.plot_optimization_history('optimization_history.png')
result.plot_parameter_importance('parameter_importance.png')
```

---

## 3. TransactionCostModel Design

### 3.1 Architecture Overview

```
┌────────────────────────────────────────────────────────────┐
│                  TransactionCostModel                       │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │  Commission  │  │   Slippage   │  │ Market Impact   │ │
│  │    Model     │  │    Model     │  │     Model       │ │
│  └──────┬───────┘  └──────┬───────┘  └────────┬────────┘ │
│         │                  │                    │           │
│         └──────────────────┴────────────────────┘           │
│                           │                                 │
│              ┌────────────▼──────────────┐                 │
│              │   CostCalculator          │                 │
│              │  - Calculate total cost   │                 │
│              │  - Split buy/sell costs   │                 │
│              │  - Time-dependent costs   │                 │
│              └────────────┬──────────────┘                 │
│                           │                                 │
│                           ▼                                 │
│              ┌───────────────────────────┐                 │
│              │    MarketCostProfile      │                 │
│              │  - KR market defaults     │                 │
│              │  - US market defaults     │                 │
│              │  - Custom profiles        │                 │
│              └───────────────────────────┘                 │
│                                                             │
└────────────────────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────┐
│   PortfolioSimulator       │
│   (Integration Point)      │
│  - Buy/sell cost calc      │
│  - Cost tracking in trades │
└────────────────────────────┘
```

### 3.2 Core Classes

#### 3.2.1 TransactionCostModel (Base Class)

```python
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from typing import Optional
import numpy as np


class OrderSide(Enum):
    """Order side enumeration."""
    BUY = "buy"
    SELL = "sell"


class TimeOfDay(Enum):
    """Time of day for cost calculation."""
    OPEN = "open"  # First 30 minutes
    REGULAR = "regular"  # Regular hours
    CLOSE = "close"  # Last 30 minutes


@dataclass
class TransactionCosts:
    """Transaction cost breakdown."""

    commission: float
    slippage: float
    market_impact: float
    total_cost: float

    @property
    def total_cost_bps(self) -> float:
        """Total cost in basis points (for reporting)."""
        return self.total_cost * 10000


class TransactionCostModel(ABC):
    """
    Base class for transaction cost models.

    Provides interface for calculating realistic trading costs
    including commission, slippage, and market impact.
    """

    def __init__(self, market: str = 'KR'):
        """
        Initialize cost model.

        Args:
            market: Market identifier (KR, US, CN, HK, JP, VN)
        """
        self.market = market

    @abstractmethod
    def calculate_costs(
        self,
        ticker: str,
        price: float,
        shares: int,
        side: OrderSide,
        time_of_day: TimeOfDay = TimeOfDay.REGULAR,
        avg_daily_volume: Optional[float] = None,
    ) -> TransactionCosts:
        """
        Calculate total transaction costs.

        Args:
            ticker: Stock ticker
            price: Execution price
            shares: Number of shares
            side: Order side (buy/sell)
            time_of_day: Time of day for execution
            avg_daily_volume: Average daily volume (for market impact)

        Returns:
            TransactionCosts breakdown
        """
        pass

    def calculate_commission(
        self,
        price: float,
        shares: int,
        side: OrderSide,
    ) -> float:
        """Calculate commission cost."""
        raise NotImplementedError("Subclass must implement")

    def calculate_slippage(
        self,
        price: float,
        shares: int,
        side: OrderSide,
        time_of_day: TimeOfDay,
    ) -> float:
        """Calculate slippage cost."""
        raise NotImplementedError("Subclass must implement")

    def calculate_market_impact(
        self,
        price: float,
        shares: int,
        side: OrderSide,
        avg_daily_volume: Optional[float],
    ) -> float:
        """Calculate market impact cost."""
        raise NotImplementedError("Subclass must implement")


#### 3.2.2 StandardCostModel

```python
class StandardCostModel(TransactionCostModel):
    """
    Standard transaction cost model with configurable parameters.

    Commission: Fixed percentage of notional value
    Slippage: Fixed basis points with time-of-day adjustments
    Market Impact: Square root model based on order size
    """

    def __init__(
        self,
        market: str = 'KR',
        commission_rate: float = 0.00015,  # 0.015%
        slippage_bps: float = 5.0,  # 5 basis points
        market_impact_coefficient: float = 0.1,
        time_of_day_multipliers: Optional[Dict[TimeOfDay, float]] = None,
    ):
        """
        Initialize standard cost model.

        Args:
            market: Market identifier
            commission_rate: Commission as fraction of notional (0.00015 = 0.015%)
            slippage_bps: Base slippage in basis points
            market_impact_coefficient: Market impact coefficient
            time_of_day_multipliers: Multipliers for different times of day
        """
        super().__init__(market)

        self.commission_rate = commission_rate
        self.slippage_bps = slippage_bps
        self.market_impact_coefficient = market_impact_coefficient

        # Default time-of-day multipliers
        if time_of_day_multipliers is None:
            self.time_of_day_multipliers = {
                TimeOfDay.OPEN: 1.5,  # 50% higher slippage at open
                TimeOfDay.REGULAR: 1.0,  # Normal slippage
                TimeOfDay.CLOSE: 1.3,  # 30% higher slippage at close
            }
        else:
            self.time_of_day_multipliers = time_of_day_multipliers

    def calculate_costs(
        self,
        ticker: str,
        price: float,
        shares: int,
        side: OrderSide,
        time_of_day: TimeOfDay = TimeOfDay.REGULAR,
        avg_daily_volume: Optional[float] = None,
    ) -> TransactionCosts:
        """Calculate total transaction costs."""

        # Calculate individual components
        commission = self.calculate_commission(price, shares, side)
        slippage = self.calculate_slippage(price, shares, side, time_of_day)
        market_impact = self.calculate_market_impact(price, shares, side, avg_daily_volume)

        total_cost = commission + slippage + market_impact

        return TransactionCosts(
            commission=commission,
            slippage=slippage,
            market_impact=market_impact,
            total_cost=total_cost,
        )

    def calculate_commission(
        self,
        price: float,
        shares: int,
        side: OrderSide,
    ) -> float:
        """
        Calculate commission cost.

        Commission = notional_value * commission_rate
        """
        notional = price * shares
        return notional * self.commission_rate

    def calculate_slippage(
        self,
        price: float,
        shares: int,
        side: OrderSide,
        time_of_day: TimeOfDay,
    ) -> float:
        """
        Calculate slippage cost.

        Slippage = notional_value * (slippage_bps / 10000) * time_multiplier
        """
        notional = price * shares
        base_slippage = notional * (self.slippage_bps / 10000)

        # Apply time-of-day multiplier
        time_multiplier = self.time_of_day_multipliers.get(time_of_day, 1.0)

        return base_slippage * time_multiplier

    def calculate_market_impact(
        self,
        price: float,
        shares: int,
        side: OrderSide,
        avg_daily_volume: Optional[float],
    ) -> float:
        """
        Calculate market impact cost using square root model.

        Market Impact = coefficient * notional * sqrt(order_size / daily_volume)

        If avg_daily_volume is None, returns 0 (no market impact).
        """
        if avg_daily_volume is None or avg_daily_volume == 0:
            return 0.0

        notional = price * shares
        volume_participation = shares / avg_daily_volume

        # Square root model (standard in market microstructure)
        impact_factor = np.sqrt(volume_participation)
        market_impact = self.market_impact_coefficient * notional * impact_factor

        return market_impact


#### 3.2.3 MarketCostProfile

```python
@dataclass
class MarketCostProfile:
    """Pre-configured cost profiles for different markets."""

    market: str
    name: str
    description: str
    commission_rate: float
    slippage_bps: float
    market_impact_coefficient: float
    time_of_day_multipliers: Dict[TimeOfDay, float]

    def create_model(self) -> StandardCostModel:
        """Create cost model from profile."""
        return StandardCostModel(
            market=self.market,
            commission_rate=self.commission_rate,
            slippage_bps=self.slippage_bps,
            market_impact_coefficient=self.market_impact_coefficient,
            time_of_day_multipliers=self.time_of_day_multipliers,
        )


# Pre-configured market profiles
MARKET_COST_PROFILES = {
    'KR_DEFAULT': MarketCostProfile(
        market='KR',
        name='Korea Default',
        description='KIS default commission + realistic slippage',
        commission_rate=0.00015,  # 0.015%
        slippage_bps=5.0,  # 5 bps
        market_impact_coefficient=0.1,
        time_of_day_multipliers={
            TimeOfDay.OPEN: 1.5,
            TimeOfDay.REGULAR: 1.0,
            TimeOfDay.CLOSE: 1.3,
        },
    ),
    'KR_LOW_COST': MarketCostProfile(
        market='KR',
        name='Korea Low Cost',
        description='Optimistic cost assumptions',
        commission_rate=0.00010,  # 0.01%
        slippage_bps=3.0,  # 3 bps
        market_impact_coefficient=0.05,
        time_of_day_multipliers={
            TimeOfDay.OPEN: 1.3,
            TimeOfDay.REGULAR: 1.0,
            TimeOfDay.CLOSE: 1.2,
        },
    ),
    'KR_HIGH_COST': MarketCostProfile(
        market='KR',
        name='Korea High Cost',
        description='Conservative cost assumptions',
        commission_rate=0.00020,  # 0.02%
        slippage_bps=10.0,  # 10 bps
        market_impact_coefficient=0.15,
        time_of_day_multipliers={
            TimeOfDay.OPEN: 2.0,
            TimeOfDay.REGULAR: 1.0,
            TimeOfDay.CLOSE: 1.5,
        },
    ),
    'US_DEFAULT': MarketCostProfile(
        market='US',
        name='US Default',
        description='US market typical costs',
        commission_rate=0.0,  # Commission-free trading
        slippage_bps=3.0,  # 3 bps
        market_impact_coefficient=0.08,
        time_of_day_multipliers={
            TimeOfDay.OPEN: 1.8,  # Higher volatility at open
            TimeOfDay.REGULAR: 1.0,
            TimeOfDay.CLOSE: 1.4,
        },
    ),
}


def get_cost_model(profile_name: str = 'KR_DEFAULT') -> StandardCostModel:
    """
    Get pre-configured cost model by profile name.

    Args:
        profile_name: Profile name from MARKET_COST_PROFILES

    Returns:
        Configured TransactionCostModel
    """
    if profile_name not in MARKET_COST_PROFILES:
        raise ValueError(f"Unknown profile: {profile_name}. "
                        f"Available: {list(MARKET_COST_PROFILES.keys())}")

    profile = MARKET_COST_PROFILES[profile_name]
    return profile.create_model()
```

### 3.3 Integration with PortfolioSimulator

```python
# Add to PortfolioSimulator class

class PortfolioSimulator:
    """
    Portfolio simulator with transaction cost modeling.
    """

    def __init__(
        self,
        config: BacktestConfig,
        cost_model: Optional[TransactionCostModel] = None,
    ):
        """
        Initialize portfolio simulator.

        Args:
            config: Backtest configuration
            cost_model: Transaction cost model (default: StandardCostModel)
        """
        self.config = config

        # Initialize cost model
        if cost_model is None:
            # Use default cost model based on config
            self.cost_model = get_cost_model('KR_DEFAULT')
        else:
            self.cost_model = cost_model

        # ... rest of initialization

    def buy(
        self,
        ticker: str,
        region: str,
        price: float,
        buy_date: date,
        kelly_fraction: float,
        pattern_type: str,
        entry_score: int,
        sector: Optional[str] = None,
        atr: Optional[float] = None,
        time_of_day: TimeOfDay = TimeOfDay.REGULAR,
    ) -> Optional[Trade]:
        """
        Execute buy order with realistic transaction costs.
        """
        # Calculate position size
        position_value = self.cash * kelly_fraction
        shares = int(position_value / price)

        if shares == 0:
            return None

        # Calculate transaction costs using cost model
        costs = self.cost_model.calculate_costs(
            ticker=ticker,
            price=price,
            shares=shares,
            side=OrderSide.BUY,
            time_of_day=time_of_day,
            avg_daily_volume=self._get_avg_volume(ticker),  # New helper method
        )

        total_cost = price * shares + costs.total_cost

        # Check if sufficient cash
        if total_cost > self.cash:
            return None

        # Deduct cash
        self.cash -= total_cost

        # Create trade with detailed cost breakdown
        trade = Trade(
            ticker=ticker,
            region=region,
            entry_date=buy_date,
            entry_price=price,
            shares=shares,
            commission=costs.commission,
            slippage=costs.slippage + costs.market_impact,  # Combined for simplicity
            pattern_type=pattern_type,
            entry_score=entry_score,
            sector=sector,
        )

        # ... rest of buy logic

        return trade

    def _get_avg_volume(self, ticker: str) -> Optional[float]:
        """
        Get average daily volume for ticker (for market impact calculation).

        Returns:
            Average daily volume or None
        """
        # Query from historical data provider
        # This would need to be added to HistoricalDataProvider
        return None  # Placeholder
```

### 3.4 Usage Example

```python
# Example: Backtest with different cost profiles

from modules.backtesting import BacktestEngine, BacktestConfig
from modules.backtesting.transaction_cost_model import get_cost_model
from modules.db_manager_sqlite import SQLiteDatabaseManager

# Initialize
db = SQLiteDatabaseManager()

# Create config
config = BacktestConfig(
    start_date=date(2023, 1, 1),
    end_date=date(2023, 12, 31),
    regions=['KR'],
    initial_capital=100_000_000,
)

# Test 1: Default costs
cost_model_default = get_cost_model('KR_DEFAULT')
engine = BacktestEngine(config, db, cost_model=cost_model_default)
result_default = engine.run()

# Test 2: High costs (conservative)
cost_model_high = get_cost_model('KR_HIGH_COST')
engine = BacktestEngine(config, db, cost_model=cost_model_high)
result_high_cost = engine.run()

# Compare results
print("Default costs:")
print(f"  Total Return: {result_default.metrics.total_return:.1%}")
print(f"  Sharpe Ratio: {result_default.metrics.sharpe_ratio:.2f}")

print("\nHigh costs:")
print(f"  Total Return: {result_high_cost.metrics.total_return:.1%}")
print(f"  Sharpe Ratio: {result_high_cost.metrics.sharpe_ratio:.2f}")

# Analyze cost impact
total_costs_default = sum(t.commission + t.slippage for t in result_default.trades)
total_costs_high = sum(t.commission + t.slippage for t in result_high_cost.trades)

print(f"\nTotal costs:")
print(f"  Default: ₩{total_costs_default:,.0f}")
print(f"  High: ₩{total_costs_high:,.0f}")
print(f"  Difference: ₩{total_costs_high - total_costs_default:,.0f}")
```

---

## 4. Integration Architecture

### 4.1 BacktestEngine Integration

```python
# Updated BacktestEngine.__init__()

class BacktestEngine:
    """Main orchestrator for backtesting."""

    def __init__(
        self,
        config: BacktestConfig,
        db: SQLiteDatabaseManager,
        cost_model: Optional[TransactionCostModel] = None,
    ):
        """
        Initialize backtest engine.

        Args:
            config: Backtest configuration
            db: SQLite database manager
            cost_model: Transaction cost model (optional)
        """
        self.config = config
        self.db = db
        self.data_provider = HistoricalDataProvider(db)

        # Initialize portfolio with cost model
        self.portfolio = PortfolioSimulator(config, cost_model=cost_model)

        self.strategy_runner = StrategyRunner(config, db)

        logger.info(f"BacktestEngine initialized: {config}")
        if cost_model is not None:
            logger.info(f"Cost model: {cost_model.__class__.__name__}")
```

### 4.2 Optimization with Cost Sensitivity

```python
# Example: Optimize parameters with cost sensitivity analysis

# Define parameter space
parameter_space = {
    'kelly_multiplier': ParameterSpec(type='float', min_value=0.25, max_value=1.0, step=0.25),
    'score_threshold': ParameterSpec(type='int', min_value=60, max_value=80, step=5),
}

# Test with different cost assumptions
cost_profiles = ['KR_LOW_COST', 'KR_DEFAULT', 'KR_HIGH_COST']

results_by_cost = {}

for profile_name in cost_profiles:
    # Create cost model
    cost_model = get_cost_model(profile_name)

    # Run optimization
    # (Need to pass cost_model through to BacktestEngine)
    optimizer = GridSearchOptimizer(opt_config, db)
    result = optimizer.optimize()

    results_by_cost[profile_name] = result

# Compare optimal parameters across cost assumptions
for profile_name, result in results_by_cost.items():
    print(f"\n{profile_name}:")
    print(f"  Best parameters: {result.best_parameters}")
    print(f"  Validation objective: {result.validation_objective:.2f}")
```

### 4.3 Module Structure

```
modules/backtesting/
├── __init__.py
├── backtest_config.py
├── backtest_engine.py
├── historical_data_provider.py
├── portfolio_simulator.py
├── strategy_runner.py
├── performance_analyzer.py
├── backtest_reporter.py
├── parameter_optimizer.py          # NEW: ParameterOptimizer base class
├── grid_search_optimizer.py        # NEW: GridSearchOptimizer
├── bayesian_optimizer.py           # NEW: BayesianOptimizer
├── walk_forward_optimizer.py       # NEW: WalkForwardOptimizer (future)
└── transaction_cost_model.py       # NEW: TransactionCostModel classes
```

---

## 5. Implementation Roadmap

### Phase 1: TransactionCostModel (Week 5)
**Priority**: High (foundation for realistic backtesting)

**Tasks**:
1. Create `transaction_cost_model.py` module
2. Implement `TransactionCostModel` base class
3. Implement `StandardCostModel`
4. Create market cost profiles (KR, US)
5. Integrate with `PortfolioSimulator`
6. Update `Trade` dataclass to track cost breakdown
7. Add cost metrics to `BacktestReporter`

**Deliverables**:
- Working TransactionCostModel
- 15+ unit tests
- Cost comparison example script

**Time Estimate**: 3-4 days

### Phase 2: ParameterOptimizer Core (Week 6)
**Priority**: High (enables systematic optimization)

**Tasks**:
1. Create `parameter_optimizer.py` base module
2. Implement `OptimizationConfig` and `ParameterSpec`
3. Implement `ParameterOptimizer` base class
4. Implement `OptimizationTrial` and `OptimizationResult`
5. Add parallel execution support
6. Implement progress tracking and logging

**Deliverables**:
- ParameterOptimizer base framework
- 10+ unit tests
- Documentation

**Time Estimate**: 4-5 days

### Phase 3: GridSearchOptimizer (Week 6-7)
**Priority**: High (most straightforward optimization method)

**Tasks**:
1. Implement `GridSearchOptimizer` class
2. Parameter grid generation
3. Parameter importance calculation
4. Visualization methods
5. Integration tests with BacktestEngine

**Deliverables**:
- Working GridSearchOptimizer
- 15+ unit tests
- Optimization example script

**Time Estimate**: 3-4 days

### Phase 4: BayesianOptimizer (Week 7-8)
**Priority**: Medium (more sophisticated optimization)

**Tasks**:
1. Add scikit-optimize dependency
2. Implement `BayesianOptimizer` class
3. Search space configuration
4. Gaussian process integration
5. Comparison with grid search

**Deliverables**:
- Working BayesianOptimizer
- 10+ unit tests
- Performance comparison

**Time Estimate**: 4-5 days

### Phase 5: Documentation & Examples (Week 8)
**Priority**: High (user enablement)

**Tasks**:
1. Write comprehensive usage guide
2. Create example optimization workflows
3. Document best practices (overfitting prevention)
4. Create visualization examples
5. Update CLAUDE.md

**Deliverables**:
- User guide document
- 5+ example scripts
- Best practices guide

**Time Estimate**: 2-3 days

---

## 6. Testing Strategy

### 6.1 Unit Tests

**TransactionCostModel**:
- Test commission calculation (fixed rate, tiered)
- Test slippage calculation (fixed bps, time-dependent)
- Test market impact (square root model, zero volume case)
- Test cost profile loading
- Test market-specific configurations

**ParameterOptimizer**:
- Test parameter space generation
- Test objective function calculation
- Test train/validation splitting
- Test best trial selection
- Test result serialization

**GridSearchOptimizer**:
- Test grid generation (int, float, categorical)
- Test exhaustive search
- Test parameter importance calculation
- Test early stopping

**BayesianOptimizer**:
- Test search space creation
- Test acquisition function
- Test convergence
- Test vs grid search equivalence (small space)

### 6.2 Integration Tests

**Cost Model Integration**:
```python
def test_backtest_with_cost_model():
    """Test backtest with transaction cost model."""
    config = BacktestConfig(...)
    cost_model = get_cost_model('KR_DEFAULT')

    engine = BacktestEngine(config, db, cost_model=cost_model)
    result = engine.run()

    # Verify costs are applied
    assert all(t.commission > 0 for t in result.trades)
    assert all(t.slippage > 0 for t in result.trades)

    # Verify impact on returns
    assert result.metrics.total_return < result_no_costs.metrics.total_return
```

**Optimization Integration**:
```python
def test_grid_search_optimization():
    """Test grid search parameter optimization."""
    parameter_space = {
        'kelly_multiplier': ParameterSpec(type='float', min_value=0.25, max_value=0.75, step=0.25),
        'score_threshold': ParameterSpec(type='int', min_value=65, max_value=75, step=5),
    }

    opt_config = OptimizationConfig(
        parameter_space=parameter_space,
        objective='sharpe_ratio',
        train_start_date=date(2023, 1, 1),
        train_end_date=date(2023, 6, 30),
        validation_start_date=date(2023, 7, 1),
        validation_end_date=date(2023, 12, 31),
        base_config=base_config,
    )

    optimizer = GridSearchOptimizer(opt_config, db)
    result = optimizer.optimize()

    # Verify optimization ran
    assert len(result.all_trials) == 3 * 3  # 3 kelly × 3 threshold
    assert result.best_parameters is not None
    assert result.validation_objective > 0
```

### 6.3 Performance Tests

**Optimization Performance**:
- Benchmark grid search vs Bayesian (100 trials)
- Test parallel speedup (1, 2, 4, 8 workers)
- Memory usage profiling
- Time per trial measurement

**Cost Model Performance**:
- Benchmark cost calculation overhead (<1ms per trade)
- Test with high-frequency backtests (1000+ trades)

---

## 7. Performance Considerations

### 7.1 Optimization Performance

**Grid Search**:
- Time complexity: O(n) where n = product of parameter grid sizes
- Parallelization: Embarrassingly parallel (linear speedup)
- Memory: O(n) for storing all trials
- Recommendation: Use for <500 parameter combinations

**Bayesian Optimization**:
- Time complexity: O(n²) for Gaussian Process (can use approximations)
- Parallelization: Sequential by nature (but batch acquisition possible)
- Memory: O(n²) for covariance matrix
- Recommendation: Use for >500 parameter combinations

**Expected Performance**:
```
Parameter Space Size | Method    | Time (4 workers) | Memory
--------------------|-----------|------------------|--------
100 combinations    | Grid      | ~15 minutes      | ~500MB
500 combinations    | Grid      | ~1.25 hours      | ~2GB
500 combinations    | Bayesian  | ~1.25 hours      | ~1GB
2000 combinations   | Bayesian  | ~5 hours         | ~4GB
```

### 7.2 Cost Model Performance

**Per-Trade Overhead**:
- Commission calculation: ~0.01ms
- Slippage calculation: ~0.01ms
- Market impact calculation: ~0.05ms (with volume lookup)
- **Total overhead**: <0.1ms per trade

**Backtest Impact**:
- 1000 trades: +100ms execution time (~0.3% overhead)
- Negligible impact on backtest performance

### 7.3 Memory Optimization

**Optimization Memory Management**:
```python
# For large optimization runs, implement streaming results
class StreamingOptimizer(ParameterOptimizer):
    """Optimizer that streams results to disk."""

    def __init__(self, *args, results_file: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.results_file = results_file
        self.trials = []  # Keep empty, stream to file

    def _run_single_trial(self, parameters, data_split):
        trial = super()._run_single_trial(parameters, data_split)

        # Stream to file
        self._append_trial_to_file(trial)

        # Don't keep in memory
        return trial

    def _append_trial_to_file(self, trial):
        """Append trial to JSONL file."""
        with open(self.results_file, 'a') as f:
            f.write(json.dumps(dataclasses.asdict(trial), default=str))
            f.write('\n')
```

---

## 8. Future Enhancements

### 8.1 Walk-Forward Optimization

```python
class WalkForwardOptimizer(ParameterOptimizer):
    """
    Walk-forward optimization for adaptive strategy.

    Repeatedly optimizes on rolling training windows and
    tests on out-of-sample validation windows.
    """

    def optimize(self) -> WalkForwardResult:
        """
        Run walk-forward optimization.

        Process:
        1. Split data into rolling windows
        2. For each window:
           a. Optimize on training period
           b. Test on validation period
        3. Aggregate results

        Returns:
            WalkForwardResult with time-varying parameters
        """
        pass
```

### 8.2 Multi-Objective Optimization

```python
class MultiObjectiveOptimizer(ParameterOptimizer):
    """
    Multi-objective optimization (Pareto frontier).

    Optimize multiple objectives simultaneously
    (e.g., maximize return AND minimize drawdown).
    """

    def __init__(
        self,
        config: OptimizationConfig,
        db: SQLiteDatabaseManager,
        objectives: List[str],
    ):
        """
        Initialize multi-objective optimizer.

        Args:
            objectives: List of objectives (e.g., ['sharpe_ratio', 'max_drawdown'])
        """
        self.objectives = objectives
        super().__init__(config, db, optimization_method='multi_objective')

    def optimize(self) -> ParetoFrontierResult:
        """Find Pareto-optimal parameter sets."""
        pass
```

### 8.3 Advanced Cost Models

```python
class AdaptiveSlippageModel(TransactionCostModel):
    """
    Adaptive slippage based on realized execution data.

    Learns slippage distribution from historical trades
    and adjusts predictions dynamically.
    """

    def fit(self, historical_trades: pd.DataFrame):
        """Fit slippage model to historical execution data."""
        pass


class MarketMakingCostModel(TransactionCostModel):
    """
    Market making cost model with bid-ask spread.

    Models costs based on order book depth and
    probability of execution at various price levels.
    """

    def calculate_costs(self, ticker, price, shares, side, order_book):
        """Calculate costs based on order book state."""
        pass
```

---

## 9. References

### Academic Papers
1. Hastie, T., et al. (2009). "The Elements of Statistical Learning"
2. Almgren, R., & Chriss, N. (2001). "Optimal Execution of Portfolio Transactions"
3. Brochu, E., et al. (2010). "A Tutorial on Bayesian Optimization"

### Industry Best Practices
1. "Advances in Financial Machine Learning" - Marcos López de Prado
2. "Quantitative Trading" - Ernest P. Chan
3. QuantConnect/Lean backtesting framework

### Libraries
1. scikit-optimize (Bayesian optimization)
2. Optuna (hyperparameter optimization)
3. Ray Tune (distributed hyperparameter tuning)

---

## Appendix A: API Reference

### ParameterOptimizer API

```python
# Class hierarchy
ParameterOptimizer (ABC)
├── GridSearchOptimizer
├── BayesianOptimizer
└── WalkForwardOptimizer (future)

# Key methods
optimizer.optimize() -> OptimizationResult
optimizer.save_results(result, filepath)
optimizer._run_single_trial(parameters, data_split) -> OptimizationTrial

# Key classes
OptimizationConfig(parameter_space, objective, train/val/test dates, ...)
ParameterSpec(type, min_value, max_value, step, values, log_scale)
OptimizationTrial(parameters, objective_value, metrics, trades, ...)
OptimizationResult(best_parameters, train/val/test objectives, all_trials, ...)
```

### TransactionCostModel API

```python
# Class hierarchy
TransactionCostModel (ABC)
├── StandardCostModel
├── AdaptiveSlippageModel (future)
└── MarketMakingCostModel (future)

# Key methods
cost_model.calculate_costs(ticker, price, shares, side, time_of_day, avg_daily_volume) -> TransactionCosts
cost_model.calculate_commission(price, shares, side) -> float
cost_model.calculate_slippage(price, shares, side, time_of_day) -> float
cost_model.calculate_market_impact(price, shares, side, avg_daily_volume) -> float

# Key classes
TransactionCosts(commission, slippage, market_impact, total_cost)
MarketCostProfile(market, name, commission_rate, slippage_bps, ...)
OrderSide(BUY, SELL)
TimeOfDay(OPEN, REGULAR, CLOSE)

# Helper functions
get_cost_model(profile_name) -> TransactionCostModel
```

---

## Appendix B: Configuration Examples

### Example 1: Grid Search with Conservative Parameters

```yaml
optimization:
  method: grid_search
  objective: sharpe_ratio
  parameter_space:
    kelly_multiplier:
      type: float
      min_value: 0.25
      max_value: 0.75
      step: 0.25
    score_threshold:
      type: int
      min_value: 70
      max_value: 80
      step: 5
    stop_loss_min:
      type: float
      min_value: 0.05
      max_value: 0.10
      step: 0.01

  data_splits:
    train:
      start_date: 2022-01-01
      end_date: 2022-12-31
    validation:
      start_date: 2023-01-01
      end_date: 2023-06-30
    test:
      start_date: 2023-07-01
      end_date: 2023-12-31

  execution:
    n_jobs: 4
    max_trials: 100
    random_seed: 42

cost_model:
  profile: KR_DEFAULT
```

### Example 2: Bayesian Optimization with Large Parameter Space

```yaml
optimization:
  method: bayesian
  objective: calmar_ratio
  parameter_space:
    kelly_multiplier:
      type: float
      min_value: 0.1
      max_value: 1.0
      log_scale: true
    score_threshold:
      type: int
      min_value: 60
      max_value: 85
    stop_loss_min:
      type: float
      min_value: 0.03
      max_value: 0.12
    profit_target:
      type: float
      min_value: 0.15
      max_value: 0.30

  data_splits:
    train:
      start_date: 2021-01-01
      end_date: 2022-06-30
    validation:
      start_date: 2022-07-01
      end_date: 2023-03-31
    test:
      start_date: 2023-04-01
      end_date: 2023-12-31

  execution:
    max_trials: 200
    n_jobs: 1  # Bayesian is sequential
    early_stopping_patience: 30
    random_seed: 42

cost_model:
  profile: KR_HIGH_COST  # Conservative assumption
```

---

## Document Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-17 | Spock Team | Initial design specification |

---

**End of Design Document**
