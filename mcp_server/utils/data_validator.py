"""
Data Quality Validator for MCP Server

Provides validation functions to detect data anomalies and quality issues
during data collection and API responses.

Key Validations:
- Zero/NULL value detection for critical fields
- Outlier detection for valuation metrics
- Cross-field consistency checks
- Temporal consistency (data freshness)
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date, timedelta
from dataclasses import dataclass
from enum import Enum
import structlog

logger = structlog.get_logger()


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """Represents a single validation issue."""
    field: str
    severity: ValidationSeverity
    message: str
    value: Any = None
    expected: str = None


class DataValidator:
    """
    Data quality validator for fundamental data.

    Performs various quality checks on fundamental data records
    and returns structured validation results.
    """

    # Fields that should never be zero for valid records
    CRITICAL_FIELDS = ['market_cap', 'shares_outstanding']

    # Fields that commonly have zero values (not errors)
    ZERO_ALLOWED_FIELDS = ['dividend_yield', 'dividend_per_share', 'fcf', 'operating_cash_flow']

    # Valuation metric ranges (typical for most markets)
    VALUATION_RANGES = {
        'per': {'min': -1000, 'max': 1000, 'typical_min': 0, 'typical_max': 100},
        'pbr': {'min': 0, 'max': 100, 'typical_min': 0.1, 'typical_max': 10},
        'psr': {'min': 0, 'max': 100, 'typical_min': 0.1, 'typical_max': 20},
        'dividend_yield': {'min': 0, 'max': 50, 'typical_min': 0, 'typical_max': 15},
    }

    def __init__(self):
        self.issues: List[ValidationIssue] = []

    def reset(self):
        """Reset validation issues for new validation run."""
        self.issues = []

    def validate_fundamentals(
        self,
        data: Dict[str, Any],
        context: str = "unknown"
    ) -> Tuple[bool, List[ValidationIssue]]:
        """
        Validate fundamental data record.

        Args:
            data: Fundamental data dictionary
            context: Context string for logging (e.g., ticker)

        Returns:
            Tuple of (is_valid, issues_list)
        """
        self.reset()

        # Check for completely empty data
        if not data:
            self.issues.append(ValidationIssue(
                field="data",
                severity=ValidationSeverity.ERROR,
                message="Empty data record"
            ))
            return False, self.issues

        # Check critical fields
        self._validate_critical_fields(data, context)

        # Check valuation metrics
        self._validate_valuation_metrics(data, context)

        # Check all-zero valuation (invalid record)
        self._validate_not_all_zeros(data, context)

        # Check data freshness
        self._validate_data_freshness(data, context)

        # Check cross-field consistency
        self._validate_cross_field_consistency(data, context)

        # Determine overall validity
        has_errors = any(i.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]
                        for i in self.issues)

        return not has_errors, self.issues

    def _validate_critical_fields(self, data: Dict, context: str):
        """Check critical fields are present and valid."""
        for field in self.CRITICAL_FIELDS:
            value = data.get(field)
            if value is None:
                self.issues.append(ValidationIssue(
                    field=field,
                    severity=ValidationSeverity.WARNING,
                    message=f"Missing critical field: {field}",
                    value=None,
                    expected="Non-null value"
                ))
            elif value == 0:
                self.issues.append(ValidationIssue(
                    field=field,
                    severity=ValidationSeverity.ERROR,
                    message=f"Zero value in critical field: {field}",
                    value=0,
                    expected="Positive value"
                ))

    def _validate_valuation_metrics(self, data: Dict, context: str):
        """Check valuation metrics are within expected ranges."""
        for field, ranges in self.VALUATION_RANGES.items():
            value = data.get(field)
            if value is None:
                continue

            try:
                value = float(value)
            except (TypeError, ValueError):
                continue

            # Check absolute bounds
            if value < ranges['min'] or value > ranges['max']:
                self.issues.append(ValidationIssue(
                    field=field,
                    severity=ValidationSeverity.ERROR,
                    message=f"{field} out of bounds: {value}",
                    value=value,
                    expected=f"{ranges['min']} to {ranges['max']}"
                ))
            # Check typical ranges (warning only)
            elif value < ranges['typical_min'] or value > ranges['typical_max']:
                self.issues.append(ValidationIssue(
                    field=field,
                    severity=ValidationSeverity.INFO,
                    message=f"{field} outside typical range: {value}",
                    value=value,
                    expected=f"Typical: {ranges['typical_min']} to {ranges['typical_max']}"
                ))

    def _validate_not_all_zeros(self, data: Dict, context: str):
        """Check that not all valuation metrics are zero (invalid record)."""
        valuation_fields = ['per', 'pbr', 'dividend_yield']
        all_zero = all(
            data.get(f) in [0, 0.0, None]
            for f in valuation_fields
        )

        if all_zero:
            self.issues.append(ValidationIssue(
                field="valuation",
                severity=ValidationSeverity.CRITICAL,
                message="All valuation metrics are zero or null - invalid record",
                value={"per": data.get("per"), "pbr": data.get("pbr")},
                expected="At least one non-zero valuation metric"
            ))

    def _validate_data_freshness(self, data: Dict, context: str):
        """Check data is recent enough."""
        data_date = data.get("date")
        if data_date is None:
            return

        # Convert to date if needed
        if isinstance(data_date, str):
            try:
                data_date = datetime.strptime(data_date[:10], "%Y-%m-%d").date()
            except ValueError:
                return
        elif isinstance(data_date, datetime):
            data_date = data_date.date()

        # Check if data is stale (more than 7 days old for DAILY)
        period_type = data.get("period_type", "DAILY")
        if period_type == "DAILY":
            max_age = timedelta(days=7)
            if date.today() - data_date > max_age:
                self.issues.append(ValidationIssue(
                    field="date",
                    severity=ValidationSeverity.WARNING,
                    message=f"Data may be stale: {data_date}",
                    value=str(data_date),
                    expected=f"Within last {max_age.days} days"
                ))

    def _validate_cross_field_consistency(self, data: Dict, context: str):
        """Check consistency between related fields."""
        # Revenue should be positive if net_income is present
        revenue = data.get("revenue")
        net_income = data.get("net_income")

        if revenue is not None and net_income is not None:
            try:
                revenue = float(revenue)
                net_income = float(net_income)

                # Net margin > 100% is suspicious
                if revenue > 0 and abs(net_income / revenue) > 1:
                    self.issues.append(ValidationIssue(
                        field="net_margin",
                        severity=ValidationSeverity.WARNING,
                        message=f"Unusual net margin: {net_income/revenue*100:.1f}%",
                        value=net_income / revenue,
                        expected="Net margin typically < 100%"
                    ))
            except (TypeError, ValueError, ZeroDivisionError):
                pass

    def get_summary(self) -> Dict:
        """Get summary of validation results."""
        return {
            "total_issues": len(self.issues),
            "by_severity": {
                "critical": sum(1 for i in self.issues if i.severity == ValidationSeverity.CRITICAL),
                "error": sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR),
                "warning": sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING),
                "info": sum(1 for i in self.issues if i.severity == ValidationSeverity.INFO),
            },
            "issues": [
                {
                    "field": i.field,
                    "severity": i.severity.value,
                    "message": i.message,
                    "value": str(i.value) if i.value is not None else None,
                    "expected": i.expected
                }
                for i in self.issues
            ]
        }


def validate_daily_fundamentals(data: Dict, ticker: str = "unknown") -> Tuple[bool, Dict]:
    """
    Convenience function to validate daily fundamentals.

    Args:
        data: Fundamental data dictionary
        ticker: Ticker symbol for context

    Returns:
        Tuple of (is_valid, validation_summary)
    """
    validator = DataValidator()
    is_valid, issues = validator.validate_fundamentals(data, context=ticker)
    return is_valid, validator.get_summary()


def filter_invalid_records(records: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Filter out invalid records from a list.

    Args:
        records: List of fundamental data records

    Returns:
        Tuple of (valid_records, invalid_records)
    """
    validator = DataValidator()
    valid = []
    invalid = []

    for record in records:
        is_valid, _ = validator.validate_fundamentals(record)
        if is_valid:
            valid.append(record)
        else:
            invalid.append(record)

    return valid, invalid
