#!/usr/bin/env python3
"""
Real-Time Backfill Progress Monitor

Live monitoring dashboard for Week 3 OHLCV backfill operations:
- Parse backfill log files in real-time
- Display progress statistics (success/failed/remaining)
- Calculate estimated completion time
- Detect and alert on errors
- Show recent activity

Features:
- Auto-refresh display (configurable interval)
- Color-coded status indicators
- Progress bar visualization
- Performance metrics (tickers/hour, avg time per ticker)
- Error pattern detection

Usage:
    # Monitor default log file
    python3 scripts/monitor_backfill_progress.py

    # Monitor specific log file
    python3 scripts/monitor_backfill_progress.py --log log/backfill_kr_week3_full_universe.log

    # Custom refresh interval (seconds)
    python3 scripts/monitor_backfill_progress.py --refresh 5

    # Single snapshot (no auto-refresh)
    python3 scripts/monitor_backfill_progress.py --once

Author: Spock Quant Platform - Week 3 Monitoring
Date: 2025-10-27
"""

import sys
import os
import time
import argparse
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class BackfillMonitor:
    """Real-time backfill progress monitor"""

    def __init__(self, log_file: str):
        """
        Initialize monitor

        Args:
            log_file: Path to backfill log file
        """
        self.log_file = log_file
        self.stats = {
            'total_tickers': 0,
            'processed': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'records_saved': 0,
            'api_calls': 0,
            'start_time': None,
            'last_update': None
        }
        self.errors = []
        self.recent_activity = []

    def parse_log_file(self):
        """Parse log file and extract statistics"""
        if not os.path.exists(self.log_file):
            raise FileNotFoundError(f"Log file not found: {self.log_file}")

        with open(self.log_file, 'r') as f:
            lines = f.readlines()

        # Reset stats
        self.errors = []
        self.recent_activity = []

        for line in lines:
            # Extract start time
            if 'KR OHLCV Historical Data Backfill' in line:
                timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if timestamp_match:
                    self.stats['start_time'] = datetime.strptime(
                        timestamp_match.group(1), '%Y-%m-%d %H:%M:%S'
                    )

            # Extract total tickers
            if 'Total Tickers:' in line:
                match = re.search(r'Total Tickers:\s*(\d+)', line)
                if match:
                    self.stats['total_tickers'] = int(match.group(1))

            # Extract processing status
            if re.search(r'\[(\d+)/(\d+)\] Processing', line):
                match = re.search(r'\[(\d+)/(\d+)\]', line)
                if match:
                    self.stats['processed'] = int(match.group(1))

            # Extract success
            if '✅' in line and 'Saved' in line:
                self.stats['success'] += 1
                match = re.search(r'Saved (\d+) records', line)
                if match:
                    self.stats['records_saved'] += int(match.group(1))

                # Track recent activity
                ticker_match = re.search(r'✅\s+(\d{6})', line)
                if ticker_match:
                    self.recent_activity.append(f"✅ {ticker_match.group(1)}")

            # Extract failures
            if '❌' in line and 'Failed' in line:
                self.stats['failed'] += 1

                # Track error
                ticker_match = re.search(r'❌\s+(\d{6})', line)
                if ticker_match:
                    self.errors.append(ticker_match.group(1))
                    self.recent_activity.append(f"❌ {ticker_match.group(1)}")

            # Extract skipped
            if '⚠️' in line and 'Skipped' in line:
                self.stats['skipped'] += 1

                ticker_match = re.search(r'⚠️\s+(\d{6})', line)
                if ticker_match:
                    self.recent_activity.append(f"⚠️  {ticker_match.group(1)}")

            # Extract API calls
            if 'API Calls:' in line:
                match = re.search(r'API Calls:\s*(\d+)', line)
                if match:
                    self.stats['api_calls'] = int(match.group(1))

            # Track last update
            timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if timestamp_match:
                self.stats['last_update'] = datetime.strptime(
                    timestamp_match.group(1), '%Y-%m-%d %H:%M:%S'
                )

        # Keep only recent activity (last 10)
        self.recent_activity = self.recent_activity[-10:]

    def calculate_progress(self) -> Dict:
        """
        Calculate progress metrics

        Returns:
            Dictionary with progress statistics
        """
        total = self.stats['total_tickers']
        processed = self.stats['processed']

        if total == 0:
            return {
                'percent_complete': 0.0,
                'remaining': 0,
                'elapsed_time': timedelta(0),
                'estimated_remaining': timedelta(0),
                'estimated_completion': None,
                'rate_per_hour': 0.0
            }

        percent_complete = (processed / total) * 100

        # Calculate time metrics
        if self.stats['start_time']:
            elapsed = datetime.now() - self.stats['start_time']
            rate_per_hour = (processed / elapsed.total_seconds()) * 3600 if processed > 0 else 0

            if processed > 0:
                avg_time_per_ticker = elapsed.total_seconds() / processed
                remaining = total - processed
                estimated_remaining = timedelta(seconds=avg_time_per_ticker * remaining)
                estimated_completion = datetime.now() + estimated_remaining
            else:
                estimated_remaining = timedelta(0)
                estimated_completion = None
        else:
            elapsed = timedelta(0)
            estimated_remaining = timedelta(0)
            estimated_completion = None
            rate_per_hour = 0.0

        return {
            'percent_complete': percent_complete,
            'remaining': total - processed,
            'elapsed_time': elapsed,
            'estimated_remaining': estimated_remaining,
            'estimated_completion': estimated_completion,
            'rate_per_hour': rate_per_hour
        }

    def format_progress_bar(self, percent: float, width: int = 50) -> str:
        """
        Create ASCII progress bar

        Args:
            percent: Completion percentage (0-100)
            width: Bar width in characters

        Returns:
            Formatted progress bar string
        """
        filled = int(width * percent / 100)
        bar = '█' * filled + '░' * (width - filled)

        if percent >= 100:
            color = Colors.OKGREEN
        elif percent >= 75:
            color = Colors.OKCYAN
        elif percent >= 50:
            color = Colors.OKBLUE
        else:
            color = Colors.WARNING

        return f"{color}{bar}{Colors.ENDC} {percent:>6.2f}%"

    def display_dashboard(self):
        """Display monitoring dashboard"""
        # Clear screen (works on Unix/Linux/Mac)
        os.system('clear' if os.name == 'posix' else 'cls')

        # Parse latest data
        try:
            self.parse_log_file()
        except Exception as e:
            print(f"{Colors.FAIL}Error parsing log file: {e}{Colors.ENDC}")
            return

        progress = self.calculate_progress()

        # Header
        print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 80}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.HEADER}WEEK 3 BACKFILL PROGRESS MONITOR{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 80}{Colors.ENDC}\n")

        # Log file info
        print(f"📄 Log File: {self.log_file}")
        if self.stats['last_update']:
            print(f"⏰ Last Update: {self.stats['last_update'].strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Progress overview
        print(f"{Colors.BOLD}📊 PROGRESS OVERVIEW{Colors.ENDC}")
        print(f"{'─' * 80}")

        total = self.stats['total_tickers']
        processed = self.stats['processed']

        print(f"Total Tickers:     {total:>6,}")
        print(f"Processed:         {processed:>6,} / {total:,}")
        print(f"Remaining:         {progress['remaining']:>6,}")
        print()

        # Progress bar
        print(f"Progress: {self.format_progress_bar(progress['percent_complete'])}")
        print()

        # Status breakdown
        print(f"{Colors.BOLD}✅ STATUS BREAKDOWN{Colors.ENDC}")
        print(f"{'─' * 80}")

        success_pct = (self.stats['success'] / processed * 100) if processed > 0 else 0
        failed_pct = (self.stats['failed'] / processed * 100) if processed > 0 else 0
        skipped_pct = (self.stats['skipped'] / processed * 100) if processed > 0 else 0

        print(f"{Colors.OKGREEN}✅ Success:{Colors.ENDC}  {self.stats['success']:>6,} ({success_pct:>6.1f}%)")
        print(f"{Colors.FAIL}❌ Failed:{Colors.ENDC}   {self.stats['failed']:>6,} ({failed_pct:>6.1f}%)")
        print(f"{Colors.WARNING}⚠️  Skipped:{Colors.ENDC}  {self.stats['skipped']:>6,} ({skipped_pct:>6.1f}%)")
        print()

        # Performance metrics
        print(f"{Colors.BOLD}⚡ PERFORMANCE METRICS{Colors.ENDC}")
        print(f"{'─' * 80}")

        print(f"Records Saved:     {self.stats['records_saved']:>10,}")
        print(f"API Calls:         {self.stats['api_calls']:>10,}")
        print(f"Rate:              {progress['rate_per_hour']:>10.1f} tickers/hour")
        print()

        # Time estimates
        print(f"{Colors.BOLD}⏱️  TIME ESTIMATES{Colors.ENDC}")
        print(f"{'─' * 80}")

        elapsed = progress['elapsed_time']
        print(f"Elapsed Time:      {str(elapsed).split('.')[0]}")

        if progress['estimated_remaining']:
            remaining = progress['estimated_remaining']
            print(f"Est. Remaining:    {str(remaining).split('.')[0]}")

        if progress['estimated_completion']:
            completion = progress['estimated_completion']
            print(f"Est. Completion:   {completion.strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Recent activity
        if self.recent_activity:
            print(f"{Colors.BOLD}📋 RECENT ACTIVITY (Last 10){Colors.ENDC}")
            print(f"{'─' * 80}")
            for activity in self.recent_activity:
                print(f"  {activity}")
            print()

        # Errors
        if self.errors:
            print(f"{Colors.BOLD}{Colors.FAIL}❌ FAILED TICKERS ({len(self.errors)}){Colors.ENDC}")
            print(f"{'─' * 80}")
            for error in self.errors[:10]:
                print(f"  {error}")
            if len(self.errors) > 10:
                print(f"  ... and {len(self.errors) - 10} more")
            print()

        print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 80}{Colors.ENDC}")
        print(f"Press Ctrl+C to exit")
        print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 80}{Colors.ENDC}\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Monitor backfill progress in real-time')
    parser.add_argument('--log', type=str, default='log/backfill_kr_week3_full_universe.log',
                       help='Path to backfill log file')
    parser.add_argument('--refresh', type=int, default=10,
                       help='Refresh interval in seconds (default: 10)')
    parser.add_argument('--once', action='store_true',
                       help='Display once and exit (no auto-refresh)')

    args = parser.parse_args()

    # Initialize monitor
    monitor = BackfillMonitor(args.log)

    try:
        if args.once:
            # Single display
            monitor.display_dashboard()
        else:
            # Auto-refresh loop
            while True:
                monitor.display_dashboard()
                time.sleep(args.refresh)

    except KeyboardInterrupt:
        print(f"\n{Colors.OKGREEN}✅ Monitor stopped{Colors.ENDC}\n")
        return 0

    except Exception as e:
        print(f"\n{Colors.FAIL}❌ Error: {e}{Colors.ENDC}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
