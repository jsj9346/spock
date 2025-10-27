"""
Backtest Configuration and Data Classes

Purpose: Define configuration structures and data models for backtesting module.

Classes:
  - BacktestConfig: Main configuration for backtest execution
  - Position: Open position tracking
  - Trade: Trade log entry
  - BacktestResult: Complete backtest results
  - PerformanceMetrics: Performance measurement structure
  - PatternMetrics: Pattern-specific performance metrics
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, List, Dict
import pandas as pd


@dataclass
class BacktestConfig:
    """
    Main configuration for backtest execution.

    Attributes:
        start_date: Backtest start date
        end_date: Backtest end date
        regions: List of regions to backtest (e.g., ['KR', 'US', 'JP'])
        tickers: Specific tickers to backtest (None = all available)
        score_threshold: LayeredScoringEngine minimum score for buy signal
        risk_profile: Risk profile (conservative, moderate, aggressive)
        kelly_multiplier: Kelly fraction multiplier (0.5 = half Kelly)
        max_position_size: Maximum position size as fraction of portfolio (0.15 = 15%)
        max_sector_exposure: Maximum sector exposure (0.40 = 40%)
        cash_reserve: Minimum cash reserve (0.20 = 20%)
        stop_loss_atr_multiplier: Stop loss as multiple of ATR
        stop_loss_min: Minimum stop loss percentage (0.05 = 5%)
        stop_loss_max: Maximum stop loss percentage (0.15 = 15%)
        profit_target: Profit taking target (0.20 = 20%)
        commission_rate: Commission rate (0.00015 = 0.015%)
        slippage_bps: Slippage in basis points
        initial_capital: Initial capital in base currency
    """

    # Time period
    start_date: date
    end_date: date

    # Region and tickers
    regions: List[str] = field(default_factory=lambda: ["KR"])
    tickers: Optional[List[str]] = None

    # Strategy parameters
    score_threshold: int = 70
    risk_profile: str = "moderate"  # conservative, moderate, aggressive

    # Position sizing
    kelly_multiplier: float = 0.5  # Half Kelly (conservative)
    max_position_size: float = 0.15  # 15% max per stock
    max_sector_exposure: float = 0.40  # 40% max per sector
    cash_reserve: float = 0.20  # 20% min cash

    # Risk management
    stop_loss_atr_multiplier: float = 1.0  # 1.0 × ATR
    stop_loss_min: float = 0.05  # 5% min stop loss
    stop_loss_max: float = 0.15  # 15% max stop loss
    profit_target: float = 0.20  # 20% profit taking

    # Transaction costs
    commission_rate: float = 0.00015  # 0.015% (KIS default for Korea)
    slippage_bps: float = 5.0  # 5 basis points

    # Initial capital
    initial_capital: float = 100_000_000  # 100M KRW

    def __post_init__(self):
        """Validate configuration parameters."""
        # Date validation
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")

        # Risk profile validation
        valid_profiles = ["conservative", "moderate", "aggressive"]
        if self.risk_profile not in valid_profiles:
            raise ValueError(f"risk_profile must be one of {valid_profiles}")

        # Region validation
        valid_regions = ["KR", "US", "CN", "HK", "JP", "VN"]
        for region in self.regions:
            if region not in valid_regions:
                raise ValueError(f"Invalid region: {region}. Must be one of {valid_regions}")

        # Parameter range validation
        if not 0 < self.kelly_multiplier <= 1.0:
            raise ValueError("kelly_multiplier must be in (0, 1.0]")
        if not 0 < self.max_position_size <= 1.0:
            raise ValueError("max_position_size must be in (0, 1.0]")
        if not 0 < self.max_sector_exposure <= 1.0:
            raise ValueError("max_sector_exposure must be in (0, 1.0]")
        if not 0 <= self.cash_reserve < 1.0:
            raise ValueError("cash_reserve must be in [0, 1.0)")
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")

    @classmethod
    def from_risk_profile(cls, start_date: date, end_date: date, risk_profile: str,
                          regions: List[str] = None, **kwargs) -> "BacktestConfig":
        """
        Create configuration from risk profile preset.

        Args:
            start_date: Backtest start date
            end_date: Backtest end date
            risk_profile: Risk profile (conservative, moderate, aggressive)
            regions: List of regions (default: ['KR'])
            **kwargs: Additional parameters to override

        Returns:
            BacktestConfig instance with profile-specific defaults
        """
        if regions is None:
            regions = ["KR"]

        # Risk profile presets (from spock_PRD.md)
        presets = {
            "conservative": {
                "score_threshold": 75,
                "kelly_multiplier": 0.25,
                "max_position_size": 0.10,
                "stop_loss_min": 0.03,
                "stop_loss_max": 0.08,
                "profit_target": 0.15,
            },
            "moderate": {
                "score_threshold": 70,
                "kelly_multiplier": 0.5,
                "max_position_size": 0.15,
                "stop_loss_min": 0.05,
                "stop_loss_max": 0.10,
                "profit_target": 0.20,
            },
            "aggressive": {
                "score_threshold": 65,
                "kelly_multiplier": 0.75,
                "max_position_size": 0.20,
                "stop_loss_min": 0.07,
                "stop_loss_max": 0.15,
                "profit_target": 0.25,
            },
        }

        if risk_profile not in presets:
            raise ValueError(f"risk_profile must be one of {list(presets.keys())}")

        # Merge preset with kwargs
        config_params = {
            "start_date": start_date,
            "end_date": end_date,
            "regions": regions,
            "risk_profile": risk_profile,
            **presets[risk_profile],
            **kwargs,  # User overrides
        }

        return cls(**config_params)


@dataclass
class Position:
    """
    Open position tracking.

    Attributes:
        ticker: Stock ticker
        region: Market region
        entry_date: Position entry date
        entry_price: Entry price
        shares: Number of shares
        stop_loss_price: Stop loss price
        profit_target_price: Profit target price
        pattern_type: Chart pattern type (Stage2, VCP, etc.)
        entry_score: LayeredScoringEngine score at entry
        sector: GICS sector
    """

    ticker: str
    region: str
    entry_date: date
    entry_price: float
    shares: int
    stop_loss_price: float
    profit_target_price: float
    pattern_type: str
    entry_score: int
    sector: Optional[str] = None

    @property
    def position_value(self) -> float:
        """Calculate current position value."""
        return self.entry_price * self.shares

    @property
    def cost_basis(self) -> float:
        """Calculate total cost basis."""
        return self.entry_price * self.shares


@dataclass
class Trade:
    """
    Trade log entry.

    Attributes:
        ticker: Stock ticker
        region: Market region
        entry_date: Trade entry date
        exit_date: Trade exit date (None if still open)
        entry_price: Entry price
        exit_price: Exit price (None if still open)
        shares: Number of shares
        commission: Total commission paid
        slippage: Total slippage cost
        pnl: Realized profit/loss (None if still open)
        pnl_pct: Return percentage (None if still open)
        pattern_type: Chart pattern type
        exit_reason: Exit reason (profit_target, stop_loss, stage3_exit, manual)
        entry_score: LayeredScoringEngine score at entry
        sector: GICS sector
    """

    ticker: str
    region: str
    entry_date: date
    entry_price: float
    shares: int
    commission: float
    slippage: float
    pattern_type: str
    entry_score: int
    exit_date: Optional[date] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    exit_reason: Optional[str] = None
    sector: Optional[str] = None

    @property
    def is_closed(self) -> bool:
        """Check if trade is closed."""
        return self.exit_date is not None

    @property
    def holding_period_days(self) -> Optional[int]:
        """Calculate holding period in days."""
        if not self.is_closed:
            return None
        return (self.exit_date - self.entry_date).days

    def close(self, exit_date: date, exit_price: float, exit_reason: str):
        """
        Close the trade and calculate P&L.

        Args:
            exit_date: Trade exit date
            exit_price: Exit price
            exit_reason: Reason for exit
        """
        self.exit_date = exit_date
        self.exit_price = exit_price
        self.exit_reason = exit_reason

        # Calculate P&L
        gross_pnl = (exit_price - self.entry_price) * self.shares
        self.pnl = gross_pnl - self.commission - self.slippage
        self.pnl_pct = (exit_price - self.entry_price) / self.entry_price


@dataclass
class PerformanceMetrics:
    """
    Performance measurement structure.

    Attributes:
        total_return: Total return
        annualized_return: Annualized return
        cagr: Compound annual growth rate
        sharpe_ratio: Sharpe ratio (risk-adjusted return)
        sortino_ratio: Sortino ratio (downside risk)
        calmar_ratio: Calmar ratio (return vs max drawdown)
        max_drawdown: Maximum drawdown
        max_drawdown_duration_days: Max drawdown duration in days
        std_returns: Standard deviation of returns
        downside_deviation: Downside deviation
        total_trades: Total number of trades
        win_rate: Win rate (percentage)
        profit_factor: Profit factor (gross profit / gross loss)
        avg_win_pct: Average winning trade percentage
        avg_loss_pct: Average losing trade percentage
        avg_win_loss_ratio: Average win/loss ratio
        avg_holding_period_days: Average holding period in days
        kelly_accuracy: Kelly prediction accuracy
        alpha: Alpha vs benchmark (optional)
        beta: Beta vs benchmark (optional)
        information_ratio: Information ratio (optional)
    """

    # Return metrics
    total_return: float
    annualized_return: float
    cagr: float

    # Risk metrics
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_duration_days: int
    std_returns: float
    downside_deviation: float

    # Trading metrics
    total_trades: int
    win_rate: float
    profit_factor: float
    avg_win_pct: float
    avg_loss_pct: float
    avg_win_loss_ratio: float
    avg_holding_period_days: float

    # Kelly validation
    kelly_accuracy: float

    # Benchmark comparison (optional)
    alpha: Optional[float] = None
    beta: Optional[float] = None
    information_ratio: Optional[float] = None

    def meets_success_criteria(self) -> bool:
        """
        Check if metrics meet success criteria from spock_PRD.md.

        Returns:
            True if all criteria are met
        """
        criteria = {
            "Total Return ≥15%": self.annualized_return >= 0.15,
            "Sharpe Ratio ≥1.5": self.sharpe_ratio >= 1.5,
            "Max Drawdown ≤15%": abs(self.max_drawdown) <= 0.15,
            "Win Rate ≥55%": self.win_rate >= 0.55,
        }
        return all(criteria.values())


@dataclass
class PatternMetrics:
    """
    Pattern-specific performance metrics.

    Attributes:
        pattern_type: Chart pattern type
        total_trades: Number of trades with this pattern
        win_rate: Win rate for this pattern
        avg_return: Average return for this pattern
        total_pnl: Total P&L for this pattern
        avg_holding_days: Average holding period for this pattern
    """

    pattern_type: str
    total_trades: int
    win_rate: float
    avg_return: float
    total_pnl: float
    avg_holding_days: float


@dataclass
class BacktestResult:
    """
    Complete backtest results.

    Attributes:
        config: Backtest configuration
        metrics: Overall performance metrics
        trades: List of all trades
        equity_curve: Portfolio value over time (date → value)
        pattern_metrics: Metrics by pattern type
        region_metrics: Metrics by region (optional)
        execution_time_seconds: Backtest execution time
    """

    config: BacktestConfig
    metrics: PerformanceMetrics
    trades: List[Trade]
    equity_curve: pd.Series
    pattern_metrics: Dict[str, PatternMetrics]
    execution_time_seconds: float
    region_metrics: Optional[Dict[str, PerformanceMetrics]] = None

    @property
    def final_portfolio_value(self) -> float:
        """Get final portfolio value."""
        return self.equity_curve.iloc[-1]

    @property
    def total_profit(self) -> float:
        """Calculate total profit."""
        return self.final_portfolio_value - self.config.initial_capital

    @property
    def winning_trades(self) -> List[Trade]:
        """Get list of winning trades."""
        return [t for t in self.trades if t.is_closed and t.pnl > 0]

    @property
    def losing_trades(self) -> List[Trade]:
        """Get list of losing trades."""
        return [t for t in self.trades if t.is_closed and t.pnl < 0]
