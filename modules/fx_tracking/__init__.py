"""
FX Tracking Module

Provides exchange rate tracking and FX signal generation for multi-currency
portfolio management.

Components:
- FXTracker: Main orchestrator for exchange rate updates
- ExchangeRateAPI: API client for fetching exchange rates

Usage:
    from modules.fx_tracking.fx_tracker import FXTracker

    tracker = FXTracker(db_manager=db)
    result = tracker.update_exchange_rates(
        currencies=['USD', 'JPY', 'EUR', 'CNY'],
        dry_run=False
    )
"""

from modules.fx_tracking.fx_tracker import FXTracker

__all__ = ['FXTracker']
