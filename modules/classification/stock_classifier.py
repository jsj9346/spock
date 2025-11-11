"""
Stock Classifier - SPAC, Preferred Stock, and Sector Classification

Handles:
- SPAC (Special Purpose Acquisition Company) detection
- Preferred stock identification
- Sector and industry classification (KR, US markets)
- Database updates to tickers table

Database Strategy:
- Updates existing ticker records with classification fields
- Uses UPDATE statements (not UPSERT) since tickers already exist

Author: Spock Quant Platform
Date: 2025-11-05
"""

import logging
import re
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class StockClassifier:
    """
    Stock classification system for multi-market support

    Features:
    - SPAC detection via name pattern matching
    - Preferred stock identification (KR, US patterns)
    - Sector/industry classification
    - Batch processing with error handling

    Usage:
        classifier = StockClassifier(db_manager=db)
        result = classifier.classify_region('KR')
    """

    # SPAC detection patterns
    SPAC_PATTERNS = [
        r'SPAC',                    # Direct SPAC mention
        r'특수목적인수',             # Korean SPAC
        r'제\d+호',                 # 제1호, 제2호 SPAC numbering
        r'purpose\s+acquisition',   # English phrase
        r'blank\s+check',           # Alternative term
    ]

    # Preferred stock patterns by region (ticker patterns only)
    PREFERRED_TICKER_PATTERNS = {
        'KR': [
            r'^\d{5}[2-9]$',        # 6-digit ticker with suffix 2-9 (e.g., 005932)
        ],
        'US': [
            r'\.PR[A-Z]$',          # Series A format (e.g., BAC.PRA)
            r'-P[A-Z]?$',           # Alternative format (e.g., BAC-PA)
            r'_p[A-Z]?$',           # Underscore format
        ],
    }

    # Preferred stock name keywords (not regex)
    PREFERRED_NAME_KEYWORDS = {
        'KR': ['우선주', '1우B', '2우B', '1우', '2우', '3우'],
        'US': ['Preferred', 'PREF', 'Pfd'],
    }

    # Sector keywords for fallback classification (Korean market)
    SECTOR_KEYWORDS_KR = {
        'Technology': ['전자', '반도체', '소프트웨어', 'IT', '통신', '디스플레이'],
        'Finance': ['은행', '증권', '보험', '금융', '카드', '자산운용'],
        'Healthcare': ['제약', '바이오', '의료', '병원', '헬스케어'],
        'Consumer': ['식품', '유통', '화장품', '패션', '의류', '소비재'],
        'Industrial': ['건설', '철강', '화학', '조선', '기계', '자동차'],
        'Energy': ['전력', '가스', '에너지', '석유', '발전'],
        'Materials': ['화학', '철강', '금속', '시멘트', '제지'],
        'Real Estate': ['건설', '부동산', '리츠'],
    }

    def __init__(self, db_manager=None):
        """
        Initialize Stock Classifier

        Args:
            db_manager: Database manager instance (PostgresDatabaseManager)
        """
        self.db = db_manager
        self.logger = logger

        # Compile regex patterns for performance
        self._spac_patterns = [re.compile(p, re.IGNORECASE) for p in self.SPAC_PATTERNS]
        self._preferred_ticker_patterns = {
            region: [re.compile(p) for p in patterns]
            for region, patterns in self.PREFERRED_TICKER_PATTERNS.items()
        }

    def classify_region(self, region: str) -> Dict:
        """
        Classify all active tickers in a region

        Args:
            region: Region code (e.g., 'KR', 'US')

        Returns:
            Dict with keys:
                - classified: Number of tickers classified
                - spac_count: Number of SPACs detected
                - preferred_count: Number of preferred stocks detected
                - errors: Number of errors
                - success: Boolean indicating success
        """
        try:
            self.logger.info(f"🔄 Classifying stocks in region: {region}")

            # Get active tickers
            tickers = self._get_active_tickers(region)

            if not tickers:
                self.logger.warning(f"⚠️  No active tickers found for region {region}")
                return {
                    'classified': 0,
                    'spac_count': 0,
                    'preferred_count': 0,
                    'errors': 0,
                    'success': False
                }

            # Classify each ticker
            results = {
                'classified': 0,
                'spac_count': 0,
                'preferred_count': 0,
                'errors': 0
            }

            for ticker_data in tickers:
                try:
                    # Classify ticker
                    classification = self._classify_ticker(ticker_data, region)

                    # Update database
                    self._update_ticker_classification(
                        ticker_data['ticker'],
                        region,
                        classification
                    )

                    # Update counters
                    results['classified'] += 1
                    if classification.get('is_spac'):
                        results['spac_count'] += 1
                    if classification.get('is_preferred'):
                        results['preferred_count'] += 1

                except Exception as e:
                    self.logger.error(
                        f"  ❌ Failed to classify {ticker_data['ticker']}: {e}"
                    )
                    results['errors'] += 1

            self.logger.info(
                f"✅ Classification complete: {results['classified']} tickers, "
                f"{results['spac_count']} SPACs, "
                f"{results['preferred_count']} preferred stocks"
            )

            results['success'] = True
            return results

        except Exception as e:
            self.logger.error(f"❌ Region classification failed: {e}")
            return {
                'classified': 0,
                'spac_count': 0,
                'preferred_count': 0,
                'errors': 1,
                'success': False,
                'error': str(e)
            }

    def _classify_ticker(self, ticker_data: Dict, region: str) -> Dict:
        """
        Classify a single ticker

        Args:
            ticker_data: Dict with ticker metadata (ticker, name, etc.)
            region: Region code

        Returns:
            Dict with classification results:
                - is_spac: Boolean
                - is_preferred: Boolean
                - sector: String (optional)
                - industry: String (optional)
        """
        ticker = ticker_data['ticker']
        name = ticker_data.get('name', '')

        # Detect SPAC
        is_spac = self._detect_spac(name, ticker)

        # Detect preferred stock
        is_preferred = self._detect_preferred(name, ticker, region)

        # Classify sector/industry
        sector_info = self._classify_sector(ticker, region, ticker_data)

        return {
            'is_spac': is_spac,
            'is_preferred': is_preferred,
            'sector': sector_info.get('sector'),
            'industry': sector_info.get('industry')
        }

    def _detect_spac(self, name: str, ticker: str) -> bool:
        """
        Detect SPAC (Special Purpose Acquisition Company)

        Args:
            name: Company name
            ticker: Ticker symbol

        Returns:
            True if SPAC detected, False otherwise
        """
        if not name:
            return False

        # Check name patterns
        for pattern in self._spac_patterns:
            if pattern.search(name):
                self.logger.debug(f"SPAC detected: {ticker} ({name})")
                return True

        return False

    def _detect_preferred(self, name: str, ticker: str, region: str) -> bool:
        """
        Detect preferred stock

        Args:
            name: Company name
            ticker: Ticker symbol
            region: Region code

        Returns:
            True if preferred stock detected, False otherwise
        """
        # Check ticker patterns (regex)
        ticker_patterns = self._preferred_ticker_patterns.get(region, [])
        for pattern in ticker_patterns:
            if pattern.search(ticker):
                self.logger.debug(f"Preferred stock detected (ticker): {ticker}")
                return True

        # Check name keywords (substring match)
        if name:
            name_keywords = self.PREFERRED_NAME_KEYWORDS.get(region, [])
            for keyword in name_keywords:
                if keyword in name:
                    self.logger.debug(f"Preferred stock detected (name): {ticker} ({name})")
                    return True

        return False

    def _classify_sector(self, ticker: str, region: str,
                        ticker_data: Dict) -> Dict:
        """
        Classify sector and industry

        Strategy:
        1. Try to fetch from external data source (KRX, yfinance)
        2. Fallback to keyword-based classification
        3. Return None if unable to classify

        Args:
            ticker: Ticker symbol
            region: Region code
            ticker_data: Additional ticker metadata

        Returns:
            Dict with keys:
                - sector: Sector name (e.g., 'Technology')
                - industry: Industry name (e.g., 'Semiconductors')
        """
        # Try external data sources first
        if region == 'KR':
            # Try KRX data (future implementation)
            # For now, use fallback
            pass
        elif region == 'US':
            # Try yfinance data (future implementation)
            pass

        # Fallback: keyword-based classification
        sector = self._classify_sector_by_keywords(ticker_data.get('name', ''), region)

        return {
            'sector': sector,
            'industry': None  # Industry requires more detailed data
        }

    def _classify_sector_by_keywords(self, name: str, region: str) -> Optional[str]:
        """
        Classify sector using keyword matching (fallback method)

        Args:
            name: Company name
            region: Region code

        Returns:
            Sector name or None
        """
        if not name or region != 'KR':
            return None  # Only KR keywords implemented

        # Check each sector's keywords
        for sector, keywords in self.SECTOR_KEYWORDS_KR.items():
            for keyword in keywords:
                if keyword in name:
                    return sector

        return None

    def _get_active_tickers(self, region: str) -> List[Dict]:
        """
        Get active tickers from database

        Args:
            region: Region code

        Returns:
            List of ticker dicts with keys: ticker, name, exchange, asset_type
        """
        if not self.db:
            return []

        query = """
            SELECT ticker, name, exchange, asset_type
            FROM tickers
            WHERE region = %s
                AND is_active = TRUE
                AND asset_type = 'STOCK'
            ORDER BY ticker
        """

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (region,))

            results = cursor.fetchall()
            return [
                {
                    'ticker': row[0],
                    'name': row[1],
                    'exchange': row[2],
                    'asset_type': row[3]
                }
                for row in results
            ]

    def _update_ticker_classification(self, ticker: str, region: str,
                                     classification: Dict):
        """
        Update ticker classification in database

        Strategy: UPDATE existing ticker record
        - Tickers already exist (inserted by TickerRefresher)
        - Just update classification fields

        Args:
            ticker: Ticker symbol
            region: Region code
            classification: Classification results dict
        """
        if not self.db:
            return

        query = """
            UPDATE tickers
            SET
                is_spac = %s,
                is_preferred = %s,
                sector = %s,
                industry = %s,
                last_updated = NOW()
            WHERE ticker = %s AND region = %s
        """

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                classification.get('is_spac', False),
                classification.get('is_preferred', False),
                classification.get('sector'),
                classification.get('industry'),
                ticker,
                region
            ))
            conn.commit()

            self.logger.debug(
                f"Updated classification for {ticker}: "
                f"SPAC={classification.get('is_spac')}, "
                f"Preferred={classification.get('is_preferred')}"
            )
