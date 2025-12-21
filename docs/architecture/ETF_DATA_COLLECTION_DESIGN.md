# ETF Data Collection System Design

**Date**: 2025-10-01
**Status**: Design Phase
**Architecture**: Hybrid Multi-Source Strategy

---

## 1. System Architecture Overview

### 1.1 Design Philosophy

```
┌─────────────────────────────────────────────────────────────────────┐
│ HYBRID ETF DATA COLLECTION ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐       │
│  │ KRX Data API│──┬──▶│ ETF         │◀──┬──│  KIS API    │       │
│  │ (Primary)   │  │   │ Collector   │   │  │ (Secondary) │       │
│  │ 10 fields   │  │   │             │   │  │ 6+ fields   │       │
│  └─────────────┘  │   └──────┬──────┘   │  └─────────────┘       │
│                   │          │          │                          │
│  ┌─────────────┐  │          │          │  ┌─────────────┐       │
│  │ OHLCV Data  │──┘          ▼          └──│ Manual CSV  │       │
│  │ (52W H/L)   │      ┌──────────────┐     │ (Fallback)  │       │
│  └─────────────┘      │   SQLite DB  │     └─────────────┘       │
│                       │  etf_details │                            │
│                       └──────────────┘                            │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Core Principles

1. **Progressive Enhancement**: Start with KRX Data API (no auth), enhance with KIS API
2. **Graceful Degradation**: CSV fallback for fields not provided by APIs
3. **Rate Limit Awareness**: 20 req/sec for KIS API, unlimited for KRX Data API
4. **Code Reusability**: Leverage existing `scanner.py` patterns (100% reusable)
5. **Minimal Authentication Dependency**: Primary source (KRX) requires no auth

---

## 2. Data Source Matrix

### 2.1 Field Coverage Comparison

| Field | Priority | KRX Data | KIS API | Calculation | Notes |
|-------|----------|----------|---------|-------------|-------|
| **Core Fields (P0)** |
| ticker | P0 | ✅ | ✅ | - | ISU_SRT_CD |
| issuer | P0 | ✅ | ❌ | - | COM_ABBRV |
| tracking_index | P0 | ✅ | ❌ | - | ETF_OBJ_IDX_NM |
| underlying_asset_class | P0 | ✅ | ❌ | - | IDX_ASST_CLSS_NM |
| expense_ratio | P0 | ✅ | ❌ | - | ETF_TOT_FEE |
| listed_shares | P0 | ✅ | ❌ | - | LIST_SHRS |
| **Enhanced Fields (P1)** |
| inception_date | P1 | ✅ | ❌ | - | LIST_DD |
| geographic_region | P1 | ✅ | ❌ | - | IDX_MKT_CLSS_NM |
| fund_type | P1 | ✅ | ❌ | - | ETF_REPLICA_METHD_TP_CD |
| leverage_ratio | P1 | ⚠️ | ❌ | Parse | IDX_CALC_INST_NM2 |
| aum | P1 | ⚠️ | ✅ | price×shares | Daily calculation |
| **Optional Fields (P2)** |
| underlying_asset_count | P2 | ❌ | ✅ | API query | Weekly update |
| tracking_error_20d | P2 | ❌ | ✅ | NAV compare | Weekly update |
| tracking_error_60d | P2 | ❌ | ✅ | NAV compare | Weekly update |
| tracking_error_120d | P2 | ❌ | ✅ | NAV compare | Weekly update |
| tracking_error_250d | P2 | ❌ | ✅ | NAV compare | Weekly update |
| week_52_high | P2 | ❌ | ✅ | OHLCV max | From daily data |
| week_52_low | P2 | ❌ | ✅ | OHLCV min | From daily data |
| sector_theme | P2 | ❌ | ❌ | Parse name | Heuristic |
| currency_hedged | P2 | ❌ | ❌ | Parse index | Heuristic |
| **Manual Fields (P3)** |
| ter | P3 | ❌ | ❌ | Manual | ETFCheck only |
| actual_expense_ratio | P3 | ❌ | ❌ | Manual | ETFCheck only |
| pension_eligible | P3 | ❌ | ❌ | Manual | Government policy |
| investment_strategy | P3 | ❌ | ❌ | Manual | Long text |

**Legend**:
- ✅ Directly available
- ⚠️ Partial data or requires calculation
- ❌ Not available

### 2.2 API Endpoint Specifications

#### KRX Data API (Primary Source)

```python
ENDPOINT = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
PARAMS = {
    'bld': 'dbms/MDC/STAT/standard/MDCSTAT04601',  # ETF 통계
    'locale': 'ko_KR',
    'trdDd': 'YYYYMMDD',
    'csvxls_isNo': 'false',
}

# Response Structure
{
    "output": [
        {
            "ISU_SRT_CD": "495710",              # ticker
            "ISU_ABBRV": "BNK 26-06 특수채...",  # name
            "COM_ABBRV": "비엔케이자산운용",        # issuer
            "ETF_OBJ_IDX_NM": "KAP 26-06...",    # tracking_index
            "IDX_MKT_CLSS_NM": "국내",            # geographic_region
            "IDX_ASST_CLSS_NM": "채권",           # underlying_asset_class
            "ETF_TOT_FEE": "0.100000",           # expense_ratio
            "LIST_SHRS": "2,106,000",            # listed_shares
            "LIST_DD": "2024/12/03",             # inception_date
            "ETF_REPLICA_METHD_TP_CD": "실물(액티브)", # fund_type
            "IDX_CALC_INST_NM2": "일반"           # leverage_ratio (partial)
        }
    ]
}

# Coverage: 1,029 ETFs
# Authentication: None required
# Rate Limit: Unlimited
# Update Frequency: Daily
```

#### KIS API (Secondary Source)

**1. ETF/ETN 현재가 (AUM Calculation)**

```python
ENDPOINT = "/uapi/etfetn/v1/quotations/inquire-price"
TR_ID = "FHPST02400000"
METHOD = "GET"

# Headers
{
    "authorization": "Bearer {access_token}",
    "appkey": "{app_key}",
    "appsecret": "{app_secret}",
    "tr_id": "FHPST02400000"
}

# Parameters
{
    "FID_COND_MRKT_DIV_CODE": "J",  # ETF
    "FID_INPUT_ISCD": "152100"       # ticker
}

# Response (Key Fields)
{
    "stck_prpr": "5200",             # 현재가
    "acml_vol": "123456",            # 누적거래량
    "hts_avls": "1234567890"         # 시가총액 (AUM proxy)
}

# Calculation: AUM = listed_shares × current_price
# Rate Limit: 20 req/sec
# Update Frequency: Daily @ 16:00 KST
```

**2. ETF 구성종목시세 (Constituent Count)**

```python
ENDPOINT = "/uapi/etfetn/v1/quotations/inquire-component-stock-price"
TR_ID = "FHKST121600C0"

# Response
{
    "output": [
        {"pdno": "005930", "prdt_name": "삼성전자", ...},
        {"pdno": "000660", "prdt_name": "SK하이닉스", ...}
    ]
}

# Calculation: underlying_asset_count = len(output)
# Update Frequency: Weekly @ Sunday 20:00 KST
```

**3. NAV 비교추이 (Tracking Error)**

```python
# Short-term tracking error (20d, 60d)
ENDPOINT = "/uapi/etfetn/v1/quotations/nav-comparison-trend"
TR_ID = "FHPST02440000"

# Long-term tracking error (120d, 250d)
ENDPOINT = "/uapi/etfetn/v1/quotations/nav-comparison-daily-trend"
TR_ID = "FHPST02440200"

# Response
{
    "output": [
        {"nav": "10050", "stck_prpr": "10000", ...}
    ]
}

# Calculation: tracking_error = ((price - nav) / nav) × 100
# Update Frequency: Weekly @ Sunday 21:00 KST
```

---

## 3. Module Architecture

### 3.1 Directory Structure

```
spock/
├── modules/
│   ├── etf_collector.py          # NEW: ETF data collection orchestrator
│   ├── etf_krx_api.py             # NEW: KRX Data API wrapper
│   ├── etf_kis_api.py             # NEW: KIS API ETF endpoints
│   ├── etf_parser.py              # NEW: Data parsing utilities
│   ├── scanner.py                 # EXISTING: Stock scanner (reuse patterns)
│   └── db_manager_sqlite.py       # EXISTING: Database operations
├── config/
│   ├── etf_manual_data.csv        # NEW: Manual ETF data (P3 fields)
│   └── market_schedule.json       # EXISTING: Market hours
└── docs/
    └── ETF_DATA_COLLECTION_DESIGN.md  # THIS FILE
```

### 3.2 Class Diagram

```
┌────────────────────────────────────────────────────────────────┐
│ ETFCollector (Orchestrator)                                    │
├────────────────────────────────────────────────────────────────┤
│ - krx_api: ETFKRXDataAPI                                       │
│ - kis_api: ETFKISApi                                           │
│ - db_manager: SQLiteDatabaseManager                            │
│ - parser: ETFDataParser                                        │
├────────────────────────────────────────────────────────────────┤
│ + collect_basic_info() → Phase 1 (KRX)                        │
│ + update_aum() → Phase 2 (KIS)                                │
│ + update_tracking_error() → Phase 3 (KIS)                     │
│ + update_52w_high_low() → Phase 4 (OHLCV)                     │
│ + load_manual_data() → Phase 5 (CSV)                          │
└────────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ ETFKRXDataAPI    │  │ ETFKISApi        │  │ ETFDataParser    │
├──────────────────┤  ├──────────────────┤  ├──────────────────┤
│ - session        │  │ - access_token   │  │                  │
│ - base_url       │  │ - app_key        │  │ + parse_krx()    │
├──────────────────┤  │ - app_secret     │  │ + parse_kis()    │
│ + get_etf_list() │  ├──────────────────┤  │ + parse_leverage│
│                  │  │ + get_price()    │  │ + parse_sector() │
│                  │  │ + get_holdings() │  │                  │
│                  │  │ + get_nav()      │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

### 3.3 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 1: Basic ETF Listing (Daily @ 09:00 KST)                 │
└─────────────────────────────────────────────────────────────────┘
    KRX Data API
         │
         │ HTTP POST (no auth)
         │ bld=dbms/MDC/STAT/standard/MDCSTAT04601
         │
         ▼
    ETFKRXDataAPI.get_etf_list()
         │
         │ Parse 10 fields
         │ - ticker, issuer, tracking_index, etc.
         │
         ▼
    ETFDataParser.parse_krx()
         │
         │ Transform & validate
         │
         ▼
    SQLiteDatabaseManager
         │
         │ INSERT INTO tickers (ticker, name, ...)
         │ INSERT INTO etf_details (ticker, issuer, ...)
         │
         ▼
    ✅ 1,029 ETFs saved

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 2: AUM Update (Daily @ 16:00 KST)                        │
└─────────────────────────────────────────────────────────────────┘
    SQLite (etf_details)
         │
         │ SELECT ticker, listed_shares FROM etf_details
         │
         ▼
    FOR EACH ticker (rate-limited: 20 req/sec):
         │
         │ ETFKISApi.get_price(ticker)
         │ OAuth 2.0 authentication
         │ TR_ID: FHPST02400000
         │
         ▼
    Calculate: AUM = listed_shares × current_price
         │
         ▼
    SQLiteDatabaseManager
         │
         │ UPDATE etf_details SET aum = ? WHERE ticker = ?
         │
         ▼
    ✅ AUM updated (~51 seconds for all ETFs)

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 3: Tracking Error (Weekly @ Sunday 21:00 KST)            │
└─────────────────────────────────────────────────────────────────┘
    FOR EACH ticker (rate-limited: 20 req/sec):
         │
         │ ETFKISApi.get_nav_trend(ticker)
         │ TR_ID: FHPST02440000 (20d, 60d)
         │ TR_ID: FHPST02440200 (120d, 250d)
         │
         ▼
    Calculate tracking errors:
         │ tracking_error = ((price - nav) / nav) × 100
         │ Average over periods: 20d, 60d, 120d, 250d
         │
         ▼
    SQLiteDatabaseManager
         │
         │ UPDATE etf_details SET
         │   tracking_error_20d = ?,
         │   tracking_error_60d = ?,
         │   ...
         │
         ▼
    ✅ Tracking errors updated (~102 seconds for all ETFs)

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 4: 52-Week High/Low (Part of daily OHLCV collection)     │
└─────────────────────────────────────────────────────────────────┘
    SQLite (ohlcv_data)
         │
         │ SELECT MAX(close), MIN(close)
         │ FROM ohlcv_data
         │ WHERE ticker = ? AND date >= DATE('now', '-250 days')
         │
         ▼
    SQLiteDatabaseManager
         │
         │ UPDATE etf_details SET
         │   week_52_high = ?,
         │   week_52_low = ?
         │
         ▼
    ✅ 52W high/low updated

┌─────────────────────────────────────────────────────────────────┐
│ PHASE 5: Manual Data (Quarterly)                               │
└─────────────────────────────────────────────────────────────────┘
    config/etf_manual_data.csv
         │
         │ ticker,ter,actual_expense_ratio,pension_eligible,...
         │ 152100,0.12,0.15,1,...
         │
         ▼
    ETFCollector.load_manual_data()
         │
         │ Parse CSV
         │ Validate fields
         │
         ▼
    SQLiteDatabaseManager
         │
         │ UPDATE etf_details SET
         │   ter = ?,
         │   actual_expense_ratio = ?,
         │   ...
         │
         ▼
    ✅ Manual fields updated
```

---

## 4. Implementation Specifications

### 4.1 Module: `etf_collector.py`

**Purpose**: Main orchestrator for ETF data collection

```python
"""
ETF 데이터 수집 통합 모듈 (하이브리드 전략)

Phase 1 (P0): KRX Data API → 기본 ETF 목록 (10 fields)
Phase 2 (P1): KIS API → AUM 계산 (1 field)
Phase 3 (P2): KIS API → 괴리율, 구성종목수 (5 fields)
Phase 4 (P2): OHLCV → 52주 고저 (2 fields)
Phase 5 (P3): CSV → 수동 입력 (4 fields)
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime

from modules.etf_krx_api import ETFKRXDataAPI
from modules.etf_kis_api import ETFKISApi
from modules.etf_parser import ETFDataParser
from modules.db_manager_sqlite import SQLiteDatabaseManager

logger = logging.getLogger(__name__)


class ETFCollector:
    """ETF 데이터 수집 오케스트레이터"""

    def __init__(self, db_path: str, kis_config: Optional[Dict] = None):
        """
        Args:
            db_path: SQLite database path
            kis_config: KIS API credentials (optional for Phase 1)
        """
        self.db_manager = SQLiteDatabaseManager(db_path)
        self.krx_api = ETFKRXDataAPI()
        self.kis_api = ETFKISApi(**kis_config) if kis_config else None
        self.parser = ETFDataParser()

    def collect_basic_info(self) -> int:
        """
        Phase 1: KRX Data API로 기본 ETF 정보 수집

        Returns:
            수집된 ETF 개수
        """
        logger.info("📊 Phase 1: KRX Data API로 기본 ETF 정보 수집 시작")

        # 1. KRX Data API 호출
        raw_data = self.krx_api.get_etf_list()
        logger.info(f"✅ KRX: {len(raw_data)}개 ETF 조회")

        # 2. 데이터 파싱 및 변환
        etf_list = []
        for item in raw_data:
            parsed = self.parser.parse_krx_data(item)
            etf_list.append(parsed)

        # 3. 데이터베이스 저장
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # 기존 ETF 데이터 삭제 (외래키 제약 고려)
            cursor.execute("DELETE FROM etf_details WHERE ticker IN (SELECT ticker FROM tickers WHERE asset_type = 'ETF')")
            cursor.execute("DELETE FROM tickers WHERE asset_type = 'ETF'")

            # 새 데이터 삽입
            for etf in etf_list:
                self._insert_etf_basic(cursor, etf)

            conn.commit()

        logger.info(f"✅ Phase 1 완료: {len(etf_list)}개 ETF 저장")
        return len(etf_list)

    def update_aum(self, tickers: Optional[List[str]] = None) -> int:
        """
        Phase 2: KIS API로 AUM 업데이트

        Args:
            tickers: 특정 종목만 업데이트 (None이면 전체)

        Returns:
            업데이트된 ETF 개수
        """
        if not self.kis_api:
            logger.warning("⚠️ KIS API 미설정 - Phase 2 스킵")
            return 0

        logger.info("📊 Phase 2: KIS API로 AUM 업데이트 시작")

        # 1. 업데이트 대상 조회
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            if tickers:
                placeholders = ','.join(['?'] * len(tickers))
                cursor.execute(f"SELECT ticker, listed_shares FROM etf_details WHERE ticker IN ({placeholders})", tickers)
            else:
                cursor.execute("SELECT ticker, listed_shares FROM etf_details")

            targets = cursor.fetchall()

        # 2. KIS API로 현재가 조회 및 AUM 계산
        updated_count = 0
        for ticker, listed_shares in targets:
            try:
                price_data = self.kis_api.get_price(ticker)
                current_price = int(price_data['stck_prpr'])

                # AUM = 상장주식수 × 현재가
                aum = listed_shares * current_price

                # 데이터베이스 업데이트
                with self.db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE etf_details
                        SET aum = ?, last_updated = ?
                        WHERE ticker = ?
                    """, (aum, datetime.now().isoformat(), ticker))
                    conn.commit()

                updated_count += 1

                # Rate limiting (20 req/sec)
                time.sleep(0.05)

            except Exception as e:
                logger.error(f"❌ {ticker} AUM 업데이트 실패: {e}")

        logger.info(f"✅ Phase 2 완료: {updated_count}/{len(targets)}개 ETF AUM 업데이트")
        return updated_count

    def update_tracking_error(self, tickers: Optional[List[str]] = None) -> int:
        """
        Phase 3: KIS API로 괴리율 업데이트

        Args:
            tickers: 특정 종목만 업데이트 (None이면 전체)

        Returns:
            업데이트된 ETF 개수
        """
        if not self.kis_api:
            logger.warning("⚠️ KIS API 미설정 - Phase 3 스킵")
            return 0

        logger.info("📊 Phase 3: KIS API로 괴리율 업데이트 시작")

        # Implementation details...
        # Similar pattern to update_aum()

        return updated_count

    def update_52w_high_low(self) -> int:
        """
        Phase 4: OHLCV 데이터로 52주 고저 업데이트

        Returns:
            업데이트된 ETF 개수
        """
        logger.info("📊 Phase 4: OHLCV 데이터로 52주 고저 업데이트 시작")

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # ETF 목록 조회
            cursor.execute("SELECT ticker FROM etf_details")
            tickers = [row[0] for row in cursor.fetchall()]

            updated_count = 0
            for ticker in tickers:
                # 250일 OHLCV 데이터로 52주 고저 계산
                cursor.execute("""
                    SELECT MAX(close) as high_52w, MIN(close) as low_52w
                    FROM ohlcv_data
                    WHERE ticker = ? AND date >= DATE('now', '-250 days')
                """, (ticker,))

                result = cursor.fetchone()
                if result and result[0]:
                    high_52w, low_52w = result

                    cursor.execute("""
                        UPDATE etf_details
                        SET week_52_high = ?, week_52_low = ?, last_updated = ?
                        WHERE ticker = ?
                    """, (int(high_52w), int(low_52w), datetime.now().isoformat(), ticker))

                    updated_count += 1

            conn.commit()

        logger.info(f"✅ Phase 4 완료: {updated_count}개 ETF 52주 고저 업데이트")
        return updated_count

    def load_manual_data(self, csv_path: str) -> int:
        """
        Phase 5: CSV 파일로 수동 데이터 로드

        Args:
            csv_path: CSV file path (config/etf_manual_data.csv)

        Returns:
            업데이트된 ETF 개수
        """
        logger.info(f"📊 Phase 5: CSV 파일로 수동 데이터 로드 시작: {csv_path}")

        # Implementation details...
        # Read CSV and update ter, actual_expense_ratio, etc.

        return updated_count

    def _insert_etf_basic(self, cursor, etf: Dict):
        """ETF 기본 정보를 tickers 및 etf_details 테이블에 삽입"""
        now = datetime.now().isoformat()

        # 1. tickers 테이블
        cursor.execute("""
            INSERT OR REPLACE INTO tickers
            (ticker, name, name_eng, exchange, region, currency, asset_type,
             listing_date, is_active, created_at, last_updated, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            etf['ticker'],
            etf['name'],
            etf.get('name_eng'),
            'KRX',
            'KR',
            'KRW',
            'ETF',
            etf.get('inception_date'),
            True,
            now,
            now,
            'KRX Data API'
        ))

        # 2. etf_details 테이블
        cursor.execute("""
            INSERT OR REPLACE INTO etf_details
            (ticker, issuer, inception_date, underlying_asset_class,
             tracking_index, geographic_region, fund_type,
             expense_ratio, listed_shares, leverage_ratio,
             created_at, last_updated, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            etf['ticker'],
            etf['issuer'],
            etf['inception_date'],
            etf['underlying_asset_class'],
            etf['tracking_index'],
            etf['geographic_region'],
            etf['fund_type'],
            etf['expense_ratio'],
            etf['listed_shares'],
            etf.get('leverage_ratio'),
            now,
            now,
            'KRX Data API'
        ))
```

### 4.2 Module: `etf_krx_api.py`

**Purpose**: KRX Data API wrapper

```python
"""
KRX Data API 래퍼 (ETF 전용)

Endpoint: http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd
Parameter: bld=dbms/MDC/STAT/standard/MDCSTAT04601
"""

import requests
from typing import List, Dict
from datetime import datetime


class ETFKRXDataAPI:
    """KRX 정보데이터시스템 API - ETF 데이터"""

    BASE_URL = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Referer': 'http://data.krx.co.kr/',
        })

    def get_etf_list(self) -> List[Dict]:
        """
        전체 ETF 목록 조회

        Returns:
            ETF 정보 리스트 (1,029개)
        """
        data = {
            'bld': 'dbms/MDC/STAT/standard/MDCSTAT04601',
            'locale': 'ko_KR',
            'trdDd': datetime.now().strftime("%Y%m%d"),
            'csvxls_isNo': 'false',
        }

        response = self.session.post(self.BASE_URL, data=data, timeout=10)
        response.raise_for_status()
        result = response.json()

        return result.get('output', [])
```

### 4.3 Module: `etf_kis_api.py`

**Purpose**: KIS API ETF endpoints wrapper

```python
"""
KIS API ETF 전용 엔드포인트 래퍼

Endpoints:
1. /uapi/etfetn/v1/quotations/inquire-price (현재가)
2. /uapi/etfetn/v1/quotations/inquire-component-stock-price (구성종목)
3. /uapi/etfetn/v1/quotations/nav-comparison-trend (괴리율 단기)
4. /uapi/etfetn/v1/quotations/nav-comparison-daily-trend (괴리율 장기)
"""

import requests
from typing import Dict, List


class ETFKISApi:
    """KIS API - ETF 데이터"""

    BASE_URL = "https://openapi.koreainvestment.com:9443"

    def __init__(self, app_key: str, app_secret: str, access_token: str = None):
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = access_token or self._get_access_token()

    def _get_access_token(self) -> str:
        """OAuth 2.0 접근 토큰 발급"""
        # Implementation details...
        pass

    def get_price(self, ticker: str) -> Dict:
        """
        ETF 현재가 조회 (AUM 계산용)

        TR_ID: FHPST02400000
        """
        endpoint = f"{self.BASE_URL}/uapi/etfetn/v1/quotations/inquire-price"

        headers = {
            "authorization": f"Bearer {self.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHPST02400000"
        }

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",  # ETF
            "FID_INPUT_ISCD": ticker
        }

        response = requests.get(endpoint, headers=headers, params=params, timeout=10)
        response.raise_for_status()

        return response.json()['output']

    def get_holdings(self, ticker: str) -> List[Dict]:
        """
        ETF 구성종목 조회

        TR_ID: FHKST121600C0
        """
        # Implementation details...
        pass

    def get_nav_trend(self, ticker: str, period: str = 'short') -> List[Dict]:
        """
        NAV 비교추이 조회 (괴리율 계산용)

        Args:
            ticker: ETF 종목코드
            period: 'short' (20d, 60d) or 'long' (120d, 250d)

        TR_ID: FHPST02440000 (short) or FHPST02440200 (long)
        """
        # Implementation details...
        pass
```

### 4.4 Module: `etf_parser.py`

**Purpose**: Data parsing and transformation utilities

```python
"""
ETF 데이터 파싱 유틸리티

주요 기능:
1. KRX Data API 응답 파싱
2. KIS API 응답 파싱
3. 레버리지 배율 파싱 (IDX_CALC_INST_NM2)
4. 섹터/테마 추출 (종목명 또는 기초지수명)
5. 환헤지 여부 추출 (기초지수명)
"""

import re
from typing import Dict, Optional


class ETFDataParser:
    """ETF 데이터 파싱 및 변환"""

    @staticmethod
    def parse_krx_data(item: Dict) -> Dict:
        """
        KRX Data API 응답을 etf_details 스키마로 변환

        Args:
            item: KRX API output 항목

        Returns:
            etf_details 테이블 형식 딕셔너리
        """
        return {
            'ticker': item['ISU_SRT_CD'],
            'name': item['ISU_ABBRV'],
            'name_full': item['ISU_NM'],
            'issuer': item['COM_ABBRV'],
            'tracking_index': item['ETF_OBJ_IDX_NM'],
            'geographic_region': item['IDX_MKT_CLSS_NM'],
            'underlying_asset_class': item['IDX_ASST_CLSS_NM'],
            'expense_ratio': float(item['ETF_TOT_FEE']),
            'listed_shares': int(item['LIST_SHRS'].replace(',', '')),
            'inception_date': ETFDataParser._parse_date(item['LIST_DD']),
            'fund_type': item['ETF_REPLICA_METHD_TP_CD'],
            'leverage_ratio': ETFDataParser._parse_leverage(item['IDX_CALC_INST_NM2']),
        }

    @staticmethod
    def _parse_date(date_str: str) -> str:
        """
        날짜 포맷 변환: '2024/12/03' → '2024-12-03'
        """
        return date_str.replace('/', '-') if date_str else None

    @staticmethod
    def _parse_leverage(calc_inst: str) -> Optional[str]:
        """
        레버리지 배율 파싱

        Examples:
            '일반' → None
            '2X 레버리지' → '2X'
            '1X 인버스' → '-1X'
            '2X 인버스' → '-2X'
        """
        if not calc_inst or calc_inst == '일반':
            return None

        # 레버리지 패턴 추출
        if '레버리지' in calc_inst:
            match = re.search(r'(\d+)X', calc_inst)
            if match:
                return f"{match.group(1)}X"

        # 인버스 패턴 추출
        if '인버스' in calc_inst:
            match = re.search(r'(\d+)X', calc_inst)
            if match:
                return f"-{match.group(1)}X"
            else:
                return "-1X"  # '인버스' (배수 명시 없음)

        return None

    @staticmethod
    def parse_sector_theme(name: str, tracking_index: str) -> Optional[str]:
        """
        섹터/테마 추출 (휴리스틱)

        Examples:
            'RISE 2차전지액티브' → '2차전지'
            'ACE 글로벌빅파마' → '헬스케어'
            'FnGuide 수소 경제 테마 지수' → '수소경제'
        """
        # 키워드 매칭
        sector_keywords = {
            '반도체': '반도체',
            'AI': 'AI',
            '2차전지': '2차전지',
            '배터리': '2차전지',
            '바이오': '바이오',
            '헬스케어': '헬스케어',
            '빅파마': '헬스케어',
            '금융': '금융',
            '은행': '금융',
            '게임': '게임',
            'IT': 'IT',
            '플랫폼': '플랫폼',
            '수소': '수소경제',
            '5G': '5G',
        }

        for keyword, theme in sector_keywords.items():
            if keyword in name or keyword in tracking_index:
                return theme

        return None

    @staticmethod
    def parse_currency_hedged(tracking_index: str) -> Optional[bool]:
        """
        환헤지 여부 추출 (휴리스틱)

        Examples:
            'MSCI Korea 지수' → False (국내)
            'S&P 500 환헤지 지수' → True
            'NASDAQ 100 지수' → False
        """
        if '환헤지' in tracking_index:
            return True

        # 국내 지수는 환헤지 불필요
        domestic_keywords = ['코스피', 'KOSPI', 'KOSDAQ', 'KRX', 'FnGuide', 'iSelect']
        if any(keyword in tracking_index for keyword in domestic_keywords):
            return False

        # 해외 지수는 대부분 환노출 (명시적 환헤지 아니면)
        return None  # Unknown
```

---

## 5. Execution Schedule

### 5.1 Cron Job Configuration

```bash
# /etc/crontab 또는 crontab -e

# Phase 1: 기본 ETF 목록 수집 (매일 09:00 KST, 장 시작 전)
0 9 * * * cd /Users/13ruce/spock && python3 -m modules.etf_collector --phase 1

# Phase 2: AUM 업데이트 (매일 16:00 KST, 장 마감 후)
0 16 * * * cd /Users/13ruce/spock && python3 -m modules.etf_collector --phase 2

# Phase 3: 괴리율 업데이트 (매주 일요일 21:00 KST)
0 21 * * 0 cd /Users/13ruce/spock && python3 -m modules.etf_collector --phase 3

# Phase 4: 52주 고저 업데이트 (매일 17:00 KST, OHLCV 수집 후)
0 17 * * * cd /Users/13ruce/spock && python3 -m modules.etf_collector --phase 4

# Phase 5: 수동 데이터 로드 (분기별, 수동 실행)
# python3 -m modules.etf_collector --phase 5 --csv config/etf_manual_data.csv
```

### 5.2 Execution Timeline (Daily)

```
08:30 - 09:00  Pre-market preparation
  └─ 09:00     Phase 1: KRX Data API ETF 목록 수집 (~5초)

09:00 - 15:30  Market hours (no ETF collection)

15:30 - 16:00  Post-market processing
  └─ 16:00     Phase 2: KIS API AUM 업데이트 (~51초)
  └─ 17:00     Phase 4: 52주 고저 업데이트 (~10초)

Sunday 21:00   Weekly update
  └─ 21:00     Phase 3: KIS API 괴리율 업데이트 (~102초)
```

---

## 6. Implementation Plan

### 6.1 Phase Timeline

```
Week 1 (P0): Foundation
├─ Day 1-2: Module structure setup
│  ├─ Create etf_collector.py
│  ├─ Create etf_krx_api.py
│  ├─ Create etf_parser.py
│  └─ Unit tests
├─ Day 3-4: KRX Data API integration
│  ├─ Implement ETFKRXDataAPI
│  ├─ Implement ETFDataParser.parse_krx_data()
│  └─ Integration test with real API
└─ Day 5: Database integration
   ├─ Update scanner.py patterns
   ├─ Test etf_details insertion
   └─ Verify 1,029 ETFs collected

Week 2 (P1): KIS API Integration
├─ Day 1-2: KIS API authentication
│  ├─ Create etf_kis_api.py
│  ├─ Implement OAuth 2.0 flow
│  └─ Test with sandbox
├─ Day 3-4: AUM calculation
│  ├─ Implement get_price()
│  ├─ Implement update_aum()
│  └─ Rate limiting test (20 req/sec)
└─ Day 5: End-to-end test
   └─ Run Phase 1 + Phase 2 pipeline

Week 3 (P2 - Optional): Advanced Features
├─ Day 1-2: Tracking error
│  ├─ Implement get_nav_trend()
│  ├─ Implement update_tracking_error()
│  └─ Test with sample ETFs
├─ Day 3: 52-week high/low
│  ├─ Implement update_52w_high_low()
│  └─ Test with OHLCV data
└─ Day 4-5: Sector parsing & validation
   ├─ Implement parse_sector_theme()
   ├─ Implement parse_currency_hedged()
   └─ Full system integration test

Week 4 (P3 - Optional): Manual Data & Production
├─ Day 1-2: CSV management
│  ├─ Create config/etf_manual_data.csv template
│  ├─ Implement load_manual_data()
│  └─ Test with sample data
├─ Day 3: Cron job setup
│  └─ Configure execution schedule
└─ Day 4-5: Production deployment
   ├─ Deploy to EC2
   ├─ Monitor first 24-hour cycle
   └─ Documentation finalization
```

### 6.2 Task Breakdown (P0 + P1)

**Priority 0 (Must Have) - 5 days**

1. **[Day 1] Module Structure Setup** (4 hours)
   - Create `modules/etf_collector.py` skeleton
   - Create `modules/etf_krx_api.py` skeleton
   - Create `modules/etf_parser.py` skeleton
   - Setup logging configuration

2. **[Day 2] KRX Data API Integration** (8 hours)
   - Implement `ETFKRXDataAPI.get_etf_list()`
   - Implement `ETFDataParser.parse_krx_data()`
   - Implement `ETFDataParser._parse_leverage()`
   - Unit tests for parser

3. **[Day 3] Database Integration** (8 hours)
   - Implement `ETFCollector.collect_basic_info()`
   - Implement `ETFCollector._insert_etf_basic()`
   - Test with real KRX Data API
   - Verify 1,029 ETFs in database

4. **[Day 4] KIS API Setup** (8 hours)
   - Create `modules/etf_kis_api.py`
   - Implement OAuth 2.0 authentication
   - Implement `ETFKISApi.get_price()`
   - Test with sandbox account

5. **[Day 5] AUM Calculation** (8 hours)
   - Implement `ETFCollector.update_aum()`
   - Test rate limiting (20 req/sec)
   - End-to-end test: Phase 1 → Phase 2
   - Performance validation (~51 seconds)

**Priority 1 (Should Have) - 3 days**

6. **[Day 6-7] Tracking Error** (16 hours)
   - Implement `ETFKISApi.get_nav_trend()`
   - Implement `ETFCollector.update_tracking_error()`
   - Test with short (20d, 60d) and long (120d, 250d) periods
   - Validation with sample ETFs

7. **[Day 8] 52-Week High/Low** (8 hours)
   - Implement `ETFCollector.update_52w_high_low()`
   - Integration with OHLCV data
   - Test with existing OHLCV collection

**Priority 2 (Nice to Have) - 2 days**

8. **[Day 9] Sector & Theme Parsing** (8 hours)
   - Implement `ETFDataParser.parse_sector_theme()`
   - Implement `ETFDataParser.parse_currency_hedged()`
   - Heuristic rules development

9. **[Day 10] Manual Data Management** (8 hours)
   - Create `config/etf_manual_data.csv` template
   - Implement `ETFCollector.load_manual_data()`
   - CSV validation logic

### 6.3 Testing Strategy

**Unit Tests**:
```python
# tests/test_etf_parser.py
def test_parse_krx_data():
    sample = {
        'ISU_SRT_CD': '152100',
        'ISU_ABBRV': 'KODEX 200',
        'COM_ABBRV': '삼성자산운용',
        # ...
    }
    result = ETFDataParser.parse_krx_data(sample)
    assert result['ticker'] == '152100'
    assert result['issuer'] == '삼성자산운용'

def test_parse_leverage():
    assert ETFDataParser._parse_leverage('일반') is None
    assert ETFDataParser._parse_leverage('2X 레버리지') == '2X'
    assert ETFDataParser._parse_leverage('1X 인버스') == '-1X'
```

**Integration Tests**:
```python
# tests/test_etf_collector.py
def test_collect_basic_info(db_path):
    collector = ETFCollector(db_path)
    count = collector.collect_basic_info()

    assert count > 1000  # At least 1,000 ETFs

    # Verify database
    with collector.db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM etf_details")
        assert cursor.fetchone()[0] == count

def test_update_aum(db_path, kis_config):
    collector = ETFCollector(db_path, kis_config)

    # Test with 5 sample ETFs
    sample_tickers = ['152100', '069500', '102110', '114800', '219390']
    updated = collector.update_aum(sample_tickers)

    assert updated == len(sample_tickers)
```

### 6.4 Deployment Checklist

**Pre-Production**:
- [ ] All P0 tests passing (100% coverage)
- [ ] KIS API authentication working
- [ ] Database schema verified
- [ ] Rate limiting tested (20 req/sec)
- [ ] Error handling comprehensive
- [ ] Logging properly configured

**Production**:
- [ ] Cron jobs configured
- [ ] Database backup enabled
- [ ] Monitoring alerts setup
- [ ] Documentation complete
- [ ] Rollback plan prepared
- [ ] First 24-hour cycle successful

---

## 7. Error Handling & Recovery

### 7.1 Error Types & Recovery Strategies

| Error Type | Recovery Strategy | Priority |
|------------|-------------------|----------|
| **KRX Data API Timeout** | Retry with exponential backoff (3 attempts) | P0 |
| **KIS API Rate Limit** | Sleep 60s, resume from last ticker | P0 |
| **KIS API Auth Failure** | Regenerate access token, retry | P0 |
| **Database Lock** | Retry with 1s delay (5 attempts) | P0 |
| **Missing OHLCV Data** | Skip 52W update for that ticker | P1 |
| **CSV Parse Error** | Log error, skip row, continue | P2 |

### 7.2 Circuit Breaker Pattern

```python
class ETFCollector:
    def __init__(self, ...):
        self.failure_count = 0
        self.failure_threshold = 10  # Circuit opens after 10 failures
        self.circuit_open = False

    def update_aum(self, tickers):
        if self.circuit_open:
            logger.error("🚨 Circuit breaker open - skipping AUM update")
            return 0

        for ticker in tickers:
            try:
                # ... update logic ...
                self.failure_count = 0  # Reset on success

            except Exception as e:
                self.failure_count += 1

                if self.failure_count >= self.failure_threshold:
                    self.circuit_open = True
                    logger.error("🚨 Circuit breaker triggered")
                    break
```

### 7.3 Monitoring & Alerts

**Key Metrics**:
- ETF collection success rate (>95%)
- AUM update latency (<60 seconds)
- KIS API error rate (<5%)
- Database write failures (<1%)

**Alert Conditions**:
- Circuit breaker triggered
- >50 consecutive failures
- Database disk space <10%
- Cron job missed execution

---

## 8. Performance Optimization

### 8.1 Optimization Strategies

**Phase 1 (KRX Data API)**:
- Single API call for all 1,029 ETFs (~5 seconds)
- No optimization needed

**Phase 2 (KIS API - AUM)**:
- Rate limit: 20 req/sec → 51 seconds total
- Batch processing with connection pooling
- Retry only failed tickers (not all)

**Phase 3 (KIS API - Tracking Error)**:
- 2 API calls per ticker → ~102 seconds
- Run weekly (not daily) to reduce load
- Parallel requests (if KIS allows)

**Phase 4 (OHLCV)**:
- Single SQL query per ticker
- Use indexes on (ticker, date)
- ~10 seconds for 1,029 ETFs

### 8.2 Caching Strategy

**SQLite Cache** (24-hour validity):
- Phase 1 results cached for 24 hours
- Avoid redundant KRX API calls
- Cache invalidation on market holidays

**Token Caching**:
- KIS access token valid for 24 hours
- Store in memory, refresh before expiry
- Avoid repeated OAuth calls

---

## 9. Next Steps

### 9.1 Immediate Actions (Week 1)

1. **Create module structure**
   ```bash
   mkdir -p ~/spock/modules
   touch ~/spock/modules/etf_collector.py
   touch ~/spock/modules/etf_krx_api.py
   touch ~/spock/modules/etf_parser.py
   touch ~/spock/modules/etf_kis_api.py
   ```

2. **Setup testing framework**
   ```bash
   mkdir -p ~/spock/tests
   touch ~/spock/tests/test_etf_collector.py
   touch ~/spock/tests/test_etf_parser.py
   ```

3. **Implement Phase 1 (KRX Data API)**
   - Priority: P0
   - Deadline: Day 3
   - Deliverable: 1,029 ETFs in database

### 9.2 Success Criteria

**Week 1 (P0)**:
- ✅ KRX Data API integration complete
- ✅ 1,029 ETFs collected and stored
- ✅ All P0 unit tests passing

**Week 2 (P1)**:
- ✅ KIS API authentication working
- ✅ AUM calculation accurate
- ✅ Rate limiting compliant (20 req/sec)

**Week 3 (P2 - Optional)**:
- ✅ Tracking error collection working
- ✅ 52-week high/low calculation accurate

**Week 4 (Production)**:
- ✅ Cron jobs running reliably
- ✅ Error handling comprehensive
- ✅ Monitoring alerts configured

---

## 10. Appendix

### 10.1 Reference Documents

- **CLAUDE.md**: Project overview and tech stack
- **init_db.py**: Database schema (etf_details table)
- **modules/scanner.py**: Stock scanner patterns (100% reusable)
- **ETF Data Collection Research** (2025-10-01): API analysis and field comparison

### 10.2 External Resources

- **KRX Data API Documentation**: http://data.krx.co.kr/
- **KIS API Documentation**: `한국투자증권_오픈API_전체문서_20250920_030000.xlsx`
- **ETFCheck.co.kr**: Manual data reference (do not crawl)

### 10.3 Contact & Support

- **Project Owner**: Spock Trading System
- **Database**: SQLite 3 (`data/spock_local.db`)
- **Deployment**: Local (macOS) or AWS EC2 (Ubuntu 20.04+)

---

**Document Version**: 1.0
**Last Updated**: 2025-10-01
**Status**: Design Complete, Ready for Implementation
