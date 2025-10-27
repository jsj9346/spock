#!/usr/bin/env python3
"""
Efficiency Factors - Asset/Capital Utilization Analysis (Phase 2B - 2 Efficiency Factors)

Categories:
- Asset Efficiency (1): Total Asset Turnover
- Capital Efficiency (1): Equity Turnover

Measures how efficiently a company uses its assets and capital to generate revenue.

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


class AssetTurnoverFactor(FactorBase):
    """Total Asset Turnover - 총자산회전율"""

    def __init__(self):
        super().__init__(
            name="Asset_Turnover",
            category=FactorCategory.EFFICIENCY,
            lookback_days=730,  # 2 years for average calculation
            min_required_days=1
        )

    def calculate(self, data, ticker: str, region: str = 'US') -> Optional[FactorResult]:
        """
        Calculate total asset turnover ratio

        Formula: Revenue / Average Total Assets
        Average Total Assets = (Beginning Total Assets + Ending Total Assets) / 2

        Higher is better: Indicates efficient asset utilization

        Args:
            data: Unused (kept for interface compatibility)
            ticker: Stock ticker symbol
            region: Market region

        Returns:
            FactorResult with asset turnover ratio
        """
        try:
            conn = psycopg2.connect(
                host='localhost',
                port=5432,
                database='quant_platform',
                user=os.getenv('USER')
            )
            cursor = conn.cursor()

            # Get current revenue and average total assets
            cursor.execute("""
                SELECT
                    current.revenue,
                    current.total_assets AS current_assets,
                    current.fiscal_year,
                    previous.total_assets AS previous_assets
                FROM ticker_fundamentals current
                LEFT JOIN ticker_fundamentals previous
                    ON current.ticker = previous.ticker
                    AND current.region = previous.region
                    AND current.fiscal_year = previous.fiscal_year + 1
                WHERE current.ticker = %s
                  AND current.region = %s
                  AND current.revenue IS NOT NULL
                  AND current.total_assets IS NOT NULL
                  AND current.total_assets > 0
                  AND previous.total_assets IS NOT NULL
                  AND previous.total_assets > 0
                ORDER BY current.fiscal_year DESC
                LIMIT 1
            """, (ticker, region))

            result = cursor.fetchone()
            conn.close()

            if not result:
                logger.debug(f"{ticker} ({region}) - {self.name}: No data available")
                return None

            revenue, current_assets, fiscal_year, previous_assets = result

            # Calculate average total assets
            avg_total_assets = (current_assets + previous_assets) / 2

            # Calculate asset turnover ratio
            asset_turnover = float(revenue / avg_total_assets)

            # Higher is better: multiply by 100 for percentile ranking
            raw_value = asset_turnover * 100

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=raw_value,
                z_score=0.0,
                percentile=50.0,
                confidence=0.9,
                metadata={
                    'asset_turnover': round(asset_turnover, 2),
                    'revenue': float(revenue),
                    'avg_total_assets': float(avg_total_assets),
                    'fiscal_year': int(fiscal_year)
                }
            )

        except Exception as e:
            logger.error(f"{ticker} ({region}) - {self.name}: {e}")
            return None

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (unused - DB query)"""
        return []


class EquityTurnoverFactor(FactorBase):
    """Equity Turnover - 자기자본회전율"""

    def __init__(self):
        super().__init__(
            name="Equity_Turnover",
            category=FactorCategory.EFFICIENCY,
            lookback_days=730,
            min_required_days=1
        )

    def calculate(self, data, ticker: str, region: str = 'US') -> Optional[FactorResult]:
        """
        Calculate equity turnover ratio

        Formula: Revenue / Average Total Equity
        Average Total Equity = (Beginning Equity + Ending Equity) / 2

        Higher is better: Indicates efficient capital utilization

        Note: Very high equity turnover may indicate excessive leverage

        Args:
            data: Unused
            ticker: Stock ticker symbol
            region: Market region

        Returns:
            FactorResult with equity turnover ratio
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
                    current.revenue,
                    current.total_equity AS current_equity,
                    current.fiscal_year,
                    previous.total_equity AS previous_equity
                FROM ticker_fundamentals current
                LEFT JOIN ticker_fundamentals previous
                    ON current.ticker = previous.ticker
                    AND current.region = previous.region
                    AND current.fiscal_year = previous.fiscal_year + 1
                WHERE current.ticker = %s
                  AND current.region = %s
                  AND current.revenue IS NOT NULL
                  AND current.total_equity IS NOT NULL
                  AND current.total_equity > 0
                  AND previous.total_equity IS NOT NULL
                  AND previous.total_equity > 0
                ORDER BY current.fiscal_year DESC
                LIMIT 1
            """, (ticker, region))

            result = cursor.fetchone()
            conn.close()

            if not result:
                logger.debug(f"{ticker} ({region}) - {self.name}: No data available")
                return None

            revenue, current_equity, fiscal_year, previous_equity = result

            # Calculate average total equity
            avg_total_equity = (current_equity + previous_equity) / 2

            # Calculate equity turnover ratio
            equity_turnover = float(revenue / avg_total_equity)

            # Higher is better: multiply by 100 for percentile ranking
            raw_value = equity_turnover * 100

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=raw_value,
                z_score=0.0,
                percentile=50.0,
                confidence=0.85,  # Slightly lower confidence due to leverage sensitivity
                metadata={
                    'equity_turnover': round(equity_turnover, 2),
                    'revenue': float(revenue),
                    'avg_total_equity': float(avg_total_equity),
                    'fiscal_year': int(fiscal_year)
                }
            )

        except Exception as e:
            logger.error(f"{ticker} ({region}) - {self.name}: {e}")
            return None

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (unused - DB query)"""
        return []


# Export all efficiency factors
__all__ = [
    'AssetTurnoverFactor',
    'EquityTurnoverFactor'
]
