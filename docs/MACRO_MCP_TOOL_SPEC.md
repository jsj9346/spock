# 매크로 분석 MCP Tool 사양서

**버전**: 1.0
**작성일**: 2025-01-12

---

## 📋 Tool 개요

### Tool 정보
- **이름**: `analyze_macro_environment`
- **목적**: 글로벌 매크로 경제 환경 종합 분석
- **응답 크기**: ~5-10KB (효율적)
- **응답 시간**: <2초

### 분석 구성요소
1. **환율** (exchange_rates + fx_valuation_signals)
2. **글로벌 지수** (global_market_indices)
3. **채권** (bond_yields)
4. **원자재** (commodities)
5. **섹터** (sector_performance)
6. **시장 regime** (통합 분석)

---

## 🔧 Tool 정의

### Input Schema

```python
{
    "type": "object",
    "properties": {
        "analysis_date": {
            "type": "string",
            "description": "Analysis date in YYYY-MM-DD format (default: latest available)",
            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
        },
        "lookback_days": {
            "type": "number",
            "description": "Number of days to analyze for trends (default: 30)",
            "minimum": 1,
            "maximum": 365,
            "default": 30
        },
        "components": {
            "type": "array",
            "description": "Macro components to include in analysis",
            "items": {
                "type": "string",
                "enum": ["currencies", "indices", "bonds", "commodities", "sectors", "all"]
            },
            "default": ["all"]
        },
        "regions": {
            "type": "array",
            "description": "Geographic regions to analyze",
            "items": {
                "type": "string",
                "enum": ["KR", "US", "EU", "JP", "CN", "HK", "global"]
            },
            "default": ["KR", "US"]
        },
        "include_ai_summary": {
            "type": "boolean",
            "description": "Generate AI-powered market regime summary",
            "default": true
        }
    },
    "required": []
}
```

### Output Structure

```json
{
    "analysis_date": "2025-01-12",
    "lookback_period": 30,
    "data_quality": "GOOD",

    "currencies": {
        "USDKRW": {
            "current": 1345.50,
            "change_1d": 0.45,
            "change_1w": -1.23,
            "change_1m": 2.34,
            "trend_score": 15.5,
            "attractiveness_score": 65.2,
            "trend": "weakening_krw",
            "volatility": "moderate"
        },
        "summary": "USD strengthening across majors, KRW under pressure"
    },

    "indices": {
        "^GSPC": {
            "name": "S&P 500",
            "region": "US",
            "current": 4785.23,
            "change_1d": 0.87,
            "change_1w": 2.34,
            "change_1m": 5.23,
            "trend_5d": "up",
            "volatility": 12.34
        },
        "^KS11": {
            "name": "KOSPI",
            "region": "KR",
            "current": 2650.45,
            "change_1d": 0.65,
            "change_1m": 3.45,
            "trend_5d": "up"
        },
        "correlation_matrix": {
            "^GSPC_^KS11": 0.68,
            "^GSPC_^N225": 0.72
        },
        "summary": "US indices outperforming, positive correlation with Asia"
    },

    "bonds": {
        "US10Y": {
            "current_yield": 4.25,
            "change_1d_bps": -5,
            "change_1m_bps": 25,
            "trend": "rising"
        },
        "yield_curve": {
            "US_10Y_2Y_spread": 0.35,
            "interpretation": "steepening_curve",
            "signal": "growth_expectations"
        },
        "summary": "Yields rising on growth optimism, curve steepening"
    },

    "commodities": {
        "GC=F": {
            "name": "Gold",
            "current": 2042.50,
            "change_1m": -2.34,
            "trend": "consolidating",
            "category": "Metals"
        },
        "CL=F": {
            "name": "Crude Oil WTI",
            "current": 72.45,
            "change_1m": 8.23,
            "trend": "bullish",
            "category": "Energy"
        },
        "summary": "Energy rally, metals consolidating"
    },

    "sectors": {
        "KR": {
            "strongest": [
                {"sector": "Technology", "return_1m": 8.45, "momentum": "strong"},
                {"sector": "Battery", "return_1m": 6.23, "momentum": "moderate"}
            ],
            "weakest": [
                {"sector": "Construction", "return_1m": -3.45, "momentum": "negative"}
            ],
            "rotation": {
                "type": "defensive_to_cyclical",
                "intensity": 0.78,
                "interpretation": "Strong rotation into growth sectors"
            }
        },
        "US": {
            "strongest": [
                {"sector": "Information Technology", "return_1m": 7.89}
            ],
            "weakest": [
                {"sector": "Utilities", "return_1m": -1.23}
            ]
        }
    },

    "market_regime": {
        "current_regime": "Risk-On with Rotation",
        "confidence": 85,
        "risk_on_score": 72,
        "key_drivers": [
            "Strong US economic data",
            "Tech sector leadership in KR and US",
            "Rising yields on growth expectations"
        ],
        "risks": [
            "Elevated valuations in tech",
            "KRW weakness pressure"
        ]
    },

    "ai_summary": "Markets in risk-on mode driven by strong US data and tech sector leadership. Technology leading with semiconductor strength in both US and Korea. Rising yields reflect growth optimism but could pressure valuations. KRW weakness warrants monitoring for Korean exporters. Sector rotation favoring growth over defensives. Recommended positioning: Overweight Technology/Battery, Underweight Defensives.",

    "recommendations": {
        "asset_allocation": {
            "equities": "overweight",
            "bonds": "neutral",
            "commodities": "selective_overweight"
        },
        "sector_rotation": {
            "favor": ["Technology", "Battery", "Healthcare"],
            "avoid": ["Utilities", "Construction"]
        },
        "risk_level": "moderate_high",
        "hedges": ["Monitor USD/KRW for export exposure"]
    }
}
```

---

## 🏗️ 구현 구조

### MacroAdapter (mcp_server/adapters/macro_adapter.py)

```python
class MacroAdapter:
    """매크로 환경 분석 어댑터"""

    def __init__(self):
        self.db = PostgresDatabaseManager()

    async def analyze_macro_environment(
        self,
        analysis_date: Optional[str] = None,
        lookback_days: int = 30,
        components: List[str] = ["all"],
        regions: List[str] = ["KR", "US"],
        include_ai_summary: bool = True
    ) -> dict:
        """
        통합 매크로 분석

        Args:
            analysis_date: 분석 날짜 (None = 최신)
            lookback_days: 추세 분석 기간
            components: 분석 구성요소
            regions: 분석 지역
            include_ai_summary: AI 요약 생성 여부

        Returns:
            매크로 분석 결과
        """
        # 날짜 정규화
        if not analysis_date:
            analysis_date = await self._get_latest_date()

        start_date = (
            datetime.strptime(analysis_date, "%Y-%m-%d") -
            timedelta(days=lookback_days)
        ).strftime("%Y-%m-%d")

        result = {
            "analysis_date": analysis_date,
            "lookback_period": lookback_days,
            "data_quality": "GOOD"
        }

        # 구성요소별 분석
        if "currencies" in components or "all" in components:
            result["currencies"] = await self._get_currencies(
                analysis_date, start_date
            )

        if "indices" in components or "all" in components:
            result["indices"] = await self._get_indices(
                analysis_date, start_date, regions
            )

        if "bonds" in components or "all" in components:
            result["bonds"] = await self._get_bonds(
                analysis_date, start_date
            )

        if "commodities" in components or "all" in components:
            result["commodities"] = await self._get_commodities(
                analysis_date, start_date
            )

        if "sectors" in components or "all" in components:
            result["sectors"] = await self._get_sectors(
                analysis_date, regions
            )

        # 시장 regime 분석
        result["market_regime"] = await self._analyze_regime(
            analysis_date, result
        )

        # AI 요약 (선택)
        if include_ai_summary:
            result["ai_summary"] = self._generate_summary(result)
            result["recommendations"] = self._generate_recommendations(result)

        return result

    async def _get_currencies(
        self,
        analysis_date: str,
        start_date: str
    ) -> dict:
        """
        환율 분석 (기존 테이블 활용)

        데이터 소스:
        - fx_valuation_signals: 밸류에이션 지표 (우선)
        - exchange_rates: 기본 환율
        """
        query = """
        SELECT
            currency,
            region,
            usd_rate as current,
            return_1m as change_1m,
            trend_score,
            attractiveness_score,
            volatility
        FROM fx_valuation_signals
        WHERE date = :analysis_date
        ORDER BY attractiveness_score DESC NULLS LAST;
        """

        currencies = await self.db.fetch_all(
            query,
            {"analysis_date": analysis_date}
        )

        result = {}
        for curr in currencies:
            result[curr["currency"]] = {
                "current": float(curr["current"]),
                "change_1m": float(curr["change_1m"] or 0),
                "trend_score": float(curr["trend_score"] or 0),
                "attractiveness_score": float(curr["attractiveness_score"] or 0),
                "volatility": float(curr["volatility"] or 0),
                "trend": self._classify_fx_trend(curr["trend_score"])
            }

        result["summary"] = self._summarize_fx(result)
        return result

    async def _get_indices(
        self,
        analysis_date: str,
        start_date: str,
        regions: List[str]
    ) -> dict:
        """
        글로벌 지수 분석 (기존 global_market_indices)
        """
        query = """
        WITH latest_data AS (
            SELECT
                symbol,
                index_name,
                region,
                close_price as current,
                change_percent as change_1d,
                trend_5d
            FROM global_market_indices
            WHERE date = :analysis_date
              AND (region = ANY(:regions) OR 'global' = ANY(:regions))
        ),
        historical_data AS (
            SELECT
                symbol,
                FIRST_VALUE(close_price) OVER (
                    PARTITION BY symbol ORDER BY date DESC
                ) / FIRST_VALUE(close_price) OVER (
                    PARTITION BY symbol ORDER BY date ASC
                ) - 1 as change_period
            FROM global_market_indices
            WHERE date >= :start_date AND date <= :analysis_date
        )
        SELECT
            l.symbol,
            l.index_name,
            l.region,
            l.current,
            l.change_1d,
            l.trend_5d,
            h.change_period * 100 as change_period
        FROM latest_data l
        LEFT JOIN historical_data h ON l.symbol = h.symbol;
        """

        indices = await self.db.fetch_all(
            query,
            {
                "analysis_date": analysis_date,
                "start_date": start_date,
                "regions": regions
            }
        )

        result = {}
        for idx in indices:
            result[idx["symbol"]] = {
                "name": idx["index_name"],
                "region": idx["region"],
                "current": float(idx["current"]),
                "change_1d": float(idx["change_1d"] or 0),
                "change_period": float(idx["change_period"] or 0),
                "trend_5d": idx["trend_5d"]
            }

        result["summary"] = self._summarize_indices(result)
        return result

    async def _get_sectors(
        self,
        analysis_date: str,
        regions: List[str]
    ) -> dict:
        """
        섹터 성과 분석 (sector_performance)
        """
        query = """
        SELECT
            region,
            sector,
            avg_return_1m,
            momentum,
            num_stocks,
            strong_stocks,
            weak_stocks
        FROM sector_performance
        WHERE date = :analysis_date
          AND region = ANY(:regions)
        ORDER BY region, avg_return_1m DESC;
        """

        sectors = await self.db.fetch_all(
            query,
            {
                "analysis_date": analysis_date,
                "regions": regions
            }
        )

        result = {}
        for region in regions:
            region_sectors = [s for s in sectors if s["region"] == region]

            if region_sectors:
                result[region] = {
                    "strongest": [
                        {
                            "sector": s["sector"],
                            "return_1m": float(s["avg_return_1m"]),
                            "momentum": s["momentum"]
                        }
                        for s in region_sectors[:3]  # Top 3
                    ],
                    "weakest": [
                        {
                            "sector": s["sector"],
                            "return_1m": float(s["avg_return_1m"]),
                            "momentum": s["momentum"]
                        }
                        for s in region_sectors[-3:]  # Bottom 3
                    ]
                }

        return result

    async def _analyze_regime(
        self,
        analysis_date: str,
        macro_data: dict
    ) -> dict:
        """
        시장 regime 분석

        Inputs:
        - 지수 수익률 (risk-on/off)
        - 환율 추세 (USD strength)
        - 원자재 (금 = safe haven)
        - 섹터 rotation

        Output:
        - regime: Risk-On/Risk-Off/Rotation/Defensive
        - confidence: 0-100
        """
        # Risk score 계산
        risk_score = 0
        confidence = 0

        # 1. 지수 수익률 (40점)
        if "indices" in macro_data:
            us_indices_positive = sum(
                1 for idx in macro_data["indices"].values()
                if isinstance(idx, dict) and idx.get("change_period", 0) > 0
            )
            risk_score += min(us_indices_positive * 10, 40)

        # 2. 환율 (20점) - USD 약세 = risk-on
        if "currencies" in macro_data:
            usd_weak = macro_data["currencies"].get("USD", {}).get("trend_score", 0) < 0
            if usd_weak:
                risk_score += 20

        # 3. 원자재 (20점) - 금 약세 = risk-on
        if "commodities" in macro_data:
            gold_weak = macro_data["commodities"].get("GC=F", {}).get("change_1m", 0) < 0
            if gold_weak:
                risk_score += 20

        # 4. 섹터 rotation (20점)
        if "sectors" in macro_data:
            growth_leading = any(
                s["sector"] in ["Technology", "Battery", "Healthcare"]
                for region in macro_data["sectors"].values()
                for s in region.get("strongest", [])
            )
            if growth_leading:
                risk_score += 20

        # Regime 분류
        if risk_score >= 70:
            regime = "Risk-On"
            confidence = 85 + (risk_score - 70) / 3
        elif risk_score <= 30:
            regime = "Risk-Off"
            confidence = 85 + (30 - risk_score) / 3
        elif 40 <= risk_score <= 60:
            regime = "Rotation"
            confidence = 70
        else:
            regime = "Mixed"
            confidence = 60

        return {
            "current_regime": regime,
            "confidence": int(confidence),
            "risk_on_score": risk_score,
            "key_drivers": self._identify_drivers(macro_data),
            "risks": self._identify_risks(macro_data)
        }

    def _generate_summary(self, result: dict) -> str:
        """AI 요약 생성 (규칙 기반)"""
        regime = result["market_regime"]["current_regime"]
        risk_score = result["market_regime"]["risk_on_score"]

        # 템플릿 기반 요약
        summary = f"Markets in {regime.lower()} mode "

        # 주요 동인
        drivers = result["market_regime"]["key_drivers"]
        if drivers:
            summary += f"driven by {', '.join(drivers[:2]).lower()}. "

        # 섹터 분석
        if "sectors" in result:
            kr_sectors = result["sectors"].get("KR", {})
            if kr_sectors and kr_sectors.get("strongest"):
                top_sector = kr_sectors["strongest"][0]["sector"]
                summary += f"{top_sector} leading with strong momentum. "

        # 리스크
        risks = result["market_regime"]["risks"]
        if risks:
            summary += f"Key risks: {', '.join(risks[:2]).lower()}."

        return summary
```

---

## 📝 사용 예제

### Claude Desktop에서

```
사용자: "현재 글로벌 시장 상황을 매크로 관점에서 분석해줘"

Claude: [analyze_macro_environment 호출]
{
  "components": ["all"],
  "regions": ["KR", "US"],
  "lookback_days": 30
}

응답: (위 Output Structure 참조)

해석:
현재 시장은 Risk-On 국면입니다 (신뢰도 85%).
S&P 500이 최근 1개월간 5.2% 상승하며 강세를 보이고 있으며,
한국에서는 Technology와 Battery 섹터가 각각 8.5%, 6.2% 상승하며
강세 rotation을 보이고 있습니다.

USD/KRW는 1,345원으로 원화 약세가 진행 중이며,
이는 수출주에 긍정적입니다. 채권 수익률 상승은 성장 기대감을
반영하지만 밸류에이션 부담 요인입니다.

추천 포지셔닝: Technology, Battery 비중 확대, Utilities 축소
```

---

## 🎯 다음 단계

1. **Phase 0**: 환율 백필 및 기존 데이터 정상화
2. **Phase 1**: 신규 테이블 생성
3. **Phase 2**: 섹터 계산기 구현
4. **Phase 3**: 데이터 수집 확장
5. **Phase 4**: MCP Tool 구현 (이 문서 기반)

---

**문서 버전**: 1.0
**최종 수정**: 2025-01-12
