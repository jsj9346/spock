#!/usr/bin/env python3
"""
Sector Backfill Script - Naver Finance Edition

Scrapes industry classification from Naver Finance for Korean stocks
and maps to GICS sectors using config/krx_to_gics_mapping.json.

Source: https://finance.naver.com/item/main.nhn?code=TICKER

Author: Spock Trading System
"""

import sys
import os
import logging
import json
import time
import re
from datetime import datetime
from typing import Dict, Tuple, Optional
import requests
from bs4 import BeautifulSoup

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_sqlite import SQLiteDatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'logs/{datetime.now().strftime("%Y%m%d")}_sector_backfill_naver.log')
    ]
)
logger = logging.getLogger(__name__)


class NaverFinanceScraper:
    """Naver Finance industry classification scraper"""

    BASE_URL = "https://finance.naver.com/item/main.nhn"
    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

    def __init__(self, rate_limit: float = 1.0):
        """
        Initialize scraper

        Args:
            rate_limit: Seconds to wait between requests (default: 1.0)
        """
        self.rate_limit = rate_limit
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.USER_AGENT})

    def get_industry(self, ticker: str) -> Optional[str]:
        """
        Scrape industry classification from Naver Finance

        Args:
            ticker: Stock ticker code (e.g., "005930")

        Returns:
            Industry name in Korean (e.g., "전기전자") or None if failed
        """
        try:
            url = f"{self.BASE_URL}?code={ticker}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Find industry classification
            # Structure: <em>(업종명 : <a href="...">산업명</a> ...)</em>
            industry_elem = None

            # Method 1: Find <em> containing "(업종명 :"
            em_tags = soup.find_all('em')
            for em in em_tags:
                if '업종명' in em.text and '(' in em.text:
                    # Find <a> tag inside this <em>
                    industry_link = em.find('a', href=re.compile(r'sise_group_detail\.naver'))
                    if industry_link:
                        industry_elem = industry_link
                        break

            # Method 2: Direct search for industry link (fallback)
            if not industry_elem:
                industry_links = soup.find_all('a', href=re.compile(r'sise_group_detail\.naver.*type=upjong'))
                if industry_links:
                    industry_elem = industry_links[0]

            if industry_elem:
                industry = industry_elem.text.strip()
                logger.debug(f"[{ticker}] Found industry: {industry}")
                return industry
            else:
                logger.warning(f"[{ticker}] Industry element not found in HTML")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"[{ticker}] Request timeout")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"[{ticker}] Request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"[{ticker}] Scraping failed: {e}")
            return None
        finally:
            # Rate limiting
            time.sleep(self.rate_limit)


class NaverSectorBackfill:
    """Sector backfill using Naver Finance scraping"""

    def __init__(self, db: SQLiteDatabaseManager, mapping_file: str, rate_limit: float = 1.0):
        self.db = db
        self.scraper = NaverFinanceScraper(rate_limit=rate_limit)
        self.mapping = self._load_mapping(mapping_file)

    def _load_mapping(self, mapping_file: str) -> Dict:
        """Load KRX → GICS mapping from JSON"""
        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            mappings = data.get('krx_to_gics_mapping', {})
            fallback = data.get('fallback_mapping', {}).get('default', {})

            logger.info(f"✅ Loaded {len(mappings)} industry mappings")
            return {'mappings': mappings, 'fallback': fallback}

        except Exception as e:
            logger.error(f"❌ Failed to load mapping file: {e}")
            return {'mappings': {}, 'fallback': {}}

    def _map_industry_to_gics(self, krx_industry: str) -> Dict:
        """
        Map KRX industry name to GICS sector

        Args:
            krx_industry: Korean industry name (e.g., "전기전자", "음식료품")

        Returns:
            Dictionary with sector, sector_code, industry, industry_code
        """
        if not krx_industry or krx_industry.strip() == '':
            return self.mapping['fallback']

        krx_industry_clean = krx_industry.strip()

        # Direct mapping
        if krx_industry_clean in self.mapping['mappings']:
            return self.mapping['mappings'][krx_industry_clean]

        # Partial match (fallback)
        for key, value in self.mapping['mappings'].items():
            if key in krx_industry_clean or krx_industry_clean in key:
                logger.debug(f"Partial match: {krx_industry_clean} → {key}")
                return value

        # Default fallback
        logger.warning(f"No mapping for: {krx_industry_clean}, using fallback")
        return self.mapping['fallback']

    def backfill_from_naver(self, dry_run: bool = False, resume_from: Optional[str] = None, preferred_only: bool = False) -> Tuple[int, int, int]:
        """
        Backfill sectors using Naver Finance scraping

        Args:
            dry_run: If True, simulate without actual DB updates
            resume_from: Resume from specific ticker (for interrupted runs)
            preferred_only: If True, only process preferred stocks

        Returns:
            (success_count, skipped_count, failed_count)
        """
        # Get stocks that need sector update
        conn = self.db._get_connection()
        cursor = conn.cursor()

        if preferred_only:
            # Query preferred stocks directly from stock_details
            cursor.execute("""
                SELECT ticker, ticker as name
                FROM stock_details
                WHERE is_preferred = 1
                  AND (sector IS NULL OR sector = 'Unknown')
                ORDER BY ticker
            """)
            stocks = [dict(row) for row in cursor.fetchall()]
            unknown_stocks = []
        else:
            # Original logic for common stocks
            stocks = self.db.get_stocks_without_sector()

            # Also get stocks with "Unknown" sector
            cursor.execute("""
                SELECT t.ticker, t.name
                FROM tickers t
                INNER JOIN stock_details sd ON t.ticker = sd.ticker
                WHERE t.asset_type = 'STOCK'
                  AND t.region = 'KR'
                  AND t.is_active = 1
                  AND (sd.sector = 'Unknown' OR sd.sector IS NULL)
            """)
            unknown_stocks = [dict(row) for row in cursor.fetchall()]

        conn.close()

        total_stocks = stocks + unknown_stocks

        # Remove duplicates
        seen = set()
        unique_stocks = []
        for stock in total_stocks:
            if stock['ticker'] not in seen:
                seen.add(stock['ticker'])
                unique_stocks.append(stock)
        total_stocks = unique_stocks

        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 Sector Backfill - Naver Finance Mode")
        logger.info("=" * 80)
        logger.info(f"📌 {len(total_stocks)}개 종목 섹터 업데이트 필요")
        logger.info(f"📌 Rate limit: {self.scraper.rate_limit}s/request")
        logger.info(f"📌 Estimated time: ~{len(total_stocks) * self.scraper.rate_limit / 60:.1f} minutes")

        if dry_run:
            logger.info("🔍 DRY RUN MODE: 실제 업데이트 없이 시뮬레이션만 진행")

        if resume_from:
            logger.info(f"📍 Resuming from ticker: {resume_from}")

        logger.info("")

        success, skipped, failed = 0, 0, 0
        resume_flag = False if resume_from else True

        for idx, stock in enumerate(total_stocks):
            ticker = stock['ticker']
            name = stock['name']

            # Resume logic
            if not resume_flag:
                if ticker == resume_from:
                    resume_flag = True
                else:
                    continue

            try:
                # Scrape industry from Naver
                krx_industry = self.scraper.get_industry(ticker)

                if krx_industry:
                    gics_mapping = self._map_industry_to_gics(krx_industry)

                    if not dry_run:
                        self.db.update_stock_sector(
                            ticker=ticker,
                            sector=gics_mapping['sector'],
                            industry=gics_mapping.get('industry', krx_industry),
                            sector_code=gics_mapping.get('sector_code'),
                            industry_code=gics_mapping.get('industry_code')
                        )

                    # Progress logging
                    if success < 10 or success % 100 == 0 or success >= len(total_stocks) - 10:
                        logger.info(
                            f"  [{idx+1}/{len(total_stocks)}] ✅ [{ticker}] {name}: "
                            f"Naver={krx_industry} → GICS={gics_mapping['sector']}"
                            f"{' (DRY RUN)' if dry_run else ''}"
                        )
                    elif success == 10:
                        logger.info(f"  ... (logging every 100 stocks) ...")

                    success += 1

                else:
                    logger.warning(f"  [{idx+1}/{len(total_stocks)}] ⏭️ [{ticker}] {name}: Scraping failed")
                    skipped += 1

            except KeyboardInterrupt:
                logger.warning("")
                logger.warning("=" * 80)
                logger.warning("🛑 Interrupted by user")
                logger.warning(f"💾 Progress: {success} success, {skipped} skipped, {failed} failed")
                logger.warning(f"📍 Resume from: {ticker}")
                logger.warning("=" * 80)
                raise

            except Exception as e:
                logger.error(f"  [{idx+1}/{len(total_stocks)}] ❌ [{ticker}] {name}: {e}")
                failed += 1

        logger.info("")
        logger.info("=" * 80)
        logger.info(f"✅ Backfill Complete: Success={success}, Skipped={skipped}, Failed={failed}")
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
              AND sd.sector IS NOT NULL AND sd.sector != '' AND sd.sector != 'Unknown'
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

    parser = argparse.ArgumentParser(description='Sector Backfill - Naver Finance')
    parser.add_argument('--dry-run', action='store_true', help='Dry run without actual updates')
    parser.add_argument('--mapping-file', default='config/krx_to_gics_mapping.json',
                       help='Path to KRX → GICS mapping JSON file')
    parser.add_argument('--rate-limit', type=float, default=1.0,
                       help='Seconds to wait between requests (default: 1.0)')
    parser.add_argument('--resume-from', type=str, default=None,
                       help='Resume from specific ticker')
    parser.add_argument('--preferred-only', action='store_true',
                       help='Only process preferred stocks (is_preferred=1)')

    args = parser.parse_args()

    stock_type = 'Preferred Stocks' if args.preferred_only else 'Common Stocks'

    logger.info("=" * 80)
    logger.info(f"🚀 Sector Backfill - Naver Finance Edition ({stock_type})")
    logger.info("=" * 80)
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'PRODUCTION'}")
    logger.info(f"Stock Type: {stock_type}")
    logger.info(f"Mapping File: {args.mapping_file}")
    logger.info(f"Rate Limit: {args.rate_limit}s/request")
    logger.info("=" * 80)

    # Initialize
    db = SQLiteDatabaseManager()
    backfill = NaverSectorBackfill(db=db, mapping_file=args.mapping_file, rate_limit=args.rate_limit)

    # Show current coverage
    logger.info("")
    logger.info("Current Coverage (Before Backfill):")
    backfill.show_coverage_report()

    # Execute backfill
    logger.info("")
    try:
        success, skipped, failed = backfill.backfill_from_naver(
            dry_run=args.dry_run,
            resume_from=args.resume_from,
            preferred_only=args.preferred_only
        )

        # Show final coverage
        if not args.dry_run and success > 0:
            logger.info("")
            logger.info("Final Coverage (After Backfill):")
            backfill.show_coverage_report()

    except KeyboardInterrupt:
        logger.info("")
        logger.info("User interrupted - exiting gracefully")

    logger.info("")
    logger.info("=" * 80)
    logger.info("✅ Naver Finance Sector Backfill Complete!")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()
