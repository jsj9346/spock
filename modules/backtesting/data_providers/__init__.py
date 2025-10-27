"""
Data Providers Module

Pluggable data provider architecture for backtesting engines.

Available Providers:
    - BaseDataProvider: Abstract base class defining interface
    - SQLiteDataProvider: SQLite database provider (legacy Spock compatibility)
    - PostgresDataProvider: PostgreSQL + TimescaleDB provider (production)

Design Philosophy:
    - Pluggable architecture: Easy to add new data sources (cloud, APIs)
    - Consistent interface: All providers implement BaseDataProvider
    - Point-in-time data: Prevent look-ahead bias in backtesting
    - Performance optimization: Caching, batch queries, connection pooling

Usage Example:
    # Legacy SQLite (backward compatible)
    from .sqlite_data_provider import SQLiteDataProvider
    provider = SQLiteDataProvider(db_manager)

    # PostgreSQL + TimescaleDB (production)
    from .postgres_data_provider import PostgresDataProvider
    provider = PostgresDataProvider(
        host='localhost',
        database='quant_platform'
    )

    # Use with BacktestEngine
    from ..backtest_engine import BacktestEngine
    engine = BacktestEngine(config, data_provider=provider)
"""

from .base_data_provider import BaseDataProvider
from .sqlite_data_provider import SQLiteDataProvider
from .postgres_data_provider import PostgresDataProvider

__all__ = ['BaseDataProvider', 'SQLiteDataProvider', 'PostgresDataProvider']
