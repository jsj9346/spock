#!/usr/bin/env python3
"""
FX Valuation Analyzer - Phase 2-A

Purpose:
    Analyze FX data to generate investment attractiveness scores for currencies.

Functionality:
    1. Multi-period returns calculation (1m, 3m, 6m, 12m)
    2. Trend score calculation (moving average convergence)
    3. Volatility analysis (60-day rolling)
    4. Momentum score calculation (rate of change)
    5. Attractiveness score (composite 0-100 scale)
    6. Confidence score (data quality + historical depth)

Database Tables:
    - Source: fx_valuation_signals (currency, date, usd_rate)
    - Update: Same table (return_*, trend_score, volatility_60d, momentum_score, attractiveness_score, confidence)

Usage:
    # Analyze all currencies for latest date
    analyzer = FXValuationAnalyzer()
    analyzer.analyze_all_currencies()

    # Analyze specific currency
    analyzer.analyze_currency('USD', date='2025-10-24')

    # Batch analysis for date range
    analyzer.analyze_date_range(start_date='2024-01-01', end_date='2025-10-24')

Author: Spock Quant Platform
Created: 2025-10-24
"""

import os
import sys
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from decimal import Decimal
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_postgres import PostgresDatabaseManager

# Initialize logger
logger = logging.getLogger(__name__)


class FXValuationAnalyzer:
    """
    FX Valuation Analyzer for currency investment attractiveness scoring.

    Scoring Components:
    1. Multi-Period Returns (40% weight):
       - 1-month return: 10%
       - 3-month return: 10%
       - 6-month return: 10%
       - 12-month return: 10%

    2. Trend Score (25% weight):
       - MA(20) vs MA(60) convergence
       - Slope of MA(20)
       - Price position vs MA(60)

    3. Momentum Score (20% weight):
       - Rate of change (30-day)
       - RSI-style momentum
       - Acceleration

    4. Volatility Penalty (15% weight):
       - Lower volatility = higher score
       - Normalized 60-day volatility
       - Risk-adjusted returns

    Confidence Score (0-100):
    - Data completeness (50%): % of days with data in last 365 days
    - Historical depth (30%): Days of available history
    - Data quality (20%): Quality score from collector
    """

    # Supported currencies
    SUPPORTED_CURRENCIES = ['USD', 'HKD', 'CNY', 'JPY', 'VND']

    # Period definitions (in days)
    PERIODS = {
        '1m': 30,
        '3m': 90,
        '6m': 180,
        '12m': 365
    }

    # Scoring weights
    WEIGHTS = {
        'returns': 0.40,      # Multi-period returns
        'trend': 0.25,        # Trend analysis
        'momentum': 0.20,     # Momentum indicators
        'volatility': 0.15    # Volatility penalty
    }

    def __init__(self, db_manager: Optional[PostgresDatabaseManager] = None):
        """
        Initialize FX Valuation Analyzer.

        Args:
            db_manager: PostgreSQL database manager (creates new if None)
        """
        self.db = db_manager if db_manager else PostgresDatabaseManager()
        logger.info("FXValuationAnalyzer initialized")

    # ================================================================
    # Public API Methods
    # ================================================================

    def analyze_all_currencies(self, analysis_date: Optional[date] = None) -> Dict[str, bool]:
        """
        Analyze all supported currencies for a given date.

        Args:
            analysis_date: Date to analyze (default: today)

        Returns:
            Dict mapping currency to success status
            Example: {'USD': True, 'HKD': True, 'CNY': False}
        """
        if analysis_date is None:
            analysis_date = date.today()

        logger.info(f"Analyzing all currencies for {analysis_date}")

        results = {}
        for currency in self.SUPPORTED_CURRENCIES:
            try:
                success = self.analyze_currency(currency, analysis_date)
                results[currency] = success
            except Exception as e:
                logger.error(f"Failed to analyze {currency}: {e}")
                results[currency] = False

        success_count = sum(1 for v in results.values() if v)
        logger.info(f"Analysis complete: {success_count}/{len(results)} currencies successful")

        return results

    def analyze_currency(self, currency: str, analysis_date: Optional[date] = None) -> bool:
        """
        Analyze single currency and update database with valuation metrics.

        Args:
            currency: Currency code (USD, HKD, CNY, JPY, VND)
            analysis_date: Date to analyze (default: today)

        Returns:
            True if analysis successful and database updated
        """
        if analysis_date is None:
            analysis_date = date.today()

        if currency not in self.SUPPORTED_CURRENCIES:
            logger.error(f"Unsupported currency: {currency}")
            return False

        logger.info(f"Analyzing {currency} for {analysis_date}")

        try:
            # Step 1: Fetch historical data
            historical_data = self._fetch_historical_data(currency, analysis_date)

            if historical_data.empty:
                logger.warning(f"No historical data for {currency} on {analysis_date}")
                return False

            # Step 2: Calculate multi-period returns
            returns = self._calculate_multi_period_returns(historical_data, analysis_date)

            # Step 3: Calculate trend score
            trend_score = self._calculate_trend_score(historical_data, analysis_date)

            # Step 4: Calculate volatility
            volatility = self._calculate_volatility(historical_data, analysis_date, window=60)

            # Step 5: Calculate momentum score
            momentum_acceleration = self._calculate_momentum_score(historical_data, analysis_date)

            # Step 6: Calculate attractiveness score (composite)
            attractiveness_score = self._calculate_attractiveness_score(
                returns, trend_score, momentum_acceleration, volatility
            )

            # Step 7: Calculate confidence score (0-1 scale)
            confidence = self._calculate_confidence_score(historical_data, analysis_date)

            # Step 8: Update database
            success = self._update_valuation_metrics(
                currency=currency,
                analysis_date=analysis_date,
                return_1m=returns.get('1m'),
                return_3m=returns.get('3m'),
                return_6m=returns.get('6m'),
                return_12m=returns.get('12m'),
                trend_score=trend_score,
                volatility=volatility,
                momentum_acceleration=momentum_acceleration,
                attractiveness_score=attractiveness_score,
                confidence=confidence
            )

            if success:
                attr_str = f"{attractiveness_score:.2f}" if attractiveness_score is not None else "N/A"
                conf_str = f"{confidence:.4f}" if confidence is not None else "N/A"
                logger.info(f"{currency} analysis complete: attractiveness={attr_str}, confidence={conf_str}")

            return success

        except Exception as e:
            logger.error(f"Error analyzing {currency}: {e}", exc_info=True)
            return False

    def analyze_date_range(
        self,
        start_date: date,
        end_date: date,
        currencies: Optional[List[str]] = None
    ) -> Dict[str, int]:
        """
        Analyze currencies over a date range (batch processing).

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            currencies: List of currencies (default: all supported)

        Returns:
            Dict mapping currency to number of successful days
        """
        if currencies is None:
            currencies = self.SUPPORTED_CURRENCIES

        logger.info(f"Batch analysis: {start_date} to {end_date} for {len(currencies)} currencies")

        results = {currency: 0 for currency in currencies}

        current_date = start_date
        while current_date <= end_date:
            for currency in currencies:
                try:
                    success = self.analyze_currency(currency, current_date)
                    if success:
                        results[currency] += 1
                except Exception as e:
                    logger.error(f"Error analyzing {currency} on {current_date}: {e}")

            current_date += timedelta(days=1)

        logger.info(f"Batch analysis complete: {results}")
        return results

    # ================================================================
    # Data Retrieval Methods
    # ================================================================

    def _fetch_historical_data(
        self,
        currency: str,
        end_date: date,
        lookback_days: int = 400
    ) -> pd.DataFrame:
        """
        Fetch historical FX data from database.

        Args:
            currency: Currency code
            end_date: End date for data
            lookback_days: Days of history to fetch (default: 400 for 12m + buffer)

        Returns:
            DataFrame with columns: date, usd_rate, data_quality
        """
        start_date = end_date - timedelta(days=lookback_days)

        query = """
            SELECT date, usd_rate, data_quality
            FROM fx_valuation_signals
            WHERE currency = %s
              AND date BETWEEN %s AND %s
            ORDER BY date ASC
        """

        results = self.db.execute_query(query, (currency, start_date, end_date))

        if not results:
            return pd.DataFrame()

        # Handle different result formats (tuple/dict)
        if isinstance(results[0], dict):
            df = pd.DataFrame(results)
        else:
            df = pd.DataFrame(results, columns=['date', 'usd_rate', 'data_quality'])

        # Convert usd_rate to float
        df['usd_rate'] = df['usd_rate'].astype(float)

        return df

    # ================================================================
    # Returns Calculation
    # ================================================================

    def _calculate_multi_period_returns(
        self,
        df: pd.DataFrame,
        analysis_date: date
    ) -> Dict[str, Optional[float]]:
        """
        Calculate returns over multiple periods (1m, 3m, 6m, 12m).

        Formula: return = (current_rate - past_rate) / past_rate

        Args:
            df: Historical data DataFrame
            analysis_date: Current analysis date

        Returns:
            Dict with keys: '1m', '3m', '6m', '12m'
            Values: return as decimal (e.g., 0.05 for 5% gain)
        """
        returns = {}

        # Get current rate
        current_row = df[df['date'] == analysis_date]
        if current_row.empty:
            logger.warning(f"No data for {analysis_date}")
            return {period: None for period in self.PERIODS.keys()}

        current_rate = current_row.iloc[0]['usd_rate']

        # Calculate returns for each period
        for period_name, days in self.PERIODS.items():
            past_date = analysis_date - timedelta(days=days)

            # Find closest available date (allow ±5 days tolerance)
            past_row = df[
                (df['date'] >= past_date - timedelta(days=5)) &
                (df['date'] <= past_date + timedelta(days=5))
            ].head(1)

            if past_row.empty:
                logger.debug(f"No data for {period_name} period ({past_date})")
                returns[period_name] = None
            else:
                past_rate = past_row.iloc[0]['usd_rate']
                period_return = (current_rate - past_rate) / past_rate
                returns[period_name] = period_return

        return returns

    # ================================================================
    # Trend Analysis
    # ================================================================

    def _calculate_trend_score(self, df: pd.DataFrame, analysis_date: date) -> Optional[float]:
        """
        Calculate trend score (0-100 scale).

        Components:
        1. MA Convergence (40%): MA(20) vs MA(60) position
        2. MA Slope (30%): Slope of MA(20)
        3. Price Position (30%): Current price vs MA(60)

        Args:
            df: Historical data DataFrame
            analysis_date: Current analysis date

        Returns:
            Trend score (0-100), or None if insufficient data
        """
        try:
            # Calculate moving averages
            df = df.copy()
            df['ma_20'] = df['usd_rate'].rolling(window=20, min_periods=15).mean()
            df['ma_60'] = df['usd_rate'].rolling(window=60, min_periods=45).mean()

            # Get current values
            current_row = df[df['date'] == analysis_date]
            if current_row.empty:
                return None

            current_rate = current_row.iloc[0]['usd_rate']
            ma_20 = current_row.iloc[0]['ma_20']
            ma_60 = current_row.iloc[0]['ma_60']

            if pd.isna(ma_20) or pd.isna(ma_60):
                logger.debug("Insufficient data for moving averages")
                return None

            # Component 1: MA Convergence (40%)
            # Positive when MA(20) > MA(60) (uptrend)
            ma_convergence = ((ma_20 - ma_60) / ma_60) * 100
            ma_convergence_score = min(100, max(0, 50 + ma_convergence * 10))

            # Component 2: MA Slope (30%)
            # Calculate slope of MA(20) over last 10 days
            ma_20_history = df[df['date'] <= analysis_date].tail(10)['ma_20']
            if len(ma_20_history) >= 2:
                ma_slope = (ma_20_history.iloc[-1] - ma_20_history.iloc[0]) / ma_20_history.iloc[0]
                ma_slope_score = min(100, max(0, 50 + ma_slope * 1000))
            else:
                ma_slope_score = 50

            # Component 3: Price Position (30%)
            # Positive when price > MA(60)
            price_position = ((current_rate - ma_60) / ma_60) * 100
            price_position_score = min(100, max(0, 50 + price_position * 10))

            # Weighted combination
            trend_score = (
                ma_convergence_score * 0.40 +
                ma_slope_score * 0.30 +
                price_position_score * 0.30
            )

            return round(trend_score, 2)

        except Exception as e:
            logger.error(f"Error calculating trend score: {e}")
            return None

    # ================================================================
    # Volatility Analysis
    # ================================================================

    def _calculate_volatility(
        self,
        df: pd.DataFrame,
        analysis_date: date,
        window: int = 60
    ) -> Optional[float]:
        """
        Calculate historical volatility (annualized standard deviation).

        Formula: volatility = std(daily_returns) * sqrt(252)

        Args:
            df: Historical data DataFrame
            analysis_date: Current analysis date
            window: Rolling window size (default: 60 days)

        Returns:
            Annualized volatility as decimal (e.g., 0.15 for 15% volatility)
        """
        try:
            # Calculate daily returns
            df = df.copy()
            df['daily_return'] = df['usd_rate'].pct_change()

            # Get data up to analysis date
            historical_df = df[df['date'] <= analysis_date].tail(window)

            if len(historical_df) < window * 0.75:  # Require 75% of data
                logger.debug(f"Insufficient data for volatility calculation ({len(historical_df)}/{window} days)")
                return None

            # Calculate standard deviation
            daily_std = historical_df['daily_return'].std()

            # Annualize (252 trading days)
            annualized_volatility = daily_std * np.sqrt(252)

            return round(annualized_volatility, 6)

        except Exception as e:
            logger.error(f"Error calculating volatility: {e}")
            return None

    # ================================================================
    # Momentum Analysis
    # ================================================================

    def _calculate_momentum_score(self, df: pd.DataFrame, analysis_date: date) -> Optional[float]:
        """
        Calculate momentum score (0-100 scale).

        Components:
        1. Rate of Change (50%): 30-day ROC
        2. RSI-Style Momentum (30%): Up days vs down days
        3. Acceleration (20%): Change in ROC

        Args:
            df: Historical data DataFrame
            analysis_date: Current analysis date

        Returns:
            Momentum score (0-100), or None if insufficient data
        """
        try:
            # Get recent data
            recent_df = df[df['date'] <= analysis_date].tail(60)

            if len(recent_df) < 30:
                logger.debug("Insufficient data for momentum calculation")
                return None

            # Component 1: Rate of Change (50%)
            current_rate = recent_df.iloc[-1]['usd_rate']
            past_rate_30d = recent_df.iloc[-30]['usd_rate'] if len(recent_df) >= 30 else recent_df.iloc[0]['usd_rate']

            roc_30d = ((current_rate - past_rate_30d) / past_rate_30d) * 100
            roc_score = min(100, max(0, 50 + roc_30d * 5))

            # Component 2: RSI-Style Momentum (30%)
            recent_df = recent_df.copy()
            recent_df['daily_change'] = recent_df['usd_rate'].diff()

            up_days = (recent_df['daily_change'] > 0).sum()
            down_days = (recent_df['daily_change'] < 0).sum()

            if up_days + down_days > 0:
                rsi_style = (up_days / (up_days + down_days)) * 100
            else:
                rsi_style = 50

            # Component 3: Acceleration (20%)
            if len(recent_df) >= 45:
                past_rate_45d = recent_df.iloc[-45]['usd_rate']
                roc_45d = ((past_rate_30d - past_rate_45d) / past_rate_45d) * 100
                acceleration = roc_30d - roc_45d
                acceleration_score = min(100, max(0, 50 + acceleration * 10))
            else:
                acceleration_score = 50

            # Weighted combination
            momentum_score = (
                roc_score * 0.50 +
                rsi_style * 0.30 +
                acceleration_score * 0.20
            )

            return round(momentum_score, 2)

        except Exception as e:
            logger.error(f"Error calculating momentum score: {e}")
            return None

    # ================================================================
    # Composite Scoring
    # ================================================================

    def _calculate_attractiveness_score(
        self,
        returns: Dict[str, Optional[float]],
        trend_score: Optional[float],
        momentum_score: Optional[float],
        volatility: Optional[float]
    ) -> Optional[float]:
        """
        Calculate composite attractiveness score (0-100 scale).

        Weights:
        - Returns (40%): Average of multi-period returns
        - Trend (25%): Trend score
        - Momentum (20%): Momentum score
        - Volatility (15%): Inverse volatility (lower vol = higher score)

        Args:
            returns: Dict of period returns
            trend_score: Trend score (0-100)
            momentum_score: Momentum score (0-100)
            volatility: Annualized volatility (0.0-1.0)

        Returns:
            Attractiveness score (0-100), or None if insufficient data
        """
        try:
            # Component 1: Returns Score (40%)
            valid_returns = [r for r in returns.values() if r is not None]

            if not valid_returns:
                logger.debug("No valid returns for attractiveness score")
                return None

            avg_return = np.mean(valid_returns)
            # Normalize: 0% return = 50, ±10% return = 0/100
            returns_score = min(100, max(0, 50 + avg_return * 500))

            # Component 2: Trend Score (25%)
            if trend_score is None:
                trend_score = 50  # Neutral if unavailable

            # Component 3: Momentum Score (20%)
            if momentum_score is None:
                momentum_score = 50  # Neutral if unavailable

            # Component 4: Volatility Score (15%)
            # Lower volatility = higher score
            if volatility is not None:
                # Normalize: 10% vol = 50, 0% vol = 100, 20% vol = 0
                volatility_score = min(100, max(0, 100 - volatility * 500))
            else:
                volatility_score = 50  # Neutral if unavailable

            # Weighted combination
            attractiveness_score = (
                returns_score * self.WEIGHTS['returns'] +
                trend_score * self.WEIGHTS['trend'] +
                momentum_score * self.WEIGHTS['momentum'] +
                volatility_score * self.WEIGHTS['volatility']
            )

            return round(attractiveness_score, 2)

        except Exception as e:
            logger.error(f"Error calculating attractiveness score: {e}")
            return None

    # ================================================================
    # Confidence Scoring
    # ================================================================

    def _calculate_confidence_score(self, df: pd.DataFrame, analysis_date: date) -> Optional[float]:
        """
        Calculate confidence score (0.0-1.0 scale).

        Components:
        1. Data Completeness (50%): % of days with data in last 365 days
        2. Historical Depth (30%): Days of available history
        3. Data Quality (20%): Average quality score from collector

        Args:
            df: Historical data DataFrame
            analysis_date: Current analysis date

        Returns:
            Confidence score (0.0-1.0)
        """
        try:
            # Component 1: Data Completeness (50%)
            last_365_days_df = df[df['date'] >= analysis_date - timedelta(days=365)]
            days_with_data = len(last_365_days_df)
            completeness_pct = min(100, (days_with_data / 365) * 100)

            # Component 2: Historical Depth (30%)
            total_days = len(df)
            # Normalize: 365 days = 100, 180 days = 50, <90 days = 0
            if total_days >= 365:
                depth_score = 100
            elif total_days >= 180:
                depth_score = 50 + ((total_days - 180) / 185) * 50
            elif total_days >= 90:
                depth_score = (total_days / 180) * 50
            else:
                depth_score = (total_days / 90) * 25

            # Component 3: Data Quality (20%)
            quality_map = {'GOOD': 100, 'PARTIAL': 50, 'STALE': 25, 'MISSING': 0}
            quality_scores = df['data_quality'].map(quality_map).fillna(0)
            avg_quality = quality_scores.mean()

            # Weighted combination (0-100 scale)
            confidence_score_100 = (
                completeness_pct * 0.50 +
                depth_score * 0.30 +
                avg_quality * 0.20
            )

            # Convert to 0-1 scale
            confidence_score = confidence_score_100 / 100.0

            return round(confidence_score, 4)

        except Exception as e:
            logger.error(f"Error calculating confidence score: {e}")
            return 0.0

    # ================================================================
    # Database Update
    # ================================================================

    def _update_valuation_metrics(
        self,
        currency: str,
        analysis_date: date,
        return_1m: Optional[float],
        return_3m: Optional[float],
        return_6m: Optional[float],
        return_12m: Optional[float],
        trend_score: Optional[float],
        volatility: Optional[float],
        momentum_acceleration: Optional[float],
        attractiveness_score: Optional[float],
        confidence: Optional[float]
    ) -> bool:
        """
        Update fx_valuation_signals table with calculated metrics.

        Args:
            currency: Currency code
            analysis_date: Date of analysis
            return_1m: 1-month return
            return_3m: 3-month return
            return_6m: 6-month return
            return_12m: 12-month return
            trend_score: Trend score (0-100)
            volatility: 60-day volatility
            momentum_acceleration: Momentum score (0-100)
            attractiveness_score: Attractiveness score (0-100)
            confidence: Confidence score (0.0-1.0)

        Returns:
            True if update successful
        """
        try:
            # Convert Decimal if needed
            def to_decimal(value):
                if value is None:
                    return None
                return Decimal(str(value))

            update_sql = """
                UPDATE fx_valuation_signals
                SET return_1m = %s,
                    return_3m = %s,
                    return_6m = %s,
                    return_12m = %s,
                    trend_score = %s,
                    volatility = %s,
                    momentum_acceleration = %s,
                    attractiveness_score = %s,
                    confidence = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE currency = %s
                  AND date = %s
            """

            params = (
                to_decimal(return_1m),
                to_decimal(return_3m),
                to_decimal(return_6m),
                to_decimal(return_12m),
                to_decimal(trend_score),
                to_decimal(volatility),
                to_decimal(momentum_acceleration),
                to_decimal(attractiveness_score),
                to_decimal(confidence),
                currency,
                analysis_date
            )

            success = self.db.execute_update(update_sql, params)

            if success:
                logger.debug(f"Updated valuation metrics for {currency} on {analysis_date}")
            else:
                logger.error(f"Failed to update valuation metrics for {currency} on {analysis_date}")

            return success

        except Exception as e:
            logger.error(f"Error updating valuation metrics: {e}", exc_info=True)
            return False


# ================================================================
# CLI Interface
# ================================================================

def main():
    """CLI entry point for FX Valuation Analyzer"""
    import argparse

    parser = argparse.ArgumentParser(
        description='FX Valuation Analyzer - Calculate currency investment attractiveness scores'
    )

    parser.add_argument(
        '--currencies',
        type=str,
        default='USD,HKD,CNY,JPY,VND',
        help='Comma-separated currency codes (default: all supported)'
    )

    parser.add_argument(
        '--date',
        type=str,
        help='Analysis date in YYYY-MM-DD format (default: today)'
    )

    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date for batch analysis (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--end-date',
        type=str,
        help='End date for batch analysis (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Calculate scores but do not update database'
    )

    args = parser.parse_args()

    # Parse currencies
    currencies = [c.strip().upper() for c in args.currencies.split(',')]

    # Initialize analyzer
    analyzer = FXValuationAnalyzer()

    # Batch analysis mode
    if args.start_date and args.end_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()

        logger.info(f"Batch analysis: {start_date} to {end_date}")
        results = analyzer.analyze_date_range(start_date, end_date, currencies)

        print("\n" + "="*60)
        print("BATCH ANALYSIS RESULTS")
        print("="*60)
        for currency, success_days in results.items():
            total_days = (end_date - start_date).days + 1
            success_rate = (success_days / total_days) * 100
            print(f"{currency}: {success_days}/{total_days} days ({success_rate:.1f}%)")
        print("="*60)

    # Single date analysis mode
    else:
        analysis_date = datetime.strptime(args.date, '%Y-%m-%d').date() if args.date else date.today()

        logger.info(f"Analyzing {len(currencies)} currencies for {analysis_date}")

        for currency in currencies:
            success = analyzer.analyze_currency(currency, analysis_date)
            status = "✓" if success else "✗"
            print(f"{status} {currency}")


if __name__ == '__main__':
    main()
