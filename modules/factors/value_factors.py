#!/usr/bin/env python3
"""
value_factors_postgres.py - PostgreSQL-integrated Value Factors (Option B Implementation)

This module reads pre-calculated factor scores from the factor_scores table instead of
directly querying ticker_fundamentals. This follows the Option B pattern where:
- Dividend Yield: Calculated by scripts/backfill_pykrx_fundamentals.py
- EV/EBITDA: Calculated by scripts/calculate_ev_ebitda.py
- Factor scores are stored in standardized format with percentile rankings

Value Strategy:
- Seeks undervalued stocks relative to intrinsic worth
- Classic value investing approach (Graham & Dodd)
- Combines multiple valuation metrics for robust alpha

Factors Implemented:
1. Dividend_Yield - Income-focused value metric (from pykrx DAILY data)
2. EV_EBITDA - Enterprise value relative to earnings (from DART SEMI-ANNUAL data)
3. CompositeValue - Weighted combination of both factors

Academic Foundation:
- Fama & French (1992): "The Cross-Section of Expected Stock Returns"
- Value premium: Undervalued stocks outperform growth stocks over time
- Factor independence verified: Correlation < 0.5 (Dividend Yield vs EV/EBITDA)

Data Source: PostgreSQL factor_scores table (Option B pattern)
"""

from typing import Optional, List, Dict, Any
import pandas as pd
from loguru import logger
import numpy as np
from datetime import datetime, date

# Import project modules
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.factors.factor_base import FactorBase, FactorResult, FactorCategory


class DividendYieldFactorPostgres(FactorBase):
    """
    Dividend Yield Factor - PostgreSQL Option B Implementation

    Reads pre-calculated scores from factor_scores table instead of querying ticker_fundamentals.

    Data Source:
    - factor_scores table: factor_name='Dividend_Yield', region='KR'
    - Calculated by: scripts/backfill_pykrx_fundamentals.py
    - Update frequency: Daily
    - Data source: pykrx (period_type='DAILY')

    Interpretation:
    - Higher percentile = Higher dividend yield = Better for income investors
    - Score already standardized as -log(yield) transformation
    - Percentile ranking: 100 = highest yield, 0 = lowest yield

    Factor Independence:
    - Correlation with EV/EBITDA: 0.224 (Pearson), 0.216 (Spearman)
    - ✅ PASS: < 0.5 threshold (factors are independent)
    """

    def __init__(self):
        super().__init__(
            name="Dividend_Yield",
            category=FactorCategory.VALUE,
            lookback_days=30,  # Use latest available data
            min_required_days=1
        )
        self.db = PostgresDatabaseManager()

    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Retrieve pre-calculated Dividend Yield score from factor_scores table

        Args:
            data: Not used (kept for interface compatibility)
            ticker: Stock ticker symbol

        Returns:
            FactorResult with Dividend Yield score, or None if unavailable
        """
        try:
            # Get latest Dividend Yield score from factor_scores table
            query = """
            SELECT
                ticker,
                score,
                percentile,
                date
            FROM factor_scores
            WHERE ticker = %s
              AND region = 'KR'
              AND factor_name = 'Dividend_Yield'
            ORDER BY date DESC
            LIMIT 1
            """

            result = self.db.execute_query(query, (ticker,))

            if not result or len(result) == 0:
                logger.debug(f"{ticker} - {self.name}: No data available in factor_scores")
                return None

            row = result[0]
            score = float(row['score'])
            percentile = float(row['percentile'])
            calc_date = row['date']

            # High confidence for pre-calculated factor scores
            confidence = 0.95

            # Get additional metadata from pykrx fundamentals
            meta_query = """
            SELECT
                dividend_yield,
                per,
                pbr,
                period_type,
                data_source
            FROM ticker_fundamentals
            WHERE ticker = %s
              AND region = 'KR'
              AND period_type = 'DAILY'
              AND data_source = 'pykrx'
              AND dividend_yield IS NOT NULL
            ORDER BY date DESC
            LIMIT 1
            """

            meta_result = self.db.execute_query(meta_query, (ticker,))

            metadata = {
                'calculation_date': str(calc_date),
                'data_source': 'factor_scores (pre-calculated)',
                'percentile': round(percentile, 2)
            }

            if meta_result and len(meta_result) > 0:
                meta_row = meta_result[0]
                div_yield = float(meta_row['dividend_yield']) if meta_row['dividend_yield'] else None

                if div_yield:
                    metadata.update({
                        'dividend_yield_pct': round(div_yield, 2),
                        'interpretation': self._interpret_dividend_yield(div_yield),
                        'raw_data_source': meta_row['data_source']
                    })

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=score,
                z_score=0.0,  # Already standardized in factor_scores
                percentile=percentile,
                confidence=confidence,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"{ticker} - {self.name} calculation error: {e}")
            return None

    def _interpret_dividend_yield(self, div_yield: float) -> str:
        """Interpret dividend yield percentage"""
        if div_yield >= 4.0:
            return "high_yield"
        elif div_yield >= 2.0:
            return "moderate_yield"
        elif div_yield > 0:
            return "low_yield"
        else:
            return "no_dividend"

    def get_required_columns(self) -> List[str]:
        """No DataFrame columns required (reads from database)"""
        return []


class EVToEBITDAFactorPostgres(FactorBase):
    """
    EV/EBITDA Factor - PostgreSQL Option B Implementation

    Reads pre-calculated scores from factor_scores table.

    Data Source:
    - factor_scores table: factor_name='EV_EBITDA', region='KR'
    - Calculated by: scripts/calculate_ev_ebitda.py
    - Update frequency: Semi-annual (DART reporting cycle)
    - Data sources: DART (fundamentals) + pykrx (market cap, shares outstanding)

    Calculation Formula:
    - EV/EBITDA = (Market Cap + Total Debt - Cash) / EBITDA
    - Score = -log(EV/EBITDA) transformation
    - Lower EV/EBITDA multiple = Higher score = Better value

    Interpretation:
    - Higher percentile = Lower EV/EBITDA = More undervalued
    - Percentile ranking: 100 = lowest multiple (best value), 0 = highest multiple

    Known Limitations:
    - DART universe: Only 91 large-cap stocks (80.2% coverage achieved)
    - Cash approximation: Uses current_assets (DART doesn't provide cash directly)
    - High anomaly rate: 31.1% tickers with EV/EBITDA >100 (DART data characteristics)

    Factor Independence:
    - Correlation with Dividend Yield: 0.224 (Pearson), 0.216 (Spearman)
    - ✅ PASS: < 0.5 threshold (factors are independent)
    """

    def __init__(self):
        super().__init__(
            name="EV_EBITDA",
            category=FactorCategory.VALUE,
            lookback_days=180,  # Semi-annual data
            min_required_days=1
        )
        self.db = PostgresDatabaseManager()

    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Retrieve pre-calculated EV/EBITDA score from factor_scores table

        Args:
            data: Not used (kept for interface compatibility)
            ticker: Stock ticker symbol

        Returns:
            FactorResult with EV/EBITDA score, or None if unavailable
        """
        try:
            # Get latest EV/EBITDA score from factor_scores table
            query = """
            SELECT
                ticker,
                score,
                percentile,
                date
            FROM factor_scores
            WHERE ticker = %s
              AND region = 'KR'
              AND factor_name = 'EV_EBITDA'
            ORDER BY date DESC
            LIMIT 1
            """

            result = self.db.execute_query(query, (ticker,))

            if not result or len(result) == 0:
                logger.debug(f"{ticker} - {self.name}: No data available in factor_scores (DART universe only)")
                return None

            row = result[0]
            score = float(row['score'])
            percentile = float(row['percentile'])
            calc_date = row['date']

            # High confidence for pre-calculated factor scores
            confidence = 0.90

            # Get additional metadata from DART fundamentals
            meta_query = """
            SELECT
                ebitda,
                total_liabilities,
                current_assets,
                fiscal_year,
                period_type,
                data_source
            FROM ticker_fundamentals
            WHERE ticker = %s
              AND region = 'KR'
              AND period_type IN ('ANNUAL', 'SEMI-ANNUAL')
              AND data_source = 'DART'
              AND ebitda IS NOT NULL
            ORDER BY fiscal_year DESC, date DESC
            LIMIT 1
            """

            meta_result = self.db.execute_query(meta_query, (ticker,))

            metadata = {
                'calculation_date': str(calc_date),
                'data_source': 'factor_scores (pre-calculated)',
                'percentile': round(percentile, 2),
                'note': 'DART universe only (large-cap stocks)'
            }

            if meta_result and len(meta_result) > 0:
                meta_row = meta_result[0]
                metadata.update({
                    'fiscal_year': meta_row['fiscal_year'],
                    'period_type': meta_row['period_type'],
                    'raw_data_source': meta_row['data_source'],
                    'ebitda_billion_krw': round(float(meta_row['ebitda']) / 1e9, 2) if meta_row['ebitda'] else None
                })

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=score,
                z_score=0.0,  # Already standardized in factor_scores
                percentile=percentile,
                confidence=confidence,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"{ticker} - {self.name} calculation error: {e}")
            return None

    def get_required_columns(self) -> List[str]:
        """No DataFrame columns required (reads from database)"""
        return []


class CompositeValueFactor(FactorBase):
    """
    Composite Value Factor - Weighted combination of Dividend Yield and EV/EBITDA

    Combines two independent value factors:
    1. Dividend Yield (50% weight) - Income-focused value metric
    2. EV/EBITDA (50% weight) - Enterprise value metric

    Methodology:
    - Uses percentile scores (0-100 scale) for apples-to-apples comparison
    - Equal weighting: Composite = 0.5 * DIV_PCT + 0.5 * EV_PCT
    - Higher composite score = Better overall value

    Advantages:
    - Diversified value signal (income + enterprise value)
    - Factors are independent (correlation < 0.5)
    - Covers different investor preferences (income vs capital appreciation)

    Limitations:
    - Only applicable to tickers with both factors (60 overlapping tickers)
    - EV/EBITDA limited to DART universe (91 large-cap stocks)
    - Requires both factors to be up-to-date

    Alternative Weightings (configurable):
    - Income-focused: DIV 70%, EV 30%
    - Growth-focused: DIV 30%, EV 70%
    - Equal-weight: DIV 50%, EV 50% (default)
    """

    def __init__(self, div_weight: float = 0.5, ev_weight: float = 0.5):
        super().__init__(
            name="Composite_Value",
            category=FactorCategory.VALUE,
            lookback_days=30,
            min_required_days=1
        )
        self.div_weight = div_weight
        self.ev_weight = ev_weight
        self.db = PostgresDatabaseManager()

        # Initialize component factors
        self.div_factor = DividendYieldFactorPostgres()
        self.ev_factor = EVToEBITDAFactorPostgres()

    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Calculate composite value score from Dividend Yield and EV/EBITDA

        Args:
            data: Not used (kept for interface compatibility)
            ticker: Stock ticker symbol

        Returns:
            FactorResult with composite value score, or None if insufficient data
        """
        try:
            # Get both component factor results
            div_result = self.div_factor.calculate(data, ticker)
            ev_result = self.ev_factor.calculate(data, ticker)

            # Both factors required for composite
            if not div_result or not ev_result:
                missing = []
                if not div_result:
                    missing.append("Dividend_Yield")
                if not ev_result:
                    missing.append("EV_EBITDA")

                logger.debug(f"{ticker} - {self.name}: Missing factors: {missing}")
                return None

            # Calculate composite score using percentiles
            composite_percentile = (
                self.div_weight * div_result.percentile +
                self.ev_weight * ev_result.percentile
            )

            # Calculate composite raw score (weighted average of scores)
            composite_score = (
                self.div_weight * div_result.raw_value +
                self.ev_weight * ev_result.raw_value
            )

            # Confidence is minimum of component confidences
            confidence = min(div_result.confidence, ev_result.confidence)

            metadata = {
                'div_percentile': round(div_result.percentile, 2),
                'ev_percentile': round(ev_result.percentile, 2),
                'div_weight': self.div_weight,
                'ev_weight': self.ev_weight,
                'div_interpretation': div_result.metadata.get('interpretation', 'N/A'),
                'composite_interpretation': self._interpret_composite(composite_percentile),
                'calculation_method': 'percentile_weighted_average'
            }

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=composite_score,
                z_score=0.0,  # Portfolio-level normalization
                percentile=composite_percentile,
                confidence=confidence,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"{ticker} - {self.name} calculation error: {e}")
            return None

    def _interpret_composite(self, percentile: float) -> str:
        """Interpret composite value percentile"""
        if percentile >= 80:
            return "strong_value"
        elif percentile >= 60:
            return "good_value"
        elif percentile >= 40:
            return "fair_value"
        elif percentile >= 20:
            return "weak_value"
        else:
            return "poor_value"

    def get_required_columns(self) -> List[str]:
        """No DataFrame columns required (reads from database)"""
        return []


def get_value_scores_batch(tickers: List[str], factor_type: str = 'composite') -> Dict[str, Optional[FactorResult]]:
    """
    Batch retrieve value factor scores for multiple tickers

    Args:
        tickers: List of ticker symbols
        factor_type: 'dividend_yield', 'ev_ebitda', or 'composite' (default)

    Returns:
        Dictionary mapping ticker to FactorResult (or None if unavailable)
    """
    if factor_type == 'dividend_yield':
        factor = DividendYieldFactorPostgres()
    elif factor_type == 'ev_ebitda':
        factor = EVToEBITDAFactorPostgres()
    elif factor_type == 'composite':
        factor = CompositeValueFactor()
    else:
        raise ValueError(f"Invalid factor_type: {factor_type}")

    results = {}
    for ticker in tickers:
        try:
            results[ticker] = factor.calculate(pd.DataFrame(), ticker)
        except Exception as e:
            logger.error(f"Batch calculation failed for {ticker}: {e}")
            results[ticker] = None

    return results


# Example usage
if __name__ == "__main__":
    logger.info("Testing PostgreSQL-integrated Value Factors...")

    # Test tickers (known to have both factors)
    test_tickers = ['005930', '000660', '000270', '005380', '005490']

    # Test Dividend Yield
    logger.info("\n1️⃣ Testing Dividend Yield Factor:")
    logger.info("=" * 80)
    div_factor = DividendYieldFactorPostgres()
    for ticker in test_tickers:
        result = div_factor.calculate(pd.DataFrame(), ticker)
        if result:
            logger.info(f"{ticker}: Percentile={result.percentile:.1f}, Score={result.raw_value:.4f}")
        else:
            logger.warning(f"{ticker}: No data")

    # Test EV/EBITDA
    logger.info("\n2️⃣ Testing EV/EBITDA Factor:")
    logger.info("=" * 80)
    ev_factor = EVToEBITDAFactorPostgres()
    for ticker in test_tickers:
        result = ev_factor.calculate(pd.DataFrame(), ticker)
        if result:
            logger.info(f"{ticker}: Percentile={result.percentile:.1f}, Score={result.raw_value:.4f}")
        else:
            logger.warning(f"{ticker}: No data")

    # Test Composite Value
    logger.info("\n3️⃣ Testing Composite Value Factor:")
    logger.info("=" * 80)
    composite_factor = CompositeValueFactor()
    for ticker in test_tickers:
        result = composite_factor.calculate(pd.DataFrame(), ticker)
        if result:
            logger.info(
                f"{ticker}: Composite={result.percentile:.1f}, "
                f"Interpretation={result.metadata.get('composite_interpretation', 'N/A')}"
            )
        else:
            logger.warning(f"{ticker}: Incomplete data")


# ============================================================================
# Backward Compatibility Layer (Deprecated)
# ============================================================================
# These classes provide backward compatibility for legacy tests that reference
# the old SQLite-based factor names. New code should use the PostgreSQL versions.
# ============================================================================

class PERatioFactor(DividendYieldFactorPostgres):
    """
    DEPRECATED: P/E Ratio Factor (backward compatibility)

    This class has been deprecated and is replaced by PostgreSQL-based factors.
    P/E ratio data is not available in the current factor_scores table.

    For backward compatibility, this aliases to DividendYieldFactorPostgres.
    Consider migrating to the new PostgreSQL-based value factors:
    - DividendYieldFactorPostgres
    - EVToEBITDAFactorPostgres
    - CompositeValueFactor
    """

    def __init__(self, db_path: str = None):
        """
        Initialize deprecated PERatioFactor

        Args:
            db_path: IGNORED - kept for backward compatibility only
        """
        if db_path:
            logger.warning(
                "PERatioFactor is deprecated. The 'db_path' parameter is ignored. "
                "P/E ratio data not available in factor_scores table. "
                "Using DividendYieldFactorPostgres as fallback. "
                "Please migrate to PostgreSQL-based factors."
            )
        super().__init__()
        self.name = "PE_Ratio_DEPRECATED"

    def _interpret_pe(self, pe_value: float) -> str:
        """Legacy method for backward compatibility"""
        if pe_value < 10:
            return "undervalued"
        elif pe_value < 20:
            return "fair_value"
        else:
            return "overvalued"


class PBRatioFactor(EVToEBITDAFactorPostgres):
    """
    DEPRECATED: P/B Ratio Factor (backward compatibility)

    This class has been deprecated and is replaced by PostgreSQL-based factors.
    P/B ratio data is not available in the current factor_scores table.

    For backward compatibility, this aliases to EVToEBITDAFactorPostgres.
    Consider migrating to the new PostgreSQL-based value factors:
    - DividendYieldFactorPostgres
    - EVToEBITDAFactorPostgres
    - CompositeValueFactor
    """

    def __init__(self, db_path: str = None):
        """
        Initialize deprecated PBRatioFactor

        Args:
            db_path: IGNORED - kept for backward compatibility only
        """
        if db_path:
            logger.warning(
                "PBRatioFactor is deprecated. The 'db_path' parameter is ignored. "
                "P/B ratio data not available in factor_scores table. "
                "Using EVToEBITDAFactorPostgres as fallback. "
                "Please migrate to PostgreSQL-based factors."
            )
        super().__init__()
        self.name = "PB_Ratio_DEPRECATED"

    def _interpret_pb(self, pb_value: float) -> str:
        """Legacy method for backward compatibility"""
        if pb_value < 1.0:
            return "deep_value"
        elif pb_value < 3.0:
            return "fair_value"
        else:
            return "overvalued"


class EVToEBITDAFactor(EVToEBITDAFactorPostgres):
    """
    DEPRECATED: EV/EBITDA Factor (backward compatibility)

    This class has been replaced by EVToEBITDAFactorPostgres.
    Use the PostgreSQL version directly for new code.
    """

    def __init__(self, db_path: str = None):
        """
        Initialize deprecated EVToEBITDAFactor

        Args:
            db_path: IGNORED - kept for backward compatibility only
        """
        if db_path:
            logger.warning(
                "EVToEBITDAFactor is deprecated. The 'db_path' parameter is ignored. "
                "Using EVToEBITDAFactorPostgres instead. "
                "Please migrate to EVToEBITDAFactorPostgres directly."
            )
        super().__init__()


class DividendYieldFactor(DividendYieldFactorPostgres):
    """
    DEPRECATED: Dividend Yield Factor (backward compatibility)

    This class has been replaced by DividendYieldFactorPostgres.
    Use the PostgreSQL version directly for new code.
    """

    def __init__(self, db_path: str = None):
        """
        Initialize deprecated DividendYieldFactor

        Args:
            db_path: IGNORED - kept for backward compatibility only
        """
        if db_path:
            logger.warning(
                "DividendYieldFactor is deprecated. The 'db_path' parameter is ignored. "
                "Using DividendYieldFactorPostgres instead. "
                "Please migrate to DividendYieldFactorPostgres directly."
            )
        super().__init__()


# ============================================================================
# HK Market Value Factors (Direct Calculation from ticker_fundamentals)
# ============================================================================

class PERatioFactorHK(FactorBase):
    """
    P/E Ratio Factor for HK Market

    Calculates value score based on Price-to-Earnings ratio from yfinance data.

    Data Source:
    - ticker_fundamentals table: per column, region='HK'
    - Update frequency: Daily (from yfinance API)
    - Coverage: 58.80% (1,550/2,636 tickers with P/E data)

    Calculation:
    - Lower P/E = Better value (more undervalued)
    - Score = -log(P/E) transformation for normalization
    - Handles negative P/E (unprofitable companies) → excluded from ranking

    Interpretation:
    - Higher percentile = Lower P/E = More undervalued
    - Typical ranges: P/E < 10 (deep value), 10-20 (fair), >20 (growth premium)

    Known Limitations:
    - 41.20% missing data (unprofitable companies, newly listed)
    - Negative earnings → no P/E ratio
    - Should be combined with other value metrics for robustness
    """

    def __init__(self, region: str = 'HK'):
        super().__init__(
            name=f"PE_Ratio_{region}",
            category=FactorCategory.VALUE,
            lookback_days=30,
            min_required_days=1
        )
        self.region = region
        self.db = PostgresDatabaseManager()

    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Calculate P/E ratio factor score

        Args:
            data: Not used (kept for interface compatibility)
            ticker: Stock ticker symbol

        Returns:
            FactorResult with P/E factor score, or None if unavailable
        """
        try:
            # Normalize ticker format for HK market (yfinance uses .HK suffix)
            ticker_for_query = f"{ticker}.HK" if not ticker.endswith('.HK') else ticker

            # Get latest P/E ratio from ticker_fundamentals
            query = """
            SELECT
                ticker,
                per,
                pbr,
                market_cap,
                date
            FROM ticker_fundamentals
            WHERE ticker = %s
              AND region = %s
              AND per IS NOT NULL
              AND per > 0
            ORDER BY date DESC
            LIMIT 1
            """

            result = self.db.execute_query(query, (ticker_for_query, self.region))

            if not result or len(result) == 0:
                logger.debug(f"{ticker} - {self.name}: No P/E data available")
                return None

            row = result[0]
            pe_ratio = float(row['per'])
            calc_date = row['date']

            # Validate P/E range (exclude extreme outliers)
            if pe_ratio <= 0 or pe_ratio > 1000:
                logger.debug(f"{ticker} - {self.name}: P/E={pe_ratio} out of valid range")
                return None

            # Calculate score: -log(P/E) so lower P/E = higher score
            score = -np.log(pe_ratio)

            # High confidence for fundamental data
            confidence = 0.90

            metadata = {
                'pe_ratio': round(pe_ratio, 2),
                'calculation_date': str(calc_date),
                'data_source': 'yfinance (ticker_fundamentals)',
                'interpretation': self._interpret_pe(pe_ratio),
                'market_cap': float(row['market_cap']) if row['market_cap'] else None
            }

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=score,
                z_score=0.0,  # Will be calculated during cross-sectional ranking
                percentile=0.0,  # Will be calculated during cross-sectional ranking
                confidence=confidence,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"{ticker} - {self.name} calculation error: {e}")
            return None

    def _interpret_pe(self, pe_value: float) -> str:
        """Interpret P/E ratio value"""
        if pe_value < 10:
            return "deep_value"
        elif pe_value < 15:
            return "moderate_value"
        elif pe_value < 20:
            return "fair_value"
        else:
            return "growth_premium"

    def get_required_columns(self) -> List[str]:
        """No DataFrame columns required (reads from database)"""
        return []


class PBRatioFactorHK(FactorBase):
    """
    P/B Ratio Factor for HK Market

    Calculates value score based on Price-to-Book ratio from yfinance data.

    Data Source:
    - ticker_fundamentals table: pbr column, region='HK'
    - Update frequency: Daily (from yfinance API)
    - Coverage: 99.77% (2,630/2,636 tickers) ✅ Excellent

    Calculation:
    - Lower P/B = Better value (trading below book value)
    - Score = -log(P/B) transformation for normalization
    - P/B < 1.0 indicates potential deep value (trading below net assets)

    Interpretation:
    - Higher percentile = Lower P/B = More undervalued
    - Typical ranges: P/B < 1 (deep value), 1-3 (fair), >3 (premium/growth)

    Advantages:
    - Near-perfect coverage (99.77%) - most reliable value metric for HK
    - Stable metric (less volatile than P/E)
    - Applicable to loss-making companies (unlike P/E)
    """

    def __init__(self, region: str = 'HK'):
        super().__init__(
            name=f"PB_Ratio_{region}",
            category=FactorCategory.VALUE,
            lookback_days=30,
            min_required_days=1
        )
        self.region = region
        self.db = PostgresDatabaseManager()

    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Calculate P/B ratio factor score

        Args:
            data: Not used (kept for interface compatibility)
            ticker: Stock ticker symbol

        Returns:
            FactorResult with P/B factor score, or None if unavailable
        """
        try:
            # Normalize ticker format for HK market (yfinance uses .HK suffix)
            ticker_for_query = f"{ticker}.HK" if not ticker.endswith('.HK') else ticker

            # Get latest P/B ratio from ticker_fundamentals
            query = """
            SELECT
                ticker,
                pbr,
                per,
                market_cap,
                date
            FROM ticker_fundamentals
            WHERE ticker = %s
              AND region = %s
              AND pbr IS NOT NULL
              AND pbr > 0
            ORDER BY date DESC
            LIMIT 1
            """

            result = self.db.execute_query(query, (ticker_for_query, self.region))

            if not result or len(result) == 0:
                logger.debug(f"{ticker} - {self.name}: No P/B data available")
                return None

            row = result[0]
            pb_ratio = float(row['pbr'])
            calc_date = row['date']

            # Validate P/B range (exclude extreme outliers)
            if pb_ratio <= 0 or pb_ratio > 100:
                logger.debug(f"{ticker} - {self.name}: P/B={pb_ratio} out of valid range")
                return None

            # Calculate score: -log(P/B) so lower P/B = higher score
            score = -np.log(pb_ratio)

            # Very high confidence due to excellent coverage
            confidence = 0.95

            metadata = {
                'pb_ratio': round(pb_ratio, 2),
                'calculation_date': str(calc_date),
                'data_source': 'yfinance (ticker_fundamentals)',
                'interpretation': self._interpret_pb(pb_ratio),
                'market_cap': float(row['market_cap']) if row['market_cap'] else None
            }

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=score,
                z_score=0.0,
                percentile=0.0,
                confidence=confidence,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"{ticker} - {self.name} calculation error: {e}")
            return None

    def _interpret_pb(self, pb_value: float) -> str:
        """Interpret P/B ratio value"""
        if pb_value < 1.0:
            return "deep_value"
        elif pb_value < 2.0:
            return "moderate_value"
        elif pb_value < 3.0:
            return "fair_value"
        else:
            return "premium_growth"

    def get_required_columns(self) -> List[str]:
        """No DataFrame columns required (reads from database)"""
        return []


class PSRatioFactorHK(FactorBase):
    """
    P/S Ratio Factor for HK Market

    Calculates value score based on Price-to-Sales ratio from yfinance data.

    Data Source:
    - ticker_fundamentals table: psr column, region='HK'
    - Update frequency: Daily (from yfinance API)
    - Expected coverage: ~90% (sales data more widely available than earnings)

    Calculation:
    - Lower P/S = Better value (cheaper relative to revenue)
    - Score = -log(P/S) transformation for normalization
    - Useful for unprofitable companies (sales always positive)

    Interpretation:
    - Higher percentile = Lower P/S = More undervalued
    - Typical ranges: P/S < 1 (deep value), 1-3 (fair), >5 (high growth)

    Advantages:
    - Applicable to unprofitable companies (unlike P/E)
    - More stable than P/E (revenue less volatile than earnings)
    - Complements P/E and P/B for comprehensive value assessment
    """

    def __init__(self, region: str = 'HK'):
        super().__init__(
            name=f"PS_Ratio_{region}",
            category=FactorCategory.VALUE,
            lookback_days=30,
            min_required_days=1
        )
        self.region = region
        self.db = PostgresDatabaseManager()

    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Calculate P/S ratio factor score

        Args:
            data: Not used (kept for interface compatibility)
            ticker: Stock ticker symbol

        Returns:
            FactorResult with P/S factor score, or None if unavailable
        """
        try:
            # Normalize ticker format for HK market (yfinance uses .HK suffix)
            ticker_for_query = f"{ticker}.HK" if not ticker.endswith('.HK') else ticker

            # Get latest P/S ratio from ticker_fundamentals
            query = """
            SELECT
                ticker,
                psr,
                per,
                pbr,
                market_cap,
                date
            FROM ticker_fundamentals
            WHERE ticker = %s
              AND region = %s
              AND psr IS NOT NULL
              AND psr > 0
            ORDER BY date DESC
            LIMIT 1
            """

            result = self.db.execute_query(query, (ticker_for_query, self.region))

            if not result or len(result) == 0:
                logger.debug(f"{ticker} - {self.name}: No P/S data available")
                return None

            row = result[0]
            ps_ratio = float(row['psr'])
            calc_date = row['date']

            # Validate P/S range (exclude extreme outliers)
            if ps_ratio <= 0 or ps_ratio > 50:
                logger.debug(f"{ticker} - {self.name}: P/S={ps_ratio} out of valid range")
                return None

            # Calculate score: -log(P/S) so lower P/S = higher score
            score = -np.log(ps_ratio)

            # High confidence for sales-based metric
            confidence = 0.90

            metadata = {
                'ps_ratio': round(ps_ratio, 2),
                'calculation_date': str(calc_date),
                'data_source': 'yfinance (ticker_fundamentals)',
                'interpretation': self._interpret_ps(ps_ratio),
                'market_cap': float(row['market_cap']) if row['market_cap'] else None
            }

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=score,
                z_score=0.0,
                percentile=0.0,
                confidence=confidence,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"{ticker} - {self.name} calculation error: {e}")
            return None

    def _interpret_ps(self, ps_value: float) -> str:
        """Interpret P/S ratio value"""
        if ps_value < 1.0:
            return "deep_value"
        elif ps_value < 2.0:
            return "moderate_value"
        elif ps_value < 5.0:
            return "fair_value"
        else:
            return "high_growth"

    def get_required_columns(self) -> List[str]:
        """No DataFrame columns required (reads from database)"""
        return []


class EVEBITDAFactorHK(FactorBase):
    """
    EV/EBITDA Factor for HK Market

    Calculates value score based on Enterprise Value to EBITDA ratio from yfinance data.

    Data Source:
    - ticker_fundamentals table: ev_ebitda column, region='HK'
    - Update frequency: Daily (from yfinance API)
    - Expected coverage: ~90% (EBITDA widely reported for established companies)

    Calculation:
    - Lower EV/EBITDA = Better value (cheaper on operating earnings basis)
    - Score = -log(EV/EBITDA) transformation for normalization
    - Accounts for debt (unlike P/E which ignores capital structure)

    Interpretation:
    - Higher percentile = Lower EV/EBITDA = More undervalued
    - Typical ranges: EV/EBITDA < 8 (value), 8-12 (fair), >15 (premium)

    Advantages:
    - Capital structure neutral (considers debt)
    - Less affected by one-time items than net income
    - Industry-comparable (EBITDA pre-depreciation)
    - Preferred metric for M&A valuations
    """

    def __init__(self, region: str = 'HK'):
        super().__init__(
            name=f"EV_EBITDA_{region}",
            category=FactorCategory.VALUE,
            lookback_days=30,
            min_required_days=1
        )
        self.region = region
        self.db = PostgresDatabaseManager()

    def calculate(self, data: pd.DataFrame, ticker: str) -> Optional[FactorResult]:
        """
        Calculate EV/EBITDA factor score

        Args:
            data: Not used (kept for interface compatibility)
            ticker: Stock ticker symbol

        Returns:
            FactorResult with EV/EBITDA factor score, or None if unavailable
        """
        try:
            # Normalize ticker format for HK market (yfinance uses .HK suffix)
            ticker_for_query = f"{ticker}.HK" if not ticker.endswith('.HK') else ticker

            # Get latest EV/EBITDA from ticker_fundamentals
            query = """
            SELECT
                ticker,
                ev_ebitda,
                ev,
                market_cap,
                date
            FROM ticker_fundamentals
            WHERE ticker = %s
              AND region = %s
              AND ev_ebitda IS NOT NULL
            ORDER BY date DESC
            LIMIT 1
            """

            result = self.db.execute_query(query, (ticker_for_query, self.region))

            if not result or len(result) == 0:
                logger.debug(f"{ticker} - {self.name}: No EV/EBITDA data available")
                return None

            row = result[0]
            ev_ebitda = float(row['ev_ebitda'])
            calc_date = row['date']

            # Validate EV/EBITDA range (exclude extreme outliers and negatives)
            if ev_ebitda <= 0 or ev_ebitda > 100:
                logger.debug(f"{ticker} - {self.name}: EV/EBITDA={ev_ebitda} out of valid range")
                return None

            # Calculate score: -log(EV/EBITDA) so lower multiple = higher score
            score = -np.log(ev_ebitda)

            # High confidence for EV-based metric
            confidence = 0.90

            metadata = {
                'ev_ebitda': round(ev_ebitda, 2),
                'calculation_date': str(calc_date),
                'data_source': 'yfinance (ticker_fundamentals)',
                'interpretation': self._interpret_ev_ebitda(ev_ebitda),
                'ev': float(row['ev']) if row['ev'] else None,
                'market_cap': float(row['market_cap']) if row['market_cap'] else None
            }

            return FactorResult(
                ticker=ticker,
                factor_name=self.name,
                raw_value=score,
                z_score=0.0,
                percentile=0.0,
                confidence=confidence,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"{ticker} - {self.name} calculation error: {e}")
            return None

    def _interpret_ev_ebitda(self, ev_ebitda_value: float) -> str:
        """Interpret EV/EBITDA ratio value"""
        if ev_ebitda_value < 8:
            return "deep_value"
        elif ev_ebitda_value < 12:
            return "fair_value"
        elif ev_ebitda_value < 15:
            return "moderate_premium"
        else:
            return "high_premium"

    def get_required_columns(self) -> List[str]:
        """No DataFrame columns required (reads from database)"""
        return []


class ValueFactorCalculatorHK:
    """
    Composite Value Score Calculator for HK Market
    
    Combines 4 value factors with weighted scoring:
    - P/B Ratio: 35% (highest weight, 99.77% coverage)
    - EV/EBITDA: 25% (capital structure neutral)
    - P/E Ratio: 20% (traditional metric)
    - P/S Ratio: 20% (applicable to unprofitable companies)
    
    Minimum Requirement: At least 2 factors needed for composite score
    
    Usage:
        calculator = ValueFactorCalculatorHK(region='HK')
        df = calculator.calculate_all_tickers()
        print(df.head(20))  # Top 20 value stocks
    """
    
    def __init__(self, region: str = 'HK'):
        self.region = region
        self.pe_factor = PERatioFactorHK(region=region)
        self.pb_factor = PBRatioFactorHK(region=region)
        self.ps_factor = PSRatioFactorHK(region=region)
        self.ev_ebitda_factor = EVEBITDAFactorHK(region=region)
        
        # Factor weights (sum = 1.0)
        self.weights = {
            'PE_Ratio_HK': 0.20,
            'PB_Ratio_HK': 0.35,  # Highest weight due to best coverage
            'PS_Ratio_HK': 0.20,
            'EV_EBITDA_HK': 0.25
        }
        
        self.results = {}
    
    def calculate_single_ticker(self, ticker: str, data: Optional[pd.DataFrame] = None) -> Optional[Dict[str, Any]]:
        """
        Calculate composite value score for a single ticker
        
        Args:
            ticker: Ticker symbol
            data: Optional OHLCV data (not used in HK implementation, kept for interface compatibility)
        
        Returns:
            Dictionary with composite score and individual factor values
            None if fewer than 2 factors available
        """
        try:
            # Calculate all 4 individual factors
            factor_results = {}
            
            pe_result = self.pe_factor.calculate(data, ticker)
            if pe_result:
                factor_results['PE_Ratio_HK'] = pe_result
            
            pb_result = self.pb_factor.calculate(data, ticker)
            if pb_result:
                factor_results['PB_Ratio_HK'] = pb_result
            
            ps_result = self.ps_factor.calculate(data, ticker)
            if ps_result:
                factor_results['PS_Ratio_HK'] = ps_result
            
            ev_result = self.ev_ebitda_factor.calculate(data, ticker)
            if ev_result:
                factor_results['EV_EBITDA_HK'] = ev_result
            
            # Need minimum 2 factors for composite score
            if len(factor_results) < 2:
                logger.warning(f"{ticker}: Insufficient factors ({len(factor_results)}/4). Need minimum 2.")
                return None
            
            # Renormalize weights for available factors
            available_factors = list(factor_results.keys())
            available_weights = {k: v for k, v in self.weights.items() if k in available_factors}
            total_weight = sum(available_weights.values())
            normalized_weights = {k: v/total_weight for k, v in available_weights.items()}
            
            # Calculate weighted composite score
            composite_score = 0.0
            individual_scores = {}
            
            for factor_name, result in factor_results.items():
                weight = normalized_weights[factor_name]
                score = result.raw_value
                composite_score += score * weight
                individual_scores[factor_name] = {
                    'score': round(score, 4),
                    'weight': round(weight, 4),
                    'metadata': result.metadata
                }
            
            return {
                'ticker': ticker,
                'composite_score': round(composite_score, 4),
                'num_factors': len(factor_results),
                'individual_scores': individual_scores,
                'coverage': {
                    'PE': 'PE_Ratio_HK' in factor_results,
                    'PB': 'PB_Ratio_HK' in factor_results,
                    'PS': 'PS_Ratio_HK' in factor_results,
                    'EV_EBITDA': 'EV_EBITDA_HK' in factor_results
                }
            }
            
        except Exception as e:
            logger.error(f"{ticker}: Error calculating composite score - {str(e)}")
            return None
    
    def calculate_all_tickers(self, tickers: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Calculate composite value scores for all tickers
        
        Args:
            tickers: List of tickers (if None, fetch all active HK tickers)
        
        Returns:
            DataFrame with columns: ticker, composite_score, percentile, num_factors, PE, PB, PS, EV_EBITDA
            Sorted by composite_score descending (highest value = best)
        """
        if tickers is None:
            # Fetch all active HK tickers
            db = PostgresDatabaseManager()
            query = """
                SELECT DISTINCT ticker 
                FROM tickers 
                WHERE region = %s AND is_active = true
                ORDER BY ticker
            """
            result = db.execute_query(query, (self.region,))
            tickers = [row['ticker'] for row in result]
            logger.info(f"Fetched {len(tickers)} active HK tickers")
        
        # Calculate for each ticker
        results = []
        for i, ticker in enumerate(tickers, 1):
            if i % 100 == 0:
                logger.info(f"Progress: {i}/{len(tickers)} tickers processed")
            
            result = self.calculate_single_ticker(ticker)
            if result:
                results.append(result)
                self.results[ticker] = result
        
        if not results:
            logger.warning("No valid results calculated")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(results)
        
        # Calculate percentile ranking (cross-sectional)
        df['percentile'] = df['composite_score'].rank(pct=True) * 100
        
        # Extract individual factor values for easier analysis
        for factor_name in ['PE_Ratio_HK', 'PB_Ratio_HK', 'PS_Ratio_HK', 'EV_EBITDA_HK']:
            short_name = factor_name.replace('_HK', '').replace('_Ratio', '')
            df[short_name] = df['individual_scores'].apply(
                lambda x: x.get(factor_name, {}).get('score') if isinstance(x, dict) else None
            )
        
        # Sort by composite score descending
        df = df.sort_values('composite_score', ascending=False).reset_index(drop=True)
        
        # Select final columns
        df = df[['ticker', 'composite_score', 'percentile', 'num_factors', 
                 'PE', 'PB', 'PS', 'EV_EBITDA', 'coverage']]
        
        logger.info(f"✅ Calculated composite scores for {len(df)} tickers")
        return df
    
    def get_factor_coverage_report(self) -> Dict[str, Any]:
        """
        Generate coverage statistics for all factors
        
        Returns:
            Dictionary with coverage percentages and sample sizes
        """
        if not self.results:
            logger.warning("No results available. Run calculate_all_tickers() first.")
            return {}
        
        total_tickers = len(self.results)
        coverage = {
            'total_tickers': total_tickers,
            'factors': {}
        }
        
        for factor_name in ['PE', 'PB', 'PS', 'EV_EBITDA']:
            count = sum(1 for r in self.results.values() 
                       if r['coverage'].get(factor_name, False))
            percentage = (count / total_tickers * 100) if total_tickers > 0 else 0
            coverage['factors'][factor_name] = {
                'count': count,
                'percentage': round(percentage, 2)
            }
        
        # Distribution by number of factors
        factor_count_dist = {}
        for r in self.results.values():
            num_factors = r['num_factors']
            factor_count_dist[num_factors] = factor_count_dist.get(num_factors, 0) + 1
        
        coverage['factor_count_distribution'] = factor_count_dist
        
        return coverage
