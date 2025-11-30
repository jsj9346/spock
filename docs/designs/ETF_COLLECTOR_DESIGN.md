# ETF Data Collector Design Document

## 1. Overview

ETF 상세 정보(`etf_details`) 및 구성종목 정보(`etf_holdings`)를 수집하여 데이터베이스에 저장하는 시스템 설계 문서입니다.

### 1.1 목표
- **6개 리전** (KR, US, JP, CN, HK, VN) ETF 데이터 수집
- `etf_details` 테이블: ETF 기본 정보 (발행사, 추적지수, 운용보수 등)
- `etf_holdings` 테이블: ETF 구성종목 정보 (종목, 비중, 보유수량 등)
- 기존 패턴 (`DividendCollector`, `CollectionTracker`) 활용

### 1.2 현재 상태
| Region | tickers (ETF) | etf_details | etf_holdings |
|--------|---------------|-------------|--------------|
| KR     | 1,045         | 0           | 0            |
| US     | 0 (미등록)    | 0           | 0            |
| JP     | 0 (미등록)    | 0           | 0            |
| HK     | 0 (미등록)    | 0           | 0            |
| CN     | 0 (미등록)    | 0           | 0            |
| VN     | 0 (미등록)    | 0           | 0            |

---

## 2. Data Sources by Region

### 2.1 KR (한국)
| 데이터 | 소스 | API/Method | 비용 |
|--------|------|------------|------|
| ETF Details | KIS API | `FHKST01010800` (ETF 상세정보) | 무료 (기존 API Key) |
| ETF Holdings | KRX Data Portal | OTP 기반 웹 크롤링 | 무료 |
| Tracking Error | KIS API | `FHPST02400000` (추적오차) | 무료 |

**기존 구현**: `kis_etf_api.py`, `krx_etf_api.py` 활용 가능

### 2.2 US (미국)
| 데이터 | 소스 | API/Method | 비용 |
|--------|------|------------|------|
| ETF Details | yfinance | `Ticker.info` | 무료 |
| ETF Holdings | SEC EDGAR N-PORT | 웹 크롤링/API | 무료 |
| Alternative | Finnhub | ETF Profile API | 유료 (Free tier 제한) |

**참고**: yfinance는 `totalAssets`, `fundFamily`, `category` 등 제공하지만 holdings는 미제공

### 2.3 JP (일본)
| 데이터 | 소스 | API/Method | 비용 |
|--------|------|------------|------|
| ETF Details | yfinance | `Ticker.info` (.T suffix) | 무료 |
| ETF Holdings | JPX/운용사 웹사이트 | 웹 크롤링 | 무료 |

**제한**: Holdings 데이터 자동 수집 어려움 (운용사별 PDF 공시)

### 2.4 HK (홍콩)
| 데이터 | 소스 | API/Method | 비용 |
|--------|------|------------|------|
| ETF Details | yfinance | `Ticker.info` (.HK suffix) | 무료 |
| ETF Holdings | HKEX/운용사 웹사이트 | 웹 크롤링 | 무료 |

**참고**: Hang Seng Investment 등 운용사 웹사이트에서 PDF 다운로드 필요

### 2.5 CN (중국)
| 데이터 | 소스 | API/Method | 비용 |
|--------|------|------------|------|
| ETF Details | yfinance (제한적) | `Ticker.info` (.SS/.SZ suffix) | 무료 |
| ETF Holdings | AKShare | 중국 시장 전용 라이브러리 | 무료 |

**제한**: yfinance에서 CN ETF는 `quoteType: EQUITY`로 인식되는 경우 많음

### 2.6 VN (베트남)
| 데이터 | 소스 | API/Method | 비용 |
|--------|------|------------|------|
| ETF Details | yfinance (매우 제한적) | - | 무료 |
| ETF Holdings | HoSE 웹사이트 | 웹 크롤링 | 무료 |

**제한**: VN 로컬 ETF 데이터 수집 매우 어려움 (US 상장 VN ETF만 가능)

---

## 3. Architecture Design

### 3.1 Class Hierarchy

```
ETFCollector (Base)
├── KRETFCollector
│   ├── KIS API (details, tracking_error)
│   └── KRX API (holdings)
├── USETFCollector
│   ├── yfinance (details)
│   └── SEC EDGAR (holdings) - Phase 2
├── JPETFCollector
│   └── yfinance (details only)
├── HKETFCollector
│   └── yfinance (details only)
├── CNETFCollector
│   ├── yfinance (details)
│   └── AKShare (holdings) - Phase 2
└── VNETFCollector
    └── yfinance (details only - limited)
```

### 3.2 File Structure

```
modules/
└── collection/
    ├── etf_collector.py          # Base class + ETFCollector
    ├── etf_details_collector.py  # ETF Details collection logic
    └── etf_holdings_collector.py # ETF Holdings collection logic (Phase 2)

scripts/
├── backfill_etf_details.py       # Initial backfill script
└── backfill_etf_holdings.py      # Holdings backfill (Phase 2)
```

### 3.3 Database Schema (기존)

**etf_details** (기존 스키마 활용):
- `ticker`, `region` (PK)
- `issuer`, `inception_date`, `tracking_index`
- `expense_ratio`, `ter`, `aum`, `listed_shares`
- `tracking_error_20d/60d/120d/250d`
- `fund_type`, `sector_theme`, `leverage_ratio`, `currency_hedged`

**etf_holdings** (기존 스키마 활용):
- `etf_ticker`, `stock_ticker`, `region`, `as_of_date` (UK)
- `weight`, `shares`, `market_value`, `rank_in_etf`

---

## 4. Implementation Plan

### Phase 1: ETF Details Collection (Week 1)

#### 4.1.1 Step 1: Base Infrastructure
- [ ] `ETFCollector` 베이스 클래스 생성
- [ ] `CollectionTracker`에 `DataType.ETF_DETAILS`, `DataType.ETF_HOLDINGS` 추가
- [ ] yfinance ETF 정보 파싱 유틸리티

#### 4.1.2 Step 2: KR ETF Details
- [ ] `KRETFCollector` 구현 (기존 `KISEtfAPI` 활용)
- [ ] KIS API에서 ETF 상세정보 + 추적오차 수집
- [ ] 1,045개 KR ETF 백필

#### 4.1.3 Step 3: US/JP/HK/CN/VN ETF Details
- [ ] yfinance 기반 `USETFCollector` 구현
- [ ] ETF ticker 목록 수집 (tickers 테이블에 ETF 등록)
- [ ] 각 리전별 ETF Details 백필

#### 4.1.4 Step 4: ETF Ticker Registration
- [ ] US: 주요 ETF 목록 등록 (SPY, QQQ, IWM, EEM 등)
- [ ] JP: TSE ETF 목록 등록 (1306.T, 1321.T 등)
- [ ] HK: HKEX ETF 목록 등록 (2800.HK, 2828.HK 등)
- [ ] CN: SSE/SZSE ETF 목록 등록 (510050.SS 등)
- [ ] VN: 로컬 ETF 제한적 (US 상장 VNM, VNAM 등)

### Phase 2: ETF Holdings Collection (Week 2+)

#### 4.2.1 KR Holdings
- [ ] KRX API 기반 구성종목 수집 (기존 `krx_etf_api.py` 활용)
- [ ] 일별 holdings 업데이트 스케줄링

#### 4.2.2 US Holdings (선택)
- [ ] SEC EDGAR N-PORT 파싱 구현
- [ ] 분기별 holdings 업데이트

#### 4.2.3 Other Regions (선택)
- [ ] CN: AKShare 기반 holdings 수집
- [ ] JP/HK: 운용사 웹사이트 크롤링 (복잡도 높음)

---

## 5. Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     ETF Collector                            │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ KR: KIS API   │ │ US: yfinance  │ │ JP/HK/CN/VN   │
│     KRX API   │ │     SEC EDGAR │ │ yfinance      │
└───────┬───────┘ └───────┬───────┘ └───────┬───────┘
        │               │               │
        └───────────────┼───────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              CollectionTracker (중복 방지)                   │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
┌───────────────────────┐     ┌───────────────────────┐
│     etf_details       │     │     etf_holdings      │
│  (PostgreSQL)         │     │   (PostgreSQL)        │
└───────────────────────┘     └───────────────────────┘
```

---

## 6. API Rate Limits & Considerations

| Source | Rate Limit | Strategy |
|--------|------------|----------|
| KIS API | 1 req/sec | 기존 rate limiter 활용 |
| KRX Data | 1 req/sec | 자체 rate limiter |
| yfinance | ~1 req/sec | 기존 `YFinanceAPI` 활용 |
| SEC EDGAR | 10 req/sec | User-Agent 설정 필요 |
| AKShare | Varies | 라이브러리 내장 |

---

## 7. Error Handling

1. **API 실패**: 3회 재시도 후 스킵, 에러 로깅
2. **데이터 누락**: NULL 허용 필드는 그대로 저장
3. **중복 방지**: `CollectionTracker` 활용
4. **외래 키 오류**: tickers 테이블에 ETF 미등록 시 자동 등록

---

## 8. Success Criteria

### Phase 1
- [ ] KR ETF Details: 1,045개 중 90%+ 수집
- [ ] US ETF Details: 주요 100개 ETF 수집
- [ ] JP/HK ETF Details: 주요 50개 ETF 수집
- [ ] CN ETF Details: 주요 30개 ETF 수집

### Phase 2
- [ ] KR ETF Holdings: 주요 100개 ETF 구성종목 수집
- [ ] US ETF Holdings: 주요 20개 ETF 구성종목 수집 (SEC N-PORT)

---

## 9. Dependencies

### 기존 활용
- `modules/api_clients/kis_etf_api.py`
- `modules/api_clients/krx_etf_api.py`
- `modules/api_clients/yfinance_api.py`
- `modules/collection/collection_tracker.py`
- `modules/db_manager_postgres.py`

### 신규 (필요 시)
- `sec-api` (SEC EDGAR N-PORT 파싱)
- `akshare` (중국 시장 데이터)

---

## 10. Timeline

| Week | Task | Deliverable |
|------|------|-------------|
| Week 1 | Phase 1.1-1.4 | ETF Details for all regions |
| Week 2 | Phase 2.1 | KR ETF Holdings |
| Week 3+ | Phase 2.2-2.3 | US/CN ETF Holdings (optional) |

---

## 11. Questions for User

1. **ETF Ticker 등록**: US/JP/HK/CN ETF를 tickers 테이블에 자동 등록할까요, 아니면 주요 ETF 목록을 수동으로 지정할까요?

2. **Holdings 수집 범위**: KR 외 다른 리전의 Holdings도 수집이 필요한가요? (복잡도 높음)

3. **업데이트 주기**: ETF Details는 월별, Holdings는 일별 업데이트가 적절할까요?

4. **우선순위 ETF**: 특별히 관심 있는 ETF 목록이 있으신가요? (예: 레버리지 ETF, 섹터 ETF 등)

---

**작성일**: 2025-11-28
**작성자**: Claude Code
**버전**: 1.0
