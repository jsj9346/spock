"""
Validation Report Generator - Comprehensive Validation Reports

Generates detailed, human-readable validation reports with visualizations
and actionable recommendations.

Purpose:
    - Generate comprehensive validation reports
    - Include performance metrics, consistency scores
    - Provide actionable recommendations
    - Export to multiple formats (HTML, PDF, Markdown)

Usage:
    from modules.backtesting.validation import ValidationReportGenerator

    generator = ValidationReportGenerator()
    report_html = generator.generate_html(validation_metrics)
"""

from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path
from loguru import logger

from .engine_validator import ValidationMetrics


class ValidationReportGenerator:
    """
    Validation report generator.

    Generates comprehensive, human-readable reports from validation results.

    Example:
        >>> generator = ValidationReportGenerator()
        >>> html = generator.generate_html(metrics_list)
        >>> generator.save_html(html, "validation_report.html")
    """

    def __init__(self):
        """Initialize ValidationReportGenerator."""
        logger.info("ValidationReportGenerator initialized")

    def generate_markdown(self, metrics_list: List[ValidationMetrics]) -> str:
        """
        Generate Markdown validation report.

        Args:
            metrics_list: List of validation metrics

        Returns:
            Markdown formatted report

        Example:
            >>> md = generator.generate_markdown(metrics)
            >>> print(md)
        """
        lines = []
        lines.append("# Validation Report")
        lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        lines.append("## Summary\n")
        passed = sum(1 for m in metrics_list if m.validation_passed)
        lines.append(f"- Total Tests: {len(metrics_list)}")
        lines.append(f"- Passed: {passed}")
        lines.append(f"- Failed: {len(metrics_list) - passed}")
        lines.append(f"- Pass Rate: {passed/len(metrics_list):.1%}\n")

        lines.append("## Detailed Results\n")
        for metrics in metrics_list:
            status = "✅ PASSED" if metrics.validation_passed else "❌ FAILED"
            lines.append(f"### {metrics.signal_generator_name} - {status}\n")
            lines.append(f"- Consistency Score: {metrics.consistency_score:.1%}")
            lines.append(f"- Return Difference: {metrics.return_difference:+.2%}")
            lines.append(f"- Trade Count Difference: {metrics.trade_count_difference:+d}")
            lines.append(f"- Speedup Factor: {metrics.speedup_factor:.1f}x\n")

            if metrics.discrepancies:
                lines.append("**Discrepancies:**")
                for key, value in metrics.discrepancies.items():
                    lines.append(f"- {key}: {value}")
                lines.append("")

            if metrics.recommendations:
                lines.append("**Recommendations:**")
                for rec in metrics.recommendations:
                    lines.append(f"- {rec}")
                lines.append("")

        return "\n".join(lines)

    def save_markdown(self, markdown: str, filepath: Path):
        """Save Markdown report to file."""
        with open(filepath, 'w') as f:
            f.write(markdown)
        logger.info(f"Saved validation report to {filepath}")
