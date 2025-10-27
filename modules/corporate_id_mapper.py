#!/usr/bin/env python3
"""
Corporate ID Mapper - Abstract Base Class

Provides unified interface for ticker → corporate identifier mapping across regions.

Each region has different corporate identifier systems:
- KR: stock_code (6-digit) → corp_code (8-digit DART code)
- US: ticker → CIK (Central Index Key)
- CN: ticker → company_name (no separate corporate ID system)
- HK: ticker → HKEX code
- JP: ticker → TSE code
- VN: ticker → HSX/HNX code

Author: Spock Trading System
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BaseCorporateIDMapper(ABC):
    """
    Abstract base class for corporate identifier mapping

    Each regional mapper handles:
    1. Download mapping data from official source
    2. Build ticker → corporate_id mapping
    3. Provide fast lookup (direct + fuzzy matching)
    4. Cache management (24-hour TTL)

    Subclasses must implement:
    - download_mapping_data()
    - build_mapping()
    - _parse_mapping_file()
    """

    def __init__(self, region_code: str, cache_path: str, cache_ttl_hours: int = 24):
        """
        Initialize corporate ID mapper

        Args:
            region_code: Region code (KR, US, CN, HK, JP, VN)
            cache_path: Path to JSON cache file
            cache_ttl_hours: Cache TTL in hours (default: 24)
        """
        self.region_code = region_code
        self.cache_path = cache_path
        self.cache_ttl_hours = cache_ttl_hours

        # In-memory mapping cache
        self.ticker_to_id = {}  # Primary mapping: ticker → corporate_id
        self.name_to_id = {}    # Secondary mapping: company_name → corporate_id (for fuzzy matching)

        # Cache metadata
        self.last_updated = None
        self.mapping_count = 0

        # Load from cache if available and fresh
        self._load_from_cache()

    # ========================================
    # ABSTRACT METHODS (must be implemented)
    # ========================================

    @abstractmethod
    def download_mapping_data(self) -> bool:
        """
        Download mapping data from official source

        Returns:
            True if successful

        Note:
            Each region implements its own download logic:
            - KR: DART API /api/corpCode.xml
            - US: SEC EDGAR company_tickers.json
            - CN: AkShare stock list
            etc.
        """
        pass

    @abstractmethod
    def build_mapping(self) -> bool:
        """
        Build ticker → corporate_id mapping from downloaded data

        Returns:
            True if successful

        Note:
            Populates self.ticker_to_id and self.name_to_id dicts
            Saves to cache file
        """
        pass

    @abstractmethod
    def _parse_mapping_file(self) -> Dict[str, str]:
        """
        Parse region-specific mapping file format

        Returns:
            Dict {ticker: corporate_id}

        Note:
            Each region has different file formats:
            - KR: XML from DART
            - US: JSON from SEC
            - CN: DataFrame from AkShare
        """
        pass

    # ========================================
    # COMMON METHODS (shared across regions)
    # ========================================

    def get_corporate_id(self, ticker: str) -> Optional[str]:
        """
        Get corporate ID for a ticker

        Args:
            ticker: Ticker symbol

        Returns:
            Corporate ID or None if not found

        Lookup strategy:
        1. Direct match: ticker_to_id[ticker]
        2. Fuzzy match: company name similarity
        3. Cache miss: None
        """
        # Ensure mapping is loaded and fresh
        if not self._is_cache_fresh():
            logger.info(f"[{self.region_code}] Cache stale, refreshing...")
            self.refresh_mapping()

        # Direct match (fast path)
        if ticker in self.ticker_to_id:
            logger.debug(f"[{self.region_code}] {ticker}: Direct match found")
            return self.ticker_to_id[ticker]

        # Fuzzy match (slow path - only if needed)
        fuzzy_result = self._fuzzy_match(ticker)
        if fuzzy_result:
            logger.debug(f"[{self.region_code}] {ticker}: Fuzzy match found")
            return fuzzy_result

        # Not found
        logger.debug(f"[{self.region_code}] {ticker}: Corporate ID not found")
        return None

    def get_corporate_ids_batch(self, tickers: List[str]) -> Dict[str, Optional[str]]:
        """
        Batch lookup for multiple tickers (efficient)

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict {ticker: corporate_id or None}

        Performance: O(n) where n = len(tickers)
        """
        # Ensure mapping is loaded and fresh
        if not self._is_cache_fresh():
            logger.info(f"[{self.region_code}] Cache stale, refreshing...")
            self.refresh_mapping()

        results = {}
        for ticker in tickers:
            # Direct match
            if ticker in self.ticker_to_id:
                results[ticker] = self.ticker_to_id[ticker]
            else:
                # Fuzzy match (fallback)
                results[ticker] = self._fuzzy_match(ticker)

        # Log statistics
        found_count = sum(1 for v in results.values() if v is not None)
        logger.info(
            f"[{self.region_code}] Batch lookup: {found_count}/{len(tickers)} found "
            f"({found_count/len(tickers)*100:.1f}%)"
        )

        return results

    def refresh_mapping(self) -> bool:
        """
        Force refresh mapping data

        Workflow:
        1. Download mapping data from official source
        2. Build ticker → corporate_id mapping
        3. Save to cache
        4. Update metadata

        Returns:
            True if successful
        """
        try:
            logger.info(f"[{self.region_code}] Refreshing corporate ID mapping...")

            # Download mapping data
            if not self.download_mapping_data():
                logger.error(f"[{self.region_code}] Failed to download mapping data")
                return False

            # Build mapping
            if not self.build_mapping():
                logger.error(f"[{self.region_code}] Failed to build mapping")
                return False

            # Save to cache
            self._save_to_cache()

            # Update metadata
            self.last_updated = datetime.now()
            self.mapping_count = len(self.ticker_to_id)

            logger.info(
                f"✅ [{self.region_code}] Mapping refreshed: {self.mapping_count} tickers"
            )
            return True

        except Exception as e:
            logger.error(f"❌ [{self.region_code}] Refresh failed: {e}")
            return False

    # ========================================
    # CACHING METHODS
    # ========================================

    def _is_cache_fresh(self) -> bool:
        """
        Check if cache is fresh (within TTL)

        Returns:
            True if cache is fresh
        """
        if not self.last_updated:
            return False

        elapsed_hours = (datetime.now() - self.last_updated).total_seconds() / 3600
        return elapsed_hours < self.cache_ttl_hours

    def _load_from_cache(self) -> bool:
        """
        Load mapping from cache file

        Returns:
            True if successful
        """
        if not os.path.exists(self.cache_path):
            logger.debug(f"[{self.region_code}] No cache file found")
            return False

        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Load mappings
            self.ticker_to_id = cache_data.get('ticker_to_id', {})
            self.name_to_id = cache_data.get('name_to_id', {})

            # Load metadata
            last_updated_str = cache_data.get('last_updated')
            if last_updated_str:
                self.last_updated = datetime.fromisoformat(last_updated_str)

            self.mapping_count = len(self.ticker_to_id)

            # Check if cache is fresh
            if not self._is_cache_fresh():
                logger.warning(
                    f"[{self.region_code}] Cache expired "
                    f"(age: {(datetime.now() - self.last_updated).total_seconds() / 3600:.1f}h)"
                )
                return False

            logger.info(
                f"✅ [{self.region_code}] Loaded {self.mapping_count} mappings from cache"
            )
            return True

        except Exception as e:
            logger.warning(f"[{self.region_code}] Failed to load cache: {e}")
            return False

    def _save_to_cache(self) -> bool:
        """
        Save mapping to cache file

        Returns:
            True if successful
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)

            # Prepare cache data
            cache_data = {
                'region_code': self.region_code,
                'ticker_to_id': self.ticker_to_id,
                'name_to_id': self.name_to_id,
                'last_updated': datetime.now().isoformat(),
                'mapping_count': len(self.ticker_to_id)
            }

            # Write to file
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            logger.info(
                f"✅ [{self.region_code}] Saved {self.mapping_count} mappings to cache"
            )
            return True

        except Exception as e:
            logger.error(f"❌ [{self.region_code}] Failed to save cache: {e}")
            return False

    # ========================================
    # FUZZY MATCHING (optional enhancement)
    # ========================================

    def _fuzzy_match(self, ticker: str) -> Optional[str]:
        """
        Fuzzy matching for ticker → corporate_id

        Args:
            ticker: Ticker symbol

        Returns:
            Corporate ID or None

        Strategy:
        1. Substring match in company names
        2. Levenshtein distance (future enhancement)

        Note:
            This is a basic implementation.
            Production would use more sophisticated algorithms.
        """
        # Try substring matching with company names
        for name, corp_id in self.name_to_id.items():
            if ticker.lower() in name.lower() or name.lower() in ticker.lower():
                logger.debug(f"[{self.region_code}] {ticker}: Fuzzy match via '{name}'")
                return corp_id

        return None

    # ========================================
    # UTILITY METHODS
    # ========================================

    def get_statistics(self) -> Dict:
        """
        Get mapping statistics

        Returns:
            Dict with statistics
        """
        return {
            'region_code': self.region_code,
            'mapping_count': self.mapping_count,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'cache_fresh': self._is_cache_fresh(),
            'cache_path': self.cache_path
        }

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"region={self.region_code} "
            f"mappings={self.mapping_count} "
            f"fresh={self._is_cache_fresh()}>"
        )
