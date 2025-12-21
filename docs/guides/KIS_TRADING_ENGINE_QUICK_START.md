# KIS Trading Engine - 3-Day Quick Start Guide

**Objective**: Complete KIS Trading Engine real API integration
**Timeline**: Day 1-3
**Current**: 25% → Target: 100%

---

## 📅 Daily Schedule

### Day 1: OAuth 2.0 Authentication (4-6 hours)

**Goal**: Enable real KIS API token generation

**Tasks**:
1. ✅ Implement `get_access_token()` (line 309) - 90 lines
2. ✅ Add token caching (`_save_token_to_cache()`) - 25 lines
3. ✅ Add cache loading (`_load_token_from_cache()`) - 30 lines
4. ✅ Write 5 authentication tests
5. ✅ Verify with 1 real API call (⚠️ 1/day limit)

**Key Files**:
- `modules/kis_trading_engine.py` (modify)
- `tests/test_kis_authentication_day1.py` (create)

**Verification**:
```bash
python3 tests/test_kis_authentication_day1.py
```

---

### Day 2: Price Query & Buy Order (6-8 hours)

**Goal**: Real-time price retrieval and buy order execution

**Tasks**:
1. ✅ Implement `get_current_price()` (line 332) - 80 lines
2. ✅ Implement `execute_buy_order()` (line 369) - 120 lines
3. ✅ Write price query tests
4. ✅ Write buy order tests (mock mode)
5. ✅ Test with real price API

**Key APIs**:
- `GET /uapi/domestic-stock/v1/quotations/inquire-price`
- `POST /uapi/domestic-stock/v1/trading/order-cash` (BUY)

**Verification**:
```bash
python3 -c "
from modules.kis_trading_engine import KISAPIClient
client = KISAPIClient(..., is_mock=False)
price = client.get_current_price('005930')
print(f'Samsung price: {price:,.0f} KRW')
"
```

---

### Day 3: Sell Order & Testing (4-6 hours)

**Goal**: Sell order execution and end-to-end validation

**Tasks**:
1. ✅ Implement `execute_sell_order()` (line 406) - 120 lines
2. ✅ Add production safety checks - 40 lines
3. ✅ Write end-to-end pipeline test
4. ✅ Run full mock trading cycle (buy → sell)
5. ✅ Document production deployment

**Key API**:
- `POST /uapi/domestic-stock/v1/trading/order-cash` (SELL)

**Verification**:
```bash
python3 tests/test_full_trading_pipeline.py
```

---

## 🔧 Implementation Shortcuts

### Day 1: OAuth Token

**Replace line 309 with**:
```python
def get_access_token(self) -> str:
    # 1. Check cache
    if self.access_token and datetime.now() < self.token_expiry:
        return self.access_token

    # 2. Mock mode
    if self.is_mock:
        self.access_token = f"MOCK_TOKEN_{datetime.now().strftime('%Y%m%d')}"
        self.token_expiry = datetime.now() + timedelta(hours=24)
        return self.access_token

    # 3. Real API call
    url = f"{self.base_url}/oauth2/tokenP"
    response = requests.post(url, json={
        "grant_type": "client_credentials",
        "appkey": self.app_key,
        "appsecret": self.app_secret
    })

    data = response.json()
    self.access_token = data["access_token"]
    self.token_expiry = datetime.now() + timedelta(seconds=data["expires_in"])
    return self.access_token
```

### Day 2: Price Query

**Replace line 332 with**:
```python
def get_current_price(self, ticker: str) -> float:
    if self.is_mock:
        return random.uniform(10000, 100000)

    url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
    response = requests.get(url,
        headers={
            "authorization": f"Bearer {self.get_access_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "FHKST01010100"
        },
        params={
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": ticker
        }
    )

    return float(response.json()["output"]["stck_prpr"])
```

### Day 2: Buy Order

**Replace line 369 with**:
```python
def execute_buy_order(self, ticker: str, quantity: int, price: int, order_type: str = '00') -> Dict:
    if self.is_mock:
        return {
            'success': True,
            'order_id': f"MOCK_BUY_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'avg_price': float(price),
            'quantity': quantity,
            'message': 'Mock order executed'
        }

    cano, acnt_prdt_cd = self.account_no.split('-')

    url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
    response = requests.post(url,
        headers={
            "authorization": f"Bearer {self.get_access_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": "TTTC0802U"  # Mock trading
        },
        json={
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "PDNO": ticker,
            "ORD_DVSN": order_type,
            "ORD_QTY": str(quantity),
            "ORD_UNPR": str(price)
        }
    )

    data = response.json()
    return {
        'success': data["rt_cd"] == "0",
        'order_id': data["output"]["ODNO"],
        'avg_price': float(price),
        'quantity': quantity,
        'message': data["msg1"]
    }
```

### Day 3: Sell Order

**Replace line 406 with**:
```python
def execute_sell_order(self, ticker: str, quantity: int, price: int, order_type: str = '00') -> Dict:
    # Same as buy order, but change tr_id to "TTTC0801U"
    # (Copy implementation from Day 2, modify headers only)
```

---

## ⚡ Quick Test Commands

### Test OAuth (Day 1)
```bash
python3 -c "
import os
from modules.kis_trading_engine import KISAPIClient
client = KISAPIClient(
    app_key=os.getenv('KIS_APP_KEY'),
    app_secret=os.getenv('KIS_APP_SECRET'),
    account_no=os.getenv('KIS_ACCOUNT_NO'),
    is_mock=False
)
token = client.get_access_token()
print(f'✅ Token: {token[:20]}...')
"
```

### Test Price Query (Day 2)
```bash
python3 -c "
import os
from modules.kis_trading_engine import KISAPIClient
client = KISAPIClient(..., is_mock=False)
price = client.get_current_price('005930')
print(f'✅ Samsung: {price:,.0f} KRW')
"
```

### Test Full Pipeline (Day 3)
```bash
python3 -c "
from modules.kis_trading_engine import KISTradingEngine
engine = KISTradingEngine('data/spock_local.db', dry_run=True)

# Buy
buy = engine.execute_buy_order('005930', 100000)
print(f'✅ Buy: {buy.quantity} shares @ {buy.price:,.0f} KRW')

# Sell
sell = engine.execute_sell_order('005930', quantity=buy.quantity)
print(f'✅ Sell: {sell.quantity} shares @ {sell.price:,.0f} KRW')
"
```

---

## 🚨 Critical Warnings

### Token Limit
- ⚠️ **1 token per day per account**
- Test in mock mode first
- Save ONE real token request for final verification

### Production Safety
- Always set `dry_run=True` for testing
- Require `KIS_PRODUCTION_CONFIRMED=YES` in .env for real trading
- Double-check account number and environment

### Rate Limiting
- Max 20 requests/second
- RateLimiter class already implemented
- Don't remove `rate_limiter.wait_if_needed()` calls

---

## 📊 Progress Tracker

**Day 1**:
- [ ] OAuth implementation (90 lines)
- [ ] Token caching (55 lines)
- [ ] 5 authentication tests
- [ ] 1 real API verification

**Day 2**:
- [ ] Price query implementation (80 lines)
- [ ] Buy order implementation (120 lines)
- [ ] Price/buy tests
- [ ] Real price API verification

**Day 3**:
- [ ] Sell order implementation (120 lines)
- [ ] Production safety (40 lines)
- [ ] End-to-end tests
- [ ] Full mock trading cycle

**Total**: ~505 new lines, 4 NotImplementedError fixed, 100% completion

---

## 📚 Reference Documents

**Detailed Design**:
- `docs/KIS_TRADING_ENGINE_DAY1_3_IMPLEMENTATION_DESIGN.md` (full spec)

**API Documentation**:
- `docs/KIS_API_CREDENTIAL_SETUP_GUIDE.md`
- `docs/KIS_TRADING_ENGINE_DESIGN.md`

**Existing Code**:
- `modules/kis_trading_engine.py` (1,195 lines, 80% complete)

---

**Start Date**: 2025-10-20
**Target Completion**: 2025-10-23
**Status**: Ready to implement
