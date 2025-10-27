"""
Engine Validator - Cross-Engine Validation

Validates consistency between vectorbt and custom backtesting engines to ensure
reliable results across different execution strategies.

Purpose:
    - Cross-validate vectorbt vs custom engine results
    - Calculate consistency scores across multiple metrics
    - Generate detailed discrepancy reports
    - Provide automated pass/fail with configurable tolerances

Key Features:
    - Multi-metric consistency scoring (return, trades, sharpe, drawdown)
    - Configurable tolerance thresholds
    - Detailed discrepancy analysis
    - Actionable recommendations
    - Historical validation tracking

Usage:
    from modules.backtesting.validation import EngineValidator
    from modules.backtesting.signal_generators.rsi_strategy import rsi_signal_generator

    validator = EngineValidator(config, data_provider)
    report = validator.validate(signal_generator=rsi_signal_generator, tolerance=0.05)

    if report.validation_passed:
        print("✅ Engines are consistent")
    else:
        print("❌ Inconsistency detected")
        for rec in report.recommendations:
            print(f"  - {rec}")
"""

import time
from dataclasses import dataclass, asdict
from typing import Callable, Tuple, Dict, Any, List, Optional
from datetime import date, datetime
from pathlib import Path
import json
import pandas as pd
from loguru import logger

from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.backtest_runner import BacktestRunner, ComparisonResult, ValidationReport
from modules.backtesting.data_providers.base_data_provider import BaseDataProvider


@dataclass
class ValidationMetrics:
    """Detailed validation metrics for a single run."""

    timestamp: datetime
    signal_generator_name: str
    config_hash: str

    # Engine results
    custom_total_return: float
    custom_sharpe_ratio: float
    custom_max_drawdown: float
    custom_total_trades: int
    custom_execution_time: float

    vectorbt_total_return: float
    vectorbt_sharpe_ratio: float
    vectorbt_max_drawdown: float
    vectorbt_total_trades: int
    vectorbt_execution_time: float

    # Consistency metrics
    consistency_score: float
    return_difference: float
    sharpe_difference: float
    drawdown_difference: float
    trade_count_difference: int
    speedup_factor: float

    # Validation results
    validation_passed: bool
    tolerance_used: float
    discrepancies: Dict[str, Any]
    recommendations: List[str]


class EngineValidator:
    """
    Cross-engine validation framework.

    Validates consistency between vectorbt and custom backtesting engines
    to ensure reliable results across different execution strategies.

    Attributes:
        config: Backtest configuration
        data_provider: Data provider for OHLCV data
        runner: BacktestRunner instance for engine coordination
        validation_history: Historical validation results

    Example:
        >>> config = BacktestConfig(...)
        >>> validator = EngineValidator(config, data_provider)
        >>>
        >>> # Single validation
        >>> report = validator.validate(rsi_signal_generator)
        >>>
        >>> # Batch validation
        >>> results = validator.validate_multiple([rsi_signal_generator, macd_signal_generator])
        >>>
        >>> # View historical results
        >>> history = validator.get_validation_history()
    """

    def __init__(
        self,
        config: BacktestConfig,
        data_provider: BaseDataProvider,
        history_path: Optional[Path] = None
    ):
        """
        Initialize EngineValidator.

        Args:
            config: Backtest configuration
            data_provider: Data provider for OHLCV data
            history_path: Optional path to store validation history (default: logs/validation_history.json)
        """
        self.config = config
        self.data_provider = data_provider
        self.runner = BacktestRunner(config, data_provider)

        # Setup validation history
        if history_path is None:
            history_path = Path(__file__).parent.parent.parent.parent / 'logs' / 'validation_history.json'
        self.history_path = history_path
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing history
        self.validation_history: List[ValidationMetrics] = self._load_history()

        logger.info(
            f"EngineValidator initialized: "
            f"period={config.start_date} to {config.end_date}, "
            f"tickers={len(config.tickers)}, "
            f"history={len(self.validation_history)} records"
        )

    def validate(
        self,
        signal_generator: Callable[[pd.Series], Tuple[pd.Series, pd.Series]],
        tolerance: float = 0.05
    ) -> ValidationReport:
        """
        Validate consistency between engines for a single signal generator.

        Args:
            signal_generator: Signal generation function
            tolerance: Acceptable difference threshold (default: 5%)

        Returns:
            ValidationReport with pass/fail status and recommendations

        Example:
            >>> report = validator.validate(rsi_signal_generator, tolerance=0.05)
            >>> print(f"Passed: {report.validation_passed}")
            >>> print(f"Consistency: {report.consistency_score:.1%}")
        """
        logger.info(f"Starting validation for {signal_generator.__name__}")

        # Run validation using BacktestRunner
        report = self.runner.validate_consistency(
            signal_generator=signal_generator,
            tolerance=tolerance
        )

        # Run comparison to get full metrics
        comparison = self.runner._run_both(signal_generator)

        # Store metrics in history
        metrics = self._create_validation_metrics(
            signal_generator=signal_generator,
            comparison=comparison,
            report=report,
            tolerance=tolerance
        )
        self.validation_history.append(metrics)
        self._save_history()

        logger.info(
            f"Validation {'PASSED' if report.validation_passed else 'FAILED'}: "
            f"consistency={report.consistency_score:.1%}, "
            f"discrepancies={len(report.discrepancies)}"
        )

        return report

    def validate_multiple(
        self,
        signal_generators: List[Callable[[pd.Series], Tuple[pd.Series, pd.Series]]],
        tolerance: float = 0.05
    ) -> Dict[str, ValidationReport]:
        """
        Validate consistency for multiple signal generators.

        Args:
            signal_generators: List of signal generation functions
            tolerance: Acceptable difference threshold

        Returns:
            Dictionary mapping signal generator names to validation reports

        Example:
            >>> generators = [rsi_signal_generator, macd_signal_generator]
            >>> results = validator.validate_multiple(generators)
            >>> for name, report in results.items():
            >>>     print(f"{name}: {'✅' if report.validation_passed else '❌'}")
        """
        logger.info(f"Starting batch validation for {len(signal_generators)} signal generators")

        results = {}
        for i, signal_generator in enumerate(signal_generators, 1):
            logger.info(f"Validating {i}/{len(signal_generators)}: {signal_generator.__name__}")

            try:
                report = self.validate(signal_generator, tolerance)
                results[signal_generator.__name__] = report

            except Exception as e:
                logger.error(f"Validation failed for {signal_generator.__name__}: {e}")
                # Create failed report
                results[signal_generator.__name__] = ValidationReport(
                    validation_passed=False,
                    consistency_score=0.0,
                    discrepancies={'error': str(e)},
                    recommendations=[f"Fix error: {e}"],
                    timestamp=date.today()
                )

        # Summary
        passed = sum(1 for r in results.values() if r.validation_passed)
        logger.info(
            f"Batch validation complete: {passed}/{len(signal_generators)} passed"
        )

        return results

    def get_validation_history(
        self,
        signal_generator_name: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[ValidationMetrics]:
        """
        Retrieve validation history.

        Args:
            signal_generator_name: Optional filter by signal generator name
            limit: Optional limit on number of results

        Returns:
            List of historical validation metrics

        Example:
            >>> # Get all history
            >>> history = validator.get_validation_history()
            >>>
            >>> # Get history for specific signal generator
            >>> rsi_history = validator.get_validation_history(signal_generator_name="rsi_signal_generator")
            >>>
            >>> # Get latest 10 validations
            >>> recent = validator.get_validation_history(limit=10)
        """
        history = self.validation_history

        # Filter by signal generator if specified
        if signal_generator_name:
            history = [
                m for m in history
                if m.signal_generator_name == signal_generator_name
            ]

        # Sort by timestamp (most recent first)
        history = sorted(history, key=lambda m: m.timestamp, reverse=True)

        # Limit results if specified
        if limit:
            history = history[:limit]

        return history

    def get_consistency_trend(
        self,
        signal_generator_name: str,
        window: int = 10
    ) -> pd.DataFrame:
        """
        Get consistency score trend for a signal generator.

        Args:
            signal_generator_name: Name of signal generator
            window: Number of recent validations to include

        Returns:
            DataFrame with timestamp, consistency_score, validation_passed columns

        Example:
            >>> trend = validator.get_consistency_trend("rsi_signal_generator", window=20)
            >>> print(trend.describe())
            >>> trend.plot(x='timestamp', y='consistency_score')
        """
        history = self.get_validation_history(
            signal_generator_name=signal_generator_name,
            limit=window
        )

        if not history:
            return pd.DataFrame()

        data = {
            'timestamp': [m.timestamp for m in history],
            'consistency_score': [m.consistency_score for m in history],
            'validation_passed': [m.validation_passed for m in history],
            'return_difference': [m.return_difference for m in history],
            'trade_count_difference': [m.trade_count_difference for m in history],
        }

        df = pd.DataFrame(data)
        df = df.sort_values('timestamp')
        return df

    def _create_validation_metrics(
        self,
        signal_generator: Callable,
        comparison: ComparisonResult,
        report: ValidationReport,
        tolerance: float
    ) -> ValidationMetrics:
        """Create ValidationMetrics from comparison and report."""
        return ValidationMetrics(
            timestamp=datetime.now(),
            signal_generator_name=signal_generator.__name__,
            config_hash=self._hash_config(),

            # Custom engine results
            custom_total_return=comparison.custom_total_return,
            custom_sharpe_ratio=comparison.custom_sharpe_ratio,
            custom_max_drawdown=comparison.custom_max_drawdown,
            custom_total_trades=comparison.custom_total_trades,
            custom_execution_time=comparison.custom_execution_time,

            # vectorbt results
            vectorbt_total_return=comparison.vectorbt_total_return,
            vectorbt_sharpe_ratio=comparison.vectorbt_sharpe_ratio,
            vectorbt_max_drawdown=comparison.vectorbt_max_drawdown,
            vectorbt_total_trades=comparison.vectorbt_total_trades,
            vectorbt_execution_time=comparison.vectorbt_execution_time,

            # Consistency metrics
            consistency_score=comparison.consistency_score,
            return_difference=comparison.return_difference,
            sharpe_difference=abs(comparison.custom_sharpe_ratio - comparison.vectorbt_sharpe_ratio),
            drawdown_difference=abs(comparison.custom_max_drawdown - comparison.vectorbt_max_drawdown),
            trade_count_difference=comparison.trade_count_difference,
            speedup_factor=comparison.speedup_factor,

            # Validation results
            validation_passed=report.validation_passed,
            tolerance_used=tolerance,
            discrepancies=report.discrepancies,
            recommendations=report.recommendations
        )

    def _hash_config(self) -> str:
        """Generate hash of backtest configuration."""
        config_str = (
            f"{self.config.start_date}_{self.config.end_date}_"
            f"{'_'.join(self.config.tickers)}_{self.config.initial_capital}"
        )
        return str(hash(config_str))

    def _load_history(self) -> List[ValidationMetrics]:
        """Load validation history from JSON file."""
        if not self.history_path.exists():
            return []

        try:
            with open(self.history_path, 'r') as f:
                data = json.load(f)

            history = []
            for item in data:
                # Convert timestamp string to datetime
                item['timestamp'] = datetime.fromisoformat(item['timestamp'])
                metrics = ValidationMetrics(**item)
                history.append(metrics)

            logger.info(f"Loaded {len(history)} validation records from {self.history_path}")
            return history

        except Exception as e:
            logger.error(f"Failed to load validation history: {e}")
            return []

    def _save_history(self):
        """Save validation history to JSON file."""
        try:
            data = []
            for metrics in self.validation_history:
                item = asdict(metrics)
                # Convert datetime to string
                item['timestamp'] = item['timestamp'].isoformat()
                data.append(item)

            with open(self.history_path, 'w') as f:
                json.dump(data, f, indent=2)

            logger.debug(f"Saved {len(data)} validation records to {self.history_path}")

        except Exception as e:
            logger.error(f"Failed to save validation history: {e}")
