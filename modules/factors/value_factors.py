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

    logger.info("\n✅ PostgreSQL-integrated Value Factors test complete!")
