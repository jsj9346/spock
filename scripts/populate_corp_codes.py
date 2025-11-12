#!/usr/bin/env python3
"""
Populate corp_code in stock_details table from DART XML

Quick fix to populate corp_code column that was just added.
After this runs, backfill_fundamentals_dart.py will use database instead of XML download.

Usage:
    python3 scripts/populate_corp_codes.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.dart_api_client import DARTApiClient
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Populate corp_code in stock_details from DART XML"""

    logger.info("="*70)
    logger.info("POPULATE CORP_CODE IN STOCK_DETAILS")
    logger.info("="*70)

    # Initialize
    db = PostgresDatabaseManager()
    dart = DARTApiClient()

    try:
        # Step 1: Download DART corp codes XML
        logger.info("Step 1: Downloading DART corporate code master...")
        xml_path = dart.download_corp_codes()

        if not xml_path or not os.path.exists(xml_path):
            logger.error("❌ Failed to download corp codes XML")
            return 1

        logger.info(f"✅ XML downloaded: {xml_path}")

        # Step 2: Parse XML
        logger.info("\nStep 2: Parsing corp codes from XML...")
        corp_data = dart.parse_corp_codes(xml_path)

        logger.info(f"✅ Parsed {len(corp_data)} companies from DART")

        # Step 3: Create stock_code -> corp_code mapping
        logger.info("\nStep 3: Creating stock_code -> corp_code mapping...")
        mapping = {}
        for corp_name, data in corp_data.items():
            stock_code = data.get('stock_code')
            corp_code = data.get('corp_code')

            if stock_code and corp_code and stock_code.strip():
                # Normalize to 6 digits
                stock_code_normalized = stock_code.strip().zfill(6)
                mapping[stock_code_normalized] = corp_code

        logger.info(f"✅ Created mapping for {len(mapping)} stock codes")

        # Step 4: Get Korean tickers from database
        logger.info("\nStep 4: Fetching Korean tickers from database...")
        query = """
        SELECT ticker FROM tickers
        WHERE region = 'KR' AND asset_type = 'STOCK'
        ORDER BY ticker
        """
        tickers = db.execute_query(query)

        logger.info(f"✅ Found {len(tickers)} Korean stock tickers")

        # Step 5: Update stock_details with corp_codes
        logger.info("\nStep 5: Updating stock_details.corp_code...")

        update_query = """
        INSERT INTO stock_details (ticker, region, corp_code)
        VALUES (%s, %s, %s)
        ON CONFLICT (ticker, region)
        DO UPDATE SET
            corp_code = EXCLUDED.corp_code,
            last_updated = NOW()
        """

        matched = 0
        updated = 0

        for row in tickers:
            ticker = row['ticker']
            corp_code = mapping.get(ticker)

            if corp_code:
                matched += 1
                success = db.execute_update(update_query, (ticker, 'KR', corp_code))
                if success:
                    updated += 1
                    if updated % 100 == 0:
                        logger.info(f"   Progress: {updated}/{matched} updated...")

        logger.info(f"\n✅ Update completed:")
        logger.info(f"   Total KR tickers: {len(tickers)}")
        logger.info(f"   Matched with DART: {matched}")
        logger.info(f"   Successfully updated: {updated}")
        logger.info(f"   No corp_code found: {len(tickers) - matched}")

        # Step 6: Verify
        logger.info("\nStep 6: Verifying results...")
        verify_query = """
        SELECT
            COUNT(*) as total,
            COUNT(corp_code) as with_corp_code,
            COUNT(*) - COUNT(corp_code) as without_corp_code
        FROM stock_details
        WHERE region = 'KR'
        """
        result = db.execute_query(verify_query)[0]

        logger.info(f"✅ Verification:")
        logger.info(f"   Total stock_details: {result['total']}")
        logger.info(f"   With corp_code: {result['with_corp_code']}")
        logger.info(f"   Without corp_code: {result['without_corp_code']}")

        # Show sample
        sample_query = """
        SELECT ticker, corp_code
        FROM stock_details
        WHERE region = 'KR' AND corp_code IS NOT NULL
        ORDER BY ticker
        LIMIT 10
        """
        samples = db.execute_query(sample_query)

        logger.info(f"\nSample corp_codes:")
        for sample in samples:
            logger.info(f"   {sample['ticker']}: {sample['corp_code']}")

        db.close_pool()
        logger.info("\n" + "="*70)
        logger.info("✅ CORP_CODE POPULATION COMPLETED")
        logger.info("="*70)

        return 0

    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        db.close_pool()
        return 1


if __name__ == '__main__':
    sys.exit(main())
