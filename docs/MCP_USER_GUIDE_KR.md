# Spock MCP 서버 - 사용자 가이드

**버전**: 0.2.0
**날짜**: 2025-10-31
**상태**: Phase 1 Week 2 완료

---

## 목차

1. [빠른 시작](#빠른-시작)
2. [설정](#설정)
3. [사용 가능한 도구](#사용-가능한-도구)
4. [사용 예제](#사용-예제)
5. [오류 처리](#오류-처리)
6. [성능](#성능)
7. [문제 해결](#문제-해결)

---

## 빠른 시작

### 필수 조건

- Python 3.11+
- TimescaleDB 확장이 설치된 PostgreSQL 17+
- Claude Code 설치 및 설정 완료
- Spock 프로젝트 환경 설정 완료

### 설치

1. **의존성 설치**:
```bash
cd ~/spock
pip install -r requirements_quant.txt
```

2. **환경 설정**:
```bash
# 데이터베이스 자격 증명이 포함된 .env 파일 생성
cp .env.example .env
# PostgreSQL 자격 증명으로 .env 편집
```

3. **설치 확인**:
```bash
python3 -m mcp_server.server
# 오류 없이 초기화되어야 함
```

---

## 설정

### MCP 서버 설정

Spock MCP 서버는 `.claude/mcp_config.json`을 통해 설정됩니다:

```json
{
  "mcpServers": {
    "spock": {
      "command": "python3",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/Users/13ruce/spock",
      "env": {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "quant_platform",
        "POSTGRES_USER": "bruce"
      }
    }
  }
}
```

### 설정 매개변수

| 매개변수 | 설명 | 기본값 |
|---------|------|--------|
| `command` | Python 인터프리터 | `python3` |
| `args` | 서버 모듈 경로 | `["-m", "mcp_server.server"]` |
| `cwd` | 작업 디렉토리 | `/Users/13ruce/spock` |
| `env.POSTGRES_HOST` | PostgreSQL 호스트 | `localhost` |
| `env.POSTGRES_PORT` | PostgreSQL 포트 | `5432` |
| `env.POSTGRES_DB` | 데이터베이스 이름 | `quant_platform` |
| `env.POSTGRES_USER` | 데이터베이스 사용자 | `bruce` |

**참고**: 보안을 위해 PostgreSQL 비밀번호는 MCP 설정이 아닌 `.env` 파일에 저장해야 합니다.

---

## 사용 가능한 도구

### query_ohlcv_data

주식 종목의 OHLCV (Open-High-Low-Close-Volume: 시가, 고가, 저가, 종가, 거래량) 과거 데이터를 조회합니다.

**용어 설명**:
- **OHLCV**: 주식 거래의 기본 정보를 나타내는 5가지 지표
  - **시가 (Open)**: 해당 기간의 첫 거래 가격
  - **고가 (High)**: 해당 기간의 최고 거래 가격
  - **저가 (Low)**: 해당 기간의 최저 거래 가격
  - **종가 (Close)**: 해당 기간의 마지막 거래 가격
  - **거래량 (Volume)**: 해당 기간 동안 거래된 총 주식 수

**함수 시그니처**:
```typescript
query_ohlcv_data(
  tickers: string[],      // 1-1000개의 종목 코드
  start_date: string,     // YYYY-MM-DD 형식
  end_date: string,       // YYYY-MM-DD 형식
  region?: "KR" | "US",   // 시장 지역 (기본값: "KR")
  timeframe?: "1d"        // 데이터 기간 (기본값: "1d")
): Promise<OHLCVResponse>
```

**입력 매개변수**:

| 매개변수 | 타입 | 필수 | 검증 | 설명 |
|---------|------|------|------|------|
| `tickers` | `string[]` | ✅ 예 | 1-1000개 항목 | 종목 코드 |
| `start_date` | `string` | ✅ 예 | YYYY-MM-DD | 시작 날짜 (포함) |
| `end_date` | `string` | ✅ 예 | YYYY-MM-DD | 종료 날짜 (포함) |
| `region` | `string` | 아니오 | "KR" \| "US" | 시장 지역 |
| `timeframe` | `string` | 아니오 | "1d" | 데이터 기간 |

**종목 코드 형식 검증**:
- **KR (한국)**: 6자리 숫자 (예: 삼성전자의 경우 `005930`)
- **US (미국)**: 1-5자 대문자 (예: Apple Inc.의 경우 `AAPL`)

**날짜 범위 검증**:
- 형식: `YYYY-MM-DD` (ISO 8601)
- 시작 날짜는 종료 날짜보다 앞서야 함
- 최대 범위: 10년 (3650일)
- 윤년 올바르게 처리

**출력 형식**:
```json
{
  "success": true,
  "data": {
    "005930": [
      {
        "date": "2024-01-01",
        "open": 75000,
        "high": 76000,
        "low": 74000,
        "close": 75500,
        "volume": 1000000
      },
      ...
    ]
  },
  "metadata": {
    "record_count": 245,
    "tickers": ["005930"]
  }
}
```

### run_backtest

vectorbt 또는 커스텀 엔진으로 전략 백테스트를 실행합니다.

**용어 설명**:
- **백테스트 (Backtest)**: 과거 데이터를 사용하여 투자 전략의 성과를 시뮬레이션하는 기법. 실제 자본을 투자하기 전에 전략의 유효성을 검증할 수 있습니다.
- **vectorbt**: 고속 백테스트를 위한 Python 라이브러리. NumPy 벡터화를 활용하여 일반 백테스트 엔진보다 100배 빠른 성능을 제공합니다.
- **샤프 비율 (Sharpe Ratio)**: 위험 대비 수익률을 측정하는 지표. 높을수록 위험 조정 수익률이 좋습니다 (1.5 이상이 우수).
- **최대 낙폭 (Max Drawdown)**: 최고점에서 최저점까지의 최대 하락률. 전략의 최악의 손실을 나타냅니다.
- **승률 (Win Rate)**: 전체 거래 중 수익을 낸 거래의 비율

**함수 시그니처**:
```typescript
run_backtest(
  strategy_type: "momentum" | "value" | "momentum_value",
  tickers: string[],          // 1-100개의 종목 코드
  start_date: string,         // YYYY-MM-DD 형식
  end_date: string,           // YYYY-MM-DD 형식
  region?: "KR" | "US",       // 시장 지역 (기본값: "KR")
  engine?: "vectorbt" | "custom",  // 엔진 (기본값: "vectorbt")
  initial_capital?: number,   // 초기 자본 (기본값: 1억 원)
  risk_profile?: "conservative" | "moderate" | "aggressive"
): Promise<BacktestResponse>
```

**입력 매개변수**:

| 매개변수 | 타입 | 필수 | 검증 | 설명 |
|---------|------|------|------|------|
| `strategy_type` | `string` | ✅ 예 | momentum \| value \| momentum_value | 백테스트할 전략 |
| `tickers` | `string[]` | ✅ 예 | 1-100개 항목 | 종목 코드 |
| `start_date` | `string` | ✅ 예 | YYYY-MM-DD | 시작 날짜 (포함) |
| `end_date` | `string` | ✅ 예 | YYYY-MM-DD | 종료 날짜 (포함) |
| `region` | `string` | 아니오 | KR \| US | 시장 지역 (기본값: KR) |
| `engine` | `string` | 아니오 | vectorbt \| custom | 백테스트 엔진 (기본값: vectorbt) |
| `initial_capital` | `number` | 아니오 | ≥1M | 초기 자본 (기본값: 1억 원) |
| `risk_profile` | `string` | 아니오 | conservative \| moderate \| aggressive | 위험 프로파일 (기본값: moderate) |

**출력 형식**:
```json
{
  "success": true,
  "engine": "vectorbt",
  "performance": {
    "total_return": 0.45,
    "annualized_return": 0.35,
    "sharpe_ratio": 1.65,
    "sortino_ratio": 2.10,
    "calmar_ratio": 1.85,
    "max_drawdown": -0.12,
    "max_drawdown_duration": 45
  },
  "trades": {
    "total_trades": 125,
    "win_rate": 0.583,
    "avg_win": 0.048,
    "avg_loss": -0.032,
    "profit_factor": 1.85
  },
  "execution": {
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "duration_days": 365,
    "initial_capital": 100000000,
    "execution_time": 0.85
  }
}
```

### optimize_strategy

워크포워드 최적화를 실행하여 최적의 전략 매개변수를 찾습니다.

**용어 설명**:
- **워크포워드 최적화 (Walk-Forward Optimization)**: 시계열 데이터를 학습 기간과 테스트 기간으로 나누어 롤링하면서 매개변수를 최적화하는 기법. 과적합을 방지하고 실제 시장에서의 성과를 더 정확하게 예측할 수 있습니다.
- **과적합 (Overfitting)**: 전략이 과거 데이터에는 잘 맞지만 미래 데이터에는 성과가 떨어지는 현상. 학습 데이터에 과도하게 최적화되어 일반화 능력이 떨어집니다.
- **강건성 점수 (Robustness Score)**: 전략의 안정성을 측정하는 지표. 학습 기간과 테스트 기간의 성과 차이를 평가하며, 0.7 이상이면 우수한 전략입니다.
- **매개변수 그리드 (Parameter Grid)**: 최적화할 매개변수들의 후보 값 조합. 예: RSI 기간 [10, 14, 20], 과매도 [20, 30]
- **모멘텀 전략 (Momentum Strategy)**: 최근 가격 상승 추세를 보이는 종목을 매수하는 전략. RSI, 이동평균 등의 지표를 활용합니다.
- **가치 전략 (Value Strategy)**: 저평가된 종목을 찾아 매수하는 전략. PER, PBR 등의 재무 지표를 활용합니다.

**함수 시그니처**:
```typescript
optimize_strategy(
  strategy_type: "momentum" | "value" | "momentum_value",
  tickers: string[],          // 1-100개의 종목 코드
  start_date: string,         // YYYY-MM-DD 형식
  end_date: string,           // YYYY-MM-DD 형식
  region?: "KR" | "US",       // 시장 지역 (기본값: "KR")
  param_grid?: object,        // 매개변수 그리드 (선택)
  train_period_days?: number, // 학습 기간 (기본값: 252)
  test_period_days?: number,  // 테스트 기간 (기본값: 63)
  metric?: string,            // 최적화 지표 (기본값: "sharpe_ratio")
  anchored?: boolean          // 고정 윈도우 (기본값: false)
): Promise<OptimizationResponse>
```

**입력 매개변수**:

| 매개변수 | 타입 | 필수 | 검증 | 설명 |
|---------|------|------|------|------|
| `strategy_type` | `string` | ✅ 예 | momentum \| value \| momentum_value | 최적화할 전략 |
| `tickers` | `string[]` | ✅ 예 | 1-100개 항목 | 종목 코드 |
| `start_date` | `string` | ✅ 예 | YYYY-MM-DD | 시작 날짜 (포함) |
| `end_date` | `string` | ✅ 예 | YYYY-MM-DD | 종료 날짜 (포함) |
| `region` | `string` | 아니오 | KR \| US | 시장 지역 (기본값: KR) |
| `param_grid` | `object` | 아니오 | Dict[str, List] | 탐색할 매개변수 |
| `train_period_days` | `number` | 아니오 | 30-1825 | 학습 기간 (기본값: 252) |
| `test_period_days` | `number` | 아니오 | 10-365 | 테스트 기간 (기본값: 63) |
| `metric` | `string` | 아니오 | sharpe_ratio \| sortino_ratio \| total_return \| annualized_return \| calmar_ratio | 최적화 지표 |
| `anchored` | `boolean` | 아니오 | true \| false | 고정 윈도우 사용 (기본값: false) |

**기본 매개변수 그리드**:
- **모멘텀**: `{"rsi_period": [10, 14, 20], "oversold": [20, 30], "overbought": [70, 80]}`
- **가치**: `{"pe_threshold": [10, 15, 20], "pb_threshold": [1.0, 1.5, 2.0]}`
- **모멘텀+가치**: 두 그리드의 조합

**출력 형식**:
```json
{
  "success": true,
  "strategy_type": "momentum",
  "optimization": {
    "best_params": {
      "rsi_period": 14,
      "oversold": 30,
      "overbought": 70
    },
    "metric_used": "sharpe_ratio"
  },
  "validation": {
    "in_sample_performance": {
      "mean": 1.85,
      "std": 0.15,
      "min": 1.65,
      "max": 2.05
    },
    "out_of_sample_performance": {
      "mean": 1.65,
      "std": 0.22,
      "min": 1.42,
      "max": 1.88
    },
    "degradation_pct": 0.108,
    "robustness_score": 0.78,
    "overfitting_detected": false,
    "recommendation": "좋음: 강건성 점수 0.78, 배포를 권장하는 전략입니다"
  }
}
```

### list_available_tickers

데이터베이스에서 사용 가능한 모든 종목 코드를 나열합니다.

**용어 설명**:
- **종목 코드 (Ticker)**: 주식 종목을 고유하게 식별하는 코드. 한국 시장은 6자리 숫자(예: 005930), 미국 시장은 알파벳 코드(예: AAPL)를 사용합니다.
- **지역 (Region)**: 시장 지역을 나타내는 코드. KR(한국 시장), US(미국 시장)
- **섹터 (Sector)**: 산업 분류. 예: IT, 금융, 제조업, 헬스케어 등

**함수 시그니처**:
```typescript
list_available_tickers(
  region?: "KR" | "US",       // 지역별 필터 (선택)
  sector?: string,            // 섹터별 필터 (선택)
  limit?: number              // 결과 제한 (기본값: 1000)
): Promise<TickersResponse>
```

**입력 매개변수**:

| 매개변수 | 타입 | 필수 | 검증 | 설명 |
|---------|------|------|------|------|
| `region` | `string` | 아니오 | KR \| US | 시장 지역별 필터 |
| `sector` | `string` | 아니오 | Any | 섹터명별 필터 |
| `limit` | `number` | 아니오 | 1-10000 | 최대 결과 수 (기본값: 1000) |

**출력 형식**:
```json
{
  "success": true,
  "count": 2,
  "filters": {
    "region": "KR",
    "sector": "Technology",
    "limit": 1000
  },
  "tickers": [
    {
      "ticker": "005930",
      "region": "KR",
      "name": "삼성전자",
      "sector": "Technology"
    },
    {
      "ticker": "000660",
      "region": "KR",
      "name": "SK하이닉스",
      "sector": "Technology"
    }
  ]
}
```

### get_system_status

데이터베이스 상태와 데이터 가용성 상태를 조회합니다.

**용어 설명**:
- **시스템 상태 (System Status)**: 데이터베이스 연결 상태, 데이터 최신성, 전체 시스템 건강도를 종합적으로 나타내는 지표
- **데이터베이스 버전 (Database Version)**: 현재 사용 중인 PostgreSQL과 TimescaleDB의 버전 정보
- **OHLCV 레코드**: 데이터베이스에 저장된 주가 데이터의 총 개수. 각 종목의 일별 데이터가 하나의 레코드입니다.
- **최신 업데이트 날짜 (Latest Date)**: 데이터베이스에 가장 최근에 저장된 주가 데이터의 날짜
- **업데이트 경과 일수 (Days Since Update)**: 마지막 데이터 업데이트 이후 경과한 일수. 1-2일 이내가 정상입니다.

**함수 시그니처**:
```typescript
get_system_status(): Promise<SystemStatusResponse>
```

**입력 매개변수**: 없음

**출력 형식**:
```json
{
  "success": true,
  "status": "healthy",
  "database": {
    "connected": true,
    "version": "PostgreSQL 17.0",
    "size": "500 MB"
  },
  "data": {
    "total_tickers": 1500,
    "ticker_counts_by_region": {
      "KR": 1000,
      "US": 500
    },
    "ohlcv_records": 50000,
    "latest_date": "2024-10-30",
    "days_since_update": 1
  }
}
```

---

### screen_etfs

이름 패턴, 상장 날짜, 기술적 지표를 기준으로 한국 ETF를 스크리닝합니다.

**용어 설명**:
- **스크리닝 (Screening)**: 특정 조건에 맞는 ETF를 필터링하여 찾는 작업
- **RSI (상대강도지수)**: 과매수/과매도 상태를 나타내는 지표 (0-100). 30 이하는 과매도, 70 이상은 과매수
- **MA 트렌드 (이동평균선 추세)**: 단기/중기/장기 이동평균선의 관계로 추세를 판단 (MA20 > MA50 > MA200 = 상승 추세)
- **거래량 평균 (Volume Average)**: ETF의 유동성을 나타내는 지표. 높을수록 매매가 활발함
- **1개월 가격 변동률**: 최근 20 거래일 동안의 가격 변화를 백분율로 표시

**함수 시그니처**:
```typescript
screen_etfs(
  filters?: {
    name_pattern?: string,
    listing_date_after?: string,
    listing_date_before?: string
  },
  technical_filters?: {
    rsi_min?: number,
    rsi_max?: number,
    ma_trend?: "bullish" | "bearish" | "neutral",
    price_change_1m_min?: number,
    price_change_1m_max?: number,
    volume_avg_20d_min?: number
  },
  region?: "KR",
  limit?: number
): Promise<ETFScreeningResponse>
```

**입력 매개변수**:

| 매개변수 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `filters.name_pattern` | string | 아니오 | ETF 이름으로 필터링 (예: "반도체", "KODEX", "200") |
| `filters.listing_date_after` | string | 아니오 | 이 날짜 이후 상장된 ETF 필터링 (YYYY-MM-DD 형식) |
| `filters.listing_date_before` | string | 아니오 | 이 날짜 이전 상장된 ETF 필터링 (YYYY-MM-DD 형식) |
| `technical_filters.rsi_min` | number | 아니오 | 최소 RSI 값 (0-100) |
| `technical_filters.rsi_max` | number | 아니오 | 최대 RSI 값 (0-100, 예: 30이면 과매도 ETF 검색) |
| `technical_filters.ma_trend` | string | 아니오 | 필요한 MA 트렌드: "bullish"(상승, MA20>MA50>MA200), "bearish"(하락, 반대), "neutral"(혼재) |
| `technical_filters.price_change_1m_min` | number | 아니오 | 최소 1개월 가격 변동률 % (예: -10.0은 10% 이상 하락하지 않은 ETF) |
| `technical_filters.price_change_1m_max` | number | 아니오 | 최대 1개월 가격 변동률 % (예: 50.0은 50% 이하 상승한 ETF) |
| `technical_filters.volume_avg_20d_min` | number | 아니오 | 최소 20일 평균 거래량 (유동성/규모 대용 지표) |
| `region` | string | 아니오 | 시장 지역 (기본값: "KR", 현재 KR만 지원) |
| `limit` | number | 아니오 | 반환할 최대 결과 수 (기본값: 50, 최대: 200) |

**출력 형식**:
```json
{
  "success": true,
  "etfs": [
    {
      "ticker": "091160",
      "name": "KODEX 반도체",
      "listing_date": "2015-05-08",
      "sector_theme": "Semiconductor",
      "current_price": 45000,
      "price_change_1m": 8.5,
      "volume_avg_20d": 2500000,
      "rsi": 65.0,
      "rsi_signal": "neutral",
      "ma_trend": "bullish",
      "ma20": 44000,
      "ma50": 43000,
      "ma200": 40000
    }
  ],
  "count": 5,
  "total_matching": 8,
  "filters_applied": {
    "name_pattern": "반도체"
  },
  "technical_filters_applied": {
    "ma_trend": "bullish",
    "rsi_max": 70
  },
  "region": "KR",
  "limitations": [
    "AUM 데이터 미제공 - 거래량을 유동성 대용 지표로 사용",
    "TER 데이터 미제공",
    "섹터/테마는 ETF 이름에서 추정 (정확도 약 70%)",
    "추적 오차 계산 예정"
  ]
}
```

**알려진 제한사항**:
- **AUM 데이터 미제공**: 펀드 규모와 유동성 대용 지표로 `volume_avg_20d`를 사용하세요
- **TER 데이터 미제공**: 운용 보수 정보가 포함되지 않습니다
- **섹터 분류**: ETF 이름에서 키워드로 추정 (정확도 약 70%)
- **추적 오차**: 아직 계산되지 않음 (향후 개선 예정)

**사용 예제**:

1. **반도체 ETF 찾기**:
```json
{
  "tool": "screen_etfs",
  "arguments": {
    "filters": {
      "name_pattern": "반도체"
    },
    "region": "KR",
    "limit": 20
  }
}
```

2. **상승 추세의 적정 RSI ETF 찾기**:
```json
{
  "tool": "screen_etfs",
  "arguments": {
    "technical_filters": {
      "ma_trend": "bullish",
      "rsi_max": 70
    },
    "region": "KR",
    "limit": 50
  }
}
```

3. **섹터 비교 (배터리 ETF + 성과 필터)**:
```json
{
  "tool": "screen_etfs",
  "arguments": {
    "filters": {
      "name_pattern": "배터리"
    },
    "technical_filters": {
      "price_change_1m_min": -20.0,
      "volume_avg_20d_min": 100000
    },
    "region": "KR"
  }
}
```

---

## 사용 예제

### 예제 1: 단일 종목 조회 (한국 시장)

**요청**:
```
2024년 삼성전자 (005930) OHLCV 데이터를 조회합니다.
```

**도구 호출**:
```json
{
  "tool": "query_ohlcv_data",
  "arguments": {
    "tickers": ["005930"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "region": "KR"
  }
}
```

**응답**:
```json
{
  "success": true,
  "data": {
    "005930": [
      {"date": "2024-01-02", "open": 76100, "high": 76800, "low": 75600, "close": 76200, "volume": 15234567},
      {"date": "2024-01-03", "open": 76200, "high": 77500, "low": 76000, "close": 77200, "volume": 18456789},
      ...
    ]
  },
  "metadata": {
    "record_count": 245,
    "tickers": ["005930"]
  }
}
```

### 예제 2: 다중 종목 (일괄 조회)

**요청**:
```
2024년 1분기 삼성 (005930), SK하이닉스 (000660), 네이버 (035420) OHLCV 데이터를 조회합니다.
```

**도구 호출**:
```json
{
  "tool": "query_ohlcv_data",
  "arguments": {
    "tickers": ["005930", "000660", "035420"],
    "start_date": "2024-01-01",
    "end_date": "2024-03-31",
    "region": "KR"
  }
}
```

**응답**:
```json
{
  "success": true,
  "data": {
    "005930": [...],
    "000660": [...],
    "035420": [...]
  },
  "metadata": {
    "record_count": 180,
    "tickers": ["005930", "000660", "035420"]
  }
}
```

### 예제 3: 미국 시장 조회

**요청**:
```
2024년 1월 애플 (AAPL) 주식 데이터를 조회합니다.
```

**도구 호출**:
```json
{
  "tool": "query_ohlcv_data",
  "arguments": {
    "tickers": ["AAPL"],
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "region": "US"
  }
}
```

### 예제 4: 모멘텀 전략 백테스트 실행

**요청**:
```
vectorbt 엔진을 사용하여 2024년 삼성 (005930)에 대한 모멘텀 전략을 백테스트합니다.
```

**도구 호출**:
```json
{
  "tool": "run_backtest",
  "arguments": {
    "strategy_type": "momentum",
    "tickers": ["005930"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "region": "KR",
    "engine": "vectorbt",
    "initial_capital": 100000000
  }
}
```

**응답**:
```json
{
  "success": true,
  "engine": "vectorbt",
  "performance": {
    "total_return": 0.38,
    "annualized_return": 0.38,
    "sharpe_ratio": 1.52,
    "sortino_ratio": 1.95,
    "calmar_ratio": 1.72,
    "max_drawdown": -0.14,
    "max_drawdown_duration": 52
  },
  "trades": {
    "total_trades": 105,
    "win_rate": 0.565,
    "avg_win": 0.045,
    "avg_loss": -0.028,
    "profit_factor": 1.75
  },
  "execution": {
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "duration_days": 365,
    "initial_capital": 100000000,
    "execution_time": 0.92
  }
}
```

### 예제 5: 전략 매개변수 최적화

**요청**:
```
워크포워드 최적화를 사용하여 삼성 (005930)의 모멘텀 전략에 대한 최적의 RSI 매개변수를 찾습니다.
```

**도구 호출**:
```json
{
  "tool": "optimize_strategy",
  "arguments": {
    "strategy_type": "momentum",
    "tickers": ["005930"],
    "start_date": "2022-01-01",
    "end_date": "2024-12-31",
    "region": "KR",
    "param_grid": {
      "rsi_period": [10, 14, 20],
      "oversold": [20, 30],
      "overbought": [70, 80]
    },
    "train_period_days": 252,
    "test_period_days": 63,
    "metric": "sharpe_ratio"
  }
}
```

**응답**:
```json
{
  "success": true,
  "strategy_type": "momentum",
  "optimization": {
    "best_params": {
      "rsi_period": 14,
      "oversold": 30,
      "overbought": 70
    },
    "metric_used": "sharpe_ratio"
  },
  "validation": {
    "in_sample_performance": {
      "mean": 1.85,
      "std": 0.15,
      "min": 1.65,
      "max": 2.05
    },
    "out_of_sample_performance": {
      "mean": 1.65,
      "std": 0.22,
      "min": 1.42,
      "max": 1.88
    },
    "degradation_pct": 0.108,
    "robustness_score": 0.78,
    "overfitting_detected": false,
    "recommendation": "좋음: 강건성 점수 0.78, 배포를 권장하는 전략입니다"
  },
  "windows": [
    {
      "window_id": 0,
      "train_start": "2022-01-01",
      "train_end": "2023-01-01",
      "test_start": "2023-01-02",
      "test_end": "2023-04-02",
      "best_params": {"rsi_period": 14},
      "train_score": 1.85,
      "test_score": 1.65,
      "degradation": 0.108
    }
  ]
}
```

### 예제 6: 사용 가능한 종목 나열

**요청**:
```
한국 시장의 모든 기술 섹터 주식을 나열합니다.
```

**도구 호출**:
```json
{
  "tool": "list_available_tickers",
  "arguments": {
    "region": "KR",
    "sector": "Technology",
    "limit": 100
  }
}
```

**응답**:
```json
{
  "success": true,
  "count": 3,
  "filters": {
    "region": "KR",
    "sector": "Technology",
    "limit": 100
  },
  "tickers": [
    {
      "ticker": "005930",
      "region": "KR",
      "name": "삼성전자",
      "sector": "Technology"
    },
    {
      "ticker": "000660",
      "region": "KR",
      "name": "SK하이닉스",
      "sector": "Technology"
    },
    {
      "ticker": "035420",
      "region": "KR",
      "name": "네이버",
      "sector": "Technology"
    }
  ]
}
```

### 예제 7: 시스템 상태 확인

**요청**:
```
Spock MCP 서버의 상태와 데이터 가용성을 확인합니다.
```

**도구 호출**:
```json
{
  "tool": "get_system_status",
  "arguments": {}
}
```

**응답**:
```json
{
  "success": true,
  "status": "healthy",
  "database": {
    "connected": true,
    "version": "PostgreSQL 17.0",
    "size": "500 MB"
  },
  "data": {
    "total_tickers": 1500,
    "ticker_counts_by_region": {
      "KR": 1000,
      "US": 500
    },
    "ohlcv_records": 50000,
    "latest_date": "2024-10-30",
    "days_since_update": 1
  }
}
```

---

## 오류 처리

### 오류 유형

Spock MCP 서버는 모든 실패 시나리오에 대해 상세한 오류 응답을 제공합니다:

#### 1. ValidationError (VALIDATION_ERROR)

**원인**: 잘못된 입력 매개변수

**예제 시나리오**:
- 잘못된 종목 코드 형식
- 잘못된 날짜 형식
- 날짜 범위가 최대값 초과
- 빈 종목 목록
- 너무 많은 종목 (>1000)

**오류 응답**:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "KR 지역에 대한 잘못된 종목 코드 형식",
    "details": {
      "invalid_tickers": ["INVALID"],
      "expected_format": "6자리 숫자"
    }
  }
}
```

#### 2. DataNotFoundError (DATA_NOT_FOUND)

**원인**: 요청한 종목/날짜에 대한 데이터 없음

**예제 시나리오**:
- 데이터베이스에 없는 종목
- 날짜 범위에 대한 데이터 없음
- 미래 날짜 요청

**오류 응답**:
```json
{
  "success": false,
  "error": {
    "code": "DATA_NOT_FOUND",
    "message": "요청한 종목/날짜에 대한 OHLCV 데이터 없음",
    "details": {
      "tickers": ["999999"],
      "start_date": "2024-01-01",
      "end_date": "2024-12-31",
      "region": "KR"
    }
  }
}
```

#### 3. DatabaseError (DATABASE_ERROR)

**원인**: 데이터베이스 연결 또는 쿼리 실패

**예제 시나리오**:
- PostgreSQL 연결 손실
- 쿼리 타임아웃
- 권한 거부됨

**오류 응답**:
```json
{
  "success": false,
  "error": {
    "code": "DATABASE_ERROR",
    "message": "OHLCV 데이터 쿼리 실패: 연결 타임아웃",
    "details": {
      "tickers": ["005930"],
      "start_date": "2024-01-01",
      "end_date": "2024-12-31"
    }
  }
}
```

#### 4. InternalError (INTERNAL_ERROR)

**원인**: 예기치 않은 서버 오류

**오류 응답**:
```json
{
  "success": false,
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "예기치 않은 오류: ...",
    "details": {
      "type": "RuntimeError"
    }
  }
}
```

---

## 성능

### 성능 목표

| 지표 | 목표 | 달성 |
|------|------|------|
| 캐시 히트 지연시간 | <100ms | ✅ <100ms |
| 캐시 미스 (단일) | <200ms | ✅ <200ms |
| 캐시 미스 (20개 배치) | <500ms | ✅ <500ms |
| 캐시 히트율 | >80% | ✅ >85% |
| 데이터베이스 연결 | 10-30개 풀링 | ✅ 10-30개 |

### 캐싱 전략

Spock MCP 서버는 **2계층 캐싱** 전략을 구현합니다:

**계층 1: MCP 어댑터 캐시**
- 인메모리 딕셔너리 캐시
- 캐시 키: `{tickers}:{start_date}:{end_date}:{region}:{timeframe}`
- 결정론적 캐시 키 (정렬된 종목)
- TTL 없음 (세션 범위)

**계층 2: PostgresDataProvider 캐시**
- `BaseDataProvider`에서 상속
- 크기 제한이 있는 DataFrame 캐싱
- LRU 제거 정책
- 캐시 히트율: >85%

### 성능 팁

1. **일괄 쿼리**: 더 나은 성능을 위해 한 번의 요청으로 여러 종목을 쿼리
2. **날짜 범위 재사용**: 동일한 쿼리는 자동으로 캐시에 히트
3. **연결 풀링**: 서버는 10-30개의 PostgreSQL 연결 유지
4. **TimescaleDB 최적화**: 쿼리는 빠른 결과를 위해 청크 제외 활용

---

## 문제 해결

### 일반적인 문제

#### 문제 1: Claude Code가 서버를 감지하지 못함

**증상**: Spock 서버가 Claude Code MCP 서버 목록에 나타나지 않음

**해결책**:
1. `.claude/mcp_config.json`이 존재하고 유효한 JSON인지 확인
2. Claude Code를 완전히 재시작
3. 서버 초기화 확인: `python3 -m mcp_server.server`
4. 설정에서 작업 디렉토리가 올바른지 확인

#### 문제 2: 데이터베이스 연결 오류

**증상**: `DATABASE_ERROR` 응답

**해결책**:
1. PostgreSQL이 실행 중인지 확인: `psql --version`
2. 연결 확인: `psql -d quant_platform`
3. `.env` 파일에 올바른 자격 증명이 있는지 확인
4. 오류에 대한 PostgreSQL 로그 확인

#### 문제 3: 데이터가 반환되지 않음

**증상**: 유효한 종목에 대한 `DATA_NOT_FOUND` 오류

**해결책**:
1. 종목이 존재하는지 확인: `SELECT * FROM tickers WHERE ticker='005930' AND region='KR';`
2. OHLCV 데이터 확인: `SELECT COUNT(*) FROM ohlcv_data WHERE ticker='005930';`
3. 필요한 경우 데이터 백필 실행
4. 날짜 범위가 사용 가능한 데이터와 겹치는지 확인

#### 문제 4: 느린 쿼리 성능

**증상**: 쿼리가 1초 이상 걸림

**해결책**:
1. 데이터베이스 크기 확인: `SELECT pg_size_pretty(pg_database_size('quant_platform'));`
2. ohlcv_data 테이블에서 `ANALYZE` 실행
3. TimescaleDB 연속 집계 확인
4. 연결 풀 확인: 10-30개의 연결이 표시되어야 함
5. 느린 쿼리를 식별하기 위해 쿼리 로깅 활성화

### 디버그 로깅

상세한 서버 작동을 위한 DEBUG 로깅 활성화:

```python
# .env 파일에서
LOG_LEVEL=DEBUG
```

**디버그 로그 출력**:
```
2025-10-30T13:38:38Z [info] data_adapter_initialized cache_max_size_mb=500
2025-10-30T13:38:38Z [info] data_query_tools_registered tool_count=1
2025-10-30T13:38:38Z [info] mcp_server_initialized server_name=spock version=0.1.0
2025-10-30T13:38:39Z [info] query_ohlcv_data_start tickers=['005930'] start_date=2024-01-01
2025-10-30T13:38:39Z [debug] cache_miss cache_key=005930:2024-01-01:2024-12-31:KR:1d
2025-10-30T13:38:39Z [info] query_ohlcv_data_success ticker_count=1 record_count=245
```

---

## 지원 및 리소스

### 문서
- **MCP 설계**: `docs/MCP_DESIGN.md` - 아키텍처 및 설계 패턴
- **MCP 워크플로우**: `docs/MCP_WORKFLOW.md` - 개발 워크플로우 및 로드맵
- **완료 보고서**: `docs/PHASE1_WEEK1_DAY*.md` - 구현 세부사항

### 코드 예제
- **통합 테스트**: `tests/mcp_server/test_data_query_tools.py`
- **수동 테스트**: Day 3-4 완료 보고서에 테스트 스크립트 포함

### 외부 리소스
- **MCP SDK 문서**: https://github.com/anthropics/mcp
- **Claude Code 문서**: https://docs.claude.com/claude-code
- **TimescaleDB 문서**: https://docs.timescale.com/

### 문제 보고

버그를 발견하거나 기능 요청이 있으신가요? 다음 정보를 포함해 주세요:
1. MCP 서버 버전
2. 오류 메시지 및 스택 추적
3. 문제를 일으킨 입력 매개변수
4. 예상 동작 vs 실제 동작
5. 디버그 로그 (해당하는 경우)

---

**최종 업데이트**: 2025-10-31
**버전**: 0.2.0
**상태**: 프로덕션 준비 완료 (Phase 1 Week 2 완료)

## 도구 요약

| 도구 | 목적 | 성능 | 상태 |
|-----|------|------|------|
| `query_ohlcv_data` | 과거 가격 데이터 조회 | 캐시 미스 시 <200ms | ✅ 프로덕션 |
| `run_backtest` | 전략 백테스트 실행 | vectorbt <1s, custom <30s | ✅ 프로덕션 |
| `optimize_strategy` | 최적 매개변수 찾기 | 그리드 크기에 따라 다름 | ✅ 프로덕션 |
| `list_available_tickers` | 사용 가능한 주식 나열 | 캐싱으로 <100ms | ✅ 프로덕션 |
| `get_system_status` | 시스템 상태 확인 | <50ms | ✅ 프로덕션 |
