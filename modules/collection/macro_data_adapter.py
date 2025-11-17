#!/usr/bin/env python3
"""
Macro Data Collection Adapter

Collects and updates macro economic indicators:
1. Global Market Indices (10 major indices)
2. Bond Yields (US Treasury: 3M, 10Y, 30Y)
3. Commodities (Gold, Silver, Oil, Natural Gas, Copper, Platinum)
4. Market Sentiment (VIX-based calculation)

Designed for orchestrator integration with daily automated updates.

Created: 2025-11-16
Phase: 2.1 - Macro Data & Automation
"""

import sys
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import time

from loguru import logger
import yfinance as yf

from modules.db_manager_postgres import PostgresDatabaseManager


class MacroDataAdapter:
    """
    Unified macro data collection adapter for orchestrator integration

    Features:
    - Global market indices (10 indices)
    - Bond yields (3 maturities)
    - Commodities (6 assets)
    - Market sentiment calculation
    - Batch processing with error handling
    - Progress tracking and statistics
    """

    # ========================================================================
    # Configuration: Market Indices
    # ========================================================================

    MARKET_INDICES = {
        '^KS11': {'name': 'KOSPI Index', 'region': 'KR'},
        '^KQ11': {'name': 'KOSDAQ Index', 'region': 'KR'},
        '^GSPC': {'name': 'S&P 500', 'region': 'US'},
        '^IXIC': {'name': 'NASDAQ Composite', 'region': 'US'},
        '^DJI': {'name': 'Dow Jones Industrial Average', 'region': 'US'},
        '^N225': {'name': 'Nikkei 225', 'region': 'JP'},
        '^HSI': {'name': 'Hang Seng Index', 'region': 'HK'},
        '000001.SS': {'name': 'Shanghai Composite', 'region': 'CN'},
        '^STOXX': {'name': 'STOXX Europe 600', 'region': 'EU'},
        '^FTSE': {'name': 'FTSE 100', 'region': 'UK'}
    }

    # ========================================================================
    # Configuration: Bonds
    # ========================================================================

    BOND_SYMBOLS = {
        'US3M': {'ticker': '^IRX', 'country': 'US', 'maturity': '3M', 'name': 'US 3-Month Treasury'},
        'US10Y': {'ticker': '^TNX', 'country': 'US', 'maturity': '10Y', 'name': 'US 10-Year Treasury'},
        'US30Y': {'ticker': '^TYX', 'country': 'US', 'maturity': '30Y', 'name': 'US 30-Year Treasury'}
    }

    # ========================================================================
    # Configuration: Commodities
    # ========================================================================

    COMMODITY_SYMBOLS = {
        'GC=F': {'name': 'Gold Futures', 'category': 'Metals'},
        'SI=F': {'name': 'Silver Futures', 'category': 'Metals'},
        'CL=F': {'name': 'Crude Oil WTI Futures', 'category': 'Energy'},
        'NG=F': {'name': 'Natural Gas Futures', 'category': 'Energy'},
        'HG=F': {'name': 'Copper Futures', 'category': 'Metals'},
        'PL=F': {'name': 'Platinum Futures', 'category': 'Metals'}
    }

    # ========================================================================
    # Configuration: Market Sentiment Symbols
    # ========================================================================

    SENTIMENT_SYMBOLS = {
        '^VIX': 'CBOE Volatility Index'
    }

    def __init__(self, db: PostgresDatabaseManager, config: Dict = None):
        """
        Initialize macro data adapter

        Args:
            db: PostgreSQL database manager
            config: Optional configuration (dry_run, batch_size, etc.)
        """
        self.db = db
        self.config = config or {}
        self.dry_run = self.config.get('dry_run', False)

        # Statistics
        self.stats = {
            'indices_processed': 0,
            'indices_success': 0,
            'indices_failed': 0,
            'indices_records': 0,
            'bonds_processed': 0,
            'bonds_success': 0,
            'bonds_failed': 0,
            'bonds_records': 0,
            'commodities_processed': 0,
            'commodities_success': 0,
            'commodities_failed': 0,
            'commodities_records': 0,
            'sentiment_processed': 0,
            'sentiment_success': 0,
            'sentiment_failed': 0,
            'sentiment_records': 0,
            'total_records': 0,
            'duration': 0,
            'success': False
        }

        logger.info("✅ MacroDataAdapter initialized")
        logger.info(f"   Database: PostgreSQL ({self.db.database})")
        logger.info(f"   Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")

    # ========================================================================
    # Global Market Indices
    # ========================================================================

    def update_market_indices(self, days: int = 30) -> Dict:
        """
        Update global market indices

        Args:
            days: Number of days to fetch (default: 30 for incremental)

        Returns:
            Statistics dictionary
        """
        logger.info("=" * 80)
        logger.info("Global Market Indices Update")
        logger.info("=" * 80)
        logger.info(f"Indices: {len(self.MARKET_INDICES)}")
        logger.info(f"Days: {days}")
        logger.info("=" * 80)

        start_time = time.time()
        start_date = date.today() - timedelta(days=days)
        end_date = date.today()

        for symbol, info in self.MARKET_INDICES.items():
            self.stats['indices_processed'] += 1

            try:
                # Fetch data from yfinance
                ticker = yf.Ticker(symbol)
                hist = ticker.history(
                    start=start_date.strftime('%Y-%m-%d'),
                    end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d')
                )

                if hist.empty:
                    logger.warning(f"⚠️ {symbol}: No data available")
                    self.stats['indices_failed'] += 1
                    continue

                # Insert records
                records_inserted = 0
                for idx, row in hist.iterrows():
                    record_date = idx.date()

                    # Skip if dry run
                    if self.dry_run:
                        records_inserted += 1
                        continue

                    # Upsert to database
                    query = """
                        INSERT INTO global_market_indices
                        (date, symbol, index_name, region, open_price, high_price, low_price, close_price, volume)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (date, symbol) DO UPDATE SET
                            open_price = EXCLUDED.open_price,
                            high_price = EXCLUDED.high_price,
                            low_price = EXCLUDED.low_price,
                            close_price = EXCLUDED.close_price,
                            volume = EXCLUDED.volume
                    """

                    with self.db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(query, (
                            record_date,
                            symbol,
                            info['name'],
                            info['region'],
                            Decimal(str(row['Open'])) if row['Open'] else None,
                            Decimal(str(row['High'])) if row['High'] else None,
                            Decimal(str(row['Low'])) if row['Low'] else None,
                            Decimal(str(row['Close'])) if row['Close'] else None,
                            int(row['Volume']) if row['Volume'] else None
                        ))
                        conn.commit()

                    records_inserted += 1

                self.stats['indices_success'] += 1
                self.stats['indices_records'] += records_inserted
                logger.info(f"✅ {symbol} ({info['name']}): {records_inserted} records")

            except Exception as e:
                self.stats['indices_failed'] += 1
                logger.error(f"❌ {symbol}: {e}")

        duration = time.time() - start_time
        logger.info(f"✅ Market indices update completed in {duration:.2f}s")
        logger.info(f"   Success: {self.stats['indices_success']}/{self.stats['indices_processed']}")
        logger.info(f"   Records: {self.stats['indices_records']}")

        return self.stats

    # ========================================================================
    # Bond Yields
    # ========================================================================

    def update_bond_yields(self, days: int = 30) -> Dict:
        """
        Update bond yields

        Args:
            days: Number of days to fetch

        Returns:
            Statistics dictionary
        """
        logger.info("=" * 80)
        logger.info("Bond Yields Update")
        logger.info("=" * 80)
        logger.info(f"Bonds: {len(self.BOND_SYMBOLS)}")
        logger.info(f"Days: {days}")
        logger.info("=" * 80)

        start_date = date.today() - timedelta(days=days)
        end_date = date.today()

        for symbol_key, bond_info in self.BOND_SYMBOLS.items():
            self.stats['bonds_processed'] += 1

            try:
                ticker = yf.Ticker(bond_info['ticker'])
                hist = ticker.history(
                    start=start_date.strftime('%Y-%m-%d'),
                    end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d')
                )

                if hist.empty:
                    logger.warning(f"⚠️ {symbol_key}: No data available")
                    self.stats['bonds_failed'] += 1
                    continue

                records_inserted = 0
                for idx, row in hist.iterrows():
                    record_date = idx.date()
                    yield_value = float(row['Close'])

                    if self.dry_run:
                        records_inserted += 1
                        continue

                    # Upsert to database (table structure from schema)
                    # PRIMARY KEY: (symbol, date)
                    query = """
                        INSERT INTO bond_yields
                        (symbol, date, country, maturity, yield)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (symbol, date) DO UPDATE SET
                            country = EXCLUDED.country,
                            maturity = EXCLUDED.maturity,
                            yield = EXCLUDED.yield
                    """

                    with self.db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(query, (
                            symbol_key,
                            record_date,
                            bond_info['country'],
                            bond_info['maturity'],
                            yield_value
                        ))
                        conn.commit()

                    records_inserted += 1

                self.stats['bonds_success'] += 1
                self.stats['bonds_records'] += records_inserted
                logger.info(f"✅ {symbol_key} ({bond_info['name']}): {records_inserted} records")

            except Exception as e:
                self.stats['bonds_failed'] += 1
                logger.error(f"❌ {symbol_key}: {e}")

        logger.info(f"✅ Bond yields update completed")
        logger.info(f"   Success: {self.stats['bonds_success']}/{self.stats['bonds_processed']}")
        logger.info(f"   Records: {self.stats['bonds_records']}")

        return self.stats

    # ========================================================================
    # Commodities
    # ========================================================================

    def update_commodities(self, days: int = 30) -> Dict:
        """
        Update commodities data (Gold, Silver, Oil, Gas, Copper, Platinum)

        Args:
            days: Number of days to fetch

        Returns:
            Statistics dictionary
        """
        logger.info("=" * 80)
        logger.info("Commodities Update")
        logger.info("=" * 80)
        logger.info(f"Commodities: {len(self.COMMODITY_SYMBOLS)}")
        logger.info(f"Days: {days}")
        logger.info("=" * 80)

        start_date = date.today() - timedelta(days=days)
        end_date = date.today()

        for symbol, commodity_info in self.COMMODITY_SYMBOLS.items():
            self.stats['commodities_processed'] += 1

            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(
                    start=start_date.strftime('%Y-%m-%d'),
                    end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d')
                )

                if hist.empty:
                    logger.warning(f"⚠️ {symbol}: No data available")
                    self.stats['commodities_failed'] += 1
                    continue

                records_inserted = 0
                for idx, row in hist.iterrows():
                    record_date = idx.date()

                    if self.dry_run:
                        records_inserted += 1
                        continue

                    # Calculate change percentage
                    change_pct = None
                    if row['Close'] and row['Open']:
                        change_pct = ((float(row['Close']) - float(row['Open'])) / float(row['Open'])) * 100

                    # Upsert to database
                    # PRIMARY KEY: (symbol, date)
                    query = """
                        INSERT INTO commodities
                        (symbol, name, category, date, close, open, high, low, volume, change_pct)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (symbol, date) DO UPDATE SET
                            name = EXCLUDED.name,
                            category = EXCLUDED.category,
                            close = EXCLUDED.close,
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            volume = EXCLUDED.volume,
                            change_pct = EXCLUDED.change_pct
                    """

                    with self.db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(query, (
                            symbol,
                            commodity_info['name'],
                            commodity_info['category'],
                            record_date,
                            Decimal(str(row['Close'])) if row['Close'] else None,
                            Decimal(str(row['Open'])) if row['Open'] else None,
                            Decimal(str(row['High'])) if row['High'] else None,
                            Decimal(str(row['Low'])) if row['Low'] else None,
                            int(row['Volume']) if row['Volume'] else None,
                            Decimal(str(change_pct)) if change_pct else None
                        ))
                        conn.commit()

                    records_inserted += 1

                self.stats['commodities_success'] += 1
                self.stats['commodities_records'] += records_inserted
                logger.info(f"✅ {symbol} ({commodity_info['name']}): {records_inserted} records")

            except Exception as e:
                self.stats['commodities_failed'] += 1
                logger.error(f"❌ {symbol}: {e}")

        logger.info(f"✅ Commodities update completed")
        logger.info(f"   Success: {self.stats['commodities_success']}/{self.stats['commodities_processed']}")
        logger.info(f"   Records: {self.stats['commodities_records']}")

        return self.stats

    # ========================================================================
    # Market Sentiment (VIX)
    # ========================================================================

    def update_market_sentiment(self, days: int = 30) -> Dict:
        """
        Update market sentiment based on VIX (CBOE Volatility Index)

        Args:
            days: Number of days to fetch

        Returns:
            Statistics dictionary
        """
        logger.info("=" * 80)
        logger.info("Market Sentiment Update (VIX)")
        logger.info("=" * 80)
        logger.info(f"Days: {days}")
        logger.info("=" * 80)

        start_date = date.today() - timedelta(days=days)
        end_date = date.today()

        for symbol, name in self.SENTIMENT_SYMBOLS.items():
            self.stats['sentiment_processed'] += 1

            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(
                    start=start_date.strftime('%Y-%m-%d'),
                    end=(end_date + timedelta(days=1)).strftime('%Y-%m-%d')
                )

                if hist.empty:
                    logger.warning(f"⚠️ {symbol}: No data available")
                    self.stats['sentiment_failed'] += 1
                    continue

                records_inserted = 0
                for idx, row in hist.iterrows():
                    record_date = idx.date()
                    vix_value = float(row['Close'])

                    if self.dry_run:
                        records_inserted += 1
                        continue

                    # Upsert to database
                    # UNIQUE KEY: date
                    query = """
                        INSERT INTO market_sentiment
                        (date, vix)
                        VALUES (%s, %s)
                        ON CONFLICT (date) DO UPDATE SET
                            vix = EXCLUDED.vix
                    """

                    with self.db._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(query, (
                            record_date,
                            Decimal(str(vix_value))
                        ))
                        conn.commit()

                    records_inserted += 1

                self.stats['sentiment_success'] += 1
                self.stats['sentiment_records'] += records_inserted
                logger.info(f"✅ {symbol} ({name}): {records_inserted} records")

            except Exception as e:
                self.stats['sentiment_failed'] += 1
                logger.error(f"❌ {symbol}: {e}")

        logger.info(f"✅ Market sentiment update completed")
        logger.info(f"   Success: {self.stats['sentiment_success']}/{self.stats['sentiment_processed']}")
        logger.info(f"   Records: {self.stats['sentiment_records']}")

        return self.stats

    # ========================================================================
    # Main Collection Workflow
    # ========================================================================

    def run_collection(
        self,
        components: List[str] = None,
        days: int = 30
    ) -> Dict:
        """
        Run macro data collection workflow

        Args:
            components: List of components to update
                       ['indices', 'bonds', 'commodities', 'sentiment']
                       If None, updates all components
            days: Number of days to fetch (incremental update)

        Returns:
            Statistics dictionary
        """
        if components is None:
            components = ['indices', 'bonds']

        logger.info("=" * 80)
        logger.info("Macro Data Collection")
        logger.info("=" * 80)
        logger.info(f"Components: {', '.join(components)}")
        logger.info(f"Days: {days}")
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        logger.info("=" * 80)

        start_time = time.time()

        try:
            # Update components
            if 'indices' in components:
                self.update_market_indices(days=days)

            if 'bonds' in components:
                self.update_bond_yields(days=days)

            if 'commodities' in components:
                self.update_commodities(days=days)

            if 'sentiment' in components:
                self.update_market_sentiment(days=days)

            # Calculate totals
            self.stats['total_records'] = (
                self.stats['indices_records'] +
                self.stats['bonds_records'] +
                self.stats['commodities_records'] +
                self.stats['sentiment_records']
            )

            self.stats['duration'] = time.time() - start_time
            self.stats['success'] = True

            # Summary
            logger.info("=" * 80)
            logger.info("Macro Data Collection Summary")
            logger.info("=" * 80)
            logger.info(f"Duration: {self.stats['duration']:.2f}s")
            logger.info(f"Total records: {self.stats['total_records']}")
            logger.info(f"Market indices: {self.stats['indices_records']}")
            logger.info(f"Bond yields: {self.stats['bonds_records']}")
            logger.info(f"Commodities: {self.stats['commodities_records']}")
            logger.info(f"Market sentiment: {self.stats['sentiment_records']}")
            logger.info("=" * 80)

            return self.stats

        except Exception as e:
            self.stats['success'] = False
            self.stats['duration'] = time.time() - start_time
            logger.error(f"❌ Macro data collection failed: {e}")
            raise


def main():
    """Test/CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Macro Data Collection')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    parser.add_argument('--days', type=int, default=30, help='Days to fetch (default: 30)')
    parser.add_argument(
        '--components',
        nargs='+',
        choices=['indices', 'bonds', 'commodities', 'sentiment'],
        help='Components to update'
    )

    args = parser.parse_args()

    # Initialize
    db = PostgresDatabaseManager()
    adapter = MacroDataAdapter(db, config={'dry_run': args.dry_run})

    # Run collection
    stats = adapter.run_collection(
        components=args.components,
        days=args.days
    )

    # Exit
    sys.exit(0 if stats['success'] else 1)


if __name__ == '__main__':
    main()
