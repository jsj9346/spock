#!/usr/bin/env python3
"""
Quality Factors - Business Quality Analysis (Phase 2A - 9 Core Factors)

Categories:
- Profitability (4): ROE, ROA, Operating Margin, Net Profit Margin
- Liquidity (2): Current Ratio, Quick Ratio
- Leverage (1): Debt-to-Equity
- Earnings Quality (2): Accruals Ratio, CF-to-NI Ratio

Migrated to PostgreSQL + TimescaleDB architecture.

Author: Spock Quant Platform
Date: 2025-10-23
"""

import os
import logging
from typing import Optional, List
from datetime import date
import psycopg2
from .factor_base import FactorBase, FactorResult, FactorCategory

logger = logging.getLogger(__name__)

class ROEFactor(FactorBase):
    """ROE (Return on Equity) - 자기자본이익률"""

    def __init__(self):
        super().__init__(name="ROE", category=FactorCategory.QUALITY, lookback_days=365, min_required_days=1)

    def calculate(self, data, ticker: str, region: str = 'US') -> Optional[FactorResult]:
        try:
            conn = psycopg2.connect(
                host='localhost',
                port=5432,
                database='quant_platform',
                user=os.getenv('USER')
            )
            cursor = conn.cursor()
            cursor.execute("""
                SELECT net_income, total_equity, fiscal_year
                FROM ticker_fundamentals
                WHERE ticker = %s AND region = %s
                  AND net_income IS NOT NULL
                  AND total_equity IS NOT NULL
                  AND total_equity > 0
                ORDER BY fiscal_year DESC LIMIT 1
            """, (ticker, region))
            result = cursor.fetchone()
            conn.close()

            if not result:
                return None

            net_income, total_equity, fiscal_year = result
            roe = float((net_income / total_equity) * 100)

            return FactorResult(
                ticker=ticker, factor_name=self.name, raw_value=roe,
                z_score=0.0, percentile=50.0, confidence=0.9,
                metadata={'roe': round(roe, 2), 'fiscal_year': fiscal_year}
            )
        except Exception as e:
            logger.error(f"{ticker} - {self.name}: {e}")
            return None

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (unused - DB query)"""
        return []


class ROAFactor(FactorBase):
    """ROA (Return on Assets) - 총자산이익률"""

    def __init__(self):
        super().__init__(name="ROA", category=FactorCategory.QUALITY, lookback_days=365, min_required_days=1)

    def calculate(self, data, ticker: str, region: str = 'US') -> Optional[FactorResult]:
        try:
            conn = psycopg2.connect(
                host='localhost',
                port=5432,
                database='quant_platform',
                user=os.getenv('USER')
            )
            cursor = conn.cursor()
            cursor.execute("""
                SELECT net_income, total_assets, fiscal_year
                FROM ticker_fundamentals
                WHERE ticker = %s AND region = %s
                  AND net_income IS NOT NULL
                  AND total_assets IS NOT NULL
                  AND total_assets > 0
                ORDER BY fiscal_year DESC LIMIT 1
            """, (ticker, region))
            result = cursor.fetchone()
            conn.close()

            if not result:
                return None

            net_income, total_assets, fiscal_year = result
            roa = float((net_income / total_assets) * 100)

            return FactorResult(
                ticker=ticker, factor_name=self.name, raw_value=roa,
                z_score=0.0, percentile=50.0, confidence=0.9,
                metadata={'roa': round(roa, 2), 'fiscal_year': fiscal_year}
            )
        except Exception as e:
            logger.error(f"{ticker} - {self.name}: {e}")
            return None

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (unused - DB query)"""
        return []


class OperatingMarginFactor(FactorBase):
    """Operating Margin - 영업이익률"""

    def __init__(self):
        super().__init__(name="Operating_Margin", category=FactorCategory.QUALITY, lookback_days=365, min_required_days=1)

    def calculate(self, data, ticker: str, region: str = 'US') -> Optional[FactorResult]:
        try:
            conn = psycopg2.connect(
                host='localhost',
                port=5432,
                database='quant_platform',
                user=os.getenv('USER')
            )
            cursor = conn.cursor()
            cursor.execute("""
                SELECT operating_profit, revenue, fiscal_year
                FROM ticker_fundamentals
                WHERE ticker = %s AND region = %s
                  AND operating_profit IS NOT NULL
                  AND revenue IS NOT NULL
                  AND revenue > 0
                ORDER BY fiscal_year DESC LIMIT 1
            """, (ticker, region))
            result = cursor.fetchone()
            conn.close()

            if not result:
                return None

            operating_profit, revenue, fiscal_year = result
            margin = float((operating_profit / revenue) * 100)

            return FactorResult(
                ticker=ticker, factor_name=self.name, raw_value=margin,
                z_score=0.0, percentile=50.0, confidence=0.95,
                metadata={'operating_margin': round(margin, 2), 'fiscal_year': fiscal_year}
            )
        except Exception as e:
            logger.error(f"{ticker} - {self.name}: {e}")
            return None

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (unused - DB query)"""
        return []


class NetProfitMarginFactor(FactorBase):
    """Net Profit Margin - 순이익률"""

    def __init__(self):
        super().__init__(name="Net_Profit_Margin", category=FactorCategory.QUALITY, lookback_days=365, min_required_days=1)

    def calculate(self, data, ticker: str, region: str = 'US') -> Optional[FactorResult]:
        try:
            conn = psycopg2.connect(
                host='localhost',
                port=5432,
                database='quant_platform',
                user=os.getenv('USER')
            )
            cursor = conn.cursor()
            cursor.execute("""
                SELECT net_income, revenue, fiscal_year
                FROM ticker_fundamentals
                WHERE ticker = %s AND region = %s
                  AND net_income IS NOT NULL
                  AND revenue IS NOT NULL
                  AND revenue > 0
                ORDER BY fiscal_year DESC LIMIT 1
            """, (ticker, region))
            result = cursor.fetchone()
            conn.close()

            if not result:
                return None

            net_income, revenue, fiscal_year = result
            margin = float((net_income / revenue) * 100)

            return FactorResult(
                ticker=ticker, factor_name=self.name, raw_value=margin,
                z_score=0.0, percentile=50.0, confidence=0.9,
                metadata={'net_profit_margin': round(margin, 2), 'fiscal_year': fiscal_year}
            )
        except Exception as e:
            logger.error(f"{ticker} - {self.name}: {e}")
            return None

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (unused - DB query)"""
        return []


class CurrentRatioFactor(FactorBase):
    """Current Ratio - 유동비율"""

    def __init__(self):
        super().__init__(name="Current_Ratio", category=FactorCategory.QUALITY, lookback_days=365, min_required_days=1)

    def calculate(self, data, ticker: str, region: str = 'US') -> Optional[FactorResult]:
        try:
            conn = psycopg2.connect(
                host='localhost',
                port=5432,
                database='quant_platform',
                user=os.getenv('USER')
            )
            cursor = conn.cursor()
            cursor.execute("""
                SELECT current_assets, current_liabilities, fiscal_year
                FROM ticker_fundamentals
                WHERE ticker = %s AND region = %s
                  AND current_assets IS NOT NULL
                  AND current_liabilities IS NOT NULL
                  AND current_liabilities > 0
                ORDER BY fiscal_year DESC LIMIT 1
            """, (ticker, region))
            result = cursor.fetchone()
            conn.close()

            if not result:
                return None

            current_assets, current_liabilities, fiscal_year = result
            ratio = float((current_assets / current_liabilities) * 100)

            return FactorResult(
                ticker=ticker, factor_name=self.name, raw_value=ratio,
                z_score=0.0, percentile=50.0, confidence=0.95,
                metadata={'current_ratio': round(ratio, 2), 'fiscal_year': fiscal_year}
            )
        except Exception as e:
            logger.error(f"{ticker} - {self.name}: {e}")
            return None

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (unused - DB query)"""
        return []


class QuickRatioFactor(FactorBase):
    """Quick Ratio - 당좌비율"""

    def __init__(self):
        super().__init__(name="Quick_Ratio", category=FactorCategory.QUALITY, lookback_days=365, min_required_days=1)

    def calculate(self, data, ticker: str, region: str = 'US') -> Optional[FactorResult]:
        try:
            conn = psycopg2.connect(
                host='localhost',
                port=5432,
                database='quant_platform',
                user=os.getenv('USER')
            )
            cursor = conn.cursor()
            cursor.execute("""
                SELECT current_assets, inventory, current_liabilities, fiscal_year
                FROM ticker_fundamentals
                WHERE ticker = %s AND region = %s
                  AND current_assets IS NOT NULL
                  AND current_liabilities IS NOT NULL
                  AND current_liabilities > 0
                ORDER BY fiscal_year DESC LIMIT 1
            """, (ticker, region))
            result = cursor.fetchone()
            conn.close()

            if not result:
                return None

            current_assets, inventory, current_liabilities, fiscal_year = result
            inventory = inventory if inventory is not None else 0
            quick_assets = current_assets - inventory
            ratio = float((quick_assets / current_liabilities) * 100)

            return FactorResult(
                ticker=ticker, factor_name=self.name, raw_value=ratio,
                z_score=0.0, percentile=50.0, confidence=0.95,
                metadata={'quick_ratio': round(ratio, 2), 'fiscal_year': fiscal_year}
            )
        except Exception as e:
            logger.error(f"{ticker} - {self.name}: {e}")
            return None

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (unused - DB query)"""
        return []


class DebtToEquityFactor(FactorBase):
    """Debt-to-Equity Ratio - 부채비율"""

    def __init__(self):
        super().__init__(name="Debt_to_Equity", category=FactorCategory.QUALITY, lookback_days=365, min_required_days=1)

    def calculate(self, data, ticker: str, region: str = 'US') -> Optional[FactorResult]:
        try:
            conn = psycopg2.connect(
                host='localhost',
                port=5432,
                database='quant_platform',
                user=os.getenv('USER')
            )
            cursor = conn.cursor()
            cursor.execute("""
                SELECT total_liabilities, total_equity, fiscal_year
                FROM ticker_fundamentals
                WHERE ticker = %s AND region = %s
                  AND total_liabilities IS NOT NULL
                  AND total_equity IS NOT NULL
                  AND total_equity > 0
                ORDER BY fiscal_year DESC LIMIT 1
            """, (ticker, region))
            result = cursor.fetchone()
            conn.close()

            if not result:
                return None

            total_liabilities, total_equity, fiscal_year = result
            ratio = float((total_liabilities / total_equity) * 100)
            factor_value = -ratio  # Negate for ranking (lower debt = higher score)

            return FactorResult(
                ticker=ticker, factor_name=self.name, raw_value=float(factor_value),
                z_score=0.0, percentile=50.0, confidence=0.95,
                metadata={'debt_to_equity': round(ratio, 2), 'fiscal_year': fiscal_year}
            )
        except Exception as e:
            logger.error(f"{ticker} - {self.name}: {e}")
            return None

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (unused - DB query)"""
        return []


class AccrualsRatioFactor(FactorBase):
    """Accruals Ratio - 발생액비율 (Sloan 1996)"""

    def __init__(self):
        super().__init__(name="Accruals_Ratio", category=FactorCategory.QUALITY, lookback_days=365, min_required_days=1)

    def calculate(self, data, ticker: str, region: str = 'US') -> Optional[FactorResult]:
        try:
            conn = psycopg2.connect(
                host='localhost',
                port=5432,
                database='quant_platform',
                user=os.getenv('USER')
            )
            cursor = conn.cursor()
            cursor.execute("""
                SELECT net_income, operating_cash_flow, total_assets, fiscal_year
                FROM ticker_fundamentals
                WHERE ticker = %s AND region = %s
                  AND net_income IS NOT NULL
                  AND operating_cash_flow IS NOT NULL
                  AND total_assets IS NOT NULL
                  AND total_assets > 0
                ORDER BY fiscal_year DESC LIMIT 1
            """, (ticker, region))
            result = cursor.fetchone()
            conn.close()

            if not result:
                return None

            net_income, operating_cash_flow, total_assets, fiscal_year = result
            accruals = net_income - operating_cash_flow
            accruals_ratio = float(accruals / total_assets)
            factor_value = -accruals_ratio  # Negate for ranking (lower accruals = higher score)

            return FactorResult(
                ticker=ticker, factor_name=self.name, raw_value=float(factor_value),
                z_score=0.0, percentile=50.0, confidence=0.9,
                metadata={'accruals_ratio': round(accruals_ratio, 4), 'fiscal_year': fiscal_year}
            )
        except Exception as e:
            logger.error(f"{ticker} - {self.name}: {e}")
            return None

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (unused - DB query)"""
        return []


class CFToNIRatioFactor(FactorBase):
    """Cash Flow to Net Income Ratio - 현금흐름/순이익"""

    def __init__(self):
        super().__init__(name="CF_to_NI_Ratio", category=FactorCategory.QUALITY, lookback_days=365, min_required_days=1)

    def calculate(self, data, ticker: str, region: str = 'US') -> Optional[FactorResult]:
        try:
            conn = psycopg2.connect(
                host='localhost',
                port=5432,
                database='quant_platform',
                user=os.getenv('USER')
            )
            cursor = conn.cursor()
            cursor.execute("""
                SELECT operating_cash_flow, net_income, fiscal_year
                FROM ticker_fundamentals
                WHERE ticker = %s AND region = %s
                  AND operating_cash_flow IS NOT NULL
                  AND net_income IS NOT NULL
                  AND net_income != 0
                ORDER BY fiscal_year DESC LIMIT 1
            """, (ticker, region))
            result = cursor.fetchone()
            conn.close()

            if not result:
                return None

            operating_cash_flow, net_income, fiscal_year = result
            ratio = float(operating_cash_flow / net_income)

            return FactorResult(
                ticker=ticker, factor_name=self.name, raw_value=ratio,
                z_score=0.0, percentile=50.0, confidence=0.9,
                metadata={'cf_to_ni_ratio': round(ratio, 2), 'fiscal_year': fiscal_year}
            )
        except Exception as e:
            logger.error(f"{ticker} - {self.name}: {e}")
            return None

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (unused - DB query)"""
        return []
