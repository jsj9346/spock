"""
Base Sector Mapper

Abstract base class for sector classification mappers.
Each regional mapper converts native sector codes to standardized GICS classification.

Author: Spock Trading System
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
import json
import logging
import os

logger = logging.getLogger(__name__)


class BaseSectorMapper(ABC):
    """
    Abstract base class for sector mappers

    Each regional market has different sector classification systems:
    - Korea: KRX 지수업종 (Korean industry classification)
    - USA: GICS (Global Industry Classification Standard) - native
    - China: CSRC (China Securities Regulatory Commission) classification
    - Hong Kong: GICS with local variations
    - Japan: TSE 33 sectors (Tokyo Stock Exchange)
    - Vietnam: ICB (Industry Classification Benchmark) or local system

    All mappers convert to standardized GICS 11 sectors for cross-market comparison.
    """

    # GICS 11 Standard Sectors (fixed)
    GICS_SECTORS = {
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

    def __init__(self, mapping_file: Optional[str] = None):
        """
        Initialize sector mapper

        Args:
            mapping_file: Path to JSON mapping file (optional)
        """
        self.mapping_data = {}
        self.fallback_sector = {
            'sector': 'Industrials',
            'sector_code': '20',
            'industry': 'Unknown',
            'industry_code': '2090'
        }

        if mapping_file and os.path.exists(mapping_file):
            self.load_mapping_file(mapping_file)

    @abstractmethod
    def map_to_gics(self, native_sector: str, native_code: Optional[str] = None) -> Dict:
        """
        Convert native sector classification to GICS standard

        Args:
            native_sector: Native sector name (e.g., "전기전자", "Technology")
            native_code: Native sector code (optional, e.g., "G25", "4510")

        Returns:
            Dictionary with standardized GICS classification:
            {
                'sector': 'Information Technology',  # GICS English name
                'sector_code': '45',                 # GICS 2-digit code
                'industry': '전기전자',               # Native industry name (preserved)
                'industry_code': 'G25',              # Native industry code (preserved)
                'native_sector': '전기전자',          # Original sector name
                'native_code': 'G25'                 # Original sector code
            }
        """
        pass

    def load_mapping_file(self, filepath: str) -> bool:
        """
        Load sector mapping from JSON file

        Args:
            filepath: Path to mapping JSON file

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.mapping_data = json.load(f)

            logger.info(f"✅ Loaded sector mapping: {filepath}")

            # Validate mapping structure
            if 'krx_to_gics_mapping' in self.mapping_data:
                mapping_count = len(self.mapping_data['krx_to_gics_mapping'])
            elif 'mapping' in self.mapping_data:
                mapping_count = len(self.mapping_data['mapping'])
            else:
                mapping_count = len(self.mapping_data)

            logger.info(f"   {mapping_count} sector mappings loaded")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to load sector mapping {filepath}: {e}")
            return False

    def get_fallback_mapping(self) -> Dict:
        """
        Get fallback sector mapping for unmapped sectors

        Returns:
            Default sector mapping (Industrials)
        """
        return self.fallback_sector.copy()

    def validate_gics_code(self, gics_code: str) -> bool:
        """
        Validate GICS sector code

        Args:
            gics_code: 2-digit GICS sector code (e.g., "45")

        Returns:
            True if valid GICS code
        """
        return gics_code in self.GICS_SECTORS

    def get_gics_sector_name(self, gics_code: str) -> Optional[str]:
        """
        Get GICS sector name from code

        Args:
            gics_code: 2-digit GICS code

        Returns:
            GICS sector name or None if invalid
        """
        return self.GICS_SECTORS.get(gics_code)

    def _normalize_sector_name(self, sector_name: str) -> str:
        """
        Normalize sector name for matching

        Args:
            sector_name: Raw sector name

        Returns:
            Normalized sector name (trimmed, lowercase for comparison)
        """
        if not sector_name:
            return ''
        return sector_name.strip()

    def get_mapping_stats(self) -> Dict:
        """
        Get statistics about the mapping data

        Returns:
            Dictionary with mapping statistics
        """
        if not self.mapping_data:
            return {'total_mappings': 0, 'gics_sectors_used': []}

        # Extract mappings based on structure
        if 'krx_to_gics_mapping' in self.mapping_data:
            mappings = self.mapping_data['krx_to_gics_mapping']
        elif 'mapping' in self.mapping_data:
            mappings = self.mapping_data['mapping']
        else:
            mappings = self.mapping_data

        # Count GICS sectors used
        gics_sectors_used = set()
        for mapping in mappings.values():
            if isinstance(mapping, dict) and 'sector' in mapping:
                gics_sectors_used.add(mapping['sector'])

        return {
            'total_mappings': len(mappings),
            'gics_sectors_used': sorted(list(gics_sectors_used)),
            'coverage': f"{len(gics_sectors_used)}/11 GICS sectors"
        }
