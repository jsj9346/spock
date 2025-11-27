"""
Smart backfill orchestration with gap-aware execution

This module coordinates the 2-phase backfill workflow:
- Phase 1: Gap analysis to identify tickers needing backfill
- Phase 2: Targeted backfill execution with progress tracking

Key Features:
- Gap-aware optimization (90%+ API call reduction)
- Executor factory pattern for different backfill types
- Checkpoint support for resume capability
- Comprehensive progress tracking and reporting
- DRY RUN mode for validation

Example Usage:
    from modules.backfill import BackfillOrchestrator, GapAnalyzer
    from modules.db_manager_postgres import PostgresDatabaseManager
    from datetime import date

    db = PostgresDatabaseManager()
    gap_analyzer = GapAnalyzer(db)
    orchestrator = BackfillOrchestrator(db, gap_analyzer, dry_run=False)

    result = orchestrator.execute_backfill(
        backfill_type='equity',
        target_columns=['capital_stock', 'capital_surplus', 'retained_earnings'],
        region='KR',
        limit=100,
        backfill_start_date=date(2022, 1, 1)
    )

    print(f"API calls saved: {result.gap_analysis.get_summary()['complete']} tickers")
    print(f"Efficiency gain: {result.gap_analysis.get_summary()['efficiency_gain_pct']:.1f}%")

Author: Quant Platform Development Team
Date: 2025-11-11
"""

import logging
import json
from typing import List, Optional
from datetime import datetime, date
from pathlib import Path

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.backfill.gap_analyzer import GapAnalyzer
from modules.backfill.data_structures import (
    GapPriority, TickerGapInfo, GapAnalysisResult,
    BackfillStats, BackfillResult
)
from modules.backfill.executor_base import BackfillExecutor

logger = logging.getLogger(__name__)


class BackfillOrchestrator:
    """
    Smart backfill orchestration with gap-aware execution

    Implements 2-phase workflow:
    1. Gap Analysis: Identify tickers with missing data
    2. Targeted Backfill: Execute backfill only for gapped tickers

    This achieves 90%+ API call reduction in incremental update scenarios
    by skipping tickers that already have complete data.
    """

    def __init__(
        self,
        db: PostgresDatabaseManager,
        gap_analyzer: Optional[GapAnalyzer] = None,
        dry_run: bool = False
    ):
        """
        Initialize BackfillOrchestrator

        Args:
            db: PostgreSQL database manager instance
            gap_analyzer: GapAnalyzer instance (creates new if None)
            dry_run: If True, preview operations without executing
        """
        self.db = db
        self.gap_analyzer = gap_analyzer or GapAnalyzer(db)
        self.dry_run = dry_run
        self.stats = BackfillStats()

        logger.debug(f"BackfillOrchestrator initialized (dry_run={dry_run})")

    def execute_backfill(
        self,
        backfill_type: str,
        target_columns: List[str],
        region: str = 'KR',
        priority: Optional[GapPriority] = None,
        limit: Optional[int] = None,
        checkpoint_interval: int = 100,
        backfill_start_date: Optional[date] = None
    ) -> BackfillResult:
        """
        Execute gap-aware backfill workflow

        Workflow:
        1. Phase 1: Gap Analysis
           - Scan database for missing/NULL values in target columns
           - Classify tickers by priority (FULLY_MISSING > PARTIALLY_MISSING > COMPLETE)
           - Skip COMPLETE tickers (optimization)

        2. Phase 2: Targeted Backfill
           - Get appropriate executor for backfill_type
           - Validate prerequisites (API auth, data availability)
           - Execute batch backfill with checkpoint support
           - Track progress and generate statistics

        Args:
            backfill_type: Type of backfill ('equity', 'listing_date', etc.)
            target_columns: List of column names to check for gaps
            region: Market region (default: 'KR')
            priority: Filter to specific priority level (optional)
            limit: Maximum number of tickers to analyze (optional)
            checkpoint_interval: Save checkpoint every N tickers (default: 100)
            backfill_start_date: Start date for backfill period (optional)

        Returns:
            BackfillResult containing gap analysis results, backfill statistics,
            checkpoint file path, and success status

        Example:
            orchestrator = BackfillOrchestrator(db, dry_run=False)
            result = orchestrator.execute_backfill(
                backfill_type='equity',
                target_columns=['capital_stock', 'capital_surplus'],
                region='KR',
                limit=100,
                backfill_start_date=date(2022, 1, 1)
            )

            if result.success:
                summary = result.get_summary()
                print(f"Efficiency gain: {summary['gap_analysis']['efficiency_gain_pct']:.1f}%")
        """
        start_time = datetime.now()

        logger.info("=" * 80)
        logger.info(f"BACKFILL ORCHESTRATION: {backfill_type.upper()}")
        logger.info("=" * 80)
        logger.info(f"모드: {'DRY RUN' if self.dry_run else 'PRODUCTION'}")
        logger.info(f"Target Columns: {', '.join(target_columns)}")
        logger.info(f"Region: {region}")
        if limit:
            logger.info(f"Limit: {limit:,} tickers")
        if priority:
            logger.info(f"Priority Filter: {priority.name}")
        logger.info("=" * 80)

        try:
            # Phase 1: Gap Analysis
            gap_result = self._phase1_gap_analysis(
                backfill_type=backfill_type,
                target_columns=target_columns,
                region=region,
                backfill_start_date=backfill_start_date,
                limit=limit
            )

            # Get backfill targets based on priority filter
            targets = gap_result.get_backfill_targets(priority=priority)

            logger.info(f"\n✅ Phase 1 완료: {len(targets):,} tickers need backfill")

            if not targets:
                logger.info("✨ 백필이 필요한 ticker가 없습니다 - 종료")
                return BackfillResult(
                    gap_analysis=gap_result,
                    backfill_stats=self.stats,
                    checkpoint_file=None,
                    success=True
                )

            # Phase 2: Targeted Backfill
            checkpoint_file = self._get_checkpoint_path(backfill_type)
            backfill_stats = self._phase2_targeted_backfill(
                backfill_type=backfill_type,
                targets=targets,
                checkpoint_interval=checkpoint_interval,
                checkpoint_file=checkpoint_file
            )

            # Final summary
            elapsed = (datetime.now() - start_time).total_seconds()

            logger.info("\n" + "=" * 80)
            logger.info("✅ BACKFILL ORCHESTRATION 완료")
            logger.info("=" * 80)
            logger.info(f"총 실행 시간: {elapsed:.1f}s")

            logger.info(f"\n📊 Gap Analysis:")
            gap_summary = gap_result.get_summary()
            for key, value in gap_summary.items():
                logger.info(f"  {key}: {value}")

            logger.info(f"\n📈 Backfill Stats:")
            stats_dict = backfill_stats.to_dict()
            for key, value in stats_dict.items():
                logger.info(f"  {key}: {value}")

            # Calculate efficiency gain
            if gap_result.total_analyzed > 0:
                api_calls_saved = len(gap_result.complete)
                efficiency_gain = (api_calls_saved / gap_result.total_analyzed) * 100
                logger.info(f"\n🚀 Efficiency Gain:")
                logger.info(f"  API calls saved: {api_calls_saved:,} ({efficiency_gain:.1f}%)")

            return BackfillResult(
                gap_analysis=gap_result,
                backfill_stats=backfill_stats,
                checkpoint_file=checkpoint_file,
                success=True
            )

        except Exception as e:
            logger.error(f"❌ Backfill orchestration failed: {e}")
            import traceback
            logger.error(traceback.format_exc())

            return BackfillResult(
                gap_analysis=None,
                backfill_stats=self.stats,
                checkpoint_file=None,
                success=False,
                error_message=str(e)
            )

    def _phase1_gap_analysis(
        self,
        backfill_type: str,
        target_columns: List[str],
        region: str,
        backfill_start_date: Optional[date] = None,
        limit: Optional[int] = None
    ) -> GapAnalysisResult:
        """
        Phase 1: Gap detection

        Executes SQL query to identify tickers with missing data in target columns.
        Results are classified by priority for optimal backfill execution order.

        Args:
            backfill_type: Type of backfill (determines target table)
            target_columns: Columns to check for NULL values
            region: Market region filter
            backfill_start_date: Start date for backfill period
            limit: Maximum number of tickers to analyze

        Returns:
            GapAnalysisResult with classified tickers and efficiency metrics
        """
        logger.info("\n[PHASE 1] Gap Analysis")
        logger.info("-" * 80)

        # Determine table based on backfill type
        table_map = {
            'equity': 'ticker_fundamentals',
            'fundamentals': 'ticker_fundamentals',
            'listing_date': 'tickers'
        }
        table = table_map.get(backfill_type, 'ticker_fundamentals')

        # Default backfill start date if not provided
        if not backfill_start_date:
            backfill_start_date = date(2022, 1, 1)
            logger.info(f"Using default backfill_start_date: {backfill_start_date}")

        # Execute gap analysis
        gap_result = self.gap_analyzer.analyze_gaps(
            table=table,
            target_columns=target_columns,
            region=region,
            asset_type='STOCK',
            backfill_start_date=backfill_start_date,
            limit=limit
        )

        return gap_result

    def _phase2_targeted_backfill(
        self,
        backfill_type: str,
        targets: List[TickerGapInfo],
        checkpoint_interval: int,
        checkpoint_file: str
    ) -> BackfillStats:
        """
        Phase 2: Execute backfill for gapped tickers only

        Gets appropriate executor for backfill_type and executes batch processing
        with checkpoint support for resume capability.

        Args:
            backfill_type: Type of backfill (determines executor)
            targets: List of tickers needing backfill (from gap analysis)
            checkpoint_interval: Save checkpoint every N tickers
            checkpoint_file: Path to checkpoint file

        Returns:
            BackfillStats with execution metrics
        """
        logger.info("\n[PHASE 2] Targeted Backfill")
        logger.info("-" * 80)

        if self.dry_run:
            logger.info("🔍 DRY RUN MODE: Skipping actual backfill execution")
            logger.info(f"Would process {len(targets):,} tickers:")
            for i, ticker_info in enumerate(targets[:10], 1):  # Show first 10
                logger.info(
                    f"  {i}. {ticker_info.ticker} ({ticker_info.name}) - "
                    f"Missing: {ticker_info.missing_count}/{ticker_info.total_count}"
                )
            if len(targets) > 10:
                logger.info(f"  ... and {len(targets) - 10} more")
            return self.stats

        # Get backfill executor for type
        executor = self._get_backfill_executor(backfill_type)

        # Validate prerequisites
        is_ready, issues = executor.validate_prerequisites()
        if not is_ready:
            logger.error("❌ Prerequisites validation failed:")
            for issue in issues:
                logger.error(f"  - {issue}")
            raise Exception(f"Prerequisites not met: {', '.join(issues)}")

        logger.info("✅ Prerequisites validation passed")

        # Execute batch backfill
        backfill_stats = executor.execute_batch(
            tickers=targets,
            checkpoint_interval=checkpoint_interval,
            checkpoint_file=checkpoint_file
        )

        return backfill_stats

    def _get_backfill_executor(
        self,
        backfill_type: str
    ) -> BackfillExecutor:
        """
        Get appropriate backfill executor for type (Factory Pattern)

        Imports executor modules dynamically to avoid circular dependencies.
        Creates executor instance with shared database connection and dry_run setting.

        Args:
            backfill_type: Type of backfill ('equity', 'listing_date', 'sec', 'edinet', etc.)

        Returns:
            BackfillExecutor instance for the specified type

        Raises:
            ValueError: If backfill_type is unknown
        """
        if backfill_type in ('equity', 'fundamentals'):
            from modules.backfill.equity_executor import EquityBackfillExecutor
            return EquityBackfillExecutor(self.db, dry_run=self.dry_run)

        elif backfill_type == 'listing_date':
            from modules.backfill.listing_date_executor import ListingDateBackfillExecutor
            return ListingDateBackfillExecutor(self.db, dry_run=self.dry_run)

        elif backfill_type == 'sec':
            # SEC EDGAR for US market fundamentals
            from modules.backfill.sec_executor import SECBackfillExecutor
            return SECBackfillExecutor(self.db, dry_run=self.dry_run)

        elif backfill_type == 'edinet':
            # EDINET for JP market fundamentals (to be implemented)
            from modules.backfill.edinet_executor import EDINETBackfillExecutor
            return EDINETBackfillExecutor(self.db, dry_run=self.dry_run)

        else:
            raise ValueError(
                f"Unknown backfill type: {backfill_type}. "
                f"Supported types: equity, fundamentals, listing_date, sec, edinet"
            )

    def _get_checkpoint_path(self, backfill_type: str) -> str:
        """
        Generate checkpoint file path

        Args:
            backfill_type: Type of backfill

        Returns:
            Checkpoint file path in format: log/backfill_{type}_checkpoint_{timestamp}.json
        """
        # Ensure logs directory exists
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return str(logs_dir / f"backfill_{backfill_type}_checkpoint_{timestamp}.json")
