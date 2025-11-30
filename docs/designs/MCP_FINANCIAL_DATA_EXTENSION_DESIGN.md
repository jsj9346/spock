# MCP 재무 데이터 확장 설계서

**버전**: 1.0.0
**작성일**: 2025-11-27
**상태**: 설계 완료, 구현 대기

---

## 목차

1. [개요](#1-개요)
2. [Phase 1: 재무 데이터 조회 MCP 도구](#2-phase-1-재무-데이터-조회-mcp-도구)
3. [Phase 2: 재무비율 계산기 MCP 도구](#3-phase-2-재무비율-계산기-mcp-도구)
4. [Phase 3: 배당 히스토리 테이블 및 MCP 도구](#4-phase-3-배당-히스토리-테이블-및-mcp-도구)
5. [Phase 4: 현금성자산 컬럼 및 현금비율](#5-phase-4-현금성자산-컬럼-및-현금비율)
6. [통합 아키텍처](#6-통합-아키텍처)
7. [구현 일정](#7-구현-일정)

---

## 1. 개요

### 1.1 배경

현재 Spock MCP 서버는 OHLCV, CAGR, 기술적 지표, 스크리닝 기능을 제공하지만,
`ticker_fundamentals` 테이블에 이미 존재하는 풍부한 재무 데이터가 MCP 도구로 노출되지 않은 상태입니다.

### 1.2 데이터 현황 분석

| 항목 | DB 컬럼 | 데이터 현황 | 상태 |
|------|---------|-------------|------|
| 유동자산 | `current_assets` | 20,704건 (5,966 종목) | ✅ 존재 |
| 유동부채 | `current_liabilities` | 20,684건 (5,957 종목) | ✅ 존재 |
| 매출채권 | `accounts_receivable` | 16,744건 (5,196 종목) | ✅ 존재 |
| 재고자산 | `inventory` | 13,030건 (4,310 종목) | ✅ 존재 |
| 총부채 | `total_liabilities` | 22,555건 (6,388 종목) | ✅ 존재 |
| 매출원가 | `cogs` | 14,729건 (4,697 종목) | ✅ 존재 |
| 판관비 | `sga_expense` | 21,746건 (6,124 종목) | ✅ 존재 |
| 이자비용 | `interest_expense` | 2,579건 (1,936 종목) | ✅ 존재 |
| 영업CF | `operating_cash_flow` | 23,231건 (5,016 종목) | ✅ 존재 |
| 투자CF | `investing_cf` | 24,995건 (6,825 종목) | ✅ 존재 |
| 재무CF | `financing_cf` | 25,680건 (6,947 종목) | ✅ 존재 |
| 배당금 | `dividend_per_share` | 160,637건 (12,875 종목) | ✅ 존재 |
| 배당수익률 | `dividend_yield` | 154,050건 (10,995 종목) | ✅ 존재 |
| 현금성자산 | - | ❌ 미존재 | 신규 추가 필요 |

### 1.3 설계 목표

1. **Phase 1**: 기존 재무 데이터를 MCP 도구로 노출 (1-2일)
2. **Phase 2**: 재무비율 계산 로직 추가 (2-3일)
3. **Phase 3**: 배당 히스토리 전용 테이블 및 도구 (3-4일)
4. **Phase 4**: 현금성자산 컬럼 추가 및 현금비율 계산 (2-3일)

---

## 2. Phase 1: 재무 데이터 조회 MCP 도구

### 2.1 도구 정의

**도구명**: `query_fundamentals`

```python
Tool(
    name="query_fundamentals",
    description=(
        "Get fundamental financial data for stocks including balance sheet, "
        "income statement, and cash flow statement items. "
        "Supports KR, US, JP, HK, CN, VN markets."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "tickers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of ticker symbols (max 50)",
                "minItems": 1,
                "maxItems": 50
            },
            "categories": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["balance_sheet", "income_statement", "cash_flow", "valuation", "all"]
                },
                "description": "Financial statement categories to retrieve",
                "default": ["all"]
            },
            "period_type": {
                "type": "string",
                "enum": ["ANNUAL", "QUARTERLY", "TTM"],
                "description": "Reporting period type",
                "default": "ANNUAL"
            },
            "periods": {
                "type": "integer",
                "description": "Number of periods to retrieve (1-10)",
                "minimum": 1,
                "maximum": 10,
                "default": 1
            },
            "region": {
                "type": "string",
                "enum": ["KR", "US", "JP", "HK", "CN", "VN"],
                "default": "KR"
            }
        },
        "required": ["tickers"]
    }
)
```

### 2.2 카테고리별 필드 매핑

```python
FUNDAMENTALS_FIELDS = {
    "balance_sheet": {
        # 자산
        "total_assets": {"name": "Total Assets", "korean": "총자산"},
        "current_assets": {"name": "Current Assets", "korean": "유동자산"},
        "accounts_receivable": {"name": "Accounts Receivable", "korean": "매출채권"},
        "inventory": {"name": "Inventory", "korean": "재고자산"},
        "pp_e": {"name": "PP&E", "korean": "유형자산"},
        # 부채
        "total_liabilities": {"name": "Total Liabilities", "korean": "총부채"},
        "current_liabilities": {"name": "Current Liabilities", "korean": "유동부채"},
        # 자본
        "total_equity": {"name": "Total Equity", "korean": "총자본"},
        "retained_earnings": {"name": "Retained Earnings", "korean": "이익잉여금"},
        "capital_stock": {"name": "Capital Stock", "korean": "자본금"},
    },
    "income_statement": {
        "revenue": {"name": "Revenue", "korean": "매출액"},
        "cogs": {"name": "Cost of Goods Sold", "korean": "매출원가"},
        "gross_profit": {"name": "Gross Profit", "korean": "매출총이익"},
        "sga_expense": {"name": "SG&A Expense", "korean": "판관비"},
        "rd_expense": {"name": "R&D Expense", "korean": "연구개발비"},
        "operating_profit": {"name": "Operating Profit", "korean": "영업이익"},
        "interest_expense": {"name": "Interest Expense", "korean": "이자비용"},
        "interest_income": {"name": "Interest Income", "korean": "이자수익"},
        "net_income": {"name": "Net Income", "korean": "순이익"},
        "ebitda": {"name": "EBITDA", "korean": "EBITDA"},
    },
    "cash_flow": {
        "operating_cash_flow": {"name": "Operating Cash Flow", "korean": "영업활동현금흐름"},
        "investing_cf": {"name": "Investing Cash Flow", "korean": "투자활동현금흐름"},
        "financing_cf": {"name": "Financing Cash Flow", "korean": "재무활동현금흐름"},
        "fcf": {"name": "Free Cash Flow", "korean": "잉여현금흐름"},
        "capex": {"name": "Capital Expenditure", "korean": "자본적지출"},
    },
    "valuation": {
        "market_cap": {"name": "Market Cap", "korean": "시가총액"},
        "per": {"name": "P/E Ratio", "korean": "PER"},
        "pbr": {"name": "P/B Ratio", "korean": "PBR"},
        "psr": {"name": "P/S Ratio", "korean": "PSR"},
        "ev": {"name": "Enterprise Value", "korean": "기업가치"},
        "ev_ebitda": {"name": "EV/EBITDA", "korean": "EV/EBITDA"},
        "dividend_yield": {"name": "Dividend Yield", "korean": "배당수익률"},
        "dividend_per_share": {"name": "DPS", "korean": "주당배당금"},
    }
}
```

### 2.3 응답 형식

```json
{
  "success": true,
  "data": {
    "005930": {
      "ticker": "005930",
      "name": "삼성전자",
      "region": "KR",
      "periods": [
        {
          "fiscal_year": 2024,
          "period_type": "ANNUAL",
          "date": "2024-12-31",
          "balance_sheet": {
            "total_assets": {"value": 455000000000000, "unit": "KRW"},
            "current_assets": {"value": 210000000000000, "unit": "KRW"},
            "total_liabilities": {"value": 100000000000000, "unit": "KRW"},
            "current_liabilities": {"value": 60000000000000, "unit": "KRW"},
            "total_equity": {"value": 355000000000000, "unit": "KRW"}
          },
          "income_statement": {
            "revenue": {"value": 300000000000000, "unit": "KRW"},
            "operating_profit": {"value": 45000000000000, "unit": "KRW"},
            "net_income": {"value": 35000000000000, "unit": "KRW"}
          },
          "cash_flow": {
            "operating_cash_flow": {"value": 50000000000000, "unit": "KRW"},
            "investing_cf": {"value": -25000000000000, "unit": "KRW"},
            "financing_cf": {"value": -10000000000000, "unit": "KRW"}
          }
        }
      ]
    }
  },
  "metadata": {
    "ticker_count": 1,
    "categories": ["balance_sheet", "income_statement", "cash_flow"],
    "period_type": "ANNUAL",
    "periods_requested": 1,
    "query_time_ms": 45
  }
}
```

### 2.4 파일 구조

```
mcp_server/
├── tools/
│   └── fundamentals_tool.py     # 신규: 재무 데이터 조회 도구
├── adapters/
│   └── data_adapter.py          # 수정: get_fundamentals() 메서드 추가
└── utils/
    └── formatters.py            # 수정: format_fundamentals_response() 추가
```

---

## 3. Phase 2: 재무비율 계산기 MCP 도구

### 3.1 도구 정의

**도구명**: `calculate_financial_ratios`

```python
Tool(
    name="calculate_financial_ratios",
    description=(
        "Calculate financial ratios from fundamental data. "
        "Includes liquidity, leverage, profitability, and efficiency ratios. "
        "Provides interpretation and industry comparison when available."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "tickers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of ticker symbols (max 20)",
                "minItems": 1,
                "maxItems": 20
            },
            "ratio_categories": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["liquidity", "leverage", "profitability", "efficiency", "valuation", "dividend", "all"]
                },
                "description": "Ratio categories to calculate",
                "default": ["all"]
            },
            "period_type": {
                "type": "string",
                "enum": ["ANNUAL", "QUARTERLY", "TTM"],
                "default": "ANNUAL"
            },
            "include_interpretation": {
                "type": "boolean",
                "description": "Include ratio interpretation and health assessment",
                "default": true
            },
            "region": {
                "type": "string",
                "enum": ["KR", "US", "JP", "HK", "CN", "VN"],
                "default": "KR"
            }
        },
        "required": ["tickers"]
    }
)
```

### 3.2 비율 카테고리 정의

```python
FINANCIAL_RATIOS = {
    "liquidity": {
        "current_ratio": {
            "name": "Current Ratio",
            "korean": "유동비율",
            "formula": "current_assets / current_liabilities",
            "unit": "ratio",
            "healthy_range": {"min": 1.5, "max": 3.0},
            "interpretation": {
                "low": "단기 채무 상환 능력 부족 위험",
                "normal": "적정 유동성 보유",
                "high": "유동자산 과다 보유 (비효율 가능성)"
            }
        },
        "quick_ratio": {
            "name": "Quick Ratio",
            "korean": "당좌비율",
            "formula": "(current_assets - inventory) / current_liabilities",
            "unit": "ratio",
            "healthy_range": {"min": 1.0, "max": 2.0},
            "interpretation": {
                "low": "단기 지급 능력 취약",
                "normal": "적정 당좌자산 보유",
                "high": "과도한 유동성"
            }
        },
        "cash_ratio": {
            "name": "Cash Ratio",
            "korean": "현금비율",
            "formula": "cash_and_equivalents / current_liabilities",
            "unit": "ratio",
            "healthy_range": {"min": 0.2, "max": 0.5},
            "requires": ["cash_and_equivalents"],  # Phase 4에서 추가
            "interpretation": {
                "low": "즉시 가용 현금 부족",
                "normal": "적정 현금 보유",
                "high": "과도한 현금 보유 (기회비용 발생)"
            }
        }
    },
    "leverage": {
        "debt_ratio": {
            "name": "Debt Ratio",
            "korean": "부채비율",
            "formula": "total_liabilities / total_equity * 100",
            "unit": "percent",
            "healthy_range": {"min": 0, "max": 200},
            "interpretation": {
                "low": "보수적 재무구조",
                "normal": "적정 레버리지",
                "high": "재무위험 증가"
            }
        },
        "debt_to_assets": {
            "name": "Debt to Assets",
            "korean": "자산대비부채비율",
            "formula": "total_liabilities / total_assets * 100",
            "unit": "percent",
            "healthy_range": {"min": 0, "max": 60}
        },
        "interest_coverage": {
            "name": "Interest Coverage Ratio",
            "korean": "이자보상배율",
            "formula": "operating_profit / interest_expense",
            "unit": "times",
            "healthy_range": {"min": 3.0, "max": null},
            "interpretation": {
                "low": "이자 지급 능력 부족 (3배 미만 위험)",
                "normal": "안정적 이자 지급 능력",
                "high": "우수한 이자 지급 여력"
            }
        }
    },
    "profitability": {
        "gross_margin": {
            "name": "Gross Profit Margin",
            "korean": "매출총이익률",
            "formula": "gross_profit / revenue * 100",
            "unit": "percent",
            "healthy_range": {"min": 20, "max": null}
        },
        "operating_margin": {
            "name": "Operating Profit Margin",
            "korean": "영업이익률",
            "formula": "operating_profit / revenue * 100",
            "unit": "percent",
            "healthy_range": {"min": 5, "max": null}
        },
        "net_margin": {
            "name": "Net Profit Margin",
            "korean": "순이익률",
            "formula": "net_income / revenue * 100",
            "unit": "percent",
            "healthy_range": {"min": 3, "max": null}
        },
        "roe": {
            "name": "Return on Equity",
            "korean": "자기자본이익률",
            "formula": "net_income / total_equity * 100",
            "unit": "percent",
            "healthy_range": {"min": 10, "max": null}
        },
        "roa": {
            "name": "Return on Assets",
            "korean": "총자산이익률",
            "formula": "net_income / total_assets * 100",
            "unit": "percent",
            "healthy_range": {"min": 5, "max": null}
        },
        "ebitda_margin": {
            "name": "EBITDA Margin",
            "korean": "EBITDA마진",
            "formula": "ebitda / revenue * 100",
            "unit": "percent",
            "healthy_range": {"min": 10, "max": null}
        }
    },
    "efficiency": {
        "asset_turnover": {
            "name": "Asset Turnover",
            "korean": "자산회전율",
            "formula": "revenue / total_assets",
            "unit": "times"
        },
        "inventory_turnover": {
            "name": "Inventory Turnover",
            "korean": "재고회전율",
            "formula": "cogs / inventory",
            "unit": "times"
        },
        "receivables_turnover": {
            "name": "Receivables Turnover",
            "korean": "매출채권회전율",
            "formula": "revenue / accounts_receivable",
            "unit": "times"
        },
        "days_inventory": {
            "name": "Days Inventory Outstanding",
            "korean": "재고자산회전일수",
            "formula": "365 / inventory_turnover",
            "unit": "days"
        },
        "days_receivables": {
            "name": "Days Sales Outstanding",
            "korean": "매출채권회전일수",
            "formula": "365 / receivables_turnover",
            "unit": "days"
        }
    },
    "dividend": {
        "dividend_yield": {
            "name": "Dividend Yield",
            "korean": "배당수익률",
            "formula": "dividend_per_share / close_price * 100",
            "unit": "percent",
            "source": "direct"  # DB에서 직접 조회
        },
        "dividend_payout_ratio": {
            "name": "Dividend Payout Ratio",
            "korean": "배당성향",
            "formula": "(dividend_per_share * shares_outstanding) / net_income * 100",
            "unit": "percent",
            "healthy_range": {"min": 20, "max": 60}
        }
    }
}
```

### 3.3 계산 로직 클래스

```python
# mcp_server/calculators/ratio_calculator.py

from typing import Dict, Optional, Any
from dataclasses import dataclass

@dataclass
class RatioResult:
    """재무비율 계산 결과"""
    name: str
    korean: str
    value: Optional[float]
    unit: str
    formula: str
    interpretation: Optional[str] = None
    health_status: Optional[str] = None  # "healthy", "caution", "warning"

class FinancialRatioCalculator:
    """재무비율 계산기"""

    def __init__(self, fundamentals: Dict[str, Any]):
        self.data = fundamentals

    def calculate_current_ratio(self) -> Optional[float]:
        """유동비율 = 유동자산 / 유동부채"""
        ca = self.data.get('current_assets')
        cl = self.data.get('current_liabilities')
        if ca and cl and cl > 0:
            return round(ca / cl, 2)
        return None

    def calculate_quick_ratio(self) -> Optional[float]:
        """당좌비율 = (유동자산 - 재고) / 유동부채"""
        ca = self.data.get('current_assets')
        inv = self.data.get('inventory', 0) or 0
        cl = self.data.get('current_liabilities')
        if ca and cl and cl > 0:
            return round((ca - inv) / cl, 2)
        return None

    def calculate_debt_ratio(self) -> Optional[float]:
        """부채비율 = 총부채 / 총자본 * 100"""
        tl = self.data.get('total_liabilities')
        te = self.data.get('total_equity')
        if tl is not None and te and te > 0:
            return round(tl / te * 100, 2)
        return None

    def calculate_interest_coverage(self) -> Optional[float]:
        """이자보상배율 = 영업이익 / 이자비용"""
        op = self.data.get('operating_profit')
        ie = self.data.get('interest_expense')
        if op and ie and ie > 0:
            return round(op / ie, 2)
        return None

    def calculate_gross_margin(self) -> Optional[float]:
        """매출총이익률 = 매출총이익 / 매출 * 100"""
        gp = self.data.get('gross_profit')
        rev = self.data.get('revenue')
        if gp and rev and rev > 0:
            return round(gp / rev * 100, 2)
        return None

    def calculate_operating_margin(self) -> Optional[float]:
        """영업이익률 = 영업이익 / 매출 * 100"""
        op = self.data.get('operating_profit')
        rev = self.data.get('revenue')
        if op and rev and rev > 0:
            return round(op / rev * 100, 2)
        return None

    def calculate_net_margin(self) -> Optional[float]:
        """순이익률 = 순이익 / 매출 * 100"""
        ni = self.data.get('net_income')
        rev = self.data.get('revenue')
        if ni and rev and rev > 0:
            return round(ni / rev * 100, 2)
        return None

    def calculate_roe(self) -> Optional[float]:
        """ROE = 순이익 / 자기자본 * 100"""
        ni = self.data.get('net_income')
        te = self.data.get('total_equity')
        if ni and te and te > 0:
            return round(ni / te * 100, 2)
        return None

    def calculate_roa(self) -> Optional[float]:
        """ROA = 순이익 / 총자산 * 100"""
        ni = self.data.get('net_income')
        ta = self.data.get('total_assets')
        if ni and ta and ta > 0:
            return round(ni / ta * 100, 2)
        return None

    def calculate_dividend_payout(self) -> Optional[float]:
        """배당성향 = (DPS * 주식수) / 순이익 * 100"""
        dps = self.data.get('dividend_per_share')
        shares = self.data.get('shares_outstanding')
        ni = self.data.get('net_income')
        if dps and shares and ni and ni > 0:
            total_dividend = dps * shares
            return round(total_dividend / ni * 100, 2)
        return None

    def calculate_all(self, categories: list = None) -> Dict[str, Dict]:
        """모든 비율 계산"""
        results = {}

        if not categories or 'liquidity' in categories or 'all' in categories:
            results['liquidity'] = {
                'current_ratio': self.calculate_current_ratio(),
                'quick_ratio': self.calculate_quick_ratio(),
            }

        if not categories or 'leverage' in categories or 'all' in categories:
            results['leverage'] = {
                'debt_ratio': self.calculate_debt_ratio(),
                'interest_coverage': self.calculate_interest_coverage(),
            }

        if not categories or 'profitability' in categories or 'all' in categories:
            results['profitability'] = {
                'gross_margin': self.calculate_gross_margin(),
                'operating_margin': self.calculate_operating_margin(),
                'net_margin': self.calculate_net_margin(),
                'roe': self.calculate_roe(),
                'roa': self.calculate_roa(),
            }

        if not categories or 'dividend' in categories or 'all' in categories:
            results['dividend'] = {
                'dividend_yield': self.data.get('dividend_yield'),
                'dividend_payout_ratio': self.calculate_dividend_payout(),
            }

        return results
```

### 3.4 응답 형식

```json
{
  "success": true,
  "data": {
    "005930": {
      "ticker": "005930",
      "name": "삼성전자",
      "fiscal_year": 2024,
      "ratios": {
        "liquidity": {
          "current_ratio": {
            "value": 2.35,
            "unit": "ratio",
            "korean": "유동비율",
            "interpretation": "적정 유동성 보유",
            "health_status": "healthy",
            "benchmark": {"industry_avg": 1.8, "sector": "반도체"}
          },
          "quick_ratio": {
            "value": 1.85,
            "unit": "ratio",
            "korean": "당좌비율",
            "interpretation": "적정 당좌자산 보유",
            "health_status": "healthy"
          }
        },
        "leverage": {
          "debt_ratio": {
            "value": 45.5,
            "unit": "percent",
            "korean": "부채비율",
            "interpretation": "보수적 재무구조",
            "health_status": "healthy"
          },
          "interest_coverage": {
            "value": 25.3,
            "unit": "times",
            "korean": "이자보상배율",
            "interpretation": "우수한 이자 지급 여력",
            "health_status": "healthy"
          }
        },
        "profitability": {
          "operating_margin": {
            "value": 15.2,
            "unit": "percent",
            "korean": "영업이익률",
            "health_status": "healthy"
          },
          "roe": {
            "value": 12.5,
            "unit": "percent",
            "korean": "자기자본이익률",
            "health_status": "healthy"
          }
        },
        "dividend": {
          "dividend_yield": {
            "value": 1.46,
            "unit": "percent",
            "korean": "배당수익률"
          },
          "dividend_payout_ratio": {
            "value": 28.5,
            "unit": "percent",
            "korean": "배당성향",
            "interpretation": "적정 배당 수준",
            "health_status": "healthy"
          }
        }
      },
      "summary": {
        "overall_health": "healthy",
        "strengths": ["유동성 양호", "낮은 부채비율", "안정적 이익률"],
        "concerns": []
      }
    }
  },
  "metadata": {
    "ticker_count": 1,
    "ratios_calculated": 10,
    "query_time_ms": 65
  }
}
```

---

## 4. Phase 3: 배당 히스토리 테이블 및 MCP 도구

### 4.1 현황 분석

현재 `ticker_fundamentals` 테이블의 배당 데이터:
- **DAILY 데이터**: 최근 배당금/배당수익률만 저장 (TTM 기준)
- **ANNUAL 데이터**: 배당 컬럼이 대부분 NULL

**문제점**:
1. 배당 이력(언제, 얼마를 지급했는지) 추적 불가
2. 배당 성장률 계산 불가
3. 배당 지급 일정(ex-date, payment date) 정보 없음

### 4.2 신규 테이블 설계

```sql
-- 배당 히스토리 테이블
CREATE TABLE dividend_history (
    id BIGSERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL,

    -- 배당 기본 정보
    fiscal_year INTEGER NOT NULL,           -- 귀속 회계연도
    dividend_type VARCHAR(20) NOT NULL,     -- 'interim', 'final', 'special', 'quarterly'
    dividend_per_share NUMERIC(15,4),       -- 주당배당금
    dividend_yield NUMERIC(10,4),           -- 배당수익률 (발표 시점)

    -- 배당 일정
    declaration_date DATE,                  -- 배당 발표일
    ex_dividend_date DATE,                  -- 배당락일
    record_date DATE,                       -- 배당기준일
    payment_date DATE,                      -- 배당지급일

    -- 추가 정보
    currency VARCHAR(3) DEFAULT 'KRW',      -- 통화
    total_dividend_amount NUMERIC(20,2),    -- 총 배당금액
    payout_ratio NUMERIC(10,4),             -- 배당성향

    -- 메타데이터
    data_source VARCHAR(50),                -- 데이터 출처 (KIS, yfinance, etc.)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- 제약조건
    CONSTRAINT uk_dividend_history UNIQUE (ticker, region, fiscal_year, dividend_type, ex_dividend_date)
);

-- 인덱스
CREATE INDEX idx_dividend_ticker_region ON dividend_history(ticker, region);
CREATE INDEX idx_dividend_fiscal_year ON dividend_history(fiscal_year DESC);
CREATE INDEX idx_dividend_ex_date ON dividend_history(ex_dividend_date DESC);
CREATE INDEX idx_dividend_payment_date ON dividend_history(payment_date);

-- 코멘트
COMMENT ON TABLE dividend_history IS '배당 이력 테이블 - 종목별 배당 지급 내역 추적';
COMMENT ON COLUMN dividend_history.dividend_type IS 'interim: 중간배당, final: 기말배당, special: 특별배당, quarterly: 분기배당';
```

### 4.3 MCP 도구 정의

**도구명**: `query_dividend_history`

```python
Tool(
    name="query_dividend_history",
    description=(
        "Get dividend payment history for stocks. "
        "Includes dividend amounts, dates, yields, and growth analysis. "
        "Useful for income investing strategy and dividend growth analysis."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "tickers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of ticker symbols (max 20)",
                "minItems": 1,
                "maxItems": 20
            },
            "years": {
                "type": "integer",
                "description": "Number of years of history (1-10)",
                "minimum": 1,
                "maximum": 10,
                "default": 5
            },
            "include_growth_analysis": {
                "type": "boolean",
                "description": "Include dividend growth rate analysis",
                "default": true
            },
            "include_upcoming": {
                "type": "boolean",
                "description": "Include upcoming dividend dates if available",
                "default": true
            },
            "region": {
                "type": "string",
                "enum": ["KR", "US", "JP", "HK", "CN", "VN"],
                "default": "KR"
            }
        },
        "required": ["tickers"]
    }
)
```

### 4.4 응답 형식

```json
{
  "success": true,
  "data": {
    "005930": {
      "ticker": "005930",
      "name": "삼성전자",
      "region": "KR",
      "currency": "KRW",
      "dividend_history": [
        {
          "fiscal_year": 2024,
          "dividend_type": "final",
          "dividend_per_share": 1444,
          "dividend_yield": 1.46,
          "ex_dividend_date": "2025-03-27",
          "payment_date": "2025-04-18",
          "payout_ratio": 28.5
        },
        {
          "fiscal_year": 2024,
          "dividend_type": "interim",
          "dividend_per_share": 361,
          "dividend_yield": 0.38,
          "ex_dividend_date": "2024-06-27",
          "payment_date": "2024-08-16",
          "payout_ratio": null
        },
        {
          "fiscal_year": 2023,
          "dividend_type": "final",
          "dividend_per_share": 1444,
          "dividend_yield": 1.52,
          "ex_dividend_date": "2024-03-27",
          "payment_date": "2024-04-19"
        }
      ],
      "growth_analysis": {
        "dividend_cagr_3y": 0.0,
        "dividend_cagr_5y": -0.028,
        "consecutive_years": 10,
        "dividend_streak": "maintained",
        "average_payout_ratio": 27.5,
        "trend": "stable"
      },
      "upcoming": {
        "next_ex_date": "2025-06-26",
        "expected_dps": 361,
        "dividend_type": "interim"
      },
      "summary": {
        "annual_dividend_2024": 1805,
        "current_yield": 1.84,
        "dividend_policy": "분기배당 (중간1회 + 기말1회)"
      }
    }
  },
  "metadata": {
    "ticker_count": 1,
    "years_requested": 5,
    "records_found": 10
  }
}
```

### 4.5 데이터 수집 전략

```python
# modules/collection/dividend_collector.py

class DividendCollector:
    """배당 데이터 수집기"""

    def __init__(self, db_manager):
        self.db = db_manager
        self.sources = {
            'KR': ['pykrx', 'krx'],      # 한국: pykrx, KRX 공시
            'US': ['yfinance', 'sec'],    # 미국: yfinance, SEC Edgar
            'JP': ['yfinance'],           # 일본: yfinance
            'HK': ['yfinance'],           # 홍콩: yfinance
        }

    async def collect_kr_dividends(self, ticker: str) -> list:
        """한국 배당 데이터 수집 (pykrx)"""
        from pykrx import stock

        # 최근 5년 배당 이력
        dividends = []
        for year in range(2020, 2025):
            try:
                div_data = stock.get_market_dividend(ticker, str(year))
                if div_data:
                    dividends.append({
                        'fiscal_year': year,
                        'dividend_per_share': div_data.get('dps'),
                        'dividend_yield': div_data.get('yield'),
                        # ... 추가 필드
                    })
            except Exception as e:
                logger.warning(f"Failed to get dividend for {ticker} {year}: {e}")

        return dividends

    async def collect_us_dividends(self, ticker: str) -> list:
        """미국 배당 데이터 수집 (yfinance)"""
        import yfinance as yf

        stock = yf.Ticker(ticker)
        dividends = stock.dividends  # pandas Series

        results = []
        for date, amount in dividends.items():
            results.append({
                'ex_dividend_date': date.strftime('%Y-%m-%d'),
                'dividend_per_share': float(amount),
                'dividend_type': 'quarterly',  # US는 대부분 분기배당
            })

        return results
```

---

## 5. Phase 4: 현금성자산 컬럼 및 현금비율

### 5.1 스키마 변경

```sql
-- 현금성자산 관련 컬럼 추가
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS cash_and_equivalents NUMERIC(20,2)
    COMMENT '현금 및 현금성자산 (Cash and Cash Equivalents)';

ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS short_term_investments NUMERIC(20,2)
    COMMENT '단기금융상품 (Short-term Investments)';

ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS marketable_securities NUMERIC(20,2)
    COMMENT '유가증권 (Marketable Securities)';

-- 인덱스 추가 (현금비율 계산 최적화)
CREATE INDEX IF NOT EXISTS idx_fundamentals_cash
ON ticker_fundamentals(ticker, region, fiscal_year DESC)
WHERE cash_and_equivalents IS NOT NULL;

-- 코멘트
COMMENT ON COLUMN ticker_fundamentals.cash_and_equivalents IS
    '현금 및 현금성자산: 현금, 요구불예금, 만기 3개월 이내 단기금융상품';
COMMENT ON COLUMN ticker_fundamentals.short_term_investments IS
    '단기금융상품: 만기 3개월~1년 금융상품';
COMMENT ON COLUMN ticker_fundamentals.marketable_securities IS
    '유가증권: 단기매매목적 또는 매도가능 유가증권';
```

### 5.2 현금비율 계산 추가

```python
# mcp_server/calculators/ratio_calculator.py 에 추가

class FinancialRatioCalculator:
    # ... 기존 메서드들 ...

    def calculate_cash_ratio(self) -> Optional[float]:
        """
        현금비율 = 현금성자산 / 유동부채

        가장 보수적인 유동성 지표.
        즉시 현금화 가능한 자산만으로 단기부채 상환 능력 측정.
        """
        cash = self.data.get('cash_and_equivalents')
        cl = self.data.get('current_liabilities')

        if cash is not None and cl and cl > 0:
            return round(cash / cl, 2)
        return None

    def calculate_cash_to_assets(self) -> Optional[float]:
        """현금자산비율 = 현금성자산 / 총자산 * 100"""
        cash = self.data.get('cash_and_equivalents')
        ta = self.data.get('total_assets')

        if cash is not None and ta and ta > 0:
            return round(cash / ta * 100, 2)
        return None

    def calculate_net_cash(self) -> Optional[float]:
        """
        순현금 = 현금성자산 - 총부채

        양수면 무차입 경영 (Net Cash Position)
        """
        cash = self.data.get('cash_and_equivalents')
        tl = self.data.get('total_liabilities')

        if cash is not None and tl is not None:
            return cash - tl
        return None
```

### 5.3 데이터 수집 확장

```python
# modules/parsers/financial_statement_parser.py 에 추가

class BalanceSheetParser:
    """재무상태표 파서"""

    # 현금성자산 매핑 (재무제표 항목명 → DB 컬럼)
    CASH_MAPPINGS = {
        'KR': {
            # DART 재무제표 항목
            '현금및현금성자산': 'cash_and_equivalents',
            '현금및현금등가물': 'cash_and_equivalents',
            '단기금융상품': 'short_term_investments',
            '단기금융자산': 'short_term_investments',
            '유가증권': 'marketable_securities',
            '단기투자자산': 'marketable_securities',
        },
        'US': {
            # SEC 10-K/10-Q 항목
            'Cash And Cash Equivalents': 'cash_and_equivalents',
            'CashAndCashEquivalentsAtCarryingValue': 'cash_and_equivalents',
            'Short-term Investments': 'short_term_investments',
            'ShortTermInvestments': 'short_term_investments',
            'Marketable Securities': 'marketable_securities',
            'MarketableSecurities': 'marketable_securities',
        },
        'JP': {
            # 일본 재무제표 항목
            '現金及び預金': 'cash_and_equivalents',
            '現金及び現金同等物': 'cash_and_equivalents',
            '有価証券': 'marketable_securities',
        }
    }

    def parse_cash_items(self, raw_data: dict, region: str) -> dict:
        """현금성자산 항목 파싱"""
        mappings = self.CASH_MAPPINGS.get(region, {})
        result = {}

        for source_key, target_key in mappings.items():
            if source_key in raw_data:
                value = raw_data[source_key]
                if value is not None:
                    result[target_key] = float(value)

        return result
```

### 5.4 응답 형식 (현금비율 추가)

```json
{
  "ratios": {
    "liquidity": {
      "current_ratio": {"value": 2.35, "unit": "ratio"},
      "quick_ratio": {"value": 1.85, "unit": "ratio"},
      "cash_ratio": {
        "value": 0.45,
        "unit": "ratio",
        "korean": "현금비율",
        "interpretation": "적정 현금 보유",
        "health_status": "healthy",
        "detail": {
          "cash_and_equivalents": 125000000000000,
          "current_liabilities": 280000000000000
        }
      }
    },
    "cash_position": {
      "cash_to_assets": {
        "value": 27.5,
        "unit": "percent",
        "korean": "현금자산비율"
      },
      "net_cash": {
        "value": 25000000000000,
        "unit": "KRW",
        "korean": "순현금",
        "interpretation": "무차입 경영 (Net Cash Position)"
      }
    }
  }
}
```

---

## 6. 통합 아키텍처

### 6.1 컴포넌트 다이어그램

```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Client (Claude)                       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         MCP Server                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                      Tools Layer                         │    │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐ │    │
│  │  │query_        │ │calculate_    │ │query_dividend_   │ │    │
│  │  │fundamentals  │ │financial_    │ │history           │ │    │
│  │  │              │ │ratios        │ │                  │ │    │
│  │  └──────┬───────┘ └──────┬───────┘ └────────┬─────────┘ │    │
│  └─────────┼────────────────┼──────────────────┼───────────┘    │
│            │                │                  │                 │
│  ┌─────────▼────────────────▼──────────────────▼───────────┐    │
│  │                    Adapters Layer                        │    │
│  │  ┌──────────────────────────────────────────────────┐   │    │
│  │  │              DataAdapter (확장)                   │   │    │
│  │  │  + get_fundamentals()                            │   │    │
│  │  │  + get_dividend_history()                        │   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────┬───────────────────────────┘    │
│                                │                                 │
│  ┌─────────────────────────────▼───────────────────────────┐    │
│  │                   Calculators Layer                      │    │
│  │  ┌────────────────────┐  ┌─────────────────────────┐    │    │
│  │  │FinancialRatio      │  │DividendGrowth           │    │    │
│  │  │Calculator          │  │Calculator               │    │    │
│  │  └────────────────────┘  └─────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────┘    │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL + TimescaleDB                      │
│  ┌─────────────────────┐  ┌─────────────────────────────────┐   │
│  │ ticker_fundamentals │  │ dividend_history (신규)          │   │
│  │ + cash_and_         │  │ - ticker, region                │   │
│  │   equivalents (신규)│  │ - fiscal_year, dividend_type    │   │
│  │ + short_term_       │  │ - dividend_per_share            │   │
│  │   investments (신규)│  │ - ex_dividend_date              │   │
│  └─────────────────────┘  │ - payment_date                  │   │
│                           └─────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 파일 구조

```
mcp_server/
├── tools/
│   ├── __init__.py
│   ├── data_query.py           # 기존: OHLCV 조회
│   ├── cagr_tool.py            # 기존: CAGR 계산
│   ├── screening_tool.py       # 기존: 종목 스크리닝
│   ├── technical_tool.py       # 기존: 기술적 지표
│   ├── fundamentals_tool.py    # 신규 Phase 1: 재무 데이터 조회
│   ├── ratios_tool.py          # 신규 Phase 2: 재무비율 계산
│   └── dividend_tool.py        # 신규 Phase 3: 배당 히스토리
│
├── adapters/
│   ├── data_adapter.py         # 수정: get_fundamentals(), get_dividend_history() 추가
│   └── ...
│
├── calculators/                # 신규 디렉토리
│   ├── __init__.py
│   ├── ratio_calculator.py     # 신규 Phase 2: 재무비율 계산 로직
│   └── dividend_calculator.py  # 신규 Phase 3: 배당 성장률 계산
│
├── utils/
│   ├── formatters.py           # 수정: 신규 응답 포매터 추가
│   └── ...
│
└── config.py                   # 기존
```

### 6.3 의존성 흐름

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Tool Handlers                         │
│  fundamentals_tool.py → ratios_tool.py → dividend_tool.py   │
└──────────────────────────────┬──────────────────────────────┘
                               │ 호출
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                      DataAdapter                             │
│  - get_fundamentals() : 재무 데이터 조회                     │
│  - get_dividend_history() : 배당 이력 조회                   │
└──────────────────────────────┬──────────────────────────────┘
                               │ 호출
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                      Calculators                             │
│  - FinancialRatioCalculator : 비율 계산                      │
│  - DividendGrowthCalculator : 배당 성장률 계산               │
└──────────────────────────────┬──────────────────────────────┘
                               │ 쿼리
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                PostgresDatabaseManager                       │
│  - ticker_fundamentals 테이블                                │
│  - dividend_history 테이블 (신규)                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. 구현 일정

### 7.1 Phase별 일정

| Phase | 작업 내용 | 예상 기간 | 의존성 |
|-------|----------|-----------|--------|
| **Phase 1** | 재무 데이터 조회 MCP 도구 | 1-2일 | 없음 |
| **Phase 2** | 재무비율 계산기 MCP 도구 | 2-3일 | Phase 1 |
| **Phase 3** | 배당 히스토리 테이블 + 도구 | 3-4일 | Phase 1 |
| **Phase 4** | 현금성자산 컬럼 + 현금비율 | 2-3일 | Phase 2 |
| **테스트** | 통합 테스트 및 검증 | 2일 | 전체 |

**총 예상 기간**: 10-14일

### 7.2 세부 작업 분해

#### Phase 1 (1-2일)
- [ ] `fundamentals_tool.py` 생성
- [ ] `DataAdapter.get_fundamentals()` 구현
- [ ] 카테고리별 필드 매핑 정의
- [ ] 응답 포매터 구현
- [ ] 단위 테스트 작성

#### Phase 2 (2-3일)
- [ ] `calculators/` 디렉토리 생성
- [ ] `FinancialRatioCalculator` 클래스 구현
- [ ] `ratios_tool.py` 생성
- [ ] 비율 해석 로직 구현
- [ ] 단위 테스트 작성

#### Phase 3 (3-4일)
- [ ] `dividend_history` 테이블 DDL 실행
- [ ] `DividendCollector` 수집기 구현
- [ ] `DividendGrowthCalculator` 구현
- [ ] `dividend_tool.py` 생성
- [ ] 초기 데이터 수집 (KR/US 주요 종목)
- [ ] 단위 테스트 작성

#### Phase 4 (2-3일)
- [ ] 스키마 마이그레이션 (현금 컬럼 추가)
- [ ] 데이터 수집 파서 수정
- [ ] `FinancialRatioCalculator`에 현금비율 추가
- [ ] 기존 데이터 백필 (US 시장)
- [ ] 단위 테스트 작성

### 7.3 우선순위

1. **즉시 구현 (High)**: Phase 1, Phase 2
   - 이미 데이터 존재, MCP 노출만 필요
   - 사용자 가치 즉시 제공

2. **단기 구현 (Medium)**: Phase 3
   - 신규 테이블 필요하지만 데이터 수집 가능
   - 배당 투자 전략에 필수

3. **중기 구현 (Low)**: Phase 4
   - 데이터 수집 확장 필요
   - Phase 2 완료 후 점진적 개선

---

## 부록 A: SQL 쿼리 예시

### A.1 재무 데이터 조회

```sql
-- 단일 종목 재무 데이터 조회
SELECT
    ticker, date, fiscal_year, period_type,
    -- Balance Sheet
    total_assets, current_assets, total_liabilities, current_liabilities, total_equity,
    inventory, accounts_receivable,
    -- Income Statement
    revenue, gross_profit, operating_profit, net_income, ebitda,
    cogs, sga_expense, interest_expense,
    -- Cash Flow
    operating_cash_flow, investing_cf, financing_cf, fcf
FROM ticker_fundamentals
WHERE ticker = '005930'
  AND region = 'KR'
  AND period_type = 'ANNUAL'
ORDER BY fiscal_year DESC
LIMIT 5;
```

### A.2 재무비율 계산 쿼리

```sql
-- 유동성 비율 계산
SELECT
    ticker,
    fiscal_year,
    ROUND(current_assets / NULLIF(current_liabilities, 0), 2) as current_ratio,
    ROUND((current_assets - COALESCE(inventory, 0)) / NULLIF(current_liabilities, 0), 2) as quick_ratio,
    ROUND(total_liabilities / NULLIF(total_equity, 0) * 100, 2) as debt_ratio,
    ROUND(operating_profit / NULLIF(interest_expense, 0), 2) as interest_coverage
FROM ticker_fundamentals
WHERE ticker IN ('005930', '000660')
  AND region = 'KR'
  AND period_type = 'ANNUAL'
  AND fiscal_year >= 2022
ORDER BY ticker, fiscal_year DESC;
```

### A.3 배당 히스토리 조회

```sql
-- 배당 성장률 계산
WITH dividend_yearly AS (
    SELECT
        ticker,
        fiscal_year,
        SUM(dividend_per_share) as annual_dps
    FROM dividend_history
    WHERE ticker = '005930' AND region = 'KR'
    GROUP BY ticker, fiscal_year
)
SELECT
    ticker,
    fiscal_year,
    annual_dps,
    LAG(annual_dps) OVER (ORDER BY fiscal_year) as prev_dps,
    ROUND((annual_dps - LAG(annual_dps) OVER (ORDER BY fiscal_year))
          / NULLIF(LAG(annual_dps) OVER (ORDER BY fiscal_year), 0) * 100, 2) as growth_rate
FROM dividend_yearly
ORDER BY fiscal_year DESC;
```

---

**문서 끝**
