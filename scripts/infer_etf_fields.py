#!/usr/bin/env python3
"""
ETF Field Inference Script

Infers missing ETF details fields from existing data using pattern matching
and mapping logic. Processes 5 fields: underlying_asset_class, leverage_ratio,
currency_hedged, sector_theme, geographic_region.

Author: Spock Trading System
"""

import sys
import os
import logging
import re
from datetime import datetime
from typing import Dict, Optional, Tuple

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_sqlite import SQLiteDatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'logs/{datetime.now().strftime("%Y%m%d")}_etf_field_inference.log')
    ]
)
logger = logging.getLogger(__name__)


class ETFFieldInferenceEngine:
    """Inference engine for deriving missing ETF field values"""

    # Asset class mapping from fund_type
    ASSET_CLASS_MAPPING = {
        '주식': 'Equity',
        '채권': 'Bond',
        '원자재': 'Commodity',
        '부동산': 'Real Estate',
        '혼합': 'Mixed',
        '통화': 'Currency',
        'Equity': 'Equity',
        'Bond': 'Bond',
        'Commodity': 'Commodity',
    }

    # Sector theme keywords (EXPANDED - Task 2)
    SECTOR_THEMES = {
        # Original themes
        '반도체': 'Semiconductor',
        'Semiconductor': 'Semiconductor',
        'AI': 'AI',
        '인공지능': 'AI',
        '바이오': 'Biotechnology',
        'Bio': 'Biotechnology',
        '헬스케어': 'Healthcare',
        'Healthcare': 'Healthcare',
        '2차전지': 'Battery',
        'Battery': 'Battery',
        '배터리': 'Battery',
        '소프트웨어': 'Software',
        'Software': 'Software',
        '클라우드': 'Cloud Computing',
        'Cloud': 'Cloud Computing',
        '자동차': 'Automotive',
        'Auto': 'Automotive',
        '에너지': 'Energy',
        'Energy': 'Energy',
        '금융': 'Financial',
        'Finance': 'Financial',
        'Financial': 'Financial',
        '통신': 'Telecommunications',
        'Telecom': 'Telecommunications',
        '미디어': 'Media',
        'Media': 'Media',
        '게임': 'Gaming',
        'Gaming': 'Gaming',
        '게이밍': 'Gaming',
        '인터넷': 'Internet',
        'Internet': 'Internet',
        'BBIG': 'Big Tech',
        'FAANG': 'Big Tech',
        'FANG': 'Big Tech',
        '로봇': 'Robotics',
        'Robot': 'Robotics',
        '우주': 'Space',
        'Space': 'Space',
        '메타버스': 'Metaverse',
        'Metaverse': 'Metaverse',
        'ESG': 'ESG',
        '부동산': 'Real Estate',
        'REIT': 'REITs',
        'Real Estate': 'Real Estate',
        '리츠': 'REITs',
        '인프라': 'Infrastructure',
        'Infrastructure': 'Infrastructure',
        '배당': 'Dividend',
        'Dividend': 'Dividend',
        '고배당': 'High Dividend',
        'High Dividend': 'High Dividend',

        # NEW: Factor-based themes
        '가치': 'Value',
        'Value': 'Value',
        '성장': 'Growth',
        'Growth': 'Growth',
        '퀄리티': 'Quality',
        'Quality': 'Quality',
        '모멘텀': 'Momentum',
        'Momentum': 'Momentum',
        '배당성장': 'Dividend Growth',
        '주주가치': 'Shareholder Value',
        '저변동': 'Low Volatility',
        'Low Volatility': 'Low Volatility',

        # NEW: Korean-specific themes
        '미래전략기술': 'Future Technology',
        '디지털성장': 'Digital Growth',
        '디지털전환': 'Digital Transformation',
        '스마트팩토리': 'Smart Factory',
        '우주항공': 'Aerospace',
        '방위산업': 'Defense',
        'K-뉴딜': 'K-New Deal',
        '벤처': 'Venture',
        '중소형': 'Small-Mid Cap',

        # NEW: ESG sub-sectors
        '친환경': 'Clean Energy',
        '탄소중립': 'Carbon Neutral',
        '수소': 'Hydrogen',
        '태양광': 'Solar',
        '풍력': 'Wind',
        '전기차': 'Electric Vehicle',
        'EV': 'Electric Vehicle',

        # NEW: Emerging tech themes
        '양자컴퓨팅': 'Quantum Computing',
        'Quantum': 'Quantum Computing',
        '사이버보안': 'Cybersecurity',
        'Cybersecurity': 'Cybersecurity',
        '핀테크': 'Fintech',
        'Fintech': 'Fintech',
        '블록체인': 'Blockchain',
        'Blockchain': 'Blockchain',
        '온디바이스': 'On-Device AI',
        'On-Device': 'On-Device AI',
        '빅데이터': 'Big Data',
        'Big Data': 'Big Data',

        # NEW: Industry-specific
        '여행': 'Travel & Leisure',
        '레저': 'Travel & Leisure',
        'Travel': 'Travel & Leisure',
        'Leisure': 'Travel & Leisure',
        '소비재': 'Consumer',
        'Consumer': 'Consumer',
        '유통': 'Retail',
        'Retail': 'Retail',
        '제약': 'Pharmaceuticals',
        'Pharma': 'Pharmaceuticals',
        '화학': 'Chemicals',
        'Chemical': 'Chemicals',
        '철강': 'Steel',
        'Steel': 'Steel',
        '조선': 'Shipbuilding',
        '건설': 'Construction',
        'Construction': 'Construction',

        # NEW: Materials & Resources
        '원자재': 'Commodities',
        'Commodities': 'Commodities',
        '광물': 'Mining',
        'Mining': 'Mining',
        '귀금속': 'Precious Metals',
        'Precious Metals': 'Precious Metals',

        # Phase 1.5: Additional sector themes
        '테크': 'Technology',
        'Tech': 'Technology',
        'Technology': 'Technology',
        '원자력': 'Nuclear Energy',
        'Nuclear': 'Nuclear Energy',
        '그룹주': 'Conglomerate',
        '블루칩': 'Large Cap',
        'Blue Chip': 'Large Cap',
        'TOP': 'Large Cap',
        'TOP10': 'Large Cap',
        'TOP5': 'Large Cap',
        '멀티에셋': 'Multi-Asset',
        'Multi-Asset': 'Multi-Asset',
        '밸류체인': 'Value Chain',
        'Value Chain': 'Value Chain',
        '커버드콜': 'Covered Call',
        'Covered Call': 'Covered Call',
    }

    # Geographic region keywords (ENHANCED - Phase 1.5)
    REGION_KEYWORDS = {
        'KR': ['코스피', '코스닥', 'KOSPI', 'KOSDAQ', 'KRX', '한국', 'Korea', '그룹주', '그룹'],
        'US': ['S&P', 'NASDAQ', '나스닥', 'Russell', 'Dow', '미국', 'US', 'USA'],
        'CN': ['중국', 'China', 'CSI', '상해', '심천', 'MSCI China', '차이나', '항셍', 'Hang Seng', '과창판', 'STAR'],
        'JP': ['일본', 'Japan', 'TOPIX', 'Nikkei', '닛케이'],
        'EU': ['유럽', 'Europe', 'STOXX', '유로', 'Euro', '독일', 'Germany', 'DAX'],
        'IN': ['인도', 'India', 'Nifty', 'SENSEX'],
        'VN': ['베트남', 'Vietnam', 'VN30'],
        'SG': ['싱가포르', 'Singapore'],
        'PH': ['필리핀', 'Philippines'],
        'RU': ['러시아', 'Russia'],
        'MX': ['멕시코', 'Mexico', 'Mexican'],
        'LATAM': ['라틴', 'Latin', 'Latin America'],
        'GLOBAL': ['Global', '글로벌', 'World', 'MSCI World', 'ACWI', '멀티'],
        'ASIA': ['아시아', 'Asia', 'MSCI Asia'],
        'EM': ['이머징', 'Emerging', 'EM'],
    }

    def __init__(self, db: SQLiteDatabaseManager):
        self.db = db

    def infer_asset_class(self, fund_type: Optional[str], tracking_index: Optional[str], name: str) -> Optional[str]:
        """
        Infer underlying asset class from fund_type and tracking_index

        Args:
            fund_type: Fund type (e.g., "국내주식형", "채권형")
            tracking_index: Tracking index name
            name: ETF name

        Returns:
            Asset class (Equity, Bond, Commodity, Real Estate, Mixed, Currency) or None
        """
        if not fund_type and not tracking_index:
            return None

        combined_text = f"{fund_type or ''} {tracking_index or ''} {name}"

        # Check for direct mappings in fund_type
        if fund_type:
            for korean, english in self.ASSET_CLASS_MAPPING.items():
                if korean in fund_type:
                    return english

        # Check for mixed/hybrid indicators
        if '혼합' in combined_text or 'Mixed' in combined_text or 'Blend' in combined_text:
            return 'Mixed'

        # Check for commodity indicators
        if any(keyword in combined_text for keyword in ['금', 'Gold', '은', 'Silver', '원유', 'Oil', 'Crude', '구리', 'Copper', '원자재', 'Commodity']):
            return 'Commodity'

        # Check for real estate indicators
        if any(keyword in combined_text for keyword in ['리츠', 'REIT', 'Real Estate', '부동산']):
            return 'Real Estate'

        # Check for bond indicators
        if any(keyword in combined_text for keyword in ['채권', 'Bond', '국채', 'Treasury', 'Credit']):
            return 'Bond'

        # Check for currency indicators
        if any(keyword in combined_text for keyword in ['통화', 'Currency', 'FX', '환율', '달러', 'Dollar', '엔화', 'Yen']):
            return 'Currency'

        # Default to Equity if contains stock-related keywords
        if any(keyword in combined_text for keyword in ['주식', 'Stock', 'Equity', 'Index', '지수']):
            return 'Equity'

        return None

    def infer_leverage_ratio(self, name: str) -> str:
        """
        Infer leverage ratio from ETF name

        Args:
            name: ETF name

        Returns:
            Leverage ratio string (1x, 2x, -1x, -2x, etc.)
        """
        name_upper = name.upper()

        # Check for inverse/short indicators
        if any(keyword in name for keyword in ['인버스', '인버스2X', 'INVERSE', 'SHORT']):
            if '2X' in name_upper or '2배' in name or 'DOUBLE' in name_upper:
                return '-2x'
            return '-1x'

        # Check for leverage indicators
        if any(keyword in name for keyword in ['레버리지', 'LEVERAGE', 'BULL']):
            if '2X' in name_upper or '2배' in name:
                return '2x'
            if '3X' in name_upper or '3배' in name:
                return '3x'
            # Default leverage is 2x if not specified
            return '2x'

        # Default: no leverage
        return '1x'

    def infer_currency_hedged(self, name: str, tracking_index: Optional[str]) -> bool:
        """
        Infer currency hedging status from name and tracking index

        Args:
            name: ETF name
            tracking_index: Tracking index name

        Returns:
            True if currency hedged, False otherwise
        """
        combined_text = f"{name} {tracking_index or ''}"

        # Hedged indicators
        hedged_keywords = [
            '환헤지', '환헷지', '(H)', '(H )', '(환헤지)',
            'Hedged', 'Currency Hedged', 'FX Hedged',
            'Yen Hedged', '엔화헤지', '달러헤지'
        ]

        return any(keyword in combined_text for keyword in hedged_keywords)

    def infer_sector_theme(self, name: str, tracking_index: Optional[str], fund_type: Optional[str] = None) -> Optional[str]:
        """
        Infer sector theme from name and tracking index
        ENHANCED: Task 2 & Task 3 - Added broad market classification

        Args:
            name: ETF name
            tracking_index: Tracking index name
            fund_type: Fund type (optional)

        Returns:
            Sector theme string or None
        """
        combined_text = f"{name} {tracking_index or ''}"

        # Check for sector theme keywords (50+ new keywords added)
        for korean, english in self.SECTOR_THEMES.items():
            if korean in combined_text:
                return english

        # Task 3: Broad Market Classification
        # Check for broad market indices (no specific sector)
        broad_market_indicators = [
            '코스피 200', 'KOSPI 200', '코스피200',
            '코스피 100', 'KOSPI 100',
            '코스닥 150', 'KOSDAQ 150',
            'S&P 500', 'S&P500',
            'NASDAQ 100', 'NASDAQ-100', 'NASDAQ100',
            'Russell', 'Dow', 'MSCI World', 'ACWI',
            '종합지수', 'Total Market', 'All Cap'
        ]

        for indicator in broad_market_indicators:
            if indicator in combined_text:
                return 'Broad Market'

        # Task 3: Fixed Income Classification
        # Check for bond/fixed income ETFs
        if fund_type and '채권' in fund_type:
            return 'Fixed Income'

        bond_indicators = [
            '채권', 'Bond', '국채', 'Treasury',
            '회사채', 'Corporate Bond', '특수채',
            'Credit', '크레딧'
        ]

        for indicator in bond_indicators:
            if indicator in combined_text:
                return 'Fixed Income'

        return None

    def infer_geographic_region(self, name: str, tracking_index: Optional[str], fund_type: Optional[str] = None) -> Optional[str]:
        """
        Infer geographic region from name and tracking index
        ENHANCED: Task 1 - Added Korean-centric fallback rules

        Args:
            name: ETF name
            tracking_index: Tracking index name
            fund_type: Fund type (optional)

        Returns:
            Region code (KR, US, CN, JP, EU, IN, GLOBAL, ASIA, EM) or None
        """
        combined_text = f"{name} {tracking_index or ''}"

        # Check for region keywords in priority order
        # Priority: Specific country > Regional > Global
        for region, keywords in self.REGION_KEYWORDS.items():
            if region == 'GLOBAL':  # Check global last
                continue
            for keyword in keywords:
                if keyword in combined_text:
                    return region

        # Check for global last
        for keyword in self.REGION_KEYWORDS['GLOBAL']:
            if keyword in combined_text:
                return 'GLOBAL'

        # TASK 1: Korean-centric fallback rules (NEW)
        # Default to KR for Korean-only index providers
        korean_index_providers = ['iSelect', 'FnGuide', 'KAP', 'Wise', 'KEDI', 'KIS', 'Fn가이드', 'KIS금융']
        for provider in korean_index_providers:
            if provider in combined_text:
                # Check if NOT a foreign market reference
                foreign_indicators = ['미국', 'US', 'USA', '중국', 'China', '일본', 'Japan', '글로벌', 'Global']
                if not any(foreign in combined_text for foreign in foreign_indicators):
                    return 'KR'

        # Bond indices default to issuer country
        if fund_type and '채권' in fund_type:
            # Korean bonds unless explicitly foreign
            foreign_bond_indicators = ['미국', '글로벌', 'Global', 'US', 'Treasury', '중국', '일본']
            if not any(foreign in combined_text for foreign in foreign_bond_indicators):
                return 'KR'

        # Bond keyword indicators
        bond_keywords = ['채권', 'Bond', '국채', '회사채', '특수채']
        if any(keyword in combined_text for keyword in bond_keywords):
            # Korean bonds unless explicitly foreign
            foreign_bond_indicators = ['미국', '글로벌', 'Global', 'US', 'Treasury', '중국', '일본']
            if not any(foreign in combined_text for foreign in foreign_bond_indicators):
                return 'KR'

        # Sector-specific Korean themes
        korean_themes = [
            '2차전지', 'K-AI', '바이오', '주주가치', '미래전략기술',
            'K-뉴딜', '벤처', '중소형', '우주항공', '방위산업',
            '디지털성장', '디지털전환', '스마트팩토리'
        ]
        for theme in korean_themes:
            if theme in combined_text:
                # Unless explicitly foreign
                foreign_indicators = ['미국', 'US', '중국', 'China', '일본', 'Japan', '글로벌', 'Global']
                if not any(foreign in combined_text for foreign in foreign_indicators):
                    return 'KR'

        # Korean-language index names (no English translation)
        korean_only_indicators = ['지수', '총수익', '주가지수']
        has_korean_only = any(indicator in combined_text for indicator in korean_only_indicators)
        has_foreign_keyword = any(foreign in combined_text for foreign in ['미국', 'US', '중국', '일본', 'Japan', 'China', '글로벌', 'Global'])

        if has_korean_only and not has_foreign_keyword:
            return 'KR'

        return None

    def process_all_etfs(self, dry_run: bool = False) -> Tuple[int, int]:
        """
        Process all ETFs and update inferred fields

        Args:
            dry_run: If True, simulate without actual updates

        Returns:
            (success_count, failed_count)
        """
        logger.info("=" * 80)
        logger.info("📊 ETF Field Inference Engine")
        logger.info("=" * 80)

        if dry_run:
            logger.info("🔍 DRY RUN MODE: Simulation only, no actual updates")

        # Fetch all ETFs
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                t.ticker, t.name,
                ed.fund_type, ed.tracking_index,
                ed.underlying_asset_class, ed.leverage_ratio,
                ed.currency_hedged, ed.sector_theme, ed.geographic_region
            FROM tickers t
            INNER JOIN etf_details ed ON t.ticker = ed.ticker
            WHERE t.asset_type = 'ETF' AND t.region = 'KR' AND t.is_active = 1
            ORDER BY t.ticker
        """)

        etfs = [dict(row) for row in cursor.fetchall()]
        conn.close()

        logger.info(f"📌 Processing {len(etfs)} ETFs for field inference")
        logger.info("")

        success_count = 0
        failed_count = 0

        # Statistics tracking
        stats = {
            'asset_class_inferred': 0,
            'leverage_inferred': 0,
            'currency_hedged_inferred': 0,
            'sector_theme_inferred': 0,
            'region_inferred': 0
        }

        for idx, etf in enumerate(etfs):
            ticker = etf['ticker']
            name = etf['name']

            try:
                updates = {}

                # Infer asset class (if NULL)
                if not etf['underlying_asset_class']:
                    asset_class = self.infer_asset_class(
                        etf['fund_type'],
                        etf['tracking_index'],
                        name
                    )
                    if asset_class:
                        updates['underlying_asset_class'] = asset_class
                        stats['asset_class_inferred'] += 1

                # Infer leverage ratio (if NULL)
                if not etf['leverage_ratio']:
                    leverage = self.infer_leverage_ratio(name)
                    updates['leverage_ratio'] = leverage
                    stats['leverage_inferred'] += 1

                # Infer currency hedged (if NULL)
                if etf['currency_hedged'] is None:
                    is_hedged = self.infer_currency_hedged(name, etf['tracking_index'])
                    updates['currency_hedged'] = is_hedged
                    stats['currency_hedged_inferred'] += 1

                # Infer sector theme (if NULL)
                if not etf['sector_theme']:
                    sector = self.infer_sector_theme(name, etf['tracking_index'], etf['fund_type'])
                    if sector:
                        updates['sector_theme'] = sector
                        stats['sector_theme_inferred'] += 1

                # Infer geographic region (if NULL)
                if not etf['geographic_region']:
                    region = self.infer_geographic_region(name, etf['tracking_index'], etf['fund_type'])
                    if region:
                        updates['geographic_region'] = region
                        stats['region_inferred'] += 1

                # Update database
                if updates and not dry_run:
                    self.db.update_etf_details(ticker, updates)

                # Logging (first 10, every 100, last 10)
                if success_count < 10 or success_count % 100 == 0 or idx >= len(etfs) - 10:
                    update_summary = ', '.join([f"{k}={v}" for k, v in updates.items() if v is not None])
                    logger.info(
                        f"  [{idx+1}/{len(etfs)}] ✅ [{ticker}] {name}: {update_summary if update_summary else 'No changes'}"
                        f"{' (DRY RUN)' if dry_run else ''}"
                    )
                elif success_count == 10:
                    logger.info(f"  ... (logging every 100 ETFs) ...")

                success_count += 1

            except Exception as e:
                logger.error(f"  [{idx+1}/{len(etfs)}] ❌ [{ticker}] {name}: {e}")
                failed_count += 1

        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 INFERENCE STATISTICS")
        logger.info("=" * 80)
        logger.info(f"Total Processed: {success_count}")
        logger.info(f"Failed: {failed_count}")
        logger.info("")
        logger.info(f"Asset Class Inferred: {stats['asset_class_inferred']}")
        logger.info(f"Leverage Ratio Inferred: {stats['leverage_inferred']}")
        logger.info(f"Currency Hedged Inferred: {stats['currency_hedged_inferred']}")
        logger.info(f"Sector Theme Inferred: {stats['sector_theme_inferred']}")
        logger.info(f"Geographic Region Inferred: {stats['region_inferred']}")
        logger.info("=" * 80)

        return (success_count, failed_count)


def main():
    """Main execution"""
    import argparse

    parser = argparse.ArgumentParser(description='ETF Field Inference Engine')
    parser.add_argument('--dry-run', action='store_true', help='Dry run without actual updates')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("🚀 ETF Field Inference Script")
    logger.info("=" * 80)
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'PRODUCTION'}")
    logger.info("=" * 80)

    # Initialize
    db = SQLiteDatabaseManager()
    engine = ETFFieldInferenceEngine(db=db)

    # Process all ETFs
    logger.info("")
    try:
        success, failed = engine.process_all_etfs(dry_run=args.dry_run)

        logger.info("")
        logger.info("=" * 80)
        logger.info(f"✅ Inference Complete: Success={success}, Failed={failed}")
        logger.info("=" * 80)

    except KeyboardInterrupt:
        logger.info("")
        logger.info("User interrupted - exiting gracefully")

    logger.info("")
    logger.info("=" * 80)
    logger.info("✅ ETF Field Inference Complete!")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()
