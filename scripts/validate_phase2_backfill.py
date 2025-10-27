#!/usr/bin/env python3
"""
Phase 2 Full Backfill Validation Script

Purpose: Validate historical fundamental data backfill (FY2022-2024)
Author: Claude Code
Date: 2025-10-24

Usage:
    python3 scripts/validate_phase2_backfill.py --log logs/phase2_full_backfill_v3.log --report logs/phase2_validation_report.md
"""

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from modules.db_manager_postgres import PostgresDatabaseManager


class Phase2BackfillValidator:
    """Validator for Phase 2 historical fundamental data backfill"""

    def __init__(self, log_file: str, db_manager: PostgresDatabaseManager):
        self.log_file = Path(log_file)
        self.db = db_manager
        self.validation_results = {}

    def parse_log_file(self) -> Dict:
        """Parse backfill log file to extract statistics"""
        print("📊 Parsing log file...")

        stats = {
            'total_tickers': 0,
            'completed_tickers': 0,
            'skipped_tickers': 0,
            'failed_tickers': 0,
            'api_calls': 0,
            'api_errors': 0,
            'start_time': None,
            'end_time': None,
            'failed_ticker_list': [],
            'skipped_ticker_list': [],
        }

        if not self.log_file.exists():
            print(f"⚠️  Log file not found: {self.log_file}")
            return stats

        with open(self.log_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract total tickers
        match = re.search(r'Retrieved (\d+) KR tickers from database', content)
        if match:
            stats['total_tickers'] = int(match.group(1))

        # Extract completed tickers
        stats['completed_tickers'] = content.count('✅') - content.count('✅ PostgreSQL')  # Exclude DB connection log

        # Extract skipped tickers (corp code not found)
        skipped_matches = re.findall(r'⚠️\s+\[(\w+)\] Corp code not found', content)
        stats['skipped_tickers'] = len(skipped_matches)
        stats['skipped_ticker_list'] = skipped_matches

        # Extract API calls and errors
        api_calls_match = re.findall(r'API Calls: (\d+) \(Errors: (\d+)\)', content)
        if api_calls_match:
            last_call = api_calls_match[-1]
            stats['api_calls'] = int(last_call[0])
            stats['api_errors'] = int(last_call[1])

        # Extract start/end time
        timestamps = re.findall(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', content)
        if timestamps:
            stats['start_time'] = timestamps[0]
            stats['end_time'] = timestamps[-1]

        # Calculate failed tickers
        stats['failed_tickers'] = stats['total_tickers'] - stats['completed_tickers'] - stats['skipped_tickers']

        return stats

    def validate_database_records(self) -> Dict:
        """Validate database records for quality and completeness"""
        print("🔍 Validating database records...")

        validation = {
            'total_records': 0,
            'records_2022': 0,
            'records_2023': 0,
            'records_2024': 0,
            'revenue_zero_count': 0,
            'ebitda_zero_count': 0,
            'revenue_zero_tickers': [],
            'ebitda_zero_tickers': [],
            'unique_tickers': 0,
        }

        # Total records count
        query = """
            SELECT COUNT(*) as total
            FROM ticker_fundamentals
            WHERE fiscal_year >= 2022 AND fiscal_year <= 2024
        """
        results = self.db.execute_query(query)
        if results:
            validation['total_records'] = results[0]['total']

        # Records by year
        for year in [2022, 2023, 2024]:
            query = f"""
                SELECT COUNT(*) as count
                FROM ticker_fundamentals
                WHERE fiscal_year = {year}
            """
            results = self.db.execute_query(query)
            if results:
                validation[f'records_{year}'] = results[0]['count']

        # Revenue = 0 count
        query = """
            SELECT COUNT(*) as count,
                   array_agg(DISTINCT ticker) as tickers
            FROM ticker_fundamentals
            WHERE fiscal_year >= 2022
              AND fiscal_year <= 2024
              AND (revenue = 0 OR revenue IS NULL)
        """
        results = self.db.execute_query(query)
        if results and results[0]['count']:
            validation['revenue_zero_count'] = results[0]['count']
            validation['revenue_zero_tickers'] = results[0]['tickers'] or []

        # EBITDA = 0 count (excluding loss-making companies where negative EBITDA is valid)
        query = """
            SELECT COUNT(*) as count,
                   array_agg(DISTINCT ticker) as tickers
            FROM ticker_fundamentals
            WHERE fiscal_year >= 2022
              AND fiscal_year <= 2024
              AND ebitda = 0
              AND operating_profit > 0  -- Exclude loss-making companies
        """
        results = self.db.execute_query(query)
        if results and results[0]['count']:
            validation['ebitda_zero_count'] = results[0]['count']
            validation['ebitda_zero_tickers'] = results[0]['tickers'] or []

        # Unique tickers count
        query = """
            SELECT COUNT(DISTINCT ticker) as count
            FROM ticker_fundamentals
            WHERE fiscal_year >= 2022 AND fiscal_year <= 2024
        """
        results = self.db.execute_query(query)
        if results:
            validation['unique_tickers'] = results[0]['count']

        return validation

    def calculate_success_rate(self, log_stats: Dict, db_validation: Dict) -> Dict:
        """Calculate success rate and performance metrics"""
        print("📈 Calculating success rate...")

        metrics = {
            'success_rate': 0.0,
            'expected_records': 0,
            'actual_records': 0,
            'data_quality_score': 0.0,
            'avg_time_per_ticker': 0.0,
            'total_duration_minutes': 0.0,
        }

        # Success rate calculation
        total_tickers = log_stats['total_tickers']
        completed_tickers = log_stats['completed_tickers']

        if total_tickers > 0:
            metrics['success_rate'] = (completed_tickers / total_tickers) * 100

        # Expected vs actual records
        metrics['expected_records'] = completed_tickers * 3  # 3 years per ticker
        metrics['actual_records'] = db_validation['total_records']

        # Data quality score (based on Revenue=0 and EBITDA=0 issues)
        total_records = db_validation['total_records']
        if total_records > 0:
            revenue_quality = 1.0 - (db_validation['revenue_zero_count'] / total_records)
            ebitda_quality = 1.0 - (db_validation['ebitda_zero_count'] / total_records)
            metrics['data_quality_score'] = ((revenue_quality + ebitda_quality) / 2) * 100

        # Duration calculation
        if log_stats['start_time'] and log_stats['end_time']:
            start = datetime.strptime(log_stats['start_time'], '%Y-%m-%d %H:%M:%S')
            end = datetime.strptime(log_stats['end_time'], '%Y-%m-%d %H:%M:%S')
            duration = (end - start).total_seconds()
            metrics['total_duration_minutes'] = duration / 60

            if completed_tickers > 0:
                metrics['avg_time_per_ticker'] = duration / completed_tickers

        return metrics

    def generate_report(self, log_stats: Dict, db_validation: Dict, metrics: Dict, output_file: str):
        """Generate validation report in Markdown format"""
        print(f"📝 Generating validation report: {output_file}")

        report_lines = [
            "# Phase 2 Full Backfill Validation Report",
            "",
            f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Log File**: `{self.log_file}`",
            f"**Backfill Period**: FY2022 - FY2024",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            f"**Success Rate**: {metrics['success_rate']:.1f}% ({log_stats['completed_tickers']:,}/{log_stats['total_tickers']:,} tickers)",
            f"**Total Records**: {db_validation['total_records']:,} (Expected: {metrics['expected_records']:,})",
            f"**Data Quality Score**: {metrics['data_quality_score']:.1f}%",
            f"**Total Duration**: {metrics['total_duration_minutes']:.1f} minutes ({metrics['total_duration_minutes']/60:.1f} hours)",
            f"**Avg Time/Ticker**: {metrics['avg_time_per_ticker']:.1f} seconds",
            "",
            "---",
            "",
            "## Backfill Statistics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Tickers | {log_stats['total_tickers']:,} |",
            f"| Completed Tickers | {log_stats['completed_tickers']:,} |",
            f"| Skipped Tickers (No corp_code) | {log_stats['skipped_tickers']:,} |",
            f"| Failed Tickers | {log_stats['failed_tickers']:,} |",
            f"| API Calls | {log_stats['api_calls']:,} |",
            f"| API Errors | {log_stats['api_errors']:,} |",
            f"| Start Time | {log_stats['start_time']} |",
            f"| End Time | {log_stats['end_time']} |",
            "",
            "---",
            "",
            "## Database Validation",
            "",
            "### Records by Year",
            "",
            "| Year | Record Count |",
            "|------|--------------|",
            f"| 2022 | {db_validation['records_2022']:,} |",
            f"| 2023 | {db_validation['records_2023']:,} |",
            f"| 2024 | {db_validation['records_2024']:,} |",
            f"| **Total** | **{db_validation['total_records']:,}** |",
            "",
            f"**Unique Tickers**: {db_validation['unique_tickers']:,}",
            "",
            "### Data Quality Issues",
            "",
            "| Issue | Count | Status |",
            "|-------|-------|--------|",
            f"| Revenue = 0 | {db_validation['revenue_zero_count']:,} | {'⚠️ REVIEW' if db_validation['revenue_zero_count'] > 0 else '✅ OK'} |",
            f"| EBITDA = 0 (Operating Profit > 0) | {db_validation['ebitda_zero_count']:,} | {'⚠️ REVIEW' if db_validation['ebitda_zero_count'] > 0 else '✅ OK'} |",
            "",
        ]

        # Add Revenue=0 tickers if any
        if db_validation['revenue_zero_count'] > 0:
            report_lines.extend([
                "#### Revenue = 0 Tickers",
                "",
                "```",
                ", ".join(db_validation['revenue_zero_tickers'][:20]),  # Show first 20
            ])
            if len(db_validation['revenue_zero_tickers']) > 20:
                report_lines.append(f"... and {len(db_validation['revenue_zero_tickers']) - 20} more")
            report_lines.extend(["```", ""])

        # Add EBITDA=0 tickers if any
        if db_validation['ebitda_zero_count'] > 0:
            report_lines.extend([
                "#### EBITDA = 0 Tickers (Operating Profit > 0)",
                "",
                "```",
                ", ".join(db_validation['ebitda_zero_tickers'][:20]),  # Show first 20
            ])
            if len(db_validation['ebitda_zero_tickers']) > 20:
                report_lines.append(f"... and {len(db_validation['ebitda_zero_tickers']) - 20} more")
            report_lines.extend(["```", ""])

        # Add skipped tickers if any
        if log_stats['skipped_tickers'] > 0:
            report_lines.extend([
                "---",
                "",
                "## Skipped Tickers (No Corp Code Mapping)",
                "",
                f"**Total**: {log_stats['skipped_tickers']:,} tickers",
                "",
                "```",
                ", ".join(log_stats['skipped_ticker_list'][:30]),  # Show first 30
            ])
            if len(log_stats['skipped_ticker_list']) > 30:
                report_lines.append(f"... and {len(log_stats['skipped_ticker_list']) - 30} more")
            report_lines.extend(["```", ""])

        # Validation decision
        report_lines.extend([
            "---",
            "",
            "## Validation Decision",
            "",
        ])

        if metrics['success_rate'] >= 90 and metrics['data_quality_score'] >= 90:
            report_lines.extend([
                "### ✅ PASS",
                "",
                "**Criteria**:",
                f"- ✅ Success Rate ≥ 90%: **{metrics['success_rate']:.1f}%**",
                f"- ✅ Data Quality Score ≥ 90%: **{metrics['data_quality_score']:.1f}%**",
                f"- ✅ API Errors: **{log_stats['api_errors']}**",
                "",
                "**Recommendation**: Phase 2 backfill successfully completed. Proceed to Phase 3 (real-time data collection automation).",
            ])
        else:
            report_lines.extend([
                "### ⚠️ REVIEW REQUIRED",
                "",
                "**Issues**:",
            ])
            if metrics['success_rate'] < 90:
                report_lines.append(f"- ❌ Success Rate < 90%: **{metrics['success_rate']:.1f}%**")
            if metrics['data_quality_score'] < 90:
                report_lines.append(f"- ❌ Data Quality Score < 90%: **{metrics['data_quality_score']:.1f}%**")
            if log_stats['api_errors'] > 0:
                report_lines.append(f"- ⚠️ API Errors: **{log_stats['api_errors']}**")

            report_lines.extend([
                "",
                "**Recommendation**: Review data quality issues and re-run backfill for failed tickers.",
            ])

        report_lines.extend([
            "",
            "---",
            "",
            f"**Last Updated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Status**: Validation Complete",
            "",
        ])

        # Write report to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(report_lines))

        print(f"✅ Validation report saved to: {output_file}")

    def run_validation(self, report_file: str):
        """Run complete validation workflow"""
        print("=" * 80)
        print("🚀 Phase 2 Full Backfill Validation")
        print("=" * 80)
        print()

        # Step 1: Parse log file
        log_stats = self.parse_log_file()

        # Step 2: Validate database records
        db_validation = self.validate_database_records()

        # Step 3: Calculate metrics
        metrics = self.calculate_success_rate(log_stats, db_validation)

        # Step 4: Generate report
        self.generate_report(log_stats, db_validation, metrics, report_file)

        print()
        print("=" * 80)
        print("📊 Validation Summary")
        print("=" * 80)
        print(f"Success Rate: {metrics['success_rate']:.1f}%")
        print(f"Total Records: {db_validation['total_records']:,}")
        print(f"Data Quality Score: {metrics['data_quality_score']:.1f}%")
        print(f"Total Duration: {metrics['total_duration_minutes']:.1f} minutes")
        print()

        if metrics['success_rate'] >= 90 and metrics['data_quality_score'] >= 90:
            print("✅ VALIDATION PASSED")
        else:
            print("⚠️ VALIDATION REVIEW REQUIRED")

        print()
        print(f"📄 Full report: {report_file}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Validate Phase 2 full backfill results")
    parser.add_argument(
        '--log',
        type=str,
        default='logs/phase2_full_backfill_v3.log',
        help='Path to backfill log file'
    )
    parser.add_argument(
        '--report',
        type=str,
        default='logs/phase2_validation_report.md',
        help='Output validation report file (Markdown)'
    )

    args = parser.parse_args()

    # Initialize database manager
    db = PostgresDatabaseManager(database='quant_platform')

    # Run validation
    validator = Phase2BackfillValidator(log_file=args.log, db_manager=db)
    validator.run_validation(report_file=args.report)

    # Close database connection
    db.close()


if __name__ == '__main__':
    main()
