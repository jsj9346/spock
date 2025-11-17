#!/usr/bin/env python3
"""
Collection Module - Direct PostgreSQL Data Collection Adapters

This module provides region-specific data collection adapters that store
data directly in PostgreSQL, eliminating SQLite dependencies.

Available Adapters:
- KRPostgresOHLCVAdapter: Direct PostgreSQL integration for KR market OHLCV data
- MacroDataAdapter: Global market indices, bonds, commodities, sentiment data
"""

from modules.collection.kr_postgres_ohlcv_adapter import KRPostgresOHLCVAdapter
from modules.collection.macro_data_adapter import MacroDataAdapter

__all__ = ['KRPostgresOHLCVAdapter', 'MacroDataAdapter']
