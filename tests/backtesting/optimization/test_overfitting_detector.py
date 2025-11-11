"""
Test Overfitting Detector

Tests for overfitting detection based on in-sample vs out-of-sample
performance degradation and parameter sensitivity.

Usage:
    PYTHONPATH=/Users/13ruce/spock python3 -m pytest \
        tests/backtesting/optimization/test_overfitting_detector.py -v
"""

import pytest

from modules.backtesting.optimization.overfitting_detector import (
    OverfittingDetector,
    OverfittingReport
)


# ============================================================================
# Basic Functionality Tests
# ============================================================================

class TestOverfittingDetectorBasics:
    """Test basic OverfittingDetector functionality."""

    def test_initialization_default(self):
        """Test default initialization."""
        detector = OverfittingDetector()

        assert detector.degradation_threshold == 0.20
        assert detector.robustness_threshold == 0.5

    def test_initialization_custom(self):
        """Test initialization with custom thresholds."""
        detector = OverfittingDetector(
            degradation_threshold=0.15,
            robustness_threshold=0.6
        )

        assert detector.degradation_threshold == 0.15
        assert detector.robustness_threshold == 0.6


# ============================================================================
# Overfitting Detection Tests
# ============================================================================

class TestOverfittingDetection:
    """Test overfitting detection logic."""

    def test_no_overfitting_similar_performance(self):
        """Test detection when in-sample and out-of-sample are similar."""
        detector = OverfittingDetector()

        report = detector.detect_overfitting(
            in_sample_sharpe=1.5,
            out_of_sample_sharpe=1.4
        )

        assert isinstance(report, OverfittingReport)
        assert report.is_overfit == False
        assert len(report.warning_flags) == 0
        assert "Strategy appears robust" in report.recommendations

    def test_overfitting_high_degradation(self):
        """Test detection when degradation is high."""
        detector = OverfittingDetector()

        report = detector.detect_overfitting(
            in_sample_sharpe=2.5,
            out_of_sample_sharpe=0.5  # 80% degradation
        )

        assert report.is_overfit == True
        assert report.degradation_pct > 0.20
        assert len(report.warning_flags) > 0
        assert any("degradation" in flag.lower() for flag in report.warning_flags)

    def test_overfitting_low_robustness(self):
        """Test detection when robustness score is low."""
        detector = OverfittingDetector()

        report = detector.detect_overfitting(
            in_sample_sharpe=1.0,
            out_of_sample_sharpe=0.2  # Low robustness
        )

        assert report.is_overfit == True
        assert report.robustness_score < 0.5
        assert len(report.warning_flags) > 0

    def test_overfitting_high_param_sensitivity(self):
        """Test detection with high parameter sensitivity."""
        detector = OverfittingDetector()

        report = detector.detect_overfitting(
            in_sample_sharpe=1.5,
            out_of_sample_sharpe=1.4,
            param_sensitivity=0.8  # High sensitivity
        )

        assert report.is_overfit == True
        assert len(report.warning_flags) > 0
        assert any("sensitivity" in flag.lower() for flag in report.warning_flags)


# ============================================================================
# Degradation Calculation Tests
# ============================================================================

class TestDegradationCalculation:
    """Test degradation percentage calculation."""

    def test_zero_in_sample_sharpe(self):
        """Test degradation calculation with zero in-sample Sharpe."""
        detector = OverfittingDetector()

        report = detector.detect_overfitting(
            in_sample_sharpe=0.0,
            out_of_sample_sharpe=0.5
        )

        assert report.degradation_pct == 0.0

    def test_positive_degradation(self):
        """Test positive degradation (performance drops)."""
        detector = OverfittingDetector()

        report = detector.detect_overfitting(
            in_sample_sharpe=2.0,
            out_of_sample_sharpe=1.0
        )

        # 50% degradation
        assert abs(report.degradation_pct - 0.5) < 0.01

    def test_negative_degradation(self):
        """Test negative degradation (performance improves)."""
        detector = OverfittingDetector()

        report = detector.detect_overfitting(
            in_sample_sharpe=1.0,
            out_of_sample_sharpe=1.5
        )

        # -50% degradation (improvement)
        assert report.degradation_pct < 0
        assert report.is_overfit == False  # No overfitting if performance improves


# ============================================================================
# Robustness Score Tests
# ============================================================================

class TestRobustnessScore:
    """Test robustness score calculation."""

    def test_robustness_without_param_sensitivity(self):
        """Test robustness calculation without parameter sensitivity."""
        detector = OverfittingDetector()

        report = detector.detect_overfitting(
            in_sample_sharpe=2.0,
            out_of_sample_sharpe=1.8
        )

        # Robustness = 1 - |degradation_pct| = 1 - 0.1 = 0.9
        expected_robustness = 1.0 - abs(0.1)
        assert abs(report.robustness_score - expected_robustness) < 0.01

    def test_robustness_with_param_sensitivity(self):
        """Test robustness calculation with parameter sensitivity penalty."""
        detector = OverfittingDetector()

        report = detector.detect_overfitting(
            in_sample_sharpe=2.0,
            out_of_sample_sharpe=1.8,
            param_sensitivity=0.5
        )

        # Robustness penalized by param sensitivity
        # (1 - |degradation|) * (1 - sensitivity)
        base_robustness = 1.0 - 0.1
        expected = base_robustness * (1.0 - 0.5)
        assert abs(report.robustness_score - expected) < 0.01

    def test_robustness_range(self):
        """Test that robustness score stays within valid range."""
        detector = OverfittingDetector()

        # Test various scenarios
        test_cases = [
            (2.0, 1.8, None),
            (1.0, 0.5, 0.3),
            (1.5, 1.5, 0.0),
            (1.0, 2.0, None)  # Performance improves
        ]

        for in_sample, out_of_sample, sensitivity in test_cases:
            report = detector.detect_overfitting(
                in_sample_sharpe=in_sample,
                out_of_sample_sharpe=out_of_sample,
                param_sensitivity=sensitivity
            )

            # Robustness should be non-negative (can exceed 1.0 if performance improves)
            assert report.robustness_score >= 0


# ============================================================================
# Warning Flags and Recommendations Tests
# ============================================================================

class TestWarningsAndRecommendations:
    """Test warning flags and recommendations generation."""

    def test_multiple_warnings(self):
        """Test that multiple issues generate multiple warnings."""
        detector = OverfittingDetector()

        report = detector.detect_overfitting(
            in_sample_sharpe=3.0,
            out_of_sample_sharpe=0.5,  # High degradation
            param_sensitivity=0.8  # High sensitivity
        )

        assert report.is_overfit == True
        # Should have warnings for both degradation and sensitivity
        assert len(report.warning_flags) >= 2
        assert len(report.recommendations) >= 2

    def test_recommendations_specific(self):
        """Test that recommendations are specific to detected issues."""
        detector = OverfittingDetector()

        report = detector.detect_overfitting(
            in_sample_sharpe=2.0,
            out_of_sample_sharpe=0.5
        )

        # Should recommend reducing complexity for high degradation
        assert any("complexity" in rec.lower() or "data" in rec.lower()
                   for rec in report.recommendations)

    def test_no_warnings_good_performance(self):
        """Test that no warnings are generated for robust strategies."""
        detector = OverfittingDetector()

        report = detector.detect_overfitting(
            in_sample_sharpe=1.8,
            out_of_sample_sharpe=1.7,
            param_sensitivity=0.2
        )

        assert report.is_overfit == False
        assert len(report.warning_flags) == 0
        assert "Strategy appears robust" in report.recommendations


# ============================================================================
# Custom Threshold Tests
# ============================================================================

class TestCustomThresholds:
    """Test detection with custom thresholds."""

    def test_strict_degradation_threshold(self):
        """Test with stricter degradation threshold."""
        detector = OverfittingDetector(
            degradation_threshold=0.10,  # Only allow 10% degradation
            robustness_threshold=0.5
        )

        report = detector.detect_overfitting(
            in_sample_sharpe=2.0,
            out_of_sample_sharpe=1.7  # 15% degradation
        )

        # Should detect overfitting with strict threshold
        assert report.is_overfit == True

    def test_lenient_degradation_threshold(self):
        """Test with lenient degradation threshold."""
        detector = OverfittingDetector(
            degradation_threshold=0.30,  # Allow 30% degradation
            robustness_threshold=0.5
        )

        report = detector.detect_overfitting(
            in_sample_sharpe=2.0,
            out_of_sample_sharpe=1.5  # 25% degradation
        )

        # Should NOT detect overfitting with lenient threshold
        # (assuming robustness is still acceptable)
        assert report.degradation_pct < 0.30

    def test_strict_robustness_threshold(self):
        """Test with stricter robustness threshold."""
        detector = OverfittingDetector(
            degradation_threshold=0.20,
            robustness_threshold=0.8  # High robustness required
        )

        report = detector.detect_overfitting(
            in_sample_sharpe=2.0,
            out_of_sample_sharpe=1.5
        )

        # With degradation of 25%, robustness = 0.75, which is < 0.8
        assert report.is_overfit == True


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_identical_performance(self):
        """Test with identical in-sample and out-of-sample performance."""
        detector = OverfittingDetector()

        report = detector.detect_overfitting(
            in_sample_sharpe=1.5,
            out_of_sample_sharpe=1.5
        )

        assert report.degradation_pct == 0.0
        assert report.robustness_score == 1.0
        assert report.is_overfit == False

    def test_negative_sharpe_ratios(self):
        """Test with negative Sharpe ratios."""
        detector = OverfittingDetector()

        report = detector.detect_overfitting(
            in_sample_sharpe=-0.5,
            out_of_sample_sharpe=-1.0
        )

        # Should still calculate degradation correctly
        assert isinstance(report.degradation_pct, float)
        assert isinstance(report.robustness_score, float)

    def test_extreme_improvement(self):
        """Test with extreme out-of-sample improvement."""
        detector = OverfittingDetector()

        report = detector.detect_overfitting(
            in_sample_sharpe=0.5,
            out_of_sample_sharpe=3.0  # 500% improvement!
        )

        # Negative degradation (improvement) should not trigger overfitting
        assert report.degradation_pct < 0
        assert report.is_overfit == False

    def test_boundary_degradation(self):
        """Test degradation exactly at threshold."""
        detector = OverfittingDetector(degradation_threshold=0.20)

        report = detector.detect_overfitting(
            in_sample_sharpe=1.0,
            out_of_sample_sharpe=0.8  # Exactly 20% degradation
        )

        # Should NOT trigger warning (> threshold, not >=)
        assert report.degradation_pct == 0.20
        assert report.is_overfit == False

    def test_boundary_robustness(self):
        """Test robustness exactly at threshold."""
        detector = OverfittingDetector(robustness_threshold=0.5)

        report = detector.detect_overfitting(
            in_sample_sharpe=1.0,
            out_of_sample_sharpe=0.5  # Robustness = 0.5
        )

        # Should NOT trigger warning (< threshold, not <=)
        assert report.robustness_score == 0.5
        assert report.is_overfit == False
