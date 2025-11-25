#!/usr/bin/env python3
"""
Validate pykrx Data Quality

This script validates pykrx fundamental data quality:
1. Coverage: % of OHLCV universe with fundamental data
2. Freshness: Data staleness (days since last update)
3. Anomalies: Unusual values (DPS, DIV, PER, PBR outliers)
4. Completeness: Missing fields by ticker

Usage:
    python3 scripts/validate_pykrx_data_quality.py
    python3 scripts/validate_pykrx_data_quality.py --show-anomalies
    python3 scripts/validate_pykrx_data_quality.py --export-csv

Author: Quant Investment Platform - Option B Validation
"""

import sys
import os
from datetime import datetime, date, timedelta
from typing import Dict, List
from loguru import logger
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logger.add(
    f"log/{datetime.now().strftime('%Y%m%d')}_pykrx_validation.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    level="INFO"
)


class PykrxDataValidator:
    """Validate pykrx fundamental data quality"""
    
    def __init__(self, db: PostgresDatabaseManager):
        self.db = db
        self.validation_results = {}
        
    def check_coverage(self) -> Dict:
        """Check coverage: % of OHLCV tickers with pykrx data"""
        
        logger.info("📊 Checking data coverage...")
        
        query = """
        WITH ohlcv_universe AS (
            SELECT DISTINCT ticker
            FROM ohlcv_data
            WHERE region = 'KR'
        ),
        pykrx_tickers AS (
            SELECT DISTINCT ticker
            FROM ticker_fundamentals
            WHERE region = 'KR'
              AND period_type = 'DAILY'
              AND data_source = 'pykrx'
        )
        SELECT
            (SELECT COUNT(*) FROM ohlcv_universe) as total_ohlcv_tickers,
            (SELECT COUNT(*) FROM pykrx_tickers) as pykrx_tickers,
            ROUND((SELECT COUNT(*) FROM pykrx_tickers)::numeric / 
                  (SELECT COUNT(*) FROM ohlcv_universe) * 100, 2) as coverage_pct
        """
        
        result = self.db.execute_query(query)
        
        if result:
            coverage = {
                'total_ohlcv_tickers': result[0]['total_ohlcv_tickers'],
                'pykrx_tickers': result[0]['pykrx_tickers'],
                'coverage_pct': float(result[0]['coverage_pct'])
            }
            
            logger.info(f"✅ Coverage: {coverage['pykrx_tickers']}/{coverage['total_ohlcv_tickers']} ({coverage['coverage_pct']}%)")
            
            # Target: ≥75% coverage
            if coverage['coverage_pct'] >= 75:
                logger.info("✅ Coverage target met (≥75%)")
            else:
                logger.warning(f"⚠️ Coverage below target: {coverage['coverage_pct']}% < 75%")
            
            self.validation_results['coverage'] = coverage
            return coverage
        
        return {}
    
    def check_freshness(self) -> Dict:
        """Check data freshness: days since last update"""
        
        logger.info("📅 Checking data freshness...")
        
        query = """
        SELECT
            MAX(date) as latest_date,
            CURRENT_DATE - MAX(date) as days_stale
        FROM ticker_fundamentals
        WHERE region = 'KR'
          AND period_type = 'DAILY'
          AND data_source = 'pykrx'
        """
        
        result = self.db.execute_query(query)
        
        if result:
            freshness = {
                'latest_date': str(result[0]['latest_date']),
                'days_stale': result[0]['days_stale']
            }
            
            logger.info(f"📅 Latest date: {freshness['latest_date']} ({freshness['days_stale']} days ago)")
            
            # Target: ≤3 days for DAILY data
            if freshness['days_stale'] <= 3:
                logger.info("✅ Data is fresh (≤3 days)")
            else:
                logger.warning(f"⚠️ Data is stale: {freshness['days_stale']} days old")
            
            self.validation_results['freshness'] = freshness
            return freshness
        
        return {}
    
    def check_anomalies(self, show_details: bool = False) -> Dict:
        """Detect anomalies: unusual values"""
        
        logger.info("🔍 Checking for anomalies...")
        
        # Check for unusually high dividend yields (>20%)
        query_high_div = """
        SELECT
            ticker,
            dividend_yield,
            dividend_per_share,
            date
        FROM ticker_fundamentals
        WHERE region = 'KR'
          AND period_type = 'DAILY'
          AND data_source = 'pykrx'
          AND dividend_yield > 20
        ORDER BY dividend_yield DESC
        LIMIT 50
        """
        
        high_div = self.db.execute_query(query_high_div)
        
        # Check for missing dividend_per_share despite dividend_yield > 0
        query_missing_dps = """
        SELECT COUNT(*) as count
        FROM ticker_fundamentals
        WHERE region = 'KR'
          AND period_type = 'DAILY'
          AND data_source = 'pykrx'
          AND dividend_yield > 0
          AND (dividend_per_share IS NULL OR dividend_per_share = 0)
        """
        
        missing_dps = self.db.execute_query(query_missing_dps)
        
        # Check for extreme PER values (<0 or >1000)
        query_extreme_per = """
        SELECT COUNT(*) as count
        FROM ticker_fundamentals
        WHERE region = 'KR'
          AND period_type = 'DAILY'
          AND data_source = 'pykrx'
          AND (per < 0 OR per > 1000)
        """
        
        extreme_per = self.db.execute_query(query_extreme_per)
        
        anomalies = {
            'high_dividend_yield_count': len(high_div),
            'missing_dps_count': missing_dps[0]['count'] if missing_dps else 0,
            'extreme_per_count': extreme_per[0]['count'] if extreme_per else 0
        }
        
        logger.info(f"🔍 Anomalies found:")
        logger.info(f"   High dividend yields (>20%): {anomalies['high_dividend_yield_count']}")
        logger.info(f"   Missing DPS: {anomalies['missing_dps_count']}")
        logger.info(f"   Extreme PER: {anomalies['extreme_per_count']}")
        
        if show_details and high_div:
            logger.info("\n📋 Top 10 High Dividend Yields:")
            logger.info("=" * 80)
            logger.info(f"{'Ticker':<8}{'Div Yield':<12}{'DPS':<12}{'Date':<12}")
            logger.info("=" * 80)
            
            for row in high_div[:10]:
                logger.info(
                    f"{row['ticker']:<8}"
                    f"{row['dividend_yield']:<12.2f}"
                    f"{row['dividend_per_share']:<12.0f}"
                    f"{str(row['date']):<12}"
                )
        
        self.validation_results['anomalies'] = anomalies
        return anomalies
    
    def check_completeness(self) -> Dict:
        """Check field completeness: % of records with non-null values"""
        
        logger.info("📈 Checking field completeness...")
        
        query = """
        SELECT
            COUNT(*) as total_records,
            SUM(CASE WHEN per IS NOT NULL THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100 as per_completeness,
            SUM(CASE WHEN pbr IS NOT NULL THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100 as pbr_completeness,
            SUM(CASE WHEN dividend_yield IS NOT NULL THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100 as div_yield_completeness,
            SUM(CASE WHEN dividend_per_share IS NOT NULL THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100 as dps_completeness
        FROM ticker_fundamentals
        WHERE region = 'KR'
          AND period_type = 'DAILY'
          AND data_source = 'pykrx'
        """
        
        result = self.db.execute_query(query)
        
        if result:
            completeness = {
                'total_records': result[0]['total_records'],
                'per_completeness': round(float(result[0]['per_completeness']), 2),
                'pbr_completeness': round(float(result[0]['pbr_completeness']), 2),
                'div_yield_completeness': round(float(result[0]['div_yield_completeness']), 2),
                'dps_completeness': round(float(result[0]['dps_completeness']), 2)
            }
            
            logger.info(f"📈 Field completeness (total records: {completeness['total_records']}):")
            logger.info(f"   PER: {completeness['per_completeness']}%")
            logger.info(f"   PBR: {completeness['pbr_completeness']}%")
            logger.info(f"   Dividend Yield: {completeness['div_yield_completeness']}%")
            logger.info(f"   DPS: {completeness['dps_completeness']}%")
            
            # Target: ≥95% completeness
            if all(v >= 95 for k, v in completeness.items() if k != 'total_records'):
                logger.info("✅ All fields meet completeness target (≥95%)")
            else:
                logger.warning("⚠️ Some fields below completeness target (<95%)")
            
            self.validation_results['completeness'] = completeness
            return completeness
        
        return {}
    
    def generate_report(self, export_csv: bool = False) -> None:
        """Generate validation summary report"""
        
        logger.info("\n" + "=" * 80)
        logger.info("pykrx Data Quality Validation Report")
        logger.info("=" * 80)
        
        # Overall status
        coverage_ok = self.validation_results.get('coverage', {}).get('coverage_pct', 0) >= 75
        freshness_ok = self.validation_results.get('freshness', {}).get('days_stale', 999) <= 3
        completeness_ok = all(
            v >= 95 for k, v in self.validation_results.get('completeness', {}).items() 
            if k != 'total_records'
        )
        
        overall_status = "✅ PASS" if all([coverage_ok, freshness_ok, completeness_ok]) else "⚠️ REVIEW NEEDED"
        
        logger.info(f"\n🎯 Overall Status: {overall_status}\n")
        
        # Summary
        logger.info("📊 Coverage:")
        logger.info(f"   {self.validation_results.get('coverage', {})}")
        
        logger.info("\n📅 Freshness:")
        logger.info(f"   {self.validation_results.get('freshness', {})}")
        
        logger.info("\n📈 Completeness:")
        logger.info(f"   {self.validation_results.get('completeness', {})}")
        
        logger.info("\n🔍 Anomalies:")
        logger.info(f"   {self.validation_results.get('anomalies', {})}")
        
        logger.info("\n" + "=" * 80)
        
        # Export to CSV if requested
        if export_csv:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"log/pykrx_validation_{timestamp}.csv"
            
            # Flatten validation results
            rows = []
            for category, data in self.validation_results.items():
                if isinstance(data, dict):
                    for key, value in data.items():
                        rows.append({
                            'category': category,
                            'metric': key,
                            'value': value
                        })
            
            df = pd.DataFrame(rows)
            df.to_csv(filename, index=False)
            logger.info(f"\n💾 Validation results exported to: {filename}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Validate pykrx data quality')
    parser.add_argument('--show-anomalies', action='store_true', help='Show detailed anomaly list')
    parser.add_argument('--export-csv', action='store_true', help='Export results to CSV')
    
    args = parser.parse_args()
    
    # Initialize database
    db = PostgresDatabaseManager()
    
    # Initialize validator
    validator = PykrxDataValidator(db)
    
    # Run validation checks
    validator.check_coverage()
    validator.check_freshness()
    validator.check_anomalies(show_details=args.show_anomalies)
    validator.check_completeness()
    
    # Generate report
    validator.generate_report(export_csv=args.export_csv)
    
    logger.info("\n✅ pykrx data quality validation complete!")


if __name__ == "__main__":
    main()
