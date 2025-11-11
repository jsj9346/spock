"""
Root conftest.py for pytest
Ensures proper Python path configuration and imports shared fixtures
"""
import sys
import os

# Add project root to Python path BEFORE pytest does anything
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def pytest_configure(config):
    """
    Pytest hook that runs early in the test lifecycle.
    Ensures sys.path is set up before test collection.
    """
    # Ensure project root is in sys.path
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    print(f"[pytest_configure] sys.path: {sys.path[:3]}")

    # Verify cli module is importable
    try:
        import cli.utils.database
        print(f"[pytest_configure] Successfully imported cli.utils.database")
    except ImportError as e:
        print(f"[pytest_configure] ERROR importing cli.utils.database: {e}")

    # Verify mcp_server module is importable
    try:
        import mcp_server.adapters
        print(f"[pytest_configure] Successfully imported mcp_server.adapters")
    except ImportError as e:
        print(f"[pytest_configure] ERROR importing mcp_server.adapters: {e}")


# Import PostgreSQL fixtures to make them available to all tests
# Add tests directory to path for fixture imports
tests_path = os.path.join(project_root, 'tests')
if tests_path not in sys.path:
    sys.path.insert(0, tests_path)

from fixtures.postgres_fixtures import (
    postgres_test_db,
    ticker_factory,
    fundamentals_factory,
    factor_score_factory,
    ohlcv_factory
)
