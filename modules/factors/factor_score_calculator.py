#!/usr/bin/env python3
"""
Factor Score Calculator - All-in-One Factor Calculation

Calculates all 27 factor scores for any ticker with automatic data fetching.

Usage Example:
    from modules.factors import FactorScoreCalculator, EqualWeightCombiner

    calculator = FactorScoreCalculator()

    # Calculate all 27 factor scores
    scores = calculator.calculate_all_scores('005930')
    # Result: {'momentum_12m': 75.5, 'rsi_momentum': 68.2, ..., 'equity_turnover': 3.2}

    # Calculate composite alpha score
    combiner = EqualWeightCombiner()
    alpha_score = calculator.calculate_composite_score('005930', combiner)
    # Result: 65.8

Author: Spock Quant Platform - Phase 2 Multi-Factor (Updated: Phase 2B)
"""

import logging
import sqlite3
import pandas as pd
from typing import Dict, Optional
from .factor_combiner import FactorCombinerBase

logger = logging.getLogger(__name__)


class FactorScoreCalculator:
    """
    All-in-one factor score calculator for 27 factors

    Handles:
    - Factor instance initialization
    - OHLCV data fetching from database
    - Factor score calculation
    - Integration with any combiner
    """

    def __init__(self, db_path: str = "./data/spock_local.db"):
        """
        Initialize calculator with all 27 factor instances

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._initialize_factors()

        logger.info(f"Initialized FactorScoreCalculator with {len(self.factors)} factors")

    def _initialize_factors(self):
        """Initialize all 27 factor instances (22 existing + 5 new)"""
        from modules.factors import (
            # Momentum factors (3)
            TwelveMonthMomentumFactor,
            RSIMomentumFactor,
            ShortTermMomentumFactor,

            # Low-volatility factors (3)
            HistoricalVolatilityFactor,
            BetaFactor,
            MaxDrawdownFactor,

            # Value factors (4)
            PERatioFactor,
            PBRatioFactor,
            EVToEBITDAFactor,
            DividendYieldFactor,

            # Quality factors (9)
            ROEFactor,
            ROAFactor,
            OperatingMarginFactor,
            NetProfitMarginFactor,
            CurrentRatioFactor,
            QuickRatioFactor,
            DebtToEquityFactor,
            AccrualsRatioFactor,
            CFToNIRatioFactor,

            # Size factors (3)
            MarketCapFactor,
            LiquidityFactor,
            FloatFactor,

            # Growth factors (3) - NEW
            RevenueGrowthFactor,
            OperatingProfitGrowthFactor,
            NetIncomeGrowthFactor,

            # Efficiency factors (2) - NEW
            AssetTurnoverFactor,
            EquityTurnoverFactor
        )

        self.factors = {
            # Momentum (3) - no db_path needed
            'momentum_12m': TwelveMonthMomentumFactor(),
            'rsi_momentum': RSIMomentumFactor(),
            'short_term_momentum': ShortTermMomentumFactor(),

            # Low-volatility (3) - no db_path needed
            'volatility': HistoricalVolatilityFactor(),
            'beta': BetaFactor(),
            'max_drawdown': MaxDrawdownFactor(),

            # Value (4) - requires db_path
            'pe_ratio': PERatioFactor(db_path=self.db_path),
            'pb_ratio': PBRatioFactor(db_path=self.db_path),
            'ev_ebitda': EVToEBITDAFactor(db_path=self.db_path),
            'dividend_yield': DividendYieldFactor(db_path=self.db_path),

            # Quality (9) - PostgreSQL direct connection
            'roe': ROEFactor(),
            'roa': ROAFactor(),
            'operating_margin': OperatingMarginFactor(),
            'net_margin': NetProfitMarginFactor(),
            'current_ratio': CurrentRatioFactor(),
            'quick_ratio': QuickRatioFactor(),
            'debt_to_equity': DebtToEquityFactor(),
            'accruals_ratio': AccrualsRatioFactor(),
            'cf_to_ni': CFToNIRatioFactor(),

            # Size (3) - requires db_path
            'market_cap': MarketCapFactor(db_path=self.db_path),
            'liquidity': LiquidityFactor(db_path=self.db_path),
            'float': FloatFactor(db_path=self.db_path),

            # Growth (3) - NEW
            'revenue_growth': RevenueGrowthFactor(),
            'operating_profit_growth': OperatingProfitGrowthFactor(),
            'net_income_growth': NetIncomeGrowthFactor(),

            # Efficiency (2) - NEW
            'asset_turnover': AssetTurnoverFactor(),
            'equity_turnover': EquityTurnoverFactor(),
        }

    def _fetch_ohlcv_data(self, ticker: str, region: str = 'KR', days: int = 365) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV data from database

        Args:
            ticker: Stock ticker code
            region: Market region (KR, US, CN, etc.)
            days: Number of days to fetch

        Returns:
            DataFrame with columns: [date, open, high, low, close, volume]
            None if no data available
        """
        try:
            conn = sqlite3.connect(self.db_path)

            query = """
                SELECT date, open, high, low, close, volume
                FROM ohlcv_data
                WHERE ticker = ? AND region = ?
                ORDER BY date DESC
                LIMIT ?
            """

            df = pd.read_sql_query(query, conn, params=(ticker, region, days))
            conn.close()

            if df.empty:
                logger.warning(f"No OHLCV data found for {ticker} ({region})")
                return None

            # Sort chronologically (oldest first)
            df = df.sort_values('date').reset_index(drop=True)

            logger.debug(f"Fetched {len(df)} days of OHLCV data for {ticker}")
            return df

        except Exception as e:
            logger.error(f"Failed to fetch OHLCV data for {ticker}: {e}")
            return None

    def calculate_all_scores(
        self,
        ticker: str,
        region: str = 'KR',
        data: Optional[pd.DataFrame] = None
    ) -> Dict[str, Optional[float]]:
        """
        Calculate all 27 factor scores for a ticker

        Args:
            ticker: Stock ticker code
            region: Market region (KR, US, CN, etc.)
            data: Optional pre-fetched OHLCV DataFrame
                  If None, will fetch from database automatically

        Returns:
            Dictionary of factor scores {factor_name: score}
            None values for factors with missing data

        Example:
            scores = calculator.calculate_all_scores('005930')
            # Result:
            # {
            #     'momentum_12m': 75.5,
            #     'rsi_momentum': 68.2,
            #     'short_term_momentum': 72.0,
            #     ...
            #     'revenue_growth': 12.5,
            #     'asset_turnover': 1.8,
            #     'equity_turnover': 3.2
            # }
        """
        # Fetch OHLCV data if not provided
        if data is None:
            data = self._fetch_ohlcv_data(ticker, region)

        scores = {}

        # Calculate each factor
        for factor_name, factor_instance in self.factors.items():
            try:
                result = factor_instance.calculate(data, ticker)

                if result:
                    scores[factor_name] = result.raw_value
                else:
                    scores[factor_name] = None
                    logger.debug(f"{ticker} - {factor_name}: No data")

            except Exception as e:
                scores[factor_name] = None
                logger.warning(f"{ticker} - {factor_name}: Error - {e}")

        # Count valid scores
        valid_count = sum(1 for v in scores.values() if v is not None)
        logger.info(f"{ticker}: Calculated {valid_count}/27 factor scores")

        return scores

    def calculate_composite_score(
        self,
        ticker: str,
        combiner: FactorCombinerBase,
        region: str = 'KR',
        data: Optional[pd.DataFrame] = None
    ) -> float:
        """
        Calculate composite alpha score using specified combiner

        Args:
            ticker: Stock ticker code
            combiner: FactorCombiner instance (Equal, Category, or Optimization)
            region: Market region
            data: Optional pre-fetched OHLCV DataFrame

        Returns:
            Composite alpha score (0-100 range)

        Example:
            from modules.factors import EqualWeightCombiner

            combiner = EqualWeightCombiner()
            alpha = calculator.calculate_composite_score('005930', combiner)
            # Result: 65.8
        """
        # Calculate all factor scores
        factor_scores = self.calculate_all_scores(ticker, region, data)

        # Filter out None values
        valid_scores = {
            name: score
            for name, score in factor_scores.items()
            if score is not None
        }

        if not valid_scores:
            logger.warning(f"{ticker}: No valid factor scores - returning neutral 50.0")
            return 50.0

        # Combine using specified combiner
        composite = combiner.combine(valid_scores)

        logger.info(f"{ticker}: Alpha score = {composite:.2f} ({len(valid_scores)} factors)")
        return composite

    def batch_calculate_scores(
        self,
        tickers: list,
        region: str = 'KR'
    ) -> pd.DataFrame:
        """
        Calculate factor scores for multiple tickers (batch)

        Args:
            tickers: List of ticker codes
            region: Market region

        Returns:
            DataFrame with columns: [ticker, factor1, factor2, ..., factor27]

        Example:
            tickers = ['005930', '000660', '035720']
            df = calculator.batch_calculate_scores(tickers)
            # Result:
            #    ticker  momentum_12m  rsi_momentum  ...  asset_turnover  equity_turnover
            # 0  005930         75.5          68.2  ...            1.8              3.2
            # 1  000660         82.1          75.0  ...            2.1              4.5
            # 2  035720         68.0          62.5  ...            1.5              2.8
        """
        results = []

        for ticker in tickers:
            scores = self.calculate_all_scores(ticker, region)
            scores['ticker'] = ticker
            results.append(scores)

        df = pd.DataFrame(results)

        # Reorder columns (ticker first, then factors)
        factor_cols = [col for col in df.columns if col != 'ticker']
        df = df[['ticker'] + factor_cols]

        logger.info(f"Batch calculated scores for {len(tickers)} tickers")
        return df

    def batch_calculate_composite(
        self,
        tickers: list,
        combiner: FactorCombinerBase,
        region: str = 'KR'
    ) -> pd.DataFrame:
        """
        Calculate composite alpha scores for multiple tickers

        Args:
            tickers: List of ticker codes
            combiner: FactorCombiner instance
            region: Market region

        Returns:
            DataFrame with columns: [ticker, alpha_score, valid_factors_count]

        Example:
            from modules.factors import CategoryWeightCombiner

            combiner = CategoryWeightCombiner({
                'MOMENTUM': 0.30,
                'VALUE': 0.25,
                'QUALITY': 0.25,
                'LOW_VOLATILITY': 0.15,
                'SIZE': 0.05
            })

            df = calculator.batch_calculate_composite(['005930', '000660'], combiner)
            # Result:
            #    ticker  alpha_score  valid_factors_count
            # 0  005930        67.8                    20
            # 1  000660        72.5                    22
        """
        results = []

        for ticker in tickers:
            # Calculate all scores
            factor_scores = self.calculate_all_scores(ticker, region)

            # Filter valid scores
            valid_scores = {
                name: score
                for name, score in factor_scores.items()
                if score is not None
            }

            # Calculate composite
            if valid_scores:
                alpha_score = combiner.combine(valid_scores)
            else:
                alpha_score = 50.0  # Neutral

            results.append({
                'ticker': ticker,
                'alpha_score': alpha_score,
                'valid_factors_count': len(valid_scores)
            })

        df = pd.DataFrame(results)

        logger.info(f"Batch calculated composite scores for {len(tickers)} tickers")
        return df
