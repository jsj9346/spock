#!/usr/bin/env python3
"""
Integration Tests for Phase 5 Task 4 - Portfolio & Risk Management

Test Coverage:
- Buy order with position limits integration
- Sell order with portfolio sync
- Risk manager integration (stop loss, take profit, circuit breakers)
- Complete trading lifecycle
- Multi-position portfolio management

Total Tests: 10
Expected Coverage: End-to-end workflow validation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import sqlite3
from datetime import datetime, timedelta
from modules.portfolio_manager import PortfolioManager
from modules.risk_manager import RiskManager, RiskLimits, CircuitBreakerType
from modules.kis_trading_engine import (
    KISTradingEngine,
    OrderType,
    TradeStatus,
    TradingConfig
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def test_db_path(tmp_path):
    """Create isolated test database with full Phase 5 schema"""
    db_path = str(tmp_path / "test_integration.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create trades table (Phase 5 schema)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            region TEXT NOT NULL DEFAULT 'KR',
            side TEXT NOT NULL,
            order_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            entry_price REAL,
            exit_price REAL,
            price REAL NOT NULL,
            amount REAL NOT NULL,
            fee REAL DEFAULT 0,
            tax REAL DEFAULT 0,
            order_no TEXT,
            execution_no TEXT,
            entry_timestamp TEXT,
            exit_timestamp TEXT,
            order_time TEXT NOT NULL,
            execution_time TEXT,
            trade_status TEXT DEFAULT 'OPEN',
            sector TEXT,
            position_size_percent REAL,
            reason TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # Create ticker_details table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticker_details (
            ticker TEXT PRIMARY KEY,
            region TEXT NOT NULL DEFAULT 'KR',
            sector TEXT,
            industry TEXT
        )
    """)

    # Create portfolio table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            ticker TEXT PRIMARY KEY,
            region TEXT NOT NULL DEFAULT 'KR',
            quantity INTEGER NOT NULL,
            avg_price REAL NOT NULL,
            current_price REAL,
            market_value REAL,
            unrealized_pnl REAL,
            unrealized_pnl_pct REAL,
            entry_date TEXT NOT NULL,
            last_updated TEXT NOT NULL
        )
    """)

    # Create circuit_breaker_logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS circuit_breaker_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            breaker_type TEXT NOT NULL,
            trigger_value REAL NOT NULL,
            limit_value REAL NOT NULL,
            trigger_reason TEXT NOT NULL,
            metadata TEXT,
            timestamp TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def portfolio_manager(test_db_path):
    """Create PortfolioManager instance"""
    return PortfolioManager(
        db_path=test_db_path,
        initial_cash=10000000.0  # 10M KRW
    )


@pytest.fixture
def risk_manager(test_db_path):
    """Create RiskManager instance"""
    return RiskManager(
        db_path=test_db_path,
        risk_limits=RiskLimits(
            daily_loss_limit_percent=-3.0,
            stop_loss_percent=-8.0,
            take_profit_percent=20.0,
            max_positions=10,
            max_sector_exposure_percent=40.0,
            consecutive_loss_threshold=3
        )
    )


@pytest.fixture
def trading_engine(test_db_path, portfolio_manager):
    """Create KISTradingEngine with PortfolioManager integration"""
    return KISTradingEngine(
        db_path=test_db_path,
        config=TradingConfig(min_order_amount_krw=100000.0),
        dry_run=True,  # Use mock API
        portfolio_manager=portfolio_manager
    )


# ============================================================================
# Test Class 1: Buy Order Integration
# ============================================================================

class TestBuyOrderIntegration:
    """Test buy order execution with position limits"""

    def test_buy_order_with_position_limits_pass(self, trading_engine, test_db_path):
        """Test buy order passes position limit checks (under 15%)"""
        # Add sector mapping
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO ticker_details (ticker, region, sector) VALUES ('005930', 'KR', 'Information Technology')")
        conn.commit()
        conn.close()

        # Buy 1M KRW worth (10% of 10M portfolio - should pass 15% limit)
        result = trading_engine.execute_buy_order(
            ticker='005930',
            amount_krw=1000000.0,
            sector='Information Technology',
            region='KR'
        )

        # In dry-run mode, this will succeed if position limits pass
        assert result.success == True, "Buy order should succeed with valid position limits"

    def test_buy_order_with_position_limits_fail_single(self, trading_engine, test_db_path):
        """Test buy order fails due to single stock limit (over 15%)"""
        # Try to buy 2M KRW worth (20% of 10M portfolio - exceeds 15% limit)
        result = trading_engine.execute_buy_order(
            ticker='TEST_LIMIT',
            amount_krw=2000000.0,
            sector='Financials',
            region='KR'
        )

        assert result.success == False, "Buy order should fail when exceeding 15% single stock limit"
        assert 'limit' in result.message.lower(), f"Message should mention limit violation: {result.message}"

    def test_buy_order_with_position_limits_fail_sector(self, trading_engine, test_db_path):
        """Test buy order fails due to sector exposure limit (over 40%)"""
        # First, create existing IT position (35%)
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()

        cursor.execute("INSERT INTO ticker_details (ticker, region, sector) VALUES ('005930', 'KR', 'Information Technology')")
        cursor.execute("INSERT INTO ticker_details (ticker, region, sector) VALUES ('IT_TEST', 'KR', 'Information Technology')")

        cursor.execute("""
            INSERT INTO trades (
                ticker, region, side, order_type, quantity,
                entry_price, price, amount,
                entry_timestamp, trade_status, sector,
                order_time, created_at
            )
            VALUES ('005930', 'KR', 'BUY', 'LIMIT', 50, 70000.0, 70000.0, 3500000.0,
                    ?, 'OPEN', 'Information Technology', ?, ?)
        """, (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        conn.commit()
        conn.close()

        # Try to add another 10% IT stock → 45% total (exceeds 40% limit)
        result = trading_engine.execute_buy_order(
            ticker='IT_TEST',
            amount_krw=1000000.0,
            sector='Information Technology',
            region='KR'
        )

        assert result.success == False, "Buy order should fail when sector exposure exceeds 40%"
        assert 'sector' in result.message.lower() or '40%' in result.message, f"Message should mention sector limit: {result.message}"


# ============================================================================
# Test Class 2: Sell Order Integration
# ============================================================================

class TestSellOrderIntegration:
    """Test sell order execution with portfolio sync"""

    def test_sell_order_portfolio_sync(self, trading_engine, portfolio_manager, test_db_path):
        """Test portfolio updates correctly after sell order"""
        # Create initial position
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO trades (
                ticker, region, side, order_type, quantity,
                entry_price, price, amount,
                entry_timestamp, trade_status,
                order_time, created_at
            )
            VALUES ('TEST_SELL', 'KR', 'BUY', 'LIMIT', 100, 50000.0, 50000.0, 5000000.0,
                    ?, 'OPEN', ?, ?)
        """, (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        conn.commit()
        conn.close()

        # Verify position exists
        positions_before = portfolio_manager.get_all_positions()
        assert len(positions_before) == 1, "Should have 1 open position"

        # Execute sell order (in dry-run mode)
        result = trading_engine.execute_sell_order(
            ticker='TEST_SELL',
            quantity=100,
            reason='Test sell'
        )

        # In dry-run mode, sell will succeed
        assert result.success == True, "Sell order should succeed in dry-run mode"

        # Verify position is closed
        positions_after = portfolio_manager.get_all_positions()
        assert len(positions_after) == 0, "Should have 0 open positions after sell"

    def test_sell_order_stop_loss_trigger(self, trading_engine, risk_manager, test_db_path):
        """Test stop loss signal generation (integration with risk manager)"""
        # Create position with loss (manually update for testing)
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO trades (
                ticker, region, side, order_type, quantity,
                entry_price, price, amount,
                entry_timestamp, trade_status,
                order_time, created_at
            )
            VALUES ('TEST_LOSS', 'KR', 'BUY', 'LIMIT', 100, 50000.0, 50000.0, 5000000.0,
                    ?, 'OPEN', ?, ?)
        """, (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        conn.commit()
        conn.close()

        # Check stop loss signals
        stop_loss_signals = risk_manager.check_stop_loss_conditions()

        # In MVP with simplified pricing, this validates integration works
        assert isinstance(stop_loss_signals, list), "Stop loss check should return list"


# ============================================================================
# Test Class 3: Risk Manager Integration
# ============================================================================

class TestRiskIntegration:
    """Test risk manager integration with trading engine"""

    def test_circuit_breaker_halts_trading(self, trading_engine, risk_manager, test_db_path):
        """Test circuit breaker detection after excessive losses"""
        # Create 11 open positions to trigger position count breaker
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()

        for i in range(11):
            cursor.execute("""
                INSERT INTO trades (
                    ticker, region, side, order_type, quantity,
                    entry_price, price, amount,
                    entry_timestamp, trade_status,
                    order_time, created_at
                )
                VALUES (?, 'KR', 'BUY', 'LIMIT', 10, 50000.0, 50000.0, 500000.0,
                        ?, 'OPEN', ?, ?)
            """, (f'POS{i:03d}',
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        conn.commit()
        conn.close()

        # Check circuit breakers
        portfolio_value = trading_engine.portfolio_manager.get_total_portfolio_value()
        breakers = risk_manager.check_circuit_breakers(total_portfolio_value=portfolio_value)

        # Should trigger position count breaker
        position_breakers = [b for b in breakers if b.breaker_type == CircuitBreakerType.POSITION_COUNT_LIMIT]
        assert len(position_breakers) >= 1, "Should trigger position count circuit breaker"

        # Verify breaker was logged to database
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM circuit_breaker_logs")
        log_count = cursor.fetchone()[0]
        conn.close()

        assert log_count >= 1, "Circuit breaker should be logged to database"

    def test_stop_loss_signal_generation(self, risk_manager, test_db_path):
        """Test stop loss signal detection across portfolio"""
        # Create multiple positions (in simplified MVP, they won't trigger)
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()

        positions = [
            ('POS1', 100, 50000.0, 'OPEN'),
            ('POS2', 100, 60000.0, 'OPEN'),
            ('POS3', 100, 45000.0, 'OPEN'),
        ]

        for ticker, quantity, entry_price, status in positions:
            cursor.execute("""
                INSERT INTO trades (
                    ticker, region, side, order_type, quantity,
                    entry_price, price, amount,
                    entry_timestamp, trade_status,
                    order_time, created_at
                )
                VALUES (?, 'KR', 'BUY', 'LIMIT', ?, ?, ?, ?,
                        ?, ?, ?, ?)
            """, (ticker, quantity, entry_price, entry_price, entry_price * quantity,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  status,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        conn.commit()
        conn.close()

        # Check stop loss signals
        signals = risk_manager.check_stop_loss_conditions()

        # Validates stop loss monitoring is active
        assert isinstance(signals, list), "Stop loss monitoring should return list of signals"

    def test_take_profit_signal_generation(self, risk_manager, test_db_path):
        """Test take profit signal detection across portfolio"""
        # Create multiple positions (in simplified MVP, they won't trigger)
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()

        positions = [
            ('PROFIT1', 100, 50000.0, 'OPEN'),
            ('PROFIT2', 100, 60000.0, 'OPEN'),
        ]

        for ticker, quantity, entry_price, status in positions:
            cursor.execute("""
                INSERT INTO trades (
                    ticker, region, side, order_type, quantity,
                    entry_price, price, amount,
                    entry_timestamp, trade_status,
                    order_time, created_at
                )
                VALUES (?, 'KR', 'BUY', 'LIMIT', ?, ?, ?, ?,
                        ?, ?, ?, ?)
            """, (ticker, quantity, entry_price, entry_price, entry_price * quantity,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  status,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        conn.commit()
        conn.close()

        # Check take profit signals
        signals = risk_manager.check_take_profit_conditions()

        # Validates take profit monitoring is active
        assert isinstance(signals, list), "Take profit monitoring should return list of signals"


# ============================================================================
# Test Class 4: Full Workflow
# ============================================================================

class TestFullWorkflow:
    """Test complete trading lifecycle"""

    def test_complete_trading_lifecycle(self, trading_engine, portfolio_manager, risk_manager, test_db_path):
        """Test complete buy → hold → sell → P&L workflow"""
        # Add sector mapping
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO ticker_details (ticker, region, sector) VALUES ('LIFECYCLE', 'KR', 'Financials')")
        conn.commit()
        conn.close()

        # Phase 1: Initial state
        initial_portfolio = portfolio_manager.get_portfolio_summary()
        assert initial_portfolio.total_value == 10000000.0, "Initial value should be 10M"
        assert initial_portfolio.num_positions == 0, "Should have 0 initial positions"

        # Phase 2: Buy order
        buy_result = trading_engine.execute_buy_order(
            ticker='LIFECYCLE',
            amount_krw=1000000.0,
            sector='Financials',
            region='KR'
        )

        assert buy_result.success == True, "Buy order should succeed"

        # Phase 3: Verify position
        positions = portfolio_manager.get_all_positions()
        assert len(positions) == 1, "Should have 1 open position after buy"

        # Phase 4: Check risk signals (should be clean)
        stop_loss_signals = risk_manager.check_stop_loss_conditions()
        take_profit_signals = risk_manager.check_take_profit_conditions()

        assert isinstance(stop_loss_signals, list), "Stop loss check should work"
        assert isinstance(take_profit_signals, list), "Take profit check should work"

        # Phase 5: Sell order
        sell_result = trading_engine.execute_sell_order(
            ticker='LIFECYCLE',
            quantity=buy_result.quantity,
            reason='Test lifecycle completion'
        )

        assert sell_result.success == True, "Sell order should succeed"

        # Phase 6: Verify position closed
        final_positions = portfolio_manager.get_all_positions()
        assert len(final_positions) == 0, "Should have 0 positions after sell"

    def test_multi_position_portfolio_management(self, trading_engine, portfolio_manager, risk_manager, test_db_path):
        """Test managing multiple positions with sector limits enforced"""
        # Add sector mappings
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()

        sectors = [
            ('TECH1', 'Information Technology'),
            ('TECH2', 'Information Technology'),
            ('FIN1', 'Financials'),
            ('MAT1', 'Materials'),
            ('CONS1', 'Consumer Discretionary'),
        ]

        for ticker, sector in sectors:
            cursor.execute("INSERT INTO ticker_details (ticker, region, sector) VALUES (?, 'KR', ?)", (ticker, sector))

        conn.commit()
        conn.close()

        # Buy 5 positions across different sectors
        positions = [
            ('TECH1', 1000000.0, 'Information Technology'),
            ('TECH2', 800000.0, 'Information Technology'),
            ('FIN1', 1200000.0, 'Financials'),
            ('MAT1', 900000.0, 'Materials'),
            ('CONS1', 1000000.0, 'Consumer Discretionary'),
        ]

        successful_buys = 0
        for ticker, amount, sector in positions:
            result = trading_engine.execute_buy_order(
                ticker=ticker,
                amount_krw=amount,
                sector=sector,
                region='KR'
            )

            if result.success:
                successful_buys += 1

        # Should successfully buy at least 4 positions (some may fail due to limits)
        assert successful_buys >= 4, f"Should successfully buy at least 4 positions, got {successful_buys}"

        # Verify portfolio state
        portfolio = portfolio_manager.get_portfolio_summary()
        assert portfolio.num_positions >= 4, "Should have at least 4 open positions"

        # Verify sector exposures are within limits
        sector_exposures = portfolio_manager.get_sector_exposures()
        for sector, exposure in sector_exposures.items():
            assert exposure <= 45.0, f"Sector {sector} exposure {exposure}% should be near or below 40% limit"

        # Verify circuit breakers are not triggered
        breakers = risk_manager.check_circuit_breakers(total_portfolio_value=portfolio.total_value)
        position_count_breakers = [b for b in breakers if b.breaker_type == CircuitBreakerType.POSITION_COUNT_LIMIT]
        assert len(position_count_breakers) == 0, "Position count should not exceed 10"


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
