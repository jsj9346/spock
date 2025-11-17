#!/usr/bin/env python3
"""
Test Script for HK Market Momentum Factors

Tests:
1. Individual factor calculations (RSI, MACD, 52W, 1M, 12M)
2. Composite momentum calculator
3. Quality validation (coverage, distribution, preliminary IC)

Usage:
    python3 scripts/test_momentum_factors_hk.py --ticker 0700
    python3 scripts/test_momentum_factors_hk.py --sample 50
    python3 scripts/test_momentum_factors_hk.py --all
"""

import sys
import os
import argparse
from typing import Optional, List
import pandas as pd
import numpy as np
from datetime import datetime

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
from loguru import logger


def test_individual_factors(ticker: str):
    """
    Test individual momentum factor calculations for a single ticker

    Args:
        ticker: HK stock ticker (e.g., '0700' for Tencent)
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"개별 Momentum Factors 테스트: {ticker}")
    logger.info(f"{'='*60}")

    # Initialize factors
    rsi_factor = RSIMomentumFactorHK(region='HK')
    macd_factor = MACDMomentumFactorHK(region='HK')
    week52_factor = Week52HighFactorHK(region='HK')
    short_term_factor = ShortTermMomentumFactorHK(region='HK')
    long_term_factor = LongTermMomentumFactorHK(region='HK')

    # Test each factor
    factors = [
        ('RSI Momentum', rsi_factor),
        ('MACD Momentum', macd_factor),
        ('52-Week High', week52_factor),
        ('Short-Term (1M)', short_term_factor),
        ('Long-Term (12M)', long_term_factor)
    ]

    results = {}
    for name, factor in factors:
        try:
            result = factor.calculate(None, ticker)
            if result:
                results[name] = result
                logger.info(f"\n✅ {name}:")
                logger.info(f"   Raw Value: {result.raw_value:.4f}")
                logger.info(f"   Confidence: {result.confidence:.2f}")
                logger.info(f"   Metadata: {result.metadata}")
            else:
                logger.warning(f"\n⚠️  {name}: No data available")
        except Exception as e:
            logger.error(f"\n❌ {name}: Error - {str(e)}")

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"요약: {len(results)}/5 팩터 계산 성공")
    logger.info(f"{'='*60}\n")

    return results


def test_composite_calculator(tickers: Optional[List[str]] = None, sample_size: Optional[int] = None):
    """
    Test composite momentum score calculator

    Args:
        tickers: List of tickers to test (optional)
        sample_size: Number of random tickers to test (optional)
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Composite Momentum Calculator 테스트")
    logger.info(f"{'='*60}")

    # Initialize calculator
    calculator = MomentumFactorCalculatorHK(region='HK')

    # Get tickers
    if tickers is None:
        db = PostgresDatabaseManager()
        if sample_size:
            # Random sample
            query = """
            SELECT ticker
            FROM tickers
            WHERE region = 'HK' AND is_active = true
            ORDER BY RANDOM()
            LIMIT %s
            """
            result = db.execute_query(query, (sample_size,))
        else:
            # All tickers
            query = "SELECT ticker FROM tickers WHERE region = 'HK' AND is_active = true ORDER BY ticker"
            result = db.execute_query(query)

        tickers = [row['ticker'].replace('.HK', '') for row in result]
        logger.info(f"Fetched {len(tickers)} HK tickers for testing")

    # Calculate composite scores
    df = calculator.calculate_all_tickers(tickers)

    if len(df) == 0:
        logger.error("❌ No results calculated")
        return None

    # Display results
    logger.info(f"\n✅ Successfully calculated momentum scores for {len(df)} tickers")
    logger.info(f"\nTop 10 Tickers by Momentum Score:")
    logger.info(f"{df.head(10).to_string()}")

    logger.info(f"\nBottom 10 Tickers by Momentum Score:")
    logger.info(f"{df.tail(10).to_string()}")

    # Statistics
    logger.info(f"\nMomentum Score Statistics:")
    logger.info(f"  Mean: {df['momentum_score'].mean():.4f}")
    logger.info(f"  Median: {df['momentum_score'].median():.4f}")
    logger.info(f"  Std Dev: {df['momentum_score'].std():.4f}")
    logger.info(f"  Min: {df['momentum_score'].min():.4f}")
    logger.info(f"  Max: {df['momentum_score'].max():.4f}")

    # Factor coverage report
    coverage_report = calculator.get_factor_coverage_report()
    logger.info(f"\nFactor Coverage Report:")
    for key, value in coverage_report.items():
        if key != 'weights':
            logger.info(f"  {key}: {value}")

    # Factor combination distribution
    if 'factor_combination_stats' in coverage_report:
        logger.info(f"\nFactor Combination Distribution:")
        for count, tickers_count in sorted(coverage_report['factor_combination_stats'].items()):
            pct = tickers_count * 100 / coverage_report['total_tickers']
            logger.info(f"  {count} factors: {tickers_count} tickers ({pct:.1f}%)")

    logger.info(f"\n{'='*60}\n")

    return df, coverage_report


def validate_factor_quality(df: pd.DataFrame):
    """
    Validate momentum factor quality

    Preliminary validation (full IC analysis requires forward returns):
    1. Coverage: % of tickers with valid scores
    2. Distribution: Score distribution characteristics
    3. Correlation: Inter-factor correlation (should be low)

    Args:
        df: DataFrame from composite calculator
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Momentum Factor 품질 검증")
    logger.info(f"{'='*60}")

    # 1. Coverage validation
    total_possible = 2636  # Total HK tickers
    coverage_pct = len(df) * 100 / total_possible
    logger.info(f"\n1. Coverage:")
    logger.info(f"   Valid scores: {len(df)}/{total_possible} ({coverage_pct:.2f}%)")

    if coverage_pct < 50:
        logger.warning(f"   ⚠️  Low coverage (<50%). Check data availability.")
    else:
        logger.info(f"   ✅ Good coverage (>50%)")

    # 2. Distribution validation
    logger.info(f"\n2. Score Distribution:")

    # Check for reasonable spread
    score_range = df['momentum_score'].max() - df['momentum_score'].min()
    logger.info(f"   Range: {score_range:.4f}")

    # Check skewness
    skew = df['momentum_score'].skew()
    logger.info(f"   Skewness: {skew:.4f}")
    if abs(skew) > 2:
        logger.warning(f"   ⚠️  High skewness (|{skew:.2f}| > 2). Distribution may be unbalanced.")
    else:
        logger.info(f"   ✅ Reasonable skewness")

    # Quintile distribution
    quintiles = pd.qcut(df['momentum_score'], q=5, labels=['Q1', 'Q2', 'Q3', 'Q4', 'Q5'])
    quintile_counts = quintiles.value_counts().sort_index()
    logger.info(f"\n   Quintile Distribution:")
    for q, count in quintile_counts.items():
        pct = count * 100 / len(df)
        logger.info(f"     {q}: {count} tickers ({pct:.1f}%)")

    # 3. Confidence validation
    logger.info(f"\n3. Confidence Metrics:")
    logger.info(f"   Mean confidence: {df['confidence'].mean():.4f}")
    logger.info(f"   Min confidence: {df['confidence'].min():.4f}")

    low_confidence = df[df['confidence'] < 0.75]
    if len(low_confidence) > 0:
        low_conf_pct = len(low_confidence) * 100 / len(df)
        logger.warning(f"   ⚠️  {len(low_confidence)} tickers with low confidence (<0.75) = {low_conf_pct:.1f}%")
    else:
        logger.info(f"   ✅ All tickers have confidence >= 0.75")

    # 4. Factor availability distribution
    logger.info(f"\n4. Factor Availability:")
    factor_counts = df['factor_count'].value_counts().sort_index()
    for count, num_tickers in factor_counts.items():
        pct = num_tickers * 100 / len(df)
        logger.info(f"   {count} factors: {num_tickers} tickers ({pct:.1f}%)")

    # 5. Summary and recommendations
    logger.info(f"\n{'='*60}")
    logger.info(f"검증 요약:")
    logger.info(f"{'='*60}")

    # Check if ready for IC analysis
    ready_for_ic = True
    issues = []

    if coverage_pct < 50:
        ready_for_ic = False
        issues.append("Low coverage (<50%)")

    if abs(skew) > 2:
        issues.append("High skewness")

    if len(low_confidence) > len(df) * 0.3:
        ready_for_ic = False
        issues.append("Too many low confidence tickers (>30%)")

    if ready_for_ic:
        logger.info("✅ Momentum factors are ready for IC analysis and validation")
        logger.info("\nNext Steps:")
        logger.info("  1. Calculate forward returns (1M, 3M, 6M, 12M)")
        logger.info("  2. Compute Information Coefficient (IC)")
        logger.info("  3. Test statistical significance (p-value < 0.05)")
        logger.info("  4. Analyze quintile performance spreads")
    else:
        logger.warning("⚠️  Factors need improvement before IC analysis")
        logger.warning(f"\nIssues found:")
        for issue in issues:
            logger.warning(f"  - {issue}")

    logger.info(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description='Test HK Market Momentum Factors')
    parser.add_argument('--ticker', type=str, help='Test single ticker (e.g., 0700)')
    parser.add_argument('--sample', type=int, help='Test random sample of N tickers')
    parser.add_argument('--all', action='store_true', help='Test all HK tickers')

    args = parser.parse_args()

    logger.info(f"\n{'='*80}")
    logger.info(f"HK Market Momentum Factors - 테스트 스크립트")
    logger.info(f"{'='*80}")
    logger.info(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Test individual ticker
    if args.ticker:
        test_individual_factors(args.ticker)

    # Test sample or all tickers
    if args.sample or args.all:
        sample_size = None if args.all else args.sample
        df, coverage = test_composite_calculator(sample_size=sample_size)

        if df is not None and len(df) > 0:
            validate_factor_quality(df)

    # Default: test a few representative tickers
    if not (args.ticker or args.sample or args.all):
        logger.info("No arguments provided. Testing default tickers...\n")

        # Test individual factors for Tencent (0700)
        test_individual_factors('0700')

        # Test composite calculator with 50 random tickers
        df, coverage = test_composite_calculator(sample_size=50)

        if df is not None and len(df) > 0:
            validate_factor_quality(df)

    logger.info("\n✅ 테스트 완료!")


if __name__ == "__main__":
    main()
