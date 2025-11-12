# 섹터 매핑 및 계산 로직 설계

**버전**: 1.0
**작성일**: 2025-01-12

---

## 📊 섹터 분류 체계

### 한국 시장 (10개 섹터)

```python
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
```

### 미국 시장 (11개 섹터) - GICS 기준

```python
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
```

---

## 🔧 섹터 계산 로직

### SQL 기반 계산 (한국 시장)

```sql
-- ============================================================================
-- 섹터 성과 계산 함수
-- ============================================================================

CREATE OR REPLACE FUNCTION calculate_kr_sector_performance(
    p_date DATE,
    p_sector_tickers TEXT[],
    p_region TEXT DEFAULT 'KR'
)
RETURNS TABLE (
    avg_return_1d DECIMAL(10,4),
    avg_return_1w DECIMAL(10,4),
    avg_return_1m DECIMAL(10,4),
    avg_return_3m DECIMAL(10,4),
    num_stocks INTEGER,
    strong_stocks INTEGER,
    weak_stocks INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH sector_prices AS (
        -- 각 ticker의 현재가 및 과거가 조회
        SELECT
            o.ticker,
            o.date,
            o.close as current_close,
            LAG(o.close, 1) OVER (PARTITION BY o.ticker ORDER BY o.date) as close_1d,
            LAG(o.close, 5) OVER (PARTITION BY o.ticker ORDER BY o.date) as close_1w,
            LAG(o.close, 21) OVER (PARTITION BY o.ticker ORDER BY o.date) as close_1m,
            LAG(o.close, 63) OVER (PARTITION BY o.ticker ORDER BY o.date) as close_3m
        FROM ohlcv_data o
        WHERE o.ticker = ANY(p_sector_tickers)
          AND o.region = p_region
          AND o.timeframe = '1d'
          AND o.date <= p_date
          AND o.date >= p_date - INTERVAL '90 days'
    ),
    sector_returns AS (
        -- 수익률 계산
        SELECT
            ticker,
            (current_close / NULLIF(close_1d, 0) - 1) * 100 as return_1d,
            (current_close / NULLIF(close_1w, 0) - 1) * 100 as return_1w,
            (current_close / NULLIF(close_1m, 0) - 1) * 100 as return_1m,
            (current_close / NULLIF(close_3m, 0) - 1) * 100 as return_3m
        FROM sector_prices
        WHERE date = p_date
          AND close_1d IS NOT NULL
          AND close_1w IS NOT NULL
          AND close_1m IS NOT NULL
          AND close_3m IS NOT NULL
    )
    SELECT
        AVG(return_1d)::DECIMAL(10,4) as avg_return_1d,
        AVG(return_1w)::DECIMAL(10,4) as avg_return_1w,
        AVG(return_1m)::DECIMAL(10,4) as avg_return_1m,
        AVG(return_3m)::DECIMAL(10,4) as avg_return_3m,
        COUNT(*)::INTEGER as num_stocks,
        COUNT(*) FILTER (WHERE return_1m > 0)::INTEGER as strong_stocks,
        COUNT(*) FILTER (WHERE return_1m <= 0)::INTEGER as weak_stocks
    FROM sector_returns;
END;
$$ LANGUAGE plpgsql;

-- 사용 예제
/*
SELECT * FROM calculate_kr_sector_performance(
    '2025-01-12',
    ARRAY['005930', '000660', '035420', '035720']  -- Technology 섹터
);
*/
```

### Python 계산 로직

```python
# modules/macro/sector_calculator.py

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from decimal import Decimal
import numpy as np

from modules.db_manager_postgres import PostgresDatabaseManager


class SectorPerformanceCalculator:
    """
    섹터 성과 계산기

    Features:
    - 기존 ohlcv_data 활용 (외부 수집 불필요)
    - SQL 함수 활용한 고성능 계산
    - 모멘텀 분류 및 rotation 감지
    """

    def __init__(self):
        self.db = PostgresDatabaseManager()

    async def calculate_daily_performance(
        self,
        region: str,
        date: str,
        sectors: Dict[str, Dict]
    ) -> Dict[str, Dict]:
        """
        일일 섹터 성과 계산

        Args:
            region: 'KR' or 'US'
            date: 계산 날짜 (YYYY-MM-DD)
            sectors: 섹터 정의 딕셔너리

        Returns:
            섹터별 성과 데이터
        """
        results = {}

        for sector_name, sector_info in sectors.items():
            tickers = sector_info["tickers"]

            # SQL 함수 호출
            query = """
            SELECT * FROM calculate_kr_sector_performance(
                :date::DATE,
                :tickers::TEXT[],
                :region
            );
            """

            sector_data = await self.db.fetch_one(
                query,
                {
                    "date": date,
                    "tickers": tickers,
                    "region": region
                }
            )

            if sector_data and sector_data["num_stocks"] > 0:
                # 모멘텀 분류
                momentum = self._classify_momentum(
                    sector_data["avg_return_1m"]
                )

                results[sector_name] = {
                    "avg_return_1d": float(sector_data["avg_return_1d"] or 0),
                    "avg_return_1w": float(sector_data["avg_return_1w"] or 0),
                    "avg_return_1m": float(sector_data["avg_return_1m"] or 0),
                    "avg_return_3m": float(sector_data["avg_return_3m"] or 0),
                    "num_stocks": sector_data["num_stocks"],
                    "strong_stocks": sector_data["strong_stocks"],
                    "weak_stocks": sector_data["weak_stocks"],
                    "momentum": momentum
                }
            else:
                # 데이터 없는 경우
                results[sector_name] = None

        return results

    def _classify_momentum(self, return_1m: float) -> str:
        """
        모멘텀 분류

        Criteria:
        - strong: return >= 10%
        - moderate: 3% <= return < 10%
        - weak: 0% <= return < 3%
        - negative: return < 0%
        """
        if return_1m is None:
            return "unknown"
        elif return_1m >= 10:
            return "strong"
        elif return_1m >= 3:
            return "moderate"
        elif return_1m >= 0:
            return "weak"
        else:
            return "negative"

    async def identify_rotation(
        self,
        sector_perf: Dict[str, Dict]
    ) -> Dict:
        """
        섹터 rotation 패턴 식별

        Returns:
            {
                "rotation_type": "growth_to_value",
                "leaders": ["Technology", "Battery"],
                "laggards": ["Utilities", "Construction"],
                "intensity": 0.75,
                "interpretation": "Strong rotation into growth sectors"
            }
        """
        # None 값 필터링
        valid_sectors = {
            name: data for name, data in sector_perf.items()
            if data is not None and data["avg_return_1m"] is not None
        }

        if len(valid_sectors) < 3:
            return {
                "rotation_type": "insufficient_data",
                "leaders": [],
                "laggards": [],
                "intensity": 0,
                "interpretation": "Insufficient sector data"
            }

        # 성과 순위 정렬
        ranked = sorted(
            valid_sectors.items(),
            key=lambda x: x[1]["avg_return_1m"],
            reverse=True
        )

        leaders = [s[0] for s in ranked[:3]]
        laggards = [s[0] for s in ranked[-3:]]

        # Rotation 강도 계산 (표준편차 기반)
        returns = [s[1]["avg_return_1m"] for s in ranked]
        intensity = min(float(np.std(returns)) / 10.0, 1.0)

        # Rotation 타입 분류
        rotation_type = self._classify_rotation_type(leaders, laggards)
        interpretation = self._generate_interpretation(
            rotation_type, leaders, laggards, intensity
        )

        return {
            "rotation_type": rotation_type,
            "leaders": leaders,
            "laggards": laggards,
            "intensity": intensity,
            "interpretation": interpretation
        }

    def _classify_rotation_type(
        self,
        leaders: List[str],
        laggards: List[str]
    ) -> str:
        """
        Rotation 타입 분류

        Types:
        - growth_to_value: 성장주 → 가치주
        - value_to_growth: 가치주 → 성장주
        - cyclical_to_defensive: 경기민감주 → 방어주
        - defensive_to_cyclical: 방어주 → 경기민감주
        - sector_specific: 특정 섹터 rotation
        """
        # 성장주 섹터
        growth_sectors = {"Technology", "Battery", "Healthcare"}
        # 가치주 섹터
        value_sectors = {"Financials", "Steel", "Utilities"}
        # 경기민감주
        cyclical_sectors = {"Automobiles", "Steel", "Construction"}
        # 방어주
        defensive_sectors = {"Utilities", "Healthcare", "Consumer Staples"}

        leaders_set = set(leaders)
        laggards_set = set(laggards)

        # 성장주 vs 가치주
        if leaders_set & growth_sectors and laggards_set & value_sectors:
            return "value_to_growth"
        elif leaders_set & value_sectors and laggards_set & growth_sectors:
            return "growth_to_value"

        # 경기민감주 vs 방어주
        if leaders_set & cyclical_sectors and laggards_set & defensive_sectors:
            return "defensive_to_cyclical"
        elif leaders_set & defensive_sectors and laggards_set & cyclical_sectors:
            return "cyclical_to_defensive"

        return "sector_specific"

    def _generate_interpretation(
        self,
        rotation_type: str,
        leaders: List[str],
        laggards: List[str],
        intensity: float
    ) -> str:
        """Rotation 해석 생성"""
        intensity_desc = (
            "Strong" if intensity > 0.7
            else "Moderate" if intensity > 0.4
            else "Mild"
        )

        interpretations = {
            "value_to_growth": f"{intensity_desc} rotation from value to growth sectors",
            "growth_to_value": f"{intensity_desc} rotation from growth to value sectors",
            "defensive_to_cyclical": f"{intensity_desc} rotation into cyclical sectors (risk-on)",
            "cyclical_to_defensive": f"{intensity_desc} rotation into defensive sectors (risk-off)",
            "sector_specific": f"{intensity_desc} sector-specific rotation"
        }

        base_msg = interpretations.get(rotation_type, "Sector rotation detected")
        return f"{base_msg}. Leaders: {', '.join(leaders)}. Laggards: {', '.join(laggards)}."

    async def save_to_db(
        self,
        region: str,
        date: str,
        sector_data: Dict[str, Dict]
    ) -> int:
        """
        섹터 성과를 sector_performance 테이블에 저장

        Returns:
            저장된 레코드 수
        """
        saved_count = 0

        for sector_name, data in sector_data.items():
            if data is None:
                continue

            query = """
            INSERT INTO sector_performance (
                region, sector, date,
                avg_return_1d, avg_return_1w, avg_return_1m, avg_return_3m,
                num_stocks, strong_stocks, weak_stocks, momentum
            )
            VALUES (
                :region, :sector, :date,
                :return_1d, :return_1w, :return_1m, :return_3m,
                :num_stocks, :strong_stocks, :weak_stocks, :momentum
            )
            ON CONFLICT (region, sector, date)
            DO UPDATE SET
                avg_return_1d = EXCLUDED.avg_return_1d,
                avg_return_1w = EXCLUDED.avg_return_1w,
                avg_return_1m = EXCLUDED.avg_return_1m,
                avg_return_3m = EXCLUDED.avg_return_3m,
                num_stocks = EXCLUDED.num_stocks,
                strong_stocks = EXCLUDED.strong_stocks,
                weak_stocks = EXCLUDED.weak_stocks,
                momentum = EXCLUDED.momentum;
            """

            await self.db.execute(
                query,
                {
                    "region": region,
                    "sector": sector_name,
                    "date": date,
                    "return_1d": data["avg_return_1d"],
                    "return_1w": data["avg_return_1w"],
                    "return_1m": data["avg_return_1m"],
                    "return_3m": data["avg_return_3m"],
                    "num_stocks": data["num_stocks"],
                    "strong_stocks": data["strong_stocks"],
                    "weak_stocks": data["weak_stocks"],
                    "momentum": data["momentum"]
                }
            )

            saved_count += 1

        return saved_count
```

---

## 📝 사용 예제

### 일일 계산 실행

```python
# scripts/calculate_sector_performance.py

import asyncio
from datetime import date
from modules.macro.sector_calculator import SectorPerformanceCalculator
from modules.macro.sector_definitions import KR_SECTORS, US_SECTORS


async def main():
    calculator = SectorPerformanceCalculator()
    today = date.today().isoformat()

    # 한국 섹터 계산
    kr_results = await calculator.calculate_daily_performance(
        region="KR",
        date=today,
        sectors=KR_SECTORS
    )

    # 결과 출력
    print(f"\n📊 한국 섹터 성과 ({today})")
    print("=" * 60)
    for sector, data in kr_results.items():
        if data:
            print(f"{sector:20} | 1M: {data['avg_return_1m']:>6.2f}% | {data['momentum']:>10}")

    # Rotation 분석
    rotation = await calculator.identify_rotation(kr_results)
    print(f"\n🔄 Rotation Analysis")
    print(f"Type: {rotation['rotation_type']}")
    print(f"Intensity: {rotation['intensity']:.2f}")
    print(f"Interpretation: {rotation['interpretation']}")

    # DB 저장
    saved = await calculator.save_to_db("KR", today, kr_results)
    print(f"\n✅ Saved {saved} sector records to database")


if __name__ == "__main__":
    asyncio.run(main())
```

### 예상 출력

```
📊 한국 섹터 성과 (2025-01-12)
============================================================
Technology           | 1M:   8.45% |     strong
Battery              | 1M:   6.23% |   moderate
Automobiles          | 1M:   4.12% |   moderate
Healthcare           | 1M:   2.34% |       weak
Financials           | 1M:   1.23% |       weak
Chemicals            | 1M:  -0.45% |   negative
Retail               | 1M:  -1.23% |   negative
Steel                | 1M:  -2.34% |   negative
Construction         | 1M:  -3.45% |   negative
Utilities            | 1M:  -0.78% |   negative

🔄 Rotation Analysis
Type: defensive_to_cyclical
Intensity: 0.78
Interpretation: Strong rotation into cyclical sectors (risk-on). Leaders: Technology, Battery, Automobiles. Laggards: Construction, Steel, Utilities.

✅ Saved 10 sector records to database
```

---

**문서 버전**: 1.0
**최종 수정**: 2025-01-12
