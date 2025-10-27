"""
Corporate ID Mappers - Region-Specific Implementations

Provides ticker → corporate identifier mapping for each market region.

Available Mappers:
- KRCorporateIDMapper: Korean market (DART corp_code)
- USCorporateIDMapper: US market (SEC CIK) [Phase 2]
- CNCorporateIDMapper: China market [Phase 2]
- HKCorporateIDMapper: Hong Kong market [Phase 2]
- JPCorporateIDMapper: Japan market [Phase 2]
- VNCorporateIDMapper: Vietnam market [Phase 2]

Author: Spock Trading System
"""

from .kr_corporate_id_mapper import KRCorporateIDMapper

__all__ = [
    'KRCorporateIDMapper',
]
