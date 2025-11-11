#!/usr/bin/env python3
"""
Factor Performance Report Generator

Batch backtest all factors and generate comprehensive performance comparison report.

Usage:
    python3 scripts/generate_factor_performance_report.py --start 2022-01-01 --end 2024-12-31
    python3 scripts/generate_factor_performance_report.py --start 2023-01-01 --end 2024-12-31 --parallel 4
    python3 scripts/generate_factor_performance_report.py --factors momentum_12m value_pb quality_roe

Features:
    - Parallel batch backtesting using ProcessPoolExecutor
    - Automatic factor discovery from database
    - CSV output with performance metrics
    - Progress tracking and error handling
    - Comparison visualizations (optional)
"""

import sys
import os
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Any
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
import pandas as pd
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.analysis.factor_backtester import FactorBacktester, FactorBacktestResult


# ============================================================================
# Factor Discovery
# ============================================================================

def discover_available_factors(
    region: str = 'KR',
    start_date: str = '2022-01-01',
    end_date: str = '2024-12-31'
) -> List[str]:
    """
    Discover available factors from database.

    Args:
        region: Region filter (default: 'KR')
        start_date: Start date for availability check
        end_date: End date for availability check

    Returns:
        List of factor names with sufficient data
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor

    logger.info(f"Discovering factors in database for {region} from {start_date} to {end_date}...")

    # Connect to PostgreSQL
    conn = psycopg2.connect(
        dbname="quant_platform",
        user=os.getenv("USER", "13ruce"),
        host="localhost",
        port=5432
    )

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Query factors with sufficient data coverage
            query = """
            SELECT
                factor_name,
                COUNT(DISTINCT ticker) as ticker_count,
                COUNT(*) as record_count,
                MIN(date) as first_date,
                MAX(date) as last_date
            FROM factor_scores
            WHERE region = %s
              AND date >= %s
              AND date <= %s
            GROUP BY factor_name
            HAVING COUNT(DISTINCT ticker) >= 10
               AND COUNT(*) >= 1000
            ORDER BY factor_name;
            """

            cur.execute(query, (region, start_date, end_date))
            rows = cur.fetchall()

            factors = []
            for row in rows:
                factor_name = row['factor_name']
                factors.append(factor_name)

                logger.info(
                    f"  {factor_name}: "
                    f"{row['ticker_count']} tickers, "
                    f"{row['record_count']} records, "
                    f"{row['first_date']} to {row['last_date']}"
                )

            logger.info(f"✅ Discovered {len(factors)} factors with sufficient data")
            return factors

    finally:
        conn.close()


# ============================================================================
# Batch Backtesting
# ============================================================================

def backtest_single_factor_worker(
    factor_name: str,
    start_date: str,
    end_date: str,
    top_n: int,
    threshold: float,
    holding_period: int,
    initial_capital: float
) -> Dict[str, Any]:
    """
    Worker function for parallel backtesting (runs in separate process).

    Args:
        factor_name: Factor to backtest
        start_date: Backtest start date
        end_date: Backtest end date
        top_n: Number of top stocks to hold
        threshold: Minimum factor score threshold
        holding_period: Days to hold positions
        initial_capital: Starting capital

    Returns:
        Dictionary with factor name and result
    """
    try:
        # Create FactorBacktester instance
        backtester = FactorBacktester(
            region='KR',
            initial_capital=initial_capital,
            max_position_size=0.15,
            commission_rate=0.00015,
            slippage_bps=5.0
        )

        # Run backtest (single ticker for now due to vectorbt limitation)
        # TODO: Once vectorbt adapter supports multi-ticker, remove ticker limitation
        result = backtester.backtest_single_factor(
            factor_name=factor_name,
            start_date=start_date,
            end_date=end_date,
            top_n=1,  # Single ticker due to vectorbt limitation
            threshold=threshold,
            holding_period=holding_period,
            tickers=None  # Auto-detect from database
        )

        return {
            'factor_name': factor_name,
            'result': result,
            'error': None
        }

    except Exception as e:
        logger.error(f"❌ Failed to backtest {factor_name}: {e}")
        return {
            'factor_name': factor_name,
            'result': None,
            'error': str(e)
        }


def batch_backtest_factors(
    factors: List[str],
    start_date: str,
    end_date: str,
    top_n: int = 10,
    threshold: float = 70.0,
    holding_period: int = 21,
    initial_capital: float = 10_000_000,
    max_workers: int = 4
) -> List[FactorBacktestResult]:
    """
    Batch backtest multiple factors in parallel.

    Args:
        factors: List of factor names to backtest
        start_date: Backtest start date
        end_date: Backtest end date
        top_n: Number of top stocks to hold
        threshold: Minimum factor score threshold
        holding_period: Days to hold positions
        initial_capital: Starting capital
        max_workers: Maximum parallel workers (default: 4)

    Returns:
        List of FactorBacktestResult objects
    """
    logger.info(f"Starting batch backtest for {len(factors)} factors...")
    logger.info(f"  Period: {start_date} to {end_date}")
    logger.info(f"  Parameters: top_n={top_n}, threshold={threshold}, holding_period={holding_period}")
    logger.info(f"  Parallel workers: {max_workers}")

    results = []
    completed = 0

    # Use ProcessPoolExecutor for parallel backtesting
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_factor = {
            executor.submit(
                backtest_single_factor_worker,
                factor_name=factor,
                start_date=start_date,
                end_date=end_date,
                top_n=top_n,
                threshold=threshold,
                holding_period=holding_period,
                initial_capital=initial_capital
            ): factor
            for factor in factors
        }

        # Process results as they complete
        for future in as_completed(future_to_factor):
            factor = future_to_factor[future]
            completed += 1

            try:
                task_result = future.result()

                if task_result['error']:
                    logger.error(f"❌ [{completed}/{len(factors)}] {factor}: {task_result['error']}")
                else:
                    result = task_result['result']
                    results.append(result)

                    logger.info(
                        f"✅ [{completed}/{len(factors)}] {factor}: "
                        f"Return={result.total_return:.2%}, "
                        f"Sharpe={result.sharpe_ratio:.2f}, "
                        f"Trades={result.total_trades}, "
                        f"Time={result.execution_time:.2f}s"
                    )

            except Exception as e:
                logger.error(f"❌ [{completed}/{len(factors)}] {factor}: Unexpected error: {e}")

    logger.info(f"✅ Batch backtest complete: {len(results)}/{len(factors)} successful")
    return results


# ============================================================================
# Report Generation
# ============================================================================

def generate_csv_report(
    results: List[FactorBacktestResult],
    output_path: str
) -> None:
    """
    Generate CSV report from backtest results.

    Args:
        results: List of FactorBacktestResult objects
        output_path: Output CSV file path
    """
    logger.info(f"Generating CSV report: {output_path}")

    # Convert results to DataFrame
    data = []
    for result in results:
        data.append({
            'factor_name': result.factor_name,
            'start_date': result.start_date,
            'end_date': result.end_date,
            'total_return': result.total_return,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown': result.max_drawdown,
            'total_trades': result.total_trades,
            'win_rate': result.win_rate,
            'execution_time': result.execution_time,
            'engine': result.engine
        })

    df = pd.DataFrame(data)

    # Sort by Sharpe ratio (descending)
    df = df.sort_values('sharpe_ratio', ascending=False)

    # Save to CSV
    df.to_csv(output_path, index=False)

    logger.info(f"✅ CSV report saved: {output_path}")
    logger.info(f"  Total factors: {len(df)}")
    logger.info(f"  Best factor: {df.iloc[0]['factor_name']} (Sharpe={df.iloc[0]['sharpe_ratio']:.2f})")
    logger.info(f"  Worst factor: {df.iloc[-1]['factor_name']} (Sharpe={df.iloc[-1]['sharpe_ratio']:.2f})")


def print_summary_statistics(results: List[FactorBacktestResult]) -> None:
    """
    Print summary statistics for batch backtest results.

    Args:
        results: List of FactorBacktestResult objects
    """
    if not results:
        logger.warning("No results to summarize")
        return

    logger.info("\n" + "="*80)
    logger.info("FACTOR PERFORMANCE SUMMARY")
    logger.info("="*80)

    # Calculate statistics
    returns = [r.total_return for r in results]
    sharpes = [r.sharpe_ratio for r in results]
    drawdowns = [r.max_drawdown for r in results]
    trades = [r.total_trades for r in results]

    # Find best performers
    best_return = max(results, key=lambda r: r.total_return)
    best_sharpe = max(results, key=lambda r: r.sharpe_ratio)
    min_drawdown = min(results, key=lambda r: r.max_drawdown)

    logger.info(f"\nOverall Statistics:")
    logger.info(f"  Total factors tested: {len(results)}")
    logger.info(f"  Average return: {sum(returns)/len(returns):.2%}")
    logger.info(f"  Average Sharpe ratio: {sum(sharpes)/len(sharpes):.2f}")
    logger.info(f"  Average max drawdown: {sum(drawdowns)/len(drawdowns):.2%}")
    logger.info(f"  Average trades: {sum(trades)/len(trades):.0f}")

    logger.info(f"\nBest Performers:")
    logger.info(f"  Highest return: {best_return.factor_name} ({best_return.total_return:.2%})")
    logger.info(f"  Highest Sharpe: {best_sharpe.factor_name} ({best_sharpe.sharpe_ratio:.2f})")
    logger.info(f"  Lowest drawdown: {min_drawdown.factor_name} ({min_drawdown.max_drawdown:.2%})")

    logger.info("\n" + "="*80 + "\n")


# ============================================================================
# Main CLI
# ============================================================================

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Generate factor performance comparison report',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backtest all factors (2022-2024)
  python3 scripts/generate_factor_performance_report.py --start 2022-01-01 --end 2024-12-31

  # Backtest specific factors
  python3 scripts/generate_factor_performance_report.py \\
    --start 2023-01-01 --end 2024-12-31 \\
    --factors momentum_12m value_pb quality_roe

  # Use 8 parallel workers
  python3 scripts/generate_factor_performance_report.py \\
    --start 2022-01-01 --end 2024-12-31 \\
    --parallel 8

  # Custom output path
  python3 scripts/generate_factor_performance_report.py \\
    --start 2022-01-01 --end 2024-12-31 \\
    --output results/factor_performance_2022_2024.csv
        """
    )

    parser.add_argument(
        '--start',
        type=str,
        required=True,
        help='Backtest start date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--end',
        type=str,
        required=True,
        help='Backtest end date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--factors',
        type=str,
        nargs='+',
        default=None,
        help='Specific factors to test (default: all factors in database)'
    )

    parser.add_argument(
        '--top-n',
        type=int,
        default=10,
        help='Number of top stocks to hold (default: 10)'
    )

    parser.add_argument(
        '--threshold',
        type=float,
        default=70.0,
        help='Minimum factor score threshold (default: 70.0)'
    )

    parser.add_argument(
        '--holding-period',
        type=int,
        default=21,
        help='Days to hold positions (default: 21)'
    )

    parser.add_argument(
        '--initial-capital',
        type=float,
        default=10_000_000,
        help='Starting capital (default: 10,000,000)'
    )

    parser.add_argument(
        '--parallel',
        type=int,
        default=4,
        help='Number of parallel workers (default: 4)'
    )

    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output CSV path (default: results/factor_performance_YYYYMMDD.csv)'
    )

    args = parser.parse_args()

    # Configure logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )

    # Create output directory
    output_dir = Path(__file__).parent.parent / 'results'
    output_dir.mkdir(exist_ok=True)

    # Generate default output path if not provided
    if args.output is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = output_dir / f'factor_performance_{timestamp}.csv'
    else:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Discover or use specified factors
    if args.factors:
        factors = args.factors
        logger.info(f"Using {len(factors)} specified factors: {', '.join(factors)}")
    else:
        factors = discover_available_factors(
            region='KR',
            start_date=args.start,
            end_date=args.end
        )

        if not factors:
            logger.error("❌ No factors found in database")
            return 1

    # Run batch backtest
    start_time = datetime.now()

    results = batch_backtest_factors(
        factors=factors,
        start_date=args.start,
        end_date=args.end,
        top_n=args.top_n,
        threshold=args.threshold,
        holding_period=args.holding_period,
        initial_capital=args.initial_capital,
        max_workers=args.parallel
    )

    elapsed = (datetime.now() - start_time).total_seconds()

    if not results:
        logger.error("❌ No successful backtests")
        return 1

    # Generate CSV report
    generate_csv_report(results, str(output_path))

    # Print summary statistics
    print_summary_statistics(results)

    logger.info(f"✅ All done in {elapsed:.1f}s!")
    logger.info(f"   Report: {output_path}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
