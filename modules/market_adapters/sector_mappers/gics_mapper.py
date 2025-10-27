"""
GICS Sector Mapper

Direct GICS classification mapper for markets that use GICS natively.
Used for: USA, Hong Kong

No conversion needed - GICS is the native classification system.

Author: Spock Trading System
"""

import logging
from typing import Dict, Optional
from .base_mapper import BaseSectorMapper

logger = logging.getLogger(__name__)


class GICSSectorMapper(BaseSectorMapper):
    """
    GICS sector mapper for markets using GICS natively

    Markets: USA (S&P, MSCI), Hong Kong (HKEX uses GICS)

    GICS Structure:
    - Level 1: 11 Sectors (e.g., 45 = Information Technology)
    - Level 2: 25 Industry Groups (e.g., 4510 = Software & Services)
    - Level 3: 74 Industries (e.g., 451020 = IT Services)
    - Level 4: 163 Sub-Industries (e.g., 45102010 = IT Consulting & Services)

    For simplicity, we use Level 1 (11 sectors) for cross-market comparison.
    """

    # GICS Level 1 Sectors (official)
    GICS_LEVEL1 = {
        '10': 'Energy',
        '15': 'Materials',
        '20': 'Industrials',
        '25': 'Consumer Discretionary',
        '30': 'Consumer Staples',
        '35': 'Health Care',
        '40': 'Financials',
        '45': 'Information Technology',
        '50': 'Communication Services',
        '55': 'Utilities',
        '60': 'Real Estate'
    }

    # Common GICS Level 2 Industry Groups (for reference)
    GICS_LEVEL2_EXAMPLES = {
        '1010': 'Energy',
        '1510': 'Materials',
        '2010': 'Capital Goods',
        '2020': 'Commercial & Professional Services',
        '2030': 'Transportation',
        '2510': 'Automobiles & Components',
        '2520': 'Consumer Durables & Apparel',
        '2530': 'Consumer Services',
        '2540': 'Retailing',
        '2550': 'Consumer Discretionary Distribution & Retail',
        '3010': 'Consumer Staples Distribution & Retail',
        '3020': 'Food, Beverage & Tobacco',
        '3030': 'Household & Personal Products',
        '3510': 'Health Care Equipment & Services',
        '3520': 'Pharmaceuticals, Biotechnology & Life Sciences',
        '4010': 'Banks',
        '4020': 'Financial Services',
        '4030': 'Insurance',
        '4040': 'Diversified Financials',
        '4510': 'Software & Services',
        '4520': 'Technology Hardware & Equipment',
        '4530': 'Semiconductors & Semiconductor Equipment',
        '5010': 'Telecommunication Services',
        '5020': 'Media & Entertainment',
        '5510': 'Utilities',
        '6010': 'Real Estate'
    }

    def __init__(self, mapping_file: Optional[str] = None):
        """
        Initialize GICS mapper

        Args:
            mapping_file: Optional JSON file for custom mappings (not needed for standard GICS)
        """
        super().__init__(mapping_file)

    def map_to_gics(self, native_sector: str, native_code: Optional[str] = None) -> Dict:
        """
        Map GICS sector to standardized format

        Since GICS is already the standard, this mainly validates and structures the data.

        Args:
            native_sector: GICS sector name (e.g., "Information Technology")
            native_code: GICS code (e.g., "45", "4510", or "451020")

        Returns:
            Standardized sector dictionary
        """
        try:
            # Case 1: GICS code provided (2, 4, 6, or 8 digits)
            if native_code:
                sector_info = self._map_by_code(native_code)
                if sector_info:
                    sector_info['native_sector'] = native_sector or sector_info['sector']
                    sector_info['native_code'] = native_code
                    return sector_info

            # Case 2: GICS sector name provided
            if native_sector:
                sector_info = self._map_by_name(native_sector)
                if sector_info:
                    sector_info['native_sector'] = native_sector
                    sector_info['native_code'] = native_code or sector_info['sector_code']
                    return sector_info

            # Case 3: No valid input
            logger.warning(f"⚠️ No valid GICS sector/code provided")
            return self.get_fallback_mapping()

        except Exception as e:
            logger.error(f"❌ GICS mapping failed: {e}")
            return self.get_fallback_mapping()

    def _map_by_code(self, gics_code: str) -> Optional[Dict]:
        """
        Map by GICS code (supports 2, 4, 6, or 8 digit codes)

        Args:
            gics_code: GICS code (e.g., "45", "4510", "451020", "45102010")

        Returns:
            Sector mapping dictionary or None if invalid
        """
        # Extract Level 1 sector code (first 2 digits)
        if len(gics_code) < 2:
            logger.warning(f"⚠️ Invalid GICS code (too short): {gics_code}")
            return None

        sector_code = gics_code[:2]

        if sector_code not in self.GICS_LEVEL1:
            logger.warning(f"⚠️ Unknown GICS sector code: {sector_code}")
            return None

        sector_name = self.GICS_LEVEL1[sector_code]

        # Try to get industry group (Level 2) if 4+ digits
        industry_name = None
        industry_code = None

        if len(gics_code) >= 4:
            industry_code = gics_code[:4]
            industry_name = self.GICS_LEVEL2_EXAMPLES.get(industry_code, f"Industry Group {industry_code}")

        return {
            'sector': sector_name,
            'sector_code': sector_code,
            'industry': industry_name or sector_name,
            'industry_code': industry_code or sector_code
        }

    def _map_by_name(self, sector_name: str) -> Optional[Dict]:
        """
        Map by GICS sector name

        Args:
            sector_name: GICS sector name (e.g., "Information Technology")

        Returns:
            Sector mapping dictionary or None if invalid
        """
        # Normalize name
        normalized = self._normalize_sector_name(sector_name)

        # Exact match (case-insensitive)
        for code, name in self.GICS_LEVEL1.items():
            if normalized.lower() == name.lower():
                return {
                    'sector': name,
                    'sector_code': code,
                    'industry': name,
                    'industry_code': code
                }

        # Partial match (contains)
        for code, name in self.GICS_LEVEL1.items():
            if normalized.lower() in name.lower() or name.lower() in normalized.lower():
                logger.info(f"✅ Partial match: '{normalized}' → '{name}'")
                return {
                    'sector': name,
                    'sector_code': code,
                    'industry': name,
                    'industry_code': code
                }

        logger.warning(f"⚠️ Unknown GICS sector name: {sector_name}")
        return None

    def validate_gics_structure(self, gics_code: str) -> Dict:
        """
        Validate and parse GICS code structure

        Args:
            gics_code: Full GICS code (2-8 digits)

        Returns:
            Dictionary with GICS hierarchy levels
        """
        result = {
            'valid': False,
            'level': None,
            'sector_code': None,
            'industry_group_code': None,
            'industry_code': None,
            'sub_industry_code': None
        }

        if not gics_code or not gics_code.isdigit():
            return result

        code_len = len(gics_code)

        if code_len >= 2:
            result['sector_code'] = gics_code[:2]
            result['level'] = 1
            result['valid'] = result['sector_code'] in self.GICS_LEVEL1

        if code_len >= 4:
            result['industry_group_code'] = gics_code[:4]
            result['level'] = 2

        if code_len >= 6:
            result['industry_code'] = gics_code[:6]
            result['level'] = 3

        if code_len == 8:
            result['sub_industry_code'] = gics_code
            result['level'] = 4

        return result
