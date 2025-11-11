# mcp_server/utils/__init__.py
"""
Utility modules for MCP server
"""

from .errors import (
    SpockMCPError,
    ValidationError,
    DataNotFoundError,
    BacktestError,
    DatabaseError,
    PortfolioError,
)
from .validators import (
    validate_tickers,
    validate_date_range,
    validate_strategy_config,
)
from .formatters import (
    format_ohlcv_response,
    format_backtest_response,
    format_portfolio_response,
)

__all__ = [
    # Errors
    "SpockMCPError",
    "ValidationError",
    "DataNotFoundError",
    "BacktestError",
    "DatabaseError",
    "PortfolioError",
    # Validators
    "validate_tickers",
    "validate_date_range",
    "validate_strategy_config",
    # Formatters
    "format_ohlcv_response",
    "format_backtest_response",
    "format_portfolio_response",
]
