#!/usr/bin/env python3
"""
Unit Tests for Portfolio Manager

Test Coverage:
- Portfolio value calculations
- Position tracking and P&L
- Position limits (4-layer validation)
- Sector exposure calculations
- Portfolio summary generation

Total Tests: 16
Expected Coverage: ≥85%
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import sqlite3
from datetime import datetime, timedelta
from modules.portfolio_manager import (
    PortfolioManager,
    Position,
    PortfolioSummary,
    POSITION_LIMITS,
    DEFAULT_SECTOR
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def test_db_path(tmp_path):
    """Create isolated test database"""
    db_path = str(tmp_path / "test_portfolio.db")

    # Initialize database schema
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

    # Create ticker_details table for sector mapping
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
def sample_trades(test_db_path):
    """Insert sample trade data"""
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()

    # Insert ticker details
    sectors = [
        ('005930', 'KR', 'Information Technology'),  # Samsung
        ('000660', 'KR', 'Materials'),                # SK Hynix
        ('035720', 'KR', 'Consumer Discretionary'),   # Kakao
    ]

    for ticker, region, sector in sectors:
        cursor.execute("""
            INSERT INTO ticker_details (ticker, region, sector)
            VALUES (?, ?, ?)
        """, (ticker, region, sector))

    # Insert open trades
    trades = [
        # Samsung: 50K @ 70,000 = 3.5M (35% of 10M)
        ('005930', 'KR', 'BUY', 'LIMIT', 50, 70000.0, 70000.0, 3500000.0,
         datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'OPEN', 'Information Technology', 35.0),

        # SK Hynix: 30K @ 100,000 = 3M (30% of 10M)
        ('000660', 'KR', 'BUY', 'LIMIT', 30, 100000.0, 100000.0, 3000000.0,
         datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'OPEN', 'Materials', 30.0),

        # Kakao: 20K @ 50,000 = 1M (10% of 10M)
        ('035720', 'KR', 'BUY', 'LIMIT', 20, 50000.0, 50000.0, 1000000.0,
         datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'OPEN', 'Consumer Discretionary', 10.0),
    ]

    for trade in trades:
        cursor.execute("""
            INSERT INTO trades (
                ticker, region, side, order_type, quantity,
                entry_price, price, amount,
                entry_timestamp, trade_status, sector, position_size_percent,
                order_time, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (*trade, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    conn.commit()
    conn.close()


# ============================================================================
# Test Class 1: Portfolio Value Calculations
# ============================================================================

class TestPortfolioValue:
    """Test portfolio value calculations"""

    def test_get_total_portfolio_value_initial(self, portfolio_manager):
        """Test initial portfolio value (10M KRW cash)"""
        total_value = portfolio_manager.get_total_portfolio_value()

        assert total_value == 10000000.0, "Initial portfolio value should be 10M KRW"

    def test_get_total_portfolio_value_with_positions(self, portfolio_manager, sample_trades):
        """Test portfolio value with open positions (cash + positions)"""
        total_value = portfolio_manager.get_total_portfolio_value()

        # Expected: 10M initial - 7.5M invested = 2.5M cash + 7.5M positions = 10M total
        # (Position values use entry prices in simplified version)
        assert total_value >= 9500000.0, "Portfolio value should be ~10M with positions"
        assert total_value <= 10500000.0, "Portfolio value should not exceed 10.5M"

    def test_get_available_cash_calculation(self, portfolio_manager, sample_trades):
        """Test available cash calculation after trades"""
        available_cash = portfolio_manager.get_available_cash()

        # Expected: 10M - 7.5M invested = 2.5M available
        assert available_cash >= 2000000.0, "Should have ~2.5M cash remaining"
        assert available_cash <= 3000000.0, "Cash should not exceed 3M"


# ============================================================================
# Test Class 2: Position Tracking
# ============================================================================

class TestPositionTracking:
    """Test position tracking and P&L calculations"""

    def test_get_all_positions_empty(self, portfolio_manager):
        """Test getting positions from empty portfolio"""
        positions = portfolio_manager.get_all_positions()

        assert len(positions) == 0, "Empty portfolio should return no positions"

    def test_get_all_positions_multiple(self, portfolio_manager, sample_trades):
        """Test getting multiple open positions"""
        positions = portfolio_manager.get_all_positions()

        assert len(positions) == 3, "Should have 3 open positions"

        # Verify position attributes
        tickers = {pos.ticker for pos in positions}
        assert tickers == {'005930', '000660', '035720'}, "Should have correct tickers"

        # Verify all positions are OPEN
        for pos in positions:
            assert pos.quantity > 0, f"{pos.ticker} should have positive quantity"
            assert pos.avg_entry_price > 0, f"{pos.ticker} should have valid entry price"

    def test_get_position_by_ticker(self, portfolio_manager, sample_trades):
        """Test getting specific position by ticker"""
        position = portfolio_manager.get_position_by_ticker('005930', 'KR')

        assert position is not None, "Should find Samsung position"
        assert position.ticker == '005930'
        assert position.quantity == 50
        assert position.avg_entry_price == 70000.0
        assert position.sector == 'Information Technology'

    def test_position_pnl_calculation(self, portfolio_manager, sample_trades):
        """Test unrealized P&L calculation accuracy"""
        positions = portfolio_manager.get_all_positions()

        for pos in positions:
            # In simplified version, current_price == entry_price
            # So unrealized P&L should be near 0
            assert pos.unrealized_pnl_percent >= -5.0, f"{pos.ticker} P&L% should be >= -5%"
            assert pos.unrealized_pnl_percent <= 5.0, f"{pos.ticker} P&L% should be <= 5%"


# ============================================================================
# Test Class 3: Position Limits (4-Layer Validation)
# ============================================================================

class TestPositionLimits:
    """Test 4-layer position limit checks"""

    def test_check_position_limits_single_stock_pass(self, portfolio_manager):
        """Test single stock limit check passes (under 15%)"""
        # Try to buy 1M KRW worth (10% of 10M portfolio)
        can_buy, reason = portfolio_manager.check_position_limits(
            ticker='TEST001',
            amount_krw=1000000.0,
            sector='Financials',
            region='KR'
        )

        assert can_buy == True, "Should allow 10% position (under 15% limit)"
        assert reason == "Position limits OK", f"Unexpected reason: {reason}"

    def test_check_position_limits_single_stock_fail(self, portfolio_manager):
        """Test single stock limit check fails (over 15%)"""
        # Try to buy 2M KRW worth (20% of 10M portfolio - exceeds 15% limit)
        can_buy, reason = portfolio_manager.check_position_limits(
            ticker='TEST002',
            amount_krw=2000000.0,
            sector='Financials',
            region='KR'
        )

        assert can_buy == False, "Should block 20% position (exceeds 15% limit)"
        assert '15' in reason or '15.0%' in reason or 'Position limit exceeded' in reason, f"Reason should mention 15% limit: {reason}"

    def test_check_position_limits_sector_fail(self, portfolio_manager, sample_trades):
        """Test sector exposure limit check fails (over 40%)"""
        # Samsung (IT sector) already has 35%
        # Try to add another 10% IT stock → 45% total (exceeds 40% limit)
        can_buy, reason = portfolio_manager.check_position_limits(
            ticker='TEST_IT',
            amount_krw=1000000.0,  # 10% more
            sector='Information Technology',  # Same sector as Samsung
            region='KR'
        )

        assert can_buy == False, "Should block sector concentration over 40%"
        assert 'sector' in reason.lower() or '40%' in reason, f"Reason should mention sector limit: {reason}"

    def test_check_position_limits_cash_reserve_fail(self, portfolio_manager, sample_trades):
        """Test cash reserve limit check fails (under 20%)"""
        # Currently have ~2.5M cash (25%)
        # Try to invest 1.5M more → 1M cash left (10% - below 20% min)
        can_buy, reason = portfolio_manager.check_position_limits(
            ticker='TEST_CASH',
            amount_krw=1500000.0,
            sector='Utilities',
            region='KR'
        )

        assert can_buy == False, "Should block trade that reduces cash below 20%"
        assert 'cash' in reason.lower() or '20%' in reason, f"Reason should mention cash reserve: {reason}"

    def test_check_position_limits_position_count_fail(self, portfolio_manager, test_db_path):
        """Test position count limit check fails (over 10 positions)"""
        # Add 11 small positions to exceed the 10-position limit without triggering cash reserve
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()

        for i in range(11):
            ticker = f'TEST{i:03d}'
            cursor.execute("""
                INSERT INTO ticker_details (ticker, region, sector)
                VALUES (?, 'KR', 'Utilities')
            """, (ticker,))

            cursor.execute("""
                INSERT INTO trades (
                    ticker, region, side, order_type, quantity,
                    entry_price, price, amount,
                    entry_timestamp, trade_status, sector,
                    order_time, created_at
                )
                VALUES (?, 'KR', 'BUY', 'LIMIT', 5, 10000.0, 10000.0, 50000.0,
                        ?, 'OPEN', 'Utilities', ?, ?)
            """, (ticker,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        conn.commit()
        conn.close()

        # Try to add 12th position (exceeds 10 limit)
        # Total invested: 11 * 50K = 550K (<10M), so cash reserve is OK
        can_buy, reason = portfolio_manager.check_position_limits(
            ticker='TEST_EXTRA',
            amount_krw=50000.0,  # Small amount to avoid cash reserve issues
            sector='Energy',
            region='KR'
        )

        assert can_buy == False, "Should block 12th position (exceeds 10 limit)"
        assert 'position' in reason.lower() or '10' in reason or 'Position count' in reason, f"Reason should mention position count: {reason}"


# ============================================================================
# Test Class 4: Sector Exposure
# ============================================================================

class TestSectorExposure:
    """Test sector exposure calculations"""

    def test_calculate_sector_exposure(self, portfolio_manager, sample_trades):
        """Test sector allocation calculation"""
        # Samsung: IT sector, 3.5M (35%)
        it_exposure = portfolio_manager.calculate_sector_exposure('Information Technology')

        assert it_exposure >= 30.0, "IT sector should be ~35%"
        assert it_exposure <= 40.0, "IT sector should not exceed 40%"

    def test_get_sector_exposures_multiple(self, portfolio_manager, sample_trades):
        """Test multi-sector portfolio exposure"""
        sector_exposures = portfolio_manager.get_sector_exposures()

        # Should have 3 sectors
        assert len(sector_exposures) >= 3, "Should have at least 3 sectors"

        # Verify sector names
        expected_sectors = {'Information Technology', 'Materials', 'Consumer Discretionary'}
        assert expected_sectors.issubset(set(sector_exposures.keys())), "Should have expected sectors"

        # Total exposure should be ≤100% (some cash reserve)
        total_exposure = sum(sector_exposures.values())
        assert total_exposure <= 100.0, "Total sector exposure should not exceed 100%"
        assert total_exposure >= 60.0, "Total sector exposure should be significant"


# ============================================================================
# Test Class 5: Portfolio Summary
# ============================================================================

class TestPortfolioSummary:
    """Test portfolio summary generation"""

    def test_get_portfolio_summary_empty(self, portfolio_manager):
        """Test portfolio summary for empty portfolio"""
        summary = portfolio_manager.get_portfolio_summary()

        assert summary.total_value == 10000000.0, "Total value should be 10M"
        assert summary.cash == 10000000.0, "Cash should be 10M"
        assert summary.positions_value == 0.0, "Positions value should be 0"
        assert summary.num_positions == 0, "Should have 0 positions"
        assert summary.total_pnl == 0.0, "P&L should be 0"

    def test_get_portfolio_summary_with_positions(self, portfolio_manager, sample_trades):
        """Test portfolio summary with open positions"""
        summary = portfolio_manager.get_portfolio_summary()

        # Basic validations
        assert summary.total_value >= 9500000.0, "Total value should be ~10M"
        assert summary.cash >= 2000000.0, "Cash should be ~2.5M"
        assert summary.positions_value >= 7000000.0, "Positions value should be ~7.5M"
        assert summary.num_positions == 3, "Should have 3 positions"

        # Sector breakdown
        assert len(summary.sector_exposures) >= 3, "Should have 3 sectors"

        # Largest positions
        assert summary.largest_position_ticker is not None, "Should have largest position"
        assert summary.largest_position_percent >= 30.0, "Largest position should be ~35%"


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
