# tests/conftest.py
"""
Root pytest configuration for all tests.

Ensures proper Python path setup before any test modules are imported.
"""

import sys
import os

def pytest_configure(config):
    """
    Called after command line options have been parsed and all plugins and
    initial conftest files been loaded.
    """
    # Add project root to Python path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Print debug info
    print(f"[pytest_configure] sys.path: {sys.path[:3]}")

    # Verify mcp_server can be imported
    try:
        from cli.utils.database import PostgresDatabaseManager
        print("[pytest_configure] Successfully imported cli.utils.database")
    except ImportError as e:
        print(f"[pytest_configure] WARNING importing cli.utils.database: {e}")

    try:
        from mcp_server.generators import StockChartGenerator
        print("[pytest_configure] Successfully imported mcp_server.generators")
    except ImportError as e:
        print(f"[pytest_configure] ERROR importing mcp_server.generators: {e}")
