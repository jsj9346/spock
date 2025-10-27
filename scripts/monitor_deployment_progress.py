#!/usr/bin/env python3
"""
Monitor Historical Fundamental Data Deployment Progress

This script monitors the progress of historical fundamental data collection
and provides real-time updates.

Usage:
    python3 scripts/monitor_deployment_progress.py [--interval SECONDS]

Arguments:
    --interval: Check interval in seconds (default: 60)
"""

import time
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_sqlite import SQLiteDatabaseManager


class DeploymentMonitor:
    """Monitor deployment progress and provide real-time updates"""

    def __init__(self, db_path: str = 'data/spock_local.db'):
        self.db = SQLiteDatabaseManager(db_path=db_path)
        self.target_tickers = 50
        self.target_rows = 250  # 50 tickers × 5 years
        self.start_time = datetime.now()
        self.last_ticker_count = 0
        self.last_row_count = 0

    def get_current_status(self):
        """Get current deployment status"""
        conn = self.db._get_connection()
        cursor = conn.cursor()

        # Count total historical rows
        cursor.execute('''
            SELECT COUNT(*) FROM ticker_fundamentals
            WHERE fiscal_year IS NOT NULL
              AND fiscal_year BETWEEN 2020 AND 2024
              AND period_type = 'ANNUAL'
        ''')
        total_rows = cursor.fetchone()[0]

        # Count distinct tickers
        cursor.execute('''
            SELECT COUNT(DISTINCT ticker) FROM ticker_fundamentals
            WHERE fiscal_year IS NOT NULL
              AND fiscal_year BETWEEN 2020 AND 2024
              AND period_type = 'ANNUAL'
        ''')
        distinct_tickers = cursor.fetchone()[0]

        # Count complete tickers (5 years)
        cursor.execute('''
            SELECT ticker, COUNT(*) as year_count
            FROM ticker_fundamentals
            WHERE fiscal_year IS NOT NULL
              AND fiscal_year BETWEEN 2020 AND 2024
              AND period_type = 'ANNUAL'
            GROUP BY ticker
            HAVING year_count = 5
        ''')
        complete_tickers = len(cursor.fetchall())

        # Count partial tickers
        partial_tickers = distinct_tickers - complete_tickers

        # Get year distribution
        cursor.execute('''
            SELECT fiscal_year, COUNT(*) as count
            FROM ticker_fundamentals
            WHERE fiscal_year IS NOT NULL
              AND fiscal_year BETWEEN 2020 AND 2024
              AND period_type = 'ANNUAL'
            GROUP BY fiscal_year
            ORDER BY fiscal_year
        ''')
        year_distribution = {row[0]: row[1] for row in cursor.fetchall()}

        conn.close()

        return {
            'total_rows': total_rows,
            'distinct_tickers': distinct_tickers,
            'complete_tickers': complete_tickers,
            'partial_tickers': partial_tickers,
            'year_distribution': year_distribution,
            'timestamp': datetime.now()
        }

    def calculate_progress(self, status):
        """Calculate progress metrics"""
        ticker_progress = (status['distinct_tickers'] / self.target_tickers) * 100
        row_progress = (status['total_rows'] / self.target_rows) * 100

        # Calculate new tickers/rows since last check
        new_tickers = status['distinct_tickers'] - self.last_ticker_count
        new_rows = status['total_rows'] - self.last_row_count

        # Update last counts
        self.last_ticker_count = status['distinct_tickers']
        self.last_row_count = status['total_rows']

        # Calculate ETA
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if new_tickers > 0 and elapsed > 0:
            tickers_per_second = status['distinct_tickers'] / elapsed
            remaining_tickers = self.target_tickers - status['distinct_tickers']
            eta_seconds = remaining_tickers / tickers_per_second if tickers_per_second > 0 else 0
            eta = datetime.fromtimestamp(time.time() + eta_seconds)
        else:
            eta = None

        return {
            'ticker_progress': ticker_progress,
            'row_progress': row_progress,
            'new_tickers': new_tickers,
            'new_rows': new_rows,
            'eta': eta,
            'elapsed_minutes': elapsed / 60
        }

    def print_status(self, status, progress):
        """Print status update"""
        print("\n" + "="*70)
        print(f"📊 DEPLOYMENT PROGRESS - {status['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)

        print(f"\n📈 Overall Progress:")
        print(f"  Tickers: {status['distinct_tickers']}/{self.target_tickers} ({progress['ticker_progress']:.1f}%)")
        print(f"  Rows:    {status['total_rows']}/{self.target_rows} ({progress['row_progress']:.1f}%)")

        print(f"\n✅ Data Quality:")
        print(f"  Complete: {status['complete_tickers']} tickers (100% - all 5 years)")
        print(f"  Partial:  {status['partial_tickers']} tickers (⚠️  financial holdings)")

        print(f"\n📅 Year Distribution:")
        for year in range(2020, 2025):
            count = status['year_distribution'].get(year, 0)
            print(f"  {year}: {count:3d} rows")

        if progress['new_tickers'] > 0:
            print(f"\n🔄 Recent Activity:")
            print(f"  New tickers: +{progress['new_tickers']}")
            print(f"  New rows:    +{progress['new_rows']}")

        print(f"\n⏱️  Timing:")
        print(f"  Elapsed: {progress['elapsed_minutes']:.1f} minutes")
        if progress['eta']:
            print(f"  ETA:     {progress['eta'].strftime('%H:%M:%S KST')}")

        # Progress bar
        ticker_bar_length = 50
        ticker_filled = int(ticker_bar_length * progress['ticker_progress'] / 100)
        ticker_bar = '█' * ticker_filled + '░' * (ticker_bar_length - ticker_filled)
        print(f"\n  [{ticker_bar}] {progress['ticker_progress']:.1f}%")

        print("="*70)

    def monitor(self, interval: int = 60, max_iterations: int = None):
        """
        Monitor deployment progress

        Args:
            interval: Check interval in seconds (default: 60)
            max_iterations: Maximum number of checks (None = infinite)
        """
        print("🚀 Starting deployment monitoring...")
        print(f"📊 Target: {self.target_tickers} tickers, {self.target_rows} rows")
        print(f"⏱️  Check interval: {interval} seconds")
        print("\nPress Ctrl+C to stop monitoring\n")

        iteration = 0

        try:
            while True:
                # Get current status
                status = self.get_current_status()
                progress = self.calculate_progress(status)

                # Print status
                self.print_status(status, progress)

                # Check if complete
                if status['distinct_tickers'] >= self.target_tickers:
                    print("\n🎉 DEPLOYMENT COMPLETE!")
                    print(f"✅ Collected {status['total_rows']} rows for {status['distinct_tickers']} tickers")
                    break

                # Check max iterations
                iteration += 1
                if max_iterations and iteration >= max_iterations:
                    print(f"\n⏸️  Reached maximum iterations ({max_iterations})")
                    break

                # Wait for next check
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\n⏸️  Monitoring stopped by user")
            print(f"📊 Last status: {status['distinct_tickers']}/{self.target_tickers} tickers, {status['total_rows']}/{self.target_rows} rows")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Monitor historical fundamental data deployment progress'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Check interval in seconds (default: 60)'
    )
    parser.add_argument(
        '--max-iterations',
        type=int,
        default=None,
        help='Maximum number of checks (default: infinite)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Check once and exit (equivalent to --max-iterations 1)'
    )

    args = parser.parse_args()

    # Create monitor
    monitor = DeploymentMonitor()

    # Run monitoring
    if args.once:
        max_iterations = 1
    else:
        max_iterations = args.max_iterations

    monitor.monitor(interval=args.interval, max_iterations=max_iterations)


if __name__ == '__main__':
    main()
