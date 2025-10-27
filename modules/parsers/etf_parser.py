"""
ETF Data Parser

Normalizes ETF data from various sources and calculates tracking errors.

Author: Spock Trading System
"""

import logging
import numpy as np
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ETFParser:
    """
    ETF data parser and normalizer

    Handles:
    - KRX ETF data parsing
    - KIS ETF details parsing
    - Tracking error calculation (20d, 60d, 120d, 250d)
    - Geographic region mapping
    - Fund type classification
    """

    # Geographic region keywords
    REGION_KEYWORDS = {
        '미국': 'US',
        'S&P': 'US',
        '나스닥': 'US',
        'NASDAQ': 'US',
        '다우': 'US',
        '중국': 'CN',
        '차이나': 'CN',
        'CHINA': 'CN',
        '일본': 'JP',
        'JAPAN': 'JP',
        '유럽': 'EU',
        'EUROPE': 'EU',
        '베트남': 'VN',
        'VIETNAM': 'VN',
        '인도': 'IN',
        'INDIA': 'IN',
        '글로벌': 'GLOBAL',
        'GLOBAL': 'GLOBAL',
        '선진국': 'DEVELOPED',
        '신흥국': 'EMERGING',
    }

    # Sector/Theme keywords
    SECTOR_KEYWORDS = {
        '반도체': 'Semiconductors',
        '2차전지': 'Secondary Battery',
        '배터리': 'Battery',
        'ESG': 'ESG',
        '바이오': 'Biotechnology',
        '헬스케어': 'Healthcare',
        '금융': 'Financials',
        '은행': 'Banks',
        'IT': 'Information Technology',
        '테크': 'Technology',
        '에너지': 'Energy',
        '리츠': 'REITs',
        '부동산': 'Real Estate',
        '채권': 'Bonds',
        '금': 'Gold',
        '원자재': 'Commodities',
    }

    def parse_krx_etf(self, raw_data: Dict) -> Dict:
        """
        Parse KRX ETF data

        Args:
            raw_data: Raw ETF data from KRX Data API

        Returns:
            Standardized ETF dictionary
        """
        try:
            ticker = raw_data['ISU_SRT_CD']
            name = raw_data['ISU_ABBRV']

            return {
                'ticker': ticker,
                'name': name,
                'name_eng': raw_data.get('ISU_ENG_NM'),
                'exchange': 'KOSPI',  # All ETFs trade on KOSPI
                'region': 'KR',
                'currency': 'KRW',
                'issuer': raw_data.get('COMPANY_NM'),  # 운용사
                'tracking_index': raw_data.get('OBJ_TP_NM'),  # 추종지수
                'listed_shares': int(raw_data.get('LIST_SHRS', 0)),
                'listing_date': raw_data.get('LIST_DD'),
                'geographic_region': self._detect_region(name),
                'sector_theme': self._detect_sector(name),
                'fund_type': self._detect_fund_type(name),
                'data_source': 'KRX Data API',
            }

        except Exception as e:
            logger.error(f"❌ KRX ETF parsing failed: {e}")
            return {}

    def parse_kis_etf_details(self, raw_data: Dict) -> Dict:
        """
        Parse KIS ETF details API response

        Args:
            raw_data: Raw ETF details from KIS API

        Returns:
            ETF details dictionary
        """
        try:
            return {
                'ticker': raw_data.get('ticker'),
                'issuer': raw_data.get('aset_mgmt_comp_nm'),
                'tracking_index': raw_data.get('idx_bztp_scl_itm_nm'),
                'expense_ratio': float(raw_data.get('tot_expn_rt', 0)),
                'listed_shares': int(raw_data.get('lstg_shr_numb', 0)),
            }

        except Exception as e:
            logger.error(f"❌ KIS ETF details parsing failed: {e}")
            return {}

    def calculate_tracking_error(self, nav_data: Dict) -> Dict:
        """
        Calculate tracking error from NAV comparison data

        Tracking Error = (ETF Price - NAV) / NAV * 100 (%)

        Args:
            nav_data: NAV comparison data from KIS API
                      {'nav_comparison': [{'date': ..., 'etf_price': ..., 'nav': ..., 'tracking_error': ...}]}

        Returns:
            Dictionary with tracking errors: {'tracking_error_20d': ..., 'tracking_error_60d': ...}
        """
        try:
            nav_comparison = nav_data.get('nav_comparison', [])
            if not nav_comparison:
                return {}

            # Extract tracking error values
            tracking_errors = [item.get('tracking_error', 0) for item in nav_comparison]

            # Calculate averages for different periods
            return {
                'tracking_error_20d': self._calc_avg(tracking_errors, 20),
                'tracking_error_60d': self._calc_avg(tracking_errors, 60),
                'tracking_error_120d': self._calc_avg(tracking_errors, 120),
                'tracking_error_250d': self._calc_avg(tracking_errors, 250),
            }

        except Exception as e:
            logger.error(f"❌ Tracking error calculation failed: {e}")
            return {}

    def _calc_avg(self, values: List[float], period: int) -> Optional[float]:
        """
        Calculate average tracking error for period

        Args:
            values: List of tracking error values
            period: Number of days

        Returns:
            Average tracking error or None
        """
        if not values:
            return None

        # Take last N values (most recent)
        period_values = values[:period] if len(values) >= period else values

        if not period_values:
            return None

        # Calculate average (ignore NaN/None values)
        valid_values = [v for v in period_values if v is not None and not np.isnan(v)]

        if not valid_values:
            return None

        return round(np.mean(valid_values), 4)

    def _detect_region(self, etf_name: str) -> Optional[str]:
        """
        Detect geographic region from ETF name

        Args:
            etf_name: ETF name (Korean or English)

        Returns:
            Region code (US, CN, KR, GLOBAL, etc.) or None
        """
        if not etf_name:
            return None

        # Check each region keyword
        for keyword, region in self.REGION_KEYWORDS.items():
            if keyword in etf_name:
                return region

        # If no specific region found, assume Korea
        return 'KR'

    def _detect_sector(self, etf_name: str) -> Optional[str]:
        """
        Detect sector/theme from ETF name

        Args:
            etf_name: ETF name

        Returns:
            Sector/theme or None
        """
        if not etf_name:
            return None

        # Check each sector keyword
        for keyword, sector in self.SECTOR_KEYWORDS.items():
            if keyword in etf_name:
                return sector

        return None

    def _detect_fund_type(self, etf_name: str) -> str:
        """
        Detect fund type from ETF name

        Args:
            etf_name: ETF name

        Returns:
            Fund type (index, sector, thematic, commodity, inverse, leverage)
        """
        if not etf_name:
            return 'index'

        name_upper = etf_name.upper()

        # Leveraged/Inverse
        if any(kw in name_upper for kw in ['레버리지', '2X', '3X', 'LEVERAGE']):
            return 'leverage'

        if any(kw in name_upper for kw in ['인버스', 'INVERSE', '숏', 'SHORT']):
            return 'inverse'

        # Commodity
        if any(kw in name_upper for kw in ['금', 'GOLD', '은', 'SILVER', '원자재', 'COMMODITY']):
            return 'commodity'

        # Thematic
        if any(kw in name_upper for kw in ['ESG', '2차전지', '바이오', '테마']):
            return 'thematic'

        # Sector
        if any(kw in name_upper for kw in ['반도체', 'IT', '금융', '에너지', '헬스케어']):
            return 'sector'

        # Default: Index fund
        return 'index'

    def validate_etf_ticker(self, ticker: str) -> bool:
        """
        Validate ETF ticker format

        Args:
            ticker: ETF ticker code

        Returns:
            True if valid ETF ticker format
        """
        # Korean ETF tickers are 6 digits
        if not ticker or len(ticker) != 6:
            return False

        # Must be all digits
        if not ticker.isdigit():
            return False

        # ETF tickers typically start with 1, 2, or 4
        # (but this is not a strict rule)
        return True
