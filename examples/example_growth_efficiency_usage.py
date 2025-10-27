#!/usr/bin/env python3
"""
Example Usage: Growth and Efficiency Factors (Phase 2B)

This example demonstrates:
1. Individual factor calculation
2. Factor score interpretation
3. Integration with existing factors
4. Batch calculation with FactorScoreCalculator

Author: Spock Quant Platform - Phase 2B Examples
Date: 2025-10-24
"""

import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.factors import (
    # Growth factors
    RevenueGrowthFactor,
    OperatingProfitGrowthFactor,
    NetIncomeGrowthFactor,

    # Efficiency factors
    AssetTurnoverFactor,
    EquityTurnoverFactor,

    # Calculator
    FactorScoreCalculator
)


def example_individual_factors():
    """Example 1: Calculate individual growth and efficiency factors"""
    print("\n" + "="*80)
    print("Example 1: Individual Factor Calculation")
    print("="*80 + "\n")

    # Initialize factors
    revenue_growth = RevenueGrowthFactor()
    op_growth = OperatingProfitGrowthFactor()
    ni_growth = NetIncomeGrowthFactor()
    asset_turnover = AssetTurnoverFactor()
    equity_turnover = EquityTurnoverFactor()

    # Test ticker (AAPL - should have data in ticker_fundamentals)
    ticker = 'AAPL'
    region = 'US'

    print(f"Calculating factors for {ticker} ({region})...\n")

    # Calculate Growth Factors
    print("Growth Factors:")
    print("-" * 80)

    revenue_result = revenue_growth.calculate(None, ticker=ticker, region=region)
    if revenue_result:
        print(f"✅ Revenue Growth (YOY): {revenue_result.metadata['revenue_growth_yoy']:+.2f}%")
        print(f"   Current Revenue: ${revenue_result.metadata['current_revenue']:,.0f}")
        print(f"   Previous Revenue: ${revenue_result.metadata['previous_revenue']:,.0f}")
        print(f"   Fiscal Year: {revenue_result.metadata['current_year']}\n")
    else:
        print(f"❌ Revenue Growth: No data available\n")

    op_result = op_growth.calculate(None, ticker=ticker, region=region)
    if op_result:
        print(f"✅ Operating Profit Growth (YOY): {op_result.metadata['op_growth_yoy']:+.2f}%")
        print(f"   Current OP: ${op_result.metadata['current_op']:,.0f}")
        print(f"   Previous OP: ${op_result.metadata['previous_op']:,.0f}\n")
    else:
        print(f"❌ Operating Profit Growth: No data available\n")

    ni_result = ni_growth.calculate(None, ticker=ticker, region=region)
    if ni_result:
        print(f"✅ Net Income Growth (YOY): {ni_result.metadata['ni_growth_yoy']:+.2f}%")
        print(f"   Current NI: ${ni_result.metadata['current_ni']:,.0f}")
        print(f"   Previous NI: ${ni_result.metadata['previous_ni']:,.0f}\n")
    else:
        print(f"❌ Net Income Growth: No data available\n")

    # Calculate Efficiency Factors
    print("\nEfficiency Factors:")
    print("-" * 80)

    asset_result = asset_turnover.calculate(None, ticker=ticker, region=region)
    if asset_result:
        print(f"✅ Asset Turnover: {asset_result.metadata['asset_turnover']:.2f}x")
        print(f"   Revenue: ${asset_result.metadata['revenue']:,.0f}")
        print(f"   Avg Total Assets: ${asset_result.metadata['avg_total_assets']:,.0f}")
        print(f"   Fiscal Year: {asset_result.metadata['fiscal_year']}\n")
    else:
        print(f"❌ Asset Turnover: No data available\n")

    equity_result = equity_turnover.calculate(None, ticker=ticker, region=region)
    if equity_result:
        print(f"✅ Equity Turnover: {equity_result.metadata['equity_turnover']:.2f}x")
        print(f"   Revenue: ${equity_result.metadata['revenue']:,.0f}")
        print(f"   Avg Total Equity: ${equity_result.metadata['avg_total_equity']:,.0f}\n")
    else:
        print(f"❌ Equity Turnover: No data available\n")


def example_factor_score_calculator():
    """Example 2: Use FactorScoreCalculator with all 27 factors"""
    print("\n" + "="*80)
    print("Example 2: FactorScoreCalculator Integration (22 → 27 Factors)")
    print("="*80 + "\n")

    # Initialize calculator
    calculator = FactorScoreCalculator()

    print(f"Total Factors Registered: {len(calculator.factors)}")
    print(f"Expected: 27 (22 existing + 3 Growth + 2 Efficiency)\n")

    # List all factor categories
    print("Factor Categories:")
    print("-" * 80)

    momentum_factors = [k for k in calculator.factors.keys() if 'momentum' in k or 'rsi' in k or 'short_term' in k]
    value_factors = [k for k in calculator.factors.keys() if 'pe' in k or 'pb' in k or 'ev' in k or 'dividend' in k]
    quality_factors = [k for k in calculator.factors.keys() if 'roe' in k or 'roa' in k or 'margin' in k or 'ratio' in k or 'equity' in k and 'turnover' not in k or 'accruals' in k or 'cf' in k]
    low_vol_factors = [k for k in calculator.factors.keys() if 'volatility' in k or 'beta' in k or 'drawdown' in k]
    size_factors = [k for k in calculator.factors.keys() if 'market_cap' in k or 'liquidity' in k or 'float' in k]
    growth_factors = [k for k in calculator.factors.keys() if 'growth' in k]
    efficiency_factors = [k for k in calculator.factors.keys() if 'turnover' in k and 'equity' in k or 'asset' in k and 'turnover' in k]

    print(f"Momentum (3): {', '.join(momentum_factors)}")
    print(f"Value (4): {', '.join(value_factors)}")
    print(f"Quality (9): {', '.join(quality_factors)}")
    print(f"Low-Vol (3): {', '.join(low_vol_factors)}")
    print(f"Size (3): {', '.join(size_factors)}")
    print(f"Growth (3) [NEW]: {', '.join(growth_factors)}")
    print(f"Efficiency (2) [NEW]: {', '.join(efficiency_factors)}")


def example_factor_comparison():
    """Example 3: Compare growth and efficiency across multiple tickers"""
    print("\n" + "="*80)
    print("Example 3: Multi-Ticker Comparison (Growth & Efficiency)")
    print("="*80 + "\n")

    # Test tickers (US tech stocks)
    tickers = ['AAPL', 'MSFT', 'GOOGL']

    # Initialize factors
    revenue_growth = RevenueGrowthFactor()
    asset_turnover = AssetTurnoverFactor()

    print(f"Comparing: {', '.join(tickers)}\n")
    print(f"{'Ticker':<10} {'Revenue Growth':<20} {'Asset Turnover':<20}")
    print("-" * 80)

    for ticker in tickers:
        # Revenue Growth
        revenue_result = revenue_growth.calculate(None, ticker=ticker, region='US')
        revenue_str = f"{revenue_result.metadata['revenue_growth_yoy']:+.2f}%" if revenue_result else "N/A"

        # Asset Turnover
        asset_result = asset_turnover.calculate(None, ticker=ticker, region='US')
        asset_str = f"{asset_result.metadata['asset_turnover']:.2f}x" if asset_result else "N/A"

        print(f"{ticker:<10} {revenue_str:<20} {asset_str:<20}")


if __name__ == '__main__':
    print("\n" + "="*80)
    print("Growth & Efficiency Factors - Usage Examples (Phase 2B)")
    print("="*80 + "\n")

    try:
        # Example 1: Individual factors
        example_individual_factors()

        # Example 2: FactorScoreCalculator integration
        example_factor_score_calculator()

        # Example 3: Multi-ticker comparison
        example_factor_comparison()

        print("\n" + "="*80)
        print("Examples Complete!")
        print("="*80 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nNote: Make sure PostgreSQL is running and ticker_fundamentals has data.")
        print("      Run 'python3 scripts/backfill_us_fundamentals.py' to populate data.")
