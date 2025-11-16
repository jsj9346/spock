# modules/macro/__init__.py
"""
Macro Analysis Module

Components:
- sector_calculator: Sector performance calculation
- sector_definitions: KR/US sector-ticker mappings
"""

from .sector_calculator import SectorPerformanceCalculator
from .sector_definitions import KR_SECTORS, US_SECTORS

__all__ = ['SectorPerformanceCalculator', 'KR_SECTORS', 'US_SECTORS']
