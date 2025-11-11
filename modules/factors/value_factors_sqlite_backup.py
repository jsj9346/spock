#!/usr/bin/env python3
"""
value_factors.py - Value Factor Implementations (Phase 2)

Value Strategy:
- Fundamental valuation metrics
- Seeks undervalued stocks relative to intrinsic worth
- Classic value investing approach (Graham & Dodd)

Factors Implemented:
1. PERatioFactor - Price-to-Earnings ratio
2. PBRatioFactor - Price-to-Book ratio
3. EVToEBITDAFactor - Enterprise Value to EBITDA
4. DividendYieldFactor - Dividend yield

Academic Foundation:
- Fama & French (1992): "The Cross-Section of Expected Stock Returns"
- Value premium: Undervalued stocks outperform growth stocks

Data Source: ticker_fundamentals table (DART API / yfinance)
"""

from typing import Optional, List
import pandas as pd
import sqlite3
from .factor_base import FactorBase, FactorResult, FactorCategory
import logging

logger = logging.getLogger(__name__)


class PERatioFactor(FactorBase):
    """
    Price-to-Earnings (P/E) Ratio Factor

    Calculation:
    - P/E = Market Price / Earnings Per Share
    - Lower P/E = higher factor score (undervalued)
    - Factor value = -P/E (for ranking, so low P/E ranks higher)

    Data Source:
    - ticker_fundamentals.per (from DART API or yfinance)

    Interpretation:
    - Higher factor value = Lower P/E = Undervalued (value opportunity)
    - Lower factor value = Higher P/E = Overvalued or growth stock
    - Typical ranges: <10 (cheap), 10-20 (fair), >20 (expensive)
    """

    def __init__(self, db_path: str = "./data/spock_local.db"):
        super().__init__(
            name="PE_Ratio",
            category=FactorCategory.VALUE,
            lookback_days=365,
            min_required_days=1
        )
        self.db_path = db_path

    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Calculate P/E ratio factor from fundamental data

        Args:
            data: Not used (kept for interface compatibility)
            ticker: Stock ticker symbol

        Returns:
            FactorResult with negated P/E ratio, or None if data unavailable
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get latest P/E ratio from ticker_fundamentals
            cursor.execute("""
                SELECT per, fiscal_year, date
                FROM ticker_fundamentals
                WHERE ticker = ? AND per IS NOT NULL
                ORDER BY fiscal_year DESC, date DESC
                LIMIT 1
            """, (ticker,))

            result = cursor.fetchone()
            conn.close()

            if not result:
                logger.debug(f"{ticker} - {self.name}: No P/E data available")
                return None

            pe_ratio, fiscal_year, data_date = result

            # Sanity check: P/E should be positive and reasonable
            if pe_ratio <= 0 or pe_ratio > 1000:
                logger.debug(f"{ticker} - {self.name}: Invalid P/E value: {pe_ratio}")
                return None

            # Negate for ranking (lower P/E = higher score)
            factor_value = float(-pe_ratio)

            # Confidence based on data freshness
            confidence = 0.9  # High confidence for fundamental data

            metadata = {
                'pe_ratio': round(pe_ratio, 2),
                'fiscal_year': fiscal_year,
                'data_date': data_date,
                'interpretation': self._interpret_pe(pe_ratio)
            }

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=factor_value,
                z_score=0.0,  # Calculated at portfolio level
                percentile=50.0,
                confidence=confidence,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"{ticker} - {self.name} calculation error: {e}")
            return None

    def _interpret_pe(self, pe_ratio: float) -> str:
        """Interpret P/E ratio value"""
        if pe_ratio < 10:
            return "undervalued"
        elif pe_ratio < 20:
            return "fair_value"
        elif pe_ratio < 30:
            return "growth_premium"
        else:
            return "overvalued"

    def get_required_columns(self) -> List[str]:
        """Required DataFrame columns (unused for DB factors)"""
        return []


class PBRatioFactor(FactorBase):
    """
    Price-to-Book (P/B) Ratio Factor

    Calculation:
    - P/B = Market Price / Book Value Per Share
    - Lower P/B = higher factor score (undervalued)
    - Factor value = -P/B

    Data Source:
    - ticker_fundamentals.pbr

    Interpretation:
    - P/B < 1.0 = Trading below book value (deep value)
    - P/B 1-3 = Fair valuation
    - P/B > 3 = Premium valuation (growth or quality)
    """

    def __init__(self, db_path: str = "./data/spock_local.db"):
        super().__init__(
            name="PB_Ratio",
            category=FactorCategory.VALUE,
            lookback_days=365,
            min_required_days=1
        )
        self.db_path = db_path

    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """Calculate P/B ratio factor"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT pbr, fiscal_year, date
                FROM ticker_fundamentals
                WHERE ticker = ? AND pbr IS NOT NULL
                ORDER BY fiscal_year DESC, date DESC
                LIMIT 1
            """, (ticker,))

            result = cursor.fetchone()
            conn.close()

            if not result:
                return None

            pb_ratio, fiscal_year, data_date = result

            # Sanity check
            if pb_ratio <= 0 or pb_ratio > 100:
                return None

            factor_value = float(-pb_ratio)
            confidence = 0.9

            metadata = {
                'pb_ratio': round(pb_ratio, 2),
                'fiscal_year': fiscal_year,
                'data_date': data_date,
                'interpretation': self._interpret_pb(pb_ratio)
            }

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=factor_value,
                z_score=0.0,
                percentile=50.0,
                confidence=confidence,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"{ticker} - {self.name} calculation error: {e}")
            return None

    def _interpret_pb(self, pb_ratio: float) -> str:
        """Interpret P/B ratio value"""
        if pb_ratio < 1.0:
            return "deep_value"
        elif pb_ratio < 3.0:
            return "fair_value"
        elif pb_ratio < 5.0:
            return "growth_premium"
        else:
            return "expensive"

    def get_required_columns(self) -> List[str]:
        return []


class EVToEBITDAFactor(FactorBase):
    """
    Enterprise Value to EBITDA Factor

    Calculation:
    - EV/EBITDA = (Market Cap + Debt - Cash) / EBITDA
    - Lower EV/EBITDA = higher factor score
    - More robust than P/E (accounts for capital structure)

    Data Source:
    - ticker_fundamentals.ev_ebitda

    Interpretation:
    - EV/EBITDA < 10 = Undervalued
    - EV/EBITDA 10-15 = Fair value
    - EV/EBITDA > 15 = Expensive or high growth
    """

    def __init__(self, db_path: str = "./data/spock_local.db"):
        super().__init__(
            name="EV_To_EBITDA",
            category=FactorCategory.VALUE,
            lookback_days=365,
            min_required_days=1
        )
        self.db_path = db_path

    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """Calculate EV/EBITDA factor"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT ev_ebitda, fiscal_year, date
                FROM ticker_fundamentals
                WHERE ticker = ? AND ev_ebitda IS NOT NULL
                ORDER BY fiscal_year DESC, date DESC
                LIMIT 1
            """, (ticker,))

            result = cursor.fetchone()
            conn.close()

            if not result:
                return None

            ev_ebitda, fiscal_year, data_date = result

            # Sanity check
            if ev_ebitda <= 0 or ev_ebitda > 500:
                return None

            factor_value = float(-ev_ebitda)
            confidence = 0.9

            metadata = {
                'ev_ebitda': round(ev_ebitda, 2),
                'fiscal_year': fiscal_year,
                'data_date': data_date,
                'interpretation': self._interpret_ev_ebitda(ev_ebitda)
            }

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=factor_value,
                z_score=0.0,
                percentile=50.0,
                confidence=confidence,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"{ticker} - {self.name} calculation error: {e}")
            return None

    def _interpret_ev_ebitda(self, ev_ebitda: float) -> str:
        """Interpret EV/EBITDA value"""
        if ev_ebitda < 10:
            return "undervalued"
        elif ev_ebitda < 15:
            return "fair_value"
        elif ev_ebitda < 20:
            return "growth_premium"
        else:
            return "expensive"

    def get_required_columns(self) -> List[str]:
        return []


class DividendYieldFactor(FactorBase):
    """
    Dividend Yield Factor

    Calculation:
    - Dividend Yield = Annual Dividend / Stock Price
    - Higher dividend yield = higher factor score (income strategy)
    - Unlike other value factors, this is NOT negated

    Data Source:
    - ticker_fundamentals.dividend_yield

    Interpretation:
    - Yield > 4% = High yield (value/income stock)
    - Yield 2-4% = Moderate yield
    - Yield < 2% = Low yield (growth stock)
    - Yield 0% = No dividend (reinvestment strategy)
    """

    def __init__(self, db_path: str = "./data/spock_local.db"):
        super().__init__(
            name="Dividend_Yield",
            category=FactorCategory.VALUE,
            lookback_days=365,
            min_required_days=1
        )
        self.db_path = db_path

    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """Calculate dividend yield factor"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT dividend_yield, fiscal_year, date
                FROM ticker_fundamentals
                WHERE ticker = ? AND dividend_yield IS NOT NULL
                ORDER BY fiscal_year DESC, date DESC
                LIMIT 1
            """, (ticker,))

            result = cursor.fetchone()
            conn.close()

            if not result:
                return None

            dividend_yield, fiscal_year, data_date = result

            # Sanity check (dividend yield should be 0-20%)
            if dividend_yield < 0 or dividend_yield > 20:
                return None

            # Do NOT negate (higher yield = higher score)
            factor_value = float(dividend_yield)
            confidence = 0.9

            metadata = {
                'dividend_yield': round(dividend_yield, 2),
                'fiscal_year': fiscal_year,
                'data_date': data_date,
                'interpretation': self._interpret_dividend_yield(dividend_yield)
            }

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=factor_value,
                z_score=0.0,
                percentile=50.0,
                confidence=confidence,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"{ticker} - {self.name} calculation error: {e}")
            return None

    def _interpret_dividend_yield(self, div_yield: float) -> str:
        """Interpret dividend yield value"""
        if div_yield >= 4.0:
            return "high_yield"
        elif div_yield >= 2.0:
            return "moderate_yield"
        elif div_yield > 0:
            return "low_yield"
        else:
            return "no_dividend"

    def get_required_columns(self) -> List[str]:
        return []


class FCFYieldFactor(FactorBase):
    """
    Free Cash Flow Yield Factor

    Calculation:
    - FCF Yield = Free Cash Flow / Market Cap
    - Higher FCF yield = higher factor score
    - More reliable than dividend yield (captures total cash generation)

    Data Source:
    - ticker_fundamentals.fcf (if available) OR calculated from cash flow statement
    - ticker_fundamentals.market_cap

    Interpretation:
    - FCF Yield > 8% = High cash generation (value stock)
    - FCF Yield 4-8% = Moderate cash generation
    - FCF Yield 0-4% = Low cash generation
    - FCF Yield < 0 = Negative free cash flow (cash burn)

    Note: Free Cash Flow = Operating Cash Flow - Capital Expenditures
    """

    def __init__(self, db_path: str = "./data/spock_local.db"):
        super().__init__(
            name="FCF_Yield",
            category=FactorCategory.VALUE,
            lookback_days=365,
            min_required_days=1
        )
        self.db_path = db_path

    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Calculate FCF Yield factor

        TODO: Current implementation requires FCF data in ticker_fundamentals table.
        Schema enhancement needed to add fcf, operating_cash_flow, capex columns.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Try to get FCF and market cap from fundamentals table
            cursor.execute("""
                SELECT market_cap, date
                FROM ticker_fundamentals
                WHERE ticker = ? AND market_cap IS NOT NULL
                ORDER BY date DESC
                LIMIT 1
            """, (ticker,))

            result = cursor.fetchone()

            if not result:
                conn.close()
                return None

            market_cap, data_date = result

            # TODO: Once FCF data is available, update this query:
            # SELECT fcf, market_cap, fiscal_year, date
            # FROM ticker_fundamentals
            # WHERE ticker = ? AND fcf IS NOT NULL AND market_cap IS NOT NULL
            # ORDER BY fiscal_year DESC, date DESC
            # LIMIT 1

            # Placeholder: Return None until FCF data is populated
            conn.close()
            logger.warning(f"{ticker} - FCF data not yet available in database. Schema enhancement required.")
            return None

            # Future implementation (when FCF data is available):
            # fcf_yield = (fcf / market_cap) * 100  # Convert to percentage
            #
            # # Sanity check (FCF yield typically -20% to +20%)
            # if fcf_yield < -20 or fcf_yield > 50:
            #     return None
            #
            # # Do NOT negate (higher FCF yield = higher score)
            # factor_value = float(fcf_yield)
            # confidence = 0.9
            #
            # metadata = {
            #     'fcf': round(fcf, 2),
            #     'market_cap': round(market_cap, 2),
            #     'fcf_yield': round(fcf_yield, 2),
            #     'fiscal_year': fiscal_year,
            #     'data_date': data_date,
            #     'interpretation': self._interpret_fcf_yield(fcf_yield)
            # }
            #
            # return FactorResult(
            #     ticker=ticker,
            #     factor_name=self.name,
            #     raw_value=factor_value,
            #     z_score=0.0,
            #     percentile=50.0,
            #     confidence=confidence,
            #     metadata=metadata
            # )

        except Exception as e:
            logger.error(f"{ticker} - {self.name} calculation error: {e}")
            return None

    def _interpret_fcf_yield(self, fcf_yield: float) -> str:
        """Interpret FCF yield value"""
        if fcf_yield >= 8.0:
            return "high_cash_generation"
        elif fcf_yield >= 4.0:
            return "moderate_cash_generation"
        elif fcf_yield >= 0:
            return "low_cash_generation"
        else:
            return "cash_burn"

    def get_required_columns(self) -> List[str]:
        return []
