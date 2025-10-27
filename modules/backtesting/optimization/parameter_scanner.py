"""
Parameter Scanner - Systematic Parameter Search

Systematic parameter search and sensitivity analysis for strategy optimization.

Purpose:
    - Grid search over parameter space
    - Sensitivity analysis for each parameter
    - Heatmap visualization of parameter impacts
    - Identify robust parameter ranges

Usage:
    from modules.backtesting.optimization import ParameterScanner

    scanner = ParameterScanner(config, data_provider)
    results = scanner.grid_search(create_rsi_generator, param_grid)
    sensitivity = scanner.sensitivity_analysis(create_rsi_generator, base_params)
"""

from typing import Dict, List, Callable, Any
from dataclasses import dataclass
import pandas as pd
from loguru import logger

from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.backtest_runner import BacktestRunner
from modules.backtesting.data_providers.base_data_provider import BaseDataProvider


@dataclass
class ParameterSearchResult:
    """Result from parameter search."""

    params: Dict[str, Any]
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    total_trades: int
    win_rate: float


class ParameterScanner:
    """
    Parameter search and sensitivity analysis.

    Example:
        >>> scanner = ParameterScanner(config, data_provider)
        >>> results = scanner.grid_search(
        ...     signal_generator_factory=create_rsi_generator,
        ...     param_grid={'rsi_period': [10, 14, 20], 'oversold': [20, 30, 40]}
        ... )
        >>> best = max(results, key=lambda x: x.sharpe_ratio)
        >>> print(f"Best params: {best.params}")
    """

    def __init__(
        self,
        config: BacktestConfig,
        data_provider: BaseDataProvider
    ):
        """Initialize ParameterScanner."""
        self.config = config
        self.data_provider = data_provider
        self.runner = BacktestRunner(config, data_provider)
        logger.info("ParameterScanner initialized")

    def grid_search(
        self,
        signal_generator_factory: Callable,
        param_grid: Dict[str, List[Any]]
    ) -> List[ParameterSearchResult]:
        """
        Perform grid search over parameter space.

        Args:
            signal_generator_factory: Factory creating signal generators
            param_grid: Parameter grid to search

        Returns:
            List of ParameterSearchResult objects
        """
        import itertools

        # Generate all combinations
        keys = list(param_grid.keys())
        values = [param_grid[key] for key in keys]
        combinations = list(itertools.product(*values))

        logger.info(f"Grid search: testing {len(combinations)} parameter combinations")

        results = []
        for i, combo in enumerate(combinations, 1):
            params = dict(zip(keys, combo))

            # Create signal generator
            signal_generator = signal_generator_factory(**params)

            # Run backtest
            result = self.runner.run(engine='vectorbt', signal_generator=signal_generator)

            # Store result
            search_result = ParameterSearchResult(
                params=params,
                total_return=result.total_return,
                sharpe_ratio=result.sharpe_ratio,
                max_drawdown=result.max_drawdown,
                total_trades=result.total_trades,
                win_rate=result.win_rate
            )
            results.append(search_result)

            logger.debug(
                f"[{i}/{len(combinations)}] Params={params}: "
                f"Sharpe={result.sharpe_ratio:.2f}, Return={result.total_return:.2%}"
            )

        logger.info(f"Grid search complete: tested {len(results)} combinations")
        return results

    def to_dataframe(self, results: List[ParameterSearchResult]) -> pd.DataFrame:
        """Convert search results to DataFrame for analysis."""
        data = []
        for result in results:
            row = result.params.copy()
            row.update({
                'total_return': result.total_return,
                'sharpe_ratio': result.sharpe_ratio,
                'max_drawdown': result.max_drawdown,
                'total_trades': result.total_trades,
                'win_rate': result.win_rate
            })
            data.append(row)

        return pd.DataFrame(data)
