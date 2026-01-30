# tests/unit/conftest.py
"""
Pytest configuration for unit tests.

Ensures proper Python path setup for importing mcp_server modules.
"""

import sys
import os

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
