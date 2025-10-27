"""
Backtest Runner - Unified Orchestrator

Provides a single interface for running backtests with either the custom
event-driven engine or the vectorbt vectorized engine, with automatic
result comparison and validation.

Usage:
    from modules.backtesting.backtest_runner import BacktestRunner

    # Run with vectorbt (fast)
    runner = BacktestRunner(config, data_provider)
    result = runner.run(engine='vectorbt', signal_generator=rsi_signal_generator)

    # Run with custom engine (accurate)
    result = runner.run(engine='custom')

    # Compare both engines
    comparison = runner.run(engine='both', signal_generator=macd_signal_generator)
    print(f"Consistency: {comparison.consistency_score:.1%}")
"""

import time
from dataclasses import dataclass, asdict
from typing import Literal, Optional, Callable, Tuple, Dict, Any, Union
from datetime import date
import pandas as pd
from loguru import logger

from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.backtest_engine import BacktestEngine
from modules.backtesting.backtest_engines.vectorbt_adapter import (
    VectorbtAdapter,
    VectorbtResult,
    VECTORBT_AVAILABLE
)
from modules.backtesting.data_providers.base_data_provider import BaseDataProvider


@dataclass
class ComparisonResult:
    """Results from comparing custom and vectorbt engines."""

    # Custom engine results
    custom_total_return: float
    custom_sharpe_ratio: float
    custom_max_drawdown: float
    custom_total_trades: int
    custom_execution_time: float

    # vectorbt results
    vectorbt_total_return: float
    vectorbt_sharpe_ratio: float
    vectorbt_max_drawdown: float
    vectorbt_total_trades: int
    vectorbt_execution_time: float

    # Comparison metrics
    consistency_score: float  # Overall consistency (0-1)
    return_difference: float  # Absolute difference in returns
    trade_count_difference: int  # Difference in trade counts
    speedup_factor: float  # vectorbt speedup vs custom

    # Detailed comparison
    metrics_match: Dict[str, bool]  # Per-metric match status
    warnings: list[str]  # Validation warnings

    def __str__(self) -> str:
        """Human-readable comparison summary."""
        return (
            f"ComparisonResult(\n"
            f"  Consistency: {self.consistency_score:.1%}\n"
            f"  Return Diff: {self.return_difference:+.2%}\n"
            f"  Trade Diff: {self.trade_count_difference:+d}\n"
            f"  Speedup: {self.speedup_factor:.1f}x\n"
            f"  Warnings: {len(self.warnings)}\n"
            f")"
        )


@dataclass
class ValidationReport:
    """Engine validation report."""

    validation_passed: bool
    consistency_score: float
    discrepancies: Dict[str, Any]
    recommendations: list[str]
    timestamp: date

    def __str__(self) -> str:
        """Human-readable validation report."""
        status = "✓ PASSED" if self.validation_passed else "✗ FAILED"
        return (
            f"ValidationReport({status})\n"
            f"  Consistency: {self.consistency_score:.1%}\n"
            f"  Discrepancies: {len(self.discrepancies)}\n"
            f"  Recommendations: {len(self.recommendations)}\n"
        )


@dataclass
class PerformanceReport:
    """Performance benchmark report."""

    custom_time: float
    vectorbt_time: float
    speedup_factor: float
    memory_usage_mb: float
    throughput_days_per_sec: float

    def __str__(self) -> str:
        """Human-readable performance report."""
        return (
            f"PerformanceReport(\n"
            f"  Custom: {self.custom_time:.3f}s\n"
            f"  vectorbt: {self.vectorbt_time:.3f}s\n"
            f"  Speedup: {self.speedup_factor:.1f}x\n"
            f"  Throughput: {self.throughput_days_per_sec:.0f} days/s\n"
            f")"
        )


class BacktestRunner:
    """
    Unified backtest orchestrator.

    Provides a single interface for running backtests with either the custom
    event-driven engine or vectorbt vectorized engine, with automatic result
    comparison and validation.

    Example:
        >>> config = BacktestConfig(...)
        >>> runner = BacktestRunner(config, data_provider)
        >>>
        >>> # Fast research with vectorbt
        >>> result = runner.run('vectorbt', signal_generator=rsi_signal_generator)
        >>>
        >>> # Validate with custom engine
        >>> comparison = runner.run('both', signal_generator=rsi_signal_generator)
        >>> print(comparison.consistency_score)  # Should be >0.95
    """

    def __init__(
        self,
        config: BacktestConfig,
        data_provider: BaseDataProvider
    ):
        """
        Initialize BacktestRunner.

        Args:
            config: Backtest configuration
            data_provider: Data provider for OHLCV data
        """
        self.config = config
        self.data_provider = data_provider

        # Initialize engines
        # For SQLiteDataProvider, also pass the db for StrategyRunner compatibility
        db = getattr(data_provider, 'db', None) if hasattr(data_provider, 'db') else None
        self.custom_engine = BacktestEngine(config, data_provider=data_provider, db=db)

        if VECTORBT_AVAILABLE:
            self.vectorbt_adapter = VectorbtAdapter(config, data_provider)
        else:
            self.vectorbt_adapter = None
            logger.warning("vectorbt not available - only custom engine will work")

        logger.info(
            f"BacktestRunner initialized: "
            f"custom={self.custom_engine is not None}, "
            f"vectorbt={self.vectorbt_adapter is not None}"
        )

    def run(
        self,
        engine: Literal['custom', 'vectorbt', 'both'] = 'vectorbt',
        signal_generator: Optional[Callable[[pd.Series], Tuple[pd.Series, pd.Series]]] = None
    ) -> Union[Dict[str, Any], VectorbtResult, ComparisonResult]:
        """
        Run backtest with specified engine.

        Args:
            engine: Engine to use ('custom', 'vectorbt', or 'both')
            signal_generator: Signal generation function (vectorbt only)
                Expected signature: (close: pd.Series) -> (entries, exits)

        Returns:
            - 'custom': Custom engine result (dict)
            - 'vectorbt': VectorbtResult
            - 'both': ComparisonResult (comparison of both engines)

        Raises:
            ValueError: If vectorbt selected but not available
            ValueError: If signal_generator not provided for vectorbt
        """
        if engine == 'custom':
            return self._run_custom()

        elif engine == 'vectorbt':
            if not VECTORBT_AVAILABLE:
                raise ValueError(
                    "vectorbt not available. Install with: pip install vectorbt"
                )
            if signal_generator is None:
                raise ValueError(
                    "signal_generator required for vectorbt engine. "
                    "Example: signal_generator=rsi_signal_generator"
                )
            return self._run_vectorbt(signal_generator)

        elif engine == 'both':
            if not VECTORBT_AVAILABLE:
                raise ValueError(
                    "vectorbt not available for comparison. "
                    "Install with: pip install vectorbt"
                )
            if signal_generator is None:
                raise ValueError(
                    "signal_generator required for vectorbt comparison"
                )
            return self._run_both(signal_generator)

        else:
            raise ValueError(
                f"Invalid engine: {engine}. "
                f"Must be 'custom', 'vectorbt', or 'both'"
            )

    def _run_custom(self) -> Dict[str, Any]:
        """Run backtest with custom event-driven engine."""
        logger.info("Running backtest with custom event-driven engine...")

        start_time = time.time()
        result = self.custom_engine.run()
        execution_time = time.time() - start_time

        result['execution_time'] = execution_time

        logger.info(
            f"Custom engine completed in {execution_time:.3f}s: "
            f"trades={len(result.get('trades', []))}, "
            f"final_value=${result.get('final_portfolio_value', 0):,.2f}"
        )

        return result

    def _run_vectorbt(
        self,
        signal_generator: Callable[[pd.Series], Tuple[pd.Series, pd.Series]]
    ) -> VectorbtResult:
        """Run backtest with vectorbt vectorized engine."""
        logger.info("Running backtest with vectorbt vectorized engine...")

        # Update adapter with signal generator
        self.vectorbt_adapter.signal_generator = signal_generator

        result = self.vectorbt_adapter.run()

        logger.info(
            f"vectorbt completed in {result.execution_time:.3f}s: "
            f"return={result.total_return:.2%}, "
            f"sharpe={result.sharpe_ratio:.2f}, "
            f"trades={result.total_trades}"
        )

        return result

    def _run_both(
        self,
        signal_generator: Callable[[pd.Series], Tuple[pd.Series, pd.Series]]
    ) -> ComparisonResult:
        """Run backtest with both engines and compare results."""
        logger.info("Running backtest with both engines for comparison...")

        # Run custom engine
        custom_result = self._run_custom()

        # Run vectorbt
        vectorbt_result = self._run_vectorbt(signal_generator)

        # Compare results
        comparison = self._compare_results(custom_result, vectorbt_result)

        logger.info(
            f"Comparison complete: "
            f"consistency={comparison.consistency_score:.1%}, "
            f"speedup={comparison.speedup_factor:.1f}x"
        )

        return comparison

    def _compare_results(
        self,
        custom_result: Dict[str, Any],
        vectorbt_result: VectorbtResult
    ) -> ComparisonResult:
        """
        Compare results from custom and vectorbt engines.

        Calculates consistency score based on:
        - Total return similarity (40%)
        - Trade count similarity (30%)
        - Sharpe ratio similarity (20%)
        - Max drawdown similarity (10%)
        """
        # Extract custom engine metrics
        custom_trades = custom_result.get('trades', [])
        custom_total_return = self._calculate_custom_return(custom_result)
        custom_sharpe = custom_result.get('sharpe_ratio', 0.0)
        custom_max_dd = custom_result.get('max_drawdown', 0.0)
        custom_time = custom_result.get('execution_time', 0.0)

        # vectorbt metrics
        vbt_return = vectorbt_result.total_return
        vbt_sharpe = vectorbt_result.sharpe_ratio
        vbt_max_dd = vectorbt_result.max_drawdown
        vbt_trades = vectorbt_result.total_trades
        vbt_time = vectorbt_result.execution_time

        # Calculate differences
        return_diff = abs(custom_total_return - vbt_return)
        trade_diff = abs(len(custom_trades) - vbt_trades)
        sharpe_diff = abs(custom_sharpe - vbt_sharpe) if custom_sharpe else float('inf')
        dd_diff = abs(custom_max_dd - vbt_max_dd)

        # Calculate consistency score (0-1)
        # Each component contributes weighted score
        return_score = max(0, 1 - (return_diff / 0.2))  # 20% tolerance
        trade_score = max(0, 1 - (trade_diff / 5))  # 5 trade tolerance
        sharpe_score = max(0, 1 - (sharpe_diff / 1.0)) if sharpe_diff != float('inf') else 0.5
        dd_score = max(0, 1 - (dd_diff / 0.1))  # 10% tolerance

        consistency_score = (
            0.40 * return_score +
            0.30 * trade_score +
            0.20 * sharpe_score +
            0.10 * dd_score
        )

        # Metrics match status
        metrics_match = {
            'return': return_diff < 0.05,  # 5% tolerance
            'trades': trade_diff <= 2,  # 2 trade tolerance
            'sharpe': sharpe_diff < 0.5 if sharpe_diff != float('inf') else False,
            'max_drawdown': dd_diff < 0.05
        }

        # Generate warnings
        warnings = []
        if return_diff > 0.1:
            warnings.append(f"Large return difference: {return_diff:.2%}")
        if trade_diff > 5:
            warnings.append(f"Large trade count difference: {trade_diff}")
        if consistency_score < 0.8:
            warnings.append(f"Low consistency score: {consistency_score:.1%}")

        # Calculate speedup
        speedup = custom_time / vbt_time if vbt_time > 0 else 0

        return ComparisonResult(
            custom_total_return=custom_total_return,
            custom_sharpe_ratio=custom_sharpe,
            custom_max_drawdown=custom_max_dd,
            custom_total_trades=len(custom_trades),
            custom_execution_time=custom_time,
            vectorbt_total_return=vbt_return,
            vectorbt_sharpe_ratio=vbt_sharpe,
            vectorbt_max_drawdown=vbt_max_dd,
            vectorbt_total_trades=vbt_trades,
            vectorbt_execution_time=vbt_time,
            consistency_score=consistency_score,
            return_difference=return_diff,
            trade_count_difference=trade_diff,
            speedup_factor=speedup,
            metrics_match=metrics_match,
            warnings=warnings
        )

    def _calculate_custom_return(self, result: Dict[str, Any]) -> float:
        """Calculate total return from custom engine result."""
        initial = self.config.initial_capital
        final = result.get('final_portfolio_value', initial)
        return (final - initial) / initial

    def validate_consistency(
        self,
        signal_generator: Callable[[pd.Series], Tuple[pd.Series, pd.Series]],
        tolerance: float = 0.05
    ) -> ValidationReport:
        """
        Validate consistency between custom and vectorbt engines.

        Args:
            signal_generator: Signal generation function for vectorbt
            tolerance: Acceptable difference threshold (default: 5%)

        Returns:
            ValidationReport with pass/fail status and recommendations
        """
        logger.info("Running consistency validation between engines...")

        # Run comparison
        comparison = self._run_both(signal_generator)

        # Check if within tolerance
        validation_passed = comparison.consistency_score >= (1 - tolerance)

        # Identify discrepancies
        discrepancies = {}
        if not comparison.metrics_match['return']:
            discrepancies['return'] = comparison.return_difference
        if not comparison.metrics_match['trades']:
            discrepancies['trades'] = comparison.trade_count_difference
        if not comparison.metrics_match['sharpe']:
            sharpe_diff = abs(
                comparison.custom_sharpe_ratio - comparison.vectorbt_sharpe_ratio
            )
            discrepancies['sharpe'] = sharpe_diff

        # Generate recommendations
        recommendations = []
        if comparison.return_difference > 0.1:
            recommendations.append(
                "Large return difference - check signal generator logic"
            )
        if comparison.trade_count_difference > 5:
            recommendations.append(
                "Trade count mismatch - verify entry/exit conditions"
            )
        if comparison.consistency_score < 0.8:
            recommendations.append(
                "Low consistency - consider using custom engine for production"
            )
        if not recommendations:
            recommendations.append("Engines are consistent - safe to use vectorbt")

        report = ValidationReport(
            validation_passed=validation_passed,
            consistency_score=comparison.consistency_score,
            discrepancies=discrepancies,
            recommendations=recommendations,
            timestamp=date.today()
        )

        logger.info(f"Validation {'PASSED' if validation_passed else 'FAILED'}: {report}")

        return report

    def benchmark_performance(
        self,
        signal_generator: Callable[[pd.Series], Tuple[pd.Series, pd.Series]]
    ) -> PerformanceReport:
        """
        Benchmark performance difference between engines.

        Args:
            signal_generator: Signal generation function for vectorbt

        Returns:
            PerformanceReport with execution times and speedup factor
        """
        logger.info("Benchmarking performance between engines...")

        # Run comparison
        comparison = self._run_both(signal_generator)

        # Calculate throughput
        days = (self.config.end_date - self.config.start_date).days
        throughput = days / comparison.vectorbt_execution_time if comparison.vectorbt_execution_time > 0 else 0

        # Estimate memory (vectorbt is more memory-intensive)
        # Rough estimate: 100MB base + 10MB per ticker
        memory_mb = 100 + (10 * len(self.config.tickers))

        report = PerformanceReport(
            custom_time=comparison.custom_execution_time,
            vectorbt_time=comparison.vectorbt_execution_time,
            speedup_factor=comparison.speedup_factor,
            memory_usage_mb=memory_mb,
            throughput_days_per_sec=throughput
        )

        logger.info(f"Performance benchmark: {report}")

        return report
