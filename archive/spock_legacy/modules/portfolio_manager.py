#!/usr/bin/env python3
"""
Portfolio Manager - Position Tracking and Limit Enforcement

🎯 Core Features:
- Real-time position tracking from trades table
- Position size limits (15% stock, 40% sector, 20% cash)
- Sector exposure calculations
- Portfolio metrics and summary
- Cash reserve management

💰 Position Limits:
- Max 15% per stock (conservative risk management)
- Max 40% per sector (diversification requirement)
- Min 20% cash reserve (liquidity buffer)
- Max 10 concurrent positions (focus requirement)

📊 Reference: Integrated with KIS Trading Engine and Risk Manager

Design: Simplified MVP (~700 lines)
Code Reuse: 80% from Makenaide trading_engine.py
"""

import os
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from collections import defaultdict

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('portfolio_manager')


# ========================================================================
# Constants and Configuration
# ========================================================================

# Position Limits (Conservative Risk Management)
POSITION_LIMITS = {
    'max_single_position_percent': 15.0,   # 15% max per stock
    'max_sector_exposure_percent': 40.0,   # 40% max per sector
    'min_cash_reserve_percent': 20.0,      # 20% minimum cash
    'max_concurrent_positions': 10,         # Max 10 stocks
}

# Default sectors for unmapped stocks
DEFAULT_SECTOR = 'Unknown'


# ========================================================================
# Data Classes
# ========================================================================

@dataclass
class Position:
    """Position information"""
    ticker: str
    region: str
    quantity: float
    avg_entry_price: float
    current_price: float
    market_value: float
    cost_basis: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    entry_timestamp: datetime
    hold_days: int
    sector: str = DEFAULT_SECTOR

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'ticker': self.ticker,
            'region': self.region,
            'quantity': self.quantity,
            'avg_entry_price': self.avg_entry_price,
            'current_price': self.current_price,
            'market_value': self.market_value,
            'cost_basis': self.cost_basis,
            'unrealized_pnl': self.unrealized_pnl,
            'unrealized_pnl_percent': self.unrealized_pnl_percent,
            'entry_timestamp': self.entry_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'hold_days': self.hold_days,
            'sector': self.sector
        }


@dataclass
class PortfolioSummary:
    """Portfolio summary metrics"""
    total_value: float
    cash: float
    cash_percent: float
    invested: float
    invested_percent: float
    position_count: int
    total_pnl: float
    total_pnl_percent: float
    daily_pnl: float
    daily_pnl_percent: float
    sector_exposures: Dict[str, float]
    largest_position_percent: float
    largest_position_ticker: Optional[str] = None

    # Aliases for backward compatibility with tests
    @property
    def num_positions(self) -> int:
        """Alias for position_count"""
        return self.position_count

    @property
    def positions_value(self) -> float:
        """Alias for invested"""
        return self.invested

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


# ========================================================================
# Portfolio Manager
# ========================================================================

class PortfolioManager:
    """
    Portfolio Manager - Position Tracking and Limit Enforcement

    Features:
    - Real-time position tracking from trades table
    - Position limit enforcement (stock/sector/cash)
    - Sector exposure calculations
    - Portfolio metrics and summary
    """

    def __init__(self, db_path: str, initial_cash: float = 10000000.0):
        """
        Initialize Portfolio Manager

        Args:
            db_path: SQLite database path
            initial_cash: Initial cash balance (default: 10M KRW)
        """
        self.db_path = db_path
        self.initial_cash = initial_cash

        # Position limits
        self.max_single_position_percent = POSITION_LIMITS['max_single_position_percent']
        self.max_sector_exposure_percent = POSITION_LIMITS['max_sector_exposure_percent']
        self.min_cash_reserve_percent = POSITION_LIMITS['min_cash_reserve_percent']
        self.max_concurrent_positions = POSITION_LIMITS['max_concurrent_positions']

        logger.info(f"📊 Portfolio Manager initialized")
        logger.info(f"   Initial cash: {initial_cash:,.0f} KRW")
        logger.info(f"   Position limits: {self.max_single_position_percent}% stock, "
                   f"{self.max_sector_exposure_percent}% sector, "
                   f"{self.min_cash_reserve_percent}% cash")

    # ====================================================================
    # Portfolio State Queries
    # ====================================================================

    def get_total_portfolio_value(self) -> float:
        """
        Get total portfolio value (cash + positions)

        Returns:
            Total portfolio value in KRW
        """
        try:
            cash = self.get_available_cash()
            positions = self.get_all_positions()

            positions_value = sum(pos.market_value for pos in positions)
            total_value = cash + positions_value

            return total_value

        except Exception as e:
            logger.error(f"Failed to get total portfolio value: {e}")
            return self.initial_cash

    def get_available_cash(self) -> float:
        """
        Get available cash balance

        Calculation:
        cash = initial_cash + realized_pnl - invested_in_open_positions

        Returns:
            Available cash in KRW
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get realized P&L from closed trades (calculate from entry/exit prices)
            cursor.execute("""
                SELECT COALESCE(SUM((exit_price - entry_price) * quantity), 0)
                FROM trades
                WHERE trade_status = 'CLOSED'
                  AND exit_price IS NOT NULL
                  AND entry_price IS NOT NULL
            """)
            realized_pnl = cursor.fetchone()[0]

            # Get invested amount in open positions
            cursor.execute("""
                SELECT COALESCE(SUM(entry_price * quantity), 0)
                FROM trades
                WHERE trade_status = 'OPEN'
            """)
            invested = cursor.fetchone()[0]

            conn.close()

            # Calculate available cash
            cash = self.initial_cash + realized_pnl - invested

            return max(0, cash)  # Ensure non-negative

        except Exception as e:
            logger.error(f"Failed to get available cash: {e}")
            return 0.0

    def get_all_positions(self, include_current_price: bool = True) -> List[Position]:
        """
        Get all open positions

        Args:
            include_current_price: If True, fetch current prices (slower)

        Returns:
            List of Position objects
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Query open positions
            cursor.execute("""
                SELECT
                    t.ticker,
                    t.region,
                    SUM(t.quantity) as total_quantity,
                    AVG(t.entry_price) as avg_entry_price,
                    MIN(t.entry_timestamp) as first_entry_timestamp,
                    COALESCE(sd.sector, ?) as sector
                FROM trades t
                LEFT JOIN stock_details sd ON t.ticker = sd.ticker
                WHERE t.trade_status = 'OPEN'
                GROUP BY t.ticker, t.region
                HAVING total_quantity > 0
                ORDER BY first_entry_timestamp DESC
            """, (DEFAULT_SECTOR,))

            rows = cursor.fetchall()
            conn.close()

            positions = []

            for row in rows:
                ticker = row[0]
                region = row[1]
                quantity = row[2]
                avg_entry_price = row[3]
                entry_timestamp_str = row[4]
                sector = row[5] or DEFAULT_SECTOR

                entry_timestamp = datetime.strptime(entry_timestamp_str, '%Y-%m-%d %H:%M:%S')
                hold_days = (datetime.now() - entry_timestamp).days

                # Get current price (simplified - would use KIS API in production)
                if include_current_price:
                    current_price = self._get_current_price(ticker, region)
                else:
                    current_price = avg_entry_price

                # Calculate metrics
                cost_basis = avg_entry_price * quantity
                market_value = current_price * quantity
                unrealized_pnl = market_value - cost_basis
                unrealized_pnl_percent = ((current_price - avg_entry_price) / avg_entry_price) * 100

                position = Position(
                    ticker=ticker,
                    region=region,
                    quantity=quantity,
                    avg_entry_price=avg_entry_price,
                    current_price=current_price,
                    market_value=market_value,
                    cost_basis=cost_basis,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_percent=unrealized_pnl_percent,
                    entry_timestamp=entry_timestamp,
                    hold_days=hold_days,
                    sector=sector
                )

                positions.append(position)

            return positions

        except Exception as e:
            logger.error(f"Failed to get all positions: {e}")
            return []

    def get_position_by_ticker(self, ticker: str, region: str = 'KR') -> Optional[Position]:
        """
        Get position for specific ticker

        Args:
            ticker: Stock ticker
            region: Market region (default: KR)

        Returns:
            Position object or None
        """
        positions = self.get_all_positions()

        for position in positions:
            if position.ticker == ticker and position.region == region:
                return position

        return None

    # ====================================================================
    # Position Limit Checks
    # ====================================================================

    def check_position_limits(self, ticker: str, amount_krw: float,
                               sector: str = DEFAULT_SECTOR, region: str = 'KR') -> Tuple[bool, str]:
        """
        Check if new position would violate any limits

        Args:
            ticker: Stock ticker
            amount_krw: Amount to invest (KRW)
            sector: Stock sector
            region: Market region

        Returns:
            (can_buy: bool, reason: str)
        """
        try:
            total_value = self.get_total_portfolio_value()

            if total_value == 0:
                return (False, "Portfolio value is zero")

            # 1. Check single position limit (15%)
            existing_position = self.get_position_by_ticker(ticker, region)
            existing_value = existing_position.market_value if existing_position else 0
            new_total_value = existing_value + amount_krw
            new_position_percent = (new_total_value / total_value) * 100

            if new_position_percent > self.max_single_position_percent:
                return (False,
                       f"Position limit exceeded: {new_position_percent:.1f}% > {self.max_single_position_percent}% "
                       f"(ticker: {ticker})")

            # 2. Check sector exposure limit (40%)
            sector_exposure = self.calculate_sector_exposure(sector)
            new_sector_exposure = ((sector_exposure * total_value / 100) + amount_krw) / total_value * 100

            if new_sector_exposure > self.max_sector_exposure_percent:
                return (False,
                       f"Sector limit exceeded: {new_sector_exposure:.1f}% > {self.max_sector_exposure_percent}% "
                       f"(sector: {sector})")

            # 3. Check cash reserve limit (20%)
            cash = self.get_available_cash()
            cash_after_buy = cash - amount_krw
            cash_percent_after = (cash_after_buy / total_value) * 100

            if cash_percent_after < self.min_cash_reserve_percent:
                return (False,
                       f"Cash reserve too low: {cash_percent_after:.1f}% < {self.min_cash_reserve_percent}% "
                       f"(need: {cash_after_buy:,.0f} KRW)")

            # 4. Check position count limit (10)
            positions = self.get_all_positions(include_current_price=False)
            current_position_count = len(positions)

            # Check if this is a new position
            is_new_position = not any(p.ticker == ticker and p.region == region for p in positions)

            if is_new_position and current_position_count >= self.max_concurrent_positions:
                return (False,
                       f"Max positions reached: {current_position_count}/{self.max_concurrent_positions}")

            # All checks passed
            return (True, "Position limits OK")

        except Exception as e:
            logger.error(f"Error checking position limits: {e}")
            return (False, f"Error: {str(e)}")

    def calculate_sector_exposure(self, sector: str) -> float:
        """
        Calculate current sector exposure as percentage of portfolio

        Args:
            sector: Sector name

        Returns:
            Sector exposure percentage (0-100)
        """
        try:
            total_value = self.get_total_portfolio_value()

            if total_value == 0:
                return 0.0

            positions = self.get_all_positions(include_current_price=False)

            sector_value = sum(
                pos.market_value for pos in positions
                if pos.sector == sector
            )

            sector_exposure = (sector_value / total_value) * 100

            return sector_exposure

        except Exception as e:
            logger.error(f"Error calculating sector exposure: {e}")
            return 0.0

    def get_sector_exposures(self) -> Dict[str, float]:
        """
        Get all sector exposures

        Returns:
            Dict[sector_name, exposure_percent]
        """
        try:
            total_value = self.get_total_portfolio_value()

            if total_value == 0:
                return {}

            positions = self.get_all_positions(include_current_price=False)

            sector_values = defaultdict(float)
            for pos in positions:
                sector_values[pos.sector] += pos.market_value

            sector_exposures = {
                sector: (value / total_value) * 100
                for sector, value in sector_values.items()
            }

            return sector_exposures

        except Exception as e:
            logger.error(f"Error getting sector exposures: {e}")
            return {}

    # ====================================================================
    # Portfolio Metrics
    # ====================================================================

    def get_portfolio_summary(self) -> PortfolioSummary:
        """
        Get comprehensive portfolio summary

        Returns:
            PortfolioSummary object
        """
        try:
            # Get basic metrics
            total_value = self.get_total_portfolio_value()
            cash = self.get_available_cash()
            positions = self.get_all_positions()

            # Calculate invested amount
            invested = sum(pos.market_value for pos in positions)

            # Calculate percentages
            cash_percent = (cash / total_value * 100) if total_value > 0 else 0
            invested_percent = (invested / total_value * 100) if total_value > 0 else 0

            # Calculate total P&L
            total_cost_basis = sum(pos.cost_basis for pos in positions)
            total_pnl = invested - total_cost_basis
            total_pnl_percent = (total_pnl / total_cost_basis * 100) if total_cost_basis > 0 else 0

            # Calculate daily P&L
            daily_pnl, daily_pnl_percent = self._calculate_daily_pnl()

            # Get sector exposures
            sector_exposures = self.get_sector_exposures()

            # Get largest position
            largest_position = None
            largest_position_percent = 0.0
            if positions:
                largest_position = max(positions, key=lambda p: p.market_value)
                largest_position_percent = largest_position.market_value / total_value * 100

            summary = PortfolioSummary(
                total_value=total_value,
                cash=cash,
                cash_percent=cash_percent,
                invested=invested,
                invested_percent=invested_percent,
                position_count=len(positions),
                total_pnl=total_pnl,
                total_pnl_percent=total_pnl_percent,
                daily_pnl=daily_pnl,
                daily_pnl_percent=daily_pnl_percent,
                sector_exposures=sector_exposures,
                largest_position_percent=largest_position_percent,
                largest_position_ticker=largest_position.ticker if largest_position else None
            )

            return summary

        except Exception as e:
            logger.error(f"Error getting portfolio summary: {e}")
            return PortfolioSummary(
                total_value=self.initial_cash,
                cash=self.initial_cash,
                cash_percent=100.0,
                invested=0.0,
                invested_percent=0.0,
                position_count=0,
                total_pnl=0.0,
                total_pnl_percent=0.0,
                daily_pnl=0.0,
                daily_pnl_percent=0.0,
                sector_exposures={},
                largest_position_percent=0.0
            )

    def _calculate_daily_pnl(self) -> Tuple[float, float]:
        """
        Calculate today's P&L

        Returns:
            (daily_pnl_krw, daily_pnl_percent)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            today = datetime.now().strftime('%Y-%m-%d')

            # Get today's closed trades P&L (calculate from entry/exit prices)
            cursor.execute("""
                SELECT COALESCE(SUM((exit_price - entry_price) * quantity), 0)
                FROM trades
                WHERE trade_status = 'CLOSED'
                  AND exit_price IS NOT NULL
                  AND entry_price IS NOT NULL
                  AND DATE(exit_timestamp) = ?
            """, (today,))

            closed_pnl = cursor.fetchone()[0]

            # Get today's entry value (for percentage calculation)
            cursor.execute("""
                SELECT COALESCE(SUM(entry_price * quantity), 0)
                FROM trades
                WHERE DATE(entry_timestamp) = ?
            """, (today,))

            today_entries = cursor.fetchone()[0]

            conn.close()

            # Calculate percentage
            daily_pnl_percent = (closed_pnl / today_entries * 100) if today_entries > 0 else 0

            return (closed_pnl, daily_pnl_percent)

        except Exception as e:
            logger.error(f"Error calculating daily P&L: {e}")
            return (0.0, 0.0)

    # ====================================================================
    # Helper Methods
    # ====================================================================

    def _get_current_price(self, ticker: str, region: str) -> float:
        """
        Get current price for ticker

        Note: This is a simplified version. In production, would use KIS API.

        Args:
            ticker: Stock ticker
            region: Market region

        Returns:
            Current price (or last known price)
        """
        try:
            # Try to get from recent trades first
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT entry_price
                FROM trades
                WHERE ticker = ? AND region = ?
                ORDER BY entry_timestamp DESC
                LIMIT 1
            """, (ticker, region))

            row = cursor.fetchone()
            conn.close()

            if row:
                return row[0]

            # Fallback: return 0 (would call KIS API in production)
            return 0.0

        except Exception as e:
            logger.error(f"Error getting current price for {ticker}: {e}")
            return 0.0

    # ====================================================================
    # Database Sync Methods
    # ====================================================================

    def sync_portfolio_table(self):
        """
        Sync portfolio table with current trades

        This method updates the portfolio table to reflect current positions
        from the trades table.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Clear existing portfolio
            cursor.execute("DELETE FROM portfolio")

            # Get current positions
            positions = self.get_all_positions()

            # Insert current positions
            for pos in positions:
                cursor.execute("""
                    INSERT INTO portfolio (
                        ticker, region, quantity, avg_entry_price,
                        current_price, market_value, unrealized_pnl,
                        unrealized_pnl_percent, sector,
                        entry_timestamp, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pos.ticker,
                    pos.region,
                    pos.quantity,
                    pos.avg_entry_price,
                    pos.current_price,
                    pos.market_value,
                    pos.unrealized_pnl,
                    pos.unrealized_pnl_percent,
                    pos.sector,
                    pos.entry_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))

            conn.commit()
            conn.close()

            logger.debug(f"✅ Portfolio table synced ({len(positions)} positions)")

        except Exception as e:
            logger.error(f"Failed to sync portfolio table: {e}")

    def log_position_limits(self):
        """
        Log current position limits status
        """
        try:
            logger.info("=" * 70)
            logger.info("[Position Limits Status]")
            logger.info("=" * 70)

            total_value = self.get_total_portfolio_value()
            cash = self.get_available_cash()
            positions = self.get_all_positions(include_current_price=False)
            sector_exposures = self.get_sector_exposures()

            logger.info(f"Total Portfolio Value: {total_value:,.0f} KRW")
            logger.info(f"Cash: {cash:,.0f} KRW ({cash/total_value*100:.1f}%)")
            logger.info(f"Position Count: {len(positions)}/{self.max_concurrent_positions}")

            logger.info(f"\nSector Exposures:")
            for sector, exposure in sorted(sector_exposures.items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {sector}: {exposure:.1f}%")

            logger.info(f"\nLargest Positions:")
            sorted_positions = sorted(positions, key=lambda p: p.market_value, reverse=True)[:5]
            for pos in sorted_positions:
                pos_percent = (pos.market_value / total_value) * 100
                logger.info(f"  {pos.ticker}: {pos_percent:.1f}%")

            logger.info("=" * 70)

        except Exception as e:
            logger.error(f"Error logging position limits: {e}")


# ========================================================================
# Main (for testing)
# ========================================================================

if __name__ == '__main__':
    # Example usage
    pm = PortfolioManager(
        db_path="data/spock_local.db",
        initial_cash=10000000  # 10M KRW
    )

    # Get portfolio summary
    summary = pm.get_portfolio_summary()
    print(f"\nPortfolio Summary:")
    print(f"  Total Value: {summary.total_value:,.0f} KRW")
    print(f"  Cash: {summary.cash:,.0f} KRW ({summary.cash_percent:.1f}%)")
    print(f"  Positions: {summary.position_count}")
    print(f"  Total P&L: {summary.total_pnl:+,.0f} KRW ({summary.total_pnl_percent:+.2f}%)")

    # Check position limits
    can_buy, reason = pm.check_position_limits('005930', 1000000, 'Technology')
    print(f"\nPosition Limit Check:")
    print(f"  Can buy: {can_buy}")
    print(f"  Reason: {reason}")

    # Log position limits
    pm.log_position_limits()
