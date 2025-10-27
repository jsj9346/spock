#!/usr/bin/env python3
"""
Unit Tests for Walk-Forward Validation

Tests the walk-forward validation logic including:
- Period generation
- Backtest orchestration
- Result aggregation
- Production readiness criteria

Author: Spock Quant Platform
Date: 2025-10-24
"""

import pytest
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.walk_forward_validation import (
    generate_walk_forward_periods,
    aggregate_results
)


class TestWalkForwardPeriods:
    """Test walk-forward period generation"""

    def test_generate_periods_basic(self):
        """Test basic period generation with 2-year train, 1-year test"""
        periods = generate_walk_forward_periods(
            start_date='2018-01-01',
            end_date='2024-01-01',
            train_years=2,
            test_years=1
        )

        # Should generate 2 periods (roll forward by test window):
        # Period 1: Train(2018-2019) -> Test(2020)
        # Period 2: Train(2020-2021) -> Test(2022)
        # Cannot fit period 3 because Test(2024) exceeds end_date(2024-01-01)
        assert len(periods) >= 2

        # Check first period
        train_start, train_end, test_start, test_end = periods[0]
        assert train_start == '2018-01-01'
        assert datetime.strptime(test_end, '%Y-%m-%d').year in [2020, 2021]

    def test_generate_periods_no_overlap(self):
        """Test that train and test periods don't overlap"""
        periods = generate_walk_forward_periods(
            start_date='2018-01-01',
            end_date='2024-01-01',
            train_years=2,
            test_years=1
        )

        for train_start, train_end, test_start, test_end in periods:
            # Train end should be before test start
            train_end_dt = datetime.strptime(train_end, '%Y-%m-%d')
            test_start_dt = datetime.strptime(test_start, '%Y-%m-%d')
            assert train_end_dt < test_start_dt

    def test_generate_periods_continuous(self):
        """Test that periods are continuous (no gaps)"""
        periods = generate_walk_forward_periods(
            start_date='2018-01-01',
            end_date='2024-01-01',
            train_years=2,
            test_years=1
        )

        for i in range(len(periods) - 1):
            current_test_start = periods[i][2]
            next_train_start = periods[i + 1][0]

            # Next train should start where current test started (rolling window)
            assert current_test_start == next_train_start

    def test_insufficient_data(self):
        """Test when not enough data for even one period"""
        periods = generate_walk_forward_periods(
            start_date='2023-01-01',
            end_date='2023-06-01',
            train_years=2,
            test_years=1
        )

        # Should return empty list (insufficient data)
        assert len(periods) == 0


class TestResultAggregation:
    """Test result aggregation logic"""

    def test_aggregate_all_positive(self):
        """Test aggregation when all periods are positive"""
        results = [
            {'return': 5.0, 'sharpe': 2.0, 'win_rate': 60.0, 'max_drawdown': -3.0, 'transaction_costs': 0.5},
            {'return': 3.0, 'sharpe': 1.5, 'win_rate': 55.0, 'max_drawdown': -5.0, 'transaction_costs': 0.6},
            {'return': 7.0, 'sharpe': 2.5, 'win_rate': 65.0, 'max_drawdown': -2.0, 'transaction_costs': 0.4}
        ]

        summary = aggregate_results(results, [])

        assert summary['avg_return'] == 5.0  # (5 + 3 + 7) / 3
        assert summary['min_return'] == 3.0
        assert summary['max_return'] == 7.0
        assert summary['positive_periods'] == 3
        assert summary['negative_periods'] == 0
        assert summary['avg_sharpe'] == 2.0

    def test_aggregate_mixed_results(self):
        """Test aggregation with mixed positive/negative periods"""
        results = [
            {'return': 10.0, 'sharpe': 2.0, 'win_rate': 60.0, 'max_drawdown': -5.0, 'transaction_costs': 0.5},
            {'return': -5.0, 'sharpe': -1.0, 'win_rate': 40.0, 'max_drawdown': -15.0, 'transaction_costs': 0.6},
            {'return': 3.0, 'sharpe': 1.0, 'win_rate': 50.0, 'max_drawdown': -8.0, 'transaction_costs': 0.4}
        ]

        summary = aggregate_results(results, [])

        assert summary['positive_periods'] == 2
        assert summary['negative_periods'] == 1
        assert summary['worst_max_dd'] == -15.0
        assert summary['avg_return'] == pytest.approx(2.67, rel=0.01)

    def test_aggregate_empty_results(self):
        """Test aggregation with empty results"""
        summary = aggregate_results([], [])
        assert summary == {}

    def test_aggregate_with_failures(self):
        """Test aggregation when some periods failed (None results)"""
        results = [
            {'return': 5.0, 'sharpe': 2.0, 'win_rate': 60.0, 'max_drawdown': -3.0, 'transaction_costs': 0.5},
            None,  # Failed backtest
            {'return': 3.0, 'sharpe': 1.5, 'win_rate': 55.0, 'max_drawdown': -5.0, 'transaction_costs': 0.6}
        ]

        summary = aggregate_results(results, [])

        # Should only aggregate successful results
        assert summary['num_periods'] == 3
        assert summary['successful_periods'] == 2
        assert summary['avg_return'] == 4.0  # (5 + 3) / 2


class TestProductionReadinessCriteria:
    """Test production readiness decision criteria"""

    def test_passes_all_criteria(self):
        """Test when strategy passes all production criteria"""
        results = [
            {'return': 5.0, 'sharpe': 2.0, 'win_rate': 60.0, 'max_drawdown': -3.0, 'transaction_costs': 0.5},
            {'return': 3.0, 'sharpe': 1.5, 'win_rate': 55.0, 'max_drawdown': -5.0, 'transaction_costs': 0.6},
            {'return': 7.0, 'sharpe': 2.5, 'win_rate': 65.0, 'max_drawdown': -2.0, 'transaction_costs': 0.4}
        ]

        summary = aggregate_results(results, [])

        # Check all criteria
        assert summary['avg_return'] > 0  # ✅ Positive average return
        assert summary['avg_sharpe'] > 1.0  # ✅ Sharpe > 1.0
        assert summary['avg_win_rate'] > 45  # ✅ Win rate > 45%
        assert summary['worst_max_dd'] > -20  # ✅ Max DD < 20%
        assert summary['positive_periods'] > summary['negative_periods']  # ✅ Positive majority

    def test_fails_negative_return(self):
        """Test when strategy has negative average return"""
        results = [
            {'return': -5.0, 'sharpe': -1.0, 'win_rate': 40.0, 'max_drawdown': -10.0, 'transaction_costs': 0.5},
            {'return': -3.0, 'sharpe': -0.5, 'win_rate': 45.0, 'max_drawdown': -8.0, 'transaction_costs': 0.6}
        ]

        summary = aggregate_results(results, [])

        # Should fail negative return criterion
        assert summary['avg_return'] < 0
        assert summary['negative_periods'] == 2

    def test_fails_low_sharpe(self):
        """Test when strategy has Sharpe < 1.0"""
        results = [
            {'return': 2.0, 'sharpe': 0.5, 'win_rate': 50.0, 'max_drawdown': -10.0, 'transaction_costs': 0.5},
            {'return': 1.0, 'sharpe': 0.3, 'win_rate': 48.0, 'max_drawdown': -12.0, 'transaction_costs': 0.6}
        ]

        summary = aggregate_results(results, [])

        # Positive return but poor risk-adjusted performance
        assert summary['avg_return'] > 0
        assert summary['avg_sharpe'] < 1.0  # ❌ Fails Sharpe criterion

    def test_fails_excessive_drawdown(self):
        """Test when strategy has max drawdown > -20%"""
        results = [
            {'return': 5.0, 'sharpe': 1.5, 'win_rate': 55.0, 'max_drawdown': -25.0, 'transaction_costs': 0.5},
            {'return': 3.0, 'sharpe': 1.2, 'win_rate': 52.0, 'max_drawdown': -22.0, 'transaction_costs': 0.6}
        ]

        summary = aggregate_results(results, [])

        # Good returns but excessive risk
        assert summary['avg_return'] > 0
        assert summary['avg_sharpe'] > 1.0
        assert summary['worst_max_dd'] < -20  # ❌ Fails drawdown criterion


# Integration test placeholder (requires database)
class TestWalkForwardIntegration:
    """Integration tests (requires actual data)"""

    @pytest.mark.skip(reason="Requires database and historical data")
    def test_tier3_validation(self):
        """
        Test actual Tier 3 validation with real data

        TODO: Enable this test once database is populated with sufficient history
        """
        # This would run actual walk-forward validation on Tier 3
        pass


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v', '--tb=short'])
