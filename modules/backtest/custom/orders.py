"""
Order Execution Module for Custom Backtesting Engine

Provides realistic order execution simulation including:
- Market and limit orders
- Partial fills and order queuing
- Price improvement opportunities
- Order rejection scenarios
- Fill probability models

References:
- KRX Market Microstructure: https://www.krx.co.kr
- Order Types and Execution: Standard exchange rules
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Literal
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from loguru import logger


class OrderType(Enum):
    """Order type enumeration"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderSide(Enum):
    """Order side enumeration"""
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    """Order status enumeration"""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    """Order representation"""
    order_id: str
    ticker: str
    order_type: OrderType
    side: OrderSide
    quantity: int
    price: Optional[float] = None  # None for market orders
    stop_price: Optional[float] = None  # For stop orders
    timestamp: datetime = field(default_factory=datetime.now)
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    filled_price: float = 0.0
    commission: float = 0.0
    tax: float = 0.0
    slippage: float = 0.0

    @property
    def remaining_quantity(self) -> int:
        """Get remaining unfilled quantity"""
        return self.quantity - self.filled_quantity

    @property
    def is_complete(self) -> bool:
        """Check if order is completely filled"""
        return self.filled_quantity >= self.quantity

    @property
    def fill_ratio(self) -> float:
        """Get fill ratio (0.0 to 1.0)"""
        return self.filled_quantity / self.quantity if self.quantity > 0 else 0.0


@dataclass
class Fill:
    """Order fill representation"""
    order_id: str
    ticker: str
    side: OrderSide
    quantity: int
    price: float
    timestamp: datetime
    commission: float = 0.0
    tax: float = 0.0
    slippage: float = 0.0

    @property
    def value(self) -> float:
        """Get fill value"""
        return self.quantity * self.price

    @property
    def total_cost(self) -> float:
        """Get total cost including fees"""
        return self.commission + self.tax + self.slippage


class OrderExecutionEngine:
    """
    Realistic order execution engine for backtesting.

    Features:
    - Market and limit order simulation
    - Partial fills based on volume
    - Price improvement for limit orders
    - Realistic fill timing
    - Transaction cost integration

    Korean Market Rules:
    - Market orders: Executed at best available price
    - Limit orders: Must meet or beat limit price
    - Trading hours: 09:00-15:30 KST
    - No pre-market/after-hours for retail
    - Tick size rules based on price level
    """

    # Korean market tick sizes
    TICK_SIZES = [
        (1000, 1),           # < ₩1,000: ₩1 tick
        (5000, 5),           # ₩1,000-5,000: ₩5 tick
        (10000, 10),         # ₩5,000-10,000: ₩10 tick
        (50000, 50),         # ₩10,000-50,000: ₩50 tick
        (100000, 100),       # ₩50,000-100,000: ₩100 tick
        (500000, 500),       # ₩100,000-500,000: ₩500 tick
        (float('inf'), 1000) # > ₩500,000: ₩1,000 tick
    ]

    def __init__(
        self,
        cost_model=None,
        partial_fill_enabled: bool = True,
        price_improvement_enabled: bool = True,
        max_participation_rate: float = 0.1,  # 10% of volume
        fill_probability_model: Literal['simple', 'volume_weighted'] = 'simple'
    ):
        """
        Initialize order execution engine.

        Args:
            cost_model: TransactionCostModel instance
            partial_fill_enabled: Allow partial fills
            price_improvement_enabled: Allow price improvement
            max_participation_rate: Maximum volume participation
            fill_probability_model: Fill probability calculation method
        """
        self.cost_model = cost_model
        self.partial_fill_enabled = partial_fill_enabled
        self.price_improvement_enabled = price_improvement_enabled
        self.max_participation_rate = max_participation_rate
        self.fill_model = fill_probability_model

        self.pending_orders: List[Order] = []
        self.filled_orders: List[Order] = []
        self.fills: List[Fill] = []

        logger.info(
            f"OrderExecutionEngine initialized: partial_fills={partial_fill_enabled}, "
            f"price_improvement={price_improvement_enabled}, "
            f"max_participation={max_participation_rate:.1%}"
        )

    def get_tick_size(self, price: float) -> float:
        """Get tick size for given price level"""
        for price_level, tick_size in self.TICK_SIZES:
            if price < price_level:
                return tick_size
        return 1000

    def round_to_tick(self, price: float) -> float:
        """Round price to valid tick size"""
        tick_size = self.get_tick_size(price)
        return round(price / tick_size) * tick_size

    def submit_order(
        self,
        ticker: str,
        order_type: OrderType,
        side: OrderSide,
        quantity: int,
        price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> Order:
        """
        Submit new order.

        Args:
            ticker: Stock ticker
            order_type: Order type (MARKET, LIMIT, etc.)
            side: Order side (BUY or SELL)
            quantity: Order quantity
            price: Limit price (for limit orders)
            stop_price: Stop price (for stop orders)

        Returns:
            Order object
        """
        # Validate inputs
        if order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT] and price is None:
            raise ValueError("Limit orders require price")

        if order_type in [OrderType.STOP, OrderType.STOP_LIMIT] and stop_price is None:
            raise ValueError("Stop orders require stop_price")

        # Round limit price to tick
        if price is not None:
            price = self.round_to_tick(price)

        # Create order
        order = Order(
            order_id=f"{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
            ticker=ticker,
            order_type=order_type,
            side=side,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            timestamp=datetime.now(),
            status=OrderStatus.SUBMITTED
        )

        self.pending_orders.append(order)
        logger.debug(f"Order submitted: {order.order_id} {order.side.value} {quantity} {ticker}")

        return order

    def execute_market_order(
        self,
        order: Order,
        current_bar: pd.Series,
        volume: Optional[float] = None
    ) -> Optional[Fill]:
        """
        Execute market order at current bar.

        Args:
            order: Order to execute
            current_bar: Current OHLCV bar
            volume: Available volume for partial fills

        Returns:
            Fill object if executed, None otherwise
        """
        # Market orders execute at open price (conservative)
        # Could also use close price for EOD execution
        execution_price = current_bar['open']

        # Calculate maximum fillable quantity
        if volume is not None and self.partial_fill_enabled:
            max_fill_qty = int(volume * self.max_participation_rate)
            fill_qty = min(order.remaining_quantity, max_fill_qty)
        else:
            fill_qty = order.remaining_quantity

        if fill_qty <= 0:
            return None

        # Calculate transaction costs
        if self.cost_model:
            costs = self.cost_model.calculate_total_cost(
                execution_price,
                fill_qty,
                'buy' if order.side == OrderSide.BUY else 'sell',
                volume=volume
            )
            commission = costs['commission']
            tax = costs['tax']
            slippage = costs['slippage']
        else:
            commission = tax = slippage = 0.0

        # Create fill
        fill = Fill(
            order_id=order.order_id,
            ticker=order.ticker,
            side=order.side,
            quantity=fill_qty,
            price=execution_price,
            timestamp=datetime.now(),
            commission=commission,
            tax=tax,
            slippage=slippage
        )

        # Update order
        order.filled_quantity += fill_qty
        order.filled_price = (
            (order.filled_price * (order.filled_quantity - fill_qty) +
             execution_price * fill_qty) / order.filled_quantity
        )
        order.commission += commission
        order.tax += tax
        order.slippage += slippage

        if order.is_complete:
            order.status = OrderStatus.FILLED
        else:
            order.status = OrderStatus.PARTIAL

        self.fills.append(fill)
        logger.debug(f"Market order filled: {fill.quantity} @ {fill.price:.0f}")

        return fill

    def execute_limit_order(
        self,
        order: Order,
        current_bar: pd.Series,
        volume: Optional[float] = None
    ) -> Optional[Fill]:
        """
        Execute limit order if price condition met.

        Args:
            order: Order to execute
            current_bar: Current OHLCV bar
            volume: Available volume

        Returns:
            Fill object if executed, None otherwise
        """
        # Check if limit price is executable
        if order.side == OrderSide.BUY:
            # Buy limit: Execute if market price <= limit price
            if current_bar['low'] <= order.price:
                # Use limit price or better (price improvement)
                if self.price_improvement_enabled:
                    execution_price = min(order.price, current_bar['open'])
                else:
                    execution_price = order.price
            else:
                return None  # Price not reached

        else:  # SELL
            # Sell limit: Execute if market price >= limit price
            if current_bar['high'] >= order.price:
                # Use limit price or better
                if self.price_improvement_enabled:
                    execution_price = max(order.price, current_bar['open'])
                else:
                    execution_price = order.price
            else:
                return None  # Price not reached

        # Calculate fill quantity (same as market order)
        if volume is not None and self.partial_fill_enabled:
            max_fill_qty = int(volume * self.max_participation_rate)
            fill_qty = min(order.remaining_quantity, max_fill_qty)
        else:
            fill_qty = order.remaining_quantity

        if fill_qty <= 0:
            return None

        # Calculate costs
        if self.cost_model:
            costs = self.cost_model.calculate_total_cost(
                execution_price,
                fill_qty,
                'buy' if order.side == OrderSide.BUY else 'sell',
                volume=volume
            )
            commission = costs['commission']
            tax = costs['tax']
            slippage = costs['slippage']
        else:
            commission = tax = slippage = 0.0

        # Create fill
        fill = Fill(
            order_id=order.order_id,
            ticker=order.ticker,
            side=order.side,
            quantity=fill_qty,
            price=execution_price,
            timestamp=datetime.now(),
            commission=commission,
            tax=tax,
            slippage=slippage
        )

        # Update order
        order.filled_quantity += fill_qty
        order.filled_price = (
            (order.filled_price * (order.filled_quantity - fill_qty) +
             execution_price * fill_qty) / order.filled_quantity
        )
        order.commission += commission
        order.tax += tax
        order.slippage += slippage

        if order.is_complete:
            order.status = OrderStatus.FILLED
        else:
            order.status = OrderStatus.PARTIAL

        self.fills.append(fill)
        logger.debug(f"Limit order filled: {fill.quantity} @ {fill.price:.0f}")

        return fill

    def process_bar(
        self,
        current_bar: pd.Series,
        volume: Optional[float] = None
    ) -> List[Fill]:
        """
        Process all pending orders for current bar.

        Args:
            current_bar: Current OHLCV bar
            volume: Available trading volume

        Returns:
            List of fills generated
        """
        fills = []

        # Process each pending order
        for order in self.pending_orders[:]:  # Copy list to allow removal
            if order.order_type == OrderType.MARKET:
                fill = self.execute_market_order(order, current_bar, volume)
            elif order.order_type == OrderType.LIMIT:
                fill = self.execute_limit_order(order, current_bar, volume)
            else:
                logger.warning(f"Unsupported order type: {order.order_type}")
                continue

            if fill:
                fills.append(fill)

            # Move completed orders to filled list
            if order.is_complete:
                self.pending_orders.remove(order)
                self.filled_orders.append(order)

        return fills

    def cancel_order(self, order_id: str) -> bool:
        """Cancel pending order"""
        for order in self.pending_orders:
            if order.order_id == order_id:
                order.status = OrderStatus.CANCELLED
                self.pending_orders.remove(order)
                logger.debug(f"Order cancelled: {order_id}")
                return True
        return False

    def get_order_status(self, order_id: str) -> Optional[Order]:
        """Get order status"""
        for order in self.pending_orders + self.filled_orders:
            if order.order_id == order_id:
                return order
        return None

    def get_fills(self, ticker: Optional[str] = None) -> List[Fill]:
        """Get all fills, optionally filtered by ticker"""
        if ticker:
            return [f for f in self.fills if f.ticker == ticker]
        return self.fills

    def reset(self):
        """Reset engine state"""
        self.pending_orders.clear()
        self.filled_orders.clear()
        self.fills.clear()
        logger.info("OrderExecutionEngine reset")
