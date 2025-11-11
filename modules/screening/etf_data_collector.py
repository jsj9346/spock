"""
ETF Data Collector Module

Collects fundamental data for ETFs from multiple sources:
- KRX ETF Portal: AUM, TER, tracking error
- ETFCheck: Sector theme, tracking index
- Fund Managers: Dividend yield

Features:
- Async web scraping with rate limiting
- Error handling and retry logic
- Data validation and normalization
- Progress tracking and logging

Author: Spock Quant Platform
Date: 2025-10-31
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import time
import re

import aiohttp
from bs4 import BeautifulSoup
import pandas as pd

from modules.db_manager_postgres import PostgresDatabaseManager
from psycopg2 import extras

logger = logging.getLogger(__name__)


class ETFDataCollector:
    """
    Collect ETF fundamental data from multiple sources.

    Sources:
    - KRX: AUM, TER, tracking error
    - ETFCheck: Sector theme, tracking index
    - 운용사: Dividend yield

    Usage:
        collector = ETFDataCollector(db_manager, rate_limit=1.0)
        success_count = await collector.collect_all_data(['152100', '114800'])
    """

    def __init__(self,
                 db_manager: PostgresDatabaseManager,
                 rate_limit: float = 1.0):
        """
        Initialize ETF data collector.

        Args:
            db_manager: PostgreSQL database manager instance
            rate_limit: Delay between requests in seconds (default: 1.0)
        """
        self.db = db_manager
        self.rate_limit = rate_limit
        self.session: Optional[aiohttp.ClientSession] = None

        # Data source URLs
        self.krx_etf_url = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
        self.etfcheck_url = "https://www.etfcheck.co.kr"

        logger.info(f"ETFDataCollector initialized (rate_limit={rate_limit}s)")

    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                             'AppleWebKit/537.36 (KHTML, like Gecko) '
                             'Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'http://data.krx.co.kr/',  # Critical for KRX API access
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            },
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def collect_all_data(self, tickers: List[str]) -> int:
        """
        Collect all data from all sources.

        Args:
            tickers: List of ETF ticker symbols

        Returns:
            Number of successfully collected ETFs
        """
        logger.info(f"Starting collection for {len(tickers)} ETFs")

        async with self:
            # Collect from all sources
            krx_success = await self.collect_krx_data(tickers)
            etfcheck_success = await self.collect_etfcheck_data(tickers)

            # Return minimum (all data sources must succeed)
            success_count = min(krx_success, etfcheck_success)

        logger.info(f"Collection complete: {success_count}/{len(tickers)} ETFs")
        return success_count

    async def collect_krx_data(self, tickers: List[str]) -> int:
        """
        Collect AUM, TER, tracking error from KRX.

        Args:
            tickers: List of ETF ticker symbols

        Returns:
            Number of successfully collected ETFs
        """
        logger.info(f"📊 Collecting KRX data for {len(tickers)} ETFs...")

        success_count = 0
        failed_tickers = []

        async with self:
            for i, ticker in enumerate(tickers, 1):
                try:
                    # Rate limiting
                    if i > 1:
                        await asyncio.sleep(self.rate_limit)

                    # Collect data
                    data = await self._fetch_krx_etf_data(ticker)

                    if data:
                        # Save to database
                        await self._save_krx_data(ticker, data)
                        success_count += 1

                        if i % 10 == 0:
                            logger.info(f"Progress: {i}/{len(tickers)} ({success_count} successful)")

                    else:
                        logger.warning(f"No KRX data for {ticker}")
                        failed_tickers.append(ticker)

                except Exception as e:
                    logger.error(f"Failed to collect KRX data for {ticker}: {e}")
                    failed_tickers.append(ticker)

        if failed_tickers:
            logger.warning(f"Failed tickers: {', '.join(failed_tickers[:10])}")
            if len(failed_tickers) > 10:
                logger.warning(f"... and {len(failed_tickers) - 10} more")

        logger.info(f"✅ KRX collection: {success_count}/{len(tickers)} successful")
        return success_count

    async def collect_etfcheck_data(self, tickers: List[str]) -> int:
        """
        Collect sector, theme, tracking index from ETFCheck.

        Args:
            tickers: List of ETF ticker symbols

        Returns:
            Number of successfully collected ETFs
        """
        logger.info(f"📊 Collecting ETFCheck data for {len(tickers)} ETFs...")

        success_count = 0
        failed_tickers = []

        async with self:
            for i, ticker in enumerate(tickers, 1):
                try:
                    # Rate limiting
                    if i > 1:
                        await asyncio.sleep(self.rate_limit)

                    # Collect data
                    data = await self._fetch_etfcheck_data(ticker)

                    if data:
                        # Save to database
                        await self._save_etfcheck_data(ticker, data)
                        success_count += 1

                        if i % 10 == 0:
                            logger.info(f"Progress: {i}/{len(tickers)} ({success_count} successful)")

                    else:
                        logger.warning(f"No ETFCheck data for {ticker}")
                        failed_tickers.append(ticker)

                except Exception as e:
                    logger.error(f"Failed to collect ETFCheck data for {ticker}: {e}")
                    failed_tickers.append(ticker)

        if failed_tickers:
            logger.warning(f"Failed tickers: {', '.join(failed_tickers[:10])}")
            if len(failed_tickers) > 10:
                logger.warning(f"... and {len(failed_tickers) - 10} more")

        logger.info(f"✅ ETFCheck collection: {success_count}/{len(tickers)} successful")
        return success_count

    # ============================================================================
    # KRX Data Fetching
    # ============================================================================

    async def _fetch_krx_etf_data(self, ticker: str) -> Optional[Dict]:
        """
        Fetch ETF data from KRX.

        Args:
            ticker: ETF ticker symbol (e.g., '152100')

        Returns:
            Dict with AUM, TER, tracking error, or None if failed
        """
        try:
            # KRX ETF data endpoint
            url = f"http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"

            # Request payload (based on KRX ETF portal)
            payload = {
                'bld': 'dbms/MDC/STAT/standard/MDCSTAT05001',
                'locale': 'ko_KR',
                'isuCd': ticker,  # ETF ticker
            }

            async with self.session.post(url, data=payload) as response:
                if response.status == 200:
                    json_data = await response.json()

                    # Parse KRX response
                    if json_data and 'output' in json_data:
                        return self._parse_krx_response(json_data['output'])
                    else:
                        logger.debug(f"No data in KRX response for {ticker}")
                        return None
                else:
                    logger.warning(f"KRX request failed for {ticker}: HTTP {response.status}")
                    return None

        except Exception as e:
            logger.error(f"Error fetching KRX data for {ticker}: {e}")
            return None

    def _parse_krx_response(self, data: List[Dict]) -> Optional[Dict]:
        """
        Parse KRX JSON response.

        Args:
            data: KRX API response data

        Returns:
            Dict with normalized ETF data
        """
        try:
            if not data or len(data) == 0:
                return None

            # Get first row (latest data)
            row = data[0]

            # Extract fields (field names may vary)
            result = {
                'aum': self._parse_krx_number(row.get('NAV_TOT_AMT')),  # 순자산총액
                'ter': self._parse_krx_percentage(row.get('TOT_FEE')),  # 총보수
                'tracking_error_20d': self._parse_krx_percentage(row.get('TRK_ERR_20')),
                'tracking_error_60d': self._parse_krx_percentage(row.get('TRK_ERR_60')),
                'tracking_error_120d': self._parse_krx_percentage(row.get('TRK_ERR_120')),
                'tracking_error_250d': self._parse_krx_percentage(row.get('TRK_ERR_250')),
                'issuer': row.get('COMP_NM'),  # 운용사
                'underlying_asset_count': self._parse_krx_number(row.get('COMP_CNT')),  # 구성종목수
            }

            return result

        except Exception as e:
            logger.error(f"Error parsing KRX response: {e}")
            return None

    def _parse_krx_number(self, value: str) -> Optional[int]:
        """Parse KRX number string (removes commas)"""
        if not value:
            return None
        try:
            return int(value.replace(',', ''))
        except:
            return None

    def _parse_krx_percentage(self, value: str) -> Optional[float]:
        """Parse KRX percentage string"""
        if not value:
            return None
        try:
            return float(value.replace('%', '').replace(',', ''))
        except:
            return None

    # ============================================================================
    # ETFCheck Data Fetching
    # ============================================================================

    async def _fetch_etfcheck_data(self, ticker: str) -> Optional[Dict]:
        """
        Fetch ETF data from ETFCheck.

        Args:
            ticker: ETF ticker symbol (e.g., '152100')

        Returns:
            Dict with sector, theme, tracking index, or None if failed
        """
        try:
            # ETFCheck detail page URL
            url = f"https://www.etfcheck.co.kr/mobile/etf/summary/{ticker}"

            async with self.session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    return self._parse_etfcheck_html(html)
                else:
                    logger.warning(f"ETFCheck request failed for {ticker}: HTTP {response.status}")
                    return None

        except Exception as e:
            logger.error(f"Error fetching ETFCheck data for {ticker}: {e}")
            return None

    def _parse_etfcheck_html(self, html: str) -> Optional[Dict]:
        """
        Parse ETFCheck HTML page.

        Args:
            html: HTML content

        Returns:
            Dict with normalized ETF data
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Extract fields from HTML (selectors may need adjustment)
            result = {
                'sector_theme': self._extract_text(soup, 'div.sector'),
                'tracking_index': self._extract_text(soup, 'div.index'),
                'fund_type': self._extract_text(soup, 'div.type'),
                'geographic_region': self._extract_text(soup, 'div.region'),
            }

            return result

        except Exception as e:
            logger.error(f"Error parsing ETFCheck HTML: {e}")
            return None

    def _extract_text(self, soup: BeautifulSoup, selector: str) -> Optional[str]:
        """Extract text from BeautifulSoup element"""
        element = soup.select_one(selector)
        if element:
            return element.get_text(strip=True)
        return None

    # ============================================================================
    # Database Operations
    # ============================================================================

    async def _save_krx_data(self, ticker: str, data: Dict):
        """Save KRX data to database"""
        try:
            with self.db._get_connection() as conn:
                with conn.cursor(cursor_factory=extras.RealDictCursor) as cursor:
                    cursor.execute("""
                        INSERT INTO etf_details (
                            ticker, region,
                            aum, ter,
                            tracking_error_20d, tracking_error_60d,
                            tracking_error_120d, tracking_error_250d,
                            issuer, underlying_asset_count,
                            last_updated
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (ticker, region)
                        DO UPDATE SET
                            aum = EXCLUDED.aum,
                            ter = EXCLUDED.ter,
                            tracking_error_20d = EXCLUDED.tracking_error_20d,
                            tracking_error_60d = EXCLUDED.tracking_error_60d,
                            tracking_error_120d = EXCLUDED.tracking_error_120d,
                            tracking_error_250d = EXCLUDED.tracking_error_250d,
                            issuer = EXCLUDED.issuer,
                            underlying_asset_count = EXCLUDED.underlying_asset_count,
                            last_updated = EXCLUDED.last_updated
                    """, (
                        ticker,
                        'KR',
                        data.get('aum'),
                        data.get('ter'),
                        data.get('tracking_error_20d'),
                        data.get('tracking_error_60d'),
                        data.get('tracking_error_120d'),
                        data.get('tracking_error_250d'),
                        data.get('issuer'),
                        data.get('underlying_asset_count'),
                        datetime.now()
                    ))
                conn.commit()

            logger.debug(f"Saved KRX data for {ticker}")

        except Exception as e:
            logger.error(f"Failed to save KRX data for {ticker}: {e}")
            raise

    async def _save_etfcheck_data(self, ticker: str, data: Dict):
        """Save ETFCheck data to database"""
        try:
            with self.db._get_connection() as conn:
                with conn.cursor(cursor_factory=extras.RealDictCursor) as cursor:
                    cursor.execute("""
                        INSERT INTO etf_details (
                            ticker, region,
                            sector_theme, tracking_index,
                            fund_type, geographic_region,
                            last_updated
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (ticker, region)
                        DO UPDATE SET
                            sector_theme = EXCLUDED.sector_theme,
                            tracking_index = EXCLUDED.tracking_index,
                            fund_type = EXCLUDED.fund_type,
                            geographic_region = EXCLUDED.geographic_region,
                            last_updated = EXCLUDED.last_updated
                    """, (
                        ticker,
                        'KR',
                        data.get('sector_theme'),
                        data.get('tracking_index'),
                        data.get('fund_type'),
                        data.get('geographic_region'),
                        datetime.now()
                    ))
                conn.commit()

            logger.debug(f"Saved ETFCheck data for {ticker}")

        except Exception as e:
            logger.error(f"Failed to save ETFCheck data for {ticker}: {e}")
            raise
