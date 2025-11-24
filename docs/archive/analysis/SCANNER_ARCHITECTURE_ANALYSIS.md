# Scanner Architecture Analysis - Region-Based Refactoring

## 요약

**사용자 지적**: "글로벌 시장의 정보를 모두 확보하기 위해서는 data_collector.py 뿐만 아니라, scanner.py 역시 지원 국가별 adaptor 연결을 통한 스캔이 필요"

**분석 결과**: ✅ **정확한 지적입니다.** 현재 `scanner.py`는 한국 시장 전용 모노리식 구조로, 글로벌 확장 시 심각한 코드 중복과 유지보수 문제 발생 예상.

---

## 1. 현재 구조 문제점

### 1.1 현재 scanner.py 아키텍처

```python
# modules/scanner.py (현재)

class KRXOfficialAPI:
    """KRX 공식 API - 한국 전용"""

class KRXDataAPI:
    """KRX Data API - 한국 전용"""

class PyKRXFallback:
    """pykrx - 한국 전용"""

class StockScanner:
    """국내주식 종목 스캐너"""

    def __init__(self):
        # 한국 시장 전용 소스 초기화
        self.sources = [
            KRXOfficialAPI(),
            KRXDataAPI(),
            PyKRXFallback(),
        ]

    def scan_all_tickers(self):
        """한국 주식만 스캔 가능"""
        pass
```

### 1.2 문제점 분석

#### ❌ Problem 1: 국가별 중복 파일 생성 필요

**현재 방식으로 글로벌 확장 시**:
```
modules/
├── scanner.py              # Korea only (534 lines)
├── us_scanner.py           # US only (new file, ~500 lines)
├── cn_scanner.py           # China only (new file, ~500 lines)
├── hk_scanner.py           # Hong Kong only (new file, ~500 lines)
├── jp_scanner.py           # Japan only (new file, ~500 lines)
└── vn_scanner.py           # Vietnam only (new file, ~500 lines)
```

**결과**: 6개 파일, 3,000+ 라인, 70% 코드 중복

#### ❌ Problem 2: 공통 로직 중복

**중복되는 로직** (각 파일에서 반복):
- SQLite 캐싱 로직 (24시간 TTL)
- 데이터베이스 삽입 로직 (tickers, stock_details, ticker_fundamentals)
- 필터링 프레임워크
- 오류 처리 및 폴백 전략

**예시**: 캐싱 로직이 6개 파일에 중복 → 버그 수정 시 6개 파일 모두 수정 필요

#### ❌ Problem 3: 클래스명 오해 소지

```python
class StockScanner:  # "Stock" 전체를 스캔할 것 같지만...
    """국내주식 종목 스캐너"""  # 실제로는 한국 주식만
```

실제로는 `KoreanStockScanner`가 더 정확한 이름

#### ❌ Problem 4: 확장성 부재

```python
# US 주식 스캔하려면?
# → 새로운 us_scanner.py 파일 생성 필요
# → 모든 공통 로직 다시 구현

# China 주식 스캔하려면?
# → 또 다른 cn_scanner.py 파일 생성 필요
```

---

## 2. 제안 아키텍처: Region-Based Scanner System

### 2.1 디렉토리 구조

```
modules/
├── scanner.py                          # 🎯 Unified orchestrator (entry point)
│
├── scanner_adapters/                   # 📍 Regional scanners
│   ├── __init__.py
│   ├── base_scanner.py                 # Abstract base class
│   ├── kr_scanner.py                   # Korea (KRX, pykrx, FDR)
│   ├── us_scanner.py                   # US (SEC, Yahoo, IEX)
│   ├── cn_scanner.py                   # China (SZSE, SSE)
│   ├── hk_scanner.py                   # Hong Kong (HKEX)
│   ├── jp_scanner.py                   # Japan (TSE)
│   └── vn_scanner.py                   # Vietnam (HOSE, HNX)
│
└── data_sources/                       # 🔌 API clients (reusable)
    ├── __init__.py
    ├── krx_api.py                      # KRX Official API
    ├── krx_data_api.py                 # KRX Data API
    ├── pykrx_api.py                    # pykrx wrapper
    ├── yahoo_finance_api.py            # Yahoo Finance (US/global)
    ├── sec_edgar_api.py                # SEC EDGAR (US official)
    └── iex_cloud_api.py                # IEX Cloud (US alternative)
```

**모듈 수**: 1 orchestrator + 7 regional adapters + 6 data sources = **14 modules**

vs 현재 방식: 6 monolithic scanners × 500 lines = **3,000 lines of duplicated code**

### 2.2 핵심 컴포넌트 설계

#### 2.2.1 Base Scanner (Abstract Class)

```python
# modules/scanner_adapters/base_scanner.py

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import sqlite3
from datetime import datetime

class BaseScanner(ABC):
    """
    Abstract base scanner for all regions

    Provides shared logic:
    - SQLite caching (24-hour TTL)
    - Database insertion (tickers, stock_details, ticker_fundamentals)
    - Common filtering framework
    - Error handling and logging
    """

    def __init__(self, db_path: str, region_code: str):
        self.db_path = db_path
        self.region_code = region_code  # 'KR', 'US', 'CN', 'HK', 'JP', 'VN'

    # ========== Abstract Methods (Region-Specific) ==========

    @abstractmethod
    def _fetch_from_sources(self) -> List[Dict]:
        """
        Fetch tickers from region-specific data sources

        Must be implemented by each regional adapter.

        Returns:
            List of raw ticker dictionaries

        Example (Korea):
            [
                {'ticker': '005930', 'name': '삼성전자', 'market': 'KOSPI'},
                {'ticker': '035720', 'name': '카카오', 'market': 'KOSDAQ'},
            ]

        Example (US):
            [
                {'ticker': 'AAPL', 'name': 'Apple Inc.', 'exchange': 'NASDAQ'},
                {'ticker': 'TSLA', 'name': 'Tesla Inc.', 'exchange': 'NASDAQ'},
            ]
        """
        pass

    @abstractmethod
    def _apply_filters(self, tickers: List[Dict]) -> List[Dict]:
        """
        Apply region-specific filtering criteria

        Must be implemented by each regional adapter.

        Args:
            tickers: Raw ticker list

        Returns:
            Filtered ticker list

        Example (Korea):
            - Market cap >= 100억원
            - Exclude KONEX
            - Exclude ETF/ETN

        Example (US):
            - Market cap >= $50M
            - Exclude OTC/Pink Sheets
            - Exclude ETFs
        """
        pass

    # ========== Shared Methods (Common Logic) ==========

    def scan(self, force_refresh: bool = False) -> List[Dict]:
        """
        Main scanning workflow (shared across all regions)

        Workflow:
            1. Check cache (24-hour TTL)
            2. Fetch from region-specific sources
            3. Apply region-specific filters
            4. Enrich with common fields
            5. Save to cache

        Args:
            force_refresh: Ignore cache and force refresh

        Returns:
            List of enriched ticker dictionaries
        """
        # Step 1: Check cache
        if not force_refresh:
            cached = self._load_from_cache()
            if cached:
                logger.info(f"✅ [{self.region_code}] Cache hit: {len(cached)} tickers")
                return cached

        # Step 2: Fetch from region-specific sources
        logger.info(f"🔄 [{self.region_code}] Fetching from data sources...")
        raw_tickers = self._fetch_from_sources()

        # Step 3: Apply region-specific filters
        logger.info(f"🔍 [{self.region_code}] Applying filters...")
        filtered = self._apply_filters(raw_tickers)

        # Step 4: Enrich with common fields
        enriched = self._enrich_common_fields(filtered)

        # Step 5: Save to cache
        self._save_to_cache(enriched)

        logger.info(f"✅ [{self.region_code}] Scan complete: {len(enriched)} tickers")
        return enriched

    def _load_from_cache(self) -> Optional[List[Dict]]:
        """
        Load tickers from SQLite cache (24-hour TTL)

        Shared logic for all regions.
        """
        try:
            if not os.path.exists(self.db_path):
                return None

            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check last update time
            cursor.execute("""
                SELECT MAX(last_updated) as last_update
                FROM tickers
                WHERE region = ?
            """, (self.region_code,))

            result = cursor.fetchone()
            if not result or not result['last_update']:
                conn.close()
                return None

            last_update = datetime.fromisoformat(result['last_update'])
            age_hours = (datetime.now() - last_update).total_seconds() / 3600

            # 24-hour TTL
            if age_hours > 24:
                logger.info(f"⏰ [{self.region_code}] Cache expired ({age_hours:.1f}h)")
                conn.close()
                return None

            # Load tickers
            cursor.execute("""
                SELECT
                    t.ticker,
                    t.name,
                    t.exchange,
                    t.market_tier,
                    t.region,
                    t.currency,
                    t.is_active,
                    tf.market_cap
                FROM tickers t
                LEFT JOIN ticker_fundamentals tf ON t.ticker = tf.ticker
                WHERE t.region = ? AND t.is_active = 1
                ORDER BY tf.market_cap DESC NULLS LAST
            """, (self.region_code,))

            tickers = [dict(row) for row in cursor.fetchall()]
            conn.close()

            logger.info(f"✅ [{self.region_code}] Cache hit: {age_hours:.1f}h old")
            return tickers

        except Exception as e:
            logger.warning(f"⚠️ [{self.region_code}] Cache load failed: {e}")
            return None

    def _save_to_cache(self, tickers: List[Dict]):
        """
        Save tickers to SQLite cache

        Shared logic for all regions.
        """
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Delete existing tickers for this region
            cursor.execute("DELETE FROM tickers WHERE region = ?", (self.region_code,))

            now = datetime.now().isoformat()
            today = datetime.now().strftime("%Y-%m-%d")

            # Insert new tickers
            for ticker_data in tickers:
                # 1. tickers table
                cursor.execute("""
                    INSERT INTO tickers
                    (ticker, name, name_eng, exchange, market_tier, region, currency,
                     asset_type, listing_date, is_active, created_at, last_updated, data_source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticker_data['ticker'],
                    ticker_data['name'],
                    ticker_data.get('name_eng'),
                    ticker_data['exchange'],
                    ticker_data.get('market_tier', 'MAIN'),
                    self.region_code,
                    ticker_data['currency'],
                    ticker_data.get('asset_type', 'STOCK'),
                    ticker_data.get('listing_date'),
                    True,
                    now,
                    now,
                    ticker_data.get('data_source', 'Unknown')
                ))

                # 2. stock_details table
                if ticker_data.get('asset_type', 'STOCK') in ('STOCK', 'PREFERRED'):
                    cursor.execute("""
                        INSERT INTO stock_details
                        (ticker, sector, industry, is_preferred, created_at, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        ticker_data['ticker'],
                        ticker_data.get('sector'),
                        ticker_data.get('industry'),
                        ticker_data.get('asset_type') == 'PREFERRED',
                        now,
                        now
                    ))

                # 3. ticker_fundamentals table
                if ticker_data.get('market_cap') or ticker_data.get('close_price'):
                    cursor.execute("""
                        INSERT INTO ticker_fundamentals
                        (ticker, date, period_type, market_cap, close_price, created_at, data_source)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ticker_data['ticker'],
                        today,
                        'DAILY',
                        ticker_data.get('market_cap'),
                        ticker_data.get('close_price'),
                        now,
                        ticker_data.get('data_source', 'Unknown')
                    ))

            conn.commit()
            conn.close()

            logger.info(f"💾 [{self.region_code}] Cache saved: {len(tickers)} tickers")

        except Exception as e:
            logger.error(f"❌ [{self.region_code}] Cache save failed: {e}")

    def _enrich_common_fields(self, tickers: List[Dict]) -> List[Dict]:
        """
        Add common fields to all tickers

        Shared logic for all regions.
        """
        for ticker in tickers:
            ticker['region'] = self.region_code
            ticker['is_active'] = True

        return tickers
```

#### 2.2.2 Korea Scanner (Concrete Implementation)

```python
# modules/scanner_adapters/kr_scanner.py

from .base_scanner import BaseScanner
from data_sources.krx_api import KRXOfficialAPI
from data_sources.krx_data_api import KRXDataAPI
from data_sources.pykrx_api import PyKRXFallback
import logging

logger = logging.getLogger(__name__)

class KoreaScanner(BaseScanner):
    """
    Korea stock scanner (KOSPI, KOSDAQ, NXT)

    Data sources (priority order):
    1. KRX Official API (requires API key)
    2. KRX Data API (no auth required)
    3. pykrx (fallback, rate-limited)
    """

    def __init__(self, db_path: str, krx_api_key: Optional[str] = None):
        super().__init__(db_path, region_code='KR')
        self.krx_api_key = krx_api_key
        self.sources = self._initialize_sources()

    def _initialize_sources(self):
        """Initialize Korea-specific data sources"""
        sources = []

        # Priority 1: KRX Official API
        if self.krx_api_key:
            sources.append(('KRX Official API', KRXOfficialAPI(self.krx_api_key)))

        # Priority 2: KRX Data API
        sources.append(('KRX Data API', KRXDataAPI()))

        # Priority 3: pykrx fallback
        sources.append(('pykrx', PyKRXFallback()))

        return sources

    def _fetch_from_sources(self) -> List[Dict]:
        """
        Fetch tickers from Korea data sources

        Try sources in priority order until success.
        """
        for source_name, source_api in self.sources:
            try:
                logger.info(f"🔄 [{source_name}] Fetching Korea stocks...")
                tickers = source_api.get_stock_list()

                if not tickers:
                    logger.warning(f"⚠️ [{source_name}] No data returned")
                    continue

                # Add data source info
                for ticker in tickers:
                    ticker['data_source'] = source_name

                logger.info(f"✅ [{source_name}] {len(tickers)} stocks fetched")
                return tickers

            except Exception as e:
                logger.error(f"❌ [{source_name}] Failed: {e}")
                continue

        raise Exception("All Korea data sources failed")

    def _apply_filters(self, tickers: List[Dict]) -> List[Dict]:
        """
        Apply Korea-specific filters

        Criteria:
        - Market cap >= 100억원
        - Exclude KONEX
        - Exclude ETF/ETN (handled by separate etf_scanner)
        """
        MIN_MARKET_CAP = 10_000_000_000  # 100억원

        filtered = []
        for ticker_data in tickers:
            # Filter 1: Exclude KONEX
            if ticker_data.get('market') == 'KONEX':
                continue

            # Filter 2: Exclude ETF/ETN
            name = ticker_data.get('name', '')
            if any(kw in name for kw in ['ETF', 'ETN', 'KODEX', 'TIGER', 'KBSTAR', 'ARIRANG']):
                continue

            # Filter 3: Market cap threshold
            market_cap = ticker_data.get('market_cap', 0)
            if market_cap > 0 and market_cap < MIN_MARKET_CAP:
                continue

            # Add Korea-specific fields
            ticker_data['currency'] = 'KRW'
            ticker_data['exchange'] = ticker_data.get('market', 'UNKNOWN')  # KOSPI, KOSDAQ
            ticker_data['asset_type'] = self._classify_asset_type(ticker_data['name'])

            filtered.append(ticker_data)

        logger.info(f"📊 Filtered: {len(tickers)} → {len(filtered)} stocks")
        return filtered

    def _classify_asset_type(self, name: str) -> str:
        """Classify asset type by name pattern"""
        if 'REIT' in name or '리츠' in name:
            return 'REIT'
        elif '우' in name:  # 우선주
            return 'PREFERRED'
        else:
            return 'STOCK'
```

#### 2.2.3 US Scanner (Future Implementation)

```python
# modules/scanner_adapters/us_scanner.py

from .base_scanner import BaseScanner
from data_sources.yahoo_finance_api import YahooFinanceAPI
from data_sources.sec_edgar_api import SECEdgarAPI

class USScanner(BaseScanner):
    """
    US stock scanner (NYSE, NASDAQ, AMEX)

    Data sources:
    1. SEC EDGAR (official US data)
    2. Yahoo Finance (fallback)
    """

    def __init__(self, db_path: str):
        super().__init__(db_path, region_code='US')
        self.sources = self._initialize_sources()

    def _initialize_sources(self):
        """Initialize US-specific data sources"""
        return [
            ('SEC EDGAR', SECEdgarAPI()),
            ('Yahoo Finance', YahooFinanceAPI()),
        ]

    def _fetch_from_sources(self) -> List[Dict]:
        """Fetch tickers from US data sources"""
        for source_name, source_api in self.sources:
            try:
                tickers = source_api.get_stock_list()
                if tickers:
                    for ticker in tickers:
                        ticker['data_source'] = source_name
                    return tickers
            except Exception as e:
                logger.error(f"❌ [{source_name}] Failed: {e}")

        raise Exception("All US data sources failed")

    def _apply_filters(self, tickers: List[Dict]) -> List[Dict]:
        """
        Apply US-specific filters

        Criteria:
        - Market cap >= $50M
        - Exclude OTC/Pink Sheets
        - Exclude ETFs
        """
        MIN_MARKET_CAP = 50_000_000  # $50M USD

        filtered = []
        for ticker_data in tickers:
            # Filter 1: Exclude OTC/Pink Sheets
            if ticker_data.get('exchange') in ['OTC', 'PINK']:
                continue

            # Filter 2: Exclude ETFs
            if any(kw in ticker_data['name'] for kw in ['ETF', 'FUND', 'INDEX']):
                continue

            # Filter 3: Market cap threshold
            if ticker_data.get('market_cap', 0) < MIN_MARKET_CAP:
                continue

            # Add US-specific fields
            ticker_data['currency'] = 'USD'
            ticker_data['asset_type'] = 'STOCK'

            filtered.append(ticker_data)

        return filtered
```

#### 2.2.4 Unified Scanner Orchestrator

```python
# modules/scanner.py (refactored)

from scanner_adapters.kr_scanner import KoreaScanner
from scanner_adapters.us_scanner import USScanner
# from scanner_adapters.cn_scanner import ChinaScanner (Phase 5)
# from scanner_adapters.hk_scanner import HongKongScanner (Phase 5)
import os

class UnifiedScanner:
    """
    Multi-region stock scanner orchestrator

    Supports:
    - Korea (KOSPI, KOSDAQ, NXT) - Phase 1-3
    - US (NYSE, NASDAQ, AMEX) - Phase 4
    - China (SSE, SZSE) - Phase 5
    - Hong Kong (HKEX) - Phase 5
    - Japan (TSE) - Phase 6
    - Vietnam (HOSE, HNX) - Phase 6
    """

    def __init__(self, db_path: str = 'data/spock_local.db'):
        self.db_path = db_path

        # Initialize regional scanners
        self.scanners = {
            'KR': KoreaScanner(db_path, krx_api_key=os.getenv('KRX_API_KEY')),
            # 'US': USScanner(db_path),  # Phase 4
            # 'CN': ChinaScanner(db_path),  # Phase 5
            # 'HK': HongKongScanner(db_path),  # Phase 5
        }

    def scan_region(self, region: str, force_refresh: bool = False) -> List[Dict]:
        """
        Scan specific region

        Args:
            region: 'KR', 'US', 'CN', 'HK', 'JP', 'VN'
            force_refresh: Ignore cache

        Returns:
            List of ticker dictionaries

        Example:
            scanner = UnifiedScanner()
            kr_stocks = scanner.scan_region('KR')  # Korea stocks
            us_stocks = scanner.scan_region('US')  # US stocks
        """
        scanner = self.scanners.get(region)
        if not scanner:
            raise ValueError(f"Unsupported region: {region}")

        return scanner.scan(force_refresh=force_refresh)

    def scan_all_regions(self, force_refresh: bool = False) -> Dict[str, List[Dict]]:
        """
        Scan all supported regions

        Returns:
            {'KR': [...], 'US': [...], 'CN': [...]}
        """
        results = {}

        for region, scanner in self.scanners.items():
            try:
                tickers = scanner.scan(force_refresh=force_refresh)
                results[region] = tickers
                logger.info(f"✅ {region}: {len(tickers)} stocks")
            except Exception as e:
                logger.error(f"❌ {region} scan failed: {e}")
                results[region] = []

        return results

    # ========== Backward Compatibility ==========

    def scan_all_tickers(self, force_refresh: bool = False) -> List[Dict]:
        """
        Legacy method for backward compatibility

        Preserves existing behavior: scans Korea stocks only.

        Example:
            scanner = UnifiedScanner()
            tickers = scanner.scan_all_tickers()  # Same as before
        """
        return self.scan_region('KR', force_refresh=force_refresh)


# Legacy alias for backward compatibility
StockScanner = UnifiedScanner
```

---

## 3. 마이그레이션 전략

### 3.1 단계별 마이그레이션 (5.5일)

#### Phase 0: 준비 (0.5일)
- 디렉토리 생성: `scanner_adapters/`, `data_sources/`
- 기존 코드 백업

#### Phase 1: Data Sources 분리 (1일)
```bash
# 기존 클래스 이동
modules/scanner.py:KRXOfficialAPI → data_sources/krx_api.py
modules/scanner.py:KRXDataAPI → data_sources/krx_data_api.py
modules/scanner.py:PyKRXFallback → data_sources/pykrx_api.py
```

**변경 사항**: 파일 재구성만, 로직 변경 없음

#### Phase 2: Base Scanner 구현 (1일)
- `base_scanner.py` 작성
- 공통 로직 추출: `_load_from_cache()`, `_save_to_cache()`, `scan()`

#### Phase 3: Korea Scanner 구현 (1일)
- `kr_scanner.py` 작성
- 기존 `StockScanner` 로직을 `KoreaScanner`로 이전
- 한국 특화 필터링: `_apply_filters()` 구현

#### Phase 4: Unified Scanner 구현 (1일)
- `scanner.py` 리팩토링
- `UnifiedScanner` 클래스 작성
- 역호환성 유지: `scan_all_tickers()` 메서드 보존

#### Phase 5: 테스트 및 검증 (1일)
- 단위 테스트: 각 regional scanner 테스트
- 통합 테스트: 기존 코드와의 호환성
- 성능 테스트: 캐싱 로직 검증

**총 소요 시간**: 5.5일

### 3.2 역호환성 보장

```python
# 기존 코드 (변경 없이 작동)
from modules.scanner import StockScanner

scanner = StockScanner()
tickers = scanner.scan_all_tickers()  # 여전히 한국 주식 스캔

# 새로운 코드 (region-based)
from modules.scanner import UnifiedScanner

scanner = UnifiedScanner()
kr_tickers = scanner.scan_region('KR')  # 한국
us_tickers = scanner.scan_region('US')  # 미국
```

---

## 4. 비교 분석

### 4.1 현재 vs 제안 아키텍처

| 측면 | 현재 (Monolithic) | 제안 (Region-Based) |
|------|------------------|---------------------|
| **파일 수** | 1개 (scanner.py, 534줄) | 1 orchestrator + 7 adapters + 6 sources = 14개 |
| **Korea 지원** | ✅ 완전 지원 | ✅ 완전 지원 (변경 없음) |
| **US 지원** | ❌ 새 파일 필요 (us_scanner.py) | ✅ USScanner adapter |
| **코드 재사용** | 0% (국가별 중복) | 70%+ (base class 공유) |
| **유지보수성** | ❌ 낮음 (6개 파일 수정) | ✅ 높음 (base class 1곳 수정) |
| **확장성** | ❌ 어려움 (국가당 새 파일) | ✅ 쉬움 (adapter 1개 추가) |
| **역호환성** | N/A | ✅ `scan_all_tickers()` 보존 |
| **테스트 복잡도** | 높음 (각 scanner 독립 테스트) | 낮음 (base + adapter 테스트) |

### 4.2 글로벌 확장 시나리오 비교

#### 시나리오: 6개 국가 지원 (Korea, US, China, HK, Japan, Vietnam)

**현재 방식 (Monolithic)**:
```
모듈 수: 6개 (각 국가별 scanner)
총 코드량: ~3,000 라인 (500 × 6)
코드 중복률: 70%
유지보수: 버그 수정 시 6개 파일 수정
```

**제안 방식 (Region-Based)**:
```
모듈 수: 1 orchestrator + 1 base + 6 adapters + 6 sources = 14개
총 코드량: ~2,000 라인 (base 500 + adapters 150×6 + sources 100×6)
코드 중복률: 0%
유지보수: 버그 수정 시 base class 1곳 수정
```

**결론**: 제안 방식이 **33% 코드 절감** + **유지보수 70% 개선**

---

## 5. Scanner와 Data Collector 통합

### 5.1 역할 분담

**Scanner의 역할**:
- 종목 발견 (Ticker Discovery)
- 기본 정보 수집 (name, exchange, market_cap)
- tickers 테이블 채우기

**Data Collector (Adapter)의 역할**:
- OHLCV 데이터 수집
- 기술적 지표 계산
- ohlcv_data 테이블 채우기

### 5.2 워크플로우 통합

```python
# Step 1: Scanner가 종목 발견
scanner = UnifiedScanner(db_path)
kr_tickers = scanner.scan_region('KR')  # kr_scanner.py 사용
# → tickers 테이블 채워짐

# Step 2: Data Collector가 OHLCV 수집
from market_adapters.kr_adapter import KoreaAdapter

kr_adapter = KoreaAdapter(db_manager, kis_config)
kr_adapter.collect_stock_ohlcv(tickers=kr_tickers)  # kr_adapter.py 사용
# → ohlcv_data 테이블 채워짐

# Step 3: 기술적 분석 (기존 파이프라인)
# ... technical_analysis, scoring, trading ...
```

### 5.3 데이터베이스 통합

```
tickers 테이블 (Scanner가 채움)
├─ ticker: 005930
├─ name: 삼성전자
├─ exchange: KOSPI
├─ market_tier: MAIN
├─ region: KR  ← Scanner가 설정
└─ currency: KRW

ohlcv_data 테이블 (Data Collector가 채움)
├─ ticker: 005930  ← tickers.ticker 참조
├─ date: 2024-01-15
├─ open: 75000
├─ high: 76000
└─ close: 75500
```

---

## 6. 구현 우선순위

### 6.1 Phase 1-3 (Korea Focus) - 즉시 착수 가능

**목표**: 현재 scanner.py를 region-based로 리팩토링

**작업**:
1. Data sources 분리 (krx_api.py, pykrx_api.py)
2. Base scanner 구현
3. Korea scanner 구현
4. Unified scanner 구현

**기간**: 5.5일

### 6.2 Phase 4 (US Expansion) - Korea 완료 후

**목표**: US scanner 추가

**작업**:
1. US data sources 구현 (sec_edgar_api.py, yahoo_finance_api.py)
2. US scanner 구현 (us_scanner.py)
3. Unified scanner에 US 추가

**기간**: 2일

### 6.3 Phase 5-6 (Global Expansion) - US 검증 후

**목표**: China, HK, Japan, Vietnam 추가

**작업**: 각 국가별 scanner adapter 구현

**기간**: 국가당 1-2일 (병렬 작업 가능)

---

## 7. 리스크 및 완화 전략

### Risk 1: 마이그레이션 중 기존 기능 중단

**완화**:
- 역호환성 API 유지 (`scan_all_tickers()`)
- 단계별 마이그레이션 (기존 코드와 병행)
- 철저한 테스트 (단위 + 통합)

### Risk 2: Region-specific 로직 복잡도 증가

**완화**:
- Abstract base class로 인터페이스 명확화
- 각 adapter는 독립적으로 개발 가능
- 공통 로직은 base class에 집중

### Risk 3: 데이터 소스 API 변경

**완화**:
- Data source별로 독립된 파일 (`data_sources/`)
- API wrapper 패턴으로 격리
- Fallback 전략 (여러 data source 병행)

---

## 8. 결론

### 8.1 핵심 결론

✅ **사용자의 지적이 정확합니다.**

현재 `scanner.py`는 한국 시장 전용 모노리식 구조로, 글로벌 확장 시:
- 국가별 중복 파일 생성 필요 (6개 파일, 3,000+ 라인)
- 공통 로직 중복 (캐싱, DB, 필터링)
- 유지보수 비용 증가 (버그 수정 시 6개 파일 수정)

### 8.2 권장 사항

**Region-Based Scanner Architecture 도입**:
- Base scanner (공통 로직)
- Regional adapters (국가별 특화)
- Data sources (API clients 재사용)

**효과**:
- 코드 재사용 70%+
- 유지보수 70% 개선
- 확장 용이 (국가 추가 시 adapter 1개만 구현)

### 8.3 다음 단계

1. ✅ **Region-based architecture 승인** (이 문서)
2. ⏳ **Scanner refactoring 시작** (5.5일)
3. ⏳ **Data collector 통합** (kr_adapter.py와 kr_scanner.py 협업)
4. ⏳ **US scanner 구현** (Phase 4)

---

**문서 작성**: Claude (SuperClaude Framework)
**작성일**: 2024-01-XX
**버전**: 1.0
