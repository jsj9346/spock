#!/usr/bin/env python3
"""
Size Factors - Market Cap and Liquidity Analysis (Phase 2 Final)

Categories:
- Market Cap: Company size (small-cap premium)
- Liquidity: Trading volume and ease of execution
- Float: Free float percentage (institutional accessibility)

Author: Spock Quant Platform - Phase 2 Complete
Updated: PostgreSQL Migration
"""

import logging
import os
import math
import psycopg2
import pandas as pd
from typing import Optional, List
from .factor_base import FactorBase, FactorResult, FactorCategory

# Import PostgreSQL database manager
try:
    from modules.db_manager_postgres import PostgresDatabaseManager
    DB_MANAGER_AVAILABLE = True
except ImportError:
    DB_MANAGER_AVAILABLE = False

logger = logging.getLogger(__name__)


class MarketCapFactor(FactorBase):
    """Market Capitalization - 시가총액

    Formula: Market Cap = Close Price × Shares Outstanding

    Ranking: Negated for small-cap tilt (lower cap = higher score)
    """

    def __init__(self):
        super().__init__(
            name="Market_Cap",
            category=FactorCategory.SIZE,
            lookback_days=1,
            min_required_days=1
        )

    def calculate(self, data, ticker: str, region: str = 'KR') -> Optional[FactorResult]:
        """
        Calculate market capitalization

        Negative factor value for small-cap tilt:
        - Lower market cap → Higher factor score (small-cap premium)

        Args:
            data: Unused (kept for interface compatibility)
            ticker: Stock ticker symbol
            region: Market region (KR, US, etc.)

        Returns:
            FactorResult with market cap score
        """
        query = """
            SELECT market_cap, shares_outstanding, close_price, fiscal_year
            FROM ticker_fundamentals
            WHERE ticker = %s
              AND region = %s
              AND market_cap IS NOT NULL
              AND market_cap > 0
            ORDER BY fiscal_year DESC
            LIMIT 1
        """

        try:
            # Use PostgresDatabaseManager if available
            if DB_MANAGER_AVAILABLE:
                db = PostgresDatabaseManager()
                results = db.execute_query(query, (ticker, region))
                result = results[0] if results else None
            else:
                # Fallback to raw psycopg2
                conn = psycopg2.connect(
                    host='localhost',
                    port=5432,
                    database='quant_platform',
                    user=os.getenv('USER')
                )
                cursor = conn.cursor()
                cursor.execute(query, (ticker, region))
                result = cursor.fetchone()
                conn.close()

            if not result:
                logger.debug(f"{ticker} ({region}) - {self.name}: No market cap data available")
                return None

            market_cap, shares_out, close_price, fiscal_year = result

            # Negative for small-cap tilt: lower market cap = higher score
            # Use log scale to compress range
            factor_value = -math.log10(market_cap / 1e12)  # Normalize to trillions of KRW

            # Market cap categories
            if market_cap > 10e12:  # >10 trillion KRW
                category = "Large Cap"
            elif market_cap > 1e12:  # 1-10 trillion
                category = "Mid Cap"
            else:  # <1 trillion
                category = "Small Cap"

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=float(factor_value),
                z_score=0.0,
                percentile=50.0,
                confidence=0.95,
                metadata={
                    'market_cap': int(market_cap),
                    'market_cap_trillion': round(market_cap / 1e12, 2),
                    'category': category,
                    'fiscal_year': int(fiscal_year)
                }
            )

        except (psycopg2.Error, Exception) as e:
            logger.error(f"{ticker} ({region}) - {self.name}: {e}")
            return None

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (unused - DB query)"""
        return []


class LiquidityFactor(FactorBase):
    """Liquidity - 유동성 (Average Daily Trading Volume)

    Formula: Liquidity = Average Daily Volume × Close Price (30-day average)

    Ranking: Positive (higher liquidity = higher score)
    """

    def __init__(self):
        super().__init__(
            name="Liquidity",
            category=FactorCategory.SIZE,
            lookback_days=30,
            min_required_days=20
        )

    def calculate(self, data: pd.DataFrame, ticker: str, region: str = 'KR') -> Optional[FactorResult]:
        """
        Calculate liquidity based on 30-day average trading volume

        Args:
            data: DataFrame with 'volume' and 'close' columns
            ticker: Stock ticker

        Returns:
            FactorResult with liquidity score (average daily value traded in KRW)
        """
        try:
            if data is None or len(data) < self.min_required_days:
                return None

            # Ensure required columns exist
            if 'volume' not in data.columns or 'close' not in data.columns:
                return None

            # Take last 30 days
            recent_data = data.tail(30)

            # Calculate daily trading value (volume × close price)
            daily_values = recent_data['volume'] * recent_data['close']

            # Average daily trading value (in KRW)
            avg_liquidity = daily_values.mean()

            if pd.isna(avg_liquidity) or avg_liquidity <= 0:
                return None

            # Liquidity categories
            if avg_liquidity > 100e8:  # >100억원/day
                category = "High Liquidity"
            elif avg_liquidity > 10e8:  # 10-100억원/day
                category = "Medium Liquidity"
            else:  # <10억원/day
                category = "Low Liquidity"

            # Use log scale for factor value (compress wide range)
            import math
            factor_value = math.log10(avg_liquidity / 1e8)  # Normalize to 억원 (100M KRW)

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=float(factor_value),
                z_score=0.0,
                percentile=50.0,
                confidence=0.85,
                metadata={
                    'avg_liquidity': int(avg_liquidity),
                    'avg_liquidity_billion': round(avg_liquidity / 1e8, 2),
                    'category': category,
                    'days_calculated': len(recent_data)
                }
            )

        except Exception as e:
            logger.error(f"{ticker} - {self.name}: {e}")
            return None

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns"""
        return ['volume', 'close']


class FloatFactor(FactorBase):
    """Free Float Percentage - 유통주식비율

    Formula: Float % = Free Float % from database

    Ranking: Positive (higher float = higher score, better for institutions)
    """

    def __init__(self):
        super().__init__(
            name="Free_Float",
            category=FactorCategory.SIZE,
            lookback_days=1,
            min_required_days=1
        )

    def calculate(self, data, ticker: str, region: str = 'KR') -> Optional[FactorResult]:
        """
        Calculate free float percentage

        Args:
            data: Unused (kept for interface compatibility)
            ticker: Stock ticker symbol
            region: Market region (KR, US, etc.)

        Returns:
            FactorResult with free float percentage
        """
        query = """
            SELECT free_float_percentage, shares_outstanding, fiscal_year
            FROM ticker_fundamentals
            WHERE ticker = %s
              AND region = %s
              AND free_float_percentage IS NOT NULL
              AND free_float_percentage > 0
            ORDER BY fiscal_year DESC
            LIMIT 1
        """

        try:
            # Use PostgresDatabaseManager if available
            if DB_MANAGER_AVAILABLE:
                db = PostgresDatabaseManager()
                results = db.execute_query(query, (ticker, region))
                result = results[0] if results else None
            else:
                # Fallback to raw psycopg2
                conn = psycopg2.connect(
                    host='localhost',
                    port=5432,
                    database='quant_platform',
                    user=os.getenv('USER')
                )
                cursor = conn.cursor()
                cursor.execute(query, (ticker, region))
                result = cursor.fetchone()
                conn.close()

            if not result:
                logger.debug(f"{ticker} ({region}) - {self.name}: No float data available")
                return None

            free_float_pct, shares_out, fiscal_year = result

            # Float categories (Korean market context)
            if free_float_pct > 50:  # >50%
                category = "High Float"
            elif free_float_pct > 30:  # 30-50%
                category = "Medium Float"
            else:  # <30%
                category = "Low Float"

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=float(free_float_pct),
                z_score=0.0,
                percentile=50.0,
                confidence=0.80,
                metadata={
                    'free_float_pct': round(free_float_pct, 2),
                    'category': category,
                    'fiscal_year': int(fiscal_year)
                }
            )

        except (psycopg2.Error, Exception) as e:
            logger.error(f"{ticker} ({region}) - {self.name}: {e}")
            return None

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (unused - DB query)"""
        return []
