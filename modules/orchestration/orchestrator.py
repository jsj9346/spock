"""
Database Update Orchestrator

Main orchestrator for unified database update pipeline.
Coordinates execution of all update steps with checkpoint-based recovery.

Author: Quant Investment Platform
Date: 2025-11-01
"""

import os
import sys
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.orchestration.checkpoint import CheckpointManager
from modules.orchestration.rate_limiter import MultiRateLimiter
from modules.orchestration.validators import DataQualityValidator
from modules.api_clients.yfinance_api import YFinanceAPI

# Rich library for progress tracking (optional)
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
    from rich.table import Table
    from rich.panel import Panel
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

logger = logging.getLogger(__name__)


class DatabaseUpdateOrchestrator:
    """
    Database update pipeline orchestrator

    Coordinates execution of all database update steps:
    1. Tickers update (KR + overseas)
    2. OHLCV data collection
    3. Fundamental data backfill
    4. Dividend yield calculation
    5. Quarterly financials (optional)

    Features:
    - Checkpoint-based recovery
    - Rate limiting for API calls
    - Data quality validation
    - Progress tracking and statistics
    - Dry-run and incremental modes

    Usage:
        orchestrator = DatabaseUpdateOrchestrator(db, config={})
        result = orchestrator.run_pipeline(
            regions=['KR', 'US'],
            steps=['tickers', 'ohlcv', 'fundamentals'],
            dry_run=False,
            incremental=True
        )
    """

    # Step execution order
    STEP_ORDER = [
        'tickers',
        'ticker_refresh',      # New: Multi-region ticker refresh with OTC filtering
        'fx_tracking',         # New: Exchange rate tracking and FX signals
        'macro_data',          # New: Global market indices, bonds, commodities, sentiment
        'ohlcv',
        'fundamentals',        # DART annual financial statements
        'daily_valuation',     # New: pykrx daily PER/PBR for valuation trend analysis
        'technical_indicators', # New: MA, RSI, MACD, BB, ATR, Volume indicators
        'classification',      # New: Stock classification (SPAC, preferred, sector/industry)
        'dividend',
        'etf_data',            # New: ETF details and holdings
        'quarterly'
    ]

    def __init__(self, db: PostgresDatabaseManager, config: Optional[Dict] = None):
        """
        Initialize orchestrator

        Args:
            db: PostgreSQL database manager
            config: Configuration dict:
                - fail_fast: Stop on first error (default: False)
                - limit: Limit number of tickers per step (for testing)
                - validate: Enable data quality validation (default: True)
        """
        self.db = db
        self.config = config or {}

        # Initialize components
        self.checkpoint_manager = CheckpointManager()
        self.rate_limiters = self._initialize_rate_limiters()
        self.validator = DataQualityValidator(db)

        # Statistics
        self.stats = {
            'start_time': None,
            'end_time': None,
            'total_duration': 0.0,
            'steps_completed': [],
            'steps_failed': [],
            'step_results': {}
        }

        logger.info("DatabaseUpdateOrchestrator initialized")

    def _initialize_rate_limiters(self) -> MultiRateLimiter:
        """Initialize rate limiters for different APIs"""
        limiters = MultiRateLimiter()

        # KIS API: 20 requests/sec, 1,000 requests/min
        limiters.add('KIS', max_rate=20, time_window=1.0)

        # DART API: ~1 request/sec (safe limit)
        limiters.add('DART', max_rate=1, time_window=1.0)

        # pykrx: No rate limit, but add for consistency
        limiters.add('pykrx', max_rate=100, time_window=1.0)

        logger.info("Rate limiters initialized (KIS: 20/s, DART: 1/s, pykrx: 100/s)")
        return limiters

    def run_pipeline(self,
                     regions: List[str],
                     steps: Optional[List[str]] = None,
                     dry_run: bool = False,
                     incremental: bool = False,
                     resume: bool = False,
                     **kwargs) -> Dict:
        """
        Run database update pipeline

        Args:
            regions: List of regions to update (e.g., ['KR', 'US'])
            steps: List of steps to execute (default: all except 'quarterly')
            dry_run: If True, preview operations without database writes
            incremental: If True, only update missing data
            resume: If True, resume from latest checkpoint
            **kwargs: Additional options passed to step executors

        Returns:
            Dictionary with execution results and statistics
        """
        self.stats['start_time'] = datetime.now()

        # Print header
        self._print_header(regions, steps, dry_run, incremental, resume)

        try:
            # Determine steps to execute
            if steps is None:
                steps = [s for s in self.STEP_ORDER if s != 'quarterly']

            # Resume from checkpoint if requested
            if resume:
                checkpoint = self.checkpoint_manager.load_latest()
                if checkpoint:
                    next_step = checkpoint.get('next_step')
                    if next_step and next_step in steps:
                        start_index = steps.index(next_step)
                        steps = steps[start_index:]
                        logger.info(f"🔄 Resuming from step: {next_step}")
                    else:
                        logger.info("✅ Pipeline already complete")
                        return self.stats

            # Execute pipeline steps with Rich progress tracking (if available)
            if RICH_AVAILABLE and kwargs.get('use_rich_ui', True):
                self._run_steps_with_rich_ui(steps, regions, dry_run, incremental, **kwargs)
            else:
                self._run_steps_basic(steps, regions, dry_run, incremental, **kwargs)

            # Data quality validation
            if self.config.get('validate', True) and not dry_run:
                self._validate_data_quality(regions)

            # Data freshness monitoring (always run - read-only, safe for dry-run)
            if self.config.get('validate', True):
                self._check_data_freshness()

        finally:
            # Finalize statistics
            self.stats['end_time'] = datetime.now()
            self.stats['total_duration'] = (
                self.stats['end_time'] - self.stats['start_time']
            ).total_seconds()

            # Print summary
            self._print_summary()

        return self.stats

    def _execute_step(self, step: str, regions: List[str], **kwargs) -> Dict:
        """
        Execute a single pipeline step with retry logic

        Args:
            step: Step name ('tickers', 'ohlcv', etc.)
            regions: List of regions
            **kwargs: Step-specific options

        Returns:
            Step execution result dict
        """
        # Route to appropriate step executor
        step_executors = {
            'tickers': self._update_tickers,
            'ticker_refresh': self._refresh_tickers,           # New step
            'fx_tracking': self._track_exchange_rates,         # New step
            'macro_data': self._update_macro_data,             # New: Global market data
            'ohlcv': self._update_ohlcv,
            'fundamentals': self._update_fundamentals,
            'daily_valuation': self._update_daily_valuation,   # New: pykrx daily PER/PBR
            'technical_indicators': self._update_technical_indicators, # New: Technical analysis
            'classification': self._classify_stocks,           # New step
            'dividend': self._calculate_dividend,
            'etf_data': self._update_etf_data,                 # New step
            'quarterly': self._update_quarterly_financials
        }

        executor = step_executors.get(step)
        if not executor:
            raise ValueError(f"Unknown step: {step}")

        # Execute step with retry logic
        return self._execute_with_retry(executor, step, regions, **kwargs)

    def _execute_with_retry(self, executor, step: str, regions: List[str],
                           max_retries: int = 3, **kwargs) -> Dict:
        """
        Execute step with exponential backoff retry logic

        Args:
            executor: Step executor function
            step: Step name (for logging)
            regions: List of regions
            max_retries: Maximum number of retry attempts (default: 3)
            **kwargs: Step-specific options

        Returns:
            Step execution result dict

        Raises:
            Exception: If all retry attempts fail
        """
        retry_delay = 5  # Initial delay in seconds

        for attempt in range(max_retries):
            try:
                # Execute step
                result = executor(regions, **kwargs)

                # Check if result indicates failure
                if isinstance(result, dict) and not result.get('success', True):
                    # If this is the last attempt, return the failed result
                    if attempt == max_retries - 1:
                        logger.warning(f"⚠️  Step '{step}' failed after {max_retries} attempts")
                        return result

                    # Otherwise, retry
                    logger.warning(
                        f"⚠️  Step '{step}' attempt {attempt + 1}/{max_retries} failed, "
                        f"retrying in {retry_delay}s..."
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue

                # Success
                if attempt > 0:
                    logger.info(f"✅ Step '{step}' succeeded on attempt {attempt + 1}")
                return result

            except Exception as e:
                # If this is the last attempt, raise the exception
                if attempt == max_retries - 1:
                    logger.error(f"❌ Step '{step}' failed after {max_retries} attempts: {e}")
                    raise

                # Otherwise, log and retry
                logger.warning(
                    f"⚠️  Step '{step}' attempt {attempt + 1}/{max_retries} raised exception: {e}"
                )
                logger.warning(f"   Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff

        # This should never be reached, but just in case
        raise RuntimeError(f"Unexpected retry loop exit for step '{step}'")

    def _update_tickers(self, regions: List[str], **kwargs) -> Dict:
        """Update ticker tables for all regions"""
        logger.info("🔄 Updating tickers...")

        results = {}

        for region in regions:
            if region == 'KR':
                # KR: Use pykrx ticker updater
                try:
                    from scripts.update_kr_tickers import KRTickerUpdater

                    updater = KRTickerUpdater(
                        self.db,
                        dry_run=kwargs.get('dry_run', False)
                    )

                    result = updater.run_update(
                        incremental=kwargs.get('incremental', True)
                    )

                    results[region] = result
                    logger.info(
                        f"  ✅ [{region}] {result.get('total_current', 0)} tickers "
                        f"({result.get('new_listings', 0)} new, {result.get('name_changes', 0)} changed) "
                        f"in {result.get('duration', 0):.2f}s"
                    )

                except Exception as e:
                    logger.error(f"  ❌ [{region}] Failed: {e}")
                    results[region] = {'success': False, 'error': str(e)}

            else:
                # Overseas: Use KIS API master files
                try:
                    from scripts.update_master_files import update_region

                    result = update_region(
                        region,
                        force_refresh=True,
                        dry_run=kwargs.get('dry_run', False)
                    )

                    results[region] = result
                    logger.info(
                        f"  ✅ [{region}] {result.get('ticker_count', 0)} tickers "
                        f"in {result.get('duration', 0):.2f}s"
                    )

                except Exception as e:
                    logger.error(f"  ❌ [{region}] Failed: {e}")
                    results[region] = {'success': False, 'error': str(e)}

        return results

    def _update_ohlcv(self, regions: List[str], **kwargs) -> Dict:
        """Update OHLCV data for all regions"""
        logger.info("🔄 Updating OHLCV data...")

        results = {}

        for region in regions:
            try:
                if region == 'KR':
                    # Use KR PostgreSQL OHLCV adapter (direct PostgreSQL integration)
                    from modules.collection.kr_postgres_ohlcv_adapter import KRPostgresOHLCVAdapter

                    adapter = KRPostgresOHLCVAdapter(
                        db=self.db,
                        config={
                            'dry_run': kwargs.get('dry_run', False),
                            'rate_limit': 0.05,  # 20 req/s
                            'batch_size': 1000,
                            'validation_threshold': 0.7
                        }
                    )

                    result = adapter.run_collection(
                        incremental=kwargs.get('incremental', True),
                        limit=self.config.get('limit'),
                        days=kwargs.get('days', 250),
                        force_refresh=kwargs.get('force_refresh', False),
                        stale_days=kwargs.get('stale_days', 7)
                    )

                    results[region] = result
                    logger.info(
                        f"  ✅ [{region}] {result.get('tickers_collected', 0)} tickers collected "
                        f"in {result.get('duration', 0):.2f}s"
                    )

                else:
                    # Overseas markets - use yfinance
                    result = self._update_ohlcv_overseas(region, **kwargs)
                    results[region] = result

                    if result.get('success'):
                        logger.info(
                            f"  ✅ [{region}] {result.get('tickers_collected', 0)} tickers collected "
                            f"in {result.get('duration', 0):.2f}s"
                        )

            except Exception as e:
                logger.error(f"  ❌ [{region}] Failed: {e}")
                results[region] = {'success': False, 'error': str(e)}

        return results

    def _update_ohlcv_overseas(self, region: str, **kwargs) -> Dict:
        """
        Update OHLCV data for overseas markets using yfinance with smart incremental updates

        Args:
            region: Region code (US, HK, JP, CN, VN)
            **kwargs: Additional arguments
                - dry_run: Preview only, no DB writes
                - incremental: Only update missing data
                - force_refresh: Force update all tickers
                - stale_days: Days threshold for stale data (default: 7)
                - limit: Maximum number of tickers to process

        Returns:
            Result dict with success status and statistics
        """
        from datetime import datetime, timedelta

        dry_run = kwargs.get('dry_run', False)
        incremental = kwargs.get('incremental', True)
        force_refresh = kwargs.get('force_refresh', False)
        stale_days = kwargs.get('stale_days', 7)
        limit = self.config.get('limit')

        mode_str = 'FORCE REFRESH' if force_refresh else ('INCREMENTAL' if incremental else 'FULL REFRESH')
        logger.info(f"  [{region}] Collecting OHLCV using yfinance ({mode_str})...")

        start_time = time.time()
        stats = {
            'tickers_processed': 0,
            'tickers_collected': 0,
            'tickers_failed': 0,
            'records_inserted': 0,
            'success': True
        }

        try:
            # Initialize yfinance API
            yf_api = YFinanceAPI(rate_limit_per_second=1.0)

            # Get ticker list from database with smart incremental logic
            if incremental and not force_refresh:
                # Smart incremental - tickers with no data or stale data (>=stale_days)
                query = f"""
                WITH latest_data AS (
                    SELECT
                        ticker,
                        MAX(date) as last_date
                    FROM ohlcv_data
                    WHERE region = %s
                    GROUP BY ticker
                )
                SELECT
                    t.ticker,
                    t.name,
                    t.region,
                    CASE WHEN ld.last_date IS NULL THEN 0 ELSE 1 END as has_data,
                    ld.last_date
                FROM tickers t
                LEFT JOIN latest_data ld ON t.ticker = ld.ticker
                WHERE t.region = %s
                  AND t.asset_type = 'STOCK'
                  AND t.is_active = TRUE
                  AND (
                      ld.last_date IS NULL  -- No data at all
                      OR ld.last_date <= CURRENT_DATE - INTERVAL '{stale_days} days'  -- Stale data (>= stale_days old)
                  )
                ORDER BY
                    has_data ASC,  -- No data first (0 before 1)
                    ld.last_date ASC NULLS FIRST  -- Oldest data next
                """
                params = (region, region)
            else:
                # All active tickers (full refresh or force refresh)
                query = """
                SELECT ticker, name, region
                FROM tickers
                WHERE region = %s
                  AND asset_type = 'STOCK'
                  AND is_active = TRUE
                ORDER BY ticker
                """
                params = (region,)

            if limit:
                query += f" LIMIT {limit}"

            tickers = self.db.execute_query(query, params)
            ticker_list = [dict(row) for row in tickers]

            if not ticker_list:
                logger.info(f"  [{region}] No tickers to update")
                stats['success'] = True
                return stats

            # Count categories for logging (only in incremental mode)
            if incremental and not force_refresh:
                no_data_query = """
                SELECT COUNT(DISTINCT t.ticker) as count
                FROM tickers t
                LEFT JOIN ohlcv_data o ON t.ticker = o.ticker AND t.region = o.region
                WHERE t.region = %s
                  AND t.asset_type = 'STOCK'
                  AND t.is_active = TRUE
                  AND o.ticker IS NULL
                """
                no_data_count = self.db.execute_query(no_data_query, (region,))[0]['count']

                stale_data_query = f"""
                WITH latest_data AS (
                    SELECT ticker, MAX(date) as last_date
                    FROM ohlcv_data
                    WHERE region = %s
                    GROUP BY ticker
                )
                SELECT COUNT(DISTINCT t.ticker) as count
                FROM tickers t
                INNER JOIN latest_data ld ON t.ticker = ld.ticker
                WHERE t.region = %s
                  AND t.asset_type = 'STOCK'
                  AND t.is_active = TRUE
                  AND ld.last_date <= CURRENT_DATE - INTERVAL '{stale_days} days'
                """
                stale_count = self.db.execute_query(stale_data_query, (region, region))[0]['count']

                logger.info(f"  [{region}] Found {len(ticker_list)} tickers to update")
                logger.info(f"     - No data: {no_data_count} tickers")
                logger.info(f"     - Stale data (>{stale_days} days): {stale_count} tickers")
            else:
                logger.info(f"  [{region}] Found {len(ticker_list)} tickers to update")

            # Collect OHLCV data for each ticker
            for i, ticker_info in enumerate(ticker_list, 1):
                ticker = ticker_info['ticker']
                stats['tickers_processed'] += 1

                try:
                    # Map ticker to yfinance format
                    yf_symbol = self._map_ticker_to_yfinance(ticker, region)

                    # Fetch OHLCV data (last 1 year)
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=365)

                    df = yf_api.get_ohlcv(
                        ticker=yf_symbol,
                        start_date=start_date.strftime('%Y-%m-%d'),
                        end_date=end_date.strftime('%Y-%m-%d')
                    )

                    if df is None or df.empty:
                        logger.debug(f"  ⚠️ [{region}:{ticker}] No OHLCV data available")
                        stats['tickers_failed'] += 1
                        continue

                    # Insert into database
                    if not dry_run:
                        for _, row in df.iterrows():
                            self.db.execute_update(
                                """
                                INSERT INTO ohlcv_data
                                (ticker, region, date, open, high, low, close, volume, timeframe)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, '1d')
                                ON CONFLICT (ticker, region, date, timeframe)
                                DO UPDATE SET
                                    open = EXCLUDED.open,
                                    high = EXCLUDED.high,
                                    low = EXCLUDED.low,
                                    close = EXCLUDED.close,
                                    volume = EXCLUDED.volume,
                                    last_updated = NOW()
                                WHERE
                                    ohlcv_data.open IS DISTINCT FROM EXCLUDED.open OR
                                    ohlcv_data.high IS DISTINCT FROM EXCLUDED.high OR
                                    ohlcv_data.low IS DISTINCT FROM EXCLUDED.low OR
                                    ohlcv_data.close IS DISTINCT FROM EXCLUDED.close OR
                                    ohlcv_data.volume IS DISTINCT FROM EXCLUDED.volume
                                """,
                                (
                                    ticker,
                                    region,
                                    row['date'],
                                    float(row['open']),
                                    float(row['high']),
                                    float(row['low']),
                                    float(row['close']),
                                    int(row['volume'])
                                )
                            )
                        stats['records_inserted'] += len(df)

                    stats['tickers_collected'] += 1

                    if i % 10 == 0:
                        logger.info(
                            f"  [{region}] Progress: {i}/{len(ticker_list)} "
                            f"({stats['tickers_collected']} success, {stats['tickers_failed']} failed)"
                        )

                except Exception as e:
                    logger.warning(f"  ⚠️ [{region}:{ticker}] Failed: {e}")
                    stats['tickers_failed'] += 1
                    continue

            stats['duration'] = time.time() - start_time
            stats['success'] = True

            logger.info(
                f"  ✅ [{region}] OHLCV collection completed: "
                f"{stats['tickers_collected']} success, {stats['tickers_failed']} failed, "
                f"{stats['records_inserted']} records in {stats['duration']:.2f}s"
            )

            return stats

        except Exception as e:
            logger.error(f"  ❌ [{region}] OHLCV collection failed: {e}")
            stats['success'] = False
            stats['error'] = str(e)
            return stats

    def _map_ticker_to_yfinance(self, ticker: str, region: str) -> str:
        """
        Map database ticker to yfinance symbol format

        Args:
            ticker: Database ticker code
            region: Region code

        Returns:
            yfinance-compatible symbol
        """
        # Ticker suffix mapping
        suffixes = {
            'US': '',       # No suffix
            'JP': '.T',     # Tokyo Stock Exchange
            'HK': '.HK',    # Hong Kong Stock Exchange
            'CN': '',       # Already has .SS or .SZ suffix
            'VN': '.VN'     # Vietnam Stock Exchange
        }

        # HK and CN already have suffixes in database
        if region in ['HK', 'CN']:
            return ticker

        # US has no suffix
        if region == 'US':
            return ticker

        # JP and VN need suffix appended
        suffix = suffixes.get(region, '')
        return f"{ticker}{suffix}"

    def _update_macro_data(self, regions: List[str], **kwargs) -> Dict:
        """
        Update macro economic data (global market indices, bonds, commodities, sentiment)

        Args:
            regions: List of regions (not region-specific, but kept for API consistency)
            **kwargs: Additional options:
                - dry_run: Preview without database writes
                - incremental: Update only recent data (default: True)
                - days: Number of days to update (default: 30)
                - components: List of components to update (default: ['indices', 'bonds'])

        Returns:
            Dictionary with execution results
        """
        logger.info("🔄 Updating macro economic data...")

        try:
            from modules.collection.macro_data_adapter import MacroDataAdapter

            # Initialize adapter
            adapter = MacroDataAdapter(
                db=self.db,
                config={
                    'dry_run': kwargs.get('dry_run', False)
                }
            )

            # Run collection
            components = kwargs.get('components', ['indices', 'bonds'])
            days = kwargs.get('days', 30)

            result = adapter.run_collection(
                components=components,
                days=days
            )

            # Extract statistics
            total_records = (
                result.get('indices_records', 0) +
                result.get('bonds_records', 0) +
                result.get('commodities_records', 0) +
                result.get('sentiment_records', 0)
            )

            total_success = (
                result.get('indices_success', 0) +
                result.get('bonds_success', 0) +
                result.get('commodities_success', 0) +
                result.get('sentiment_success', 0)
            )

            total_processed = (
                result.get('indices_processed', 0) +
                result.get('bonds_processed', 0) +
                result.get('commodities_processed', 0) +
                result.get('sentiment_processed', 0)
            )

            logger.info(
                f"  ✅ Macro data updated: {total_success}/{total_processed} sources "
                f"({total_records} records) in {result.get('duration', 0):.2f}s"
            )

            return {
                'success': total_success == total_processed and total_processed > 0,
                'total_records': total_records,
                'components': components,
                'duration': result.get('duration', 0)
            }

        except Exception as e:
            logger.error(f"  ❌ Macro data update failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _update_fundamentals(self, regions: List[str], **kwargs) -> Dict:
        """Update fundamental data for all regions"""
        logger.info("🔄 Updating fundamental data...")

        results = {}

        for region in regions:
            if region == 'KR':
                try:
                    # Use DART API for KR market
                    from scripts.backfill_fundamentals_dart import DARTFundamentalBackfiller
                    from modules.dart_api_client import DARTApiClient

                    dart_api_key = os.getenv('DART_API_KEY')
                    if not dart_api_key:
                        logger.error(f"  ❌ [{region}] DART_API_KEY not found")
                        results[region] = {
                            'success': False,
                            'error': 'DART_API_KEY not configured'
                        }
                        continue

                    # Initialize DART backfiller
                    # Rate limit: 3.6s/request = 1000 req/hour (DART limit: 1000 req/day)
                    dart = DARTApiClient(api_key=dart_api_key, rate_limit_delay=3.6)
                    backfiller = DARTFundamentalBackfiller(
                        self.db, dart,
                        dry_run=kwargs.get('dry_run', False),
                        rate_limit_delay=1.0
                    )

                    # Run backfill
                    result = backfiller.run_backfill(
                        incremental=kwargs.get('incremental', True),
                        limit=self.config.get('limit')
                    )

                    results[region] = result

                    logger.info(
                        f"  ✅ [{region}] {result['tickers_success']} success, "
                        f"{result['tickers_failed']} failed"
                    )

                except Exception as e:
                    logger.error(f"  ❌ [{region}] Failed: {e}")
                    results[region] = {'success': False, 'error': str(e)}

            else:
                # Use yfinance for overseas markets
                try:
                    from scripts.backfill_fundamentals_yfinance import YFinanceFundamentalBackfiller

                    backfiller = YFinanceFundamentalBackfiller(
                        self.db,
                        dry_run=kwargs.get('dry_run', False),
                        rate_limit_delay=0.5  # 2 requests/second
                    )

                    # Run backfill for specific region
                    result = backfiller.run_backfill(
                        region=region,
                        incremental=kwargs.get('incremental', True),
                        limit=self.config.get('limit')
                    )

                    results[region] = result

                    logger.info(
                        f"  ✅ [{region}] {result.get('success', 0)} success, "
                        f"{result.get('failed', 0)} failed"
                    )

                except Exception as e:
                    logger.error(f"  ❌ [{region}] Failed: {e}")
                    results[region] = {'success': False, 'error': str(e)}

        return results

    def _calculate_dividend(self, regions: List[str], **kwargs) -> Dict:
        """Calculate dividend yield for all regions"""
        logger.info("🔄 Calculating dividend yield...")

        results = {}

        for region in regions:
            if region == 'KR':
                try:
                    # Use dividend yield calculator for KR market
                    from scripts.calculate_dividend_yield import DividendYieldCalculator

                    calculator = DividendYieldCalculator(
                        self.db,
                        dry_run=kwargs.get('dry_run', False)
                    )

                    result = calculator.calculate_all_tickers()

                    results[region] = result

                    logger.info(
                        f"  ✅ [{region}] {result.get('tickers_success', 0)} tickers calculated"
                    )

                except Exception as e:
                    logger.error(f"  ❌ [{region}] Failed: {e}")
                    results[region] = {'success': False, 'error': str(e)}

            else:
                # Overseas dividend calculation not implemented
                logger.info(f"  [{region}] Overseas dividend calculation not implemented")
                results[region] = {
                    'success': False,
                    'message': 'Overseas dividend calculation not implemented'
                }

        return results

    def _update_quarterly_financials(self, regions: List[str], **kwargs) -> Dict:
        """Update quarterly financial statements (KR only, optional)"""
        logger.info("🔄 Updating quarterly financials...")

        results = {}

        for region in regions:
            if region == 'KR':
                logger.warning(f"  ⚠️ [{region}] Quarterly financials updater not yet implemented")
                results[region] = {
                    'success': False,
                    'message': 'Quarterly financials updater not implemented'
                }
            else:
                # Not applicable for overseas markets
                results[region] = {
                    'success': True,
                    'message': 'Not applicable for overseas markets'
                }

        return results

    def _update_daily_valuation(self, regions: List[str], **kwargs) -> Dict:
        """
        Update daily valuation multiples (PER, PBR) from pykrx

        Purpose: Enable historical valuation multiple trend analysis
        Data Source: pykrx (KRX market data)
        Update Frequency: Daily
        """
        logger.info("🔄 Updating daily valuation multiples (PER, PBR)...")

        results = {}

        for region in regions:
            if region == 'KR':
                try:
                    from scripts.backfill_fundamentals_pykrx import PyKRXFundamentalBackfiller
                    from datetime import date, timedelta

                    # Initialize backfiller
                    backfiller = PyKRXFundamentalBackfiller(
                        self.db,
                        dry_run=kwargs.get('dry_run', False),
                        rate_limit_delay=0.5  # 2 requests/second
                    )

                    # Determine date range
                    end_date = date.today()
                    if kwargs.get('incremental', True):
                        # Incremental: Last 7 days to catch up
                        start_date = end_date - timedelta(days=7)
                    else:
                        # Full: Last 30 days
                        start_date = end_date - timedelta(days=30)

                    # Run backfill
                    logger.info(f"  → Date range: {start_date} to {end_date}")
                    stats = backfiller.run_backfill(
                        start_date=start_date,
                        end_date=end_date,
                        incremental=kwargs.get('incremental', True),
                        limit=self.config.get('limit')
                    )

                    results[region] = stats

                    logger.info(
                        f"  ✅ [{region}] {stats['tickers_success']} tickers, "
                        f"{stats['dates_processed']} dates, "
                        f"{stats['records_inserted']} inserted, "
                        f"{stats['records_updated']} updated"
                    )

                except Exception as e:
                    import traceback
                    logger.error(f"  ❌ [{region}] Daily valuation update failed: {e}")
                    logger.error(f"  Traceback: {traceback.format_exc()}")
                    results[region] = {'success': False, 'error': str(e)}

            else:
                # Overseas markets: Daily valuation already handled by yfinance
                logger.info(f"  [{region}] Daily valuation handled by yfinance fundamentals step")
                results[region] = {
                    'success': True,
                    'message': 'Handled by yfinance in fundamentals step'
                }

        return results

    def _update_technical_indicators(self, regions: List[str], **kwargs) -> Dict:
        """
        Update technical indicators (MA, RSI, MACD, Bollinger Bands, ATR, Volume)

        Purpose: Calculate technical analysis indicators for trading strategies
        Indicators: MA(5,20,50,100,200), RSI-14, MACD, BB, ATR, Volume ratios
        Storage: Updates ohlcv_data table columns
        """
        logger.info("🔄 Updating technical indicators...")

        results = {}

        for region in regions:
            if region == 'KR':
                try:
                    logger.info(f"  [{region}] Calculating technical indicators from ohlcv_data...")

                    # Get list of tickers
                    query = """
                    SELECT DISTINCT ticker
                    FROM tickers
                    WHERE region = %s AND asset_type = 'STOCK' AND is_active = TRUE
                    ORDER BY ticker
                    """
                    if self.config.get('limit'):
                        query += f" LIMIT {self.config.get('limit')}"

                    tickers = self.db.execute_query(query, (region,))

                    if not tickers:
                        logger.warning(f"  ⚠️ [{region}] No tickers found")
                        results[region] = {'success': False, 'message': 'No tickers found'}
                        continue

                    # Calculate indicators for each ticker
                    success_count = 0
                    failed_count = 0

                    for ticker_row in tickers:
                        ticker = ticker_row['ticker']

                        try:
                            # Get OHLCV data (last 250 days for MA200)
                            ohlcv_query = """
                            SELECT date, open, high, low, close, volume
                            FROM ohlcv_data
                            WHERE ticker = %s AND region = %s
                            ORDER BY date DESC
                            LIMIT 250
                            """
                            ohlcv = self.db.execute_query(ohlcv_query, (ticker, region))

                            if len(ohlcv) < 20:
                                logger.debug(f"  [{ticker}] Insufficient data ({len(ohlcv)} days)")
                                failed_count += 1
                                continue

                            # Convert to DataFrame
                            import pandas as pd
                            df = pd.DataFrame(ohlcv)
                            df = df.sort_values('date')  # Ascending for calculation

                            # Calculate using pandas_ta
                            try:
                                import pandas_ta as ta

                                # Moving Averages
                                df['ma5'] = ta.sma(df['close'], length=5)
                                df['ma20'] = ta.sma(df['close'], length=20)
                                df['ma50'] = ta.sma(df['close'], length=50)
                                df['ma100'] = ta.sma(df['close'], length=100)
                                df['ma200'] = ta.sma(df['close'], length=200)

                                # RSI
                                df['rsi_14'] = ta.rsi(df['close'], length=14)

                                # MACD
                                macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
                                if macd is not None and not macd.empty:
                                    df['macd'] = macd['MACD_12_26_9']
                                    df['macd_signal'] = macd['MACDs_12_26_9']
                                    df['macd_hist'] = macd['MACDh_12_26_9']

                                # Bollinger Bands
                                bbands = ta.bbands(df['close'], length=20, std=2)
                                if bbands is not None and not bbands.empty:
                                    df['bb_upper'] = bbands['BBU_20_2.0']
                                    df['bb_middle'] = bbands['BBM_20_2.0']
                                    df['bb_lower'] = bbands['BBL_20_2.0']

                                # ATR
                                df['atr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)

                                # Volume indicators
                                df['volume_ma20'] = ta.sma(df['volume'], length=20)
                                df['volume_ratio'] = df['volume'] / df['volume_ma20']

                                # Update latest row only (most recent date)
                                if not kwargs.get('dry_run', False):
                                    latest = df.iloc[-1]

                                    update_query = """
                                    UPDATE ohlcv_data
                                    SET
                                        ma5 = %s, ma20 = %s, ma50 = %s, ma100 = %s, ma200 = %s,
                                        rsi_14 = %s,
                                        macd = %s, macd_signal = %s, macd_hist = %s,
                                        bb_upper = %s, bb_middle = %s, bb_lower = %s,
                                        atr_14 = %s,
                                        volume_ma20 = %s, volume_ratio = %s,
                                        last_updated = NOW()
                                    WHERE ticker = %s AND region = %s AND date = %s
                                    AND (
                                        ma5 IS DISTINCT FROM %s OR
                                        ma20 IS DISTINCT FROM %s OR
                                        ma50 IS DISTINCT FROM %s OR
                                        ma100 IS DISTINCT FROM %s OR
                                        ma200 IS DISTINCT FROM %s OR
                                        rsi_14 IS DISTINCT FROM %s OR
                                        macd IS DISTINCT FROM %s OR
                                        macd_signal IS DISTINCT FROM %s OR
                                        macd_hist IS DISTINCT FROM %s OR
                                        bb_upper IS DISTINCT FROM %s OR
                                        bb_middle IS DISTINCT FROM %s OR
                                        bb_lower IS DISTINCT FROM %s OR
                                        atr_14 IS DISTINCT FROM %s OR
                                        volume_ma20 IS DISTINCT FROM %s OR
                                        volume_ratio IS DISTINCT FROM %s
                                    )
                                    """

                                    params = (
                                        # SET clause values (15)
                                        latest.get('ma5'), latest.get('ma20'), latest.get('ma50'),
                                        latest.get('ma100'), latest.get('ma200'),
                                        latest.get('rsi_14'),
                                        latest.get('macd'), latest.get('macd_signal'), latest.get('macd_hist'),
                                        latest.get('bb_upper'), latest.get('bb_middle'), latest.get('bb_lower'),
                                        latest.get('atr_14'),
                                        latest.get('volume_ma20'), latest.get('volume_ratio'),
                                        # WHERE identifiers (3)
                                        ticker, region, latest['date'],
                                        # WHERE comparison values (15) - same as SET values
                                        latest.get('ma5'), latest.get('ma20'), latest.get('ma50'),
                                        latest.get('ma100'), latest.get('ma200'),
                                        latest.get('rsi_14'),
                                        latest.get('macd'), latest.get('macd_signal'), latest.get('macd_hist'),
                                        latest.get('bb_upper'), latest.get('bb_middle'), latest.get('bb_lower'),
                                        latest.get('atr_14'),
                                        latest.get('volume_ma20'), latest.get('volume_ratio')
                                    )

                                    self.db.execute_update(update_query, params)

                                success_count += 1
                                logger.debug(f"  ✅ [{ticker}] Indicators calculated")

                            except ImportError:
                                logger.error(f"  ❌ pandas_ta not installed - pip install pandas-ta")
                                failed_count += 1
                                break

                        except Exception as e:
                            logger.debug(f"  ❌ [{ticker}] Failed: {e}")
                            failed_count += 1
                            continue

                    results[region] = {
                        'success': True,
                        'tickers_success': success_count,
                        'tickers_failed': failed_count,
                        'total_tickers': len(tickers)
                    }

                    logger.info(
                        f"  ✅ [{region}] {success_count} tickers calculated, "
                        f"{failed_count} failed"
                    )

                except Exception as e:
                    import traceback
                    logger.error(f"  ❌ [{region}] Technical indicators failed: {e}")
                    logger.error(f"  Traceback: {traceback.format_exc()}")
                    results[region] = {'success': False, 'error': str(e)}

            elif region == 'HK':
                # HK market: Use existing script if available
                logger.info(f"  [{region}] Using HK technical indicators script...")
                try:
                    # Placeholder for HK script integration
                    results[region] = {
                        'success': False,
                        'message': 'HK technical indicators script integration pending'
                    }
                except Exception as e:
                    logger.error(f"  ❌ [{region}] Failed: {e}")
                    results[region] = {'success': False, 'error': str(e)}

            else:
                logger.info(f"  [{region}] Technical indicators not yet implemented")
                results[region] = {
                    'success': False,
                    'message': 'Not implemented for this region'
                }

        return results

    def _validate_data_quality(self, regions: List[str]) -> None:
        """Validate data quality after pipeline execution"""
        logger.info(f"\n{'='*80}")
        logger.info("Data Quality Validation")
        logger.info(f"{'='*80}")

        validation_results = self.validator.validate_pipeline_output(regions)

        # Store in stats
        self.stats['validation'] = validation_results

    def _check_data_freshness(self) -> None:
        """
        Check data freshness across all data sources

        This is a read-only operation, safe to run in dry-run mode.
        Monitors OHLCV data, macro data (indices, bonds), and fundamentals.
        """
        try:
            from modules.monitoring.data_freshness import DataFreshnessMonitor

            monitor = DataFreshnessMonitor(db=self.db)
            freshness_results = monitor.run_full_check(verbose=True)

            # Store freshness results in stats
            self.stats['freshness'] = freshness_results

            # Log summary
            summary = freshness_results.get('summary', {})
            if summary.get('criticals', 0) > 0:
                logger.warning(
                    f"⚠️  Data freshness: {summary['criticals']} critical issues detected"
                )
            elif summary.get('warnings', 0) > 0:
                logger.info(
                    f"ℹ️  Data freshness: {summary['warnings']} warnings detected"
                )
            else:
                logger.info("✅ Data freshness: All data sources are fresh")

        except Exception as e:
            logger.warning(f"⚠️  Data freshness check failed: {e}")

    def _print_header(self, regions, steps, dry_run, incremental, resume):
        """Print pipeline header"""
        print("\n" + "="*80)
        print("📊 Database Update Pipeline - Quant Investment Platform")
        print("="*80)
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Regions: {', '.join(regions)}")
        print(f"Steps: {', '.join(steps or self.STEP_ORDER)}")
        print(f"Mode: {'DRY RUN' if dry_run else 'INCREMENTAL' if incremental else 'FULL UPDATE'}")
        if resume:
            print("Resume: Yes")
        print("="*80 + "\n")

    def _print_summary(self):
        """Print execution summary"""
        print("\n" + "="*80)
        print("📊 Execution Summary")
        print("="*80)

        # Steps completed
        if self.stats['steps_completed']:
            print(f"✅ Steps completed: {', '.join(self.stats['steps_completed'])}")

        # Steps failed
        if self.stats['steps_failed']:
            print(f"❌ Steps failed: {', '.join(self.stats['steps_failed'])}")

        # Duration
        duration = self.stats['total_duration']
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        print(f"⏱️  Total duration: {minutes}m {seconds}s")

        # Validation results
        if 'validation' in self.stats:
            validation = self.stats['validation']
            passed = sum(1 for v in validation.values() if v.get('passed', False))
            total = len(validation)
            print(f"🔍 Validation: {passed}/{total} regions passed")

        # End time
        print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80 + "\n")

    # ========================================================================
    # New Step Executors (Phase 1 Week 1)
    # ========================================================================

    def _refresh_tickers(self, regions: List[str], **kwargs) -> Dict:
        """
        Refresh tickers using new TickerRefresher system

        Args:
            regions: List of regions to refresh
            **kwargs: Additional options (dry_run, incremental)

        Returns:
            Refresh results dict
        """
        logger.info("🔄 Refreshing tickers (new system)...")

        results = {}

        for region in regions:
            try:
                from modules.ticker_refresh.ticker_refresher import TickerRefresher

                refresher = TickerRefresher(db_manager=self.db)

                result = refresher.refresh_region(
                    region,
                    incremental=kwargs.get('incremental', True)
                )

                results[region] = result
                logger.info(
                    f"  ✅ [{region}] {result.get('new', 0)} new, "
                    f"{result.get('updated', 0)} updated, "
                    f"{result.get('delisted', 0)} delisted"
                )

            except Exception as e:
                logger.error(f"  ❌ [{region}] Failed: {e}")
                results[region] = {'success': False, 'error': str(e)}

        return results

    def _track_exchange_rates(self, regions: List[str], **kwargs) -> Dict:
        """
        Track exchange rates for base currency conversions

        Args:
            regions: List of regions (used to determine currencies)
            **kwargs: Additional options (dry_run)

        Returns:
            FX tracking results dict
        """
        logger.info("🔄 Tracking exchange rates...")

        try:
            from modules.fx_tracking.fx_tracker import FXTracker

            tracker = FXTracker(db_manager=self.db)

            # Determine currencies based on regions
            currencies = self._get_currencies_for_regions(regions)

            result = tracker.update_exchange_rates(
                currencies=currencies,
                dry_run=kwargs.get('dry_run', False)
            )

            logger.info(
                f"  ✅ Updated {result.get('updated', 0)} exchange rates, "
                f"calculated {result.get('signals', 0)} FX signals"
            )

            return result

        except Exception as e:
            logger.error(f"  ❌ FX tracking failed: {e}")
            return {'success': False, 'error': str(e)}

    def _classify_stocks(self, regions: List[str], **kwargs) -> Dict:
        """
        Classify stocks by sector/industry and detect SPAC/preferred stocks

        Args:
            regions: List of regions to classify
            **kwargs: Additional options (dry_run, limit)

        Returns:
            Classification results dict
        """
        logger.info("🔄 Classifying stocks...")

        results = {}

        for region in regions:
            try:
                from modules.classification.stock_classifier import StockClassifier

                classifier = StockClassifier(db_manager=self.db)

                result = classifier.classify_region(
                    region,
                    limit=self.config.get('limit')
                )

                results[region] = result
                logger.info(
                    f"  ✅ [{region}] Classified {result.get('classified', 0)} stocks, "
                    f"detected {result.get('spac_count', 0)} SPACs, "
                    f"{result.get('preferred_count', 0)} preferred stocks"
                )

            except Exception as e:
                logger.error(f"  ❌ [{region}] Failed: {e}")
                results[region] = {'success': False, 'error': str(e)}

        return results

    def _update_etf_data(self, regions: List[str], **kwargs) -> Dict:
        """
        Update ETF details and holdings

        Args:
            regions: List of regions to update
            **kwargs: Additional options (dry_run, incremental)

        Returns:
            ETF update results dict
        """
        logger.info("🔄 Updating ETF data...")

        results = {}

        for region in regions:
            try:
                from modules.etf_update.etf_updater import ETFUpdater

                updater = ETFUpdater(db_manager=self.db)

                result = updater.update_region(
                    region,
                    incremental=kwargs.get('incremental', True),
                    update_holdings=True
                )

                results[region] = result
                logger.info(
                    f"  ✅ [{region}] Updated {result.get('etf_count', 0)} ETFs, "
                    f"{result.get('holdings_updated', 0)} holdings"
                )

            except Exception as e:
                logger.error(f"  ❌ [{region}] Failed: {e}")
                results[region] = {'success': False, 'error': str(e)}

        return results

    def _get_currencies_for_regions(self, regions: List[str]) -> List[str]:
        """
        Get currencies to track based on regions

        Args:
            regions: List of region codes

        Returns:
            List of currency codes
        """
        region_to_currency = {
            'KR': ['USD', 'JPY', 'CNY', 'EUR', 'HKD'],  # ✅ HKD 추가
            'US': ['KRW', 'JPY', 'CNY', 'EUR', 'GBP'],
            'JP': ['USD', 'KRW', 'CNY', 'EUR'],
            'CN': ['USD', 'KRW', 'JPY', 'EUR', 'HKD'],  # ✅ HKD 추가
            'HK': ['USD', 'KRW', 'JPY', 'CNY', 'HKD'],  # ✅ HKD 추가 (자국 통화)
            'VN': ['USD', 'KRW', 'JPY', 'CNY']
        }

        currencies = set()
        for region in regions:
            currencies.update(region_to_currency.get(region, ['USD', 'EUR', 'JPY']))

        return list(currencies)

    # ========================================================================
    # Progress Tracking Methods (Rich UI)
    # ========================================================================

    def _run_steps_with_rich_ui(self, steps: List[str], regions: List[str],
                                dry_run: bool, incremental: bool, **kwargs):
        """
        Execute pipeline steps with Rich progress tracking UI

        Args:
            steps: List of steps to execute
            regions: List of regions
            dry_run: Dry-run mode flag
            incremental: Incremental mode flag
            **kwargs: Additional options
        """
        console = Console()

        # Create progress display
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console
        ) as progress:

            overall_task = progress.add_task(
                f"[cyan]Database Update Pipeline ({len(steps)} steps)",
                total=len(steps)
            )

            for idx, step in enumerate(steps, 1):
                # Update task description
                progress.update(
                    overall_task,
                    description=f"[cyan]Step {idx}/{len(steps)}: {step.upper()}"
                )

                try:
                    # Execute step
                    step_result = self._execute_step(
                        step, regions,
                        dry_run=dry_run,
                        incremental=incremental,
                        **kwargs
                    )

                    # Save checkpoint
                    self.checkpoint_manager.save(
                        step, step_result,
                        metadata={'regions': regions, 'dry_run': dry_run}
                    )

                    # Update statistics
                    self.stats['steps_completed'].append(step)
                    self.stats['step_results'][step] = step_result

                    # Update progress
                    progress.update(overall_task, advance=1)

                    console.print(f"✅ [green]Step '{step}' completed[/green]")

                except Exception as e:
                    console.print(f"❌ [red]Step '{step}' failed: {e}[/red]")

                    self.stats['steps_failed'].append(step)
                    self.stats['step_results'][step] = {
                        'success': False,
                        'error': str(e)
                    }

                    # Handle error based on fail_fast config
                    if self.config.get('fail_fast', False):
                        console.print("[red]Stopping due to fail_fast=True[/red]")
                        raise

                    # Continue to next step
                    console.print("[yellow]Continuing to next step...[/yellow]")
                    progress.update(overall_task, advance=1)

        # Print completion summary
        self._print_rich_summary(console)

    def _run_steps_basic(self, steps: List[str], regions: List[str],
                        dry_run: bool, incremental: bool, **kwargs):
        """
        Execute pipeline steps with basic logging (no Rich UI)

        Args:
            steps: List of steps to execute
            regions: List of regions
            dry_run: Dry-run mode flag
            incremental: Incremental mode flag
            **kwargs: Additional options
        """
        for idx, step in enumerate(steps, 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"Step {idx}/{len(steps)}: {step.upper()}")
            logger.info(f"{'='*80}")

            try:
                # Execute step
                step_result = self._execute_step(
                    step, regions,
                    dry_run=dry_run,
                    incremental=incremental,
                    **kwargs
                )

                # Save checkpoint
                self.checkpoint_manager.save(
                    step, step_result,
                    metadata={'regions': regions, 'dry_run': dry_run}
                )

                # Update statistics
                self.stats['steps_completed'].append(step)
                self.stats['step_results'][step] = step_result

                logger.info(f"✅ Step '{step}' completed")

            except Exception as e:
                logger.error(f"❌ Step '{step}' failed: {e}")

                self.stats['steps_failed'].append(step)
                self.stats['step_results'][step] = {
                    'success': False,
                    'error': str(e)
                }

                # Handle error based on fail_fast config
                if self.config.get('fail_fast', False):
                    logger.error("Stopping due to fail_fast=True")
                    raise

                # Continue to next step
                logger.info("Continuing to next step...")

    def _print_rich_summary(self, console: 'Console'):
        """
        Print execution summary using Rich formatting

        Args:
            console: Rich Console instance
        """
        # Create summary table
        table = Table(title="Pipeline Execution Summary", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        # Add statistics
        duration = (datetime.now() - self.stats['start_time']).total_seconds()
        table.add_row("Duration", f"{duration:.2f}s")
        table.add_row("Steps Completed", str(len(self.stats['steps_completed'])))
        table.add_row("Steps Failed", str(len(self.stats['steps_failed'])))

        # Print table
        console.print(table)

        # Print failed steps if any
        if self.stats['steps_failed']:
            console.print("\n[red]Failed Steps:[/red]")
            for step in self.stats['steps_failed']:
                error = self.stats['step_results'][step].get('error', 'Unknown error')
                console.print(f"  • {step}: {error}")
