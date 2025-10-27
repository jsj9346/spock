#!/usr/bin/env python3
"""
Global Stock Metadata Enrichment Script

Orchestrates metadata enrichment across 5 global markets:
- US (NASDAQ, NYSE, AMEX)
- CN (SSE, SZSE A-shares)
- HK (HKEX)
- JP (TSE)
- VN (HOSE, HNX)

Usage:
    python3 scripts/enrich_global_metadata.py [options]

Examples:
    # Basic usage (incremental mode)
    python3 scripts/enrich_global_metadata.py

    # Force refresh specific regions
    python3 scripts/enrich_global_metadata.py --regions US CN HK --force-refresh

    # Dry run for US market
    python3 scripts/enrich_global_metadata.py --regions US --dry-run

    # Phase 3: Parallel execution (2-3x speedup)
    python3 scripts/enrich_global_metadata.py --parallel --max-workers 5

    # Phase 3: Progress bar + parallel
    python3 scripts/enrich_global_metadata.py --parallel --progress-bar

    # Phase 3: Prometheus metrics export
    python3 scripts/enrich_global_metadata.py --prometheus-port 8003

    # Phase 3: Full optimization stack
    python3 scripts/enrich_global_metadata.py --parallel --progress-bar --prometheus-port 8003

Author: Spock Trading System
"""

import os
import sys
import logging
import argparse
import time
import random
import threading
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.market_adapters.us_adapter_kis import USAdapterKIS
from modules.market_adapters.cn_adapter_kis import CNAdapterKIS
from modules.market_adapters.hk_adapter_kis import HKAdapterKIS
from modules.market_adapters.jp_adapter_kis import JPAdapterKIS
from modules.market_adapters.vn_adapter_kis import VNAdapterKIS

# Optional imports for enhanced features
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


@dataclass
class EnrichmentConfig:
    """Configuration for metadata enrichment"""
    regions: List[str]
    force_refresh: bool = False
    incremental: bool = True
    max_age_days: int = 30
    dry_run: bool = False
    max_retries: int = 3
    retry_delay: float = 5.0
    verbose: bool = False
    log_file: str = 'logs/enrich_global_metadata.log'
    report_file: str = 'logs/enrichment_report.txt'
    # Phase 3: Performance optimization flags
    parallel: bool = False
    max_workers: int = 5
    progress_bar: bool = False
    prometheus_port: Optional[int] = None


@dataclass
class RegionResult:
    """Result for single region enrichment"""
    region: str
    total_stocks: int = 0
    enriched_count: int = 0
    failed_count: int = 0
    kis_mapping_count: int = 0
    yfinance_count: int = 0
    success_rate: float = 0.0
    execution_time: float = 0.0
    error: Optional[str] = None
    retry_attempts: int = 0


@dataclass
class GlobalEnrichmentResult:
    """Global enrichment result across all regions"""
    config: EnrichmentConfig
    region_results: List[RegionResult] = field(default_factory=list)
    total_execution_time: float = 0.0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def total_stocks(self) -> int:
        return sum(r.total_stocks for r in self.region_results)

    @property
    def total_enriched(self) -> int:
        return sum(r.enriched_count for r in self.region_results)

    @property
    def total_failed(self) -> int:
        return sum(r.failed_count for r in self.region_results)

    @property
    def overall_success_rate(self) -> float:
        if self.total_stocks == 0:
            return 0.0
        return self.total_enriched / self.total_stocks

    @property
    def total_kis_mapping(self) -> int:
        return sum(r.kis_mapping_count for r in self.region_results)

    @property
    def total_yfinance(self) -> int:
        return sum(r.yfinance_count for r in self.region_results)


class GlobalMetadataEnricher:
    """Main orchestrator for global metadata enrichment"""

    def __init__(self, config: EnrichmentConfig):
        self.config = config
        self.db = SQLiteDatabaseManager()
        self.logger = self._setup_logging()
        self.adapters = {}
        self._adapter_lock = threading.Lock()  # Thread-safe adapter initialization

        # Phase 3: Prometheus metrics
        self.metrics = None
        if config.prometheus_port and PROMETHEUS_AVAILABLE:
            self._setup_prometheus_metrics()
            try:
                start_http_server(config.prometheus_port)
                self.logger.info(f"📊 Prometheus metrics server started on port {config.prometheus_port}")
            except Exception as e:
                self.logger.warning(f"⚠️  Failed to start Prometheus server: {e}")

    def _setup_prometheus_metrics(self):
        """Setup Prometheus metrics collectors"""
        if not PROMETHEUS_AVAILABLE:
            return

        self.metrics = {
            'regions_processed': Counter(
                'spock_enrichment_regions_processed_total',
                'Total regions processed',
                ['region', 'status']
            ),
            'stocks_enriched': Counter(
                'spock_enrichment_stocks_enriched_total',
                'Total stocks enriched',
                ['region', 'source']
            ),
            'enrichment_duration': Histogram(
                'spock_enrichment_duration_seconds',
                'Enrichment duration per region',
                ['region'],
                buckets=[10, 30, 60, 120, 300, 600, 1200, 1800, 3600]
            ),
            'success_rate': Gauge(
                'spock_enrichment_success_rate',
                'Success rate per region',
                ['region']
            ),
            'retry_attempts': Counter(
                'spock_enrichment_retry_attempts_total',
                'Total retry attempts',
                ['region']
            )
        }

    def _setup_logging(self) -> logging.Logger:
        """
        Setup logging configuration

        Creates dual-output logging:
        - Console: INFO level (or DEBUG if verbose)
        - File: DEBUG level (comprehensive logging)

        Returns:
            Configured logger instance
        """
        # Create logs directory if not exists
        log_dir = os.path.dirname(self.config.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Create logger
        logger = logging.getLogger('GlobalMetadataEnricher')
        logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        logger.handlers.clear()

        # Console handler (INFO or DEBUG based on verbose flag)
        console_handler = logging.StreamHandler(sys.stdout)
        console_level = logging.DEBUG if self.config.verbose else logging.INFO
        console_handler.setLevel(console_level)
        console_format = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)

        # File handler (DEBUG level, comprehensive)
        file_handler = logging.FileHandler(self.config.log_file, mode='a')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

        return logger

    def _initialize_adapters(self) -> None:
        """
        Initialize market adapters for selected regions

        Loads KIS API credentials from .env and creates adapter instances.

        Raises:
            ValueError: If KIS API credentials not found
            RuntimeError: If adapter initialization fails
        """
        # Load KIS API credentials
        load_dotenv()
        app_key = os.getenv('KIS_APP_KEY')
        app_secret = os.getenv('KIS_APP_SECRET')

        if not app_key or not app_secret:
            raise ValueError(
                "KIS API credentials not found. "
                "Please set KIS_APP_KEY and KIS_APP_SECRET in .env file"
            )

        # Define adapter classes
        adapter_classes = {
            'US': USAdapterKIS,
            'CN': CNAdapterKIS,
            'HK': HKAdapterKIS,
            'JP': JPAdapterKIS,
            'VN': VNAdapterKIS
        }

        # Initialize adapters for selected regions
        for region in self.config.regions:
            if region not in adapter_classes:
                self.logger.warning(f"Unknown region: {region}, skipping")
                continue

            try:
                adapter_class = adapter_classes[region]
                self.adapters[region] = adapter_class(
                    db_manager=self.db,
                    app_key=app_key,
                    app_secret=app_secret
                )
                self.logger.info(f"✅ Initialized {region} adapter")

            except Exception as e:
                self.logger.error(f"❌ Failed to initialize {region} adapter: {e}")
                raise RuntimeError(f"Adapter initialization failed for {region}") from e

    def _is_retriable_error(self, error: Exception) -> bool:
        """
        Determine if error is retriable

        Retriable errors:
        - Network errors (ConnectionError, TimeoutError)
        - API rate limits (429 status)
        - Transient database errors (lock timeout)

        Non-retriable errors:
        - Invalid credentials (401, 403)
        - Missing data (KeyError, AttributeError)
        - Logic errors (ValueError, TypeError)
        """
        retriable_patterns = [
            'ConnectionError',
            'TimeoutError',
            'HTTPError: 429',
            'database is locked',
            'RateLimitError'
        ]

        error_str = str(error)
        return any(pattern in error_str for pattern in retriable_patterns)

    def _enrich_region(self, region: str) -> RegionResult:
        """
        Enrich metadata for single region with retry logic

        Args:
            region: Region code (US, CN, HK, JP, VN)

        Returns:
            RegionResult with enrichment summary

        Retry Logic:
        - Exponential backoff: 5s → 10s → 20s
        - Max retries: 3 (configurable)
        - Retries on: Network errors, API rate limits, transient DB errors
        - No retry on: Invalid credentials, missing data, logic errors
        """
        result = RegionResult(region=region)
        start_time = time.time()

        adapter = self.adapters.get(region)
        if not adapter:
            result.error = f"Adapter not initialized for {region}"
            self.logger.error(f"❌ {result.error}")
            if self.metrics:
                self.metrics['regions_processed'].labels(region=region, status='error').inc()
            return result

        # Dry run mode
        if self.config.dry_run:
            self.logger.info(f"🔍 [DRY RUN] Would enrich {region} stocks")
            # Query database for stock counts
            db_tickers = self.db.get_tickers(region=region, asset_type='STOCK', is_active=True)
            result.total_stocks = len(db_tickers)
            result.enriched_count = result.total_stocks
            result.success_rate = 1.0  # Assume success for dry run
            result.execution_time = 0.0
            if self.metrics:
                self.metrics['regions_processed'].labels(region=region, status='dry_run').inc()
            return result

        # Retry loop
        retry_delay = self.config.retry_delay
        for attempt in range(self.config.max_retries):
            try:
                self.logger.info(f"🚀 Enriching {region} stocks (attempt {attempt + 1}/{self.config.max_retries})...")

                # Call adapter enrichment method
                summary = adapter.enrich_stock_metadata(
                    force_refresh=self.config.force_refresh,
                    incremental=self.config.incremental,
                    max_age_days=self.config.max_age_days
                )

                # Populate result from summary
                result.total_stocks = summary['total_stocks']
                result.enriched_count = summary['enriched_count']
                result.failed_count = summary['failed_count']
                result.kis_mapping_count = summary['kis_mapping_count']
                result.yfinance_count = summary['yfinance_count']
                result.success_rate = summary['success_rate']
                result.execution_time = float(summary['execution_time'].replace(' seconds', ''))
                result.retry_attempts = attempt

                # Update Prometheus metrics
                if self.metrics:
                    self.metrics['regions_processed'].labels(region=region, status='success').inc()
                    self.metrics['stocks_enriched'].labels(region=region, source='kis').inc(result.kis_mapping_count)
                    self.metrics['stocks_enriched'].labels(region=region, source='yfinance').inc(result.yfinance_count)
                    self.metrics['enrichment_duration'].labels(region=region).observe(result.execution_time)
                    self.metrics['success_rate'].labels(region=region).set(result.success_rate)
                    if attempt > 0:
                        self.metrics['retry_attempts'].labels(region=region).inc(attempt)

                self.logger.info(f"✅ {region} enrichment complete: {result.enriched_count}/{result.total_stocks} stocks")
                return result

            except Exception as e:
                result.retry_attempts = attempt + 1
                self.logger.error(f"❌ {region} enrichment failed (attempt {attempt + 1}): {e}")

                # Check if retriable error
                if not self._is_retriable_error(e):
                    result.error = str(e)
                    if self.metrics:
                        self.metrics['regions_processed'].labels(region=region, status='failed').inc()
                    return result

                # Retry with exponential backoff
                if attempt < self.config.max_retries - 1:
                    jitter = random.uniform(0, 1)  # Add jitter to prevent thundering herd
                    wait_time = retry_delay + jitter
                    self.logger.info(f"⏳ Retrying in {wait_time:.1f} seconds...")
                    time.sleep(wait_time)
                    retry_delay *= 2  # Exponential backoff
                else:
                    result.error = f"Max retries exceeded: {e}"
                    if self.metrics:
                        self.metrics['regions_processed'].labels(region=region, status='failed').inc()

        return result

    def enrich_all_regions(self) -> GlobalEnrichmentResult:
        """
        Orchestrate enrichment across all selected regions

        Process:
        1. Initialize adapters for selected regions
        2. For each region:
           a. Log start with region emoji
           b. Call _enrich_region() with retry logic
           c. Collect result
           d. Update progress tracker
        3. Calculate global statistics
        4. Generate comprehensive report
        5. Return GlobalEnrichmentResult

        Phase 3 Enhancements:
        - Parallel execution with ThreadPoolExecutor (--parallel flag)
        - Progress bars with tqdm (--progress-bar flag)
        - Prometheus metrics export (--prometheus-port flag)

        Returns:
            GlobalEnrichmentResult with all region results and summary
        """
        result = GlobalEnrichmentResult(
            config=self.config,
            start_time=datetime.now()
        )

        self.logger.info("="*80)
        self.logger.info("🌍 GLOBAL STOCK METADATA ENRICHMENT")
        self.logger.info("="*80)
        self.logger.info(f"Regions: {', '.join(self.config.regions)}")
        self.logger.info(f"Mode: {'Force Refresh' if self.config.force_refresh else 'Incremental'}")
        self.logger.info(f"Max Age: {self.config.max_age_days} days")
        self.logger.info(f"Dry Run: {self.config.dry_run}")
        if self.config.parallel:
            self.logger.info(f"Parallel: Yes (max_workers={self.config.max_workers})")
        if self.config.progress_bar and TQDM_AVAILABLE:
            self.logger.info(f"Progress Bar: Enabled")
        self.logger.info("="*80)

        # Initialize adapters
        try:
            self._initialize_adapters()
        except Exception as e:
            self.logger.error(f"❌ Adapter initialization failed: {e}")
            return result

        # Choose execution strategy
        if self.config.parallel:
            result = self._enrich_parallel(result)
        else:
            result = self._enrich_sequential(result)

        # Calculate global statistics
        result.end_time = datetime.now()
        result.total_execution_time = (result.end_time - result.start_time).total_seconds()

        self.logger.info("")
        self.logger.info("="*80)
        self.logger.info("📊 GLOBAL ENRICHMENT SUMMARY")
        self.logger.info("="*80)
        self.logger.info(f"Total Stocks: {result.total_stocks:,}")
        self.logger.info(f"Enriched: {result.total_enriched:,} ({result.overall_success_rate:.1%})")
        self.logger.info(f"Failed: {result.total_failed:,}")
        self.logger.info(f"KIS Mapping: {result.total_kis_mapping:,} (instant)")
        self.logger.info(f"yfinance API: {result.total_yfinance:,} (API calls)")
        self.logger.info(f"Total Time: {result.total_execution_time:.2f}s ({result.total_execution_time/60:.1f} min)")
        if self.config.parallel and result.total_execution_time > 0:
            sequential_estimate = sum(r.execution_time for r in result.region_results)
            speedup = sequential_estimate / result.total_execution_time if result.total_execution_time > 0 else 1.0
            self.logger.info(f"Speedup: {speedup:.2f}x (vs sequential)")
        self.logger.info("="*80)

        return result

    def _enrich_sequential(self, result: GlobalEnrichmentResult) -> GlobalEnrichmentResult:
        """
        Sequential enrichment execution (original behavior)

        Args:
            result: GlobalEnrichmentResult to populate

        Returns:
            Updated GlobalEnrichmentResult
        """
        region_emojis = {
            'US': '🇺🇸',
            'CN': '🇨🇳',
            'HK': '🇭🇰',
            'JP': '🇯🇵',
            'VN': '🇻🇳'
        }

        # Setup progress bar if enabled
        iterator = self.config.regions
        if self.config.progress_bar and TQDM_AVAILABLE:
            iterator = tqdm(iterator, desc="Enriching regions", unit="region")

        for i, region in enumerate(iterator, 1):
            emoji = region_emojis.get(region, '🌍')
            if not self.config.progress_bar or not TQDM_AVAILABLE:
                self.logger.info("")
                self.logger.info(f"{emoji} [{i}/{len(self.config.regions)}] Processing {region} market...")
                self.logger.info("-"*80)

            region_result = self._enrich_region(region)
            result.region_results.append(region_result)

            # Log region summary
            if region_result.error:
                self.logger.error(f"❌ {region} failed: {region_result.error}")
            else:
                self.logger.info(f"✅ {region} complete:")
                self.logger.info(f"   Total: {region_result.total_stocks} stocks")
                self.logger.info(f"   Enriched: {region_result.enriched_count} ({region_result.success_rate:.1%})")
                self.logger.info(f"   KIS: {region_result.kis_mapping_count}, yfinance: {region_result.yfinance_count}")
                self.logger.info(f"   Time: {region_result.execution_time:.2f}s")

        return result

    def _enrich_parallel(self, result: GlobalEnrichmentResult) -> GlobalEnrichmentResult:
        """
        Parallel enrichment execution using ThreadPoolExecutor

        Phase 3 Enhancement: Concurrent processing for 2-3x speedup

        Expected Performance:
        - US (11.2 min) + CN (16.7 min) + HK (5.0 min) + JP (7.1 min) + VN (2.3 min)
        - Sequential: ~42 min total
        - Parallel (5 workers): ~17 min total (2.5x speedup)

        Thread Safety:
        - Each adapter has independent KIS API client (no shared state)
        - SQLite database uses write-ahead logging (WAL) for concurrent writes
        - Logging uses thread-safe handlers

        Args:
            result: GlobalEnrichmentResult to populate

        Returns:
            Updated GlobalEnrichmentResult
        """
        region_emojis = {
            'US': '🇺🇸',
            'CN': '🇨🇳',
            'HK': '🇭🇰',
            'JP': '🇯🇵',
            'VN': '🇻🇳'
        }

        self.logger.info(f"⚡ Starting parallel enrichment with {self.config.max_workers} workers")

        # Setup progress bar if enabled
        if self.config.progress_bar and TQDM_AVAILABLE:
            pbar = tqdm(total=len(self.config.regions), desc="Enriching regions", unit="region")
        else:
            pbar = None

        # Execute regions in parallel
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all regions to executor
            future_to_region = {
                executor.submit(self._enrich_region, region): region
                for region in self.config.regions
            }

            # Collect results as they complete
            for future in as_completed(future_to_region):
                region = future_to_region[future]
                emoji = region_emojis.get(region, '🌍')

                try:
                    region_result = future.result()
                    result.region_results.append(region_result)

                    # Log region summary
                    if region_result.error:
                        self.logger.error(f"❌ {emoji} {region} failed: {region_result.error}")
                    else:
                        self.logger.info(f"✅ {emoji} {region} complete:")
                        self.logger.info(f"   Total: {region_result.total_stocks} stocks")
                        self.logger.info(f"   Enriched: {region_result.enriched_count} ({region_result.success_rate:.1%})")
                        self.logger.info(f"   KIS: {region_result.kis_mapping_count}, yfinance: {region_result.yfinance_count}")
                        self.logger.info(f"   Time: {region_result.execution_time:.2f}s")

                except Exception as e:
                    self.logger.error(f"❌ {emoji} {region} fatal error: {e}")
                    result.region_results.append(RegionResult(
                        region=region,
                        error=str(e)
                    ))

                finally:
                    if pbar:
                        pbar.update(1)

        if pbar:
            pbar.close()

        return result

    def _generate_report(self, result: GlobalEnrichmentResult) -> str:
        """
        Generate comprehensive enrichment report

        Report Sections:
        1. Header (timestamp, configuration)
        2. Global Summary (total stocks, success rate, execution time)
        3. Region-by-Region Breakdown
        4. Performance Metrics (KIS vs yfinance, API calls, rate)
        5. Error Details (failed regions, retry attempts)
        6. Recommendations (incremental mode, age threshold)

        Args:
            result: GlobalEnrichmentResult with all region data

        Returns:
            Formatted report string (markdown-compatible)
        """
        lines = []

        # Header
        lines.append("="*80)
        lines.append("GLOBAL STOCK METADATA ENRICHMENT REPORT")
        lines.append("="*80)
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Start Time: {result.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"End Time: {result.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Total Duration: {result.total_execution_time:.2f}s ({result.total_execution_time/60:.1f} min)")
        lines.append("")

        # Configuration
        lines.append("CONFIGURATION")
        lines.append("-"*80)
        lines.append(f"Regions: {', '.join(result.config.regions)}")
        lines.append(f"Mode: {'Force Refresh' if result.config.force_refresh else 'Incremental'}")
        lines.append(f"Max Age: {result.config.max_age_days} days")
        lines.append(f"Dry Run: {result.config.dry_run}")
        lines.append(f"Max Retries: {result.config.max_retries}")
        lines.append("")

        # Global Summary
        lines.append("GLOBAL SUMMARY")
        lines.append("-"*80)
        lines.append(f"Total Stocks: {result.total_stocks:,}")
        lines.append(f"Successfully Enriched: {result.total_enriched:,} ({result.overall_success_rate:.1%})")
        lines.append(f"Failed: {result.total_failed:,}")
        lines.append(f"KIS Mapping (Instant): {result.total_kis_mapping:,}")
        lines.append(f"yfinance API Calls: {result.total_yfinance:,}")
        lines.append("")

        # Region Breakdown
        lines.append("REGION BREAKDOWN")
        lines.append("-"*80)
        lines.append(f"{'Region':<8} {'Total':>8} {'Enriched':>10} {'Failed':>8} {'KIS':>8} {'yfinance':>10} {'Time':>10} {'Status':<10}")
        lines.append("-"*80)

        for r in result.region_results:
            status = "✅ OK" if not r.error else f"❌ {r.error[:20]}"
            lines.append(
                f"{r.region:<8} "
                f"{r.total_stocks:>8,} "
                f"{r.enriched_count:>10,} "
                f"{r.failed_count:>8,} "
                f"{r.kis_mapping_count:>8,} "
                f"{r.yfinance_count:>10,} "
                f"{r.execution_time:>9.1f}s "
                f"{status:<10}"
            )
        lines.append("")

        # Performance Metrics
        lines.append("PERFORMANCE METRICS")
        lines.append("-"*80)
        if result.total_execution_time > 0:
            stocks_per_sec = result.total_enriched / result.total_execution_time
            lines.append(f"Enrichment Rate: {stocks_per_sec:.2f} stocks/sec")
        if result.total_yfinance > 0 and result.total_execution_time > 0:
            api_rate = result.total_yfinance / result.total_execution_time
            lines.append(f"yfinance API Rate: {api_rate:.2f} req/sec (target: 1 req/sec)")
        if result.total_stocks > 0:
            lines.append(f"KIS Mapping Efficiency: {result.total_kis_mapping / result.total_stocks:.1%} (instant)")
        lines.append("")

        # Error Details
        failed_regions = [r for r in result.region_results if r.error]
        if failed_regions:
            lines.append("ERROR DETAILS")
            lines.append("-"*80)
            for r in failed_regions:
                lines.append(f"{r.region}: {r.error}")
                lines.append(f"  Retry Attempts: {r.retry_attempts}")
            lines.append("")

        # Recommendations
        lines.append("RECOMMENDATIONS")
        lines.append("-"*80)
        if result.overall_success_rate < 0.95:
            lines.append("⚠️  Success rate < 95%. Review error logs and consider increasing max_retries.")
        if result.total_execution_time > 3600:  # > 1 hour
            lines.append("⚠️  Execution time > 1 hour. Consider using incremental mode or parallel execution.")
        if result.total_yfinance > 5000:
            lines.append("⚠️  >5,000 yfinance API calls. Consider reducing max_age_days for incremental mode.")
        if not failed_regions and result.overall_success_rate >= 0.95:
            lines.append("✅ All regions enriched successfully. No issues detected.")
        lines.append("")

        lines.append("="*80)
        return "\n".join(lines)

    def _write_report(self, report: str, result: GlobalEnrichmentResult) -> None:
        """
        Write report to file and console

        Args:
            report: Formatted report string
            result: GlobalEnrichmentResult
        """
        # Write to console
        print("\n" + report)

        # Write to file
        try:
            report_dir = os.path.dirname(self.config.report_file)
            if report_dir and not os.path.exists(report_dir):
                os.makedirs(report_dir)

            with open(self.config.report_file, 'w') as f:
                f.write(report)

            self.logger.info(f"📄 Report saved to: {self.config.report_file}")

        except Exception as e:
            self.logger.error(f"❌ Failed to write report file: {e}")


def parse_arguments() -> EnrichmentConfig:
    """Parse command-line arguments and return configuration"""
    parser = argparse.ArgumentParser(
        description='Global Stock Metadata Enrichment Script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Enrich all regions (incremental mode)
  python3 scripts/enrich_global_metadata.py

  # Enrich specific regions (force refresh)
  python3 scripts/enrich_global_metadata.py --regions US CN HK --force-refresh

  # Dry run for US market only
  python3 scripts/enrich_global_metadata.py --regions US --dry-run

  # Full refresh with custom age threshold
  python3 scripts/enrich_global_metadata.py --force-refresh --max-age-days 7

  # Verbose logging with detailed output
  python3 scripts/enrich_global_metadata.py --verbose --log-file /tmp/enrichment.log
        '''
    )

    # Region selection
    parser.add_argument(
        '--regions',
        nargs='+',
        choices=['US', 'CN', 'HK', 'JP', 'VN', 'ALL'],
        default=['ALL'],
        help='Regions to enrich (default: ALL)'
    )

    # Enrichment mode
    parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Skip cache and re-fetch all metadata (default: incremental)'
    )

    parser.add_argument(
        '--max-age-days',
        type=int,
        default=30,
        help='Max age for incremental mode (default: 30 days)'
    )

    # Execution control
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview operations without database modifications'
    )

    # Logging and output
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--log-file',
        type=str,
        default='logs/enrich_global_metadata.log',
        help='Log file path (default: logs/enrich_global_metadata.log)'
    )

    parser.add_argument(
        '--report-file',
        type=str,
        default='logs/enrichment_report.txt',
        help='Report output file (default: logs/enrichment_report.txt)'
    )

    # Error handling
    parser.add_argument(
        '--max-retries',
        type=int,
        default=3,
        help='Max retry attempts for transient failures (default: 3)'
    )

    parser.add_argument(
        '--retry-delay',
        type=float,
        default=5.0,
        help='Initial retry delay in seconds (default: 5.0)'
    )

    # Phase 3: Performance optimization flags
    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Enable parallel region processing (2-3x speedup)'
    )

    parser.add_argument(
        '--max-workers',
        type=int,
        default=5,
        help='Max parallel workers for parallel mode (default: 5)'
    )

    parser.add_argument(
        '--progress-bar',
        action='store_true',
        help='Show progress bar (requires tqdm package)'
    )

    parser.add_argument(
        '--prometheus-port',
        type=int,
        default=None,
        help='Prometheus metrics server port (requires prometheus_client package)'
    )

    args = parser.parse_args()

    # Handle 'ALL' region
    if 'ALL' in args.regions:
        args.regions = ['US', 'CN', 'HK', 'JP', 'VN']

    # Create config
    config = EnrichmentConfig(
        regions=args.regions,
        force_refresh=args.force_refresh,
        incremental=not args.force_refresh,  # Auto-disable incremental if force_refresh
        max_age_days=args.max_age_days,
        dry_run=args.dry_run,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
        verbose=args.verbose,
        log_file=args.log_file,
        report_file=args.report_file,
        # Phase 3: Performance optimization
        parallel=args.parallel,
        max_workers=args.max_workers,
        progress_bar=args.progress_bar,
        prometheus_port=args.prometheus_port
    )

    return config


def validate_config(config: EnrichmentConfig) -> None:
    """
    Validate configuration and check prerequisites

    Args:
        config: EnrichmentConfig to validate

    Raises:
        ValueError: If configuration is invalid
        FileNotFoundError: If required files are missing
    """
    # Validate regions
    valid_regions = {'US', 'CN', 'HK', 'JP', 'VN'}
    for region in config.regions:
        if region not in valid_regions:
            raise ValueError(f"Invalid region: {region}. Must be one of {valid_regions}")

    # Validate max_age_days
    if config.max_age_days < 1:
        raise ValueError(f"max_age_days must be >= 1, got {config.max_age_days}")

    # Validate max_retries
    if config.max_retries < 1:
        raise ValueError(f"max_retries must be >= 1, got {config.max_retries}")

    # Validate retry_delay
    if config.retry_delay < 0:
        raise ValueError(f"retry_delay must be >= 0, got {config.retry_delay}")

    # Phase 3: Validate performance optimization settings
    if config.parallel:
        if config.max_workers < 1 or config.max_workers > 10:
            raise ValueError(f"max_workers must be between 1 and 10, got {config.max_workers}")

    if config.progress_bar and not TQDM_AVAILABLE:
        raise ValueError(
            "Progress bar requested but tqdm package not installed. "
            "Install with: pip install tqdm"
        )

    if config.prometheus_port:
        if not PROMETHEUS_AVAILABLE:
            raise ValueError(
                "Prometheus metrics requested but prometheus_client package not installed. "
                "Install with: pip install prometheus-client"
            )
        if config.prometheus_port < 1024 or config.prometheus_port > 65535:
            raise ValueError(f"prometheus_port must be between 1024 and 65535, got {config.prometheus_port}")

    # Check .env file exists
    env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if not os.path.exists(env_file):
        raise FileNotFoundError(
            f".env file not found at {env_file}. "
            "Please create .env with KIS_APP_KEY and KIS_APP_SECRET"
        )


def main() -> int:
    """
    Main entry point

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Parse arguments
        config = parse_arguments()

        # Validate configuration
        validate_config(config)

        # Initialize enricher
        enricher = GlobalMetadataEnricher(config)

        # Execute enrichment
        result = enricher.enrich_all_regions()

        # Generate and write report
        report = enricher._generate_report(result)
        enricher._write_report(report, result)

        # Return exit code based on success rate
        if result.overall_success_rate >= 0.95:
            enricher.logger.info("✅ Enrichment completed successfully")
            return 0
        else:
            enricher.logger.warning(f"⚠️  Enrichment completed with warnings (success rate: {result.overall_success_rate:.1%})")
            return 0  # Still return 0 for partial success

    except KeyboardInterrupt:
        print("\n❌ Enrichment interrupted by user")
        return 1

    except Exception as e:
        print(f"\n❌ Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
