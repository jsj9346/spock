#!/usr/bin/env python3
"""
Example: Using Size Factors for Portfolio Construction

Demonstrates how to use Size factors (Market Cap, Liquidity, Free Float)
to implement size-based portfolio strategies in the Korean market.

Size Factors analyze:
- Market Cap: Company size (small-cap premium strategy)
- Liquidity: Trading volume (execution feasibility)
- Float: Free float percentage (institutional accessibility)

Strategies Demonstrated:
1. Small-Cap Strategy: Tilt towards smaller companies (size premium)
2. Liquidity-Filtered: Only trade liquid stocks (practical execution)
3. High Float Filter: Institutional-friendly stocks (low manipulation risk)

Prerequisites:
- ticker_fundamentals table with market_cap, free_float_percentage
- OHLCV data for liquidity calculation (30-day average)

Usage:
    python3 examples/example_size_factors_usage.py

Author: Spock Quant Platform - Phase 2 Complete
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import sqlite3
from modules.factors import (
    MarketCapFactor,
    LiquidityFactor,
    FloatFactor
)


def calculate_size_scores_for_universe(db_path: str = "./data/spock_local.db"):
    """
    Calculate size factor scores for all stocks in the universe

    Returns:
        DataFrame with ticker and all size factor scores
    """
    # Initialize factors
    market_cap_factor = MarketCapFactor(db_path=db_path)
    float_factor = FloatFactor(db_path=db_path)

    # Get all tickers with fundamental data
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT ticker
        FROM ticker_fundamentals
        WHERE market_cap IS NOT NULL
        ORDER BY ticker
    """)

    tickers = [row[0] for row in cursor.fetchall()]
    conn.close()

    print(f"📊 Analyzing {len(tickers)} stocks with size data...")

    # Data availability warning
    if len(tickers) < 5:
        print(f"⚠️  WARNING: Only {len(tickers)} tickers have size data")
        print(f"   Consider running data collection scripts")
        print()

    # Calculate factors for each ticker
    results = []

    for ticker in tickers:
        market_cap_result = market_cap_factor.calculate(None, ticker)
        float_result = float_factor.calculate(None, ticker)

        # Note: Liquidity factor requires OHLCV data (not implemented in this example)
        # For production use: query ohlcv_data table and calculate liquidity

        row = {
            'ticker': ticker,
            # Market Cap (raw value is negative for small-cap tilt)
            'market_cap': market_cap_result.metadata['market_cap'] if market_cap_result else None,
            'market_cap_trillion': market_cap_result.metadata['market_cap_trillion'] if market_cap_result else None,
            'size_category': market_cap_result.metadata['category'] if market_cap_result else None,
            'market_cap_score': market_cap_result.raw_value if market_cap_result else None,
            # Float
            'free_float_pct': float_result.metadata['free_float_pct'] if float_result else None,
            'float_category': float_result.metadata['category'] if float_result else None,
            'float_score': float_result.raw_value if float_result else None,
        }

        results.append(row)

    # Convert to DataFrame
    df = pd.DataFrame(results)

    return df


def apply_size_strategies(df: pd.DataFrame):
    """
    Apply various size-based investment strategies

    Strategies:
    1. Small-Cap Strategy: Top quartile by market cap score (smallest companies)
    2. Large-Cap Strategy: Bottom quartile by market cap score (largest companies)
    3. High Float Filter: Only stocks with >40% free float
    4. Small-Cap + High Float: Combine small-cap tilt with high float requirement
    """
    strategies = {}

    # Strategy 1: Small-Cap Strategy (highest market_cap_score)
    if 'market_cap_score' in df.columns:
        small_cap_threshold = df['market_cap_score'].quantile(0.75)
        strategies['small_cap'] = df[df['market_cap_score'] >= small_cap_threshold]

    # Strategy 2: Large-Cap Strategy (lowest market_cap_score)
    if 'market_cap_score' in df.columns:
        large_cap_threshold = df['market_cap_score'].quantile(0.25)
        strategies['large_cap'] = df[df['market_cap_score'] <= large_cap_threshold]

    # Strategy 3: High Float Filter (>40% free float)
    if 'free_float_pct' in df.columns:
        strategies['high_float'] = df[df['free_float_pct'] > 40]

    # Strategy 4: Small-Cap + High Float (Quality small-caps)
    if 'market_cap_score' in df.columns and 'free_float_pct' in df.columns:
        small_cap_threshold = df['market_cap_score'].quantile(0.75)
        strategies['quality_small_cap'] = df[
            (df['market_cap_score'] >= small_cap_threshold) &
            (df['free_float_pct'] > 40)
        ]

    return strategies


def display_size_analysis(df: pd.DataFrame, strategies: dict):
    """Display size analysis results in a readable format"""
    print("\n" + "="*100)
    print("📈 SIZE FACTORS ANALYSIS - MARKET CAP & LIQUIDITY")
    print("="*100)
    print()

    # Size distribution
    print("📊 SIZE CATEGORY DISTRIBUTION")
    print("-" * 100)
    if 'size_category' in df.columns:
        category_counts = df['size_category'].value_counts()
        for category, count in category_counts.items():
            percentage = (count / len(df)) * 100
            print(f"   {category:15s}: {count:3d} stocks ({percentage:5.1f}%)")
    print()

    # Top 10 by market cap
    print("🏢 TOP 10 LARGEST COMPANIES (Market Cap)")
    print("-" * 100)
    if 'market_cap_trillion' in df.columns:
        top_10 = df.nlargest(10, 'market_cap_trillion')[[
            'ticker', 'market_cap_trillion', 'size_category', 'free_float_pct'
        ]]
        print(top_10.to_string(index=False))
    print()

    # Bottom 10 by market cap (small-caps)
    print("🏪 TOP 10 SMALLEST COMPANIES (Small-Cap)")
    print("-" * 100)
    if 'market_cap_trillion' in df.columns:
        bottom_10 = df.nsmallest(10, 'market_cap_trillion')[[
            'ticker', 'market_cap_trillion', 'size_category', 'free_float_pct'
        ]]
        print(bottom_10.to_string(index=False))
    print()

    # Float distribution
    print("💎 FREE FLOAT DISTRIBUTION")
    print("-" * 100)
    if 'float_category' in df.columns:
        float_counts = df['float_category'].value_counts()
        for category, count in float_counts.items():
            percentage = (count / len(df)) * 100
            print(f"   {category:15s}: {count:3d} stocks ({percentage:5.1f}%)")
    print()

    # Strategy results
    print("🎯 SIZE-BASED STRATEGY RESULTS")
    print("-" * 100)
    for strategy_name, strategy_df in strategies.items():
        print(f"\n   Strategy: {strategy_name.upper().replace('_', ' ')}")
        print(f"   Universe: {len(strategy_df)} stocks")
        if len(strategy_df) > 0:
            avg_market_cap = strategy_df['market_cap_trillion'].mean() if 'market_cap_trillion' in strategy_df.columns else 0
            avg_float = strategy_df['free_float_pct'].mean() if 'free_float_pct' in strategy_df.columns else 0
            print(f"   Avg Market Cap: {avg_market_cap:.2f} trillion KRW")
            print(f"   Avg Free Float: {avg_float:.1f}%")

            # Top 5 stocks in strategy
            if len(strategy_df) > 0:
                print(f"\n   Top 5 stocks:")
                top_5 = strategy_df.head(5)[[
                    'ticker', 'market_cap_trillion', 'size_category', 'free_float_pct'
                ]]
                print(top_5.to_string(index=False))
    print()

    print("="*100)
    print("✅ Size Analysis Complete")
    print("="*100)


def main():
    """Main execution function"""
    print("="*100)
    print("📏 SIZE FACTORS ANALYSIS - 3 Size Metrics")
    print("="*100)
    print("Market Cap: Company size (small-cap premium)")
    print("Liquidity: Trading volume (execution feasibility)")
    print("Free Float: Institutional accessibility (low manipulation risk)")
    print("="*100)
    print()

    try:
        # Calculate size scores
        df = calculate_size_scores_for_universe()

        # Apply size strategies
        strategies = apply_size_strategies(df)

        # Display analysis
        display_size_analysis(df, strategies)

        # Save to CSV
        output_file = "size_factors_analysis.csv"
        df.to_csv(output_file, index=False)
        print(f"\n💾 Results saved to: {output_file}")
        print()

        # Usage example
        print("📝 NEXT STEPS:")
        print("   1. Small-Cap Strategy: Top quartile by size score")
        print("   2. Apply liquidity filter: Avoid illiquid small-caps")
        print("   3. High Float requirement: >40% for institutional portfolios")
        print("   4. Combine with Quality/Value factors for multi-factor portfolio")
        print("   5. Backtest strategies with modules/backtest/backtest_engine.py")
        print()

        # Academic insights
        print("📚 ACADEMIC INSIGHTS:")
        print("   • Fama-French (1993): Small-cap premium ~2-3% annually")
        print("   • But: Small-cap effect weakened since 2000")
        print("   • Korea: Small-cap premium exists but episodic")
        print("   • Liquidity risk: Small-caps have higher trading costs")
        print("   • Recommendation: Combine size with quality filters")
        print()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 TROUBLESHOOTING:")
        print("   1. Ensure ticker_fundamentals table has market_cap data")
        print("   2. Add free_float_percentage column:")
        print("      ALTER TABLE ticker_fundamentals ADD COLUMN free_float_percentage REAL;")
        print("   3. For liquidity analysis, populate OHLCV data")
        print("   4. Check database path: ./data/spock_local.db")
        print()


if __name__ == '__main__':
    main()
