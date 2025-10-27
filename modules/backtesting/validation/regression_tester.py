"""
Regression Tester - Automated Regression Testing

Automated testing framework for detecting performance regressions in backtesting
engines by comparing current results against known reference results.

Purpose:
    - Create and maintain reference backtest results
    - Automated testing against reference results
    - Track performance metrics over time
    - Alert on degradation >5%

Key Features:
    - Reference result storage (JSON format)
    - Automated regression detection
    - Performance trend tracking
    - Configurable tolerance thresholds
    - CI/CD integration ready

Usage:
    from modules.backtesting.validation import RegressionTester

    # Create reference results
    tester = RegressionTester(config, data_provider)
    tester.create_reference("rsi_strategy_v1", rsi_signal_generator)

    # Run regression tests
    results = tester.test_regression("rsi_strategy_v1", rsi_signal_generator)
    assert results.passed, results.failure_message
"""

import time
from dataclasses import dataclass, asdict
from typing import Callable, Tuple, Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import json
import pandas as pd
from loguru import logger

from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.backtest_runner import BacktestRunner, VectorbtResult
from modules.backtesting.data_providers.base_data_provider import BaseDataProvider


@dataclass
class ReferenceResult:
    """Reference backtest result for regression testing."""

    test_name: str
    signal_generator_name: str
    created_at: datetime
    config_hash: str

    # Performance metrics
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    avg_trade_duration: float

    # Execution metrics
    execution_time: float

    # Metadata
    description: str
    tags: List[str]


@dataclass
class RegressionTestResult:
    """Result of a regression test."""

    test_name: str
    timestamp: datetime
    passed: bool

    # Comparison with reference
    reference_result: ReferenceResult
    current_total_return: float
    current_sharpe_ratio: float
    current_max_drawdown: float
    current_total_trades: int
    current_execution_time: float

    # Deviations
    return_deviation: float
    sharpe_deviation: float
    drawdown_deviation: float
    trade_count_deviation: int
    execution_time_deviation: float

    # Status
    failures: List[str]
    warnings: List[str]
    failure_message: Optional[str]


class RegressionTester:
    """
    Automated regression testing framework.

    Maintains reference results and automatically detects performance
    regressions by comparing current backtest results against known
    reference results.

    Attributes:
        config: Backtest configuration
        data_provider: Data provider for OHLCV data
        runner: BacktestRunner instance
        reference_dir: Directory storing reference results

    Example:
        >>> tester = RegressionTester(config, data_provider)
        >>>
        >>> # Create reference result
        >>> tester.create_reference(
        ...     test_name="rsi_strategy_v1",
        ...     signal_generator=rsi_signal_generator,
        ...     description="RSI strategy baseline"
        ... )
        >>>
        >>> # Run regression test
        >>> result = tester.test_regression("rsi_strategy_v1", rsi_signal_generator)
        >>> assert result.passed, result.failure_message
        >>>
        >>> # Run all regression tests
        >>> results = tester.test_all_references()
    """

    def __init__(
        self,
        config: BacktestConfig,
        data_provider: BaseDataProvider,
        reference_dir: Optional[Path] = None,
        tolerance: float = 0.05  # 5% tolerance
    ):
        """
        Initialize RegressionTester.

        Args:
            config: Backtest configuration
            data_provider: Data provider for OHLCV data
            reference_dir: Directory for storing reference results (default: tests/validation/references)
            tolerance: Acceptable deviation threshold (default: 5%)
        """
        self.config = config
        self.data_provider = data_provider
        self.runner = BacktestRunner(config, data_provider)
        self.tolerance = tolerance

        # Setup reference directory
        if reference_dir is None:
            reference_dir = Path(__file__).parent.parent.parent.parent / 'tests' / 'validation' / 'references'
        self.reference_dir = reference_dir
        self.reference_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"RegressionTester initialized: "
            f"tolerance={tolerance:.1%}, "
            f"reference_dir={self.reference_dir}"
        )

    def create_reference(
        self,
        test_name: str,
        signal_generator: Callable[[pd.Series], Tuple[pd.Series, pd.Series]],
        description: str = "",
        tags: Optional[List[str]] = None,
        overwrite: bool = False
    ) -> ReferenceResult:
        """
        Create reference result for regression testing.

        Args:
            test_name: Unique name for this test
            signal_generator: Signal generation function
            description: Optional description of this test
            tags: Optional tags for categorization
            overwrite: Whether to overwrite existing reference

        Returns:
            ReferenceResult created

        Raises:
            FileExistsError: If reference exists and overwrite=False

        Example:
            >>> ref = tester.create_reference(
            ...     test_name="rsi_strategy_v1",
            ...     signal_generator=rsi_signal_generator,
            ...     description="RSI strategy baseline (30/70 thresholds)",
            ...     tags=["rsi", "mean_reversion", "baseline"]
            ... )
        """
        reference_path = self.reference_dir / f"{test_name}.json"

        # Check if reference exists
        if reference_path.exists() and not overwrite:
            raise FileExistsError(
                f"Reference '{test_name}' already exists. "
                f"Use overwrite=True to replace."
            )

        logger.info(f"Creating reference result for '{test_name}'...")

        # Run backtest using vectorbt (reference engine)
        result = self.runner.run(
            engine='vectorbt',
            signal_generator=signal_generator
        )

        # Create reference result
        reference = ReferenceResult(
            test_name=test_name,
            signal_generator_name=signal_generator.__name__,
            created_at=datetime.now(),
            config_hash=self._hash_config(),

            # Performance metrics
            total_return=result.total_return,
            sharpe_ratio=result.sharpe_ratio,
            max_drawdown=result.max_drawdown,
            win_rate=result.win_rate,
            total_trades=result.total_trades,
            avg_trade_duration=result.avg_trade_duration,

            # Execution metrics
            execution_time=result.execution_time,

            # Metadata
            description=description,
            tags=tags or []
        )

        # Save reference
        self._save_reference(reference)

        logger.info(
            f"Reference '{test_name}' created: "
            f"return={result.total_return:.2%}, "
            f"sharpe={result.sharpe_ratio:.2f}, "
            f"trades={result.total_trades}"
        )

        return reference

    def test_regression(
        self,
        test_name: str,
        signal_generator: Callable[[pd.Series], Tuple[pd.Series, pd.Series]],
        tolerance: Optional[float] = None
    ) -> RegressionTestResult:
        """
        Run regression test against reference result.

        Args:
            test_name: Name of reference test
            signal_generator: Signal generation function
            tolerance: Optional custom tolerance (default: use instance tolerance)

        Returns:
            RegressionTestResult with pass/fail status

        Raises:
            FileNotFoundError: If reference doesn't exist

        Example:
            >>> result = tester.test_regression("rsi_strategy_v1", rsi_signal_generator)
            >>> if not result.passed:
            ...     print(f"Regression detected: {result.failure_message}")
            ...     for failure in result.failures:
            ...         print(f"  - {failure}")
        """
        # Load reference
        reference = self._load_reference(test_name)

        # Use custom or instance tolerance
        if tolerance is None:
            tolerance = self.tolerance

        logger.info(f"Running regression test '{test_name}' (tolerance={tolerance:.1%})...")

        # Run current backtest
        current_result = self.runner.run(
            engine='vectorbt',
            signal_generator=signal_generator
        )

        # Calculate deviations
        return_deviation = abs(current_result.total_return - reference.total_return)
        sharpe_deviation = abs(current_result.sharpe_ratio - reference.sharpe_ratio)
        drawdown_deviation = abs(current_result.max_drawdown - reference.max_drawdown)
        trade_count_deviation = abs(current_result.total_trades - reference.total_trades)
        execution_time_deviation = abs(current_result.execution_time - reference.execution_time)

        # Check for failures
        failures = []
        warnings = []

        # Return regression
        if return_deviation > tolerance:
            failures.append(
                f"Return regressed by {return_deviation:.2%} "
                f"(reference: {reference.total_return:.2%}, "
                f"current: {current_result.total_return:.2%})"
            )
        elif return_deviation > tolerance / 2:
            warnings.append(
                f"Return deviation {return_deviation:.2%} approaching tolerance"
            )

        # Sharpe regression
        sharpe_threshold = 0.5  # Absolute threshold for Sharpe
        if sharpe_deviation > sharpe_threshold:
            failures.append(
                f"Sharpe ratio regressed by {sharpe_deviation:.2f} "
                f"(reference: {reference.sharpe_ratio:.2f}, "
                f"current: {current_result.sharpe_ratio:.2f})"
            )
        elif sharpe_deviation > sharpe_threshold / 2:
            warnings.append(
                f"Sharpe deviation {sharpe_deviation:.2f} approaching threshold"
            )

        # Drawdown regression
        if drawdown_deviation > tolerance:
            failures.append(
                f"Max drawdown regressed by {drawdown_deviation:.2%} "
                f"(reference: {reference.max_drawdown:.2%}, "
                f"current: {current_result.max_drawdown:.2%})"
            )

        # Trade count regression
        trade_threshold = max(5, int(reference.total_trades * 0.2))  # 20% or 5 trades
        if trade_count_deviation > trade_threshold:
            failures.append(
                f"Trade count changed by {trade_count_deviation} "
                f"(reference: {reference.total_trades}, "
                f"current: {current_result.total_trades})"
            )

        # Execution time regression (warning only)
        if execution_time_deviation > reference.execution_time * 0.5:  # 50% slower
            warnings.append(
                f"Execution time increased by {execution_time_deviation:.2f}s "
                f"(reference: {reference.execution_time:.2f}s, "
                f"current: {current_result.execution_time:.2f}s)"
            )

        # Determine pass/fail
        passed = len(failures) == 0
        failure_message = None if passed else f"{len(failures)} regression(s) detected"

        result = RegressionTestResult(
            test_name=test_name,
            timestamp=datetime.now(),
            passed=passed,

            # Reference
            reference_result=reference,

            # Current results
            current_total_return=current_result.total_return,
            current_sharpe_ratio=current_result.sharpe_ratio,
            current_max_drawdown=current_result.max_drawdown,
            current_total_trades=current_result.total_trades,
            current_execution_time=current_result.execution_time,

            # Deviations
            return_deviation=return_deviation,
            sharpe_deviation=sharpe_deviation,
            drawdown_deviation=drawdown_deviation,
            trade_count_deviation=trade_count_deviation,
            execution_time_deviation=execution_time_deviation,

            # Status
            failures=failures,
            warnings=warnings,
            failure_message=failure_message
        )

        # Log result
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(
            f"Regression test '{test_name}' {status}: "
            f"failures={len(failures)}, warnings={len(warnings)}"
        )

        if failures:
            for failure in failures:
                logger.warning(f"  Failure: {failure}")

        if warnings:
            for warning in warnings:
                logger.info(f"  Warning: {warning}")

        return result

    def test_all_references(
        self,
        signal_generators: Dict[str, Callable[[pd.Series], Tuple[pd.Series, pd.Series]]]
    ) -> Dict[str, RegressionTestResult]:
        """
        Run all regression tests.

        Args:
            signal_generators: Dictionary mapping test names to signal generators

        Returns:
            Dictionary mapping test names to regression test results

        Example:
            >>> generators = {
            ...     "rsi_strategy_v1": rsi_signal_generator,
            ...     "macd_strategy_v1": macd_signal_generator,
            ... }
            >>> results = tester.test_all_references(generators)
            >>> passed = sum(1 for r in results.values() if r.passed)
            >>> print(f"{passed}/{len(results)} tests passed")
        """
        logger.info(f"Running all regression tests ({len(signal_generators)} tests)...")

        results = {}
        for test_name, signal_generator in signal_generators.items():
            try:
                result = self.test_regression(test_name, signal_generator)
                results[test_name] = result

            except FileNotFoundError:
                logger.warning(f"Reference '{test_name}' not found - skipping")

            except Exception as e:
                logger.error(f"Regression test '{test_name}' failed with error: {e}")

        # Summary
        passed = sum(1 for r in results.values() if r.passed)
        logger.info(f"Regression testing complete: {passed}/{len(results)} passed")

        return results

    def list_references(self) -> List[ReferenceResult]:
        """
        List all available reference results.

        Returns:
            List of reference results

        Example:
            >>> references = tester.list_references()
            >>> for ref in references:
            ...     print(f"{ref.test_name}: {ref.description}")
        """
        references = []

        for reference_file in self.reference_dir.glob("*.json"):
            try:
                reference = self._load_reference(reference_file.stem)
                references.append(reference)
            except Exception as e:
                logger.error(f"Failed to load reference {reference_file.name}: {e}")

        return references

    def delete_reference(self, test_name: str):
        """
        Delete a reference result.

        Args:
            test_name: Name of reference to delete

        Example:
            >>> tester.delete_reference("old_strategy_v1")
        """
        reference_path = self.reference_dir / f"{test_name}.json"
        if reference_path.exists():
            reference_path.unlink()
            logger.info(f"Deleted reference '{test_name}'")
        else:
            logger.warning(f"Reference '{test_name}' not found")

    def _hash_config(self) -> str:
        """Generate hash of backtest configuration."""
        config_str = (
            f"{self.config.start_date}_{self.config.end_date}_"
            f"{'_'.join(self.config.tickers)}_{self.config.initial_capital}"
        )
        return str(hash(config_str))

    def _save_reference(self, reference: ReferenceResult):
        """Save reference result to JSON file."""
        reference_path = self.reference_dir / f"{reference.test_name}.json"

        data = asdict(reference)
        data['created_at'] = data['created_at'].isoformat()

        with open(reference_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.debug(f"Saved reference to {reference_path}")

    def _load_reference(self, test_name: str) -> ReferenceResult:
        """Load reference result from JSON file."""
        reference_path = self.reference_dir / f"{test_name}.json"

        if not reference_path.exists():
            raise FileNotFoundError(
                f"Reference '{test_name}' not found at {reference_path}"
            )

        with open(reference_path, 'r') as f:
            data = json.load(f)

        # Convert timestamp string to datetime
        data['created_at'] = datetime.fromisoformat(data['created_at'])

        return ReferenceResult(**data)
