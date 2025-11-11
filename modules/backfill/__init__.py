"""
Backfill Optimization Module

Smart backfill orchestration with gap-aware execution for efficient
database population and incremental updates.

Components:
- GapAnalyzer: Column-level gap detection
- BackfillOrchestrator: High-level workflow coordination
- BackfillExecutor: Abstract base class for specific backfill implementations
- Data Structures: Core data types (GapPriority, TickerGapInfo, etc.)

Features:
- Pre-scan gap analysis (~2 seconds)
- Priority-based execution (fully_missing > partially_missing > complete)
- API call optimization (>90% reduction)
- Progress checkpointing
- Dry-run support

Example Usage:
    from modules.backfill import BackfillOrchestrator, GapAnalyzer
    from modules.db_manager_postgres import PostgresDatabaseManager

    # Initialize components
    db = PostgresDatabaseManager()
    gap_analyzer = GapAnalyzer(db)
    orchestrator = BackfillOrchestrator(db, gap_analyzer, dry_run=False)

    # Execute gap-aware backfill
    result = orchestrator.execute_backfill(
        backfill_type='equity',
        target_columns=['capital_stock', 'capital_surplus', 'retained_earnings'],
        region='KR',
        limit=100
    )

    # Check results
    summary = result.get_summary()
    print(f"API calls saved: {summary['gap_analysis']['api_calls_saved']}")
    print(f"Efficiency gain: {summary['gap_analysis']['efficiency_gain_pct']:.1f}%")

Author: Quant Platform Development Team
Date: 2025-11-11
"""

from modules.backfill.data_structures import (
    GapPriority,
    TickerGapInfo,
    GapAnalysisResult,
    BackfillStats,
    BackfillResult
)

# Component imports
from modules.backfill.gap_analyzer import GapAnalyzer
from modules.backfill.executor_base import BackfillExecutor
from modules.backfill.orchestrator import BackfillOrchestrator
from modules.backfill.equity_executor import EquityBackfillExecutor
from modules.backfill.listing_date_executor import ListingDateBackfillExecutor

__all__ = [
    # Data structures
    'GapPriority',
    'TickerGapInfo',
    'GapAnalysisResult',
    'BackfillStats',
    'BackfillResult',

    # Core components
    'GapAnalyzer',
    'BackfillExecutor',
    'BackfillOrchestrator',

    # Executor implementations
    'EquityBackfillExecutor',
    'ListingDateBackfillExecutor',
]

__version__ = '2.0.0'
__author__ = 'Quant Platform Development Team'
