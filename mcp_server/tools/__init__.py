# mcp_server/tools/__init__.py
"""
MCP Server Tools

Collection of MCP tools for quant analysis.
Each tool is a thin wrapper around existing business logic.
"""

from .data_query import register_data_query_tools

__all__ = ["register_data_query_tools"]
