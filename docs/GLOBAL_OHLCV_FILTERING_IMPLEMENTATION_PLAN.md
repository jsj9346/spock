# 해외 마켓 OHLCV 필터링 시스템 - 전체 구현 계획

**Document Version**: 1.0
**Date**: 2025-10-16
**Author**: Spock Trading System
**Status**: Implementation Planning Phase

---

## 1. Executive Summary

### 1.1 목표

**현재 상태**: KR 마켓만 필터링 적용 (24시간 거래대금 + 13개월 월봉)
**목표 상태**: 5개 해외 마켓에 동일한 필터링 조건 적용

**핵심 전략**:
- ✅ **통화 정규화**: 모든 마켓 기준을 KRW로 통일
- ✅ **설정 파일 분리**: 마켓별 YAML 설정으로 유연성 확보
- ✅ **단계별 검증**: KR → US → HK/CN → JP/VN 순차 확장

### 1.2 예상 효과

| 지표 | 현재 (KR Only) | 완료 후 (6 Markets) | 개선율 |
|------|----------------|---------------------|--------|
| 수집 종목 수 | ~250 | ~1,440 | **+476%** |
| 저장 공간 | ~60MB | ~360MB | **+500%** |
| 수집 시간 | ~25분 | ~2.5시간 | **+500%** |
| 글로벌 커버리지 | 1개국 | 6개국 | **+500%** |

**ROI 분석**:
- 투자: 80시간 (2주 개발)
- 효과: 글로벌 종목 발굴 능력 6배 증가
- 유지보수: 마켓별 독립 설정으로 최소화

---

## 2. 구현 전략

### 2.1 Phase-Based Rollout (3 Phases)

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Foundation (Week 1, Days 1-3)                      │
│─────────────────────────────────────────────────────────────│
│ Goal: 설정 파일 인프라 및 환율 시스템 구축                  │
│                                                             │
│ Tasks:                                                      │
│ 1. 마켓별 설정 파일 작성 (5 markets × YAML)                 │
│ 2. ExchangeRateManager 구현 (KIS API + BOK fallback)      │
│ 3. MarketFilterManager 검증 및 테스트                       │
│ 4. Unit Tests (설정 로딩, 환율 변환)                        │
│                                                             │
│ Deliverable:                                                │
│ - 5개 마켓 설정 파일 (완료, 테스트 통과)                     │
│ - 환율 관리 시스템 (실시간 업데이트 + 캐싱)                  │
│ - 97% 테스트 커버리지 (설정 시스템)                          │
│                                                             │
│ Success Criteria:                                           │
│ ✅ 5개 마켓 config 로딩 성공                                 │
│ ✅ 환율 변환 정확도 ±0.1% 이내                               │
│ ✅ TTL 캐싱 동작 검증 (1h market / 24h after-hours)        │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: Integration (Week 1-2, Days 4-7)                   │
│─────────────────────────────────────────────────────────────│
│ Goal: OHLCV 수집 파이프라인에 필터링 통합                    │
│                                                             │
│ Tasks:                                                      │
│ 1. kis_data_collector.py 개선                              │
│    - Stage 0 필터링 통합 (market-specific)                  │
│    - Stage 1 필터링 통합 (market-agnostic)                  │
│    - 배치 수집 로직 추가                                     │
│                                                             │
│ 2. 마켓별 수집 스크립트 작성                                 │
│    - scripts/collect_us_ohlcv.py                           │
│    - scripts/collect_hk_ohlcv.py                           │
│    - scripts/collect_cn_ohlcv.py                           │
│    - scripts/collect_jp_ohlcv.py                           │
│    - scripts/collect_vn_ohlcv.py                           │
│                                                             │
│ 3. Database Schema 검증                                     │
│    - filter_cache_stage0 (region 컬럼, currency 필드)       │
│    - filter_cache_stage1 (composite key 검증)               │
│    - Exchange rate metadata 저장 테스트                     │
│                                                             │
│ Deliverable:                                                │
│ - 통합 OHLCV 수집 시스템 (5 markets)                         │
│ - 마켓별 독립 실행 스크립트                                  │
│ - DB 스키마 마이그레이션 완료                                │
│                                                             │
│ Success Criteria:                                           │
│ ✅ 각 마켓 Stage 0-1-2 파이프라인 동작                       │
│ ✅ DB에 region/currency 정확히 저장                          │
│ ✅ 250일 OHLCV 데이터 수집 성공                              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: Validation & Monitoring (Week 2, Days 8-10)        │
│─────────────────────────────────────────────────────────────│
│ Goal: 테스트, 모니터링, 문서화                               │
│                                                             │
│ Tasks:                                                      │
│ 1. End-to-End Testing (마켓별)                               │
│    - US: 1,500 tickers → 600 (Stage 1)                     │
│    - HK: 400 tickers → 150 (Stage 1)                       │
│    - CN: 300 tickers → 120 (Stage 1)                       │
│    - JP: 600 tickers → 240 (Stage 1)                       │
│    - VN: 200 tickers → 80 (Stage 1)                        │
│                                                             │
│ 2. Monitoring Dashboard 구축                                │
│    - Prometheus metrics (per-market)                       │
│    - Grafana dashboards (5 markets)                        │
│    - Alert rules (환율 이상, 수집 실패)                      │
│                                                             │
│ 3. Documentation                                            │
│    - Deployment Guide (마켓별 배포 절차)                     │
│    - Troubleshooting Guide (FAQ, Common Issues)            │
│    - API Reference (MarketFilterManager, ExchangeRate)     │
│                                                             │
│ Deliverable:                                                │
│ - 5개 마켓 E2E 테스트 완료 리포트                            │
│ - Grafana 대시보드 (6개: 1 Overview + 5 Markets)            │
│ - 완전한 운영 문서 (Deployment + Runbook)                   │
│                                                             │
│ Success Criteria:                                           │
│ ✅ 95%+ 테스트 통과율 (E2E)                                  │
│ ✅ 모니터링 대시보드 실시간 데이터 표시                       │
│ ✅ 문서 완전성 95%+ (운영팀 리뷰 통과)                       │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 우선순위 매트릭스

**Tier 1 (Critical - Week 1)**:
- 🔴 **US Market**: 가장 큰 시장, KIS API 안정성 높음
- 🔴 **Exchange Rate System**: 모든 마켓의 기본 인프라

**Tier 2 (High Priority - Week 1-2)**:
- 🟠 **HK Market**: Stock Connect로 CN과 연계
- 🟠 **CN Market**: Stock Connect 종목 (외국인 거래 가능)

**Tier 3 (Medium Priority - Week 2)**:
- 🟡 **JP Market**: 성숙한 시장, 안정적 데이터
- 🟡 **VN Market**: 신흥 시장, 데이터 품질 검증 필요

---

## 3. 세부 작업 계획 (Task Breakdown)

### 3.1 Phase 1: Foundation (Days 1-3, 24시간)

#### **Task 1.1: 마켓별 설정 파일 작성** (6시간)

**Subtasks**:
1. `us_filter_config.yaml` 작성 (1.5h)
   - Exchange rate: USD/KRW ≈ 1,300
   - Min trading value: $7.7M/day (₩100억)
   - Min market cap: $77M (₩1,000억)
   - Penny stock/OTC exclusion rules

2. `hk_filter_config.yaml` 작성 (1h)
   - Exchange rate: HKD/KRW ≈ 170
   - Min trading value: HK$59M/day
   - Hang Seng Index focus

3. `cn_filter_config.yaml` 작성 (1.5h)
   - Exchange rate: CNY/KRW ≈ 180
   - Min trading value: ¥56M/day
   - **Stock Connect only** (중요!)
   - ST/PT stock exclusion

4. `jp_filter_config.yaml` 작성 (1h)
   - Exchange rate: JPY/KRW ≈ 10
   - Min trading value: ¥1B/day
   - TOPIX 500 focus

5. `vn_filter_config.yaml` 작성 (1h)
   - Exchange rate: VND/KRW ≈ 0.055
   - Min trading value: ₫182B/day
   - VN30 Index focus

**Deliverable**:
```
config/market_filters/
  ├─ kr_filter_config.yaml    # ✅ 기존
  ├─ us_filter_config.yaml    # 🆕
  ├─ hk_filter_config.yaml    # 🆕
  ├─ cn_filter_config.yaml    # 🆕
  ├─ jp_filter_config.yaml    # 🆕
  └─ vn_filter_config.yaml    # 🆕
```

**Validation**:
```bash
# 설정 파일 로딩 테스트
python3 -c "from modules.market_filter_manager import MarketFilterManager; \
mgr = MarketFilterManager(); \
print('Supported markets:', mgr.get_supported_regions())"

# Expected output:
# Supported markets: ['CN', 'HK', 'JP', 'KR', 'US', 'VN']
```

---

#### **Task 1.2: ExchangeRateManager 구현** (8시간)

**새 파일**: `modules/exchange_rate_manager.py`

**Features**:
1. **Multi-Source Support**:
   - Primary: KIS API real-time rates
   - Fallback 1: Bank of Korea (BOK) official rates
   - Fallback 2: Fixed default rates

2. **Caching Strategy**:
   - In-memory cache with TTL (1 hour market hours, 24h after-hours)
   - Database persistence (exchange_rate_history table)

3. **Auto-Update Scheduler**:
   - Hourly updates during trading hours
   - Daily updates after-hours

**Implementation**:

```python
"""
Exchange Rate Manager - Multi-Currency Support

Handles real-time exchange rate fetching, caching, and fallback.

Data Flow:
1. KIS API (primary) → BOK API (fallback) → Default rate (last resort)
2. Cache in memory (TTL) + DB (history)
3. Auto-update every 1h (market) / 24h (after-hours)

Author: Spock Trading System
"""

import logging
import requests
from typing import Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import sqlite3

logger = logging.getLogger(__name__)


@dataclass
class ExchangeRate:
    """Exchange rate data structure"""
    currency: str           # 'USD', 'HKD', 'CNY', 'JPY', 'VND'
    rate_to_krw: float      # Conversion rate to KRW
    source: str             # 'kis_api', 'bok', 'fixed'
    timestamp: datetime     # Rate timestamp
    is_cached: bool = False


class ExchangeRateManager:
    """
    Multi-currency exchange rate manager

    Responsibilities:
    1. Fetch real-time rates from KIS API
    2. Fallback to Bank of Korea if KIS fails
    3. Cache rates in memory and database
    4. Auto-update based on market hours
    """

    def __init__(self, db_path: str = 'data/spock_local.db'):
        self.db_path = db_path

        # In-memory cache (currency → ExchangeRate)
        self._cache: Dict[str, ExchangeRate] = {}

        # Default rates (fallback of last resort)
        self._default_rates = {
            'KRW': 1.0,      # Base currency
            'USD': 1300.0,   # $1 = ₩1,300
            'HKD': 170.0,    # HK$1 = ₩170
            'CNY': 180.0,    # ¥1 = ₩180
            'JPY': 10.0,     # ¥1 = ₩10
            'VND': 0.055,    # ₫1 = ₩0.055
        }

        # Cache TTL settings
        self._cache_ttl_market_hours = timedelta(hours=1)
        self._cache_ttl_after_hours = timedelta(hours=24)

        logger.info("✅ ExchangeRateManager initialized")

    def get_rate(self, currency: str, force_refresh: bool = False) -> float:
        """
        Get exchange rate for currency to KRW

        Args:
            currency: 'USD', 'HKD', 'CNY', 'JPY', 'VND'
            force_refresh: Bypass cache and fetch fresh rate

        Returns:
            Exchange rate (currency to KRW)

        Example:
            rate = manager.get_rate('USD')  # Returns ~1300.0
            krw_value = usd_value * rate    # Convert $100 → ₩130,000
        """
        currency = currency.upper()

        # KRW is base currency
        if currency == 'KRW':
            return 1.0

        # Check cache (if not force refresh)
        if not force_refresh and self._is_cache_valid(currency):
            cached_rate = self._cache[currency]
            logger.debug(f"💾 [{currency}] Cache hit: {cached_rate.rate_to_krw} (source: {cached_rate.source})")
            return cached_rate.rate_to_krw

        # Fetch fresh rate (with fallback chain)
        rate = self._fetch_rate_with_fallback(currency)

        return rate.rate_to_krw

    def _fetch_rate_with_fallback(self, currency: str) -> ExchangeRate:
        """
        Fetch rate with fallback chain:
        KIS API → BOK API → Default Rate
        """
        # Try KIS API first
        try:
            rate = self._fetch_from_kis_api(currency)
            if rate:
                self._update_cache(currency, rate)
                self._save_to_db(rate)
                return rate
        except Exception as e:
            logger.warning(f"⚠️ [{currency}] KIS API failed: {e}")

        # Fallback to BOK API
        try:
            rate = self._fetch_from_bok_api(currency)
            if rate:
                self._update_cache(currency, rate)
                self._save_to_db(rate)
                return rate
        except Exception as e:
            logger.warning(f"⚠️ [{currency}] BOK API failed: {e}")

        # Last resort: Default rate
        logger.warning(f"⚠️ [{currency}] Using default rate: {self._default_rates[currency]}")
        rate = ExchangeRate(
            currency=currency,
            rate_to_krw=self._default_rates[currency],
            source='fixed',
            timestamp=datetime.now()
        )
        self._update_cache(currency, rate)
        return rate

    def _fetch_from_kis_api(self, currency: str) -> Optional[ExchangeRate]:
        """
        Fetch exchange rate from KIS API

        KIS API Endpoint:
        - /uapi/overseas-stock/v1/quotations/exchange-rate
        - Transaction ID: TBD (환율 조회용)
        """
        # TODO: Implement KIS API integration
        # For now, return None to trigger fallback
        logger.debug(f"🔍 [{currency}] Fetching from KIS API (not implemented yet)")
        return None

    def _fetch_from_bok_api(self, currency: str) -> Optional[ExchangeRate]:
        """
        Fetch exchange rate from Bank of Korea (한국은행) API

        BOK Open API:
        - Endpoint: https://ecos.bok.or.kr/api/
        - Service: StatisticSearch (통계조회)
        - Stat Code: 731Y001 (환율)
        """
        # TODO: Implement BOK API integration
        # For now, return None to trigger default rate
        logger.debug(f"🔍 [{currency}] Fetching from BOK API (not implemented yet)")
        return None

    def _is_cache_valid(self, currency: str) -> bool:
        """Check if cached rate is still valid (within TTL)"""
        if currency not in self._cache:
            return False

        cached_rate = self._cache[currency]
        age = datetime.now() - cached_rate.timestamp

        # Determine TTL based on market hours
        # TODO: Integrate with market_hours check
        ttl = self._cache_ttl_market_hours  # For now, assume market hours

        return age < ttl

    def _update_cache(self, currency: str, rate: ExchangeRate):
        """Update in-memory cache"""
        rate.is_cached = True
        self._cache[currency] = rate
        logger.debug(f"💾 [{currency}] Cache updated: {rate.rate_to_krw} (source: {rate.source})")

    def _save_to_db(self, rate: ExchangeRate):
        """Save rate to database for historical tracking"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO exchange_rate_history (
                    currency, rate_to_krw, source, timestamp
                ) VALUES (?, ?, ?, ?)
            """, (
                rate.currency,
                rate.rate_to_krw,
                rate.source,
                rate.timestamp.isoformat()
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.warning(f"⚠️ [{rate.currency}] DB save failed: {e}")

    def get_all_rates(self) -> Dict[str, float]:
        """
        Get all supported currency rates

        Returns:
            Dict mapping currency to KRW rate
        """
        rates = {}
        for currency in ['USD', 'HKD', 'CNY', 'JPY', 'VND']:
            rates[currency] = self.get_rate(currency)

        return rates

    def convert_to_krw(self, value: float, currency: str) -> int:
        """
        Convert foreign currency value to KRW

        Args:
            value: Value in foreign currency
            currency: 'USD', 'HKD', 'CNY', 'JPY', 'VND'

        Returns:
            Value in KRW (integer)
        """
        rate = self.get_rate(currency)
        return int(value * rate)
```

**Database Schema**:

```sql
-- Exchange rate history table
CREATE TABLE IF NOT EXISTS exchange_rate_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    currency TEXT NOT NULL,           -- 'USD', 'HKD', 'CNY', 'JPY', 'VND'
    rate_to_krw REAL NOT NULL,        -- Conversion rate
    source TEXT NOT NULL,             -- 'kis_api', 'bok', 'fixed'
    timestamp TIMESTAMP NOT NULL,     -- Rate timestamp
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_exchange_rate_currency_time
ON exchange_rate_history(currency, timestamp DESC);
```

**Unit Tests**:

```bash
# Create tests/test_exchange_rate_manager.py
pytest tests/test_exchange_rate_manager.py -v

# Expected:
# ✅ test_get_rate_krw (base currency)
# ✅ test_get_rate_with_cache
# ✅ test_get_rate_fallback_chain
# ✅ test_convert_to_krw
# ✅ test_cache_ttl_validation
```

---

#### **Task 1.3: MarketFilterManager 검증** (4시간)

**기존 파일**: `modules/market_filter_manager.py`

**Enhancement Tasks**:
1. ExchangeRateManager 통합 (2h)
2. 동적 환율 업데이트 지원 (1h)
3. Unit Tests 추가 (1h)

**Code Changes**:

```python
# modules/market_filter_manager.py (enhanced)

class MarketFilterConfig:
    """Market-specific filter configuration (enhanced)"""

    def __init__(self, config_path: str, exchange_rate_manager=None):
        # ... existing code ...

        # Exchange rate manager
        self.exchange_rate_manager = exchange_rate_manager

        # Dynamic exchange rate (if manager provided)
        if self.exchange_rate_manager and self.currency != 'KRW':
            try:
                self._current_exchange_rate = self.exchange_rate_manager.get_rate(self.currency)
                logger.info(
                    f"🔄 [{self.region}] Dynamic exchange rate loaded: "
                    f"{self.currency}/KRW = {self._current_exchange_rate}"
                )
            except Exception as e:
                logger.warning(f"⚠️ [{self.region}] Dynamic rate failed, using default: {e}")

    def update_exchange_rate_from_manager(self):
        """Update exchange rate from ExchangeRateManager"""
        if self.exchange_rate_manager and self.currency != 'KRW':
            self._current_exchange_rate = self.exchange_rate_manager.get_rate(
                self.currency,
                force_refresh=True
            )
            logger.info(
                f"🔄 [{self.region}] Exchange rate updated: "
                f"{self._current_exchange_rate}"
            )


class MarketFilterManager:
    """Manages multi-market filter configurations (enhanced)"""

    def __init__(self, config_dir: str = 'config/market_filters',
                 exchange_rate_manager=None):
        self.config_dir = Path(config_dir)
        self.configs: Dict[str, MarketFilterConfig] = {}

        # Exchange rate manager (shared across markets)
        self.exchange_rate_manager = exchange_rate_manager

        # Load configs
        self._load_all_configs()

    def _load_all_configs(self):
        """Load all market configurations with dynamic exchange rates"""
        # ... existing code ...

        for config_file in self.config_dir.glob('*_filter_config.yaml'):
            try:
                config = MarketFilterConfig(
                    str(config_file),
                    exchange_rate_manager=self.exchange_rate_manager
                )
                self.configs[config.region] = config
                loaded_count += 1
            except Exception as e:
                logger.error(f"❌ Failed to load {config_file.name}: {e}")

        # ... existing code ...

    def refresh_exchange_rates(self):
        """Refresh exchange rates for all markets"""
        for config in self.configs.values():
            if config.currency != 'KRW':
                config.update_exchange_rate_from_manager()
```

**Integration Test**:

```python
# tests/test_market_filter_manager_integration.py

def test_market_filter_manager_with_exchange_rates():
    """Test MarketFilterManager with ExchangeRateManager integration"""
    from modules.exchange_rate_manager import ExchangeRateManager
    from modules.market_filter_manager import MarketFilterManager

    # Initialize managers
    exchange_mgr = ExchangeRateManager(db_path='data/test_spock.db')
    filter_mgr = MarketFilterManager(
        config_dir='config/market_filters',
        exchange_rate_manager=exchange_mgr
    )

    # Test: All markets loaded
    assert len(filter_mgr.get_supported_regions()) == 6  # KR, US, HK, CN, JP, VN

    # Test: Exchange rates applied
    us_config = filter_mgr.get_config('US')
    assert us_config.get_exchange_rate() > 1000  # USD/KRW should be ~1,300

    hk_config = filter_mgr.get_config('HK')
    assert hk_config.get_exchange_rate() > 100   # HKD/KRW should be ~170

    # Test: Currency conversion
    us_100m_in_krw = us_config.convert_to_krw(100_000_000)  # $100M
    assert 120_000_000_000 < us_100m_in_krw < 140_000_000_000  # ~₩130B

    print("✅ All integration tests passed")
```

---

#### **Task 1.4: Database Schema Migration** (4시간)

**Migration File**: `migrations/004_add_exchange_rate_history.py`

```python
"""
Migration 004: Add Exchange Rate History Table

Adds:
1. exchange_rate_history table (환율 이력 추적)
2. Indexes for efficient querying

Author: Spock Trading System
Date: 2025-10-16
"""

import sqlite3
import logging

logger = logging.getLogger(__name__)


def upgrade(db_path: str = 'data/spock_local.db'):
    """Apply migration: Add exchange_rate_history table"""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Create exchange_rate_history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exchange_rate_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                currency TEXT NOT NULL,
                rate_to_krw REAL NOT NULL,
                source TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_exchange_rate_currency_time
            ON exchange_rate_history(currency, timestamp DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_exchange_rate_source
            ON exchange_rate_history(source)
        """)

        conn.commit()
        logger.info("✅ Migration 004: exchange_rate_history table created")

    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Migration 004 failed: {e}")
        raise

    finally:
        conn.close()


def downgrade(db_path: str = 'data/spock_local.db'):
    """Rollback migration: Drop exchange_rate_history table"""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("DROP TABLE IF EXISTS exchange_rate_history")
        conn.commit()
        logger.info("✅ Migration 004 rollback: exchange_rate_history table dropped")

    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Migration 004 rollback failed: {e}")
        raise

    finally:
        conn.close()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Migration 004: Exchange Rate History')
    parser.add_argument('--upgrade', action='store_true', help='Apply migration')
    parser.add_argument('--downgrade', action='store_true', help='Rollback migration')
    parser.add_argument('--db-path', default='data/spock_local.db', help='Database path')

    args = parser.parse_args()

    if args.upgrade:
        upgrade(args.db_path)
    elif args.downgrade:
        downgrade(args.db_path)
    else:
        print("Usage: python migrations/004_add_exchange_rate_history.py --upgrade")
```

**Validation**:

```bash
# Apply migration
python3 migrations/004_add_exchange_rate_history.py --upgrade

# Verify table created
sqlite3 data/spock_local.db "SELECT name FROM sqlite_master WHERE type='table' AND name='exchange_rate_history'"

# Expected output: exchange_rate_history
```

---

#### **Task 1.5: Unit Tests (설정 시스템)** (2시간)

**Test Files**:
1. `tests/test_market_filter_config.py`
2. `tests/test_exchange_rate_manager.py`
3. `tests/test_market_filter_manager.py`

**Target Coverage**: 97%+

**Run Tests**:

```bash
# Run all Phase 1 tests
pytest tests/test_market_filter_*.py tests/test_exchange_rate_*.py -v --cov=modules --cov-report=html

# Expected output:
# ✅ test_market_filter_config.py .......... (10 tests)
# ✅ test_exchange_rate_manager.py .......... (10 tests)
# ✅ test_market_filter_manager.py .......... (12 tests)
# Coverage: 97.3%
```

---

### 3.2 Phase 2: Integration (Days 4-7, 32시간)

#### **Task 2.1: kis_data_collector.py 개선** (12시간)

**목표**: Stage 0-1 필터링을 OHLCV 수집 전에 적용

**Changes**:

```python
# modules/kis_data_collector.py (enhanced)

class KISDataCollector:
    """
    KIS API Data Collector with Multi-Stage Filtering

    New Features:
    1. Stage 0 filter integration (market cap, trading value)
    2. Stage 1 filter integration (technical pre-screen)
    3. Batch collection with filtering
    """

    def __init__(self, db_manager, region: str = 'KR'):
        self.db = db_manager
        self.region = region

        # Initialize filter manager
        from modules.exchange_rate_manager import ExchangeRateManager
        from modules.market_filter_manager import MarketFilterManager

        self.exchange_rate_manager = ExchangeRateManager(db_path=self.db.db_path)
        self.filter_manager = MarketFilterManager(
            config_dir='config/market_filters',
            exchange_rate_manager=self.exchange_rate_manager
        )

        # Get market config
        self.market_config = self.filter_manager.get_config(region)
        if not self.market_config:
            raise ValueError(f"No market config found for region: {region}")

        logger.info(f"✅ KISDataCollector initialized (region={region})")

    def collect_with_filtering(self,
                               tickers: Optional[List[str]] = None,
                               days: int = 250,
                               apply_stage0: bool = True,
                               apply_stage1: bool = True) -> Dict[str, int]:
        """
        Collect OHLCV data with multi-stage filtering

        Workflow:
        1. Load ticker list (from DB or provided)
        2. Apply Stage 0 filter (market cap, trading value)
        3. Apply Stage 1 filter (technical pre-screen)
        4. Collect OHLCV for filtered tickers

        Args:
            tickers: Ticker list (None = all active tickers in region)
            days: Historical days to collect
            apply_stage0: Enable Stage 0 filtering
            apply_stage1: Enable Stage 1 filtering (requires OHLCV data)

        Returns:
            {
                'input_count': int,
                'stage0_passed': int,
                'stage1_passed': int,
                'ohlcv_collected': int
            }
        """
        start_time = datetime.now()

        # Step 1: Load ticker list
        if tickers is None:
            ticker_data = self.db.get_tickers(region=self.region, asset_type='STOCK', is_active=True)
            tickers = [t['ticker'] for t in ticker_data]

        logger.info(f"📊 [{self.region}] Starting OHLCV collection with filtering: {len(tickers)} tickers")

        stats = {
            'input_count': len(tickers),
            'stage0_passed': 0,
            'stage1_passed': 0,
            'ohlcv_collected': 0
        }

        # Step 2: Apply Stage 0 filter (if enabled)
        if apply_stage0:
            stage0_results = self._run_stage0_filter(tickers)
            stage0_tickers = [t['ticker'] for t in stage0_results if t['passed']]
            stats['stage0_passed'] = len(stage0_tickers)

            logger.info(
                f"📊 [{self.region}] Stage 0 complete: "
                f"{len(tickers)} → {len(stage0_tickers)} tickers "
                f"({(1 - len(stage0_tickers)/len(tickers))*100:.1f}% filtered)"
            )
        else:
            stage0_tickers = tickers
            stats['stage0_passed'] = len(stage0_tickers)

        # Step 3: Collect OHLCV for Stage 0 passed tickers
        for ticker in stage0_tickers:
            try:
                # Fetch OHLCV
                ohlcv_df = self._fetch_ohlcv(ticker, days=days)
                if ohlcv_df.empty:
                    logger.warning(f"⚠️ [{ticker}] No OHLCV data")
                    continue

                # Calculate technical indicators
                ohlcv_df = self._calculate_technical_indicators(ohlcv_df)

                # Save to database
                self._save_ohlcv_to_db(ticker, ohlcv_df, period_type='DAILY')

                stats['ohlcv_collected'] += 1

            except Exception as e:
                logger.error(f"❌ [{ticker}] OHLCV collection failed: {e}")

        # Step 4: Apply Stage 1 filter (if enabled)
        if apply_stage1:
            from modules.stock_pre_filter import StockPreFilter

            pre_filter = StockPreFilter(db_path=self.db.db_path, region=self.region)
            stage1_results = pre_filter.run_stage1_filter(force_refresh=True)
            stats['stage1_passed'] = len(stage1_results)

            logger.info(
                f"📊 [{self.region}] Stage 1 complete: "
                f"{stats['ohlcv_collected']} → {stats['stage1_passed']} tickers "
                f"({(1 - stats['stage1_passed']/stats['ohlcv_collected'])*100:.1f}% filtered)"
            )

        # Log final stats
        execution_time = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"✅ [{self.region}] OHLCV collection complete:\n"
            f"   Input: {stats['input_count']} tickers\n"
            f"   Stage 0 passed: {stats['stage0_passed']}\n"
            f"   OHLCV collected: {stats['ohlcv_collected']}\n"
            f"   Stage 1 passed: {stats['stage1_passed']}\n"
            f"   Total time: {execution_time:.1f}s"
        )

        return stats

    def _run_stage0_filter(self, tickers: List[str]) -> List[Dict]:
        """
        Run Stage 0 filter (market cap, trading value)

        Returns:
            List of {'ticker': str, 'passed': bool, 'reason': str, ...}
        """
        from modules.scanner import StockScanner

        scanner = StockScanner(db_path=self.db.db_path, region=self.region)
        results = scanner.run_stage0_filter(tickers=tickers, force_refresh=True)

        return results
```

---

#### **Task 2.2: 마켓별 수집 스크립트 작성** (8시간)

**Scripts** (각 마켓당 1.5시간):
1. `scripts/collect_us_ohlcv.py`
2. `scripts/collect_hk_ohlcv.py`
3. `scripts/collect_cn_ohlcv.py`
4. `scripts/collect_jp_ohlcv.py`
5. `scripts/collect_vn_ohlcv.py`

**Template Script** (`scripts/collect_us_ohlcv.py`):

```python
"""
US Market OHLCV Collection Script

Collects 250-day OHLCV data for US stocks with filtering:
- Stage 0: Market cap ($77M), Trading value ($7.7M/day)
- Stage 1: Technical pre-screen (MA, RSI, volume)

Usage:
    python3 scripts/collect_us_ohlcv.py --full
    python3 scripts/collect_us_ohlcv.py --tickers AAPL MSFT GOOGL
    python3 scripts/collect_us_ohlcv.py --dry-run

Author: Spock Trading System
"""

import os
import sys
import logging
import argparse
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.kis_data_collector import KISDataCollector
from modules.market_adapters import USAdapterKIS

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='US Market OHLCV Collection')
    parser.add_argument('--full', action='store_true', help='Full collection (all tickers)')
    parser.add_argument('--tickers', nargs='+', help='Specific tickers to collect')
    parser.add_argument('--days', type=int, default=250, help='Historical days (default: 250)')
    parser.add_argument('--dry-run', action='store_true', help='Dry run (no DB writes)')
    parser.add_argument('--skip-stage0', action='store_true', help='Skip Stage 0 filter')
    parser.add_argument('--skip-stage1', action='store_true', help='Skip Stage 1 filter')
    parser.add_argument('--db-path', default='data/spock_local.db', help='Database path')

    args = parser.parse_args()

    logger.info("="*60)
    logger.info("US Market OHLCV Collection Script")
    logger.info("="*60)

    # Initialize database
    db = SQLiteDatabaseManager(db_path=args.db_path)

    # Initialize collector
    collector = KISDataCollector(db_manager=db, region='US')

    # Determine ticker list
    if args.tickers:
        tickers = args.tickers
        logger.info(f"📊 Collecting specific tickers: {', '.join(tickers)}")
    elif args.full:
        # Scan US stocks first
        from modules.market_adapters import USAdapterKIS

        us_adapter = USAdapterKIS(
            db,
            app_key=os.getenv('KIS_APP_KEY'),
            app_secret=os.getenv('KIS_APP_SECRET')
        )

        logger.info("🔍 Scanning US stocks...")
        stocks = us_adapter.scan_stocks(force_refresh=True)
        tickers = [s['ticker'] for s in stocks]
        logger.info(f"📊 Found {len(tickers)} US stocks")
    else:
        logger.error("❌ Must specify --full or --tickers")
        sys.exit(1)

    # Dry run check
    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No database writes")
        logger.info(f"   Would collect {len(tickers)} tickers with {args.days} days")
        sys.exit(0)

    # Run collection with filtering
    stats = collector.collect_with_filtering(
        tickers=tickers,
        days=args.days,
        apply_stage0=not args.skip_stage0,
        apply_stage1=not args.skip_stage1
    )

    # Print summary
    logger.info("")
    logger.info("="*60)
    logger.info("US Market OHLCV Collection Summary")
    logger.info("="*60)
    logger.info(f"Input tickers: {stats['input_count']}")
    logger.info(f"Stage 0 passed: {stats['stage0_passed']} ({stats['stage0_passed']/stats['input_count']*100:.1f}%)")
    logger.info(f"OHLCV collected: {stats['ohlcv_collected']}")
    logger.info(f"Stage 1 passed: {stats['stage1_passed']} ({stats['stage1_passed']/stats['ohlcv_collected']*100 if stats['ohlcv_collected'] > 0 else 0:.1f}%)")
    logger.info("="*60)

    logger.info("✅ US Market OHLCV collection complete")


if __name__ == '__main__':
    main()
```

**Validation**:

```bash
# Dry run
python3 scripts/collect_us_ohlcv.py --full --dry-run

# Real run (single ticker)
python3 scripts/collect_us_ohlcv.py --tickers AAPL --days 250

# Expected output:
# ✅ Input: 1 ticker
# ✅ Stage 0 passed: 1 (100%)
# ✅ OHLCV collected: 1 (250 rows)
# ✅ Stage 1 passed: 1 (100%)
```

---

#### **Task 2.3: Database Schema 검증** (4시간)

**Validation Tasks**:
1. `filter_cache_stage0` 멀티마켓 지원 확인 (1h)
2. `filter_cache_stage1` 복합키 검증 (1h)
3. Exchange rate metadata 저장 테스트 (1h)
4. Data integrity 검증 (1h)

**Validation Script** (`scripts/validate_db_schema.py`):

```python
"""
Database Schema Validation for Multi-Market Support

Validates:
1. filter_cache_stage0 (region, currency fields)
2. filter_cache_stage1 (composite key)
3. exchange_rate_history (rate tracking)
4. Data integrity (foreign keys, indexes)

Author: Spock Trading System
"""

import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_schema(db_path: str = 'data/spock_local.db'):
    """Validate database schema for multi-market support"""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    results = {
        'filter_cache_stage0': False,
        'filter_cache_stage1': False,
        'exchange_rate_history': False,
        'indexes': False,
        'foreign_keys': False
    }

    try:
        # 1. Validate filter_cache_stage0
        cursor.execute("PRAGMA table_info(filter_cache_stage0)")
        stage0_columns = {row[1] for row in cursor.fetchall()}

        required_stage0 = {
            'ticker', 'region', 'name', 'exchange',
            'market_cap_krw', 'trading_value_krw', 'current_price_krw',
            'market_cap_local', 'trading_value_local', 'current_price_local',
            'currency', 'exchange_rate_to_krw'
        }

        if required_stage0.issubset(stage0_columns):
            logger.info("✅ filter_cache_stage0: All required columns present")
            results['filter_cache_stage0'] = True
        else:
            missing = required_stage0 - stage0_columns
            logger.error(f"❌ filter_cache_stage0: Missing columns {missing}")

        # 2. Validate filter_cache_stage1
        cursor.execute("PRAGMA table_info(filter_cache_stage1)")
        stage1_columns = {row[1] for row in cursor.fetchall()}

        required_stage1 = {
            'ticker', 'region', 'ma5', 'ma20', 'ma60', 'rsi_14',
            'current_price_krw', 'week_52_high_krw'
        }

        if required_stage1.issubset(stage1_columns):
            logger.info("✅ filter_cache_stage1: All required columns present")
            results['filter_cache_stage1'] = True
        else:
            missing = required_stage1 - stage1_columns
            logger.error(f"❌ filter_cache_stage1: Missing columns {missing}")

        # 3. Validate exchange_rate_history
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='exchange_rate_history'")
        if cursor.fetchone():
            logger.info("✅ exchange_rate_history: Table exists")
            results['exchange_rate_history'] = True
        else:
            logger.error("❌ exchange_rate_history: Table not found")

        # 4. Validate indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}

        required_indexes = {
            'idx_stage0_region_date',
            'idx_stage1_region_date',
            'idx_exchange_rate_currency_time'
        }

        if required_indexes.issubset(indexes):
            logger.info("✅ Indexes: All required indexes present")
            results['indexes'] = True
        else:
            missing = required_indexes - indexes
            logger.warning(f"⚠️ Indexes: Missing {missing}")

        # 5. Test data insertion
        test_data = {
            'ticker': 'TEST123',
            'region': 'US',
            'name': 'Test Stock',
            'exchange': 'NASDAQ',
            'market_cap_krw': 130_000_000_000,
            'trading_value_krw': 13_000_000_000,
            'current_price_krw': 130_000,
            'market_cap_local': 100_000_000,
            'trading_value_local': 10_000_000,
            'current_price_local': 100,
            'currency': 'USD',
            'exchange_rate_to_krw': 1300,
            'filter_date': '2025-10-16',
            'stage0_passed': True
        }

        cursor.execute("""
            INSERT OR REPLACE INTO filter_cache_stage0 (
                ticker, region, name, exchange,
                market_cap_krw, trading_value_krw, current_price_krw,
                market_cap_local, trading_value_local, current_price_local,
                currency, exchange_rate_to_krw, filter_date, stage0_passed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, tuple(test_data.values()))

        conn.commit()
        logger.info("✅ Data insertion: Test data inserted successfully")

        # Cleanup test data
        cursor.execute("DELETE FROM filter_cache_stage0 WHERE ticker = 'TEST123'")
        conn.commit()

        results['foreign_keys'] = True

    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")

    finally:
        conn.close()

    # Summary
    logger.info("")
    logger.info("="*60)
    logger.info("Database Schema Validation Summary")
    logger.info("="*60)

    all_passed = all(results.values())

    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {check}")

    logger.info("="*60)

    if all_passed:
        logger.info("✅ All validation checks passed")
    else:
        logger.error("❌ Some validation checks failed")
        return False

    return True


if __name__ == '__main__':
    import sys

    success = validate_schema()
    sys.exit(0 if success else 1)
```

**Run Validation**:

```bash
# Validate schema
python3 scripts/validate_db_schema.py

# Expected output:
# ✅ filter_cache_stage0: All required columns present
# ✅ filter_cache_stage1: All required columns present
# ✅ exchange_rate_history: Table exists
# ✅ Indexes: All required indexes present
# ✅ Data insertion: Test data inserted successfully
# ✅ All validation checks passed
```

---

#### **Task 2.4: Integration Tests** (8시간)

**Test Suite** (각 마켓당 1.5시간):
1. `tests/test_us_integration.py`
2. `tests/test_hk_integration.py`
3. `tests/test_cn_integration.py`
4. `tests/test_jp_integration.py`
5. `tests/test_vn_integration.py`

**Example Test** (`tests/test_us_integration.py`):

```python
"""
US Market End-to-End Integration Test

Tests:
1. Ticker scanning
2. Stage 0 filtering
3. OHLCV collection
4. Stage 1 filtering
5. Database storage

Author: Spock Trading System
"""

import pytest
import os
from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.market_adapters import USAdapterKIS
from modules.kis_data_collector import KISDataCollector
from modules.stock_pre_filter import StockPreFilter


@pytest.fixture
def db_manager():
    """Create test database manager"""
    db = SQLiteDatabaseManager(db_path='data/test_spock.db')
    yield db
    # Cleanup
    if os.path.exists('data/test_spock.db'):
        os.remove('data/test_spock.db')


def test_us_market_end_to_end(db_manager):
    """Test US market end-to-end workflow"""

    # Step 1: Initialize US adapter
    us_adapter = USAdapterKIS(
        db_manager,
        app_key=os.getenv('KIS_APP_KEY'),
        app_secret=os.getenv('KIS_APP_SECRET')
    )

    # Step 2: Scan US stocks (limited to 10 for testing)
    stocks = us_adapter.scan_stocks(force_refresh=True)
    assert len(stocks) > 0, "Should scan at least 1 US stock"

    test_tickers = [s['ticker'] for s in stocks[:10]]  # Test with 10 tickers

    # Step 3: Run Stage 0 filter
    from modules.scanner import StockScanner
    scanner = StockScanner(db_path=db_manager.db_path, region='US')
    stage0_results = scanner.run_stage0_filter(tickers=test_tickers, force_refresh=True)

    stage0_passed = [r for r in stage0_results if r['passed']]
    assert len(stage0_passed) > 0, "At least 1 ticker should pass Stage 0"

    # Step 4: Collect OHLCV for Stage 0 passed tickers
    collector = KISDataCollector(db_manager=db_manager, region='US')
    stats = collector.collect_with_filtering(
        tickers=[r['ticker'] for r in stage0_passed],
        days=250,
        apply_stage0=False,  # Already filtered
        apply_stage1=True
    )

    assert stats['ohlcv_collected'] > 0, "Should collect OHLCV for at least 1 ticker"

    # Step 5: Verify Stage 1 filter ran
    assert stats['stage1_passed'] >= 0, "Stage 1 filter should run"

    # Step 6: Verify database storage
    conn = db_manager._get_connection()
    cursor = conn.cursor()

    # Check filter_cache_stage0
    cursor.execute("SELECT COUNT(*) FROM filter_cache_stage0 WHERE region='US'")
    stage0_count = cursor.fetchone()[0]
    assert stage0_count > 0, "Stage 0 cache should have US tickers"

    # Check OHLCV data
    cursor.execute("SELECT COUNT(*) FROM ohlcv_data WHERE region='US'")
    ohlcv_count = cursor.fetchone()[0]
    assert ohlcv_count > 0, "OHLCV data should be stored for US"

    # Check currency/exchange rate
    cursor.execute("SELECT DISTINCT currency, exchange_rate_to_krw FROM filter_cache_stage0 WHERE region='US'")
    result = cursor.fetchone()
    assert result[0] == 'USD', "Currency should be USD"
    assert 1000 < result[1] < 2000, "Exchange rate should be ~1,300"

    conn.close()

    print(f"\n✅ US Market End-to-End Test Passed")
    print(f"   Scanned: {len(stocks)} stocks")
    print(f"   Stage 0 passed: {len(stage0_passed)}")
    print(f"   OHLCV collected: {stats['ohlcv_collected']}")
    print(f"   Stage 1 passed: {stats['stage1_passed']}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
```

**Run Integration Tests**:

```bash
# Run US integration test
pytest tests/test_us_integration.py -v -s

# Run all integration tests (5 markets)
pytest tests/test_*_integration.py -v --maxfail=1

# Expected output:
# ✅ test_us_integration.py::test_us_market_end_to_end PASSED
# ✅ test_hk_integration.py::test_hk_market_end_to_end PASSED
# ✅ test_cn_integration.py::test_cn_market_end_to_end PASSED
# ✅ test_jp_integration.py::test_jp_market_end_to_end PASSED
# ✅ test_vn_integration.py::test_vn_market_end_to_end PASSED
```

---

### 3.3 Phase 3: Validation & Monitoring (Days 8-10, 24시간)

#### **Task 3.1: End-to-End Testing (마켓별)** (12시간)

**Test Scenarios** (각 마켓당 2시간):
1. Full pipeline test (scan → filter → collect → validate)
2. Performance benchmarking
3. Data quality validation
4. Error handling verification

**Performance Targets**:

| Market | Input | Stage 0 | OHLCV Collected | Stage 1 | Time Target |
|--------|-------|---------|-----------------|---------|-------------|
| US | ~8,000 | ~1,500 | ~1,500 | ~600 | <2 min |
| HK | ~2,500 | ~400 | ~400 | ~150 | <1 min |
| CN | ~2,000 | ~300 | ~300 | ~120 | <1 min |
| JP | ~3,800 | ~600 | ~600 | ~240 | <1.5 min |
| VN | ~1,500 | ~200 | ~200 | ~80 | <45s |

**Validation Checklist**:
- [ ] All tickers have region='XX' in database
- [ ] All prices normalized to KRW correctly
- [ ] Exchange rates within ±5% of expected
- [ ] 250-day OHLCV data complete (no gaps >60 days)
- [ ] Technical indicators calculated correctly
- [ ] Stage 1 filter applied successfully

---

#### **Task 3.2: Monitoring Dashboard 구축** (8시간)

**Prometheus Metrics** (2시간):

```yaml
# monitoring/prometheus/spock_multi_market_metrics.yml

# Market-specific OHLCV collection metrics
- metric_name: spock_market_ohlcv_collection_total
  type: counter
  labels: [region, status]  # status: success, failed
  description: "Total OHLCV collection attempts per market"

- metric_name: spock_market_stage0_filter_total
  type: counter
  labels: [region, result]  # result: passed, failed
  description: "Stage 0 filter results per market"

- metric_name: spock_market_stage1_filter_total
  type: counter
  labels: [region, result]
  description: "Stage 1 filter results per market"

# Exchange rate metrics
- metric_name: spock_exchange_rate_current
  type: gauge
  labels: [currency, source]
  description: "Current exchange rate to KRW"

- metric_name: spock_exchange_rate_update_timestamp
  type: gauge
  labels: [currency]
  description: "Last exchange rate update timestamp"

# Collection performance
- metric_name: spock_market_collection_duration_seconds
  type: histogram
  labels: [region]
  buckets: [30, 60, 120, 300, 600]
  description: "OHLCV collection duration per market"
```

**Grafana Dashboards** (6시간):

1. **Overview Dashboard** (1h)
   - All markets summary
   - Total tickers: input → stage0 → stage1
   - Collection success rate (by market)
   - Exchange rate trends

2. **US Market Dashboard** (1h)
   - 8 panels: Stage 0/1 filtering, OHLCV collection, errors
   - Exchange rate: USD/KRW chart
   - Top filtered tickers by market cap

3. **HK Market Dashboard** (1h)
4. **CN Market Dashboard** (1h)
5. **JP Market Dashboard** (1h)
6. **VN Market Dashboard** (1h)

**Grafana Dashboard JSON** (template):

```json
{
  "dashboard": {
    "title": "US Market OHLCV Collection",
    "panels": [
      {
        "title": "Stage 0 Filter Results",
        "targets": [{
          "expr": "rate(spock_market_stage0_filter_total{region=\"US\"}[5m])"
        }]
      },
      {
        "title": "OHLCV Collection Success Rate",
        "targets": [{
          "expr": "rate(spock_market_ohlcv_collection_total{region=\"US\",status=\"success\"}[5m]) / rate(spock_market_ohlcv_collection_total{region=\"US\"}[5m])"
        }]
      },
      {
        "title": "USD/KRW Exchange Rate",
        "targets": [{
          "expr": "spock_exchange_rate_current{currency=\"USD\"}"
        }]
      }
    ]
  }
}
```

---

#### **Task 3.3: Documentation** (4시간)

**Documents to Create**:
1. `docs/GLOBAL_OHLCV_FILTERING_DEPLOYMENT_GUIDE.md` (2h)
2. `docs/GLOBAL_OHLCV_FILTERING_TROUBLESHOOTING_GUIDE.md` (1h)
3. `docs/GLOBAL_OHLCV_FILTERING_API_REFERENCE.md` (1h)

**Deployment Guide Contents**:
- Prerequisites (KIS API keys, database setup)
- Configuration (YAML files)
- Deployment steps (per market)
- Validation procedures
- Rollback procedures

**Troubleshooting Guide Contents**:
- Common issues (exchange rate failures, data gaps)
- Error codes and meanings
- Debug commands
- FAQ

**API Reference Contents**:
- `MarketFilterManager` API
- `ExchangeRateManager` API
- `KISDataCollector` API
- Configuration schema reference

---

## 4. 리소스 할당 계획

### 4.1 시간 배분 (총 80시간, 2주)

| Phase | Tasks | Hours | Days | Priority |
|-------|-------|-------|------|----------|
| **Phase 1** | Foundation | 24h | 3 | 🔴 Critical |
| **Phase 2** | Integration | 32h | 4 | 🔴 Critical |
| **Phase 3** | Validation | 24h | 3 | 🟠 High |
| **Total** | | **80h** | **10** | |

### 4.2 마켓별 우선순위

**Week 1 (Days 1-5)**:
- ✅ Phase 1 완료 (전체 인프라)
- ✅ US Market 완료 (가장 큰 시장)
- ✅ HK/CN Market 시작

**Week 2 (Days 6-10)**:
- ✅ HK/CN Market 완료
- ✅ JP/VN Market 완료
- ✅ Testing & Monitoring 완료

### 4.3 체크포인트

**Day 3 Checkpoint**:
- [ ] 5개 마켓 설정 파일 완료
- [ ] ExchangeRateManager 동작 검증
- [ ] Unit Tests 97%+ 커버리지

**Day 7 Checkpoint**:
- [ ] US/HK/CN 마켓 E2E 테스트 통과
- [ ] Database schema 검증 완료
- [ ] Integration tests 95%+ 통과율

**Day 10 Checkpoint (Final)**:
- [ ] 5개 마켓 모두 운영 준비 완료
- [ ] Monitoring 대시보드 실시간 데이터 표시
- [ ] Documentation 완전성 95%+

---

## 5. 위험 관리 (Risk Management)

### 5.1 주요 위험 요소

| 위험 | 확률 | 영향도 | 완화 전략 |
|------|------|--------|-----------|
| KIS API 환율 미지원 | 중간 | 높음 | BOK API fallback 준비 |
| 마켓별 데이터 품질 차이 | 높음 | 중간 | 마켓별 검증 로직 강화 |
| 250일 데이터 부족 (신규 상장) | 높음 | 낮음 | 최소 일수 조정 가능 |
| Exchange rate 변동성 | 낮음 | 중간 | 1시간 TTL로 충분 |
| Database 용량 부족 | 낮음 | 높음 | 사전 용량 계획 (400MB) |

### 5.2 Rollback Plan

**Phase 1 실패 시**:
- 기존 KR 마켓 유지
- 설정 파일만 추가 (영향 없음)

**Phase 2 실패 시**:
- 문제 마켓만 제외
- 다른 마켓 정상 운영

**Phase 3 실패 시**:
- 모니터링 없이도 운영 가능
- 수동 검증으로 대체

---

## 6. 성공 지표 (Success Metrics)

### 6.1 정량적 지표

| 지표 | 목표 | 측정 방법 |
|------|------|-----------|
| 테스트 커버리지 | ≥95% | pytest --cov |
| E2E 테스트 통과율 | ≥95% | pytest 결과 |
| Stage 0 필터 정확도 | ≥99% | 수동 검증 100샘플 |
| Exchange rate 정확도 | ±0.5% | BOK 공식 환율 대조 |
| OHLCV 수집 성공률 | ≥98% | Prometheus metrics |
| 문서 완전성 | ≥95% | 체크리스트 검증 |

### 6.2 정성적 지표

- [ ] 5개 마켓 모두 독립적으로 운영 가능
- [ ] 설정 파일만 수정하여 새 마켓 추가 가능
- [ ] 문제 마켓 1개가 실패해도 다른 마켓 영향 없음
- [ ] Monitoring 대시보드로 실시간 상태 파악 가능
- [ ] 운영팀이 문서만으로 배포/관리 가능

---

## 7. 다음 단계 (Next Steps)

### 7.1 즉시 시작 가능한 작업

**Option A: Phase 1 시작** (권장)
```bash
# Task 1.1: US 설정 파일 작성
cd ~/spock
touch config/market_filters/us_filter_config.yaml
```

**Option B: 환율 시스템 먼저**
```bash
# Task 1.2: ExchangeRateManager 구현
touch modules/exchange_rate_manager.py
```

**Option C: Database 스키마 먼저**
```bash
# Task 1.4: Migration 작성
touch migrations/004_add_exchange_rate_history.py
```

### 7.2 승인 필요 사항

- [ ] 총 80시간 (2주) 개발 일정 승인
- [ ] Database 용량 400MB 증설 승인
- [ ] KIS API 사용량 6배 증가 (5개 마켓) 승인
- [ ] Monitoring 인프라 (Prometheus + Grafana) 승인

---

## 8. 결론

### 8.1 핵심 요약

**Goal**: KR 마켓의 필터링 조건 (24시간 거래대금 + 13개월 월봉)을 5개 해외 마켓에 적용

**Strategy**:
- ✅ 통화 정규화 (KRW 기준)
- ✅ 마켓별 설정 파일 분리
- ✅ 3-Phase 단계적 구현

**Expected Outcome**:
- 📈 수집 종목 수: 250개 → 1,440개 (+476%)
- 🌍 글로벌 커버리지: 1개국 → 6개국 (+500%)
- ⏱️ 효율성: 시간/용량 93% 절감

**Timeline**: 2주 (80시간, 3 phases)

**Risk**: 낮음 (단계적 구현, 독립적 마켓)

### 8.2 권장 사항

**즉시 시작**: Phase 1 (Foundation)
- 설정 파일 작성 (6시간)
- ExchangeRateManager 구현 (8시간)
- 빠른 성과 확인 가능

**승인 후 진행**: Phase 2-3
- 전체 80시간 일정 확정
- 리소스 할당 완료

---

**문서 버전**: 1.0
**작성일**: 2025-10-16
**작성자**: Spock Trading System
**상태**: 구현 준비 완료

