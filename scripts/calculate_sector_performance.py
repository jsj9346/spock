#!/usr/bin/env python3
"""
Sector Performance Calculation Script

Purpose:
- Calculate daily sector performance from ohlcv_data
- Store results in sector_performance table
- Support both KR and US markets

Usage:
    # Single date
    python3 scripts/calculate_sector_performance.py \\
      --region KR \\
      --date 2025-01-12

    # Date range backfill
    python3 scripts/calculate_sector_performance.py \\
      --region KR \\
      --start-date 2024-01-01 \\
      --end-date 2025-01-12

Author: Spock Quant Platform
Created: 2025-11-12
"""

import os
import sys
import argparse
import logging
from datetime import datetime, date, timedelta

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.macro import SectorPerformanceCalculator
from modules.db_manager_postgres import PostgresDatabaseManager
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def calculate_single_date(calculator: SectorPerformanceCalculator, analysis_date: date, region: str):
    """
    Calculate sector performance for a single date

    Args:
        calculator: SectorPerformanceCalculator instance
        analysis_date: Date to calculate
        region: Market region

    Returns:
        Number of sectors processed
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"Calculating {region} Sector Performance: {analysis_date}")
    logger.info(f"{'='*80}")

    try:
        # Calculate performance
        sector_performance = calculator.calculate_daily_performance(
            analysis_date=analysis_date,
            region=region
        )

        if not sector_performance:
            logger.warning(f"⚠️  No sector data calculated for {region} on {analysis_date}")
            return 0

        # Log results
        logger.info(f"\nSector Performance Summary ({len(sector_performance)} sectors):")
        logger.info(f"{'─'*80}")

        for sector, metrics in sorted(sector_performance.items(), key=lambda x: x[1]['avg_return_1m'], reverse=True):
            logger.info(
                f"  {sector:25s}: 1D={metrics['avg_return_1d']:+6.2f}% | "
                f"1W={metrics['avg_return_1w']:+6.2f}% | "
                f"1M={metrics['avg_return_1m']:+6.2f}% | "
                f"Momentum={metrics['momentum']:8s}"
            )

        # Identify rotation
        rotation = calculator.identify_rotation(sector_performance)
        logger.info(f"\nRotation Analysis:")
        logger.info(f"  Leaders:  {', '.join(rotation['leaders'])}")
        logger.info(f"  Laggards: {', '.join(rotation['laggards'])}")
        logger.info(f"  Pattern:  {rotation['pattern']} (Confidence: {rotation['confidence']})")

        # Save to database
        inserted = calculator.save_to_db(
            analysis_date=analysis_date,
            region=region,
            sector_performance=sector_performance
        )

        logger.info(f"\n✅ Saved {inserted} sector records for {region} on {analysis_date}")
        return len(sector_performance)

    except Exception as e:
        logger.error(f"❌ Error calculating {region} sectors for {analysis_date}: {e}")
        import traceback
        traceback.print_exc()
        return 0


def calculate_date_range(
    calculator: SectorPerformanceCalculator,
    start_date: date,
    end_date: date,
    region: str
):
    """
    Calculate sector performance for a date range

    Args:
        calculator: SectorPerformanceCalculator instance
        start_date: Start date
        end_date: End date
        region: Market region

    Returns:
        Total number of dates processed
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"Backfilling {region} Sector Performance")
    logger.info(f"{'='*80}")
    logger.info(f"Date range: {start_date} → {end_date}")
    logger.info(f"Total days: {(end_date - start_date).days + 1}")

    current_date = start_date
    processed_count = 0
    failed_dates = []

    while current_date <= end_date:
        try:
            # Calculate for current date
            sector_performance = calculator.calculate_daily_performance(
                analysis_date=current_date,
                region=region
            )

            if sector_performance:
                # Save to database
                inserted = calculator.save_to_db(
                    analysis_date=current_date,
                    region=region,
                    sector_performance=sector_performance
                )

                if inserted > 0:
                    processed_count += 1
                    logger.info(f"  ✓ {current_date}: {inserted} sectors")
                else:
                    logger.warning(f"  ⚠️  {current_date}: No data saved")
            else:
                failed_dates.append(current_date)
                logger.warning(f"  ⚠️  {current_date}: No data calculated")

        except Exception as e:
            failed_dates.append(current_date)
            logger.error(f"  ❌ {current_date}: {e}")

        # Move to next date
        current_date += timedelta(days=1)

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info(f"Backfill Summary")
    logger.info(f"{'='*80}")
    logger.info(f"Total dates processed: {processed_count}")
    logger.info(f"Failed dates: {len(failed_dates)}")

    if failed_dates:
        logger.info(f"\nFailed dates ({len(failed_dates)}):")
        for failed_date in failed_dates[:10]:  # Show first 10
            logger.info(f"  - {failed_date}")
        if len(failed_dates) > 10:
            logger.info(f"  ... and {len(failed_dates) - 10} more")

    return processed_count


def main():
    """Entry point"""
    parser = argparse.ArgumentParser(description='Sector Performance Calculation')
    parser.add_argument('--region', type=str, required=True, choices=['KR', 'US'],
                       help='Market region (KR or US)')
    parser.add_argument('--date', type=str, help='Single date (YYYY-MM-DD)')
    parser.add_argument('--start-date', type=str, help='Start date for backfill (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date for backfill (YYYY-MM-DD)')

    args = parser.parse_args()

    # Load environment
    load_dotenv()

    # Validate arguments
    if args.date:
        if args.start_date or args.end_date:
            logger.error("❌ Cannot specify both --date and --start-date/--end-date")
            sys.exit(1)
        mode = "single"
        analysis_date = datetime.strptime(args.date, '%Y-%m-%d').date()
    elif args.start_date and args.end_date:
        mode = "range"
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').date()
    else:
        logger.error("❌ Must specify either --date or --start-date/--end-date")
        sys.exit(1)

    logger.info("="*80)
    logger.info("SECTOR PERFORMANCE CALCULATION")
    logger.info("="*80)
    logger.info(f"Region: {args.region}")
    logger.info(f"Mode: {mode}")

    # Initialize calculator
    db = PostgresDatabaseManager()
    calculator = SectorPerformanceCalculator(db_manager=db)

    # Execute calculation
    if mode == "single":
        logger.info(f"Date: {analysis_date}")
        logger.info("")

        result = calculate_single_date(calculator, analysis_date, args.region)

        if result > 0:
            logger.info(f"\n✅ Successfully calculated {result} sectors")
            sys.exit(0)
        else:
            logger.error(f"\n❌ Failed to calculate sector performance")
            sys.exit(1)

    else:  # range mode
        logger.info(f"Date range: {start_date} → {end_date}")
        logger.info("")

        processed = calculate_date_range(calculator, start_date, end_date, args.region)

        if processed > 0:
            logger.info(f"\n✅ Successfully processed {processed} dates")
            sys.exit(0)
        else:
            logger.error(f"\n❌ No dates processed successfully")
            sys.exit(1)


if __name__ == '__main__':
    main()
