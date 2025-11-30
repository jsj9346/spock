"""
Fundamentals Module

This module provides data models, constants, and utilities for fundamental
financial analysis including annual fundamentals, year-over-year comparisons,
CAGR calculations, and comprehensive comparison analysis.

Key Components:
    - models: Data classes for fundamentals data structures
    - constants: Configuration values and metric definitions

Example Usage:
    from modules.fundamentals import (
        AnnualFundamentals,
        YoYComparison,
        CAGRResult,
        FundamentalsComparisonResult,
        INCOME_STATEMENT_METRICS,
        BALANCE_SHEET_METRICS,
        CURRENCY_MAP
    )

    # Create annual fundamentals instance
    annual = AnnualFundamentals(
        ticker='005930',
        region='KR',
        fiscal_year=2024,
        period_end=date(2024, 12, 31),
        revenue=Decimal('300000000000000'),
        net_income=Decimal('25000000000000')
    )

    # Access metric categories
    for metric in INCOME_STATEMENT_METRICS:
        print(f"Analyzing {metric}")
"""

# Import all models
from modules.fundamentals.models import (
    AnnualFundamentals,
    YoYComparison,
    CAGRResult,
    FundamentalsComparisonResult,
)

# Import TTM Calculator
from modules.fundamentals.ttm_calculator import (
    TTMCalculator,
    TTMResult,
)

# Import TTM Service
from modules.fundamentals.ttm_service import (
    TTMService,
)

# Import Comparison Analyzer
from modules.fundamentals.comparison_analyzer import (
    ComparisonAnalyzer,
)

# Import all constants
from modules.fundamentals.constants import (
    # Metric categories
    INCOME_STATEMENT_METRICS,
    BALANCE_SHEET_METRICS,
    RATIO_METRICS,
    ALL_METRICS,

    # Thresholds and mappings
    TREND_THRESHOLDS,
    CURRENCY_MAP,
    DB_COLUMN_MAP,
    DB_TO_MODEL_MAP,

    # Default values
    MIN_CAGR_YEARS,
    MAX_LOOKBACK_YEARS,
    MIN_DATA_POINTS,

    # Data quality
    MAX_RATIO_VALUE,
    MIN_VALID_VALUE,
    MAX_YOY_GROWTH,

    # Display formatting
    DECIMAL_PLACES,
    METRIC_DISPLAY_NAMES,
)

# Define public API
__all__ = [
    # Models
    'AnnualFundamentals',
    'YoYComparison',
    'CAGRResult',
    'FundamentalsComparisonResult',

    # TTM
    'TTMCalculator',
    'TTMResult',
    'TTMService',

    # Comparison
    'ComparisonAnalyzer',

    # Metric categories
    'INCOME_STATEMENT_METRICS',
    'BALANCE_SHEET_METRICS',
    'RATIO_METRICS',
    'ALL_METRICS',

    # Thresholds and mappings
    'TREND_THRESHOLDS',
    'CURRENCY_MAP',
    'DB_COLUMN_MAP',
    'DB_TO_MODEL_MAP',

    # Default values
    'MIN_CAGR_YEARS',
    'MAX_LOOKBACK_YEARS',
    'MIN_DATA_POINTS',

    # Data quality
    'MAX_RATIO_VALUE',
    'MIN_VALID_VALUE',
    'MAX_YOY_GROWTH',

    # Display formatting
    'DECIMAL_PLACES',
    'METRIC_DISPLAY_NAMES',
]

# Module metadata
__version__ = '1.0.0'
__author__ = 'Quant Investment Platform'
__description__ = 'Fundamental financial data models and analysis tools'
