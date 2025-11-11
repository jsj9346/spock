# mcp_server/adapters/__init__.py
"""
MCP Server Adapters

Thin wrappers around existing business logic modules.
Optimized for MCP protocol with caching and error handling.
"""

from .data_adapter import DataAdapter
from .backtest_adapter import BacktestAdapter
from .system_adapter import SystemAdapter
from .optimization_adapter import OptimizationAdapter

__all__ = ["DataAdapter", "BacktestAdapter", "SystemAdapter", "OptimizationAdapter"]
