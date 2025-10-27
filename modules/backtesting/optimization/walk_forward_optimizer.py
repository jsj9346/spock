"""
Walk-Forward Optimizer - Time-Series Cross-Validation

Walk-forward optimization for backtesting to prevent overfitting by using
rolling windows of train/test periods.

Purpose:
    - Rolling window validation (train/test splits)
    - Out-of-sample testing framework
    - Parameter optimization using vectorbt speed
    - Validation using custom engine accuracy
    - Overfitting detection

Key Features:
    - Anchored or rolling window strategies
    - Parallel optimization using vectorbt
    - Out-of-sample validation
    - Performance degradation tracking
    - Robustness scoring

Usage:
    from modules.backtesting.optimization import WalkForwardOptimizer

    optimizer = WalkForwardOptimizer(config, data_provider)
    results = optimizer.optimize(
        signal_generator_factory=create_rsi_generator,
        param_grid={'rsi_period': [10, 14, 20], 'oversold': [20, 30, 40]},
        train_period_days=252,
        test_period_days=63
    )
"""

from typing import Dict, List, Callable, Any, Tuple
from datetime import date, timedelta
from dataclasses import dataclass
import pandas as pd
from loguru import logger

from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.backtest_runner import BacktestRunner
from modules.backtesting.data_providers.base_data_provider import BaseDataProvider


@dataclass
class WalkForwardWindow:
    """Single walk-forward window definition."""

    window_id: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date


@dataclass
class WalkForwardResult:
    """Walk-forward optimization result."""

    best_params: Dict[str, Any]
    all_results: List[Dict]
    windows: List[WalkForwardWindow]
    in_sample_performance: Dict[str, float]
    out_of_sample_performance: Dict[str, float]
    degradation_pct: float
    robustness_score: float
    overfitting_detected: bool


class WalkForwardOptimizer:
    """
    Walk-forward optimization framework.

    Implements time-series cross-validation using rolling windows to prevent
    overfitting and validate strategy robustness.

    Example:
        >>> optimizer = WalkForwardOptimizer(config, data_provider)
        >>>
        >>> # Define signal generator factory
        >>> def create_rsi_generator(rsi_period, oversold, overbought):
        ...     def generator(close):
        ...         # RSI calculation with params
        ...         return entries, exits
        ...     return generator
        >>>
        >>> # Define parameter grid
        >>> param_grid = {
        ...     'rsi_period': [10, 14, 20],
        ...     'oversold': [20, 30, 40],
        ...     'overbought': [60, 70, 80]
        ... }
        >>>
        >>> # Run optimization
        >>> result = optimizer.optimize(
        ...     signal_generator_factory=create_rsi_generator,
        ...     param_grid=param_grid,
        ...     train_period_days=252,
        ...     test_period_days=63
        ... )
        >>>
        >>> print(f"Best params: {result.best_params}")
        >>> print(f"Robustness: {result.robustness_score:.2f}")
    """

    def __init__(
        self,
        config: BacktestConfig,
        data_provider: BaseDataProvider
    ):
        """
        Initialize WalkForwardOptimizer.

        Args:
            config: Backtest configuration
            data_provider: Data provider for OHLCV data
        """
        self.config = config
        self.data_provider = data_provider
        self.runner = BacktestRunner(config, data_provider)

        logger.info("WalkForwardOptimizer initialized")

    def create_windows(
        self,
        start_date: date,
        end_date: date,
        train_period_days: int,
        test_period_days: int,
        step_days: int = None,
        anchored: bool = False
    ) -> List[WalkForwardWindow]:
        """
        Create walk-forward windows.

        Args:
            start_date: Start date for optimization
            end_date: End date for optimization
            train_period_days: Training period length
            test_period_days: Testing period length
            step_days: Step size between windows (default: test_period_days)
            anchored: Use anchored window (train from start) vs rolling window

        Returns:
            List of WalkForwardWindow objects

        Example:
            >>> windows = optimizer.create_windows(
            ...     start_date=date(2020, 1, 1),
            ...     end_date=date(2023, 12, 31),
            ...     train_period_days=252,
            ...     test_period_days=63
            ... )
            >>> print(f"Created {len(windows)} windows")
        """
        if step_days is None:
            step_days = test_period_days

        windows = []
        window_id = 0
        current_start = start_date

        while True:
            # Calculate train period
            train_start = start_date if anchored else current_start
            train_end = current_start + timedelta(days=train_period_days)

            # Calculate test period
            test_start = train_end + timedelta(days=1)
            test_end = test_start + timedelta(days=test_period_days)

            # Stop if test period exceeds end date
            if test_end > end_date:
                break

            # Create window
            window = WalkForwardWindow(
                window_id=window_id,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end
            )
            windows.append(window)

            # Move to next window
            window_id += 1
            current_start = current_start + timedelta(days=step_days)

        logger.info(
            f"Created {len(windows)} walk-forward windows: "
            f"train={train_period_days}d, test={test_period_days}d, "
            f"{'anchored' if anchored else 'rolling'}"
        )

        return windows

    def optimize(
        self,
        signal_generator_factory: Callable,
        param_grid: Dict[str, List[Any]],
        train_period_days: int = 252,
        test_period_days: int = 63,
        metric: str = 'sharpe_ratio',
        anchored: bool = False
    ) -> WalkForwardResult:
        """
        Run walk-forward optimization.

        Args:
            signal_generator_factory: Factory function creating signal generators from params
            param_grid: Parameter grid to search
            train_period_days: Training period length
            test_period_days: Testing period length
            metric: Optimization metric (sharpe_ratio, total_return, etc.)
            anchored: Use anchored vs rolling windows

        Returns:
            WalkForwardResult with optimization results

        Example:
            >>> result = optimizer.optimize(
            ...     signal_generator_factory=create_rsi_generator,
            ...     param_grid={'rsi_period': [10, 14, 20]},
            ...     metric='sharpe_ratio'
            ... )
        """
        # Create windows
        windows = self.create_windows(
            start_date=self.config.start_date,
            end_date=self.config.end_date,
            train_period_days=train_period_days,
            test_period_days=test_period_days,
            anchored=anchored
        )

        logger.info(f"Starting walk-forward optimization with {len(windows)} windows")

        # Generate parameter combinations
        param_combinations = self._generate_param_combinations(param_grid)
        logger.info(f"Testing {len(param_combinations)} parameter combinations")

        # Store results
        all_results = []
        in_sample_scores = []
        out_of_sample_scores = []

        # Iterate over windows
        for window in windows:
            logger.info(
                f"Window {window.window_id + 1}/{len(windows)}: "
                f"train={window.train_start} to {window.train_end}, "
                f"test={window.test_start} to {window.test_end}"
            )

            # Optimize on training period
            best_params, best_train_score = self._optimize_window(
                signal_generator_factory=signal_generator_factory,
                param_combinations=param_combinations,
                start_date=window.train_start,
                end_date=window.train_end,
                metric=metric
            )

            # Validate on test period
            test_score = self._validate_params(
                signal_generator_factory=signal_generator_factory,
                params=best_params,
                start_date=window.test_start,
                end_date=window.test_end,
                metric=metric
            )

            # Store results
            window_result = {
                'window_id': window.window_id,
                'best_params': best_params,
                'train_score': best_train_score,
                'test_score': test_score,
                'degradation': (best_train_score - test_score) / best_train_score if best_train_score != 0 else 0
            }
            all_results.append(window_result)
            in_sample_scores.append(best_train_score)
            out_of_sample_scores.append(test_score)

            logger.info(
                f"Window {window.window_id + 1} results: "
                f"train={best_train_score:.2f}, test={test_score:.2f}, "
                f"degradation={window_result['degradation']:.1%}"
            )

        # Calculate aggregate metrics
        avg_in_sample = sum(in_sample_scores) / len(in_sample_scores)
        avg_out_of_sample = sum(out_of_sample_scores) / len(out_of_sample_scores)
        degradation_pct = (avg_in_sample - avg_out_of_sample) / avg_in_sample if avg_in_sample != 0 else 0

        # Calculate robustness score (0-1)
        # High score = low degradation + consistent performance
        degradation_penalty = abs(degradation_pct)
        consistency_score = 1.0 - (pd.Series(out_of_sample_scores).std() / (abs(avg_out_of_sample) + 0.001))
        robustness_score = max(0, (1.0 - degradation_penalty) * consistency_score)

        # Detect overfitting (degradation > 20% or robustness < 0.5)
        overfitting_detected = degradation_pct > 0.20 or robustness_score < 0.5

        # Find most common best params across windows
        param_votes = {}
        for result in all_results:
            param_key = str(sorted(result['best_params'].items()))
            param_votes[param_key] = param_votes.get(param_key, 0) + 1

        most_common_params_key = max(param_votes, key=param_votes.get)
        best_params = eval(f"dict({most_common_params_key})")  # Reconstruct dict from string

        result = WalkForwardResult(
            best_params=best_params,
            all_results=all_results,
            windows=windows,
            in_sample_performance={
                'mean': avg_in_sample,
                'std': pd.Series(in_sample_scores).std(),
                'min': min(in_sample_scores),
                'max': max(in_sample_scores)
            },
            out_of_sample_performance={
                'mean': avg_out_of_sample,
                'std': pd.Series(out_of_sample_scores).std(),
                'min': min(out_of_sample_scores),
                'max': max(out_of_sample_scores)
            },
            degradation_pct=degradation_pct,
            robustness_score=robustness_score,
            overfitting_detected=overfitting_detected
        )

        logger.info(
            f"Walk-forward optimization complete: "
            f"best_params={best_params}, "
            f"robustness={robustness_score:.2f}, "
            f"overfitting={'YES' if overfitting_detected else 'NO'}"
        )

        return result

    def _generate_param_combinations(self, param_grid: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
        """Generate all parameter combinations from grid."""
        import itertools

        keys = list(param_grid.keys())
        values = [param_grid[key] for key in keys]
        combinations = list(itertools.product(*values))

        param_combinations = [
            dict(zip(keys, combo))
            for combo in combinations
        ]

        return param_combinations

    def _optimize_window(
        self,
        signal_generator_factory: Callable,
        param_combinations: List[Dict[str, Any]],
        start_date: date,
        end_date: date,
        metric: str
    ) -> Tuple[Dict[str, Any], float]:
        """Optimize parameters for a single window."""
        best_params = None
        best_score = float('-inf')

        # Create temporary config for this window
        window_config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.config.initial_capital,
            regions=self.config.regions,
            tickers=self.config.tickers,
            max_position_size=self.config.max_position_size,
            score_threshold=self.config.score_threshold,
            risk_profile=self.config.risk_profile,
            commission_rate=self.config.commission_rate,
            slippage_bps=self.config.slippage_bps
        )

        window_runner = BacktestRunner(window_config, self.data_provider)

        # Test each parameter combination
        for params in param_combinations:
            # Create signal generator with these params
            signal_generator = signal_generator_factory(**params)

            # Run backtest
            result = window_runner.run(engine='vectorbt', signal_generator=signal_generator)

            # Get score
            score = getattr(result, metric)

            # Update best
            if score > best_score:
                best_score = score
                best_params = params

        return best_params, best_score

    def _validate_params(
        self,
        signal_generator_factory: Callable,
        params: Dict[str, Any],
        start_date: date,
        end_date: date,
        metric: str
    ) -> float:
        """Validate parameters on test period."""
        # Create config for test period
        test_config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.config.initial_capital,
            regions=self.config.regions,
            tickers=self.config.tickers,
            max_position_size=self.config.max_position_size,
            score_threshold=self.config.score_threshold,
            risk_profile=self.config.risk_profile,
            commission_rate=self.config.commission_rate,
            slippage_bps=self.config.slippage_bps
        )

        test_runner = BacktestRunner(test_config, self.data_provider)

        # Create signal generator
        signal_generator = signal_generator_factory(**params)

        # Run backtest
        result = test_runner.run(engine='vectorbt', signal_generator=signal_generator)

        # Return score
        return getattr(result, metric)
