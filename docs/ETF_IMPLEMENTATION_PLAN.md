# ETF Data Collection - Implementation Plan

**Date**: 2025-10-01
**Estimated Duration**: 10 days (P0+P1) to 15 days (P0+P1+P2)
**Status**: Ready to Start

---

## Overview

이 문서는 하이브리드 ETF 데이터 수집 시스템의 구체적인 구현 계획을 제공합니다.

**참조 문서**:
- [ETF_DATA_COLLECTION_DESIGN.md](ETF_DATA_COLLECTION_DESIGN.md) - 시스템 아키텍처 및 설계
- [init_db.py](../init_db.py) - 데이터베이스 스키마
- [modules/scanner.py](../modules/scanner.py) - 재사용 가능한 패턴

---

## Phase-Based Implementation

### Phase 0: Setup (Day 0 - 0.5 days)

**Goal**: 프로젝트 구조 준비 및 개발 환경 설정

**Tasks**:

1. **Create module structure**
   ```bash
   cd ~/spock
   mkdir -p modules tests config docs
   touch modules/etf_collector.py
   touch modules/etf_krx_api.py
   touch modules/etf_parser.py
   touch modules/etf_kis_api.py
   touch tests/test_etf_collector.py
   touch tests/test_etf_parser.py
   touch config/etf_manual_data.csv
   ```

2. **Setup logging configuration**
   ```python
   # modules/etf_collector.py
   import logging

   logging.basicConfig(
       level=logging.INFO,
       format='%(asctime)s [%(levelname)s] %(message)s',
       handlers=[
           logging.FileHandler('log/etf_collection.log'),
           logging.StreamHandler()
       ]
   )
   logger = logging.getLogger(__name__)
   ```

3. **Verify database schema**
   ```bash
   python3 -c "import sqlite3; conn = sqlite3.connect('data/spock_local.db'); print(conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\" AND name IN (\"tickers\", \"etf_details\")').fetchall())"
   ```

**Deliverables**:
- ✅ Directory structure created
- ✅ Logging configured
- ✅ Database schema verified

---

### Phase 1: KRX Data API Integration (Day 1-3 - 3 days)

**Goal**: KRX Data API로 기본 ETF 목록 수집 (10 fields, 1,029 ETFs)

#### Day 1: KRX API Wrapper (8 hours)

**Tasks**:

1. **Implement `etf_krx_api.py`**
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
       BASE_URL = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"

       def __init__(self):
           self.session = requests.Session()
           self.session.headers.update({
               'User-Agent': 'Mozilla/5.0',
               'Accept': 'application/json',
               'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
               'Referer': 'http://data.krx.co.kr/',
           })

       def get_etf_list(self) -> List[Dict]:
           """전체 ETF 목록 조회 (1,029개)"""
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

2. **Test KRX API connection**
   ```bash
   python3 << EOF
   from modules.etf_krx_api import ETFKRXDataAPI

   api = ETFKRXDataAPI()
   etfs = api.get_etf_list()
   print(f"✅ {len(etfs)} ETFs collected")
   print(f"Sample: {etfs[0]}")
   EOF
   ```

**Deliverables**:
- ✅ `etf_krx_api.py` implemented
- ✅ Connection test passing
- ✅ 1,029 ETFs retrieved

---

#### Day 2: Data Parser (8 hours)

**Tasks**:

1. **Implement `etf_parser.py`**
   ```python
   """
   ETF 데이터 파싱 유틸리티
   """

   import re
   from typing import Dict, Optional

   class ETFDataParser:
       @staticmethod
       def parse_krx_data(item: Dict) -> Dict:
           """KRX API 응답을 etf_details 스키마로 변환"""
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
           """날짜 포맷 변환: '2024/12/03' → '2024-12-03'"""
           return date_str.replace('/', '-') if date_str else None

       @staticmethod
       def _parse_leverage(calc_inst: str) -> Optional[str]:
           """레버리지 배율 파싱"""
           if not calc_inst or calc_inst == '일반':
               return None

           if '레버리지' in calc_inst:
               match = re.search(r'(\d+)X', calc_inst)
               if match:
                   return f"{match.group(1)}X"

           if '인버스' in calc_inst:
               match = re.search(r'(\d+)X', calc_inst)
               if match:
                   return f"-{match.group(1)}X"
               else:
                   return "-1X"

           return None
   ```

2. **Unit tests for parser**
   ```python
   # tests/test_etf_parser.py
   import pytest
   from modules.etf_parser import ETFDataParser

   def test_parse_krx_data():
       sample = {
           'ISU_SRT_CD': '152100',
           'ISU_ABBRV': 'KODEX 200',
           'ISU_NM': 'KODEX 200 증권상장지수투자신탁(주식)',
           'COM_ABBRV': '삼성자산운용',
           'ETF_OBJ_IDX_NM': '코스피 200',
           'IDX_MKT_CLSS_NM': '국내',
           'IDX_ASST_CLSS_NM': '주식',
           'ETF_TOT_FEE': '0.015000',
           'LIST_SHRS': '100,000,000',
           'LIST_DD': '2002/10/14',
           'ETF_REPLICA_METHD_TP_CD': '실물(패시브)',
           'IDX_CALC_INST_NM2': '일반',
       }

       result = ETFDataParser.parse_krx_data(sample)

       assert result['ticker'] == '152100'
       assert result['name'] == 'KODEX 200'
       assert result['issuer'] == '삼성자산운용'
       assert result['expense_ratio'] == 0.015
       assert result['listed_shares'] == 100000000
       assert result['inception_date'] == '2002-10-14'
       assert result['leverage_ratio'] is None

   def test_parse_leverage():
       assert ETFDataParser._parse_leverage('일반') is None
       assert ETFDataParser._parse_leverage('2X 레버리지') == '2X'
       assert ETFDataParser._parse_leverage('1X 인버스') == '-1X'
       assert ETFDataParser._parse_leverage('2X 인버스') == '-2X'
       assert ETFDataParser._parse_leverage('인버스') == '-1X'

   def test_parse_date():
       assert ETFDataParser._parse_date('2024/12/03') == '2024-12-03'
       assert ETFDataParser._parse_date(None) is None
   ```

3. **Run unit tests**
   ```bash
   pytest tests/test_etf_parser.py -v
   ```

**Deliverables**:
- ✅ `etf_parser.py` implemented
- ✅ Unit tests passing (100% coverage)
- ✅ Parser handles all KRX fields

---

#### Day 3: Database Integration (8 hours)

**Tasks**:

1. **Implement `etf_collector.py` (Phase 1 only)**
   ```python
   """
   ETF 데이터 수집 통합 모듈
   """

   import logging
   from typing import List, Dict, Optional
   from datetime import datetime

   from modules.etf_krx_api import ETFKRXDataAPI
   from modules.etf_parser import ETFDataParser
   from modules.db_manager_sqlite import SQLiteDatabaseManager

   logger = logging.getLogger(__name__)

   class ETFCollector:
       def __init__(self, db_path: str):
           self.db_manager = SQLiteDatabaseManager(db_path)
           self.krx_api = ETFKRXDataAPI()
           self.parser = ETFDataParser()

       def collect_basic_info(self) -> int:
           """Phase 1: KRX Data API로 기본 ETF 정보 수집"""
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

2. **Integration test**
   ```python
   # tests/test_etf_collector.py
   import pytest
   from modules.etf_collector import ETFCollector

   def test_collect_basic_info():
       db_path = 'data/spock_local.db'
       collector = ETFCollector(db_path)

       count = collector.collect_basic_info()

       assert count > 1000  # At least 1,000 ETFs

       # Verify database
       with collector.db_manager.get_connection() as conn:
           cursor = conn.cursor()

           # Check tickers table
           cursor.execute("SELECT COUNT(*) FROM tickers WHERE asset_type = 'ETF'")
           assert cursor.fetchone()[0] == count

           # Check etf_details table
           cursor.execute("SELECT COUNT(*) FROM etf_details")
           assert cursor.fetchone()[0] == count

           # Verify sample data
           cursor.execute("""
               SELECT t.ticker, t.name, e.issuer, e.expense_ratio
               FROM tickers t
               JOIN etf_details e ON t.ticker = e.ticker
               WHERE t.ticker = '152100'
           """)
           result = cursor.fetchone()
           assert result is not None
           assert result[1] == 'KODEX 200'
   ```

3. **Run full integration test**
   ```bash
   pytest tests/test_etf_collector.py -v

   # Manual verification
   python3 << EOF
   from modules.etf_collector import ETFCollector

   collector = ETFCollector('data/spock_local.db')
   count = collector.collect_basic_info()
   print(f"✅ {count} ETFs collected and saved")
   EOF

   # Check database
   python3 -c "
   import sqlite3
   conn = sqlite3.connect('data/spock_local.db')
   cursor = conn.cursor()
   cursor.execute('SELECT COUNT(*) FROM etf_details')
   print(f'ETF count: {cursor.fetchone()[0]}')
   cursor.execute('SELECT ticker, name, issuer, expense_ratio FROM tickers t JOIN etf_details e ON t.ticker = e.ticker LIMIT 5')
   print('Sample ETFs:')
   for row in cursor.fetchall():
       print(f'  {row}')
   "
   ```

**Deliverables**:
- ✅ `etf_collector.py` Phase 1 implemented
- ✅ Integration tests passing
- ✅ 1,029 ETFs in database
- ✅ All 10 fields populated

**Milestone**: Phase 1 Complete ✅

---

### Phase 2: KIS API Integration (Day 4-5 - 2 days)

**Goal**: KIS API로 AUM 계산 (1 field)

#### Day 4: KIS API Authentication (8 hours)

**Tasks**:

1. **Setup KIS API credentials**
   ```bash
   # .env file
   KIS_APP_KEY=your_app_key
   KIS_APP_SECRET=your_app_secret
   KIS_ACCOUNT=your_account_number
   ```

2. **Implement `etf_kis_api.py`**
   ```python
   """
   KIS API ETF 전용 엔드포인트 래퍼
   """

   import os
   import requests
   from typing import Dict
   from dotenv import load_dotenv

   load_dotenv()

   class ETFKISApi:
       BASE_URL = "https://openapi.koreainvestment.com:9443"

       def __init__(self, app_key: str = None, app_secret: str = None, access_token: str = None):
           self.app_key = app_key or os.getenv('KIS_APP_KEY')
           self.app_secret = app_secret or os.getenv('KIS_APP_SECRET')
           self.access_token = access_token or self._get_access_token()

       def _get_access_token(self) -> str:
           """OAuth 2.0 접근 토큰 발급"""
           endpoint = f"{self.BASE_URL}/oauth2/tokenP"

           data = {
               "grant_type": "client_credentials",
               "appkey": self.app_key,
               "appsecret": self.app_secret
           }

           response = requests.post(endpoint, json=data, timeout=10)
           response.raise_for_status()

           result = response.json()
           return result['access_token']

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
               "tr_id": "FHPST02400000",
               "custtype": "P"  # 개인
           }

           params = {
               "FID_COND_MRKT_DIV_CODE": "J",  # ETF
               "FID_INPUT_ISCD": ticker
           }

           response = requests.get(endpoint, headers=headers, params=params, timeout=10)
           response.raise_for_status()

           return response.json()['output']
   ```

3. **Test KIS API authentication**
   ```bash
   python3 << EOF
   from modules.etf_kis_api import ETFKISApi

   api = ETFKISApi()
   print(f"✅ Access token: {api.access_token[:20]}...")

   # Test get_price with KODEX 200
   price_data = api.get_price('152100')
   print(f"✅ KODEX 200 price: {price_data['stck_prpr']}")
   EOF
   ```

**Deliverables**:
- ✅ `etf_kis_api.py` implemented
- ✅ OAuth 2.0 authentication working
- ✅ get_price() tested

---

#### Day 5: AUM Calculation (8 hours)

**Tasks**:

1. **Implement AUM update in `etf_collector.py`**
   ```python
   import time
   from modules.etf_kis_api import ETFKISApi

   class ETFCollector:
       def __init__(self, db_path: str, kis_config: Optional[Dict] = None):
           self.db_manager = SQLiteDatabaseManager(db_path)
           self.krx_api = ETFKRXDataAPI()
           self.kis_api = ETFKISApi(**kis_config) if kis_config else None
           self.parser = ETFDataParser()

       def update_aum(self, tickers: Optional[List[str]] = None) -> int:
           """Phase 2: KIS API로 AUM 업데이트"""
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
   ```

2. **Test AUM calculation**
   ```python
   # tests/test_etf_collector.py
   def test_update_aum():
       db_path = 'data/spock_local.db'
       kis_config = {
           'app_key': os.getenv('KIS_APP_KEY'),
           'app_secret': os.getenv('KIS_APP_SECRET')
       }

       collector = ETFCollector(db_path, kis_config)

       # Test with 5 sample ETFs
       sample_tickers = ['152100', '069500', '102110', '114800', '219390']
       updated = collector.update_aum(sample_tickers)

       assert updated == len(sample_tickers)

       # Verify AUM values
       with collector.db_manager.get_connection() as conn:
           cursor = conn.cursor()
           cursor.execute("""
               SELECT ticker, aum
               FROM etf_details
               WHERE ticker IN ('152100', '069500')
           """)
           results = cursor.fetchall()

           for ticker, aum in results:
               assert aum > 0
               print(f"✅ {ticker} AUM: {aum:,} KRW")
   ```

3. **Run end-to-end test**
   ```bash
   pytest tests/test_etf_collector.py::test_update_aum -v

   # Manual test with all ETFs (takes ~51 seconds)
   python3 << EOF
   import time
   from modules.etf_collector import ETFCollector

   start = time.time()

   collector = ETFCollector('data/spock_local.db', {
       'app_key': os.getenv('KIS_APP_KEY'),
       'app_secret': os.getenv('KIS_APP_SECRET')
   })

   updated = collector.update_aum()

   elapsed = time.time() - start
   print(f"✅ {updated} ETFs updated in {elapsed:.1f} seconds")
   print(f"Rate: {updated/elapsed:.1f} req/sec")
   EOF
   ```

**Deliverables**:
- ✅ AUM calculation implemented
- ✅ Rate limiting working (20 req/sec)
- ✅ Integration test passing
- ✅ Performance validated (~51 seconds)

**Milestone**: Phase 2 Complete ✅

---

### Phase 3: Advanced Features (Optional - Day 6-8 - 3 days)

**Goal**: 괴리율, 구성종목수, 52주 고저 수집 (8 fields)

#### Day 6-7: Tracking Error (16 hours)

**Tasks**:

1. **Implement NAV comparison endpoints**
   ```python
   # modules/etf_kis_api.py
   def get_nav_trend(self, ticker: str, period: str = 'short') -> List[Dict]:
       """
       NAV 비교추이 조회 (괴리율 계산용)

       Args:
           ticker: ETF 종목코드
           period: 'short' (20d, 60d) or 'long' (120d, 250d)
       """
       if period == 'short':
           endpoint = f"{self.BASE_URL}/uapi/etfetn/v1/quotations/nav-comparison-trend"
           tr_id = "FHPST02440000"
       else:
           endpoint = f"{self.BASE_URL}/uapi/etfetn/v1/quotations/nav-comparison-daily-trend"
           tr_id = "FHPST02440200"

       headers = {
           "authorization": f"Bearer {self.access_token}",
           "appkey": self.app_key,
           "appsecret": self.app_secret,
           "tr_id": tr_id,
           "custtype": "P"
       }

       params = {
           "FID_COND_MRKT_DIV_CODE": "J",
           "FID_INPUT_ISCD": ticker
       }

       response = requests.get(endpoint, headers=headers, params=params, timeout=10)
       response.raise_for_status()

       return response.json()['output']

   def get_holdings(self, ticker: str) -> List[Dict]:
       """ETF 구성종목 조회"""
       endpoint = f"{self.BASE_URL}/uapi/etfetn/v1/quotations/inquire-component-stock-price"

       headers = {
           "authorization": f"Bearer {self.access_token}",
           "appkey": self.app_key,
           "appsecret": self.app_secret,
           "tr_id": "FHKST121600C0",
           "custtype": "P"
       }

       params = {
           "FID_COND_MRKT_DIV_CODE": "J",
           "FID_INPUT_ISCD": ticker
       }

       response = requests.get(endpoint, headers=headers, params=params, timeout=10)
       response.raise_for_status()

       return response.json()['output']
   ```

2. **Implement tracking error calculation**
   ```python
   # modules/etf_collector.py
   def update_tracking_error(self, tickers: Optional[List[str]] = None) -> int:
       """Phase 3: KIS API로 괴리율 업데이트"""
       if not self.kis_api:
           logger.warning("⚠️ KIS API 미설정 - Phase 3 스킵")
           return 0

       logger.info("📊 Phase 3: KIS API로 괴리율 업데이트 시작")

       # 업데이트 대상 조회
       with self.db_manager.get_connection() as conn:
           cursor = conn.cursor()

           if tickers:
               placeholders = ','.join(['?'] * len(tickers))
               cursor.execute(f"SELECT ticker FROM etf_details WHERE ticker IN ({placeholders})", tickers)
           else:
               cursor.execute("SELECT ticker FROM etf_details")

           targets = [row[0] for row in cursor.fetchall()]

       updated_count = 0
       for ticker in targets:
           try:
               # Short-term tracking error (20d, 60d)
               short_data = self.kis_api.get_nav_trend(ticker, 'short')
               te_20d = self._calculate_tracking_error(short_data[:20])
               te_60d = self._calculate_tracking_error(short_data[:60])

               # Long-term tracking error (120d, 250d)
               long_data = self.kis_api.get_nav_trend(ticker, 'long')
               te_120d = self._calculate_tracking_error(long_data[:120])
               te_250d = self._calculate_tracking_error(long_data)

               # Constituent count
               holdings = self.kis_api.get_holdings(ticker)
               asset_count = len(holdings)

               # Update database
               with self.db_manager.get_connection() as conn:
                   cursor = conn.cursor()
                   cursor.execute("""
                       UPDATE etf_details
                       SET tracking_error_20d = ?,
                           tracking_error_60d = ?,
                           tracking_error_120d = ?,
                           tracking_error_250d = ?,
                           underlying_asset_count = ?,
                           last_updated = ?
                       WHERE ticker = ?
                   """, (te_20d, te_60d, te_120d, te_250d, asset_count,
                         datetime.now().isoformat(), ticker))
                   conn.commit()

               updated_count += 1

               # Rate limiting (20 req/sec, 3 API calls per ticker)
               time.sleep(0.15)

           except Exception as e:
               logger.error(f"❌ {ticker} 괴리율 업데이트 실패: {e}")

       logger.info(f"✅ Phase 3 완료: {updated_count}/{len(targets)}개 ETF 업데이트")
       return updated_count

   def _calculate_tracking_error(self, nav_data: List[Dict]) -> float:
       """괴리율 계산: ((price - nav) / nav) × 100"""
       if not nav_data:
           return None

       errors = []
       for item in nav_data:
           nav = float(item.get('nav', 0))
           price = float(item.get('stck_prpr', 0))

           if nav > 0:
               error = ((price - nav) / nav) * 100
               errors.append(error)

       return sum(errors) / len(errors) if errors else None
   ```

**Deliverables**:
- ✅ NAV comparison implemented
- ✅ Tracking error calculation working
- ✅ Constituent count collection working

---

#### Day 8: 52-Week High/Low (8 hours)

**Tasks**:

1. **Implement 52W high/low calculation**
   ```python
   # modules/etf_collector.py
   def update_52w_high_low(self) -> int:
       """Phase 4: OHLCV 데이터로 52주 고저 업데이트"""
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
   ```

**Deliverables**:
- ✅ 52W high/low calculation implemented
- ✅ Integration with OHLCV data working

**Milestone**: Phase 3 Complete ✅

---

### Phase 4: Production Deployment (Day 9-10 - 2 days)

**Goal**: Cron job 설정 및 운영 환경 배포

#### Day 9: Cron Job Setup (8 hours)

**Tasks**:

1. **Create execution script**
   ```bash
   # scripts/run_etf_collection.sh
   #!/bin/bash

   cd /Users/13ruce/spock

   # Phase 1: 기본 ETF 목록 수집
   if [ "$1" == "phase1" ]; then
       python3 -c "
   from modules.etf_collector import ETFCollector
   collector = ETFCollector('data/spock_local.db')
   count = collector.collect_basic_info()
   print(f'✅ Phase 1: {count} ETFs collected')
   "
   fi

   # Phase 2: AUM 업데이트
   if [ "$1" == "phase2" ]; then
       python3 -c "
   from modules.etf_collector import ETFCollector
   import os
   collector = ETFCollector('data/spock_local.db', {
       'app_key': os.getenv('KIS_APP_KEY'),
       'app_secret': os.getenv('KIS_APP_SECRET')
   })
   count = collector.update_aum()
   print(f'✅ Phase 2: {count} ETFs AUM updated')
   "
   fi

   # Phase 3: 괴리율 업데이트
   if [ "$1" == "phase3" ]; then
       python3 -c "
   from modules.etf_collector import ETFCollector
   import os
   collector = ETFCollector('data/spock_local.db', {
       'app_key': os.getenv('KIS_APP_KEY'),
       'app_secret': os.getenv('KIS_APP_SECRET')
   })
   count = collector.update_tracking_error()
   print(f'✅ Phase 3: {count} ETFs tracking error updated')
   "
   fi

   # Phase 4: 52주 고저 업데이트
   if [ "$1" == "phase4" ]; then
       python3 -c "
   from modules.etf_collector import ETFCollector
   collector = ETFCollector('data/spock_local.db')
   count = collector.update_52w_high_low()
   print(f'✅ Phase 4: {count} ETFs 52W high/low updated')
   "
   fi
   ```

2. **Setup cron jobs**
   ```bash
   # crontab -e

   # Phase 1: 기본 ETF 목록 수집 (매일 09:00 KST)
   0 9 * * * cd /Users/13ruce/spock && ./scripts/run_etf_collection.sh phase1 >> log/etf_collection.log 2>&1

   # Phase 2: AUM 업데이트 (매일 16:00 KST)
   0 16 * * * cd /Users/13ruce/spock && ./scripts/run_etf_collection.sh phase2 >> log/etf_collection.log 2>&1

   # Phase 3: 괴리율 업데이트 (매주 일요일 21:00 KST)
   0 21 * * 0 cd /Users/13ruce/spock && ./scripts/run_etf_collection.sh phase3 >> log/etf_collection.log 2>&1

   # Phase 4: 52주 고저 업데이트 (매일 17:00 KST)
   0 17 * * * cd /Users/13ruce/spock && ./scripts/run_etf_collection.sh phase4 >> log/etf_collection.log 2>&1
   ```

3. **Test cron jobs manually**
   ```bash
   # Test each phase
   ./scripts/run_etf_collection.sh phase1
   ./scripts/run_etf_collection.sh phase2
   ./scripts/run_etf_collection.sh phase3
   ./scripts/run_etf_collection.sh phase4

   # Check logs
   tail -f log/etf_collection.log
   ```

**Deliverables**:
- ✅ Execution scripts created
- ✅ Cron jobs configured
- ✅ Manual tests passing

---

#### Day 10: Monitoring & Documentation (8 hours)

**Tasks**:

1. **Setup monitoring**
   ```python
   # modules/etf_monitoring.py
   import sqlite3
   from datetime import datetime, timedelta

   def check_data_freshness(db_path: str):
       """데이터 신선도 체크"""
       conn = sqlite3.connect(db_path)
       cursor = conn.cursor()

       # Check last update time
       cursor.execute("""
           SELECT MAX(last_updated)
           FROM etf_details
       """)
       last_updated = cursor.fetchone()[0]

       if last_updated:
           last_updated_dt = datetime.fromisoformat(last_updated)
           hours_ago = (datetime.now() - last_updated_dt).total_seconds() / 3600

           if hours_ago > 24:
               print(f"⚠️ Warning: ETF data is {hours_ago:.1f} hours old")
           else:
               print(f"✅ ETF data is fresh ({hours_ago:.1f} hours ago)")

   def check_data_completeness(db_path: str):
       """데이터 완전성 체크"""
       conn = sqlite3.connect(db_path)
       cursor = conn.cursor()

       # Check field completeness
       checks = {
           'ticker': 'ticker IS NOT NULL',
           'issuer': 'issuer IS NOT NULL',
           'expense_ratio': 'expense_ratio IS NOT NULL',
           'aum': 'aum IS NOT NULL AND aum > 0',
           'tracking_error_20d': 'tracking_error_20d IS NOT NULL',
           'week_52_high': 'week_52_high IS NOT NULL',
       }

       for field, condition in checks.items():
           cursor.execute(f"""
               SELECT COUNT(*) * 100.0 / (SELECT COUNT(*) FROM etf_details)
               FROM etf_details
               WHERE {condition}
           """)
           coverage = cursor.fetchone()[0]
           print(f"{field}: {coverage:.1f}% coverage")
   ```

2. **Create monitoring script**
   ```bash
   # scripts/monitor_etf_data.sh
   #!/bin/bash

   cd /Users/13ruce/spock

   python3 -c "
   from modules.etf_monitoring import check_data_freshness, check_data_completeness

   print('📊 ETF Data Health Check')
   print('=' * 60)

   check_data_freshness('data/spock_local.db')
   print()
   check_data_completeness('data/spock_local.db')
   "
   ```

3. **Final documentation**
   - Update [README.md](../README.md) with ETF collection info
   - Create deployment runbook
   - Document troubleshooting procedures

**Deliverables**:
- ✅ Monitoring scripts created
- ✅ Health checks working
- ✅ Documentation complete

**Milestone**: Production Ready ✅

---

## Success Criteria

### Phase 1 (P0) - Must Have
- [x] 1,029 ETFs collected from KRX Data API
- [x] 10 fields populated in database
- [x] Unit tests passing (100% coverage)
- [x] Integration tests passing
- [x] Execution time < 10 seconds

### Phase 2 (P1) - Should Have
- [x] KIS API authentication working
- [x] AUM calculation accurate
- [x] Rate limiting compliant (20 req/sec)
- [x] Execution time < 60 seconds for all ETFs
- [x] Error rate < 5%

### Phase 3 (P2) - Nice to Have
- [ ] Tracking error collection working
- [ ] Constituent count accurate
- [ ] 52W high/low calculation correct
- [ ] Execution time < 120 seconds

### Phase 4 (Production)
- [ ] Cron jobs running reliably
- [ ] Monitoring alerts configured
- [ ] Error handling comprehensive
- [ ] Logs properly rotated
- [ ] Documentation complete

---

## Troubleshooting Guide

### Common Issues

**1. KRX Data API Timeout**
```bash
# Symptom: Connection timeout or 504 error
# Solution: Retry with exponential backoff

python3 << EOF
import time
for attempt in range(3):
    try:
        data = krx_api.get_etf_list()
        break
    except Exception as e:
        print(f"Attempt {attempt+1} failed: {e}")
        time.sleep(2 ** attempt)
EOF
```

**2. KIS API Rate Limit**
```bash
# Symptom: 429 Too Many Requests
# Solution: Reduce request rate or use exponential backoff

# Check current rate
time.sleep(0.05)  # 20 req/sec

# If still failing, increase delay
time.sleep(0.1)   # 10 req/sec
```

**3. Database Lock**
```bash
# Symptom: SQLite database is locked
# Solution: Ensure proper connection management

# Bad: Nested connections
with conn1:
    with conn2:  # Causes lock
        ...

# Good: Single connection
with self.db_manager.get_connection() as conn:
    ...
```

**4. Missing OHLCV Data**
```bash
# Symptom: NULL 52W high/low
# Solution: Ensure OHLCV collection runs first

# Check OHLCV data
python3 -c "
import sqlite3
conn = sqlite3.connect('data/spock_local.db')
cursor = conn.cursor()
cursor.execute('SELECT ticker, COUNT(*) FROM ohlcv_data WHERE ticker IN (SELECT ticker FROM etf_details) GROUP BY ticker HAVING COUNT(*) < 250')
print(cursor.fetchall())
"
```

---

## Performance Benchmarks

| Phase | ETF Count | Expected Time | Actual Time | Notes |
|-------|-----------|---------------|-------------|-------|
| Phase 1 | 1,029 | <10 sec | TBD | KRX Data API |
| Phase 2 | 1,029 | ~51 sec | TBD | KIS API (20 req/sec) |
| Phase 3 | 1,029 | ~102 sec | TBD | KIS API (3 calls/ETF) |
| Phase 4 | 1,029 | ~10 sec | TBD | SQLite query |
| **Total** | 1,029 | ~173 sec | TBD | Full pipeline |

---

## Next Steps After Implementation

1. **Integrate with scanner.py**
   - Add ETF support to stock scanner
   - Unified ticker collection workflow

2. **Extend to OHLCV collection**
   - Add ETF ticker support in data_collector.py
   - Collect 250-day OHLCV data for ETFs

3. **Enable technical analysis**
   - Run LayeredScoringEngine on ETFs
   - ETF-specific scoring rules

4. **Portfolio management**
   - Add ETF to portfolio allocation
   - Risk management with ETF diversification

---

**Document Version**: 1.0
**Last Updated**: 2025-10-01
**Status**: Ready for Implementation
