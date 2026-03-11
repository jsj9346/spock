#!/usr/bin/env python3
"""
US Preferred Stock/Class Fundamentals Backfill

Collects fundamental data for US tickers containing '/' (preferred stocks, share classes)
using yfinance.

Usage:
    python3 scripts/backfill_us_preferred_fundamentals.py

Author: Spock Trading System
"""

import os
import sys
import time
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, List

import yfinance as yf

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_postgres import PostgresDatabaseManager

# Configure logging
log_file = f"log/{datetime.now().strftime('%Y%m%d')}_us_preferred_fundamentals.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class USPreferredFundamentalsCollector:
    """Collect fundamentals for US preferred stocks and share classes."""

    def __init__(self, db_manager: PostgresDatabaseManager):
        self.db = db_manager
        self.rate_limit = 1.0  # 1 request per second
        self.last_request = 0
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'no_data': 0,
            'start_time': None
        }

    def _rate_limit_sleep(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_request
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request = time.time()

    def _to_yf_ticker(self, ticker: str) -> str:
        """Convert DB ticker to yfinance format."""
        # DB format: BRK/B, MS/A -> yfinance: BRK-B, MS-PA
        # Try multiple formats for preferred stocks
        return ticker.replace('/', '-')

    def _safe_decimal(self, value) -> Optional[Decimal]:
        """Safely convert to Decimal."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value) -> Optional[int]:
        """Safely convert to int."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def get_target_tickers(self) -> List[Dict]:
        """Get US tickers containing '/'."""
        query = """
            SELECT ticker, name, exchange
            FROM tickers
            WHERE region = 'US' AND ticker LIKE '%%/%%' AND is_active = true
            ORDER BY ticker
        """
        return self.db.execute_query(query)

    def collect_fundamentals(self, ticker: str) -> Optional[Dict]:
        """Collect fundamentals from yfinance."""
        yf_ticker = self._to_yf_ticker(ticker)

        try:
            self._rate_limit_sleep()
            stock = yf.Ticker(yf_ticker)
            info = stock.info

            if not info or 'symbol' not in info:
                return None

            # Extract fundamental metrics matching table schema
            fundamentals = {
                'ticker': ticker,
                'region': 'US',
                'date': date.today(),
                'period_type': 'DAILY',
                'data_source': 'yfinance',

                # Market data
                'market_cap': self._safe_int(info.get('marketCap')),
                'shares_outstanding': self._safe_int(info.get('sharesOutstanding')),
                'ev': self._safe_int(info.get('enterpriseValue')),
                'close_price': self._safe_decimal(info.get('previousClose')),

                # Valuation ratios
                'per': self._safe_decimal(info.get('trailingPE') or info.get('forwardPE')),
                'pbr': self._safe_decimal(info.get('priceToBook')),
                'psr': self._safe_decimal(info.get('priceToSalesTrailing12Months')),
                'pcr': self._safe_decimal(info.get('priceToFreeCashflow')),
                'ev_ebitda': self._safe_decimal(info.get('enterpriseToEbitda')),

                # Dividend
                'dividend_yield': self._safe_decimal(info.get('dividendYield')),
                'dividend_per_share': self._safe_decimal(info.get('dividendRate')),

                # EPS
                'trailing_eps': self._safe_decimal(info.get('trailingEps')),
                'forward_eps': self._safe_decimal(info.get('forwardEps')),
            }

            return fundamentals

        except Exception as e:
            logger.debug(f"[{ticker}] Error: {e}")
            return None

    def save_fundamentals(self, data: Dict) -> bool:
        """Save fundamentals to database."""
        query = """
            INSERT INTO ticker_fundamentals (
                ticker, region, date, period_type, data_source,
                market_cap, shares_outstanding, ev, close_price,
                per, pbr, psr, pcr, ev_ebitda,
                dividend_yield, dividend_per_share,
                trailing_eps, forward_eps,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s,
                NOW()
            )
            ON CONFLICT (ticker, region, date, period_type)
            DO UPDATE SET
                market_cap = EXCLUDED.market_cap,
                shares_outstanding = EXCLUDED.shares_outstanding,
                ev = EXCLUDED.ev,
                close_price = EXCLUDED.close_price,
                per = EXCLUDED.per,
                pbr = EXCLUDED.pbr,
                psr = EXCLUDED.psr,
                pcr = EXCLUDED.pcr,
                ev_ebitda = EXCLUDED.ev_ebitda,
                dividend_yield = EXCLUDED.dividend_yield,
                dividend_per_share = EXCLUDED.dividend_per_share,
                trailing_eps = EXCLUDED.trailing_eps,
                forward_eps = EXCLUDED.forward_eps,
                data_source = EXCLUDED.data_source
        """

        try:
            params = (
                data['ticker'], data['region'], data['date'], data['period_type'], data['data_source'],
                data['market_cap'], data['shares_outstanding'], data['ev'], data['close_price'],
                data['per'], data['pbr'], data['psr'], data['pcr'], data['ev_ebitda'],
                data['dividend_yield'], data['dividend_per_share'],
                data['trailing_eps'], data['forward_eps']
            )
            return self.db.execute_update(query, params)
        except Exception as e:
            logger.error(f"[{data['ticker']}] DB save error: {e}")
            return False

    def run(self):
        """Run the backfill process."""
        logger.info("=" * 60)
        logger.info("US Preferred Stock Fundamentals Backfill")
        logger.info("=" * 60)

        # Get target tickers
        tickers = self.get_target_tickers()
        self.stats['total'] = len(tickers)
        self.stats['start_time'] = time.time()

        logger.info(f"Target tickers: {len(tickers)}")
        logger.info(f"Rate limit: {self.rate_limit} req/sec")
        logger.info(f"Estimated time: ~{len(tickers) * self.rate_limit / 60:.1f} minutes")
        logger.info("-" * 60)

        for i, ticker_info in enumerate(tickers, 1):
            ticker = ticker_info['ticker']
            name = ticker_info['name'][:30] if ticker_info['name'] else ''

            # Progress
            elapsed = time.time() - self.stats['start_time']
            rate = i / elapsed if elapsed > 0 else 0
            eta = (len(tickers) - i) / rate if rate > 0 else 0

            # Collect
            fundamentals = self.collect_fundamentals(ticker)

            if fundamentals:
                if self.save_fundamentals(fundamentals):
                    self.stats['success'] += 1
                    pe = fundamentals.get('per') or '-'
                    dy = fundamentals.get('dividend_yield') or '-'
                    logger.info(f"[{i}/{len(tickers)}] ✅ {ticker} (PE:{pe}, DY:{dy})")
                else:
                    self.stats['failed'] += 1
                    logger.warning(f"[{i}/{len(tickers)}] ❌ {ticker} - Save failed")
            else:
                self.stats['no_data'] += 1
                # Only log every 10th no-data to reduce noise
                if i % 10 == 0 or i <= 5:
                    logger.info(f"[{i}/{len(tickers)}] ⚠️ {ticker} - No yfinance data")

            # Progress summary every 50 tickers
            if i % 50 == 0:
                pct = i / len(tickers) * 100
                logger.info(f"--- Progress: {i}/{len(tickers)} ({pct:.1f}%) | Success: {self.stats['success']} | ETA: {eta/60:.1f}min ---")

        # Summary
        elapsed = time.time() - self.stats['start_time']
        logger.info("=" * 60)
        logger.info("BACKFILL COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total: {self.stats['total']}")
        logger.info(f"Success: {self.stats['success']}")
        logger.info(f"No Data: {self.stats['no_data']}")
        logger.info(f"Failed: {self.stats['failed']}")
        if self.stats['total'] > 0:
            logger.info(f"Success rate: {self.stats['success']/self.stats['total']*100:.1f}%")
        logger.info(f"Duration: {elapsed/60:.1f} minutes")
        logger.info("=" * 60)


def main():
    """Main entry point."""
    from dotenv import load_dotenv
    load_dotenv()

    db_manager = PostgresDatabaseManager()

    collector = USPreferredFundamentalsCollector(db_manager)
    collector.run()


if __name__ == '__main__':
    main()
