# mcp_server/utils/formatters.py
"""
Output formatting utilities for MCP server

Provides JSON and text formatting for various response types.
"""

import json
from typing import Dict, List


def format_ohlcv_response(data: Dict[str, List[Dict]]) -> str:
    """
    Format OHLCV data for MCP response.

    Args:
        data: Dictionary mapping ticker -> list of OHLCV records
              Example: {
                  "005930": [
                      {"date": "2024-01-01", "open": 70000, "high": 71000, "low": 69000, "close": 70500, "volume": 10000000},
                      ...
                  ]
              }

    Returns:
        str: JSON-formatted response string

    Output Format:
        {
            "success": true,
            "data": {...},
            "metadata": {
                "record_count": int,
                "tickers": list
            }
        }

    Example:
        >>> data = {"005930": [{"date": "2024-01-01", "open": 70000, ...}]}
        >>> result = format_ohlcv_response(data)
        >>> "success" in result
        True
    """
    # Calculate metadata
    total_records = sum(len(records) for records in data.values())
    tickers = list(data.keys())

    # Build response
    response = {
        "success": True,
        "data": data,
        "metadata": {
            "record_count": total_records,
            "tickers": tickers
        }
    }

    # Return formatted JSON
    return json.dumps(response, indent=2, ensure_ascii=False)


def format_backtest_response(results: Dict) -> str:
    """
    Format backtest results for MCP response.

    Args:
        results: Backtest results dictionary from BacktestAdapter with structure:
            {
                "success": bool,
                "engine": str,
                "performance": {
                    "total_return": float,
                    "annual_return": float,
                    "sharpe_ratio": float,
                    "max_drawdown": float
                },
                "trades": {
                    "total_trades": int,
                    "win_rate": float
                },
                "execution": {
                    "execution_time": float,
                    "start_date": str,
                    "end_date": str,
                    "initial_capital": float
                }
            }

    Returns:
        str: JSON-formatted response

    Example:
        >>> results = {
        ...     "success": True,
        ...     "engine": "vectorbt",
        ...     "performance": {"total_return": 0.45, "sharpe_ratio": 1.65},
        ...     "trades": {"total_trades": 125, "win_rate": 0.583}
        ... }
        >>> text = format_backtest_response(results)
        >>> "success" in text
        True
    """
    # Return JSON response directly (already formatted by adapter)
    return json.dumps(results, indent=2, ensure_ascii=False)


def format_portfolio_response(analysis: Dict) -> str:
    """
    Format portfolio analysis for MCP response.

    Args:
        analysis: Portfolio analysis results

    Returns:
        str: Formatted response text

    Note:
        Implementation deferred to Phase 2 (Week 3-4)

    Example:
        >>> analysis = {"total_value": 10000000}
        >>> result = format_portfolio_response(analysis)
        >>> "Phase 2" in result
        True
    """
    return "Portfolio formatting - Implementation deferred to Phase 2"
