# mcp_server/__init__.py
"""
Spock MCP Server

Model Context Protocol (MCP) server for AI-powered quant analysis.
"""

import os
import sys
from pathlib import Path


def configure_mcp_logging():
    """
    Configure loguru globally for MCP server compatibility.

    MCP protocol requires clean JSON communication on stdio.
    This function:
    1. Removes default loguru handlers (which output colored text to stderr)
    2. Adds file-based logging only
    3. Ensures no ANSI color codes are emitted

    Must be called BEFORE importing any modules that use loguru.
    """
    try:
        from loguru import logger

        # Remove all default handlers
        logger.remove()

        # Add file handler only (no stderr output)
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)

        log_file = log_dir / "mcp_server.log"

        logger.add(
            log_file,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            level="INFO",
            rotation="10 MB",
            retention="7 days",
            compression="zip",
            enqueue=True,  # Thread-safe logging
            colorize=False,  # No ANSI color codes
        )

        # Optional: Add stderr handler ONLY for CRITICAL errors
        # This helps with debugging catastrophic failures
        logger.add(
            sys.stderr,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
            level="CRITICAL",
            colorize=False,  # No colors for MCP compatibility
        )

        logger.info("MCP Server logging configured successfully")
        logger.info(f"Log file: {log_file}")

    except ImportError:
        # Loguru not installed, skip configuration
        pass


# Configure logging immediately on module import
configure_mcp_logging()


# Import after logging is configured
from .server import SpockMCPServer, main
from .config import Config

__version__ = "0.1.0"
__all__ = ["SpockMCPServer", "main", "Config", "configure_mcp_logging"]
