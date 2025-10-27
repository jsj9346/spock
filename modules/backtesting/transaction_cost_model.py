"""
Transaction Cost Model

Purpose: Realistic modeling of trading costs including commission, slippage, and market impact.

Key Features:
  - Pluggable cost model architecture
  - Commission modeling (fixed percentage, tiered)
  - Slippage modeling (fixed bps, time-of-day dependent)
  - Market impact modeling (square root model based on order size)
  - Market-specific cost profiles (KR, US, CN, HK, JP, VN)
  - Time-of-day multipliers for realistic cost estimation

Design Philosophy:
  - Separation of concerns (commission vs slippage vs market impact)
  - Transparency (separate cost components for analysis)
  - Flexibility (pluggable models for different markets)
  - Realism (based on real-world trading costs)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict
from enum import Enum
import numpy as np


class OrderSide(Enum):
    """Order side enumeration."""
    BUY = "buy"
    SELL = "sell"


class TimeOfDay(Enum):
    """Time of day for order execution."""
    OPEN = "open"          # Market open (first 30 minutes)
    REGULAR = "regular"    # Regular trading hours
    CLOSE = "close"        # Market close (last 30 minutes)


@dataclass
class TransactionCosts:
    """
    Transaction costs breakdown.

    Attributes:
        commission: Commission cost (fixed percentage)
        slippage: Slippage cost (price impact from bid-ask spread)
        market_impact: Market impact cost (price movement from order size)
        total_cost: Total transaction cost (commission + slippage + market_impact)
    """
    commission: float
    slippage: float
    market_impact: float

    @property
    def total_cost(self) -> float:
        """Total transaction cost."""
        return self.commission + self.slippage + self.market_impact

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            'commission': self.commission,
            'slippage': self.slippage,
            'market_impact': self.market_impact,
            'total_cost': self.total_cost,
        }


class TransactionCostModel(ABC):
    """
    Abstract base class for transaction cost models.

    Design Pattern:
        - Template Method pattern for cost calculation
        - Pluggable architecture for different market characteristics
        - Separate methods for each cost component
    """

    @abstractmethod
    def calculate_costs(
        self,
        ticker: str,
        price: float,
        shares: int,
        side: OrderSide,
        time_of_day: TimeOfDay = TimeOfDay.REGULAR,
        avg_daily_volume: Optional[float] = None,
    ) -> TransactionCosts:
        """
        Calculate total transaction costs.

        Args:
            ticker: Stock ticker symbol
            price: Execution price
            shares: Number of shares
            side: Order side (BUY or SELL)
            time_of_day: Time of day for execution
            avg_daily_volume: Average daily volume (for market impact calculation)

        Returns:
            TransactionCosts with breakdown of all cost components
        """
        pass

    @abstractmethod
    def calculate_commission(self, price: float, shares: int, side: OrderSide) -> float:
        """
        Calculate commission cost.

        Args:
            price: Execution price
            shares: Number of shares
            side: Order side (BUY or SELL)

        Returns:
            Commission cost in currency units
        """
        pass

    @abstractmethod
    def calculate_slippage(
        self,
        price: float,
        shares: int,
        side: OrderSide,
        time_of_day: TimeOfDay,
    ) -> float:
        """
        Calculate slippage cost.

        Args:
            price: Execution price
            shares: Number of shares
            side: Order side (BUY or SELL)
            time_of_day: Time of day for execution

        Returns:
            Slippage cost in currency units
        """
        pass

    @abstractmethod
    def calculate_market_impact(
        self,
        price: float,
        shares: int,
        side: OrderSide,
        avg_daily_volume: Optional[float],
    ) -> float:
        """
        Calculate market impact cost.

        Args:
            price: Execution price
            shares: Number of shares
            side: Order side (BUY or SELL)
            avg_daily_volume: Average daily volume

        Returns:
            Market impact cost in currency units
        """
        pass


class StandardCostModel(TransactionCostModel):
    """
    Standard transaction cost model.

    Features:
        - Fixed percentage commission
        - Fixed bps slippage with time-of-day multipliers
        - Square root market impact model

    Cost Components:
        1. Commission: Fixed percentage of notional value
        2. Slippage: Fixed bps × notional × time_of_day_multiplier
        3. Market Impact: coefficient × notional × sqrt(shares / avg_daily_volume)

    Example:
        >>> cost_model = StandardCostModel(
        ...     commission_rate=0.00015,  # 0.015%
        ...     slippage_bps=5.0,
        ...     market_impact_coefficient=0.1,
        ... )
        >>> costs = cost_model.calculate_costs(
        ...     ticker='005930',
        ...     price=70000,
        ...     shares=100,
        ...     side=OrderSide.BUY,
        ...     time_of_day=TimeOfDay.OPEN,
        ...     avg_daily_volume=5000000,
        ... )
        >>> print(f"Total cost: {costs.total_cost:,.0f} KRW")
    """

    def __init__(
        self,
        commission_rate: float = 0.00015,
        slippage_bps: float = 5.0,
        market_impact_coefficient: float = 0.1,
        time_of_day_multipliers: Optional[Dict[TimeOfDay, float]] = None,
    ):
        """
        Initialize standard cost model.

        Args:
            commission_rate: Commission rate (default: 0.00015 = 0.015%)
            slippage_bps: Slippage in basis points (default: 5.0 bps)
            market_impact_coefficient: Market impact coefficient (default: 0.1)
            time_of_day_multipliers: Time-of-day multipliers for slippage
                                    (default: open=1.5, regular=1.0, close=1.3)
        """
        self.commission_rate = commission_rate
        self.slippage_bps = slippage_bps
        self.market_impact_coefficient = market_impact_coefficient

        if time_of_day_multipliers is None:
            self.time_of_day_multipliers = {
                TimeOfDay.OPEN: 1.5,     # Higher slippage at market open
                TimeOfDay.REGULAR: 1.0,  # Normal slippage during regular hours
                TimeOfDay.CLOSE: 1.3,    # Higher slippage at market close
            }
        else:
            self.time_of_day_multipliers = time_of_day_multipliers

    def calculate_costs(
        self,
        ticker: str,
        price: float,
        shares: int,
        side: OrderSide,
        time_of_day: TimeOfDay = TimeOfDay.REGULAR,
        avg_daily_volume: Optional[float] = None,
    ) -> TransactionCosts:
        """
        Calculate total transaction costs.

        Args:
            ticker: Stock ticker symbol
            price: Execution price
            shares: Number of shares
            side: Order side (BUY or SELL)
            time_of_day: Time of day for execution
            avg_daily_volume: Average daily volume (for market impact calculation)

        Returns:
            TransactionCosts with breakdown of all cost components
        """
        commission = self.calculate_commission(price, shares, side)
        slippage = self.calculate_slippage(price, shares, side, time_of_day)
        market_impact = self.calculate_market_impact(price, shares, side, avg_daily_volume)

        return TransactionCosts(
            commission=commission,
            slippage=slippage,
            market_impact=market_impact,
        )

    def calculate_commission(self, price: float, shares: int, side: OrderSide) -> float:
        """
        Calculate commission cost (fixed percentage).

        Args:
            price: Execution price
            shares: Number of shares
            side: Order side (BUY or SELL)

        Returns:
            Commission cost in currency units
        """
        notional = price * shares
        return notional * self.commission_rate

    def calculate_slippage(
        self,
        price: float,
        shares: int,
        side: OrderSide,
        time_of_day: TimeOfDay,
    ) -> float:
        """
        Calculate slippage cost (fixed bps with time-of-day adjustment).

        Args:
            price: Execution price
            shares: Number of shares
            side: Order side (BUY or SELL)
            time_of_day: Time of day for execution

        Returns:
            Slippage cost in currency units
        """
        notional = price * shares
        base_slippage = notional * (self.slippage_bps / 10000.0)  # Convert bps to decimal

        # Apply time-of-day multiplier
        multiplier = self.time_of_day_multipliers.get(time_of_day, 1.0)
        return base_slippage * multiplier

    def calculate_market_impact(
        self,
        price: float,
        shares: int,
        side: OrderSide,
        avg_daily_volume: Optional[float],
    ) -> float:
        """
        Calculate market impact cost (square root model).

        Model: impact = coefficient × notional × sqrt(shares / avg_daily_volume)

        Args:
            price: Execution price
            shares: Number of shares
            side: Order side (BUY or SELL)
            avg_daily_volume: Average daily volume

        Returns:
            Market impact cost in currency units
        """
        if avg_daily_volume is None or avg_daily_volume <= 0:
            return 0.0

        notional = price * shares
        volume_participation = shares / avg_daily_volume

        # Square root model: impact increases with sqrt of volume participation
        impact_factor = np.sqrt(volume_participation)

        return self.market_impact_coefficient * notional * impact_factor


class ZeroCostModel(TransactionCostModel):
    """
    Zero cost model (no transaction costs).

    Use Cases:
        - Baseline backtests without transaction costs
        - Comparison with realistic cost models
        - High-frequency strategies where costs are negligible
    """

    def calculate_costs(
        self,
        ticker: str,
        price: float,
        shares: int,
        side: OrderSide,
        time_of_day: TimeOfDay = TimeOfDay.REGULAR,
        avg_daily_volume: Optional[float] = None,
    ) -> TransactionCosts:
        """Return zero costs."""
        return TransactionCosts(
            commission=0.0,
            slippage=0.0,
            market_impact=0.0,
        )

    def calculate_commission(self, price: float, shares: int, side: OrderSide) -> float:
        """Return zero commission."""
        return 0.0

    def calculate_slippage(
        self,
        price: float,
        shares: int,
        side: OrderSide,
        time_of_day: TimeOfDay,
    ) -> float:
        """Return zero slippage."""
        return 0.0

    def calculate_market_impact(
        self,
        price: float,
        shares: int,
        side: OrderSide,
        avg_daily_volume: Optional[float],
    ) -> float:
        """Return zero market impact."""
        return 0.0


# ============================================================================
# Market Cost Profiles
# ============================================================================

@dataclass
class MarketCostProfile:
    """
    Market-specific cost profile.

    Attributes:
        market: Market code (KR, US, CN, HK, JP, VN)
        name: Profile name
        commission_rate: Commission rate (decimal)
        slippage_bps: Slippage in basis points
        market_impact_coefficient: Market impact coefficient
        time_of_day_multipliers: Time-of-day multipliers for slippage
    """
    market: str
    name: str
    commission_rate: float
    slippage_bps: float
    market_impact_coefficient: float
    time_of_day_multipliers: Dict[TimeOfDay, float]

    def to_cost_model(self) -> StandardCostModel:
        """Convert profile to StandardCostModel."""
        return StandardCostModel(
            commission_rate=self.commission_rate,
            slippage_bps=self.slippage_bps,
            market_impact_coefficient=self.market_impact_coefficient,
            time_of_day_multipliers=self.time_of_day_multipliers,
        )


# Pre-configured market cost profiles
MARKET_COST_PROFILES = {
    'KR_DEFAULT': MarketCostProfile(
        market='KR',
        name='Korea Default',
        commission_rate=0.00015,  # 0.015% (typical Korean broker)
        slippage_bps=5.0,         # 5 bps slippage
        market_impact_coefficient=0.1,
        time_of_day_multipliers={
            TimeOfDay.OPEN: 1.5,     # Higher volatility at open
            TimeOfDay.REGULAR: 1.0,
            TimeOfDay.CLOSE: 1.3,    # Higher volatility at close
        },
    ),
    'KR_LOW_COST': MarketCostProfile(
        market='KR',
        name='Korea Low Cost (Optimistic)',
        commission_rate=0.00005,  # 0.005% (discount broker)
        slippage_bps=3.0,         # 3 bps slippage (liquid stocks)
        market_impact_coefficient=0.05,
        time_of_day_multipliers={
            TimeOfDay.OPEN: 1.3,
            TimeOfDay.REGULAR: 1.0,
            TimeOfDay.CLOSE: 1.2,
        },
    ),
    'KR_HIGH_COST': MarketCostProfile(
        market='KR',
        name='Korea High Cost (Conservative)',
        commission_rate=0.0003,   # 0.03% (full-service broker)
        slippage_bps=10.0,        # 10 bps slippage (illiquid stocks)
        market_impact_coefficient=0.2,
        time_of_day_multipliers={
            TimeOfDay.OPEN: 2.0,
            TimeOfDay.REGULAR: 1.0,
            TimeOfDay.CLOSE: 1.5,
        },
    ),
    'US_DEFAULT': MarketCostProfile(
        market='US',
        name='US Default (Commission-Free)',
        commission_rate=0.0,      # 0% (Robinhood, Webull, etc.)
        slippage_bps=2.0,         # 2 bps slippage (tight spreads)
        market_impact_coefficient=0.05,
        time_of_day_multipliers={
            TimeOfDay.OPEN: 1.8,     # High volatility at US open
            TimeOfDay.REGULAR: 1.0,
            TimeOfDay.CLOSE: 1.5,
        },
    ),
    'US_LEGACY': MarketCostProfile(
        market='US',
        name='US Legacy (Traditional Broker)',
        commission_rate=0.0001,   # 0.01% or $5-10 per trade
        slippage_bps=3.0,
        market_impact_coefficient=0.08,
        time_of_day_multipliers={
            TimeOfDay.OPEN: 1.8,
            TimeOfDay.REGULAR: 1.0,
            TimeOfDay.CLOSE: 1.5,
        },
    ),
}


def get_cost_model(profile_name: str = 'KR_DEFAULT') -> TransactionCostModel:
    """
    Get transaction cost model from profile name.

    Args:
        profile_name: Profile name (e.g., 'KR_DEFAULT', 'US_DEFAULT')

    Returns:
        TransactionCostModel instance

    Raises:
        ValueError: If profile_name is not found

    Example:
        >>> cost_model = get_cost_model('KR_DEFAULT')
        >>> costs = cost_model.calculate_costs(
        ...     ticker='005930',
        ...     price=70000,
        ...     shares=100,
        ...     side=OrderSide.BUY,
        ... )
    """
    if profile_name == 'ZERO':
        return ZeroCostModel()

    if profile_name not in MARKET_COST_PROFILES:
        raise ValueError(
            f"Unknown cost profile: {profile_name}. "
            f"Available profiles: {list(MARKET_COST_PROFILES.keys())}"
        )

    profile = MARKET_COST_PROFILES[profile_name]
    return profile.to_cost_model()
