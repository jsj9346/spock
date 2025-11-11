#!/usr/bin/env python3
"""
Backfill Tracking Errors for ETFs

Calculate and store tracking error metrics for all ETFs with known underlying indices.

Tracking Error Calculation:
- 20-day window: Short-term tracking quality
- 60-day window: Medium-term tracking quality
- 120-day window: Semi-annual tracking quality
- 250-day window: Annual tracking quality (standard)

Usage:
    python3 scripts/backfill_tracking_errors.py [--limit 50] [--dry-run]

Author: Spock Quant Platform
Date: 2025-10-31
"""

import sys
import os
import argparse
import asyncio
from typing import Optional, List, Dict
from datetime import datetime

sys.path.insert(0, '/Users/13ruce/spock')
os.chdir('/Users/13ruce/spock')

from modules.analysis.tracking_error_calculator import TrackingErrorCalculator
from config.database import get_connection
from loguru import logger


# Index ticker mapping (Korean indices)
INDEX_MAPPING = {
    "KOSPI 200": "U001",
    "KOSDAQ 150": "U201",
    "KRX 300": "U301",
    "KOSPI": "U000",
    "KOSDAQ": "U200",

    # Sector indices
    "반도체": "U011",        # Semiconductor
    "2차전지": "U012",       # Secondary Battery
    "바이오": "U013",        # Bio/Healthcare
    "금융": "U014",          # Finance
    "IT": "U015",            # IT/Technology
}


async def get_etfs_with_indices(limit: Optional[int] = None) -> List[Dict]:
    """
    Get ETFs with known underlying indices.

    Args:
        limit: Maximum number of ETFs to process

    Returns:
        List of ETF dicts with ticker, name, and index_ticker
    """
    etfs = []

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Query ETFs with tracking indices
            query = """
                SELECT t.ticker, t.name, ed.tracking_index
                FROM tickers t
                LEFT JOIN etf_details ed ON t.ticker = ed.ticker AND t.region = ed.region
                WHERE t.region = 'KR'
                  AND t.asset_type = 'ETF'
                  AND ed.tracking_index IS NOT NULL
                ORDER BY t.ticker
            """

            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query)
            rows = cursor.fetchall()

            for row in rows:
                ticker, name, tracking_index = row

                # Map index name to ticker
                index_ticker = None
                for index_name, index_code in INDEX_MAPPING.items():
                    if index_name in tracking_index:
                        index_ticker = index_code
                        break

                if index_ticker:
                    etfs.append({
                        "ticker": ticker,
                        "name": name,
                        "tracking_index": tracking_index,
                        "index_ticker": index_ticker
                    })

            logger.info(f"Found {len(etfs)} ETFs with known indices")
            return etfs

    except Exception as e:
        logger.error(f"Failed to fetch ETFs: {e}")
        return []


async def backfill_tracking_errors(
    limit: Optional[int] = None,
    dry_run: bool = False
):
    """
    Backfill tracking errors for all ETFs.

    Args:
        limit: Maximum number of ETFs to process
        dry_run: If True, calculate but don't save to database
    """
    print("\n" + "="*80)
    print("TRACKING ERROR BACKFILL")
    print("="*80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'DRY RUN' if dry_run else 'PRODUCTION'}")
    print(f"Limit: {limit if limit else 'All ETFs'}")
    print("="*80)
    print()

    # Get ETFs
    etfs = await get_etfs_with_indices(limit)

    if not etfs:
        print("No ETFs found with known indices.")
        return

    print(f"Processing {len(etfs)} ETFs...")
    print()

    # Initialize calculator
    calc = TrackingErrorCalculator()

    # Track statistics
    stats = {
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "errors": []
    }

    # Process each ETF
    for i, etf in enumerate(etfs, 1):
        ticker = etf["ticker"]
        name = etf["name"]
        index_ticker = etf["index_ticker"]

        print(f"[{i}/{len(etfs)}] {ticker} ({name[:30]}...) vs. {index_ticker}")

        try:
            # Calculate tracking errors
            results = await calc.calculate_multiple_windows(
                etf_ticker=ticker,
                index_ticker=index_ticker,
                windows=[20, 60, 120, 250],
                region="KR"
            )

            # Display results
            for window, result in results.items():
                if result:
                    te = result["tracking_error_annualized"]
                    interpretation = calc.interpret_tracking_error(te)
                    print(f"  {window}: {te:.2f}% ({interpretation['rating']})")

            # Save to database (unless dry run)
            if not dry_run:
                success = await calc.save_tracking_errors(
                    etf_ticker=ticker,
                    index_ticker=index_ticker,
                    region="KR"
                )

                if success:
                    stats["success"] += 1
                    print(f"  ✅ Saved to database")
                else:
                    stats["failed"] += 1
                    stats["errors"].append(f"{ticker}: Failed to save")
                    print(f"  ❌ Failed to save")
            else:
                stats["success"] += 1
                print(f"  ✓ Calculation successful (dry run)")

        except Exception as e:
            stats["failed"] += 1
            stats["errors"].append(f"{ticker}: {str(e)}")
            logger.error(f"Failed to process {ticker}: {e}")
            print(f"  ❌ Error: {e}")

        print()

    # Display summary
    print("="*80)
    print("BACKFILL SUMMARY")
    print("="*80)
    print(f"Success:  {stats['success']}")
    print(f"Failed:   {stats['failed']}")
    print(f"Skipped:  {stats['skipped']}")
    print(f"Total:    {len(etfs)}")
    print("="*80)

    if stats["errors"]:
        print("\nErrors:")
        for error in stats["errors"][:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(stats["errors"]) > 10:
            print(f"  ... and {len(stats['errors']) - 10} more")

    print()


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Backfill tracking errors for ETFs"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of ETFs to process"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate but don't save to database"
    )

    args = parser.parse_args()

    await backfill_tracking_errors(
        limit=args.limit,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    asyncio.run(main())
