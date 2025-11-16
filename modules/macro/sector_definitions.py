# modules/macro/sector_definitions.py
"""
Sector Definitions for KR and US Markets

Purpose:
- Centralized sector-ticker mappings
- Used by SectorPerformanceCalculator

Data Sources:
- KR: KOSPI major components by sector
- US: GICS sector classification

Last Updated: 2025-11-12
"""

# ============================================================================
# Korean Market Sectors (10 sectors)
# ============================================================================

KR_SECTORS = {
    "Technology": {
        "tickers": [
            "005930",  # 삼성전자
            "000660",  # SK하이닉스
            "035420",  # NAVER
            "035720",  # 카카오
            "000270",  # 기아 (전장부품)
        ],
        "description": "반도체, 전자, IT 서비스",
        "market_cap_weight": 0.35  # KOSPI 시가총액 비중
    },

    "Battery": {
        "tickers": [
            "373220",  # LG에너지솔루션
            "066970",  # 에코프로비엠
            "247540",  # 에코프로
            "086520",  # 에코프로에이치엔
            "051910",  # LG화학 (배터리 소재)
        ],
        "description": "2차전지, 배터리 소재",
        "market_cap_weight": 0.08
    },

    "Automobiles": {
        "tickers": [
            "005380",  # 현대차
            "000270",  # 기아
            "012330",  # 현대모비스
        ],
        "description": "완성차, 자동차 부품",
        "market_cap_weight": 0.10
    },

    "Financials": {
        "tickers": [
            "055550",  # 신한지주
            "105560",  # KB금융
            "086790",  # 하나금융지주
            "138930",  # BNK금융지주
            "316140",  # 우리금융지주
        ],
        "description": "은행, 증권, 보험",
        "market_cap_weight": 0.12
    },

    "Healthcare": {
        "tickers": [
            "207940",  # 삼성바이오로직스
            "068270",  # 셀트리온
            "326030",  # SK바이오팜
            "302440",  # SK바이오사이언스
            "028300",  # HLB
        ],
        "description": "바이오, 제약",
        "market_cap_weight": 0.08
    },

    "Steel": {
        "tickers": [
            "005490",  # POSCO홀딩스
            "004020",  # 현대제철
        ],
        "description": "철강",
        "market_cap_weight": 0.04
    },

    "Chemicals": {
        "tickers": [
            "051910",  # LG화학
            "009830",  # 한화솔루션
            "096770",  # SK이노베이션
        ],
        "description": "화학, 정유",
        "market_cap_weight": 0.06
    },

    "Retail": {
        "tickers": [
            "051900",  # LG생활건강
            "069960",  # 현대백화점
            "006400",  # 삼성SDI (일부)
        ],
        "description": "유통, 화장품",
        "market_cap_weight": 0.05
    },

    "Construction": {
        "tickers": [
            "000720",  # 현대건설
            "028260",  # 삼성물산
            "042660",  # 한화오션
        ],
        "description": "건설, 조선",
        "market_cap_weight": 0.04
    },

    "Utilities": {
        "tickers": [
            "015760",  # 한국전력
        ],
        "description": "전력, 가스",
        "market_cap_weight": 0.02
    }
}


# ============================================================================
# US Market Sectors (11 sectors) - GICS Classification
# ============================================================================

US_SECTORS = {
    "Information Technology": {
        "gics_code": 45,
        "representative_etf": "XLK",  # Technology Select Sector SPDR ETF
        "description": "Software, Hardware, Semiconductors",
        "sp500_weight": 0.28
    },

    "Healthcare": {
        "gics_code": 35,
        "representative_etf": "XLV",
        "description": "Pharmaceuticals, Biotech, Medical Devices",
        "sp500_weight": 0.14
    },

    "Financials": {
        "gics_code": 40,
        "representative_etf": "XLF",
        "description": "Banks, Insurance, Investment Services",
        "sp500_weight": 0.13
    },

    "Communication Services": {
        "gics_code": 50,
        "representative_etf": "XLC",
        "description": "Telecom, Media, Entertainment",
        "sp500_weight": 0.09
    },

    "Consumer Discretionary": {
        "gics_code": 25,
        "representative_etf": "XLY",
        "description": "Retail, Automotive, Leisure",
        "sp500_weight": 0.11
    },

    "Consumer Staples": {
        "gics_code": 30,
        "representative_etf": "XLP",
        "description": "Food, Beverages, Household Products",
        "sp500_weight": 0.07
    },

    "Industrials": {
        "gics_code": 20,
        "representative_etf": "XLI",
        "description": "Aerospace, Machinery, Transportation",
        "sp500_weight": 0.09
    },

    "Energy": {
        "gics_code": 10,
        "representative_etf": "XLE",
        "description": "Oil & Gas, Energy Equipment",
        "sp500_weight": 0.04
    },

    "Materials": {
        "gics_code": 15,
        "representative_etf": "XLB",
        "description": "Chemicals, Metals, Mining",
        "sp500_weight": 0.03
    },

    "Real Estate": {
        "gics_code": 60,
        "representative_etf": "XLRE",
        "description": "REITs, Real Estate Management",
        "sp500_weight": 0.03
    },

    "Utilities": {
        "gics_code": 55,
        "representative_etf": "XLU",
        "description": "Electric, Gas, Water Utilities",
        "sp500_weight": 0.03
    }
}


# ============================================================================
# Sector Utilities
# ============================================================================

def get_all_kr_tickers():
    """Get all KR tickers from all sectors"""
    all_tickers = set()
    for sector_data in KR_SECTORS.values():
        all_tickers.update(sector_data["tickers"])
    return sorted(list(all_tickers))


def get_sector_for_kr_ticker(ticker: str) -> str:
    """Get sector name for a KR ticker"""
    for sector_name, sector_data in KR_SECTORS.items():
        if ticker in sector_data["tickers"]:
            return sector_name
    return "Unknown"


def get_us_sector_etfs():
    """Get all US sector representative ETFs"""
    return {
        sector: data["representative_etf"]
        for sector, data in US_SECTORS.items()
    }
