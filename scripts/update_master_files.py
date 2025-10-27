#!/usr/bin/env python3
"""
Automated Master File Update Script

Runs daily at 6AM KST to download new master files and refresh ticker database.
Supports all regions: US, HK, JP, CN, VN

Features:
- Force refresh master files from KIS servers
- Multi-region support with parallel updates
- Comprehensive logging and error handling
- Prometheus metrics export
- Alert notifications on failures

Schedule:
- Daily: 6:00 AM KST (after US market close, before Asia open)
- Weekly: Sunday 3:00 AM KST (full refresh + validation)

Author: Spock Trading System
Date: 2025-10-15
"""

import sys
import os
import time
import logging
from datetime import datetime
from typing import Dict, List
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.api_clients.kis_master_file_manager import KISMasterFileManager
from modules.api_clients.kis_overseas_stock_api import KISOverseasStockAPI
from dotenv import load_dotenv

# Setup logging
log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(f'{log_dir}/master_file_updates.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def print_separator(title: str = None):
    """Print section separator"""
    logger.info("=" * 80)
    if title:
        logger.info(title)
        logger.info("=" * 80)


def update_region(region: str, force_refresh: bool = True, dry_run: bool = False) -> Dict:
    """
    Update master files for a region

    Args:
        region: Region code (US, HK, JP, CN, VN)
        force_refresh: Force download new master files
        dry_run: Test mode without actual updates

    Returns:
        Dictionary with update results:
        {
            'success': bool,
            'ticker_count': int,
            'duration': float,
            'error': str (if failed)
        }
    """
    start_time = time.time()
    result = {
        'success': False,
        'ticker_count': 0,
        'duration': 0.0,
        'error': None
    }

    try:
        logger.info(f"🔄 [{region}] Starting update...")

        if dry_run:
            logger.info(f"   [DRY RUN] Simulating update for {region}")
            result['success'] = True
            result['ticker_count'] = 1000  # Dummy count
            result['duration'] = time.time() - start_time
            return result

        # Initialize API
        api = KISOverseasStockAPI(
            os.getenv('KIS_APP_KEY'),
            os.getenv('KIS_APP_SECRET')
        )

        # Force refresh master files
        tickers = api.get_tickers_with_details(region, force_refresh=force_refresh)

        if tickers:
            result['success'] = True
            result['ticker_count'] = len(tickers)
            result['duration'] = time.time() - start_time

            logger.info(
                f"✅ [{region}] Update successful: {len(tickers):,} tickers "
                f"in {result['duration']:.2f}s"
            )
        else:
            result['error'] = "No tickers returned"
            logger.warning(f"⚠️ [{region}] No tickers returned")

    except Exception as e:
        result['error'] = str(e)
        result['duration'] = time.time() - start_time
        logger.error(f"❌ [{region}] Update failed: {e}")

    return result


def validate_data_quality(regions: List[str]) -> Dict:
    """
    Validate data quality after updates

    Args:
        regions: List of region codes to validate

    Returns:
        Dictionary with validation results per region
    """
    logger.info("🔍 Validating data quality...")

    validation_results = {}
    manager = KISMasterFileManager()

    for region in regions:
        try:
            tickers = manager.get_all_tickers(region, force_refresh=False)

            # Calculate completeness
            complete_count = 0
            for ticker in tickers:
                if all([
                    ticker.get('ticker'),
                    ticker.get('name'),
                    ticker.get('exchange'),
                    ticker.get('region') == region,
                    ticker.get('currency')
                ]):
                    complete_count += 1

            completeness = (complete_count / len(tickers) * 100) if tickers else 0

            validation_results[region] = {
                'total': len(tickers),
                'complete': complete_count,
                'completeness': completeness,
                'passed': completeness >= 95.0
            }

            status = "✅" if completeness >= 95.0 else "⚠️"
            logger.info(
                f"   {status} [{region}] {len(tickers):,} tickers, "
                f"{completeness:.1f}% complete"
            )

        except Exception as e:
            logger.error(f"   ❌ [{region}] Validation failed: {e}")
            validation_results[region] = {
                'total': 0,
                'complete': 0,
                'completeness': 0.0,
                'passed': False,
                'error': str(e)
            }

    return validation_results


def export_metrics(results: Dict[str, Dict]):
    """
    Export update metrics for Prometheus

    Args:
        results: Update results dictionary
    """
    try:
        metrics_file = 'data/master_file_update_metrics.prom'
        os.makedirs(os.path.dirname(metrics_file), exist_ok=True)

        with open(metrics_file, 'w') as f:
            f.write("# HELP spock_master_file_update_success Update success indicator\n")
            f.write("# TYPE spock_master_file_update_success gauge\n")

            for region, result in results.items():
                success = 1 if result.get('success', False) else 0
                f.write(f'spock_master_file_update_success{{region="{region}"}} {success}\n')

            f.write("\n# HELP spock_master_file_ticker_count Total tickers after update\n")
            f.write("# TYPE spock_master_file_ticker_count gauge\n")

            for region, result in results.items():
                count = result.get('ticker_count', 0)
                f.write(f'spock_master_file_ticker_count{{region="{region}"}} {count}\n')

            f.write("\n# HELP spock_master_file_update_duration_seconds Update duration\n")
            f.write("# TYPE spock_master_file_update_duration_seconds gauge\n")

            for region, result in results.items():
                duration = result.get('duration', 0.0)
                f.write(f'spock_master_file_update_duration_seconds{{region="{region}"}} {duration:.3f}\n')

            f.write("\n# HELP spock_master_file_update_timestamp Last update timestamp\n")
            f.write("# TYPE spock_master_file_update_timestamp gauge\n")
            timestamp = int(time.time())
            f.write(f'spock_master_file_update_timestamp {timestamp}\n')

        logger.info(f"✅ Metrics exported to {metrics_file}")

    except Exception as e:
        logger.error(f"❌ Failed to export metrics: {e}")


def send_alert(subject: str, message: str):
    """
    Send alert notification (placeholder for future implementation)

    Args:
        subject: Alert subject
        message: Alert message
    """
    # TODO: Implement Slack/Email notification
    logger.warning(f"🚨 ALERT: {subject}")
    logger.warning(f"   {message}")


def main(regions: List[str] = None, force_refresh: bool = True,
         dry_run: bool = False, validate: bool = True):
    """
    Main update routine

    Args:
        regions: List of regions to update (None = all)
        force_refresh: Force download new master files
        dry_run: Test mode without actual updates
        validate: Run data quality validation
    """
    print_separator()
    logger.info(f"Master File Daily Update - {datetime.now()}")
    if dry_run:
        logger.info("⚠️ DRY RUN MODE - No actual updates will be performed")
    print_separator()

    # Default to all regions if not specified
    if regions is None:
        regions = ['US', 'HK', 'JP', 'CN', 'VN']

    # Update all regions
    results = {}
    total_start = time.time()

    for region in regions:
        results[region] = update_region(region, force_refresh, dry_run)
        # Rate limiting between regions
        time.sleep(0.5)

    total_duration = time.time() - total_start

    # Validate data quality
    if validate and not dry_run:
        print_separator("Data Quality Validation")
        validation_results = validate_data_quality(regions)

        # Check for failures
        failed_validations = [
            r for r, v in validation_results.items()
            if not v.get('passed', False)
        ]

        if failed_validations:
            send_alert(
                "Master File Update - Data Quality Warning",
                f"Regions with <95% completeness: {', '.join(failed_validations)}"
            )

    # Export metrics
    if not dry_run:
        export_metrics(results)

    # Summary
    print_separator("Update Summary")

    for region in regions:
        result = results[region]
        if result['success']:
            logger.info(
                f"  ✅ {region:2}: {result['ticker_count']:,} tickers "
                f"in {result['duration']:.2f}s"
            )
        else:
            error = result.get('error', 'Unknown error')
            logger.error(f"  ❌ {region:2}: Failed - {error}")

    # Calculate success rate
    passed = sum(1 for r in results.values() if r['success'])
    total = len(results)
    success_rate = (passed / total * 100) if total > 0 else 0

    logger.info(f"\nTotal: {passed}/{total} regions updated successfully ({success_rate:.0f}%)")
    logger.info(f"Duration: {total_duration:.2f}s")

    # Send alert if any failures
    if passed < total:
        failed_regions = [r for r, res in results.items() if not res['success']]
        send_alert(
            "Master File Update - Partial Failure",
            f"Failed regions: {', '.join(failed_regions)}"
        )

    print_separator()

    return passed == total


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Update master files for all regions')
    parser.add_argument(
        '--regions',
        nargs='+',
        choices=['US', 'HK', 'JP', 'CN', 'VN'],
        help='Regions to update (default: all)'
    )
    parser.add_argument(
        '--no-force',
        action='store_true',
        help='Do not force refresh (use cache if available)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Test mode without actual updates'
    )
    parser.add_argument(
        '--no-validate',
        action='store_true',
        help='Skip data quality validation'
    )

    args = parser.parse_args()

    try:
        success = main(
            regions=args.regions,
            force_refresh=not args.no_force,
            dry_run=args.dry_run,
            validate=not args.no_validate
        )
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logger.info("\n⚠️ Update interrupted by user")
        sys.exit(130)

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
