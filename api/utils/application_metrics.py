"""
Application-Level Prometheus Metrics

Custom metrics for business logic monitoring:
- Backtesting performance and results
- Factor calculation performance
- Portfolio optimization metrics
- Data quality metrics

Author: Quant Platform Development Team
Date: 2025-10-22
Version: 1.0.0
"""

from prometheus_client import Histogram, Counter, Gauge


# ============================================================================
# Backtesting Metrics
# ============================================================================

# Backtest execution duration
BACKTEST_DURATION = Histogram(
    'backtest_duration_seconds',
    'Backtest execution duration in seconds',
    ['strategy_name', 'engine'],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0)
)

# Backtest execution counter
BACKTEST_EXECUTIONS = Counter(
    'backtest_executions_total',
    'Total number of backtest executions',
    ['strategy_name', 'engine', 'status']  # status: success, failed, timeout
)

# Backtest result metrics (Gauges for latest values)
BACKTEST_SHARPE_RATIO = Gauge(
    'backtest_sharpe_ratio',
    'Sharpe ratio of backtest result',
    ['strategy_name']
)

BACKTEST_TOTAL_RETURN = Gauge(
    'backtest_total_return_percent',
    'Total return percentage of backtest',
    ['strategy_name']
)

BACKTEST_MAX_DRAWDOWN = Gauge(
    'backtest_max_drawdown_percent',
    'Maximum drawdown percentage of backtest',
    ['strategy_name']
)

BACKTEST_WIN_RATE = Gauge(
    'backtest_win_rate_percent',
    'Win rate percentage of backtest',
    ['strategy_name']
)

BACKTEST_NUM_TRADES = Gauge(
    'backtest_num_trades',
    'Number of trades in backtest',
    ['strategy_name']
)


# ============================================================================
# Factor Analysis Metrics
# ============================================================================

# Factor calculation duration
FACTOR_CALCULATION_DURATION = Histogram(
    'factor_calculation_duration_seconds',
    'Factor calculation duration in seconds',
    ['factor_name'],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0)
)

# Factor calculation counter
FACTOR_CALCULATIONS = Counter(
    'factor_calculations_total',
    'Total number of factor calculations',
    ['factor_name', 'status']  # status: success, failed
)

# Factor usage counter
FACTOR_USAGE = Counter(
    'factor_usage_total',
    'Number of times each factor was used',
    ['factor_name']
)

# Factor score statistics (latest values)
FACTOR_SCORE_MEAN = Gauge(
    'factor_score_mean',
    'Mean factor score',
    ['factor_name']
)

FACTOR_SCORE_STDDEV = Gauge(
    'factor_score_stddev',
    'Standard deviation of factor scores',
    ['factor_name']
)


# ============================================================================
# Portfolio Optimization Metrics (Future Implementation)
# ============================================================================

# Portfolio optimization duration
OPTIMIZATION_DURATION = Histogram(
    'optimization_duration_seconds',
    'Portfolio optimization duration in seconds',
    ['method', 'num_assets'],
    buckets=(0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0)
)

# Optimization execution counter
OPTIMIZATION_EXECUTIONS = Counter(
    'optimization_executions_total',
    'Total number of optimization executions',
    ['method', 'status']  # status: success, failed, no_solution, timeout
)

# Constraint violations counter
OPTIMIZATION_CONSTRAINT_VIOLATIONS = Counter(
    'optimization_constraint_violations_total',
    'Number of constraint violations during optimization',
    ['constraint_type']  # position_limit, sector_limit, turnover_limit
)

# Portfolio risk metrics (latest values)
PORTFOLIO_VAR_95 = Gauge(
    'portfolio_var_95_percent',
    'Portfolio Value at Risk (95% confidence)',
    ['portfolio_name']
)

PORTFOLIO_VOLATILITY = Gauge(
    'portfolio_volatility_annual',
    'Portfolio annual volatility',
    ['portfolio_name']
)

PORTFOLIO_SHARPE_RATIO = Gauge(
    'portfolio_sharpe_ratio',
    'Portfolio Sharpe ratio',
    ['portfolio_name']
)


# ============================================================================
# Data Quality Metrics
# ============================================================================

# Data missing ratio
DATA_MISSING_RATIO = Gauge(
    'data_missing_ratio_percent',
    'Percentage of missing data points',
    ['data_type', 'region']  # ohlcv, fundamentals, technical_indicators
)

# Data freshness (hours since last update)
DATA_FRESHNESS = Gauge(
    'data_freshness_hours',
    'Hours since last data update',
    ['data_source', 'region']  # kis_api, polygon_io, yfinance
)

# Data collection errors
DATA_COLLECTION_ERRORS = Counter(
    'data_collection_errors_total',
    'Total number of data collection errors',
    ['data_source', 'error_type']
)

# Data collection duration
DATA_COLLECTION_DURATION = Histogram(
    'data_collection_duration_seconds',
    'Data collection duration in seconds',
    ['data_source', 'data_type'],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0)
)


# ============================================================================
# Strategy Performance Metrics (Real-time Portfolio)
# ============================================================================

# Current portfolio value
PORTFOLIO_VALUE = Gauge(
    'portfolio_value_krw',
    'Current portfolio value in KRW',
    ['portfolio_name']
)

# Daily P&L
PORTFOLIO_DAILY_PNL = Gauge(
    'portfolio_daily_pnl_krw',
    'Daily profit/loss in KRW',
    ['portfolio_name']
)

# Position count
PORTFOLIO_POSITION_COUNT = Gauge(
    'portfolio_position_count',
    'Number of positions in portfolio',
    ['portfolio_name']
)

# Trade execution counter
TRADE_EXECUTIONS = Counter(
    'trade_executions_total',
    'Total number of trade executions',
    ['portfolio_name', 'side', 'status']  # side: buy/sell, status: success/failed
)


# ============================================================================
# API Usage Metrics (Application-Level)
# ============================================================================

# Strategy creation counter
STRATEGY_CREATIONS = Counter(
    'strategy_creations_total',
    'Total number of strategy creations',
    ['strategy_type']
)

# Backtest requests by region
BACKTEST_REQUESTS_BY_REGION = Counter(
    'backtest_requests_by_region_total',
    'Total backtest requests by region',
    ['region']  # KR, US, CN, HK, JP, VN
)

# Factor combination usage
FACTOR_COMBINATION_USAGE = Counter(
    'factor_combination_usage_total',
    'Number of times each factor combination was used',
    ['factor_combination']  # e.g., "momentum+value+quality"
)


# ============================================================================
# Utility Functions
# ============================================================================

def record_backtest_result(
    strategy_name: str,
    sharpe_ratio: float = None,
    total_return: float = None,
    max_drawdown: float = None,
    win_rate: float = None,
    num_trades: int = None
):
    """
    Record backtest result metrics.

    Args:
        strategy_name: Strategy name
        sharpe_ratio: Sharpe ratio (optional)
        total_return: Total return in percentage (optional)
        max_drawdown: Maximum drawdown in percentage (optional)
        win_rate: Win rate in percentage (optional)
        num_trades: Number of trades (optional)
    """
    if sharpe_ratio is not None:
        BACKTEST_SHARPE_RATIO.labels(strategy_name=strategy_name).set(sharpe_ratio)

    if total_return is not None:
        BACKTEST_TOTAL_RETURN.labels(strategy_name=strategy_name).set(total_return)

    if max_drawdown is not None:
        BACKTEST_MAX_DRAWDOWN.labels(strategy_name=strategy_name).set(abs(max_drawdown))

    if win_rate is not None:
        BACKTEST_WIN_RATE.labels(strategy_name=strategy_name).set(win_rate)

    if num_trades is not None:
        BACKTEST_NUM_TRADES.labels(strategy_name=strategy_name).set(num_trades)


def record_factor_statistics(factor_name: str, scores: list):
    """
    Record factor score statistics.

    Args:
        factor_name: Factor name
        scores: List of factor scores
    """
    if not scores:
        return

    import numpy as np

    mean_score = np.mean(scores)
    stddev_score = np.std(scores)

    FACTOR_SCORE_MEAN.labels(factor_name=factor_name).set(mean_score)
    FACTOR_SCORE_STDDEV.labels(factor_name=factor_name).set(stddev_score)
