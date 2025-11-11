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
        'ticker_refresh',    # New: Multi-region ticker refresh with OTC filtering
        'fx_tracking',       # New: Exchange rate tracking and FX signals
        'ohlcv',
        'fundamentals',
        'classification',    # New: Stock classification (SPAC, preferred, sector/industry)
        'dividend',
        'etf_data',          # New: ETF details and holdings
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
            'ticker_refresh': self._refresh_tickers,         # New step
            'fx_tracking': self._track_exchange_rates,       # New step
            'ohlcv': self._update_ohlcv,
            'fundamentals': self._update_fundamentals,
            'classification': self._classify_stocks,         # New step
            'dividend': self._calculate_dividend,
            'etf_data': self._update_etf_data,               # New step
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
                    # Use OHLCV collector adapter for KR market
                    from scripts.collect_ohlcv_orchestrated import OHLCVCollectorAdapter

                    adapter = OHLCVCollectorAdapter(
                        self.db,
                        region=region,
                        dry_run=kwargs.get('dry_run', False)
                    )

                    result = adapter.run_collection(
                        incremental=kwargs.get('incremental', True),
                        limit=self.config.get('limit')
                    )

                    results[region] = result
                    logger.info(
                        f"  ✅ [{region}] {result.get('tickers_collected', 0)} tickers collected "
                        f"in {result.get('duration', 0):.2f}s"
                    )

                else:
                    # Overseas markets
                    logger.info(f"  [{region}] Overseas OHLCV collection not implemented")
                    results[region] = {
                        'success': False,
                        'message': 'Overseas OHLCV collector not implemented'
                    }

            except Exception as e:
                logger.error(f"  ❌ [{region}] Failed: {e}")
                results[region] = {'success': False, 'error': str(e)}

        return results

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
                    dart = DARTApiClient(api_key=dart_api_key)
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
                # Use yfinance for overseas markets (to be implemented)
                logger.info(f"  [{region}] Overseas fundamental updater not implemented")
                results[region] = {
                    'success': False,
                    'message': 'Overseas fundamental updater not implemented'
                }

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

    def _validate_data_quality(self, regions: List[str]) -> None:
        """Validate data quality after pipeline execution"""
        logger.info(f"\n{'='*80}")
        logger.info("Data Quality Validation")
        logger.info(f"{'='*80}")

        validation_results = self.validator.validate_pipeline_output(regions)

        # Store in stats
        self.stats['validation'] = validation_results

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
            'KR': ['USD', 'JPY', 'CNY', 'EUR'],
            'US': ['KRW', 'JPY', 'CNY', 'EUR'],
            'JP': ['USD', 'KRW', 'CNY', 'EUR'],
            'CN': ['USD', 'KRW', 'JPY', 'EUR'],
            'HK': ['USD', 'KRW', 'JPY', 'CNY'],
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
