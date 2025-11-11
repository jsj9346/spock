# Spock MCP Server - 아키텍처 및 Tool 설계

AI 기반 퀀트 분석을 위한 MCP 서버 상세 설계 문서

---

## 목차

1. [시스템 아키텍처](#1-시스템-아키텍처)
2. [설계 원칙](#2-설계-원칙)
3. [프로젝트 구조](#3-프로젝트-구조)
4. [MCP Tools 상세 설계 (8개)](#4-mcp-tools-상세-설계)
5. [Adapter Layer 설계](#5-adapter-layer-설계)
6. [Utils 및 공통 컴포넌트](#6-utils-및-공통-컴포넌트)
7. [에러 처리 전략](#7-에러-처리-전략)
8. [성능 최적화](#8-성능-최적화)
9. [보안 설계](#9-보안-설계)

---

## 1. 시스템 아키텍처

### 1.1 프로젝트 개요

**Spock MCP Server**는 Claude Code가 자연어로 퀀트 분석을 수행할 수 있도록 하는 MCP(Model Context Protocol) 서버입니다.

**핵심 가치 제안**:
- ✅ 자연어 → 퀀트 분석 (원클릭 워크플로우)
- ✅ 데이터 조회, 백테스트, 포트폴리오 분석 통합
- ✅ 기존 Spock 모듈 100% 재사용 (Thin Wrapper Pattern)

**현재 상태** (2025-10-30):
```yaml
Database:
  - PostgreSQL + TimescaleDB
  - 1,369,467 OHLCV 레코드
  - 표준화 완료 (timeframe='1d')

Backtesting:
  - vectorbt Adapter (100x faster)
  - Custom Engine (production-ready)
  - Walk-Forward Optimization

Factors:
  - Value (P/E, P/B, EV/EBITDA)
  - Momentum (12-month return, RSI)
  - Quality (ROE, Debt/Equity)

Test Status:
  ⚠️ 24.9% coverage (목표: 70%+)
  ⚠️ 18 failing tests (SQLite schema)
```

---

### 1.2 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                   Claude Code (User)                         │
│  "삼성전자 Momentum 백테스트해줘" (자연어)                    │
└────────────────────────┬────────────────────────────────────┘
                         │ MCP Protocol (stdio)
┌────────────────────────▼────────────────────────────────────┐
│                  Spock MCP Server                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  MCP SDK Layer                                       │   │
│  │  - Tool Registration & Dispatch                      │   │
│  │  - Resource Management                               │   │
│  │  - Protocol Handling                                 │   │
│  └─────────────────────┬───────────────────────────────┘   │
│                        │                                     │
│  ┌─────────────────────▼───────────────────────────────┐   │
│  │  Tool Layer (8 Core Tools)                          │   │
│  │  1. query_ohlcv_data                                │   │
│  │  2. query_factor_scores                             │   │
│  │  3. query_technical_indicators                      │   │
│  │  4. run_backtest                                    │   │
│  │  5. optimize_strategy_params                        │   │
│  │  6. analyze_portfolio                               │   │
│  │  7. rebalance_portfolio                             │   │
│  │  8. get_system_status                               │   │
│  └─────────────────────┬───────────────────────────────┘   │
│                        │                                     │
│  ┌─────────────────────▼───────────────────────────────┐   │
│  │  Business Logic Adapter (Thin Wrapper)              │   │
│  │  - Input Validation & Transformation                │   │
│  │  - Error Handling & Retry Logic                     │   │
│  │  - Result Formatting & Caching                      │   │
│  └─────────────────────┬───────────────────────────────┘   │
└────────────────────────┼─────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              Existing Spock Modules (Reuse)                  │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ Data Providers   │  │ Backtest Engines │                │
│  │ - Postgres       │  │ - vectorbt       │                │
│  │ - Cache Layer    │  │ - Custom Engine  │                │
│  └──────────────────┘  └──────────────────┘                │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ Factor Library   │  │ Portfolio Opt    │                │
│  │ - Value          │  │ - Mean-Variance  │                │
│  │ - Momentum       │  │ - Risk Parity    │                │
│  └──────────────────┘  └──────────────────┘                │
└─────────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│           PostgreSQL + TimescaleDB Database                  │
│  - ohlcv_data (hypertable)                                   │
│  - ticker_fundamentals, technical_analysis                   │
│  - backtest_results, portfolio_holdings                      │
└─────────────────────────────────────────────────────────────┘
```

**레이어별 역할**:
1. **MCP SDK Layer**: MCP 프로토콜 처리 및 Tool 등록
2. **Tool Layer**: 8개 도구의 인터페이스 정의
3. **Adapter Layer**: 기존 모듈과의 통합 (Thin Wrapper)
4. **Modules Layer**: 비즈니스 로직 (100% 재사용)
5. **Database Layer**: 데이터 영속성

---

## 2. 설계 원칙

### 2.1 Thin Wrapper Pattern

**철학**: MCP 도구는 단순 어댑터, 비즈니스 로직은 기존 modules/ 재사용

```python
# ✅ 올바른 패턴 (25줄 이내)
@tool
async def query_ohlcv_data(...):
    # 1. Input Validation (5줄)
    validate_tickers(tickers)
    validate_date_range(start_date, end_date)

    # 2. Call Existing Module (5줄)
    adapter = DataAdapter()
    data = await adapter.get_ohlcv(...)

    # 3. Format Result (10줄)
    return format_ohlcv_response(data)

    # 4. Error Handling (5줄)
    except SpockMCPError as e:
        return error_response(e)
```

```python
# ❌ 잘못된 패턴 (100줄 이상)
@tool
async def query_ohlcv_data(...):
    # 여기서 SQL 쿼리 직접 작성
    # 여기서 데이터 처리 로직 구현
    # 여기서 캐싱 로직 구현
    # → 중복 코드, 유지보수 어려움
```

**Why Thin Wrapper?**
- ✅ CLI/WebUI도 같은 모듈 재사용 가능
- ✅ 테스트 간편 (단위 테스트는 modules/에만)
- ✅ 버그 수정이 전체 인터페이스에 적용
- ✅ MCP는 단순 프로토콜 번역기 역할

---

### 2.2 Performance First

**목표 응답 시간**:
| 작업 | 목표 | 전략 |
|------|------|------|
| OHLCV 조회 (단일) | <100ms | 캐싱 |
| OHLCV 조회 (100종목) | <500ms | 배치 처리 |
| Factor 조회 | <200ms | 사전 계산 + 캐싱 |
| 백테스트 (5년) | <2s | vectorbt |
| 포트폴리오 분석 | <300ms | 병렬 계산 |

**최적화 전략**:
1. **LRU 캐싱**: 자주 조회되는 데이터 메모리 저장
2. **배치 처리**: 100개 이상 종목은 자동 배치
3. **병렬 처리**: asyncio로 동시 요청 처리
4. **인덱싱**: PostgreSQL 인덱스 최적화

---

### 2.3 Error Resilience

**에러 처리 원칙**:
- **명확한 에러 메시지**: 사용자가 이해 가능한 설명
- **복구 전략**: Retry with exponential backoff
- **Circuit Breaker**: 반복 실패 시 빠른 실패
- **Graceful Degradation**: 부분 실패 시 가능한 결과 반환

---

### 2.4 Test-Driven Development

**테스트 전략**:
- **단위 테스트**: 각 Tool 독립 테스트 (>80% coverage)
- **통합 테스트**: Tool → Adapter → Module 흐름
- **E2E 테스트**: Claude Code → MCP → DB 전체 흐름
- **MCP 프로토콜 테스트**: MCP SDK 레벨 검증

---

## 3. 프로젝트 구조

```
~/spock/
├── mcp_server/                      # MCP 서버 루트
│   ├── __init__.py
│   ├── server.py                    # MCP 서버 진입점
│   ├── config.py                    # 환경 설정
│   ├── logging_config.py            # 로깅 설정
│   │
│   ├── tools/                       # MCP Tools (8개)
│   │   ├── __init__.py
│   │   ├── data_query.py            # Tools 1-3: 데이터 조회
│   │   │   ├── query_ohlcv_data()
│   │   │   ├── query_factor_scores()
│   │   │   └── query_technical_indicators()
│   │   │
│   │   ├── backtest.py              # Tools 4-5: 백테스트
│   │   │   ├── run_backtest()
│   │   │   └── optimize_strategy_params()
│   │   │
│   │   ├── portfolio.py             # Tools 6-7: 포트폴리오
│   │   │   ├── analyze_portfolio()
│   │   │   └── rebalance_portfolio()
│   │   │
│   │   └── system.py                # Tool 8: 시스템 상태
│   │       └── get_system_status()
│   │
│   ├── adapters/                    # Business Logic Adapter
│   │   ├── __init__.py
│   │   ├── data_adapter.py          # PostgresDataProvider wrapper
│   │   │   └── DataAdapter class
│   │   │
│   │   ├── backtest_adapter.py      # BacktestEngine wrapper
│   │   │   └── BacktestAdapter class
│   │   │
│   │   └── portfolio_adapter.py     # Optimizer wrapper
│   │       └── PortfolioAdapter class
│   │
│   ├── utils/                       # 공통 유틸리티
│   │   ├── __init__.py
│   │   ├── validators.py            # 입력 검증
│   │   │   ├── validate_tickers()
│   │   │   ├── validate_date_range()
│   │   │   └── validate_strategy_config()
│   │   │
│   │   ├── formatters.py            # 출력 포맷팅
│   │   │   ├── format_ohlcv_response()
│   │   │   ├── format_backtest_response()
│   │   │   └── format_portfolio_response()
│   │   │
│   │   ├── cache.py                 # 캐싱 로직
│   │   │   └── CacheManager class
│   │   │
│   │   └── errors.py                # 에러 정의
│   │       ├── SpockMCPError
│   │       ├── ValidationError
│   │       ├── DataNotFoundError
│   │       └── BacktestError
│   │
│   └── resources/                   # MCP Resources (선택적)
│       ├── __init__.py
│       ├── strategies.py            # 전략 정의
│       │   └── get_strategy_definition()
│       │
│       └── results.py               # 백테스트 결과
│           └── get_backtest_results()
│
├── tests/mcp_server/                # MCP 테스트
│   ├── test_data_query_tools.py     # Tool 1-3 테스트
│   ├── test_backtest_tools.py       # Tool 4-5 테스트
│   ├── test_portfolio_tools.py      # Tool 6-7 테스트
│   ├── test_system_tools.py         # Tool 8 테스트
│   ├── test_adapters.py             # Adapter 테스트
│   ├── test_validators.py           # Validator 테스트
│   ├── test_integration.py          # 통합 테스트
│   └── test_mcp_protocol.py         # MCP 프로토콜 테스트
│
├── pyproject.toml                   # 패키지 정의
└── docs/
    ├── MCP_DESIGN.md                # 이 문서
    ├── MCP_WORKFLOW.md              # 구현 워크플로우
    └── MCP_USER_GUIDE.md            # 사용 가이드
```

---

## 4. MCP Tools 상세 설계

### 4.1 Tool 1: query_ohlcv_data

**목적**: OHLCV 가격 데이터 조회

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "tickers": {
      "type": "array",
      "items": {"type": "string"},
      "description": "종목 코드 리스트 (예: ['005930', '000660'])"
    },
    "start_date": {
      "type": "string",
      "format": "date",
      "description": "조회 시작일 (YYYY-MM-DD)"
    },
    "end_date": {
      "type": "string",
      "format": "date",
      "description": "조회 종료일 (YYYY-MM-DD)"
    },
    "region": {
      "type": "string",
      "enum": ["KR", "US"],
      "default": "KR",
      "description": "시장 구분"
    },
    "timeframe": {
      "type": "string",
      "enum": ["1d", "1w", "1mo"],
      "default": "1d",
      "description": "봉 주기"
    }
  },
  "required": ["tickers", "start_date", "end_date"]
}
```

**Output Format**:
```json
{
  "success": true,
  "data": {
    "005930": [
      {
        "date": "2024-01-01",
        "open": 70000,
        "high": 71000,
        "low": 69500,
        "close": 70500,
        "volume": 10000000
      }
    ]
  },
  "metadata": {
    "query_time_ms": 45,
    "record_count": 250,
    "cache_hit": false
  }
}
```

**Implementation Pattern**:
```python
@tool
async def query_ohlcv_data(
    tickers: List[str],
    start_date: str,
    end_date: str,
    region: str = "KR",
    timeframe: str = "1d"
) -> List[TextContent]:
    """
    OHLCV 가격 데이터 조회

    Examples:
    - "삼성전자 최근 1년 일봉 데이터"
    - "KOSPI200 종목 2023년 월봉"
    """
    logger.info(
        "tool.query_ohlcv_data",
        tickers=tickers,
        date_range=f"{start_date} to {end_date}"
    )

    try:
        # 1. Validate inputs (5줄)
        validate_tickers(tickers, region)
        validate_date_range(start_date, end_date)

        # 2. Call existing module (5줄)
        adapter = DataAdapter()
        data = await adapter.get_ohlcv(
            tickers, start_date, end_date, region, timeframe
        )

        # 3. Format result (10줄)
        return [TextContent(
            type="text",
            text=format_ohlcv_response(data)
        )]

    except SpockMCPError as e:
        logger.error("tool.error", error=e.to_dict())
        return [TextContent(type="text", text=str(e.to_dict()))]
```

**Usage Examples**:
```
User → Claude: "삼성전자 최근 1년 일봉 데이터"
Claude → spock__query_ohlcv_data(
    tickers=["005930"],
    start_date="2024-01-01",
    end_date="2024-12-31"
)
```

**Performance Targets**:
- <100ms (캐시 적중)
- <500ms (DB 조회, 단일 종목)
- <2s (DB 조회, 100 종목)

**Error Handling**:
- `ValidationError`: 잘못된 ticker 형식, 날짜 범위
- `DataNotFoundError`: 데이터 없음
- `DatabaseError`: DB 연결 실패

---

### 4.2 Tool 2: query_factor_scores

**목적**: Factor 점수 조회 (Value, Momentum, Quality)

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "tickers": {
      "type": "array",
      "items": {"type": "string"},
      "description": "종목 코드 리스트"
    },
    "factors": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["value", "momentum", "quality", "low_vol", "size"]
      },
      "description": "조회할 팩터 유형"
    },
    "date": {
      "type": "string",
      "format": "date",
      "description": "기준일 (null이면 최신)"
    }
  },
  "required": ["tickers", "factors"]
}
```

**Output Format**:
```json
{
  "success": true,
  "data": {
    "005930": {
      "value": {
        "score": 85,
        "pe_ratio": 12.5,
        "pb_ratio": 1.2,
        "dividend_yield": 2.5,
        "percentile": 75
      },
      "momentum": {
        "score": 72,
        "return_12m": 0.15,
        "rsi": 68,
        "percentile": 65
      }
    }
  },
  "reference_date": "2024-01-15",
  "universe_size": 200
}
```

**Usage Examples**:
```
User: "삼성전자의 현재 Value, Momentum 점수"
→ query_factor_scores(["005930"], ["value", "momentum"])

User: "KOSPI200의 모든 팩터 점수 (2024-01-01)"
→ query_factor_scores([...], ["value", "momentum", "quality"], "2024-01-01")
```

**Performance Targets**:
- <200ms (캐시 적중)
- <1s (DB 조회 + 계산, 단일 종목)

---

### 4.3 Tool 3: query_technical_indicators

**목적**: 기술적 지표 조회 (RSI, MACD, Bollinger Bands)

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "tickers": {
      "type": "array",
      "items": {"type": "string"}
    },
    "indicators": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["rsi", "macd", "bbands", "sma", "ema"]
      }
    },
    "start_date": {"type": "string"},
    "end_date": {"type": "string"},
    "params": {
      "type": "object",
      "description": "지표별 파라미터 (예: rsi_period=14)"
    }
  },
  "required": ["tickers", "indicators", "start_date", "end_date"]
}
```

**Output Format**:
```json
{
  "success": true,
  "data": {
    "005930": {
      "rsi": [
        {"date": "2024-01-01", "value": 65.2}
      ],
      "macd": [
        {
          "date": "2024-01-01",
          "macd": 1.2,
          "signal": 0.8,
          "histogram": 0.4
        }
      ],
      "bbands": [
        {
          "date": "2024-01-01",
          "upper": 72000,
          "middle": 70000,
          "lower": 68000
        }
      ]
    }
  }
}
```

---

### 4.4 Tool 4: run_backtest

**목적**: 전략 백테스트 실행

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "strategy_config": {
      "type": "object",
      "properties": {
        "type": {
          "type": "string",
          "enum": ["momentum", "value", "multi_factor", "custom"]
        },
        "params": {
          "type": "object",
          "description": "전략별 파라미터"
        },
        "universe": {
          "type": "array",
          "items": {"type": "string"},
          "description": "투자 유니버스"
        },
        "rebalance_frequency": {
          "type": "string",
          "enum": ["daily", "weekly", "monthly", "quarterly"]
        }
      }
    },
    "start_date": {"type": "string"},
    "end_date": {"type": "string"},
    "engine": {
      "type": "string",
      "enum": ["vectorbt", "custom"],
      "default": "vectorbt"
    },
    "initial_cash": {
      "type": "number",
      "default": 10000000
    }
  },
  "required": ["strategy_config", "start_date", "end_date"]
}
```

**Output Format**:
```json
{
  "success": true,
  "backtest_id": "bt_20240115_abc123",
  "performance": {
    "total_return": 0.182,
    "cagr": 0.165,
    "sharpe_ratio": 1.65,
    "max_drawdown": -0.223,
    "win_rate": 0.583,
    "profit_factor": 1.85,
    "volatility": 0.142
  },
  "trades": {
    "total_trades": 125,
    "avg_holding_period_days": 45,
    "largest_win": 0.15,
    "largest_loss": -0.08
  },
  "portfolio_curve": [
    {"date": "2020-01-01", "value": 10000000},
    {"date": "2020-01-02", "value": 10050000}
  ],
  "monthly_returns": [
    {"month": "2020-01", "return": 0.05}
  ]
}
```

**Usage Examples**:
```
User: "Momentum 전략 2020-2023 백테스트"
→ run_backtest({
    strategy_config: {
        type: "momentum",
        universe: ["005930", "000660"],
        params: {"lookback_period": 120}
    },
    start_date: "2020-01-01",
    end_date: "2023-12-31"
})

User: "Value+Momentum 멀티팩터 성과 분석"
→ run_backtest({
    strategy_config: {
        type: "multi_factor",
        params: {
            factors: ["value", "momentum"],
            weights: [0.5, 0.5]
        }
    }
})
```

**Performance Targets**:
- <2s (5년 백테스트, vectorbt)
- <30s (5년 백테스트, custom engine)

---

### 4.5 Tool 5: optimize_strategy_params

**목적**: 전략 파라미터 최적화 (Walk-Forward)

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "strategy_type": {
      "type": "string",
      "enum": ["momentum", "value", "multi_factor"]
    },
    "param_ranges": {
      "type": "object",
      "description": "파라미터 탐색 범위",
      "example": {
        "lookback_period": [60, 120, 180, 252],
        "top_n": [10, 20, 30]
      }
    },
    "optimization_metric": {
      "type": "string",
      "enum": ["sharpe_ratio", "cagr", "calmar_ratio"],
      "default": "sharpe_ratio"
    },
    "walk_forward": {
      "type": "boolean",
      "default": true,
      "description": "Walk-forward 검증 활성화"
    },
    "train_test_split": {
      "type": "number",
      "default": 0.7,
      "description": "학습/테스트 데이터 비율"
    }
  },
  "required": ["strategy_type", "param_ranges"]
}
```

**Output Format**:
```json
{
  "success": true,
  "best_params": {
    "lookback_period": 120,
    "top_n": 20
  },
  "in_sample_sharpe": 1.85,
  "out_of_sample_sharpe": 1.42,
  "overfitting_score": 0.23,
  "optimization_results": [
    {
      "params": {"lookback_period": 60, "top_n": 10},
      "in_sample_sharpe": 1.25,
      "out_of_sample_sharpe": 0.95
    },
    {
      "params": {"lookback_period": 120, "top_n": 20},
      "in_sample_sharpe": 1.85,
      "out_of_sample_sharpe": 1.42
    }
  ],
  "walk_forward_windows": 25
}
```

---

### 4.6 Tool 6: analyze_portfolio

**목적**: 포트폴리오 리스크/성과 분석

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "holdings": {
      "type": "object",
      "description": "보유 종목 및 비중",
      "example": {
        "005930": 0.25,
        "000660": 0.20,
        "035420": 0.15
      }
    },
    "date": {
      "type": "string",
      "format": "date",
      "description": "분석 기준일 (null이면 현재)"
    },
    "risk_metrics": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["var", "cvar", "volatility", "beta", "correlation"]
      },
      "default": ["var", "cvar", "volatility"]
    }
  },
  "required": ["holdings"]
}
```

**Output Format**:
```json
{
  "success": true,
  "risk_metrics": {
    "portfolio_var_95": 0.062,
    "portfolio_cvar_95": 0.089,
    "annualized_volatility": 0.185,
    "beta_kospi": 1.15
  },
  "factor_exposures": {
    "value": 0.45,
    "momentum": 0.32,
    "quality": 0.28,
    "low_vol": -0.15
  },
  "sector_allocation": {
    "IT": 0.52,
    "Finance": 0.25,
    "Consumer": 0.23
  },
  "concentration_risk": {
    "top_3_weight": 0.58,
    "herfindahl_index": 0.15
  },
  "correlation_matrix": {
    "005930": {"000660": 0.45, "035420": 0.38}
  },
  "warnings": [
    "⚠️ Portfolio VaR (6.2%) exceeds target (<5%)",
    "⚠️ IT sector concentration (52%) exceeds limit (<40%)",
    "⚠️ Top 3 holdings (58%) too concentrated"
  ]
}
```

**Performance Targets**:
- <300ms (10 종목 포트폴리오)
- <1s (100 종목 포트폴리오)

---

### 4.7 Tool 7: rebalance_portfolio

**목적**: 포트폴리오 리밸런싱 추천

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "current_holdings": {
      "type": "object",
      "description": "현재 보유 종목 및 비중"
    },
    "target_method": {
      "type": "string",
      "enum": ["mean_variance", "risk_parity", "kelly", "equal_weight"],
      "description": "최적화 방법"
    },
    "constraints": {
      "type": "object",
      "properties": {
        "max_position_weight": {"type": "number", "default": 0.15},
        "max_sector_weight": {"type": "number", "default": 0.4},
        "max_turnover": {"type": "number", "default": 0.5},
        "min_cash_reserve": {"type": "number", "default": 0.05}
      }
    },
    "universe": {
      "type": "array",
      "items": {"type": "string"},
      "description": "투자 가능 종목 (null이면 현재 보유 종목)"
    }
  },
  "required": ["current_holdings", "target_method"]
}
```

**Output Format**:
```json
{
  "success": true,
  "target_weights": {
    "005930": 0.15,
    "000660": 0.15,
    "035420": 0.12,
    "051910": 0.10,
    "cash": 0.05
  },
  "trades": [
    {"ticker": "005930", "action": "sell", "amount": -0.10, "reason": "Reduce concentration"},
    {"ticker": "035420", "action": "buy", "amount": 0.05, "reason": "Diversification"},
    {"ticker": "051910", "action": "buy", "amount": 0.10, "reason": "Add new position"}
  ],
  "expected_improvement": {
    "current_sharpe": 1.42,
    "target_sharpe": 1.58,
    "current_var": 0.062,
    "target_var": 0.048,
    "current_volatility": 0.185,
    "target_volatility": 0.168
  },
  "transaction_cost_estimate": 0.0012,
  "implementation_notes": [
    "Reduces IT sector from 52% to 38%",
    "Improves diversification (HHI: 0.15 → 0.11)",
    "Expected to reduce VaR by 22%"
  ]
}
```

---

### 4.8 Tool 8: get_system_status

**목적**: 시스템 상태 확인

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "check_components": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["database", "cache", "data_freshness", "backtest_history"]
      },
      "default": ["database", "data_freshness"]
    }
  }
}
```

**Output Format**:
```json
{
  "success": true,
  "database": {
    "status": "healthy",
    "connection_time_ms": 12,
    "total_records": 1369467,
    "last_update": "2024-01-15 09:00:00",
    "disk_usage_gb": 2.5
  },
  "cache": {
    "status": "healthy",
    "hit_rate": 0.87,
    "size_mb": 245,
    "evictions_last_hour": 12
  },
  "data_freshness": {
    "kr_market": {
      "latest_date": "2024-01-15",
      "delay_days": 0,
      "status": "up_to_date"
    },
    "us_market": {
      "latest_date": "2024-01-14",
      "delay_days": 1,
      "status": "acceptable"
    }
  },
  "backtest_history": {
    "total_backtests": 1250,
    "last_7_days": 45,
    "avg_duration_seconds": 1.8
  }
}
```

---

## 5. Adapter Layer 설계

### 5.1 DataAdapter

**목적**: PostgresDataProvider wrapper

```python
# mcp_server/adapters/data_adapter.py
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from typing import List, Dict
import pandas as pd
from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider
from ..utils.errors import DataNotFoundError
import structlog

logger = structlog.get_logger()

class DataAdapter:
    """Adapter for data providers"""

    def __init__(self):
        self.provider = PostgresDataProvider()
        self.cache = {}  # Simple in-memory cache

    async def get_ohlcv(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        region: str = "KR",
        timeframe: str = "1d"
    ) -> Dict[str, List[Dict]]:
        """Get OHLCV data with caching"""
        logger.info(
            "data_adapter.get_ohlcv",
            tickers=tickers,
            start_date=start_date,
            end_date=end_date
        )

        # Check cache
        cache_key = self._make_cache_key(tickers, start_date, end_date, timeframe)
        if cache_key in self.cache:
            logger.info("data_adapter.cache_hit")
            return self.cache[cache_key]

        # Call existing module
        data = self.provider.get_ohlcv(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            region=region,
            timeframe=timeframe
        )

        if data.empty:
            raise DataNotFoundError(
                "No data found for specified criteria",
                {"tickers": tickers, "date_range": f"{start_date} to {end_date}"}
            )

        # Format as dict
        result = {}
        for ticker in tickers:
            ticker_data = data[data['ticker'] == ticker]
            if not ticker_data.empty:
                result[ticker] = ticker_data.to_dict('records')

        # Cache result
        self.cache[cache_key] = result

        return result

    def _make_cache_key(self, tickers, start_date, end_date, timeframe):
        """Generate cache key"""
        return f"ohlcv:{','.join(sorted(tickers))}:{start_date}:{end_date}:{timeframe}"
```

---

### 5.2 BacktestAdapter

**목적**: BacktestEngine wrapper

```python
# mcp_server/adapters/backtest_adapter.py
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from typing import Dict
from modules.backtesting.backtest_engines.vectorbt_adapter import VectorbtAdapter
from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider
from ..utils.errors import BacktestError
import structlog

logger = structlog.get_logger()

class BacktestAdapter:
    """Adapter for backtest engines"""

    def __init__(self):
        self.data_provider = PostgresDataProvider()
        self.vectorbt_adapter = VectorbtAdapter()

    async def run_backtest(
        self,
        strategy_config: Dict,
        start_date: str,
        end_date: str,
        engine: str = "vectorbt",
        initial_cash: float = 10000000
    ) -> Dict:
        """Run backtest"""
        logger.info(
            "backtest_adapter.run",
            strategy=strategy_config.get("type"),
            date_range=f"{start_date} to {end_date}",
            engine=engine
        )

        try:
            # 1. Load data
            universe = strategy_config.get("universe", [])
            data = self.data_provider.get_ohlcv(
                tickers=universe,
                start_date=start_date,
                end_date=end_date
            )

            # 2. Run backtest
            if engine == "vectorbt":
                results = self.vectorbt_adapter.run_backtest(
                    strategy=strategy_config,
                    data=data,
                    start_date=start_date,
                    end_date=end_date,
                    initial_cash=initial_cash
                )
            else:
                raise BacktestError(f"Unsupported engine: {engine}")

            # 3. Generate backtest ID
            backtest_id = self._generate_backtest_id(strategy_config, start_date, end_date)

            # 4. Save results to DB (optional)
            # self._save_backtest_results(backtest_id, results)

            # 5. Format results
            return {
                "success": True,
                "backtest_id": backtest_id,
                "performance": results["performance"],
                "trades": results["trades"],
                "portfolio_curve": results.get("portfolio_curve", [])
            }

        except Exception as e:
            logger.error("backtest_adapter.error", error=str(e))
            raise BacktestError(f"Backtest failed: {e}")

    def _generate_backtest_id(self, strategy_config, start_date, end_date):
        """Generate unique backtest ID"""
        import hashlib
        hash_input = f"{strategy_config}{start_date}{end_date}"
        hash_suffix = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        return f"bt_{start_date}_{end_date}_{hash_suffix}"
```

---

### 5.3 PortfolioAdapter

**목적**: Portfolio Optimizer wrapper

```python
# mcp_server/adapters/portfolio_adapter.py
from typing import Dict, List
from ..utils.errors import SpockMCPError
import structlog

logger = structlog.get_logger()

class PortfolioAdapter:
    """Adapter for portfolio optimization"""

    def __init__(self):
        # TODO: Import portfolio optimizer modules
        pass

    async def analyze_portfolio(
        self,
        holdings: Dict[str, float],
        date: str = None,
        risk_metrics: List[str] = None
    ) -> Dict:
        """Analyze portfolio risk and performance"""
        logger.info("portfolio_adapter.analyze", holdings=holdings)

        # TODO: Implement using modules/optimization/
        # - Calculate VaR, CVaR
        # - Factor exposures
        # - Sector allocation
        # - Correlation matrix

        return {
            "risk_metrics": {},
            "factor_exposures": {},
            "warnings": []
        }

    async def rebalance_portfolio(
        self,
        current_holdings: Dict[str, float],
        target_method: str,
        constraints: Dict = None
    ) -> Dict:
        """Generate rebalancing recommendations"""
        logger.info("portfolio_adapter.rebalance", method=target_method)

        # TODO: Implement using modules/optimization/
        # - Mean-Variance optimization
        # - Risk Parity
        # - Kelly Criterion

        return {
            "target_weights": {},
            "trades": [],
            "expected_improvement": {}
        }
```

---

## 6. Utils 및 공통 컴포넌트

### 6.1 Config Management

```python
# mcp_server/config.py
import os
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass
class Config:
    """MCP Server Configuration"""

    # Database
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str

    # Performance
    cache_max_size_mb: int = 500
    cache_ttl_seconds: int = 3600
    batch_size: int = 100

    # Logging
    log_level: str = "INFO"
    log_dir: str = "logs"

    # Security (Phase 2)
    api_key: str = None
    rate_limit_per_minute: int = 60

    @classmethod
    def from_env(cls):
        """Load config from environment"""
        load_dotenv()
        return cls(
            postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
            postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
            postgres_db=os.getenv("POSTGRES_DB", "quant_platform"),
            postgres_user=os.getenv("POSTGRES_USER", "bruce"),
            postgres_password=os.getenv("POSTGRES_PASSWORD", ""),
            cache_max_size_mb=int(os.getenv("CACHE_MAX_SIZE_MB", "500")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            # api_key=os.getenv("SPOCK_MCP_API_KEY")
        )
```

---

### 6.2 Validators

```python
# mcp_server/utils/validators.py
import re
from datetime import datetime
from typing import List, Dict
from .errors import ValidationError

def validate_tickers(tickers: List[str], region: str = "KR") -> None:
    """Validate ticker symbols"""
    if not tickers:
        raise ValidationError("Ticker list cannot be empty")

    if len(tickers) > 1000:
        raise ValidationError("Ticker list too large (max 1000)")

    if region == "KR":
        # KR: 6-digit numeric
        pattern = re.compile(r'^\d{6}$')
        for ticker in tickers:
            if not pattern.match(ticker):
                raise ValidationError(
                    f"Invalid KR ticker: {ticker}",
                    {"ticker": ticker, "expected_format": "6-digit numeric"}
                )
    elif region == "US":
        # US: 1-5 uppercase letters
        pattern = re.compile(r'^[A-Z]{1,5}$')
        for ticker in tickers:
            if not pattern.match(ticker):
                raise ValidationError(
                    f"Invalid US ticker: {ticker}",
                    {"ticker": ticker, "expected_format": "1-5 uppercase letters"}
                )

def validate_date_range(start_date: str, end_date: str) -> None:
    """Validate date range"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        raise ValidationError(f"Invalid date format: {e}")

    if start >= end:
        raise ValidationError("start_date must be before end_date")

    # 최대 10년 제한
    if (end - start).days > 3650:
        raise ValidationError("Date range cannot exceed 10 years")

def validate_strategy_config(config: Dict) -> None:
    """Validate strategy configuration"""
    required_fields = ["type", "universe"]
    for field in required_fields:
        if field not in config:
            raise ValidationError(f"Missing required field: {field}")

    if config["type"] not in ["momentum", "value", "multi_factor", "custom"]:
        raise ValidationError(f"Invalid strategy type: {config['type']}")

    if not config.get("universe"):
        raise ValidationError("Universe cannot be empty")
```

---

### 6.3 Error Definitions

```python
# mcp_server/utils/errors.py
from typing import Dict, Optional

class SpockMCPError(Exception):
    """Base exception for all MCP errors"""

    def __init__(self, code: str, message: str, details: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self):
        return {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details
            }
        }

class ValidationError(SpockMCPError):
    """Input validation failed"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__("VALIDATION_ERROR", message, details)

class DataNotFoundError(SpockMCPError):
    """Requested data not available"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__("DATA_NOT_FOUND", message, details)

class BacktestError(SpockMCPError):
    """Backtest execution failed"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__("BACKTEST_ERROR", message, details)

class DatabaseError(SpockMCPError):
    """Database operation failed"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__("DATABASE_ERROR", message, details)

class PortfolioError(SpockMCPError):
    """Portfolio operation failed"""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__("PORTFOLIO_ERROR", message, details)
```

---

### 6.4 Cache Manager

```python
# mcp_server/utils/cache.py
from typing import Any, Optional
import time
from collections import OrderedDict

class CacheManager:
    """LRU Cache Manager"""

    def __init__(self, max_size_mb: int = 500, ttl_seconds: int = 3600):
        self.max_size = max_size_mb * 1024 * 1024  # Convert to bytes
        self.ttl = ttl_seconds
        self.cache = OrderedDict()
        self.timestamps = {}
        self.current_size = 0

    def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        if key not in self.cache:
            return None

        # Check TTL
        if time.time() - self.timestamps[key] > self.ttl:
            self._evict(key)
            return None

        # Move to end (LRU)
        self.cache.move_to_end(key)
        return self.cache[key]

    def set(self, key: str, value: Any) -> None:
        """Set cache value"""
        # Estimate size (simplified)
        value_size = len(str(value).encode('utf-8'))

        # Evict if needed
        while self.current_size + value_size > self.max_size and self.cache:
            oldest_key = next(iter(self.cache))
            self._evict(oldest_key)

        # Add to cache
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            self.cache[key] = value
            self.timestamps[key] = time.time()
            self.current_size += value_size

    def _evict(self, key: str) -> None:
        """Evict key from cache"""
        if key in self.cache:
            value_size = len(str(self.cache[key]).encode('utf-8'))
            del self.cache[key]
            del self.timestamps[key]
            self.current_size -= value_size

    def clear(self) -> None:
        """Clear entire cache"""
        self.cache.clear()
        self.timestamps.clear()
        self.current_size = 0

    def stats(self) -> dict:
        """Get cache statistics"""
        return {
            "size_mb": self.current_size / (1024 * 1024),
            "items": len(self.cache),
            "max_size_mb": self.max_size / (1024 * 1024)
        }
```

---

## 7. 에러 처리 전략

### 7.1 에러 응답 포맷

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid ticker symbol",
    "details": {
      "ticker": "INVALID",
      "valid_format": "6-digit numeric for KR market"
    }
  }
}
```

### 7.2 Retry Logic

```python
async def with_retry(
    func,
    max_retries: int = 3,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Retry with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return await func()
        except exceptions as e:
            if attempt == max_retries - 1:
                raise

            wait_time = backoff ** attempt
            logger.warning(
                "retry.attempt",
                attempt=attempt + 1,
                wait_time=wait_time,
                error=str(e)
            )
            await asyncio.sleep(wait_time)
```

### 7.3 Circuit Breaker

```python
class CircuitBreaker:
    """Circuit breaker pattern"""

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open

    async def call(self, func):
        """Call function with circuit breaker"""
        if self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half_open"
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = await func()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful call"""
        self.failures = 0
        self.state = "closed"

    def _on_failure(self):
        """Handle failed call"""
        self.failures += 1
        self.last_failure_time = time.time()

        if self.failures >= self.failure_threshold:
            self.state = "open"
```

---

## 8. 성능 최적화

### 8.1 배치 처리

```python
async def query_ohlcv_data_batch(
    tickers: List[str],
    start_date: str,
    end_date: str,
    batch_size: int = 100
) -> Dict:
    """Batch processing for large ticker lists"""
    if len(tickers) <= batch_size:
        return await _query_single_batch(tickers, start_date, end_date)

    # Split into batches
    batches = [tickers[i:i+batch_size] for i in range(0, len(tickers), batch_size)]

    # Process in parallel
    results = await asyncio.gather(*[
        _query_single_batch(batch, start_date, end_date)
        for batch in batches
    ])

    # Merge results
    merged = {}
    for result in results:
        merged.update(result)

    return merged
```

### 8.2 성능 목표

| 작업 | 목표 응답 시간 | 최적화 전략 |
|------|----------------|-------------|
| OHLCV 조회 (단일 종목) | <100ms | LRU 캐싱 |
| OHLCV 조회 (100 종목) | <500ms | 배치 처리 + 병렬 |
| Factor 조회 | <200ms | 사전 계산 + 캐싱 |
| 백테스트 (5년) | <2s | vectorbt 엔진 |
| 포트폴리오 분석 | <300ms | 병렬 계산 |

---

## 9. 보안 설계

### 9.1 API 인증 (Phase 2)

```python
class AuthMiddleware:
    """API Key authentication"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def authenticate(self, request_api_key: str) -> bool:
        """Verify API key"""
        return request_api_key == self.api_key
```

### 9.2 Rate Limiting (Phase 2)

```python
class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(self, max_requests_per_minute: int = 60):
        self.max_requests = max_requests_per_minute
        self.tokens = max_requests_per_minute
        self.last_refill = time.time()

    async def acquire(self) -> bool:
        """Acquire rate limit token"""
        self._refill()

        if self.tokens > 0:
            self.tokens -= 1
            return True

        return False

    def _refill(self):
        """Refill tokens"""
        now = time.time()
        elapsed = now - self.last_refill

        tokens_to_add = elapsed * (self.max_requests / 60)
        self.tokens = min(self.max_requests, self.tokens + tokens_to_add)
        self.last_refill = now
```

---

## 부록: 성능 벤치마크

### A.1 목표 성능 지표

| 메트릭 | Phase 1 목표 | Phase 2 목표 | Phase 3 목표 |
|--------|--------------|--------------|--------------|
| OHLCV 조회 (캐시) | <100ms | <50ms | <20ms |
| OHLCV 조회 (DB) | <500ms | <300ms | <200ms |
| 백테스트 (5년) | <2s | <1s | <1s |
| 캐시 적중률 | >70% | >80% | >90% |
| 동시 요청 처리 | 5 req/s | 10 req/s | 20 req/s |

---

**문서 작성일**: 2025-10-30
**문서 버전**: 1.0.0
**작성자**: Claude (Spock Team)
