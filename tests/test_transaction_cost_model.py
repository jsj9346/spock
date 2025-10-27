"""
Unit Tests for Transaction Cost Model

Purpose: Validate transaction cost calculations including commission, slippage, and market impact.

Test Coverage:
  - TransactionCosts dataclass
  - ZeroCostModel
  - StandardCostModel (commission, slippage, market impact)
  - Market cost profiles (KR_DEFAULT, US_DEFAULT, etc.)
  - Cost model factory function
  - Edge cases and validation

Author: Spock Development Team
"""

import pytest
import numpy as np
from modules.backtesting.transaction_cost_model import (
    TransactionCosts,
    TransactionCostModel,
    StandardCostModel,
    ZeroCostModel,
    OrderSide,
    TimeOfDay,
    MarketCostProfile,
    MARKET_COST_PROFILES,
    get_cost_model,
)


class TestTransactionCosts:
    """Test TransactionCosts dataclass."""

    def test_total_cost_calculation(self):
        """Test total cost calculation."""
        costs = TransactionCosts(
            commission=100.0,
            slippage=50.0,
            market_impact=25.0,
        )
        assert costs.total_cost == 175.0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        costs = TransactionCosts(
            commission=100.0,
            slippage=50.0,
            market_impact=25.0,
        )
        result = costs.to_dict()
        assert result == {
            'commission': 100.0,
            'slippage': 50.0,
            'market_impact': 25.0,
            'total_cost': 175.0,
        }

    def test_zero_costs(self):
        """Test zero costs."""
        costs = TransactionCosts(
            commission=0.0,
            slippage=0.0,
            market_impact=0.0,
        )
        assert costs.total_cost == 0.0


class TestZeroCostModel:
    """Test ZeroCostModel."""

    def test_calculate_costs_returns_zero(self):
        """Test that calculate_costs returns zero costs."""
        model = ZeroCostModel()
        costs = model.calculate_costs(
            ticker='AAPL',
            price=150.0,
            shares=100,
            side=OrderSide.BUY,
            time_of_day=TimeOfDay.OPEN,
            avg_daily_volume=1000000,
        )
        assert costs.commission == 0.0
        assert costs.slippage == 0.0
        assert costs.market_impact == 0.0
        assert costs.total_cost == 0.0

    def test_calculate_commission_returns_zero(self):
        """Test that calculate_commission returns zero."""
        model = ZeroCostModel()
        commission = model.calculate_commission(
            price=150.0,
            shares=100,
            side=OrderSide.BUY,
        )
        assert commission == 0.0

    def test_calculate_slippage_returns_zero(self):
        """Test that calculate_slippage returns zero."""
        model = ZeroCostModel()
        slippage = model.calculate_slippage(
            price=150.0,
            shares=100,
            side=OrderSide.BUY,
            time_of_day=TimeOfDay.REGULAR,
        )
        assert slippage == 0.0

    def test_calculate_market_impact_returns_zero(self):
        """Test that calculate_market_impact returns zero."""
        model = ZeroCostModel()
        impact = model.calculate_market_impact(
            price=150.0,
            shares=100,
            side=OrderSide.BUY,
            avg_daily_volume=1000000,
        )
        assert impact == 0.0


class TestStandardCostModel:
    """Test StandardCostModel."""

    def test_commission_calculation(self):
        """Test commission calculation (fixed percentage)."""
        model = StandardCostModel(commission_rate=0.001)  # 0.1%

        commission = model.calculate_commission(
            price=100.0,
            shares=100,
            side=OrderSide.BUY,
        )

        # Expected: 100 * 100 * 0.001 = 10.0
        assert commission == 10.0

    def test_slippage_calculation_regular_hours(self):
        """Test slippage calculation during regular hours."""
        model = StandardCostModel(slippage_bps=5.0)  # 5 bps

        slippage = model.calculate_slippage(
            price=100.0,
            shares=100,
            side=OrderSide.BUY,
            time_of_day=TimeOfDay.REGULAR,
        )

        # Expected: 100 * 100 * 0.0005 * 1.0 (regular multiplier) = 5.0
        assert slippage == 5.0

    def test_slippage_calculation_market_open(self):
        """Test slippage calculation at market open (higher multiplier)."""
        model = StandardCostModel(
            slippage_bps=5.0,
            time_of_day_multipliers={
                TimeOfDay.OPEN: 1.5,
                TimeOfDay.REGULAR: 1.0,
                TimeOfDay.CLOSE: 1.3,
            }
        )

        slippage = model.calculate_slippage(
            price=100.0,
            shares=100,
            side=OrderSide.BUY,
            time_of_day=TimeOfDay.OPEN,
        )

        # Expected: 100 * 100 * 0.0005 * 1.5 (open multiplier) = 7.5
        assert slippage == 7.5

    def test_slippage_calculation_market_close(self):
        """Test slippage calculation at market close (higher multiplier)."""
        model = StandardCostModel(
            slippage_bps=5.0,
            time_of_day_multipliers={
                TimeOfDay.OPEN: 1.5,
                TimeOfDay.REGULAR: 1.0,
                TimeOfDay.CLOSE: 1.3,
            }
        )

        slippage = model.calculate_slippage(
            price=100.0,
            shares=100,
            side=OrderSide.BUY,
            time_of_day=TimeOfDay.CLOSE,
        )

        # Expected: 100 * 100 * 0.0005 * 1.3 (close multiplier) = 6.5
        assert slippage == 6.5

    def test_market_impact_calculation(self):
        """Test market impact calculation (square root model)."""
        model = StandardCostModel(market_impact_coefficient=0.1)

        impact = model.calculate_market_impact(
            price=100.0,
            shares=1000,
            side=OrderSide.BUY,
            avg_daily_volume=1000000,
        )

        # Expected: 0.1 * (100 * 1000) * sqrt(1000 / 1000000)
        # = 0.1 * 100000 * sqrt(0.001)
        # = 0.1 * 100000 * 0.03162...
        # ≈ 316.2
        expected = 0.1 * 100000 * np.sqrt(0.001)
        assert pytest.approx(impact, rel=1e-3) == expected

    def test_market_impact_no_volume_data(self):
        """Test market impact when no volume data is available."""
        model = StandardCostModel(market_impact_coefficient=0.1)

        impact = model.calculate_market_impact(
            price=100.0,
            shares=1000,
            side=OrderSide.BUY,
            avg_daily_volume=None,
        )

        # Expected: 0.0 (no volume data)
        assert impact == 0.0

    def test_market_impact_zero_volume(self):
        """Test market impact with zero volume."""
        model = StandardCostModel(market_impact_coefficient=0.1)

        impact = model.calculate_market_impact(
            price=100.0,
            shares=1000,
            side=OrderSide.BUY,
            avg_daily_volume=0,
        )

        # Expected: 0.0 (invalid volume)
        assert impact == 0.0

    def test_calculate_costs_comprehensive(self):
        """Test comprehensive cost calculation."""
        model = StandardCostModel(
            commission_rate=0.001,  # 0.1%
            slippage_bps=5.0,       # 5 bps
            market_impact_coefficient=0.1,
        )

        costs = model.calculate_costs(
            ticker='AAPL',
            price=100.0,
            shares=1000,
            side=OrderSide.BUY,
            time_of_day=TimeOfDay.REGULAR,
            avg_daily_volume=1000000,
        )

        # Commission: 100 * 1000 * 0.001 = 100.0
        assert costs.commission == 100.0

        # Slippage: 100 * 1000 * 0.0005 * 1.0 = 50.0
        assert costs.slippage == 50.0

        # Market impact: 0.1 * 100000 * sqrt(0.001) ≈ 316.2
        expected_impact = 0.1 * 100000 * np.sqrt(0.001)
        assert pytest.approx(costs.market_impact, rel=1e-3) == expected_impact

        # Total cost
        assert pytest.approx(costs.total_cost, rel=1e-3) == 100.0 + 50.0 + expected_impact


class TestMarketCostProfiles:
    """Test market-specific cost profiles."""

    def test_kr_default_profile_exists(self):
        """Test that KR_DEFAULT profile exists."""
        assert 'KR_DEFAULT' in MARKET_COST_PROFILES

        profile = MARKET_COST_PROFILES['KR_DEFAULT']
        assert profile.market == 'KR'
        assert profile.commission_rate == 0.00015  # 0.015%
        assert profile.slippage_bps == 5.0
        assert profile.market_impact_coefficient == 0.1

    def test_kr_low_cost_profile_exists(self):
        """Test that KR_LOW_COST profile exists."""
        assert 'KR_LOW_COST' in MARKET_COST_PROFILES

        profile = MARKET_COST_PROFILES['KR_LOW_COST']
        assert profile.market == 'KR'
        assert profile.commission_rate == 0.00005  # Lower commission
        assert profile.slippage_bps == 3.0  # Lower slippage

    def test_kr_high_cost_profile_exists(self):
        """Test that KR_HIGH_COST profile exists."""
        assert 'KR_HIGH_COST' in MARKET_COST_PROFILES

        profile = MARKET_COST_PROFILES['KR_HIGH_COST']
        assert profile.market == 'KR'
        assert profile.commission_rate == 0.0003  # Higher commission
        assert profile.slippage_bps == 10.0  # Higher slippage

    def test_us_default_profile_exists(self):
        """Test that US_DEFAULT profile exists."""
        assert 'US_DEFAULT' in MARKET_COST_PROFILES

        profile = MARKET_COST_PROFILES['US_DEFAULT']
        assert profile.market == 'US'
        assert profile.commission_rate == 0.0  # Commission-free
        assert profile.slippage_bps == 2.0  # Tight spreads

    def test_profile_to_cost_model(self):
        """Test converting profile to cost model."""
        profile = MARKET_COST_PROFILES['KR_DEFAULT']
        model = profile.to_cost_model()

        assert isinstance(model, StandardCostModel)
        assert model.commission_rate == profile.commission_rate
        assert model.slippage_bps == profile.slippage_bps
        assert model.market_impact_coefficient == profile.market_impact_coefficient


class TestCostModelFactory:
    """Test cost model factory function."""

    def test_get_cost_model_kr_default(self):
        """Test getting KR_DEFAULT cost model."""
        model = get_cost_model('KR_DEFAULT')

        assert isinstance(model, StandardCostModel)
        assert model.commission_rate == 0.00015

    def test_get_cost_model_us_default(self):
        """Test getting US_DEFAULT cost model."""
        model = get_cost_model('US_DEFAULT')

        assert isinstance(model, StandardCostModel)
        assert model.commission_rate == 0.0  # Commission-free

    def test_get_cost_model_zero(self):
        """Test getting ZERO cost model."""
        model = get_cost_model('ZERO')

        assert isinstance(model, ZeroCostModel)

    def test_get_cost_model_invalid_profile(self):
        """Test getting invalid cost model raises ValueError."""
        with pytest.raises(ValueError) as excinfo:
            get_cost_model('INVALID_PROFILE')

        assert 'Unknown cost profile' in str(excinfo.value)


class TestRealWorldScenarios:
    """Test real-world trading scenarios."""

    def test_kr_stock_typical_trade(self):
        """Test typical Korean stock trade."""
        model = get_cost_model('KR_DEFAULT')

        # Buy 100 shares of Samsung (005930) at 70,000 KRW
        costs = model.calculate_costs(
            ticker='005930',
            price=70000,
            shares=100,
            side=OrderSide.BUY,
            time_of_day=TimeOfDay.REGULAR,
            avg_daily_volume=5000000,
        )

        # Commission: 70000 * 100 * 0.00015 = 1,050 KRW
        assert costs.commission == 1050.0

        # Slippage: 70000 * 100 * 0.0005 * 1.0 = 3,500 KRW
        assert costs.slippage == 3500.0

        # Market impact should be relatively small (liquid stock)
        assert costs.market_impact > 0

        # Total cost
        assert costs.total_cost > 4550.0  # Commission + slippage + some impact

    def test_us_stock_typical_trade(self):
        """Test typical US stock trade."""
        model = get_cost_model('US_DEFAULT')

        # Buy 100 shares of Apple at $150
        costs = model.calculate_costs(
            ticker='AAPL',
            price=150.0,
            shares=100,
            side=OrderSide.BUY,
            time_of_day=TimeOfDay.REGULAR,
            avg_daily_volume=50000000,
        )

        # Commission: $0 (commission-free)
        assert costs.commission == 0.0

        # Slippage: 150 * 100 * 0.0002 * 1.0 = $3.0
        assert costs.slippage == 3.0

        # Market impact should be very small (very liquid stock)
        assert costs.market_impact < 5.0

    def test_market_open_high_slippage(self):
        """Test that market open has higher slippage."""
        model = get_cost_model('KR_DEFAULT')

        # Same trade, different times
        costs_open = model.calculate_costs(
            ticker='005930',
            price=70000,
            shares=100,
            side=OrderSide.BUY,
            time_of_day=TimeOfDay.OPEN,
            avg_daily_volume=5000000,
        )

        costs_regular = model.calculate_costs(
            ticker='005930',
            price=70000,
            shares=100,
            side=OrderSide.BUY,
            time_of_day=TimeOfDay.REGULAR,
            avg_daily_volume=5000000,
        )

        # Open should have higher slippage (1.5x multiplier)
        assert costs_open.slippage > costs_regular.slippage
        assert costs_open.slippage / costs_regular.slippage == 1.5

    def test_large_order_high_market_impact(self):
        """Test that large orders have higher market impact."""
        model = get_cost_model('KR_DEFAULT')

        # Small order (100 shares)
        costs_small = model.calculate_costs(
            ticker='005930',
            price=70000,
            shares=100,
            side=OrderSide.BUY,
            time_of_day=TimeOfDay.REGULAR,
            avg_daily_volume=5000000,
        )

        # Large order (10,000 shares)
        costs_large = model.calculate_costs(
            ticker='005930',
            price=70000,
            shares=10000,
            side=OrderSide.BUY,
            time_of_day=TimeOfDay.REGULAR,
            avg_daily_volume=5000000,
        )

        # Large order should have significantly higher market impact
        assert costs_large.market_impact > costs_small.market_impact

        # Market impact formula: coefficient × notional × sqrt(shares / avg_daily_volume)
        # For 100x shares: notional increases 100x, sqrt term increases 10x
        # So total impact increases 100x * 10x = 1000x
        ratio = costs_large.market_impact / costs_small.market_impact
        assert 900.0 < ratio < 1100.0  # Allow some tolerance (should be ~1000x)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
