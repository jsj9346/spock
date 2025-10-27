#!/usr/bin/env python3
"""
validate_kr_data_quality.py - Comprehensive Data Quality Validation

Purpose:
- Validate OHLCV data coverage (target: 250 days per ticker)
- Validate technical indicator completeness (target: <1% NULL)
- Detect data anomalies (gaps, outliers, missing values)
- Generate comprehensive quality report

Exit Codes:
- 0: All validations passed
- 1: Critical issues found (data coverage or indicator NULL rates)
- 2: Warnings found (minor data gaps or anomalies)
"""

import sys
import os
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = 'data/spock_local.db'
REGION = 'KR'

# Quality thresholds
TARGET_DAYS = 250
CRITICAL_DAYS_THRESHOLD = 200  # Minimum for MA200
EXCELLENT_NULL_THRESHOLD = 1.0  # <1% NULL is excellent
ACCEPTABLE_NULL_THRESHOLD = 5.0  # <5% NULL is acceptable

# Technical indicators
INDICATOR_COLUMNS = [
    'ma5', 'ma20', 'ma60', 'ma120', 'ma200',
    'rsi_14',
    'macd', 'macd_signal', 'macd_hist',
    'bb_upper', 'bb_middle', 'bb_lower',
    'atr', 'atr_14',
    'volume_ma20', 'volume_ratio'
]

# Critical indicators (required for LayeredScoringEngine)
CRITICAL_INDICATORS = ['ma120', 'ma200', 'rsi_14', 'atr_14']


def get_coverage_statistics(conn: sqlite3.Connection) -> Dict:
    """Get data coverage statistics per ticker"""
    cursor = conn.cursor()

    cursor.execute('''
        SELECT ticker,
               COUNT(*) as day_count,
               MIN(date) as first_date,
               MAX(date) as last_date
        FROM ohlcv_data
        WHERE region = ?
        GROUP BY ticker
        ORDER BY day_count ASC
    ''', (REGION,))

    results = cursor.fetchall()

    coverage_data = []
    for ticker, day_count, first_date, last_date in results:
        coverage_data.append({
            'ticker': ticker,
            'day_count': day_count,
            'first_date': first_date,
            'last_date': last_date
        })

    return {
        'total_tickers': len(coverage_data),
        'coverage_data': coverage_data,
        'avg_days': sum(d['day_count'] for d in coverage_data) / len(coverage_data) if coverage_data else 0,
        'min_days': min(d['day_count'] for d in coverage_data) if coverage_data else 0,
        'max_days': max(d['day_count'] for d in coverage_data) if coverage_data else 0
    }


def get_null_statistics(conn: sqlite3.Connection) -> Dict:
    """Get NULL statistics for each indicator"""
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM ohlcv_data WHERE region = ?', (REGION,))
    total_rows = cursor.fetchone()[0]

    null_stats = {}
    for col in INDICATOR_COLUMNS:
        cursor.execute(f'SELECT COUNT(*) FROM ohlcv_data WHERE region = ? AND {col} IS NULL', (REGION,))
        null_count = cursor.fetchone()[0]
        null_stats[col] = {
            'null_count': null_count,
            'null_rate': (null_count / total_rows * 100) if total_rows > 0 else 0
        }

    return {
        'total_rows': total_rows,
        'null_stats': null_stats
    }


def detect_data_gaps(conn: sqlite3.Connection, sample_size: int = 100) -> List[Dict]:
    """Detect gaps in time-series data (missing dates)"""
    cursor = conn.cursor()

    # Get random sample of tickers
    cursor.execute('SELECT DISTINCT ticker FROM ohlcv_data WHERE region = ? ORDER BY RANDOM() LIMIT ?', (REGION, sample_size))
    sample_tickers = [row[0] for row in cursor.fetchall()]

    gaps_detected = []

    for ticker in sample_tickers:
        cursor.execute('''
            SELECT date FROM ohlcv_data
            WHERE ticker = ? AND region = ?
            ORDER BY date ASC
        ''', (ticker, REGION))

        dates = [row[0] for row in cursor.fetchall()]

        if len(dates) < 2:
            continue

        # Convert to pandas datetime for gap detection
        date_series = pd.to_datetime(dates)
        date_range = pd.date_range(start=date_series.min(), end=date_series.max(), freq='D')

        # Find missing dates (excluding weekends)
        missing_dates = date_range.difference(date_series)
        weekday_missing = [d for d in missing_dates if d.weekday() < 5]  # Exclude Sat/Sun

        if len(weekday_missing) > 10:  # Report if >10 weekday gaps
            gaps_detected.append({
                'ticker': ticker,
                'total_gaps': len(weekday_missing),
                'first_gap': str(weekday_missing[0]),
                'last_gap': str(weekday_missing[-1])
            })

    return gaps_detected


def detect_outliers(conn: sqlite3.Connection, sample_size: int = 50) -> List[Dict]:
    """Detect price outliers (abnormal price movements)"""
    cursor = conn.cursor()

    # Get random sample of tickers
    cursor.execute('SELECT DISTINCT ticker FROM ohlcv_data WHERE region = ? ORDER BY RANDOM() LIMIT ?', (REGION, sample_size))
    sample_tickers = [row[0] for row in cursor.fetchall()]

    outliers_detected = []

    for ticker in sample_tickers:
        cursor.execute('''
            SELECT date, close FROM ohlcv_data
            WHERE ticker = ? AND region = ?
            ORDER BY date ASC
        ''', (ticker, REGION))

        data = cursor.fetchall()

        if len(data) < 20:
            continue

        df = pd.DataFrame(data, columns=['date', 'close'])
        df['pct_change'] = df['close'].pct_change()

        # Detect extreme movements (>20% single-day change)
        extreme_moves = df[abs(df['pct_change']) > 0.20]

        if len(extreme_moves) > 0:
            outliers_detected.append({
                'ticker': ticker,
                'extreme_moves': len(extreme_moves),
                'max_move': f"{extreme_moves['pct_change'].abs().max()*100:.1f}%",
                'dates': extreme_moves['date'].tolist()[:3]  # First 3 dates
            })

    return outliers_detected


def print_validation_report(coverage_stats: Dict, null_stats: Dict, gaps: List[Dict], outliers: List[Dict]) -> int:
    """Print comprehensive validation report and return exit code"""
    print("="*80)
    print("KR Market Data Quality Validation Report")
    print("="*80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Section 1: Data Coverage
    print(f"\n{'='*80}")
    print("1. DATA COVERAGE ANALYSIS")
    print(f"{'='*80}")
    print(f"Total tickers: {coverage_stats['total_tickers']:,}")
    print(f"Average coverage: {coverage_stats['avg_days']:.1f} days")
    print(f"Coverage range: {coverage_stats['min_days']} - {coverage_stats['max_days']} days")

    # Coverage distribution
    coverage_data = coverage_stats['coverage_data']
    below_critical = len([d for d in coverage_data if d['day_count'] < CRITICAL_DAYS_THRESHOLD])
    below_target = len([d for d in coverage_data if CRITICAL_DAYS_THRESHOLD <= d['day_count'] < TARGET_DAYS])
    at_target = len([d for d in coverage_data if d['day_count'] >= TARGET_DAYS])

    print(f"\n📊 Coverage Distribution:")
    print(f"   < {CRITICAL_DAYS_THRESHOLD} days (critical):     {below_critical:,} tickers ({below_critical/coverage_stats['total_tickers']*100:.1f}%)")
    print(f"   {CRITICAL_DAYS_THRESHOLD}-{TARGET_DAYS-1} days (acceptable): {below_target:,} tickers ({below_target/coverage_stats['total_tickers']*100:.1f}%)")
    print(f"   ≥ {TARGET_DAYS} days (target):      {at_target:,} tickers ({at_target/coverage_stats['total_tickers']*100:.1f}%)")

    # Show worst 10 tickers
    if below_critical > 0:
        print(f"\n⚠️  Worst 10 Tickers (insufficient data):")
        worst_10 = sorted(coverage_data, key=lambda x: x['day_count'])[:10]
        for d in worst_10:
            print(f"      {d['ticker']}: {d['day_count']} days ({d['first_date']} → {d['last_date']})")

    # Coverage assessment
    coverage_score = 0
    if coverage_stats['avg_days'] >= TARGET_DAYS:
        print(f"\n   ✅ EXCELLENT - Average coverage meets target ({TARGET_DAYS} days)")
        coverage_score = 0
    elif coverage_stats['avg_days'] >= CRITICAL_DAYS_THRESHOLD:
        print(f"\n   ⚠️  ACCEPTABLE - Average coverage above critical threshold ({CRITICAL_DAYS_THRESHOLD} days)")
        coverage_score = 1
    else:
        print(f"\n   ❌ CRITICAL - Average coverage below minimum threshold")
        coverage_score = 2

    # Section 2: Indicator Completeness
    print(f"\n{'='*80}")
    print("2. TECHNICAL INDICATOR COMPLETENESS")
    print(f"{'='*80}")
    print(f"Total OHLCV rows: {null_stats['total_rows']:,}")

    print(f"\n📊 Indicator NULL Rates:")
    print(f"\n   Moving Averages:")
    for col in ['ma5', 'ma20', 'ma60', 'ma120', 'ma200']:
        null_rate = null_stats['null_stats'][col]['null_rate']
        status = "✅" if null_rate < EXCELLENT_NULL_THRESHOLD else "⚠️ " if null_rate < ACCEPTABLE_NULL_THRESHOLD else "❌"
        print(f"      {status} {col.upper():8s}: {null_rate:6.2f}%  ({null_stats['null_stats'][col]['null_count']:,} NULL)")

    print(f"\n   Momentum & Trend:")
    for col in ['rsi_14', 'macd', 'macd_signal', 'macd_hist']:
        null_rate = null_stats['null_stats'][col]['null_rate']
        status = "✅" if null_rate < EXCELLENT_NULL_THRESHOLD else "⚠️ " if null_rate < ACCEPTABLE_NULL_THRESHOLD else "❌"
        print(f"      {status} {col.upper():12s}: {null_rate:6.2f}%  ({null_stats['null_stats'][col]['null_count']:,} NULL)")

    print(f"\n   Bollinger Bands:")
    for col in ['bb_upper', 'bb_middle', 'bb_lower']:
        null_rate = null_stats['null_stats'][col]['null_rate']
        status = "✅" if null_rate < EXCELLENT_NULL_THRESHOLD else "⚠️ " if null_rate < ACCEPTABLE_NULL_THRESHOLD else "❌"
        print(f"      {status} {col.upper():10s}: {null_rate:6.2f}%  ({null_stats['null_stats'][col]['null_count']:,} NULL)")

    print(f"\n   Volatility:")
    for col in ['atr', 'atr_14']:
        null_rate = null_stats['null_stats'][col]['null_rate']
        status = "✅" if null_rate < EXCELLENT_NULL_THRESHOLD else "⚠️ " if null_rate < ACCEPTABLE_NULL_THRESHOLD else "❌"
        print(f"      {status} {col.upper():8s}: {null_rate:6.2f}%  ({null_stats['null_stats'][col]['null_count']:,} NULL)")

    print(f"\n   Volume:")
    for col in ['volume_ma20', 'volume_ratio']:
        null_rate = null_stats['null_stats'][col]['null_rate']
        status = "✅" if null_rate < EXCELLENT_NULL_THRESHOLD else "⚠️ " if null_rate < ACCEPTABLE_NULL_THRESHOLD else "❌"
        print(f"      {status} {col.upper():13s}: {null_rate:6.2f}%  ({null_stats['null_stats'][col]['null_count']:,} NULL)")

    # Critical indicators assessment
    critical_score = 0
    critical_issues = []
    for col in CRITICAL_INDICATORS:
        null_rate = null_stats['null_stats'][col]['null_rate']
        if null_rate >= ACCEPTABLE_NULL_THRESHOLD:
            critical_issues.append(f"{col.upper()}: {null_rate:.2f}%")
            critical_score = max(critical_score, 2)
        elif null_rate >= EXCELLENT_NULL_THRESHOLD:
            critical_issues.append(f"{col.upper()}: {null_rate:.2f}%")
            critical_score = max(critical_score, 1)

    if critical_score == 0:
        print(f"\n   ✅ EXCELLENT - All critical indicators < {EXCELLENT_NULL_THRESHOLD}% NULL")
    elif critical_score == 1:
        print(f"\n   ⚠️  ACCEPTABLE - Some critical indicators have minor gaps")
        for issue in critical_issues:
            print(f"      - {issue}")
    else:
        print(f"\n   ❌ CRITICAL - High NULL rates in critical indicators")
        for issue in critical_issues:
            print(f"      - {issue}")

    # Section 3: Data Gap Detection
    print(f"\n{'='*80}")
    print("3. TIME-SERIES GAP DETECTION (Sample: 100 tickers)")
    print(f"{'='*80}")

    if len(gaps) == 0:
        print(f"   ✅ No significant gaps detected")
        gap_score = 0
    elif len(gaps) <= 5:
        print(f"   ⚠️  Minor gaps detected in {len(gaps)} tickers:")
        for gap in gaps[:5]:
            print(f"      - {gap['ticker']}: {gap['total_gaps']} weekday gaps ({gap['first_gap']} → {gap['last_gap']})")
        gap_score = 1
    else:
        print(f"   ⚠️  Gaps detected in {len(gaps)} tickers (showing first 5):")
        for gap in gaps[:5]:
            print(f"      - {gap['ticker']}: {gap['total_gaps']} weekday gaps ({gap['first_gap']} → {gap['last_gap']})")
        gap_score = 1

    # Section 4: Price Outlier Detection
    print(f"\n{'='*80}")
    print("4. PRICE OUTLIER DETECTION (Sample: 50 tickers)")
    print(f"{'='*80}")

    if len(outliers) == 0:
        print(f"   ✅ No extreme price movements detected")
        outlier_score = 0
    elif len(outliers) <= 3:
        print(f"   ℹ️  Minor outliers detected in {len(outliers)} tickers:")
        for outlier in outliers:
            print(f"      - {outlier['ticker']}: {outlier['extreme_moves']} extreme moves (max: {outlier['max_move']})")
        outlier_score = 0  # Outliers are informational, not critical
    else:
        print(f"   ℹ️  Outliers detected in {len(outliers)} tickers (showing first 3):")
        for outlier in outliers[:3]:
            print(f"      - {outlier['ticker']}: {outlier['extreme_moves']} extreme moves (max: {outlier['max_move']})")
        outlier_score = 0  # Outliers are informational, not critical

    # Final Assessment
    print(f"\n{'='*80}")
    print("FINAL ASSESSMENT")
    print(f"{'='*80}")

    overall_score = max(coverage_score, critical_score, gap_score, outlier_score)

    if overall_score == 0:
        print(f"✅ EXCELLENT - All validations passed")
        print(f"✅ Data quality is ready for LayeredScoringEngine execution")
        exit_code = 0
    elif overall_score == 1:
        print(f"⚠️  ACCEPTABLE - Minor issues detected")
        print(f"⚠️  Data is usable but may have minor gaps or NULL values")
        exit_code = 2
    else:
        print(f"❌ CRITICAL - Major issues detected")
        print(f"❌ Data collection or indicator recalculation may be required")
        exit_code = 1

    # Recommendations
    print(f"\n📋 Recommendations:")
    if coverage_score == 2:
        print(f"   1. Run full historical data collection to increase coverage to {TARGET_DAYS} days")
    if critical_score >= 1:
        print(f"   2. Run technical indicator recalculation to fix NULL values")
    if coverage_score == 0 and critical_score == 0:
        print(f"   ✅ No action required - proceed with LayeredScoringEngine execution")

    print(f"\n{'='*80}")

    return exit_code


def main():
    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    print("Starting KR market data quality validation...\n")

    # 1. Coverage statistics
    print("📊 Analyzing data coverage...")
    coverage_stats = get_coverage_statistics(conn)

    # 2. NULL statistics
    print("📊 Analyzing indicator completeness...")
    null_stats = get_null_statistics(conn)

    # 3. Gap detection
    print("📊 Detecting time-series gaps (sample: 100 tickers)...")
    gaps = detect_data_gaps(conn, sample_size=100)

    # 4. Outlier detection
    print("📊 Detecting price outliers (sample: 50 tickers)...")
    outliers = detect_outliers(conn, sample_size=50)

    # Generate report
    exit_code = print_validation_report(coverage_stats, null_stats, gaps, outliers)

    conn.close()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
