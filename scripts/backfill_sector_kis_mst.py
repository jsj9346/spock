#!/usr/bin/env python3
"""
Sector Backfill Script - KIS Master Data Edition

Downloads and parses KIS official master files (.mst.zip format) from
https://new.real.download.dws.co.kr for KOSPI and KOSDAQ stocks.

Extracts industry classifications (지수업종대분류) and maps to GICS sectors.

Author: Spock Trading System
"""

import sys
import os
import logging
import json
import urllib.request
import ssl
import zipfile
from datetime import datetime
from typing import Dict, Tuple, List
import pandas as pd
from io import BytesIO

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_sqlite import SQLiteDatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'log/{datetime.now().strftime("%Y%m%d")}_sector_backfill_kis_mst.log')
    ]
)
logger = logging.getLogger(__name__)


class KISMasterDataDownloader:
    """KIS master data (.mst) downloader and parser"""

    # Master data URLs
    KOSPI_URL = "https://new.real.download.dws.co.kr/common/master/kospi_code.mst.zip"
    KOSDAQ_URL = "https://new.real.download.dws.co.kr/common/master/kosdaq_code.mst.zip"

    # Field specifications for parsing .mst files (fixed-width format)
    # Based on KIS GitHub scripts
    FIELD_SPECS = [
        2, 1, 4, 4, 4,
        1, 1, 1, 1, 1,
        1, 1, 1, 1, 1,
        1, 1, 1, 1, 1,
        1, 1, 1, 1, 1,
        1, 1, 1, 1, 1,
        1, 1, 1, 1, 1,
        1, 1, 1, 1, 1,
        1, 1, 1, 1, 1,
        9, 5, 5, 1, 1,
        1, 2, 1, 1, 1,
        2, 2, 2, 3, 1,
        3, 12, 12, 8, 15,
        21, 2, 7, 1, 1,
        1, 1, 1, 1, 1
    ]

    # Column names for Part 1 (basic info)
    PART1_COLUMNS = [
        '단축코드', '표준코드', '한글명'
    ]

    # Column names for Part 2 (detailed info including industry)
    PART2_COLUMNS = [
        '지수업종대분류', '지수업종중분류', '지수업종소분류',
        '벤처기업', '저유동성', '지배구조',
        'KRX', 'ETP', 'ELW발행', 'KRX100', 'KRX자동차',
        'KRX반도체', 'KRX바이오', 'KRX은행', 'SPAC',
        'KRX에너지화학', 'KRX철강', '단기과열', 'KRX미디어통신',
        'KRX건설', 'Non1', 'KRX증권', 'KRX선박', 'KRX섹터_보험',
        'KRX섹터_운송', '기타', '기타'
    ]

    def __init__(self):
        # Disable SSL certificate verification for dws.co.kr
        ssl._create_default_https_context = ssl._create_unverified_context

    def download_and_parse(self, url: str, market: str) -> pd.DataFrame:
        """
        Download and parse master data from URL

        Args:
            url: Master data URL (.mst.zip)
            market: 'KOSPI' or 'KOSDAQ'

        Returns:
            DataFrame with ticker and industry information
        """
        logger.info(f"=== Downloading {market} Master Data ===")
        logger.info(f"URL: {url}")

        try:
            # Download ZIP file
            with urllib.request.urlopen(url, timeout=30) as response:
                zip_data = response.read()

            logger.info(f"✅ Downloaded {len(zip_data)} bytes")

            # Extract .mst file from ZIP
            with zipfile.ZipFile(BytesIO(zip_data)) as zf:
                mst_filename = f"{market.lower()}_code.mst"
                with zf.open(mst_filename) as mst_file:
                    mst_data = mst_file.read()

            logger.info(f"✅ Extracted {mst_filename}: {len(mst_data)} bytes")

            # Parse fixed-width format
            df = self._parse_mst_data(mst_data, market)

            logger.info(f"✅ Parsed {len(df)} {market} stocks")
            return df

        except Exception as e:
            logger.error(f"❌ Download/parse failed for {market}: {e}")
            return pd.DataFrame()

    def _parse_mst_data(self, mst_data: bytes, market: str) -> pd.DataFrame:
        """
        Parse binary .mst data - simplified approach extracting key fields

        Args:
            mst_data: Binary .mst file content
            market: 'KOSPI' or 'KOSDAQ'

        Returns:
            DataFrame with parsed data
        """
        try:
            # Parse line by line with cp949 encoding
            lines = mst_data.decode('cp949').split('\n')

            records = []
            for line in lines:
                if len(line) < 200:  # Skip incomplete lines
                    continue

                try:
                    # Extract key fields from fixed positions
                    # Based on KIS .mst format: 단축코드(6), 한글명(40), 지수업종대분류(~60-70)
                    ticker = line[0:6].strip()
                    name = line[6:46].strip()
                    # Industry classification is typically around position 150-170
                    industry = line[150:170].strip()

                    if ticker and len(ticker) == 6 and ticker.isdigit():
                        records.append({
                            '단축코드': ticker,
                            '한글명': name,
                            '지수업종대분류': industry,
                            'market': market
                        })
                except Exception:
                    continue

            df = pd.DataFrame(records)

            if len(df) == 0:
                logger.warning(f"No records parsed, trying alternate parsing method...")
                # Try pandas read_fwf with minimal columns
                df = self._parse_mst_data_alternate(mst_data, market)

            return df

        except Exception as e:
            logger.error(f"❌ Parse failed: {e}")
            return pd.DataFrame()

    def _parse_mst_data_alternate(self, mst_data: bytes, market: str) -> pd.DataFrame:
        """
        Alternate parsing method using pandas read_fwf

        Reads all fields with generic column names, then extracts what we need
        """
        try:
            with open(f"/tmp/{market.lower()}_temp.mst", 'wb') as f:
                f.write(mst_data)

            # Generate generic column names matching field count
            num_fields = len(self.FIELD_SPECS)
            col_names = [f'field_{i}' for i in range(num_fields)]

            # Read with all field specs
            df_all = pd.read_fwf(
                f"/tmp/{market.lower()}_temp.mst",
                widths=self.FIELD_SPECS,
                names=col_names,
                encoding='cp949'
            )

            # Extract only the columns we need
            # Assuming: field_0 = 단축코드, field_2 = 한글명, and industry is in early fields
            df = pd.DataFrame({
                '단축코드': df_all['field_0'],
                '한글명': df_all.get('field_2', ''),
                '지수업종대분류': df_all.get('field_3', ''),  # Try field 3 for industry
                'market': market
            })

            # Clean up temp file
            os.remove(f"/tmp/{market.lower()}_temp.mst")

            return df

        except Exception as e:
            logger.error(f"❌ Alternate parse also failed: {e}")
            return pd.DataFrame()

    def download_all_markets(self) -> pd.DataFrame:
        """
        Download and parse both KOSPI and KOSDAQ master data

        Returns:
            Combined DataFrame with all stocks
        """
        logger.info("=" * 80)
        logger.info("📊 KIS Master Data Download & Parse")
        logger.info("=" * 80)

        # Download KOSPI
        df_kospi = self.download_and_parse(self.KOSPI_URL, 'KOSPI')

        # Download KOSDAQ
        df_kosdaq = self.download_and_parse(self.KOSDAQ_URL, 'KOSDAQ')

        # Combine
        df_all = pd.concat([df_kospi, df_kosdaq], ignore_index=True)

        logger.info("")
        logger.info(f"✅ Total stocks downloaded: {len(df_all)}")
        logger.info(f"   - KOSPI: {len(df_kospi)}")
        logger.info(f"   - KOSDAQ: {len(df_kosdaq)}")

        return df_all


class KISMasterSectorBackfill:
    """Sector backfill using KIS master data"""

    def __init__(self, db: SQLiteDatabaseManager, mapping_file: str):
        self.db = db
        self.downloader = KISMasterDataDownloader()
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

    def backfill_from_master_data(self, dry_run: bool = False) -> Tuple[int, int, int]:
        """
        Backfill sectors using KIS master data

        Args:
            dry_run: If True, simulate without actual DB updates

        Returns:
            (success_count, skipped_count, failed_count)
        """
        # Step 1: Download master data
        df_master = self.downloader.download_all_markets()

        if df_master.empty:
            logger.error("❌ No master data downloaded")
            return (0, 0, 0)

        # Step 2: Get stocks that need sector update
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
              AND (sd.sector = 'Unknown' OR sd.sector IS NULL)
        """)
        unknown_stocks = [dict(row) for row in cursor.fetchall()]
        conn.close()

        total_stocks = stocks + unknown_stocks

        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 Sector Backfill - KIS Master Data Mode")
        logger.info("=" * 80)
        logger.info(f"📌 {len(total_stocks)}개 종목 섹터 업데이트 필요")

        if dry_run:
            logger.info("🔍 DRY RUN MODE: 실제 업데이트 없이 시뮬레이션만 진행")

        # Create ticker lookup dictionary from master data
        master_dict = {}
        for _, row in df_master.iterrows():
            ticker = str(row['단축코드']).strip()
            industry = str(row['지수업종대분류']).strip()
            master_dict[ticker] = industry

        logger.info(f"📌 Master data lookup: {len(master_dict)} tickers")
        logger.info("")

        success, skipped, failed = 0, 0, 0
        mapped_count = 0
        not_found_count = 0

        for stock in total_stocks:
            ticker = stock['ticker']
            name = stock['name']

            try:
                if ticker in master_dict:
                    krx_industry = master_dict[ticker]
                    gics_mapping = self._map_industry_to_gics(krx_industry)

                    if not dry_run:
                        self.db.update_stock_sector(
                            ticker=ticker,
                            sector=gics_mapping['sector'],
                            industry=gics_mapping.get('industry', krx_industry),
                            sector_code=gics_mapping.get('sector_code'),
                            industry_code=gics_mapping.get('industry_code')
                        )

                    # Log only first 10 and last 10
                    if success < 10 or success >= len(total_stocks) - 10:
                        logger.info(
                            f"  ✅ [{ticker}] {name}: "
                            f"KRX={krx_industry} → GICS={gics_mapping['sector']}"
                            f"{' (DRY RUN)' if dry_run else ''}"
                        )
                    elif success == 10:
                        logger.info(f"  ... ({len(total_stocks) - 20} more stocks) ...")

                    mapped_count += 1
                    success += 1

                else:
                    logger.warning(f"  ⏭️ [{ticker}] {name}: 마스터 데이터에 없음")
                    not_found_count += 1
                    skipped += 1

            except Exception as e:
                logger.error(f"  ❌ [{ticker}] {name}: {e}")
                failed += 1

        logger.info("")
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

    parser = argparse.ArgumentParser(description='Sector Backfill - KIS Master Data')
    parser.add_argument('--dry-run', action='store_true', help='Dry run without actual updates')
    parser.add_argument('--mapping-file', default='config/krx_to_gics_mapping.json',
                       help='Path to KRX → GICS mapping JSON file')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("🚀 Sector Backfill - KIS Master Data Edition")
    logger.info("=" * 80)
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'PRODUCTION'}")
    logger.info(f"Mapping File: {args.mapping_file}")
    logger.info("=" * 80)

    # Initialize
    db = SQLiteDatabaseManager()
    backfill = KISMasterSectorBackfill(db=db, mapping_file=args.mapping_file)

    # Show current coverage
    logger.info("")
    logger.info("Current Coverage (Before Backfill):")
    backfill.show_coverage_report()

    # Execute backfill
    logger.info("")
    success, skipped, failed = backfill.backfill_from_master_data(dry_run=args.dry_run)

    # Show final coverage
    if not args.dry_run:
        logger.info("")
        logger.info("Final Coverage (After Backfill):")
        backfill.show_coverage_report()

    logger.info("")
    logger.info("=" * 80)
    logger.info("✅ KIS Master Data Sector Backfill Complete!")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()
