#!/usr/bin/env python3
"""
KR OHLCV Data Quality Validation Script

Validates Korean market OHLCV data quality including:
1. Ticker coverage (expected: 3,745 tickers)
2. 250-day data requirement per ticker
3. Technical indicator completeness (MA, RSI, MACD, BB, ATR)
4. Data freshness (most recent trading day)
5. Data gaps and anomalies

Usage:
    python3 scripts/validate_kr_ohlcv_quality.py
    python3 scripts/validate_kr_ohlcv_quality.py --detailed
    python3 scripts/validate_kr_ohlcv_quality.py --export-report

Exit Codes:
    0: All validations passed
    1: Critical issues found (blocks trading)
    2: Warnings found (review recommended)
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import argparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_sqlite import SQLiteDatabaseManager


class KROHLCVQualityValidator:
    """Korean market OHLCV data quality validator"""

    def __init__(self, db: SQLiteDatabaseManager):
        self.db = db
        self.region = "KR"
        self.expected_ticker_count = 3745
        self.min_days_required = 250
        self.critical_issues = []
        self.warnings = []
        self.stats = {}

    def run_all_validations(self) -> Dict:
        """Run all validation checks"""
        print("=" * 80)
        print("KR OHLCV Data Quality Validation")
        print("=" * 80)
        print(f"Region: {self.region}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Database: {self.db.db_path}")
        print("=" * 80)

        # Run all validation checks
        self.validate_ticker_count()
        self.validate_data_coverage()
        self.validate_technical_indicators()
        self.validate_data_freshness()
        self.validate_data_gaps()
        self.validate_data_anomalies()

        # Generate summary
        return self.generate_summary()

    def validate_ticker_count(self):
        """Validate total ticker count"""
        print("\n📊 Validation 1: Ticker Count")
        print("-" * 80)

        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT COUNT(DISTINCT ticker)
            FROM ohlcv_data
            WHERE region = ?
        ''', (self.region,))

        actual_count = cursor.fetchone()[0]
        self.stats['ticker_count'] = actual_count

        if actual_count == 0:
            self.critical_issues.append("CRITICAL: No KR tickers found in database")
            print(f"❌ CRITICAL: No KR tickers found")
        elif actual_count < self.expected_ticker_count * 0.9:
            self.warnings.append(f"WARNING: Ticker count ({actual_count}) is significantly below expected ({self.expected_ticker_count})")
            print(f"⚠️  WARNING: {actual_count} tickers (expected: {self.expected_ticker_count})")
        else:
            print(f"✅ Ticker count: {actual_count} (expected: {self.expected_ticker_count})")

        conn.close()

    def validate_data_coverage(self):
        """Validate 250-day data coverage per ticker"""
        print("\n📅 Validation 2: Data Coverage (250-day requirement)")
        print("-" * 80)

        conn = self.db._get_connection()
        cursor = conn.cursor()

        # Get tickers with insufficient data
        cursor.execute('''
            SELECT ticker, COUNT(*) as day_count
            FROM ohlcv_data
            WHERE region = ?
            GROUP BY ticker
            HAVING day_count < ?
        ''', (self.region, self.min_days_required))

        insufficient_tickers = cursor.fetchall()

        if insufficient_tickers:
            self.warnings.append(f"WARNING: {len(insufficient_tickers)} tickers have < {self.min_days_required} days of data")
            print(f"⚠️  WARNING: {len(insufficient_tickers)} tickers with < {self.min_days_required} days")

            if len(insufficient_tickers) <= 10:
                print("\nTickers with insufficient data:")
                for ticker, count in insufficient_tickers:
                    print(f"  - {ticker}: {count} days")
        else:
            print(f"✅ All tickers have ≥ {self.min_days_required} days of data")

        # Get average coverage
        cursor.execute('''
            SELECT AVG(day_count) as avg_days, MIN(day_count) as min_days, MAX(day_count) as max_days
            FROM (
                SELECT COUNT(*) as day_count
                FROM ohlcv_data
                WHERE region = ?
                GROUP BY ticker
            )
        ''', (self.region,))

        avg_days, min_days, max_days = cursor.fetchone()
        self.stats['avg_days'] = avg_days
        self.stats['min_days'] = min_days
        self.stats['max_days'] = max_days

        print(f"\nCoverage statistics:")
        print(f"  Average: {avg_days:.1f} days")
        print(f"  Min: {min_days} days")
        print(f"  Max: {max_days} days")

        conn.close()

    def validate_technical_indicators(self):
        """Validate technical indicator completeness"""
        print("\n📈 Validation 3: Technical Indicator Completeness")
        print("-" * 80)

        conn = self.db._get_connection()
        cursor = conn.cursor()

        indicators = {
            'ma5': 'MA5',
            'ma20': 'MA20',
            'ma60': 'MA60',
            'ma120': 'MA120',
            'ma200': 'MA200',
            'rsi_14': 'RSI-14',
            'macd': 'MACD',
            'macd_signal': 'MACD Signal',
            'macd_hist': 'MACD Histogram',
            'bb_upper': 'BB Upper',
            'bb_middle': 'BB Middle',
            'bb_lower': 'BB Lower',
            'atr_14': 'ATR-14',
            'volume_ma20': 'Volume MA20',
            'volume_ratio': 'Volume Ratio'
        }

        # Get total row count for percentage calculation
        cursor.execute('SELECT COUNT(*) FROM ohlcv_data WHERE region = ?', (self.region,))
        total_rows = cursor.fetchone()[0]
        self.stats['total_rows'] = total_rows

        indicator_issues = []

        for col_name, display_name in indicators.items():
            cursor.execute(f'''
                SELECT COUNT(*)
                FROM ohlcv_data
                WHERE region = ? AND {col_name} IS NULL
            ''', (self.region,))

            null_count = cursor.fetchone()[0]
            null_pct = (null_count / total_rows * 100) if total_rows > 0 else 0

            if null_count > 0:
                if null_pct > 10:  # Critical if >10% NULL
                    self.critical_issues.append(f"CRITICAL: {display_name} has {null_count:,} NULL values ({null_pct:.2f}%)")
                    print(f"❌ {display_name}: {null_count:,} NULL ({null_pct:.2f}%)")
                else:
                    self.warnings.append(f"WARNING: {display_name} has {null_count:,} NULL values ({null_pct:.2f}%)")
                    print(f"⚠️  {display_name}: {null_count:,} NULL ({null_pct:.2f}%)")
                indicator_issues.append((display_name, null_count, null_pct))
            else:
                print(f"✅ {display_name}: Complete (0 NULL)")

        if not indicator_issues:
            print("\n🎉 All technical indicators are 100% complete!")

        conn.close()

    def validate_data_freshness(self):
        """Validate data is up-to-date"""
        print("\n🕐 Validation 4: Data Freshness")
        print("-" * 80)

        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT MAX(date) as latest_date
            FROM ohlcv_data
            WHERE region = ?
        ''', (self.region,))

        latest_date_str = cursor.fetchone()[0]

        if latest_date_str:
            latest_date = datetime.strptime(latest_date_str, '%Y-%m-%d')
            days_old = (datetime.now() - latest_date).days
            self.stats['latest_date'] = latest_date_str
            self.stats['days_old'] = days_old

            if days_old > 5:  # Critical if >5 days old
                self.critical_issues.append(f"CRITICAL: Data is {days_old} days old (latest: {latest_date_str})")
                print(f"❌ CRITICAL: Data is {days_old} days old")
            elif days_old > 2:  # Warning if >2 days old
                self.warnings.append(f"WARNING: Data is {days_old} days old (latest: {latest_date_str})")
                print(f"⚠️  WARNING: Data is {days_old} days old")
            else:
                print(f"✅ Data is fresh (latest: {latest_date_str}, {days_old} days old)")
        else:
            self.critical_issues.append("CRITICAL: No date information found")
            print(f"❌ CRITICAL: No date information found")

        conn.close()

    def validate_data_gaps(self):
        """Detect missing dates in data"""
        print("\n🔍 Validation 5: Data Gap Detection")
        print("-" * 80)

        conn = self.db._get_connection()
        cursor = conn.cursor()

        # Sample 10 tickers for gap detection
        cursor.execute('''
            SELECT DISTINCT ticker
            FROM ohlcv_data
            WHERE region = ?
            LIMIT 10
        ''', (self.region,))

        sample_tickers = [row[0] for row in cursor.fetchall()]

        total_gaps = 0

        for ticker in sample_tickers:
            cursor.execute('''
                SELECT date
                FROM ohlcv_data
                WHERE region = ? AND ticker = ?
                ORDER BY date ASC
            ''', (self.region, ticker))

            dates = [datetime.strptime(row[0], '%Y-%m-%d') for row in cursor.fetchall()]

            if len(dates) < 2:
                continue

            # Check for gaps >7 days (accounting for weekends/holidays)
            gaps = []
            for i in range(1, len(dates)):
                days_diff = (dates[i] - dates[i-1]).days
                if days_diff > 7:  # Suspicious gap
                    gaps.append((dates[i-1].strftime('%Y-%m-%d'), dates[i].strftime('%Y-%m-%d'), days_diff))
                    total_gaps += 1

            if gaps and len(gaps) <= 3:
                print(f"⚠️  {ticker}: {len(gaps)} gap(s) detected")
                for start, end, days in gaps:
                    print(f"     {start} → {end} ({days} days)")

        if total_gaps == 0:
            print(f"✅ No significant gaps detected in sample ({len(sample_tickers)} tickers)")
        elif total_gaps < 10:
            self.warnings.append(f"WARNING: {total_gaps} data gaps detected in sample")
        else:
            self.critical_issues.append(f"CRITICAL: {total_gaps} data gaps detected in sample")

        conn.close()

    def validate_data_anomalies(self):
        """Detect data anomalies (zero prices, extreme volumes)"""
        print("\n⚡ Validation 6: Data Anomaly Detection")
        print("-" * 80)

        conn = self.db._get_connection()
        cursor = conn.cursor()

        # Check for zero prices
        cursor.execute('''
            SELECT COUNT(*)
            FROM ohlcv_data
            WHERE region = ? AND (open = 0 OR high = 0 OR low = 0 OR close = 0)
        ''', (self.region,))

        zero_price_count = cursor.fetchone()[0]

        if zero_price_count > 0:
            self.critical_issues.append(f"CRITICAL: {zero_price_count} rows with zero prices detected")
            print(f"❌ CRITICAL: {zero_price_count} rows with zero prices")
        else:
            print(f"✅ No zero price anomalies")

        # Check for zero volumes
        cursor.execute('''
            SELECT COUNT(*)
            FROM ohlcv_data
            WHERE region = ? AND volume = 0
        ''', (self.region,))

        zero_volume_count = cursor.fetchone()[0]

        if zero_volume_count > 0:
            zero_volume_pct = (zero_volume_count / self.stats['total_rows'] * 100) if self.stats['total_rows'] > 0 else 0
            if zero_volume_pct > 1:
                self.warnings.append(f"WARNING: {zero_volume_count} rows ({zero_volume_pct:.2f}%) with zero volume")
                print(f"⚠️  WARNING: {zero_volume_count} rows with zero volume ({zero_volume_pct:.2f}%)")
            else:
                print(f"✅ Zero volume rows: {zero_volume_count} ({zero_volume_pct:.2f}%) - acceptable")
        else:
            print(f"✅ No zero volume anomalies")

        conn.close()

    def generate_summary(self) -> Dict:
        """Generate validation summary"""
        print("\n" + "=" * 80)
        print("Validation Summary")
        print("=" * 80)

        # Stats summary
        print("\n📊 Statistics:")
        print(f"  Total tickers: {self.stats.get('ticker_count', 'N/A')}")
        print(f"  Total OHLCV rows: {self.stats.get('total_rows', 'N/A'):,}")
        print(f"  Average coverage: {self.stats.get('avg_days', 0):.1f} days")
        print(f"  Min coverage: {self.stats.get('min_days', 'N/A')} days")
        print(f"  Max coverage: {self.stats.get('max_days', 'N/A')} days")
        print(f"  Latest data: {self.stats.get('latest_date', 'N/A')} ({self.stats.get('days_old', 'N/A')} days old)")

        # Issues summary
        print(f"\n🚨 Critical Issues: {len(self.critical_issues)}")
        for issue in self.critical_issues:
            print(f"  - {issue}")

        print(f"\n⚠️  Warnings: {len(self.warnings)}")
        for warning in self.warnings:
            print(f"  - {warning}")

        # Overall status
        print("\n" + "=" * 80)
        if self.critical_issues:
            print("❌ VALIDATION FAILED: Critical issues found")
            print("   → Trading is BLOCKED until issues are resolved")
            exit_code = 1
        elif self.warnings:
            print("⚠️  VALIDATION PASSED WITH WARNINGS")
            print("   → Trading is allowed, but review recommended")
            exit_code = 2
        else:
            print("✅ VALIDATION PASSED: All checks successful")
            print("   → Data quality is excellent, ready for trading")
            exit_code = 0

        print("=" * 80)

        return {
            'exit_code': exit_code,
            'stats': self.stats,
            'critical_issues': self.critical_issues,
            'warnings': self.warnings
        }


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Validate KR OHLCV data quality')
    parser.add_argument('--detailed', action='store_true', help='Show detailed validation results')
    parser.add_argument('--export-report', action='store_true', help='Export validation report to file')
    args = parser.parse_args()

    try:
        # Initialize database
        db = SQLiteDatabaseManager()
        print(f"✅ Database initialized: {db.db_path}")

        # Run validation
        validator = KROHLCVQualityValidator(db)
        result = validator.run_all_validations()

        # Export report if requested
        if args.export_report:
            report_path = Path(__file__).parent.parent / 'logs' / f'kr_ohlcv_validation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
            # TODO: Implement report export
            print(f"\n📝 Report export: {report_path} (TODO)")

        return result['exit_code']

    except Exception as e:
        print(f"\n❌ Validation failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
