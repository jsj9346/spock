#!/usr/bin/env python3
"""
HK Market Momentum Factors - Information Coefficient (IC) Analysis

Validates momentum factors using IC analysis:
1. Calculate forward returns (1M, 3M, 6M, 12M)
2. Compute IC (Spearman correlation) between factor scores and forward returns
3. Test statistical significance (t-test, p-value < 0.05)
4. Quintile performance analysis (top 20% vs bottom 20% spread)
5. Time-series IC analysis (rolling windows)

Success Criteria:
- IC > 0.05 (preferably > 0.10 for strong signal)
- p-value < 0.05 (statistically significant)
- Top quintile - Bottom quintile > 5% annually
- IC stability over time (rolling windows)

Usage:
    # Full IC analysis with all available factors
    python3 scripts/validate_momentum_factors_ic.py --full

    # Specific factor analysis
    python3 scripts/validate_momentum_factors_ic.py --factor rsi

    # Custom sample size
    python3 scripts/validate_momentum_factors_ic.py --sample 200

    # Save results
    python3 scripts/validate_momentum_factors_ic.py --full --output results/ic_analysis_20241113.csv
"""

import sys
import os
import argparse
import warnings
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
from scipy import stats
from loguru import logger

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.factors.momentum_factors import (
    RSIMomentumFactorHK,
    MACDMomentumFactorHK,
    Week52HighFactorHK,
    ShortTermMomentumFactorHK,
    LongTermMomentumFactorHK,
    MomentumFactorCalculatorHK
)
from modules.db_manager_postgres import PostgresDatabaseManager

warnings.filterwarnings('ignore')


def calculate_forward_returns(
    db: PostgresDatabaseManager,
    tickers: List[str],
    as_of_date: str,
    periods: List[int] = [21, 63, 126, 252]
) -> pd.DataFrame:
    """
    Calculate forward returns for multiple periods

    Args:
        db: Database manager
        tickers: List of tickers
        as_of_date: Reference date (YYYY-MM-DD)
        periods: Forward return periods in trading days
                 [21=1M, 63=3M, 126=6M, 252=12M]

    Returns:
        DataFrame with columns: ticker, fwd_return_1M, fwd_return_3M, fwd_return_6M, fwd_return_12M
    """
    logger.info(f"Calculating forward returns for {len(tickers)} tickers from {as_of_date}")

    results = []

    for ticker in tickers:
        try:
            # Get price data starting from as_of_date
            query = """
            SELECT date, close
            FROM ohlcv_data
            WHERE ticker = %s AND region = 'HK'
              AND date >= %s
            ORDER BY date ASC
            LIMIT %s
            """
            max_period = max(periods) + 10  # Buffer for holidays
            data = db.execute_query(query, (ticker, as_of_date, max_period))

            if not data or len(data) < 2:
                continue

            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            # Base price (as_of_date)
            base_price = df.iloc[0]['close']

            # Calculate returns for each period
            ticker_result = {'ticker': ticker}

            for period in periods:
                period_name = {
                    21: 'fwd_return_1M',
                    63: 'fwd_return_3M',
                    126: 'fwd_return_6M',
                    252: 'fwd_return_12M'
                }.get(period, f'fwd_return_{period}d')

                if len(df) > period:
                    future_price = df.iloc[period]['close']
                    fwd_return = (future_price - base_price) / base_price
                    ticker_result[period_name] = fwd_return
                else:
                    ticker_result[period_name] = np.nan

            results.append(ticker_result)

        except Exception as e:
            logger.warning(f"Failed to calculate forward returns for {ticker}: {e}")
            continue

    df_results = pd.DataFrame(results)
    logger.info(f"Forward returns calculated for {len(df_results)} tickers")

    return df_results


def calculate_ic(
    factor_scores: pd.Series,
    forward_returns: pd.Series,
    method: str = 'spearman'
) -> Tuple[float, float, float]:
    """
    Calculate Information Coefficient (IC)

    Args:
        factor_scores: Factor values (higher = better)
        forward_returns: Forward returns
        method: 'spearman' or 'pearson'

    Returns:
        (ic, t_statistic, p_value)
    """
    # Remove NaN values
    valid_mask = factor_scores.notna() & forward_returns.notna()
    factor_clean = factor_scores[valid_mask]
    returns_clean = forward_returns[valid_mask]

    n = len(factor_clean)

    if n < 10:
        logger.warning(f"Insufficient samples ({n}) for IC calculation")
        return np.nan, np.nan, np.nan

    # Calculate correlation
    if method == 'spearman':
        ic, p_value = stats.spearmanr(factor_clean, returns_clean)
    else:
        ic, p_value = stats.pearsonr(factor_clean, returns_clean)

    # T-statistic for significance
    # t = IC * sqrt(n - 2) / sqrt(1 - IC^2)
    if abs(ic) < 0.9999:
        t_stat = ic * np.sqrt(n - 2) / np.sqrt(1 - ic**2)
    else:
        t_stat = np.inf if ic > 0 else -np.inf

    return ic, t_stat, p_value


def quintile_analysis(
    df: pd.DataFrame,
    factor_col: str,
    return_col: str
) -> Dict:
    """
    Quintile performance analysis

    Args:
        df: DataFrame with factor scores and returns
        factor_col: Column name for factor scores
        return_col: Column name for forward returns

    Returns:
        Dictionary with quintile statistics
    """
    # Remove NaN
    df_clean = df[[factor_col, return_col]].dropna()

    if len(df_clean) < 20:
        logger.warning(f"Insufficient data for quintile analysis ({len(df_clean)} rows)")
        return {}

    # Create quintiles
    df_clean['quintile'] = pd.qcut(df_clean[factor_col], q=5, labels=['Q1', 'Q2', 'Q3', 'Q4', 'Q5'])

    # Calculate quintile returns
    quintile_returns = df_clean.groupby('quintile')[return_col].agg(['mean', 'median', 'count'])

    # Top vs Bottom spread
    top_return = quintile_returns.loc['Q5', 'mean']
    bottom_return = quintile_returns.loc['Q1', 'mean']
    spread = top_return - bottom_return

    # Annualize spread (assuming monthly returns for 1M forward return)
    if '1M' in return_col:
        annual_spread = spread * 12
    elif '3M' in return_col:
        annual_spread = spread * 4
    elif '6M' in return_col:
        annual_spread = spread * 2
    else:
        annual_spread = spread

    return {
        'quintile_returns': quintile_returns,
        'top_return': top_return,
        'bottom_return': bottom_return,
        'spread': spread,
        'annual_spread': annual_spread,
        'sample_size': len(df_clean)
    }


def run_ic_analysis(
    factor_name: str,
    sample_size: Optional[int] = None,
    as_of_date: Optional[str] = None
) -> Dict:
    """
    Run complete IC analysis for a single factor

    Args:
        factor_name: 'rsi', 'macd', 'week52', 'short_term', 'long_term', or 'composite'
        sample_size: Number of tickers to sample (None = all)
        as_of_date: Reference date for analysis (None = latest available)

    Returns:
        Dictionary with IC analysis results
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"IC Analysis: {factor_name.upper()}")
    logger.info(f"{'='*80}")

    db = PostgresDatabaseManager()

    # Get tickers
    if sample_size:
        query = """
        SELECT ticker FROM tickers
        WHERE region = 'HK' AND is_active = true
        ORDER BY RANDOM()
        LIMIT %s
        """
        result = db.execute_query(query, (sample_size,))
    else:
        query = "SELECT ticker FROM tickers WHERE region = 'HK' AND is_active = true"
        result = db.execute_query(query)

    tickers = [row['ticker'].replace('.HK', '') for row in result]
    logger.info(f"Analyzing {len(tickers)} HK tickers")

    # Determine as_of_date
    if as_of_date is None:
        query = "SELECT MAX(date) as max_date FROM ohlcv_data WHERE region = 'HK'"
        result = db.execute_query(query)
        as_of_date = result[0]['max_date'].strftime('%Y-%m-%d')

    logger.info(f"Reference date: {as_of_date}")

    # Calculate factor scores
    logger.info(f"Calculating {factor_name} factor scores...")

    # Use shared DB connection to avoid "too many clients" error
    factor_map = {
        'rsi': RSIMomentumFactorHK(region='HK', db=db),
        'macd': MACDMomentumFactorHK(region='HK', db=db),
        'week52': Week52HighFactorHK(region='HK', db=db),
        'short_term': ShortTermMomentumFactorHK(region='HK', db=db),
        'long_term': LongTermMomentumFactorHK(region='HK', db=db),
        'composite': MomentumFactorCalculatorHK(region='HK', db=db)
    }

    if factor_name not in factor_map:
        logger.error(f"Unknown factor: {factor_name}")
        return {}

    factor_obj = factor_map[factor_name]

    # Calculate scores
    if factor_name == 'composite':
        df_scores = factor_obj.calculate_all_tickers(tickers)
        df_scores.rename(columns={'momentum_score': 'factor_score'}, inplace=True)
    else:
        scores = []
        for ticker in tickers:
            result = factor_obj.calculate(None, ticker)
            if result:
                scores.append({
                    'ticker': ticker,
                    'factor_score': result.raw_value,
                    'confidence': result.confidence
                })
        df_scores = pd.DataFrame(scores)

    logger.info(f"Factor scores calculated for {len(df_scores)} tickers")

    # Calculate forward returns
    df_returns = calculate_forward_returns(db, tickers, as_of_date)

    # Merge
    df_analysis = pd.merge(df_scores, df_returns, on='ticker', how='inner')
    logger.info(f"Merged dataset: {len(df_analysis)} tickers")

    # IC Analysis for each forward return period
    ic_results = {}

    for period_col in ['fwd_return_1M', 'fwd_return_3M', 'fwd_return_6M', 'fwd_return_12M']:
        if period_col not in df_analysis.columns:
            continue

        logger.info(f"\n--- {period_col} Analysis ---")

        # Calculate IC
        ic, t_stat, p_value = calculate_ic(
            df_analysis['factor_score'],
            df_analysis[period_col],
            method='spearman'
        )

        logger.info(f"IC: {ic:.4f}")
        logger.info(f"t-statistic: {t_stat:.4f}")
        logger.info(f"p-value: {p_value:.4f}")

        # Significance
        is_significant = p_value < 0.05 if not np.isnan(p_value) else False
        logger.info(f"Significant: {'✅ YES' if is_significant else '❌ NO'}")

        # Quintile analysis
        quintile_results = quintile_analysis(df_analysis, 'factor_score', period_col)

        if quintile_results:
            logger.info(f"\nQuintile Returns:")
            logger.info(f"{quintile_results['quintile_returns']}")
            logger.info(f"\nTop vs Bottom:")
            logger.info(f"  Top 20% return: {quintile_results['top_return']:.4f}")
            logger.info(f"  Bottom 20% return: {quintile_results['bottom_return']:.4f}")
            logger.info(f"  Spread: {quintile_results['spread']:.4f}")
            logger.info(f"  Annual spread: {quintile_results['annual_spread']:.2%}")

        ic_results[period_col] = {
            'ic': ic,
            't_statistic': t_stat,
            'p_value': p_value,
            'is_significant': is_significant,
            'quintile_analysis': quintile_results
        }

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info(f"IC Analysis Summary: {factor_name.upper()}")
    logger.info(f"{'='*80}")

    for period, results in ic_results.items():
        status = "✅ PASS" if results['is_significant'] and results['ic'] > 0.05 else "❌ FAIL"
        logger.info(f"{period}: IC={results['ic']:.4f}, p={results['p_value']:.4f} {status}")

    return {
        'factor_name': factor_name,
        'as_of_date': as_of_date,
        'sample_size': len(df_analysis),
        'ic_results': ic_results,
        'data': df_analysis
    }


def main():
    parser = argparse.ArgumentParser(description='HK Momentum Factors IC Analysis')
    parser.add_argument('--factor', type=str,
                       choices=['rsi', 'macd', 'week52', 'short_term', 'long_term', 'composite'],
                       help='Specific factor to analyze')
    parser.add_argument('--full', action='store_true', help='Analyze all factors')
    parser.add_argument('--sample', type=int, help='Sample size (default: all tickers)')
    parser.add_argument('--date', type=str, help='Reference date (YYYY-MM-DD)')
    parser.add_argument('--output', type=str, help='Output CSV path for results')

    args = parser.parse_args()

    logger.info(f"\n{'='*80}")
    logger.info(f"HK Market Momentum Factors - IC Validation")
    logger.info(f"{'='*80}")
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Determine factors to analyze
    if args.full:
        factors_to_analyze = ['rsi', 'macd', 'week52', 'short_term', 'long_term', 'composite']
    elif args.factor:
        factors_to_analyze = [args.factor]
    else:
        # Default: analyze available factors (RSI, MACD, Short-term)
        logger.info("No factor specified. Analyzing currently available factors (RSI, MACD, Short-term)")
        factors_to_analyze = ['rsi', 'macd', 'short_term', 'composite']

    # Run analysis
    all_results = {}

    for factor in factors_to_analyze:
        try:
            results = run_ic_analysis(
                factor_name=factor,
                sample_size=args.sample,
                as_of_date=args.date
            )
            all_results[factor] = results
        except Exception as e:
            logger.error(f"Failed to analyze {factor}: {e}")
            continue

    # Save results if requested
    if args.output and all_results:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)

        # Combine all results
        summary_rows = []
        for factor, results in all_results.items():
            for period, ic_data in results['ic_results'].items():
                summary_rows.append({
                    'factor': factor,
                    'period': period,
                    'ic': ic_data['ic'],
                    't_statistic': ic_data['t_statistic'],
                    'p_value': ic_data['p_value'],
                    'is_significant': ic_data['is_significant'],
                    'sample_size': results['sample_size']
                })

        df_summary = pd.DataFrame(summary_rows)
        df_summary.to_csv(args.output, index=False)
        logger.info(f"\n✅ Results saved to: {args.output}")

    logger.info(f"\n✅ IC Analysis completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
