"""
Fundamentals Constants and Configuration

This module contains constants, configuration values, and mappings used throughout
the fundamentals module for data processing, analysis, and database operations.
"""

from typing import List, Dict, Tuple


# =============================================================================
# Metric Categories
# =============================================================================

INCOME_STATEMENT_METRICS: List[str] = [
    'revenue',
    'operating_profit',
    'net_income',
    'ebitda',
    'gross_profit',
    'interest_expense',
    'interest_income'
]

BALANCE_SHEET_METRICS: List[str] = [
    'total_assets',
    'total_equity',
    'total_liabilities',
    'current_assets',
    'current_liabilities',
    'total_debt'
]

RATIO_METRICS: List[str] = [
    'roe',
    'roa',
    'operating_margin',
    'net_margin',
    'debt_ratio'
]

# All metrics combined
ALL_METRICS: List[str] = (
    INCOME_STATEMENT_METRICS +
    BALANCE_SHEET_METRICS +
    RATIO_METRICS
)


# =============================================================================
# Trend Classification Thresholds
# =============================================================================

TREND_THRESHOLDS: Dict[str, float | Tuple[float, float]] = {
    'improving': 0.05,          # >5% growth = improving
    'declining': -0.05,         # <-5% growth = declining
    'stable': (-0.05, 0.05)     # between -5% and 5% = stable
}


# =============================================================================
# Currency Mapping by Region
# =============================================================================

CURRENCY_MAP: Dict[str, str] = {
    'KR': 'KRW',    # South Korea - Won
    'US': 'USD',    # United States - Dollar
    'JP': 'JPY',    # Japan - Yen
    'HK': 'HKD',    # Hong Kong - Dollar
    'CN': 'CNY'     # China - Yuan
}


# =============================================================================
# Database Column Mappings
# =============================================================================

# Maps logical field names to actual database column names
# Use this when the database schema uses different naming conventions
DB_COLUMN_MAP: Dict[str, str] = {
    'operating_income': 'operating_profit',  # DB uses operating_profit
}

# Reverse mapping for DB -> Model conversion
DB_TO_MODEL_MAP: Dict[str, str] = {
    v: k for k, v in DB_COLUMN_MAP.items()
}


# =============================================================================
# Default Values and Limits
# =============================================================================

# Minimum number of years required for CAGR calculation
MIN_CAGR_YEARS: int = 2

# Maximum number of years to look back for historical data
MAX_LOOKBACK_YEARS: int = 10

# Minimum number of data points required for trend analysis
MIN_DATA_POINTS: int = 2


# =============================================================================
# Data Quality Thresholds
# =============================================================================

# Maximum acceptable absolute value for ratios (for outlier detection)
MAX_RATIO_VALUE: float = 10.0  # 1000%

# Minimum acceptable value for key metrics (for data quality checks)
MIN_VALID_VALUE: float = 0.0

# Maximum year-over-year growth rate considered valid (for outlier detection)
MAX_YOY_GROWTH: float = 5.0  # 500%


# =============================================================================
# Display Formatting
# =============================================================================

# Number of decimal places for different metric types
DECIMAL_PLACES: Dict[str, int] = {
    'currency': 0,      # No decimals for currency values
    'ratio': 4,         # 4 decimals for ratios (e.g., 0.1234)
    'percentage': 2,    # 2 decimals for percentages (e.g., 12.34%)
    'growth_rate': 2    # 2 decimals for growth rates (e.g., 15.50%)
}

# Metric display names (for user-facing output)
METRIC_DISPLAY_NAMES: Dict[str, str] = {
    'revenue': 'Revenue',
    'operating_profit': 'Operating Profit',
    'net_income': 'Net Income',
    'ebitda': 'EBITDA',
    'total_assets': 'Total Assets',
    'total_equity': 'Total Equity',
    'total_liabilities': 'Total Liabilities',
    'roe': 'Return on Equity (ROE)',
    'roa': 'Return on Assets (ROA)',
    'operating_margin': 'Operating Margin',
    'net_margin': 'Net Margin',
    'debt_ratio': 'Debt Ratio'
}
