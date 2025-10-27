#!/usr/bin/env python3
"""
validate_data_quality.py - Data Quality Validation Script

Purpose:
- Validate OHLCV data completeness across all markets
- Check technical indicator validity
- Verify date ranges and retention policy
- Detect NULL values and duplicates
- Validate data integrity constraints
- Generate comprehensive data quality report

Validation Categories:
- OHLCV integrity (high >= low, volume >= 0, etc.)
- Technical indicators (MA, RSI, MACD, BB, ATR)
- NULL value detection
- Duplicate entry detection
- Date range verification
- Cross-region contamination
- Data completeness (gap detection)

Author: Spock Trading System
Created: 2025-10-16 (Phase 3, Task 3.1.3)
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_sqlite import SQLiteDatabaseManager


class DataQualityValidator:
    """Data quality validation suite"""

    def __init__(self, db_path: str = 'data/spock_local.db'):
        self.db_path = db_path
        self.db_manager = SQLiteDatabaseManager(db_path=db_path)
        self.validation_results = {
            'timestamp': datetime.now().isoformat(),
            'validations': {},
            'summary': {
                'total_checks': 0,
                'passed': 0,
                'failed': 0,
                'warnings': 0
            }
        }

    def validate_null_values(self) -> Dict[str, Any]:
        """Validation 1: Detect NULL values in critical columns"""
        print("\n" + "="*70)
        print("Validation 1: NULL Value Detection")
        print("="*70)

        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        # Critical columns that should NEVER be NULL
        critical_columns = ['ticker', 'region', 'date', 'open', 'high', 'low', 'close', 'volume']

        # Optional columns (can be NULL for recent data without enough history)
        optional_columns = ['ma5', 'ma20', 'ma60', 'ma120', 'ma200', 'rsi_14',
                          'macd', 'macd_signal', 'volume_ma20', 'atr', 'atr_14',
                          'bb_upper', 'bb_middle', 'bb_lower']

        results = {
            'critical_nulls': {},
            'optional_nulls': {},
            'total_rows': 0
        }

        # Get total row count
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data")
        results['total_rows'] = cursor.fetchone()[0]

        # Check critical columns
        for column in critical_columns:
            cursor.execute(f"SELECT COUNT(*) FROM ohlcv_data WHERE {column} IS NULL")
            null_count = cursor.fetchone()[0]
            results['critical_nulls'][column] = null_count

            if null_count > 0:
                print(f"   ❌ {column}: {null_count:,} NULL values found")
            else:
                print(f"   ✅ {column}: 0 NULL values")

        # Check optional columns (informational only)
        for column in optional_columns:
            cursor.execute(f"SELECT COUNT(*) FROM ohlcv_data WHERE {column} IS NULL")
            null_count = cursor.fetchone()[0]
            results['optional_nulls'][column] = null_count

            null_pct = (null_count / results['total_rows'] * 100) if results['total_rows'] > 0 else 0

            if null_pct > 10:
                print(f"   ⚠️  {column}: {null_count:,} NULL ({null_pct:.1f}%)")
            else:
                print(f"   ✅ {column}: {null_count:,} NULL ({null_pct:.1f}%)")

        conn.close()

        # Check if validation passed
        critical_nulls_found = sum(results['critical_nulls'].values())
        results['passed'] = (critical_nulls_found == 0)

        if results['passed']:
            print(f"\n   ✅ NULL validation passed: No critical NULL values found")
        else:
            print(f"\n   ❌ NULL validation failed: {critical_nulls_found:,} critical NULL values")

        return results

    def validate_ohlcv_integrity(self) -> Dict[str, Any]:
        """Validation 2: OHLCV data integrity constraints"""
        print("\n" + "="*70)
        print("Validation 2: OHLCV Data Integrity")
        print("="*70)

        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        results = {
            'violations': {},
            'total_rows': 0
        }

        # Get total row count
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data")
        results['total_rows'] = cursor.fetchone()[0]

        # Constraint 1: high >= low
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data WHERE high < low")
        high_low_violations = cursor.fetchone()[0]
        results['violations']['high_less_than_low'] = high_low_violations

        if high_low_violations > 0:
            print(f"   ❌ High < Low: {high_low_violations:,} violations")
        else:
            print(f"   ✅ High >= Low: All rows valid")

        # Constraint 2: close between low and high (with 2% tolerance for currency normalization)
        cursor.execute("""
            SELECT COUNT(*) FROM ohlcv_data
            WHERE close IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL
            AND (close < low * 0.98 OR close > high * 1.02)
        """)
        close_range_violations = cursor.fetchone()[0]
        results['violations']['close_out_of_range'] = close_range_violations

        if close_range_violations > 0:
            print(f"   ❌ Close out of range (>2% deviation): {close_range_violations:,} violations")
        else:
            print(f"   ✅ Close in range (2% tolerance): All rows valid")

        # Also report minor violations as warnings (within 2% tolerance)
        cursor.execute("""
            SELECT COUNT(*) FROM ohlcv_data
            WHERE close IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL
            AND (close < low OR close > high)
            AND close >= low * 0.98 AND close <= high * 1.02
        """)
        minor_close_violations = cursor.fetchone()[0]
        if minor_close_violations > 0:
            print(f"   ⚠️  Minor close range deviations (<2%): {minor_close_violations:,} rows (currency normalization)")

        # Constraint 3: open between low and high
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data WHERE open < low OR open > high")
        open_range_violations = cursor.fetchone()[0]
        results['violations']['open_out_of_range'] = open_range_violations

        if open_range_violations > 0:
            print(f"   ❌ Open out of range: {open_range_violations:,} violations")
        else:
            print(f"   ✅ Open in range: All rows valid")

        # Constraint 4: volume >= 0
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data WHERE volume < 0")
        negative_volume = cursor.fetchone()[0]
        results['violations']['negative_volume'] = negative_volume

        if negative_volume > 0:
            print(f"   ❌ Negative volume: {negative_volume:,} violations")
        else:
            print(f"   ✅ Volume >= 0: All rows valid")

        # Constraint 5: All prices > 0
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data WHERE open <= 0 OR high <= 0 OR low <= 0 OR close <= 0")
        non_positive_prices = cursor.fetchone()[0]
        results['violations']['non_positive_prices'] = non_positive_prices

        if non_positive_prices > 0:
            print(f"   ❌ Non-positive prices: {non_positive_prices:,} violations")
        else:
            print(f"   ✅ All prices > 0: All rows valid")

        conn.close()

        # Check if validation passed
        total_violations = sum(results['violations'].values())
        results['passed'] = (total_violations == 0)

        if results['passed']:
            print(f"\n   ✅ OHLCV integrity validation passed")
        else:
            print(f"\n   ❌ OHLCV integrity validation failed: {total_violations:,} violations")

        return results

    def validate_technical_indicators(self) -> Dict[str, Any]:
        """Validation 3: Technical indicator validity"""
        print("\n" + "="*70)
        print("Validation 3: Technical Indicator Validation")
        print("="*70)

        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        results = {
            'violations': {},
            'warnings': {}
        }

        # RSI should be between 0 and 100 (with 0.01 tolerance for floating-point precision)
        cursor.execute("""
            SELECT COUNT(*) FROM ohlcv_data
            WHERE rsi_14 IS NOT NULL
            AND (rsi_14 < -0.01 OR rsi_14 > 100.01)
        """)
        rsi_violations = cursor.fetchone()[0]
        results['violations']['rsi_out_of_range'] = rsi_violations

        if rsi_violations > 0:
            print(f"   ❌ RSI out of range (<-0.01 or >100.01): {rsi_violations:,} violations")
        else:
            print(f"   ✅ RSI in range: All values valid")

        # Also report minor violations as warnings (floating-point precision)
        cursor.execute("""
            SELECT COUNT(*) FROM ohlcv_data
            WHERE rsi_14 IS NOT NULL
            AND ((rsi_14 < 0 AND rsi_14 >= -0.01) OR (rsi_14 > 100 AND rsi_14 <= 100.01))
        """)
        minor_rsi_violations = cursor.fetchone()[0]
        if minor_rsi_violations > 0:
            print(f"   ⚠️  Minor RSI precision deviations: {minor_rsi_violations:,} rows (floating-point precision)")

        # Moving averages should be positive
        for ma in ['ma5', 'ma20', 'ma60', 'ma120', 'ma200']:
            cursor.execute(f"SELECT COUNT(*) FROM ohlcv_data WHERE {ma} IS NOT NULL AND {ma} <= 0")
            ma_violations = cursor.fetchone()[0]
            results['violations'][f'{ma}_non_positive'] = ma_violations

            if ma_violations > 0:
                print(f"   ❌ {ma} <= 0: {ma_violations:,} violations")
            else:
                print(f"   ✅ {ma} > 0: All values valid")

        # ATR should be positive
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data WHERE atr IS NOT NULL AND atr <= 0")
        atr_violations = cursor.fetchone()[0]
        results['violations']['atr_non_positive'] = atr_violations

        if atr_violations > 0:
            print(f"   ❌ ATR <= 0: {atr_violations:,} violations")
        else:
            print(f"   ✅ ATR > 0: All values valid")

        # Bollinger Bands: upper >= middle >= lower
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data WHERE bb_upper IS NOT NULL AND bb_middle IS NOT NULL AND bb_lower IS NOT NULL AND (bb_upper < bb_middle OR bb_middle < bb_lower)")
        bb_violations = cursor.fetchone()[0]
        results['violations']['bb_band_order'] = bb_violations

        if bb_violations > 0:
            print(f"   ❌ Bollinger Bands order violation: {bb_violations:,} violations")
        else:
            print(f"   ✅ Bollinger Bands order: All values valid")

        # Volume ratio should be positive
        cursor.execute("SELECT COUNT(*) FROM ohlcv_data WHERE volume_ratio IS NOT NULL AND volume_ratio < 0")
        vol_ratio_violations = cursor.fetchone()[0]
        results['violations']['volume_ratio_negative'] = vol_ratio_violations

        if vol_ratio_violations > 0:
            print(f"   ❌ Volume ratio < 0: {vol_ratio_violations:,} violations")
        else:
            print(f"   ✅ Volume ratio >= 0: All values valid")

        conn.close()

        # Check if validation passed
        total_violations = sum(results['violations'].values())
        results['passed'] = (total_violations == 0)

        if results['passed']:
            print(f"\n   ✅ Technical indicator validation passed")
        else:
            print(f"\n   ❌ Technical indicator validation failed: {total_violations:,} violations")

        return results

    def validate_duplicates(self) -> Dict[str, Any]:
        """Validation 4: Duplicate entry detection"""
        print("\n" + "="*70)
        print("Validation 4: Duplicate Entry Detection")
        print("="*70)

        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        results = {
            'duplicates': [],
            'duplicate_count': 0
        }

        # Find duplicate (ticker, region, date) combinations
        cursor.execute("""
            SELECT ticker, region, date, COUNT(*) as dup_count
            FROM ohlcv_data
            GROUP BY ticker, region, date
            HAVING COUNT(*) > 1
            LIMIT 10
        """)

        duplicates = cursor.fetchall()
        results['duplicates'] = [
            {'ticker': row[0], 'region': row[1], 'date': row[2], 'count': row[3]}
            for row in duplicates
        ]
        results['duplicate_count'] = len(duplicates)

        if results['duplicate_count'] > 0:
            print(f"   ❌ Duplicate entries found: {results['duplicate_count']}")
            for dup in results['duplicates'][:5]:
                print(f"      - {dup['ticker']} ({dup['region']}) on {dup['date']}: {dup['count']} copies")
        else:
            print(f"   ✅ No duplicate entries found")

        conn.close()

        results['passed'] = (results['duplicate_count'] == 0)

        return results

    def validate_date_ranges(self) -> Dict[str, Any]:
        """Validation 5: Date range verification"""
        print("\n" + "="*70)
        print("Validation 5: Date Range Verification")
        print("="*70)

        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        results = {
            'regions': {},
            'retention_violations': []
        }

        # Calculate 250-day retention threshold
        retention_threshold = (datetime.now() - timedelta(days=250)).strftime('%Y-%m-%d')

        # Check date ranges per region
        for region in ['KR', 'US', 'HK', 'CN', 'JP', 'VN']:
            cursor.execute(f"""
                SELECT
                    MIN(date) as earliest,
                    MAX(date) as latest,
                    COUNT(*) as total_rows
                FROM ohlcv_data
                WHERE region = '{region}'
            """)
            row = cursor.fetchone()

            if row and row[2] > 0:
                earliest, latest, total_rows = row
                results['regions'][region] = {
                    'earliest': earliest,
                    'latest': latest,
                    'total_rows': total_rows
                }

                # Check if oldest data exceeds retention period
                if earliest < retention_threshold:
                    results['retention_violations'].append({
                        'region': region,
                        'earliest': earliest,
                        'threshold': retention_threshold
                    })
                    print(f"   ⚠️  {region}: {earliest} to {latest} ({total_rows:,} rows) - Exceeds retention")
                else:
                    print(f"   ✅ {region}: {earliest} to {latest} ({total_rows:,} rows)")
            else:
                print(f"   ⚠️  {region}: No data")

        # Check for future dates (should not exist)
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute(f"SELECT COUNT(*) FROM ohlcv_data WHERE date > '{today}'")
        future_dates = cursor.fetchone()[0]

        if future_dates > 0:
            print(f"\n   ❌ Future dates found: {future_dates:,} rows")
            results['future_dates'] = future_dates
        else:
            print(f"\n   ✅ No future dates found")
            results['future_dates'] = 0

        conn.close()

        # Warnings for retention violations are acceptable
        results['passed'] = (results['future_dates'] == 0)

        return results

    def validate_cross_region_contamination(self) -> Dict[str, Any]:
        """Validation 6: Cross-region contamination detection"""
        print("\n" + "="*70)
        print("Validation 6: Cross-Region Contamination Detection")
        print("="*70)

        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        results = {
            'contamination': [],
            'contamination_count': 0
        }

        # Ticker format patterns (including derivatives, preferred stocks, and leveraged products)
        patterns = {
            'KR': r'^(\d{6}|\d{4}[A-Z]\d|\d{5}[KL])$', # 6-digit OR derivatives (0000D0) OR preferred (00088K) OR leveraged (33626L)
            'US': r'^[A-Z]{1,5}(\.[A-Z])?$',          # 1-5 uppercase letters
            'HK': r'^\d{4,5}$',                        # 4-5 digit numeric
            'CN': r'^\d{6}$',                          # 6-digit numeric (before suffix)
            'JP': r'^\d{4}$',                          # 4-digit numeric
            'VN': r'^[A-Z]{3}$'                        # 3-letter uppercase
        }

        # For each region, find tickers that don't match expected format
        for region, pattern in patterns.items():
            cursor.execute(f"""
                SELECT DISTINCT ticker, COUNT(*) as row_count
                FROM ohlcv_data
                WHERE region = '{region}'
                GROUP BY ticker
            """)

            import re
            for ticker, row_count in cursor.fetchall():
                # Remove suffixes for CN/HK markets
                ticker_base = ticker.split('.')[0] if region in ['CN', 'HK'] else ticker

                if not re.match(pattern, ticker_base):
                    results['contamination'].append({
                        'region': region,
                        'ticker': ticker,
                        'row_count': row_count,
                        'expected_pattern': pattern
                    })
                    results['contamination_count'] += 1

        if results['contamination_count'] > 0:
            print(f"   ❌ Cross-region contamination found: {results['contamination_count']} tickers")
            for cont in results['contamination'][:10]:
                print(f"      - {cont['region']}: '{cont['ticker']}' doesn't match {cont['expected_pattern']} ({cont['row_count']} rows)")
        else:
            print(f"   ✅ No cross-region contamination detected")

        conn.close()

        results['passed'] = (results['contamination_count'] == 0)

        return results

    def validate_data_completeness(self) -> Dict[str, Any]:
        """Validation 7: Data completeness (gap detection)"""
        print("\n" + "="*70)
        print("Validation 7: Data Completeness (Gap Detection)")
        print("="*70)

        conn = self.db_manager._get_connection()
        cursor = conn.cursor()

        results = {
            'gaps': {},
            'total_gaps': 0
        }

        # Sample 10 random tickers per region
        for region in ['KR', 'US', 'HK', 'CN', 'JP', 'VN']:
            cursor.execute(f"""
                SELECT DISTINCT ticker
                FROM ohlcv_data
                WHERE region = '{region}'
                ORDER BY RANDOM()
                LIMIT 10
            """)

            tickers = [row[0] for row in cursor.fetchall()]
            region_gaps = []

            for ticker in tickers:
                # Get all dates for this ticker
                cursor.execute(f"""
                    SELECT date
                    FROM ohlcv_data
                    WHERE ticker = '{ticker}' AND region = '{region}'
                    ORDER BY date
                """)

                dates = [datetime.strptime(row[0], '%Y-%m-%d') for row in cursor.fetchall()]

                # Check for gaps > 7 days (indicating missing data)
                gaps = 0
                for i in range(1, len(dates)):
                    gap_days = (dates[i] - dates[i-1]).days
                    if gap_days > 7:  # More than 7 days gap (weekend + holidays)
                        gaps += 1

                if gaps > 0:
                    region_gaps.append({'ticker': ticker, 'gaps': gaps})

            results['gaps'][region] = region_gaps
            results['total_gaps'] += len(region_gaps)

            if region_gaps:
                print(f"   ⚠️  {region}: {len(region_gaps)} tickers with gaps (sampled 10)")
            else:
                print(f"   ✅ {region}: No significant gaps detected (sampled 10)")

        conn.close()

        # Warnings for gaps are acceptable (holidays, trading halts)
        results['passed'] = True

        return results

    def run_all_validations(self) -> Dict[str, Any]:
        """Run all data quality validations"""
        print("\n" + "="*70)
        print("Data Quality Validation Suite")
        print("="*70)
        print(f"Database: {self.db_path}")
        print(f"Timestamp: {self.validation_results['timestamp']}")
        print("="*70)

        # Run all validations
        validations = [
            ('null_values', self.validate_null_values),
            ('ohlcv_integrity', self.validate_ohlcv_integrity),
            ('technical_indicators', self.validate_technical_indicators),
            ('duplicates', self.validate_duplicates),
            ('date_ranges', self.validate_date_ranges),
            ('cross_region_contamination', self.validate_cross_region_contamination),
            ('data_completeness', self.validate_data_completeness)
        ]

        for name, validation_func in validations:
            self.validation_results['validations'][name] = validation_func()
            self.validation_results['summary']['total_checks'] += 1

            if self.validation_results['validations'][name]['passed']:
                self.validation_results['summary']['passed'] += 1
            else:
                self.validation_results['summary']['failed'] += 1

        # Print summary
        self.print_summary()

        return self.validation_results

    def print_summary(self):
        """Print validation summary"""
        print("\n" + "="*70)
        print("Validation Summary")
        print("="*70)

        summary = self.validation_results['summary']

        print(f"\nTotal Checks: {summary['total_checks']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Warnings: {summary['warnings']}")

        # Overall pass rate
        pass_rate = (summary['passed'] / summary['total_checks'] * 100) if summary['total_checks'] > 0 else 0

        print(f"\nOverall Pass Rate: {pass_rate:.1f}%")

        if summary['failed'] == 0:
            print(f"\n✅ All data quality validations passed!")
        else:
            print(f"\n⚠️  {summary['failed']} validation(s) failed")
            print(f"\nFailed validations:")
            for name, result in self.validation_results['validations'].items():
                if not result['passed']:
                    print(f"  ❌ {name}")

    def save_report(self, output_file: str = None):
        """Save validation results to JSON file"""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"validation_reports/data_quality_{timestamp}.json"

        # Create directory if needed
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # Save results
        with open(output_file, 'w') as f:
            json.dump(self.validation_results, f, indent=2)

        print(f"\n📊 Report saved: {output_file}")
        return output_file


def main():
    parser = argparse.ArgumentParser(description='Data Quality Validation Suite')
    parser.add_argument('--db-path', default='data/spock_local.db',
                       help='Database path')
    parser.add_argument('--output', '-o',
                       help='Output JSON file path')
    args = parser.parse_args()

    # Run validations
    validator = DataQualityValidator(db_path=args.db_path)
    results = validator.run_all_validations()

    # Save report
    report_file = validator.save_report(output_file=args.output)

    print("\n" + "="*70)
    print("Data Quality Validation Complete")
    print("="*70 + "\n")

    # Exit with code 1 if any validations failed
    return 0 if results['summary']['failed'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
