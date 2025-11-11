"""
conftest.py for fixtures directory

Pytest will automatically discover and register fixtures defined in postgres_fixtures.py
"""

# Import all fixtures to make them available to tests
from .postgres_fixtures import (
    postgres_test_db,
    ticker_factory,
    fundamentals_factory,
    factor_score_factory,
    ohlcv_factory
)

__all__ = [
    'postgres_test_db',
    'ticker_factory',
    'fundamentals_factory',
    'factor_score_factory',
    'ohlcv_factory'
]
