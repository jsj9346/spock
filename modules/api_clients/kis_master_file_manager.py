#!/usr/bin/env python3
"""
KIS Master File Manager

Downloads and parses KIS overseas stock master files (.cod files) from DWS server.
Implements file size-based change detection for efficient updates.

Based on: https://github.com/koreainvestment/open-trading-api/blob/main/stocks_info/overseas_stock_code.py

Author: Spock Trading System
Date: 2025-10-15
"""

import pandas as pd
import urllib.request
import ssl
import zipfile
import os
import shutil
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class KISMasterFileManager:
    """
    KIS Master File Manager

    Downloads, parses, and manages overseas stock master files from KIS DWS server.

    Features:
    - File size-based change detection (download only if size changed)
    - Automatic backup and restore
    - Multi-region support (US, CN, HK, JP, VN)
    - Ticker normalization per market
    - Cache management
    """

    # Base URL for master file downloads
    BASE_URL = "https://new.real.download.dws.co.kr/common/master"

    # Region to market code mapping
    MARKET_CODES = {
        'US': ['nas', 'nys', 'ams'],
        'CN': ['shs', 'szs'],  # Exclude 'shi', 'szi' (indices)
        'HK': ['hks'],
        'JP': ['tse'],
        'VN': ['hnx', 'hsx'],
    }

    # Market code to exchange name mapping
    EXCHANGE_NAMES = {
        'nas': 'NASDAQ',
        'nys': 'NYSE',
        'ams': 'AMEX',
        'hks': 'HKEX',
        'shs': 'SSE',
        'szs': 'SZSE',
        'tse': 'TSE',
        'hnx': 'HNX',
        'hsx': 'HOSE',
    }

    # Currency mapping
    CURRENCIES = {
        'US': 'USD',
        'CN': 'CNY',
        'HK': 'HKD',
        'JP': 'JPY',
        'VN': 'VND',
    }

    # Column names for .cod files
    COLUMN_NAMES = [
        'National code', 'Exchange id', 'Exchange code', 'Exchange name',
        'Symbol', 'realtime symbol', 'Korea name', 'English name',
        'Security type', 'currency', 'float position', 'data type',
        'base price', 'Bid order size', 'Ask order size',
        'market start time', 'market end time',
        'DR 여부', 'DR 국가코드', '업종분류코드',
        '지수구성종목 존재 여부', 'Tick size Type',
        '구분코드', 'Tick size type 상세'
    ]

    def __init__(self, cache_dir: str = 'data/master_files'):
        """
        Initialize KIS Master File Manager

        Args:
            cache_dir: Directory to cache downloaded master files
        """
        self.cache_dir = cache_dir
        self.backup_dir = os.path.join(cache_dir, 'backups')

        # Create directories
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)

        # Disable SSL verification (as per KIS example)
        ssl._create_default_https_context = ssl._create_unverified_context

        logger.info(f"KISMasterFileManager initialized (cache: {self.cache_dir})")

    def download_market(self, market_code: str, force: bool = False) -> str:
        """
        Download master file for specific market

        Args:
            market_code: Market code (e.g., 'nas', 'nys', 'hks')
            force: Force download regardless of size check

        Returns:
            Path to extracted .cod file

        Raises:
            ValueError: If market_code is invalid
            IOError: If download or extraction fails
        """
        if not self._is_valid_market_code(market_code):
            raise ValueError(f"Invalid market code: {market_code}")

        # Check if update needed (file size comparison)
        if not force and not self._needs_update(market_code):
            logger.info(f"[{market_code}] No update needed - using cached file")
            return self._get_cod_path(market_code)

        # Backup existing file (if exists)
        self._backup_file(market_code)

        # Download
        url = f"{self.BASE_URL}/{market_code}mst.cod.zip"
        zip_path = os.path.join(self.cache_dir, f"{market_code}mst.cod.zip")
        temp_zip_path = f"{zip_path}.tmp"

        try:
            logger.info(f"[{market_code}] Downloading from {url}")

            # Download to temp file first
            urllib.request.urlretrieve(url, temp_zip_path)

            # Verify download size
            downloaded_size = os.path.getsize(temp_zip_path)
            if downloaded_size == 0:
                raise IOError(f"Downloaded file is empty")

            # Move temp file to final location (atomic operation)
            os.replace(temp_zip_path, zip_path)

            logger.info(f"[{market_code}] Downloaded: {zip_path} ({downloaded_size:,} bytes)")

        except Exception as e:
            # Clean up temp file
            if os.path.exists(temp_zip_path):
                os.remove(temp_zip_path)

            logger.error(f"[{market_code}] Download failed: {e}")

            # Restore from backup if available
            if self._restore_from_backup(market_code):
                logger.info(f"[{market_code}] Restored from backup")
                return self._get_cod_path(market_code)

            raise IOError(f"Download failed and no backup available: {e}")

        # Extract
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.cache_dir)

            cod_path = self._get_cod_path(market_code)
            cod_size = os.path.getsize(cod_path)

            logger.info(f"[{market_code}] Extracted to {cod_path} ({cod_size:,} bytes)")

            return cod_path

        except Exception as e:
            logger.error(f"[{market_code}] Extraction failed: {e}")

            # Restore from backup
            if self._restore_from_backup(market_code):
                logger.info(f"[{market_code}] Restored from backup after extraction failure")
                return self._get_cod_path(market_code)

            raise IOError(f"Extraction failed and no backup available: {e}")

    def parse_market(self, market_code: str) -> pd.DataFrame:
        """
        Parse master file for specific market

        Args:
            market_code: Market code

        Returns:
            DataFrame with parsed stock tickers

        Raises:
            FileNotFoundError: If .cod file doesn't exist
            ValueError: If parsing fails
        """
        cod_path = self._get_cod_path(market_code)

        if not os.path.exists(cod_path):
            raise FileNotFoundError(
                f"Master file not found: {cod_path}. "
                f"Run download_market('{market_code}') first."
            )

        try:
            # Read tab-separated file with cp949 encoding
            df = pd.read_table(
                cod_path,
                sep='\t',
                encoding='cp949',
                names=self.COLUMN_NAMES
            )

            # Filter: Only stocks (Security type == 2)
            # Note: Security type is int, not string
            df = df[df['Security type'] == 2].copy()

            logger.info(f"[{market_code}] Parsed {len(df)} stocks from {cod_path}")

            return df

        except Exception as e:
            logger.error(f"[{market_code}] Parse failed: {e}")
            raise ValueError(f"Failed to parse master file: {e}")

    def get_all_tickers(self, region: str, force_refresh: bool = False) -> List[Dict]:
        """
        Get all tickers for region

        Args:
            region: Region code (US, CN, HK, JP, VN)
            force_refresh: Force download of master files

        Returns:
            List of ticker dictionaries

        Raises:
            ValueError: If region is invalid
        """
        if region not in self.MARKET_CODES:
            raise ValueError(
                f"Invalid region: {region}. "
                f"Valid regions: {', '.join(self.MARKET_CODES.keys())}"
            )

        market_codes = self.MARKET_CODES[region]
        all_tickers = []

        logger.info(f"[{region}] Collecting tickers from {len(market_codes)} markets")

        for market_code in market_codes:
            try:
                # Download (if needed)
                self.download_market(market_code, force=force_refresh)

                # Parse
                df = self.parse_market(market_code)

                # Convert to ticker dictionaries
                for _, row in df.iterrows():
                    # Handle NaN values - convert to string and handle
                    symbol = row['Symbol'] if pd.notna(row['Symbol']) else ''
                    # Convert symbol to string (may be int64 for HK/CN)
                    symbol = str(symbol) if symbol else ''

                    eng_name = row['English name'] if pd.notna(row['English name']) else ''
                    kor_name = row.get('Korea name', '')
                    kor_name = kor_name if pd.notna(kor_name) else ''
                    sector_code = row.get('업종분류코드', '')
                    sector_code = str(sector_code) if pd.notna(sector_code) else ''

                    # Skip if no valid symbol
                    if not symbol or symbol == 'nan':
                        continue

                    ticker_info = {
                        'ticker': self._normalize_ticker(symbol, market_code),
                        'name': eng_name,
                        'name_kor': kor_name,
                        'exchange': self._get_exchange_name(market_code),
                        'region': region,
                        'currency': self._get_currency(region),
                        'sector_code': sector_code,
                        'market_code': market_code,
                    }
                    all_tickers.append(ticker_info)

            except Exception as e:
                logger.error(f"[{market_code}] Failed to collect tickers: {e}")
                # Continue with other markets
                continue

        logger.info(f"[{region}] Total tickers collected: {len(all_tickers)}")

        return all_tickers

    def get_ticker_count(self, market_code: str) -> int:
        """
        Get ticker count for specific market without parsing

        Args:
            market_code: Market code

        Returns:
            Number of tickers (stocks only)
        """
        try:
            df = self.parse_market(market_code)
            return len(df)
        except:
            return 0

    def _needs_update(self, market_code: str) -> bool:
        """
        Check if master file needs update (size comparison)

        Args:
            market_code: Market code

        Returns:
            True if update needed (remote zip size > local zip size or file doesn't exist)
        """
        local_zip_path = os.path.join(self.cache_dir, f"{market_code}mst.cod.zip")
        local_cod_path = self._get_cod_path(market_code)

        if not os.path.exists(local_cod_path):
            logger.info(f"[{market_code}] Local file doesn't exist - download required")
            return True

        # If we don't have the zip file, we need to download to compare
        if not os.path.exists(local_zip_path):
            logger.info(f"[{market_code}] Local zip doesn't exist - download required")
            return True

        # Get local zip file size
        local_size = os.path.getsize(local_zip_path)

        # Get remote zip file size via HTTP HEAD request
        url = f"{self.BASE_URL}/{market_code}mst.cod.zip"

        try:
            req = urllib.request.Request(url, method='HEAD')
            with urllib.request.urlopen(req, timeout=10) as response:
                remote_size = int(response.headers.get('Content-Length', 0))

        except Exception as e:
            logger.warning(f"[{market_code}] Failed to check remote size: {e}")
            return False  # Can't check, don't download

        # Compare sizes (zip to zip)
        if remote_size > local_size:
            logger.info(
                f"[{market_code}] Update needed: "
                f"local zip={local_size:,} bytes, remote zip={remote_size:,} bytes "
                f"(+{remote_size - local_size:,} bytes)"
            )
            return True

        elif remote_size < local_size:
            logger.warning(
                f"[{market_code}] Remote zip smaller than local "
                f"(local={local_size:,}, remote={remote_size:,}) - "
                f"possible delisting or corruption, will download"
            )
            return True

        else:
            logger.info(f"[{market_code}] File unchanged ({local_size:,} bytes) - skip")
            return False

    def _backup_file(self, market_code: str) -> Optional[str]:
        """
        Create timestamped backup of master file

        Args:
            market_code: Market code

        Returns:
            Path to backup file, or None if no file to backup
        """
        cod_path = self._get_cod_path(market_code)

        if not os.path.exists(cod_path):
            return None

        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"{market_code}mst.cod.{timestamp}.bak"
        backup_path = os.path.join(self.backup_dir, backup_filename)

        try:
            shutil.copy2(cod_path, backup_path)
            logger.info(f"[{market_code}] Backup created: {backup_path}")

            # Cleanup old backups (keep last 7)
            self._cleanup_old_backups(market_code, keep=7)

            return backup_path

        except Exception as e:
            logger.warning(f"[{market_code}] Backup failed: {e}")
            return None

    def _restore_from_backup(self, market_code: str) -> bool:
        """
        Restore most recent backup

        Args:
            market_code: Market code

        Returns:
            True if restore successful
        """
        backups = self._list_backups(market_code)

        if not backups:
            logger.warning(f"[{market_code}] No backups found")
            return False

        # Get most recent backup
        latest_backup = backups[0]
        cod_path = self._get_cod_path(market_code)

        try:
            shutil.copy2(latest_backup, cod_path)
            logger.info(f"[{market_code}] Restored from backup: {latest_backup}")
            return True

        except Exception as e:
            logger.error(f"[{market_code}] Restore failed: {e}")
            return False

    def _list_backups(self, market_code: str) -> List[str]:
        """
        List all backups for given market, sorted by timestamp (newest first)

        Args:
            market_code: Market code

        Returns:
            List of backup file paths
        """
        if not os.path.exists(self.backup_dir):
            return []

        backups = []
        prefix = f"{market_code}mst.cod."

        for filename in os.listdir(self.backup_dir):
            if filename.startswith(prefix) and filename.endswith('.bak'):
                backup_path = os.path.join(self.backup_dir, filename)
                backups.append(backup_path)

        # Sort by modification time (newest first)
        backups.sort(key=os.path.getmtime, reverse=True)

        return backups

    def _cleanup_old_backups(self, market_code: str, keep: int = 7):
        """
        Delete old backups beyond keep limit

        Args:
            market_code: Market code
            keep: Number of backups to keep
        """
        backups = self._list_backups(market_code)

        if len(backups) > keep:
            for old_backup in backups[keep:]:
                try:
                    os.remove(old_backup)
                    logger.info(f"[{market_code}] Deleted old backup: {old_backup}")
                except Exception as e:
                    logger.warning(f"[{market_code}] Failed to delete backup: {e}")

    def _normalize_ticker(self, symbol: str, market_code: str) -> str:
        """
        Normalize ticker symbol based on market

        Args:
            symbol: Raw ticker symbol
            market_code: Market code

        Returns:
            Normalized ticker symbol
        """
        # US markets: Use as-is (AAPL, MSFT)
        if market_code in ['nas', 'nys', 'ams']:
            return symbol.strip().upper()

        # Hong Kong: Add .HK suffix if not present
        elif market_code == 'hks':
            symbol = symbol.strip()
            if not symbol.endswith('.HK'):
                # Pad to 4 digits: 700 → 0700.HK
                symbol = symbol.zfill(4) + '.HK'
            return symbol

        # China: Add .SS or .SZ suffix
        elif market_code == 'shs':
            symbol = symbol.strip()
            if not symbol.endswith('.SS'):
                symbol = symbol + '.SS'
            return symbol

        elif market_code == 'szs':
            symbol = symbol.strip()
            if not symbol.endswith('.SZ'):
                symbol = symbol + '.SZ'
            return symbol

        # Japan: Use 4-digit code (7203)
        elif market_code == 'tse':
            return symbol.strip()

        # Vietnam: 3-letter uppercase (VCB, FPT)
        elif market_code in ['hnx', 'hsx']:
            return symbol.strip().upper()

        return symbol.strip()

    def _get_exchange_name(self, market_code: str) -> str:
        """Get exchange name from market code"""
        return self.EXCHANGE_NAMES.get(market_code, market_code.upper())

    def _get_currency(self, region: str) -> str:
        """Get currency from region"""
        return self.CURRENCIES.get(region, 'USD')

    def _get_cod_path(self, market_code: str) -> str:
        """Get path to .cod file"""
        return os.path.join(self.cache_dir, f"{market_code}mst.cod")

    def _is_valid_market_code(self, market_code: str) -> bool:
        """Check if market code is valid"""
        all_codes = []
        for codes in self.MARKET_CODES.values():
            all_codes.extend(codes)
        return market_code in all_codes

    def get_cache_status(self) -> Dict:
        """
        Get cache status for all markets

        Returns:
            Dictionary with cache status information
        """
        status = {}

        for region, market_codes in self.MARKET_CODES.items():
            for market_code in market_codes:
                cod_path = self._get_cod_path(market_code)

                if os.path.exists(cod_path):
                    file_size = os.path.getsize(cod_path)
                    modified_time = datetime.fromtimestamp(os.path.getmtime(cod_path))
                    ticker_count = self.get_ticker_count(market_code)

                    status[market_code] = {
                        'cached': True,
                        'file_size': file_size,
                        'modified': modified_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'ticker_count': ticker_count,
                        'exchange': self._get_exchange_name(market_code),
                        'region': region,
                    }
                else:
                    status[market_code] = {
                        'cached': False,
                        'exchange': self._get_exchange_name(market_code),
                        'region': region,
                    }

        return status

    def clear_cache(self, market_code: Optional[str] = None):
        """
        Clear cache files

        Args:
            market_code: Specific market code to clear, or None for all
        """
        if market_code:
            # Clear specific market
            cod_path = self._get_cod_path(market_code)
            zip_path = os.path.join(self.cache_dir, f"{market_code}mst.cod.zip")

            for path in [cod_path, zip_path]:
                if os.path.exists(path):
                    os.remove(path)
                    logger.info(f"[{market_code}] Removed: {path}")

        else:
            # Clear all
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.cod') or filename.endswith('.zip'):
                    file_path = os.path.join(self.cache_dir, filename)
                    os.remove(file_path)
                    logger.info(f"Removed: {file_path}")


def main():
    """Test and demonstration"""
    import sys

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    manager = KISMasterFileManager()

    # Show cache status
    print("\n" + "=" * 80)
    print("Cache Status")
    print("=" * 80)

    status = manager.get_cache_status()
    for market_code, info in status.items():
        if info['cached']:
            print(
                f"[{market_code}] {info['exchange']:10} "
                f"| {info['ticker_count']:5,} stocks "
                f"| {info['file_size']:10,} bytes "
                f"| Modified: {info['modified']}"
            )
        else:
            print(f"[{market_code}] {info['exchange']:10} | Not cached")

    # Download and parse US markets
    print("\n" + "=" * 80)
    print("Testing US Market Download")
    print("=" * 80)

    try:
        us_tickers = manager.get_all_tickers('US', force_refresh=True)
        print(f"\n✅ Successfully collected {len(us_tickers):,} US tickers")

        # Show sample
        print("\nSample tickers (first 5):")
        for ticker in us_tickers[:5]:
            print(
                f"  {ticker['ticker']:10} | "
                f"{ticker['name'][:40]:40} | "
                f"{ticker['exchange']:8} | "
                f"{ticker['currency']}"
            )

    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
