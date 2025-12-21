# Region-Based Data Collection Architecture

## 1. KIS API Structure Analysis

### API Category Mapping

KIS API는 **자산군(Asset Class)** 기준으로 분류되어 있으며, 지역/거래소는 **파라미터**로 구분:

```
국내주식 (Domestic Stock)
├─ 코스피 (KOSPI)
├─ 코스피NXT (KOSPI NXT) ← 제2거래소
├─ 코스닥 (KOSDAQ)
└─ 코스닥NXT (KOSDAQ NXT) ← 제2거래소

ETF/ETN
├─ 국내 ETF/ETN
└─ 해외 ETF (KIS API 문서 확인 필요)

해외주식 (Overseas Stock)
├─ 미국 (US)
│  ├─ 나스닥 (NASDAQ)
│  ├─ 뉴욕 (NYSE)
│  └─ 아멕스 (AMEX)
├─ 중국 (China)
│  ├─ 상해 (Shanghai Stock Exchange)
│  ├─ 상해지수 (SSE Composite)
│  ├─ 심천 (Shenzhen Stock Exchange)
│  └─ 심천지수 (SZSE Component)
├─ 홍콩 (Hong Kong)
│  └─ HKEX (Hong Kong Stock Exchange)
├─ 일본 (Japan)
│  └─ 도쿄 (Tokyo Stock Exchange)
└─ 베트남 (Vietnam)
   ├─ 하노이 (Hanoi Stock Exchange - HNX)
   └─ 호치민 (Ho Chi Minh Stock Exchange - HOSE)

국내선물옵션 (Domestic Futures & Options)
해외선물옵션 (Overseas Futures & Options)
국내채권 (Domestic Bonds)
```

### Key Insights

1. **Asset-First Hierarchy**: KIS API는 국내/해외 → 자산군 → 거래소 순서로 분류
2. **Exchange Code Parameters**:
   - 국내: `mkt_id` (STK=코스피, SQ=코스닥, NXT=NXT)
   - 해외: `excd` (NASD=나스닥, NYSE=뉴욕, SEHK=홍콩 등)
3. **Endpoint Patterns**:
   - 국내: `/uapi/domestic-stock/v1/*`
   - ETF: `/uapi/etfetn/v1/*` (국내 전용)
   - 해외: `/uapi/overseas-price/v1/*` (모든 해외 시장 통합)

---

## 2. Revised Region-Based Architecture

### Core Principle

> **"Region as Primary Boundary, Asset Type as Internal Logic"**
>
> - 각 지역 어댑터는 해당 지역의 **모든 자산군**(주식, ETF, 선물옵션 등)을 처리
> - API 클라이언트는 **자산군별로 분리** (KIS API 엔드포인트 구조 반영)
> - 파서는 **자산 타입별로 분리** (데이터 스키마 차이 반영)

### Directory Structure

```
modules/
├── data_collector.py                    # 🎯 Main orchestrator
│
├── market_adapters/                     # 📍 Regional adapters (6개 지역)
│   ├── __init__.py
│   ├── base_adapter.py                  # Abstract base class
│   ├── kr_adapter.py                    # 🇰🇷 Korea (KOSPI, KOSDAQ, NXT)
│   ├── us_adapter.py                    # 🇺🇸 US (NASDAQ, NYSE, AMEX)
│   ├── cn_adapter.py                    # 🇨🇳 China (SSE, SZSE)
│   ├── hk_adapter.py                    # 🇭🇰 Hong Kong (HKEX)
│   ├── jp_adapter.py                    # 🇯🇵 Japan (TSE)
│   └── vn_adapter.py                    # 🇻🇳 Vietnam (HNX, HOSE)
│
├── api_clients/                         # 🔌 API clients (자산군별 분리)
│   ├── __init__.py
│   ├── kis_domestic_stock_api.py        # KIS 국내주식 API (/domestic-stock/*)
│   ├── kis_etf_api.py                   # KIS ETF/ETN API (/etfetn/*)
│   ├── kis_overseas_stock_api.py        # KIS 해외주식 API (/overseas-price/*)
│   ├── krx_data_api.py                  # KRX Data API (공식, 인증 불필요)
│   ├── pykrx_api.py                     # pykrx fallback (Korea only)
│   └── yahoo_finance_api.py             # Yahoo Finance fallback (US)
│
├── parsers/                             # 🔄 Data parsers (자산 타입별 분리)
│   ├── __init__.py
│   ├── stock_parser.py                  # 주식 데이터 정규화
│   ├── etf_parser.py                    # ETF 데이터 정규화
│   └── futures_parser.py                # 선물옵션 데이터 정규화 (future)
│
└── db_manager_sqlite.py                 # 💾 Database layer (unchanged)
```

---

## 3. Regional Adapter Design

### 3.1 Korea Adapter (kr_adapter.py)

**Scope**: KOSPI, KOSDAQ, KOSPI NXT, KOSDAQ NXT, Korea ETFs

**Data Sources**:
- Primary: KRX Data API (official, no auth, real-time)
- Secondary: KIS API (domestic-stock, etfetn endpoints)
- Fallback: pykrx (community library)

**Example Implementation**:

```python
from typing import List, Dict, Optional
from api_clients.kis_domestic_stock_api import KISDomesticStockAPI
from api_clients.kis_etf_api import KISEtfAPI
from api_clients.krx_data_api import KRXDataAPI
from api_clients.pykrx_api import PyKRXAPI
from parsers.stock_parser import StockParser
from parsers.etf_parser import ETFParser

class KoreaAdapter:
    """
    Korea market data collector

    Supported Markets:
    - KOSPI (코스피)
    - KOSPI NXT (코스피 NXT) - 제2거래소
    - KOSDAQ (코스닥)
    - KOSDAQ NXT (코스닥 NXT) - 제2거래소
    - Korea ETF/ETN
    """

    SUPPORTED_EXCHANGES = ['KOSPI', 'KOSDAQ', 'KOSPI_NXT', 'KOSDAQ_NXT']

    def __init__(self, db_manager, kis_config: Dict):
        self.db = db_manager

        # API Clients (자산군별 분리)
        self.kis_stock_api = KISDomesticStockAPI(**kis_config)
        self.kis_etf_api = KISEtfAPI(**kis_config)
        self.krx_api = KRXDataAPI()
        self.pykrx_api = PyKRXAPI()  # Fallback

        # Parsers (자산 타입별 분리)
        self.stock_parser = StockParser()
        self.etf_parser = ETFParser()

    # ========== 주식 수집 메서드 ==========

    def collect_stock_list(self, exchanges: Optional[List[str]] = None) -> int:
        """
        KRX Data API로 주식 목록 수집

        Args:
            exchanges: ['KOSPI', 'KOSDAQ', 'KOSPI_NXT', 'KOSDAQ_NXT']
                      None이면 전체 수집

        Returns:
            수집된 주식 수
        """
        exchanges = exchanges or self.SUPPORTED_EXCHANGES
        total_count = 0

        for exchange in exchanges:
            try:
                # KRX Data API로 주식 목록 조회
                raw_data = self.krx_api.get_stock_list(exchange=exchange)

                # 파싱 및 데이터베이스 삽입
                stock_list = [self.stock_parser.parse_krx_stock(item, exchange)
                             for item in raw_data]

                inserted = self.db.bulk_insert_stocks(stock_list)
                total_count += inserted

                logger.info(f"✅ {exchange}: {inserted}개 주식 수집 완료")

            except Exception as e:
                logger.error(f"❌ {exchange} 주식 수집 실패: {e}")
                # Fallback to pykrx
                self._fallback_stock_collection(exchange)

        return total_count

    def update_stock_financials(self, tickers: Optional[List[str]] = None) -> int:
        """
        KIS API로 재무정보 업데이트 (PER, PBR, ROE 등)

        Args:
            tickers: 업데이트할 종목 리스트 (None이면 전체)

        Returns:
            업데이트된 주식 수
        """
        if tickers is None:
            tickers = self.db.get_stock_tickers(region='KR')

        updated_count = 0
        for ticker in tickers:
            try:
                # KIS API로 재무정보 조회
                financials = self.kis_stock_api.get_financials(ticker)

                # 데이터베이스 업데이트
                self.db.update_stock_financials(ticker, financials)
                updated_count += 1

                # Rate limiting (20 req/sec)
                time.sleep(0.05)

            except Exception as e:
                logger.error(f"❌ {ticker} 재무정보 업데이트 실패: {e}")

        return updated_count

    # ========== ETF 수집 메서드 ==========

    def collect_etf_basic_info(self) -> int:
        """
        Phase 1: KRX Data API로 ETF 기본 정보 수집

        Returns:
            수집된 ETF 수
        """
        try:
            # KRX Data API로 ETF 목록 조회 (1,029개)
            raw_data = self.krx_api.get_etf_list()

            # 파싱 (10개 필드: ticker, issuer, tracking_index 등)
            etf_list = [self.etf_parser.parse_krx_etf(item) for item in raw_data]

            # 데이터베이스 삽입
            inserted = self.db.bulk_insert_etfs(etf_list)

            logger.info(f"✅ Korea ETF: {inserted}개 수집 완료")
            return inserted

        except Exception as e:
            logger.error(f"❌ Korea ETF 수집 실패: {e}")
            return 0

    def update_etf_aum(self, tickers: Optional[List[str]] = None) -> int:
        """
        Phase 2: KIS API로 ETF AUM 업데이트

        AUM = 상장주식수 × 현재가

        Args:
            tickers: 업데이트할 ETF 리스트 (None이면 전체)

        Returns:
            업데이트된 ETF 수
        """
        if tickers is None:
            # 데이터베이스에서 Korea ETF 목록 조회
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT ticker, listed_shares
                FROM etf_details
                WHERE ticker IN (SELECT ticker FROM tickers WHERE region = 'KR')
            """)
            targets = cursor.fetchall()
        else:
            targets = [(t, self.db.get_etf_listed_shares(t)) for t in tickers]

        updated_count = 0
        for ticker, listed_shares in targets:
            try:
                # KIS ETF API로 현재가 조회
                price_data = self.kis_etf_api.get_current_price(ticker)
                current_price = int(price_data['stck_prpr'])

                # AUM 계산
                aum = listed_shares * current_price

                # 데이터베이스 업데이트
                self.db.update_etf_field(ticker, 'aum', aum)
                updated_count += 1

                # Rate limiting (20 req/sec)
                time.sleep(0.05)

            except Exception as e:
                logger.error(f"❌ {ticker} AUM 업데이트 실패: {e}")

        logger.info(f"✅ {updated_count}개 ETF AUM 업데이트 완료")
        return updated_count

    def update_etf_tracking_error(self, tickers: Optional[List[str]] = None) -> int:
        """
        Phase 3: KIS API로 ETF 추적오차 업데이트

        KIS API 엔드포인트:
        - FHPST02440000: 단기 NAV 괴리율
        - FHPST02440200: 장기 NAV 괴리율

        Args:
            tickers: 업데이트할 ETF 리스트 (None이면 전체)

        Returns:
            업데이트된 ETF 수
        """
        if tickers is None:
            tickers = self.db.get_etf_tickers(region='KR')

        updated_count = 0
        for ticker in tickers:
            try:
                # KIS ETF API로 NAV 괴리율 조회
                nav_data = self.kis_etf_api.get_nav_comparison_trend(ticker)

                # 추적오차 계산 (20일, 60일, 120일, 250일)
                tracking_errors = self.etf_parser.calculate_tracking_error(nav_data)

                # 데이터베이스 업데이트
                self.db.update_etf_tracking_errors(ticker, tracking_errors)
                updated_count += 1

                # Rate limiting (20 req/sec)
                time.sleep(0.05)

            except Exception as e:
                logger.error(f"❌ {ticker} 추적오차 업데이트 실패: {e}")

        logger.info(f"✅ {updated_count}개 ETF 추적오차 업데이트 완료")
        return updated_count

    # ========== NXT 거래소 전용 메서드 ==========

    def collect_nxt_stocks(self) -> int:
        """
        NXT 거래소 주식 수집

        NXT는 2024년 출범한 제2거래소로, KOSPI NXT와 KOSDAQ NXT로 구성

        Returns:
            수집된 NXT 주식 수
        """
        nxt_exchanges = ['KOSPI_NXT', 'KOSDAQ_NXT']
        return self.collect_stock_list(exchanges=nxt_exchanges)

    # ========== 공통 유틸리티 메서드 ==========

    def health_check(self) -> Dict:
        """API 연결 상태 확인"""
        return {
            'kis_stock_api': self.kis_stock_api.check_connection(),
            'kis_etf_api': self.kis_etf_api.check_connection(),
            'krx_api': self.krx_api.check_connection(),
            'pykrx_api': self.pykrx_api.check_connection(),
        }

    def _fallback_stock_collection(self, exchange: str) -> int:
        """pykrx 폴백 수집"""
        try:
            raw_data = self.pykrx_api.get_stock_list(exchange)
            stock_list = [self.stock_parser.parse_pykrx_stock(item, exchange)
                         for item in raw_data]
            return self.db.bulk_insert_stocks(stock_list)
        except Exception as e:
            logger.error(f"❌ pykrx 폴백도 실패: {e}")
            return 0
```

### 3.2 US Adapter (us_adapter.py)

**Scope**: NASDAQ, NYSE, AMEX (stocks + ETFs)

**Data Sources**:
- Primary: KIS API (overseas-price endpoints)
- Fallback: Yahoo Finance API

**Example Implementation**:

```python
from api_clients.kis_overseas_stock_api import KISOverseasStockAPI
from api_clients.yahoo_finance_api import YahooFinanceAPI
from parsers.stock_parser import StockParser
from parsers.etf_parser import ETFParser

class USAdapter:
    """
    US market data collector

    Supported Markets:
    - NASDAQ
    - NYSE (New York Stock Exchange)
    - AMEX (American Stock Exchange)

    Asset Types:
    - Stocks
    - ETFs (US-listed)
    """

    SUPPORTED_EXCHANGES = ['NASD', 'NYSE', 'AMEX']  # KIS excd codes

    def __init__(self, db_manager, kis_config: Dict):
        self.db = db_manager

        # API Clients
        self.kis_api = KISOverseasStockAPI(**kis_config)
        self.yahoo_api = YahooFinanceAPI()  # Fallback

        # Parsers
        self.stock_parser = StockParser()
        self.etf_parser = ETFParser()

    def collect_stock_list(self, exchanges: Optional[List[str]] = None) -> int:
        """
        KIS API로 미국 주식 목록 수집

        Note: KIS API는 전체 목록 제공 안 함 (ticker 입력 필요)
              → 사전 정의된 ticker list 사용 또는 Yahoo Finance 크롤링

        Args:
            exchanges: ['NASD', 'NYSE', 'AMEX']

        Returns:
            수집된 주식 수
        """
        # Option 1: Predefined ticker list (recommended)
        predefined_tickers = self._load_us_ticker_list()  # CSV or JSON

        # Option 2: Yahoo Finance fallback
        # us_tickers = self.yahoo_api.get_all_tickers(exchanges)

        stock_list = []
        for ticker in predefined_tickers:
            try:
                # KIS API로 주식 정보 조회
                stock_info = self.kis_api.get_stock_info(ticker)

                # 파싱
                parsed = self.stock_parser.parse_kis_overseas_stock(stock_info)
                stock_list.append(parsed)

                # Rate limiting
                time.sleep(0.05)

            except Exception as e:
                logger.error(f"❌ {ticker} 수집 실패: {e}")

        # 데이터베이스 삽입
        return self.db.bulk_insert_stocks(stock_list)

    def collect_etf_list(self) -> int:
        """
        미국 ETF 목록 수집

        KIS API는 ETF 전용 엔드포인트가 없음 (stock과 동일한 overseas-price 사용)
        → Yahoo Finance로 ETF 리스트 확보 후 KIS API로 상세 정보 조회
        """
        # Yahoo Finance로 US ETF 목록 조회
        etf_tickers = self.yahoo_api.get_etf_list(country='US')

        etf_list = []
        for ticker in etf_tickers:
            try:
                # KIS API로 ETF 정보 조회 (overseas-price 엔드포인트 사용)
                etf_info = self.kis_api.get_stock_info(ticker)  # Stock과 동일 API

                # ETF 파서로 변환
                parsed = self.etf_parser.parse_kis_overseas_etf(etf_info)
                etf_list.append(parsed)

                # Rate limiting
                time.sleep(0.05)

            except Exception as e:
                logger.error(f"❌ {ticker} ETF 수집 실패: {e}")

        return self.db.bulk_insert_etfs(etf_list)

    def health_check(self) -> Dict:
        """API 연결 상태 확인"""
        return {
            'kis_api': self.kis_api.check_connection(),
            'yahoo_api': self.yahoo_api.check_connection(),
        }
```

### 3.3 China/HK/Japan/Vietnam Adapters

**동일한 패턴 적용**:
- Primary: KIS API (overseas-price endpoints with different `excd` codes)
- Fallback: Region-specific APIs (if available)

```python
# cn_adapter.py
class ChinaAdapter:
    SUPPORTED_EXCHANGES = ['SHAA', 'SHAZ', 'SZAA', 'SZAZ']  # 상해A, 상해지수, 심천A, 심천지수

# hk_adapter.py
class HongKongAdapter:
    SUPPORTED_EXCHANGES = ['SEHK']  # Hong Kong Stock Exchange

# jp_adapter.py
class JapanAdapter:
    SUPPORTED_EXCHANGES = ['TSE']  # Tokyo Stock Exchange

# vn_adapter.py
class VietnamAdapter:
    SUPPORTED_EXCHANGES = ['HNX', 'HOSE']  # 하노이, 호치민
```

---

## 4. API Client Design

### 4.1 KIS Domestic Stock API

```python
# api_clients/kis_domestic_stock_api.py

class KISDomesticStockAPI:
    """
    KIS 국내주식 API 클라이언트

    Endpoint: /uapi/domestic-stock/v1/*

    Supported Markets:
    - KOSPI (mkt_id='STK')
    - KOSDAQ (mkt_id='SQ')
    - KOSPI NXT (mkt_id='NXT')
    - KOSDAQ NXT (mkt_id='NXT')
    """

    BASE_URL = "https://openapi.koreainvestment.com:9443"

    def __init__(self, app_key: str, app_secret: str):
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = self._get_access_token()

    def get_stock_price(self, ticker: str, market: str = 'STK') -> Dict:
        """
        국내주식 현재가 조회

        Args:
            ticker: 종목코드 (6자리)
            market: 시장구분 ('STK'=코스피, 'SQ'=코스닥, 'NXT'=NXT)

        Returns:
            {'stck_prpr': 현재가, 'prdy_vrss': 전일대비, ...}
        """
        endpoint = f"{self.BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"

        headers = {
            'authorization': f'Bearer {self.access_token}',
            'appkey': self.app_key,
            'appsecret': self.app_secret,
            'tr_id': 'FHKST01010100',  # 국내주식 현재가 TR_ID
        }

        params = {
            'FID_COND_MRKT_DIV_CODE': market,
            'FID_INPUT_ISCD': ticker,
        }

        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()

        return response.json()['output']

    def get_financials(self, ticker: str) -> Dict:
        """
        국내주식 재무정보 조회 (PER, PBR, ROE 등)

        Args:
            ticker: 종목코드 (6자리)

        Returns:
            {'per': PER, 'pbr': PBR, 'roe': ROE, ...}
        """
        # KIS API 재무정보 엔드포인트 호출
        # (구체적인 TR_ID는 API 문서 확인 필요)
        pass
```

### 4.2 KIS ETF API

```python
# api_clients/kis_etf_api.py

class KISEtfAPI:
    """
    KIS ETF/ETN API 클라이언트

    Endpoint: /uapi/etfetn/v1/*

    Korea 국내 ETF 전용
    """

    BASE_URL = "https://openapi.koreainvestment.com:9443"

    def get_current_price(self, ticker: str) -> Dict:
        """
        ETF 현재가 조회

        TR_ID: FHPST02400000

        Args:
            ticker: ETF 종목코드 (6자리)

        Returns:
            {'stck_prpr': 현재가, 'nav': NAV, ...}
        """
        endpoint = f"{self.BASE_URL}/uapi/etfetn/v1/quotations/inquire-price"

        headers = {
            'authorization': f'Bearer {self.access_token}',
            'appkey': self.app_key,
            'appsecret': self.app_secret,
            'tr_id': 'FHPST02400000',
        }

        params = {'FID_INPUT_ISCD': ticker}

        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()

        return response.json()['output']

    def get_constituent_stocks(self, ticker: str) -> List[Dict]:
        """
        ETF 구성종목 조회

        TR_ID: FHKST121600C0

        Args:
            ticker: ETF 종목코드 (6자리)

        Returns:
            [{'ticker': '005930', 'weight': 25.3, ...}, ...]
        """
        endpoint = f"{self.BASE_URL}/uapi/etfetn/v1/quotations/inquire-component-stock-price"

        headers = {
            'authorization': f'Bearer {self.access_token}',
            'appkey': self.app_key,
            'appsecret': self.app_secret,
            'tr_id': 'FHKST121600C0',
        }

        params = {'FID_INPUT_ISCD': ticker}

        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()

        return response.json()['output']

    def get_nav_comparison_trend(self, ticker: str) -> Dict:
        """
        ETF NAV 괴리율 조회 (추적오차 계산용)

        TR_ID: FHPST02440000 (단기), FHPST02440200 (장기)

        Args:
            ticker: ETF 종목코드 (6자리)

        Returns:
            {'nav_deviation_20d': 0.15, 'nav_deviation_60d': 0.12, ...}
        """
        # Short-term NAV comparison (20일)
        short_term = self._get_nav_comparison(ticker, 'FHPST02440000')

        # Long-term NAV comparison (120일)
        long_term = self._get_nav_comparison(ticker, 'FHPST02440200')

        return {**short_term, **long_term}
```

### 4.3 KIS Overseas Stock API

```python
# api_clients/kis_overseas_stock_api.py

class KISOverseasStockAPI:
    """
    KIS 해외주식 API 클라이언트

    Endpoint: /uapi/overseas-price/v1/*

    Supported Markets:
    - US: NASD, NYSE, AMEX
    - China: SHAA, SHAZ, SZAA, SZAZ
    - Hong Kong: SEHK
    - Japan: TSE
    - Vietnam: HNX, HOSE
    """

    BASE_URL = "https://openapi.koreainvestment.com:9443"

    EXCHANGE_CODES = {
        'NASDAQ': 'NASD',
        'NYSE': 'NYSE',
        'AMEX': 'AMEX',
        'SHANGHAI': 'SHAA',
        'SHENZHEN': 'SZAA',
        'HONG_KONG': 'SEHK',
        'TOKYO': 'TSE',
        'HANOI': 'HNX',
        'HCMC': 'HOSE',
    }

    def get_stock_info(self, ticker: str, exchange: str = 'NASD') -> Dict:
        """
        해외주식 정보 조회

        Args:
            ticker: 종목코드 (AAPL, TSLA 등)
            exchange: 거래소 코드 ('NASD', 'NYSE', 'SEHK' 등)

        Returns:
            {'ticker': 'AAPL', 'price': 150.25, ...}
        """
        excd = self.EXCHANGE_CODES.get(exchange, exchange)

        endpoint = f"{self.BASE_URL}/uapi/overseas-price/v1/quotations/price"

        headers = {
            'authorization': f'Bearer {self.access_token}',
            'appkey': self.app_key,
            'appsecret': self.app_secret,
            'tr_id': 'HHDFS00000300',  # 해외주식 현재가 TR_ID
        }

        params = {
            'EXCD': excd,
            'SYMB': ticker,
        }

        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()

        return response.json()['output']
```

---

## 5. Module Count Comparison

### Asset-Type-Based (현재 플랜)
```
etf_collector.py
etf_krx_api.py
etf_kis_api.py
etf_parser.py

stock_collector.py
stock_krx_api.py
stock_kis_api.py
stock_parser.py

→ 8개 모듈 × 6개 지역 = 48개 모듈 (재사용 불가능)
```

### Region-Based (제안)
```
market_adapters/ (6개 지역)
├── kr_adapter.py
├── us_adapter.py
├── cn_adapter.py
├── hk_adapter.py
├── jp_adapter.py
└── vn_adapter.py

api_clients/ (6개 클라이언트)
├── kis_domestic_stock_api.py
├── kis_etf_api.py
├── kis_overseas_stock_api.py
├── krx_data_api.py
├── pykrx_api.py
└── yahoo_finance_api.py

parsers/ (3개 파서)
├── stock_parser.py
├── etf_parser.py
└── futures_parser.py

→ 총 15개 모듈 (68% 감소)
```

---

## 6. Migration Plan

### Phase 0: Restructure (0.5 days)

**Create new directory structure**:
```bash
mkdir -p modules/market_adapters
mkdir -p modules/api_clients
mkdir -p modules/parsers
```

### Phase 1: Refactor API Clients (1 day)

**Rename and split existing modules**:
```bash
# Before
etf_kis_api.py → 하나의 파일에 모든 KIS API 로직

# After
api_clients/kis_domestic_stock_api.py  # 국내주식 전용
api_clients/kis_etf_api.py             # ETF 전용
api_clients/kis_overseas_stock_api.py  # 해외주식 전용
```

**Migration Steps**:
1. `etf_kis_api.py`에서 ETF 관련 메서드 추출 → `kis_etf_api.py`
2. 국내주식 메서드 추출 → `kis_domestic_stock_api.py`
3. 해외주식 메서드 추출 → `kis_overseas_stock_api.py`
4. 공통 인증 로직은 각 클라이언트에서 상속받을 수 있도록 `kis_base_api.py` 생성

### Phase 2: Create Korea Adapter (2 days)

**Implement kr_adapter.py**:
```bash
# Combine existing logic
etf_collector.py → kr_adapter.py (ETF 메서드)
stock_collector.py → kr_adapter.py (Stock 메서드)
```

**Key Changes**:
- Single class with both `collect_etf_*()` and `collect_stock_*()` methods
- Shared API clients (`self.kis_etf_api`, `self.kis_stock_api`)
- Region-specific data sources (`self.krx_api`, `self.pykrx_api`)

### Phase 3: Implement Other Regions (3 days)

**Create adapters in order of priority**:
1. `us_adapter.py` (Phase 4 target)
2. `cn_adapter.py`, `hk_adapter.py` (Phase 5 target)
3. `jp_adapter.py`, `vn_adapter.py` (Phase 6, optional)

### Phase 4: Update Orchestrator (1 day)

**Refactor data_collector.py**:
```python
from market_adapters.kr_adapter import KoreaAdapter
from market_adapters.us_adapter import USAdapter

class DataCollector:
    def __init__(self, db_path: str, kis_config: Dict):
        self.db = SQLiteDatabaseManager(db_path)

        # Regional adapters
        self.adapters = {
            'KR': KoreaAdapter(self.db, kis_config),
            'US': USAdapter(self.db, kis_config),
            # 'CN': ChinaAdapter(self.db, kis_config),
            # 'HK': HongKongAdapter(self.db, kis_config),
        }

    def collect_all_etfs(self, regions: List[str] = ['KR']) -> Dict:
        """모든 지역의 ETF 수집"""
        results = {}
        for region in regions:
            adapter = self.adapters.get(region)
            if adapter:
                results[region] = adapter.collect_etf_basic_info()
        return results

    def collect_all_stocks(self, regions: List[str] = ['KR']) -> Dict:
        """모든 지역의 주식 수집"""
        results = {}
        for region in regions:
            adapter = self.adapters.get(region)
            if adapter:
                results[region] = adapter.collect_stock_list()
        return results
```

---

## 7. Benefits Summary

### ✅ Scalability
- 새로운 국가 추가: **1개 어댑터 파일만 생성** (vs 8개 모듈)
- 새로운 자산군 추가: **1개 파서 + 각 어댑터에 메서드 추가** (vs 전체 재구현)

### ✅ Maintainability
- KIS API 인증 로직 변경: **1개 파일 수정** (api_clients/kis_base_api.py)
- 데이터베이스 스키마 변경: **파서 파일만 수정** (parsers/*)
- 버그 픽스: **영향받는 어댑터만 수정** (독립적)

### ✅ Code Reuse
- KIS API 클라이언트: **모든 지역 어댑터에서 공유**
- 파서 로직: **모든 지역 어댑터에서 공유**
- 데이터베이스 레이어: **변경 없음**

### ✅ Testing
- 단위 테스트: **어댑터별로 독립적으로 테스트 가능**
- 통합 테스트: **지역별로 격리된 테스트 환경**
- Mock API: **API 클라이언트만 mocking하면 전체 어댑터 테스트 가능**

### ✅ API Structure Alignment
- KIS API의 실제 구조 반영: `domestic-*` vs `overseas-*` vs `etfetn`
- Exchange code 파라미터 활용: `mkt_id`, `excd`
- 자연스러운 확장 경로: 지역 추가 시 기존 코드 재사용

---

## 8. Risks and Mitigations

### Risk 1: Adapter 파일 크기 증가
- **문제**: kr_adapter.py가 주식 + ETF + 선물옵션 로직을 모두 포함하면 1,000줄 이상
- **완화**:
  - Private 메서드로 세부 로직 분리 (`_collect_kospi()`, `_collect_kosdaq()`)
  - Mixin 패턴 사용: `KoreaStockMixin`, `KoreaETFMixin`으로 분리 후 다중상속

### Risk 2: 지역별 API 차이
- **문제**: 일부 지역은 KIS API가 불완전할 수 있음 (베트남, 일본 등)
- **완화**:
  - Fallback API 클라이언트 준비 (Yahoo Finance, local APIs)
  - Adapter 내부에서 data source 선택 로직 캡슐화

### Risk 3: 데이터베이스 스키마 불일치
- **문제**: 지역별로 필요한 필드가 다를 수 있음 (US는 dividend_yield, Korea는 외국인보유율)
- **완화**:
  - `stock_details`, `etf_details` 테이블에 Optional 필드 추가
  - JSON 컬럼 활용: `regional_metadata` (지역별 추가 정보 저장)

---

## 9. Next Steps

1. ✅ **Region-based architecture 승인** (이 문서)
2. ⏳ **ETF_IMPLEMENTATION_PLAN_V2.md 작성** (revised plan with region-based approach)
3. ⏳ **Phase 0: Directory restructure** (0.5 days)
4. ⏳ **Phase 1: API clients refactoring** (1 day)
5. ⏳ **Phase 2: Korea adapter implementation** (2 days)
