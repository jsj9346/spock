# mcp_server/generators/__init__.py
"""
Chart generators for MCP Server.

Provides chart generation capabilities for visualizing stock data:
- StockChartGenerator: Candlestick charts with technical indicators
- ReturnComparisonGenerator: Multi-stock return comparison charts
"""

from .stock_chart_generator import StockChartGenerator
from .return_comparison_generator import ReturnComparisonGenerator

__all__ = ["StockChartGenerator", "ReturnComparisonGenerator"]
