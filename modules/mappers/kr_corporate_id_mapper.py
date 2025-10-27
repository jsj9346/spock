#!/usr/bin/env python3
"""
Korean Corporate ID Mapper

Maps Korean stock tickers (6-digit codes) to DART corporate codes (8-digit).

Data Source: DART Open API
- Endpoint: /api/corpCode.xml
- Contains: ~100,000 companies (listed + unlisted)
- Format: ZIP file with CORPCODE.xml

Cache Strategy:
- Master XML file: 24-hour TTL (config/dart_corp_codes.xml)
- JSON mapping: 24-hour TTL (config/corp_code_mapping_kr.json)
- In-memory dict: Session-based

Author: Spock Trading System
"""

import os
import logging
import zipfile
import requests
import xml.etree.ElementTree as ET
from typing import Dict, Optional
from datetime import datetime

from ..corporate_id_mapper import BaseCorporateIDMapper

logger = logging.getLogger(__name__)


class KRCorporateIDMapper(BaseCorporateIDMapper):
    """
    Korean stock ticker → DART corporate code mapper

    Mapping:
    - stock_code (6-digit) → corp_code (8-digit)
    - company_name → corp_code (fuzzy matching)

    Example:
        mapper = KRCorporateIDMapper()
        corp_code = mapper.get_corporate_id('005930')  # Samsung Electronics
        # Returns: '00126380'
    """

    DART_API_BASE_URL = "https://opendart.fss.or.kr/api"
    CORP_CODE_ENDPOINT = "/corpCode.xml"

    def __init__(self,
                 api_key: Optional[str] = None,
                 cache_path: str = "config/corp_code_mapping_kr.json",
                 xml_path: str = "config/dart_corp_codes.xml",
                 cache_ttl_hours: int = 24):
        """
        Initialize Korean corporate ID mapper

        Args:
            api_key: DART API key (if None, loads from environment DART_API_KEY)
            cache_path: Path to JSON cache file
            xml_path: Path to DART XML file
            cache_ttl_hours: Cache TTL in hours (default: 24)
        """
        # Initialize base class
        super().__init__(
            region_code='KR',
            cache_path=cache_path,
            cache_ttl_hours=cache_ttl_hours
        )

        # DART API credentials
        self.api_key = api_key or os.getenv('DART_API_KEY')
        if not self.api_key:
            logger.warning(
                "⚠️ DART_API_KEY not found. "
                "Corporate ID mapping will not work until API key is set. "
                "Get API key from: https://opendart.fss.or.kr/"
            )

        # File paths
        self.xml_path = xml_path

        # Rate limiting
        self.rate_limit_delay = 36.0  # 100 requests/hour

        logger.info(f"📊 KRCorporateIDMapper initialized")

    def download_mapping_data(self) -> bool:
        """
        Download DART corporate code master file

        Downloads ZIP file containing CORPCODE.xml from DART API.

        Returns:
            True if successful

        Note:
            This downloads ~100,000 company records (~50MB compressed).
            Rate limit: 1,000 requests/day (but this only needs 1 call/day)
        """
        if not self.api_key:
            logger.error("❌ [KR] DART_API_KEY not set, cannot download corp codes")
            return False

        try:
            logger.info(f"📥 [KR] Downloading DART corporate code master...")

            # Request ZIP file from DART API
            url = f"{self.DART_API_BASE_URL}{self.CORP_CODE_ENDPOINT}"
            params = {'crtfc_key': self.api_key}

            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()

            # Ensure directory exists
            os.makedirs(os.path.dirname(self.xml_path), exist_ok=True)

            # Save ZIP file temporarily
            zip_path = self.xml_path.replace('.xml', '.zip')
            with open(zip_path, 'wb') as f:
                f.write(response.content)

            logger.debug(f"[KR] ZIP file saved: {zip_path}")

            # Extract XML from ZIP
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # DART returns file named 'CORPCODE.xml'
                zip_ref.extractall(os.path.dirname(self.xml_path))

            # Rename extracted file to our target path
            extracted_file = os.path.join(os.path.dirname(self.xml_path), 'CORPCODE.xml')
            if os.path.exists(extracted_file):
                if os.path.exists(self.xml_path):
                    os.remove(self.xml_path)
                os.rename(extracted_file, self.xml_path)

            # Clean up ZIP file
            os.remove(zip_path)

            logger.info(f"✅ [KR] Corporate code master downloaded: {self.xml_path}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ [KR] DART API request failed: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ [KR] Download failed: {e}")
            return False

    def build_mapping(self) -> bool:
        """
        Build ticker → corp_code mapping from DART XML

        Parses CORPCODE.xml and creates two mappings:
        1. stock_code → corp_code (primary)
        2. company_name → corp_code (for fuzzy matching)

        Returns:
            True if successful

        Note:
            Only includes listed companies (stock_code is not empty).
            Filters out unlisted companies to reduce mapping size.
        """
        try:
            if not os.path.exists(self.xml_path):
                logger.error(f"❌ [KR] XML file not found: {self.xml_path}")
                return False

            logger.info(f"🔄 [KR] Parsing DART corporate codes from {self.xml_path}...")

            # Parse XML file
            tree = ET.parse(self.xml_path)
            root = tree.getroot()

            # Clear existing mappings
            self.ticker_to_id = {}
            self.name_to_id = {}

            # Parse each company entry
            total_count = 0
            listed_count = 0

            for corp in root.findall('list'):
                total_count += 1

                # Extract fields
                corp_code = corp.find('corp_code')
                corp_name = corp.find('corp_name')
                stock_code = corp.find('stock_code')

                if corp_code is None or corp_name is None or stock_code is None:
                    continue

                corp_code_value = corp_code.text
                corp_name_value = corp_name.text
                stock_code_value = stock_code.text

                # Skip if no stock code (unlisted company)
                if not stock_code_value or stock_code_value.strip() == '':
                    continue

                # Add to mappings
                self.ticker_to_id[stock_code_value] = corp_code_value
                self.name_to_id[corp_name_value] = corp_code_value

                listed_count += 1

            # Update metadata
            self.mapping_count = len(self.ticker_to_id)

            logger.info(
                f"✅ [KR] Built mappings: {listed_count} listed companies "
                f"(total: {total_count}, filtered: {total_count - listed_count})"
            )

            return True

        except ET.ParseError as e:
            logger.error(f"❌ [KR] XML parsing failed: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ [KR] Build mapping failed: {e}")
            return False

    def _parse_mapping_file(self) -> Dict[str, str]:
        """
        Parse DART XML file (implementation of abstract method)

        Returns:
            Dict {stock_code: corp_code}

        Note:
            This method is called by refresh_mapping() workflow.
            For Korean market, we use build_mapping() instead.
        """
        # This method is not used for Korean market
        # We use build_mapping() which parses XML directly
        return self.ticker_to_id

    def get_corporate_id(self, ticker: str) -> Optional[str]:
        """
        Get DART corporate code for a Korean stock ticker

        Args:
            ticker: Korean stock ticker (6-digit code, e.g., '005930')

        Returns:
            DART corporate code (8-digit) or None

        Example:
            corp_code = mapper.get_corporate_id('005930')
            # Returns: '00126380' (Samsung Electronics)
        """
        # Ensure mapping is loaded
        if not self.ticker_to_id and not self._is_cache_fresh():
            logger.info(f"[KR] No mapping loaded, attempting to load from cache or refresh...")
            if not self._load_from_cache():
                logger.warning(f"[KR] Cache not available, refreshing from DART...")
                self.refresh_mapping()

        # Call parent class implementation
        corp_code = super().get_corporate_id(ticker)

        if corp_code:
            logger.debug(f"[KR] {ticker} → {corp_code}")
        else:
            logger.debug(f"[KR] {ticker} → Not found")

        return corp_code

    def get_company_name(self, ticker: str) -> Optional[str]:
        """
        Get company name for a ticker

        Args:
            ticker: Korean stock ticker (6-digit code)

        Returns:
            Company name or None

        Example:
            name = mapper.get_company_name('005930')
            # Returns: '삼성전자'
        """
        # Reverse lookup in name_to_id mapping
        corp_code = self.get_corporate_id(ticker)
        if not corp_code:
            return None

        for name, code in self.name_to_id.items():
            if code == corp_code:
                return name

        return None


def main():
    """
    CLI interface for Korean corporate ID mapper

    Usage:
        # Download and build mapping
        python3 modules/mappers/kr_corporate_id_mapper.py --refresh

        # Lookup single ticker
        python3 modules/mappers/kr_corporate_id_mapper.py --ticker 005930

        # Batch lookup
        python3 modules/mappers/kr_corporate_id_mapper.py --file tickers.txt

        # Show statistics
        python3 modules/mappers/kr_corporate_id_mapper.py --stats
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='Korean Corporate ID Mapper - DART corp_code lookup'
    )
    parser.add_argument(
        '--refresh',
        action='store_true',
        help='Download and refresh mapping data'
    )
    parser.add_argument(
        '--ticker',
        type=str,
        help='Look up corporate code for a ticker (e.g., 005930)'
    )
    parser.add_argument(
        '--file',
        type=str,
        help='Look up corporate codes for tickers in file (one per line)'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show mapping statistics'
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize mapper
    mapper = KRCorporateIDMapper()

    # Handle commands
    if args.refresh:
        logger.info("🔄 Refreshing corporate ID mapping...")
        success = mapper.refresh_mapping()
        if success:
            logger.info(f"✅ Refresh complete: {mapper.mapping_count} mappings")
        else:
            logger.error("❌ Refresh failed")
            return 1

    elif args.ticker:
        corp_code = mapper.get_corporate_id(args.ticker)
        company_name = mapper.get_company_name(args.ticker)

        if corp_code:
            print(f"✅ Ticker: {args.ticker}")
            print(f"   Corp Code: {corp_code}")
            print(f"   Company: {company_name or 'N/A'}")
        else:
            print(f"❌ Ticker: {args.ticker} - Not found")
            return 1

    elif args.file:
        with open(args.file, 'r') as f:
            tickers = [line.strip() for line in f if line.strip()]

        results = mapper.get_corporate_ids_batch(tickers)

        print(f"\n{'Ticker':<10} {'Corp Code':<12} {'Status'}")
        print("-" * 40)

        for ticker, corp_code in results.items():
            status = "✅ Found" if corp_code else "❌ Not found"
            print(f"{ticker:<10} {corp_code or 'N/A':<12} {status}")

    elif args.stats:
        stats = mapper.get_statistics()
        print("\n" + "="*50)
        print("Korean Corporate ID Mapper Statistics")
        print("="*50)
        print(f"Region: {stats['region_code']}")
        print(f"Mappings: {stats['mapping_count']:,}")
        print(f"Last Updated: {stats['last_updated']}")
        print(f"Cache Fresh: {stats['cache_fresh']}")
        print(f"Cache Path: {stats['cache_path']}")
        print("="*50 + "\n")

    else:
        parser.print_help()

    return 0


if __name__ == '__main__':
    exit(main())
