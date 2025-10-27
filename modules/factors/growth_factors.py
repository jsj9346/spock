#!/usr/bin/env python3
"""
Growth Factors - Revenue/Profit Growth Analysis (Phase 2B - 3 Growth Factors)

Categories:
- Revenue Growth (1): YOY Revenue Growth Rate
- Profitability Growth (2): Operating Profit Growth, Net Income Growth

Calculates year-over-year growth rates using ticker_fundamentals data.

Author: Spock Quant Platform - Phase 2B Multi-Factor Expansion
Date: 2025-10-24
"""

import os
import logging
from typing import Optional, List
from datetime import date
import psycopg2
from .factor_base import FactorBase, FactorResult, FactorCategory

logger = logging.getLogger(__name__)


class RevenueGrowthFactor(FactorBase):
    """Revenue Growth (YOY) - 매출 증가율"""

    def __init__(self):
        super().__init__(
            name="Revenue_Growth_YOY",
            category=FactorCategory.GROWTH,
            lookback_days=730,  # 2 years for YOY comparison
            min_required_days=1
        )

    def calculate(self, data, ticker: str, region: str = 'US') -> Optional[FactorResult]:
        """
        Calculate YOY revenue growth rate

        Formula: ((Current Year Revenue - Previous Year Revenue) / Previous Year Revenue) * 100

        Args:
            data: Unused (kept for interface compatibility)
            ticker: Stock ticker symbol
            region: Market region (US, KR, etc.)

        Returns:
            FactorResult with revenue growth rate (%)
        """
        try:
            conn = psycopg2.connect(
                host='localhost',
                port=5432,
                database='quant_platform',
                user=os.getenv('USER')
            )
            cursor = conn.cursor()

            # Get current and previous year revenue
            cursor.execute("""
                SELECT
                    current.revenue AS current_revenue,
                    current.fiscal_year AS current_year,
                    previous.revenue AS previous_revenue,
                    previous.fiscal_year AS previous_year
                FROM ticker_fundamentals current
                LEFT JOIN ticker_fundamentals previous
                    ON current.ticker = previous.ticker
                    AND current.region = previous.region
                    AND current.fiscal_year = previous.fiscal_year + 1
                WHERE current.ticker = %s
                  AND current.region = %s
                  AND current.revenue IS NOT NULL
                  AND previous.revenue IS NOT NULL
                  AND previous.revenue > 0
                ORDER BY current.fiscal_year DESC
                LIMIT 1
            """, (ticker, region))

            result = cursor.fetchone()
            conn.close()

            if not result:
                logger.debug(f"{ticker} ({region}) - {self.name}: No YOY data available")
                return None

            current_revenue, current_year, previous_revenue, previous_year = result

            # Calculate YOY growth rate
            growth_rate = float(((current_revenue - previous_revenue) / previous_revenue) * 100)

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=growth_rate,
                z_score=0.0,  # Will be calculated in batch processing
                percentile=50.0,
                confidence=0.9,
                metadata={
                    'revenue_growth_yoy': round(growth_rate, 2),
                    'current_year': int(current_year),
                    'previous_year': int(previous_year),
                    'current_revenue': float(current_revenue),
                    'previous_revenue': float(previous_revenue)
                }
            )

        except Exception as e:
            logger.error(f"{ticker} ({region}) - {self.name}: {e}")
            return None

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (unused - DB query)"""
        return []


class OperatingProfitGrowthFactor(FactorBase):
    """Operating Profit Growth (YOY) - 영업이익 증가율"""

    def __init__(self):
        super().__init__(
            name="Operating_Profit_Growth_YOY",
            category=FactorCategory.GROWTH,
            lookback_days=730,
            min_required_days=1
        )

    def calculate(self, data, ticker: str, region: str = 'US') -> Optional[FactorResult]:
        """
        Calculate YOY operating profit growth rate

        Formula: ((Current OP - Previous OP) / Previous OP) * 100

        Args:
            data: Unused
            ticker: Stock ticker symbol
            region: Market region

        Returns:
            FactorResult with operating profit growth rate (%)
        """
        try:
            conn = psycopg2.connect(
                host='localhost',
                port=5432,
                database='quant_platform',
                user=os.getenv('USER')
            )
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    current.operating_profit AS current_op,
                    current.fiscal_year AS current_year,
                    previous.operating_profit AS previous_op,
                    previous.fiscal_year AS previous_year
                FROM ticker_fundamentals current
                LEFT JOIN ticker_fundamentals previous
                    ON current.ticker = previous.ticker
                    AND current.region = previous.region
                    AND current.fiscal_year = previous.fiscal_year + 1
                WHERE current.ticker = %s
                  AND current.region = %s
                  AND current.operating_profit IS NOT NULL
                  AND previous.operating_profit IS NOT NULL
                  AND previous.operating_profit != 0
                ORDER BY current.fiscal_year DESC
                LIMIT 1
            """, (ticker, region))

            result = cursor.fetchone()
            conn.close()

            if not result:
                logger.debug(f"{ticker} ({region}) - {self.name}: No YOY data available")
                return None

            current_op, current_year, previous_op, previous_year = result

            # Handle negative previous operating profit (growth rate may be misleading)
            if previous_op < 0:
                # If turning profitable, assign high positive growth (capped at 200%)
                if current_op > 0:
                    growth_rate = 200.0
                else:
                    # Both negative - calculate absolute change
                    growth_rate = float(((current_op - previous_op) / abs(previous_op)) * 100)
            else:
                # Normal case: previous OP is positive
                growth_rate = float(((current_op - previous_op) / previous_op) * 100)

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=growth_rate,
                z_score=0.0,
                percentile=50.0,
                confidence=0.85,  # Slightly lower confidence for profit volatility
                metadata={
                    'op_growth_yoy': round(growth_rate, 2),
                    'current_year': int(current_year),
                    'previous_year': int(previous_year),
                    'current_op': float(current_op),
                    'previous_op': float(previous_op)
                }
            )

        except Exception as e:
            logger.error(f"{ticker} ({region}) - {self.name}: {e}")
            return None

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (unused - DB query)"""
        return []


class NetIncomeGrowthFactor(FactorBase):
    """Net Income Growth (YOY) - 순이익 증가율"""

    def __init__(self):
        super().__init__(
            name="Net_Income_Growth_YOY",
            category=FactorCategory.GROWTH,
            lookback_days=730,
            min_required_days=1
        )

    def calculate(self, data, ticker: str, region: str = 'US') -> Optional[FactorResult]:
        """
        Calculate YOY net income growth rate

        Formula: ((Current NI - Previous NI) / Previous NI) * 100

        Args:
            data: Unused
            ticker: Stock ticker symbol
            region: Market region

        Returns:
            FactorResult with net income growth rate (%)
        """
        try:
            conn = psycopg2.connect(
                host='localhost',
                port=5432,
                database='quant_platform',
                user=os.getenv('USER')
            )
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    current.net_income AS current_ni,
                    current.fiscal_year AS current_year,
                    previous.net_income AS previous_ni,
                    previous.fiscal_year AS previous_year
                FROM ticker_fundamentals current
                LEFT JOIN ticker_fundamentals previous
                    ON current.ticker = previous.ticker
                    AND current.region = previous.region
                    AND current.fiscal_year = previous.fiscal_year + 1
                WHERE current.ticker = %s
                  AND current.region = %s
                  AND current.net_income IS NOT NULL
                  AND previous.net_income IS NOT NULL
                  AND previous.net_income != 0
                ORDER BY current.fiscal_year DESC
                LIMIT 1
            """, (ticker, region))

            result = cursor.fetchone()
            conn.close()

            if not result:
                logger.debug(f"{ticker} ({region}) - {self.name}: No YOY data available")
                return None

            current_ni, current_year, previous_ni, previous_year = result

            # Handle negative previous net income (loss to profit scenario)
            if previous_ni < 0:
                if current_ni > 0:
                    growth_rate = 200.0  # Capped at 200% for loss-to-profit turnaround
                else:
                    growth_rate = float(((current_ni - previous_ni) / abs(previous_ni)) * 100)
            else:
                growth_rate = float(((current_ni - previous_ni) / previous_ni) * 100)

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=growth_rate,
                z_score=0.0,
                percentile=50.0,
                confidence=0.85,
                metadata={
                    'ni_growth_yoy': round(growth_rate, 2),
                    'current_year': int(current_year),
                    'previous_year': int(previous_year),
                    'current_ni': float(current_ni),
                    'previous_ni': float(previous_ni)
                }
            )

        except Exception as e:
            logger.error(f"{ticker} ({region}) - {self.name}: {e}")
            return None

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (unused - DB query)"""
        return []


# Export all growth factors
__all__ = [
    'RevenueGrowthFactor',
    'OperatingProfitGrowthFactor',
    'NetIncomeGrowthFactor'
]
