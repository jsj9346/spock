"""
SQLite Database Manager for Spock Trading System

Lightweight CRUD wrapper around init_db.py schema.
Provides methods needed by market adapters for ticker discovery and data collection.

Author: Spock Trading System
"""

import os
import sqlite3
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class SQLiteDatabaseManager:
    """SQLite database operations manager"""

    def __init__(self, db_path: str = 'data/spock_local.db'):
        """
        Initialize database manager

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

        # Ensure database exists
        if not os.path.exists(db_path):
            raise FileNotFoundError(
                f"Database not found: {db_path}\n"
                f"Please run: python init_db.py"
            )

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        return conn

    # ========================================
    # TICKER CACHE OPERATIONS
    # ========================================

    def get_last_update_time(self, region: str, asset_type: str) -> Optional[datetime]:
        """
        Get last update timestamp for region + asset_type combination

        Args:
            region: Region code (KR, US, CN, HK, JP, VN)
            asset_type: STOCK or ETF

        Returns:
            datetime object or None if no records found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT MAX(last_updated) as last_update
            FROM tickers
            WHERE region = ? AND asset_type = ?
        """, (region, asset_type))

        result = cursor.fetchone()
        conn.close()

        if result and result['last_update']:
            return datetime.fromisoformat(result['last_update'])
        return None

    def get_tickers(self,
                   region: str,
                   asset_type: str,
                   is_active: bool = True) -> List[Dict]:
        """
        Get tickers filtered by region and asset type

        Args:
            region: Region code (KR, US, etc.)
            asset_type: STOCK or ETF
            is_active: Only active tickers (default: True)

        Returns:
            List of ticker dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = """
            SELECT *
            FROM tickers
            WHERE region = ? AND asset_type = ?
        """
        params = [region, asset_type]

        if is_active:
            query += " AND is_active = 1"

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        # Convert Row objects to dictionaries
        return [dict(row) for row in results]

    def get_stock_tickers(self, region: str) -> List[str]:
        """Get list of stock ticker codes for region"""
        tickers = self.get_tickers(region=region, asset_type='STOCK', is_active=True)
        return [t['ticker'] for t in tickers]

    def get_etf_tickers(self, region: str) -> List[str]:
        """Get list of ETF ticker codes for region"""
        tickers = self.get_tickers(region=region, asset_type='ETF', is_active=True)
        return [t['ticker'] for t in tickers]

    def delete_tickers(self, region: str, asset_type: str) -> int:
        """
        Delete tickers by region and asset_type

        Args:
            region: Region code
            asset_type: STOCK or ETF

        Returns:
            Number of tickers deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM tickers
            WHERE region = ? AND asset_type = ?
        """, (region, asset_type))

        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"🗑️  Deleted {deleted_count} tickers ({region}/{asset_type})")
        return deleted_count

    # ========================================
    # TICKER INSERT OPERATIONS
    # ========================================

    def insert_ticker(self, ticker_data: Dict) -> bool:
        """
        Insert or replace ticker into tickers table

        Args:
            ticker_data: Dictionary with ticker information

        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO tickers (
                    ticker, name, name_eng,
                    exchange, region, currency,
                    asset_type, listing_date,
                    lot_size,
                    is_active, delisting_date,
                    created_at, last_updated, data_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker_data['ticker'],
                ticker_data['name'],
                ticker_data.get('name_eng'),
                ticker_data['exchange'],
                ticker_data['region'],
                ticker_data['currency'],
                ticker_data['asset_type'],
                ticker_data.get('listing_date'),
                ticker_data.get('lot_size', 1),
                ticker_data.get('is_active', True),
                ticker_data.get('delisting_date'),
                ticker_data['created_at'],
                ticker_data['last_updated'],
                ticker_data.get('data_source', 'Unknown'),
            ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ Insert ticker failed: {ticker_data.get('ticker')} - {e}")
            conn.close()
            return False

    def insert_stock_details(self, stock_data: Dict) -> bool:
        """
        Insert or replace stock-specific details

        Args:
            stock_data: Dictionary with stock details
                - ticker (required): Stock ticker code
                - region (optional): Region code (KR, US, CN, HK, JP, VN)
                - sector, sector_code, industry, industry_code (optional)
                - is_spac, is_preferred, par_value (optional)
                - created_at, last_updated (required)

        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO stock_details (
                    ticker, region, sector, sector_code, industry, industry_code,
                    is_spac, is_preferred, par_value,
                    created_at, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                stock_data['ticker'],
                stock_data.get('region'),  # ✅ Added region support
                stock_data.get('sector'),
                stock_data.get('sector_code'),
                stock_data.get('industry'),
                stock_data.get('industry_code'),
                stock_data.get('is_spac', False),
                stock_data.get('is_preferred', False),
                stock_data.get('par_value'),
                stock_data['created_at'],
                stock_data['last_updated'],
            ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ Insert stock_details failed: {stock_data.get('ticker')} - {e}")
            conn.close()
            return False

    def update_stock_details(self, ticker: str, updates: Dict) -> bool:
        """
        Update specific fields in stock_details table

        Args:
            ticker: Stock ticker code
            updates: Dictionary with fields to update
                    {'sector': 'IT', 'industry': '반도체', 'par_value': 100}

        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Build UPDATE query dynamically based on provided fields
            set_clauses = []
            params = []

            for field, value in updates.items():
                if field in ['sector', 'sector_code', 'industry', 'industry_code',
                           'is_spac', 'is_preferred', 'par_value']:
                    set_clauses.append(f"{field} = ?")
                    params.append(value)

            if not set_clauses:
                logger.warning(f"⚠️ [{ticker}] No valid fields to update")
                conn.close()
                return False

            # Add last_updated timestamp
            set_clauses.append("last_updated = ?")
            params.append(datetime.now().isoformat())

            # Add ticker to params
            params.append(ticker)

            query = f"""
                UPDATE stock_details
                SET {', '.join(set_clauses)}
                WHERE ticker = ?
            """

            cursor.execute(query, params)

            if cursor.rowcount == 0:
                logger.warning(f"⚠️ [{ticker}] No rows updated (ticker not found)")
                conn.close()
                return False

            conn.commit()
            conn.close()

            logger.info(f"✅ [{ticker}] stock_details updated: {', '.join(updates.keys())}")
            return True

        except Exception as e:
            logger.error(f"❌ Update stock_details failed: {ticker} - {e}")
            conn.close()
            return False

    def bulk_update_stock_details(self, updates: List[Dict[str, Any]]) -> int:
        """
        Bulk update stock_details table for metadata enrichment.

        Args:
            updates: List of update dictionaries
                [
                    {
                        'ticker': 'AAPL',
                        'region': 'US',
                        'sector': 'Information Technology',
                        'industry': 'Consumer Electronics',
                        'industry_code': 'GICS45203010',
                        'is_spac': False,
                        'is_preferred': False,
                        'enriched_at': datetime.now()
                    },
                    ...
                ]

        Returns:
            Number of successfully updated records

        Usage:
            from modules.stock_metadata_enricher import StockMetadataEnricher

            enricher = StockMetadataEnricher(db_manager, kis_api)
            results = enricher.enrich_region(region='US')

            # Extract updates from enrichment results
            updates = [
                {
                    'ticker': r.ticker,
                    'region': r.region,
                    'sector': r.sector,
                    'industry': r.industry,
                    'industry_code': r.industry_code,
                    'is_spac': r.is_spac,
                    'is_preferred': r.is_preferred,
                    'enriched_at': r.enriched_at
                }
                for r in results if r.success
            ]

            # Bulk update database
            updated_count = db_manager.bulk_update_stock_details(updates)
        """
        if not updates:
            return 0

        conn = self._get_connection()
        cursor = conn.cursor()

        updated_count = 0

        try:
            for update in updates:
                # Extract fields
                ticker = update.get('ticker')
                region = update.get('region')

                if not ticker:
                    logger.warning("⚠️  Skipping update: ticker missing")
                    continue

                # Build SET clauses dynamically
                set_clauses = []
                params = []

                # Metadata fields
                valid_fields = ['sector', 'sector_code', 'industry', 'industry_code',
                              'is_spac', 'is_preferred', 'par_value']

                for field in valid_fields:
                    if field in update:
                        set_clauses.append(f"{field} = ?")
                        params.append(update[field])

                # Add enriched_at timestamp if provided
                if 'enriched_at' in update:
                    set_clauses.append("enriched_at = ?")
                    params.append(update['enriched_at'].isoformat() if hasattr(update['enriched_at'], 'isoformat') else update['enriched_at'])

                if not set_clauses:
                    logger.debug(f"⚠️  [{ticker}] No valid fields to update")
                    continue

                # Add last_updated timestamp
                set_clauses.append("last_updated = ?")
                params.append(datetime.now().isoformat())

                # WHERE clause parameters
                where_params = [ticker]
                where_clause = "ticker = ?"

                # Add region to WHERE clause if provided
                if region:
                    where_clause += " AND region = ?"
                    where_params.append(region)

                params.extend(where_params)

                # Execute UPDATE
                query = f"""
                    UPDATE stock_details
                    SET {', '.join(set_clauses)}
                    WHERE {where_clause}
                """

                cursor.execute(query, params)

                if cursor.rowcount > 0:
                    updated_count += 1

            # Commit transaction
            conn.commit()
            conn.close()

            if updated_count > 0:
                logger.info(f"💾 Bulk updated {updated_count}/{len(updates)} stock_details records")

            return updated_count

        except Exception as e:
            logger.error(f"❌ Bulk update stock_details failed: {e}")
            conn.rollback()
            conn.close()
            return updated_count

    def insert_etf_details(self, etf_data: Dict) -> bool:
        """
        Insert or replace ETF-specific details

        Args:
            etf_data: Dictionary with ETF details

        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO etf_details (
                    ticker, issuer, inception_date, underlying_asset_class,
                    tracking_index, geographic_region, sector_theme, fund_type,
                    aum, listed_shares, underlying_asset_count,
                    expense_ratio, ter, actual_expense_ratio,
                    leverage_ratio, currency_hedged,
                    tracking_error_20d, tracking_error_60d, tracking_error_120d, tracking_error_250d,
                    pension_eligible, investment_strategy,
                    created_at, last_updated, data_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                etf_data['ticker'],
                etf_data.get('issuer'),
                etf_data.get('inception_date'),
                etf_data.get('underlying_asset_class'),
                etf_data.get('tracking_index') or 'Unknown',
                etf_data.get('geographic_region'),
                etf_data.get('sector_theme'),
                etf_data.get('fund_type'),
                etf_data.get('aum'),
                etf_data.get('listed_shares'),
                etf_data.get('underlying_asset_count'),
                etf_data.get('expense_ratio') or 0.0,
                etf_data.get('ter'),
                etf_data.get('actual_expense_ratio'),
                etf_data.get('leverage_ratio'),
                etf_data.get('currency_hedged'),
                etf_data.get('tracking_error_20d'),
                etf_data.get('tracking_error_60d'),
                etf_data.get('tracking_error_120d'),
                etf_data.get('tracking_error_250d'),
                etf_data.get('pension_eligible'),
                etf_data.get('investment_strategy'),
                etf_data['created_at'],
                etf_data['last_updated'],
                etf_data.get('data_source', 'Unknown'),
            ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ Insert etf_details failed: {etf_data.get('ticker')} - {e}")
            conn.close()
            return False

    def update_etf_details(self, ticker: str, updates: Dict) -> bool:
        """
        Update specific fields in etf_details table

        Args:
            ticker: ETF ticker code
            updates: Dictionary with fields to update
                    {'expense_ratio': 0.15, 'tracking_index': 'KOSPI 200', 'issuer': '삼성자산운용(주)'}

        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Build UPDATE query dynamically based on provided fields
            set_clauses = []
            params = []

            valid_fields = [
                'issuer', 'inception_date', 'underlying_asset_class', 'tracking_index',
                'geographic_region', 'sector_theme', 'fund_type', 'aum', 'listed_shares',
                'underlying_asset_count', 'expense_ratio', 'ter', 'actual_expense_ratio',
                'leverage_ratio', 'currency_hedged', 'tracking_error_20d', 'tracking_error_60d',
                'tracking_error_120d', 'tracking_error_250d',
                'week_52_high', 'week_52_low',
                'pension_eligible', 'investment_strategy'
            ]

            for field, value in updates.items():
                if field in valid_fields:
                    set_clauses.append(f"{field} = ?")
                    params.append(value)

            if not set_clauses:
                logger.warning(f"⚠️ [{ticker}] No valid fields to update")
                conn.close()
                return False

            # Add last_updated timestamp
            set_clauses.append("last_updated = ?")
            params.append(datetime.now().isoformat())

            # Add ticker to params
            params.append(ticker)

            query = f"""
                UPDATE etf_details
                SET {', '.join(set_clauses)}
                WHERE ticker = ?
            """

            cursor.execute(query, params)

            if cursor.rowcount == 0:
                logger.warning(f"⚠️ [{ticker}] No rows updated (ticker not found)")
                conn.close()
                return False

            conn.commit()
            conn.close()

            logger.debug(f"✅ [{ticker}] etf_details updated: {', '.join(updates.keys())}")
            return True

        except Exception as e:
            logger.error(f"❌ Update etf_details failed: {ticker} - {e}")
            conn.close()
            return False

    def insert_ticker_fundamentals(self, fundamental_data: Dict) -> bool:
        """
        Insert ticker fundamental data (time-series)

        Args:
            fundamental_data: Dictionary with fundamental metrics
                Required: ticker, date, period_type, created_at

                Market Data:
                - shares_outstanding, market_cap, close_price
                - per, pbr, psr, pcr, ev, ev_ebitda
                - dividend_yield, dividend_per_share

                Financial Statements:
                - total_assets, total_liabilities, total_equity
                - revenue, operating_profit, net_income, ebitda

                Quality Factors (Phase 2 - NEW):
                - cogs, gross_profit, depreciation, interest_expense
                - current_assets, current_liabilities, inventory, accounts_receivable
                - cash_and_equivalents, operating_cash_flow, capital_expenditure

                Metadata:
                - fiscal_year, data_source

        Returns:
            True if successful

        Examples:
            # Current year data
            fundamental_data = {
                'ticker': '005930',
                'date': '2025-10-17',
                'period_type': 'ANNUAL',
                'fiscal_year': 2025,
                'per': 12.5,
                'pbr': 1.8,
                'created_at': '2025-10-17T10:00:00',
                'data_source': 'DART-2025-11011'
            }

            # Historical data for backtesting
            fundamental_data = {
                'ticker': '005930',
                'date': '2022-04-01',
                'period_type': 'ANNUAL',
                'fiscal_year': 2021,
                'per': 10.2,
                'pbr': 1.5,
                'created_at': '2025-10-17T10:00:00',
                'data_source': 'DART-2021-11011'
            }
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO ticker_fundamentals (
                    ticker, date, period_type, fiscal_year,
                    shares_outstanding, market_cap, close_price,
                    per, pbr, psr, pcr, ev, ev_ebitda,
                    dividend_yield, dividend_per_share,
                    total_assets, total_liabilities, total_equity,
                    revenue, operating_profit, net_income, ebitda,
                    cogs, gross_profit, depreciation, interest_expense,
                    current_assets, current_liabilities, inventory, accounts_receivable, cash_and_equivalents,
                    operating_cash_flow, capital_expenditure, free_float_percentage,
                    created_at, data_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fundamental_data['ticker'],
                fundamental_data['date'],
                fundamental_data.get('period_type', 'DAILY'),
                fundamental_data.get('fiscal_year'),
                fundamental_data.get('shares_outstanding'),
                fundamental_data.get('market_cap'),
                fundamental_data.get('close_price'),
                fundamental_data.get('per'),
                fundamental_data.get('pbr'),
                fundamental_data.get('psr'),
                fundamental_data.get('pcr'),
                fundamental_data.get('ev'),
                fundamental_data.get('ev_ebitda'),
                fundamental_data.get('dividend_yield'),
                fundamental_data.get('dividend_per_share'),
                fundamental_data.get('total_assets'),
                fundamental_data.get('total_liabilities'),
                fundamental_data.get('total_equity'),
                fundamental_data.get('revenue'),
                fundamental_data.get('operating_profit'),
                fundamental_data.get('net_income'),
                fundamental_data.get('ebitda'),
                fundamental_data.get('cogs'),
                fundamental_data.get('gross_profit'),
                fundamental_data.get('depreciation'),
                fundamental_data.get('interest_expense'),
                fundamental_data.get('current_assets'),
                fundamental_data.get('current_liabilities'),
                fundamental_data.get('inventory'),
                fundamental_data.get('accounts_receivable'),
                fundamental_data.get('cash_and_equivalents'),
                fundamental_data.get('operating_cash_flow'),
                fundamental_data.get('capital_expenditure'),
                fundamental_data.get('free_float_percentage'),
                fundamental_data['created_at'],
                fundamental_data.get('data_source', 'Unknown'),
            ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ Insert ticker_fundamentals failed: {fundamental_data.get('ticker')} - {e}")
            conn.close()
            return False

    def get_ticker_fundamentals(self,
                                ticker: str,
                                region: Optional[str] = None,
                                period_type: Optional[str] = None,
                                fiscal_year: Optional[int] = None,
                                limit: int = 10) -> List[Dict]:
        """
        Retrieve fundamental data for a ticker

        Args:
            ticker: Ticker symbol
            region: Market region filter (optional)
            period_type: Period type filter (DAILY, QUARTERLY, ANNUAL)
            fiscal_year: Fiscal year filter (e.g., 2022, 2023) for backtesting
            limit: Number of records to return (default: 10)

        Returns:
            List of fundamental data dictionaries (newest first)

        Examples:
            # Get latest fundamental data
            fundamentals = db.get_ticker_fundamentals('005930', region='KR', limit=1)

            # Get 2022 annual data for backtesting
            fundamentals = db.get_ticker_fundamentals(
                ticker='005930',
                period_type='ANNUAL',
                fiscal_year=2022,
                limit=1
            )
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Build query with optional filters
            query = """
                SELECT
                    ticker, date, period_type, fiscal_year,
                    shares_outstanding, market_cap, close_price,
                    per, pbr, psr, pcr, ev, ev_ebitda,
                    dividend_yield, dividend_per_share,
                    created_at, data_source
                FROM ticker_fundamentals
                WHERE ticker = ?
            """
            params = [ticker]

            if region:
                # Note: ticker_fundamentals table doesn't have region column yet
                # For now, we rely on ticker format to determine region
                # This will be enhanced in Phase 3 if needed
                pass

            if period_type:
                query += " AND period_type = ?"
                params.append(period_type)

            if fiscal_year:
                query += " AND fiscal_year = ?"
                params.append(fiscal_year)

            query += " ORDER BY date DESC, created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            # Convert to list of dictionaries
            fundamentals = []
            for row in rows:
                fundamentals.append({
                    'ticker': row[0],
                    'date': row[1],
                    'period_type': row[2],
                    'fiscal_year': row[3],
                    'shares_outstanding': row[4],
                    'market_cap': row[5],
                    'close_price': row[6],
                    'per': row[7],
                    'pbr': row[8],
                    'psr': row[9],
                    'pcr': row[10],
                    'ev': row[11],
                    'ev_ebitda': row[12],
                    'dividend_yield': row[13],
                    'dividend_per_share': row[14],
                    'created_at': row[15],
                    'data_source': row[16]
                })

            return fundamentals

        except Exception as e:
            logger.error(f"❌ Get ticker_fundamentals failed: {ticker} - {e}")
            conn.close()
            return []

    def get_latest_fundamentals_batch(self,
                                     tickers: List[str],
                                     period_type: str = 'DAILY') -> Dict[str, Dict]:
        """
        Retrieve latest fundamental data for multiple tickers (batch query)

        Args:
            tickers: List of ticker symbols
            period_type: Period type filter (default: DAILY)

        Returns:
            Dict {ticker: fundamental_data}

        Example:
            tickers = ['005930', '035720', '000660']
            fundamentals = db.get_latest_fundamentals_batch(tickers)
            for ticker, data in fundamentals.items():
                print(f"{ticker}: PER={data['per']}, PBR={data['pbr']}")
        """
        if not tickers:
            return {}

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Build query with IN clause
            placeholders = ','.join('?' * len(tickers))
            query = f"""
                SELECT
                    ticker, date, period_type,
                    shares_outstanding, market_cap, close_price,
                    per, pbr, psr, pcr, ev, ev_ebitda,
                    dividend_yield, dividend_per_share,
                    created_at, data_source
                FROM ticker_fundamentals
                WHERE ticker IN ({placeholders})
                  AND period_type = ?
                ORDER BY ticker, date DESC, created_at DESC
            """
            params = tickers + [period_type]

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            # Group by ticker and keep only latest for each
            fundamentals = {}
            for row in rows:
                ticker = row[0]
                if ticker not in fundamentals:
                    fundamentals[ticker] = {
                        'ticker': row[0],
                        'date': row[1],
                        'period_type': row[2],
                        'shares_outstanding': row[3],
                        'market_cap': row[4],
                        'close_price': row[5],
                        'per': row[6],
                        'pbr': row[7],
                        'psr': row[8],
                        'pcr': row[9],
                        'ev': row[10],
                        'ev_ebitda': row[11],
                        'dividend_yield': row[12],
                        'dividend_per_share': row[13],
                        'created_at': row[14],
                        'data_source': row[15]
                    }

            return fundamentals

        except Exception as e:
            logger.error(f"❌ Get latest_fundamentals_batch failed - {e}")
            conn.close()
            return {}

    # ========================================
    # OHLCV DATA OPERATIONS
    # ========================================

    def insert_ohlcv_bulk(self,
                          ticker: str,
                          ohlcv_df: pd.DataFrame,
                          timeframe: str = 'D',
                          region: str = None) -> int:
        """
        Bulk insert OHLCV data with technical indicators

        Args:
            ticker: Ticker code
            ohlcv_df: DataFrame with OHLCV + technical indicators
            timeframe: D (daily), W (weekly), M (monthly)
            region: Region code (KR, US, CN, HK, JP, VN) - Required for global market support

        Returns:
            Number of rows inserted
        """
        conn = self._get_connection()

        # Ensure required columns exist
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in ohlcv_df.columns for col in required_cols):
            logger.error(f"❌ Missing required OHLCV columns for {ticker}")
            conn.close()
            return 0

        # Prepare DataFrame for insertion
        ohlcv_df = ohlcv_df.copy()
        ohlcv_df['ticker'] = ticker
        ohlcv_df['timeframe'] = timeframe
        ohlcv_df['region'] = region  # Global market support
        ohlcv_df['created_at'] = datetime.now().isoformat()

        # Validate region (warn if None for backward compatibility)
        if region is None:
            logger.warning(f"⚠️ [{ticker}] Region not specified - NULL will be stored")
        elif region not in ['KR', 'US', 'CN', 'HK', 'JP', 'VN']:
            logger.warning(f"⚠️ [{ticker}] Invalid region: {region} (expected: KR, US, CN, HK, JP, VN)")

        # Ensure date column exists
        if 'date' not in ohlcv_df.columns:
            ohlcv_df.reset_index(inplace=True)
            if ohlcv_df.columns[0] != 'date':
                ohlcv_df.rename(columns={ohlcv_df.columns[0]: 'date'}, inplace=True)

        # Convert date to string
        ohlcv_df['date'] = pd.to_datetime(ohlcv_df['date']).dt.strftime('%Y-%m-%d')

        # Select columns that exist in the database
        db_columns = [
            'ticker', 'date', 'timeframe', 'region',
            'open', 'high', 'low', 'close', 'volume',
            'ma5', 'ma20', 'ma60', 'ma120', 'ma200',
            'rsi_14', 'macd', 'macd_signal', 'macd_hist',
            'bb_upper', 'bb_middle', 'bb_lower', 'atr_14',
            'created_at'
        ]

        # Keep only columns that exist in DataFrame
        existing_columns = [col for col in db_columns if col in ohlcv_df.columns]
        insert_df = ohlcv_df[existing_columns]

        # Insert using pandas to_sql (REPLACE mode)
        try:
            insert_df.to_sql('ohlcv_data', conn, if_exists='append', index=False)
            inserted_count = len(insert_df)
            conn.close()

            logger.info(f"💾 [{ticker}] {inserted_count} OHLCV rows inserted ({timeframe})")
            return inserted_count

        except Exception as e:
            logger.error(f"❌ Bulk insert OHLCV failed: {ticker} - {e}")
            conn.close()
            return 0

    def get_ohlcv(self,
                  ticker: str,
                  period_type: str = 'DAILY',
                  limit: Optional[int] = None) -> List[Dict]:
        """
        Get OHLCV data for a ticker

        Args:
            ticker: Ticker code
            period_type: 'DAILY', 'WEEKLY', 'MONTHLY'
            limit: Number of rows to return (None = all)

        Returns:
            List of OHLCV dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Convert period_type to timeframe
        timeframe_map = {'DAILY': 'D', 'WEEKLY': 'W', 'MONTHLY': 'M'}
        timeframe = timeframe_map.get(period_type, 'D')

        query = """
            SELECT ticker, date, timeframe,
                   open, high, low, close, volume,
                   ma5, ma20, ma60, ma120, ma200,
                   rsi_14, macd, macd_signal, macd_hist,
                   bb_upper, bb_middle, bb_lower, atr_14,
                   created_at
            FROM ohlcv_data
            WHERE ticker = ? AND timeframe = ?
            ORDER BY date DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query, (ticker, timeframe))
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    # ========================================
    # ETF-SPECIFIC OPERATIONS
    # ========================================

    def get_etf_field(self, ticker: str, field_name: str):
        """Get specific field from etf_details table"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(f"""
            SELECT {field_name}
            FROM etf_details
            WHERE ticker = ?
        """, (ticker,))

        result = cursor.fetchone()
        conn.close()

        return result[field_name] if result else None

    def update_etf_field(self, ticker: str, field_name: str, value) -> bool:
        """Update specific field in etf_details table"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(f"""
                UPDATE etf_details
                SET {field_name} = ?, last_updated = ?
                WHERE ticker = ?
            """, (value, datetime.now().isoformat(), ticker))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ Update ETF field failed: {ticker}.{field_name} - {e}")
            conn.close()
            return False

    def update_etf_tracking_errors(self, ticker: str, tracking_errors: Dict) -> bool:
        """Update all tracking error fields for ETF"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE etf_details
                SET tracking_error_20d = ?,
                    tracking_error_60d = ?,
                    tracking_error_120d = ?,
                    tracking_error_250d = ?,
                    last_updated = ?
                WHERE ticker = ?
            """, (
                tracking_errors.get('tracking_error_20d'),
                tracking_errors.get('tracking_error_60d'),
                tracking_errors.get('tracking_error_120d'),
                tracking_errors.get('tracking_error_250d'),
                datetime.now().isoformat(),
                ticker,
            ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ Update tracking errors failed: {ticker} - {e}")
            conn.close()
            return False

    # ========================================
    # ETF HOLDINGS OPERATIONS (Phase 1: 2025-10-17)
    # ========================================

    def insert_etf_info(self, etf_data: Dict) -> bool:
        """
        Insert or replace ETF metadata into etfs table (Phase 1)

        Args:
            etf_data: Dictionary with ETF information
                - ticker (required): ETF ticker code
                - name (required): ETF name
                - region (required): Region code (KR, US, CN, HK, JP, VN)
                - category: ETF category (Equity, Bond, Commodity, etc.)
                - tracking_index: Index being tracked
                - total_assets: Total AUM in base currency
                - expense_ratio: Annual expense ratio
                - ... (see etfs table schema for complete fields)

        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO etfs (
                    ticker, name, region, category, tracking_index,
                    issuer, inception_date, total_assets, nav,
                    expense_ratio, dividend_yield, pe_ratio, pb_ratio,
                    ytd_return, week_52_high, week_52_low,
                    avg_volume_3m, shares_outstanding,
                    underlying_asset_class, geographic_focus, sector_focus,
                    investment_strategy, rebalance_frequency,
                    created_at, last_updated, data_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                etf_data['ticker'],
                etf_data['name'],
                etf_data['region'],
                etf_data.get('category'),
                etf_data.get('tracking_index'),
                etf_data.get('issuer'),
                etf_data.get('inception_date'),
                etf_data.get('total_assets'),
                etf_data.get('nav'),
                etf_data.get('expense_ratio'),
                etf_data.get('dividend_yield'),
                etf_data.get('pe_ratio'),
                etf_data.get('pb_ratio'),
                etf_data.get('ytd_return'),
                etf_data.get('week_52_high'),
                etf_data.get('week_52_low'),
                etf_data.get('avg_volume_3m'),
                etf_data.get('shares_outstanding'),
                etf_data.get('underlying_asset_class'),
                etf_data.get('geographic_focus'),
                etf_data.get('sector_focus'),
                etf_data.get('investment_strategy'),
                etf_data.get('rebalance_frequency'),
                etf_data['created_at'],
                etf_data['last_updated'],
                etf_data.get('data_source', 'Unknown'),
            ))

            conn.commit()
            conn.close()
            logger.info(f"✅ [{etf_data['ticker']}] ETF info inserted/updated")
            return True

        except Exception as e:
            logger.error(f"❌ Insert ETF info failed: {etf_data.get('ticker')} - {e}")
            conn.close()
            return False

    def insert_etf_holding(self, holding_data: Dict) -> bool:
        """
        Insert or replace single ETF holding record

        Args:
            holding_data: Dictionary with holding information
                - etf_ticker (required): ETF ticker code
                - stock_ticker (required): Stock ticker code
                - weight (required): Weight percentage (0-100)
                - as_of_date (required): Date of holding data (YYYY-MM-DD)
                - shares: Number of shares held
                - market_value: Market value in base currency
                - rank_in_etf: Rank by weight in ETF
                - sector: Stock sector
                - country: Stock country

        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO etf_holdings (
                    etf_ticker, stock_ticker, weight, shares, market_value,
                    rank_in_etf, sector, country,
                    as_of_date, created_at, data_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                holding_data['etf_ticker'],
                holding_data['stock_ticker'],
                holding_data['weight'],
                holding_data.get('shares'),
                holding_data.get('market_value'),
                holding_data.get('rank_in_etf'),
                holding_data.get('sector'),
                holding_data.get('country'),
                holding_data['as_of_date'],
                holding_data['created_at'],
                holding_data.get('data_source', 'Unknown'),
            ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ Insert holding failed: {holding_data.get('etf_ticker')} - {e}")
            conn.close()
            return False

    def insert_etf_holdings_bulk(self, holdings: List[Dict]) -> int:
        """
        Bulk insert ETF holdings for efficiency

        Args:
            holdings: List of holding dictionaries

        Returns:
            Number of holdings inserted
        """
        if not holdings:
            return 0

        conn = self._get_connection()
        cursor = conn.cursor()

        inserted_count = 0

        try:
            for holding in holdings:
                cursor.execute("""
                    INSERT OR REPLACE INTO etf_holdings (
                        etf_ticker, stock_ticker, weight, shares, market_value,
                        rank_in_etf, sector, country,
                        as_of_date, created_at, data_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    holding['etf_ticker'],
                    holding['stock_ticker'],
                    holding['weight'],
                    holding.get('shares'),
                    holding.get('market_value'),
                    holding.get('rank_in_etf'),
                    holding.get('sector'),
                    holding.get('country'),
                    holding['as_of_date'],
                    holding['created_at'],
                    holding.get('data_source', 'Unknown'),
                ))
                inserted_count += 1

            conn.commit()
            conn.close()

            if inserted_count > 0:
                logger.info(f"💾 Inserted {inserted_count} ETF holdings")

            return inserted_count

        except Exception as e:
            logger.error(f"❌ Bulk insert holdings failed: {e}")
            conn.close()
            return inserted_count

    def get_etfs_by_stock(self, stock_ticker: str, as_of_date: str = None) -> List[Dict]:
        """
        Get all ETFs containing a specific stock (Stock → ETF query)

        Args:
            stock_ticker: Stock ticker code
            as_of_date: Date to query (YYYY-MM-DD). If None, uses latest date.

        Returns:
            List of ETF dictionaries with holding details
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if as_of_date is None:
            # Use latest available date
            cursor.execute("""
                SELECT MAX(as_of_date) as latest_date
                FROM etf_holdings
                WHERE stock_ticker = ?
            """, (stock_ticker,))
            result = cursor.fetchone()
            as_of_date = result['latest_date'] if result else None

        if as_of_date is None:
            conn.close()
            return []

        cursor.execute("""
            SELECT
                h.etf_ticker,
                e.name as etf_name,
                e.region,
                e.category,
                h.weight,
                h.rank_in_etf,
                h.shares,
                h.market_value,
                h.as_of_date
            FROM etf_holdings h
            INNER JOIN etfs e ON h.etf_ticker = e.ticker
            WHERE h.stock_ticker = ?
              AND h.as_of_date = ?
            ORDER BY h.weight DESC
        """, (stock_ticker, as_of_date))

        results = cursor.fetchall()
        conn.close()

        return [dict(row) for row in results]

    def get_stocks_by_etf(self, etf_ticker: str, as_of_date: str = None,
                         min_weight: float = None) -> List[Dict]:
        """
        Get all stocks in a specific ETF (ETF → Stock query)

        Args:
            etf_ticker: ETF ticker code
            as_of_date: Date to query (YYYY-MM-DD). If None, uses latest date.
            min_weight: Minimum weight threshold (e.g., 5.0 for stocks >5%)

        Returns:
            List of stock dictionaries with holding details
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if as_of_date is None:
            # Use latest available date
            cursor.execute("""
                SELECT MAX(as_of_date) as latest_date
                FROM etf_holdings
                WHERE etf_ticker = ?
            """, (etf_ticker,))
            result = cursor.fetchone()
            as_of_date = result['latest_date'] if result else None

        if as_of_date is None:
            conn.close()
            return []

        query = """
            SELECT
                h.stock_ticker,
                t.name as stock_name,
                t.region,
                h.weight,
                h.rank_in_etf,
                h.shares,
                h.market_value,
                h.sector,
                h.country,
                h.as_of_date
            FROM etf_holdings h
            INNER JOIN tickers t ON h.stock_ticker = t.ticker
            WHERE h.etf_ticker = ?
              AND h.as_of_date = ?
        """
        params = [etf_ticker, as_of_date]

        if min_weight is not None:
            query += " AND h.weight >= ?"
            params.append(min_weight)

        query += " ORDER BY h.rank_in_etf ASC"

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return [dict(row) for row in results]

    def get_etf_weight_history(self, etf_ticker: str, stock_ticker: str,
                               days: int = 90) -> List[Dict]:
        """
        Get historical weight changes for a stock in an ETF

        Args:
            etf_ticker: ETF ticker code
            stock_ticker: Stock ticker code
            days: Number of days of history to retrieve

        Returns:
            List of holding records ordered by date DESC
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                as_of_date,
                weight,
                rank_in_etf,
                shares,
                market_value
            FROM etf_holdings
            WHERE etf_ticker = ?
              AND stock_ticker = ?
              AND as_of_date >= date('now', '-' || ? || ' days')
            ORDER BY as_of_date DESC
        """, (etf_ticker, stock_ticker, days))

        results = cursor.fetchall()
        conn.close()

        return [dict(row) for row in results]

    def delete_old_etf_holdings(self, retention_days: int = 365) -> int:
        """
        Delete ETF holdings older than retention period

        Args:
            retention_days: Number of days to retain (default: 365)

        Returns:
            Number of rows deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM etf_holdings
            WHERE as_of_date < date('now', '-' || ? || ' days')
        """, (retention_days,))

        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        if deleted_count > 0:
            logger.info(f"🗑️  Deleted {deleted_count} old ETF holdings (>{retention_days} days)")

        return deleted_count

    # ========================================
    # UTILITY OPERATIONS
    # ========================================

    def get_ticker_count(self, region: str = None, asset_type: str = None) -> int:
        """Get ticker count with optional filters"""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT COUNT(*) as count FROM tickers WHERE 1=1"
        params = []

        if region:
            query += " AND region = ?"
            params.append(region)

        if asset_type:
            query += " AND asset_type = ?"
            params.append(asset_type)

        cursor.execute(query, params)
        result = cursor.fetchone()
        conn.close()

        return result['count'] if result else 0

    def health_check(self) -> Dict:
        """Check database health and return statistics"""
        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {}

        # Check table existence
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN ('tickers', 'stock_details', 'etf_details', 'ohlcv_data')
        """)
        tables = [row['name'] for row in cursor.fetchall()]

        stats['tables_exist'] = len(tables) == 4
        stats['missing_tables'] = [t for t in ['tickers', 'stock_details', 'etf_details', 'ohlcv_data'] if t not in tables]

        # Count records
        if 'tickers' in tables:
            cursor.execute("SELECT COUNT(*) as count FROM tickers")
            stats['ticker_count'] = cursor.fetchone()['count']

        if 'ohlcv_data' in tables:
            cursor.execute("SELECT COUNT(*) as count FROM ohlcv_data")
            stats['ohlcv_count'] = cursor.fetchone()['count']

        conn.close()

        stats['db_path'] = self.db_path
        stats['db_exists'] = os.path.exists(self.db_path)
        stats['db_size_mb'] = os.path.getsize(self.db_path) / (1024 * 1024) if stats['db_exists'] else 0

        return stats

    # ========================================
    # SECTOR BACKFILL OPERATIONS
    # ========================================

    def get_stocks_without_sector(self, limit: int = None) -> List[Dict]:
        """
        Get stocks that don't have sector information

        Args:
            limit: Maximum number of stocks to return

        Returns:
            List of stock dictionaries (ticker, name)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = """
            SELECT t.ticker, t.name
            FROM tickers t
            LEFT JOIN stock_details sd ON t.ticker = sd.ticker
            WHERE t.asset_type = 'STOCK'
              AND t.region = 'KR'
              AND t.is_active = 1
              AND (sd.sector IS NULL OR sd.sector = '')
            ORDER BY t.ticker
        """

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()

        return [dict(row) for row in results]

    def update_stock_sector(self, ticker: str, sector: str, industry: str = None,
                          sector_code: str = None, industry_code: str = None) -> bool:
        """
        Update sector information for a stock

        Args:
            ticker: Stock ticker code
            sector: Sector name
            industry: Industry name (optional)
            sector_code: Sector code (optional)
            industry_code: Industry code (optional)

        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Check if stock_details row exists
            cursor.execute("SELECT COUNT(*) as count FROM stock_details WHERE ticker = ?", (ticker,))
            exists = cursor.fetchone()['count'] > 0

            if exists:
                # Update existing row
                cursor.execute("""
                    UPDATE stock_details
                    SET sector = ?,
                        industry = ?,
                        sector_code = ?,
                        industry_code = ?,
                        last_updated = ?
                    WHERE ticker = ?
                """, (sector, industry, sector_code, industry_code, datetime.now().isoformat(), ticker))
            else:
                # Insert new row
                cursor.execute("""
                    INSERT INTO stock_details (
                        ticker, sector, industry, sector_code, industry_code,
                        created_at, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticker, sector, industry, sector_code, industry_code,
                    datetime.now().isoformat(), datetime.now().isoformat()
                ))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ Update stock sector failed: {ticker} - {e}")
            conn.close()
            return False

    def get_sector_coverage_stats(self) -> Dict:
        """
        Get statistics on sector coverage

        Returns:
            Dictionary with coverage statistics
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total active KR stocks
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM tickers
            WHERE asset_type = 'STOCK' AND region = 'KR' AND is_active = 1
        """)
        total = cursor.fetchone()['count']

        # Stocks with sector info
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM tickers t
            INNER JOIN stock_details sd ON t.ticker = sd.ticker
            WHERE t.asset_type = 'STOCK'
              AND t.region = 'KR'
              AND t.is_active = 1
              AND sd.sector IS NOT NULL
              AND sd.sector != ''
        """)
        with_sector = cursor.fetchone()['count']

        conn.close()

        return {
            'total': total,
            'with_sector': with_sector,
            'without_sector': total - with_sector,
            'coverage_percent': (with_sector / total * 100) if total > 0 else 0
        }

    # ========================================
    # BACKTESTING OPERATIONS (Week 1: 2025-10-17)
    # ========================================

    def create_backtest_tables(self):
        """
        Create backtesting tables if they don't exist.

        Tables created:
          - backtest_results: Backtest configuration and performance metrics
          - backtest_trades: Individual trade records
          - backtest_equity_curve: Daily portfolio values
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # backtest_results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backtest_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_hash TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    regions TEXT NOT NULL,

                    config_json TEXT NOT NULL,

                    total_return REAL,
                    annualized_return REAL,
                    cagr REAL,
                    sharpe_ratio REAL,
                    sortino_ratio REAL,
                    calmar_ratio REAL,
                    max_drawdown REAL,

                    total_trades INTEGER,
                    win_rate REAL,
                    profit_factor REAL,
                    avg_win_loss_ratio REAL,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    execution_time_seconds REAL,

                    UNIQUE(config_hash, start_date, end_date)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_backtest_results_created
                ON backtest_results(created_at)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_backtest_results_sharpe
                ON backtest_results(sharpe_ratio)
            """)

            # backtest_trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backtest_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backtest_id INTEGER NOT NULL,

                    ticker TEXT NOT NULL,
                    region TEXT NOT NULL,
                    entry_date TEXT NOT NULL,
                    exit_date TEXT,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    shares INTEGER NOT NULL,

                    commission REAL NOT NULL,
                    slippage REAL NOT NULL,

                    pnl REAL,
                    pnl_pct REAL,

                    pattern_type TEXT,
                    entry_score INTEGER,
                    exit_reason TEXT,

                    FOREIGN KEY (backtest_id) REFERENCES backtest_results(id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_backtest_trades_backtest
                ON backtest_trades(backtest_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_backtest_trades_ticker
                ON backtest_trades(ticker)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_backtest_trades_pattern
                ON backtest_trades(pattern_type)
            """)

            # backtest_equity_curve table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backtest_equity_curve (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backtest_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    portfolio_value REAL NOT NULL,
                    cash REAL NOT NULL,
                    positions_value REAL NOT NULL,
                    daily_return REAL,

                    FOREIGN KEY (backtest_id) REFERENCES backtest_results(id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_backtest_equity_backtest
                ON backtest_equity_curve(backtest_id)
            """)

            conn.commit()
            conn.close()

            logger.info("✅ Backtest tables created successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Create backtest tables failed: {e}")
            conn.close()
            return False

    # ========================================
    # DATABASE MAINTENANCE OPERATIONS
    # ========================================

    def cleanup_old_ohlcv_data(self, retention_days: int = 250) -> int:
        """
        Delete OHLCV data older than retention period (250-day policy)

        Args:
            retention_days: Number of days to retain (default: 250)
                           - 250 days is sufficient for MA200 calculation
                           - Ensures database size remains manageable

        Returns:
            Number of rows deleted

        Usage:
            # Manual cleanup
            from modules.db_manager_sqlite import SQLiteDatabaseManager
            db = SQLiteDatabaseManager()
            deleted = db.cleanup_old_ohlcv_data(retention_days=250)
            print(f"Deleted {deleted:,} old OHLCV rows")

            # Automated cleanup (weekly_maintenance.sh)
            python3 -c "from modules.db_manager_sqlite import SQLiteDatabaseManager; \\
            db = SQLiteDatabaseManager(); \\
            deleted = db.cleanup_old_ohlcv_data(retention_days=250); \\
            print(f'✅ Deleted {deleted:,} old rows')"
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Calculate cutoff date
            cursor.execute("""
                SELECT date('now', '-' || ? || ' days') as cutoff_date
            """, (retention_days,))
            cutoff_date = cursor.fetchone()['cutoff_date']

            logger.info(f"🗑️  Cleaning OHLCV data older than {cutoff_date} ({retention_days} days)")

            # Delete old records
            cursor.execute("""
                DELETE FROM ohlcv_data
                WHERE date < ?
            """, (cutoff_date,))

            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()

            if deleted_count > 0:
                logger.info(f"✅ Deleted {deleted_count:,} old OHLCV rows (retention: {retention_days} days)")
            else:
                logger.info(f"✅ No old OHLCV data to delete (retention: {retention_days} days)")

            return deleted_count

        except Exception as e:
            logger.error(f"❌ Cleanup old OHLCV data failed: {e}")
            conn.rollback()
            conn.close()
            return 0

    def vacuum_database(self) -> Dict[str, Any]:
        """
        Optimize database by running VACUUM operation

        VACUUM reclaims unused space, optimizes internal structure,
        and improves query performance.

        Returns:
            Dictionary with vacuum results:
                - size_before_mb: Database size before VACUUM (MB)
                - size_after_mb: Database size after VACUUM (MB)
                - space_reclaimed_mb: Space reclaimed (MB)
                - space_reclaimed_pct: Space reclaimed (%)
                - duration_seconds: VACUUM execution time (seconds)

        Usage:
            # Manual VACUUM
            from modules.db_manager_sqlite import SQLiteDatabaseManager
            db = SQLiteDatabaseManager()
            result = db.vacuum_database()
            print(f"Space reclaimed: {result['space_reclaimed_mb']:.2f} MB ({result['space_reclaimed_pct']:.1f}%)")

            # Automated VACUUM (weekly_maintenance.sh)
            python3 -c "from modules.db_manager_sqlite import SQLiteDatabaseManager; \\
            db = SQLiteDatabaseManager(); \\
            result = db.vacuum_database(); \\
            print(f'Space reclaimed: {result[\"space_reclaimed_mb\"]:.2f} MB')"
        """
        import time

        # Get size before VACUUM
        size_before = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        size_before_mb = size_before / (1024 * 1024)

        logger.info(f"🔧 Starting VACUUM operation (current size: {size_before_mb:.2f} MB)")

        start_time = time.time()

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Run VACUUM
            cursor.execute("VACUUM")

            conn.close()

            # Get size after VACUUM
            size_after = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            size_after_mb = size_after / (1024 * 1024)

            space_reclaimed = size_before - size_after
            space_reclaimed_mb = space_reclaimed / (1024 * 1024)
            space_reclaimed_pct = (space_reclaimed / size_before * 100) if size_before > 0 else 0

            duration = time.time() - start_time

            result = {
                'size_before_mb': round(size_before_mb, 2),
                'size_after_mb': round(size_after_mb, 2),
                'space_reclaimed_mb': round(space_reclaimed_mb, 2),
                'space_reclaimed_pct': round(space_reclaimed_pct, 1),
                'duration_seconds': round(duration, 2)
            }

            logger.info(
                f"✅ VACUUM complete: {size_before_mb:.2f} MB → {size_after_mb:.2f} MB "
                f"(reclaimed {space_reclaimed_mb:.2f} MB, {space_reclaimed_pct:.1f}%) "
                f"in {duration:.2f}s"
            )

            return result

        except Exception as e:
            logger.error(f"❌ VACUUM operation failed: {e}")
            return {
                'size_before_mb': round(size_before_mb, 2),
                'size_after_mb': round(size_before_mb, 2),
                'space_reclaimed_mb': 0.0,
                'space_reclaimed_pct': 0.0,
                'duration_seconds': round(time.time() - start_time, 2),
                'error': str(e)
            }

    def analyze_database(self) -> bool:
        """
        Update query optimizer statistics using ANALYZE

        ANALYZE gathers statistics about the distribution of data
        in tables and indexes, helping SQLite choose better query plans.

        Returns:
            True if successful

        Usage:
            # Manual ANALYZE
            from modules.db_manager_sqlite import SQLiteDatabaseManager
            db = SQLiteDatabaseManager()
            db.analyze_database()

            # Automated ANALYZE (weekly_maintenance.sh)
            sqlite3 data/spock_local.db "ANALYZE;"
        """
        logger.info("📊 Running ANALYZE to update query optimizer statistics")

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Run ANALYZE
            cursor.execute("ANALYZE")

            conn.close()

            logger.info("✅ ANALYZE complete - Query optimizer statistics updated")
            return True

        except Exception as e:
            logger.error(f"❌ ANALYZE operation failed: {e}")
            return False

    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive database statistics

        Returns:
            Dictionary with database statistics:
                - db_path: Database file path
                - db_size_mb: Database size (MB)
                - table_count: Number of tables
                - total_rows: Total rows across all tables
                - ohlcv_rows: OHLCV data rows
                - ticker_count: Total tickers
                - regions: List of regions
                - oldest_ohlcv_date: Oldest OHLCV data date
                - newest_ohlcv_date: Newest OHLCV data date
                - data_retention_days: Actual data retention (days)

        Usage:
            from modules.db_manager_sqlite import SQLiteDatabaseManager
            db = SQLiteDatabaseManager()
            stats = db.get_database_stats()
            print(f"Database size: {stats['db_size_mb']:.2f} MB")
            print(f"OHLCV rows: {stats['ohlcv_rows']:,}")
            print(f"Data retention: {stats['data_retention_days']} days")
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {}

        try:
            # Basic file info
            stats['db_path'] = self.db_path
            stats['db_size_mb'] = round(os.path.getsize(self.db_path) / (1024 * 1024), 2) if os.path.exists(self.db_path) else 0

            # Table count
            cursor.execute("SELECT COUNT(*) as count FROM sqlite_master WHERE type='table'")
            stats['table_count'] = cursor.fetchone()['count']

            # OHLCV statistics
            cursor.execute("SELECT COUNT(*) as count FROM ohlcv_data")
            stats['ohlcv_rows'] = cursor.fetchone()['count']

            cursor.execute("SELECT COUNT(DISTINCT ticker) as count FROM ohlcv_data")
            stats['unique_tickers'] = cursor.fetchone()['count']

            cursor.execute("SELECT COUNT(DISTINCT region) as count FROM ohlcv_data WHERE region IS NOT NULL")
            result = cursor.fetchone()
            stats['unique_regions'] = result['count'] if result else 0

            cursor.execute("SELECT DISTINCT region FROM ohlcv_data WHERE region IS NOT NULL ORDER BY region")
            stats['regions'] = [row['region'] for row in cursor.fetchall()]

            # Date range
            cursor.execute("SELECT MIN(date) as oldest, MAX(date) as newest FROM ohlcv_data")
            result = cursor.fetchone()
            if result and result['oldest']:
                stats['oldest_ohlcv_date'] = result['oldest']
                stats['newest_ohlcv_date'] = result['newest']

                # Calculate actual retention days
                cursor.execute("""
                    SELECT CAST(julianday(?) - julianday(?) AS INTEGER) as retention_days
                """, (result['newest'], result['oldest']))
                stats['data_retention_days'] = cursor.fetchone()['retention_days']
            else:
                stats['oldest_ohlcv_date'] = None
                stats['newest_ohlcv_date'] = None
                stats['data_retention_days'] = 0

            # Ticker count
            cursor.execute("SELECT COUNT(*) as count FROM tickers")
            stats['ticker_count'] = cursor.fetchone()['count']

            conn.close()

            return stats

        except Exception as e:
            logger.error(f"❌ Get database stats failed: {e}")
            conn.close()
            return stats
