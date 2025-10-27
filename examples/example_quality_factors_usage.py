#!/usr/bin/env python3
"""
Example: Using Quality Factors for Business Quality Analysis

Demonstrates how to use Quality factors (ROE, ROA, Operating Margin, Net Margin,
Current Ratio, Quick Ratio, Debt-to-Equity, Accruals Ratio, CF-to-NI Ratio)
to identify high-quality businesses in the Korean market.

Quality Factors analyze 4 dimensions:
- Profitability: ROE, ROA, Operating Margin, Net Profit Margin
- Liquidity: Current Ratio, Quick Ratio
- Leverage: Debt-to-Equity
- Earnings Quality: Accruals Ratio, CF-to-NI Ratio

Prerequisites:
- ticker_fundamentals table populated with Phase 2A columns
- Schema extended with 11 new columns (run scripts/extend_schema_for_quality_factors.py)
- Realistic test data (run scripts/populate_test_quality_data.py)

Usage:
    python3 examples/example_quality_factors_usage.py

Author: Spock Quant Platform - Phase 2A Quality Factors
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import sqlite3
from modules.factors import (
    ROEFactor,
    ROAFactor,
    OperatingMarginFactor,
    NetProfitMarginFactor,
    CurrentRatioFactor,
    QuickRatioFactor,
    DebtToEquityFactor,
    AccrualsRatioFactor,
    CFToNIRatioFactor
)


def calculate_quality_scores_for_universe(db_path: str = "./data/spock_local.db"):
    """
    Calculate quality factor scores for all stocks in the universe

    Returns:
        DataFrame with ticker and all quality factor scores
    """
    # Initialize factors
    roe_factor = ROEFactor(db_path=db_path)
    roa_factor = ROAFactor(db_path=db_path)
    op_margin_factor = OperatingMarginFactor(db_path=db_path)
    net_margin_factor = NetProfitMarginFactor(db_path=db_path)
    current_ratio_factor = CurrentRatioFactor(db_path=db_path)
    quick_ratio_factor = QuickRatioFactor(db_path=db_path)
    debt_factor = DebtToEquityFactor(db_path=db_path)
    accruals_factor = AccrualsRatioFactor(db_path=db_path)
    cf_ni_factor = CFToNIRatioFactor(db_path=db_path)

    # Get all tickers with fundamental data
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT ticker
        FROM ticker_fundamentals
        WHERE net_income IS NOT NULL OR current_assets IS NOT NULL OR operating_cash_flow IS NOT NULL
        ORDER BY ticker
    """)

    tickers = [row[0] for row in cursor.fetchall()]
    conn.close()

    print(f"📊 Analyzing {len(tickers)} stocks with quality data...")

    # Data availability warning
    if len(tickers) < 5:
        print(f"⚠️  WARNING: Only {len(tickers)} tickers have quality data")
        print(f"   Consider running: python3 scripts/populate_test_quality_data.py")
        print()

    # Calculate factors for each ticker
    results = []

    for ticker in tickers:
        roe_result = roe_factor.calculate(None, ticker)
        roa_result = roa_factor.calculate(None, ticker)
        op_margin_result = op_margin_factor.calculate(None, ticker)
        net_margin_result = net_margin_factor.calculate(None, ticker)
        current_ratio_result = current_ratio_factor.calculate(None, ticker)
        quick_ratio_result = quick_ratio_factor.calculate(None, ticker)
        debt_result = debt_factor.calculate(None, ticker)
        accruals_result = accruals_factor.calculate(None, ticker)
        cf_ni_result = cf_ni_factor.calculate(None, ticker)

        row = {
            'ticker': ticker,
            # Profitability
            'roe': roe_result.metadata['roe'] if roe_result else None,
            'roa': roa_result.metadata['roa'] if roa_result else None,
            'op_margin': op_margin_result.metadata['operating_margin'] if op_margin_result else None,
            'net_margin': net_margin_result.metadata['net_profit_margin'] if net_margin_result else None,
            # Liquidity
            'current_ratio': current_ratio_result.metadata['current_ratio'] if current_ratio_result else None,
            'quick_ratio': quick_ratio_result.metadata['quick_ratio'] if quick_ratio_result else None,
            # Leverage (negative score inverted for display)
            'debt_equity': -debt_result.raw_value if debt_result else None,
            # Earnings Quality (negative score inverted)
            'accruals': -accruals_result.raw_value if accruals_result else None,
            'cf_ni_ratio': cf_ni_result.metadata['cf_to_ni_ratio'] if cf_ni_result else None,
            # Composite score (average of available factors)
            'profitability_score': sum([
                roe_result.raw_value if roe_result else 0,
                roa_result.raw_value if roa_result else 0,
                op_margin_result.raw_value if op_margin_result else 0,
                net_margin_result.raw_value if net_margin_result else 0
            ]) / 4,
            'liquidity_score': sum([
                current_ratio_result.raw_value if current_ratio_result else 0,
                quick_ratio_result.raw_value if quick_ratio_result else 0
            ]) / 2,
            'leverage_score': debt_result.raw_value if debt_result else 0,
            'earnings_quality_score': sum([
                accruals_result.raw_value if accruals_result else 0,
                cf_ni_result.raw_value if cf_ni_result else 0
            ]) / 2
        }

        results.append(row)

    # Convert to DataFrame
    df = pd.DataFrame(results)

    # Calculate composite quality score (higher = better)
    df['quality_score'] = (
        df['profitability_score'].fillna(0) * 0.4 +
        df['liquidity_score'].fillna(0) * 0.2 +
        df['leverage_score'].fillna(0) * 0.2 +
        df['earnings_quality_score'].fillna(0) * 0.2
    )

    return df


def categorize_by_quality(df: pd.DataFrame):
    """
    Categorize stocks by quality profile

    Categories:
    - Quality Champions: High profitability + Low debt + Strong liquidity
    - Profitable Growth: High profitability but moderate debt
    - Conservative: Low profitability but very strong balance sheet
    - Financial Distress: Negative profitability or poor liquidity
    """
    categories = []

    for _, row in df.iterrows():
        # Check key metrics
        roe = row['roe'] if pd.notna(row['roe']) else 0
        debt = row['debt_equity'] if pd.notna(row['debt_equity']) else 0
        current = row['current_ratio'] if pd.notna(row['current_ratio']) else 0
        net_margin = row['net_margin'] if pd.notna(row['net_margin']) else 0

        # Categorization logic
        if roe > 15 and debt < 100 and current > 200:
            category = "Quality Champion"
        elif roe > 15 and debt < 200:
            category = "Profitable Growth"
        elif roe > 0 and debt < 50 and current > 250:
            category = "Conservative"
        elif roe < 0 or net_margin < 0 or current < 100:
            category = "Financial Distress"
        else:
            category = "Moderate Quality"

        categories.append(category)

    df['quality_category'] = categories
    return df


def display_quality_analysis(df: pd.DataFrame):
    """Display quality analysis results in a readable format"""
    print("\n" + "="*100)
    print("📈 QUALITY FACTORS ANALYSIS - BUSINESS QUALITY ASSESSMENT")
    print("="*100)
    print()

    # Top 10 by quality score
    print("🏆 TOP 10 QUALITY STOCKS (Highest Quality Score)")
    print("-" * 100)
    top_10 = df.nlargest(10, 'quality_score')[[
        'ticker', 'roe', 'roa', 'op_margin', 'net_margin',
        'current_ratio', 'debt_equity', 'quality_score', 'quality_category'
    ]]
    print(top_10.to_string(index=False))
    print()

    # Category distribution
    print("📊 QUALITY CATEGORY DISTRIBUTION")
    print("-" * 100)
    category_counts = df['quality_category'].value_counts()
    for category, count in category_counts.items():
        percentage = (count / len(df)) * 100
        print(f"   {category:25s}: {count:3d} stocks ({percentage:5.1f}%)")
    print()

    # Profitability stars
    print("⭐ PROFITABILITY CHAMPIONS (ROE > 20%)")
    print("-" * 100)
    profit_stars = df[df['roe'] > 20].nlargest(5, 'roe')[[
        'ticker', 'roe', 'roa', 'op_margin', 'net_margin'
    ]]
    if len(profit_stars) > 0:
        print(profit_stars.to_string(index=False))
    else:
        print("   No stocks with ROE > 20% found")
    print()

    # Liquidity champions
    print("💧 LIQUIDITY CHAMPIONS (Current Ratio > 300%)")
    print("-" * 100)
    liquidity_champs = df[df['current_ratio'] > 300].nlargest(5, 'current_ratio')[[
        'ticker', 'current_ratio', 'quick_ratio', 'quality_category'
    ]]
    if len(liquidity_champs) > 0:
        print(liquidity_champs.to_string(index=False))
    else:
        print("   No stocks with Current Ratio > 300% found")
    print()

    # Low debt companies
    print("🛡️ LOW DEBT COMPANIES (Debt-to-Equity < 50%)")
    print("-" * 100)
    low_debt = df[df['debt_equity'] < 50].nsmallest(5, 'debt_equity')[[
        'ticker', 'debt_equity', 'roe', 'quality_category'
    ]]
    if len(low_debt) > 0:
        print(low_debt.to_string(index=False))
    else:
        print("   No stocks with Debt-to-Equity < 50% found")
    print()

    # High earnings quality
    print("💎 HIGH EARNINGS QUALITY (CF-to-NI Ratio > 1.0)")
    print("-" * 100)
    high_eq = df[df['cf_ni_ratio'] > 1.0].nlargest(5, 'cf_ni_ratio')[[
        'ticker', 'cf_ni_ratio', 'accruals', 'net_margin'
    ]]
    if len(high_eq) > 0:
        print(high_eq.to_string(index=False))
    else:
        print("   No stocks with CF-to-NI Ratio > 1.0 found")
    print()

    # Financial distress warnings
    print("⚠️ FINANCIAL DISTRESS WARNINGS")
    print("-" * 100)
    distress = df[df['quality_category'] == 'Financial Distress'][[
        'ticker', 'roe', 'net_margin', 'current_ratio', 'debt_equity'
    ]]
    if len(distress) > 0:
        print(distress.to_string(index=False))
    else:
        print("   No stocks in financial distress found")
    print()

    print("="*100)
    print("✅ Quality Analysis Complete")
    print("="*100)


def main():
    """Main execution function"""
    print("="*100)
    print("🔬 QUALITY FACTORS ANALYSIS - 9 Core Quality Metrics")
    print("="*100)
    print("Profitability: ROE, ROA, Operating Margin, Net Profit Margin")
    print("Liquidity: Current Ratio, Quick Ratio")
    print("Leverage: Debt-to-Equity")
    print("Earnings Quality: Accruals Ratio, CF-to-NI Ratio")
    print("="*100)
    print()

    try:
        # Calculate quality scores
        df = calculate_quality_scores_for_universe()

        # Categorize stocks
        df = categorize_by_quality(df)

        # Display analysis
        display_quality_analysis(df)

        # Save to CSV
        output_file = "quality_factors_analysis.csv"
        df.to_csv(output_file, index=False)
        print(f"\n💾 Results saved to: {output_file}")
        print()

        # Usage example
        print("📝 NEXT STEPS:")
        print("   1. Review Quality Champions for long positions")
        print("   2. Avoid Financial Distress stocks")
        print("   3. Combine with Value/Momentum factors for multi-factor strategy")
        print("   4. Backtest quality portfolios with modules/backtest/backtest_engine.py")
        print()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 TROUBLESHOOTING:")
        print("   1. Ensure database schema is extended:")
        print("      python3 scripts/extend_schema_for_quality_factors.py")
        print("   2. Populate test data:")
        print("      python3 scripts/populate_test_quality_data.py")
        print("   3. Check database path: ./data/spock_local.db")
        print()


if __name__ == '__main__':
    main()
