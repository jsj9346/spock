"""
Transaction Cost Model for Backtesting

Provides realistic transaction cost calculations including:
- Korean market commission schedules (KIS, KB, Samsung, etc.)
- Tax rules (securities transaction tax, capital gains tax)
- Slippage models (fixed, volume-based, volatility-based)
- Market impact estimation

References:
- KIS Commission Schedule: https://www.koreaninvestment.com
- FSS Tax Rules: https://www.fss.or.kr
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Union, Literal
from dataclasses import dataclass
from loguru import logger


@dataclass
class CommissionSchedule:
    """Commission rate schedule by order value"""
    base_rate: float  # Base commission rate (percentage)
    min_commission: float  # Minimum commission per trade
    max_commission: float  # Maximum commission per trade (None = no cap)

    def calculate(self, order_value: float) -> float:
        """Calculate commission for given order value"""
        commission = order_value * self.base_rate
        commission = max(commission, self.min_commission)
        if self.max_commission is not None:
            commission = min(commission, self.max_commission)
        return commission


class TransactionCostModel:
    """
    Comprehensive transaction cost model for backtesting.

    Use Cases:
    - Realistic backtest simulation with all transaction costs
    - Broker comparison and selection
    - Strategy cost analysis and optimization
    - Slippage impact estimation

    Korean Market Tax Rules:
    - Securities Transaction Tax: 0.23% (sell only, KOSPI/KOSDAQ)
    - Capital Gains Tax: 22% on gains >20M KRW/year (calculated separately)
    - No stamp duty or other taxes
    """

    # Korean broker commission schedules (as of 2024)
    BROKERS = {
        'KIS': CommissionSchedule(
            base_rate=0.00015,  # 0.015% (standard rate)
            min_commission=0,
            max_commission=None
        ),
        'KIS_VIP': CommissionSchedule(
            base_rate=0.00010,  # 0.01% (VIP rate for >100M monthly volume)
            min_commission=0,
            max_commission=None
        ),
        'KB': CommissionSchedule(
            base_rate=0.00014,  # 0.014%
            min_commission=1000,
            max_commission=None
        ),
        'SAMSUNG': CommissionSchedule(
            base_rate=0.00015,  # 0.015%
            min_commission=1000,
            max_commission=None
        ),
        'MIRAE': CommissionSchedule(
            base_rate=0.00014,  # 0.014%
            min_commission=1000,
            max_commission=None
        ),
        'NH': CommissionSchedule(
            base_rate=0.00015,  # 0.015%
            min_commission=1000,
            max_commission=None
        ),
    }

    # Tax rates
    SECURITIES_TAX_RATE = 0.0023  # 0.23% (sell only)
    AGRICULTURAL_TAX_RATE = 0.00023  # 0.023% (included in securities tax)

    def __init__(
        self,
        broker: str = 'KIS',
        region: str = 'KR',
        slippage_model: Literal['fixed', 'volume', 'volatility'] = 'fixed',
        slippage_bps: float = 5.0,  # 5 basis points = 0.05%
        apply_taxes: bool = True,
        market_impact_model: bool = False
    ):
        """
        Initialize transaction cost model.

        Args:
            broker: Broker name (KIS, KB, SAMSUNG, etc.)
            region: Market region (KR, US, JP)
            slippage_model: Slippage calculation method
            slippage_bps: Slippage in basis points (1 bps = 0.01%)
            apply_taxes: Apply transaction taxes
            market_impact_model: Use sophisticated market impact model
        """
        self.broker = broker.upper()
        self.region = region.upper()
        self.slippage_model = slippage_model
        self.slippage_bps = slippage_bps
        self.apply_taxes = apply_taxes
        self.market_impact_model = market_impact_model

        # Get commission schedule
        if self.broker not in self.BROKERS:
            logger.warning(f"Unknown broker {broker}, using KIS default")
            self.broker = 'KIS'

        self.commission_schedule = self.BROKERS[self.broker]

        logger.info(
            f"TransactionCostModel initialized: broker={self.broker}, "
            f"region={self.region}, slippage={self.slippage_bps}bps, "
            f"taxes={self.apply_taxes}"
        )

    def calculate_commission(
        self,
        order_value: float,
        side: Literal['buy', 'sell']
    ) -> float:
        """
        Calculate broker commission.

        Args:
            order_value: Order value (price * quantity)
            side: Order side (buy or sell)

        Returns:
            Commission amount
        """
        return self.commission_schedule.calculate(order_value)

    def calculate_tax(
        self,
        order_value: float,
        side: Literal['buy', 'sell']
    ) -> float:
        """
        Calculate transaction taxes.

        Args:
            order_value: Order value (price * quantity)
            side: Order side (buy or sell)

        Returns:
            Tax amount
        """
        if not self.apply_taxes or self.region != 'KR':
            return 0.0

        # Securities transaction tax (sell only)
        if side == 'sell':
            return order_value * self.SECURITIES_TAX_RATE

        return 0.0

    def calculate_slippage(
        self,
        price: float,
        quantity: float,
        side: Literal['buy', 'sell'],
        volume: Optional[float] = None,
        volatility: Optional[float] = None
    ) -> float:
        """
        Calculate slippage cost.

        Args:
            price: Order price
            quantity: Order quantity
            side: Order side (buy or sell)
            volume: Average daily volume (for volume-based model)
            volatility: Price volatility (for volatility-based model)

        Returns:
            Slippage amount (positive value)
        """
        if self.slippage_model == 'fixed':
            # Fixed basis point slippage
            slippage_rate = self.slippage_bps / 10000  # Convert bps to decimal
            return price * quantity * slippage_rate

        elif self.slippage_model == 'volume' and volume is not None:
            # Volume-based slippage (higher for larger orders)
            participation_rate = quantity / volume if volume > 0 else 0.0
            # Square root model: impact ∝ sqrt(participation_rate)
            impact_factor = np.sqrt(participation_rate) * self.slippage_bps
            slippage_rate = min(impact_factor / 10000, 0.01)  # Cap at 1%
            return price * quantity * slippage_rate

        elif self.slippage_model == 'volatility' and volatility is not None:
            # Volatility-based slippage (higher in volatile markets)
            volatility_factor = max(volatility, 0.001)  # Minimum 0.1% volatility
            slippage_rate = (self.slippage_bps / 10000) * (1 + volatility_factor * 10)
            slippage_rate = min(slippage_rate, 0.02)  # Cap at 2%
            return price * quantity * slippage_rate

        else:
            # Fallback to fixed slippage
            slippage_rate = self.slippage_bps / 10000
            return price * quantity * slippage_rate

    def calculate_total_cost(
        self,
        price: float,
        quantity: float,
        side: Literal['buy', 'sell'],
        volume: Optional[float] = None,
        volatility: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculate total transaction costs.

        Args:
            price: Execution price
            quantity: Order quantity
            side: Order side (buy or sell)
            volume: Average daily volume
            volatility: Price volatility

        Returns:
            Dictionary with cost breakdown
        """
        order_value = price * quantity

        commission = self.calculate_commission(order_value, side)
        tax = self.calculate_tax(order_value, side)
        slippage = self.calculate_slippage(price, quantity, side, volume, volatility)

        total_cost = commission + tax + slippage

        return {
            'order_value': order_value,
            'commission': commission,
            'tax': tax,
            'slippage': slippage,
            'total_cost': total_cost,
            'cost_bps': (total_cost / order_value * 10000) if order_value > 0 else 0.0
        }

    def calculate_effective_price(
        self,
        price: float,
        quantity: float,
        side: Literal['buy', 'sell'],
        volume: Optional[float] = None,
        volatility: Optional[float] = None
    ) -> float:
        """
        Calculate effective execution price including all costs.

        Args:
            price: Quoted price
            quantity: Order quantity
            side: Order side (buy or sell)
            volume: Average daily volume
            volatility: Price volatility

        Returns:
            Effective price (higher for buys, lower for sells)
        """
        costs = self.calculate_total_cost(price, quantity, side, volume, volatility)

        if side == 'buy':
            # Buyer pays costs, effective price is higher
            return price + (costs['total_cost'] / quantity)
        else:
            # Seller receives less, effective price is lower
            return price - (costs['total_cost'] / quantity)

    def estimate_roundtrip_cost(
        self,
        price: float,
        quantity: float,
        volume: Optional[float] = None,
        volatility: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Estimate total roundtrip cost (buy + sell).

        Args:
            price: Current price
            quantity: Position size
            volume: Average daily volume
            volatility: Price volatility

        Returns:
            Roundtrip cost breakdown
        """
        buy_costs = self.calculate_total_cost(price, quantity, 'buy', volume, volatility)
        sell_costs = self.calculate_total_cost(price, quantity, 'sell', volume, volatility)

        return {
            'buy_cost': buy_costs['total_cost'],
            'sell_cost': sell_costs['total_cost'],
            'roundtrip_cost': buy_costs['total_cost'] + sell_costs['total_cost'],
            'roundtrip_bps': ((buy_costs['total_cost'] + sell_costs['total_cost']) /
                             (price * quantity) * 10000)
        }


class MarketImpactModel:
    """
    Advanced market impact model based on academic research.

    Based on Almgren-Chriss model and empirical market microstructure.
    """

    def __init__(
        self,
        temporary_impact_coeff: float = 0.1,
        permanent_impact_coeff: float = 0.05,
        volatility_multiplier: float = 1.0
    ):
        """
        Initialize market impact model.

        Args:
            temporary_impact_coeff: Temporary impact coefficient
            permanent_impact_coeff: Permanent impact coefficient
            volatility_multiplier: Volatility adjustment factor
        """
        self.temp_coeff = temporary_impact_coeff
        self.perm_coeff = permanent_impact_coeff
        self.vol_mult = volatility_multiplier

    def calculate_impact(
        self,
        price: float,
        quantity: float,
        volume: float,
        volatility: float
    ) -> Dict[str, float]:
        """
        Calculate market impact for large order.

        Args:
            price: Current price
            quantity: Order quantity
            volume: Average daily volume
            volatility: Daily volatility

        Returns:
            Impact breakdown (temporary and permanent)
        """
        participation_rate = quantity / volume if volume > 0 else 0.0

        # Temporary impact (recovers after trade)
        temp_impact = (self.temp_coeff * price * volatility *
                      self.vol_mult * np.sqrt(participation_rate))

        # Permanent impact (price moves permanently)
        perm_impact = (self.perm_coeff * price * volatility *
                      self.vol_mult * participation_rate)

        total_impact = temp_impact + perm_impact

        return {
            'temporary_impact': temp_impact,
            'permanent_impact': perm_impact,
            'total_impact': total_impact,
            'impact_bps': (total_impact / price * 10000)
        }
