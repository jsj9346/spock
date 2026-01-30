#!/usr/bin/env python3
"""
test_backfill.py - Unit Tests for Backfill Module

Tests for:
- GapPriority enum
- TickerGapInfo dataclass
- GapAnalysisResult dataclass
- BackfillStats dataclass
- BackfillResult dataclass
- BackfillExecutor abstract class

Coverage target: backfill/* (~700+ Stmts)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import date, datetime
from typing import List, Tuple

from modules.backfill.data_structures import (
    GapPriority,
    TickerGapInfo,
    GapAnalysisResult,
    BackfillStats,
    BackfillResult
)


class TestGapPriority(unittest.TestCase):
    """Test GapPriority enum"""

    def test_fully_missing_value(self):
        """Test FULLY_MISSING priority value"""
        self.assertEqual(GapPriority.FULLY_MISSING.value, 1)

    def test_partially_missing_value(self):
        """Test PARTIALLY_MISSING priority value"""
        self.assertEqual(GapPriority.PARTIALLY_MISSING.value, 2)

    def test_complete_value(self):
        """Test COMPLETE priority value"""
        self.assertEqual(GapPriority.COMPLETE.value, 3)

    def test_str_representation(self):
        """Test string representation"""
        self.assertEqual(str(GapPriority.FULLY_MISSING), "fully_missing")
        self.assertEqual(str(GapPriority.PARTIALLY_MISSING), "partially_missing")
        self.assertEqual(str(GapPriority.COMPLETE), "complete")

    def test_repr_representation(self):
        """Test repr representation"""
        self.assertEqual(repr(GapPriority.FULLY_MISSING), "GapPriority.FULLY_MISSING")

    def test_priority_ordering(self):
        """Test priority ordering (lower value = higher priority)"""
        self.assertLess(GapPriority.FULLY_MISSING.value, GapPriority.PARTIALLY_MISSING.value)
        self.assertLess(GapPriority.PARTIALLY_MISSING.value, GapPriority.COMPLETE.value)


class TestTickerGapInfo(unittest.TestCase):
    """Test TickerGapInfo dataclass"""

    def test_basic_creation(self):
        """Test basic TickerGapInfo creation"""
        info = TickerGapInfo(
            ticker='005930',
            name='삼성전자',
            region='KR'
        )

        self.assertEqual(info.ticker, '005930')
        self.assertEqual(info.name, '삼성전자')
        self.assertEqual(info.region, 'KR')
        self.assertEqual(info.missing_count, 0)
        self.assertEqual(info.total_count, 0)
        self.assertEqual(info.priority, GapPriority.COMPLETE)

    def test_with_full_data(self):
        """Test TickerGapInfo with all fields"""
        info = TickerGapInfo(
            ticker='005930',
            name='삼성전자',
            region='KR',
            corp_code='00126380',
            listing_date=date(1975, 6, 11),
            missing_count=3,
            total_count=5,
            priority=GapPriority.PARTIALLY_MISSING,
            target_columns=['capital_stock', 'capital_surplus']
        )

        self.assertEqual(info.corp_code, '00126380')
        self.assertEqual(info.listing_date, date(1975, 6, 11))
        self.assertEqual(info.missing_count, 3)
        self.assertEqual(info.total_count, 5)
        self.assertEqual(len(info.target_columns), 2)

    def test_validation_missing_exceeds_total(self):
        """Test validation: missing_count cannot exceed total_count"""
        with self.assertRaises(ValueError) as ctx:
            TickerGapInfo(
                ticker='005930',
                name='삼성전자',
                region='KR',
                missing_count=10,
                total_count=5
            )

        self.assertIn('cannot exceed', str(ctx.exception))

    def test_gap_percentage_calculation(self):
        """Test gap percentage property"""
        info = TickerGapInfo(
            ticker='005930',
            name='삼성전자',
            region='KR',
            missing_count=3,
            total_count=10
        )

        self.assertAlmostEqual(info.gap_percentage, 30.0)

    def test_gap_percentage_zero_total(self):
        """Test gap percentage with zero total (100%)"""
        info = TickerGapInfo(
            ticker='005930',
            name='삼성전자',
            region='KR',
            missing_count=0,
            total_count=0
        )

        self.assertEqual(info.gap_percentage, 100.0)

    def test_needs_backfill_fully_missing(self):
        """Test needs_backfill for FULLY_MISSING"""
        info = TickerGapInfo(
            ticker='005930',
            name='삼성전자',
            region='KR',
            priority=GapPriority.FULLY_MISSING
        )

        self.assertTrue(info.needs_backfill)

    def test_needs_backfill_partially_missing(self):
        """Test needs_backfill for PARTIALLY_MISSING"""
        info = TickerGapInfo(
            ticker='005930',
            name='삼성전자',
            region='KR',
            priority=GapPriority.PARTIALLY_MISSING
        )

        self.assertTrue(info.needs_backfill)

    def test_needs_backfill_complete(self):
        """Test needs_backfill for COMPLETE"""
        info = TickerGapInfo(
            ticker='005930',
            name='삼성전자',
            region='KR',
            priority=GapPriority.COMPLETE
        )

        self.assertFalse(info.needs_backfill)

    def test_to_dict(self):
        """Test to_dict serialization"""
        info = TickerGapInfo(
            ticker='005930',
            name='삼성전자',
            region='KR',
            corp_code='00126380',
            listing_date=date(1975, 6, 11),
            missing_count=3,
            total_count=5,
            priority=GapPriority.PARTIALLY_MISSING,
            target_columns=['capital_stock']
        )

        d = info.to_dict()

        self.assertEqual(d['ticker'], '005930')
        self.assertEqual(d['name'], '삼성전자')
        self.assertEqual(d['listing_date'], '1975-06-11')
        self.assertEqual(d['gap_percentage'], 60.0)
        self.assertEqual(d['priority'], 'partially_missing')
        self.assertTrue(d['needs_backfill'])

    def test_from_dict(self):
        """Test from_dict deserialization"""
        data = {
            'ticker': '005930',
            'name': '삼성전자',
            'region': 'KR',
            'corp_code': '00126380',
            'listing_date': '1975-06-11',
            'missing_count': 3,
            'total_count': 5,
            'priority': 'partially_missing',
            'target_columns': ['capital_stock']
        }

        info = TickerGapInfo.from_dict(data)

        self.assertEqual(info.ticker, '005930')
        self.assertEqual(info.listing_date, date(1975, 6, 11))
        self.assertEqual(info.priority, GapPriority.PARTIALLY_MISSING)

    def test_from_dict_no_listing_date(self):
        """Test from_dict without listing_date"""
        data = {
            'ticker': '005930',
            'name': '삼성전자',
            'region': 'KR',
            'missing_count': 0,
            'total_count': 5,
            'priority': 'complete'
        }

        info = TickerGapInfo.from_dict(data)

        self.assertIsNone(info.listing_date)

    def test_serialization_round_trip(self):
        """Test to_dict and from_dict round trip"""
        original = TickerGapInfo(
            ticker='005930',
            name='삼성전자',
            region='KR',
            corp_code='00126380',
            listing_date=date(1975, 6, 11),
            missing_count=3,
            total_count=5,
            priority=GapPriority.PARTIALLY_MISSING,
            target_columns=['capital_stock', 'capital_surplus']
        )

        # Serialize and deserialize
        d = original.to_dict()
        restored = TickerGapInfo.from_dict(d)

        self.assertEqual(original.ticker, restored.ticker)
        self.assertEqual(original.name, restored.name)
        self.assertEqual(original.listing_date, restored.listing_date)
        self.assertEqual(original.priority, restored.priority)


class TestGapAnalysisResult(unittest.TestCase):
    """Test GapAnalysisResult dataclass"""

    def setUp(self):
        """Create sample ticker gap infos"""
        self.fully_missing = [
            TickerGapInfo(ticker='005930', name='삼성전자', region='KR',
                         missing_count=3, total_count=3, priority=GapPriority.FULLY_MISSING),
            TickerGapInfo(ticker='000660', name='SK하이닉스', region='KR',
                         missing_count=3, total_count=3, priority=GapPriority.FULLY_MISSING)
        ]
        self.partially_missing = [
            TickerGapInfo(ticker='035420', name='NAVER', region='KR',
                         missing_count=1, total_count=3, priority=GapPriority.PARTIALLY_MISSING)
        ]
        self.complete = [
            TickerGapInfo(ticker='051910', name='LG화학', region='KR',
                         missing_count=0, total_count=3, priority=GapPriority.COMPLETE)
        ]

    def test_basic_creation(self):
        """Test basic GapAnalysisResult creation"""
        result = GapAnalysisResult(
            fully_missing=self.fully_missing,
            partially_missing=self.partially_missing,
            complete=self.complete,
            total_analyzed=4,
            analysis_time_sec=1.5
        )

        self.assertEqual(len(result.fully_missing), 2)
        self.assertEqual(len(result.partially_missing), 1)
        self.assertEqual(len(result.complete), 1)
        self.assertEqual(result.total_analyzed, 4)

    def test_validation_total_mismatch(self):
        """Test validation: total must match sum of categorized"""
        with self.assertRaises(ValueError) as ctx:
            GapAnalysisResult(
                fully_missing=self.fully_missing,
                partially_missing=self.partially_missing,
                complete=self.complete,
                total_analyzed=10,  # Wrong: should be 4
                analysis_time_sec=1.5
            )

        self.assertIn('does not match', str(ctx.exception))

    def test_get_backfill_targets_all(self):
        """Test get_backfill_targets returns all needing backfill"""
        result = GapAnalysisResult(
            fully_missing=self.fully_missing,
            partially_missing=self.partially_missing,
            complete=self.complete,
            total_analyzed=4,
            analysis_time_sec=1.5
        )

        targets = result.get_backfill_targets()

        self.assertEqual(len(targets), 3)  # 2 fully + 1 partially

    def test_get_backfill_targets_fully_missing(self):
        """Test get_backfill_targets with FULLY_MISSING filter"""
        result = GapAnalysisResult(
            fully_missing=self.fully_missing,
            partially_missing=self.partially_missing,
            complete=self.complete,
            total_analyzed=4,
            analysis_time_sec=1.5
        )

        targets = result.get_backfill_targets(GapPriority.FULLY_MISSING)

        self.assertEqual(len(targets), 2)

    def test_get_backfill_targets_complete(self):
        """Test get_backfill_targets with COMPLETE filter"""
        result = GapAnalysisResult(
            fully_missing=self.fully_missing,
            partially_missing=self.partially_missing,
            complete=self.complete,
            total_analyzed=4,
            analysis_time_sec=1.5
        )

        targets = result.get_backfill_targets(GapPriority.COMPLETE)

        self.assertEqual(len(targets), 1)

    def test_get_summary(self):
        """Test get_summary statistics"""
        result = GapAnalysisResult(
            fully_missing=self.fully_missing,
            partially_missing=self.partially_missing,
            complete=self.complete,
            total_analyzed=4,
            analysis_time_sec=1.5
        )

        summary = result.get_summary()

        self.assertEqual(summary['total_analyzed'], 4)
        self.assertEqual(summary['fully_missing'], 2)
        self.assertEqual(summary['partially_missing'], 1)
        self.assertEqual(summary['complete'], 1)
        self.assertEqual(summary['needs_backfill'], 3)
        self.assertEqual(summary['api_calls_saved'], 1)
        self.assertEqual(summary['efficiency_gain_pct'], 25.0)

    def test_to_dict(self):
        """Test to_dict serialization"""
        result = GapAnalysisResult(
            fully_missing=self.fully_missing,
            partially_missing=self.partially_missing,
            complete=self.complete,
            total_analyzed=4,
            analysis_time_sec=1.5
        )

        d = result.to_dict()

        self.assertIn('fully_missing', d)
        self.assertIn('partially_missing', d)
        self.assertIn('complete', d)
        self.assertIn('summary', d)
        self.assertEqual(len(d['fully_missing']), 2)

    def test_from_dict(self):
        """Test from_dict deserialization"""
        original = GapAnalysisResult(
            fully_missing=self.fully_missing,
            partially_missing=self.partially_missing,
            complete=self.complete,
            total_analyzed=4,
            analysis_time_sec=1.5
        )

        d = original.to_dict()
        restored = GapAnalysisResult.from_dict(d)

        self.assertEqual(len(restored.fully_missing), 2)
        self.assertEqual(restored.total_analyzed, 4)


class TestBackfillStats(unittest.TestCase):
    """Test BackfillStats dataclass"""

    def test_default_creation(self):
        """Test default BackfillStats creation"""
        stats = BackfillStats()

        self.assertEqual(stats.tickers_processed, 0)
        self.assertEqual(stats.tickers_success, 0)
        self.assertEqual(stats.tickers_failed, 0)
        self.assertEqual(stats.tickers_skipped, 0)
        self.assertEqual(stats.records_inserted, 0)
        self.assertEqual(stats.records_updated, 0)
        self.assertEqual(stats.api_calls, 0)
        self.assertEqual(stats.execution_time_sec, 0.0)
        self.assertEqual(stats.errors, [])

    def test_with_values(self):
        """Test BackfillStats with values"""
        stats = BackfillStats(
            tickers_processed=100,
            tickers_success=95,
            tickers_failed=3,
            tickers_skipped=2,
            records_inserted=285,
            records_updated=10,
            api_calls=98,
            execution_time_sec=120.5,
            errors=['Error 1', 'Error 2']
        )

        self.assertEqual(stats.tickers_processed, 100)
        self.assertEqual(stats.tickers_success, 95)
        self.assertEqual(len(stats.errors), 2)

    def test_to_dict(self):
        """Test to_dict serialization"""
        stats = BackfillStats(
            tickers_processed=10,
            tickers_success=8,
            tickers_failed=2,
            execution_time_sec=15.678
        )

        d = stats.to_dict()

        self.assertEqual(d['tickers_processed'], 10)
        self.assertEqual(d['tickers_success'], 8)
        self.assertEqual(d['execution_time_sec'], 15.68)  # Rounded

    def test_from_dict(self):
        """Test from_dict deserialization"""
        data = {
            'tickers_processed': 10,
            'tickers_success': 8,
            'tickers_failed': 2,
            'execution_time_sec': 15.5
        }

        stats = BackfillStats.from_dict(data)

        self.assertEqual(stats.tickers_processed, 10)
        self.assertEqual(stats.tickers_success, 8)

    def test_merge(self):
        """Test merge two BackfillStats"""
        stats1 = BackfillStats(
            tickers_processed=50,
            tickers_success=45,
            tickers_failed=5,
            records_inserted=135,
            api_calls=50,
            execution_time_sec=60.0
        )

        stats2 = BackfillStats(
            tickers_processed=30,
            tickers_success=28,
            tickers_failed=2,
            records_inserted=84,
            api_calls=30,
            execution_time_sec=40.0
        )

        merged = stats1.merge(stats2)

        self.assertEqual(merged.tickers_processed, 80)
        self.assertEqual(merged.tickers_success, 73)
        self.assertEqual(merged.tickers_failed, 7)
        self.assertEqual(merged.records_inserted, 219)
        self.assertEqual(merged.api_calls, 80)
        self.assertEqual(merged.execution_time_sec, 100.0)


class TestBackfillResult(unittest.TestCase):
    """Test BackfillResult dataclass"""

    def setUp(self):
        """Create sample data"""
        self.gap_analysis = GapAnalysisResult(
            fully_missing=[
                TickerGapInfo(ticker='005930', name='삼성전자', region='KR',
                             missing_count=3, total_count=3, priority=GapPriority.FULLY_MISSING)
            ],
            partially_missing=[],
            complete=[],
            total_analyzed=1,
            analysis_time_sec=0.5
        )

        self.stats = BackfillStats(
            tickers_processed=1,
            tickers_success=1,
            records_inserted=3,
            api_calls=1,
            execution_time_sec=5.0
        )

    def test_success_result(self):
        """Test successful BackfillResult"""
        result = BackfillResult(
            gap_analysis=self.gap_analysis,
            backfill_stats=self.stats,
            checkpoint_file='log/checkpoint.json',
            success=True
        )

        self.assertTrue(result.success)
        self.assertIsNone(result.error_message)

    def test_failed_result(self):
        """Test failed BackfillResult"""
        result = BackfillResult(
            gap_analysis=self.gap_analysis,
            backfill_stats=self.stats,
            checkpoint_file='log/checkpoint.json',
            success=False,
            error_message='API rate limit exceeded'
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, 'API rate limit exceeded')

    def test_get_summary(self):
        """Test get_summary"""
        result = BackfillResult(
            gap_analysis=self.gap_analysis,
            backfill_stats=self.stats,
            checkpoint_file='log/checkpoint.json',
            success=True
        )

        summary = result.get_summary()

        self.assertIn('gap_analysis', summary)
        self.assertIn('backfill_stats', summary)
        self.assertIn('checkpoint_file', summary)
        self.assertTrue(summary['success'])

    def test_get_summary_no_gap_analysis(self):
        """Test get_summary without gap analysis"""
        result = BackfillResult(
            gap_analysis=None,
            backfill_stats=self.stats,
            checkpoint_file=None,
            success=True
        )

        summary = result.get_summary()

        self.assertIsNone(summary['gap_analysis'])

    def test_to_dict(self):
        """Test to_dict serialization"""
        result = BackfillResult(
            gap_analysis=self.gap_analysis,
            backfill_stats=self.stats,
            checkpoint_file='log/checkpoint.json',
            success=True
        )

        d = result.to_dict()

        self.assertIn('gap_analysis', d)
        self.assertIn('backfill_stats', d)
        self.assertTrue(d['success'])

    def test_from_dict(self):
        """Test from_dict deserialization"""
        original = BackfillResult(
            gap_analysis=self.gap_analysis,
            backfill_stats=self.stats,
            checkpoint_file='log/checkpoint.json',
            success=True
        )

        d = original.to_dict()
        restored = BackfillResult.from_dict(d)

        self.assertTrue(restored.success)
        self.assertEqual(restored.checkpoint_file, 'log/checkpoint.json')


# Parametrized tests
@pytest.mark.parametrize("priority,expected_str", [
    (GapPriority.FULLY_MISSING, "fully_missing"),
    (GapPriority.PARTIALLY_MISSING, "partially_missing"),
    (GapPriority.COMPLETE, "complete"),
])
def test_gap_priority_str(priority, expected_str):
    """Test GapPriority string conversion"""
    assert str(priority) == expected_str


@pytest.mark.parametrize("missing,total,expected_pct", [
    (0, 10, 0.0),
    (5, 10, 50.0),
    (10, 10, 100.0),
    (3, 10, 30.0),
])
def test_gap_percentage_calculations(missing, total, expected_pct):
    """Test gap percentage calculation"""
    info = TickerGapInfo(
        ticker='TEST',
        name='Test',
        region='KR',
        missing_count=missing,
        total_count=total
    )
    assert info.gap_percentage == expected_pct


@pytest.mark.parametrize("priority,needs_backfill", [
    (GapPriority.FULLY_MISSING, True),
    (GapPriority.PARTIALLY_MISSING, True),
    (GapPriority.COMPLETE, False),
])
def test_needs_backfill_by_priority(priority, needs_backfill):
    """Test needs_backfill property by priority"""
    info = TickerGapInfo(
        ticker='TEST',
        name='Test',
        region='KR',
        priority=priority
    )
    assert info.needs_backfill == needs_backfill


class TestBackfillExecutorBase(unittest.TestCase):
    """Test BackfillExecutor abstract class"""

    def test_cannot_instantiate_directly(self):
        """Test BackfillExecutor cannot be instantiated directly"""
        from modules.backfill.executor_base import BackfillExecutor

        with self.assertRaises(TypeError):
            BackfillExecutor(Mock(), dry_run=True)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases"""

    def test_empty_gap_analysis_result(self):
        """Test empty GapAnalysisResult"""
        result = GapAnalysisResult(
            fully_missing=[],
            partially_missing=[],
            complete=[],
            total_analyzed=0,
            analysis_time_sec=0.0
        )

        summary = result.get_summary()

        self.assertEqual(summary['total_analyzed'], 0)
        self.assertEqual(summary['efficiency_gain_pct'], 0)

    def test_json_serializable(self):
        """Test all dataclasses are JSON serializable"""
        info = TickerGapInfo(
            ticker='005930',
            name='삼성전자',
            region='KR',
            listing_date=date(1975, 6, 11),
            missing_count=3,
            total_count=5,
            priority=GapPriority.PARTIALLY_MISSING
        )

        # Should not raise
        json_str = json.dumps(info.to_dict())
        self.assertIsInstance(json_str, str)

        # Should deserialize back
        restored_data = json.loads(json_str)
        restored = TickerGapInfo.from_dict(restored_data)
        self.assertEqual(restored.ticker, '005930')


if __name__ == '__main__':
    unittest.main(verbosity=2)
