"""
Unit tests for GapAnalyzer component

Tests gap detection SQL generation, priority classification,
and end-to-end gap analysis workflow.

Author: Quant Platform Development Team
Date: 2025-11-11
"""

import pytest
from datetime import date
from unittest.mock import Mock, MagicMock
from modules.backfill.gap_analyzer import GapAnalyzer
from modules.backfill.data_structures import GapPriority, TickerGapInfo, GapAnalysisResult
from modules.db_manager_postgres import PostgresDatabaseManager


class TestGapAnalyzer:
    """Unit tests for GapAnalyzer component"""

    @pytest.fixture
    def mock_db(self):
        """Mock PostgresDatabaseManager"""
        db = Mock(spec=PostgresDatabaseManager)
        return db

    @pytest.fixture
    def gap_analyzer(self, mock_db):
        """GapAnalyzer instance with mocked database"""
        return GapAnalyzer(mock_db)

    # ============================================================================
    # SQL Query Generation Tests
    # ============================================================================

    def test_gap_query_single_column(self, gap_analyzer):
        """Test query generation for single target column"""
        query, params = gap_analyzer.get_gap_query(
            table='ticker_fundamentals',
            target_columns=['capital_stock'],
            filters={
                'region': 'KR',
                'asset_type': 'STOCK',
                'backfill_start_date': date(2022, 1, 1),
                'limit': None
            }
        )

        # Verify NULL condition
        assert 'tf.capital_stock IS NULL' in query
        assert 'FILTER' in query
        assert 'COUNT(tf.id)' in query

        # Verify parameters
        assert params['region'] == 'KR'
        assert params['asset_type'] == 'STOCK'
        assert params['backfill_start_date'] == date(2022, 1, 1)
        assert 'limit' not in params  # limit is None

        # Verify SQL structure
        assert 'WITH ticker_gaps AS' in query
        assert 'LEFT JOIN ticker_fundamentals tf' in query
        assert 'GROUP BY' in query
        assert 'ORDER BY priority' in query

    def test_gap_query_multiple_columns(self, gap_analyzer):
        """Test query generation for multiple target columns"""
        query, params = gap_analyzer.get_gap_query(
            table='ticker_fundamentals',
            target_columns=['capital_stock', 'capital_surplus', 'retained_earnings'],
            filters={
                'region': 'KR',
                'asset_type': 'STOCK',
                'backfill_start_date': date(2022, 1, 1),
                'limit': None
            }
        )

        # Verify all columns in NULL condition
        assert 'tf.capital_stock IS NULL' in query
        assert 'tf.capital_surplus IS NULL' in query
        assert 'tf.retained_earnings IS NULL' in query

        # Verify OR logic between columns
        assert query.count(' OR ') >= 2  # At least 2 ORs for 3 columns

        # Verify single FILTER clause (all columns in one condition)
        assert query.count('FILTER') == 1

    def test_gap_query_with_limit(self, gap_analyzer):
        """Test query generation with LIMIT clause"""
        query, params = gap_analyzer.get_gap_query(
            table='ticker_fundamentals',
            target_columns=['capital_stock'],
            filters={
                'region': 'KR',
                'asset_type': 'STOCK',
                'backfill_start_date': date(2022, 1, 1),
                'limit': 100
            }
        )

        # Verify LIMIT in query
        assert 'LIMIT %(limit)s' in query or 'LIMIT' in query

        # Verify limit parameter
        assert params['limit'] == 100

    def test_gap_query_without_backfill_date(self, gap_analyzer):
        """Test query generation without backfill_start_date"""
        query, params = gap_analyzer.get_gap_query(
            table='ticker_fundamentals',
            target_columns=['capital_stock'],
            filters={
                'region': 'KR',
                'asset_type': 'STOCK',
                'backfill_start_date': None,
                'limit': None
            }
        )

        # Verify no date filter in parameters
        assert 'backfill_start_date' not in params

        # Verify basic structure still present
        assert 'ticker_gaps' in query
        assert params['region'] == 'KR'
        assert params['asset_type'] == 'STOCK'

    def test_gap_query_priority_classification(self, gap_analyzer):
        """Test priority classification logic in SQL"""
        query, params = gap_analyzer.get_gap_query(
            table='ticker_fundamentals',
            target_columns=['capital_stock'],
            filters={
                'region': 'KR',
                'asset_type': 'STOCK',
                'backfill_start_date': date(2022, 1, 1),
                'limit': None
            }
        )

        # Verify priority CASE logic
        assert 'CASE' in query
        assert 'WHEN total_count = 0 THEN 1' in query  # FULLY_MISSING
        assert 'WHEN missing_count = total_count THEN 1' in query  # FULLY_MISSING
        assert 'WHEN missing_count > 0 THEN 2' in query  # PARTIALLY_MISSING
        assert 'ELSE 3' in query  # COMPLETE

    # ============================================================================
    # Priority Classification Tests
    # ============================================================================

    def test_classify_gap_priority_fully_missing_no_data(self):
        """Test FULLY_MISSING classification when no data exists"""
        priority = GapAnalyzer.classify_gap_priority(
            missing_count=0,
            total_count=0
        )
        assert priority == GapPriority.FULLY_MISSING

    def test_classify_gap_priority_fully_missing_all_null(self):
        """Test FULLY_MISSING classification when all values are NULL"""
        priority = GapAnalyzer.classify_gap_priority(
            missing_count=10,
            total_count=10
        )
        assert priority == GapPriority.FULLY_MISSING

    def test_classify_gap_priority_partially_missing(self):
        """Test PARTIALLY_MISSING classification"""
        priority = GapAnalyzer.classify_gap_priority(
            missing_count=5,
            total_count=10
        )
        assert priority == GapPriority.PARTIALLY_MISSING

    def test_classify_gap_priority_complete(self):
        """Test COMPLETE classification"""
        priority = GapAnalyzer.classify_gap_priority(
            missing_count=0,
            total_count=10
        )
        assert priority == GapPriority.COMPLETE

    def test_classify_gap_priority_edge_cases(self):
        """Test edge cases for priority classification"""
        # Single missing record
        assert GapAnalyzer.classify_gap_priority(1, 10) == GapPriority.PARTIALLY_MISSING

        # Almost complete (9/10 missing)
        assert GapAnalyzer.classify_gap_priority(9, 10) == GapPriority.PARTIALLY_MISSING

        # Fully missing (100/100)
        assert GapAnalyzer.classify_gap_priority(100, 100) == GapPriority.FULLY_MISSING

    # ============================================================================
    # Gap Analysis Workflow Tests
    # ============================================================================

    def test_analyze_gaps_empty_result(self, gap_analyzer, mock_db):
        """Test gap analysis with no results"""
        # Mock database to return empty list
        mock_db.execute_query.return_value = []

        result = gap_analyzer.analyze_gaps(
            table='ticker_fundamentals',
            target_columns=['capital_stock'],
            region='KR',
            backfill_start_date=date(2022, 1, 1)
        )

        # Verify result structure
        assert isinstance(result, GapAnalysisResult)
        assert len(result.fully_missing) == 0
        assert len(result.partially_missing) == 0
        assert len(result.complete) == 0
        assert result.total_analyzed == 0

        # Verify database query was called
        mock_db.execute_query.assert_called_once()

    def test_analyze_gaps_mixed_results(self, gap_analyzer, mock_db):
        """Test gap analysis with mixed priority results"""
        # Mock database response with different priorities
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

        result = gap_analyzer.analyze_gaps(
            table='ticker_fundamentals',
            target_columns=['capital_stock'],
            region='KR',
            backfill_start_date=date(2022, 1, 1)
        )

        # Verify classification
        assert len(result.fully_missing) == 1
        assert len(result.partially_missing) == 1
        assert len(result.complete) == 1
        assert result.total_analyzed == 3

        # Verify ticker info
        assert result.fully_missing[0].ticker == '005930'
        assert result.partially_missing[0].ticker == '000660'
        assert result.complete[0].ticker == '005380'

        # Verify priorities
        assert result.fully_missing[0].priority == GapPriority.FULLY_MISSING
        assert result.partially_missing[0].priority == GapPriority.PARTIALLY_MISSING
        assert result.complete[0].priority == GapPriority.COMPLETE

    def test_analyze_gaps_backfill_targets(self, gap_analyzer, mock_db):
        """Test get_backfill_targets() excludes COMPLETE tickers"""
        mock_db.execute_query.return_value = [
            {
                'ticker': '005930',
                'name': 'Samsung',
                'listing_date': None,
                'corp_code': None,
                'missing_count': 10,
                'total_count': 10,
                'priority': 1
            },
            {
                'ticker': '000660',
                'name': 'SK Hynix',
                'listing_date': None,
                'corp_code': None,
                'missing_count': 5,
                'total_count': 10,
                'priority': 2
            },
            {
                'ticker': '005380',
                'name': 'Hyundai',
                'listing_date': None,
                'corp_code': None,
                'missing_count': 0,
                'total_count': 10,
                'priority': 3
            }
        ]

        result = gap_analyzer.analyze_gaps(
            table='ticker_fundamentals',
            target_columns=['capital_stock'],
            region='KR',
            backfill_start_date=date(2022, 1, 1)
        )

        # Get backfill targets (should exclude COMPLETE)
        targets = result.get_backfill_targets()
        assert len(targets) == 2
        assert targets[0].ticker == '005930'
        assert targets[1].ticker == '000660'

    def test_analyze_gaps_summary(self, gap_analyzer, mock_db):
        """Test get_summary() calculates correct metrics"""
        mock_db.execute_query.return_value = [
            {'ticker': '005930', 'name': 'Samsung', 'listing_date': None,
             'corp_code': None, 'missing_count': 10, 'total_count': 10, 'priority': 1},
            {'ticker': '000660', 'name': 'SK Hynix', 'listing_date': None,
             'corp_code': None, 'missing_count': 5, 'total_count': 10, 'priority': 2},
            {'ticker': '005380', 'name': 'Hyundai', 'listing_date': None,
             'corp_code': None, 'missing_count': 0, 'total_count': 10, 'priority': 3},
            {'ticker': '035720', 'name': 'Kakao', 'listing_date': None,
             'corp_code': None, 'missing_count': 0, 'total_count': 10, 'priority': 3},
        ]

        result = gap_analyzer.analyze_gaps(
            table='ticker_fundamentals',
            target_columns=['capital_stock'],
            region='KR',
            backfill_start_date=date(2022, 1, 1)
        )

        summary = result.get_summary()

        # Verify counts
        assert summary['total_analyzed'] == 4
        assert summary['fully_missing'] == 1
        assert summary['partially_missing'] == 1
        assert summary['complete'] == 2
        assert summary['needs_backfill'] == 2

        # Verify efficiency metrics
        assert summary['api_calls_saved'] == 2
        assert summary['efficiency_gain_pct'] == 50.0  # 2/4 = 50%

    def test_analyze_gaps_performance(self, gap_analyzer, mock_db):
        """Test that analysis_time_sec is recorded"""
        mock_db.execute_query.return_value = []

        result = gap_analyzer.analyze_gaps(
            table='ticker_fundamentals',
            target_columns=['capital_stock'],
            region='KR',
            backfill_start_date=date(2022, 1, 1)
        )

        # Verify timing is recorded
        assert hasattr(result, 'analysis_time_sec')
        assert result.analysis_time_sec >= 0
        assert result.analysis_time_sec < 1.0  # Should be fast with mocked DB

    def test_analyze_gaps_with_limit(self, gap_analyzer, mock_db):
        """Test gap analysis with limit parameter"""
        mock_db.execute_query.return_value = [
            {'ticker': '005930', 'name': 'Samsung', 'listing_date': None,
             'corp_code': None, 'missing_count': 10, 'total_count': 10, 'priority': 1}
        ]

        result = gap_analyzer.analyze_gaps(
            table='ticker_fundamentals',
            target_columns=['capital_stock'],
            region='KR',
            backfill_start_date=date(2022, 1, 1),
            limit=10
        )

        # Verify query was called with limit in parameters
        call_args = mock_db.execute_query.call_args
        query, params = call_args[0]
        assert params['limit'] == 10

    def test_analyze_gaps_exception_handling(self, gap_analyzer, mock_db):
        """Test exception handling during query execution"""
        # Mock database to raise exception
        mock_db.execute_query.side_effect = Exception("Database connection failed")

        with pytest.raises(Exception) as exc_info:
            gap_analyzer.analyze_gaps(
                table='ticker_fundamentals',
                target_columns=['capital_stock'],
                region='KR',
                backfill_start_date=date(2022, 1, 1)
            )

        assert "Database connection failed" in str(exc_info.value)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
