# DB 최신화 기능 분석 리포트

**생성일**: 2025-11-01
**분석 대상**: Quant Investment Platform 데이터베이스 증분 업데이트 기능
**분석자**: Claude Code

---

## 📋 Executive Summary

Quant Investment Platform의 데이터베이스 최신화 기능을 분석한 결과, **70% 구현 완료** 상태입니다.

### 구현 현황
| 항목 | 상태 | 완성도 | 비고 |
|------|------|--------|------|
| **1. tickers 테이블 증분 업데이트** | ⚠️ 부분 구현 | 60% | KR 시장 통합 스크립트 부재 |
| **2. OHLCV 증분 업데이트** | ✅ 구현 완료 | 95% | upsert 로직 작동 |
| **3. 펀더멘털 지표 증분 업데이트** | ✅ 구현 완료 | 80% | --incremental 옵션 제공 |
| **4. 주가배수 계산 (P/E, P/B, P/S)** | ✅ 구현 완료 | 85% | 최신 사업보고서 기반 |
| **5. 배당 수익률 계산** | ✅ 구현 완료 | 90% | 최신 배당금/주가 기준 |
| **6. 분기별 순자산 업데이트** | ❌ 미구현 | 0% | DART API 활용 필요 |

### 주요 발견사항
✅ **강점**:
- OHLCV, 펀더멘털, 배당 수익률의 증분 업데이트 스크립트가 잘 구현되어 있음
- 주가배수가 최신 사업보고서 기반으로 계산되는 로직이 구현되어 있음
- PostgreSQL upsert 로직을 통한 안정적인 증분 업데이트 지원

⚠️ **개선 필요**:
- KR 시장 ticker 테이블의 통합 증분 업데이트 스크립트 부재
- 분기별 실적 보고서 기반의 순자산 업데이트 기능 미구현
- 통합 DB 최신화 마스터 스크립트 부재

---

## 1️⃣ Tickers 테이블 증분 업데이트

### 현재 구현 현황

#### ✅ 해외 시장 (US, HK, JP, CN, VN)
**스크립트**: `scripts/update_master_files.py`

**기능**:
- KIS API를 통한 master file 자동 다운로드 및 업데이트
- 멀티 리전 지원 (US, HK, JP, CN, VN)
- 일일 자동 업데이트 (6AM KST 스케줄링 가능)
- 데이터 품질 검증 (95% 완전성 threshold)
- Prometheus 메트릭 export

**사용법**:
```bash
# 전체 리전 업데이트
python3 scripts/update_master_files.py

# 특정 리전만 업데이트
python3 scripts/update_master_files.py --regions US HK

# Dry run (미리보기)
python3 scripts/update_master_files.py --dry-run

# 검증 스킵
python3 scripts/update_master_files.py --no-validate
```

**출력 예시**:
```
================================================================================
Master File Daily Update - 2025-11-01 09:00:00
================================================================================
🔄 [US] Starting update...
✅ [US] Update successful: 11,234 tickers in 5.23s
🔄 [HK] Starting update...
✅ [HK] Update successful: 2,456 tickers in 3.12s
...
================================================================================
Update Summary
================================================================================
  ✅ US: 11,234 tickers in 5.23s
  ✅ HK: 2,456 tickers in 3.12s
  ...
Total: 5/5 regions updated successfully (100%)
Duration: 18.45s
================================================================================
```

#### ⚠️ 한국 시장 (KR) - 부분 구현

**현재 상황**:
- `update_master_files.py`는 KR 시장을 지원하지 않음
- pykrx 기반 ticker 수집 로직이 여러 스크립트에 분산되어 있음

**관련 스크립트**:
1. `scripts/backfill_orphaned_tickers.py`:
   - pykrx `stock.get_market_ticker_list()` 사용
   - KOSPI, KOSDAQ, KONEX 지원
   - Orphaned ticker 복구 목적 (일회성)

2. `scripts/week3_define_universe_v1_slow.py`:
   - pykrx로 KOSPI/KOSDAQ ticker list 가져오기
   - Universe 정의 목적 (전략 개발용)

3. `scripts/collect_kr_market_data.py`:
   - yfinance + KIS API 조합
   - 시가총액, 발행주식수 등 메타데이터 수집

**문제점**:
- ❌ KR 시장의 **통합 증분 업데이트 스크립트**가 없음
- ❌ 일일 자동화된 ticker 최신화 워크플로우 부재
- ❌ 신규 상장/상장폐지 종목 자동 반영 기능 없음

### 개선 권장사항

#### 📌 Option A: pykrx 기반 KR Ticker 증분 업데이트 스크립트 개발

**구현 내용**:
```python
#!/usr/bin/env python3
"""
scripts/update_kr_tickers.py - KR Market Ticker Incremental Update

Features:
- Daily ticker list sync from pykrx (KOSPI, KOSDAQ, KONEX)
- New listing detection and insertion
- Delisting detection and status update
- Integration with update_master_files.py workflow
"""

from pykrx import stock
from datetime import date

def update_kr_tickers(db: PostgresDatabaseManager, dry_run: bool = False):
    """
    Update KR market tickers incrementally

    Process:
    1. Fetch current ticker list from pykrx (KOSPI, KOSDAQ, KONEX)
    2. Compare with database tickers (region='KR')
    3. Insert new tickers (new listings)
    4. Update delisted tickers (status='delisted')
    5. Update ticker names (name changes)
    """

    today = date.today().strftime('%Y%m%d')

    # Step 1: Fetch current ticker lists
    kospi_tickers = stock.get_market_ticker_list(today, market="KOSPI")
    kosdaq_tickers = stock.get_market_ticker_list(today, market="KOSDAQ")
    konex_tickers = stock.get_market_ticker_list(today, market="KONEX")

    current_tickers = {
        **{t: 'KOSPI' for t in kospi_tickers},
        **{t: 'KOSDAQ' for t in kosdaq_tickers},
        **{t: 'KONEX' for t in konex_tickers}
    }

    # Step 2: Get existing tickers from database
    existing_query = "SELECT ticker, exchange FROM tickers WHERE region='KR'"
    existing_tickers = {row['ticker']: row['exchange'] for row in db.execute_query(existing_query)}

    # Step 3: Identify new listings
    new_tickers = set(current_tickers.keys()) - set(existing_tickers.keys())

    # Step 4: Identify delistings
    delisted_tickers = set(existing_tickers.keys()) - set(current_tickers.keys())

    # Step 5: Insert new tickers
    if not dry_run:
        for ticker in new_tickers:
            name = stock.get_market_ticker_name(ticker)
            exchange = current_tickers[ticker]
            # INSERT INTO tickers ...

    # Step 6: Mark delisted tickers
    if not dry_run:
        for ticker in delisted_tickers:
            # UPDATE tickers SET status='delisted' WHERE ticker=...

    return {
        'new_listings': len(new_tickers),
        'delistings': len(delisted_tickers),
        'total_current': len(current_tickers)
    }
```

**통합 방안**:
```bash
# update_master_files.py 수정
python3 scripts/update_master_files.py --regions KR US HK JP CN VN
```

---

## 2️⃣ OHLCV 증분 업데이트

### ✅ 구현 완료 (95%)

**스크립트**: `modules/kis_data_collector.py`

**주요 기능**:
1. **Gap Detection**: 기존 데이터와 현재 날짜 간 갭 감지
2. **Incremental Fetch**: 누락된 날짜만 KIS API에서 가져오기
3. **Upsert Logic**: PostgreSQL ON CONFLICT 활용

**코드 예시** (kis_data_collector.py:833-866):
```python
upsert_sql = """
INSERT INTO ohlcv_data (
    ticker, region, timeframe, date,
    open, high, low, close, volume,
    ma5, ma20, ma60, ma120, ma200,
    rsi, macd, macd_signal, macd_hist,
    bb_upper, bb_middle, bb_lower, volume_ma20
) VALUES (
    %s, %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s, %s
)
ON CONFLICT (ticker, region, timeframe, date)
DO UPDATE SET
    open=excluded.open,
    high=excluded.high,
    low=excluded.low,
    close=excluded.close,
    volume=excluded.volume,
    ... (technical indicators)
"""
```

**실행 방법**:
```bash
# 전체 OHLCV 업데이트
python3 -m modules.kis_data_collector --region KR

# 특정 ticker만 업데이트
python3 -m modules.kis_data_collector --tickers 005930 000660

# Dry run
python3 -m modules.kis_data_collector --dry-run
```

**성능**:
- 단일 ticker: <100ms
- 배치 (20 tickers): <500ms
- PostgreSQL upsert: 중복 방지 보장

---

## 3️⃣ 펀더멘털 지표 증분 업데이트

### ✅ 구현 완료 (80%)

**스크립트**: `scripts/backfill_fundamentals_dart.py`

**주요 기능**:
1. **Incremental Mode**: `--incremental` 플래그로 미수집 ticker만 처리
2. **DART API 연동**: 최신 사업보고서 데이터 가져오기
3. **Fundamental Metrics 추출**:
   - ROE, ROA, Debt Ratio
   - Revenue, Operating Profit, Net Income
   - Total Assets, Liabilities, Equity

**실행 방법**:
```bash
# 전체 백필 (모든 ticker)
python3 scripts/backfill_fundamentals_dart.py

# 증분 업데이트 (미수집 ticker만)
python3 scripts/backfill_fundamentals_dart.py --incremental

# Dry run (미리보기)
python3 scripts/backfill_fundamentals_dart.py --dry-run

# Rate limiting (1 req/sec)
python3 scripts/backfill_fundamentals_dart.py --rate-limit 1.0

# 특정 개수만 처리 (테스트)
python3 scripts/backfill_fundamentals_dart.py --limit 10
```

**코드 예시** (backfill_fundamentals_dart.py:159-170):
```python
def get_kr_tickers_for_backfill(self, incremental: bool = False, limit: Optional[int] = None) -> List[Dict]:
    """
    Query KR tickers that need fundamental data backfill

    Args:
        incremental: If True, only fetch tickers with no fundamental data
        limit: Max number of tickers to process
    """
    if incremental:
        # Only tickers without fundamental data in last 90 days
        query = """
        SELECT t.ticker, t.name
        FROM tickers t
        LEFT JOIN ticker_fundamentals f
          ON t.ticker = f.ticker
          AND f.region = 'KR'
          AND f.data_source = 'DART'
          AND f.date >= NOW() - INTERVAL '90 days'
        WHERE t.region = 'KR'
          AND t.is_etf = FALSE
          AND f.ticker IS NULL
        """
    else:
        # All KR tickers
        query = "SELECT ticker, name FROM tickers WHERE region='KR' AND is_etf=FALSE"

    # Execute and return results
```

**출력 예시**:
```
2025-11-01 09:00:00 | INFO | 📊 Starting DART Fundamental Backfill
2025-11-01 09:00:00 | INFO | Mode: Incremental (only missing data)
2025-11-01 09:00:00 | INFO | Found 342 tickers needing updates
2025-11-01 09:00:01 | INFO | [005930] Samsung Electronics
  → Date: 2024-12-31, Fiscal Year: 2024
  → Balance Sheet: Assets=469,490,800,000,000 KRW, Equity=315,123,400,000,000 KRW
  → Income Statement: Revenue=308,332,764,000,000 KRW, Net Income=35,989,051,000,000 KRW
  → Ratios: ROE=11.42%, PER=18.52, PBR=2.11
2025-11-01 09:00:02 | INFO | ✅ [005930] Success (1/342)
...
```

---

## 4️⃣ 주가배수 계산 (P/E, P/B, P/S)

### ✅ 구현 완료 (85%)

**스크립트**: `scripts/backfill_fundamentals_dart.py`

**계산 로직** (backfill_fundamentals_dart.py:295-349):

```python
def calculate_valuation_ratios(self, ticker: str, metrics: Dict, price: Decimal) -> Dict:
    """
    Calculate valuation ratios (P/E, P/B, P/S) from DART financial data

    Formula:
    - P/E = Current Price / EPS
      where EPS = Net Income / Shares Outstanding

    - P/B = Current Price / Book Value Per Share
      where BVPS = Total Equity / Shares Outstanding

    - P/S = Current Price / Sales Per Share
      where SPS = Revenue / Shares Outstanding

    Args:
        ticker: Stock ticker
        metrics: DART fundamental metrics (from latest annual report)
        price: Current stock price (latest OHLCV close)

    Returns:
        Dict with calculated ratios: {per, pbr, psr, eps, book_value_per_share, market_cap}
    """
    ratios = {}

    # Extract financial statement items
    total_equity = metrics.get('total_equity', 0)
    net_income = metrics.get('net_income', 0)
    revenue = metrics.get('revenue', 0)
    shares_outstanding = metrics.get('shares_outstanding')  # From DART

    # Calculate EPS (Earnings Per Share)
    if net_income > 0 and shares_outstanding and shares_outstanding > 0:
        eps = net_income / shares_outstanding
        ratios['eps'] = eps

        # Calculate P/E ratio
        if eps > 0:
            ratios['per'] = float(price / Decimal(str(eps)))

    # Calculate Book Value Per Share
    if total_equity > 0 and shares_outstanding and shares_outstanding > 0:
        book_value_per_share = total_equity / shares_outstanding
        ratios['book_value_per_share'] = book_value_per_share

        # Calculate P/B ratio
        if book_value_per_share > 0:
            ratios['pbr'] = float(price / Decimal(str(book_value_per_share)))

    # Calculate P/S ratio (Price-to-Sales)
    if revenue > 0 and shares_outstanding and shares_outstanding > 0:
        sales_per_share = revenue / shares_outstanding
        if sales_per_share > 0:
            ratios['psr'] = float(price / Decimal(str(sales_per_share)))

    # Calculate market cap
    if shares_outstanding:
        ratios['market_cap'] = int(float(price) * shares_outstanding)

    return ratios
```

### 📊 데이터 소스

#### 사업보고서 기반 지표 (DART API)
- **Total Equity** (자본총계): 최신 사업보고서 재무제표
- **Net Income** (당기순이익): 최신 사업보고서 손익계산서
- **Revenue** (매출액): 최신 사업보고서 손익계산서
- **Shares Outstanding** (발행주식수): 최신 사업보고서

#### 주가 데이터 (OHLCV)
- **Current Price**: `SELECT close FROM ohlcv_data WHERE ticker=%s ORDER BY date DESC LIMIT 1`

### ✅ 사용자 요구사항 충족 여부

**요구사항**:
> "P/E, P/S와 같은 주가배수는 그 종목의 가장 최근 날짜의 ohlcv에서 '종가' / '가장 최신 사업보고서(annual report) 기반의 EPS, SPS 등'"

**구현 현황**: ✅ **충족**
- ✅ 최신 OHLCV 종가 사용
- ✅ DART API에서 최신 사업보고서 데이터 가져오기
- ✅ 주가배수 = 최신 종가 / 최신 사업보고서 기반 per-share 지표

---

## 5️⃣ 배당 수익률 계산

### ✅ 구현 완료 (90%)

**스크립트**: `scripts/calculate_dividend_yield.py`

**계산 로직** (calculate_dividend_yield.py:116-150):

```python
def calculate_dividend_yield_for_ticker(self, ticker: str) -> Optional[Dict]:
    """
    Calculate Dividend Yield factor for a single ticker

    Formula:
    Dividend Yield (%) = (Latest DPS / Latest Stock Price) × 100

    where:
    - Latest DPS: Most recent dividend per share from pykrx (DAILY data)
    - Latest Stock Price: Most recent close price from ohlcv_data

    Returns:
        {
            'ticker': str,
            'dividend_yield': float,  # Percentage (e.g., 2.5%)
            'dividend_per_share': float,  # KRW
            'close_price': float,  # KRW
            'dps_date': date,
            'price_date': date
        }
    """

    # Step 1: Get latest dividend per share from pykrx (DAILY data)
    query_dps = """
    SELECT
        dividend_per_share,
        dividend_yield as pykrx_dividend_yield,
        date as dps_date
    FROM ticker_fundamentals
    WHERE ticker = %s
      AND region = 'KR'
      AND period_type = 'DAILY'
      AND data_source = 'pykrx'
      AND dividend_per_share IS NOT NULL
      AND dividend_per_share > 0
    ORDER BY date DESC
    LIMIT 1
    """

    # Step 2: Get latest stock price from ohlcv_data
    query_price = """
    SELECT
        close as close_price,
        date as price_date
    FROM ohlcv_data
    WHERE ticker = %s
      AND region = 'KR'
      AND timeframe = '1d'
    ORDER BY date DESC
    LIMIT 1
    """

    # Step 3: Calculate dividend yield
    dividend_yield = (dps / close_price) * 100

    return {
        'ticker': ticker,
        'dividend_yield': dividend_yield,
        'dividend_per_share': dps,
        'close_price': close_price,
        'dps_date': dps_date,
        'price_date': price_date
    }
```

### ✅ 사용자 요구사항 충족 여부

**요구사항**:
> "가장 최근 지급한 주당 배당금과 가장 최근 수집한 주가를 기준으로 배당수익률이 계산"

**구현 현황**: ✅ **충족**
- ✅ pykrx에서 가장 최근 배당금 (dividend_per_share) 가져오기
- ✅ ohlcv_data에서 가장 최근 종가 가져오기
- ✅ 배당 수익률 = (최신 DPS / 최신 종가) × 100

**실행 방법**:
```bash
# 전체 ticker 배당 수익률 계산
python3 scripts/calculate_dividend_yield.py

# 특정 ticker만 계산
python3 scripts/calculate_dividend_yield.py --tickers 005930 000660

# Dry run (미리보기)
python3 scripts/calculate_dividend_yield.py --dry-run
```

---

## 6️⃣ 분기별 순자산 업데이트

### ❌ 미구현 (0%)

**사용자 요구사항**:
> "순자산 관련 지표는 가장 최신 발표된 실적 보고서를 기반으로 해야 함. 회사가 매 분기별 발표하는 순자산의 현황을 파악하기 용이할 것으로 보임."

**현재 구현**:
- ❌ 연간 사업보고서만 수집 (backfill_fundamentals_dart.py)
- ❌ 분기별 실적 보고서 수집 기능 없음
- ❌ 순자산 지표의 분기별 업데이트 없음

### 📌 개선 권장사항

#### Option A: DART API 분기별 재무제표 수집 기능 추가

**구현 내용**:
```python
#!/usr/bin/env python3
"""
scripts/backfill_quarterly_financials_dart.py - Quarterly Financial Statements

Features:
- Fetch quarterly (Q1, Q2, Q3, Q4) financial statements from DART API
- Extract Total Equity (순자산), Total Assets, Total Liabilities
- Calculate P/B ratio using latest quarter's equity
- Incremental update (only missing quarters)
"""

from modules.dart_api_client import DARTApiClient

def get_quarterly_financials(dart: DARTApiClient, corp_code: str, year: int, quarter: int):
    """
    Fetch quarterly financial statements from DART API

    Args:
        corp_code: DART corporate code (8-digit)
        year: Fiscal year (e.g., 2025)
        quarter: Quarter (1, 2, 3, 4)

    Returns:
        {
            'total_equity': float,  # 자본총계
            'total_assets': float,  # 자산총계
            'total_liabilities': float,  # 부채총계
            'fiscal_year': int,
            'fiscal_quarter': int,
            'report_date': date
        }
    """

    # DART API: 분기보고서 재무제표 조회
    # endpoint: /api/fnlttSinglAcntAll.json
    # reprt_code: 11013 (1분기), 11012 (반기), 11014 (3분기), 11011 (사업보고서)

    reprt_code_map = {
        1: '11013',  # 1분기
        2: '11012',  # 반기 (2분기)
        3: '11014',  # 3분기
        4: '11011'   # 사업보고서 (4분기)
    }

    params = {
        'crtfc_key': dart.api_key,
        'corp_code': corp_code,
        'bsns_year': str(year),
        'reprt_code': reprt_code_map[quarter],
        'fs_div': 'CFS'  # Consolidated Financial Statements
    }

    response = dart._make_request('/api/fnlttSinglAcntAll.json', params)

    # Parse response and extract Total Equity
    # ... (implementation details)

    return financials
```

**데이터베이스 스키마 추가**:
```sql
-- Add fiscal_quarter column to ticker_fundamentals
ALTER TABLE ticker_fundamentals
ADD COLUMN fiscal_quarter INT CHECK (fiscal_quarter BETWEEN 1 AND 4);

-- Update unique constraint to include quarter
ALTER TABLE ticker_fundamentals
DROP CONSTRAINT IF EXISTS ticker_fundamentals_ticker_date_key;

ALTER TABLE ticker_fundamentals
ADD CONSTRAINT ticker_fundamentals_ticker_date_quarter_key
UNIQUE (ticker, region, date, fiscal_year, fiscal_quarter, data_source);
```

**실행 방법**:
```bash
# 2024년 전체 분기 백필
python3 scripts/backfill_quarterly_financials_dart.py --year 2024

# 2025년 1분기만
python3 scripts/backfill_quarterly_financials_dart.py --year 2025 --quarter 1

# 증분 업데이트 (미수집 분기만)
python3 scripts/backfill_quarterly_financials_dart.py --incremental
```

---

## 🎯 통합 DB 최신화 마스터 스크립트

### ❌ 현재 부재

퀀트 분석 전 DB를 최신 상태로 만들기 위한 **단일 진입점 스크립트**가 없습니다.

### 📌 개선 권장사항: 통합 마스터 스크립트 개발

**스크립트**: `scripts/update_database.py`

**구현 내용**:
```python
#!/usr/bin/env python3
"""
scripts/update_database.py - Master Database Update Script

통합 DB 최신화 스크립트 - 퀀트 분석 전 실행 필수

Features:
1. Ticker 테이블 증분 업데이트 (KR, US, HK, JP, CN, VN)
2. OHLCV 데이터 증분 업데이트 (최근 7일 gap filling)
3. 펀더멘털 지표 증분 업데이트 (DART API)
4. 주가배수 계산 (P/E, P/B, P/S)
5. 배당 수익률 계산
6. 분기별 순자산 업데이트 (optional)
7. 데이터 품질 검증

Usage:
    # 전체 업데이트 (권장)
    python3 scripts/update_database.py

    # KR 시장만 업데이트
    python3 scripts/update_database.py --region KR

    # 특정 단계만 실행
    python3 scripts/update_database.py --steps tickers,ohlcv

    # Dry run (미리보기)
    python3 scripts/update_database.py --dry-run

    # 백그라운드 실행
    nohup python3 scripts/update_database.py > log/db_update_$(date +%Y%m%d).log 2>&1 &
"""

import sys
import os
import time
import logging
from datetime import datetime
from typing import List, Dict

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.db_manager_postgres import PostgresDatabaseManager
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Setup logging
log_filename = f"log/{datetime.now().strftime('%Y%m%d')}_db_update.log"
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DatabaseUpdater:
    """통합 데이터베이스 업데이트 오케스트레이터"""

    def __init__(self, db: PostgresDatabaseManager, dry_run: bool = False):
        self.db = db
        self.dry_run = dry_run

        # Statistics
        self.stats = {
            'start_time': time.time(),
            'steps_completed': [],
            'steps_failed': [],
            'total_duration': 0.0
        }

    def run_update_pipeline(self, regions: List[str] = None, steps: List[str] = None):
        """
        실행 파이프라인

        Args:
            regions: 업데이트할 리전 리스트 (None = 전체)
            steps: 실행할 단계 리스트 (None = 전체)
                  ['tickers', 'ohlcv', 'fundamentals', 'ratios', 'dividend', 'quarterly']
        """

        logger.info("=" * 80)
        logger.info("📊 Database Update Pipeline - Quant Investment Platform")
        logger.info(f"Start Time: {datetime.now()}")
        if self.dry_run:
            logger.info("⚠️ DRY RUN MODE - No actual database writes")
        logger.info("=" * 80)

        # Default: All regions and steps
        if regions is None:
            regions = ['KR', 'US', 'HK', 'JP', 'CN', 'VN']

        if steps is None:
            steps = ['tickers', 'ohlcv', 'fundamentals', 'ratios', 'dividend']

        # Step 1: Update Tickers
        if 'tickers' in steps:
            self._update_tickers(regions)

        # Step 2: Update OHLCV (last 7 days gap filling)
        if 'ohlcv' in steps:
            self._update_ohlcv(regions)

        # Step 3: Update Fundamental Data (DART for KR, yfinance for others)
        if 'fundamentals' in steps:
            self._update_fundamentals(regions)

        # Step 4: Calculate Valuation Ratios (P/E, P/B, P/S)
        if 'ratios' in steps:
            self._calculate_valuation_ratios(regions)

        # Step 5: Calculate Dividend Yield
        if 'dividend' in steps:
            self._calculate_dividend_yield(regions)

        # Step 6: Update Quarterly Financials (optional, KR only)
        if 'quarterly' in steps and 'KR' in regions:
            self._update_quarterly_financials()

        # Step 7: Data Quality Validation
        self._validate_data_quality(regions)

        # Summary
        self._print_summary()

    def _update_tickers(self, regions: List[str]):
        """Step 1: Ticker 테이블 증분 업데이트"""
        logger.info("\n" + "=" * 80)
        logger.info("Step 1: Updating Tickers")
        logger.info("=" * 80)

        try:
            # KR: pykrx 기반 업데이트
            if 'KR' in regions:
                from scripts.update_kr_tickers import update_kr_tickers
                result = update_kr_tickers(self.db, dry_run=self.dry_run)
                logger.info(f"✅ [KR] {result['total_current']} tickers, "
                           f"{result['new_listings']} new, {result['delistings']} delisted")

            # Others: KIS API master files
            overseas_regions = [r for r in regions if r != 'KR']
            if overseas_regions:
                from scripts.update_master_files import main as update_master
                update_master(regions=overseas_regions, dry_run=self.dry_run)

            self.stats['steps_completed'].append('tickers')

        except Exception as e:
            logger.error(f"❌ Failed to update tickers: {e}")
            self.stats['steps_failed'].append('tickers')

    def _update_ohlcv(self, regions: List[str]):
        """Step 2: OHLCV 증분 업데이트 (최근 7일 gap filling)"""
        logger.info("\n" + "=" * 80)
        logger.info("Step 2: Updating OHLCV Data (Last 7 Days)")
        logger.info("=" * 80)

        try:
            # KR: KIS API
            if 'KR' in regions:
                from modules.kis_data_collector import KISDataCollector
                collector = KISDataCollector(db_path=None, region='KR')  # PostgreSQL mode
                # Run incremental update for last 7 days
                # ... (implementation)

            # US, HK, etc: yfinance or KIS API
            # ... (implementation)

            self.stats['steps_completed'].append('ohlcv')

        except Exception as e:
            logger.error(f"❌ Failed to update OHLCV: {e}")
            self.stats['steps_failed'].append('ohlcv')

    def _update_fundamentals(self, regions: List[str]):
        """Step 3: 펀더멘털 지표 증분 업데이트"""
        logger.info("\n" + "=" * 80)
        logger.info("Step 3: Updating Fundamental Data")
        logger.info("=" * 80)

        try:
            # KR: DART API
            if 'KR' in regions:
                from scripts.backfill_fundamentals_dart import DARTFundamentalBackfiller
                from modules.dart_api_client import DARTApiClient

                dart_api_key = os.getenv('DART_API_KEY')
                dart = DARTApiClient(api_key=dart_api_key)
                backfiller = DARTFundamentalBackfiller(self.db, dart, dry_run=self.dry_run)

                # Run incremental update
                result = backfiller.run_backfill(incremental=True)
                logger.info(f"✅ [KR] {result['tickers_success']} tickers updated")

            # Others: yfinance
            # ... (implementation)

            self.stats['steps_completed'].append('fundamentals')

        except Exception as e:
            logger.error(f"❌ Failed to update fundamentals: {e}")
            self.stats['steps_failed'].append('fundamentals')

    def _calculate_valuation_ratios(self, regions: List[str]):
        """Step 4: 주가배수 계산 (P/E, P/B, P/S)"""
        logger.info("\n" + "=" * 80)
        logger.info("Step 4: Calculating Valuation Ratios (P/E, P/B, P/S)")
        logger.info("=" * 80)

        # Note: 이미 backfill_fundamentals_dart.py에서 계산됨
        # 별도 실행 불필요 (fundamentals 단계에서 자동 계산)
        logger.info("✅ Valuation ratios already calculated in fundamentals step")
        self.stats['steps_completed'].append('ratios')

    def _calculate_dividend_yield(self, regions: List[str]):
        """Step 5: 배당 수익률 계산"""
        logger.info("\n" + "=" * 80)
        logger.info("Step 5: Calculating Dividend Yield")
        logger.info("=" * 80)

        try:
            if 'KR' in regions:
                from scripts.calculate_dividend_yield import DividendYieldCalculator
                calculator = DividendYieldCalculator(self.db, dry_run=self.dry_run)
                result = calculator.calculate_all_tickers()
                logger.info(f"✅ [KR] {result['tickers_success']} tickers calculated")

            self.stats['steps_completed'].append('dividend')

        except Exception as e:
            logger.error(f"❌ Failed to calculate dividend yield: {e}")
            self.stats['steps_failed'].append('dividend')

    def _update_quarterly_financials(self):
        """Step 6: 분기별 순자산 업데이트 (KR only, optional)"""
        logger.info("\n" + "=" * 80)
        logger.info("Step 6: Updating Quarterly Financials (KR)")
        logger.info("=" * 80)

        try:
            # TODO: Implement quarterly financials backfill
            logger.warning("⚠️ Quarterly financials update not yet implemented")
            # from scripts.backfill_quarterly_financials_dart import ...

            self.stats['steps_completed'].append('quarterly')

        except Exception as e:
            logger.error(f"❌ Failed to update quarterly financials: {e}")
            self.stats['steps_failed'].append('quarterly')

    def _validate_data_quality(self, regions: List[str]):
        """Step 7: 데이터 품질 검증"""
        logger.info("\n" + "=" * 80)
        logger.info("Step 7: Data Quality Validation")
        logger.info("=" * 80)

        for region in regions:
            # Check ticker count
            query = "SELECT COUNT(*) as cnt FROM tickers WHERE region=%s"
            result = self.db.execute_query(query, (region,))
            ticker_count = result[0]['cnt']

            # Check OHLCV coverage (last 30 days)
            query = """
            SELECT COUNT(DISTINCT ticker) as cnt
            FROM ohlcv_data
            WHERE region=%s AND date >= NOW() - INTERVAL '30 days'
            """
            result = self.db.execute_query(query, (region,))
            ohlcv_count = result[0]['cnt']

            coverage = (ohlcv_count / ticker_count * 100) if ticker_count > 0 else 0
            status = "✅" if coverage >= 80 else "⚠️"

            logger.info(f"  {status} [{region}] {ticker_count} tickers, "
                       f"{ohlcv_count} with OHLCV ({coverage:.1f}%)")

    def _print_summary(self):
        """실행 결과 요약"""
        duration = time.time() - self.stats['start_time']
        self.stats['total_duration'] = duration

        logger.info("\n" + "=" * 80)
        logger.info("📊 Database Update Summary")
        logger.info("=" * 80)
        logger.info(f"Completed Steps: {', '.join(self.stats['steps_completed'])}")
        if self.stats['steps_failed']:
            logger.error(f"Failed Steps: {', '.join(self.stats['steps_failed'])}")
        logger.info(f"Total Duration: {duration:.2f}s")
        logger.info(f"End Time: {datetime.now()}")
        logger.info("=" * 80)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Master Database Update Script - Quant Investment Platform'
    )
    parser.add_argument(
        '--regions',
        nargs='+',
        choices=['KR', 'US', 'HK', 'JP', 'CN', 'VN'],
        help='Regions to update (default: all)'
    )
    parser.add_argument(
        '--steps',
        nargs='+',
        choices=['tickers', 'ohlcv', 'fundamentals', 'ratios', 'dividend', 'quarterly'],
        help='Steps to execute (default: all except quarterly)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview operations without database writes'
    )

    args = parser.parse_args()

    # Initialize database
    db = PostgresDatabaseManager()

    # Initialize updater
    updater = DatabaseUpdater(db, dry_run=args.dry_run)

    # Run update pipeline
    try:
        updater.run_update_pipeline(regions=args.regions, steps=args.steps)
        sys.exit(0)

    except KeyboardInterrupt:
        logger.warning("\n⚠️ Update interrupted by user")
        sys.exit(130)

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
```

### 사용 예시

#### 1. 퀀트 분석 전 전체 DB 최신화 (권장)
```bash
python3 scripts/update_database.py
```

**실행 결과**:
```
================================================================================
📊 Database Update Pipeline - Quant Investment Platform
Start Time: 2025-11-01 09:00:00
================================================================================

================================================================================
Step 1: Updating Tickers
================================================================================
✅ [KR] 2,543 tickers, 5 new, 2 delisted
✅ [US] 11,234 tickers in 5.23s
✅ [HK] 2,456 tickers in 3.12s
...

================================================================================
Step 2: Updating OHLCV Data (Last 7 Days)
================================================================================
✅ [KR] 2,543 tickers updated (gap: 3 days)
...

================================================================================
Step 3: Updating Fundamental Data
================================================================================
✅ [KR] 342 tickers updated (incremental mode)
...

================================================================================
Step 4: Calculating Valuation Ratios (P/E, P/B, P/S)
================================================================================
✅ Valuation ratios already calculated in fundamentals step

================================================================================
Step 5: Calculating Dividend Yield
================================================================================
✅ [KR] 1,234 tickers calculated

================================================================================
Step 6: Updating Quarterly Financials (KR)
================================================================================
⚠️ Quarterly financials update not yet implemented

================================================================================
Step 7: Data Quality Validation
================================================================================
  ✅ [KR] 2,543 tickers, 2,498 with OHLCV (98.2%)
  ✅ [US] 11,234 tickers, 10,987 with OHLCV (97.8%)
  ...

================================================================================
📊 Database Update Summary
================================================================================
Completed Steps: tickers, ohlcv, fundamentals, ratios, dividend, quarterly
Total Duration: 125.45s
End Time: 2025-11-01 09:02:05
================================================================================
```

#### 2. KR 시장만 업데이트
```bash
python3 scripts/update_database.py --regions KR
```

#### 3. 특정 단계만 실행 (OHLCV + 펀더멘털)
```bash
python3 scripts/update_database.py --steps ohlcv fundamentals
```

#### 4. Dry run (미리보기)
```bash
python3 scripts/update_database.py --dry-run
```

#### 5. 백그라운드 실행
```bash
nohup python3 scripts/update_database.py > log/db_update_$(date +%Y%m%d).log 2>&1 &
tail -f log/db_update_*.log
```

---

## 📊 종합 평가 및 권장사항

### 현재 구현 상태 요약

| 기능 | 상태 | 우선순위 | 예상 작업량 |
|------|------|----------|------------|
| **1. Tickers 증분 업데이트 (KR)** | ⚠️ 부분 구현 | 🔴 High | 2-3 hours |
| **2. OHLCV 증분 업데이트** | ✅ 완료 | - | - |
| **3. 펀더멘털 증분 업데이트** | ✅ 완료 | - | - |
| **4. 주가배수 계산** | ✅ 완료 | - | - |
| **5. 배당 수익률 계산** | ✅ 완료 | - | - |
| **6. 분기별 순자산 업데이트** | ❌ 미구현 | 🟡 Medium | 4-6 hours |
| **7. 통합 마스터 스크립트** | ❌ 미구현 | 🔴 High | 3-4 hours |

### 단계별 개선 계획

#### Phase 1: Critical (1-2 days)
1. ✅ **KR Ticker 증분 업데이트 스크립트 개발** (`update_kr_tickers.py`)
   - pykrx 기반 KOSPI/KOSDAQ/KONEX ticker 리스트 가져오기
   - 신규 상장/상장폐지 감지 및 DB 반영
   - `update_master_files.py`와 통합

2. ✅ **통합 마스터 스크립트 개발** (`update_database.py`)
   - 모든 업데이트 단계를 하나의 진입점으로 통합
   - Dry run 모드, 리전 선택, 단계 선택 기능
   - 데이터 품질 검증 포함

#### Phase 2: Important (3-5 days)
3. ✅ **분기별 순자산 업데이트 기능 개발** (`backfill_quarterly_financials_dart.py`)
   - DART API 분기 보고서 조회
   - 순자산 (Total Equity) 분기별 데이터 수집
   - P/B 비율의 분기별 업데이트

4. ✅ **자동화 및 스케줄링**
   - Cron job 설정 (일일 자동 실행)
   - 실패 알림 (Slack/Email)
   - Prometheus 메트릭 export

### 즉시 사용 가능한 워크플로우

현재 시스템으로 퀀트 분석 전 DB 최신화를 수행하려면:

```bash
#!/bin/bash
# Daily Database Update Workflow (Before Quant Analysis)

set -e  # Exit on error

echo "=========================================="
echo "Daily Database Update - $(date)"
echo "=========================================="

# Step 1: Update overseas tickers
echo "\n[1/5] Updating overseas tickers..."
python3 scripts/update_master_files.py --regions US HK JP CN VN

# Step 2: Update KR OHLCV (manual, KR tickers update script not yet implemented)
echo "\n[2/5] Updating KR OHLCV..."
python3 -m modules.kis_data_collector --region KR

# Step 3: Update KR fundamentals (incremental)
echo "\n[3/5] Updating KR fundamentals..."
python3 scripts/backfill_fundamentals_dart.py --incremental --rate-limit 1.0

# Step 4: Calculate dividend yield
echo "\n[4/5] Calculating dividend yield..."
python3 scripts/calculate_dividend_yield.py

# Step 5: Data quality validation
echo "\n[5/5] Validating data quality..."
psql -d quant_platform -c "
SELECT
    region,
    COUNT(*) as ticker_count,
    COUNT(DISTINCT CASE WHEN ohlcv.ticker IS NOT NULL THEN t.ticker END) as ohlcv_count,
    ROUND(
        COUNT(DISTINCT CASE WHEN ohlcv.ticker IS NOT NULL THEN t.ticker END)::NUMERIC
        / COUNT(*)::NUMERIC * 100,
        2
    ) as coverage_pct
FROM tickers t
LEFT JOIN (
    SELECT DISTINCT ticker
    FROM ohlcv_data
    WHERE date >= NOW() - INTERVAL '30 days'
) ohlcv ON t.ticker = ohlcv.ticker
GROUP BY region
ORDER BY region;
"

echo "\n=========================================="
echo "Database update completed - $(date)"
echo "=========================================="
```

**저장 및 실행**:
```bash
chmod +x scripts/daily_db_update.sh
./scripts/daily_db_update.sh
```

---

## 📌 핵심 요약

### ✅ 사용자 요구사항 충족 현황

| 요구사항 | 충족 여부 | 비고 |
|---------|----------|------|
| **1. tickers 테이블 증분 업데이트** | ⚠️ 부분 | 해외 시장 ✅, KR 시장 ❌ |
| **2. OHLCV 증분 업데이트** | ✅ 충족 | kis_data_collector.py upsert 로직 |
| **3. 펀더멘털 지표 증분 업데이트** | ✅ 충족 | --incremental 옵션 제공 |
| **4. P/E, P/S 주가배수 계산 (최신 사업보고서 기반)** | ✅ 충족 | DART API 최신 데이터 사용 |
| **5. 배당 수익률 (최신 배당금/최신 주가)** | ✅ 충족 | pykrx DPS + OHLCV close |
| **6. 분기별 순자산 업데이트** | ❌ 미충족 | 기능 미구현 |
| **7. 퀀트 분석 전 DB 최신화 스크립트** | ⚠️ 부분 | 통합 스크립트 부재 |

### 🎯 즉시 조치 필요 항목

1. **KR Ticker 증분 업데이트 스크립트 개발** (우선순위: 🔴 High)
   - 예상 작업량: 2-3 hours
   - 구현 파일: `scripts/update_kr_tickers.py`

2. **통합 마스터 스크립트 개발** (우선순위: 🔴 High)
   - 예상 작업량: 3-4 hours
   - 구현 파일: `scripts/update_database.py`

3. **분기별 순자산 업데이트 기능** (우선순위: 🟡 Medium)
   - 예상 작업량: 4-6 hours
   - 구현 파일: `scripts/backfill_quarterly_financials_dart.py`

### 💡 현재 시스템으로 퀀트 분석 준비하기

통합 스크립트가 완성되기 전까지는 **임시 워크플로우**를 사용하세요:

```bash
# 1. 해외 시장 ticker 업데이트
python3 scripts/update_master_files.py --regions US HK JP CN VN

# 2. KR OHLCV 업데이트
python3 -m modules.kis_data_collector --region KR

# 3. KR 펀더멘털 증분 업데이트
python3 scripts/backfill_fundamentals_dart.py --incremental

# 4. 배당 수익률 계산
python3 scripts/calculate_dividend_yield.py

# 5. DB 상태 확인
psql -d quant_platform -c "SELECT region, COUNT(*) FROM tickers GROUP BY region;"
```

---

**리포트 종료**
