"""
Risk Management Module for Spock Trading System

Implements automated risk management including:
- Stop loss monitoring (-8% loss trigger)
- Take profit monitoring (+20% gain trigger)
- Circuit breakers (daily loss limit -3%, position count, sector exposure)
- Daily P&L calculations
- Risk metrics tracking

Author: Spock Team
Created: 2025-10-14
Phase: Phase 5 Task 4 - Portfolio Management & Risk Management
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitBreakerType(Enum):
    """Circuit breaker trigger types"""
    DAILY_LOSS_LIMIT = "daily_loss_limit"           # Daily loss exceeds -3%
    POSITION_COUNT_LIMIT = "position_count_limit"   # Too many concurrent positions
    SECTOR_EXPOSURE_LIMIT = "sector_exposure_limit" # Sector concentration too high
    CONSECUTIVE_LOSSES = "consecutive_losses"       # Multiple consecutive losing trades


@dataclass
class RiskLimits:
    """Risk management limits configuration"""
    daily_loss_limit_percent: float = -3.0      # -3% daily loss triggers circuit breaker
    stop_loss_percent: float = -8.0             # -8% individual position stop loss
    take_profit_percent: float = 20.0           # +20% individual position take profit
    max_positions: int = 10                      # Maximum concurrent positions
    max_sector_exposure_percent: float = 40.0   # Maximum sector concentration
    consecutive_loss_threshold: int = 3         # Number of consecutive losses to trigger


@dataclass
class StopLossSignal:
    """Stop loss trigger signal"""
    ticker: str
    region: str
    entry_price: float
    current_price: float
    unrealized_pnl_percent: float
    position_value: float
    trigger_reason: str
    timestamp: datetime


@dataclass
class TakeProfitSignal:
    """Take profit trigger signal"""
    ticker: str
    region: str
    entry_price: float
    current_price: float
    unrealized_pnl_percent: float
    position_value: float
    trigger_reason: str
    timestamp: datetime


@dataclass
class CircuitBreakerSignal:
    """Circuit breaker trigger signal"""
    breaker_type: CircuitBreakerType
    trigger_value: float
    limit_value: float
    trigger_reason: str
    timestamp: datetime
    metadata: Dict


@dataclass
class DailyRiskMetrics:
    """Daily risk metrics summary"""
    date: str
    realized_pnl: float
    realized_pnl_percent: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    total_pnl: float
    total_pnl_percent: float
    num_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    consecutive_wins: int
    consecutive_losses: int
    circuit_breaker_triggered: bool


class RiskManager:
    """
    Risk Manager for automated risk management

    Features:
    - Stop loss monitoring (-8% loss trigger)
    - Take profit monitoring (+20% gain trigger)
    - Circuit breakers (daily loss -3%, position count, sector exposure)
    - Daily P&L calculations
    - Risk metrics tracking

    MVP Implementation:
    - Simplified stop loss/take profit based on entry price
    - Basic circuit breakers without complex recovery
    - Deferred: ATR-based trailing stops, VaR, Sharpe ratio calculation
    """

    def __init__(self, db_path: str, risk_limits: Optional[RiskLimits] = None):
        """
        Initialize RiskManager

        Args:
            db_path: Path to SQLite database
            risk_limits: Risk limits configuration (defaults to RiskLimits())
        """
        self.db_path = db_path
        self.risk_limits = risk_limits or RiskLimits()

        logger.info(f"🛡️ RiskManager initialized with limits: "
                   f"daily_loss={self.risk_limits.daily_loss_limit_percent}%, "
                   f"stop_loss={self.risk_limits.stop_loss_percent}%, "
                   f"take_profit={self.risk_limits.take_profit_percent}%")

    # ============================================================
    # Stop Loss Monitoring
    # ============================================================

    def check_stop_loss_conditions(self) -> List[StopLossSignal]:
        """
        Check all open positions for stop loss conditions

        Stop Loss Rule (Mark Minervini):
        - Trigger when position loss exceeds -8% from entry price

        Returns:
            List of StopLossSignal for positions that hit stop loss
        """
        try:
            stop_loss_signals = []

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Query open positions with unrealized P&L
                cursor.execute("""
                    SELECT
                        t.ticker,
                        t.region,
                        AVG(t.entry_price) as avg_entry_price,
                        SUM(t.quantity) as total_quantity,
                        t.entry_price as last_price  -- Simplified: use entry price as current
                    FROM trades t
                    WHERE t.trade_status = 'OPEN'
                    GROUP BY t.ticker, t.region
                    HAVING total_quantity > 0
                """)

                positions = cursor.fetchall()

                for ticker, region, avg_entry_price, quantity, current_price in positions:
                    # Calculate unrealized P&L percentage
                    unrealized_pnl_percent = ((current_price - avg_entry_price) / avg_entry_price) * 100

                    # Check stop loss condition
                    if unrealized_pnl_percent <= self.risk_limits.stop_loss_percent:
                        position_value = quantity * current_price

                        signal = StopLossSignal(
                            ticker=ticker,
                            region=region,
                            entry_price=avg_entry_price,
                            current_price=current_price,
                            unrealized_pnl_percent=unrealized_pnl_percent,
                            position_value=position_value,
                            trigger_reason=f"Loss {unrealized_pnl_percent:.2f}% exceeds stop loss {self.risk_limits.stop_loss_percent}%",
                            timestamp=datetime.now()
                        )

                        stop_loss_signals.append(signal)
                        logger.warning(f"⛔ Stop Loss Triggered: {ticker} ({region}) - "
                                     f"Loss: {unrealized_pnl_percent:.2f}% "
                                     f"(Entry: {avg_entry_price:,.0f}, Current: {current_price:,.0f})")

            return stop_loss_signals

        except Exception as e:
            logger.error(f"❌ Stop loss check failed: {e}")
            return []

    # ============================================================
    # Take Profit Monitoring
    # ============================================================

    def check_take_profit_conditions(self) -> List[TakeProfitSignal]:
        """
        Check all open positions for take profit conditions

        Take Profit Rule (William O'Neil):
        - Trigger when position gain exceeds +20% from entry price

        Returns:
            List of TakeProfitSignal for positions that hit take profit
        """
        try:
            take_profit_signals = []

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Query open positions with unrealized P&L
                cursor.execute("""
                    SELECT
                        t.ticker,
                        t.region,
                        AVG(t.entry_price) as avg_entry_price,
                        SUM(t.quantity) as total_quantity,
                        t.entry_price as last_price  -- Simplified: use entry price as current
                    FROM trades t
                    WHERE t.trade_status = 'OPEN'
                    GROUP BY t.ticker, t.region
                    HAVING total_quantity > 0
                """)

                positions = cursor.fetchall()

                for ticker, region, avg_entry_price, quantity, current_price in positions:
                    # Calculate unrealized P&L percentage
                    unrealized_pnl_percent = ((current_price - avg_entry_price) / avg_entry_price) * 100

                    # Check take profit condition
                    if unrealized_pnl_percent >= self.risk_limits.take_profit_percent:
                        position_value = quantity * current_price

                        signal = TakeProfitSignal(
                            ticker=ticker,
                            region=region,
                            entry_price=avg_entry_price,
                            current_price=current_price,
                            unrealized_pnl_percent=unrealized_pnl_percent,
                            position_value=position_value,
                            trigger_reason=f"Gain {unrealized_pnl_percent:.2f}% exceeds take profit {self.risk_limits.take_profit_percent}%",
                            timestamp=datetime.now()
                        )

                        take_profit_signals.append(signal)
                        logger.info(f"🎯 Take Profit Triggered: {ticker} ({region}) - "
                                   f"Gain: {unrealized_pnl_percent:.2f}% "
                                   f"(Entry: {avg_entry_price:,.0f}, Current: {current_price:,.0f})")

            return take_profit_signals

        except Exception as e:
            logger.error(f"❌ Take profit check failed: {e}")
            return []

    # ============================================================
    # Circuit Breakers
    # ============================================================

    def check_circuit_breakers(self, total_portfolio_value: float) -> List[CircuitBreakerSignal]:
        """
        Check all circuit breaker conditions

        Circuit Breakers:
        1. Daily Loss Limit: Daily P&L < -3% of portfolio value
        2. Position Count Limit: Open positions > max_positions (10)
        3. Sector Exposure Limit: Single sector > 40% of portfolio
        4. Consecutive Losses: More than 3 consecutive losing trades

        Args:
            total_portfolio_value: Current total portfolio value

        Returns:
            List of CircuitBreakerSignal for triggered breakers
        """
        breaker_signals = []

        # Check 1: Daily Loss Limit
        daily_loss_signal = self._check_daily_loss_limit(total_portfolio_value)
        if daily_loss_signal:
            breaker_signals.append(daily_loss_signal)

        # Check 2: Position Count Limit
        position_count_signal = self._check_position_count_limit()
        if position_count_signal:
            breaker_signals.append(position_count_signal)

        # Check 3: Sector Exposure Limit
        sector_exposure_signal = self._check_sector_exposure_limit(total_portfolio_value)
        if sector_exposure_signal:
            breaker_signals.append(sector_exposure_signal)

        # Check 4: Consecutive Losses
        consecutive_loss_signal = self._check_consecutive_losses()
        if consecutive_loss_signal:
            breaker_signals.append(consecutive_loss_signal)

        return breaker_signals

    def _check_daily_loss_limit(self, total_portfolio_value: float) -> Optional[CircuitBreakerSignal]:
        """Check if daily loss exceeds -3% limit"""
        try:
            daily_pnl = self.calculate_daily_pnl()
            daily_pnl_percent = (daily_pnl / total_portfolio_value) * 100 if total_portfolio_value > 0 else 0

            if daily_pnl_percent <= self.risk_limits.daily_loss_limit_percent:
                signal = CircuitBreakerSignal(
                    breaker_type=CircuitBreakerType.DAILY_LOSS_LIMIT,
                    trigger_value=daily_pnl_percent,
                    limit_value=self.risk_limits.daily_loss_limit_percent,
                    trigger_reason=f"Daily loss {daily_pnl_percent:.2f}% exceeds limit {self.risk_limits.daily_loss_limit_percent}%",
                    timestamp=datetime.now(),
                    metadata={
                        'daily_pnl': daily_pnl,
                        'portfolio_value': total_portfolio_value
                    }
                )

                logger.error(f"🚨 CIRCUIT BREAKER: Daily Loss Limit - "
                           f"Loss: {daily_pnl_percent:.2f}% ({daily_pnl:,.0f} KRW)")

                # Log to circuit_breaker_logs table
                self._log_circuit_breaker(signal)

                return signal

            return None

        except Exception as e:
            logger.error(f"❌ Daily loss limit check failed: {e}")
            return None

    def _check_position_count_limit(self) -> Optional[CircuitBreakerSignal]:
        """Check if open positions exceed limit"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Count open positions
                cursor.execute("""
                    SELECT COUNT(DISTINCT ticker || region)
                    FROM trades
                    WHERE trade_status = 'OPEN'
                """)

                open_positions = cursor.fetchone()[0]

                if open_positions > self.risk_limits.max_positions:
                    signal = CircuitBreakerSignal(
                        breaker_type=CircuitBreakerType.POSITION_COUNT_LIMIT,
                        trigger_value=float(open_positions),
                        limit_value=float(self.risk_limits.max_positions),
                        trigger_reason=f"Open positions {open_positions} exceeds limit {self.risk_limits.max_positions}",
                        timestamp=datetime.now(),
                        metadata={'open_positions': open_positions}
                    )

                    logger.error(f"🚨 CIRCUIT BREAKER: Position Count - "
                               f"{open_positions} positions (limit: {self.risk_limits.max_positions})")

                    self._log_circuit_breaker(signal)
                    return signal

            return None

        except Exception as e:
            logger.error(f"❌ Position count check failed: {e}")
            return None

    def _check_sector_exposure_limit(self, total_portfolio_value: float) -> Optional[CircuitBreakerSignal]:
        """Check if any sector exposure exceeds 40% limit"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Calculate sector exposures
                cursor.execute("""
                    SELECT
                        COALESCE(td.sector, t.sector, 'Unknown') as sector,
                        SUM(t.quantity * t.entry_price) as sector_value
                    FROM trades t
                    LEFT JOIN ticker_details td ON t.ticker = td.ticker AND t.region = td.region
                    WHERE t.trade_status = 'OPEN'
                    GROUP BY COALESCE(td.sector, t.sector, 'Unknown')
                """)

                sector_exposures = cursor.fetchall()

                for sector, sector_value in sector_exposures:
                    exposure_percent = (sector_value / total_portfolio_value) * 100 if total_portfolio_value > 0 else 0

                    if exposure_percent > self.risk_limits.max_sector_exposure_percent:
                        signal = CircuitBreakerSignal(
                            breaker_type=CircuitBreakerType.SECTOR_EXPOSURE_LIMIT,
                            trigger_value=exposure_percent,
                            limit_value=self.risk_limits.max_sector_exposure_percent,
                            trigger_reason=f"Sector {sector} exposure {exposure_percent:.2f}% exceeds limit {self.risk_limits.max_sector_exposure_percent}%",
                            timestamp=datetime.now(),
                            metadata={
                                'sector': sector,
                                'sector_value': sector_value,
                                'portfolio_value': total_portfolio_value
                            }
                        )

                        logger.error(f"🚨 CIRCUIT BREAKER: Sector Exposure - "
                                   f"{sector}: {exposure_percent:.2f}% (limit: {self.risk_limits.max_sector_exposure_percent}%)")

                        self._log_circuit_breaker(signal)
                        return signal

            return None

        except Exception as e:
            logger.error(f"❌ Sector exposure check failed: {e}")
            return None

    def _check_consecutive_losses(self) -> Optional[CircuitBreakerSignal]:
        """Check if consecutive losing trades exceed threshold"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get recent closed trades ordered by timestamp
                cursor.execute("""
                    SELECT
                        exit_price - entry_price as pnl
                    FROM trades
                    WHERE trade_status = 'CLOSED'
                    ORDER BY exit_timestamp DESC
                    LIMIT ?
                """, (self.risk_limits.consecutive_loss_threshold * 2,))

                recent_trades = cursor.fetchall()

                if not recent_trades:
                    return None

                # Count consecutive losses from most recent trade
                consecutive_losses = 0
                for (pnl,) in recent_trades:
                    if pnl < 0:
                        consecutive_losses += 1
                    else:
                        break

                if consecutive_losses >= self.risk_limits.consecutive_loss_threshold:
                    signal = CircuitBreakerSignal(
                        breaker_type=CircuitBreakerType.CONSECUTIVE_LOSSES,
                        trigger_value=float(consecutive_losses),
                        limit_value=float(self.risk_limits.consecutive_loss_threshold),
                        trigger_reason=f"Consecutive losses {consecutive_losses} exceeds threshold {self.risk_limits.consecutive_loss_threshold}",
                        timestamp=datetime.now(),
                        metadata={'consecutive_losses': consecutive_losses}
                    )

                    logger.error(f"🚨 CIRCUIT BREAKER: Consecutive Losses - "
                               f"{consecutive_losses} losing trades in a row")

                    self._log_circuit_breaker(signal)
                    return signal

            return None

        except Exception as e:
            logger.error(f"❌ Consecutive losses check failed: {e}")
            return None

    def _log_circuit_breaker(self, signal: CircuitBreakerSignal):
        """Log circuit breaker trigger to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO circuit_breaker_logs
                    (breaker_type, trigger_value, limit_value, trigger_reason, metadata, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    signal.breaker_type.value,
                    signal.trigger_value,
                    signal.limit_value,
                    signal.trigger_reason,
                    str(signal.metadata),
                    signal.timestamp.isoformat()
                ))

                conn.commit()
                logger.info(f"📝 Circuit breaker logged: {signal.breaker_type.value}")

        except Exception as e:
            logger.error(f"❌ Failed to log circuit breaker: {e}")

    # ============================================================
    # Daily P&L Calculations
    # ============================================================

    def calculate_daily_pnl(self, date: Optional[str] = None) -> float:
        """
        Calculate realized P&L for a specific date

        Args:
            date: Date string in YYYY-MM-DD format (default: today)

        Returns:
            Total realized P&L in KRW
        """
        try:
            if date is None:
                date = datetime.now().strftime('%Y-%m-%d')

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Calculate realized P&L from closed trades
                cursor.execute("""
                    SELECT SUM((exit_price - entry_price) * quantity)
                    FROM trades
                    WHERE trade_status = 'CLOSED'
                      AND DATE(exit_timestamp) = ?
                """, (date,))

                result = cursor.fetchone()
                daily_pnl = result[0] if result[0] is not None else 0.0

                return daily_pnl

        except Exception as e:
            logger.error(f"❌ Daily P&L calculation failed: {e}")
            return 0.0

    def get_daily_risk_metrics(self, date: Optional[str] = None) -> DailyRiskMetrics:
        """
        Calculate comprehensive daily risk metrics

        Args:
            date: Date string in YYYY-MM-DD format (default: today)

        Returns:
            DailyRiskMetrics with all calculated metrics
        """
        try:
            if date is None:
                date = datetime.now().strftime('%Y-%m-%d')

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get closed trades for the day
                cursor.execute("""
                    SELECT
                        (exit_price - entry_price) * quantity as realized_pnl
                    FROM trades
                    WHERE trade_status = 'CLOSED'
                      AND DATE(exit_timestamp) = ?
                """, (date,))

                closed_trades = [row[0] for row in cursor.fetchall()]

                # Calculate metrics
                num_trades = len(closed_trades)
                realized_pnl = sum(closed_trades)

                winning_trades = [pnl for pnl in closed_trades if pnl > 0]
                losing_trades = [pnl for pnl in closed_trades if pnl < 0]

                win_rate = (len(winning_trades) / num_trades * 100) if num_trades > 0 else 0.0
                avg_win = (sum(winning_trades) / len(winning_trades)) if winning_trades else 0.0
                avg_loss = (sum(losing_trades) / len(losing_trades)) if losing_trades else 0.0
                largest_win = max(winning_trades) if winning_trades else 0.0
                largest_loss = min(losing_trades) if losing_trades else 0.0

                # Count consecutive wins/losses
                consecutive_wins = 0
                consecutive_losses = 0
                current_streak_type = None
                current_streak = 0

                for pnl in reversed(closed_trades):
                    if pnl > 0:
                        if current_streak_type == 'win':
                            current_streak += 1
                        else:
                            current_streak_type = 'win'
                            current_streak = 1
                    else:
                        if current_streak_type == 'loss':
                            current_streak += 1
                        else:
                            current_streak_type = 'loss'
                            current_streak = 1

                if current_streak_type == 'win':
                    consecutive_wins = current_streak
                elif current_streak_type == 'loss':
                    consecutive_losses = current_streak

                # Check if circuit breaker was triggered
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM circuit_breaker_logs
                    WHERE DATE(timestamp) = ?
                """, (date,))

                circuit_breaker_triggered = cursor.fetchone()[0] > 0

                # Calculate portfolio value for percentage calculations
                # Simplified: assume 10M KRW initial capital
                portfolio_value = 10000000.0  # TODO: Get from PortfolioManager

                metrics = DailyRiskMetrics(
                    date=date,
                    realized_pnl=realized_pnl,
                    realized_pnl_percent=(realized_pnl / portfolio_value) * 100 if portfolio_value > 0 else 0,
                    unrealized_pnl=0.0,  # TODO: Calculate from open positions
                    unrealized_pnl_percent=0.0,
                    total_pnl=realized_pnl,
                    total_pnl_percent=(realized_pnl / portfolio_value) * 100 if portfolio_value > 0 else 0,
                    num_trades=num_trades,
                    win_rate=win_rate,
                    avg_win=avg_win,
                    avg_loss=avg_loss,
                    largest_win=largest_win,
                    largest_loss=largest_loss,
                    consecutive_wins=consecutive_wins,
                    consecutive_losses=consecutive_losses,
                    circuit_breaker_triggered=circuit_breaker_triggered
                )

                return metrics

        except Exception as e:
            logger.error(f"❌ Daily risk metrics calculation failed: {e}")
            # Return empty metrics
            return DailyRiskMetrics(
                date=date or datetime.now().strftime('%Y-%m-%d'),
                realized_pnl=0.0,
                realized_pnl_percent=0.0,
                unrealized_pnl=0.0,
                unrealized_pnl_percent=0.0,
                total_pnl=0.0,
                total_pnl_percent=0.0,
                num_trades=0,
                win_rate=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                largest_win=0.0,
                largest_loss=0.0,
                consecutive_wins=0,
                consecutive_losses=0,
                circuit_breaker_triggered=False
            )

    # ============================================================
    # Risk Reporting
    # ============================================================

    def generate_risk_report(self) -> str:
        """
        Generate comprehensive risk management report

        Returns:
            Formatted risk report string
        """
        try:
            # Get today's risk metrics
            metrics = self.get_daily_risk_metrics()

            report = f"""
╔══════════════════════════════════════════════════════════════╗
║              RISK MANAGEMENT REPORT - {metrics.date}           ║
╠══════════════════════════════════════════════════════════════╣
║ Daily P&L                                                     ║
║   Realized P&L:     {metrics.realized_pnl:>12,.0f} KRW ({metrics.realized_pnl_percent:>6.2f}%)  ║
║   Unrealized P&L:   {metrics.unrealized_pnl:>12,.0f} KRW ({metrics.unrealized_pnl_percent:>6.2f}%)  ║
║   Total P&L:        {metrics.total_pnl:>12,.0f} KRW ({metrics.total_pnl_percent:>6.2f}%)  ║
╠══════════════════════════════════════════════════════════════╣
║ Trading Performance                                           ║
║   Number of Trades: {metrics.num_trades:>12}                          ║
║   Win Rate:         {metrics.win_rate:>12.2f}%                        ║
║   Avg Win:          {metrics.avg_win:>12,.0f} KRW                     ║
║   Avg Loss:         {metrics.avg_loss:>12,.0f} KRW                    ║
║   Largest Win:      {metrics.largest_win:>12,.0f} KRW                 ║
║   Largest Loss:     {metrics.largest_loss:>12,.0f} KRW                ║
╠══════════════════════════════════════════════════════════════╣
║ Risk Status                                                   ║
║   Consecutive Wins:  {metrics.consecutive_wins:>12}                   ║
║   Consecutive Losses:{metrics.consecutive_losses:>12}                 ║
║   Circuit Breaker:   {"TRIGGERED" if metrics.circuit_breaker_triggered else "Normal":>12}           ║
╚══════════════════════════════════════════════════════════════╝
"""

            return report

        except Exception as e:
            logger.error(f"❌ Risk report generation failed: {e}")
            return f"Risk report generation failed: {e}"
