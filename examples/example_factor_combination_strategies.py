#!/usr/bin/env python3
"""
Example: Multi-Factor Portfolio Construction Strategies

Demonstrates 3 different factor combination strategies:
1. Aggressive Growth: Momentum + Value focus (공격적 성장)
2. Defensive Quality: Quality + Low-Vol focus (방어적 안정)
3. All-Weather Optimized: Historical optimization (전천후 최적화)

Each strategy:
- Calculates alpha scores for stock universe
- Ranks stocks by composite score
- Selects top 30 stocks
- Outputs to terminal + CSV file

Usage:
    python3 examples/example_factor_combination_strategies.py

Prerequisites:
    - ticker_fundamentals table with data
    - OHLCV data for factor calculation

Author: Spock Quant Platform - Phase 2 Multi-Factor
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from datetime import datetime
from modules.factors import (
    FactorScoreCalculator,
    EqualWeightCombiner,
    CategoryWeightCombiner,
    OptimizationCombiner
)


def get_sample_universe(db_path: str = "./data/spock_local.db") -> list:
    """
    Get sample stock universe for testing

    In production, this would query KOSPI 200 or other indices
    For now, returns sample tickers for demonstration

    Returns:
        List of ticker codes
    """
    import sqlite3

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get Korean tickers with recent fundamental data (DART API)
    # Prioritize most recently updated Korean tickers
    cursor.execute("""
        SELECT DISTINCT ticker
        FROM ticker_fundamentals
        WHERE LENGTH(ticker) = 6 AND ticker GLOB '[0-9][0-9][0-9][0-9][0-9][0-9]'
        ORDER BY date DESC
        LIMIT 50
    """)

    tickers = [row[0] for row in cursor.fetchall()]
    conn.close()

    if len(tickers) == 0:
        print("⚠️  No tickers found in database")
        print("   Returning sample tickers for demonstration")
        return ['TEST001', 'TEST002', 'TEST003']

    return tickers


def strategy_1_aggressive_growth(calculator: FactorScoreCalculator, tickers: list) -> pd.DataFrame:
    """
    Strategy 1: Aggressive Growth - Momentum + Value Focus

    투자 전략:
    - MOMENTUM 40%: 추세 추종, 상승 모멘텀 포착
    - VALUE 35%: 저평가 매수 기회
    - QUALITY 15%: 최소한의 품질 필터
    - LOW_VOL 5%: 리스크 관리 (최소)
    - SIZE 5%: 소형주 프리미엄 (최소)

    적합 시장: Bull Market, 경기 회복기
    목표: 높은 수익률 (Sharpe > 1.5)
    위험: Bear Market에서 큰 손실 가능
    """
    print("\n" + "="*100)
    print("📈 STRATEGY 1: AGGRESSIVE GROWTH (공격적 성장)")
    print("="*100)

    # Configure combiner
    category_weights = {
        'MOMENTUM': 0.40,
        'VALUE': 0.35,
        'QUALITY': 0.15,
        'LOW_VOL': 0.05,
        'SIZE': 0.05
    }

    combiner = CategoryWeightCombiner(category_weights)

    print(f"\n📊 Category Weights:")
    for category, weight in category_weights.items():
        print(f"   {category:15s}: {weight:.0%}")

    # Calculate composite scores
    print(f"\n🔄 Calculating alpha scores for {len(tickers)} stocks...")
    results = calculator.batch_calculate_composite(tickers, combiner)

    # Rank stocks
    results = results.sort_values('alpha_score', ascending=False).reset_index(drop=True)
    results['rank'] = range(1, len(results) + 1)

    # Select top 30
    top_30 = results.head(30).copy()
    top_30['weight'] = 1.0 / len(top_30)  # Equal weight
    top_30['strategy_name'] = 'Aggressive Growth'

    return top_30


def strategy_2_defensive_quality(calculator: FactorScoreCalculator, tickers: list) -> pd.DataFrame:
    """
    Strategy 2: Defensive Quality - Quality + Low-Vol Focus

    투자 전략:
    - QUALITY 40%: 우량주 중심 (높은 ROE, 낮은 부채)
    - LOW_VOL 30%: 변동성 최소화, 방어적 포지셔닝
    - VALUE 15%: 가치 요인 보조
    - MOMENTUM 10%: 최소 모멘텀 필터
    - SIZE 5%: 소형주 회피

    적합 시장: Bear Market, 고변동성 환경
    목표: 낮은 변동성 (Max Drawdown < 15%)
    위험: Bull Market에서 상승 기회 제한적
    """
    print("\n" + "="*100)
    print("🛡️  STRATEGY 2: DEFENSIVE QUALITY (방어적 안정)")
    print("="*100)

    category_weights = {
        'MOMENTUM': 0.10,
        'VALUE': 0.15,
        'QUALITY': 0.40,
        'LOW_VOL': 0.30,
        'SIZE': 0.05
    }

    combiner = CategoryWeightCombiner(category_weights)

    print(f"\n📊 Category Weights:")
    for category, weight in category_weights.items():
        print(f"   {category:15s}: {weight:.0%}")

    print(f"\n🔄 Calculating alpha scores for {len(tickers)} stocks...")
    results = calculator.batch_calculate_composite(tickers, combiner)

    results = results.sort_values('alpha_score', ascending=False).reset_index(drop=True)
    results['rank'] = range(1, len(results) + 1)

    top_30 = results.head(30).copy()
    top_30['weight'] = 1.0 / len(top_30)
    top_30['strategy_name'] = 'Defensive Quality'

    return top_30


def strategy_3_all_weather_optimized(calculator: FactorScoreCalculator, tickers: list) -> pd.DataFrame:
    """
    Strategy 3: All-Weather Optimized - Historical Optimization

    투자 전략:
    - 과거 데이터 기반 최적화 (2018-2023)
    - Sharpe Ratio 최대화
    - 균형 잡힌 포트폴리오

    적합 시장: 모든 시장 환경
    목표: 일관된 알파 창출
    위험: Overfitting, 시장 환경 변화
    """
    print("\n" + "="*100)
    print("⚖️  STRATEGY 3: ALL-WEATHER OPTIMIZED (전천후 최적화)")
    print("="*100)

    # Optimize weights
    combiner = OptimizationCombiner(db_path="./data/spock_local.db")

    print("\n🔄 Optimizing factor weights (2018-2023)...")
    combiner.fit(start_date='2018-01-01', end_date='2023-12-31', objective='max_sharpe')

    # Display optimal weights
    print("\n📊 Optimal Factor Weights (Top 10):")
    optimal_weights = combiner.get_optimal_weights()
    sorted_weights = sorted(optimal_weights.items(), key=lambda x: -x[1])[:10]

    for factor, weight in sorted_weights:
        print(f"   {factor:20s}: {weight:.2%}")

    print(f"\n🔄 Calculating alpha scores for {len(tickers)} stocks...")
    results = calculator.batch_calculate_composite(tickers, combiner)

    results = results.sort_values('alpha_score', ascending=False).reset_index(drop=True)
    results['rank'] = range(1, len(results) + 1)

    top_30 = results.head(30).copy()
    top_30['weight'] = 1.0 / len(top_30)
    top_30['strategy_name'] = 'All-Weather Optimized'

    return top_30


def display_portfolio(portfolio: pd.DataFrame, strategy_name: str):
    """Display portfolio results to terminal"""
    print(f"\n🎯 TOP 30 PORTFOLIO - {strategy_name.upper()}")
    print("-" * 100)

    if len(portfolio) == 0:
        print("   No stocks selected (insufficient data)")
        return

    # Display top 10
    display_df = portfolio.head(10)[['rank', 'ticker', 'alpha_score', 'valid_factors_count', 'weight']]
    print(display_df.to_string(index=False))
    print(f"\n   ... and {len(portfolio) - 10} more stocks")

    # Summary statistics
    print(f"\n📈 Portfolio Summary:")
    print(f"   Total Stocks: {len(portfolio)}")
    print(f"   Avg Alpha Score: {portfolio['alpha_score'].mean():.2f}")
    print(f"   Min Alpha Score: {portfolio['alpha_score'].min():.2f}")
    print(f"   Max Alpha Score: {portfolio['alpha_score'].max():.2f}")
    print(f"   Avg Valid Factors: {portfolio['valid_factors_count'].mean():.1f} / 22")


def save_to_csv(portfolio: pd.DataFrame, strategy_name: str):
    """Save portfolio to CSV file"""
    timestamp = datetime.now().strftime('%Y%m%d')
    strategy_slug = strategy_name.lower().replace(' ', '_').replace('-', '_')
    filename = f"portfolio_{strategy_slug}_{timestamp}.csv"

    # Select columns for CSV
    output_df = portfolio[[
        'rank', 'ticker', 'alpha_score', 'valid_factors_count', 'weight', 'strategy_name'
    ]]

    output_df.to_csv(filename, index=False)
    print(f"\n💾 Portfolio saved to: {filename}")


def main():
    """Main execution function"""
    print("="*100)
    print("🚀 MULTI-FACTOR PORTFOLIO CONSTRUCTION - 3 STRATEGIES")
    print("="*100)
    print("\nDemonstrates:")
    print("  1. Aggressive Growth: Momentum + Value (40% + 35%)")
    print("  2. Defensive Quality: Quality + Low-Vol (40% + 30%)")
    print("  3. All-Weather Optimized: Historical optimization (max Sharpe)")
    print("\nOutput: Terminal display + CSV files")
    print("="*100)

    try:
        # Initialize calculator
        calculator = FactorScoreCalculator(db_path="./data/spock_local.db")

        # Get stock universe
        print("\n📋 Loading stock universe...")
        tickers = get_sample_universe()
        print(f"   Found {len(tickers)} stocks")

        if len(tickers) == 0:
            print("\n❌ No stocks found - exiting")
            return

        # Run Strategy 1: Aggressive Growth
        portfolio_1 = strategy_1_aggressive_growth(calculator, tickers)
        display_portfolio(portfolio_1, "Aggressive Growth")
        save_to_csv(portfolio_1, "Aggressive Growth")

        # Run Strategy 2: Defensive Quality
        portfolio_2 = strategy_2_defensive_quality(calculator, tickers)
        display_portfolio(portfolio_2, "Defensive Quality")
        save_to_csv(portfolio_2, "Defensive Quality")

        # Run Strategy 3: All-Weather Optimized
        portfolio_3 = strategy_3_all_weather_optimized(calculator, tickers)
        display_portfolio(portfolio_3, "All-Weather Optimized")
        save_to_csv(portfolio_3, "All-Weather Optimized")

        # Final summary
        print("\n" + "="*100)
        print("✅ ALL STRATEGIES COMPLETE")
        print("="*100)
        print("\n📝 NEXT STEPS:")
        print("   1. Review CSV files for portfolio composition")
        print("   2. Backtest strategies with modules/backtest/backtest_engine.py")
        print("   3. Optimize portfolio weights with modules/optimization/")
        print("   4. Monitor live performance with modules/risk/")
        print("\n📚 ACADEMIC INSIGHTS:")
        print("   • Strategy 1 (Momentum+Value): Jegadeesh & Titman (1993) + Fama-French (1992)")
        print("   • Strategy 2 (Quality+LowVol): Asness et al. (2014) + Ang et al. (2006)")
        print("   • Strategy 3 (Optimized): Markowitz (1952) mean-variance framework")
        print()

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 TROUBLESHOOTING:")
        print("   1. Ensure database exists: ./data/spock_local.db")
        print("   2. Populate ticker_fundamentals table with market_cap, pe_ratio, etc.")
        print("   3. Populate ohlcv_data table for momentum/volatility factors")
        print("   4. Run: python3 modules/kis_data_collector.py --region KR")
        print()
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
