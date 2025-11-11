"""
Ticker Refresh System - Multi-region ticker synchronization

Handles:
- Multi-region ticker refresh (KR, US, HK, JP, CN, VN)
- Stock and ETF filtering (exclude OTC)
- New listing detection
- Delisting detection
- Ticker metadata updates
"""

from typing import Dict, List, Optional, Set
from datetime import datetime, date
import logging
from dataclasses import dataclass

from modules.db_manager_postgres import PostgresDatabaseManager


@dataclass
class TickerChange:
    """Represents a change in ticker status"""
    ticker: str
    region: str
    change_type: str  # 'new', 'updated', 'delisted'
    metadata: Dict
    timestamp: datetime


class TickerRefresher:
    """Multi-region ticker refresh system"""

    # Supported regions
    SUPPORTED_REGIONS = ['KR', 'US', 'HK', 'JP', 'CN', 'VN']

    # Asset types to include
    VALID_ASSET_TYPES = ['STOCK', 'ETF']

    def __init__(self, db_manager: Optional[PostgresDatabaseManager] = None,
                 kis_app_key: Optional[str] = None,
                 kis_app_secret: Optional[str] = None):
        """
        Initialize TickerRefresher

        Args:
            db_manager: Database manager instance. If None, creates new instance.
            kis_app_key: KIS API app key (required for KR market)
            kis_app_secret: KIS API app secret (required for KR market)
        """
        self.db = db_manager or PostgresDatabaseManager()
        self.logger = logging.getLogger(__name__)

        # Store KIS credentials for KR adapter
        self.kis_app_key = kis_app_key
        self.kis_app_secret = kis_app_secret

        # If credentials not provided, try to load from environment
        if not self.kis_app_key or not self.kis_app_secret:
            self._load_kis_credentials()

        # Market adapters will be imported lazily to avoid circular imports
        self._adapters = {}

    def refresh_all_regions(self, incremental: bool = True) -> Dict[str, Dict]:
        """
        Refresh tickers for all supported regions

        Args:
            incremental: If True, only check for changes. If False, full refresh.

        Returns:
            Dict mapping region to refresh statistics
        """
        results = {}

        for region in self.SUPPORTED_REGIONS:
            try:
                self.logger.info(f"Refreshing tickers for region: {region}")
                result = self.refresh_region(region, incremental)
                results[region] = result

            except Exception as e:
                self.logger.error(f"Failed to refresh {region}: {e}")
                results[region] = {'status': 'error', 'error': str(e)}

        return results

    def refresh_region(self, region: str, incremental: bool = True) -> Dict:
        """
        Refresh tickers for a specific region

        Args:
            region: Region code (KR, US, HK, JP, CN, VN)
            incremental: If True, only check for changes

        Returns:
            Refresh statistics dict
        """
        if region not in self.SUPPORTED_REGIONS:
            raise ValueError(f"Unsupported region: {region}")

        self.logger.info(f"Starting ticker refresh for {region} (incremental={incremental})")

        # 1. Fetch live tickers from exchange
        live_tickers = self._fetch_live_tickers(region)
        self.logger.info(f"Fetched {len(live_tickers)} live tickers from {region}")

        # 2. Validate and filter
        valid_tickers = self._validate_tickers(live_tickers, region)
        self.logger.info(f"Validated {len(valid_tickers)} tickers (filtered out {len(live_tickers) - len(valid_tickers)})")

        # 3. Get existing tickers from database
        existing_tickers = self._get_existing_tickers(region)
        self.logger.info(f"Found {len(existing_tickers)} existing tickers in database")

        # 4. Detect changes
        changes = self._detect_changes(valid_tickers, existing_tickers, region)

        # 5. Apply updates
        stats = self._apply_updates(changes, region)

        self.logger.info(f"Ticker refresh completed for {region}: {stats}")
        return stats

    def _fetch_live_tickers(self, region: str) -> List[Dict]:
        """
        Fetch live tickers from exchange API

        Args:
            region: Region code

        Returns:
            List of ticker dictionaries
        """
        adapter = self._get_adapter(region)

        try:
            if region == 'KR':
                # Use pykrx for Korean market
                tickers = adapter.fetch_kr_tickers()
            elif region == 'US':
                # Use yfinance for US market
                tickers = adapter.fetch_us_tickers()
            else:
                # Use appropriate adapter for other regions
                tickers = adapter.fetch_tickers()

            return tickers

        except Exception as e:
            self.logger.error(f"Failed to fetch tickers from {region}: {e}")
            raise

    def _validate_tickers(self, tickers: List[Dict], region: str) -> List[Dict]:
        """
        Validate and filter tickers

        Filters out:
        - OTC tickers
        - Invalid ticker symbols
        - Non-supported asset types

        Args:
            tickers: List of raw ticker data
            region: Region code

        Returns:
            List of validated ticker dictionaries
        """
        valid_tickers = []

        for ticker in tickers:
            # Check asset type
            asset_type = ticker.get('asset_type', '').upper()
            if asset_type not in self.VALID_ASSET_TYPES:
                continue

            # Check for OTC
            if self._is_otc_ticker(ticker, region):
                continue

            # Validate ticker symbol
            if not self._is_valid_ticker_symbol(ticker['ticker'], region):
                continue

            valid_tickers.append(ticker)

        return valid_tickers

    def _is_otc_ticker(self, ticker: Dict, region: str) -> bool:
        """
        Check if ticker is from OTC market

        Args:
            ticker: Ticker data dictionary
            region: Region code

        Returns:
            True if ticker is OTC
        """
        if region == 'US':
            # US OTC indicators
            symbol = ticker.get('ticker', '')
            exchange = ticker.get('exchange', '').upper()

            # Check for OTC exchanges
            otc_exchanges = ['OTCMKTS', 'PINK', 'OTCQB', 'OTCQX']
            if exchange in otc_exchanges:
                return True

            # Check for OTC suffix patterns
            if symbol.endswith('.PK') or symbol.endswith('.OB'):
                return True

        # Add region-specific OTC detection logic here

        return False

    def _is_valid_ticker_symbol(self, ticker: str, region: str) -> bool:
        """
        Validate ticker symbol format

        Args:
            ticker: Ticker symbol
            region: Region code

        Returns:
            True if ticker symbol is valid
        """
        if not ticker or len(ticker) == 0:
            return False

        if region == 'KR':
            # Korean tickers are 6-digit numbers
            return ticker.isdigit() and len(ticker) == 6

        elif region == 'US':
            # US tickers are 1-5 uppercase letters
            return ticker.isalpha() and ticker.isupper() and 1 <= len(ticker) <= 5

        # Add region-specific validation logic here

        return True

    def _get_existing_tickers(self, region: str) -> Dict[str, Dict]:
        """
        Get existing tickers from database

        Args:
            region: Region code

        Returns:
            Dict mapping ticker symbol to ticker data
        """
        query = """
            SELECT ticker, name, asset_type, exchange, status,
                   listing_date, delisting_date, last_updated
            FROM tickers
            WHERE region = %s
        """

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (region,))
            rows = cursor.fetchall()

            return {
                row[0]: {
                    'ticker': row[0],
                    'name': row[1],
                    'asset_type': row[2],
                    'exchange': row[3],
                    'status': row[4],
                    'listing_date': row[5],
                    'delisting_date': row[6],
                    'last_updated': row[7]
                }
                for row in rows
            }

    def _detect_changes(self, valid_tickers: List[Dict],
                       existing_tickers: Dict[str, Dict],
                       region: str) -> List[TickerChange]:
        """
        Detect changes between live and existing tickers

        Args:
            valid_tickers: List of validated live tickers
            existing_tickers: Dict of existing tickers from database
            region: Region code

        Returns:
            List of TickerChange objects
        """
        changes = []
        live_ticker_symbols = {t['ticker'] for t in valid_tickers}

        # Detect new tickers
        for ticker_data in valid_tickers:
            ticker = ticker_data['ticker']

            if ticker not in existing_tickers:
                changes.append(TickerChange(
                    ticker=ticker,
                    region=region,
                    change_type='new',
                    metadata=ticker_data,
                    timestamp=datetime.now()
                ))

            # Detect updated tickers
            elif self._has_metadata_changed(ticker_data, existing_tickers[ticker]):
                changes.append(TickerChange(
                    ticker=ticker,
                    region=region,
                    change_type='updated',
                    metadata=ticker_data,
                    timestamp=datetime.now()
                ))

        # Detect delisted tickers
        for ticker, ticker_data in existing_tickers.items():
            if ticker_data['status'] == 'active' and ticker not in live_ticker_symbols:
                changes.append(TickerChange(
                    ticker=ticker,
                    region=region,
                    change_type='delisted',
                    metadata=ticker_data,
                    timestamp=datetime.now()
                ))

        return changes

    def _has_metadata_changed(self, live_data: Dict, db_data: Dict) -> bool:
        """
        Check if ticker metadata has changed

        Args:
            live_data: Live ticker data
            db_data: Database ticker data

        Returns:
            True if metadata has changed
        """
        # Compare key fields
        fields_to_compare = ['name', 'exchange', 'asset_type']

        for field in fields_to_compare:
            if live_data.get(field) != db_data.get(field):
                return True

        return False

    def _apply_updates(self, changes: List[TickerChange], region: str) -> Dict:
        """
        Apply ticker changes to database

        Args:
            changes: List of TickerChange objects
            region: Region code

        Returns:
            Statistics dictionary
        """
        stats = {
            'new': 0,
            'updated': 0,
            'delisted': 0,
            'errors': 0
        }

        for change in changes:
            try:
                if change.change_type == 'new':
                    self._insert_new_ticker(change)
                    stats['new'] += 1

                elif change.change_type == 'updated':
                    self._update_existing_ticker(change)
                    stats['updated'] += 1

                elif change.change_type == 'delisted':
                    self._mark_delisted_ticker(change)
                    stats['delisted'] += 1

            except Exception as e:
                self.logger.error(f"Failed to apply change for {change.ticker}: {e}")
                stats['errors'] += 1

        return stats

    def _insert_new_ticker(self, change: TickerChange):
        """Insert new ticker into database"""
        query = """
            INSERT INTO tickers (
                ticker, region, name, asset_type, exchange, status,
                listing_date, last_updated
            ) VALUES (
                %s, %s, %s, %s, %s, 'active', %s, %s
            )
        """

        metadata = change.metadata

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                change.ticker,
                change.region,
                metadata.get('name'),
                metadata.get('asset_type'),
                metadata.get('exchange'),
                metadata.get('listing_date') or datetime.now().date(),
                datetime.now()
            ))
            conn.commit()

    def _update_existing_ticker(self, change: TickerChange):
        """Update existing ticker metadata"""
        query = """
            UPDATE tickers
            SET name = %s, exchange = %s, asset_type = %s, last_updated = %s
            WHERE ticker = %s AND region = %s
        """

        metadata = change.metadata

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                metadata.get('name'),
                metadata.get('exchange'),
                metadata.get('asset_type'),
                datetime.now(),
                change.ticker,
                change.region
            ))
            conn.commit()

    def _mark_delisted_ticker(self, change: TickerChange):
        """Mark ticker as delisted"""
        query = """
            UPDATE tickers
            SET status = 'delisted', delisting_date = %s, last_updated = %s
            WHERE ticker = %s AND region = %s
        """

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                datetime.now().date(),
                datetime.now(),
                change.ticker,
                change.region
            ))
            conn.commit()

    def _load_kis_credentials(self):
        """Load KIS credentials from environment variables"""
        import os
        from dotenv import load_dotenv

        load_dotenv()

        self.kis_app_key = os.getenv('KIS_APP_KEY')
        self.kis_app_secret = os.getenv('KIS_APP_SECRET')

        if not self.kis_app_key or not self.kis_app_secret:
            self.logger.warning(
                "⚠️  KIS API credentials not found in environment. "
                "KR market adapter will not be available."
            )

    def _get_adapter(self, region: str):
        """Get market adapter for region (lazy loading)"""
        if region not in self._adapters:
            if region == 'KR':
                from modules.market_adapters.kr_adapter import KRMarketAdapter

                if not self.kis_app_key or not self.kis_app_secret:
                    raise ValueError(
                        "KIS API credentials required for KR market adapter. "
                        "Please set KIS_APP_KEY and KIS_APP_SECRET environment variables."
                    )

                self._adapters[region] = KRMarketAdapter(
                    db_manager=self.db,
                    kis_app_key=self.kis_app_key,
                    kis_app_secret=self.kis_app_secret
                )

            elif region == 'US':
                from modules.market_adapters.us_adapter import USMarketAdapter
                self._adapters[region] = USMarketAdapter()
            # Add other regions as needed

        return self._adapters[region]
