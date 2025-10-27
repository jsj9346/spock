"""
Consistency Monitor - Real-time Consistency Monitoring

Real-time monitoring of consistency between backtesting engines during
development and testing workflows.

Purpose:
    - Real-time consistency monitoring
    - Alert on degradation
    - Track consistency trends
    - Integration with validation framework

Usage:
    from modules.backtesting.validation import ConsistencyMonitor

    monitor = ConsistencyMonitor(config, data_provider)
    monitor.start_monitoring(signal_generators_dict)
"""

from typing import Dict, Callable, Tuple, List
from datetime import datetime, timedelta
import pandas as pd
from loguru import logger

from modules.backtesting.backtest_config import BacktestConfig
from modules.backtesting.data_providers.base_data_provider import BaseDataProvider
from .engine_validator import EngineValidator


class ConsistencyMonitor:
    """
    Real-time consistency monitoring.

    Monitors consistency between engines and alerts on degradation.

    Example:
        >>> monitor = ConsistencyMonitor(config, data_provider)
        >>> status = monitor.check_consistency(signal_generator)
        >>> if not status['passed']:
        ...     print(f"Alert: {status['message']}")
    """

    def __init__(
        self,
        config: BacktestConfig,
        data_provider: BaseDataProvider,
        alert_threshold: float = 0.90  # Alert if consistency <90%
    ):
        """
        Initialize ConsistencyMonitor.

        Args:
            config: Backtest configuration
            data_provider: Data provider
            alert_threshold: Consistency threshold for alerts
        """
        self.config = config
        self.data_provider = data_provider
        self.alert_threshold = alert_threshold
        self.validator = EngineValidator(config, data_provider)

        logger.info(f"ConsistencyMonitor initialized (alert_threshold={alert_threshold:.1%})")

    def check_consistency(
        self,
        signal_generator: Callable[[pd.Series], Tuple[pd.Series, pd.Series]],
        tolerance: float = 0.05
    ) -> Dict:
        """
        Check consistency for a signal generator.

        Args:
            signal_generator: Signal generation function
            tolerance: Validation tolerance

        Returns:
            Dictionary with status information

        Example:
            >>> status = monitor.check_consistency(rsi_signal_generator)
            >>> print(f"Consistency: {status['consistency_score']:.1%}")
        """
        report = self.validator.validate(signal_generator, tolerance)

        status = {
            'passed': report.consistency_score >= self.alert_threshold,
            'consistency_score': report.consistency_score,
            'validation_passed': report.validation_passed,
            'message': self._generate_message(report),
            'timestamp': datetime.now()
        }

        if not status['passed']:
            logger.warning(
                f"🚨 Consistency alert: {signal_generator.__name__} "
                f"scored {report.consistency_score:.1%} "
                f"(threshold: {self.alert_threshold:.1%})"
            )

        return status

    def _generate_message(self, report) -> str:
        """Generate status message from validation report."""
        if report.validation_passed:
            return f"✅ Consistent ({report.consistency_score:.1%})"
        else:
            return f"❌ Inconsistent ({report.consistency_score:.1%})"
