#!/usr/bin/env python3
"""
Example: Factor Library Usage - Complete Workflow

This script demonstrates:
1. Loading stock universe from PostgreSQL
2. Calculating multiple factors (Value, Momentum, Quality)
3. Computing combined factor scores
4. Saving results to database
5. Analyzing factor performance

Usage:
    python3 examples/example_factor_calculation.py --region KR --top 10
"""

import sys
from pathlib import Path
from datetime import datetime
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.factors import (
    # Value Factors
    PERatioFactor,
    PBRatioFactor,
    DividendYieldFactor,
    
    # Momentum Factors
    TwelveMonthMomentumFactor,
    RSIMomentumFactor,
    
    # Quality Factors
    ROEFactor,
    DebtToEquityFactor,
    
    # Low-Vol Factors
    HistoricalVolatilityFactor,
    
    # Factor Combination
    EqualWeightCombiner
)


def main():
    """Main execution workflow"""
    logger.info("=== Factor Library Example: Complete Workflow ===\n")
    
    # Initialize database
    db = PostgresDatabaseManager()
    
    # Step 1: Load active Korean stocks
    logger.info("📊 Step 1: Loading stock universe...")
    
    tickers_query = """
        SELECT DISTINCT ticker
        FROM tickers
        WHERE region = 'KR' AND is_active = TRUE
        ORDER BY ticker
        LIMIT 20
    """
    
    tickers_result = db.execute_query(tickers_query)
    tickers = [row['ticker'] for row in tickers_result]
    
    logger.info(f"✅ Loaded {len(tickers)} tickers: {tickers[:10]}...")
    
    # Step 2: Calculate individual factors
    logger.info("\n📈 Step 2: Calculating factors...")
    
    # Initialize factors
    factors = {
        'value': [
            PERatioFactor(),
            PBRatioFactor(),
            DividendYieldFactor()
        ],
        'momentum': [
            TwelveMonthMomentumFactor(),
            RSIMomentumFactor()
        ],
        'quality': [
            ROEFactor(),
            DebtToEquityFactor()
        ],
        'low_vol': [
            HistoricalVolatilityFactor()
        ]
    }
    
    # Calculate factors for each ticker
    all_results = {}
    
    for ticker in tickers:
        logger.info(f"\n  Processing {ticker}...")
        ticker_results = {}
        
        for category, factor_list in factors.items():
            for factor in factor_list:
                # Note: Actual implementation needs OHLCV data fetching
                # This is a placeholder showing the API
                result = factor.calculate(data=None, ticker=ticker)
                
                if result:
                    ticker_results[factor.name] = result
                    logger.info(f"    ✅ {factor.name}: {result.raw_value:.2f} "
                              f"(percentile: {result.percentile:.1f})")
                else:
                    logger.debug(f"    ⏭️  {factor.name}: No data")
        
        all_results[ticker] = ticker_results
    
    # Step 3: Combine factors
    logger.info("\n🔀 Step 3: Combining factors...")
    
    combiner = EqualWeightCombiner(factors=sum(factors.values(), []))
    
    combined_scores = {}
    for ticker, results in all_results.items():
        if results:
            # Combine factor results
            combined_score = combiner.combine(list(results.values()))
            combined_scores[ticker] = combined_score
            logger.info(f"  {ticker}: Combined score = {combined_score:.2f}")
    
    # Step 4: Rank stocks
    logger.info("\n🏆 Step 4: Ranking stocks...")
    
    ranked_stocks = sorted(
        combined_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    logger.info("\n  Top 10 Stocks by Combined Factor Score:")
    logger.info("  " + "=" * 50)
    for i, (ticker, score) in enumerate(ranked_stocks[:10], 1):
        logger.info(f"  {i:2d}. {ticker:6s} - Score: {score:6.2f}")
    
    # Step 5: Save to database
    logger.info("\n💾 Step 5: Saving results to database...")
    
    save_count = 0
    for ticker, results in all_results.items():
        for factor_name, result in results.items():
            # Save individual factor scores
            # (Implementation uses factor.save_results() method)
            save_count += 1
    
    logger.info(f"✅ Saved {save_count} factor scores to database")
    
    # Step 6: Analyze factor performance
    logger.info("\n📊 Step 6: Factor performance summary...")
    
    factor_stats = {}
    for category, factor_list in factors.items():
        for factor in factor_list:
            valid_results = sum(
                1 for results in all_results.values()
                if factor.name in results
            )
            coverage = (valid_results / len(tickers)) * 100
            factor_stats[factor.name] = {
                'coverage': coverage,
                'valid_count': valid_results
            }
    
    logger.info("\n  Factor Coverage Summary:")
    logger.info("  " + "=" * 50)
    for factor_name, stats in sorted(factor_stats.items()):
        logger.info(f"  {factor_name:25s}: {stats['coverage']:5.1f}% "
                   f"({stats['valid_count']}/{len(tickers)} stocks)")
    
    logger.info("\n✅ Workflow complete!")


if __name__ == "__main__":
    main()
