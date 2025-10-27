"""
Overfitting Detector - Strategy Overfitting Detection

Detects overfitted strategies by analyzing in-sample vs out-of-sample
performance degradation and parameter stability.

Purpose:
    - Detect overfitted strategies
    - Analyze in-sample vs out-of-sample performance
    - Check parameter sensitivity
    - Validate strategy robustness

Usage:
    from modules.backtesting.optimization import OverfittingDetector

    detector = OverfittingDetector()
    is_overfit = detector.detect_overfitting(
        in_sample_sharpe=2.5,
        out_of_sample_sharpe=0.8,
        param_sensitivity=0.7
    )
"""

from dataclasses import dataclass
from typing import Optional
from loguru import logger


@dataclass
class OverfittingReport:
    """Overfitting detection report."""

    is_overfit: bool
    degradation_pct: float
    robustness_score: float
    warning_flags: list[str]
    recommendations: list[str]


class OverfittingDetector:
    """
    Overfitting detection framework.

    Analyzes strategy performance to detect overfitting patterns.

    Example:
        >>> detector = OverfittingDetector()
        >>> report = detector.detect_overfitting(
        ...     in_sample_sharpe=2.5,
        ...     out_of_sample_sharpe=0.8
        ... )
        >>> if report.is_overfit:
        ...     print("Warning: Strategy appears overfit")
        ...     for rec in report.recommendations:
        ...         print(f"  - {rec}")
    """

    def __init__(
        self,
        degradation_threshold: float = 0.20,  # 20% degradation
        robustness_threshold: float = 0.5  # Minimum robustness score
    ):
        """
        Initialize OverfittingDetector.

        Args:
            degradation_threshold: Maximum acceptable performance degradation
            robustness_threshold: Minimum acceptable robustness score
        """
        self.degradation_threshold = degradation_threshold
        self.robustness_threshold = robustness_threshold

        logger.info(
            f"OverfittingDetector initialized: "
            f"degradation_threshold={degradation_threshold:.1%}, "
            f"robustness_threshold={robustness_threshold:.2f}"
        )

    def detect_overfitting(
        self,
        in_sample_sharpe: float,
        out_of_sample_sharpe: float,
        param_sensitivity: Optional[float] = None
    ) -> OverfittingReport:
        """
        Detect overfitting based on performance metrics.

        Args:
            in_sample_sharpe: In-sample Sharpe ratio
            out_of_sample_sharpe: Out-of-sample Sharpe ratio
            param_sensitivity: Optional parameter sensitivity score (0-1)

        Returns:
            OverfittingReport with detection results

        Example:
            >>> report = detector.detect_overfitting(2.5, 0.8)
            >>> print(f"Overfit: {report.is_overfit}")
        """
        # Calculate degradation
        if in_sample_sharpe == 0:
            degradation_pct = 0.0
        else:
            degradation_pct = (in_sample_sharpe - out_of_sample_sharpe) / in_sample_sharpe

        # Calculate robustness score (higher is better)
        robustness_score = 1.0 - abs(degradation_pct)
        if param_sensitivity is not None:
            robustness_score *= (1.0 - param_sensitivity)  # Penalize high sensitivity

        # Detect overfitting
        warning_flags = []
        recommendations = []

        # Check degradation
        if degradation_pct > self.degradation_threshold:
            warning_flags.append(f"High degradation: {degradation_pct:.1%}")
            recommendations.append("Reduce model complexity or increase training data")

        # Check robustness
        if robustness_score < self.robustness_threshold:
            warning_flags.append(f"Low robustness: {robustness_score:.2f}")
            recommendations.append("Validate with walk-forward analysis")

        # Check parameter sensitivity
        if param_sensitivity is not None and param_sensitivity > 0.5:
            warning_flags.append(f"High parameter sensitivity: {param_sensitivity:.2f}")
            recommendations.append("Find more robust parameter ranges")

        is_overfit = len(warning_flags) > 0

        report = OverfittingReport(
            is_overfit=is_overfit,
            degradation_pct=degradation_pct,
            robustness_score=robustness_score,
            warning_flags=warning_flags,
            recommendations=recommendations if is_overfit else ["Strategy appears robust"]
        )

        if is_overfit:
            logger.warning(f"Overfitting detected: {len(warning_flags)} warnings")
        else:
            logger.info(f"No overfitting detected (robustness={robustness_score:.2f})")

        return report
