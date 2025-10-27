"""
Grid Search Optimizer

Purpose: Exhaustive parameter search using grid sampling.

Key Features:
  - Generate all parameter combinations
  - Parallel execution with ThreadPoolExecutor
  - Parameter importance calculation
  - Early stopping support
  - Progress tracking

Design Philosophy:
  - Exhaustive exploration for small parameter spaces (<1000 combinations)
  - Embarrassingly parallel (linear speedup with workers)
  - Reproducible results (fixed parameter order)

Author: Spock Development Team
"""

from itertools import product
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import time

from .parameter_optimizer import (
    ParameterOptimizer,
    OptimizationConfig,
    OptimizationResult,
    OptimizationTrial,
)
from modules.db_manager_sqlite import SQLiteDatabaseManager


logger = logging.getLogger(__name__)


class GridSearchOptimizer(ParameterOptimizer):
    """
    Grid search optimizer for exhaustive parameter exploration.

    Grid search tests all combinations of parameter values.
    Best for small parameter spaces (<1000 combinations).

    Features:
        - Exhaustive search of parameter space
        - Parallel execution with ThreadPoolExecutor
        - Parameter importance analysis
        - Early stopping support

    Example:
        >>> from datetime import date
        >>> from modules.backtesting import GridSearchOptimizer, OptimizationConfig, ParameterSpec
        >>>
        >>> # Define parameter space
        >>> parameter_space = {
        ...     'kelly_multiplier': ParameterSpec(type='float', min_value=0.25, max_value=1.0, step=0.25),
        ...     'score_threshold': ParameterSpec(type='int', min_value=60, max_value=80, step=5),
        ... }
        >>>
        >>> # Create config
        >>> opt_config = OptimizationConfig(
        ...     parameter_space=parameter_space,
        ...     objective='sharpe_ratio',
        ...     train_start_date=date(2023, 1, 1),
        ...     train_end_date=date(2023, 6, 30),
        ...     validation_start_date=date(2023, 7, 1),
        ...     validation_end_date=date(2023, 12, 31),
        ...     base_config=base_config,
        ... )
        >>>
        >>> # Run optimization
        >>> optimizer = GridSearchOptimizer(opt_config, db)
        >>> result = optimizer.optimize()
        >>> print(result.best_parameters)
    """

    def __init__(self, config: OptimizationConfig, db: SQLiteDatabaseManager):
        """
        Initialize grid search optimizer.

        Args:
            config: Optimization configuration
            db: Database manager
        """
        super().__init__(config, db, optimization_method='grid')

    def optimize(self) -> OptimizationResult:
        """
        Run grid search optimization.

        Returns:
            OptimizationResult with best parameters and analysis

        Process:
            1. Generate parameter grid (all combinations)
            2. Run trials in parallel using ThreadPoolExecutor
            3. Track best trial during execution
            4. Validate best parameters on validation data
            5. Calculate parameter importance
            6. Return complete results
        """
        self.start_time = time.time()

        # Generate parameter grid
        param_grid = self._generate_parameter_grid()
        self.total_trials = len(param_grid)

        logger.info(f"Grid search: {self.total_trials} parameter combinations")
        logger.info(f"Parallel execution: {self.config.n_jobs} workers")

        # Run trials in parallel
        with ThreadPoolExecutor(max_workers=self.config.n_jobs) as executor:
            # Submit all trials
            futures = {
                executor.submit(self._run_single_trial, params, 'train'): params
                for params in param_grid
            }

            # Process completed trials
            for future in as_completed(futures):
                try:
                    trial = future.result()
                    self.trials.append(trial)
                    self.completed_trials += 1

                    # Update best trial
                    if self.best_trial is None or \
                       trial.objective_value > self.best_trial.objective_value:
                        self.best_trial = trial
                        logger.info(
                            f"New best trial #{trial.trial_number}: "
                            f"objective={trial.objective_value:.4f}, "
                            f"params={trial.parameters}"
                        )

                    # Progress logging
                    if self.completed_trials % 10 == 0 or self.completed_trials == self.total_trials:
                        self._log_progress()

                    # Early stopping check
                    if self._check_early_stopping():
                        logger.info("Early stopping triggered")
                        # Cancel remaining futures
                        for f in futures:
                            f.cancel()
                        break

                except Exception as e:
                    params = futures[future]
                    logger.error(f"Trial failed for parameters {params}: {str(e)}")
                    continue

        # Validate best parameters
        logger.info(f"Validating best trial: {self.best_trial.parameters}")
        validation_trial = self._validate_best_trial()

        # Calculate parameter importance
        parameter_importance = self._calculate_parameter_importance()

        # Create result
        execution_time = time.time() - self.start_time

        result = OptimizationResult(
            best_parameters=self.best_trial.parameters,
            train_objective=self.best_trial.objective_value,
            validation_objective=validation_trial.objective_value,
            all_trials=self.trials,
            parameter_importance=parameter_importance,
            execution_time_seconds=execution_time,
            optimization_method='grid',
        )

        logger.info(f"Optimization complete: {self.completed_trials} trials in {execution_time:.1f}s")
        logger.info(f"Best train objective: {result.train_objective:.4f}")
        logger.info(f"Best validation objective: {result.validation_objective:.4f}")
        logger.info(f"Parameter importance: {parameter_importance}")

        return result

    def _generate_parameter_grid(self) -> List[Dict[str, Any]]:
        """
        Generate all parameter combinations for grid search.

        Returns:
            List of parameter dictionaries

        Example:
            >>> param_space = {
            ...     'kelly': ParameterSpec(type='float', min_value=0.25, max_value=0.75, step=0.25),
            ...     'threshold': ParameterSpec(type='int', min_value=60, max_value=70, step=5),
            ... }
            >>> grid = self._generate_parameter_grid()
            >>> # Returns: [
            >>> #     {'kelly': 0.25, 'threshold': 60},
            >>> #     {'kelly': 0.25, 'threshold': 65},
            >>> #     {'kelly': 0.25, 'threshold': 70},
            >>> #     {'kelly': 0.50, 'threshold': 60},
            >>> #     ... (9 combinations total)
            >>> # ]
        """
        # Extract parameter names and values
        param_names = []
        param_values_list = []

        for param_name, param_spec in self.config.parameter_space.items():
            param_names.append(param_name)

            if param_spec.type == 'categorical':
                # Use provided values directly
                param_values_list.append(param_spec.values)

            elif param_spec.type in ['int', 'float']:
                # Generate grid points
                if param_spec.step is None:
                    raise ValueError(f"step required for {param_name} (type={param_spec.type})")

                values = []
                current = param_spec.min_value

                while current <= param_spec.max_value:
                    # Cast to int if parameter type is int
                    if param_spec.type == 'int':
                        values.append(int(current))
                    else:
                        values.append(float(current))

                    current += param_spec.step

                param_values_list.append(values)

            else:
                raise ValueError(f"Unknown parameter type: {param_spec.type}")

        # Generate all combinations using itertools.product
        param_grid = []
        for combination in product(*param_values_list):
            params = dict(zip(param_names, combination))
            param_grid.append(params)

        return param_grid

    def _check_early_stopping(self) -> bool:
        """
        Check if early stopping criteria is met.

        Returns:
            True if optimization should stop early, False otherwise

        Early stopping logic:
            If no improvement in best objective for N trials (patience),
            stop optimization early to save computation.
        """
        if self.config.early_stopping_patience is None:
            return False

        if len(self.trials) < self.config.early_stopping_patience:
            return False

        # Get recent trials (last N trials)
        recent_trials = self.trials[-self.config.early_stopping_patience:]

        # Check if any recent trial improved over best trial found before them
        best_before_recent = max(
            t.objective_value for t in self.trials[:-self.config.early_stopping_patience]
        )

        recent_best = max(t.objective_value for t in recent_trials)

        # No improvement if recent best is not better than previous best
        return recent_best <= best_before_recent
