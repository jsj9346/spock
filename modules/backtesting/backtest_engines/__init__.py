"""
Backtest Engines Module

Multiple backtesting engine implementations with unified interface.

Available Engines:
    - Custom Event-Driven Engine (production, detailed simulation)
    - vectorbt Adapter (research, 100x faster, vectorized)
    - backtrader Adapter (optional, advanced features)
    - zipline Adapter (optional, institutional-grade)

Design Philosophy:
    - Pluggable architecture for easy engine switching
    - Standardized result format across engines
    - BaseDataProvider integration (SQLite/PostgreSQL compatible)
    - Performance-optimized for different use cases

Usage Example:
    # vectorbt for rapid research
    from .vectorbt_adapter import VectorbtAdapter
    adapter = VectorbtAdapter(config, data_provider)
    result = adapter.run()

    # Custom engine for production
    from ..backtest_engine import BacktestEngine
    engine = BacktestEngine(config, data_provider=data_provider)
    result = engine.run()
"""

__version__ = '0.1.0'

__all__ = []  # Populated as engines are implemented
