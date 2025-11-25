"""
Ticker Status Manager for yfinance data collection optimization.

Manages ticker status to skip unsupported/delisted tickers and optimize
data collection performance.

Usage:
    from modules.ticker_status_manager import TickerStatusManager
    from modules.db_manager_postgres import PostgresDatabaseManager

    db = PostgresDatabaseManager()
    tsm = TickerStatusManager(db)

    # Get active tickers for collection
    tickers = tsm.get_active_tickers('JP')

    # Update status on success/failure
    tsm.mark_success('7203', 'JP')
    tsm.mark_failure('9224', 'JP', 'No data found, symbol may be delisted')
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from modules.db_manager_postgres import PostgresDatabaseManager

logger = logging.getLogger(__name__)


class TickerStatusManager:
    """yfinance 티커 상태 관리 클래스"""

    # Status constants
    STATUS_UNKNOWN = 'unknown'      # 초기 상태 (아직 확인 안됨)
    STATUS_ACTIVE = 'active'        # 정상 수집 가능
    STATUS_DELISTED = 'delisted'    # 상장폐지/거래정지 (자동)
    STATUS_UNSUPPORTED = 'unsupported'  # yfinance 미지원 (자동)
    STATUS_BLACKLIST = 'blacklist'  # 수동 블랙리스트
    STATUS_RETRY = 'retry'          # 일시적 오류, 재시도 필요

    # Statuses to skip during collection
    SKIP_STATUSES = {STATUS_DELISTED, STATUS_UNSUPPORTED, STATUS_BLACKLIST}

    # Statuses to process during collection
    ACTIVE_STATUSES = {STATUS_UNKNOWN, STATUS_ACTIVE, STATUS_RETRY}

    # Error message patterns -> status mapping
    ERROR_STATUS_MAP = {
        'no data found': STATUS_DELISTED,
        'no data': STATUS_DELISTED,
        'no ohlcv data': STATUS_DELISTED,
        'symbol may be delisted': STATUS_DELISTED,
        'no timezone found': STATUS_DELISTED,
        'quote not found': STATUS_DELISTED,
        'not found': STATUS_DELISTED,
        'rate limit': STATUS_RETRY,
        'timeout': STATUS_RETRY,
        'connection': STATUS_RETRY,
        'too many requests': STATUS_RETRY,
    }

    # Fail count threshold before status change
    FAIL_COUNT_THRESHOLD = 3

    # Days before re-verification of stale status
    STALE_DAYS = 30

    def __init__(self, db_manager: PostgresDatabaseManager):
        """
        Initialize TickerStatusManager.

        Args:
            db_manager: PostgresDatabaseManager instance
        """
        self.db = db_manager

    # =========================================================================
    # Query Methods
    # =========================================================================

    def get_active_tickers(self, region: str, include_retry: bool = True) -> List[str]:
        """
        Get list of tickers eligible for data collection.

        Excludes tickers with skip statuses (delisted, unsupported, blacklist).
        Includes tickers that need re-verification (>30 days since last check).

        Args:
            region: Market region (KR, HK, US, JP, CN, VN)
            include_retry: Whether to include 'retry' status tickers

        Returns:
            List of ticker symbols
        """
        active_statuses = list(self.ACTIVE_STATUSES)
        if not include_retry:
            active_statuses.remove(self.STATUS_RETRY)

        query = """
            SELECT ticker
            FROM tickers
            WHERE region = %s
              AND (
                  yf_status IN %s
                  OR (yf_status IN ('delisted', 'unsupported')
                      AND yf_last_check < NOW() - INTERVAL '%s days')
              )
            ORDER BY ticker
        """

        result = self.db.execute_query(query, (region, tuple(active_statuses), self.STALE_DAYS))
        return [row['ticker'] for row in result]

    def get_skip_tickers(self, region: str) -> List[str]:
        """
        Get list of tickers to skip during collection.

        Args:
            region: Market region

        Returns:
            List of ticker symbols to skip
        """
        query = """
            SELECT ticker
            FROM tickers
            WHERE region = %s
              AND yf_status IN %s
              AND (yf_last_check IS NULL OR yf_last_check >= NOW() - INTERVAL '%s days')
            ORDER BY ticker
        """

        result = self.db.execute_query(query, (region, tuple(self.SKIP_STATUSES), self.STALE_DAYS))
        return [row['ticker'] for row in result]

    def get_status(self, ticker: str, region: str) -> Optional[Dict]:
        """
        Get status details for a single ticker.

        Args:
            ticker: Ticker symbol
            region: Market region

        Returns:
            Dict with status details or None if not found
        """
        query = """
            SELECT ticker, region, yf_status, yf_last_check,
                   yf_fail_reason, yf_fail_count
            FROM tickers
            WHERE ticker = %s AND region = %s
        """

        result = self.db.execute_query(query, (ticker, region))
        return result[0] if result else None

    def get_status_summary(self, region: str) -> Dict:
        """
        Get status summary statistics for a region.

        Args:
            region: Market region

        Returns:
            Dict with status counts
        """
        query = """
            SELECT yf_status, COUNT(*) as count
            FROM tickers
            WHERE region = %s
            GROUP BY yf_status
            ORDER BY yf_status
        """

        result = self.db.execute_query(query, (region,))

        summary = {
            'total': 0,
            'active': 0,
            'unknown': 0,
            'retry': 0,
            'delisted': 0,
            'unsupported': 0,
            'blacklist': 0,
            'skip_count': 0,
            'process_count': 0,
        }

        for row in result:
            status = row['yf_status'] or 'unknown'
            count = row['count']
            summary['total'] += count
            summary[status] = count

            if status in self.SKIP_STATUSES:
                summary['skip_count'] += count
            else:
                summary['process_count'] += count

        return summary

    # =========================================================================
    # Status Update Methods
    # =========================================================================

    def mark_success(self, ticker: str, region: str):
        """
        Mark ticker as successfully collected (active status).

        Args:
            ticker: Ticker symbol
            region: Market region
        """
        query = """
            UPDATE tickers
            SET yf_status = %s,
                yf_last_check = NOW(),
                yf_fail_count = 0,
                yf_fail_reason = NULL
            WHERE ticker = %s AND region = %s
        """

        self.db.execute_update(query, (self.STATUS_ACTIVE, ticker, region))
        logger.debug(f"Marked {ticker} ({region}) as active")

    def mark_failure(self, ticker: str, region: str, error_msg: str):
        """
        Mark ticker as failed and update status based on error type.

        - First/second failure: Increment fail_count, keep status
        - Third+ failure: Change status based on error type

        Args:
            ticker: Ticker symbol
            region: Market region
            error_msg: Error message from yfinance
        """
        error_lower = error_msg.lower()

        # Classify error type
        new_status = self.STATUS_RETRY  # Default: retry
        fail_reason = 'unknown_error'

        for pattern, status in self.ERROR_STATUS_MAP.items():
            if pattern in error_lower:
                new_status = status
                fail_reason = pattern.replace(' ', '_')
                break

        # Special handling for US preferred stocks (ticker contains /)
        if region == 'US' and '/' in ticker:
            new_status = self.STATUS_UNSUPPORTED
            fail_reason = 'preferred_stock'

        # Update with conditional status change
        query = """
            UPDATE tickers
            SET yf_fail_count = yf_fail_count + 1,
                yf_last_check = NOW(),
                yf_fail_reason = %s,
                yf_status = CASE
                    WHEN yf_fail_count >= %s THEN %s
                    WHEN yf_status = 'unknown' AND %s IN ('delisted', 'unsupported') THEN %s
                    ELSE yf_status
                END
            WHERE ticker = %s AND region = %s
        """

        self.db.execute_update(query, (
            fail_reason,
            self.FAIL_COUNT_THRESHOLD - 1,  # Change on 3rd failure (count starts at 0)
            new_status,
            new_status,  # For immediate change on first failure for clear errors
            new_status,
            ticker,
            region
        ))

        logger.debug(f"Marked {ticker} ({region}) failure: {fail_reason}")

    def set_blacklist(self, ticker: str, region: str, reason: str = 'manual'):
        """
        Manually add ticker to blacklist.

        Args:
            ticker: Ticker symbol
            region: Market region
            reason: Reason for blacklisting
        """
        query = """
            UPDATE tickers
            SET yf_status = %s,
                yf_last_check = NOW(),
                yf_fail_reason = %s
            WHERE ticker = %s AND region = %s
        """

        self.db.execute_update(query, (self.STATUS_BLACKLIST, reason, ticker, region))
        logger.info(f"Blacklisted {ticker} ({region}): {reason}")

    def clear_blacklist(self, ticker: str, region: str):
        """
        Remove ticker from blacklist (reset to unknown for re-verification).

        Args:
            ticker: Ticker symbol
            region: Market region
        """
        query = """
            UPDATE tickers
            SET yf_status = %s,
                yf_last_check = NULL,
                yf_fail_count = 0,
                yf_fail_reason = NULL
            WHERE ticker = %s AND region = %s
        """

        self.db.execute_update(query, (self.STATUS_UNKNOWN, ticker, region))
        logger.info(f"Cleared blacklist for {ticker} ({region})")

    def reset_status(self, ticker: str, region: str):
        """
        Reset ticker status to unknown for re-verification.

        Args:
            ticker: Ticker symbol
            region: Market region
        """
        self.clear_blacklist(ticker, region)  # Same operation

    # =========================================================================
    # Batch Operations
    # =========================================================================

    def bulk_mark_success(self, tickers: List[Tuple[str, str]]):
        """
        Mark multiple tickers as successful.

        Args:
            tickers: List of (ticker, region) tuples
        """
        query = """
            UPDATE tickers
            SET yf_status = %s,
                yf_last_check = NOW(),
                yf_fail_count = 0,
                yf_fail_reason = NULL
            WHERE ticker = %s AND region = %s
        """

        for ticker, region in tickers:
            self.db.execute_update(query, (self.STATUS_ACTIVE, ticker, region))

    def auto_detect_unsupported(self, region: str) -> int:
        """
        Auto-detect unsupported tickers based on known patterns.

        Currently detects:
        - US preferred stocks (ticker contains '/')

        Args:
            region: Market region

        Returns:
            Number of tickers marked as unsupported
        """
        if region != 'US':
            return 0

        # Mark US preferred stocks as unsupported
        query = """
            UPDATE tickers
            SET yf_status = %s,
                yf_fail_reason = 'preferred_stock',
                yf_last_check = NOW()
            WHERE region = 'US'
              AND ticker LIKE '%%/%%'
              AND yf_status != %s
        """

        # Get count before update
        count_query = """
            SELECT COUNT(*) as cnt FROM tickers
            WHERE region = 'US' AND ticker LIKE '%%/%%' AND yf_status != %s
        """
        result = self.db.execute_query(count_query, (self.STATUS_UNSUPPORTED,))
        count = result[0]['cnt'] if result else 0

        if count > 0:
            self.db.execute_update(query, (self.STATUS_UNSUPPORTED, self.STATUS_UNSUPPORTED))
            logger.info(f"Auto-detected {count} US preferred stocks as unsupported")

        return count

    def init_status_from_ohlcv(self, region: str) -> Dict:
        """
        Initialize status based on existing OHLCV data.

        - Tickers with recent data (7 days) -> active
        - Tickers with stale data (30+ days) -> unknown (needs verification)

        Args:
            region: Market region

        Returns:
            Dict with counts of each status set
        """
        results = {'active': 0, 'unknown': 0}

        # Mark tickers with recent OHLCV data as active
        active_query = """
            UPDATE tickers t
            SET yf_status = 'active',
                yf_last_check = NOW()
            WHERE t.region = %s
              AND t.yf_status = 'unknown'
              AND EXISTS (
                  SELECT 1 FROM ohlcv_data o
                  WHERE o.ticker = t.ticker
                    AND o.region = t.region
                    AND o.date >= CURRENT_DATE - INTERVAL '7 days'
              )
        """

        # Count before
        count_query = """
            SELECT COUNT(*) as cnt FROM tickers t
            WHERE t.region = %s AND t.yf_status = 'unknown'
              AND EXISTS (
                  SELECT 1 FROM ohlcv_data o
                  WHERE o.ticker = t.ticker AND o.region = t.region
                    AND o.date >= CURRENT_DATE - INTERVAL '7 days'
              )
        """
        result = self.db.execute_query(count_query, (region,))
        results['active'] = result[0]['cnt'] if result else 0

        if results['active'] > 0:
            self.db.execute_update(active_query, (region,))

        logger.info(f"[{region}] Initialized status: {results['active']} active from OHLCV data")
        return results

    def verify_stale_tickers(self, region: str, days: int = None) -> List[str]:
        """
        Get list of tickers that need re-verification.

        Args:
            region: Market region
            days: Days threshold (default: STALE_DAYS)

        Returns:
            List of tickers needing verification
        """
        if days is None:
            days = self.STALE_DAYS

        query = """
            SELECT ticker
            FROM tickers
            WHERE region = %s
              AND yf_status IN ('delisted', 'unsupported')
              AND yf_last_check < NOW() - INTERVAL '%s days'
            ORDER BY ticker
        """

        result = self.db.execute_query(query, (region, days))
        return [row['ticker'] for row in result]

    def get_fail_summary(self, region: str) -> List[Dict]:
        """
        Get summary of failure reasons for a region.

        Args:
            region: Market region

        Returns:
            List of dicts with fail_reason and count
        """
        query = """
            SELECT yf_fail_reason, COUNT(*) as count
            FROM tickers
            WHERE region = %s
              AND yf_fail_reason IS NOT NULL
            GROUP BY yf_fail_reason
            ORDER BY count DESC
        """

        return self.db.execute_query(query, (region,))
