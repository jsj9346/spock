#!/usr/bin/env python3
"""
Example: Using Value Factors for Stock Selection

Demonstrates how to use Value factors (P/E, P/B, EV/EBITDA, Dividend Yield)
to identify undervalued stocks in the Korean market.

Prerequisites:
- ticker_fundamentals table populated with fundamental data
- Use fundamental_data_collector.py to collect data from DART API

Usage:
    python3 examples/example_value_factors_usage.py

Author: Spock Quant Platform - Phase 2
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import sqlite3
from modules.factors import (
    PERatioFactor,
    PBRatioFactor,
    EVToEBITDAFactor,
    DividendYieldFactor
)


def calculate_value_scores_for_universe(db_path: str = "./data/spock_local.db"):
    """
    Calculate value factor scores for all stocks in the universe

    Returns:
        DataFrame with ticker and all value factor scores
    """
    # Initialize factors
    pe_factor = PERatioFactor(db_path=db_path)
    pb_factor = PBRatioFactor(db_path=db_path)
    ev_factor = EVToEBITDAFactor(db_path=db_path)
    div_factor = DividendYieldFactor(db_path=db_path)

    # Get all tickers with fundamental data
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT ticker
        FROM ticker_fundamentals
        WHERE per IS NOT NULL OR pbr IS NOT NULL OR ev_ebitda IS NOT NULL OR dividend_yield IS NOT NULL
        ORDER BY ticker
    """)

    tickers = [row[0] for row in cursor.fetchall()]
    conn.close()

    print(f"📊 Analyzing {len(tickers)} stocks with fundamental data...")

    # Data availability warning
    if len(tickers) < 10:
        print(f"⚠️  WARNING: Only {len(tickers)} tickers have fundamental data")
        print(f"   Consider running: python3 modules/fundamental_data_collector.py --region KR")
        print()

    # Calculate factors for each ticker
    results = []

    for ticker in tickers:
        pe_result = pe_factor.calculate(None, ticker)
        pb_result = pb_factor.calculate(None, ticker)
        ev_result = ev_factor.calculate(None, ticker)
        div_result = div_factor.calculate(None, ticker)

        row = {
            'ticker': ticker,
            'pe_score': pe_result.raw_value if pe_result else None,
            'pe_ratio': pe_result.metadata['pe_ratio'] if pe_result else None,
            'pb_score': pb_result.raw_value if pb_result else None,
            'pb_ratio': pb_result.metadata['pb_ratio'] if pb_result else None,
            'ev_ebitda_score': ev_result.raw_value if ev_result else None,
            'ev_ebitda': ev_result.metadata['ev_ebitda'] if ev_result else None,
            'div_yield_score': div_result.raw_value if div_result else None,
            'div_yield': div_result.metadata['dividend_yield'] if div_result else None,
        }

        results.append(row)

    df = pd.DataFrame(results)

    # Calculate composite value score (average of z-scores across factors)
    # Note: In production, you'd calculate z-scores across the universe
    # Here we use simple average of negated ratios for demonstration

    # Normalize each factor (simple min-max scaling for demo)
    # Only normalize if there's sufficient variance (>1 unique values)
    normalized_cols = []

    for col in ['pe_score', 'pb_score', 'ev_ebitda_score']:
        if df[col].notna().sum() > 1 and df[col].nunique() > 1:
            df[f'{col}_norm'] = (df[col] - df[col].min()) / (df[col].max() - df[col].min())
            normalized_cols.append(f'{col}_norm')

    # Dividend yield is already positive (higher = better), so normalize directly
    if df['div_yield_score'].notna().sum() > 1 and df['div_yield_score'].nunique() > 1:
        df['div_yield_score_norm'] = (df['div_yield_score'] - df['div_yield_score'].min()) / (
            df['div_yield_score'].max() - df['div_yield_score'].min()
        )
        normalized_cols.append('div_yield_score_norm')

    # Composite value score (equal weight) - use only available normalized columns
    if normalized_cols:
        df['composite_value_score'] = df[normalized_cols].mean(axis=1, skipna=True)
    else:
        # Fallback: use raw scores if normalization not possible
        raw_cols = [col for col in ['pe_score', 'pb_score', 'ev_ebitda_score', 'div_yield_score']
                    if col in df.columns and df[col].notna().sum() > 0]
        if raw_cols:
            df['composite_value_score'] = df[raw_cols].mean(axis=1, skipna=True)
        else:
            df['composite_value_score'] = 0.0

    return df


def find_value_stocks(df: pd.DataFrame, top_n: int = 10):
    """
    Find top value stocks based on composite score

    Args:
        df: DataFrame from calculate_value_scores_for_universe()
        top_n: Number of top stocks to return

    Returns:
        DataFrame with top value stocks
    """
    # Sort by composite value score (higher = better value)
    value_stocks = df.sort_values('composite_value_score', ascending=False).head(top_n)

    return value_stocks[[
        'ticker',
        'pe_ratio',
        'pb_ratio',
        'ev_ebitda',
        'div_yield',
        'composite_value_score'
    ]]


def categorize_stocks_by_style(df: pd.DataFrame):
    """
    Categorize stocks by investment style

    Returns:
        Dict of DataFrames by category
    """
    categories = {}

    # Deep Value: Low P/E (<10) AND Low P/B (<1.5)
    categories['deep_value'] = df[
        (df['pe_ratio'] < 10) &
        (df['pb_ratio'] < 1.5)
    ].sort_values('pe_ratio')

    # High Dividend: Dividend yield > 3%
    categories['high_dividend'] = df[
        df['div_yield'] > 3.0
    ].sort_values('div_yield', ascending=False)

    # Quality Value: Low P/E (<15) AND Low EV/EBITDA (<12)
    categories['quality_value'] = df[
        (df['pe_ratio'] < 15) &
        (df['ev_ebitda'] < 12)
    ].sort_values('ev_ebitda')

    # Growth: High P/E (>25) AND High P/B (>3)
    categories['growth'] = df[
        (df['pe_ratio'] > 25) &
        (df['pb_ratio'] > 3)
    ].sort_values('pe_ratio', ascending=False)

    return categories


def main():
    """Main demonstration"""
    print("=" * 80)
    print("Value Factor Analysis - Stock Selection Example")
    print("=" * 80)

    # Calculate value scores
    df = calculate_value_scores_for_universe()

    print(f"\n✅ Analyzed {len(df)} stocks")
    print(f"   - P/E available: {df['pe_ratio'].notna().sum()}")
    print(f"   - P/B available: {df['pb_ratio'].notna().sum()}")
    print(f"   - EV/EBITDA available: {df['ev_ebitda'].notna().sum()}")
    print(f"   - Dividend Yield available: {df['div_yield'].notna().sum()}")

    # Warn about insufficient data
    if df['pe_ratio'].notna().sum() < 10:
        print(f"\n⚠️  Insufficient fundamental data for meaningful analysis")
        print(f"   Need ≥10 tickers with each factor for statistical validity")
        print(f"   Current coverage is too sparse for production use")
        print()

    # Find top value stocks
    print("\n" + "=" * 80)
    print("🏆 Top 10 Value Stocks (Based on Composite Score)")
    print("=" * 80)

    top_value = find_value_stocks(df, top_n=10)
    print(top_value.to_string(index=False))

    # Categorize by style
    print("\n" + "=" * 80)
    print("📊 Stock Categories by Investment Style")
    print("=" * 80)

    categories = categorize_stocks_by_style(df)

    for category_name, category_df in categories.items():
        print(f"\n{category_name.upper().replace('_', ' ')} ({len(category_df)} stocks):")
        if len(category_df) > 0:
            print(category_df[['ticker', 'pe_ratio', 'pb_ratio', 'ev_ebitda', 'div_yield']].head(5).to_string(index=False))
        else:
            print("  No stocks in this category")

    # Summary statistics
    print("\n" + "=" * 80)
    print("📈 Summary Statistics")
    print("=" * 80)

    summary = df[['pe_ratio', 'pb_ratio', 'ev_ebitda', 'div_yield']].describe()
    print(summary.to_string())

    print("\n" + "=" * 80)
    print("✅ Analysis Complete")
    print("=" * 80)


if __name__ == '__main__':
    main()
