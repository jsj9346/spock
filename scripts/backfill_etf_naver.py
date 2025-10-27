#!/usr/bin/env python3
"""
ETF Details Backfill Script - Naver Finance Edition

Scrapes ETF information from Naver Finance and populates etf_details table.

Source: https://finance.naver.com/item/main.nhn?code=TICKER

Author: Spock Trading System
"""

import sys
import os
import logging
import time
import re
from datetime import datetime
from typing import Dict, Optional
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
        logging.FileHandler(f'logs/{datetime.now().strftime("%Y%m%d")}_etf_backfill_naver.log')
    ]
)
logger = logging.getLogger(__name__)


class NaverFinanceETFScraper:
    """Naver Finance ETF information scraper"""

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

    def get_etf_details(self, ticker: str) -> Optional[Dict]:
        """
        Scrape ETF details from Naver Finance

        Args:
            ticker: ETF ticker code (e.g., "069500")

        Returns:
            Dictionary with ETF details or None if failed
        """
        try:
            url = f"{self.BASE_URL}?code={ticker}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Verify this is an ETF page
            if 'ETF' not in response.text:
                logger.warning(f"[{ticker}] Not an ETF page")
                return None

            etf_data = {
                'expense_ratio': None,
                'tracking_index': None,
                'fund_type': None,
                'inception_date': None,
                'issuer': None,
                'aum': None,
                'listed_shares': None
            }

            # Extract expense ratio (펀드보수)
            expense_table = soup.find('table', {'summary': '펀드보수 정보'})
            if expense_table:
                td = expense_table.find('td')
                if td:
                    em = td.find('em')
                    if em:
                        expense_text = em.text.strip()
                        # Extract percentage: "0.15%" -> 0.15
                        match = re.search(r'([\d.]+)%', expense_text)
                        if match:
                            etf_data['expense_ratio'] = float(match.group(1))

            # Extract tracking index and other info from 기초지수 정보 table
            index_table = soup.find('table', {'summary': '기초지수 정보'})
            if index_table:
                rows = index_table.find_all('tr')
                for row in rows:
                    th = row.find('th')
                    td = row.find('td')
                    if not th or not td:
                        continue

                    field_name = th.text.strip()

                    if field_name == '기초지수':
                        span = td.find('span')
                        if span:
                            etf_data['tracking_index'] = span.get('title') or span.text.strip()

                    elif field_name == '유형':
                        span = td.find('span')
                        if span:
                            etf_data['fund_type'] = span.get('title') or span.text.strip()

                    elif field_name == '상장일':
                        date_text = td.text.strip()
                        # Parse date: "2002년 10월 14일" -> "2002-10-14"
                        date_match = re.search(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', date_text)
                        if date_match:
                            year, month, day = date_match.groups()
                            etf_data['inception_date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

            # Extract issuer (자산운용사) - it's in the same table as 펀드보수
            if expense_table:
                rows = expense_table.find_all('tr')
                for row in rows:
                    th = row.find('th')
                    td = row.find('td')
                    if not th or not td:
                        continue

                    if '자산운용사' in th.text:
                        span = td.find('span')
                        if span:
                            etf_data['issuer'] = span.get('title') or span.text.strip()

            # Extract AUM and listed shares from 시가총액 정보 table
            mc_table = soup.find('table', {'summary': '시가총액 정보'})
            if mc_table:
                rows = mc_table.find_all('tr')
                for row in rows:
                    th = row.find('th')
                    td = row.find('td')
                    if not th or not td:
                        continue

                    field_name = th.text.strip()

                    if field_name == '시가총액':
                        # Parse: "9조 6,954억원" or "1조 2,345억원"
                        aum_text = td.text.strip()
                        # Remove whitespace and newlines
                        aum_text = ''.join(aum_text.split())

                        # Extract trillions and billions
                        trillion_match = re.search(r'(\d+)조', aum_text)
                        billion_match = re.search(r'([\d,]+)억', aum_text)

                        aum_value = 0
                        if trillion_match:
                            aum_value += int(trillion_match.group(1)) * 1_000_000_000_000
                        if billion_match:
                            billion_str = billion_match.group(1).replace(',', '')
                            aum_value += int(billion_str) * 100_000_000

                        if aum_value > 0:
                            etf_data['aum'] = aum_value

                    elif field_name == '상장주식수':
                        # Parse: "191,250,000" or "123,456,789"
                        shares_text = td.text.strip().replace(',', '').replace(' ', '')
                        try:
                            etf_data['listed_shares'] = int(shares_text)
                        except ValueError:
                            logger.debug(f"[{ticker}] Failed to parse listed_shares: {shares_text}")

            logger.debug(f"[{ticker}] Scraped: {etf_data}")
            return etf_data

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


class NaverETFBackfill:
    """ETF details backfill using Naver Finance scraping"""

    def __init__(self, db: SQLiteDatabaseManager, rate_limit: float = 1.0):
        self.db = db
        self.scraper = NaverFinanceETFScraper(rate_limit=rate_limit)

    def backfill_from_naver(self, dry_run: bool = False, resume_from: Optional[str] = None) -> tuple:
        """
        Backfill ETF details using Naver Finance scraping

        Args:
            dry_run: If True, simulate without actual DB updates
            resume_from: Resume from specific ticker (for interrupted runs)

        Returns:
            (success_count, skipped_count, failed_count)
        """
        # Get ETFs that need details update
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT t.ticker, t.name
            FROM tickers t
            INNER JOIN etf_details ed ON t.ticker = ed.ticker
            WHERE t.asset_type = 'ETF'
              AND t.region = 'KR'
              AND t.is_active = 1
              AND (ed.expense_ratio IS NULL
                   OR ed.tracking_index = 'Unknown'
                   OR ed.issuer IS NULL
                   OR ed.aum IS NULL
                   OR ed.listed_shares IS NULL)
            ORDER BY t.ticker
        """)
        etfs = [dict(row) for row in cursor.fetchall()]
        conn.close()

        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 ETF Details Backfill - Naver Finance Mode")
        logger.info("=" * 80)
        logger.info(f"📌 {len(etfs)}개 ETF 정보 업데이트 필요")
        logger.info(f"📌 Rate limit: {self.scraper.rate_limit}s/request")
        logger.info(f"📌 Estimated time: ~{len(etfs) * self.scraper.rate_limit / 60:.1f} minutes")

        if dry_run:
            logger.info("🔍 DRY RUN MODE: 실제 업데이트 없이 시뮬레이션만 진행")

        if resume_from:
            logger.info(f"📍 Resuming from ticker: {resume_from}")

        logger.info("")

        success, skipped, failed = 0, 0, 0
        resume_flag = False if resume_from else True

        for idx, etf in enumerate(etfs):
            ticker = etf['ticker']
            name = etf['name']

            # Resume logic
            if not resume_flag:
                if ticker == resume_from:
                    resume_flag = True
                else:
                    continue

            try:
                # Scrape ETF details from Naver
                etf_data = self.scraper.get_etf_details(ticker)

                if etf_data and any(v is not None for v in etf_data.values()):
                    if not dry_run:
                        # Update database
                        updates = {}
                        if etf_data['expense_ratio'] is not None:
                            updates['expense_ratio'] = etf_data['expense_ratio']
                        if etf_data['tracking_index']:
                            updates['tracking_index'] = etf_data['tracking_index']
                        if etf_data['fund_type']:
                            updates['fund_type'] = etf_data['fund_type']
                        if etf_data['inception_date']:
                            updates['inception_date'] = etf_data['inception_date']
                        if etf_data['issuer']:
                            updates['issuer'] = etf_data['issuer']
                        if etf_data['aum'] is not None:
                            updates['aum'] = etf_data['aum']
                        if etf_data['listed_shares'] is not None:
                            updates['listed_shares'] = etf_data['listed_shares']

                        if updates:
                            self.db.update_etf_details(ticker, updates)

                    # Progress logging
                    if success < 10 or success % 100 == 0 or success >= len(etfs) - 10:
                        summary = f"운용보수={etf_data['expense_ratio']}%, 지수={etf_data['tracking_index']}, 운용사={etf_data['issuer']}"
                        logger.info(
                            f"  [{idx+1}/{len(etfs)}] ✅ [{ticker}] {name}: {summary}"
                            f"{' (DRY RUN)' if dry_run else ''}"
                        )
                    elif success == 10:
                        logger.info(f"  ... (logging every 100 ETFs) ...")

                    success += 1

                else:
                    logger.warning(f"  [{idx+1}/{len(etfs)}] ⏭️ [{ticker}] {name}: Scraping failed")
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
                logger.error(f"  [{idx+1}/{len(etfs)}] ❌ [{ticker}] {name}: {e}")
                failed += 1

        logger.info("")
        logger.info("=" * 80)
        logger.info(f"✅ Backfill Complete: Success={success}, Skipped={skipped}, Failed={failed}")
        logger.info("=" * 80)

        return (success, skipped, failed)

    def show_coverage_report(self):
        """Show ETF details coverage statistics"""
        conn = self.db._get_connection()
        cursor = conn.cursor()

        # Total ETFs
        cursor.execute("""
            SELECT COUNT(*) as total
            FROM tickers
            WHERE asset_type = 'ETF' AND region = 'KR' AND is_active = 1
        """)
        total = cursor.fetchone()['total']

        # Coverage by field
        cursor.execute("""
            SELECT
                SUM(CASE WHEN ed.expense_ratio IS NOT NULL THEN 1 ELSE 0 END) as has_expense,
                SUM(CASE WHEN ed.tracking_index IS NOT NULL AND ed.tracking_index != 'Unknown' THEN 1 ELSE 0 END) as has_index,
                SUM(CASE WHEN ed.issuer IS NOT NULL THEN 1 ELSE 0 END) as has_issuer,
                SUM(CASE WHEN ed.inception_date IS NOT NULL THEN 1 ELSE 0 END) as has_date,
                SUM(CASE WHEN ed.fund_type IS NOT NULL THEN 1 ELSE 0 END) as has_type,
                SUM(CASE WHEN ed.aum IS NOT NULL THEN 1 ELSE 0 END) as has_aum,
                SUM(CASE WHEN ed.listed_shares IS NOT NULL THEN 1 ELSE 0 END) as has_shares
            FROM tickers t
            INNER JOIN etf_details ed ON t.ticker = ed.ticker
            WHERE t.asset_type = 'ETF' AND t.region = 'KR' AND t.is_active = 1
        """)
        coverage = cursor.fetchone()

        conn.close()

        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 ETF DETAILS COVERAGE REPORT")
        logger.info("=" * 80)
        logger.info(f"Total ETFs: {total}")
        logger.info(f"Expense Ratio: {coverage['has_expense']}/{total} ({coverage['has_expense']/total*100:.1f}%)")
        logger.info(f"Tracking Index: {coverage['has_index']}/{total} ({coverage['has_index']/total*100:.1f}%)")
        logger.info(f"Issuer: {coverage['has_issuer']}/{total} ({coverage['has_issuer']/total*100:.1f}%)")
        logger.info(f"Inception Date: {coverage['has_date']}/{total} ({coverage['has_date']/total*100:.1f}%)")
        logger.info(f"Fund Type: {coverage['has_type']}/{total} ({coverage['has_type']/total*100:.1f}%)")
        logger.info(f"AUM: {coverage['has_aum']}/{total} ({coverage['has_aum']/total*100:.1f}%)")
        logger.info(f"Listed Shares: {coverage['has_shares']}/{total} ({coverage['has_shares']/total*100:.1f}%)")
        logger.info("=" * 80)


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description='ETF Details Backfill - Naver Finance')
    parser.add_argument('--dry-run', action='store_true', help='Dry run without actual updates')
    parser.add_argument('--rate-limit', type=float, default=1.0,
                       help='Seconds to wait between requests (default: 1.0)')
    parser.add_argument('--resume-from', type=str, default=None,
                       help='Resume from specific ticker')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("🚀 ETF Details Backfill - Naver Finance Edition")
    logger.info("=" * 80)
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'PRODUCTION'}")
    logger.info(f"Rate Limit: {args.rate_limit}s/request")
    logger.info("=" * 80)

    # Initialize
    db = SQLiteDatabaseManager()
    backfill = NaverETFBackfill(db=db, rate_limit=args.rate_limit)

    # Show current coverage
    logger.info("")
    logger.info("Current Coverage (Before Backfill):")
    backfill.show_coverage_report()

    # Execute backfill
    logger.info("")
    try:
        success, skipped, failed = backfill.backfill_from_naver(
            dry_run=args.dry_run,
            resume_from=args.resume_from
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
    logger.info("✅ Naver Finance ETF Backfill Complete!")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()
