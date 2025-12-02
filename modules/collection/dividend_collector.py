"""
Dividend Data Collector

Collects dividend history data from multiple sources for different regions.
Supports KR (pykrx), US/JP/HK (yfinance), and stores in dividend_history table.

Author: Quant Platform Development Team
Date: 2025-11-27
"""

import os
import sys
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from contextlib import contextmanager

from loguru import logger


@contextmanager
def suppress_pykrx_logging():
    """
    pykrx 라이브러리의 로깅 버그를 우회하기 위한 컨텍스트 매니저.

    pykrx의 util.py에서 `logging.info(args, kwargs)` 형태로 잘못된
    로깅 호출을 하여 TypeError가 발생함. 이를 우회하기 위해
    pykrx 호출 시 logging 레벨을 임시로 WARNING으로 올림.
    """
    # Get the root logger and save current level
    root_logger = logging.getLogger()
    original_level = root_logger.level

    try:
        # Suppress INFO level logs during pykrx calls
        root_logger.setLevel(logging.WARNING)
        yield
    finally:
        # Restore original level
        root_logger.setLevel(original_level)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.db_manager_postgres import PostgresDatabaseManager


class DividendType(Enum):
    """Dividend type enumeration"""
    INTERIM = "interim"       # Mid-year dividend
    FINAL = "final"           # Year-end dividend
    SPECIAL = "special"       # Special/one-time dividend
    QUARTERLY = "quarterly"   # Quarterly dividend
    ANNUAL = "annual"         # Annual dividend


@dataclass
class DividendRecord:
    """Dividend record data class"""
    ticker: str
    region: str
    fiscal_year: int
    dividend_type: str
    dividend_per_share: float
    dividend_yield: Optional[float] = None
    declaration_date: Optional[date] = None
    ex_dividend_date: Optional[date] = None
    record_date: Optional[date] = None
    payment_date: Optional[date] = None
    currency: str = "USD"
    total_dividend_amount: Optional[float] = None
    payout_ratio: Optional[float] = None
    data_source: str = "unknown"


# Currency mapping by region
CURRENCY_MAP = {
    "KR": "KRW",
    "US": "USD",
    "JP": "JPY",
    "HK": "HKD",
    "CN": "CNY",
    "VN": "VND",
}


class DividendCollector:
    """
    Dividend data collector for multiple regions.

    Supports:
    - KR: pykrx library
    - US, JP, HK: yfinance library
    - CN, VN: yfinance (limited support)

    중복 방지:
    - CollectionTracker를 사용하여 같은 날 동일 ticker 재수집 방지
    - force=True 옵션으로 강제 재수집 가능
    """

    def __init__(
        self,
        db_manager: Optional[PostgresDatabaseManager] = None,
        skip_same_day: bool = True
    ):
        """
        Initialize DividendCollector.

        Args:
            db_manager: PostgresDatabaseManager instance. Creates new if not provided.
            skip_same_day: True면 같은 날 수집된 ticker 스킵 (기본: True)
        """
        self.db = db_manager or PostgresDatabaseManager()
        self.collected_count = 0
        self.error_count = 0
        self.skipped_count = 0  # 스킵된 ticker 수

        # CollectionTracker 초기화
        from modules.collection.collection_tracker import CollectionTracker
        self.tracker = CollectionTracker(self.db, skip_same_day=skip_same_day)

    def collect_kr_dividends(self, ticker: str, years: int = 5) -> List[DividendRecord]:
        """
        Collect Korean stock dividend data using pykrx.

        Args:
            ticker: Korean ticker (6-digit)
            years: Number of years to collect

        Returns:
            List of DividendRecord objects
        """
        records = []
        current_year = datetime.now().year

        # Validate ticker format (must be 6-digit numeric for KR)
        if not ticker or len(ticker) != 6 or not ticker.isdigit():
            logger.debug(f"Skipping invalid KR ticker format: {ticker}")
            return records

        try:
            from pykrx import stock

            # Validate ticker exists in pykrx before proceeding
            # Use suppress_pykrx_logging to avoid logging format bug in pykrx
            with suppress_pykrx_logging():
                try:
                    from pykrx.website.krx.market.ticker import get_stock_ticker_isin
                    isin = get_stock_ticker_isin(ticker)
                    if isin is None:
                        logger.debug(f"Ticker {ticker} not found in KRX registry, skipping")
                        return records
                except Exception:
                    # If validation fails, continue anyway (pykrx may still work)
                    pass

            for year in range(current_year - years + 1, current_year + 1):
                try:
                    # Get dividend data for the year
                    # pykrx provides annual dividend summary
                    start_date = f"{year}0101"
                    end_date = f"{year}1231"

                    # Try to get dividend yield data
                    # Use suppress_pykrx_logging to avoid logging format bug in pykrx
                    try:
                        with suppress_pykrx_logging():
                            div_data = stock.get_market_cap_by_date(
                                start_date, end_date, ticker
                            )
                        if div_data is not None and not div_data.empty:
                            # Get last record of the year
                            last_record = div_data.iloc[-1]
                            if '배당수익률' in last_record and last_record['배당수익률'] > 0:
                                record = DividendRecord(
                                    ticker=ticker,
                                    region="KR",
                                    fiscal_year=year,
                                    dividend_type=DividendType.ANNUAL.value,
                                    dividend_per_share=0,  # Not directly available
                                    dividend_yield=float(last_record['배당수익률']),
                                    currency="KRW",
                                    data_source="pykrx",
                                )
                                records.append(record)
                    except Exception as e:
                        logger.debug(f"pykrx dividend data not available for {ticker} {year}: {e}")

                except Exception as e:
                    logger.warning(f"Failed to get KR dividend for {ticker} year {year}: {e}")

        except ImportError:
            logger.warning("pykrx not installed. Install with: pip install pykrx")

        return records

    def collect_yfinance_dividends(
        self,
        ticker: str,
        region: str,
        years: int = 5
    ) -> List[DividendRecord]:
        """
        Collect dividend data using yfinance.

        Supports US, JP, HK, and other markets.

        Args:
            ticker: Ticker symbol (US format or with suffix for other markets)
            region: Region code
            years: Number of years to collect

        Returns:
            List of DividendRecord objects
        """
        records = []

        try:
            import yfinance as yf

            # Format ticker for yfinance
            yf_ticker = self._format_yfinance_ticker(ticker, region)
            stock = yf.Ticker(yf_ticker)

            # Get dividend history
            dividends = stock.dividends

            if dividends is None or dividends.empty:
                logger.debug(f"No dividend data for {yf_ticker}")
                return records

            # Filter by date range (use timezone-naive comparison)
            cutoff_date = datetime.now() - timedelta(days=years * 365)

            for div_date, amount in dividends.items():
                # Convert to timezone-naive datetime for comparison
                div_datetime = div_date.to_pydatetime()
                if hasattr(div_datetime, 'tzinfo') and div_datetime.tzinfo is not None:
                    div_datetime = div_datetime.replace(tzinfo=None)

                if div_datetime < cutoff_date:
                    continue

                # Determine dividend type based on region
                if region == "US":
                    div_type = DividendType.QUARTERLY.value
                else:
                    div_type = DividendType.ANNUAL.value

                # Determine fiscal year from ex-dividend date
                fiscal_year = div_date.year

                record = DividendRecord(
                    ticker=ticker,
                    region=region,
                    fiscal_year=fiscal_year,
                    dividend_type=div_type,
                    dividend_per_share=float(amount),
                    ex_dividend_date=div_date.date(),
                    currency=CURRENCY_MAP.get(region, "USD"),
                    data_source="yfinance",
                )
                records.append(record)

        except ImportError:
            logger.warning("yfinance not installed. Install with: pip install yfinance")
        except Exception as e:
            logger.error(f"Failed to collect yfinance dividends for {ticker}: {e}")

        return records

    def _format_yfinance_ticker(self, ticker: str, region: str) -> str:
        """Format ticker for yfinance API based on region."""
        if region == "US":
            # US preferred stocks/classes: DB uses '/' but yfinance uses '.'
            # e.g., BRK/B → BRK.B, MS/A → MS.A
            return ticker.replace('/', '-') if '/' in ticker else ticker
        elif region == "JP":
            return f"{ticker}.T"
        elif region == "HK":
            # HK tickers need leading zeros and .HK suffix
            return f"{ticker.zfill(4)}.HK"
        elif region == "KR":
            return f"{ticker}.KS"
        elif region == "CN":
            # Shanghai: .SS, Shenzhen: .SZ
            if ticker.startswith("6"):
                return f"{ticker}.SS"
            else:
                return f"{ticker}.SZ"
        else:
            return ticker

    def save_dividend_record(self, record: DividendRecord) -> bool:
        """
        Save a single dividend record to the database.

        Uses UPSERT to handle duplicates.

        Args:
            record: DividendRecord to save

        Returns:
            True if successful, False otherwise
        """
        query = """
        INSERT INTO dividend_history (
            ticker, region, fiscal_year, dividend_type,
            dividend_per_share, dividend_yield,
            declaration_date, ex_dividend_date, record_date, payment_date,
            currency, total_dividend_amount, payout_ratio, data_source
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        ON CONFLICT (ticker, region, fiscal_year, dividend_type, ex_dividend_date)
        DO UPDATE SET
            dividend_per_share = EXCLUDED.dividend_per_share,
            dividend_yield = EXCLUDED.dividend_yield,
            declaration_date = COALESCE(EXCLUDED.declaration_date, dividend_history.declaration_date),
            record_date = COALESCE(EXCLUDED.record_date, dividend_history.record_date),
            payment_date = COALESCE(EXCLUDED.payment_date, dividend_history.payment_date),
            total_dividend_amount = COALESCE(EXCLUDED.total_dividend_amount, dividend_history.total_dividend_amount),
            payout_ratio = COALESCE(EXCLUDED.payout_ratio, dividend_history.payout_ratio),
            data_source = EXCLUDED.data_source,
            updated_at = NOW();
        """

        try:
            success = self.db.execute_update(query, (
                record.ticker,
                record.region,
                record.fiscal_year,
                record.dividend_type,
                record.dividend_per_share,
                record.dividend_yield,
                record.declaration_date,
                record.ex_dividend_date,
                record.record_date,
                record.payment_date,
                record.currency,
                record.total_dividend_amount,
                record.payout_ratio,
                record.data_source,
            ))
            return success
        except Exception as e:
            logger.error(f"Failed to save dividend record for {record.ticker}: {e}")
            return False

    def save_dividend_records(self, records: List[DividendRecord]) -> int:
        """
        Save multiple dividend records to the database.

        Args:
            records: List of DividendRecord objects

        Returns:
            Number of successfully saved records
        """
        saved = 0
        for record in records:
            if self.save_dividend_record(record):
                saved += 1
                self.collected_count += 1
            else:
                self.error_count += 1
        return saved

    def collect_ticker_dividends(
        self,
        ticker: str,
        region: str,
        years: int = 5
    ) -> List[DividendRecord]:
        """
        Collect dividend data for a single ticker.

        Args:
            ticker: Ticker symbol
            region: Region code
            years: Number of years to collect

        Returns:
            List of DividendRecord objects
        """
        if region == "KR":
            # Try pykrx first, fall back to yfinance
            records = self.collect_kr_dividends(ticker, years)
            if not records:
                records = self.collect_yfinance_dividends(ticker, region, years)
        else:
            records = self.collect_yfinance_dividends(ticker, region, years)

        return records

    def collect_and_save(
        self,
        ticker: str,
        region: str,
        years: int = 5
    ) -> int:
        """
        Collect and save dividend data for a single ticker.

        Args:
            ticker: Ticker symbol
            region: Region code
            years: Number of years to collect

        Returns:
            Number of records saved
        """
        records = self.collect_ticker_dividends(ticker, region, years)
        if records:
            return self.save_dividend_records(records)
        return 0

    def collect_batch(
        self,
        tickers: List[str],
        region: str,
        years: int = 5,
        force: bool = False
    ) -> Dict[str, int]:
        """
        Collect dividend data for multiple tickers.

        중복 방지:
        - CollectionTracker를 사용하여 같은 날 수집된 ticker 자동 스킵
        - force=True 옵션으로 강제 재수집 가능

        Args:
            tickers: List of ticker symbols
            region: Region code
            years: Number of years to collect
            force: True면 이미 수집된 ticker도 재수집

        Returns:
            Dictionary with ticker -> records_saved count
        """
        import time
        from modules.collection.collection_tracker import DataType

        results = {}
        self.skipped_count = 0

        # 스킵할 ticker 확인 (force=False인 경우)
        if not force:
            to_process, to_skip = self.tracker.should_skip_batch(
                tickers, region, DataType.DIVIDEND
            )

            if to_skip:
                logger.info(
                    f"  ⏭️  [{region}] {len(to_skip)} tickers skipped "
                    f"(already collected today)"
                )
                self.skipped_count = len(to_skip)
                for ticker in to_skip:
                    results[ticker] = 0  # 스킵됨
        else:
            to_process = tickers
            logger.info(f"  🔄 [{region}] Force mode - recollecting all {len(tickers)} tickers")

        total = len(to_process)

        if total == 0:
            logger.info(f"  ✅ [{region}] All tickers already collected today")
            return results

        logger.info(f"  📊 [{region}] Collecting dividends for {total} tickers...")

        for i, ticker in enumerate(to_process):
            start_time = time.time()
            try:
                count = self.collect_and_save(ticker, region, years)
                duration_ms = int((time.time() - start_time) * 1000)

                results[ticker] = count

                # 추적 기록
                self.tracker.mark_collected(
                    ticker, region, DataType.DIVIDEND,
                    status='success',
                    records_count=count,
                    duration_ms=duration_ms
                )

                if (i + 1) % 100 == 0 or (i + 1) == total:
                    logger.info(f"  Progress: {i+1}/{total} ({(i+1)/total*100:.1f}%)")

            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.error(f"Failed to collect dividends for {ticker}: {e}")
                results[ticker] = 0

                # 실패 기록
                self.tracker.mark_collected(
                    ticker, region, DataType.DIVIDEND,
                    status='failed',
                    duration_ms=duration_ms,
                    error_message=str(e)
                )

        return results

    def get_dividend_history(
        self,
        ticker: str,
        region: str,
        years: Optional[int] = None
    ) -> List[Dict]:
        """
        Get dividend history from database.

        Args:
            ticker: Ticker symbol
            region: Region code
            years: Number of years to retrieve (None for all)

        Returns:
            List of dividend records as dictionaries
        """
        if years:
            cutoff_year = datetime.now().year - years
            query = """
            SELECT * FROM dividend_history
            WHERE ticker = %s AND region = %s AND fiscal_year >= %s
            ORDER BY fiscal_year DESC, ex_dividend_date DESC;
            """
            params = (ticker, region, cutoff_year)
        else:
            query = """
            SELECT * FROM dividend_history
            WHERE ticker = %s AND region = %s
            ORDER BY fiscal_year DESC, ex_dividend_date DESC;
            """
            params = (ticker, region)

        result = self.db.execute_query(query, params)
        return result if result else []

    def get_summary_stats(self) -> Dict:
        """Get summary statistics from dividend_history table."""
        query = """
        SELECT
            region,
            COUNT(*) as total_records,
            COUNT(DISTINCT ticker) as unique_tickers,
            MIN(fiscal_year) as min_year,
            MAX(fiscal_year) as max_year,
            COUNT(DISTINCT data_source) as sources
        FROM dividend_history
        GROUP BY region
        ORDER BY total_records DESC;
        """
        result = self.db.execute_query(query)
        return {row['region']: dict(row) for row in result} if result else {}


def main():
    """Test the DividendCollector"""
    logger.info("Testing DividendCollector")

    collector = DividendCollector()

    # Test with a few sample tickers
    test_tickers = [
        ("005930", "KR"),  # Samsung
        ("AAPL", "US"),    # Apple
        ("7203", "JP"),    # Toyota
    ]

    for ticker, region in test_tickers:
        logger.info(f"\nCollecting dividends for {ticker} ({region})")
        records = collector.collect_ticker_dividends(ticker, region, years=3)
        logger.info(f"Found {len(records)} dividend records")

        for record in records[:3]:
            logger.info(
                f"  {record.fiscal_year} {record.dividend_type}: "
                f"{record.dividend_per_share} {record.currency}"
            )

    # Get summary stats
    stats = collector.get_summary_stats()
    logger.info(f"\nDatabase Summary: {stats}")


if __name__ == "__main__":
    main()
