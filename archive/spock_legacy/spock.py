#!/usr/bin/env python3
"""
Spock Automated Trading System - Main Orchestrator

7-Stage Pipeline Architecture:
  Stage 0: Market Hours Check
  Stage 1: Stock Scanning & Filtering
  Stage 2: OHLCV Data Collection
  Stage 3: Technical Analysis
  Stage 4: Position Sizing
  Stage 5: Trade Execution
  Stage 6: Portfolio Sync

Usage:
  python3 spock.py --dry-run --region KR --risk-level moderate
  python3 spock.py --live --region US --enable-gpt
  python3 spock.py --after-hours --region KR
"""

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

# Core modules
from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.scanner import StockScanner
from modules.market_filter_manager import MarketFilterManager
from modules.kis_data_collector import KISDataCollector
from modules.integrated_scoring_system import IntegratedScoringSystem
from modules.kelly_calculator import KellyCalculator
from modules.kis_trading_engine import KISTradingEngine
from modules.portfolio_manager import PortfolioManager
from modules.risk_manager import RiskManager
from modules.stock_utils import check_market_hours

# Optional modules
try:
    from modules.stock_sentiment import StockSentiment
    SENTIMENT_AVAILABLE = True
except ImportError:
    SENTIMENT_AVAILABLE = False


# ============================================================================
# ENUMS & DATACLASSES
# ============================================================================

class ExecutionMode(Enum):
    """Execution mode configuration"""
    DRY_RUN = "dry_run"
    LIVE = "live"
    AFTER_HOURS = "after_hours"
    BACKTEST = "backtest"


class RiskLevel(Enum):
    """Risk profile configuration"""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class ErrorSeverity(Enum):
    """Error severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ErrorCategory(Enum):
    """Error category classification"""
    API = "api"
    DATABASE = "database"
    VALIDATION = "validation"
    EXECUTION = "execution"
    CONFIGURATION = "configuration"


@dataclass
class ExecutionConfig:
    """Execution configuration"""
    mode: ExecutionMode
    region: str
    risk_level: RiskLevel
    enable_sentiment: bool = False
    max_positions: int = 10
    max_portfolio_allocation: float = 0.80
    min_cash_reserve: float = 0.20
    scoring_threshold: float = 70.0
    kelly_multiplier: float = 0.5  # Half Kelly

    def __post_init__(self):
        """Validate configuration"""
        if self.max_portfolio_allocation + self.min_cash_reserve > 1.0:
            raise ValueError("Portfolio allocation + cash reserve cannot exceed 100%")
        if not 0 < self.scoring_threshold <= 100:
            raise ValueError("Scoring threshold must be between 0 and 100")


@dataclass
class PipelineResult:
    """Pipeline execution result"""
    success: bool
    region: str
    execution_mode: ExecutionMode
    candidates_scanned: int = 0
    candidates_filtered: int = 0
    candidates_analyzed: int = 0
    trades_executed: int = 0
    portfolio_value: float = 0.0
    cash_balance: float = 0.0
    execution_time_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "region": self.region,
            "execution_mode": self.execution_mode.value,
            "candidates_scanned": self.candidates_scanned,
            "candidates_filtered": self.candidates_filtered,
            "candidates_analyzed": self.candidates_analyzed,
            "trades_executed": self.trades_executed,
            "portfolio_value": self.portfolio_value,
            "cash_balance": self.cash_balance,
            "execution_time_seconds": self.execution_time_seconds,
            "timestamp": self.timestamp.isoformat(),
            "errors": self.errors,
            "warnings": self.warnings
        }


@dataclass
class ErrorContext:
    """Error context for recovery system"""
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    stage: str
    timestamp: datetime = field(default_factory=datetime.now)
    recovery_attempted: bool = False
    recovery_successful: bool = False


# ============================================================================
# SPOCK ORCHESTRATOR
# ============================================================================

class SpockOrchestrator:
    """Main orchestrator for Spock trading system"""

    def __init__(
        self,
        config_path: str = "./config",
        db_path: str = "./data/spock_local.db",
        log_path: str = "./logs",
        log_level: str = "INFO"
    ):
        """Initialize Spock orchestrator

        Args:
            config_path: Configuration directory path
            db_path: SQLite database path
            log_path: Log directory path
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.config_path = Path(config_path)
        self.db_path = Path(db_path)
        self.log_path = Path(log_path)
        self.log_level = log_level

        # Ensure directories exist
        self.config_path.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.mkdir(parents=True, exist_ok=True)

        # Setup logging
        self.logger = self._setup_logging()
        self.logger.info("Initializing Spock Orchestrator...")

        # Initialize subsystems
        self._initialize_subsystems()

        self.logger.info("Spock Orchestrator initialized successfully")

    def _setup_logging(self) -> logging.Logger:
        """Setup logging system"""
        log_file = self.log_path / f"{datetime.now().strftime('%Y%m%d')}_spock.log"

        # Create logger
        logger = logging.getLogger("spock")
        logger.setLevel(getattr(logging, self.log_level))

        # File handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, self.log_level))
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)

        # Add handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger

    def _initialize_subsystems(self):
        """Initialize all subsystems"""
        self.logger.info("Initializing subsystems...")

        # Database
        self.db = SQLiteDatabaseManager(str(self.db_path))
        self.logger.info("✅ Database manager initialized")

        # Scanner
        self.scanner = StockScanner(db_path=str(self.db_path))
        self.logger.info("✅ Stock scanner initialized")

        # Filter manager
        self.filter_manager = MarketFilterManager(str(self.config_path))
        self.logger.info("✅ Market filter manager initialized")

        # Data collector
        self.data_collector = KISDataCollector(str(self.db_path))
        self.logger.info("✅ KIS data collector initialized")

        # Scoring system
        self.scoring_system = IntegratedScoringSystem(str(self.db_path))
        self.logger.info("✅ Integrated scoring system initialized")

        # Kelly calculator
        self.kelly_calculator = KellyCalculator(str(self.db_path))
        self.logger.info("✅ Kelly calculator initialized")

        # Trading engine
        self.trading_engine = KISTradingEngine(str(self.db_path))
        self.logger.info("✅ KIS trading engine initialized")

        # Portfolio manager
        self.portfolio_manager = PortfolioManager(str(self.db_path))
        self.logger.info("✅ Portfolio manager initialized")

        # Risk manager
        self.risk_manager = RiskManager(str(self.db_path))
        self.logger.info("✅ Risk manager initialized")

        # Optional modules
        self.sentiment_analyzer = None

        if SENTIMENT_AVAILABLE:
            try:
                self.sentiment_analyzer = StockSentiment(str(self.db_path))
                self.logger.info("✅ Sentiment analyzer initialized")
            except Exception as e:
                self.logger.warning(f"⚠️ Sentiment analyzer initialization failed: {e}")

    async def run_pipeline(self, config: ExecutionConfig) -> PipelineResult:
        """Run main trading pipeline

        Args:
            config: Execution configuration

        Returns:
            PipelineResult with execution details
        """
        start_time = datetime.now()
        result = PipelineResult(
            success=False,
            region=config.region,
            execution_mode=config.mode
        )

        try:
            self.logger.info(f"=" * 80)
            self.logger.info(f"Starting Spock Pipeline - {config.mode.value.upper()} mode")
            self.logger.info(f"Region: {config.region} | Risk: {config.risk_level.value}")
            self.logger.info(f"=" * 80)

            # After-hours mode: data collection only
            if config.mode == ExecutionMode.AFTER_HOURS:
                return await self._after_hours_pipeline(config, result)

            # Stage 0: Market Hours Check
            if not await self._stage0_market_check(config):
                result.warnings.append("Market is closed - skipping execution")
                result.success = True
                return result

            # Stage 1: Stock Scanning & Filtering
            candidates = await self._stage1_scan_and_filter(config, result)
            if not candidates:
                result.warnings.append("No candidates found after filtering")
                result.success = True
                return result

            # Stage 2: OHLCV Data Collection
            await self._stage2_data_collection(config, result, candidates)

            # Stage 3: Technical Analysis
            analyzed_candidates = await self._stage3_technical_analysis(config, result, candidates)
            if not analyzed_candidates:
                result.warnings.append("No candidates passed technical analysis")
                result.success = True
                return result

            # Stage 4: Position Sizing
            sized_candidates = await self._stage4_position_sizing(config, result, analyzed_candidates)

            # Stage 5: Trade Execution
            if config.mode == ExecutionMode.LIVE:
                await self._stage5_trade_execution(config, result, sized_candidates)
            else:
                self.logger.info(f"DRY RUN: Would execute {len(sized_candidates)} trades")
                result.trades_executed = len(sized_candidates)

            # Stage 6: Portfolio Sync
            await self._stage6_portfolio_sync(config, result)

            result.success = True

        except Exception as e:
            self.logger.error(f"Pipeline execution failed: {e}", exc_info=True)
            result.errors.append(f"Pipeline execution error: {str(e)}")
            result.success = False

        finally:
            # Calculate execution time
            result.execution_time_seconds = (datetime.now() - start_time).total_seconds()

            # Log summary
            self._log_pipeline_summary(result)

        return result

    async def _stage0_market_check(self, config: ExecutionConfig) -> bool:
        """Stage 0: Check if market is open

        Returns:
            True if market is open or after-hours (allow trading logic to proceed)
            False if market is closed (weekend/holiday)
        """
        self.logger.info("Stage 0: Market Hours Check")

        try:
            market_status = check_market_hours()

            status = market_status['status']
            current_time = market_status['current_time_kst']
            is_weekend = market_status.get('is_weekend', False)
            is_holiday = market_status.get('is_holiday', False)

            self.logger.info(f"Current time (KST): {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"Market status: {status.upper()}")

            if is_weekend:
                self.logger.warning("Weekend detected - market closed")
                return False

            if is_holiday:
                self.logger.warning("Holiday detected - market closed")
                return False

            if status == 'market_closed':
                self.logger.warning("Market is closed")
                next_open = market_status.get('next_open')
                if next_open:
                    self.logger.info(f"Next market open: {next_open.strftime('%Y-%m-%d %H:%M')}")
                return False

            # Allow execution for: pre_market, market_open, after_hours
            if status in ['pre_market', 'market_open', 'after_hours']:
                self.logger.info(f"✅ Market check passed - {status}")
                return True

            self.logger.warning(f"Unknown market status: {status}")
            return False

        except Exception as e:
            self.logger.error(f"Market hours check failed: {e}")
            # Conservative: assume market is closed on error
            return False

    async def _stage1_scan_and_filter(
        self,
        config: ExecutionConfig,
        result: PipelineResult
    ) -> List[str]:
        """Stage 1: Scan and filter stocks

        Calls scanner.run_full_pipeline() which:
        - Stage 0: Scans all tickers from market data sources
        - Stage 1: Applies filters (market cap, volume, blacklist, etc.)

        Returns:
            List of filtered ticker codes
        """
        self.logger.info("Stage 1: Stock Scanning & Filtering")

        try:
            # Run scanner pipeline
            # force_refresh=False: Use cached ticker list if available
            # auto_stage1=True: Automatically run Stage 1 filtering after Stage 0
            # skip_data_collection=True: Don't collect OHLCV data yet (Stage 2 will do this)
            scanner_result = self.scanner.run_full_pipeline(
                force_refresh=False,
                auto_stage1=True,
                skip_data_collection=True,
                test_sample=None
            )

            # Extract results
            stage0_passed = scanner_result.get('stage0', {}).get('passed', 0)
            stage1_passed = scanner_result.get('stage1_filter', {}).get('passed', 0)

            result.candidates_scanned = stage0_passed
            result.candidates_filtered = stage1_passed

            # Get filtered ticker list from filter_cache_stage1 database
            filtered_tickers = self._load_stage1_tickers()

            self.logger.info(f"✅ Scanning complete: {stage0_passed} scanned → {stage1_passed} filtered ({len(filtered_tickers)} tickers loaded)")

            return filtered_tickers

        except Exception as e:
            self.logger.error(f"Stage 1 failed: {e}")
            result.errors.append(f"Stage 1 scanning error: {str(e)}")
            return []

    async def _stage2_data_collection(
        self,
        config: ExecutionConfig,
        result: PipelineResult,
        candidates: List[str]
    ):
        """Stage 2: Collect OHLCV data

        Calls data_collector.collect_data() which:
        - Fetches 250-day OHLCV data from KIS API
        - Calculates technical indicators (MA5/20/60/120/200, RSI, MACD, etc.)
        - Applies incremental update strategy (gap detection)
        - Saves to ohlcv_data table with UPSERT logic

        Weekly cleanup:
        - Runs on Sundays to delete OHLCV data older than 450 days
        - 450-day retention = 390 days (13-month filter) + 60-day buffer
        - Reclaims disk space via SQLite VACUUM
        """
        self.logger.info(f"Stage 2: OHLCV Data Collection ({len(candidates)} candidates)")

        try:
            # Run data collection for filtered candidates
            # force_full=False: Use incremental update strategy
            self.data_collector.collect_data(tickers=candidates, force_full=False)

            self.logger.info(f"✅ Data collection complete for {len(candidates)} tickers")

            # Weekly cleanup: delete old OHLCV data (Sunday execution)
            if datetime.now().weekday() == 6:  # 0=Monday, 6=Sunday
                try:
                    self.logger.info("🗑️ Weekly cleanup: Applying data retention policy...")

                    # Retention period: 450 days
                    # = 390 days (min_ohlcv_days for 13-month filter)
                    # + 60 days (max_gap_days buffer)
                    retention_days = 450

                    cleanup_result = self.data_collector.apply_data_retention_policy(
                        retention_days=retention_days
                    )

                    # Log cleanup statistics
                    deleted_rows = cleanup_result.get('deleted_rows', 0)
                    affected_tickers = cleanup_result.get('affected_tickers', 0)
                    size_reduction_pct = cleanup_result.get('size_reduction_pct', 0.0)

                    self.logger.info(
                        f"✅ Weekly cleanup complete: "
                        f"{deleted_rows:,} rows deleted, "
                        f"{affected_tickers} tickers affected, "
                        f"{size_reduction_pct:.1f}% database size reduction"
                    )

                    result.warnings.append(
                        f"Data cleanup: {deleted_rows:,} old OHLCV rows deleted (>{retention_days} days)"
                    )

                except Exception as cleanup_error:
                    # Non-critical: log warning but don't fail pipeline
                    self.logger.warning(f"⚠️ Weekly cleanup failed (non-critical): {cleanup_error}")
                    result.warnings.append(f"Data cleanup warning: {str(cleanup_error)}")

        except Exception as e:
            self.logger.error(f"Stage 2 failed: {e}")
            result.errors.append(f"Stage 2 data collection error: {str(e)}")

    async def _stage3_technical_analysis(
        self,
        config: ExecutionConfig,
        result: PipelineResult,
        candidates: List[str]
    ) -> List[Dict]:
        """Stage 3: Perform technical analysis

        Calls scoring_system.analyze_multiple_tickers() which:
        - Runs LayeredScoringEngine (3-layer, 100-point system)
        - Layer 1 (Macro): Market regime, volume profile, price action (25 pts)
        - Layer 2 (Structural): Stage analysis, MA alignment, relative strength (45 pts)
        - Layer 3 (Micro): Pattern recognition, volume spike, momentum (30 pts)
        - Filters by scoring threshold (default: 70+)

        Returns:
            List of analyzed candidates with scores and recommendations
        """
        self.logger.info(f"Stage 3: Technical Analysis ({len(candidates)} candidates)")

        try:
            # Run parallel technical analysis
            analysis_results = await self.scoring_system.analyze_multiple_tickers(
                tickers=candidates,
                max_concurrent=10
            )

            # Save results to database
            if analysis_results:
                self.scoring_system.save_results_to_db(analysis_results)

            # Filter by scoring threshold
            filtered_candidates = [
                {
                    'ticker': res.ticker,
                    'total_score': res.total_score,
                    'quality_score': res.quality_score,
                    'recommendation': res.recommendation,
                    'confidence': res.confidence,
                    'stage': res.stage,
                    'macro_score': res.macro_score,
                    'structural_score': res.structural_score,
                    'micro_score': res.micro_score,
                    'details': res.details
                }
                for res in analysis_results
                if res.total_score >= config.scoring_threshold
            ]

            result.candidates_analyzed = len(filtered_candidates)

            self.logger.info(f"✅ Technical analysis complete: {len(analysis_results)} analyzed, "
                           f"{len(filtered_candidates)} passed (threshold: {config.scoring_threshold})")

            return filtered_candidates

        except Exception as e:
            self.logger.error(f"Stage 3 failed: {e}")
            result.errors.append(f"Stage 3 technical analysis error: {str(e)}")
            return []

    async def _stage4_position_sizing(
        self,
        config: ExecutionConfig,
        result: PipelineResult,
        analyzed_candidates: List[Dict]
    ) -> List[Dict]:
        """Stage 4: Calculate position sizes

        Calls kelly_calculator.calculate_batch_positions() which:
        - Detects pattern type from technical analysis
        - Maps pattern to historical win rate (Stage 1→2: 67.5%, VCP: 62.5%, etc.)
        - Applies quality score adjustments (12-25 pts: 0.8x-1.4x multiplier)
        - Calculates Kelly optimal position size
        - Applies Half Kelly (0.5 multiplier) for conservative sizing
        - Enforces max position limit (8-15% based on risk level)

        Returns:
            List of candidates with Kelly position sizing
        """
        self.logger.info(f"Stage 4: Position Sizing ({len(analyzed_candidates)} candidates)")

        try:
            # Calculate Kelly positions for all candidates
            candidates_with_kelly = self.kelly_calculator.calculate_batch_positions(analyzed_candidates)

            # Filter out candidates with insufficient allocation
            portfolio_status = self.kelly_calculator.get_portfolio_allocation_status()
            remaining_allocation = portfolio_status['remaining_allocation']

            # Sort by final_position_pct (highest first)
            candidates_with_kelly.sort(
                key=lambda x: x.get('kelly_analysis').final_position_pct if x.get('kelly_analysis') else 0,
                reverse=True
            )

            # Apply Kelly multiplier from config (default: 0.5 = Half Kelly)
            sized_candidates = []
            for candidate in candidates_with_kelly:
                kelly_result = candidate.get('kelly_analysis')

                if not kelly_result:
                    continue

                # Apply Kelly multiplier
                final_position = kelly_result.final_position_pct * config.kelly_multiplier

                # Check if we have enough remaining allocation
                if final_position <= remaining_allocation:
                    candidate['position_size_pct'] = final_position
                    candidate['position_size_krw'] = 0  # Will be calculated by trading engine
                    candidate['kelly_pattern'] = kelly_result.detected_pattern.value
                    sized_candidates.append(candidate)
                    remaining_allocation -= final_position
                else:
                    self.logger.warning(f"{candidate['ticker']} Kelly position {final_position:.2f}% "
                                      f"exceeds remaining allocation {remaining_allocation:.2f}% - skipped")

            self.logger.info(f"✅ Position sizing complete: {len(sized_candidates)}/{len(analyzed_candidates)} "
                           f"positions sized (remaining allocation: {remaining_allocation:.2f}%)")

            return sized_candidates

        except Exception as e:
            self.logger.error(f"Stage 4 failed: {e}")
            result.errors.append(f"Stage 4 position sizing error: {str(e)}")
            return []

    async def _stage5_trade_execution(
        self,
        config: ExecutionConfig,
        result: PipelineResult,
        sized_candidates: List[Dict]
    ):
        """Stage 5: Execute trades

        Calls trading_engine.execute_buy_order() for each candidate which:
        - Checks position limits (15% stock, 40% sector, 20% cash reserve, 10 positions)
        - Gets current price from KIS API
        - Adjusts price to tick size (Korean market: 1-1,000 KRW tick sizes)
        - Calculates fee-adjusted quantity (0.015% commission)
        - Executes KIS API buy order (market or limit)
        - Saves trade record to trades table
        - Syncs portfolio table
        """
        self.logger.info(f"Stage 5: Trade Execution ({len(sized_candidates)} orders)")

        try:
            # Get portfolio value for position sizing
            portfolio_value = self.portfolio_manager.get_total_portfolio_value()

            executed_count = 0
            failed_count = 0

            for candidate in sized_candidates:
                ticker = candidate['ticker']
                position_pct = candidate['position_size_pct']
                sector = candidate.get('details', {}).get('sector', 'Unknown')

                # Calculate position size in KRW
                amount_krw = portfolio_value * (position_pct / 100.0)

                self.logger.info(f"Executing buy order: {ticker} ({position_pct:.2f}% = {amount_krw:,.0f} KRW)")

                # Execute buy order
                trade_result = self.trading_engine.execute_buy_order(
                    ticker=ticker,
                    amount_krw=amount_krw,
                    sector=sector,
                    region=config.region
                )

                if trade_result.success:
                    executed_count += 1
                    self.logger.info(f"✅ {ticker}: {trade_result.quantity} shares @ {trade_result.price:.0f} KRW")
                else:
                    failed_count += 1
                    self.logger.warning(f"❌ {ticker}: {trade_result.message}")

            result.trades_executed = executed_count

            self.logger.info(f"✅ Trade execution complete: {executed_count} success, {failed_count} failed")

        except Exception as e:
            self.logger.error(f"Stage 5 failed: {e}")
            result.errors.append(f"Stage 5 trade execution error: {str(e)}")

    async def _stage6_portfolio_sync(
        self,
        config: ExecutionConfig,
        result: PipelineResult
    ):
        """Stage 6: Sync portfolio state

        Calls portfolio_manager methods to:
        - Get total portfolio value (cash + positions)
        - Get available cash balance
        - Get all open positions with current prices
        - Sync portfolio table with trades table
        - Calculate portfolio metrics (P&L, exposure, etc.)
        """
        self.logger.info("Stage 6: Portfolio Sync")

        try:
            # Sync portfolio table with latest trades
            self.portfolio_manager.sync_portfolio_table()

            # Get portfolio summary
            summary = self.portfolio_manager.get_portfolio_summary()

            # Update result
            result.portfolio_value = summary.total_value
            result.cash_balance = summary.cash

            # Log portfolio status
            self.logger.info(f"Portfolio Summary:")
            self.logger.info(f"  Total Value: {summary.total_value:,.0f} KRW")
            self.logger.info(f"  Cash: {summary.cash:,.0f} KRW ({summary.cash_percent:.1f}%)")
            self.logger.info(f"  Positions: {summary.position_count}")
            self.logger.info(f"  Total P&L: {summary.total_pnl:+,.0f} KRW ({summary.total_pnl_percent:+.2f}%)")

            if summary.position_count > 0:
                self.logger.info(f"  Largest Position: {summary.largest_position_ticker} "
                               f"({summary.largest_position_percent:.1f}%)")

            # Check position limits
            self.portfolio_manager.log_position_limits()

            self.logger.info("✅ Portfolio sync complete")

        except Exception as e:
            self.logger.error(f"Stage 6 failed: {e}")
            result.errors.append(f"Stage 6 portfolio sync error: {str(e)}")

    async def _after_hours_pipeline(
        self,
        config: ExecutionConfig,
        result: PipelineResult
    ) -> PipelineResult:
        """After-hours mode: data collection only

        Runs Stages 0-2 for data collection without trading:
        - Stage 0: Market hours check (informational only)
        - Stage 1: Stock scanning & filtering
        - Stage 2: OHLCV data collection

        Skips Stages 3-6 (analysis, sizing, trading, sync)
        """
        self.logger.info("After-Hours Mode: Data Collection Only")

        try:
            # Stage 0: Market hours check (informational only)
            market_status_ok = await self._stage0_market_check(config)
            if market_status_ok:
                self.logger.info("Market is open - after-hours mode will still run data collection only")

            # Stage 1: Stock Scanning & Filtering
            candidates = await self._stage1_scan_and_filter(config, result)
            if not candidates:
                result.warnings.append("No candidates found after filtering")
                result.success = True
                return result

            # Stage 2: OHLCV Data Collection
            await self._stage2_data_collection(config, result, candidates)

            result.success = True
            self.logger.info(f"✅ After-hours data collection complete: {len(candidates)} tickers processed")

        except Exception as e:
            self.logger.error(f"After-hours pipeline failed: {e}")
            result.errors.append(f"After-hours pipeline error: {str(e)}")
            result.success = False

        return result

    def _load_stage1_tickers(self) -> List[str]:
        """Load filtered tickers from Stage 1 cache (filter_cache_stage1)

        Returns:
            List of ticker codes that passed Stage 1 filtering
        """
        import sqlite3

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Query for tickers that passed Stage 1 filtering
            cursor.execute("""
                SELECT ticker
                FROM filter_cache_stage1
                WHERE region = ? AND stage1_passed = 1
                ORDER BY created_at DESC
            """, (self.scanner.region,))

            tickers = [row[0] for row in cursor.fetchall()]
            conn.close()

            self.logger.debug(f"Loaded {len(tickers)} tickers from Stage 1 cache")
            return tickers

        except Exception as e:
            self.logger.error(f"Failed to load Stage 1 tickers: {e}")
            return []

    def _log_pipeline_summary(self, result: PipelineResult):
        """Log pipeline execution summary"""
        self.logger.info("")
        self.logger.info("=" * 80)
        self.logger.info("PIPELINE EXECUTION SUMMARY")
        self.logger.info("=" * 80)
        self.logger.info(f"Status: {'✅ SUCCESS' if result.success else '❌ FAILED'}")
        self.logger.info(f"Region: {result.region}")
        self.logger.info(f"Mode: {result.execution_mode.value}")
        self.logger.info(f"Execution Time: {result.execution_time_seconds:.2f}s")
        self.logger.info("")
        self.logger.info(f"Candidates Scanned: {result.candidates_scanned}")
        self.logger.info(f"Candidates Filtered: {result.candidates_filtered}")
        self.logger.info(f"Candidates Analyzed: {result.candidates_analyzed}")
        self.logger.info(f"Trades Executed: {result.trades_executed}")
        self.logger.info("")
        self.logger.info(f"Portfolio Value: {result.portfolio_value:,.2f}")
        self.logger.info(f"Cash Balance: {result.cash_balance:,.2f}")

        if result.warnings:
            self.logger.info("")
            self.logger.info(f"Warnings ({len(result.warnings)}):")
            for warning in result.warnings:
                self.logger.warning(f"  - {warning}")

        if result.errors:
            self.logger.info("")
            self.logger.info(f"Errors ({len(result.errors)}):")
            for error in result.errors:
                self.logger.error(f"  - {error}")

        self.logger.info("=" * 80)


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Spock Automated Trading System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run mode (safe testing)
  python3 spock.py --dry-run --region KR --risk-level moderate

  # Live trading
  python3 spock.py --live --region KR --risk-level conservative

  # After-hours data collection
  python3 spock.py --after-hours --region KR

  # Backtest mode
  python3 spock.py --backtest --region US --risk-level aggressive

  # Debug mode
  python3 spock.py --dry-run --region KR --debug
        """
    )

    # Execution mode (required)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--dry-run', action='store_true',
                           help='Dry run mode (no real trades)')
    mode_group.add_argument('--live', action='store_true',
                           help='Live trading mode')
    mode_group.add_argument('--after-hours', action='store_true',
                           help='After-hours data collection mode')
    mode_group.add_argument('--backtest', action='store_true',
                           help='Backtest mode')

    # Region (required)
    parser.add_argument('--region', type=str, required=True,
                       choices=['KR', 'US', 'CN', 'HK', 'JP', 'VN'],
                       help='Trading region')

    # Risk level
    parser.add_argument('--risk-level', type=str, default='moderate',
                       choices=['conservative', 'moderate', 'aggressive'],
                       help='Risk profile (default: moderate)')

    # Optional features
    parser.add_argument('--enable-sentiment', action='store_true',
                       help='Enable market sentiment analysis')

    # Configuration
    parser.add_argument('--max-positions', type=int, default=10,
                       help='Maximum number of positions (default: 10)')
    parser.add_argument('--scoring-threshold', type=float, default=70.0,
                       help='Minimum scoring threshold (default: 70.0)')

    # Paths
    parser.add_argument('--config-path', type=str, default='./config',
                       help='Configuration directory path')
    parser.add_argument('--db-path', type=str, default='./data/spock_local.db',
                       help='Database path')
    parser.add_argument('--log-path', type=str, default='./logs',
                       help='Log directory path')

    # Debug
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')

    args = parser.parse_args()

    # Determine execution mode
    if args.dry_run:
        mode = ExecutionMode.DRY_RUN
    elif args.live:
        mode = ExecutionMode.LIVE
    elif args.after_hours:
        mode = ExecutionMode.AFTER_HOURS
    else:
        mode = ExecutionMode.BACKTEST

    # Create execution config
    config = ExecutionConfig(
        mode=mode,
        region=args.region,
        risk_level=RiskLevel(args.risk_level),
        enable_sentiment=args.enable_sentiment,
        max_positions=args.max_positions,
        scoring_threshold=args.scoring_threshold
    )

    # Initialize orchestrator
    log_level = "DEBUG" if args.debug else "INFO"
    orchestrator = SpockOrchestrator(
        config_path=args.config_path,
        db_path=args.db_path,
        log_path=args.log_path,
        log_level=log_level
    )

    # Run pipeline
    result = asyncio.run(orchestrator.run_pipeline(config))

    # Exit with appropriate code
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
