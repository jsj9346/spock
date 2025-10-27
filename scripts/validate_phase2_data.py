#!/usr/bin/env python3
"""
Phase 2 Data Validation Script

Purpose: Validate data quality after Phase 2 fundamental data backfill

Validation Checks:
1. Mathematical Consistency:
   - Gross Profit = Revenue - COGS (within 1% tolerance)
   - EBITDA = Operating Profit + Depreciation (within 1% tolerance)
   - Operating Expense = COGS + SG&A
   - EBITDA Margin = EBITDA / Revenue * 100

2. Data Completeness:
   - Core fields availability (Revenue, Operating Profit, Net Income)
   - Manufacturing fields (COGS, PP&E, Accounts Receivable)
   - Cash flow fields (Investing CF, Financing CF)

3. Data Quality:
   - No negative gross profit (unless justified)
   - Reasonable EBITDA margins (-50% to 100%)
   - Depreciation estimation success rate
   - NULL vs 0 distinction for industry-specific fields

4. Industry-Specific Validation:
   - Financial companies: Loan portfolio, NIM populated
   - Manufacturing companies: COGS, PP&E populated
   - All companies: Cash flows populated

Usage:
    # Validate all Phase 2 data
    python3 scripts/validate_phase2_data.py

    # Validate specific year range
    python3 scripts/validate_phase2_data.py --start-year 2022 --end-year 2024

    # Validate specific tickers
    python3 scripts/validate_phase2_data.py --tickers 005930,000660,105560

    # Generate detailed report
    python3 scripts/validate_phase2_data.py --verbose --output reports/phase2_validation.json

Author: Quant Investment Platform - Phase 2
Date: 2025-10-24
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import json
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from collections import defaultdict

from modules.db_manager_postgres import DatabaseManager
from loguru import logger

# Validation thresholds
TOLERANCE_PERCENT = 1.0  # 1% tolerance for calculations
MIN_EBITDA_MARGIN = -50.0  # Minimum reasonable EBITDA margin
MAX_EBITDA_MARGIN = 100.0  # Maximum reasonable EBITDA margin
MIN_DATA_COMPLETENESS = 0.85  # 85% minimum data completeness

class Phase2DataValidator:
    """Phase 2 fundamental data validation"""

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.validation_results = {
            'total_records': 0,
            'passed_records': 0,
            'failed_records': 0,
            'warnings': 0,
            'checks': {
                'mathematical_consistency': {},
                'data_completeness': {},
                'data_quality': {},
                'industry_specific': {}
            },
            'anomalies': [],
            'summary': {}
        }

    def validate_all(self,
                    start_year: Optional[int] = None,
                    end_year: Optional[int] = None,
                    tickers: Optional[List[str]] = None,
                    verbose: bool = False) -> Dict:
        """
        Run all validation checks

        Args:
            start_year: Start fiscal year (optional)
            end_year: End fiscal year (optional)
            tickers: List of specific tickers to validate (optional)
            verbose: Enable detailed logging

        Returns:
            Dict with validation results
        """
        logger.info("="*80)
        logger.info("🔍 Phase 2 Data Validation")
        logger.info("="*80)

        # Build query
        query = """
        SELECT
            ticker, region, fiscal_year, period_type,
            revenue, operating_profit, net_income,
            cogs, gross_profit, pp_e, depreciation, accounts_receivable,
            sga_expense, rd_expense, operating_expense,
            interest_income, interest_expense, loan_portfolio, npl_amount, nim,
            investing_cf, financing_cf, ebitda, ebitda_margin,
            total_assets, total_liabilities, total_equity,
            created_at, updated_at
        FROM ticker_fundamentals
        WHERE region = 'KR'
        """

        params = []

        if start_year and end_year:
            query += " AND fiscal_year BETWEEN %s AND %s"
            params.extend([start_year, end_year])

        if tickers:
            placeholders = ','.join(['%s'] * len(tickers))
            query += f" AND ticker IN ({placeholders})"
            params.extend(tickers)

        query += " ORDER BY ticker, fiscal_year DESC"

        # Execute query
        logger.info(f"Querying ticker_fundamentals...")
        self.db.execute_query(query, params)
        records = self.db.cursor.fetchall()

        if not records:
            logger.warning("⚠️ No records found for validation")
            return self.validation_results

        self.validation_results['total_records'] = len(records)
        logger.info(f"✅ Loaded {len(records)} records for validation\n")

        # Column names
        columns = [desc[0] for desc in self.db.cursor.description]

        # Convert to list of dicts
        records_dict = []
        for record in records:
            record_dict = dict(zip(columns, record))
            records_dict.append(record_dict)

        # Run validation checks
        logger.info("📊 Running validation checks...")
        logger.info("="*80)

        self._validate_mathematical_consistency(records_dict, verbose)
        self._validate_data_completeness(records_dict, verbose)
        self._validate_data_quality(records_dict, verbose)
        self._validate_industry_specific(records_dict, verbose)

        # Generate summary
        self._generate_summary()

        # Display results
        self._display_results(verbose)

        return self.validation_results

    def _validate_mathematical_consistency(self, records: List[Dict], verbose: bool):
        """Check 1: Mathematical consistency"""
        logger.info("\n🧮 Check 1: Mathematical Consistency")
        logger.info("-"*80)

        checks = {
            'gross_profit': {'passed': 0, 'failed': 0, 'na': 0},
            'ebitda': {'passed': 0, 'failed': 0, 'na': 0},
            'operating_expense': {'passed': 0, 'failed': 0, 'na': 0},
            'ebitda_margin': {'passed': 0, 'failed': 0, 'na': 0}
        }

        for record in records:
            ticker = record['ticker']
            year = record['fiscal_year']

            # 1.1 Gross Profit = Revenue - COGS
            revenue = record.get('revenue') or 0
            cogs = record.get('cogs') or 0
            gross_profit = record.get('gross_profit') or 0

            if revenue > 0 and cogs > 0 and gross_profit > 0:
                expected_gp = revenue - cogs
                diff_percent = abs(gross_profit - expected_gp) / expected_gp * 100

                if diff_percent <= TOLERANCE_PERCENT:
                    checks['gross_profit']['passed'] += 1
                else:
                    checks['gross_profit']['failed'] += 1
                    self.validation_results['anomalies'].append({
                        'ticker': ticker,
                        'year': year,
                        'check': 'gross_profit',
                        'expected': expected_gp,
                        'actual': gross_profit,
                        'diff_percent': diff_percent
                    })
                    if verbose:
                        logger.warning(f"  ⚠️ [{ticker}] {year}: Gross Profit mismatch ({diff_percent:.2f}%)")
            else:
                checks['gross_profit']['na'] += 1

            # 1.2 EBITDA = Operating Profit + Depreciation
            operating_profit = record.get('operating_profit') or 0
            depreciation = record.get('depreciation') or 0
            ebitda = record.get('ebitda') or 0

            if operating_profit != 0 and depreciation > 0 and ebitda > 0:
                expected_ebitda = operating_profit + depreciation
                diff_percent = abs(ebitda - expected_ebitda) / abs(expected_ebitda) * 100 if expected_ebitda != 0 else 0

                if diff_percent <= TOLERANCE_PERCENT:
                    checks['ebitda']['passed'] += 1
                else:
                    checks['ebitda']['failed'] += 1
                    self.validation_results['anomalies'].append({
                        'ticker': ticker,
                        'year': year,
                        'check': 'ebitda',
                        'expected': expected_ebitda,
                        'actual': ebitda,
                        'diff_percent': diff_percent
                    })
                    if verbose:
                        logger.warning(f"  ⚠️ [{ticker}] {year}: EBITDA mismatch ({diff_percent:.2f}%)")
            else:
                checks['ebitda']['na'] += 1

            # 1.3 Operating Expense = COGS + SG&A
            sga_expense = record.get('sga_expense') or 0
            operating_expense = record.get('operating_expense') or 0

            if cogs > 0 and sga_expense > 0 and operating_expense > 0:
                expected_opex = cogs + sga_expense
                diff_percent = abs(operating_expense - expected_opex) / expected_opex * 100

                if diff_percent <= TOLERANCE_PERCENT:
                    checks['operating_expense']['passed'] += 1
                else:
                    checks['operating_expense']['failed'] += 1
                    if verbose:
                        logger.warning(f"  ⚠️ [{ticker}] {year}: Operating Expense mismatch ({diff_percent:.2f}%)")
            else:
                checks['operating_expense']['na'] += 1

            # 1.4 EBITDA Margin = EBITDA / Revenue * 100
            ebitda_margin = record.get('ebitda_margin') or 0

            if revenue > 0 and ebitda > 0 and ebitda_margin > 0:
                expected_margin = (ebitda / revenue * 100)
                diff_percent = abs(ebitda_margin - expected_margin) / expected_margin * 100 if expected_margin != 0 else 0

                if diff_percent <= TOLERANCE_PERCENT:
                    checks['ebitda_margin']['passed'] += 1
                else:
                    checks['ebitda_margin']['failed'] += 1
                    if verbose:
                        logger.warning(f"  ⚠️ [{ticker}] {year}: EBITDA Margin mismatch ({diff_percent:.2f}%)")
            else:
                checks['ebitda_margin']['na'] += 1

        # Store results
        self.validation_results['checks']['mathematical_consistency'] = checks

        # Display summary
        for check_name, stats in checks.items():
            total = stats['passed'] + stats['failed']
            if total > 0:
                pass_rate = stats['passed'] / total * 100
                status = "✅" if pass_rate >= 95 else "⚠️" if pass_rate >= 85 else "❌"
                logger.info(f"  {status} {check_name}: {stats['passed']}/{total} passed ({pass_rate:.1f}%)")

    def _validate_data_completeness(self, records: List[Dict], verbose: bool):
        """Check 2: Data completeness"""
        logger.info("\n📋 Check 2: Data Completeness")
        logger.info("-"*80)

        field_groups = {
            'core': ['revenue', 'operating_profit', 'net_income'],
            'manufacturing': ['cogs', 'pp_e', 'accounts_receivable'],
            'retail': ['sga_expense'],
            'financial': ['interest_income', 'interest_expense'],
            'cash_flow': ['investing_cf', 'financing_cf'],
            'calculated': ['gross_profit', 'ebitda', 'ebitda_margin']
        }

        completeness = defaultdict(lambda: {'total': 0, 'populated': 0})

        for record in records:
            for group_name, fields in field_groups.items():
                for field in fields:
                    value = record.get(field)
                    completeness[field]['total'] += 1
                    if value is not None and value != 0:
                        completeness[field]['populated'] += 1

        # Store and display results
        for field, stats in sorted(completeness.items()):
            rate = stats['populated'] / stats['total'] * 100 if stats['total'] > 0 else 0
            status = "✅" if rate >= 85 else "⚠️" if rate >= 70 else "❌"

            self.validation_results['checks']['data_completeness'][field] = {
                'total': stats['total'],
                'populated': stats['populated'],
                'rate': rate
            }

            logger.info(f"  {status} {field}: {stats['populated']}/{stats['total']} ({rate:.1f}%)")

    def _validate_data_quality(self, records: List[Dict], verbose: bool):
        """Check 3: Data quality"""
        logger.info("\n🔍 Check 3: Data Quality")
        logger.info("-"*80)

        quality_checks = {
            'negative_gross_profit': 0,
            'unreasonable_ebitda_margin': 0,
            'depreciation_estimated': 0,
            'null_vs_zero_correct': 0
        }

        for record in records:
            ticker = record['ticker']
            year = record['fiscal_year']

            # 3.1 Negative gross profit (anomaly)
            gross_profit = record.get('gross_profit') or 0
            if gross_profit < 0:
                quality_checks['negative_gross_profit'] += 1
                self.validation_results['anomalies'].append({
                    'ticker': ticker,
                    'year': year,
                    'check': 'negative_gross_profit',
                    'value': gross_profit
                })
                if verbose:
                    logger.warning(f"  ⚠️ [{ticker}] {year}: Negative gross profit ({gross_profit:,.0f})")

            # 3.2 Unreasonable EBITDA margin
            ebitda_margin = record.get('ebitda_margin') or 0
            if ebitda_margin != 0 and (ebitda_margin < MIN_EBITDA_MARGIN or ebitda_margin > MAX_EBITDA_MARGIN):
                quality_checks['unreasonable_ebitda_margin'] += 1
                self.validation_results['anomalies'].append({
                    'ticker': ticker,
                    'year': year,
                    'check': 'unreasonable_ebitda_margin',
                    'value': ebitda_margin
                })
                if verbose:
                    logger.warning(f"  ⚠️ [{ticker}] {year}: Unreasonable EBITDA margin ({ebitda_margin:.1f}%)")

            # 3.3 Depreciation successfully estimated
            depreciation = record.get('depreciation') or 0
            if depreciation > 0:
                quality_checks['depreciation_estimated'] += 1

            # 3.4 NULL vs 0 distinction
            # Financial fields should be NULL for non-financial companies
            loan_portfolio = record.get('loan_portfolio')
            if loan_portfolio is None:
                quality_checks['null_vs_zero_correct'] += 1

        # Store and display
        self.validation_results['checks']['data_quality'] = quality_checks

        total_records = len(records)
        logger.info(f"  Negative Gross Profit: {quality_checks['negative_gross_profit']} ({quality_checks['negative_gross_profit']/total_records*100:.1f}%)")
        logger.info(f"  Unreasonable EBITDA Margin: {quality_checks['unreasonable_ebitda_margin']} ({quality_checks['unreasonable_ebitda_margin']/total_records*100:.1f}%)")
        logger.info(f"  Depreciation Estimated: {quality_checks['depreciation_estimated']}/{total_records} ({quality_checks['depreciation_estimated']/total_records*100:.1f}%)")
        logger.info(f"  NULL Handling Correct: {quality_checks['null_vs_zero_correct']}/{total_records} ({quality_checks['null_vs_zero_correct']/total_records*100:.1f}%)")

    def _validate_industry_specific(self, records: List[Dict], verbose: bool):
        """Check 4: Industry-specific validation"""
        logger.info("\n🏭 Check 4: Industry-Specific Validation")
        logger.info("-"*80)

        industry_stats = {
            'manufacturing': {'count': 0, 'cogs_populated': 0, 'ppe_populated': 0},
            'financial': {'count': 0, 'loan_populated': 0, 'nim_populated': 0},
            'all': {'count': 0, 'cf_populated': 0}
        }

        for record in records:
            # Identify industry by field availability
            loan_portfolio = record.get('loan_portfolio')
            cogs = record.get('cogs') or 0
            pp_e = record.get('pp_e') or 0

            # Financial company (has loan portfolio)
            if loan_portfolio is not None and loan_portfolio > 0:
                industry_stats['financial']['count'] += 1
                if loan_portfolio > 0:
                    industry_stats['financial']['loan_populated'] += 1
                nim = record.get('nim')
                if nim is not None:
                    industry_stats['financial']['nim_populated'] += 1

            # Manufacturing company (has COGS and PP&E)
            elif cogs > 0 or pp_e > 0:
                industry_stats['manufacturing']['count'] += 1
                if cogs > 0:
                    industry_stats['manufacturing']['cogs_populated'] += 1
                if pp_e > 0:
                    industry_stats['manufacturing']['ppe_populated'] += 1

            # All companies should have cash flows
            industry_stats['all']['count'] += 1
            investing_cf = record.get('investing_cf')
            financing_cf = record.get('financing_cf')
            if (investing_cf is not None and investing_cf != 0) or (financing_cf is not None and financing_cf != 0):
                industry_stats['all']['cf_populated'] += 1

        # Store and display
        self.validation_results['checks']['industry_specific'] = industry_stats

        logger.info(f"  Manufacturing Companies: {industry_stats['manufacturing']['count']}")
        if industry_stats['manufacturing']['count'] > 0:
            logger.info(f"    - COGS populated: {industry_stats['manufacturing']['cogs_populated']}/{industry_stats['manufacturing']['count']} ({industry_stats['manufacturing']['cogs_populated']/industry_stats['manufacturing']['count']*100:.1f}%)")
            logger.info(f"    - PP&E populated: {industry_stats['manufacturing']['ppe_populated']}/{industry_stats['manufacturing']['count']} ({industry_stats['manufacturing']['ppe_populated']/industry_stats['manufacturing']['count']*100:.1f}%)")

        logger.info(f"  Financial Companies: {industry_stats['financial']['count']}")
        if industry_stats['financial']['count'] > 0:
            logger.info(f"    - Loan Portfolio populated: {industry_stats['financial']['loan_populated']}/{industry_stats['financial']['count']} ({industry_stats['financial']['loan_populated']/industry_stats['financial']['count']*100:.1f}%)")
            logger.info(f"    - NIM populated: {industry_stats['financial']['nim_populated']}/{industry_stats['financial']['count']} ({industry_stats['financial']['nim_populated']/industry_stats['financial']['count']*100:.1f}%)")

        logger.info(f"  All Companies: {industry_stats['all']['count']}")
        logger.info(f"    - Cash Flows populated: {industry_stats['all']['cf_populated']}/{industry_stats['all']['count']} ({industry_stats['all']['cf_populated']/industry_stats['all']['count']*100:.1f}%)")

    def _generate_summary(self):
        """Generate overall validation summary"""
        total = self.validation_results['total_records']

        # Count passed/failed
        math_checks = self.validation_results['checks']['mathematical_consistency']
        passed = sum(check['passed'] for check in math_checks.values())
        failed = sum(check['failed'] for check in math_checks.values())

        self.validation_results['passed_records'] = passed
        self.validation_results['failed_records'] = failed
        self.validation_results['warnings'] = len(self.validation_results['anomalies'])

        # Overall pass rate
        total_checks = passed + failed
        pass_rate = (passed / total_checks * 100) if total_checks > 0 else 0

        self.validation_results['summary'] = {
            'total_records': total,
            'total_checks': total_checks,
            'pass_rate': pass_rate,
            'anomaly_count': len(self.validation_results['anomalies'])
        }

    def _display_results(self, verbose: bool):
        """Display validation results summary"""
        logger.info("\n" + "="*80)
        logger.info("📊 Validation Summary")
        logger.info("="*80)

        summary = self.validation_results['summary']
        logger.info(f"Total Records: {summary['total_records']}")
        logger.info(f"Total Checks: {summary['total_checks']}")
        logger.info(f"Pass Rate: {summary['pass_rate']:.1f}%")
        logger.info(f"Anomalies: {summary['anomaly_count']}")

        # Overall status
        if summary['pass_rate'] >= 95:
            logger.info("\n✅ Validation PASSED - Data quality is excellent")
        elif summary['pass_rate'] >= 85:
            logger.warning("\n⚠️ Validation PASSED with warnings - Review anomalies")
        else:
            logger.error("\n❌ Validation FAILED - Data quality issues detected")

        logger.info("="*80)

    def save_report(self, output_file: str):
        """Save validation report to JSON file"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.validation_results, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"📄 Validation report saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Phase 2 Data Validation')
    parser.add_argument('--start-year', type=int, help='Start fiscal year')
    parser.add_argument('--end-year', type=int, help='End fiscal year')
    parser.add_argument('--tickers', type=str, help='Comma-separated ticker list')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    parser.add_argument('--output', type=str, help='Output JSON report file')

    args = parser.parse_args()

    # Parse tickers
    tickers = args.tickers.split(',') if args.tickers else None

    # Initialize database
    db = DatabaseManager()

    try:
        # Run validation
        validator = Phase2DataValidator(db)
        results = validator.validate_all(
            start_year=args.start_year,
            end_year=args.end_year,
            tickers=tickers,
            verbose=args.verbose
        )

        # Save report if requested
        if args.output:
            validator.save_report(args.output)

        # Exit code based on validation result
        pass_rate = results['summary']['pass_rate']
        if pass_rate >= 85:
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        db.close()


if __name__ == '__main__':
    main()
