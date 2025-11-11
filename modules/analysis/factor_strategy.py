"""
Factor Strategy - Signal Generator for Factor-Based Trading

This module provides signal generators that integrate factor scores with
backtesting engines (vectorbt + custom).

Usage:
    from modules.factors.factor_combiner import OptimizationCombiner
    from modules.analysis.factor_strategy import create_factor_signal_generator

    # Create combiner and fit
    combiner = OptimizationCombiner()
    combiner.fit(start_date='2022-01-01', end_date='2024-12-31')

    # Create signal generator
    signal_gen = create_factor_signal_generator(
        factor_combiner=combiner,
        top_n=10,
        threshold=70.0
    )

    # Use with BacktestRunner
    result = runner.run(engine='vectorbt', signal_generator=signal_gen)
"""

from typing import Callable, Tuple, Optional, Dict, List
import pandas as pd
import numpy as np
from datetime import date, timedelta
from loguru import logger

from modules.factors.factor_combiner import FactorCombinerBase


def create_factor_signal_generator(
    factor_combiner: FactorCombinerBase,
    top_n: int = 10,
    bottom_n: int = 0,
    threshold: float = 70.0,
    holding_period: int = 21,
    rebalance_freq: int = 21
) -> Callable:
    """
    Create signal generator for factor-based long/short strategy

    Strategy Logic:
    1. Calculate composite factor scores using combiner
    2. Select top N stocks (score > threshold) for long positions
    3. Optional: Select bottom N stocks for short positions
    4. Rebalance every rebalance_freq days
    5. Exit after holding_period days

    Args:
        factor_combiner: Combiner to use (Equal/Category/Optimization)
        top_n: Number of stocks to long (default: 10)
        bottom_n: Number of stocks to short (default: 0 - long only)
        threshold: Minimum score for long positions (0-100)
        holding_period: Days to hold positions (default: 21)
        rebalance_freq: Days between rebalances (default: 21)

    Returns:
        Signal generator function: (close: pd.DataFrame) -> (entries, exits)
    """

    # Internal state for tracking positions
    position_entry_dates = {}  # {ticker: entry_date}
    last_rebalance_date = None

    def signal_generator(close: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """
        Generate trading signals based on factor scores

        Args:
            close: DataFrame with close prices
                   Index: dates (DatetimeIndex)
                   Columns: tickers (str)
                   OR Series with close prices for single ticker

        Returns:
            Tuple of:
                - entries: Boolean series for entry signals (True = enter position)
                - exits: Boolean series for exit signals (True = exit position)
        """
        nonlocal position_entry_dates, last_rebalance_date

        # Handle Series input (single ticker from vectorbt)
        if isinstance(close, pd.Series):
            ticker_name = close.name if close.name else 'ticker'
            close = close.to_frame(name=ticker_name)

        # Get current date
        current_date = close.index[-1]

        # Initialize signals
        entries = pd.Series(False, index=close.columns)
        exits = pd.Series(False, index=close.columns)

        # Check if it's time to rebalance
        if last_rebalance_date is None or (current_date - last_rebalance_date).days >= rebalance_freq:
            logger.debug(f"Rebalancing on {current_date.date()}")

            # Get factor scores for all available tickers
            try:
                composite_scores = _calculate_composite_scores(
                    tickers=close.columns.tolist(),
                    as_of_date=current_date.date(),
                    factor_combiner=factor_combiner
                )
            except Exception as e:
                logger.error(f"Failed to calculate composite scores: {e}")
                return entries, exits

            # Sort tickers by composite score
            sorted_tickers = sorted(
                composite_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )

            # Select top N tickers for long positions
            long_candidates = [
                ticker for ticker, score in sorted_tickers[:top_n * 2]  # Oversample
                if score >= threshold
            ][:top_n]

            # Select bottom N tickers for short positions (if enabled)
            short_candidates = []
            if bottom_n > 0:
                short_candidates = [
                    ticker for ticker, score in sorted_tickers[-bottom_n * 2:]
                    if score <= (100 - threshold)
                ][-bottom_n:]

            # Generate entry signals
            for ticker in long_candidates + short_candidates:
                if ticker in close.columns:
                    entries[ticker] = True
                    position_entry_dates[ticker] = current_date

            last_rebalance_date = current_date

        # Check for exit signals (holding period exceeded)
        for ticker, entry_date in list(position_entry_dates.items()):
            holding_days = (current_date - entry_date).days

            if holding_days >= holding_period:
                if ticker in close.columns:
                    exits[ticker] = True
                del position_entry_dates[ticker]

        return entries, exits

    return signal_generator


def _calculate_composite_scores(
    tickers: List[str],
    as_of_date: date,
    factor_combiner: FactorCombinerBase,
    region: str = 'KR'
) -> Dict[str, float]:
    """
    Calculate composite factor scores for multiple tickers

    Args:
        tickers: List of ticker symbols
        as_of_date: Date for factor scores
        factor_combiner: Combiner to use
        region: Region filter (default: 'KR')

    Returns:
        Dictionary of {ticker: composite_score}
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor
    import os

    composite_scores = {}

    # Connect to PostgreSQL
    conn = psycopg2.connect(
        dbname="quant_platform",
        user=os.getenv("USER", "13ruce"),
        host="localhost",
        port=5432
    )

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Query factor percentiles (normalized 0-100 scores) for all tickers
            query = """
            SELECT ticker, factor_name, percentile
            FROM factor_scores
            WHERE ticker = ANY(%s)
              AND region = %s
              AND date = %s
            ORDER BY ticker, factor_name;
            """

            cur.execute(query, (tickers, region, as_of_date))
            rows = cur.fetchall()

    finally:
        conn.close()

    if not rows:
        logger.warning(f"No factor scores found for {len(tickers)} tickers on {as_of_date}")
        # Return neutral scores (50.0)
        return {ticker: 50.0 for ticker in tickers}

    # Group by ticker
    from collections import defaultdict
    ticker_scores = defaultdict(dict)

    for row in rows:
        # Use percentile (0-100 normalized) instead of raw score
        ticker_scores[row['ticker']][row['factor_name']] = float(row['percentile'])

    # Calculate composite scores using combiner
    for ticker, factor_scores in ticker_scores.items():
        composite_scores[ticker] = factor_combiner.combine(factor_scores)

    # For tickers without scores, use neutral score
    for ticker in tickers:
        if ticker not in composite_scores:
            composite_scores[ticker] = 50.0

    logger.debug(f"Calculated scores for {len(composite_scores)} tickers")

    return composite_scores


def create_single_factor_signal_generator(
    factor_name: str,
    top_n: int = 10,
    threshold: float = 70.0,
    holding_period: int = 21
) -> Callable:
    """
    Create signal generator for single-factor strategy

    Simpler version that uses only one factor (for factor analysis)

    Args:
        factor_name: Name of factor to use (e.g., 'momentum_12m')
        top_n: Number of stocks to hold
        threshold: Minimum factor score (0-100)
        holding_period: Days to hold positions

    Returns:
        Signal generator function
    """
    from modules.factors.factor_combiner import EqualWeightCombiner

    # Create single-factor combiner
    combiner = EqualWeightCombiner()

    # Override combine method to use only specified factor
    def single_factor_combine(scores: Dict[str, float]) -> float:
        return scores.get(factor_name, 50.0)

    combiner.combine = single_factor_combine

    # Use main generator with single-factor combiner
    return create_factor_signal_generator(
        factor_combiner=combiner,
        top_n=top_n,
        threshold=threshold,
        holding_period=holding_period
    )


def create_vectorbt_factor_signal_generator(
    factor_name: str,
    threshold: float = 70.0,
    region: str = 'KR'
) -> Callable:
    """
    Create vectorbt-compatible signal generator for single-factor strategy.

    Unlike the event-driven create_factor_signal_generator(), this version
    generates all signals upfront for the entire period (vectorbt batch processing).

    Strategy:
    - Buy when factor score > threshold
    - Exit when factor score < threshold

    Args:
        factor_name: Name of factor to use (e.g., '12M_Momentum')
        threshold: Minimum percentile score (0-100) for long positions
        region: Region filter (default: 'KR')

    Returns:
        Signal generator function: (close: pd.Series) -> (entries, exits)
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor
    import os

    def vectorbt_signal_generator(close: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """
        Generate trading signals for entire period.

        Args:
            close: Close price Series
                   Index: dates (DatetimeIndex)
                   Name: ticker symbol

        Returns:
            Tuple of (entries, exits) boolean Series
        """
        # Get ticker from Series name
        ticker = close.name if close.name else close.index.name

        if not ticker:
            logger.error("Cannot determine ticker from close price Series")
            return pd.Series(False, index=close.index), pd.Series(False, index=close.index)

        # Query all factor scores for this ticker and period
        start_date = close.index[0].date()
        end_date = close.index[-1].date()

        conn = psycopg2.connect(
            dbname="quant_platform",
            user=os.getenv("USER", "13ruce"),
            host="localhost",
            port=5432
        )

        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                SELECT date, percentile
                FROM factor_scores
                WHERE ticker = %s
                  AND region = %s
                  AND factor_name = %s
                  AND date >= %s
                  AND date <= %s
                ORDER BY date;
                """

                cur.execute(query, (ticker, region, factor_name, start_date, end_date))
                rows = cur.fetchall()

        finally:
            conn.close()

        if not rows:
            logger.warning(
                f"No factor scores found for {ticker} ({factor_name}) "
                f"from {start_date} to {end_date}"
            )
            return pd.Series(False, index=close.index), pd.Series(False, index=close.index)

        # Convert to DataFrame with date index
        scores_df = pd.DataFrame(rows)
        scores_df['date'] = pd.to_datetime(scores_df['date'])
        scores_df = scores_df.set_index('date')

        # Reindex to match close prices (forward fill scores for missing dates)
        scores_aligned = scores_df['percentile'].reindex(close.index, method='ffill')

        # Generate signals
        # Entry: score crosses above threshold
        # Exit: score crosses below threshold
        entries = (scores_aligned >= threshold) & (scores_aligned.shift(1) < threshold)
        exits = (scores_aligned < threshold) & (scores_aligned.shift(1) >= threshold)

        # Log signal count
        num_entries = entries.sum()
        num_exits = exits.sum()
        logger.debug(
            f"Generated {num_entries} entries, {num_exits} exits "
            f"for {ticker} ({factor_name}, threshold={threshold})"
        )

        return entries, exits

    return vectorbt_signal_generator


if __name__ == '__main__':
    """Test signal generator"""
    import sys
    sys.path.insert(0, '/Users/13ruce/spock')

    from modules.factors.factor_combiner import EqualWeightCombiner
    from datetime import datetime

    print("Testing factor signal generator...")

    # Create simple combiner
    combiner = EqualWeightCombiner()

    # Create signal generator
    signal_gen = create_factor_signal_generator(
        factor_combiner=combiner,
        top_n=5,
        threshold=60.0
    )

    # Create dummy price data
    dates = pd.date_range(start='2024-01-01', end='2024-01-10', freq='D')
    tickers = ['000020', '005930', '035420']
    close = pd.DataFrame(
        np.random.randn(len(dates), len(tickers)) * 10 + 100,
        index=dates,
        columns=tickers
    )

    # Generate signals
    entries, exits = signal_gen(close)

    print(f"\nEntry signals: {entries[entries].index.tolist()}")
    print(f"Exit signals: {exits[exits].index.tolist()}")
    print("\n✅ Signal generator test completed!")
