"""
Backfill Optimization Data Structures

Core data structures for scan-then-backfill optimization system:
- Gap analysis metadata
- Priority classification
- Execution statistics

Author: Quant Platform Development Team
Date: 2025-11-11
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import date


class GapPriority(Enum):
    """
    Gap priority classification for backfill targeting

    Priority levels:
    - FULLY_MISSING: No data at all or all records have NULL values (highest priority)
    - PARTIALLY_MISSING: Some records have NULL values
    - COMPLETE: No gaps, all data present (skip backfill)
    """
    FULLY_MISSING = 1      # No data at all (highest priority)
    PARTIALLY_MISSING = 2  # Some columns NULL
    COMPLETE = 3           # No gaps (skip)

    def __str__(self):
        return self.name.lower()

    def __repr__(self):
        return f"GapPriority.{self.name}"


@dataclass
class TickerGapInfo:
    """
    Metadata for a single ticker's data gaps

    Contains all information needed to make backfill decisions:
    - Ticker identification (ticker, name, region)
    - Gap metrics (missing_count, total_count)
    - Priority classification
    - External identifiers (corp_code for DART API)

    Example:
        gap_info = TickerGapInfo(
            ticker='005930',
            name='삼성전자',
            region='KR',
            corp_code='00126380',
            listing_date=date(1975, 6, 11),
            missing_count=3,
            total_count=3,
            priority=GapPriority.FULLY_MISSING,
            target_columns=['capital_stock', 'capital_surplus']
        )
    """
    ticker: str
    name: str
    region: str
    corp_code: Optional[str] = None
    listing_date: Optional[date] = None
    missing_count: int = 0      # Number of records with NULL values
    total_count: int = 0        # Total records in backfill period
    priority: GapPriority = GapPriority.COMPLETE
    target_columns: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate data consistency"""
        if self.missing_count > self.total_count:
            raise ValueError(
                f"missing_count ({self.missing_count}) cannot exceed "
                f"total_count ({self.total_count})"
            )

    @property
    def gap_percentage(self) -> float:
        """Calculate gap percentage"""
        if self.total_count == 0:
            return 100.0
        return (self.missing_count / self.total_count) * 100

    @property
    def needs_backfill(self) -> bool:
        """Check if ticker needs backfill"""
        return self.priority in (GapPriority.FULLY_MISSING, GapPriority.PARTIALLY_MISSING)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'ticker': self.ticker,
            'name': self.name,
            'region': self.region,
            'corp_code': self.corp_code,
            'listing_date': self.listing_date.isoformat() if self.listing_date else None,
            'missing_count': self.missing_count,
            'total_count': self.total_count,
            'gap_percentage': round(self.gap_percentage, 2),
            'priority': str(self.priority),
            'target_columns': self.target_columns,
            'needs_backfill': self.needs_backfill
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TickerGapInfo':
        """Create from dictionary (deserialization)"""
        # Convert listing_date string to date object
        listing_date = None
        if data.get('listing_date'):
            from datetime import datetime
            listing_date = datetime.fromisoformat(data['listing_date']).date()

        # Convert priority string to enum
        priority = GapPriority[data['priority'].upper()]

        return cls(
            ticker=data['ticker'],
            name=data['name'],
            region=data['region'],
            corp_code=data.get('corp_code'),
            listing_date=listing_date,
            missing_count=data['missing_count'],
            total_count=data['total_count'],
            priority=priority,
            target_columns=data.get('target_columns', [])
        )


@dataclass
class GapAnalysisResult:
    """
    Result of gap analysis with prioritized ticker lists

    Organizes tickers by priority for efficient backfill targeting:
    - fully_missing: Highest priority (no data at all)
    - partially_missing: Medium priority (some gaps)
    - complete: Skip backfill (no gaps)

    Example:
        result = GapAnalysisResult(
            fully_missing=[ticker1, ticker2],
            partially_missing=[ticker3],
            complete=[ticker4, ticker5],
            total_analyzed=5,
            analysis_time_sec=1.87
        )

        # Get tickers needing backfill
        targets = result.get_backfill_targets()
        print(f"{len(targets)} tickers need backfill")

        # Get efficiency metrics
        summary = result.get_summary()
        print(f"API calls saved: {summary['complete']} ({summary['complete']/summary['total_analyzed']*100:.1f}%)")
    """
    fully_missing: List[TickerGapInfo] = field(default_factory=list)
    partially_missing: List[TickerGapInfo] = field(default_factory=list)
    complete: List[TickerGapInfo] = field(default_factory=list)
    total_analyzed: int = 0
    analysis_time_sec: float = 0.0

    def __post_init__(self):
        """Validate result consistency"""
        calculated_total = len(self.fully_missing) + len(self.partially_missing) + len(self.complete)
        if self.total_analyzed != calculated_total:
            raise ValueError(
                f"total_analyzed ({self.total_analyzed}) does not match "
                f"sum of categorized tickers ({calculated_total})"
            )

    def get_backfill_targets(
        self,
        priority: Optional[GapPriority] = None
    ) -> List[TickerGapInfo]:
        """
        Get tickers needing backfill by priority

        Args:
            priority: Filter by specific priority (None = all needing backfill)

        Returns:
            List of tickers needing backfill

        Example:
            # Get only fully missing tickers
            high_priority = result.get_backfill_targets(GapPriority.FULLY_MISSING)

            # Get all tickers needing backfill (default)
            all_targets = result.get_backfill_targets()
        """
        if priority == GapPriority.FULLY_MISSING:
            return self.fully_missing
        elif priority == GapPriority.PARTIALLY_MISSING:
            return self.partially_missing
        elif priority == GapPriority.COMPLETE:
            return self.complete
        else:
            # Return all needing backfill (excluding complete)
            return self.fully_missing + self.partially_missing

    def get_summary(self) -> Dict[str, Any]:
        """
        Get gap analysis summary statistics

        Returns:
            Dictionary with summary metrics:
            - total_analyzed: Total tickers analyzed
            - fully_missing: Count of tickers with no data
            - partially_missing: Count of tickers with partial data
            - complete: Count of tickers with complete data (will skip)
            - needs_backfill: Total tickers needing backfill
            - api_calls_saved: Number of API calls saved by skipping complete tickers
            - efficiency_gain_pct: Percentage of API calls saved
            - analysis_time_sec: Time taken for gap analysis
        """
        needs_backfill = len(self.fully_missing) + len(self.partially_missing)
        api_calls_saved = len(self.complete)
        efficiency_gain_pct = (api_calls_saved / self.total_analyzed * 100) if self.total_analyzed > 0 else 0

        return {
            'total_analyzed': self.total_analyzed,
            'fully_missing': len(self.fully_missing),
            'partially_missing': len(self.partially_missing),
            'complete': len(self.complete),
            'needs_backfill': needs_backfill,
            'api_calls_saved': api_calls_saved,
            'efficiency_gain_pct': round(efficiency_gain_pct, 2),
            'analysis_time_sec': round(self.analysis_time_sec, 2)
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'fully_missing': [t.to_dict() for t in self.fully_missing],
            'partially_missing': [t.to_dict() for t in self.partially_missing],
            'complete': [t.to_dict() for t in self.complete],
            'total_analyzed': self.total_analyzed,
            'analysis_time_sec': self.analysis_time_sec,
            'summary': self.get_summary()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GapAnalysisResult':
        """Create from dictionary (deserialization)"""
        return cls(
            fully_missing=[TickerGapInfo.from_dict(t) for t in data['fully_missing']],
            partially_missing=[TickerGapInfo.from_dict(t) for t in data['partially_missing']],
            complete=[TickerGapInfo.from_dict(t) for t in data['complete']],
            total_analyzed=data['total_analyzed'],
            analysis_time_sec=data['analysis_time_sec']
        )


@dataclass
class BackfillStats:
    """
    Backfill execution statistics

    Tracks all metrics during backfill execution:
    - Ticker processing counts (processed, success, failed, skipped)
    - Database operations (inserts, updates)
    - API metrics (calls, rate limiting)
    - Execution time
    - Error messages

    Example:
        stats = BackfillStats()
        stats.tickers_processed += 1
        stats.tickers_success += 1
        stats.api_calls += 1
        stats.records_inserted += 3

        print(stats.to_dict())
    """
    tickers_processed: int = 0
    tickers_success: int = 0
    tickers_failed: int = 0
    tickers_skipped: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    api_calls: int = 0
    execution_time_sec: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging and serialization"""
        return {
            'tickers_processed': self.tickers_processed,
            'tickers_success': self.tickers_success,
            'tickers_failed': self.tickers_failed,
            'tickers_skipped': self.tickers_skipped,
            'records_inserted': self.records_inserted,
            'records_updated': self.records_updated,
            'api_calls': self.api_calls,
            'execution_time_sec': round(self.execution_time_sec, 2),
            'errors': self.errors
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BackfillStats':
        """Create from dictionary (deserialization)"""
        return cls(
            tickers_processed=data.get('tickers_processed', 0),
            tickers_success=data.get('tickers_success', 0),
            tickers_failed=data.get('tickers_failed', 0),
            tickers_skipped=data.get('tickers_skipped', 0),
            records_inserted=data.get('records_inserted', 0),
            records_updated=data.get('records_updated', 0),
            api_calls=data.get('api_calls', 0),
            execution_time_sec=data.get('execution_time_sec', 0.0)
        )

    def merge(self, other: 'BackfillStats') -> 'BackfillStats':
        """
        Merge with another BackfillStats instance

        Useful for aggregating stats from multiple batches or parallel executions.

        Args:
            other: Another BackfillStats instance to merge

        Returns:
            New BackfillStats with combined values
        """
        return BackfillStats(
            tickers_processed=self.tickers_processed + other.tickers_processed,
            tickers_success=self.tickers_success + other.tickers_success,
            tickers_failed=self.tickers_failed + other.tickers_failed,
            tickers_skipped=self.tickers_skipped + other.tickers_skipped,
            records_inserted=self.records_inserted + other.records_inserted,
            records_updated=self.records_updated + other.records_updated,
            api_calls=self.api_calls + other.api_calls,
            execution_time_sec=self.execution_time_sec + other.execution_time_sec
        )


@dataclass
class BackfillResult:
    """
    Result of backfill execution

    Combines gap analysis results with execution statistics for
    comprehensive reporting and monitoring.

    Example:
        result = BackfillResult(
            gap_analysis=gap_result,
            backfill_stats=stats,
            checkpoint_file='log/checkpoint_20251111.json',
            success=True
        )

        summary = result.get_summary()
        print(f"Backfill {'succeeded' if result.success else 'failed'}")
        print(f"API calls saved: {summary['gap_analysis']['api_calls_saved']}")
    """
    gap_analysis: Optional[GapAnalysisResult]
    backfill_stats: BackfillStats
    checkpoint_file: Optional[str]
    success: bool
    error_message: Optional[str] = None

    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive summary of backfill execution

        Returns:
            Dictionary with complete execution summary including:
            - gap_analysis: Gap analysis metrics
            - backfill_stats: Execution statistics
            - checkpoint_file: Path to checkpoint file
            - success: Execution success status
            - error_message: Error details if failed
        """
        return {
            'gap_analysis': self.gap_analysis.get_summary() if self.gap_analysis else None,
            'backfill_stats': self.backfill_stats.to_dict(),
            'checkpoint_file': self.checkpoint_file,
            'success': self.success,
            'error_message': self.error_message
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'gap_analysis': self.gap_analysis.to_dict() if self.gap_analysis else None,
            'backfill_stats': self.backfill_stats.to_dict(),
            'checkpoint_file': self.checkpoint_file,
            'success': self.success,
            'error_message': self.error_message
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BackfillResult':
        """Create from dictionary (deserialization)"""
        gap_analysis = None
        if data.get('gap_analysis'):
            gap_analysis = GapAnalysisResult.from_dict(data['gap_analysis'])

        return cls(
            gap_analysis=gap_analysis,
            backfill_stats=BackfillStats.from_dict(data['backfill_stats']),
            checkpoint_file=data.get('checkpoint_file'),
            success=data['success'],
            error_message=data.get('error_message')
        )


# Example usage and testing
if __name__ == '__main__':
    """Example usage of data structures"""
    from datetime import date
    import json

    # Example 1: TickerGapInfo
    print("=" * 80)
    print("Example 1: TickerGapInfo")
    print("=" * 80)

    ticker_gap = TickerGapInfo(
        ticker='005930',
        name='삼성전자',
        region='KR',
        corp_code='00126380',
        listing_date=date(1975, 6, 11),
        missing_count=3,
        total_count=3,
        priority=GapPriority.FULLY_MISSING,
        target_columns=['capital_stock', 'capital_surplus', 'retained_earnings']
    )

    print(f"Ticker: {ticker_gap.ticker} ({ticker_gap.name})")
    print(f"Gap: {ticker_gap.missing_count}/{ticker_gap.total_count} ({ticker_gap.gap_percentage:.1f}%)")
    print(f"Priority: {ticker_gap.priority}")
    print(f"Needs backfill: {ticker_gap.needs_backfill}")
    print(f"\nSerialized:")
    print(json.dumps(ticker_gap.to_dict(), indent=2, ensure_ascii=False))

    # Example 2: GapAnalysisResult
    print("\n" + "=" * 80)
    print("Example 2: GapAnalysisResult")
    print("=" * 80)

    fully_missing_tickers = [
        TickerGapInfo(
            ticker='005930',
            name='삼성전자',
            region='KR',
            missing_count=3,
            total_count=3,
            priority=GapPriority.FULLY_MISSING,
            target_columns=['capital_stock']
        ),
        TickerGapInfo(
            ticker='000660',
            name='SK하이닉스',
            region='KR',
            missing_count=3,
            total_count=3,
            priority=GapPriority.FULLY_MISSING,
            target_columns=['capital_stock']
        )
    ]

    partially_missing_tickers = [
        TickerGapInfo(
            ticker='035420',
            name='NAVER',
            region='KR',
            missing_count=1,
            total_count=3,
            priority=GapPriority.PARTIALLY_MISSING,
            target_columns=['capital_stock']
        )
    ]

    complete_tickers = [
        TickerGapInfo(
            ticker='051910',
            name='LG화학',
            region='KR',
            missing_count=0,
            total_count=3,
            priority=GapPriority.COMPLETE,
            target_columns=['capital_stock']
        )
    ]

    gap_result = GapAnalysisResult(
        fully_missing=fully_missing_tickers,
        partially_missing=partially_missing_tickers,
        complete=complete_tickers,
        total_analyzed=4,
        analysis_time_sec=1.87
    )

    print(f"Gap Analysis Summary:")
    summary = gap_result.get_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")

    print(f"\nBackfill Targets: {len(gap_result.get_backfill_targets())} tickers")
    print(f"API Calls Saved: {len(gap_result.complete)} ({summary['efficiency_gain_pct']:.1f}%)")

    # Example 3: BackfillResult
    print("\n" + "=" * 80)
    print("Example 3: BackfillResult")
    print("=" * 80)

    backfill_stats = BackfillStats(
        tickers_processed=3,
        tickers_success=3,
        tickers_failed=0,
        records_inserted=9,
        api_calls=3,
        execution_time_sec=324.5
    )

    result = BackfillResult(
        gap_analysis=gap_result,
        backfill_stats=backfill_stats,
        checkpoint_file='log/checkpoint_20251111.json',
        success=True
    )

    print(f"Backfill Execution Summary:")
    result_summary = result.get_summary()
    print(json.dumps(result_summary, indent=2, ensure_ascii=False))
