#!/usr/bin/env python3
"""
Multi-Factor Strategy - Phase 2 Backtesting

Validated factors from Phase 1.4:
- Max_Drawdown (IC=-0.166, p=0.0002) - Risk Avoidance
- Liquidity (IC=-0.097, p=0.0297) - Liquidity Filter
- Short_Term_Momentum (IC=0.093, p=0.0384) - Momentum

Strategy:
- Universe: Top 200 liquid KR stocks
- Rebalancing: Monthly (month-end)
- Portfolio: Long top 20, Short bottom 20
- Transaction Cost: 0.3% (one-way)

Author: Spock Quant Platform
Date: 2025-11-23
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from modules.db_manager_postgres import PostgresDatabaseManager
import logging

logger = logging.getLogger(__name__)


class MultiFactorStrategy:
    """
    Multi-Factor Long-Short Strategy

    Combines 3 validated factors with optimal weights determined by IC magnitude.
    """

    def __init__(
        self,
        db_manager: PostgresDatabaseManager,
        universe_size: int = 200,
        long_short_count: int = 20,
        rebal_freq: str = 'M',  # 'M' for month-end
        transaction_cost: float = 0.003  # 0.3%
    ):
        """
        Initialize Multi-Factor Strategy

        Args:
            db_manager: PostgreSQL database manager
            universe_size: Number of stocks in universe (default: 200)
            long_short_count: Number of stocks in long/short portfolio (default: 20)
            rebal_freq: Rebalancing frequency ('M' for monthly, default: 'M')
            transaction_cost: One-way transaction cost (default: 0.003 = 0.3%)
        """
        self.db = db_manager
        self.universe_size = universe_size
        self.long_short_count = long_short_count
        self.rebal_freq = rebal_freq
        self.transaction_cost = transaction_cost

        # Factor weights based on IC magnitude (normalized)
        # |IC|: Max_Drawdown=0.166, Liquidity=0.097, Momentum=0.093
        # Normalized: 0.166/(0.166+0.097+0.093) ≈ 0.47, 0.27, 0.26
        self.factor_weights = {
            'max_drawdown': 0.47,      # Strongest factor
            'liquidity': 0.27,
            'short_term_momentum': 0.26
        }

        logger.info(f"MultiFactorStrategy initialized: universe={universe_size}, "
                   f"long/short={long_short_count}, rebal={rebal_freq}")

    def get_universe(
        self,
        date: datetime,
        min_trading_days: int = 200
    ) -> List[str]:
        """
        Get trading universe (top N liquid stocks)

        Args:
            date: As-of date
            min_trading_days: Minimum trading days in past year (default: 200)

        Returns:
            List of tickers in universe
        """
        lookback_start = date - timedelta(days=365)

        query = """
            SELECT
                ticker,
                AVG(volume) as avg_volume,
                COUNT(*) as trading_days
            FROM ohlcv_data
            WHERE timeframe = '1d'
              AND region = 'KR'
              AND date >= %s
              AND date <= %s
            GROUP BY ticker
            HAVING COUNT(*) >= %s
            ORDER BY avg_volume DESC
            LIMIT %s
        """

        result = self.db.execute_query(
            query,
            (lookback_start.date(), date.date(), min_trading_days, self.universe_size)
        )

        tickers = [row['ticker'] for row in result]
        logger.info(f"Universe on {date.date()}: {len(tickers)} tickers")

        return tickers

    def calculate_max_drawdown_factor(
        self,
        ticker: str,
        end_date: datetime,
        lookback_days: int = 180,  # Reduced from 252 to 180
        min_days: int = 120  # Minimum required trading days
    ) -> Optional[float]:
        """
        Calculate Max Drawdown factor (lower is better)

        Args:
            ticker: Stock ticker
            end_date: Calculation end date
            lookback_days: Target lookback period in days (default: 180)
            min_days: Minimum required trading days (default: 120)

        Returns:
            Max drawdown value (negative, lower is worse)
        """
        # Use calendar days for query (weekends + holidays)
        start_date = end_date - timedelta(days=int(lookback_days * 1.5))  # ~270 calendar days for 180 trading days

        query = """
            SELECT date, close
            FROM ohlcv_data
            WHERE ticker = %s
              AND region = 'KR'
              AND timeframe = '1d'
              AND date >= %s
              AND date <= %s
            ORDER BY date ASC
        """

        result = self.db.execute_query(query, (ticker, start_date.date(), end_date.date()))

        if len(result) < min_days:
            return None

        # Use available data (up to lookback_days)
        prices = [float(row['close']) for row in result[-lookback_days:]]

        # Calculate max drawdown
        peak = prices[0]
        max_dd = 0.0

        for price in prices:
            if price > peak:
                peak = price
            dd = (price - peak) / peak
            if dd < max_dd:
                max_dd = dd

        return max_dd  # Negative value

    def calculate_liquidity_factor(
        self,
        ticker: str,
        end_date: datetime,
        lookback_days: int = 60,
        min_days: int = 30  # Minimum required trading days
    ) -> Optional[float]:
        """
        Calculate Liquidity factor (average volume)

        Args:
            ticker: Stock ticker
            end_date: Calculation end date
            lookback_days: Target lookback period in days (default: 60)
            min_days: Minimum required trading days (default: 30)

        Returns:
            Average volume (higher is better)
        """
        # Use calendar days for query
        start_date = end_date - timedelta(days=int(lookback_days * 1.5))  # ~90 calendar days

        query = """
            SELECT AVG(volume) as avg_volume, COUNT(*) as count
            FROM ohlcv_data
            WHERE ticker = %s
              AND region = 'KR'
              AND timeframe = '1d'
              AND date >= %s
              AND date <= %s
        """

        result = self.db.execute_query(query, (ticker, start_date.date(), end_date.date()))

        if not result or result[0]['count'] < min_days:
            return None

        return float(result[0]['avg_volume'])

    def calculate_momentum_factor(
        self,
        ticker: str,
        end_date: datetime,
        lookback_days: int = 21,
        min_days: int = 15  # Minimum required trading days
    ) -> Optional[float]:
        """
        Calculate Short-Term Momentum factor (21-day return)

        Args:
            ticker: Stock ticker
            end_date: Calculation end date
            lookback_days: Target lookback period in days (default: 21)
            min_days: Minimum required trading days (default: 15)

        Returns:
            21-day return (higher is better)
        """
        # Use calendar days for query
        start_date = end_date - timedelta(days=int(lookback_days * 1.5))  # ~31 calendar days

        query = """
            SELECT date, close
            FROM ohlcv_data
            WHERE ticker = %s
              AND region = 'KR'
              AND timeframe = '1d'
              AND date >= %s
              AND date <= %s
            ORDER BY date ASC
        """

        result = self.db.execute_query(query, (ticker, start_date.date(), end_date.date()))

        if len(result) < min_days:
            return None

        # Take first and last close
        start_close = float(result[0]['close'])
        end_close = float(result[-1]['close'])

        return (end_close - start_close) / start_close

    def calculate_composite_score(
        self,
        ticker: str,
        date: datetime
    ) -> Optional[float]:
        """
        Calculate composite factor score for a ticker

        Args:
            ticker: Stock ticker
            date: Calculation date

        Returns:
            Composite score (higher is better for long)
        """
        # Calculate individual factors
        max_dd = self.calculate_max_drawdown_factor(ticker, date)
        liquidity = self.calculate_liquidity_factor(ticker, date)
        momentum = self.calculate_momentum_factor(ticker, date)

        # Check if all factors are available
        if max_dd is None or liquidity is None or momentum is None:
            return None

        # Normalize factors (z-score will be done at universe level)
        # For now, just combine with weights
        # Note: Max_drawdown is negative (lower is worse), so invert it
        score = (
            -max_dd * self.factor_weights['max_drawdown'] +  # Invert: avoid high drawdown
            liquidity * self.factor_weights['liquidity'] +
            momentum * self.factor_weights['short_term_momentum']
        )

        return score

    def rank_universe(
        self,
        tickers: List[str],
        date: datetime
    ) -> pd.DataFrame:
        """
        Rank universe by composite factor score

        Args:
            tickers: List of tickers in universe
            date: Ranking date

        Returns:
            DataFrame with columns: ticker, score, rank
        """
        scores = []

        for ticker in tickers:
            score = self.calculate_composite_score(ticker, date)
            if score is not None:
                scores.append({'ticker': ticker, 'score': score})

        if not scores:
            logger.warning(f"No valid scores on {date.date()}")
            return pd.DataFrame()

        df = pd.DataFrame(scores)

        # Z-score normalization
        df['score_z'] = (df['score'] - df['score'].mean()) / df['score'].std()

        # Rank (1 = best)
        df['rank'] = df['score_z'].rank(ascending=False, method='first').astype(int)
        df = df.sort_values('rank')

        logger.info(f"Ranked {len(df)} stocks on {date.date()}")

        return df

    def generate_signals(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Generate trading signals for backtesting period

        Args:
            start_date: Backtest start date
            end_date: Backtest end date

        Returns:
            DataFrame with columns: date, ticker, signal, rank, score
            signal: 1 (long), -1 (short), 0 (neutral)
        """
        # Generate rebalancing dates (month-ends)
        rebal_dates = pd.date_range(start=start_date, end=end_date, freq='M')

        all_signals = []

        for rebal_date in rebal_dates:
            logger.info(f"\n{'='*60}")
            logger.info(f"Rebalancing on {rebal_date.date()}")
            logger.info(f"{'='*60}")

            # Get universe
            universe = self.get_universe(rebal_date)

            if not universe:
                logger.warning(f"Empty universe on {rebal_date.date()}")
                continue

            # Rank universe
            rankings = self.rank_universe(universe, rebal_date)

            if rankings.empty:
                logger.warning(f"No rankings on {rebal_date.date()}")
                continue

            # Generate signals
            # Long: Top N
            long_tickers = rankings.head(self.long_short_count)['ticker'].tolist()
            # Short: Bottom N
            short_tickers = rankings.tail(self.long_short_count)['ticker'].tolist()

            logger.info(f"Long {len(long_tickers)} tickers: {long_tickers[:5]}...")
            logger.info(f"Short {len(short_tickers)} tickers: {short_tickers[:5]}...")

            # Create signal records
            for _, row in rankings.iterrows():
                ticker = row['ticker']
                if ticker in long_tickers:
                    signal = 1
                elif ticker in short_tickers:
                    signal = -1
                else:
                    signal = 0

                all_signals.append({
                    'date': rebal_date.date(),
                    'ticker': ticker,
                    'signal': signal,
                    'rank': row['rank'],
                    'score': row['score_z']
                })

        signals_df = pd.DataFrame(all_signals)

        logger.info(f"\nGenerated {len(signals_df)} signals across {len(rebal_dates)} rebalancing dates")
        logger.info(f"Long signals: {(signals_df['signal'] == 1).sum()}")
        logger.info(f"Short signals: {(signals_df['signal'] == -1).sum()}")

        return signals_df


def main():
    """Test strategy signal generation"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    db = PostgresDatabaseManager()
    strategy = MultiFactorStrategy(db)

    # Test signal generation for 2024
    start = datetime(2024, 1, 1)
    end = datetime(2024, 11, 30)

    signals = strategy.generate_signals(start, end)

    # Save signals
    output_file = 'multi_factor_signals_2024.csv'
    signals.to_csv(output_file, index=False)
    logger.info(f"\nSignals saved to {output_file}")

    # Summary statistics
    print("\n" + "="*60)
    print("Signal Generation Summary")
    print("="*60)
    print(f"Period: {start.date()} to {end.date()}")
    print(f"Total signals: {len(signals)}")
    print(f"Rebalancing dates: {signals['date'].nunique()}")
    print(f"Long positions: {(signals['signal'] == 1).sum()}")
    print(f"Short positions: {(signals['signal'] == -1).sum()}")
    print("="*60)


if __name__ == '__main__':
    main()
