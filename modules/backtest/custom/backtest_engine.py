"""
Custom Event-Driven Backtesting Engine

Production-grade backtesting engine with bar-by-bar event processing.
Complements VectorBT by providing:
- Order-level execution validation
- Custom order types and logic
- Compliance auditing and trade logging
- Realistic market microstructure simulation

Performance Target: <30s for 5-year backtest (10 stocks)
Accuracy Target: >95% match with VectorBT reference results

Architecture:
┌─────────────────────────────────────────────────────────────┐
│                    BacktestEngine                            │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │  Event   │→│  Signal      │→│  Order Execution   │   │
│  │  Loop    │  │  Interpreter │  │  Engine            │   │
│  └──────────┘  └──────────────┘  └────────────────────┘   │
│       ↓              ↓                    ↓                 │
│  ┌──────────────────────────────────────────────────┐      │
│  │           Position Tracker                        │      │
│  │  (Holdings, Cash, Portfolio Value, P&L)          │      │
│  └──────────────────────────────────────────────────┘      │
│       ↓                                                      │
│  ┌──────────────────────────────────────────────────┐      │
│  │           Trade Logger                            │      │
│  │  (Entry/Exit, P&L, Holding Period)               │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘

Usage:
    from modules.backtest.custom.backtest_engine import BacktestEngine
    from modules.backtest.common.costs import TransactionCostModel

    engine = BacktestEngine(
        initial_capital=100_000_000,
        cost_model=TransactionCostModel(broker='KIS')
    )

    results = engine.run(
        data={'005930': ohlcv_df},
        signals={'005930': signal_series}
    )
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger
import time

from .orders import (
    OrderExecutionEngine, Order, OrderType, OrderSide, OrderStatus, Fill
)
from modules.backtest.common.costs import TransactionCostModel
from modules.backtest.common.metrics import PerformanceMetrics


@dataclass
class Position:
    """Current position representation"""
    ticker: str
    quantity: int
    entry_price: float
    entry_date: datetime
    current_price: float = 0.0
    unrealized_pnl: float = 0.0

    def update(self, current_price: float):
        """Update position with current market price"""
        self.current_price = current_price
        self.unrealized_pnl = (current_price - self.entry_price) * self.quantity


@dataclass
class Trade:
    """Completed trade representation"""
    ticker: str
    side: str  # 'LONG' or 'SHORT'
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    commission: float
    tax: float
    holding_days: int

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFrame construction"""
        return {
            'ticker': self.ticker,
            'side': self.side,
            'entry_date': self.entry_date,
            'exit_date': self.exit_date,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'quantity': self.quantity,
            'pnl': self.pnl,
            'pnl_pct': self.pnl_pct,
            'commission': self.commission,
            'tax': self.tax,
            'holding_days': self.holding_days
        }


class PositionTracker:
    """
    Portfolio position and cash management system.

    Tracks:
    - Cash balance
    - Open positions (holdings)
    - Portfolio value (cash + position values)
    - Realized and unrealized P&L
    - Equity curve over time
    """

    def __init__(self, initial_capital: float):
        """
        Initialize position tracker.

        Args:
            initial_capital: Starting cash balance
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.equity_curve: List[Tuple[datetime, float]] = []

        logger.debug(f"PositionTracker initialized: capital=₩{initial_capital:,.0f}")

    def get_position(self, ticker: str) -> Optional[Position]:
        """Get current position for ticker"""
        return self.positions.get(ticker)

    def has_position(self, ticker: str) -> bool:
        """Check if position exists for ticker"""
        return ticker in self.positions

    def add_position(self, ticker: str, quantity: int, price: float, date: datetime):
        """
        Add new position or increase existing position.

        Args:
            ticker: Stock ticker
            quantity: Number of shares
            price: Entry price
            date: Entry date
        """
        if self.has_position(ticker):
            # Average up/down existing position
            existing = self.positions[ticker]
            total_quantity = existing.quantity + quantity
            avg_price = (
                (existing.entry_price * existing.quantity + price * quantity) /
                total_quantity
            )
            existing.quantity = total_quantity
            existing.entry_price = avg_price
        else:
            # New position
            self.positions[ticker] = Position(
                ticker=ticker,
                quantity=quantity,
                entry_price=price,
                entry_date=date,
                current_price=price
            )

        logger.debug(f"Position added: {ticker} {quantity}@₩{price:,.0f}")

    def reduce_position(self, ticker: str, quantity: int) -> Optional[Position]:
        """
        Reduce or close position.

        Args:
            ticker: Stock ticker
            quantity: Number of shares to reduce

        Returns:
            Closed position if fully exited, None otherwise
        """
        if not self.has_position(ticker):
            logger.warning(f"Attempted to reduce non-existent position: {ticker}")
            return None

        position = self.positions[ticker]

        if quantity >= position.quantity:
            # Full exit
            closed_position = position
            del self.positions[ticker]
            logger.debug(f"Position closed: {ticker}")
            return closed_position
        else:
            # Partial exit
            position.quantity -= quantity
            logger.debug(f"Position reduced: {ticker} by {quantity} shares")
            return None

    def update_prices(self, prices: Dict[str, float]):
        """
        Update all position prices and unrealized P&L.

        Args:
            prices: Dictionary of {ticker: current_price}
        """
        for ticker, position in self.positions.items():
            if ticker in prices:
                position.update(prices[ticker])

    def get_portfolio_value(self) -> float:
        """Calculate total portfolio value (cash + positions)"""
        position_value = sum(
            pos.quantity * pos.current_price
            for pos in self.positions.values()
        )
        return self.cash + position_value

    def get_holdings(self) -> Dict[str, int]:
        """Get current holdings as {ticker: quantity}"""
        return {ticker: pos.quantity for ticker, pos in self.positions.items()}

    def get_unrealized_pnl(self) -> float:
        """Calculate total unrealized P&L"""
        return sum(pos.unrealized_pnl for pos in self.positions.values())

    def record_equity(self, date: datetime):
        """Record current portfolio value for equity curve"""
        self.equity_curve.append((date, self.get_portfolio_value()))

    def get_equity_curve_df(self) -> pd.DataFrame:
        """Get equity curve as DataFrame"""
        if not self.equity_curve:
            return pd.DataFrame(columns=['date', 'portfolio_value'])

        df = pd.DataFrame(self.equity_curve, columns=['date', 'portfolio_value'])
        df.set_index('date', inplace=True)
        return df


class SignalInterpreter:
    """
    Translates strategy signals into order submissions.

    Handles:
    - Signal-to-order logic
    - Position sizing (equal weight, risk parity, Kelly)
    - Rebalancing (buy/sell/hold decisions)
    - Order batching for efficiency
    """

    def __init__(
        self,
        position_tracker: PositionTracker,
        order_engine: OrderExecutionEngine,
        size_type: str = 'equal_weight',
        target_positions: int = 3
    ):
        """
        Initialize signal interpreter.

        Args:
            position_tracker: Position tracking system
            order_engine: Order execution engine
            size_type: Position sizing method ('equal_weight', 'risk_parity', 'kelly')
            target_positions: Number of target positions to hold
        """
        self.tracker = position_tracker
        self.engine = order_engine
        self.size_type = size_type
        self.target_positions = target_positions

        logger.debug(f"SignalInterpreter initialized: size={size_type}, n={target_positions}")

    def interpret_signals(
        self,
        signals: Dict[str, bool],
        prices: Dict[str, float],
        date: datetime
    ) -> List[Order]:
        """
        Convert signals to orders.

        Args:
            signals: {ticker: should_hold} boolean dict
            prices: {ticker: current_price} dict
            date: Current date

        Returns:
            List of orders to submit
        """
        orders = []
        current_holdings = self.tracker.get_holdings()

        # Determine target holdings from signals
        target_tickers = {ticker for ticker, signal in signals.items() if signal}
        current_tickers = set(current_holdings.keys())

        # Tickers to exit
        to_exit = current_tickers - target_tickers
        for ticker in to_exit:
            quantity = current_holdings[ticker]
            order = self.engine.submit_order(
                ticker=ticker,
                order_type=OrderType.MARKET,
                side=OrderSide.SELL,
                quantity=quantity
            )
            orders.append(order)
            logger.debug(f"Exit order: {ticker} {quantity} shares")

        # Tickers to enter or rebalance
        to_enter = target_tickers - current_tickers

        if to_enter:
            # Calculate position sizes
            allocation_per_position = self.tracker.cash / len(to_enter)

            for ticker in to_enter:
                if ticker not in prices:
                    logger.warning(f"No price for {ticker}, skipping")
                    continue

                price = prices[ticker]
                quantity = int(allocation_per_position / price)

                if quantity > 0:
                    order = self.engine.submit_order(
                        ticker=ticker,
                        order_type=OrderType.MARKET,
                        side=OrderSide.BUY,
                        quantity=quantity
                    )
                    orders.append(order)
                    logger.debug(f"Entry order: {ticker} {quantity}@₩{price:,.0f}")

        return orders


class TradeLogger:
    """
    Records and analyzes completed trades.

    Tracks:
    - Entry and exit prices/dates
    - P&L (absolute and percentage)
    - Transaction costs
    - Holding periods
    - Trade statistics
    """

    def __init__(self):
        """Initialize trade logger"""
        self.trades: List[Trade] = []
        logger.debug("TradeLogger initialized")

    def record_trade(
        self,
        ticker: str,
        entry_date: datetime,
        exit_date: datetime,
        entry_price: float,
        exit_price: float,
        quantity: int,
        commission: float,
        tax: float
    ):
        """
        Record completed trade.

        Args:
            ticker: Stock ticker
            entry_date: Trade entry date
            exit_date: Trade exit date
            entry_price: Entry price
            exit_price: Exit price
            quantity: Number of shares
            commission: Total commission paid
            tax: Total tax paid
        """
        gross_pnl = (exit_price - entry_price) * quantity
        net_pnl = gross_pnl - commission - tax
        pnl_pct = (exit_price - entry_price) / entry_price
        holding_days = (exit_date - entry_date).days

        trade = Trade(
            ticker=ticker,
            side='LONG',  # TODO: Support short positions
            entry_date=entry_date,
            exit_date=exit_date,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            pnl=net_pnl,
            pnl_pct=pnl_pct,
            commission=commission,
            tax=tax,
            holding_days=holding_days
        )

        self.trades.append(trade)
        logger.debug(f"Trade logged: {ticker} P&L=₩{net_pnl:,.0f} ({pnl_pct:.2%})")

    def get_trades_df(self) -> pd.DataFrame:
        """Get all trades as DataFrame"""
        if not self.trades:
            return pd.DataFrame()

        return pd.DataFrame([t.to_dict() for t in self.trades])

    def get_trade_stats(self) -> Dict:
        """Calculate trade statistics"""
        if not self.trades:
            return {}

        df = self.get_trades_df()

        return {
            'total_trades': len(df),
            'winning_trades': len(df[df['pnl'] > 0]),
            'losing_trades': len(df[df['pnl'] < 0]),
            'win_rate': len(df[df['pnl'] > 0]) / len(df),
            'avg_win': df[df['pnl'] > 0]['pnl'].mean() if len(df[df['pnl'] > 0]) > 0 else 0,
            'avg_loss': df[df['pnl'] < 0]['pnl'].mean() if len(df[df['pnl'] < 0]) > 0 else 0,
            'avg_holding_days': df['holding_days'].mean(),
            'total_pnl': df['pnl'].sum(),
            'total_commission': df['commission'].sum(),
            'total_tax': df['tax'].sum()
        }


class BacktestEngine:
    """
    Custom event-driven backtesting engine.

    Provides production-grade backtesting with:
    - Bar-by-bar event processing
    - Realistic order execution
    - Position tracking and portfolio accounting
    - Comprehensive trade logging
    - Performance metrics calculation

    Performance: Target <30s for 5-year backtest (10 stocks)
    Accuracy: Target >95% match with VectorBT
    """

    def __init__(
        self,
        initial_capital: float = 100_000_000,
        cost_model: Optional[TransactionCostModel] = None,
        size_type: str = 'equal_weight',
        target_positions: int = 3
    ):
        """
        Initialize backtesting engine.

        Args:
            initial_capital: Starting capital (KRW)
            cost_model: Transaction cost model (defaults to KIS broker)
            size_type: Position sizing method
            target_positions: Number of positions to hold
        """
        self.initial_capital = initial_capital

        # Initialize components
        if cost_model is None:
            cost_model = TransactionCostModel(broker='KIS', slippage_bps=5.0)

        self.order_engine = OrderExecutionEngine(cost_model=cost_model)
        self.tracker = PositionTracker(initial_capital)
        self.interpreter = SignalInterpreter(
            self.tracker,
            self.order_engine,
            size_type=size_type,
            target_positions=target_positions
        )
        self.trade_logger = TradeLogger()

        logger.info(f"BacktestEngine initialized: capital=₩{initial_capital:,.0f}")

    def run(
        self,
        data: Dict[str, pd.DataFrame],
        signals: Dict[str, pd.Series],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict:
        """
        Run backtest with event-driven simulation.

        Args:
            data: {ticker: OHLCV DataFrame} with DatetimeIndex
            signals: {ticker: boolean Series} indicating hold/no-hold
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)

        Returns:
            Dictionary with backtest results:
            - metrics: Performance metrics dict
            - equity_curve: Portfolio value over time
            - trades: Trade log DataFrame
            - trade_stats: Trade statistics dict
        """
        start_time = time.time()
        logger.info("=" * 80)
        logger.info("CUSTOM BACKTEST ENGINE - Starting Simulation")
        logger.info("=" * 80)

        # Align all data to common date range
        all_dates = self._get_common_dates(data, start_date, end_date)
        logger.info(f"Simulation period: {all_dates[0]} to {all_dates[-1]} ({len(all_dates)} days)")

        # Event loop: Bar-by-bar processing
        for i, current_date in enumerate(all_dates):
            # Get current prices for all tickers
            current_prices = {
                ticker: df.loc[current_date, 'close']
                for ticker, df in data.items()
                if current_date in df.index
            }

            # Update position values with current prices
            self.tracker.update_prices(current_prices)

            # Get current signals
            current_signals = {
                ticker: sig.loc[current_date] if current_date in sig.index else False
                for ticker, sig in signals.items()
            }

            # Interpret signals → generate orders
            orders = self.interpreter.interpret_signals(
                current_signals,
                current_prices,
                current_date
            )

            # Process bar: Execute orders
            for order in orders:
                ticker = order.ticker
                if ticker not in data or current_date not in data[ticker].index:
                    continue

                bar = data[ticker].loc[current_date]
                fills = self.order_engine.process_bar(bar, volume=bar['volume'])

                # Update positions based on fills
                for fill in fills:
                    self._process_fill(fill, current_date)

            # Record equity for this bar
            self.tracker.record_equity(current_date)

            # Progress logging every 100 days
            if (i + 1) % 100 == 0:
                portfolio_value = self.tracker.get_portfolio_value()
                logger.info(f"Day {i+1}/{len(all_dates)}: Portfolio=₩{portfolio_value:,.0f}")

        # Calculate final results
        execution_time = time.time() - start_time
        logger.info(f"✅ Simulation completed in {execution_time:.2f}s")

        results = self._calculate_results()
        results['execution_time'] = execution_time

        return results

    def _get_common_dates(
        self,
        data: Dict[str, pd.DataFrame],
        start_date: Optional[str],
        end_date: Optional[str]
    ) -> pd.DatetimeIndex:
        """Get common date range across all tickers"""
        # Find union of all dates
        all_dates = pd.DatetimeIndex([])
        for df in data.values():
            all_dates = all_dates.union(df.index)

        all_dates = all_dates.sort_values()

        # Apply date filters
        if start_date:
            all_dates = all_dates[all_dates >= pd.to_datetime(start_date)]
        if end_date:
            all_dates = all_dates[all_dates <= pd.to_datetime(end_date)]

        return all_dates

    def _process_fill(self, fill: Fill, current_date: datetime):
        """Process order fill and update positions/cash"""
        ticker = fill.ticker

        if fill.side == OrderSide.BUY:
            # Deduct cash
            total_cost = fill.value + fill.commission + fill.slippage
            self.tracker.cash -= total_cost

            # Add/increase position
            self.tracker.add_position(
                ticker,
                fill.quantity,
                fill.price,
                current_date
            )

        elif fill.side == OrderSide.SELL:
            # Add cash
            net_proceeds = fill.value - fill.commission - fill.tax - fill.slippage
            self.tracker.cash += net_proceeds

            # Reduce/close position
            closed_position = self.tracker.reduce_position(ticker, fill.quantity)

            # Log trade if position fully closed
            if closed_position:
                self.trade_logger.record_trade(
                    ticker=ticker,
                    entry_date=closed_position.entry_date,
                    exit_date=current_date,
                    entry_price=closed_position.entry_price,
                    exit_price=fill.price,
                    quantity=fill.quantity,
                    commission=fill.commission,
                    tax=fill.tax
                )

    def _calculate_results(self) -> Dict:
        """Calculate final backtest results and metrics"""
        # Get equity curve
        equity_df = self.tracker.get_equity_curve_df()

        if len(equity_df) == 0:
            logger.warning("No equity curve data - empty backtest")
            return {}

        # Calculate returns
        returns = equity_df['portfolio_value'].pct_change().dropna()

        # Calculate performance metrics
        metrics_calc = PerformanceMetrics(returns, risk_free_rate=0.0)
        metrics = metrics_calc.calculate_all()

        # Add trade statistics
        trade_stats = self.trade_logger.get_trade_stats()
        metrics.update(trade_stats)

        # Final portfolio value
        final_value = equity_df['portfolio_value'].iloc[-1]
        metrics['final_portfolio_value'] = final_value
        metrics['total_return_pct'] = (final_value - self.initial_capital) / self.initial_capital

        results = {
            'metrics': metrics,
            'equity_curve': equity_df,
            'trades': self.trade_logger.get_trades_df(),
            'trade_stats': trade_stats,
            'final_positions': self.tracker.get_holdings()
        }

        logger.info("=" * 80)
        logger.info("BACKTEST RESULTS SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Initial Capital:  ₩{self.initial_capital:,.0f}")
        logger.info(f"Final Value:      ₩{final_value:,.0f}")
        logger.info(f"Total Return:     {metrics['total_return_pct']:.2%}")
        logger.info(f"Sharpe Ratio:     {metrics['sharpe_ratio']:.2f}")
        logger.info(f"Max Drawdown:     {metrics['max_drawdown']:.2%}")
        logger.info(f"Total Trades:     {trade_stats.get('total_trades', 0)}")
        logger.info(f"Win Rate:         {trade_stats.get('win_rate', 0):.2%}")

        return results
