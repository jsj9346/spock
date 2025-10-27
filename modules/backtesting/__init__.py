"""
Spock Backtesting Module

Purpose: Enable power users to validate trading strategies with historical data
         before live deployment.

Core Components:
  - BacktestEngine: Main orchestrator for event-driven backtesting
  - HistoricalDataProvider: Efficient historical data access with caching
  - PortfolioSimulator: Position tracking and P&L calculation
  - PerformanceAnalyzer: Comprehensive performance metrics
  - StrategyRunner: LayeredScoringEngine integration
  - ParameterOptimizer: Automated parameter tuning
  - TransactionCostModel: Realistic cost modeling
  - BacktestReporter: Multi-format report generation

Design Philosophy:
  - Event-driven architecture to prevent look-ahead bias
  - 80%+ code reuse from existing Spock modules
  - In-memory data structures for fast iteration
  - Pluggable strategy and cost models
  - Evidence-based metrics aligned with spock_PRD.md

Author: Spock Development Team
Version: 1.0.0
"""

from .backtest_config import (
    BacktestConfig,
    Position,
    Trade,
    BacktestResult,
    PerformanceMetrics,
    PatternMetrics,
)
from .backtest_engine import BacktestEngine
from .historical_data_provider import HistoricalDataProvider
from .portfolio_simulator import PortfolioSimulator
from .strategy_runner import StrategyRunner, run_generate_buy_signals
from .performance_analyzer import PerformanceAnalyzer
from .backtest_reporter import BacktestReporter
from .transaction_cost_model import (
    TransactionCostModel,
    StandardCostModel,
    ZeroCostModel,
    get_cost_model,
    OrderSide,
    TimeOfDay,
    TransactionCosts,
    MarketCostProfile,
    MARKET_COST_PROFILES,
)
from .parameter_optimizer import (
    ParameterOptimizer,
    ParameterSpec,
    OptimizationConfig,
    OptimizationTrial,
    OptimizationResult,
)
from .grid_search_optimizer import GridSearchOptimizer

__all__ = [
    "BacktestConfig",
    "Position",
    "Trade",
    "BacktestResult",
    "PerformanceMetrics",
    "PatternMetrics",
    "BacktestEngine",
    "HistoricalDataProvider",
    "PortfolioSimulator",
    "StrategyRunner",
    "run_generate_buy_signals",
    "PerformanceAnalyzer",
    "BacktestReporter",
    "TransactionCostModel",
    "StandardCostModel",
    "ZeroCostModel",
    "get_cost_model",
    "OrderSide",
    "TimeOfDay",
    "TransactionCosts",
    "MarketCostProfile",
    "MARKET_COST_PROFILES",
    "ParameterOptimizer",
    "ParameterSpec",
    "OptimizationConfig",
    "OptimizationTrial",
    "OptimizationResult",
    "GridSearchOptimizer",
]

__version__ = "1.0.0"
