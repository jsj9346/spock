#!/usr/bin/env python3
"""
Walk-Forward Validation for Multi-Factor Strategy

Validates strategy robustness across multiple out-of-sample periods.
Uses rolling window approach: train on N years, test on M years, roll forward.

Key Features:
- Out-of-sample IC calculation (train period)
- Backtest execution (test period)
- Statistical aggregation across all periods
- Regime-aware performance analysis

Usage:
    # Validate Tier 3 configuration (recommended)
    python3 scripts/walk_forward_validation.py \
      --factors Operating_Profit_Margin,RSI_Momentum,ROE_Proxy \
      --train-years 2 \
      --test-years 1 \
      --start 2018-01-01 \
      --end 2024-10-09 \
      --capital 100000000

    # Custom configuration
    python3 scripts/walk_forward_validation.py \
      --factors 12M_Momentum,1M_Momentum,PE_Ratio \
      --train-years 3 \
      --test-years 1 \
      --start 2015-01-01 \
      --end 2024-10-09

Author: Spock Quant Platform
Date: 2025-10-24
Purpose: Production readiness validation for Tier 3 configuration
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import argparse
from loguru import logger
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
import subprocess

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_postgres import PostgresDatabaseManager

# Configure logger
logger.remove()
logger.add(
    lambda msg: print(msg, end=''),
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)


def generate_walk_forward_periods(
    start_date: str,
    end_date: str,
    train_years: int,
    test_years: int
) -> List[Tuple[str, str, str, str]]:
    """
    Generate walk-forward training and testing periods.

    Args:
        start_date: Overall start date (YYYY-MM-DD)
        end_date: Overall end date (YYYY-MM-DD)
        train_years: Years for IC calculation (training)
        test_years: Years for backtesting (testing)

    Returns:
        List of (train_start, train_end, test_start, test_end) tuples
    """
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')

    periods = []
    current_start = start

    while True:
        # Train period: current_start + train_years
        train_end = current_start + timedelta(days=train_years * 365)

        # Test period: train_end + test_years
        test_start = train_end + timedelta(days=1)
        test_end = test_start + timedelta(days=test_years * 365)

        # Stop if test period exceeds overall end date
        if test_end > end:
            break

        periods.append((
            current_start.strftime('%Y-%m-%d'),
            train_end.strftime('%Y-%m-%d'),
            test_start.strftime('%Y-%m-%d'),
            test_end.strftime('%Y-%m-%d')
        ))

        # Roll forward by test_years
        current_start = test_start

    return periods


def run_single_backtest(
    factors: List[str],
    ic_start: str,
    ic_end: str,
    backtest_start: str,
    backtest_end: str,
    capital: float,
    top_percentile: int,
    rebalance_freq: str,
    weighting_method: str = 'ic'
) -> Dict:
    """
    Run single backtest using backtest_orthogonal_factors.py

    Returns:
        Dict with results: {
            'return': float,
            'sharpe': float,
            'win_rate': float,
            'max_drawdown': float,
            'transaction_costs': float,
            'avg_holdings': float
        }
    """
    # Build command
    cmd = [
        'python3',
        'scripts/backtest_orthogonal_factors.py',
        '--start', backtest_start,
        '--end', backtest_end,
        '--ic-start', ic_start,
        '--ic-end', ic_end,
        '--factors', ','.join(factors),
        '--capital', str(capital),
        '--top-percentile', str(top_percentile),
        '--rebalance-freq', rebalance_freq,
        '--weighting-method', weighting_method,
        '--rolling-window', '252',
        '--no-signed-ic'
    ]

    logger.info(f"\n🔄 Running backtest: {backtest_start} to {backtest_end}")
    logger.info(f"   IC period: {ic_start} to {ic_end}")

    try:
        # Run backtest
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode != 0:
            logger.error(f"❌ Backtest failed: {result.stderr}")
            return None

        # Parse output for results
        output = result.stdout

        # Extract metrics from output
        metrics = {}

        def safe_float(value_str, default=0.0):
            """Safely parse float, handling 'nan', empty strings, and None"""
            try:
                value_str = value_str.strip()
                if value_str.lower() == 'nan' or not value_str:
                    return default
                return float(value_str)
            except (ValueError, AttributeError):
                return default

        for line in output.split('\n'):
            try:
                if 'Total Return:' in line:
                    value = line.split(':')[-1].replace('%', '').strip()
                    metrics['return'] = safe_float(value)
                elif 'Sharpe Ratio:' in line:
                    value = line.split(':')[-1].strip()
                    metrics['sharpe'] = safe_float(value)
                elif 'Win Rate:' in line:
                    value = line.split(':')[-1].replace('%', '').strip()
                    metrics['win_rate'] = safe_float(value)
                elif 'Max Drawdown:' in line:
                    value = line.split(':')[-1].replace('%', '').strip()
                    # Max DD is negative, but store as absolute value
                    metrics['max_drawdown'] = safe_float(value)
                elif 'Total Costs:' in line:
                    # Extract from format "₩    432,763"
                    cost_str = line.split(':')[-1].replace('₩', '').replace(',', '').strip()
                    cost_value = safe_float(cost_str)
                    metrics['transaction_costs'] = (cost_value / capital * 100) if capital > 0 else 0.0
                elif 'Avg Holdings:' in line:
                    value = line.split(':')[-1].strip()
                    metrics['avg_holdings'] = safe_float(value)
            except Exception as e:
                logger.debug(f"   ⚠️  Failed to parse line: {line.strip()} - {e}")
                continue

        logger.info(f"   ✅ Return: {metrics.get('return', 0):.2f}%, "
                   f"Sharpe: {metrics.get('sharpe', 0):.2f}, "
                   f"Win Rate: {metrics.get('win_rate', 0):.0f}%, "
                   f"Max DD: {metrics.get('max_drawdown', 0):.2f}%")

        return metrics

    except subprocess.TimeoutExpired:
        logger.error(f"❌ Backtest timed out (>300s)")
        return None
    except Exception as e:
        logger.error(f"❌ Backtest error: {e}")
        return None


def aggregate_results(all_results: List[Dict], periods: List[Tuple]) -> Dict:
    """
    Aggregate results across all walk-forward periods

    Returns:
        Dict with aggregated statistics
    """
    if not all_results:
        return {}

    returns = [r['return'] for r in all_results if r]
    sharpes = [r['sharpe'] for r in all_results if r]
    win_rates = [r['win_rate'] for r in all_results if r]
    max_dds = [r['max_drawdown'] for r in all_results if r]
    txn_costs = [r['transaction_costs'] for r in all_results if r]

    return {
        'num_periods': len(all_results),
        'successful_periods': len([r for r in all_results if r]),
        'avg_return': np.mean(returns),
        'std_return': np.std(returns),
        'min_return': np.min(returns),
        'max_return': np.max(returns),
        'avg_sharpe': np.mean(sharpes),
        'std_sharpe': np.std(sharpes),
        'avg_win_rate': np.mean(win_rates),
        'avg_max_dd': np.mean(max_dds),
        'worst_max_dd': np.min(max_dds),
        'avg_txn_cost': np.mean(txn_costs),
        'positive_periods': len([r for r in returns if r > 0]),
        'negative_periods': len([r for r in returns if r < 0])
    }


def print_summary(results: Dict, periods: List[Tuple], factors: List[str]):
    """Print comprehensive walk-forward validation summary"""
    logger.info("\n" + "=" * 80)
    logger.info("WALK-FORWARD VALIDATION SUMMARY")
    logger.info("=" * 80)

    logger.info(f"\n📊 Configuration:")
    logger.info(f"   Factors: {', '.join(factors)}")
    logger.info(f"   Periods: {results['num_periods']}")
    logger.info(f"   Successful: {results['successful_periods']}/{results['num_periods']}")

    logger.info(f"\n📈 RETURNS:")
    logger.info(f"   Average:    {results['avg_return']:>8.2f}%")
    logger.info(f"   Std Dev:    {results['std_return']:>8.2f}%")
    logger.info(f"   Min:        {results['min_return']:>8.2f}%")
    logger.info(f"   Max:        {results['max_return']:>8.2f}%")
    logger.info(f"   Positive:   {results['positive_periods']}/{results['num_periods']} periods")
    logger.info(f"   Negative:   {results['negative_periods']}/{results['num_periods']} periods")

    logger.info(f"\n📊 RISK METRICS:")
    logger.info(f"   Avg Sharpe: {results['avg_sharpe']:>8.2f}")
    logger.info(f"   Std Sharpe: {results['std_sharpe']:>8.2f}")
    logger.info(f"   Avg Win Rate: {results['avg_win_rate']:>6.1f}%")
    logger.info(f"   Avg Max DD:   {results['avg_max_dd']:>6.2f}%")
    logger.info(f"   Worst Max DD: {results['worst_max_dd']:>6.2f}%")

    logger.info(f"\n💰 COSTS:")
    logger.info(f"   Avg Transaction Cost: {results['avg_txn_cost']:.2f}% of capital")

    # Decision criteria
    logger.info(f"\n🎯 PRODUCTION READINESS CHECK:")
    criteria = {
        'Positive Avg Return': results['avg_return'] > 0,
        'Sharpe > 1.0': results['avg_sharpe'] > 1.0,
        'Win Rate > 45%': results['avg_win_rate'] > 45,
        'Max DD < 20%': results['worst_max_dd'] > -20,
        'Positive Majority': results['positive_periods'] > results['negative_periods']
    }

    for criterion, passed in criteria.items():
        status = "✅" if passed else "❌"
        logger.info(f"   {status} {criterion}")

    all_passed = all(criteria.values())
    logger.info(f"\n{'🚀 READY FOR PRODUCTION' if all_passed else '⚠️  NEEDS IMPROVEMENT'}")
    logger.info("=" * 80)


def main():
    parser = argparse.ArgumentParser(description='Walk-Forward Validation')

    # Period configuration
    parser.add_argument('--start', required=True, help='Overall start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='Overall end date (YYYY-MM-DD)')
    parser.add_argument('--train-years', type=int, default=2, help='Years for IC calculation')
    parser.add_argument('--test-years', type=int, default=1, help='Years for backtesting')

    # Strategy configuration
    parser.add_argument('--factors', required=True, help='Comma-separated factor names')
    parser.add_argument('--capital', type=float, default=100_000_000, help='Initial capital')
    parser.add_argument('--top-percentile', type=int, default=45, help='Top percentile for stock selection')
    parser.add_argument('--rebalance-freq', default='Q', choices=['M', 'Q', 'SA', 'A'], help='Rebalance frequency')
    parser.add_argument('--weighting-method', default='ic', choices=['ic', 'equal'],
                        help='Phase 3: Factor weighting method (ic=IC-weighted, equal=1/n per factor)')

    args = parser.parse_args()

    factors = [f.strip() for f in args.factors.split(',')]

    logger.info("=" * 80)
    logger.info("WALK-FORWARD VALIDATION - Out-of-Sample Testing")
    logger.info("=" * 80)
    logger.info(f"\n⏱️  Period: {args.start} to {args.end}")
    logger.info(f"📚 Train Window: {args.train_years} years")
    logger.info(f"🧪 Test Window: {args.test_years} years")
    logger.info(f"📊 Factors: {', '.join(factors)}")

    # Generate walk-forward periods
    periods = generate_walk_forward_periods(
        args.start,
        args.end,
        args.train_years,
        args.test_years
    )

    logger.info(f"\n🔄 Generated {len(periods)} walk-forward periods:")
    for i, (train_start, train_end, test_start, test_end) in enumerate(periods, 1):
        logger.info(f"   Period {i}: Train({train_start} to {train_end}) → Test({test_start} to {test_end})")

    # Run backtests for each period
    all_results = []
    for i, (train_start, train_end, test_start, test_end) in enumerate(periods, 1):
        logger.info(f"\n{'=' * 80}")
        logger.info(f"PERIOD {i}/{len(periods)}")
        logger.info(f"{'=' * 80}")

        result = run_single_backtest(
            factors=factors,
            ic_start=train_start,
            ic_end=train_end,
            backtest_start=test_start,
            backtest_end=test_end,
            capital=args.capital,
            top_percentile=args.top_percentile,
            rebalance_freq=args.rebalance_freq,
            weighting_method=args.weighting_method
        )

        all_results.append(result)

    # Aggregate and print summary
    summary = aggregate_results(all_results, periods)
    print_summary(summary, periods, factors)

    # Save results to file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = project_root / f'analysis/walk_forward_results_{timestamp}.csv'

    results_df = pd.DataFrame([
        {
            'period': i + 1,
            'train_start': train_start,
            'train_end': train_end,
            'test_start': test_start,
            'test_end': test_end,
            **result
        }
        for i, ((train_start, train_end, test_start, test_end), result)
        in enumerate(zip(periods, all_results))
        if result
    ])

    results_df.to_csv(output_file, index=False)
    logger.info(f"\n💾 Results saved: {output_file}")


if __name__ == '__main__':
    main()
