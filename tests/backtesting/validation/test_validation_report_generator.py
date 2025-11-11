"""
Test Validation Report Generator

Tests for comprehensive validation report generation with Markdown formatting
and file I/O operations.

Usage:
    PYTHONPATH=/Users/13ruce/spock python3 -m pytest \
        tests/backtesting/validation/test_validation_report_generator.py -v
"""

import pytest
from pathlib import Path
from datetime import datetime
import tempfile
import os

from modules.backtesting.validation.validation_report_generator import (
    ValidationReportGenerator
)
from modules.backtesting.validation.engine_validator import ValidationMetrics


# ============================================================================
# Basic Functionality Tests
# ============================================================================

class TestValidationReportGeneratorBasics:
    """Test basic ValidationReportGenerator functionality."""

    def test_initialization(self):
        """Test ValidationReportGenerator initialization."""
        generator = ValidationReportGenerator()

        # Generator should initialize without errors
        assert generator is not None

    def test_multiple_instances_independent(self):
        """Test that multiple generator instances are independent."""
        gen1 = ValidationReportGenerator()
        gen2 = ValidationReportGenerator()

        # Instances should be independent
        assert gen1 is not gen2


# ============================================================================
# Markdown Generation Tests
# ============================================================================

class TestMarkdownGeneration:
    """Test generate_markdown functionality."""

    def test_generate_markdown_with_single_metric(self):
        """Test Markdown generation with single validation metric."""
        generator = ValidationReportGenerator()

        metrics = ValidationMetrics(
            signal_generator_name="test_strategy",
            consistency_score=0.95,
            return_difference=0.02,
            trade_count_difference=5,
            speedup_factor=100.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        markdown = generator.generate_markdown([metrics])

        # Check report structure
        assert "# Validation Report" in markdown
        assert "## Summary" in markdown
        assert "## Detailed Results" in markdown
        assert "test_strategy" in markdown

    def test_generate_markdown_with_multiple_metrics(self):
        """Test Markdown generation with multiple validation metrics."""
        generator = ValidationReportGenerator()

        metrics_list = [
            ValidationMetrics(
                signal_generator_name="strategy_1",
                consistency_score=0.95,
                return_difference=0.02,
                trade_count_difference=5,
                speedup_factor=100.0,
                validation_passed=True,
                discrepancies={},
                recommendations=[]
            ),
            ValidationMetrics(
                signal_generator_name="strategy_2",
                consistency_score=0.85,
                return_difference=-0.01,
                trade_count_difference=-3,
                speedup_factor=80.0,
                validation_passed=True,
                discrepancies={},
                recommendations=[]
            )
        ]

        markdown = generator.generate_markdown(metrics_list)

        # Both strategies should be in report
        assert "strategy_1" in markdown
        assert "strategy_2" in markdown

    def test_generate_markdown_includes_timestamp(self):
        """Test that generated Markdown includes timestamp."""
        generator = ValidationReportGenerator()

        metrics = ValidationMetrics(
            signal_generator_name="test_strategy",
            consistency_score=0.95,
            return_difference=0.02,
            trade_count_difference=5,
            speedup_factor=100.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        markdown = generator.generate_markdown([metrics])

        # Should include timestamp
        assert "Generated:" in markdown
        # Timestamp format: YYYY-MM-DD HH:MM:SS
        assert datetime.now().strftime('%Y-%m-%d') in markdown


# ============================================================================
# Markdown Formatting Tests
# ============================================================================

class TestMarkdownFormatting:
    """Test Markdown formatting and content."""

    def test_passed_validation_shows_checkmark(self):
        """Test that passed validation shows checkmark emoji."""
        generator = ValidationReportGenerator()

        metrics = ValidationMetrics(
            signal_generator_name="passing_strategy",
            consistency_score=0.95,
            return_difference=0.02,
            trade_count_difference=5,
            speedup_factor=100.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        markdown = generator.generate_markdown([metrics])

        assert "✅ PASSED" in markdown

    def test_failed_validation_shows_cross(self):
        """Test that failed validation shows cross emoji."""
        generator = ValidationReportGenerator()

        metrics = ValidationMetrics(
            signal_generator_name="failing_strategy",
            consistency_score=0.70,
            return_difference=0.15,
            trade_count_difference=20,
            speedup_factor=50.0,
            validation_passed=False,
            discrepancies={"metric": "value"},
            recommendations=["Fix issue"]
        )

        markdown = generator.generate_markdown([metrics])

        assert "❌ FAILED" in markdown

    def test_percentages_formatted_correctly(self):
        """Test that percentages are formatted with correct precision."""
        generator = ValidationReportGenerator()

        metrics = ValidationMetrics(
            signal_generator_name="test_strategy",
            consistency_score=0.9543,
            return_difference=0.0234,
            trade_count_difference=5,
            speedup_factor=100.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        markdown = generator.generate_markdown([metrics])

        # Consistency score: .1% format (95.4%)
        assert "95.4%" in markdown
        # Return difference: .2% format (2.34%)
        assert "2.34%" in markdown or "+2.34%" in markdown

    def test_speedup_factor_formatted_correctly(self):
        """Test that speedup factor is formatted with correct precision."""
        generator = ValidationReportGenerator()

        metrics = ValidationMetrics(
            signal_generator_name="test_strategy",
            consistency_score=0.95,
            return_difference=0.02,
            trade_count_difference=5,
            speedup_factor=123.456,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        markdown = generator.generate_markdown([metrics])

        # Speedup factor: .1f format (123.5x)
        assert "123.5x" in markdown

    def test_trade_count_difference_sign(self):
        """Test that trade count difference includes + or - sign."""
        generator = ValidationReportGenerator()

        # Positive difference
        metrics_positive = ValidationMetrics(
            signal_generator_name="strategy_positive",
            consistency_score=0.95,
            return_difference=0.02,
            trade_count_difference=5,
            speedup_factor=100.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        # Negative difference
        metrics_negative = ValidationMetrics(
            signal_generator_name="strategy_negative",
            consistency_score=0.95,
            return_difference=0.02,
            trade_count_difference=-3,
            speedup_factor=100.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        markdown_positive = generator.generate_markdown([metrics_positive])
        markdown_negative = generator.generate_markdown([metrics_negative])

        # Positive should have + sign
        assert "+5" in markdown_positive
        # Negative should have - sign
        assert "-3" in markdown_negative


# ============================================================================
# Summary Section Tests
# ============================================================================

class TestSummarySection:
    """Test summary section generation."""

    def test_summary_total_tests(self):
        """Test that summary shows correct total test count."""
        generator = ValidationReportGenerator()

        metrics_list = [
            ValidationMetrics(
                signal_generator_name=f"strategy_{i}",
                consistency_score=0.95,
                return_difference=0.02,
                trade_count_difference=5,
                speedup_factor=100.0,
                validation_passed=True,
                discrepancies={},
                recommendations=[]
            )
            for i in range(5)
        ]

        markdown = generator.generate_markdown(metrics_list)

        assert "Total Tests: 5" in markdown

    def test_summary_passed_count(self):
        """Test that summary shows correct passed count."""
        generator = ValidationReportGenerator()

        metrics_list = [
            ValidationMetrics(
                signal_generator_name="strategy_1",
                consistency_score=0.95,
                return_difference=0.02,
                trade_count_difference=5,
                speedup_factor=100.0,
                validation_passed=True,
                discrepancies={},
                recommendations=[]
            ),
            ValidationMetrics(
                signal_generator_name="strategy_2",
                consistency_score=0.95,
                return_difference=0.02,
                trade_count_difference=5,
                speedup_factor=100.0,
                validation_passed=True,
                discrepancies={},
                recommendations=[]
            ),
            ValidationMetrics(
                signal_generator_name="strategy_3",
                consistency_score=0.70,
                return_difference=0.15,
                trade_count_difference=20,
                speedup_factor=50.0,
                validation_passed=False,
                discrepancies={"metric": "value"},
                recommendations=["Fix issue"]
            )
        ]

        markdown = generator.generate_markdown(metrics_list)

        assert "Passed: 2" in markdown
        assert "Failed: 1" in markdown

    def test_summary_pass_rate(self):
        """Test that summary calculates correct pass rate."""
        generator = ValidationReportGenerator()

        metrics_list = [
            ValidationMetrics(
                signal_generator_name="strategy_1",
                consistency_score=0.95,
                return_difference=0.02,
                trade_count_difference=5,
                speedup_factor=100.0,
                validation_passed=True,
                discrepancies={},
                recommendations=[]
            ),
            ValidationMetrics(
                signal_generator_name="strategy_2",
                consistency_score=0.70,
                return_difference=0.15,
                trade_count_difference=20,
                speedup_factor=50.0,
                validation_passed=False,
                discrepancies={},
                recommendations=[]
            )
        ]

        markdown = generator.generate_markdown(metrics_list)

        # 1/2 = 50.0%
        assert "Pass Rate: 50.0%" in markdown


# ============================================================================
# Detailed Results Tests
# ============================================================================

class TestDetailedResults:
    """Test detailed results section generation."""

    def test_detailed_results_includes_all_metrics(self):
        """Test that detailed results include all metric values."""
        generator = ValidationReportGenerator()

        metrics = ValidationMetrics(
            signal_generator_name="comprehensive_strategy",
            consistency_score=0.9543,
            return_difference=0.0234,
            trade_count_difference=5,
            speedup_factor=123.4,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        markdown = generator.generate_markdown([metrics])

        # All metrics should be present
        assert "Consistency Score:" in markdown
        assert "Return Difference:" in markdown
        assert "Trade Count Difference:" in markdown
        assert "Speedup Factor:" in markdown

    def test_detailed_results_strategy_name_as_heading(self):
        """Test that strategy name appears as heading."""
        generator = ValidationReportGenerator()

        metrics = ValidationMetrics(
            signal_generator_name="my_custom_strategy",
            consistency_score=0.95,
            return_difference=0.02,
            trade_count_difference=5,
            speedup_factor=100.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        markdown = generator.generate_markdown([metrics])

        # Strategy name should be in heading (###)
        assert "### my_custom_strategy" in markdown


# ============================================================================
# Discrepancies Section Tests
# ============================================================================

class TestDiscrepancies:
    """Test discrepancies section generation."""

    def test_discrepancies_section_present_when_exists(self):
        """Test that discrepancies section appears when discrepancies exist."""
        generator = ValidationReportGenerator()

        metrics = ValidationMetrics(
            signal_generator_name="strategy_with_issues",
            consistency_score=0.85,
            return_difference=0.10,
            trade_count_difference=10,
            speedup_factor=50.0,
            validation_passed=False,
            discrepancies={
                "returns": "Custom engine: 10%, vectorbt: 12%",
                "trades": "Custom: 50, vectorbt: 60"
            },
            recommendations=[]
        )

        markdown = generator.generate_markdown([metrics])

        assert "**Discrepancies:**" in markdown
        assert "returns:" in markdown
        assert "trades:" in markdown

    def test_discrepancies_section_absent_when_empty(self):
        """Test that discrepancies section is absent when no discrepancies."""
        generator = ValidationReportGenerator()

        metrics = ValidationMetrics(
            signal_generator_name="clean_strategy",
            consistency_score=0.95,
            return_difference=0.02,
            trade_count_difference=5,
            speedup_factor=100.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        markdown = generator.generate_markdown([metrics])

        # Discrepancies section should not appear
        assert "**Discrepancies:**" not in markdown


# ============================================================================
# Recommendations Section Tests
# ============================================================================

class TestRecommendations:
    """Test recommendations section generation."""

    def test_recommendations_section_present_when_exists(self):
        """Test that recommendations section appears when recommendations exist."""
        generator = ValidationReportGenerator()

        metrics = ValidationMetrics(
            signal_generator_name="strategy_needs_improvement",
            consistency_score=0.80,
            return_difference=0.08,
            trade_count_difference=15,
            speedup_factor=60.0,
            validation_passed=False,
            discrepancies={},
            recommendations=[
                "Review signal generation logic",
                "Check transaction cost calculations",
                "Validate entry/exit timing"
            ]
        )

        markdown = generator.generate_markdown([metrics])

        assert "**Recommendations:**" in markdown
        assert "Review signal generation logic" in markdown
        assert "Check transaction cost calculations" in markdown
        assert "Validate entry/exit timing" in markdown

    def test_recommendations_section_absent_when_empty(self):
        """Test that recommendations section is absent when no recommendations."""
        generator = ValidationReportGenerator()

        metrics = ValidationMetrics(
            signal_generator_name="perfect_strategy",
            consistency_score=0.95,
            return_difference=0.02,
            trade_count_difference=5,
            speedup_factor=100.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        markdown = generator.generate_markdown([metrics])

        # Recommendations section should not appear
        assert "**Recommendations:**" not in markdown


# ============================================================================
# File Operations Tests
# ============================================================================

class TestFileOperations:
    """Test file I/O operations."""

    def test_save_markdown_creates_file(self):
        """Test that save_markdown creates file successfully."""
        generator = ValidationReportGenerator()

        metrics = ValidationMetrics(
            signal_generator_name="test_strategy",
            consistency_score=0.95,
            return_difference=0.02,
            trade_count_difference=5,
            speedup_factor=100.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        markdown = generator.generate_markdown([metrics])

        # Use temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
            temp_path = Path(f.name)

        try:
            generator.save_markdown(markdown, temp_path)

            # File should exist
            assert temp_path.exists()

            # File should contain markdown content
            with open(temp_path, 'r') as f:
                content = f.read()

            assert "# Validation Report" in content
            assert "test_strategy" in content
        finally:
            # Cleanup
            if temp_path.exists():
                os.unlink(temp_path)

    def test_save_markdown_content_matches(self):
        """Test that saved markdown content matches generated content."""
        generator = ValidationReportGenerator()

        metrics = ValidationMetrics(
            signal_generator_name="content_test_strategy",
            consistency_score=0.9543,
            return_difference=0.0234,
            trade_count_difference=5,
            speedup_factor=123.4,
            validation_passed=True,
            discrepancies={"key": "value"},
            recommendations=["recommendation 1", "recommendation 2"]
        )

        markdown = generator.generate_markdown([metrics])

        # Use temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
            temp_path = Path(f.name)

        try:
            generator.save_markdown(markdown, temp_path)

            # Read saved content
            with open(temp_path, 'r') as f:
                saved_content = f.read()

            # Content should match exactly
            assert saved_content == markdown
        finally:
            # Cleanup
            if temp_path.exists():
                os.unlink(temp_path)

    def test_save_markdown_overwrites_existing_file(self):
        """Test that save_markdown overwrites existing file."""
        generator = ValidationReportGenerator()

        metrics = ValidationMetrics(
            signal_generator_name="overwrite_test",
            consistency_score=0.95,
            return_difference=0.02,
            trade_count_difference=5,
            speedup_factor=100.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        markdown = generator.generate_markdown([metrics])

        # Use temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md') as f:
            temp_path = Path(f.name)
            f.write("OLD CONTENT THAT SHOULD BE REPLACED")

        try:
            generator.save_markdown(markdown, temp_path)

            # Read content
            with open(temp_path, 'r') as f:
                content = f.read()

            # Old content should be gone
            assert "OLD CONTENT" not in content
            # New content should be present
            assert "# Validation Report" in content
        finally:
            # Cleanup
            if temp_path.exists():
                os.unlink(temp_path)


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_metrics_list_handled(self):
        """Test handling of empty metrics list."""
        generator = ValidationReportGenerator()

        markdown = generator.generate_markdown([])

        # Should still generate report structure
        assert "# Validation Report" in markdown
        assert "## Summary" in markdown
        # Total tests should be 0
        assert "Total Tests: 0" in markdown

    def test_zero_consistency_score(self):
        """Test formatting with zero consistency score."""
        generator = ValidationReportGenerator()

        metrics = ValidationMetrics(
            signal_generator_name="zero_consistency",
            consistency_score=0.0,
            return_difference=0.50,
            trade_count_difference=100,
            speedup_factor=1.0,
            validation_passed=False,
            discrepancies={},
            recommendations=[]
        )

        markdown = generator.generate_markdown([metrics])

        # 0.0% should be formatted correctly
        assert "0.0%" in markdown

    def test_very_high_speedup_factor(self):
        """Test formatting with very high speedup factor."""
        generator = ValidationReportGenerator()

        metrics = ValidationMetrics(
            signal_generator_name="extreme_speedup",
            consistency_score=0.95,
            return_difference=0.02,
            trade_count_difference=5,
            speedup_factor=9999.9,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        markdown = generator.generate_markdown([metrics])

        # Very high speedup should be formatted
        assert "9999.9x" in markdown

    def test_negative_return_difference(self):
        """Test formatting with negative return difference."""
        generator = ValidationReportGenerator()

        metrics = ValidationMetrics(
            signal_generator_name="negative_return",
            consistency_score=0.95,
            return_difference=-0.0543,
            trade_count_difference=-10,
            speedup_factor=100.0,
            validation_passed=True,
            discrepancies={},
            recommendations=[]
        )

        markdown = generator.generate_markdown([metrics])

        # Negative percentage should include - sign
        assert "-5.43%" in markdown or "-5.4%" in markdown
