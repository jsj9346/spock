"""
Portfolio Simulator

Purpose: Track positions, cash, and P&L throughout backtest execution.

Key Features:
  - Maintain current positions and cash balance
  - Execute simulated trades (buy/sell)
  - Calculate P&L (realized and unrealized)
  - Enforce position limits (max position size, sector exposure)
  - Track transaction costs (commission, slippage)
  - Generate trade log

Design Philosophy:
  - Realistic execution modeling with transaction costs
  - Position limit enforcement (risk management)
  - Comprehensive trade logging for analysis
"""

from datetime import date
from typing import List, Dict, Optional
import logging

from .backtest_config import BacktestConfig, Position, Trade
from .transaction_cost_model import (
    TransactionCostModel,
    get_cost_model,
    OrderSide,
    TimeOfDay,
)


logger = logging.getLogger(__name__)


class PortfolioSimulator:
    """
    Portfolio tracking and P&L calculation for backtesting.

    Attributes:
        config: Backtest configuration
        cash: Current cash balance
        positions: Dictionary of open positions {ticker: Position}
        trades: List of completed trades
        portfolio_values: Dictionary of daily portfolio values {date: value}
    """

    def __init__(self, config: BacktestConfig, cost_model: Optional[TransactionCostModel] = None):
        """
        Initialize portfolio with starting capital.

        Args:
            config: Backtest configuration
            cost_model: Transaction cost model (optional, defaults to KR_DEFAULT)
        """
        self.config = config
        self.cash = config.initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.portfolio_values: Dict[date, float] = {}

        # Initialize cost model
        if cost_model is None:
            # Default to Korea market cost profile
            self.cost_model = get_cost_model('KR_DEFAULT')
        else:
            self.cost_model = cost_model

        logger.info(
            f"Portfolio initialized: initial_capital={config.initial_capital:,.0f}, "
            f"cost_model={self.cost_model.__class__.__name__}"
        )

    def buy(
        self,
        ticker: str,
        region: str,
        price: float,
        buy_date: date,
        kelly_fraction: float,
        pattern_type: str,
        entry_score: int,
        sector: Optional[str] = None,
        atr: Optional[float] = None,
    ) -> Optional[Trade]:
        """
        Execute buy order with position sizing and limit enforcement.

        Args:
            ticker: Stock ticker
            region: Market region
            price: Entry price
            buy_date: Trade date
            kelly_fraction: Kelly formula position size
            pattern_type: Chart pattern type
            entry_score: LayeredScoringEngine score
            sector: GICS sector (optional)
            atr: Average True Range for stop loss (optional)

        Returns:
            Trade object if order executed, None if rejected

        Position Sizing:
            1. Calculate Kelly position size = kelly_fraction × kelly_multiplier × portfolio_value
            2. Cap at max_position_size × portfolio_value
            3. Ensure sufficient cash available
            4. Check sector exposure limits
        """
        # Check if already holding position
        if ticker in self.positions:
            logger.debug(f"Already holding position in {ticker}, skipping buy")
            return None

        # Calculate position size
        portfolio_value = self.get_portfolio_value({ticker: price})
        kelly_position_size = (
            kelly_fraction * self.config.kelly_multiplier * portfolio_value
        )
        max_position_value = self.config.max_position_size * portfolio_value

        position_value = min(kelly_position_size, max_position_value)

        # Calculate shares and costs
        shares = int(position_value / price)
        if shares == 0:
            logger.debug(f"Position size too small for {ticker}, skipping")
            return None

        actual_position_value = shares * price

        # Calculate transaction costs using cost model
        costs = self.cost_model.calculate_costs(
            ticker=ticker,
            price=price,
            shares=shares,
            side=OrderSide.BUY,
            time_of_day=TimeOfDay.REGULAR,  # Default to regular hours (can be enhanced later)
            avg_daily_volume=None,  # Can be enhanced with volume data
        )

        commission = costs.commission
        slippage = costs.slippage + costs.market_impact  # Combine slippage and market impact
        total_cost = actual_position_value + costs.total_cost

        # Check cash availability
        if total_cost > self.cash:
            logger.debug(
                f"Insufficient cash for {ticker}: need={total_cost:,.0f}, available={self.cash:,.0f}"
            )
            return None

        # Check cash reserve
        remaining_cash = self.cash - total_cost
        if remaining_cash < self.config.cash_reserve * self.config.initial_capital:
            logger.debug(
                f"Cash reserve violation for {ticker}: would leave {remaining_cash:,.0f}"
            )
            return None

        # Check sector exposure limit (if sector provided)
        if sector is not None:
            current_sector_exposure = self._get_sector_exposure(sector, {ticker: price})
            new_sector_exposure = (
                current_sector_exposure + actual_position_value
            ) / portfolio_value

            if new_sector_exposure > self.config.max_sector_exposure:
                logger.debug(
                    f"Sector exposure violation for {ticker} (sector={sector}): "
                    f"would be {new_sector_exposure:.1%} > {self.config.max_sector_exposure:.1%}"
                )
                return None

        # Calculate stop loss and profit target
        stop_loss_price = self._calculate_stop_loss(price, atr)
        profit_target_price = price * (1 + self.config.profit_target)

        # Execute trade
        self.cash -= total_cost

        position = Position(
            ticker=ticker,
            region=region,
            entry_date=buy_date,
            entry_price=price,
            shares=shares,
            stop_loss_price=stop_loss_price,
            profit_target_price=profit_target_price,
            pattern_type=pattern_type,
            entry_score=entry_score,
            sector=sector,
        )
        self.positions[ticker] = position

        trade = Trade(
            ticker=ticker,
            region=region,
            entry_date=buy_date,
            entry_price=price,
            shares=shares,
            commission=commission,
            slippage=slippage,
            pattern_type=pattern_type,
            entry_score=entry_score,
            sector=sector,
        )

        logger.info(
            f"BUY: {ticker} × {shares} @ {price:,.2f} = {actual_position_value:,.0f} "
            f"(pattern={pattern_type}, score={entry_score}, stop={stop_loss_price:,.2f})"
        )

        return trade

    def sell(
        self,
        ticker: str,
        price: float,
        sell_date: date,
        exit_reason: str,
    ) -> Optional[Trade]:
        """
        Execute sell order and realize P&L.

        Args:
            ticker: Stock ticker
            price: Exit price
            sell_date: Trade date
            exit_reason: Reason for exit (profit_target, stop_loss, stage3_exit, etc.)

        Returns:
            Closed Trade object if order executed, None if no position
        """
        if ticker not in self.positions:
            logger.warning(f"No position to sell for {ticker}")
            return None

        position = self.positions[ticker]

        # Calculate proceeds and costs using cost model
        gross_proceeds = position.shares * price

        costs = self.cost_model.calculate_costs(
            ticker=ticker,
            price=price,
            shares=position.shares,
            side=OrderSide.SELL,
            time_of_day=TimeOfDay.REGULAR,  # Default to regular hours
            avg_daily_volume=None,  # Can be enhanced with volume data
        )

        commission = costs.commission
        slippage = costs.slippage + costs.market_impact  # Combine slippage and market impact
        net_proceeds = gross_proceeds - costs.total_cost

        # Update cash
        self.cash += net_proceeds

        # Find corresponding open trade
        open_trade = None
        for trade in self.trades:
            if (
                trade.ticker == ticker
                and trade.entry_date == position.entry_date
                and not trade.is_closed
            ):
                open_trade = trade
                break

        if open_trade is None:
            # Create new trade object for orphaned position
            open_trade = Trade(
                ticker=ticker,
                region=position.region,
                entry_date=position.entry_date,
                entry_price=position.entry_price,
                shares=position.shares,
                commission=commission,
                slippage=slippage,
                pattern_type=position.pattern_type,
                entry_score=position.entry_score,
                sector=position.sector,
            )
            self.trades.append(open_trade)

        # Close trade
        open_trade.close(sell_date, price, exit_reason)

        # Remove position
        del self.positions[ticker]

        pnl_pct = (price - position.entry_price) / position.entry_price
        logger.info(
            f"SELL: {ticker} × {position.shares} @ {price:,.2f} "
            f"(P&L={open_trade.pnl:,.0f}, {pnl_pct:+.1%}, reason={exit_reason})"
        )

        return open_trade

    def update_positions(
        self, current_date: date, current_prices: Dict[str, float]
    ) -> List[str]:
        """
        Update unrealized P&L and check exit conditions.

        Args:
            current_date: Current backtest date
            current_prices: Dictionary of current prices {ticker: price}

        Returns:
            List of tickers triggering exit signals

        Exit Conditions:
            1. Stop loss hit
            2. Profit target reached
        """
        exit_signals = []

        for ticker, position in list(self.positions.items()):
            if ticker not in current_prices:
                logger.warning(f"No price data for {ticker} on {current_date}")
                continue

            current_price = current_prices[ticker]

            # Check stop loss
            if current_price <= position.stop_loss_price:
                logger.info(
                    f"Stop loss triggered for {ticker}: "
                    f"price={current_price:,.2f} <= stop={position.stop_loss_price:,.2f}"
                )
                exit_signals.append((ticker, "stop_loss"))

            # Check profit target
            elif current_price >= position.profit_target_price:
                logger.info(
                    f"Profit target reached for {ticker}: "
                    f"price={current_price:,.2f} >= target={position.profit_target_price:,.2f}"
                )
                exit_signals.append((ticker, "profit_target"))

        return exit_signals

    def get_portfolio_value(self, current_prices: Dict[str, float]) -> float:
        """
        Calculate total portfolio value (cash + positions).

        Args:
            current_prices: Dictionary of current prices {ticker: price}

        Returns:
            Total portfolio value
        """
        positions_value = sum(
            position.shares * current_prices.get(ticker, position.entry_price)
            for ticker, position in self.positions.items()
        )
        return self.cash + positions_value

    def get_current_positions(self) -> List[Position]:
        """
        Get list of open positions.

        Returns:
            List of Position objects
        """
        return list(self.positions.values())

    def record_daily_value(self, current_date: date, current_prices: Dict[str, float]):
        """
        Record daily portfolio value for equity curve.

        Args:
            current_date: Date
            current_prices: Current prices
        """
        portfolio_value = self.get_portfolio_value(current_prices)
        self.portfolio_values[current_date] = portfolio_value

    # NOTE: _calculate_commission and _calculate_slippage methods removed
    # Transaction costs now calculated via TransactionCostModel (Week 5 enhancement)

    def _calculate_stop_loss(
        self, entry_price: float, atr: Optional[float]
    ) -> float:
        """
        Calculate stop loss price.

        Args:
            entry_price: Entry price
            atr: Average True Range (optional)

        Returns:
            Stop loss price

        Logic:
            - If ATR available: entry_price - (ATR × multiplier)
            - Otherwise: entry_price × (1 - stop_loss_min)
            - Bounded by [stop_loss_min, stop_loss_max]
        """
        if atr is not None:
            atr_stop = entry_price - (atr * self.config.stop_loss_atr_multiplier)
            stop_pct = (entry_price - atr_stop) / entry_price
            stop_pct = max(self.config.stop_loss_min, min(stop_pct, self.config.stop_loss_max))
            return entry_price * (1 - stop_pct)
        else:
            return entry_price * (1 - self.config.stop_loss_min)

    def _get_sector_exposure(
        self, sector: str, current_prices: Dict[str, float]
    ) -> float:
        """
        Calculate current exposure to sector.

        Args:
            sector: GICS sector
            current_prices: Current prices

        Returns:
            Total value in sector
        """
        sector_value = 0.0
        for ticker, position in self.positions.items():
            if position.sector == sector:
                price = current_prices.get(ticker, position.entry_price)
                sector_value += position.shares * price
        return sector_value

    def get_statistics(self) -> Dict[str, any]:
        """
        Get portfolio statistics.

        Returns:
            Dictionary with portfolio statistics
        """
        total_positions = len(self.positions)
        total_trades = len([t for t in self.trades if t.is_closed])
        winning_trades = len([t for t in self.trades if t.is_closed and t.pnl > 0])
        losing_trades = len([t for t in self.trades if t.is_closed and t.pnl < 0])

        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        return {
            "cash": self.cash,
            "open_positions": total_positions,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
        }
