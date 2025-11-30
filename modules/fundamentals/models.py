"""
Fundamentals Data Models

This module defines data models for fundamental financial data including annual
fundamentals, year-over-year comparisons, CAGR calculations, and comparison results.

All models use dataclasses for clean, type-safe data structures.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import date
from decimal import Decimal


@dataclass
class AnnualFundamentals:
    """
    Annual financial statement data for a single fiscal year.

    Attributes:
        ticker: Stock ticker symbol
        region: Market region (KR, US, JP, HK, CN)
        fiscal_year: Fiscal year (YYYY)
        period_end: End date of the fiscal period

        # Income Statement
        revenue: Total revenue/sales
        operating_profit: Operating profit (EBIT)
        net_income: Net income after tax
        ebitda: Earnings before interest, taxes, depreciation, and amortization

        # Balance Sheet
        total_assets: Total assets
        total_equity: Total shareholders' equity
        total_liabilities: Total liabilities

        # Derived Ratios (calculated)
        roe: Return on Equity (net_income / total_equity)
        roa: Return on Assets (net_income / total_assets)
        operating_margin: Operating margin (operating_profit / revenue)
        net_margin: Net margin (net_income / revenue)
        debt_ratio: Debt ratio (total_liabilities / total_assets)
    """
    ticker: str
    region: str
    fiscal_year: int
    period_end: date

    # Income Statement
    revenue: Optional[Decimal] = None
    operating_profit: Optional[Decimal] = None
    net_income: Optional[Decimal] = None
    ebitda: Optional[Decimal] = None

    # Balance Sheet
    total_assets: Optional[Decimal] = None
    total_equity: Optional[Decimal] = None
    total_liabilities: Optional[Decimal] = None

    # Derived Ratios (calculated)
    roe: Optional[float] = None
    roa: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    debt_ratio: Optional[float] = None


@dataclass
class YoYComparison:
    """
    Year-over-year comparison result for a specific metric.

    Attributes:
        ticker: Stock ticker symbol
        region: Market region (KR, US, JP, HK, CN)
        metric: Name of the metric being compared
        current_year: Current fiscal year
        previous_year: Previous fiscal year
        current_value: Value in current year
        previous_value: Value in previous year
        growth_rate: YoY growth rate ((current - previous) / previous)
        trend: Trend classification ('improving', 'stable', 'declining')
    """
    ticker: str
    region: str
    metric: str
    current_year: int
    previous_year: int
    current_value: Optional[Decimal]
    previous_value: Optional[Decimal]
    growth_rate: Optional[float]  # (current - previous) / previous
    trend: str  # 'improving', 'stable', 'declining'


@dataclass
class CAGRResult:
    """
    Compound Annual Growth Rate (CAGR) calculation result.

    CAGR = (end_value / start_value)^(1/years) - 1

    Attributes:
        ticker: Stock ticker symbol
        region: Market region (KR, US, JP, HK, CN)
        metric: Name of the metric
        start_year: Starting fiscal year
        end_year: Ending fiscal year
        start_value: Value at start year
        end_value: Value at end year
        cagr: Calculated CAGR as a decimal (e.g., 0.15 for 15%)
        years: Number of years in the period
    """
    ticker: str
    region: str
    metric: str
    start_year: int
    end_year: int
    start_value: Optional[Decimal]
    end_value: Optional[Decimal]
    cagr: Optional[float]
    years: int


@dataclass
class FundamentalsComparisonResult:
    """
    Comprehensive fundamentals comparison analysis result.

    This is the primary result object returned by the fundamentals comparison tool,
    containing all annual data, YoY comparisons, CAGR calculations, and trend summaries.

    Attributes:
        ticker: Stock ticker symbol
        region: Market region (KR, US, JP, HK, CN)
        currency: Currency code (KRW, USD, JPY, HKD, CNY)
        annual_data: List of annual fundamentals for each year
        yoy_comparisons: List of year-over-year comparisons for all metrics
        cagr_results: List of CAGR calculations for all metrics
        summary: Dictionary of trend summaries by metric
    """
    ticker: str
    region: str
    currency: str
    annual_data: List[AnnualFundamentals]
    yoy_comparisons: List[YoYComparison]
    cagr_results: List[CAGRResult]
    summary: Dict[str, str]  # metric -> trend summary
