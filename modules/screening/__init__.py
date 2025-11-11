# modules/screening/__init__.py
"""
Stock Screening Module

Provides technical indicator calculations and composite scoring
for stock screening workflows.

Components:
- TechnicalCalculator: RSI, MA, and trend analysis
- CompositeScorer: Weighted fundamental + technical scoring (Phase 3)
"""

__all__ = ['TechnicalCalculator', 'CompositeScorer']
