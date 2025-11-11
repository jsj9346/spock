# mcp_server/utils/validators.py
"""
Input validation utilities for MCP server

Provides comprehensive validation for tickers, dates, strategy configurations,
and project path restrictions.
"""

import os
import re
from datetime import datetime
from typing import Dict, List

from .errors import ValidationError, PathValidationError


def validate_tickers(tickers: List[str], region: str = "KR") -> None:
    """
    Validate ticker symbols based on region.

    Args:
        tickers: List of ticker symbols
        region: Market region ("KR" or "US")

    Raises:
        ValidationError: If any ticker is invalid

    Validation Rules:
        - Must not be empty
        - Max 1000 tickers
        - KR: 6-digit numeric (e.g., "005930")
        - US: 1-5 uppercase letters (e.g., "AAPL")

    Examples:
        >>> validate_tickers(["005930"], "KR")  # OK
        >>> validate_tickers(["AAPL"], "US")  # OK
        >>> validate_tickers(["INVALID"], "KR")  # Raises ValidationError
    """
    # Check if empty
    if not tickers:
        raise ValidationError(
            "Ticker list cannot be empty",
            {"provided_count": 0}
        )

    # Check max limit
    if len(tickers) > 1000:
        raise ValidationError(
            "Too many tickers",
            {"provided_count": len(tickers), "max_allowed": 1000}
        )

    # Validate format based on region
    if region == "KR":
        pattern = r'^\d{6}$'
        format_desc = "6-digit numeric"
    elif region == "US":
        pattern = r'^[A-Z]{1,5}$'
        format_desc = "1-5 uppercase letters"
    else:
        raise ValidationError(
            f"Invalid region: {region}",
            {"provided_region": region, "allowed_regions": ["KR", "US"]}
        )

    # Check each ticker
    invalid_tickers = []
    for ticker in tickers:
        if not re.match(pattern, ticker):
            invalid_tickers.append(ticker)

    if invalid_tickers:
        raise ValidationError(
            f"Invalid ticker format for region {region}",
            {
                "invalid_tickers": invalid_tickers[:10],  # Show first 10
                "expected_format": format_desc,
                "region": region,
                "total_invalid": len(invalid_tickers)
            }
        )


def validate_date_range(start_date: str, end_date: str) -> None:
    """
    Validate date range.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Raises:
        ValidationError: If date range is invalid

    Validation Rules:
        - Format must be YYYY-MM-DD
        - start_date must be before end_date
        - Range cannot exceed 10 years (3650 days)

    Examples:
        >>> validate_date_range("2024-01-01", "2024-12-31")  # OK
        >>> validate_date_range("2024-12-31", "2024-01-01")  # Raises ValidationError
        >>> validate_date_range("2020-01-01", "2035-01-01")  # Raises ValidationError (> 10 years)
    """
    # Parse dates
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    except ValueError as e:
        raise ValidationError(
            f"Invalid start_date format: {start_date}",
            {"expected_format": "YYYY-MM-DD", "error": str(e)}
        )

    try:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        raise ValidationError(
            f"Invalid end_date format: {end_date}",
            {"expected_format": "YYYY-MM-DD", "error": str(e)}
        )

    # Check start < end
    if start_dt >= end_dt:
        raise ValidationError(
            "start_date must be before end_date",
            {
                "start_date": start_date,
                "end_date": end_date,
                "days_diff": (end_dt - start_dt).days
            }
        )

    # Check max range (10 years = 3650 days)
    days_diff = (end_dt - start_dt).days
    if days_diff > 3650:
        raise ValidationError(
            "Date range cannot exceed 10 years",
            {
                "start_date": start_date,
                "end_date": end_date,
                "days_requested": days_diff,
                "max_days_allowed": 3650
            }
        )


def validate_strategy_config(config: Dict) -> None:
    """
    Validate strategy configuration.

    Args:
        config: Strategy configuration dictionary

    Raises:
        ValidationError: If configuration is invalid

    Required Fields:
        - type: Strategy type (must be in allowed list)
        - universe: Investment universe (non-empty list)

    Allowed Strategy Types:
        - "momentum"
        - "value"
        - "multi_factor"
        - "custom"

    Examples:
        >>> validate_strategy_config({"type": "momentum", "universe": ["005930"]})  # OK
        >>> validate_strategy_config({"type": "invalid"})  # Raises ValidationError
        >>> validate_strategy_config({"type": "momentum", "universe": []})  # Raises ValidationError
    """
    # Check required fields
    if "type" not in config:
        raise ValidationError(
            "Missing required field: type",
            {"provided_fields": list(config.keys())}
        )

    if "universe" not in config:
        raise ValidationError(
            "Missing required field: universe",
            {"provided_fields": list(config.keys())}
        )

    # Validate strategy type
    allowed_types = ["momentum", "value", "multi_factor", "custom"]
    strategy_type = config["type"]
    if strategy_type not in allowed_types:
        raise ValidationError(
            f"Invalid strategy type: {strategy_type}",
            {
                "provided_type": strategy_type,
                "allowed_types": allowed_types
            }
        )

    # Validate universe
    universe = config["universe"]
    if not isinstance(universe, list):
        raise ValidationError(
            "Universe must be a list",
            {"provided_type": type(universe).__name__}
        )

    if len(universe) == 0:
        raise ValidationError(
            "Universe cannot be empty",
            {"provided_count": 0}
        )


def validate_project_context(allowed_path: str) -> None:
    """
    Validate current working directory is within allowed project path.

    This validation ensures the MCP server only operates within the
    designated project directory, preventing unauthorized access from
    other projects or directories.

    Args:
        allowed_path: Absolute path to allowed project directory

    Raises:
        PathValidationError: If current directory is outside allowed path

    Security Features:
        - Resolves symlinks to prevent symlink attacks
        - Validates canonical paths to prevent path traversal
        - Fail-fast on validation failure (server won't start)

    Examples:
        >>> # Valid case (within project)
        >>> os.chdir("/Users/13ruce/spock")
        >>> validate_project_context("/Users/13ruce/spock")  # OK

        >>> # Invalid case (outside project)
        >>> os.chdir("/tmp")
        >>> validate_project_context("/Users/13ruce/spock")  # Raises PathValidationError
    """
    # Get current working directory and resolve symlinks
    current_path = os.path.realpath(os.getcwd())
    resolved_allowed_path = os.path.realpath(allowed_path)

    # Check if current path is within allowed path
    if not current_path.startswith(resolved_allowed_path):
        raise PathValidationError(
            "MCP server must operate within allowed project path",
            {
                "current_path": current_path,
                "allowed_path": resolved_allowed_path,
                "reason": "Current working directory is outside allowed project"
            }
        )


def validate_file_path(path: str, allowed_path: str) -> None:
    """
    Validate file path is within allowed project directory.

    This validation prevents path traversal attacks and ensures all
    file operations stay within the project boundary.

    Args:
        path: File path to validate (can be relative or absolute)
        allowed_path: Absolute path to allowed project directory

    Raises:
        PathValidationError: If resolved path is outside allowed directory

    Security Features:
        - Prevents path traversal with ../ patterns
        - Resolves symlinks to prevent symlink attacks
        - Validates against canonical paths
        - Blocks absolute paths outside project

    Examples:
        >>> # Valid relative path
        >>> validate_file_path("data/stocks.csv", "/Users/13ruce/spock")  # OK

        >>> # Invalid path traversal
        >>> validate_file_path("../../etc/passwd", "/Users/13ruce/spock")  # Raises

        >>> # Invalid absolute path
        >>> validate_file_path("/tmp/evil.py", "/Users/13ruce/spock")  # Raises
    """
    # Resolve allowed path
    resolved_allowed_path = os.path.realpath(allowed_path)

    # If path is relative, join with current directory
    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)

    # Resolve symlinks and normalize path
    resolved_path = os.path.realpath(path)

    # Check if resolved path is within allowed path
    if not resolved_path.startswith(resolved_allowed_path):
        raise PathValidationError(
            "File path is outside allowed project directory",
            {
                "provided_path": path,
                "resolved_path": resolved_path,
                "allowed_path": resolved_allowed_path,
                "reason": "Path traversal attempt or absolute path outside project"
            }
        )
