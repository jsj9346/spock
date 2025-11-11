"""
Equity fundamentals backfill executor with DART API integration

This executor implements backfill logic for equity fundamental data
(capital_stock, capital_surplus, retained_earnings, etc.) using DART Open API.

Key Features:
- DART API integration for KR market equity data
- Automatic corp_code lookup
- Error handling for missing/invalid data
- Rate limiting compliance
- Database transaction management

Example Usage:
    from modules.db_manager_postgres import PostgresDatabaseManager
    from modules.backfill.equity_executor import EquityBackfillExecutor

    db = PostgresDatabaseManager()
    executor = EquityBackfillExecutor(db, dry_run=False)

    # Single ticker
    ticker_info = TickerGapInfo(
        ticker='005930',
        name='Samsung Electronics',
        region='KR',
        ...
    )
    success = executor.execute_ticker(ticker_info)

Author: Quant Platform Development Team
Date: 2025-11-11
"""

import logging
from typing import Tuple, List, Optional, Dict, Any
from datetime import date

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.backfill.executor_base import BackfillExecutor
from modules.backfill.data_structures import TickerGapInfo
from modules.dart_api_client import DARTApiClient

logger = logging.getLogger(__name__)


class EquityBackfillExecutor(BackfillExecutor):
    """
    Equity fundamentals backfill executor with DART API integration

    Implements backfill logic for ticker_fundamentals table:
    - Retrieves data from DART Open API
    - Extracts equity account fields (capital_stock, capital_surplus, retained_earnings)
    - Updates database with transaction safety
    """

    def __init__(
        self,
        db: PostgresDatabaseManager,
        dry_run: bool = False,
        rate_limit_delay: float = 36.0,
        max_retries: int = 3,
        retry_delay: float = 5.0
    ):
        """
        Initialize EquityBackfillExecutor

        Args:
            db: PostgreSQL database manager instance
            dry_run: If True, preview operations without executing
            rate_limit_delay: Delay between API calls (default: 36s = 100 req/hour)
            max_retries: Maximum retry attempts for failed operations
            retry_delay: Delay between retry attempts in seconds
        """
        super().__init__(
            db=db,
            dry_run=dry_run,
            rate_limit_delay=rate_limit_delay,
            max_retries=max_retries,
            retry_delay=retry_delay
        )

        # Initialize DART API client
        self.dart_client = None  # Lazy initialization in validate_prerequisites()

        logger.debug("EquityBackfillExecutor initialized")

    def validate_prerequisites(self) -> Tuple[bool, List[str]]:
        """
        Validate prerequisites before execution

        Checks:
        1. DART API key availability
        2. DART API client initialization
        3. Database connection
        4. Corp codes file availability

        Returns:
            (준비 완료 여부, 문제점 목록) 튜플
        """
        issues = []

        # Check DART API key
        try:
            self.dart_client = DARTApiClient(rate_limit_delay=self.rate_limit_delay)
            logger.info("✅ DART API client initialized")
        except ValueError as e:
            issues.append(f"DART API key not found: {e}")
            logger.error(f"❌ {issues[-1]}")

        # Check database connection
        try:
            # Simple query to test connection
            test_query = "SELECT 1"
            self.db.execute_query(test_query)
            logger.info("✅ Database connection verified")
        except Exception as e:
            issues.append(f"Database connection failed: {e}")
            logger.error(f"❌ {issues[-1]}")

        # Check corp codes availability
        try:
            if self.dart_client:
                # Try to download/update corp codes
                corp_codes_path = self.dart_client.download_corp_codes()
                corp_codes = self.dart_client.parse_corp_codes(corp_codes_path)
                logger.info(f"✅ Corp codes loaded: {len(corp_codes):,} companies")
        except Exception as e:
            issues.append(f"Corp codes loading failed: {e}")
            logger.warning(f"⚠️  {issues[-1]}")
            # This is a warning, not a critical error

        return (len(issues) == 0, issues)

    def execute_ticker(self, ticker_info: TickerGapInfo) -> bool:
        """
        Execute backfill for single ticker

        Workflow:
        1. Lookup corp_code for ticker
        2. Call DART API to get fundamental metrics
        3. Extract equity account fields
        4. Update database with new data

        Args:
            ticker_info: Ticker information from gap analysis

        Returns:
            True if successful, False otherwise
        """
        ticker = ticker_info.ticker
        name = ticker_info.name

        logger.info(f"처리 중: {ticker} ({name})")

        try:
            # Get fundamental metrics from DART API
            metrics = self.dart_client.get_fundamental_metrics(
                ticker=ticker,
                corp_code=ticker_info.corp_code  # May be None (client will lookup)
            )

            if not metrics:
                logger.warning(f"⚠️  {ticker}: DART API returned no data")
                return False

            # Extract relevant fields
            equity_data = self._extract_equity_fields(metrics)

            if not equity_data:
                logger.warning(f"⚠️  {ticker}: No equity data extracted")
                return False

            # Update database
            success = self._update_database(ticker, ticker_info.region, equity_data)

            if success:
                logger.info(f"✅ {ticker}: Equity data updated successfully")
                self.stats.records_updated += 1
                return True
            else:
                logger.warning(f"⚠️  {ticker}: Database update failed")
                return False

        except Exception as e:
            logger.error(f"❌ {ticker}: Error during backfill - {e}")
            return False

    def _extract_equity_fields(self, metrics: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """
        Extract equity account fields from DART metrics

        Args:
            metrics: Dictionary returned from DART API

        Returns:
            Dictionary with equity fields or None if extraction fails

        Expected metrics keys:
        - capital_stock: 자본금
        - capital_surplus: 자본잉여금
        - retained_earnings: 이익잉여금 (또는 retained_earnings_deficit)
        - treasury_stock: 자기주식
        - accumulated_other_comprehensive_income: 기타포괄손익누계액
        """
        if not metrics:
            return None

        equity_data = {}

        # Map DART field names to database column names
        field_mapping = {
            'capital_stock': 'capital_stock',
            'capital_surplus': 'capital_surplus',
            'retained_earnings': 'retained_earnings',
            'retained_earnings_deficit': 'retained_earnings',  # Alternative name
            'treasury_stock': 'treasury_stock',
            'accumulated_other_comprehensive_income': 'accumulated_other_comprehensive_income'
        }

        # Extract available fields
        for dart_field, db_column in field_mapping.items():
            if dart_field in metrics and metrics[dart_field] is not None:
                # Convert to float if needed
                try:
                    value = float(metrics[dart_field])
                    equity_data[db_column] = value
                except (ValueError, TypeError):
                    logger.warning(f"⚠️  Could not convert {dart_field}={metrics[dart_field]} to float")
                    continue

        # Extract date if available
        if 'date' in metrics:
            equity_data['date'] = metrics['date']
        elif 'report_date' in metrics:
            equity_data['date'] = metrics['report_date']

        return equity_data if equity_data else None

    def _update_database(
        self,
        ticker: str,
        region: str,
        equity_data: Dict[str, Any]
    ) -> bool:
        """
        Update ticker_fundamentals table with equity data

        Uses UPSERT logic (INSERT ... ON CONFLICT UPDATE) to handle
        both new records and updates to existing records.

        Args:
            ticker: Ticker symbol
            region: Market region
            equity_data: Dictionary with equity fields and date

        Returns:
            True if update successful, False otherwise
        """
        try:
            # Extract date from equity_data
            data_date = equity_data.get('date')
            if not data_date:
                # Use latest available date from existing records
                date_query = """
                SELECT MAX(date) as latest_date
                FROM ticker_fundamentals
                WHERE ticker = %(ticker)s AND region = %(region)s
                """
                result = self.db.execute_query(
                    date_query,
                    {'ticker': ticker, 'region': region}
                )
                if result and result[0].get('latest_date'):
                    data_date = result[0]['latest_date']
                else:
                    data_date = date.today()

            # Build UPDATE query with only available fields
            update_fields = []
            params = {
                'ticker': ticker,
                'region': region,
                'date': data_date
            }

            for field in ['capital_stock', 'capital_surplus', 'retained_earnings',
                          'treasury_stock', 'accumulated_other_comprehensive_income']:
                if field in equity_data:
                    update_fields.append(f"{field} = %({field})s")
                    params[field] = equity_data[field]

            if not update_fields:
                logger.warning(f"⚠️  {ticker}: No fields to update")
                return False

            # UPSERT query
            query = f"""
            INSERT INTO ticker_fundamentals (ticker, region, date, {', '.join(params.keys() - {'ticker', 'region', 'date'})})
            VALUES (%(ticker)s, %(region)s, %(date)s, {', '.join([f'%({k})s' for k in params.keys() - {'ticker', 'region', 'date'}])})
            ON CONFLICT (ticker, region, date)
            DO UPDATE SET
                {', '.join(update_fields)},
                updated_at = CURRENT_TIMESTAMP
            """

            self.db.execute_query(query, params)
            return True

        except Exception as e:
            logger.error(f"❌ Database update error for {ticker}: {e}")
            return False
