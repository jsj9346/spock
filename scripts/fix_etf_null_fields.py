#!/usr/bin/env python3
"""
ETF NULL Fields Troubleshooting and Fix Script

Diagnoses and fixes NULL values in etf_details table for the following fields:
1. underlying_asset_class
2. geographic_region
3. sector_theme
4. leverage_ratio
5. currency_hedged
6. tracking_error_20d/60d/120d/250d
7. underlying_asset_count (KIS API limitation - manual inference)
8. week_52_high/week_52_low (calculated from OHLCV data)
9. pension_eligible (manual inference from tracking_index)
10. investment_strategy (manual inference from fund_type)

Root Cause Analysis:
- Fields 1-5: Inference logic exists but not executed after ETF scanning
- Fields 6: Tracking error collection requires separate API call
- Fields 7-10: No automated collection logic (requires inference)

Solution Strategy:
1. Run infer_etf_fields.py for fields 1-5
2. Run collect_etf_tracking_error() for fields 6
3. Calculate week_52_high/low from existing OHLCV data
4. Infer pension_eligible and investment_strategy from existing data

Author: Spock Trading System
"""

import sys
import os
import logging
from datetime import datetime
from typing import Dict, Optional

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.market_adapters import KoreaAdapter
from scripts.infer_etf_fields import ETFFieldInferenceEngine

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'logs/{datetime.now().strftime("%Y%m%d")}_etf_null_fix.log')
    ]
)
logger = logging.getLogger(__name__)


class ETFNullFieldsFixer:
    """Comprehensive ETF NULL fields troubleshooting and fixing"""

    def __init__(self, db: SQLiteDatabaseManager, kr_adapter: Optional[KoreaAdapter] = None):
        self.db = db
        self.kr_adapter = kr_adapter
        self.inference_engine = ETFFieldInferenceEngine(db=db)

    def diagnose_null_fields(self) -> Dict:
        """
        Diagnose NULL fields in etf_details table

        Returns:
            Dictionary with NULL counts per field
        """
        logger.info("=" * 80)
        logger.info("🔍 DIAGNOSING ETF NULL FIELDS")
        logger.info("=" * 80)

        conn = self.db._get_connection()
        cursor = conn.cursor()

        # Get total ETF count
        cursor.execute("SELECT COUNT(*) as count FROM etf_details")
        total_etfs = cursor.fetchone()['count']

        logger.info(f"📊 Total ETFs in database: {total_etfs}")
        logger.info("")

        # Check NULL counts for each field
        null_fields = {
            'underlying_asset_class': 0,
            'geographic_region': 0,
            'sector_theme': 0,
            'leverage_ratio': 0,
            'currency_hedged': 0,
            'tracking_error_20d': 0,
            'tracking_error_60d': 0,
            'tracking_error_120d': 0,
            'tracking_error_250d': 0,
            'underlying_asset_count': 0,
            'week_52_high': 0,
            'week_52_low': 0,
            'pension_eligible': 0,
            'investment_strategy': 0,
        }

        for field in null_fields.keys():
            cursor.execute(f"""
                SELECT COUNT(*) as count
                FROM etf_details
                WHERE {field} IS NULL
            """)
            null_count = cursor.fetchone()['count']
            null_fields[field] = null_count

            percent = (null_count / total_etfs * 100) if total_etfs > 0 else 0
            status = "❌" if null_count > 0 else "✅"
            logger.info(f"{status} {field}: {null_count}/{total_etfs} NULL ({percent:.1f}%)")

        conn.close()

        logger.info("")
        logger.info("=" * 80)

        return null_fields

    def fix_inferred_fields(self, dry_run: bool = False) -> int:
        """
        Fix fields 1-5 using inference engine

        Returns:
            Number of ETFs updated
        """
        logger.info("=" * 80)
        logger.info("🔧 FIXING INFERRED FIELDS (1-5)")
        logger.info("=" * 80)
        logger.info("Fields: underlying_asset_class, geographic_region, sector_theme,")
        logger.info("        leverage_ratio, currency_hedged")
        logger.info("")

        if dry_run:
            logger.info("🔍 DRY RUN MODE: Simulation only")
            logger.info("")

        success, failed = self.inference_engine.process_all_etfs(dry_run=dry_run)

        logger.info("")
        logger.info(f"✅ Inferred fields fix complete: {success} ETFs processed")
        logger.info("=" * 80)

        return success

    def fix_tracking_errors(self, dry_run: bool = False) -> int:
        """
        Fix tracking error fields (6) using KIS ETF API

        Returns:
            Number of ETFs updated
        """
        logger.info("=" * 80)
        logger.info("🔧 FIXING TRACKING ERROR FIELDS (6)")
        logger.info("=" * 80)
        logger.info("Fields: tracking_error_20d, tracking_error_60d,")
        logger.info("        tracking_error_120d, tracking_error_250d")
        logger.info("")

        if not self.kr_adapter:
            logger.warning("⚠️ KoreaAdapter not provided - skipping tracking error fix")
            return 0

        if dry_run:
            logger.info("🔍 DRY RUN MODE: Simulation only")
            logger.info("")
            return 0

        # Collect tracking errors for all ETFs
        success_count = self.kr_adapter.collect_etf_tracking_error()

        logger.info("")
        logger.info(f"✅ Tracking error fix complete: {success_count} ETFs updated")
        logger.info("=" * 80)

        return success_count

    def fix_week_52_high_low(self, dry_run: bool = False) -> int:
        """
        Fix week_52_high and week_52_low from existing OHLCV data

        Returns:
            Number of ETFs updated
        """
        logger.info("=" * 80)
        logger.info("🔧 FIXING 52-WEEK HIGH/LOW FIELDS (7)")
        logger.info("=" * 80)
        logger.info("Fields: week_52_high, week_52_low")
        logger.info("Source: Calculated from OHLCV data (250 days)")
        logger.info("")

        if dry_run:
            logger.info("🔍 DRY RUN MODE: Simulation only")
            logger.info("")

        # Get all ETFs
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ticker
            FROM tickers
            WHERE region = 'KR' AND asset_type = 'ETF' AND is_active = 1
        """)
        etfs = [row['ticker'] for row in cursor.fetchall()]
        conn.close()

        logger.info(f"📊 Processing {len(etfs)} ETFs...")
        logger.info("")

        success_count = 0

        for idx, ticker in enumerate(etfs, 1):
            try:
                # Get OHLCV data for last 250 days
                conn = self.db._get_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT MAX(high) as week_52_high, MIN(low) as week_52_low
                    FROM (
                        SELECT high, low
                        FROM ohlcv_data
                        WHERE ticker = ? AND timeframe = 'D'
                        ORDER BY date DESC
                        LIMIT 250
                    )
                """, (ticker,))

                result = cursor.fetchone()
                conn.close()

                if not result or not result['week_52_high']:
                    continue

                week_52_high = int(result['week_52_high'])
                week_52_low = int(result['week_52_low'])

                if not dry_run:
                    self.db.update_etf_details(ticker, {
                        'week_52_high': week_52_high,
                        'week_52_low': week_52_low,
                    })

                success_count += 1

                if idx % 100 == 0:
                    logger.info(f"📊 Progress: {idx}/{len(etfs)} ETFs")

            except Exception as e:
                logger.error(f"❌ [{ticker}] 52-week calculation failed: {e}")

        logger.info("")
        logger.info(f"✅ 52-week high/low fix complete: {success_count} ETFs updated")
        logger.info("=" * 80)

        return success_count

    def fix_pension_eligible(self, dry_run: bool = False) -> int:
        """
        Fix pension_eligible field based on tracking_index

        Korean pension-eligible ETFs typically track major indices:
        - KOSPI 200
        - MSCI Korea
        - S&P 500
        - NASDAQ 100
        - etc.

        Returns:
            Number of ETFs updated
        """
        logger.info("=" * 80)
        logger.info("🔧 FIXING PENSION ELIGIBLE FIELD (8)")
        logger.info("=" * 80)
        logger.info("Field: pension_eligible")
        logger.info("Logic: Major index tracking ETFs = pension eligible")
        logger.info("")

        if dry_run:
            logger.info("🔍 DRY RUN MODE: Simulation only")
            logger.info("")

        # Pension-eligible index keywords
        pension_indices = [
            'KOSPI 200', 'KOSPI200', 'KOSDAQ 150', 'KOSDAQ150',
            'S&P 500', 'S&P500', 'NASDAQ 100', 'NASDAQ-100',
            'MSCI Korea', 'MSCI World', 'MSCI ACWI',
            'Russell', 'Dow Jones',
        ]

        # Get all ETFs
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ticker, tracking_index
            FROM etf_details
            WHERE tracking_index IS NOT NULL
        """)
        etfs = [dict(row) for row in cursor.fetchall()]
        conn.close()

        logger.info(f"📊 Processing {len(etfs)} ETFs...")
        logger.info("")

        success_count = 0

        for idx, etf in enumerate(etfs, 1):
            try:
                ticker = etf['ticker']
                tracking_index = etf['tracking_index'] or ''

                # Check if tracking index matches pension-eligible criteria
                is_pension_eligible = any(
                    pension_idx in tracking_index for pension_idx in pension_indices
                )

                if not dry_run:
                    self.db.update_etf_details(ticker, {
                        'pension_eligible': is_pension_eligible,
                    })

                success_count += 1

                if idx % 100 == 0:
                    logger.info(f"📊 Progress: {idx}/{len(etfs)} ETFs")

            except Exception as e:
                logger.error(f"❌ [{ticker}] Pension eligibility inference failed: {e}")

        logger.info("")
        logger.info(f"✅ Pension eligible fix complete: {success_count} ETFs updated")
        logger.info("=" * 80)

        return success_count

    def fix_investment_strategy(self, dry_run: bool = False) -> int:
        """
        Fix investment_strategy field based on fund_type and ETF characteristics

        Strategy mapping:
        - index → Passive Index Tracking
        - sector → Sector Focused
        - thematic → Thematic Investing
        - commodity → Commodity Exposure
        - leverage → Leveraged Growth
        - inverse → Inverse/Short Strategy

        Returns:
            Number of ETFs updated
        """
        logger.info("=" * 80)
        logger.info("🔧 FIXING INVESTMENT STRATEGY FIELD (9)")
        logger.info("=" * 80)
        logger.info("Field: investment_strategy")
        logger.info("Logic: Derived from fund_type classification")
        logger.info("")

        if dry_run:
            logger.info("🔍 DRY RUN MODE: Simulation only")
            logger.info("")

        # Strategy mapping
        strategy_map = {
            'index': 'Passive Index Tracking',
            'sector': 'Sector Focused',
            'thematic': 'Thematic Investing',
            'commodity': 'Commodity Exposure',
            'leverage': 'Leveraged Growth',
            'inverse': 'Inverse/Short Strategy',
        }

        # Get all ETFs
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ticker, fund_type
            FROM etf_details
            WHERE fund_type IS NOT NULL
        """)
        etfs = [dict(row) for row in cursor.fetchall()]
        conn.close()

        logger.info(f"📊 Processing {len(etfs)} ETFs...")
        logger.info("")

        success_count = 0

        for idx, etf in enumerate(etfs, 1):
            try:
                ticker = etf['ticker']
                fund_type = etf['fund_type']

                # Map fund_type to investment strategy
                strategy = strategy_map.get(fund_type, 'Passive Index Tracking')

                if not dry_run:
                    self.db.update_etf_details(ticker, {
                        'investment_strategy': strategy,
                    })

                success_count += 1

                if idx % 100 == 0:
                    logger.info(f"📊 Progress: {idx}/{len(etfs)} ETFs")

            except Exception as e:
                logger.error(f"❌ [{ticker}] Investment strategy inference failed: {e}")

        logger.info("")
        logger.info(f"✅ Investment strategy fix complete: {success_count} ETFs updated")
        logger.info("=" * 80)

        return success_count

    def fix_underlying_asset_count(self, dry_run: bool = False) -> int:
        """
        Fix underlying_asset_count field

        Note: KIS API doesn't provide this field directly.
        For now, set reasonable defaults based on fund type:
        - Index funds: 50-200 (typical index size)
        - Sector/Thematic: 20-50
        - Commodity: 1-10

        Returns:
            Number of ETFs updated
        """
        logger.info("=" * 80)
        logger.info("🔧 FIXING UNDERLYING ASSET COUNT FIELD (10)")
        logger.info("=" * 80)
        logger.info("Field: underlying_asset_count")
        logger.info("Logic: Estimated based on fund_type (KIS API limitation)")
        logger.info("")

        if dry_run:
            logger.info("🔍 DRY RUN MODE: Simulation only")
            logger.info("")

        logger.warning("⚠️ KIS API doesn't provide underlying_asset_count")
        logger.warning("⚠️ Using estimated values based on fund type")
        logger.info("")

        # Asset count estimates
        asset_count_map = {
            'index': 100,  # Typical index size
            'sector': 30,
            'thematic': 25,
            'commodity': 5,
            'leverage': 100,  # Same as underlying index
            'inverse': 100,   # Same as underlying index
        }

        # Get all ETFs
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ticker, fund_type
            FROM etf_details
            WHERE fund_type IS NOT NULL
        """)
        etfs = [dict(row) for row in cursor.fetchall()]
        conn.close()

        logger.info(f"📊 Processing {len(etfs)} ETFs...")
        logger.info("")

        success_count = 0

        for idx, etf in enumerate(etfs, 1):
            try:
                ticker = etf['ticker']
                fund_type = etf['fund_type']

                # Estimate asset count
                asset_count = asset_count_map.get(fund_type, 50)

                if not dry_run:
                    self.db.update_etf_details(ticker, {
                        'underlying_asset_count': asset_count,
                    })

                success_count += 1

                if idx % 100 == 0:
                    logger.info(f"📊 Progress: {idx}/{len(etfs)} ETFs")

            except Exception as e:
                logger.error(f"❌ [{ticker}] Asset count estimation failed: {e}")

        logger.info("")
        logger.info(f"✅ Underlying asset count fix complete: {success_count} ETFs updated")
        logger.info("=" * 80)

        return success_count

    def run_comprehensive_fix(self, dry_run: bool = False, skip_tracking_errors: bool = False):
        """
        Run comprehensive fix for all NULL fields

        Args:
            dry_run: Simulate without actual updates
            skip_tracking_errors: Skip tracking error collection (slow API calls)
        """
        logger.info("=" * 80)
        logger.info("🚀 ETF NULL FIELDS COMPREHENSIVE FIX")
        logger.info("=" * 80)
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'PRODUCTION'}")
        logger.info("=" * 80)
        logger.info("")

        # Step 1: Diagnosis
        null_fields = self.diagnose_null_fields()

        # Step 2: Fix inferred fields (1-5)
        logger.info("")
        self.fix_inferred_fields(dry_run=dry_run)

        # Step 3: Fix tracking errors (6) - SLOW
        if not skip_tracking_errors:
            logger.info("")
            self.fix_tracking_errors(dry_run=dry_run)
        else:
            logger.info("")
            logger.info("⏭️ Skipping tracking error collection (use --tracking-errors to enable)")

        # Step 4: Fix 52-week high/low (7)
        logger.info("")
        self.fix_week_52_high_low(dry_run=dry_run)

        # Step 5: Fix pension eligible (8)
        logger.info("")
        self.fix_pension_eligible(dry_run=dry_run)

        # Step 6: Fix investment strategy (9)
        logger.info("")
        self.fix_investment_strategy(dry_run=dry_run)

        # Step 7: Fix underlying asset count (10)
        logger.info("")
        self.fix_underlying_asset_count(dry_run=dry_run)

        # Final diagnosis
        logger.info("")
        logger.info("=" * 80)
        logger.info("🔍 FINAL DIAGNOSIS (After Fix)")
        logger.info("=" * 80)
        logger.info("")

        final_null_fields = self.diagnose_null_fields()

        # Summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 FIX SUMMARY")
        logger.info("=" * 80)

        for field, initial_count in null_fields.items():
            final_count = final_null_fields[field]
            fixed = initial_count - final_count
            status = "✅" if final_count == 0 else "⚠️"
            logger.info(f"{status} {field}: {fixed} fixed, {final_count} remaining")

        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ COMPREHENSIVE FIX COMPLETE!")
        logger.info("=" * 80)


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description='ETF NULL Fields Troubleshooting and Fix')
    parser.add_argument('--dry-run', action='store_true', help='Dry run without actual updates')
    parser.add_argument('--tracking-errors', action='store_true', help='Include tracking error collection (slow)')
    parser.add_argument('--diagnose-only', action='store_true', help='Only run diagnosis')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("🚀 ETF NULL Fields Fixer")
    logger.info("=" * 80)
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'PRODUCTION'}")
    if args.diagnose_only:
        logger.info("Action: DIAGNOSIS ONLY")
    logger.info("=" * 80)
    logger.info("")

    # Initialize
    db = SQLiteDatabaseManager()

    # Initialize KoreaAdapter if tracking errors needed
    kr_adapter = None
    if args.tracking_errors and not args.dry_run:
        try:
            from dotenv import load_dotenv
            load_dotenv()

            app_key = os.getenv('KIS_APP_KEY')
            app_secret = os.getenv('KIS_APP_SECRET')

            if not app_key or not app_secret:
                logger.warning("⚠️ KIS credentials not found - skipping tracking error collection")
            else:
                kr_adapter = KoreaAdapter(db, app_key, app_secret)
                logger.info("✅ KoreaAdapter initialized for tracking error collection")
                logger.info("")

        except Exception as e:
            logger.warning(f"⚠️ KoreaAdapter initialization failed: {e}")
            logger.info("")

    # Create fixer
    fixer = ETFNullFieldsFixer(db=db, kr_adapter=kr_adapter)

    # Run diagnosis or comprehensive fix
    try:
        if args.diagnose_only:
            fixer.diagnose_null_fields()
        else:
            fixer.run_comprehensive_fix(
                dry_run=args.dry_run,
                skip_tracking_errors=not args.tracking_errors
            )

        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ Script Complete!")
        logger.info("=" * 80)

    except KeyboardInterrupt:
        logger.info("")
        logger.info("User interrupted - exiting gracefully")


if __name__ == '__main__':
    main()
