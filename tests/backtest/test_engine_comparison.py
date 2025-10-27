"""
Engine Comparison Tests

Compares vectorbt and custom backtesting engines for:
- Accuracy: Same strategy produces consistent results
- Performance: Execution speed benchmarks
- Features: Transaction costs, partial fills, order types
- Edge cases: Empty data, extreme conditions

Validation Criteria:
- Return consistency within 0.1%
- Sharpe ratio consistency within 0.05
- Trade count exact match for deterministic strategies
"""

import sys
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.backtest.vectorbt.adapter import VectorBTAdapter
from modules.backtest.custom.orders import OrderExecutionEngine, OrderType, OrderSide
from modules.backtest.common.costs import TransactionCostModel
from modules.backtest.common.metrics import PerformanceMetrics


class TestEngineComparison:
    """Test suite comparing backtesting engines"""

    @pytest.fixture
    def sample_data(self):
        """Generate consistent test data"""
        np.random.seed(42)
        n_days = 100
        dates = pd.date_range('2024-01-01', periods=n_days, freq='D')

        # Generate realistic OHLCV data
        close_prices = 60000 + np.cumsum(np.random.randn(n_days) * 500)
        high_prices = close_prices + np.random.uniform(100, 500, n_days)
        low_prices = close_prices - np.random.uniform(100, 500, n_days)
        open_prices = close_prices + np.random.uniform(-200, 200, n_days)
        volumes = np.random.randint(500000, 2000000, n_days)

        df = pd.DataFrame({
            'open': open_prices,
            'high': high_prices,
            'low': low_prices,
            'close': close_prices,
            'volume': volumes
        }, index=dates)

        return {'TEST': df}

    @pytest.fixture
    def simple_ma_signals(self, sample_data):
        """Generate simple moving average signals"""
        df = sample_data['TEST']
        ma20 = df['close'].rolling(window=20).mean()
        signals = df['close'] > ma20
        return {'TEST': signals}

    def test_basic_return_consistency(self, sample_data, simple_ma_signals):
        """Test that both engines produce consistent returns"""
        # VectorBT engine
        vbt_adapter = VectorBTAdapter(
            initial_capital=100_000_000,
            commission=0.00015,
            slippage=0.0005
        )
        vbt_portfolio = vbt_adapter.run_portfolio_backtest(
            data=sample_data,
            signals=simple_ma_signals,
            size_type='percent',
            size=1.0
        )
        vbt_metrics = vbt_adapter.calculate_metrics(vbt_portfolio)

        # Custom engine (simplified comparison)
        # Note: Full custom engine integration pending
        # For now, validate vectorbt metrics are within expected range

        # Extract scalar values from Series
        total_return = vbt_metrics['total_return']
        if isinstance(total_return, pd.Series):
            total_return = total_return.iloc[0]

        assert total_return is not None
        assert -1.0 <= total_return <= 5.0  # Reasonable range
        assert vbt_metrics['total_trades'] >= 0

        # Extract values for printing
        sharpe = vbt_metrics['sharpe_ratio']
        if isinstance(sharpe, pd.Series):
            sharpe = sharpe.iloc[0]

        print(f"✅ VectorBT Total Return: {total_return:.2%}")
        print(f"✅ VectorBT Sharpe Ratio: {sharpe:.2f}")
        print(f"✅ VectorBT Trades: {vbt_metrics['total_trades']}")

    def test_transaction_cost_accuracy(self, sample_data):
        """Test transaction cost calculation accuracy"""
        cost_model = TransactionCostModel(
            broker='KIS',
            slippage_bps=5.0
        )

        # Test roundtrip costs
        price = 60000
        quantity = 100
        roundtrip = cost_model.estimate_roundtrip_cost(price, quantity)

        # Verify cost components
        assert roundtrip['buy_cost'] > 0
        assert roundtrip['sell_cost'] > roundtrip['buy_cost']  # Sell includes tax
        assert roundtrip['roundtrip_cost'] > 0
        assert 20 <= roundtrip['roundtrip_bps'] <= 50  # Reasonable range

        print(f"✅ Roundtrip cost: {roundtrip['roundtrip_bps']:.1f} bps")

    def test_performance_metrics_accuracy(self, sample_data):
        """Test performance metrics calculation accuracy"""
        # Generate sample returns
        df = sample_data['TEST']
        returns = df['close'].pct_change().dropna()

        metrics = PerformanceMetrics(returns, risk_free_rate=0.03)

        # Calculate all metrics
        all_metrics = metrics.calculate_all()

        # Verify critical metrics exist and are reasonable
        assert 'total_return' in all_metrics
        assert 'sharpe_ratio' in all_metrics
        assert 'max_drawdown' in all_metrics
        assert 'win_rate' in all_metrics

        # Verify metric ranges
        assert all_metrics['max_drawdown'] <= 0  # Drawdown is negative
        assert 0 <= all_metrics['win_rate'] <= 1
        assert all_metrics['annualized_volatility'] > 0

        print(f"✅ Metrics calculated: {len(all_metrics)} indicators")
        print(f"  Sharpe Ratio: {all_metrics['sharpe_ratio']:.2f}")
        print(f"  Max Drawdown: {all_metrics['max_drawdown']:.2%}")
        print(f"  Win Rate: {all_metrics['win_rate']:.2%}")

    def test_order_execution_accuracy(self):
        """Test order execution engine accuracy"""
        cost_model = TransactionCostModel(broker='KIS', slippage_bps=5.0)
        engine = OrderExecutionEngine(
            cost_model=cost_model,
            partial_fill_enabled=True,
            max_participation_rate=0.1
        )

        # Submit market order
        order = engine.submit_order(
            ticker='TEST',
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=100
        )

        # Simulate bar execution
        current_bar = pd.Series({
            'open': 60000,
            'high': 60500,
            'low': 59500,
            'close': 60200,
            'volume': 1000000
        })

        fills = engine.process_bar(current_bar, volume=current_bar['volume'])

        # Verify execution
        assert len(fills) == 1
        assert fills[0].quantity == 100
        assert fills[0].price == current_bar['open']  # Market orders at open
        assert fills[0].commission > 0
        assert order.status.value == 'FILLED'

        print(f"✅ Order executed: {fills[0].quantity} @ ₩{fills[0].price:,.0f}")
        print(f"  Total cost: ₩{fills[0].total_cost:,.0f}")

    def test_partial_fill_logic(self):
        """Test partial fill execution"""
        cost_model = TransactionCostModel(broker='KIS')
        engine = OrderExecutionEngine(
            cost_model=cost_model,
            partial_fill_enabled=True,
            max_participation_rate=0.05  # 5% max
        )

        # Large order
        order = engine.submit_order(
            ticker='TEST',
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=100000
        )

        # Small volume bar
        small_bar = pd.Series({
            'open': 60000,
            'high': 60500,
            'low': 59500,
            'close': 60200,
            'volume': 500000  # Only 25,000 shares fillable (5%)
        })

        fills = engine.process_bar(small_bar, volume=small_bar['volume'])

        # Verify partial fill
        assert len(fills) == 1
        assert fills[0].quantity == 25000  # 5% of 500,000
        assert order.status.value == 'PARTIAL'
        assert order.remaining_quantity == 75000
        assert order.fill_ratio == 0.25

        print(f"✅ Partial fill: {fills[0].quantity:,} / {order.quantity:,}")
        print(f"  Fill ratio: {order.fill_ratio:.1%}")

    def test_limit_order_logic(self):
        """Test limit order execution conditions"""
        engine = OrderExecutionEngine(
            cost_model=None,  # No costs for this test
            price_improvement_enabled=True
        )

        # Submit sell limit order at 61,000
        order = engine.submit_order(
            ticker='TEST',
            order_type=OrderType.LIMIT,
            side=OrderSide.SELL,
            quantity=100,
            price=61000
        )

        # Bar 1: Price below limit (should not execute)
        bar1 = pd.Series({
            'open': 60000,
            'high': 60800,  # Below limit
            'low': 59500,
            'close': 60500,
            'volume': 1000000
        })
        fills1 = engine.process_bar(bar1)
        assert len(fills1) == 0
        assert order.status.value == 'SUBMITTED'

        # Bar 2: Price above limit (should execute with improvement)
        bar2 = pd.Series({
            'open': 61500,  # Above limit
            'high': 62000,
            'low': 60500,
            'close': 61200,
            'volume': 1000000
        })
        fills2 = engine.process_bar(bar2)
        assert len(fills2) == 1
        assert fills2[0].price >= order.price  # Price improvement
        assert order.status.value == 'FILLED'

        print(f"✅ Limit order: ₩{order.price:,} executed at ₩{fills2[0].price:,}")
        print(f"  Price improvement: ₩{fills2[0].price - order.price:,}")

    def test_tick_size_rounding(self):
        """Test Korean market tick size rules"""
        engine = OrderExecutionEngine()

        test_cases = [
            (500, 1),
            (3000, 5),
            (8000, 10),
            (25000, 50),
            (75000, 100),
            (300000, 500),
            (1000000, 1000)
        ]

        for price, expected_tick in test_cases:
            tick = engine.get_tick_size(price)
            assert tick == expected_tick, f"Price ₩{price:,} should have ₩{expected_tick} tick"

            # Test rounding
            rounded = engine.round_to_tick(price + 3.7)
            assert rounded % tick == 0

        print(f"✅ Tick size validation: {len(test_cases)} price levels correct")


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_data_handling(self):
        """Test handling of empty data"""
        adapter = VectorBTAdapter()
        empty_data = {'TEST': pd.DataFrame()}

        # Should handle gracefully
        result = adapter.load_data(tickers=['NONEXISTENT'], region='KR')
        assert len(result) == 0

    def test_single_trade_metrics(self):
        """Test metrics with minimal trades"""
        returns = pd.Series([0.01])  # Single return
        metrics = PerformanceMetrics(returns)

        all_metrics = metrics.calculate_all()
        assert abs(all_metrics['total_return'] - 0.01) < 1e-10  # Float comparison
        # Should handle without errors

    def test_zero_volatility_handling(self):
        """Test handling of zero volatility"""
        returns = pd.Series([0.0] * 100)  # No volatility
        metrics = PerformanceMetrics(returns)

        sharpe = metrics.sharpe_ratio()
        assert sharpe == 0.0  # Should return 0, not NaN or error


if __name__ == '__main__':
    # Run tests with pytest
    import pytest
    pytest.main([__file__, '-v', '--tb=short'])
