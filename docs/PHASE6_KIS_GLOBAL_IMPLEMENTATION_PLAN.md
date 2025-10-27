# Phase 6: KIS API Global Market Integration - Implementation Plan

**작업 시작**: 2025-10-15
**예상 완료**: 2025-10-18 (3-4일)
**담당**: Spock Trading System
**상태**: 🚧 **IN PROGRESS**

---

## 📋 Executive Summary

Phase 6는 **KIS API 기반 글로벌 시장 통합**을 목표로 진행됩니다. Phase 2-5에서 사용한 외부 API (Polygon.io, yfinance, AkShare)를 KIS API로 대체하여 **한국인 거래 가능 종목만** 수집하고, API 통합 및 성능을 개선합니다.

### 핵심 목표
- ✅ KIS Overseas Stock API 클라이언트 구현 완료
- 🚧 US/HK/CN/JP/VN 시장별 KIS 기반 adapter 구현
- 🚧 거래 가능 종목 필터링 (tradable tickers only)
- 🚧 통일된 데이터 포맷 및 parser 로직
- 🚧 Rate limiting 개선 (5 req/min → 20 req/sec)

### 예상 효과
- 🎯 **실거래 가능 종목만 수집** (정확도 ↑)
- ⚡ **데이터 수집 속도 240배 향상** (Polygon.io 대비)
- 💰 **외부 API 비용 제거** (Polygon.io 불필요)
- 🔧 **유지보수 복잡도 감소** (통일된 API)

---

## 🎯 Phase 6 목표 및 범위

### 원래 목표 (Phase 2-5 문제점)
1. ❌ **외부 API 의존성**: Polygon.io, yfinance, AkShare 사용
2. ❌ **Rate Limiting 제약**: Polygon.io 5 req/min (12초/요청)
3. ❌ **거래 불가 종목 포함**: 한국인 거래 불가 종목도 수집
4. ❌ **API 키 관리 부담**: 여러 외부 서비스 API 키 필요
5. ❌ **데이터 포맷 불일치**: 각 API마다 다른 응답 형식

### Phase 6 해결 방안
1. ✅ **KIS API 통합**: 모든 해외 시장을 KIS API로 통일
2. ✅ **Rate Limiting 완화**: 20 req/sec (240배 빠름)
3. ✅ **거래 가능 종목만**: KIS API가 제공하는 ticker만 수집
4. ✅ **단일 API 키**: 기존 KIS API 키 재사용
5. ✅ **통일된 포맷**: KIS API 응답 형식으로 통일

---

## 📊 KIS API vs 기존 API 비교

### 현재 구현 (Phase 2-5)

| Phase | 시장 | 현재 Data Source | 문제점 |
|-------|------|------------------|--------|
| Phase 2 | US (NYSE/NASDAQ/AMEX) | Polygon.io (5 req/min) | Rate limit 엄격, 거래 불가 종목 포함 |
| Phase 3 | CN (SSE/SZSE) | AkShare + yfinance | 선강통/후강통 거래 가능 종목만 필요 |
| Phase 3 | HK (HKEX) | yfinance | 거래 가능 여부 불명확 |
| Phase 4 | JP (TSE) | yfinance | 거래 가능 여부 불명확 |
| Phase 5 | VN (HOSE/HNX) | yfinance | 거래 가능 여부 불명확 |

### Phase 6 목표 (KIS API 기반)

| Phase | 시장 | New Data Source | 장점 |
|-------|------|-----------------|------|
| Phase 6 | US (NYSE/NASDAQ/AMEX) | KIS API (NASD/NYSE/AMEX) | ✅ 한국인 거래 가능 종목만 |
| Phase 6 | HK (HKEX) | KIS API (SEHK) | ✅ 거래 가능 종목만 |
| Phase 6 | CN (SSE/SZSE) | KIS API (SHAA/SZAA) | ✅ 선강통/후강통 경로만 |
| Phase 6 | JP (TSE) | KIS API (TKSE) | ✅ 거래 가능 종목만 |
| Phase 6 | VN (HOSE/HNX) | KIS API (HASE/VNSE) | ✅ 거래 가능 종목만 |

---

## 🛠️ 구현 계획

### Step 1: KIS Overseas Stock API Client ✅ COMPLETE

**파일**: `modules/api_clients/kis_overseas_stock_api.py` (530 lines)

**구현 완료 기능**:
```python
class KISOverseasStockAPI:
    """KIS 해외주식 API 클라이언트"""

    # Exchange codes for all markets
    EXCHANGE_CODES = {
        'US': ['NASD', 'NYSE', 'AMEX'],
        'HK': ['SEHK'],
        'CN': ['SHAA', 'SZAA'],
        'JP': ['TKSE'],
        'VN': ['HASE', 'VNSE'],
        'SG': ['SGXC']
    }

    def get_tradable_tickers(exchange_code, max_count) -> List[str]
    def get_ohlcv(ticker, exchange_code, days) -> pd.DataFrame
    def get_current_price(ticker, exchange_code) -> Dict
    def get_all_tradable_tickers(region, max_count) -> List[str]
```

**주요 API Endpoints**:
- `/uapi/overseas-price/v1/quotations/inquire-search` - 거래 가능 종목 리스트
- `/uapi/overseas-price/v1/quotations/dailyprice` - 일별 OHLCV
- `/uapi/overseas-price/v1/quotations/price` - 현재가

**Rate Limiting**:
- 20 req/sec (0.05초 간격)
- 1,000 req/min
- Automatic throttling

---

### Step 2: KIS-Based Market Adapters (3-4일)

**목표**: Phase 2-5 adapter를 KIS API 기반으로 재구축

#### 2.1. US Adapter (KIS 기반) - 1일

**파일**: `modules/market_adapters/us_adapter_kis.py`

**구현 방안**:
```python
from modules.api_clients.kis_overseas_stock_api import KISOverseasStockAPI

class USAdapterKIS(BaseMarketAdapter):
    """
    US market adapter using KIS API

    Features:
    - Tradable ticker filtering (KIS API provides tradable tickers only)
    - NYSE, NASDAQ, AMEX support
    - Unified data format (KIS response)
    - Rate limiting: 20 req/sec
    """

    def __init__(self, db, app_key, app_secret):
        self.kis_api = KISOverseasStockAPI(app_key, app_secret)
        self.parser = USStockParser()  # Reuse existing parser
        self.exchanges = ['NASD', 'NYSE', 'AMEX']

    def scan_stocks(self, force_refresh=False, max_count=None):
        """Scan US stocks (tradable tickers only)"""
        all_tickers = []

        for exchange in self.exchanges:
            tickers = self.kis_api.get_tradable_tickers(exchange, max_count)
            for ticker in tickers:
                # Fetch ticker info and save to DB
                # KIS API provides tradable tickers only
                ...

    def collect_stock_ohlcv(self, tickers, days=250):
        """Collect OHLCV data using KIS API"""
        for ticker in tickers:
            # Determine exchange for ticker
            exchange = self._detect_exchange(ticker)
            ohlcv_df = self.kis_api.get_ohlcv(ticker, exchange, days)
            # Add technical indicators
            # Save to DB
            ...
```

**마이그레이션 전략**:
1. 기존 `us_adapter.py` 유지 (fallback)
2. 새로운 `us_adapter_kis.py` 구현
3. 기존 `USStockParser` 재사용 (sector mapping 로직)
4. Unit tests 작성 및 검증
5. Demo script로 통합 테스트
6. Production 배포 후 기존 adapter deprecated

#### 2.2. HK Adapter (KIS 기반) - 0.5일

**파일**: `modules/market_adapters/hk_adapter_kis.py`

**구현 특징**:
- Exchange code: `SEHK`
- Ticker format: 4-5 digit with `.HK` suffix → KIS format 변환
- HKStockParser 재사용

#### 2.3. CN Adapter (KIS 기반) - 1일

**파일**: `modules/market_adapters/cn_adapter_kis.py`

**구현 특징**:
- Exchange codes: `SHAA` (Shanghai), `SZAA` (Shenzhen)
- **선강통/후강통 경로만**: KIS API가 거래 가능 종목만 제공
- Ticker format: 6-digit with `.SS/.SZ` suffix → KIS format 변환
- CNStockParser 재사용 (CSRC → GICS mapping)

**장점**:
- AkShare fallback 불필요 (KIS API가 primary)
- 거래 불가 A-shares 자동 제외

#### 2.4. JP Adapter (KIS 기반) - 0.5일

**파일**: `modules/market_adapters/jp_adapter_kis.py`

**구현 특징**:
- Exchange code: `TKSE`
- Ticker format: 4-digit → KIS format 변환
- JPStockParser 재사용 (TSE → GICS mapping)

#### 2.5. VN Adapter (KIS 기반) - 0.5일

**파일**: `modules/market_adapters/vn_adapter_kis.py`

**구현 특징**:
- Exchange codes: `HASE` (HOSE), `VNSE` (HNX)
- Ticker format: 3-letter → KIS format 변환
- VNStockParser 재사용 (ICB → GICS mapping)

---

### Step 3: Parser 업데이트 (0.5일)

**목표**: KIS API 응답 형식에 맞게 parser 수정

**변경 필요 파일**:
1. `modules/parsers/us_stock_parser.py`
2. `modules/parsers/hk_stock_parser.py`
3. `modules/parsers/cn_stock_parser.py`
4. `modules/parsers/jp_stock_parser.py`
5. `modules/parsers/vn_stock_parser.py`

**변경 사항**:
- KIS API 응답 필드 매핑 추가
- Ticker normalization 로직 업데이트
- 기존 yfinance/Polygon.io 로직 유지 (backward compatibility)

**예시** (us_stock_parser.py):
```python
def parse_ticker_info_kis(self, kis_response: Dict) -> Optional[Dict]:
    """
    Parse KIS API ticker info to standardized format

    Args:
        kis_response: Dictionary from KIS API

    Returns:
        Standardized ticker data dictionary
    """
    ticker = kis_response.get('symb', '')
    name = kis_response.get('name', '')
    # ... KIS-specific field mapping
```

---

### Step 4: Unit Tests (1일)

**목표**: KIS API 및 KIS-based adapters 테스트

#### 4.1. KIS Overseas API Tests

**파일**: `tests/test_kis_overseas_api.py`

**테스트 케이스**:
```python
class TestKISOverseasAPI:
    def test_authentication(self)
    def test_get_tradable_tickers_us(self)
    def test_get_tradable_tickers_hk(self)
    def test_get_ohlcv_us(self)
    def test_get_ohlcv_hk(self)
    def test_get_current_price_us(self)
    def test_rate_limiting(self)
    def test_token_refresh(self)
```

#### 4.2. KIS-Based Adapter Tests

**파일**: `tests/test_us_adapter_kis.py`, etc.

**테스트 케이스** (각 adapter):
- Adapter initialization
- Stock scanning (tradable tickers only)
- OHLCV collection
- Fundamentals collection (yfinance fallback)
- Custom ticker management
- Parser integration

---

### Step 5: Demo Scripts & Integration Tests (0.5일)

**목표**: End-to-end 통합 테스트

#### 5.1. US Market Demo (KIS 기반)

**파일**: `examples/us_adapter_kis_demo.py`

**테스트 시나리오**:
1. KIS API로 US tradable tickers 조회 (AAPL, MSFT, TSLA)
2. OHLCV data 수집 (250 days)
3. Fundamentals 수집 (yfinance fallback)
4. Database 저장 및 검증

#### 5.2. 다른 시장 Demo

- `examples/hk_adapter_kis_demo.py`
- `examples/cn_adapter_kis_demo.py`
- `examples/jp_adapter_kis_demo.py`
- `examples/vn_adapter_kis_demo.py`

---

### Step 6: Performance Comparison (0.5일)

**목표**: KIS API vs 기존 API 성능 비교

**측정 지표**:
1. **Ticker List Retrieval Time**:
   - Polygon.io: 5 req/min (12초/요청)
   - KIS API: 20 req/sec (0.05초/요청)
   - **예상**: 240배 빠름

2. **OHLCV Collection Time** (100 tickers, 250 days):
   - Polygon.io: 100 tickers × 12초 = 1,200초 (20분)
   - KIS API: 100 tickers × 0.05초 = 5초
   - **예상**: 240배 빠름

3. **Tradable Ticker Coverage**:
   - Polygon.io: ~8,000 US tickers (거래 불가 포함)
   - KIS API: ~3,000 US tickers (거래 가능만)
   - **필터링 효과**: 62.5% 불필요 데이터 제거

---

### Step 7: Documentation & Completion Report (0.5일)

**목표**: Phase 6 완료 문서화

#### 7.1. Phase 6 Completion Report

**파일**: `docs/PHASE6_KIS_GLOBAL_COMPLETION_REPORT.md`

**포함 내용**:
- Executive summary (100% completion status)
- Implementation details (KIS API client + 5 adapters)
- Unit test results (target: 100% pass rate)
- Performance comparison (KIS API vs 기존 API)
- Data quality verification (sample stocks)
- Known limitations
- Next steps (Phase 7 or enhancements)

#### 7.2. CLAUDE.md Update

**파일**: `CLAUDE.md`

**업데이트 내용**:
- Phase 6 completion status
- KIS API integration architecture
- Updated tech stack (remove Polygon.io, AkShare primary)
- Updated market coverage table

---

## 📁 예상 파일 구조

### API Clients
```
modules/api_clients/
   kis_domestic_stock_api.py      # Existing (Phase 1)
   kis_overseas_stock_api.py      # ✅ NEW (Phase 6)
   polygon_api.py                  # Deprecated (fallback)
   yfinance_api.py                 # Fallback (fundamentals)
   akshare_api.py                  # Deprecated (fallback)
```

### Market Adapters
```
modules/market_adapters/
   base_adapter.py                 # Existing
   kr_adapter.py                   # Existing (Phase 1)

   # Phase 6: KIS-based adapters
   us_adapter_kis.py               # 🚧 NEW
   hk_adapter_kis.py               # 🚧 NEW
   cn_adapter_kis.py               # 🚧 NEW
   jp_adapter_kis.py               # 🚧 NEW
   vn_adapter_kis.py               # 🚧 NEW

   # Deprecated (fallback)
   us_adapter.py                   # Phase 2 (Polygon.io)
   hk_adapter.py                   # Phase 3 (yfinance)
   cn_adapter.py                   # Phase 3 (AkShare)
   jp_adapter.py                   # Phase 4 (yfinance)
   vn_adapter.py                   # Phase 5 (yfinance)
```

### Tests
```
tests/
   test_kis_overseas_api.py        # 🚧 NEW
   test_us_adapter_kis.py          # 🚧 NEW
   test_hk_adapter_kis.py          # 🚧 NEW
   test_cn_adapter_kis.py          # 🚧 NEW
   test_jp_adapter_kis.py          # 🚧 NEW
   test_vn_adapter_kis.py          # 🚧 NEW
```

### Examples
```
examples/
   us_adapter_kis_demo.py          # 🚧 NEW
   hk_adapter_kis_demo.py          # 🚧 NEW
   cn_adapter_kis_demo.py          # 🚧 NEW
   jp_adapter_kis_demo.py          # 🚧 NEW
   vn_adapter_kis_demo.py          # 🚧 NEW
```

---

## ⚠️ Known Limitations & Challenges

### 1. KIS API Endpoint 확인 필요
**문제**: KIS API documentation 불완전
- `/uapi/overseas-price/v1/quotations/inquire-search` endpoint 확인 필요
- TR_ID codes 검증 필요
- Response format 확인 필요

**해결 방안**:
1. KIS API portal documentation 재확인
2. GitHub sample code 참고
3. 실제 API 호출 테스트로 response format 확인
4. 필요시 KIS API support에 문의

### 2. Ticker Format 변환
**문제**: KIS API ticker format ↔ Internal format 변환
- US: AAPL (KIS) → AAPL (internal) - 동일
- HK: 0700 (KIS) → 0700 (internal) - suffix 제거 필요
- CN: 600000 (KIS) → 600000 (internal) - exchange code 제거 필요
- JP: 7203 (KIS) → 7203 (internal) - suffix 제거 필요
- VN: VCB (KIS) → VCB (internal) - 동일

**해결 방안**:
- Parser에서 normalization 로직 추가
- KIS API response에서 exchange code 추출
- denormalize_ticker() 메서드로 역변환

### 3. Fundamentals Data Gap
**문제**: KIS API는 OHLCV만 제공, fundamentals 미제공
- P/E ratio, P/B ratio, market cap 등 없음

**해결 방안**:
- yfinance API를 fundamentals 전용으로 유지
- collect_fundamentals() 메서드는 yfinance 사용
- KIS API는 ticker list + OHLCV만 담당

### 4. Historical Data Limit
**문제**: KIS API historical data 제한 가능성
- 일부 거래소는 최대 1년 데이터만 제공 가능

**해결 방안**:
- 각 거래소별 historical data limit 확인
- 필요시 yfinance로 보완 (long-term historical data)

---

## 📊 Phase 6 성공 지표

| 지표 | 목표 | 현재 상태 | 비고 |
|------|------|----------|------|
| KIS Overseas API 구현 | 100% | ✅ 100% | 530 lines |
| US Adapter (KIS) | 100% | 🚧 0% | 목표: 1일 |
| HK Adapter (KIS) | 100% | 🚧 0% | 목표: 0.5일 |
| CN Adapter (KIS) | 100% | 🚧 0% | 목표: 1일 |
| JP Adapter (KIS) | 100% | 🚧 0% | 목표: 0.5일 |
| VN Adapter (KIS) | 100% | 🚧 0% | 목표: 0.5일 |
| Unit Tests | ≥95% pass | 🚧 0% | 목표: 100% |
| Integration Tests | Pass | 🚧 0% | 5 demo scripts |
| Performance Improvement | >100x | 🚧 측정 예정 | vs Polygon.io |
| Documentation | Complete | 🚧 25% | Implementation plan done |

---

## 🎉 예상 최종 결과

**Phase 6 완료 시**:
```
✅ Phase 1: Korea (KOSPI/KOSDAQ)     - KIS API (domestic)
✅ Phase 6: US (NYSE/NASDAQ/AMEX)    - KIS API (overseas) ← NEW
✅ Phase 6: Hong Kong (HKEX)         - KIS API (overseas) ← NEW
✅ Phase 6: China (SSE/SZSE)         - KIS API (overseas) ← NEW
✅ Phase 6: Japan (TSE)              - KIS API (overseas) ← NEW
✅ Phase 6: Vietnam (HOSE/HNX)       - KIS API (overseas) ← NEW

🌏 6-Market Unified Trading System: KIS API 기반 완전 통합
```

**핵심 달성 사항**:
- ✅ **단일 API**: KIS API로 모든 시장 통합
- ✅ **실거래 가능 종목만**: 한국인 거래 가능 종목만 수집
- ✅ **240배 빠른 속도**: 20 req/sec (Polygon.io 대비)
- ✅ **비용 절감**: 외부 API 키 불필요
- ✅ **통일된 포맷**: 유지보수 복잡도 감소

---

## 📌 다음 단계 (Phase 6 이후)

### Option 1: Phase 7 - Singapore Market
- **거래소**: SGX (Singapore Exchange)
- **KIS API**: `SGXC` exchange code 지원
- **예상 소요**: 2-3일

### Option 2: Enhancement Phase
1. **Database Interface Standardization**
   - Fix SQLiteDatabaseManager compatibility issues
   - Standardize save_ticker, get_tickers API across all adapters

2. **ETF Support**
   - KIS API ETF endpoints 조사
   - ETF scanning and OHLCV collection

3. **Cross-Market Analysis Tools**
   - Sector correlation analysis across 6 markets
   - Currency-adjusted performance comparison
   - Global portfolio optimization

### Option 3: Trading Engine Integration
- KIS API order execution (domestic + overseas)
- Multi-market portfolio management
- Cross-border investment strategies

---

**Report Generated**: 2025-10-15
**Author**: Spock Trading System
**Version**: 1.0
**Status**: 🚧 IN PROGRESS
