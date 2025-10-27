"""
Blacklist Manager - Dual-System Ticker Filtering

Manages both DB-based (permanent deactivation) and file-based (temporary exclusion)
blacklists for multi-region stock markets (KR, US, CN, HK, JP, VN).

Author: Spock Trading System
Created: 2025-10-17
"""

import json
import os
from datetime import datetime, date
from typing import Dict, List, Optional, Set
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class BlacklistManager:
    """
    Dual-system blacklist manager for global stock markets

    System 1 (DB-based): Permanent deactivation (is_active=False)
        - Delisted stocks
        - Trading halted stocks
        - Data quality issues

    System 2 (File-based): Temporary exclusion with reason tracking
        - Investor personal judgment
        - Temporary exclusion with expiry date
        - Audit trail and compliance
    """

    # Valid regions (Phase 1-6)
    VALID_REGIONS = ['KR', 'US', 'CN', 'HK', 'JP', 'VN']

    # Ticker format validation patterns per region
    TICKER_PATTERNS = {
        'KR': r'^\d{6}$',                    # 6-digit numeric
        'US': r'^[A-Z]{1,5}(\.[A-Z])?$',    # 1-5 letters, optional .A/.B
        'CN': r'^\d{6}\.(SS|SZ)$',          # 6-digit with .SS/.SZ
        'HK': r'^\d{4,5}(\.HK)?$',          # 4-5 digit with optional .HK
        'JP': r'^\d{4}$',                    # 4-digit numeric
        'VN': r'^[A-Z]{3}$'                  # 3-letter uppercase
    }

    def __init__(self, db_manager, config_path: str = "config/stock_blacklist.json"):
        """
        Initialize blacklist manager

        Args:
            db_manager: SQLiteDatabaseManager instance
            config_path: Path to blacklist JSON file
        """
        self.db = db_manager
        self.config_path = config_path
        self._file_blacklist: Dict[str, Dict[str, Dict]] = {}
        self._load_file_blacklist()

    # ========================================
    # SYSTEM 1: DB-BASED PERMANENT BLACKLIST
    # ========================================

    def deactivate_ticker_db(self, ticker: str, region: str, reason: str = None) -> bool:
        """
        Permanently deactivate ticker in database (is_active=False)

        Use cases:
        - Delisted stocks
        - Trading halted permanently
        - Data quality failures

        Args:
            ticker: Ticker code
            region: Region code (KR, US, CN, HK, JP, VN)
            reason: Deactivation reason (optional, logged)

        Returns:
            True if successful, False otherwise
        """
        if not self._validate_region(region):
            logger.error(f"❌ Invalid region: {region}")
            return False

        if not self._validate_ticker_format(ticker, region):
            logger.error(f"❌ Invalid ticker format for {region}: {ticker}")
            return False

        try:
            # Update is_active=False in tickers table
            conn = self.db._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE tickers
                SET is_active = 0,
                    last_updated = ?
                WHERE ticker = ? AND region = ?
            """, (datetime.now().isoformat(), ticker, region))

            if cursor.rowcount == 0:
                logger.warning(f"⚠️ Ticker not found in DB: {region}:{ticker}")
                conn.close()
                return False

            conn.commit()
            conn.close()

            log_reason = f" (reason: {reason})" if reason else ""
            logger.info(f"✅ Deactivated in DB: {region}:{ticker}{log_reason}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to deactivate {region}:{ticker}: {e}")
            return False

    def reactivate_ticker_db(self, ticker: str, region: str) -> bool:
        """
        Reactivate ticker in database (is_active=True)

        Args:
            ticker: Ticker code
            region: Region code

        Returns:
            True if successful, False otherwise
        """
        if not self._validate_region(region):
            logger.error(f"❌ Invalid region: {region}")
            return False

        try:
            conn = self.db._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE tickers
                SET is_active = 1,
                    last_updated = ?
                WHERE ticker = ? AND region = ?
            """, (datetime.now().isoformat(), ticker, region))

            if cursor.rowcount == 0:
                logger.warning(f"⚠️ Ticker not found in DB: {region}:{ticker}")
                conn.close()
                return False

            conn.commit()
            conn.close()

            logger.info(f"✅ Reactivated in DB: {region}:{ticker}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to reactivate {region}:{ticker}: {e}")
            return False

    def get_db_blacklist(self, region: str = None) -> Dict[str, List[str]]:
        """
        Get list of deactivated tickers from database

        Args:
            region: Filter by region (None = all regions)

        Returns:
            Dict mapping region to list of deactivated tickers
            Example: {'KR': ['005930', '000660'], 'US': ['TSLA']}
        """
        try:
            conn = self.db._get_connection()
            cursor = conn.cursor()

            if region:
                if not self._validate_region(region):
                    logger.error(f"❌ Invalid region: {region}")
                    return {}

                cursor.execute("""
                    SELECT ticker FROM tickers
                    WHERE region = ? AND is_active = 0
                    ORDER BY ticker
                """, (region,))

                tickers = [row[0] for row in cursor.fetchall()]
                conn.close()
                return {region: tickers}
            else:
                cursor.execute("""
                    SELECT region, ticker FROM tickers
                    WHERE is_active = 0
                    ORDER BY region, ticker
                """)

                result: Dict[str, List[str]] = {r: [] for r in self.VALID_REGIONS}
                for region, ticker in cursor.fetchall():
                    if region in result:
                        result[region].append(ticker)

                conn.close()
                return result

        except Exception as e:
            logger.error(f"❌ Failed to get DB blacklist: {e}")
            return {}

    # ========================================
    # SYSTEM 2: FILE-BASED TEMPORARY BLACKLIST
    # ========================================

    def add_to_file_blacklist(self,
                              ticker: str,
                              region: str,
                              reason: str,
                              added_by: str = "user",
                              expire_date: Optional[str] = None,
                              notes: Optional[str] = None) -> bool:
        """
        Add ticker to file-based blacklist (temporary exclusion)

        Use cases:
        - Personal investment judgment
        - Temporary exclusion with expiry
        - Requires audit trail

        Args:
            ticker: Ticker code
            region: Region code
            reason: Exclusion reason (required)
            added_by: Who added it (system, user, analyst)
            expire_date: Expiry date (YYYY-MM-DD format, None=permanent)
            notes: Additional notes

        Returns:
            True if successful, False otherwise
        """
        if not self._validate_region(region):
            logger.error(f"❌ Invalid region: {region}")
            return False

        if not self._validate_ticker_format(ticker, region):
            logger.error(f"❌ Invalid ticker format for {region}: {ticker}")
            return False

        if not reason or reason.strip() == "":
            logger.error(f"❌ Reason is required for blacklisting")
            return False

        # Get ticker name from DB
        ticker_name = self._get_ticker_name(ticker, region)

        # Ensure region exists in blacklist
        if region not in self._file_blacklist:
            self._file_blacklist[region] = {}

        # Add ticker to blacklist
        self._file_blacklist[region][ticker] = {
            "name": ticker_name,
            "reason": reason,
            "added_date": datetime.now().strftime("%Y-%m-%d"),
            "added_by": added_by,
            "expire_date": expire_date,
            "notes": notes
        }

        # Save to file
        if self._save_file_blacklist():
            logger.info(f"✅ Added to file blacklist: {region}:{ticker} (reason: {reason})")
            return True
        else:
            logger.error(f"❌ Failed to save file blacklist")
            return False

    def remove_from_file_blacklist(self, ticker: str, region: str) -> bool:
        """
        Remove ticker from file-based blacklist

        Args:
            ticker: Ticker code
            region: Region code

        Returns:
            True if successful, False otherwise
        """
        if not self._validate_region(region):
            logger.error(f"❌ Invalid region: {region}")
            return False

        if region not in self._file_blacklist or ticker not in self._file_blacklist[region]:
            logger.warning(f"⚠️ Ticker not in file blacklist: {region}:{ticker}")
            return False

        del self._file_blacklist[region][ticker]

        if self._save_file_blacklist():
            logger.info(f"✅ Removed from file blacklist: {region}:{ticker}")
            return True
        else:
            logger.error(f"❌ Failed to save file blacklist")
            return False

    def get_file_blacklist(self, region: str = None, include_expired: bool = False) -> Dict[str, List[str]]:
        """
        Get list of tickers from file-based blacklist

        Args:
            region: Filter by region (None = all regions)
            include_expired: Include expired entries (default: False)

        Returns:
            Dict mapping region to list of blacklisted tickers
        """
        result: Dict[str, List[str]] = {}

        regions_to_check = [region] if region else self.VALID_REGIONS

        for r in regions_to_check:
            if r not in self._file_blacklist:
                result[r] = []
                continue

            tickers = []
            for ticker, info in self._file_blacklist[r].items():
                # Check expiry
                if not include_expired and info.get('expire_date'):
                    try:
                        expire_date = datetime.strptime(info['expire_date'], '%Y-%m-%d').date()
                        if expire_date < date.today():
                            continue  # Skip expired entries
                    except ValueError:
                        logger.warning(f"⚠️ Invalid expire_date format: {info['expire_date']}")

                tickers.append(ticker)

            result[r] = tickers

        return result

    # ========================================
    # UNIFIED FILTERING API
    # ========================================

    def is_blacklisted(self, ticker: str, region: str) -> bool:
        """
        Check if ticker is blacklisted (DB OR file-based)

        Args:
            ticker: Ticker code
            region: Region code

        Returns:
            True if blacklisted, False otherwise
        """
        # Check DB blacklist (is_active=False)
        try:
            conn = self.db._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT is_active FROM tickers
                WHERE ticker = ? AND region = ?
            """, (ticker, region))

            result = cursor.fetchone()
            conn.close()

            if result and result[0] == 0:  # is_active=False
                return True
        except Exception as e:
            logger.warning(f"⚠️ Failed to check DB blacklist: {e}")

        # Check file blacklist (with expiry check)
        file_blacklist = self.get_file_blacklist(region=region, include_expired=False)
        if region in file_blacklist and ticker in file_blacklist[region]:
            return True

        return False

    def filter_blacklisted_tickers(self, tickers: List[str], region: str) -> List[str]:
        """
        Filter out blacklisted tickers from list

        Args:
            tickers: List of ticker codes
            region: Region code

        Returns:
            List of non-blacklisted tickers
        """
        if not self._validate_region(region):
            logger.error(f"❌ Invalid region: {region}")
            return tickers

        # Get all blacklisted tickers (DB + file)
        db_blacklist = self.get_db_blacklist(region=region).get(region, [])
        file_blacklist = self.get_file_blacklist(region=region, include_expired=False).get(region, [])

        all_blacklisted = set(db_blacklist + file_blacklist)

        filtered = [t for t in tickers if t not in all_blacklisted]

        removed_count = len(tickers) - len(filtered)
        if removed_count > 0:
            logger.info(f"🔍 Filtered {removed_count} blacklisted tickers from {region}")

        return filtered

    def get_combined_blacklist(self, region: str = None) -> Dict[str, Set[str]]:
        """
        Get combined blacklist (DB + file) as sets for fast lookup

        Args:
            region: Filter by region (None = all regions)

        Returns:
            Dict mapping region to set of blacklisted tickers
        """
        db_blacklist = self.get_db_blacklist(region=region)
        file_blacklist = self.get_file_blacklist(region=region, include_expired=False)

        result: Dict[str, Set[str]] = {}

        regions_to_process = [region] if region else self.VALID_REGIONS

        for r in regions_to_process:
            db_set = set(db_blacklist.get(r, []))
            file_set = set(file_blacklist.get(r, []))
            result[r] = db_set.union(file_set)

        return result

    # ========================================
    # MAINTENANCE & UTILITIES
    # ========================================

    def cleanup_expired_entries(self) -> int:
        """
        Remove expired entries from file-based blacklist

        Returns:
            Number of entries removed
        """
        removed_count = 0
        today = date.today()

        for region in list(self._file_blacklist.keys()):
            for ticker in list(self._file_blacklist[region].keys()):
                info = self._file_blacklist[region][ticker]
                expire_date_str = info.get('expire_date')

                if expire_date_str:
                    try:
                        expire_date = datetime.strptime(expire_date_str, '%Y-%m-%d').date()
                        if expire_date < today:
                            del self._file_blacklist[region][ticker]
                            removed_count += 1
                            logger.info(f"🗑️ Removed expired entry: {region}:{ticker}")
                    except ValueError:
                        logger.warning(f"⚠️ Invalid expire_date: {expire_date_str}")

        if removed_count > 0:
            self._save_file_blacklist()

        return removed_count

    def get_blacklist_summary(self) -> Dict:
        """
        Get summary statistics of blacklist system

        Returns:
            Dict with summary information
        """
        db_blacklist = self.get_db_blacklist()
        file_blacklist = self.get_file_blacklist(include_expired=False)

        summary = {
            "total_db_blacklist": sum(len(tickers) for tickers in db_blacklist.values()),
            "total_file_blacklist": sum(len(tickers) for tickers in file_blacklist.values()),
            "by_region": {}
        }

        for region in self.VALID_REGIONS:
            db_count = len(db_blacklist.get(region, []))
            file_count = len(file_blacklist.get(region, []))
            summary["by_region"][region] = {
                "db_blacklist": db_count,
                "file_blacklist": file_count,
                "total": db_count + file_count
            }

        return summary

    # ========================================
    # PRIVATE METHODS
    # ========================================

    def _load_file_blacklist(self):
        """Load blacklist from JSON file"""
        try:
            # Ensure config directory exists
            config_dir = os.path.dirname(self.config_path)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
                logger.info(f"📁 Created config directory: {config_dir}")

            if not os.path.exists(self.config_path):
                # Create empty blacklist file
                self._file_blacklist = {region: {} for region in self.VALID_REGIONS}
                self._save_file_blacklist()
                logger.info(f"✅ Created empty blacklist file: {self.config_path}")
                return

            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self._file_blacklist = data.get('blacklist', {})

            # Ensure all regions exist
            for region in self.VALID_REGIONS:
                if region not in self._file_blacklist:
                    self._file_blacklist[region] = {}

            logger.info(f"✅ Loaded blacklist from: {self.config_path}")

        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in blacklist file: {e}")
            # Backup corrupted file
            backup_path = f"{self.config_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            if os.path.exists(self.config_path):
                import shutil
                shutil.copy2(self.config_path, backup_path)
                logger.info(f"📋 Backed up corrupted file: {backup_path}")

            # Create empty blacklist
            self._file_blacklist = {region: {} for region in self.VALID_REGIONS}
            self._save_file_blacklist()

        except Exception as e:
            logger.error(f"❌ Failed to load blacklist file: {e}")
            self._file_blacklist = {region: {} for region in self.VALID_REGIONS}

    def _save_file_blacklist(self) -> bool:
        """Save blacklist to JSON file"""
        try:
            # Ensure directory exists
            config_dir = os.path.dirname(self.config_path)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)

            data = {
                "version": "2.0",
                "last_updated": datetime.now().isoformat(),
                "blacklist": self._file_blacklist
            }

            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug(f"💾 Saved blacklist to: {self.config_path}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to save blacklist file: {e}")
            return False

    def _validate_region(self, region: str) -> bool:
        """Validate region code"""
        return region in self.VALID_REGIONS

    def _validate_ticker_format(self, ticker: str, region: str) -> bool:
        """Validate ticker format for region"""
        import re

        if region not in self.TICKER_PATTERNS:
            return True  # Skip validation if pattern not defined

        pattern = self.TICKER_PATTERNS[region]
        return bool(re.match(pattern, ticker))

    def _get_ticker_name(self, ticker: str, region: str) -> str:
        """Get ticker name from database"""
        try:
            conn = self.db._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM tickers
                WHERE ticker = ? AND region = ?
            """, (ticker, region))

            result = cursor.fetchone()
            conn.close()

            if result:
                return result[0]
            else:
                return "Unknown"

        except Exception as e:
            logger.warning(f"⚠️ Failed to get ticker name: {e}")
            return "Unknown"


# ========================================
# CONVENIENCE FUNCTIONS
# ========================================

def create_blacklist_manager(db_manager) -> BlacklistManager:
    """
    Factory function to create BlacklistManager instance

    Args:
        db_manager: SQLiteDatabaseManager instance

    Returns:
        BlacklistManager instance
    """
    return BlacklistManager(db_manager)
