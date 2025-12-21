# Scanner.py Integration Guide - MarketFilterManager

**Purpose**: Integrate MarketFilterManager into scanner.py for Stage 0 filtering
**Estimated Time**: 3-4 hours
**Status**: Implementation Guide

---

## Current State Analysis

### Existing scanner.py Structure (534 lines)
```python
class StockScanner:
    def __init__(self, db_path: str = 'data/spock_local.db'):
        self.db_path = db_path
        self.krx_api_key = os.getenv('KRX_API_KEY')
        self.sources = self._initialize_sources()  # KRX, pykrx, FDR

    def scan_all_tickers(self, force_refresh: bool = False) -> List[Dict]:
        # 1. Check cache (line 270-274)
        # 2. Try each data source sequentially (line 276-297)
        # 3. Apply Spock filters (line 287) ← TARGET FOR REPLACEMENT
        # 4. Save to cache (line 290)

    def _apply_spock_filters(self, tickers: List[Dict]) -> List[Dict]:
        # ❌ OLD: Hardcoded Korean market filters (line 302-335)
        # - MIN_MARKET_CAP = 10B KRW (line 309)
        # - KONEX exclusion (line 319)
        # - ETF/ETN exclusion (line 323-325)
        #
        # ✅ NEW: Use MarketFilterManager
        pass

    def _save_to_cache(self, tickers: List[Dict], source: str):
        # ❌ OLD: Saves to 'tickers' table (line 395-484)
        #
        # ✅ NEW: Save to 'filter_cache_stage0' table
        pass
```

---

## Integration Strategy

### Step 1: Add MarketFilterManager Import

**Location**: Line ~20 (after existing imports)

```python
# === EXISTING IMPORTS ===
import os
import sys
import time
import logging
import sqlite3
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta

# === NEW IMPORT (ADD THIS) ===
from modules.market_filter_manager import MarketFilterManager, FilterResult
```

---

### Step 2: Update StockScanner.__init__()

**Location**: Line ~232-237

**BEFORE**:
```python
class StockScanner:
    def __init__(self, db_path: str = 'data/spock_local.db'):
        self.db_path = db_path
        self.krx_api_key = os.getenv('KRX_API_KEY')  # 환경변수에서 로드

        # 데이터 소스 초기화
        self.sources = self._initialize_sources()
```

**AFTER**:
```python
class StockScanner:
    def __init__(self, db_path: str = 'data/spock_local.db', region: str = 'KR'):
        self.db_path = db_path
        self.region = region.upper()  # 'KR', 'US', etc.
        self.krx_api_key = os.getenv('KRX_API_KEY')

        # NEW: MarketFilterManager 초기화
        self.filter_manager = MarketFilterManager(
            config_dir='config/market_filters'
        )

        # Verify region config exists
        if not self.filter_manager.has_config(self.region):
            raise ValueError(
                f"No configuration found for region: {self.region}. "
                f"Available: {self.filter_manager.get_supported_regions()}"
            )

        # 데이터 소스 초기화
        self.sources = self._initialize_sources()
```

---

### Step 3: Replace _apply_spock_filters() Method

**Location**: Line ~302-335

**BEFORE**:
```python
def _apply_spock_filters(self, tickers: List[Dict]) -> List[Dict]:
    """
    Spock 필터링 기준 적용
    - 시가총액 >= 100억원
    - ETF/ETN 제외
    - KONEX 제외
    """
    MIN_MARKET_CAP = 10_000_000_000  # 100억원

    filtered = []
    for ticker_data in tickers:
        # 시가총액 필터 (있는 경우만)
        market_cap = ticker_data.get('market_cap', 0)
        if market_cap > 0 and market_cap < MIN_MARKET_CAP:
            continue

        # KONEX 제외
        if ticker_data.get('market') == 'KONEX':
            continue

        # ETF/ETN 제외
        name = ticker_data.get('name', '')
        if any(keyword in name for keyword in ['ETF', 'ETN', 'KODEX', 'TIGER', 'KBSTAR', 'ARIRANG']):
            continue

        # 기본 필드 추가
        ticker_data['region'] = 'KR'
        ticker_data['currency'] = 'KRW'
        ticker_data['is_active'] = True

        filtered.append(ticker_data)

    logger.info(f"📊 필터링: {len(tickers)} → {len(filtered)}개 종목 (시가총액 100억 이상)")
    return filtered
```

**AFTER**:
```python
def _apply_stage0_filter(self, tickers: List[Dict]) -> List[Dict]:
    """
    Stage 0: Basic Market Filter (MarketFilterManager 사용)

    Args:
        tickers: Raw ticker list from data source

    Returns:
        Filtered ticker list with normalized data
    """
    logger.info(f"🔍 Stage 0 필터 적용 중... (입력: {len(tickers)}개)")

    filtered = []
    passed_count = 0
    filter_reasons = {}

    for ticker_data in tickers:
        ticker = ticker_data.get('ticker', 'UNKNOWN')

        # Prepare data for filter (must have local currency values)
        filter_input = {
            'ticker': ticker,
            'name': ticker_data.get('name', ''),
            'asset_type': self._classify_asset_type(ticker_data.get('name', '')),
            'market': ticker_data.get('market', 'UNKNOWN'),
            'market_cap_local': ticker_data.get('market_cap', 0),
            'trading_value_local': ticker_data.get('trading_value', 0),
            'price_local': ticker_data.get('close_price', 0),
            'market_warn_code': ticker_data.get('market_warn_code', '00'),
            'is_delisting': ticker_data.get('is_delisting', False)
        }

        # Apply filter using MarketFilterManager
        result: FilterResult = self.filter_manager.apply_stage0_filter(
            region=self.region,
            ticker_data=filter_input
        )

        if result.passed:
            # Merge normalized data back into ticker_data
            ticker_data.update(result.normalized_data)
            ticker_data['region'] = self.region
            ticker_data['stage0_passed'] = True
            filtered.append(ticker_data)
            passed_count += 1
        else:
            # Track filter reasons for reporting
            reason = result.reason
            filter_reasons[reason] = filter_reasons.get(reason, 0) + 1

    # Log filter statistics
    reduction_rate = (len(tickers) - passed_count) / len(tickers) * 100
    logger.info(
        f"✅ Stage 0 필터 완료: {len(tickers)} → {passed_count}개 "
        f"({reduction_rate:.1f}% 감소)"
    )

    # Log top filter reasons
    if filter_reasons:
        top_reasons = sorted(
            filter_reasons.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        logger.info(f"📊 필터링 이유 (상위 5개):")
        for reason, count in top_reasons:
            logger.info(f"   - {reason}: {count}개")

    return filtered
```

---

### Step 4: Update scan_all_tickers() to Use New Filter

**Location**: Line ~287

**BEFORE**:
```python
# 필터링 적용
filtered = self._apply_spock_filters(tickers)
```

**AFTER**:
```python
# Stage 0 필터 적용 (MarketFilterManager)
filtered = self._apply_stage0_filter(tickers)
```

---

### Step 5: Replace _save_to_cache() Method

**Location**: Line ~395-484

**BEFORE**:
```python
def _save_to_cache(self, tickers: List[Dict], source: str):
    """SQLite 캐시에 종목 저장 (tickers + ticker_fundamentals 분리)"""
    try:
        # ... saves to 'tickers' and 'ticker_fundamentals' tables
        pass
```

**AFTER**:
```python
def _save_to_filter_cache(self, tickers: List[Dict], source: str):
    """
    Stage 0 필터 결과를 filter_cache_stage0 테이블에 저장

    Args:
        tickers: Filtered ticker list with normalized data
        source: Data source name
    """
    try:
        # DB 디렉토리 생성
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 기존 filter_cache_stage0 데이터 삭제 (해당 region만)
        cursor.execute(
            "DELETE FROM filter_cache_stage0 WHERE region = ?",
            (self.region,)
        )

        # 새 데이터 삽입
        now = datetime.now().isoformat()
        today = datetime.now().strftime("%Y-%m-%d")
        inserted_count = 0

        for ticker_data in tickers:
            ticker = ticker_data['ticker']

            # filter_cache_stage0 테이블에 삽입
            cursor.execute("""
                INSERT OR REPLACE INTO filter_cache_stage0
                (
                    ticker, region, name, exchange,
                    market_cap_krw, trading_value_krw, current_price_krw,
                    market_cap_local, trading_value_local, current_price_local,
                    currency, exchange_rate_to_krw, exchange_rate_date, exchange_rate_source,
                    market_warn_code, is_delisting,
                    filter_date, stage0_passed, created_at, last_updated
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker,
                self.region,
                ticker_data.get('name'),
                ticker_data.get('market'),
                # KRW normalized values
                ticker_data.get('market_cap_krw'),
                ticker_data.get('trading_value_krw'),
                ticker_data.get('current_price_krw'),
                # Local currency values
                ticker_data.get('market_cap_local'),
                ticker_data.get('trading_value_local'),
                ticker_data.get('current_price_local'),
                # Exchange rate metadata
                ticker_data.get('currency', 'KRW'),
                ticker_data.get('exchange_rate_to_krw', 1.0),
                ticker_data.get('exchange_rate_date', today),
                ticker_data.get('exchange_rate_source', 'fixed'),
                # Market-specific fields
                ticker_data.get('market_warn_code'),
                ticker_data.get('is_delisting', False),
                # Filter metadata
                today,
                True,  # stage0_passed
                now,
                now
            ))

            inserted_count += 1

        conn.commit()
        conn.close()

        logger.info(
            f"💾 filter_cache_stage0 저장 완료: {inserted_count}개 종목 "
            f"(Region: {self.region}, Source: {source})"
        )

    except Exception as e:
        logger.error(f"캐시 저장 실패: {e}")
        raise
```

---

### Step 6: Update _load_from_cache() Method

**Location**: Line ~337-393

**BEFORE**:
```python
def _load_from_cache(self) -> Optional[List[Dict]]:
    """SQLite 캐시에서 종목 로드 (24시간 이내)"""
    # ... loads from 'tickers' table
```

**AFTER**:
```python
def _load_from_filter_cache(self) -> Optional[List[Dict]]:
    """
    filter_cache_stage0 테이블에서 캐시 로드 (TTL 확인)

    Returns:
        Cached ticker list or None if cache expired/empty
    """
    try:
        if not os.path.exists(self.db_path):
            return None

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 최근 업데이트 확인 (region별)
        cursor.execute("""
            SELECT MAX(last_updated) as last_update
            FROM filter_cache_stage0
            WHERE region = ? AND stage0_passed = 1
        """, (self.region,))

        result = cursor.fetchone()

        if not result or not result['last_update']:
            conn.close()
            return None

        last_update = datetime.fromisoformat(result['last_update'])
        age_hours = (datetime.now() - last_update).total_seconds() / 3600

        # TTL check (1 hour during market hours, 24 hours after-hours)
        # Simplified: Use 24-hour TTL for now
        if age_hours > 24:
            logger.info(f"⏰ 캐시 만료 ({age_hours:.1f}시간 경과)")
            conn.close()
            return None

        # Load cached tickers
        cursor.execute("""
            SELECT
                ticker,
                name,
                exchange as market,
                region,
                currency,
                market_cap_krw,
                trading_value_krw,
                current_price_krw,
                market_cap_local,
                trading_value_local,
                current_price_local,
                exchange_rate_to_krw,
                exchange_rate_date,
                exchange_rate_source,
                filter_date
            FROM filter_cache_stage0
            WHERE region = ? AND stage0_passed = 1
            ORDER BY market_cap_krw DESC
        """, (self.region,))

        tickers = [dict(row) for row in cursor.fetchall()]
        conn.close()

        logger.info(
            f"✅ 캐시 히트: {len(tickers)}개 종목 로드 "
            f"({age_hours:.1f}시간 전 데이터, Region: {self.region})"
        )
        return tickers

    except Exception as e:
        logger.warning(f"캐시 로드 실패: {e}")
        return None
```

---

### Step 7: Update scan_all_tickers() Method

**Location**: Line ~259-300

**BEFORE**:
```python
def scan_all_tickers(self, force_refresh: bool = False) -> List[Dict]:
    # Layer 0: Cache 확인 (최우선)
    if not force_refresh:
        cached = self._load_from_cache()
        if cached:
            logger.info(f"✅ [Cache] {len(cached)}개 종목 로드 (캐시 사용)")
            return cached

    # Layer 1-4: 순차적으로 시도
    for source_name, source_api in self.sources:
        try:
            # ... fetch tickers
            # 필터링 적용
            filtered = self._apply_spock_filters(tickers)

            # Cache 저장
            self._save_to_cache(filtered, source=source_name)
            # ...
```

**AFTER**:
```python
def scan_all_tickers(self, force_refresh: bool = False) -> List[Dict]:
    """
    전체 종목 스캔 + Stage 0 필터 적용

    Args:
        force_refresh: 캐시 무시하고 강제 갱신

    Returns:
        Stage 0 필터를 통과한 종목 리스트
    """
    # Layer 0: Cache 확인 (filter_cache_stage0)
    if not force_refresh:
        cached = self._load_from_filter_cache()  # ← CHANGED
        if cached:
            logger.info(f"✅ [Cache] {len(cached)}개 종목 로드 (Region: {self.region})")
            return cached

    # Layer 1-4: 순차적으로 시도
    for source_name, source_api in self.sources:
        try:
            logger.info(f"🔄 [{source_name}] 종목 조회 시도...")
            tickers = source_api.get_stock_list()

            if not tickers:
                logger.warning(f"⚠️ [{source_name}] 데이터 없음, 다음 소스 시도")
                continue

            # Stage 0 필터 적용 (MarketFilterManager)
            filtered = self._apply_stage0_filter(tickers)  # ← CHANGED

            # Cache 저장 (filter_cache_stage0)
            self._save_to_filter_cache(filtered, source=source_name)  # ← CHANGED

            logger.info(f"✅ [{source_name}] {len(filtered)}개 종목 스캔 완료")
            return filtered

        except Exception as e:
            logger.error(f"❌ [{source_name}] 실패: {e}")
            continue

    # 모든 소스 실패
    raise Exception("❌ 모든 데이터 소스 실패. 네트워크 확인 필요.")
```

---

### Step 8: Update CLI Arguments

**Location**: Line ~500-514

**BEFORE**:
```python
parser = argparse.ArgumentParser(description='국내주식 종목 스캐너')
parser.add_argument('--force-refresh', action='store_true', help='캐시 무시하고 강제 갱신')
parser.add_argument('--db-path', default='data/spock_local.db', help='SQLite DB 경로')
parser.add_argument('--debug', action='store_true', help='디버그 모드')
```

**AFTER**:
```python
parser = argparse.ArgumentParser(description='다중 시장 종목 스캐너 (Multi-Market Scanner)')
parser.add_argument('--force-refresh', action='store_true', help='캐시 무시하고 강제 갱신')
parser.add_argument('--db-path', default='data/spock_local.db', help='SQLite DB 경로')
parser.add_argument('--region', default='KR', help='시장 지역 코드 (KR, US, HK, CN, JP, VN)')
parser.add_argument('--debug', action='store_true', help='디버그 모드')
```

**Update scanner initialization** (Line ~514):

**BEFORE**:
```python
scanner = StockScanner(db_path=args.db_path)
```

**AFTER**:
```python
scanner = StockScanner(db_path=args.db_path, region=args.region)
```

---

## Testing Plan

### Unit Tests
```bash
# Test MarketFilterManager integration
python3 -c "
from modules.scanner import StockScanner
scanner = StockScanner(region='KR')
print('✅ Scanner initialized with MarketFilterManager')
print(f'Region: {scanner.region}')
print(f'Filter config loaded: {scanner.filter_manager.has_config(\"KR\")}')
"
```

### Integration Test
```bash
# Test full scan with filtering
python3 modules/scanner.py --force-refresh --region KR --debug

# Expected output:
# 🔄 [KRX Data API] 종목 조회 시도...
# ✅ [KRX Data API] 2,500개 종목 조회
# 🔍 Stage 0 필터 적용 중... (입력: 2,500개)
# ✅ Stage 0 필터 완료: 2,500 → 600개 (76.0% 감소)
# 📊 필터링 이유 (상위 5개):
#    - market_cap_too_low: 1,200개
#    - etf: 300개
#    - price_too_low: 200개
# 💾 filter_cache_stage0 저장 완료: 600개 종목 (Region: KR)
```

---

## Validation Checklist

### Functional Tests
- [ ] MarketFilterManager initializes correctly
- [ ] Korea config (kr_filter_config.yaml) loads successfully
- [ ] Stage 0 filter applies thresholds correctly
- [ ] filter_cache_stage0 table saves data properly
- [ ] Cache TTL works (24-hour expiration)
- [ ] Force refresh bypasses cache
- [ ] Filter reasons logged correctly

### Performance Tests
- [ ] Scan completes in < 10 seconds (Stage 0 only)
- [ ] Database queries use indexes (check EXPLAIN QUERY PLAN)
- [ ] Memory usage stays < 500MB

### Error Handling Tests
- [ ] Handles missing config file gracefully
- [ ] Handles database connection errors
- [ ] Handles malformed ticker data
- [ ] Logs errors appropriately

---

## Migration Path (Safe Rollout)

### Option 1: Feature Flag (Recommended)
```python
# Add flag to enable/disable new filter
USE_MARKET_FILTER_MANAGER = os.getenv('USE_MARKET_FILTER_MANAGER', 'true').lower() == 'true'

if USE_MARKET_FILTER_MANAGER:
    filtered = self._apply_stage0_filter(tickers)  # New
else:
    filtered = self._apply_spock_filters(tickers)  # Old
```

### Option 2: Parallel Validation
```python
# Run both filters and compare results
old_filtered = self._apply_spock_filters(tickers)
new_filtered = self._apply_stage0_filter(tickers)

# Log differences
diff = set(old_filtered) - set(new_filtered)
if diff:
    logger.warning(f"⚠️ Filter mismatch: {len(diff)} tickers differ")
```

---

## Estimated Implementation Time

| Step | Description | Time |
|------|-------------|------|
| 1-2 | Imports + __init__() update | 30 min |
| 3-4 | Replace _apply_spock_filters() | 1 hour |
| 5-6 | Replace cache methods | 1 hour |
| 7-8 | Update scan_all_tickers() + CLI | 30 min |
| Testing | Unit + integration tests | 1 hour |
| **TOTAL** | **Full integration** | **4 hours** |

---

## Next Steps After Integration

1. **Test with Real Data**: Run scanner with actual KOSPI/KOSDAQ data
2. **Validate Filter Results**: Compare old vs new filter counts
3. **Performance Benchmark**: Measure execution time
4. **Proceed to Task 5**: Create stock_pre_filter.py (Stage 1)

---

**End of Integration Guide**
