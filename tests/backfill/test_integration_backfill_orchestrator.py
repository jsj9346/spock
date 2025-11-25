"""
Integration tests for BackfillOrchestrator

Tests the complete 2-phase backfill workflow with all components:
- GapAnalyzer
- BackfillOrchestrator
- EquityBackfillExecutor
- ListingDateBackfillExecutor

Author: Quant Platform Development Team
Date: 2025-11-11
"""

import pytest
from datetime import date
from unittest.mock import Mock, MagicMock, patch
from modules.backfill import (
    BackfillOrchestrator,
    GapAnalyzer,
    EquityBackfillExecutor,
    ListingDateBackfillExecutor,
    GapPriority,
    TickerGapInfo
)
from modules.db_manager_postgres import PostgresDatabaseManager


class TestBackfillOrchestratorIntegration:
    """Integration tests for BackfillOrchestrator workflow"""

    @pytest.fixture
    def mock_db(self):
        """Mock PostgresDatabaseManager"""
        db = Mock(spec=PostgresDatabaseManager)
        return db

    @pytest.fixture
    def gap_analyzer(self, mock_db):
        """GapAnalyzer instance with mocked database"""
        return GapAnalyzer(mock_db)

    @pytest.fixture
    def orchestrator(self, mock_db, gap_analyzer):
        """BackfillOrchestrator instance"""
        return BackfillOrchestrator(mock_db, gap_analyzer, dry_run=True)

    # ============================================================================
    # Initialization Tests
    # ============================================================================

    def test_orchestrator_initialization(self, mock_db):
        """Test BackfillOrchestrator initialization"""
        orchestrator = BackfillOrchestrator(mock_db, dry_run=True)

        assert orchestrator.db == mock_db
        assert orchestrator.dry_run == True
        assert orchestrator.gap_analyzer is not None
        assert isinstance(orchestrator.gap_analyzer, GapAnalyzer)

    def test_orchestrator_with_custom_gap_analyzer(self, mock_db, gap_analyzer):
        """Test BackfillOrchestrator with custom GapAnalyzer"""
        orchestrator = BackfillOrchestrator(mock_db, gap_analyzer, dry_run=False)

        assert orchestrator.gap_analyzer == gap_analyzer
        assert orchestrator.dry_run == False

    # ============================================================================
    # Executor Factory Tests
    # ============================================================================

    def test_get_executor_equity(self, orchestrator):
        """Test executor factory returns EquityBackfillExecutor for equity type"""
        executor = orchestrator._get_backfill_executor('equity')

        assert isinstance(executor, EquityBackfillExecutor)
        assert executor.dry_run == orchestrator.dry_run

    def test_get_executor_listing_date(self, orchestrator):
        """Test executor factory returns ListingDateBackfillExecutor for listing_date type"""
        executor = orchestrator._get_backfill_executor('listing_date')

        assert isinstance(executor, ListingDateBackfillExecutor)
        assert executor.dry_run == orchestrator.dry_run

    def test_get_executor_unknown_type(self, orchestrator):
        """Test executor factory raises error for unknown type"""
        with pytest.raises(ValueError) as exc_info:
            orchestrator._get_backfill_executor('unknown_type')

        assert "Unknown backfill type" in str(exc_info.value)

    # ============================================================================
    # DRY RUN Workflow Tests
    # ============================================================================

    def test_execute_backfill_dry_run_empty_gaps(self, orchestrator, mock_db):
        """Test dry run with no gaps (all tickers complete)"""
        # Mock gap analysis to return no gaps
        mock_db.execute_query.return_value = []

        result = orchestrator.execute_backfill(
            backfill_type='equity',
            target_columns=['capital_stock'],
            region='KR',
            limit=10
        )

        assert result.success == True
        assert result.gap_analysis.total_analyzed == 0
        assert result.backfill_stats.tickers_processed == 0

    def test_execute_backfill_dry_run_with_gaps(self, orchestrator, mock_db):
        """Test dry run with gaps detected"""
        # Mock gap analysis to return 3 tickers with gaps
        mock_db.execute_query.return_value = [
            {
                'ticker': '005930',
                'name': 'Samsung Electronics',
                'listing_date': date(1975, 6, 11),
                'corp_code': None,
                'missing_count': 10,
                'total_count': 10,
                'priority': 1  # FULLY_MISSING
            },
            {
                'ticker': '000660',
                'name': 'SK Hynix',
                'listing_date': date(1996, 12, 26),
                'corp_code': None,
                'missing_count': 5,
                'total_count': 10,
                'priority': 2  # PARTIALLY_MISSING
            },
            {
                'ticker': '005380',
                'name': 'Hyundai Motor',
                'listing_date': date(1974, 1, 26),
                'corp_code': None,
                'missing_count': 0,
                'total_count': 10,
                'priority': 3  # COMPLETE
            }
        ]

        result = orchestrator.execute_backfill(
            backfill_type='equity',
            target_columns=['capital_stock'],
            region='KR',
            limit=10
        )

        assert result.success == True
        assert result.gap_analysis.total_analyzed == 3
        assert result.gap_analysis.fully_missing[0].ticker == '005930'
        assert result.gap_analysis.partially_missing[0].ticker == '000660'
        assert result.gap_analysis.complete[0].ticker == '005380'

        # DRY RUN mode - no actual execution
        assert result.backfill_stats.tickers_processed == 0
        assert result.backfill_stats.tickers_success == 0

    def test_execute_backfill_priority_filter(self, orchestrator, mock_db):
        """Test backfill with priority filter"""
        # Mock gap analysis
        mock_db.execute_query.return_value = [
            {'ticker': '005930', 'name': 'Samsung', 'listing_date': None,
             'corp_code': None, 'missing_count': 10, 'total_count': 10, 'priority': 1},
            {'ticker': '000660', 'name': 'SK Hynix', 'listing_date': None,
             'corp_code': None, 'missing_count': 5, 'total_count': 10, 'priority': 2},
        ]

        # Filter to FULLY_MISSING only
        result = orchestrator.execute_backfill(
            backfill_type='equity',
            target_columns=['capital_stock'],
            region='KR',
            priority=GapPriority.FULLY_MISSING,
            limit=10
        )

        assert result.success == True
        # Should only include FULLY_MISSING tickers (005930)
        targets = result.gap_analysis.get_backfill_targets(priority=GapPriority.FULLY_MISSING)
        assert len(targets) == 1
        assert targets[0].ticker == '005930'

    # ============================================================================
    # Checkpoint Path Tests
    # ============================================================================

    def test_get_checkpoint_path(self, orchestrator):
        """Test checkpoint path generation"""
        path = orchestrator._get_checkpoint_path('equity')

        assert 'log/backfill_equity_checkpoint_' in path
        assert path.endswith('.json')

    # ============================================================================
    # Error Handling Tests
    # ============================================================================

    def test_execute_backfill_gap_analysis_error(self, orchestrator, mock_db):
        """Test error handling during gap analysis"""
        # Mock database to raise exception
        mock_db.execute_query.side_effect = Exception("Database error")

        result = orchestrator.execute_backfill(
            backfill_type='equity',
            target_columns=['capital_stock'],
            region='KR'
        )

        assert result.success == False
        assert result.error_message is not None
        assert "Database error" in result.error_message

    def test_execute_backfill_invalid_backfill_type(self, orchestrator, mock_db):
        """Test error handling for invalid backfill type"""
        # Mock gap analysis to succeed
        mock_db.execute_query.return_value = [
            {'ticker': '005930', 'name': 'Samsung', 'listing_date': None,
             'corp_code': None, 'missing_count': 10, 'total_count': 10, 'priority': 1}
        ]

        # Set dry_run=False to trigger executor creation
        orchestrator.dry_run = False

        result = orchestrator.execute_backfill(
            backfill_type='invalid_type',
            target_columns=['capital_stock'],
            region='KR'
        )

        assert result.success == False
        assert result.error_message is not None
        assert "Unknown backfill type" in result.error_message


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
