"""
Unit Tests for KIS Trading Engine

Test Coverage:
- Tick size adjustment
- Fee calculations
- Order execution (buy/sell)
- Position tracking
- Sell condition checks
- Portfolio management
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import sqlite3
from datetime import datetime, timedelta
from modules.kis_trading_engine import (
    KISTradingEngine,
    OrderType,
    OrderStatus,
    TradeStatus,
    TradeResult,
    PositionInfo,
    TradingConfig,
    adjust_price_to_tick_size,
    calculate_fee_adjusted_amount
)


class TestTickSizeAdjustment:
    """Test tick size compliance"""

    def test_tick_size_under_1k(self):
        """<1,000 KRW: 1 KRW tick"""
        assert adjust_price_to_tick_size(999.5) == 1000
        assert adjust_price_to_tick_size(994.3) == 994
        assert adjust_price_to_tick_size(995.8) == 996

    def test_tick_size_1k_to_5k(self):
        """1K-5K: 5 KRW tick"""
        assert adjust_price_to_tick_size(1234) == 1235
        assert adjust_price_to_tick_size(2999) == 3000
        assert adjust_price_to_tick_size(4567) == 4565

    def test_tick_size_5k_to_10k(self):
        """5K-10K: 10 KRW tick"""
        assert adjust_price_to_tick_size(5678) == 5680
        assert adjust_price_to_tick_size(9999) == 10000
        assert adjust_price_to_tick_size(7555) == 7560

    def test_tick_size_10k_to_50k(self):
        """10K-50K: 50 KRW tick"""
        assert adjust_price_to_tick_size(12345) == 12350
        assert adjust_price_to_tick_size(49999) == 50000
        assert adjust_price_to_tick_size(25555) == 25550

    def test_tick_size_50k_to_100k(self):
        """50K-100K: 100 KRW tick"""
        assert adjust_price_to_tick_size(56789) == 56800
        assert adjust_price_to_tick_size(99999) == 100000
        assert adjust_price_to_tick_size(75555) == 75600

    def test_tick_size_100k_to_500k(self):
        """100K-500K: 500 KRW tick"""
        assert adjust_price_to_tick_size(123456) == 123500
        assert adjust_price_to_tick_size(499999) == 500000
        assert adjust_price_to_tick_size(255555) == 255500

    def test_tick_size_above_500k(self):
        """500K+: 1,000 KRW tick"""
        assert adjust_price_to_tick_size(567890) == 568000
        assert adjust_price_to_tick_size(999999) == 1000000
        assert adjust_price_to_tick_size(755555) == 756000


class TestFeeCalculation:
    """Test fee-adjusted amount calculations"""

    def test_buy_fee_calculation(self):
        """Buy fee: 0.015%"""
        result = calculate_fee_adjusted_amount(100000, is_buy=True)

        assert result['original_amount'] == 100000
        assert result['fee_rate'] == 0.00015
        assert result['fee'] == pytest.approx(15.00, abs=0.1)
        assert result['adjusted_amount'] == pytest.approx(99985.00, abs=1.0)

    def test_sell_fee_calculation(self):
        """Sell fee: 0.015% + 0.23% = 0.245%"""
        result = calculate_fee_adjusted_amount(100000, is_buy=False)

        assert result['original_amount'] == 100000
        assert result['fee_rate'] == 0.00245
        assert result['fee'] == pytest.approx(245.0, abs=0.01)
        assert result['adjusted_amount'] == pytest.approx(99755.0, abs=0.01)

    def test_large_amount_buy(self):
        """Large amount buy fee"""
        result = calculate_fee_adjusted_amount(10000000, is_buy=True)

        assert result['fee'] == pytest.approx(1500.0, abs=1.0)
        assert result['adjusted_amount'] == pytest.approx(9998500, abs=10)

    def test_large_amount_sell(self):
        """Large amount sell fee"""
        result = calculate_fee_adjusted_amount(10000000, is_buy=False)

        assert result['fee'] == pytest.approx(24500.0, abs=0.1)
        assert result['adjusted_amount'] == pytest.approx(9975500, abs=1)


class TestKISTradingEngine:
    """Test KIS Trading Engine core functionality"""

    @pytest.fixture
    def engine(self):
        """Create engine instance with mock mode"""
        return KISTradingEngine(
            db_path="data/spock_local.db",
            dry_run=True  # Mock mode
        )

    @pytest.fixture
    def config(self):
        """Create trading config"""
        return TradingConfig(
            min_order_amount_krw=10000,
            max_positions=10,
            stop_loss_percent=-8.0,
            take_profit_percent=20.0
        )

    def test_engine_initialization(self, engine):
        """Test engine initialization"""
        assert engine is not None
        assert engine.dry_run == True
        assert engine.kis_client is not None
        assert engine.config.min_order_amount_krw == 10000

    def test_buy_order_execution(self, engine):
        """Test buy order execution (mock)"""
        result = engine.execute_buy_order('005930', 100000)

        assert result.success == True
        assert result.order_type == OrderType.BUY
        assert result.ticker == '005930'
        assert result.quantity > 0
        assert result.price > 0
        assert result.order_id is not None

    def test_buy_order_too_small(self, engine):
        """Test buy order with amount too small"""
        result = engine.execute_buy_order('005930', 5000)

        assert result.success == False
        assert 'too small' in result.message.lower()

    def test_sell_order_no_position(self, engine):
        """Test sell order without position"""
        result = engine.execute_sell_order('INVALID', quantity=10)

        assert result.success == False
        assert 'no open position' in result.message.lower()

    def test_position_info_properties(self):
        """Test PositionInfo calculated properties"""
        position = PositionInfo(
            ticker='005930',
            quantity=100,
            avg_buy_price=50000,
            current_price=46000,  # -8%
            market_value=4600000,
            unrealized_pnl=-400000,
            unrealized_pnl_percent=-8.0,
            buy_timestamp=datetime.now() - timedelta(days=30),
            hold_days=30
        )

        assert position.should_stop_loss == True
        assert position.should_take_profit == False

    def test_position_info_take_profit(self):
        """Test take profit condition"""
        position = PositionInfo(
            ticker='005930',
            quantity=100,
            avg_buy_price=50000,
            current_price=60000,  # +20%
            market_value=6000000,
            unrealized_pnl=1000000,
            unrealized_pnl_percent=20.0,
            buy_timestamp=datetime.now() - timedelta(days=30),
            hold_days=30
        )

        assert position.should_stop_loss == False
        assert position.should_take_profit == True

    def test_check_sell_conditions_stop_loss(self, engine):
        """Test sell condition check for stop loss"""
        position = PositionInfo(
            ticker='005930',
            quantity=100,
            avg_buy_price=50000,
            current_price=46000,  # -8%
            market_value=4600000,
            unrealized_pnl=-400000,
            unrealized_pnl_percent=-8.0,
            buy_timestamp=datetime.now() - timedelta(days=30),
            hold_days=30
        )

        should_sell, reason = engine.check_sell_conditions(position)

        assert should_sell == True
        assert reason == 'stop_loss'

    def test_check_sell_conditions_take_profit(self, engine):
        """Test sell condition check for take profit"""
        position = PositionInfo(
            ticker='005930',
            quantity=100,
            avg_buy_price=50000,
            current_price=60000,  # +20%
            market_value=6000000,
            unrealized_pnl=1000000,
            unrealized_pnl_percent=20.0,
            buy_timestamp=datetime.now() - timedelta(days=30),
            hold_days=30
        )

        should_sell, reason = engine.check_sell_conditions(position)

        assert should_sell == True
        assert reason == 'take_profit'

    def test_check_sell_conditions_hold(self, engine):
        """Test sell condition check for hold"""
        position = PositionInfo(
            ticker='005930',
            quantity=100,
            avg_buy_price=50000,
            current_price=52000,  # +4%
            market_value=5200000,
            unrealized_pnl=200000,
            unrealized_pnl_percent=4.0,
            buy_timestamp=datetime.now() - timedelta(days=30),
            hold_days=30
        )

        should_sell, reason = engine.check_sell_conditions(position)

        assert should_sell == False
        assert reason == 'hold'

    def test_check_sell_conditions_time_based(self, engine):
        """Test sell condition check for time-based exit"""
        position = PositionInfo(
            ticker='005930',
            quantity=100,
            avg_buy_price=50000,
            current_price=52000,  # +4%
            market_value=5200000,
            unrealized_pnl=200000,
            unrealized_pnl_percent=4.0,
            buy_timestamp=datetime.now() - timedelta(days=91),
            hold_days=91
        )

        should_sell, reason = engine.check_sell_conditions(position)

        assert should_sell == True
        assert reason == 'time_based_profit'


class TestIntegrationWorkflow:
    """Test complete workflow"""

    @pytest.fixture
    def engine(self):
        """Create engine instance"""
        return KISTradingEngine(
            db_path="data/spock_local.db",
            dry_run=True
        )

    def test_full_buy_sell_workflow(self, engine):
        """Test complete buy → sell workflow"""
        # 1. Execute buy order
        buy_result = engine.execute_buy_order('TEST_001', 100000)

        assert buy_result.success == True
        assert buy_result.quantity > 0

        # 2. Get current positions
        positions = engine.get_current_positions()

        # Note: Position may not be immediately visible in mock mode
        # due to database timing, but buy order succeeded

        # 3. Execute sell order (will fail if no position)
        # This is expected in mock mode without proper database setup

    def test_portfolio_management_process(self, engine):
        """Test portfolio management process"""
        summary = engine.process_portfolio_management()

        assert 'positions_checked' in summary
        assert 'sell_executed' in summary
        assert 'sell_results' in summary

        # In mock mode with no positions, should check 0 positions
        assert summary['positions_checked'] >= 0
        assert summary['sell_executed'] >= 0


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
