# KIS Trading Engine - Architecture Diagram

**Purpose**: Visual guide for Day 1-3 implementation
**Components**: 4 NotImplementedError fixes with data flow

---

## 🏗️ System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        KISTradingEngine                              │
│  (modules/kis_trading_engine.py - 1,195 lines)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐   │
│  │  Portfolio     │    │  Position      │    │  Risk          │   │
│  │  Manager       │◄──►│  Tracking      │◄──►│  Management    │   │
│  │  (Phase 5)     │    │  (DB: trades)  │    │  (Stop/Profit) │   │
│  └────────────────┘    └────────────────┘    └────────────────┘   │
│         ▲                      ▲                      ▲            │
│         │                      │                      │            │
│         └──────────────────────┼──────────────────────┘            │
│                                │                                    │
│                    ┌───────────▼──────────┐                        │
│                    │   KISAPIClient        │                        │
│                    │  (Lines 265-407)      │                        │
│                    │  ┌─────────────────┐  │                        │
│                    │  │ 4 NotImpl Errors│  │                        │
│                    │  └─────────────────┘  │                        │
│                    └───────────┬───────────┘                        │
│                                │                                    │
└────────────────────────────────┼────────────────────────────────────┘
                                 │
                                 ▼
         ┌───────────────────────────────────────────────────────┐
         │          KIS API Server                                │
         │  (openapi.koreainvestment.com:9443)                    │
         ├───────────────────────────────────────────────────────┤
         │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐│
         │  │  OAuth 2.0   │  │  Price Query │  │  Trading     ││
         │  │  /oauth2     │  │  /quotations │  │  /order-cash ││
         │  │  /tokenP     │  │  /inquire-   │  │  (buy/sell)  ││
         │  │              │  │  price       │  │              ││
         │  └──────────────┘  └──────────────┘  └──────────────┘│
         └───────────────────────────────────────────────────────┘
```

---

## 📋 Day 1: OAuth 2.0 Flow

```
┌──────────────────────────────────────────────────────────────────┐
│  Day 1: OAuth 2.0 Authentication (Line 309)                      │
└──────────────────────────────────────────────────────────────────┘

┌─────────────┐                                   ┌──────────────┐
│  Trading    │                                   │  KIS API     │
│  Engine     │                                   │  Server      │
└──────┬──────┘                                   └──────┬───────┘
       │                                                 │
       │ 1. get_access_token()                          │
       ├─────────────────────────────────────────────►  │
       │    Check cache (token_expiry > now?)           │
       │                                                 │
       │ 2. Cache MISS → Request new token              │
       │    POST /oauth2/tokenP                         │
       │    {grant_type, appkey, appsecret}             │
       ├─────────────────────────────────────────────►  │
       │                                                 │
       │                                 3. Validate     │
       │                                    credentials  │
       │                                                 │
       │ 4. Return access_token (JWT)                   │
       │    {access_token, expires_in: 86400}           │
       │ ◄─────────────────────────────────────────────┤
       │                                                 │
       │ 5. Store token + expiry                        │
       │    self.access_token = "eyJ0eXAi..."           │
       │    self.token_expiry = now + 24h               │
       │                                                 │
       │ 6. Save to cache file                          │
       │    data/.kis_token_cache.json                  │
       │                                                 │
       │ 7. Return token to caller                      │
       │                                                 │
       ▼                                                 ▼

┌─────────────────────────────────────────────────────────────────┐
│  Cache File: data/.kis_token_cache.json                         │
├─────────────────────────────────────────────────────────────────┤
│  {                                                               │
│    "access_token": "eyJ0eXAiOiJKV1QiLCJhbG...",                 │
│    "token_expiry": "2025-10-21T09:00:00",                       │
│    "app_key": "PA1234567890abcdefghij"                          │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘

Token Lifecycle:
├─ Issue: Once per day (1 request/day limit)
├─ Validity: 24 hours
├─ Cache: Reused until expiry
└─ Refresh: Auto-request when expired
```

---

## 📋 Day 2: Price Query & Buy Order Flow

```
┌──────────────────────────────────────────────────────────────────┐
│  Day 2a: Real-Time Price Query (Line 332)                       │
└──────────────────────────────────────────────────────────────────┘

┌─────────────┐                                   ┌──────────────┐
│  Trading    │                                   │  KIS API     │
│  Engine     │                                   │  Server      │
└──────┬──────┘                                   └──────┬───────┘
       │                                                 │
       │ 1. get_current_price("005930")                 │
       │    Validate ticker format (6 digits)           │
       │                                                 │
       │ 2. Get access token                            │
       │    access_token = get_access_token()           │
       │                                                 │
       │ 3. Query price                                 │
       │    GET /quotations/inquire-price               │
       │    Headers: {authorization, appkey, tr_id}     │
       │    Params: {ticker: "005930"}                  │
       ├─────────────────────────────────────────────►  │
       │                                                 │
       │                                 4. Lookup price │
       │                                    in database  │
       │                                                 │
       │ 5. Return price data                           │
       │    {stck_prpr: "71000",                        │
       │     prdy_vrss: "1000",                         │
       │     acml_vol: "1234567"}                       │
       │ ◄─────────────────────────────────────────────┤
       │                                                 │
       │ 6. Parse & return                              │
       │    return float("71000") → 71000.0             │
       │                                                 │
       ▼                                                 ▼


┌──────────────────────────────────────────────────────────────────┐
│  Day 2b: Buy Order Execution (Line 369)                         │
└──────────────────────────────────────────────────────────────────┘

┌─────────────┐                                   ┌──────────────┐
│  Trading    │                                   │  KIS API     │
│  Engine     │                                   │  Server      │
└──────┬──────┘                                   └──────┬───────┘
       │                                                 │
       │ 1. execute_buy_order(ticker, qty, price)       │
       │    Validate inputs (ticker, quantity, price)   │
       │    Adjust price to tick size                   │
       │                                                 │
       │ 2. Get access token                            │
       │    access_token = get_access_token()           │
       │                                                 │
       │ 3. Parse account number                        │
       │    "12345678-01" → CANO="12345678"             │
       │                    ACNT_PRDT_CD="01"           │
       │                                                 │
       │ 4. Submit buy order                            │
       │    POST /trading/order-cash                    │
       │    Headers: {authorization, tr_id: TTTC0802U}  │
       │    Body: {CANO, PDNO, ORD_QTY, ORD_UNPR}       │
       ├─────────────────────────────────────────────►  │
       │                                                 │
       │                             5. Validate order   │
       │                                (balance, limits)│
       │                                                 │
       │                             6. Execute order    │
       │                                (match with      │
       │                                 market)         │
       │                                                 │
       │ 7. Return order confirmation                   │
       │    {rt_cd: "0",                                │
       │     output: {ODNO: "0000123456",               │
       │              ORD_TMD: "121530"}}               │
       │ ◄─────────────────────────────────────────────┤
       │                                                 │
       │ 8. Save trade record to DB                     │
       │    INSERT INTO trades (ticker, entry_price,    │
       │                        quantity, ...)          │
       │                                                 │
       │ 9. Return TradeResult                          │
       │    {success: True,                             │
       │     order_id: "0000123456",                    │
       │     quantity: 10}                              │
       │                                                 │
       ▼                                                 ▼
```

---

## 📋 Day 3: Sell Order & Full Cycle

```
┌──────────────────────────────────────────────────────────────────┐
│  Day 3a: Sell Order Execution (Line 406)                        │
└──────────────────────────────────────────────────────────────────┘

┌─────────────┐                                   ┌──────────────┐
│  Trading    │                                   │  KIS API     │
│  Engine     │                                   │  Server      │
└──────┬──────┘                                   └──────┬───────┘
       │                                                 │
       │ 1. execute_sell_order(ticker, qty, price)      │
       │    Get position from DB                        │
       │    Validate sell quantity ≤ position quantity  │
       │                                                 │
       │ 2. Get access token                            │
       │    access_token = get_access_token()           │
       │                                                 │
       │ 3. Submit sell order                           │
       │    POST /trading/order-cash                    │
       │    Headers: {tr_id: TTTC0801U}  ◄── SELL tr_id │
       │    Body: {CANO, PDNO, ORD_QTY, ORD_UNPR}       │
       ├─────────────────────────────────────────────►  │
       │                                                 │
       │ 4. Return order confirmation                   │
       │    {rt_cd: "0", output: {ODNO: "..."}}         │
       │ ◄─────────────────────────────────────────────┤
       │                                                 │
       │ 5. Calculate P&L                               │
       │    pnl = (exit_price - entry_price) * qty      │
       │    pnl_percent = (exit_price/entry_price-1)*100│
       │                                                 │
       │ 6. Update trade record                         │
       │    UPDATE trades SET                           │
       │      exit_price = ?,                           │
       │      trade_status = 'CLOSED'                   │
       │    WHERE ticker = ? AND trade_status = 'OPEN'  │
       │                                                 │
       │ 7. Return TradeResult with P&L                 │
       │                                                 │
       ▼                                                 ▼


┌──────────────────────────────────────────────────────────────────┐
│  Day 3b: Full Trading Cycle (End-to-End Test)                   │
└──────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────┐
    │ 1. Get Current Price                                 │
    │    price = get_current_price("005930") → 71,000 KRW │
    └─────────────────┬───────────────────────────────────┘
                      │
    ┌─────────────────▼───────────────────────────────────┐
    │ 2. Execute Buy Order                                 │
    │    buy_result = execute_buy_order(                   │
    │        ticker="005930",                              │
    │        amount_krw=100000                             │
    │    )                                                 │
    │    → Bought 1 share @ 71,000 KRW                     │
    └─────────────────┬───────────────────────────────────┘
                      │
    ┌─────────────────▼───────────────────────────────────┐
    │ 3. Verify Position                                   │
    │    positions = get_current_positions()               │
    │    → 1 position found: 005930, qty=1                 │
    └─────────────────┬───────────────────────────────────┘
                      │
    ┌─────────────────▼───────────────────────────────────┐
    │ 4. Wait / Monitor (Optional)                         │
    │    price_now = get_current_price("005930")           │
    │    → 72,000 KRW (up 1.4%)                            │
    └─────────────────┬───────────────────────────────────┘
                      │
    ┌─────────────────▼───────────────────────────────────┐
    │ 5. Execute Sell Order                                │
    │    sell_result = execute_sell_order(                 │
    │        ticker="005930",                              │
    │        quantity=1,                                   │
    │        reason="take_profit"                          │
    │    )                                                 │
    │    → Sold 1 share @ 72,000 KRW                       │
    │    → P&L: +1,000 KRW (+1.4%)                         │
    └─────────────────┬───────────────────────────────────┘
                      │
    ┌─────────────────▼───────────────────────────────────┐
    │ 6. Verify Closed Position                            │
    │    positions = get_current_positions()               │
    │    → 0 positions (trade closed successfully)         │
    └──────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow Diagram

```
┌───────────────────────────────────────────────────────────────────┐
│                        Data Flow Overview                          │
└───────────────────────────────────────────────────────────────────┘

Environment Variables (.env)
├─ KIS_APP_KEY
├─ KIS_APP_SECRET
└─ KIS_ACCOUNT_NO
         │
         ▼
┌────────────────────┐
│  KISAPIClient      │
│  __init__()        │
└────────┬───────────┘
         │
         ├─► (Day 1) get_access_token()
         │            ├─► POST /oauth2/tokenP
         │            └─► Cache: .kis_token_cache.json
         │
         ├─► (Day 2a) get_current_price()
         │            ├─► GET /quotations/inquire-price
         │            └─► Return: float (price in KRW)
         │
         ├─► (Day 2b) execute_buy_order()
         │            ├─► POST /trading/order-cash (BUY)
         │            └─► Return: {order_id, quantity, price}
         │
         └─► (Day 3) execute_sell_order()
                      ├─► POST /trading/order-cash (SELL)
                      └─► Return: {order_id, quantity, price}
                               │
                               ▼
                      ┌────────────────────┐
                      │  SQLite Database   │
                      │  (trades table)    │
                      ├────────────────────┤
                      │ INSERT (buy)       │
                      │ UPDATE (sell)      │
                      │ SELECT (positions) │
                      └────────────────────┘
```

---

## 🛡️ Error Handling Flow

```
┌───────────────────────────────────────────────────────────────────┐
│                     Error Handling Strategy                        │
└───────────────────────────────────────────────────────────────────┘

API Call
   │
   ├─► HTTP 200 OK
   │   └─► Parse JSON → Return data
   │
   ├─► HTTP 401 Unauthorized
   │   └─► Token expired → get_access_token() → Retry
   │
   ├─► HTTP 403 Forbidden
   │   └─► Invalid credentials → Raise ValueError
   │
   ├─► HTTP 429 Too Many Requests
   │   └─► Rate limit exceeded → Wait 60s → Retry
   │
   ├─► HTTP 500 Server Error
   │   └─► KIS API down → Log error → Raise HTTPError
   │
   ├─► Timeout (>10s)
   │   └─► Network issue → Log error → Raise Timeout
   │
   └─► Connection Error
       └─► Cannot reach API → Log error → Raise RequestException

All errors:
├─► Log to logger.error()
├─► Return TradeResult(success=False, message=error_msg)
└─► Preserve error context for debugging
```

---

## 📊 Testing Pyramid

```
┌───────────────────────────────────────────────────────────────────┐
│                          Testing Strategy                          │
└───────────────────────────────────────────────────────────────────┘

                         ┌────────────────┐
                         │  Integration   │  ← Day 3: E2E Test
                         │  Tests (1)     │    (buy → sell cycle)
                         └────────┬───────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │     API Tests (7)          │  ← Day 1-3:
                    │  - OAuth (2 tests)         │    Real API calls
                    │  - Price (2 tests)         │    (mock + real)
                    │  - Buy (2 tests)           │
                    │  - Sell (1 test)           │
                    └─────────────┬──────────────┘
                                  │
            ┌─────────────────────▼─────────────────────┐
            │          Unit Tests (15)                   │  ← Existing:
            │  - Tick size (3 tests)                     │    Helper
            │  - Fee calculation (3 tests)               │    functions
            │  - Rate limiter (3 tests)                  │
            │  - Input validation (3 tests)              │
            │  - Token caching (3 tests)                 │
            └────────────────────────────────────────────┘

Total Tests: 23 tests (15 existing + 7 new + 1 integration)
```

---

## 🎯 Success Criteria

**Day 1**:
- ✅ Real OAuth token obtained
- ✅ Token cached successfully
- ✅ 2/2 authentication tests pass

**Day 2**:
- ✅ Real price query returns valid data
- ✅ Mock buy order executes without error
- ✅ 4/4 price & buy tests pass

**Day 3**:
- ✅ Mock sell order executes without error
- ✅ Full buy → sell cycle completes
- ✅ 1/1 integration test passes
- ✅ 0 NotImplementedError remaining

**Overall**:
- ✅ 7/7 new tests pass
- ✅ 23/23 total tests pass
- ✅ Production-ready code (with safety checks)

---

**Document Version**: 1.0
**Created**: 2025-10-20
**Purpose**: Visual guide for KIS Trading Engine implementation
