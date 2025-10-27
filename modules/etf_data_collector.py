"""
ETF Data Collection Module (Phase 2: Week 2)

Collects ETF holdings data from various sources and populates etfs + etf_holdings tables.

Data Sources by Market:
- KR: etfcheck.co.kr (web scraping)
- US: Polygon.io / ETF.com (API)
- CN/HK: AkShare + yfinance (hybrid)
- JP/VN: yfinance (fallback)

Author: Spock Trading System
Date: 2025-10-17
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ETFDataCollector(ABC):
    """
    Abstract base class for ETF data collection

    Each regional collector handles:
    1. ETF Discovery → etfs table
    2. Holdings Collection → etf_holdings table
    3. Data Enrichment (optional) → etf metadata updates

    Shared resources:
    - Database manager
    - Region code
    - Common caching logic
    - Common database operations
    """

    def __init__(self, db_manager, region_code: str):
        """
        Initialize ETF data collector

        Args:
            db_manager: SQLiteDatabaseManager instance
            region_code: 'KR', 'US', 'CN', 'HK', 'JP', 'VN'
        """
        self.db = db_manager
        self.region_code = region_code

    # ========================================
    # PHASE 1: ETF DISCOVERY
    # ========================================

    @abstractmethod
    def scan_etfs(self, force_refresh: bool = False) -> List[Dict]:
        """
        Discover ETFs and populate etfs table

        Workflow:
        1. Check cache (24-hour TTL)
        2. Fetch from region-specific sources
        3. Parse and enrich ETF metadata
        4. Save to etfs table

        Args:
            force_refresh: Ignore cache and force refresh

        Returns:
            List of ETF dictionaries

        Example return:
            [
                {
                    'ticker': '152100',
                    'name': 'TIGER 200',
                    'region': 'KR',
                    'category': 'Equity',
                    'tracking_index': 'KOSPI 200',
                    'total_assets': 5000000000000,
                    'expense_ratio': 0.15,
                    ...
                },
                ...
            ]
        """
        pass

    # ========================================
    # PHASE 2: HOLDINGS COLLECTION
    # ========================================

    @abstractmethod
    def collect_etf_holdings(
        self,
        etf_tickers: Optional[List[str]] = None,
        as_of_date: str = None
    ) -> int:
        """
        Collect ETF holdings and populate etf_holdings table

        Workflow:
        1. Get ETF list (from DB if not provided)
        2. Fetch holdings from region-specific source
        3. Parse holding data (ticker, weight, shares, etc.)
        4. Save to etf_holdings table

        Args:
            etf_tickers: List of ETF ticker codes (None = all ETFs in region)
            as_of_date: Date for holdings (YYYY-MM-DD). If None, uses today.

        Returns:
            Number of ETFs successfully updated

        Example holdings data:
            {
                'etf_ticker': '152100',
                'stock_ticker': '005930',
                'weight': 25.5,
                'shares': 1000000,
                'market_value': 75000000000,
                'rank_in_etf': 1,
                'sector': 'IT',
                'country': 'KR',
                'as_of_date': '2025-10-17',
                'created_at': '2025-10-17T10:00:00',
                'data_source': 'etfcheck.co.kr',
            }
        """
        pass

    # ========================================
    # PHASE 3: DATA ENRICHMENT (OPTIONAL)
    # ========================================

    def update_etf_metadata(self, etf_tickers: Optional[List[str]] = None) -> int:
        """
        Update ETF metadata (AUM, NAV, expense ratio, etc.)

        Optional: Can be implemented by regional collectors if data available

        Args:
            etf_tickers: List of ETF ticker codes (None = all ETFs)

        Returns:
            Number of ETFs updated
        """
        logger.info(f"[{self.region_code}] ETF metadata update not implemented")
        return 0

    # ========================================
    # SHARED UTILITIES (COMMON LOGIC)
    # ========================================

    def _load_etfs_from_cache(self, ttl_hours: int = 24) -> Optional[List[Dict]]:
        """
        Load ETFs from database cache with TTL check

        Args:
            ttl_hours: Cache time-to-live in hours (default: 24)

        Returns:
            List of cached ETFs or None if cache miss/expired
        """
        try:
            # Check last update time
            last_update = self.db.get_last_update_time(
                region=self.region_code,
                asset_type='ETF'
            )

            if not last_update:
                return None

            # Check TTL
            age = datetime.now() - last_update

            if age > timedelta(hours=ttl_hours):
                logger.info(f"[{self.region_code}] ETF cache expired ({age.total_seconds()/3600:.1f}h)")
                return None

            # Load ETFs from tickers table
            etfs = self.db.get_tickers(
                region=self.region_code,
                asset_type='ETF',
                is_active=True
            )

            logger.info(f"✅ [{self.region_code}] ETF cache hit: {len(etfs)} ETFs")
            return etfs

        except Exception as e:
            logger.warning(f"⚠️ [{self.region_code}] ETF cache load failed: {e}")
            return None

    def _save_etf_to_db(self, etf_data: Dict) -> bool:
        """
        Save single ETF to etfs table

        Args:
            etf_data: ETF dictionary with metadata

        Returns:
            True if successful
        """
        now = datetime.now().isoformat()

        # Ensure required fields
        etf_data['created_at'] = now
        etf_data['last_updated'] = now
        etf_data['region'] = self.region_code

        # Insert into etfs table (Phase 1 schema)
        success = self.db.insert_etf_info(etf_data)

        if success:
            logger.debug(f"✅ [{etf_data['ticker']}] ETF saved to database")
        else:
            logger.error(f"❌ [{etf_data['ticker']}] ETF save failed")

        return success

    def _save_holdings_bulk(self, holdings: List[Dict]) -> int:
        """
        Bulk save ETF holdings to etf_holdings table

        Args:
            holdings: List of holding dictionaries

        Returns:
            Number of holdings inserted
        """
        if not holdings:
            return 0

        now = datetime.now().isoformat()

        # Ensure created_at for all holdings
        for holding in holdings:
            holding['created_at'] = now

        # Bulk insert using database manager
        inserted_count = self.db.insert_etf_holdings_bulk(holdings)

        logger.info(f"💾 [{self.region_code}] Saved {inserted_count} ETF holdings")

        return inserted_count

    def _validate_holding_data(self, holding: Dict) -> bool:
        """
        Validate holding data before insertion

        Args:
            holding: Holding dictionary

        Returns:
            True if valid
        """
        required_fields = ['etf_ticker', 'stock_ticker', 'weight', 'as_of_date']

        for field in required_fields:
            if field not in holding or holding[field] is None:
                logger.warning(f"⚠️ Invalid holding: missing {field}")
                return False

        # Validate weight range (0-100%)
        if not (0 <= holding['weight'] <= 100):
            logger.warning(f"⚠️ Invalid weight: {holding['weight']} (must be 0-100)")
            return False

        return True

    def _cleanup_old_holdings(self, retention_days: int = 365) -> int:
        """
        Delete old holdings based on retention policy

        From Phase 1 design:
        - 30 days: Daily updates (most recent)
        - 90 days: Weekly snapshots
        - 365 days: Monthly snapshots

        Args:
            retention_days: Days to retain (default: 365)

        Returns:
            Number of rows deleted
        """
        deleted_count = self.db.delete_old_etf_holdings(retention_days=retention_days)

        if deleted_count > 0:
            logger.info(f"🗑️  [{self.region_code}] Deleted {deleted_count} old holdings (>{retention_days} days)")

        return deleted_count

    # ========================================
    # REPORTING & DIAGNOSTICS
    # ========================================

    def get_collection_stats(self) -> Dict:
        """
        Get ETF collection statistics

        Returns:
            Dictionary with collection stats
        """
        stats = {
            'region': self.region_code,
            'etf_count': 0,
            'holdings_count': 0,
            'latest_holdings_date': None,
            'coverage_summary': {},
        }

        # ETF count
        stats['etf_count'] = self.db.get_ticker_count(
            region=self.region_code,
            asset_type='ETF'
        )

        # Holdings count (would need custom query in db_manager)
        # For now, placeholder

        logger.info(f"📊 [{self.region_code}] ETF Stats: {stats['etf_count']} ETFs")

        return stats
