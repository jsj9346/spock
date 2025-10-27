"""
Stock Data Parser

Normalizes stock data from various sources (KRX, pykrx) to standardized format
for database insertion.

Author: Spock Trading System
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class StockParser:
    """
    Stock data parser and normalizer

    Handles:
    - KRX Data API response parsing
    - pykrx data parsing
    - Exchange mapping (KOSPI/KOSDAQ/KONEX)
    - Market tier detection (MAIN/NXT/KONEX)
    - GICS sector mapping
    """

    # GICS Sector mapping (simplified for Korean market)
    SECTOR_KEYWORDS = {
        # Energy
        '에너지': 'Energy',
        # Materials
        '소재': 'Materials',
        '화학': 'Materials',
        '철강': 'Materials',
        # Industrials
        '자본재': 'Industrials',
        '산업재': 'Industrials',
        '운송': 'Industrials',
        '조선': 'Industrials',
        '건설': 'Industrials',
        # Consumer Discretionary
        '자동차': 'Consumer Discretionary',
        '경기소비재': 'Consumer Discretionary',
        '현대차': 'Consumer Discretionary',
        # Consumer Staples
        '필수소비재': 'Consumer Staples',
        '식품': 'Consumer Staples',
        # Health Care
        '건강관리': 'Health Care',
        '제약': 'Health Care',
        '바이오': 'Health Care',
        # Financials
        '금융': 'Financials',
        '은행': 'Financials',
        '증권': 'Financials',
        '보험': 'Financials',
        # Information Technology
        '정보기술': 'Information Technology',
        '반도체': 'Information Technology',
        '하이닉스': 'Information Technology',  # SK하이닉스
        '삼성전자': 'Information Technology',
        '소프트웨어': 'Information Technology',
        'IT': 'Information Technology',
        # Communication Services
        '통신서비스': 'Communication Services',
        '미디어': 'Communication Services',
        '엔터': 'Communication Services',
        # Utilities
        '유틸리티': 'Utilities',
        '전기': 'Utilities',
        '가스': 'Utilities',
        # Real Estate
        '부동산': 'Real Estate',
    }

    def parse_krx_stock(self, raw_data: Dict) -> Dict:
        """
        Parse KRX Data API stock response

        Args:
            raw_data: Raw stock data from KRX Data API

        Returns:
            Standardized stock dictionary
        """
        try:
            ticker = raw_data['ISU_SRT_CD']
            name = raw_data['ISU_ABBRV']
            market = self._map_exchange(raw_data.get('MKT_TP_NM', ''))

            return {
                'ticker': ticker,
                'name': name,
                'name_eng': raw_data.get('ISU_ENG_NM'),
                'exchange': market,
                'market_tier': self._detect_tier(raw_data),
                'region': 'KR',
                'currency': 'KRW',
                'listing_date': raw_data.get('LIST_DD'),
                'sector': self._map_sector(name),
                'industry': raw_data.get('INDUTY_NM'),
                'is_preferred': self._is_preferred(name),
                'data_source': raw_data.get('data_source', 'KRX Data API'),
            }

        except Exception as e:
            logger.error(f"❌ KRX stock parsing failed: {e}")
            return {}

    def parse_pykrx_stock(self, ticker: str, name: str, market: str) -> Dict:
        """
        Parse pykrx stock data

        Args:
            ticker: Stock ticker code
            name: Stock name
            market: Market code (KOSPI, KOSDAQ)

        Returns:
            Standardized stock dictionary
        """
        try:
            return {
                'ticker': ticker,
                'name': name,
                'exchange': market,
                'market_tier': 'MAIN',  # pykrx doesn't provide tier info
                'region': 'KR',
                'currency': 'KRW',
                'sector': self._map_sector(name),
                'is_preferred': self._is_preferred(name),
                'data_source': 'pykrx',
            }

        except Exception as e:
            logger.error(f"❌ pykrx stock parsing failed: {e}")
            return {}

    def parse_market_cap_data(self, raw_data: Dict) -> Dict:
        """
        Parse KRX market cap data

        Args:
            raw_data: Raw market cap data from KRX

        Returns:
            Market cap dictionary
        """
        try:
            return {
                'ticker': raw_data['ISU_SRT_CD'],
                'close_price': int(raw_data.get('TDD_CLSPRC', 0)),
                'market_cap': int(raw_data.get('MKTCAP', 0)) * 100000000,  # 억원 → 원
                'volume': int(raw_data.get('ACC_TRDVOL', 0)),
                'trading_value': int(raw_data.get('ACC_TRDVAL', 0)) * 1000000,  # 백만원 → 원
            }

        except Exception as e:
            logger.error(f"❌ Market cap parsing failed: {e}")
            return {}

    def _map_exchange(self, krx_market: str) -> str:
        """
        Map KRX market code to standard exchange name

        Args:
            krx_market: KRX market type name

        Returns:
            Standard exchange name (KOSPI, KOSDAQ, KONEX)
        """
        # Normalize to uppercase for comparison
        krx_market_upper = krx_market.upper()

        market_map = {
            'KOSPI': 'KOSPI',
            'KOSDAQ': 'KOSDAQ',
            'KONEX': 'KONEX',
            'STK': 'KOSPI',  # 주권 = KOSPI
            'KSQ': 'KOSDAQ',  # 코스닥
            '코스피': 'KOSPI',
            '코스닥': 'KOSDAQ',
            '코넥스': 'KONEX',
        }

        return market_map.get(krx_market_upper, market_map.get(krx_market, 'UNKNOWN'))

    def _detect_tier(self, data: Dict) -> str:
        """
        Detect market tier (MAIN, NXT, KONEX)

        Args:
            data: Stock data dictionary with market_classification field

        Returns:
            Market tier (MAIN, NXT, KONEX)
        """
        market_classification = data.get('market_classification', '')
        market_name = data.get('MKT_TP_NM', '')

        # Check for NXT market
        if 'NXT' in market_classification or 'NXT' in market_name:
            return 'NXT'

        # Check for KONEX
        if 'KONEX' in market_classification or 'KONEX' in market_name:
            return 'KONEX'

        # Default: MAIN market
        return 'MAIN'

    def _map_sector(self, stock_name: str) -> Optional[str]:
        """
        Map stock name to GICS sector (keyword-based)

        Args:
            stock_name: Korean stock name

        Returns:
            GICS sector name or None
        """
        if not stock_name:
            return None

        # Check each sector keyword
        for keyword, sector in self.SECTOR_KEYWORDS.items():
            if keyword in stock_name:
                return sector

        # Default: None (will be updated later with more accurate data)
        return None

    def _is_preferred(self, stock_name: str) -> bool:
        """
        Check if stock is preferred stock

        Args:
            stock_name: Stock name

        Returns:
            True if preferred stock
        """
        if not stock_name:
            return False

        # Preferred stock keywords
        preferred_keywords = ['우', '우선주', '1우', '2우', '3우']

        return any(keyword in stock_name for keyword in preferred_keywords)

    def validate_ticker(self, ticker: str) -> bool:
        """
        Validate ticker format

        Args:
            ticker: Stock ticker code

        Returns:
            True if valid ticker format
        """
        # Korean stock tickers are 6 digits
        if not ticker or len(ticker) != 6:
            return False

        # Must be all digits
        if not ticker.isdigit():
            return False

        return True
