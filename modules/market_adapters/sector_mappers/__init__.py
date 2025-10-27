"""
Sector Mapper System

Provides pluggable sector classification mappers for different countries.
All mappers convert native sector classifications to standardized GICS 11 sectors.

Available Mappers:
- GICSSectorMapper: US, Hong Kong (direct GICS, no conversion needed)
- CSRCSectorMapper: China (CSRC classification → GICS)
- TSESectorMapper: Japan (TSE 33 sectors → GICS)
- ICBSectorMapper: Vietnam (ICB → GICS)

Author: Spock Trading System
"""

from .base_mapper import BaseSectorMapper
from .gics_mapper import GICSSectorMapper

__all__ = [
    'BaseSectorMapper',
    'GICSSectorMapper',
]
