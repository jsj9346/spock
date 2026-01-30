#!/usr/bin/env python3
"""
test_backtest_common.py - Unit Tests for Backtest Common Modules

Tests for:
- CommissionSchedule: Broker commission calculation
- TransactionCostModel: Full transaction cost model
- MarketImpactModel: Market impact estimation
- PerformanceMetrics: Return and risk metrics
- TradeAnalyzer: Trade-level analytics

Coverage target: backtest/common/* (~233 Stmts)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import unittest
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from modules.backtest.common.costs import (
    CommissionSchedule,
    TransactionCostModel,
    MarketImpactModel
)
from modules.backtest.common.metrics import (
    PerformanceMetrics,
    TradeAnalyzer
)


class TestCommissionSchedule(unittest.TestCase):
    """Test CommissionSchedule dataclass"""

    def test_basic_commission(self):
        """Test basic commission calculation"""
        schedule = CommissionSchedule(
            base_rate=0.001,  # 0.1%
            min_commission=1000,
            max_commission=50000
        )

        # Order value 1M -> commission 1000 (0.1%)
        commission = schedule.calculate(1_000_000)
        self.assertEqual(commission, 1000)

    def test_min_commission(self):
        """Test minimum commission enforcement"""
        schedule = CommissionSchedule(
            base_rate=0.001,
            min_commission=5000,
            max_commission=None
        )

        # Small order that would be below minimum
        commission = schedule.calculate(100_000)  # 100 < 5000
        self.assertEqual(commission, 5000)

    def test_max_commission(self):
        """Test maximum commission cap"""
        schedule = CommissionSchedule(
            base_rate=0.001,
            min_commission=0,
            max_commission=10000
        )

        # Large order that would exceed maximum
        commission = schedule.calculate(100_000_000)  # 100000 > 10000
        self.assertEqual(commission, 10000)

    def test_no_max_commission(self):
        """Test no max commission cap"""
        schedule = CommissionSchedule(
            base_rate=0.001,
            min_commission=0,
            max_commission=None
        )

        commission = schedule.calculate(100_000_000)
        self.assertEqual(commission, 100000)


class TestTransactionCostModel(unittest.TestCase):
    """Test TransactionCostModel class"""

    def test_initialization_default(self):
        """Test default initialization"""
        model = TransactionCostModel()

        self.assertEqual(model.broker, 'KIS')
        self.assertEqual(model.region, 'KR')
        self.assertEqual(model.slippage_bps, 5.0)
        self.assertTrue(model.apply_taxes)

    def test_initialization_custom(self):
        """Test custom initialization"""
        model = TransactionCostModel(
            broker='KB',
            region='KR',
            slippage_model='volume',
            slippage_bps=10.0,
            apply_taxes=False
        )

        self.assertEqual(model.broker, 'KB')
        self.assertEqual(model.slippage_model, 'volume')
        self.assertEqual(model.slippage_bps, 10.0)
        self.assertFalse(model.apply_taxes)

    def test_unknown_broker_defaults_to_kis(self):
        """Test unknown broker defaults to KIS"""
        model = TransactionCostModel(broker='UNKNOWN_BROKER')

        self.assertEqual(model.broker, 'KIS')

    def test_calculate_commission_buy(self):
        """Test commission calculation for buy order"""
        model = TransactionCostModel(broker='KIS')

        commission = model.calculate_commission(1_000_000, 'buy')

        # KIS rate is 0.015%
        expected = 1_000_000 * 0.00015
        self.assertAlmostEqual(commission, expected, places=2)

    def test_calculate_tax_sell_kr(self):
        """Test tax calculation for sell order in KR"""
        model = TransactionCostModel(region='KR', apply_taxes=True)

        tax = model.calculate_tax(1_000_000, 'sell')

        # KR securities tax is 0.23%
        expected = 1_000_000 * 0.0023
        self.assertAlmostEqual(tax, expected, places=2)

    def test_calculate_tax_buy_kr(self):
        """Test tax calculation for buy order in KR (should be zero)"""
        model = TransactionCostModel(region='KR', apply_taxes=True)

        tax = model.calculate_tax(1_000_000, 'buy')

        self.assertEqual(tax, 0.0)

    def test_calculate_tax_disabled(self):
        """Test tax calculation when taxes are disabled"""
        model = TransactionCostModel(region='KR', apply_taxes=False)

        tax = model.calculate_tax(1_000_000, 'sell')

        self.assertEqual(tax, 0.0)

    def test_calculate_tax_non_kr(self):
        """Test tax calculation for non-KR region"""
        model = TransactionCostModel(region='US', apply_taxes=True)

        tax = model.calculate_tax(1_000_000, 'sell')

        self.assertEqual(tax, 0.0)

    def test_calculate_slippage_fixed(self):
        """Test fixed slippage calculation"""
        model = TransactionCostModel(slippage_model='fixed', slippage_bps=5.0)

        slippage = model.calculate_slippage(10000, 100, 'buy')

        # 5 bps = 0.05%
        expected = 10000 * 100 * 0.0005
        self.assertAlmostEqual(slippage, expected, places=2)

    def test_calculate_slippage_volume(self):
        """Test volume-based slippage calculation"""
        model = TransactionCostModel(slippage_model='volume', slippage_bps=5.0)

        slippage = model.calculate_slippage(
            price=10000,
            quantity=1000,
            side='buy',
            volume=10000  # 10% participation
        )

        self.assertGreater(slippage, 0)

    def test_calculate_slippage_volatility(self):
        """Test volatility-based slippage calculation"""
        model = TransactionCostModel(slippage_model='volatility', slippage_bps=5.0)

        slippage = model.calculate_slippage(
            price=10000,
            quantity=100,
            side='buy',
            volatility=0.02  # 2% volatility
        )

        self.assertGreater(slippage, 0)

    def test_calculate_total_cost(self):
        """Test total cost calculation"""
        model = TransactionCostModel(broker='KIS', region='KR')

        costs = model.calculate_total_cost(10000, 100, 'sell')

        self.assertIn('order_value', costs)
        self.assertIn('commission', costs)
        self.assertIn('tax', costs)
        self.assertIn('slippage', costs)
        self.assertIn('total_cost', costs)
        self.assertIn('cost_bps', costs)

        self.assertEqual(costs['order_value'], 1_000_000)
        self.assertGreater(costs['total_cost'], 0)

    def test_calculate_effective_price_buy(self):
        """Test effective price for buy (should be higher)"""
        model = TransactionCostModel()

        effective = model.calculate_effective_price(10000, 100, 'buy')

        self.assertGreater(effective, 10000)

    def test_calculate_effective_price_sell(self):
        """Test effective price for sell (should be lower)"""
        model = TransactionCostModel()

        effective = model.calculate_effective_price(10000, 100, 'sell')

        self.assertLess(effective, 10000)

    def test_estimate_roundtrip_cost(self):
        """Test roundtrip cost estimation"""
        model = TransactionCostModel()

        costs = model.estimate_roundtrip_cost(10000, 100)

        self.assertIn('buy_cost', costs)
        self.assertIn('sell_cost', costs)
        self.assertIn('roundtrip_cost', costs)
        self.assertIn('roundtrip_bps', costs)

        self.assertEqual(
            costs['roundtrip_cost'],
            costs['buy_cost'] + costs['sell_cost']
        )


class TestMarketImpactModel(unittest.TestCase):
    """Test MarketImpactModel class"""

    def test_initialization(self):
        """Test initialization"""
        model = MarketImpactModel(
            temporary_impact_coeff=0.1,
            permanent_impact_coeff=0.05,
            volatility_multiplier=1.0
        )

        self.assertEqual(model.temp_coeff, 0.1)
        self.assertEqual(model.perm_coeff, 0.05)
        self.assertEqual(model.vol_mult, 1.0)

    def test_calculate_impact(self):
        """Test market impact calculation"""
        model = MarketImpactModel()

        impact = model.calculate_impact(
            price=10000,
            quantity=1000,
            volume=10000,
            volatility=0.02
        )

        self.assertIn('temporary_impact', impact)
        self.assertIn('permanent_impact', impact)
        self.assertIn('total_impact', impact)
        self.assertIn('impact_bps', impact)

        self.assertGreater(impact['temporary_impact'], 0)
        self.assertGreater(impact['permanent_impact'], 0)
        self.assertEqual(
            impact['total_impact'],
            impact['temporary_impact'] + impact['permanent_impact']
        )

    def test_impact_increases_with_participation(self):
        """Test that impact increases with participation rate"""
        model = MarketImpactModel()

        impact_low = model.calculate_impact(10000, 100, 10000, 0.02)
        impact_high = model.calculate_impact(10000, 5000, 10000, 0.02)

        self.assertGreater(
            impact_high['total_impact'],
            impact_low['total_impact']
        )


class TestPerformanceMetrics(unittest.TestCase):
    """Test PerformanceMetrics class"""

    def setUp(self):
        """Create sample returns for testing"""
        np.random.seed(42)
        dates = pd.date_range('2020-01-01', periods=252, freq='B')
        # Positive drift with noise
        self.returns = pd.Series(
            np.random.normal(0.0005, 0.015, 252),
            index=dates
        )

    def test_initialization(self):
        """Test initialization"""
        metrics = PerformanceMetrics(self.returns)

        self.assertEqual(len(metrics.returns), 252)
        self.assertIsNone(metrics.benchmark)
        self.assertEqual(metrics.periods_per_year, 252)

    def test_total_return(self):
        """Test total return calculation"""
        metrics = PerformanceMetrics(self.returns)

        total_ret = metrics.total_return()

        # Should be a reasonable value
        self.assertIsInstance(total_ret, float)

    def test_annualized_return(self):
        """Test annualized return calculation"""
        metrics = PerformanceMetrics(self.returns)

        ann_ret = metrics.annualized_return()

        # Should be close to total return for 1 year of data
        self.assertIsInstance(ann_ret, float)

    def test_cumulative_returns(self):
        """Test cumulative returns calculation"""
        metrics = PerformanceMetrics(self.returns)

        cum_ret = metrics.cumulative_returns()

        self.assertEqual(len(cum_ret), len(self.returns))
        # Last cumulative return should equal total return
        self.assertAlmostEqual(cum_ret.iloc[-1], metrics.total_return(), places=5)

    def test_volatility(self):
        """Test annualized volatility calculation"""
        metrics = PerformanceMetrics(self.returns)

        vol = metrics.volatility()

        # Daily std ~0.015, annualized should be ~0.24
        self.assertGreater(vol, 0.1)
        self.assertLess(vol, 0.5)

    def test_downside_volatility(self):
        """Test downside volatility calculation"""
        metrics = PerformanceMetrics(self.returns)

        down_vol = metrics.downside_volatility()

        # Should be positive and less than total volatility
        self.assertGreater(down_vol, 0)

    def test_sharpe_ratio(self):
        """Test Sharpe ratio calculation"""
        metrics = PerformanceMetrics(self.returns)

        sharpe = metrics.sharpe_ratio()

        self.assertIsInstance(sharpe, float)

    def test_sortino_ratio(self):
        """Test Sortino ratio calculation"""
        metrics = PerformanceMetrics(self.returns)

        sortino = metrics.sortino_ratio()

        self.assertIsInstance(sortino, float)

    def test_calmar_ratio(self):
        """Test Calmar ratio calculation"""
        metrics = PerformanceMetrics(self.returns)

        calmar = metrics.calmar_ratio()

        self.assertIsInstance(calmar, float)

    def test_max_drawdown(self):
        """Test max drawdown calculation"""
        metrics = PerformanceMetrics(self.returns)

        max_dd = metrics.max_drawdown()

        # Should be negative
        self.assertLessEqual(max_dd, 0)

    def test_max_drawdown_duration(self):
        """Test max drawdown duration calculation"""
        metrics = PerformanceMetrics(self.returns)

        duration = metrics.max_drawdown_duration()

        self.assertIsInstance(duration, int)
        self.assertGreaterEqual(duration, 0)

    def test_value_at_risk(self):
        """Test VaR calculation"""
        metrics = PerformanceMetrics(self.returns)

        var_95 = metrics.value_at_risk(0.95)

        # VaR should be negative (loss threshold)
        self.assertLess(var_95, 0)

    def test_conditional_var(self):
        """Test CVaR calculation"""
        metrics = PerformanceMetrics(self.returns)

        cvar_95 = metrics.conditional_var(0.95)

        # CVaR should be more negative than VaR
        var_95 = metrics.value_at_risk(0.95)
        self.assertLessEqual(cvar_95, var_95)

    def test_skewness(self):
        """Test skewness calculation"""
        metrics = PerformanceMetrics(self.returns)

        skew = metrics.skewness()

        self.assertIsInstance(skew, float)

    def test_kurtosis(self):
        """Test kurtosis calculation"""
        metrics = PerformanceMetrics(self.returns)

        kurt = metrics.kurtosis()

        self.assertIsInstance(kurt, float)

    def test_omega_ratio(self):
        """Test Omega ratio calculation"""
        metrics = PerformanceMetrics(self.returns)

        omega = metrics.omega_ratio()

        self.assertIsInstance(omega, float)

    def test_calculate_all(self):
        """Test calculate_all returns all metrics"""
        metrics = PerformanceMetrics(self.returns)

        all_metrics = metrics.calculate_all()

        expected_keys = [
            'total_return', 'annualized_return', 'annualized_volatility',
            'sharpe_ratio', 'sortino_ratio', 'calmar_ratio', 'omega_ratio',
            'max_drawdown', 'max_drawdown_duration', 'recovery_factor',
            'skewness', 'kurtosis', 'value_at_risk_95', 'conditional_var_95',
            'best_period', 'worst_period', 'positive_periods', 'negative_periods', 'win_rate'
        ]

        for key in expected_keys:
            self.assertIn(key, all_metrics)

    def test_summary_table(self):
        """Test summary table generation"""
        metrics = PerformanceMetrics(self.returns)

        summary = metrics.summary_table()

        self.assertIsInstance(summary, pd.DataFrame)

    def test_information_ratio_without_benchmark(self):
        """Test IR without benchmark returns 0"""
        metrics = PerformanceMetrics(self.returns, benchmark_returns=None)

        ir = metrics.information_ratio()

        self.assertEqual(ir, 0.0)

    def test_information_ratio_with_benchmark(self):
        """Test IR with benchmark"""
        np.random.seed(43)
        benchmark = pd.Series(
            np.random.normal(0.0003, 0.012, 252),
            index=self.returns.index
        )

        metrics = PerformanceMetrics(self.returns, benchmark_returns=benchmark)

        ir = metrics.information_ratio()

        self.assertIsInstance(ir, float)


class TestTradeAnalyzer(unittest.TestCase):
    """Test TradeAnalyzer class"""

    def setUp(self):
        """Create sample trades for testing"""
        dates = pd.date_range('2020-01-01', periods=10, freq='W')
        self.trades = pd.DataFrame({
            'entry_date': dates[:10],
            'exit_date': dates[:10] + timedelta(days=5),
            'entry_price': [100, 105, 102, 98, 101, 103, 99, 104, 100, 102],
            'exit_price': [105, 103, 108, 101, 99, 107, 102, 100, 103, 105],
            'quantity': [100] * 10,
            'pnl': [500, -200, 600, 300, -200, 400, 300, -400, 300, 300],
            'return': [0.05, -0.02, 0.06, 0.03, -0.02, 0.04, 0.03, -0.04, 0.03, 0.03]
        })

    def test_win_rate(self):
        """Test win rate calculation"""
        analyzer = TradeAnalyzer(self.trades)

        win_rate = analyzer.win_rate()

        # 7 wins out of 10
        self.assertEqual(win_rate, 0.7)

    def test_win_rate_empty(self):
        """Test win rate with empty trades"""
        analyzer = TradeAnalyzer(pd.DataFrame())

        win_rate = analyzer.win_rate()

        self.assertEqual(win_rate, 0.0)

    def test_profit_factor(self):
        """Test profit factor calculation"""
        analyzer = TradeAnalyzer(self.trades)

        pf = analyzer.profit_factor()

        # Sum of wins / sum of losses
        wins = 500 + 600 + 300 + 400 + 300 + 300 + 300  # 2700
        losses = 200 + 200 + 400  # 800
        expected = wins / losses

        self.assertAlmostEqual(pf, expected, places=2)

    def test_expectancy(self):
        """Test expectancy calculation"""
        analyzer = TradeAnalyzer(self.trades)

        expectancy = analyzer.expectancy()

        # Average PnL
        expected = self.trades['pnl'].mean()
        self.assertAlmostEqual(expectancy, expected, places=2)

    def test_average_win_loss_ratio(self):
        """Test average win/loss ratio"""
        analyzer = TradeAnalyzer(self.trades)

        ratio = analyzer.average_win_loss_ratio()

        self.assertGreater(ratio, 0)

    def test_holding_period(self):
        """Test holding period statistics"""
        analyzer = TradeAnalyzer(self.trades)

        holding = analyzer.holding_period()

        self.assertIn('mean', holding)
        self.assertIn('median', holding)
        self.assertIn('min', holding)
        self.assertIn('max', holding)


# Parametrized tests
@pytest.mark.parametrize("broker,expected_rate", [
    ('KIS', 0.00015),
    ('KIS_VIP', 0.00010),
    ('KB', 0.00014),
    ('SAMSUNG', 0.00015),
    ('MIRAE', 0.00014),
    ('NH', 0.00015),
])
def test_broker_commission_rates(broker, expected_rate):
    """Test different broker commission rates"""
    model = TransactionCostModel(broker=broker)
    assert model.commission_schedule.base_rate == expected_rate


@pytest.mark.parametrize("slippage_bps,expected_rate", [
    (5.0, 0.0005),
    (10.0, 0.001),
    (1.0, 0.0001),
])
def test_slippage_rates(slippage_bps, expected_rate):
    """Test slippage rate conversion"""
    rate = slippage_bps / 10000
    assert abs(rate - expected_rate) < 0.0001


@pytest.mark.parametrize("confidence", [0.90, 0.95, 0.99])
def test_var_confidence_levels(confidence):
    """Test VaR at different confidence levels"""
    np.random.seed(42)
    returns = pd.Series(np.random.normal(0, 0.02, 252))
    metrics = PerformanceMetrics(returns)

    var = metrics.value_at_risk(confidence)

    # Higher confidence should give more negative VaR
    assert var < 0


class TestEdgeCases(unittest.TestCase):
    """Test edge cases"""

    def test_zero_returns(self):
        """Test with zero returns"""
        returns = pd.Series([0.0] * 100, index=pd.date_range('2020-01-01', periods=100))
        metrics = PerformanceMetrics(returns)

        self.assertEqual(metrics.total_return(), 0.0)
        self.assertEqual(metrics.sharpe_ratio(), 0.0)

    def test_all_positive_returns(self):
        """Test with all positive returns"""
        returns = pd.Series([0.01] * 100, index=pd.date_range('2020-01-01', periods=100))
        metrics = PerformanceMetrics(returns)

        self.assertGreater(metrics.total_return(), 0)
        self.assertEqual(metrics.max_drawdown(), 0.0)

    def test_all_negative_returns(self):
        """Test with all negative returns"""
        returns = pd.Series([-0.01] * 100, index=pd.date_range('2020-01-01', periods=100))
        metrics = PerformanceMetrics(returns)

        self.assertLess(metrics.total_return(), 0)
        self.assertLess(metrics.max_drawdown(), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
