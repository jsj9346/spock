# Spock Trading System - API Integration Guide

**Complete API reference for KIS API integration and external data sources**
**Last Updated**: 2025-10-18

---

## Table of Contents

1. [KIS API Overview](#1-kis-api-overview)
2. [OAuth 2.0 Authentication](#2-oauth-20-authentication)
3. [KIS Domestic Stock API](#3-kis-domestic-stock-api-korea)
4. [KIS Overseas Stock API](#4-kis-overseas-stock-api-phase-6)
5. [Rate Limiting & Error Handling](#5-rate-limiting--error-handling)
6. [External APIs](#6-external-apis)
7. [API Comparison Matrix](#7-api-comparison-matrix)
8. [Common Workflows](#8-common-workflows)

---

## 1. KIS API Overview

### 1.1 What is KIS API?

**Korea Investment & Securities (한국투자증권) Open API** provides programmatic access to:
- Stock market data (OHLCV, real-time quotes)
- Order execution (buy/sell)
- Portfolio management (balance, positions)
- Market information (tickers, sectors, indices)

**Official Documentation**: https://apiportal.koreainvestment.com

---

### 1.2 API Credentials Setup

**Quick Setup** (Interactive):
```bash
# Run interactive setup script
python3 scripts/setup_credentials.py

# Follow prompts:
# 1. Enter APP_KEY (20 characters)
# 2. Enter APP_SECRET (40 characters)
# 3. Credentials saved to .env with secure permissions (600)
```

**Manual Setup**:
```bash
# Create .env file
cat > .env <<EOF
KIS_APP_KEY=your_app_key_here_20chars
KIS_APP_SECRET=your_app_secret_here_40chars
EOF

# Set secure permissions
chmod 600 .env

# Add to .gitignore
echo ".env" >> .gitignore
```

**Credential Validation**:
```bash
# Validate credentials
python3 scripts/validate_kis_credentials.py

# Expected output:
# ✅ Environment file exists
# ✅ APP_KEY loaded (20 chars)
# ✅ APP_SECRET loaded (40 chars)
# ✅ OAuth token obtained successfully
# ✅ US market data: Accessible
# 🎉 All validation checks passed!
```

**Important Notes**:
- ⚠️ **1-per-day token limit**: Access tokens can only be issued once per day
- ⚠️ **Usage restrictions**: Frequent token requests may result in API suspension
- ⚠️ **Secure storage**: .env file must have 600 permissions (owner read/write only)
- ⚠️ **Never commit**: Ensure .env is in .gitignore

---

### 1.3 API Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Spock Trading System                  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────┐      ┌─────────────────────────┐ │
│  │   BaseKISAPI     │──────│  TokenManager (OAuth)   │ │
│  │  (base_kis_api)  │      │  - 24h token caching    │ │
│  └──────────────────┘      │  - Auto-refresh         │ │
│          │                  └─────────────────────────┘ │
│          │                                               │
│   ┌──────┴────────┬─────────────────┬─────────────┐     │
│   │               │                 │             │     │
│   ▼               ▼                 ▼             ▼     │
│ ┌────────┐  ┌──────────┐  ┌─────────────┐  ┌─────────┐│
│ │Domestic│  │ Overseas │  │  ETF API    │  │ Master  ││
│ │Stock   │  │ Stock    │  │(kis_etf_api)│  │  File   ││
│ │API     │  │ API      │  └─────────────┘  │ Manager ││
│ │(KR)    │  │(Phase 6) │                   └─────────┘│
│ └────────┘  └──────────┘                               │
│                                                          │
└─────────────────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
   ┌──────────┐        ┌──────────────────────┐
   │   KRX    │        │   NYSE, NASDAQ,      │
   │  KOSPI   │        │   HKEX, SSE, SZSE,   │
   │  KOSDAQ  │        │   TSE, HOSE, HNX     │
   └──────────┘        └──────────────────────┘
```

---

## 2. OAuth 2.0 Authentication

### 2.1 Token Lifecycle

```yaml
Token Generation:
  URL: https://openapi.koreainvestment.com:9443/oauth2/tokenP
  Method: POST
  Headers:
    Content-Type: application/json
  Body:
    grant_type: "client_credentials"
    appkey: "{APP_KEY}"
    appsecret: "{APP_SECRET}"

Token Response:
  {
    "access_token": "eyJ0eXAiOiJKV1Q...",
    "access_token_token_expired": "2024-10-19 09:00:00",
    "token_type": "Bearer",
    "expires_in": 86400
  }

Token Usage:
  Headers:
    authorization: "Bearer {access_token}"
    appkey: "{APP_KEY}"
    appsecret: "{APP_SECRET}"
```

---

### 2.2 Token Caching Strategy

**24-Hour Token Caching** (Implemented in `base_kis_api.py`):

```python
from modules.api_clients.base_kis_api import BaseKISAPI

# Token automatically cached for 24 hours
kis_api = BaseKISAPI(app_key, app_secret)

# First request: Token generated and cached
response1 = kis_api.request('GET', '/endpoint1')

# Subsequent requests: Use cached token (no re-generation)
response2 = kis_api.request('GET', '/endpoint2')
response3 = kis_api.request('GET', '/endpoint3')

# Token auto-refreshes after 24 hours
```

**Cache Storage**:
```python
# Token cache location
cache_file = ~/.spock/kis_token_cache.json

# Cache structure
{
  "access_token": "eyJ0eXAiOiJKV1Q...",
  "expires_at": "2024-10-19T09:00:00",
  "token_type": "Bearer"
}
```

**Token Inspection**:
```bash
# Check token cache status
python3 scripts/check_token_cache.py

# Output:
# Token Status: Valid
# Expires At: 2024-10-19 09:00:00
# Time Remaining: 23h 45m 30s
```

---

## 3. KIS Domestic Stock API (Korea)

### 3.1 API Base URL
```
Production: https://openapi.koreainvestment.com:9443
Sandbox:    https://openapivts.koreainvestment.com:29443
```

---

### 3.2 Get Daily Price (OHLCV)

**Endpoint**: `/uapi/domestic-stock/v1/quotations/inquire-daily-price`

**Request**:
```http
GET /uapi/domestic-stock/v1/quotations/inquire-daily-price HTTP/1.1
Host: openapi.koreainvestment.com:9443
authorization: Bearer {access_token}
appkey: {APP_KEY}
appsecret: {APP_SECRET}
tr_id: FHKST01010400

Query Parameters:
  FID_COND_MRKT_DIV_CODE: J  # Market code (J: Stock, Q: KOSDAQ)
  FID_INPUT_ISCD: 005930     # Ticker (Samsung Electronics)
  FID_PERIOD_DIV_CODE: D     # Period (D: Daily, W: Weekly, M: Monthly)
  FID_ORG_ADJ_PRC: 1         # Adjusted price (0: Raw, 1: Adjusted)
```

**Response**:
```json
{
  "output": [
    {
      "stck_bsop_date": "20241018",  // Date
      "stck_oprc": "70000",          // Open
      "stck_hgpr": "71000",          // High
      "stck_lwpr": "69500",          // Low
      "stck_clpr": "70500",          // Close
      "acml_vol": "12345678",        // Volume
      "acml_tr_pbmn": "876543210000" // Trading value
    }
  ],
  "rt_cd": "0",
  "msg_cd": "MCA00000",
  "msg1": "정상처리 되었습니다."
}
```

**Python Implementation**:
```python
from modules.api_clients import KISDomesticStockAPI

domestic_api = KISDomesticStockAPI(app_key, app_secret)

# Get 250 days of OHLCV data
ohlcv = domestic_api.get_daily_price(
    ticker='005930',
    start_date='20240101',
    end_date='20241018',
    adjusted=True
)

# Returns pandas DataFrame:
#       date    open    high     low   close    volume
# 0  2024-01-02  70000   71000   69500   70500  12345678
# 1  2024-01-03  70500   72000   70000   71500  10234567
# ...
```

---

### 3.3 Get Current Price (Real-Time Quote)

**Endpoint**: `/uapi/domestic-stock/v1/quotations/inquire-price`

**Request**:
```http
GET /uapi/domestic-stock/v1/quotations/inquire-price HTTP/1.1
authorization: Bearer {access_token}
appkey: {APP_KEY}
appsecret: {APP_SECRET}
tr_id: FHKST01010100

Query Parameters:
  FID_COND_MRKT_DIV_CODE: J
  FID_INPUT_ISCD: 005930
```

**Response**:
```json
{
  "output": {
    "stck_prpr": "70500",          // Current price
    "prdy_vrss": "500",            // Change from previous day
    "prdy_vrss_sign": "2",         // Change sign (2: +, 5: -)
    "prdy_ctrt": "0.71",           // Change percentage
    "acml_vol": "12345678",        // Accumulated volume
    "stck_hgpr": "71000",          // High
    "stck_lwpr": "69500"           // Low
  }
}
```

**Python Implementation**:
```python
# Get real-time quote
quote = domestic_api.get_current_price('005930')

print(f"Current Price: {quote['price']:,} KRW")
print(f"Change: {quote['change']:+.2f}%")
print(f"Volume: {quote['volume']:,}")
```

---

### 3.4 Place Order (Buy/Sell)

**Endpoint**: `/uapi/domestic-stock/v1/trading/order-cash`

**Request** (Buy Order):
```http
POST /uapi/domestic-stock/v1/trading/order-cash HTTP/1.1
authorization: Bearer {access_token}
appkey: {APP_KEY}
appsecret: {APP_SECRET}
tr_id: TTTC0802U  # Buy order

Content-Type: application/json
{
  "CANO": "12345678",        // Account number
  "ACNT_PRDT_CD": "01",      // Account product code
  "PDNO": "005930",          // Ticker
  "ORD_DVSN": "00",          // Order type (00: Limit, 01: Market)
  "ORD_QTY": "10",           // Quantity
  "ORD_UNPR": "70000"        // Price (0 for market order)
}
```

**Response**:
```json
{
  "output": {
    "KRX_FWDG_ORD_ORGNO": "91252",      // Order number
    "ODNO": "0000123456",               // Order ID
    "ORD_TMD": "153000"                 // Order time
  },
  "rt_cd": "0",
  "msg1": "주문이 완료되었습니다."
}
```

**Python Implementation**:
```python
from modules.kis_trading_engine import KISTradingEngine

engine = KISTradingEngine(db, dry_run=False)

# Place buy order
result = engine.execute_buy_order(
    ticker='005930',
    quantity=10,
    price=70000,      # Auto-adjusted to nearest tick (70,000)
    order_type='limit'
)

if result['success']:
    print(f"Order ID: {result['order_id']}")
    print(f"Executed Price: {result['price']:,} KRW")
```

---

### 3.5 Get Portfolio Balance

**Endpoint**: `/uapi/domestic-stock/v1/trading/inquire-balance`

**Request**:
```http
GET /uapi/domestic-stock/v1/trading/inquire-balance HTTP/1.1
authorization: Bearer {access_token}
appkey: {APP_KEY}
appsecret: {APP_SECRET}
tr_id: TTTC8434R

Query Parameters:
  CANO: 12345678
  ACNT_PRDT_CD: 01
  AFHR_FLPR_YN: N  # After-hours flag
  FNCG_AMT_AUTO_RDPT_YN: N
  FUND_STTL_ICLD_YN: N
  INQR_DVSN: 01
  OFL_YN: N
  PRCS_DVSN: 00
  UNPR_DVSN: 01
  CTX_AREA_FK100: ""
  CTX_AREA_NK100: ""
```

**Response**:
```json
{
  "output1": [
    {
      "pdno": "005930",              // Ticker
      "prdt_name": "삼성전자",         // Stock name
      "hldg_qty": "100",             // Holding quantity
      "pchs_avg_pric": "68000",      // Average purchase price
      "prpr": "70500",               // Current price
      "evlu_pfls_amt": "250000",     // P&L amount
      "evlu_pfls_rt": "3.68"         // P&L percentage
    }
  ],
  "output2": [
    {
      "tot_evlu_amt": "7050000",     // Total evaluation amount
      "pchs_amt_smtl_amt": "6800000", // Total purchase amount
      "evlu_pfls_smtl_amt": "250000", // Total P&L
      "nass_amt": "10000000",        // Net asset
      "fncg_gld_auto_rdpt_yn": "N"
    }
  ]
}
```

**Python Implementation**:
```python
from modules.portfolio_manager import PortfolioManager

pm = PortfolioManager(db)

# Sync portfolio with KIS API
pm.sync_portfolio_from_kis()

# Get current positions
positions = pm.get_current_positions()

for pos in positions:
    print(f"{pos['ticker']}: {pos['quantity']} shares")
    print(f"  Avg Price: {pos['avg_price']:,} KRW")
    print(f"  Current: {pos['current_price']:,} KRW")
    print(f"  P&L: {pos['pnl']:+,.0f} KRW ({pos['pnl_pct']:+.2f}%)")
```

---

## 4. KIS Overseas Stock API (Phase 6)

### 4.1 API Base URL
```
Production: https://openapi.koreainvestment.com:9443
Sandbox:    https://openapivts.koreainvestment.com:29443
```

---

### 4.2 Supported Markets (Exchange Codes)

```yaml
United States:
  NASD: NASDAQ
  NYSE: New York Stock Exchange
  AMEX: American Stock Exchange

Hong Kong:
  SEHK: Hong Kong Stock Exchange

China:
  SHAA: Shanghai A-shares (선강통)
  SZAA: Shenzhen A-shares (후강통)

Japan:
  TKSE: Tokyo Stock Exchange

Vietnam:
  HASE: Ho Chi Minh Stock Exchange
  VNSE: Hanoi Stock Exchange
```

---

### 4.3 Get Daily Price (Overseas OHLCV)

**Endpoint**: `/uapi/overseas-price/v1/quotations/dailyprice`

**Request**:
```http
GET /uapi/overseas-price/v1/quotations/dailyprice HTTP/1.1
authorization: Bearer {access_token}
appkey: {APP_KEY}
appsecret: {APP_SECRET}
tr_id: HHDFS76240000

Query Parameters:
  AUTH: ""
  EXCD: NASD              # Exchange code
  SYMB: AAPL              # Ticker
  GUBN: 0                 # Period (0: Daily, 1: Weekly, 2: Monthly)
  BYMD: 20241018          # End date
  MODP: 1                 # Adjusted price (0: Raw, 1: Adjusted)
```

**Response**:
```json
{
  "output2": [
    {
      "xymd": "20241018",   // Date
      "clos": "150.25",     // Close
      "sign": "2",          // Change sign
      "diff": "1.50",       // Change
      "rate": "1.01",       // Change percentage
      "open": "149.00",     // Open
      "high": "151.00",     // High
      "low": "148.50",      // Low
      "tvol": "50000000"    // Volume
    }
  ],
  "rt_cd": "0"
}
```

**Python Implementation**:
```python
from modules.api_clients import KISOverseasStockAPI

overseas_api = KISOverseasStockAPI(app_key, app_secret)

# Get US stock OHLCV
us_ohlcv = overseas_api.get_daily_price(
    ticker='AAPL',
    exchange='NASD',
    start_date='20240101',
    end_date='20241018',
    adjusted=True
)

# Returns pandas DataFrame:
#       date     open     high      low    close    volume
# 0  2024-01-02  149.00  151.00  148.50  150.25  50000000
# 1  2024-01-03  150.50  152.00  150.00  151.75  45000000
# ...
```

---

### 4.4 Get Current Price (Overseas Real-Time Quote)

**Endpoint**: `/uapi/overseas-price/v1/quotations/price`

**Request**:
```http
GET /uapi/overseas-price/v1/quotations/price HTTP/1.1
authorization: Bearer {access_token}
appkey: {APP_KEY}
appsecret: {APP_SECRET}
tr_id: HHDFS00000300

Query Parameters:
  AUTH: ""
  EXCD: NASD
  SYMB: AAPL
```

**Response**:
```json
{
  "output": {
    "last": "150.25",         // Current price
    "diff": "1.50",           // Change
    "rate": "1.01",           // Change percentage
    "tvol": "50000000",       // Volume
    "t_xprc": "148.75",       // Previous close
    "e_hogau": "151.00",      // High
    "e_hdgau": "148.50"       // Low
  }
}
```

**Python Implementation**:
```python
# Get US stock real-time quote
us_quote = overseas_api.get_current_price('AAPL', exchange='NASD')

print(f"Current Price: ${us_quote['price']:.2f}")
print(f"Change: {us_quote['change']:+.2f}%")
print(f"Volume: {us_quote['volume']:,}")
```

---

### 4.5 Master File Integration

**Purpose**: Download and parse ticker lists for overseas markets

**Master File URLs**:
```yaml
NASD: https://new.real.download.dws.co.kr/common/master/nasdaqlst.cod
NYSE: https://new.real.download.dws.co.kr/common/master/nyselst.cod
AMEX: https://new.real.download.dws.co.kr/common/master/amexlst.cod
SEHK: https://new.real.download.dws.co.kr/common/master/hkexlst.cod
SHAA: https://new.real.download.dws.co.kr/common/master/shanghailstALL.cod
SZAA: https://new.real.download.dws.co.kr/common/master/shenzhenlstALL.cod
TKSE: https://new.real.download.dws.co.kr/common/master/tokyolst.cod
HASE: https://new.real.download.dws.co.kr/common/master/vnlst.cod
```

**File Format**: Binary fixed-width format

**Python Implementation**:
```python
from modules.api_clients import KISMasterFileManager

master_mgr = KISMasterFileManager()

# Download and parse NASDAQ master file
nasdaq_stocks = master_mgr.get_master_data('NASD', force_refresh=True)

# Returns list of dictionaries:
# [
#   {
#     'ticker': 'AAPL',
#     'name': 'Apple Inc.',
#     'market_cap': 2500000000000,
#     'sector': 'Technology'
#   },
#   ...
# ]

# Auto-refresh if cache expired (24-hour TTL)
nyse_stocks = master_mgr.get_master_data('NYSE')  # Uses cache if fresh
```

---

### 4.6 Place Overseas Order

**Endpoint**: `/uapi/overseas-stock/v1/trading/order`

**Request** (US Buy Order):
```http
POST /uapi/overseas-stock/v1/trading/order HTTP/1.1
authorization: Bearer {access_token}
appkey: {APP_KEY}
appsecret: {APP_SECRET}
tr_id: TTTT1002U  # US buy order

Content-Type: application/json
{
  "CANO": "12345678",
  "ACNT_PRDT_CD": "01",
  "OVRS_EXCG_CD": "NASD",    // Exchange code
  "PDNO": "AAPL",            // Ticker
  "ORD_DVSN": "00",          // Order type (00: Limit)
  "ORD_QTY": "10",
  "OVRS_ORD_UNPR": "150.00", // Price in USD
  "ORD_SVR_DVSN_CD": "0"
}
```

**Transaction IDs by Market**:
```yaml
US Buy:    TTTT1002U
US Sell:   TTTT1006U
HK Buy:    TTTT1002H
HK Sell:   TTTT1006H
CN Buy:    TTTT1002C
CN Sell:   TTTT1006C
JP Buy:    TTTT1002J
JP Sell:   TTTT1006J
VN Buy:    TTTT1002V
VN Sell:   TTTT1006V
```

**Python Implementation**:
```python
# Place US buy order
result = engine.execute_buy_order(
    ticker='AAPL',
    exchange='NASD',
    quantity=10,
    price=150.00,
    order_type='limit'
)
```

---

## 5. Rate Limiting & Error Handling

### 5.1 KIS API Rate Limits

```yaml
Request Rate Limits:
  Per Second: 20 requests
  Per Minute: 1,000 requests
  Per Hour: 50,000 requests (estimated)

Token Limits:
  Generation: Once per day
  Expiry: 24 hours
  Refresh: Automatic (when expired)
```

**Rate Limiter Implementation** (`base_kis_api.py`):
```python
class BaseKISAPI:
    def __init__(self, app_key, app_secret):
        self.rate_limiter = RateLimiter(
            max_per_second=20,
            max_per_minute=1000
        )

    def request(self, method, endpoint, **kwargs):
        # Wait if rate limit reached
        self.rate_limiter.wait_if_needed()

        # Make request
        response = requests.request(method, url, **kwargs)

        # Track request count
        self.rate_limiter.increment()

        return response
```

---

### 5.2 Error Codes & Recovery

**Common KIS API Error Codes**:
```yaml
EGW00123: Invalid access token
  Recovery: Regenerate token (auto-recovery)

EGW00124: Rate limit exceeded
  Recovery: Wait 1 second, retry with exponential backoff

EGW00125: Invalid API key/secret
  Recovery: Check credentials, manual intervention

EGW00201: Order rejected (insufficient balance)
  Recovery: Check portfolio balance, reduce order size

EGW00202: Order rejected (invalid price)
  Recovery: Adjust price to nearest tick size

EGW00203: Order rejected (trading halt)
  Recovery: Wait for trading resumption, cancel order
```

**Error Handling Implementation**:
```python
from modules.auto_recovery_system import AutoRecoverySystem

recovery = AutoRecoverySystem(db)

try:
    result = domestic_api.get_daily_price('005930')
except KISAPIError as e:
    if e.code == 'EGW00123':
        # Auto-regenerate token
        recovery.recover_from_error('API_TOKEN_EXPIRED')
    elif e.code == 'EGW00124':
        # Wait and retry
        recovery.recover_from_error('API_RATE_LIMIT')
    else:
        raise
```

---

### 5.3 Exponential Backoff Retry

**Retry Strategy**:
```python
def retry_with_backoff(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except KISAPIError as e:
            if attempt == max_retries - 1:
                raise

            # Exponential backoff: 1s, 2s, 4s
            wait_time = 2 ** attempt
            print(f"Retry {attempt+1}/{max_retries} after {wait_time}s")
            time.sleep(wait_time)

    raise Exception("Max retries exceeded")
```

---

## 6. External APIs

### 6.1 Polygon.io API (US Stocks) - Legacy

**Base URL**: https://api.polygon.io

**API Key Setup**:
```bash
# Add to .env
POLYGON_API_KEY=your_polygon_api_key_here
```

**Rate Limits** (Free Tier):
- 5 requests per minute
- 100 requests per day

**Get Daily Bars**:
```http
GET /v2/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-10-18 HTTP/1.1
Host: api.polygon.io
Authorization: Bearer {POLYGON_API_KEY}
```

**⚠️ Deprecated**: Use `USAdapterKIS` (Phase 6) instead - 240x faster

---

### 6.2 AkShare API (China Stocks) - Legacy

**Installation**:
```bash
pip install akshare
```

**Get Daily Bars**:
```python
import akshare as ak

# Get stock data
df = ak.stock_zh_a_hist(
    symbol='600519',
    period='daily',
    start_date='20240101',
    end_date='20241018',
    adjust='qfq'  # Forward-adjusted
)
```

**Rate Limits**: Self-imposed 1.5 req/sec

**⚠️ Deprecated**: Use `CNAdapterKIS` (Phase 6) instead - 13x faster

---

### 6.3 yfinance API (Global Stocks) - Fallback

**Installation**:
```bash
pip install yfinance
```

**Get Daily Bars**:
```python
import yfinance as yf

# Get stock data
ticker = yf.Ticker('AAPL')
df = ticker.history(period='1y')
```

**Rate Limits**: Self-imposed 1.0 req/sec

**Use Cases**: Fallback when KIS API unavailable

---

## 7. API Comparison Matrix

### 7.1 Performance Comparison

| Market | KIS API | Legacy API | Speedup | Ticker Count |
|--------|---------|------------|---------|--------------|
| **Korea** | 20 req/sec | N/A | N/A | ~2,000 |
| **US** | 20 req/sec | 5 req/min (Polygon) | **240x** | ~3,000 |
| **China** | 20 req/sec | 1.5 req/sec (AkShare) | **13x** | ~300-500 |
| **Hong Kong** | 20 req/sec | 1.0 req/sec (yfinance) | **20x** | ~500-1,000 |
| **Japan** | 20 req/sec | 1.0 req/sec (yfinance) | **20x** | ~500-1,000 |
| **Vietnam** | 20 req/sec | 1.0 req/sec (yfinance) | **20x** | ~100-300 |

---

### 7.2 Feature Comparison

| Feature | KIS API | Polygon | AkShare | yfinance |
|---------|---------|---------|---------|----------|
| **OHLCV Data** | ✅ | ✅ | ✅ | ✅ |
| **Real-Time Quote** | ✅ | ✅ | ✅ | ✅ |
| **Order Execution** | ✅ | ❌ | ❌ | ❌ |
| **Portfolio Balance** | ✅ | ❌ | ❌ | ❌ |
| **API Key Required** | ✅ | ✅ | ❌ | ❌ |
| **Rate Limit** | 20 req/sec | 5 req/min | 1.5 req/sec | 1.0 req/sec |
| **Cost** | Free | Free Tier | Free | Free |
| **Tradable Tickers Only** | ✅ | ❌ | ❌ | ❌ |

---

## 8. Common Workflows

### 8.1 Initial Setup

```bash
# 1. Setup credentials
python3 scripts/setup_credentials.py

# 2. Validate credentials
python3 scripts/validate_kis_credentials.py

# 3. Test connection
python3 scripts/test_kis_connection.py
```

---

### 8.2 Data Collection (US Market)

```python
from modules.market_adapters import USAdapterKIS
from modules.db_manager_sqlite import SQLiteDatabaseManager

# Initialize
db = SQLiteDatabaseManager()
app_key = os.getenv('KIS_APP_KEY')
app_secret = os.getenv('KIS_APP_SECRET')
us_adapter = USAdapterKIS(db, app_key, app_secret)

# Scan tickers (~3,000 stocks, ~3 min)
tickers = us_adapter.scan_stocks(force_refresh=True)

# Collect OHLCV (~750,000 rows, ~5 min)
us_adapter.collect_stock_ohlcv(
    tickers=tickers[:100],  # Start with 100 stocks
    days=250
)
```

---

### 8.3 Order Execution

```python
from modules.kis_trading_engine import KISTradingEngine

# Initialize engine
engine = KISTradingEngine(db, dry_run=False)

# Place buy order
result = engine.execute_buy_order(
    ticker='AAPL',
    exchange='NASD',
    quantity=10,
    price=150.00,
    order_type='limit'
)

if result['success']:
    print(f"✅ Order executed: {result['order_id']}")
else:
    print(f"❌ Order failed: {result['error']}")
```

---

### 8.4 Portfolio Sync

```python
from modules.portfolio_manager import PortfolioManager

# Initialize
pm = PortfolioManager(db)

# Sync portfolio from KIS API
pm.sync_portfolio_from_kis()

# Get positions
positions = pm.get_current_positions()

# Calculate P&L
total_pnl = pm.calculate_total_pnl()
print(f"Total P&L: {total_pnl:+,.0f} KRW")
```

---

## Appendix

### A. KIS API Endpoint Reference

**Domestic Stock API**:
```
/uapi/domestic-stock/v1/quotations/inquire-daily-price
/uapi/domestic-stock/v1/quotations/inquire-price
/uapi/domestic-stock/v1/trading/order-cash
/uapi/domestic-stock/v1/trading/inquire-balance
```

**Overseas Stock API**:
```
/uapi/overseas-price/v1/quotations/dailyprice
/uapi/overseas-price/v1/quotations/price
/uapi/overseas-stock/v1/trading/order
/uapi/overseas-stock/v1/trading/inquire-balance
```

**OAuth**:
```
/oauth2/tokenP
/oauth2/Approval
```

---

### B. Transaction ID Reference

**Domestic (Korea)**:
```
FHKST01010400: Daily price (OHLCV)
FHKST01010100: Current price (real-time)
TTTC0802U: Buy order
TTTC0801U: Sell order
TTTC8434R: Portfolio balance
```

**Overseas (US)**:
```
HHDFS76240000: Daily price (OHLCV)
HHDFS00000300: Current price (real-time)
TTTT1002U: Buy order
TTTT1006U: Sell order
TTTS3012R: Portfolio balance
```

**Overseas (Hong Kong)**:
```
HHDFS76240000: Daily price
HHDFS00000300: Current price
TTTT1002H: Buy order
TTTT1006H: Sell order
```

**Overseas (China)**:
```
HHDFS76240000: Daily price
HHDFS00000300: Current price
TTTT1002C: Buy order
TTTT1006C: Sell order
```

**Overseas (Japan)**:
```
HHDFS76240000: Daily price
HHDFS00000300: Current price
TTTT1002J: Buy order
TTTT1006J: Sell order
```

**Overseas (Vietnam)**:
```
HHDFS76240000: Daily price
HHDFS00000300: Current price
TTTT1002V: Buy order
TTTT1006V: Sell order
```

---

### C. Market Schedule (Trading Hours)

```yaml
Korea (KST):
  Trading: 09:00-15:30 (no lunch break)
  Pre-Market: 08:30-09:00
  After-Market: 15:40-16:00

United States (EST):
  Trading: 09:30-16:00
  Pre-Market: 04:00-09:30
  After-Market: 16:00-20:00

Hong Kong (HKT):
  Trading: 09:30-12:00, 13:00-16:00 (lunch break)
  Pre-Market: 09:00-09:30

China (CST):
  Trading: 09:30-11:30, 13:00-15:00 (lunch break)
  Call Auction: 09:15-09:25

Japan (JST):
  Trading: 09:00-11:30, 12:30-15:00 (lunch break)

Vietnam (ICT):
  Trading: 09:00-11:30, 13:00-15:00 (lunch break)
```

---

### D. Additional Resources

**Official Documentation**:
- KIS API Portal: https://apiportal.koreainvestment.com
- KIS API Guide (Korean): https://wikidocs.net/book/7845

**Community Resources**:
- GitHub Issues: https://github.com/koreainvestment/open-trading-api/issues
- Slack Channel: (Contact KIS for access)

**Spock Documentation**:
- [CLAUDE.md](CLAUDE.md) - Complete project documentation
- [PROJECT_INDEX.md](PROJECT_INDEX.md) - Navigation guide
- [COMPONENT_REFERENCE.md](COMPONENT_REFERENCE.md) - Module documentation

---

**Last Updated**: 2025-10-18
**Maintained By**: Spock Development Team
