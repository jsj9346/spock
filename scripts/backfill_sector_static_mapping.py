#!/usr/bin/env python3
"""
Sector Backfill Script - Static Mapping Edition

Uses static sector mapping from config/static_sector_mapping.json
to populate stock_details.sector for Korean stocks.

Fallback strategy:
1. Static mapping (176 major stocks)
2. "Unknown" for unmapped stocks

Author: Spock Trading System
"""

import sys
import os
import json
import logging
from datetime import datetime
from typing import Dict, Tuple

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_sqlite import SQLiteDatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'logs/{datetime.now().strftime("%Y%m%d")}_sector_backfill_static.log')
    ]
)
logger = logging.getLogger(__name__)


class StaticSectorBackfill:
    """Static sector mapping backfill"""

    def __init__(self, db: SQLiteDatabaseManager, mapping_file: str):
        self.db = db
        self.mapping_file = mapping_file
        self.sector_map = self._load_mapping()

    def _load_mapping(self) -> Dict:
        """Load static sector mapping from JSON"""
        try:
            with open(self.mapping_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            mappings = data.get('mappings', {})
            logger.info(f"✅ Loaded {len(mappings)} sector mappings from {self.mapping_file}")
            return mappings

        except Exception as e:
            logger.error(f"❌ Failed to load sector mapping: {e}")
            return {}

    def backfill_with_static_mapping(self, dry_run: bool = False) -> Tuple[int, int, int]:
        """
        Backfill sectors using static mapping

        Returns:
            (success_count, skipped_count, failed_count)
        """
        logger.info("=" * 80)
        logger.info("📊 Sector Backfill - Static Mapping Mode")
        logger.info("=" * 80)

        if not self.sector_map:
            logger.error("❌ No sector mappings loaded")
            return (0, 0, 0)

        # Get all stocks without sector
        stocks = self.db.get_stocks_without_sector()
        logger.info(f"📌 {len(stocks)}개 종목 섹터 업데이트 필요")

        if dry_run:
            logger.info("🔍 DRY RUN MODE: 실제 업데이트 없이 시뮬레이션만 진행")

        success, skipped, failed = 0, 0, 0
        mapped_count = 0
        unknown_count = 0

        for stock in stocks:
            ticker = stock['ticker']
            name = stock['name']

            try:
                # Check if ticker exists in static mapping
                if ticker in self.sector_map:
                    sector_info = self.sector_map[ticker]

                    if not dry_run:
                        self.db.update_stock_sector(
                            ticker=ticker,
                            sector=sector_info['sector'],
                            industry=sector_info.get('industry'),
                            sector_code=sector_info.get('sector_code'),
                            industry_code=sector_info.get('industry_code')
                        )

                    logger.info(
                        f"✅ [{ticker}] {name}: "
                        f"섹터={sector_info['sector']}, 업종={sector_info.get('industry', 'N/A')}"
                        f"{' (DRY RUN)' if dry_run else ''}"
                    )
                    mapped_count += 1
                    success += 1

                else:
                    # Fallback: Mark as "Unknown"
                    if not dry_run:
                        self.db.update_stock_sector(
                            ticker=ticker,
                            sector='Unknown',
                            industry='Unknown',
                            sector_code=None,
                            industry_code=None
                        )

                    logger.info(
                        f"⚠️ [{ticker}] {name}: 섹터=Unknown (정적 매핑 없음)"
                        f"{' (DRY RUN)' if dry_run else ''}"
                    )
                    unknown_count += 1
                    success += 1

            except Exception as e:
                logger.error(f"❌ [{ticker}] {name}: {e}")
                failed += 1

        logger.info("=" * 80)
        logger.info(f"✅ Backfill Complete: Success={success}, Skipped={skipped}, Failed={failed}")
        logger.info(f"📊 Mapped={mapped_count}, Unknown={unknown_count}")
        logger.info("=" * 80)

        return (success, skipped, failed)

    def show_coverage_report(self):
        """Show sector coverage statistics"""
        stats = self.db.get_sector_coverage_stats()

        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 SECTOR COVERAGE REPORT")
        logger.info("=" * 80)
        logger.info(f"Total Stocks: {stats['total']}")
        logger.info(f"With Sector: {stats['with_sector']} ({stats['coverage_percent']:.1f}%)")
        logger.info(f"Without Sector: {stats['without_sector']}")
        logger.info("=" * 80)

        # Count by sector
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT sd.sector, COUNT(*) as count
            FROM tickers t
            INNER JOIN stock_details sd ON t.ticker = sd.ticker
            WHERE t.asset_type = 'STOCK' AND t.region = 'KR' AND t.is_active = 1
              AND sd.sector IS NOT NULL AND sd.sector != ''
            GROUP BY sd.sector
            ORDER BY count DESC
        """)

        logger.info("")
        logger.info("Sector Distribution:")
        for row in cursor.fetchall():
            sector = row['sector']
            count = row['count']
            logger.info(f"  {sector}: {count}개")

        conn.close()


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description='Sector Backfill - Static Mapping')
    parser.add_argument('--dry-run', action='store_true', help='Dry run without actual updates')
    parser.add_argument('--mapping-file', default='config/static_sector_mapping.json',
                       help='Path to static sector mapping JSON file')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("🚀 Sector Backfill - Static Mapping Edition")
    logger.info("=" * 80)
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'PRODUCTION'}")
    logger.info(f"Mapping File: {args.mapping_file}")
    logger.info("=" * 80)

    # Initialize
    db = SQLiteDatabaseManager()
    backfill = StaticSectorBackfill(db=db, mapping_file=args.mapping_file)

    # Show current coverage
    logger.info("")
    logger.info("Current Coverage (Before Backfill):")
    backfill.show_coverage_report()

    # Execute backfill
    logger.info("")
    success, skipped, failed = backfill.backfill_with_static_mapping(dry_run=args.dry_run)

    # Show final coverage
    if not args.dry_run:
        logger.info("")
        logger.info("Final Coverage (After Backfill):")
        backfill.show_coverage_report()

    logger.info("")
    logger.info("=" * 80)
    logger.info("✅ Sector Backfill Complete!")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()
