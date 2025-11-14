# modules/screening/__init__.py
"""
Stock Screening Module

Provides standardized stock screening functionality with:
- Technical indicator filters (RSI, MACD, MA trends)
- Fundamental filters (PER, PBR, dividend yield, market cap)
- Multi-region support (KR, HK, US)
- Export capabilities (CSV, Excel)

Components:
- StockScreener: Unified screening engine (Phase 2.2)
- FilterRegistry: Filter registration and management
- TechnicalCalculator: RSI, MA, and trend analysis
- CompositeScorer: Weighted fundamental + technical scoring (Phase 3)

Usage:
    from modules.screening import StockScreener, FilterRegistry

    screener = StockScreener(db_manager)
    results = screener.screen_technical(region='HK', rsi_max=35)
    results.to_csv('oversold_stocks.csv')
"""

from modules.screening.stock_screener import (
    StockScreener,
    FilterRegistry,
    ScreeningResult
)

__all__ = [
    'StockScreener',
    'FilterRegistry',
    'ScreeningResult',
    'TechnicalCalculator',
    'CompositeScorer'
]
