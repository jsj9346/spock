# 펀더멘털 TTM/연도별 조회 기능 - 구현 우선순위

## 현재 데이터 상태 분석

### 데이터베이스 현황 (2024-11-27 기준)

| period_type | 레코드 수 | ticker 수 | 기간 |
|-------------|----------|----------|------|
| **DAILY** | 127,027 | 2,721 | 2024-07-23 ~ 2025-11-26 |
| **ANNUAL** | 2,488 | 1,934 | 2022-12-31 ~ 2024-12-31 |
| **QUARTERLY** | 1 | 1 | 2024-09-30 (거의 없음) ⚠️ |
| **SEMI-ANNUAL** | 90 | 90 | 2025-06-30 |

### 핵심 발견사항

1. **QUARTERLY 데이터 부재**: TTM 계산을 위한 분기 데이터가 거의 없음 (1건만 존재)
2. **ANNUAL 데이터 양호**: 1,934개 ticker에 대해 3년치 연간 데이터 존재
3. **DART 백필 스크립트 존재**: `scripts/backfill_fundamentals_dart.py` 구현됨

### 삼성전자(005930) 연간 데이터 예시

| fiscal_year | revenue (조원) | operating_profit | net_income | ROE 계산 가능 |
|-------------|---------------|-----------------|------------|--------------|
| 2024 | 300.9 | 32.7 | 34.5 | ✅ |
| 2023 | 258.9 | 6.6 | 15.5 | ✅ |
| 2022 | 302.2 | 43.4 | 55.7 | ✅ |

---

## 구현 우선순위 (재조정)

### 🔴 Priority 0: 데이터 기반 확보 (선결조건)

**문제**: QUARTERLY 데이터 없이는 TTM 계산 불가능

| 작업 | 설명 | 예상 기간 | 의존성 |
|------|------|----------|--------|
| **P0.1** | DART 분기 백필 확장 | 2-3일 | DART API Key |
| **P0.2** | 분기 데이터 품질 검증 | 0.5일 | P0.1 |

**P0.1 상세: DART 분기 백필**
```bash
# 현재 연간(11011)만 수집 → 분기(11012, 11013, 11014) 추가 필요
# 보고서 코드:
# - 11011: 사업보고서 (연간)
# - 11012: 반기보고서
# - 11013: 1분기보고서
# - 11014: 3분기보고서

# 목표: 최근 8분기 데이터 수집 (TTM 계산 + 여유분)
python3 scripts/backfill_fundamentals_dart.py \
  --report-type quarterly \
  --start-year 2023 \
  --limit 100  # 테스트
```

**대안 전략**: QUARTERLY 백필 완료 전까지 ANNUAL 기반 기능 먼저 구현

---

### 🟠 Priority 1: ANNUAL 기반 핵심 기능 (MVP)

**목표**: 분기 데이터 없이도 연도별 비교 기능 제공

| 작업 ID | 작업명 | 설명 | 예상 기간 | 의존성 |
|---------|-------|------|----------|--------|
| **P1.1** | 기본 모듈 구조 생성 | `modules/fundamentals/` 디렉토리 및 기본 파일 | 0.5일 | 없음 |
| **P1.2** | 연도별 비교 분석기 | `comparison_analyzer.py` - YoY 성장률, 추세 분석 | 1일 | P1.1 |
| **P1.3** | DB 조회 확장 | `get_fundamentals_multi_year()` 메서드 | 0.5일 | P1.1 |
| **P1.4** | MCP Tool (v1) | `query_fundamentals_annual` - 연도별 조회 | 1일 | P1.2, P1.3 |
| **P1.5** | 단위 테스트 | 연도별 비교 기능 테스트 | 0.5일 | P1.4 |

**P1 산출물**:
```python
# 연도별 비교 조회 (TTM 없이)
response = await query_fundamentals_annual(
    tickers=["005930", "000660"],
    years=[2024, 2023, 2022],
    metrics=["revenue", "net_income", "roe"]
)

# 응답 예시
{
    "005930": {
        "annual": [
            {"fiscal_year": 2024, "revenue": 300.9T, "yoy_growth": 16.2%},
            {"fiscal_year": 2023, "revenue": 258.9T, "yoy_growth": -14.3%},
            {"fiscal_year": 2022, "revenue": 302.2T, "yoy_growth": 8.1%}
        ],
        "cagr_3y": {"revenue": 0.002, "net_income": -0.15}
    }
}
```

**예상 기간**: 3.5일

---

### 🟡 Priority 2: TTM 계산 엔진

**의존성**: P0.1 (QUARTERLY 데이터 백필) 완료 필요

| 작업 ID | 작업명 | 설명 | 예상 기간 | 의존성 |
|---------|-------|------|----------|--------|
| **P2.1** | TTM Calculator | `ttm_calculator.py` - 4분기 합산/평균 로직 | 1.5일 | P0.1 |
| **P2.2** | Period Aggregator | `period_aggregator.py` - 분기 선택/검증 | 1일 | P2.1 |
| **P2.3** | 파생 비율 계산 | ROE_TTM, ROA_TTM, 마진 계산 | 0.5일 | P2.2 |
| **P2.4** | DB 쿼리 확장 | `get_fundamentals_with_ttm()` | 0.5일 | P2.3 |
| **P2.5** | 단위 테스트 | TTM 계산 정확도 검증 | 1일 | P2.4 |

**P2 산출물**:
```python
# TTM 계산기 핵심 로직
class TTMCalculator:
    SUM_METRICS = ['revenue', 'operating_profit', 'net_income', 'ebitda']
    POINT_METRICS = ['total_assets', 'total_equity', 'total_liabilities']

    def calculate(self, quarterly_data: List[Dict]) -> TTMResult:
        # 최근 4분기 합산 (손익계산서)
        # 최신값 사용 (재무상태표)
        # 파생 비율 계산
        pass
```

**예상 기간**: 4.5일

---

### 🟢 Priority 3: 통합 API 및 Tool

| 작업 ID | 작업명 | 설명 | 예상 기간 | 의존성 |
|---------|-------|------|----------|--------|
| **P3.1** | DataAdapter 확장 | `get_fundamentals_unified()` | 1일 | P1, P2 |
| **P3.2** | MCP Tool (v2) | `query_fundamentals_unified` - TTM+연도별 | 1일 | P3.1 |
| **P3.3** | 응답 포맷터 | JSON 응답 구조화, 비교 분석 포함 | 0.5일 | P3.2 |
| **P3.4** | 통합 테스트 | 엔드투엔드 테스트 | 0.5일 | P3.3 |

**예상 기간**: 3일

---

### 🔵 Priority 4: 고급 기능 (선택적)

| 작업 ID | 작업명 | 설명 | 예상 기간 | 의존성 |
|---------|-------|------|----------|--------|
| **P4.1** | LTM 지원 | Last Twelve Months (TTM과 동의어, 명시적 지원) | 0.5일 | P3 |
| **P4.2** | 분기별 추세 | 분기별 성장률 및 계절성 분석 | 1일 | P3 |
| **P4.3** | 섹터 비교 | 동종업계 TTM 비교 | 1.5일 | P3 |
| **P4.4** | 캐싱 최적화 | TTM 계산 결과 캐싱 | 1일 | P3 |

**예상 기간**: 4일 (선택적)

---

## 권장 구현 순서

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase A: MVP (ANNUAL 기반) - 즉시 시작 가능                      │
│  ────────────────────────────────────────────────────────────── │
│  P1.1 → P1.2 → P1.3 → P1.4 → P1.5                               │
│  예상: 3.5일                                                     │
│  산출물: 연도별 비교 MCP Tool                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase B: 데이터 준비 (병렬 진행 가능)                            │
│  ────────────────────────────────────────────────────────────── │
│  P0.1 (DART 분기 백필) → P0.2 (품질 검증)                        │
│  예상: 2.5일                                                     │
│  산출물: 8분기 QUARTERLY 데이터                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase C: TTM 엔진                                               │
│  ────────────────────────────────────────────────────────────── │
│  P2.1 → P2.2 → P2.3 → P2.4 → P2.5                               │
│  예상: 4.5일                                                     │
│  산출물: TTM 계산 모듈                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase D: 통합                                                   │
│  ────────────────────────────────────────────────────────────── │
│  P3.1 → P3.2 → P3.3 → P3.4                                      │
│  예상: 3일                                                       │
│  산출물: query_fundamentals_unified MCP Tool                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 상세 작업 목록

### Phase A: MVP (연도별 비교)

```
□ P1.1 기본 모듈 구조 (0.5일)
  ├── modules/fundamentals/__init__.py
  ├── modules/fundamentals/models.py (데이터 모델)
  └── modules/fundamentals/constants.py (상수 정의)

□ P1.2 연도별 비교 분석기 (1일)
  ├── modules/fundamentals/comparison_analyzer.py
  ├── YoY 성장률 계산
  ├── CAGR 계산
  └── 추세 분류 (improving/stable/declining)

□ P1.3 DB 조회 확장 (0.5일)
  └── PostgresDatabaseManager.get_fundamentals_multi_year()

□ P1.4 MCP Tool v1 (1일)
  ├── mcp_server/tools/fundamentals_annual_tool.py
  └── query_fundamentals_annual Tool 정의

□ P1.5 단위 테스트 (0.5일)
  └── tests/unit/test_comparison_analyzer.py
```

### Phase B: 데이터 준비

```
□ P0.1 DART 분기 백필 확장 (2-3일)
  ├── scripts/backfill_fundamentals_dart.py 수정
  │   ├── report_type 파라미터 추가 (11012, 11013, 11014)
  │   └── 분기별 데이터 파싱 로직
  ├── 2023 Q1 ~ 2024 Q3 데이터 수집
  └── 최소 1,000개 ticker 목표

□ P0.2 분기 데이터 품질 검증 (0.5일)
  ├── 연속성 검증 (4분기 연속 존재 여부)
  ├── 값 범위 검증 (음수 매출 등 이상치)
  └── 연간 데이터와 정합성 검증 (Q1+Q2+Q3+Q4 ≈ Annual)
```

### Phase C: TTM 엔진

```
□ P2.1 TTM Calculator (1.5일)
  ├── modules/fundamentals/ttm_calculator.py
  ├── 합산 로직 (손익계산서 지표)
  ├── 최신값 로직 (재무상태표 지표)
  └── 데이터 완성도 검증

□ P2.2 Period Aggregator (1일)
  ├── modules/fundamentals/period_aggregator.py
  ├── 분기 선택 로직 (as_of_date 기준)
  └── 누락 분기 처리

□ P2.3 파생 비율 계산 (0.5일)
  ├── ROE_TTM, ROA_TTM
  ├── Operating Margin TTM
  └── Net Margin TTM

□ P2.4 DB 쿼리 확장 (0.5일)
  └── PostgresDatabaseManager.get_fundamentals_with_ttm()

□ P2.5 단위 테스트 (1일)
  ├── tests/unit/test_ttm_calculator.py
  └── 삼성전자 실데이터 검증
```

### Phase D: 통합

```
□ P3.1 DataAdapter 확장 (1일)
  └── DataAdapter.get_fundamentals_unified()

□ P3.2 MCP Tool v2 (1일)
  ├── mcp_server/tools/fundamentals_unified_tool.py
  └── query_fundamentals_unified Tool 정의

□ P3.3 응답 포맷터 (0.5일)
  └── format_unified_response() 구현

□ P3.4 통합 테스트 (0.5일)
  └── tests/integration/test_fundamentals_unified.py
```

---

## 예상 총 일정

| Phase | 기간 | 누적 | 주요 산출물 |
|-------|------|------|-----------|
| **A (MVP)** | 3.5일 | 3.5일 | 연도별 비교 Tool |
| **B (데이터)** | 2.5일 | 6일 | 분기 데이터 |
| **C (TTM)** | 4.5일 | 10.5일 | TTM 계산기 |
| **D (통합)** | 3일 | 13.5일 | 통합 Tool |

**총 예상 기간**: 약 **13.5일** (약 2.5주)

---

## 즉시 시작 가능한 작업

### 오늘 시작 권장: P1.1 + P1.2

```bash
# 1. 모듈 구조 생성
mkdir -p modules/fundamentals
touch modules/fundamentals/__init__.py
touch modules/fundamentals/models.py
touch modules/fundamentals/constants.py
touch modules/fundamentals/comparison_analyzer.py

# 2. 연도별 비교 분석기 구현 시작
# - YoY 성장률 계산
# - CAGR 계산
# - 기존 ANNUAL 데이터 활용
```

### 병렬 작업 권장: P0.1

```bash
# DART 분기 백필 스크립트 분석 및 수정
# 현재 연간(11011)만 지원 → 분기(11012-11014) 추가
python3 scripts/backfill_fundamentals_dart.py --dry-run --limit 5
```

---

## 리스크 및 대응 방안

| 리스크 | 영향 | 대응 방안 |
|--------|------|----------|
| DART API 분기 데이터 불완전 | TTM 계산 불가 | Phase A (연도별) 먼저 완료하여 가치 제공 |
| 분기 데이터 정합성 이슈 | TTM 정확도 저하 | 연간 합계와 교차 검증 로직 추가 |
| API 호출 제한 | 백필 지연 | 배치 처리 + 레이트 리미팅 조정 |

---

**작성일**: 2024-11-27
**상태**: 우선순위 확정, Phase A 즉시 시작 가능
