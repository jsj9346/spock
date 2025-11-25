#!/usr/bin/env python3
"""
Sector Backfill Script - KIS GitHub Master File Edition

Downloads and parses KIS official master file (종목코드 마스터) from GitHub
to populate comprehensive sector information for Korean stocks.

Source: https://github.com/koreainvestment/open-trading-api
File: 종목코드_마스터.xlsx

This replaces "Unknown" sectors with actual industry classifications.

Author: Spock Trading System
"""

import sys
import os
import logging
import requests
from datetime import datetime
from typing import Dict, Tuple, List
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_sqlite import SQLiteDatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'log/{datetime.now().strftime("%Y%m%d")}_sector_backfill_kis_master.log')
    ]
)
logger = logging.getLogger(__name__)


class KISMasterFileDownloader:
    """KIS GitHub master file downloader and parser"""

    # KIS GitHub repository URLs
    GITHUB_RAW_BASE = "https://raw.githubusercontent.com/koreainvestment/open-trading-api/main"
    MASTER_FILE_PATH = "exchange_code/종목코드_마스터.xlsx"

    def __init__(self):
        self.master_file_url = f"{self.GITHUB_RAW_BASE}/{self.MASTER_FILE_PATH}"

    def download_master_file(self, output_path: str = "data/kis_master.xlsx") -> bool:
        """
        Download KIS master file from GitHub

        Args:
            output_path: Local path to save downloaded file

        Returns:
            True if successful
        """
        logger.info("=" * 80)
        logger.info("📥 Downloading KIS Master File from GitHub")
        logger.info("=" * 80)
        logger.info(f"URL: {self.master_file_url}")

        try:
            response = requests.get(self.master_file_url, timeout=30)
            response.raise_for_status()

            # Save file
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(response.content)

            file_size_kb = len(response.content) / 1024
            logger.info(f"✅ Downloaded: {output_path} ({file_size_kb:.1f} KB)")
            return True

        except Exception as e:
            logger.error(f"❌ Download failed: {e}")
            return False

    def parse_master_file(self, file_path: str) -> List[Dict]:
        """
        Parse KIS master Excel file

        Args:
            file_path: Path to downloaded Excel file

        Returns:
            List of stock dictionaries with sector info
        """
        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 Parsing KIS Master File")
        logger.info("=" * 80)

        try:
            # Read Excel file
            df = pd.read_excel(file_path, engine='openpyxl')

            logger.info(f"📌 Loaded {len(df)} rows from master file")
            logger.info(f"📌 Columns: {list(df.columns)}")

            stocks = []

            for idx, row in df.iterrows():
                # Extract relevant fields
                # Note: Column names may vary - adjust based on actual file structure
                ticker = str(row.get('단축코드', row.get('종목코드', ''))).strip()

                if not ticker:
                    continue

                stock_info = {
                    'ticker': ticker,
                    'name': row.get('한글명', row.get('종목명', '')),
                    'sector': row.get('섹터', row.get('업종', 'Unknown')),
                    'industry': row.get('업종', row.get('산업', 'Unknown')),
                    'sector_code': row.get('섹터코드', None),
                    'industry_code': row.get('업종코드', None),
                }

                stocks.append(stock_info)

            logger.info(f"✅ Parsed {len(stocks)} stocks from master file")
            return stocks

        except Exception as e:
            logger.error(f"❌ Parse failed: {e}")
            return []


class KISMasterSectorBackfill:
    """Sector backfill using KIS master file"""

    def __init__(self, db: SQLiteDatabaseManager):
        self.db = db
        self.downloader = KISMasterFileDownloader()

    def backfill_from_master_file(self, dry_run: bool = False) -> Tuple[int, int, int]:
        """
        Backfill sectors using KIS master file

        Args:
            dry_run: If True, simulate without actual DB updates

        Returns:
            (success_count, skipped_count, failed_count)
        """
        # Step 1: Download master file
        master_file_path = "data/kis_master.xlsx"
        if not self.downloader.download_master_file(master_file_path):
            logger.error("❌ Failed to download master file")
            return (0, 0, 0)

        # Step 2: Parse master file
        master_stocks = self.downloader.parse_master_file(master_file_path)
        if not master_stocks:
            logger.error("❌ No stocks parsed from master file")
            return (0, 0, 0)

        # Create lookup dictionary
        master_map = {stock['ticker']: stock for stock in master_stocks}

        # Step 3: Get stocks that need sector update (currently "Unknown")
        stocks = self.db.get_stocks_without_sector()

        # Also get stocks with "Unknown" sector
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.ticker, t.name
            FROM tickers t
            INNER JOIN stock_details sd ON t.ticker = sd.ticker
            WHERE t.asset_type = 'STOCK'
              AND t.region = 'KR'
              AND t.is_active = 1
              AND sd.sector = 'Unknown'
        """)
        unknown_stocks = [dict(row) for row in cursor.fetchall()]
        conn.close()

        total_stocks = stocks + unknown_stocks
        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 Sector Backfill - KIS Master File Mode")
        logger.info("=" * 80)
        logger.info(f"📌 {len(total_stocks)}개 종목 섹터 업데이트 필요")

        if dry_run:
            logger.info("🔍 DRY RUN MODE: 실제 업데이트 없이 시뮬레이션만 진행")

        success, skipped, failed = 0, 0, 0
        mapped_count = 0
        not_found_count = 0

        for stock in total_stocks:
            ticker = stock['ticker']
            name = stock['name']

            try:
                if ticker in master_map:
                    master_info = master_map[ticker]

                    if not dry_run:
                        self.db.update_stock_sector(
                            ticker=ticker,
                            sector=master_info['sector'],
                            industry=master_info.get('industry', 'Unknown'),
                            sector_code=master_info.get('sector_code'),
                            industry_code=master_info.get('industry_code')
                        )

                    logger.info(
                        f"✅ [{ticker}] {name}: "
                        f"섹터={master_info['sector']}, 업종={master_info.get('industry', 'N/A')}"
                        f"{' (DRY RUN)' if dry_run else ''}"
                    )
                    mapped_count += 1
                    success += 1

                else:
                    logger.warning(f"⏭️ [{ticker}] {name}: 마스터 파일에 없음 (Unknown 유지)")
                    not_found_count += 1
                    skipped += 1

            except Exception as e:
                logger.error(f"❌ [{ticker}] {name}: {e}")
                failed += 1

        logger.info("=" * 80)
        logger.info(f"✅ Backfill Complete: Success={success}, Skipped={skipped}, Failed={failed}")
        logger.info(f"📊 Mapped={mapped_count}, Not Found={not_found_count}")
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
            LIMIT 20
        """)

        logger.info("")
        logger.info("Sector Distribution (Top 20):")
        for row in cursor.fetchall():
            sector = row['sector']
            count = row['count']
            logger.info(f"  {sector}: {count}개")

        conn.close()


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description='Sector Backfill - KIS Master File')
    parser.add_argument('--dry-run', action='store_true', help='Dry run without actual updates')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("🚀 Sector Backfill - KIS Master File Edition")
    logger.info("=" * 80)
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'PRODUCTION'}")
    logger.info("=" * 80)

    # Initialize
    db = SQLiteDatabaseManager()
    backfill = KISMasterSectorBackfill(db=db)

    # Show current coverage
    logger.info("")
    logger.info("Current Coverage (Before Backfill):")
    backfill.show_coverage_report()

    # Execute backfill
    logger.info("")
    success, skipped, failed = backfill.backfill_from_master_file(dry_run=args.dry_run)

    # Show final coverage
    if not args.dry_run:
        logger.info("")
        logger.info("Final Coverage (After Backfill):")
        backfill.show_coverage_report()

    logger.info("")
    logger.info("=" * 80)
    logger.info("✅ KIS Master File Sector Backfill Complete!")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()
