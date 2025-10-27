# KIS Trading Engine - Day 1-3 Implementation Design

**Date**: 2025-10-20
**Task**: Complete KIS Trading Engine (4 NotImplementedError fixes)
**Timeline**: 3 days
**Current Status**: 25% Complete → 100% Complete

---

## 📋 Executive Summary

### Current State Analysis
**File**: `modules/kis_trading_engine.py` (1,195 lines, 80% complete)

**✅ Completed Features**:
- Tick size compliance (lines 57-188)
- Fee calculation (lines 191-221)
- Rate limiter (lines 228-258)
- Mock API client (lines 265-407)
- Position tracking (lines 856-925)
- Stop loss/take profit logic (lines 927-950)
- Portfolio management (lines 952-1003)
- Database operations (lines 1009-1170)
- Lot size handling (lines 470-533)
- Blacklist integration (lines 567-579)

**❌ 4 NotImplementedError Locations**:
1. **Line 309**: `_get_access_token()` - OAuth 2.0 authentication
2. **Line 332**: `get_current_price()` - Real-time price query
3. **Line 369**: `execute_buy_order()` - Buy order execution
4. **Line 406**: `execute_sell_order()` - Sell order execution

**Critical Gap**: System can only run in **dry_run=True** mode (mock trading). Real trading is blocked.

---

## 🎯 3-Day Implementation Plan

### Day 1: OAuth 2.0 Authentication (Lines 306-309)
**Objective**: Enable real KIS API authentication
**Estimated Time**: 4-6 hours
**Complexity**: Medium (API integration)

### Day 2: Price Query & Buy Order (Lines 332, 369)
**Objective**: Real-time price retrieval and buy order execution
**Estimated Time**: 6-8 hours
**Complexity**: High (order validation, error handling)

### Day 3: Sell Order & Integration Testing (Line 406)
**Objective**: Sell order execution and end-to-end testing
**Estimated Time**: 4-6 hours
**Complexity**: Medium (similar to buy order)

---

## 🔧 Day 1: OAuth 2.0 Authentication Implementation

### 1.1 Design Specification

**API Endpoint**:
```
POST https://openapi.koreainvestment.com:9443/oauth2/tokenP
```

**Request Format**:
```json
{
    "grant_type": "client_credentials",
    "appkey": "{KIS_APP_KEY}",
    "appsecret": "{KIS_APP_SECRET}"
}
```

**Response Format**:
```json
{
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbG...",
    "access_token_token_expired": "2025-10-21 09:00:00",
    "token_type": "Bearer",
    "expires_in": 86400
}
```

**Token Lifecycle**:
- **Validity**: 24 hours (86,400 seconds)
- **Issuance Limit**: 1 per day per account
- **Auto-Refresh**: Not supported (must re-issue next day)

### 1.2 Implementation Code

**Location**: `modules/kis_trading_engine.py:290-309`

```python
def get_access_token(self) -> str:
    """
    Access token 발급 (24시간 유효)

    KIS API OAuth 2.0 인증
    - Endpoint: POST /oauth2/tokenP
    - Rate Limit: 1 request/day
    - Token Validity: 24 hours

    Returns:
        Access token (JWT format)

    Raises:
        requests.HTTPError: API request failed
        ValueError: Invalid credentials
    """
    # 1. Check if existing token is still valid
    if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
        logger.info(f"✅ Using cached access token (expires: {self.token_expiry})")
        return self.access_token

    # 2. Mock mode fallback
    if self.is_mock:
        self.access_token = f"MOCK_TOKEN_{datetime.now().strftime('%Y%m%d')}"
        self.token_expiry = datetime.now() + timedelta(hours=24)
        logger.info("✅ Mock access token generated")
        return self.access_token

    # 3. Real OAuth 2.0 token request
    logger.info("🔐 Requesting new KIS API access token...")

    try:
        # 3a. Prepare request
        url = f"{self.base_url}/oauth2/tokenP"
        headers = {
            "content-type": "application/json; charset=utf-8"
        }
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }

        # 3b. Send POST request
        response = requests.post(url, headers=headers, json=body, timeout=10)

        # 3c. Handle errors
        if response.status_code != 200:
            error_msg = f"Token request failed: {response.status_code} - {response.text}"
            logger.error(f"❌ {error_msg}")
            raise requests.HTTPError(error_msg)

        # 3d. Parse response
        data = response.json()

        if "access_token" not in data:
            error_msg = f"Invalid response: {data}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        # 3e. Store token and expiry
        self.access_token = data["access_token"]
        expires_in = data.get("expires_in", 86400)  # Default 24 hours
        self.token_expiry = datetime.now() + timedelta(seconds=expires_in)

        logger.info(f"✅ Access token obtained successfully")
        logger.info(f"   Token type: {data.get('token_type', 'Bearer')}")
        logger.info(f"   Expires at: {self.token_expiry}")

        # 3f. Optional: Save token to cache file (for 24-hour reuse)
        self._save_token_to_cache()

        return self.access_token

    except requests.exceptions.Timeout:
        logger.error("❌ Token request timed out (>10s)")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Token request failed: {e}")
        raise
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"❌ Failed to parse token response: {e}")
        raise


def _save_token_to_cache(self):
    """
    Save access token to cache file for 24-hour reuse

    File: data/.kis_token_cache.json
    Format: {
        "access_token": "eyJ0eXAi...",
        "token_expiry": "2025-10-21 09:00:00",
        "app_key": "PA12..." (for validation)
    }
    """
    try:
        cache_file = os.path.join(os.path.dirname(self.db_path), ".kis_token_cache.json")

        cache_data = {
            "access_token": self.access_token,
            "token_expiry": self.token_expiry.isoformat(),
            "app_key": self.app_key  # For validation
        }

        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)

        logger.debug(f"💾 Token cached to {cache_file}")

    except Exception as e:
        logger.warning(f"⚠️  Failed to cache token: {e}")


def _load_token_from_cache(self):
    """
    Load cached access token if still valid

    Returns:
        True if cached token loaded successfully
    """
    try:
        cache_file = os.path.join(os.path.dirname(self.db_path), ".kis_token_cache.json")

        if not os.path.exists(cache_file):
            return False

        with open(cache_file, 'r') as f:
            cache_data = json.load(f)

        # Validate cache
        if cache_data.get("app_key") != self.app_key:
            logger.warning("⚠️  Cached token belongs to different app_key")
            return False

        # Check expiry
        token_expiry = datetime.fromisoformat(cache_data["token_expiry"])
        if datetime.now() >= token_expiry:
            logger.debug("⏰ Cached token expired")
            return False

        # Load token
        self.access_token = cache_data["access_token"]
        self.token_expiry = token_expiry

        logger.info(f"✅ Loaded cached token (expires: {self.token_expiry})")
        return True

    except Exception as e:
        logger.warning(f"⚠️  Failed to load cached token: {e}")
        return False
```

### 1.3 Constructor Modification

**Add token cache loading to `__init__`**:

```python
def __init__(self, app_key: str, app_secret: str, account_no: str, base_url: str = None, is_mock: bool = True):
    self.app_key = app_key
    self.app_secret = app_secret
    self.account_no = account_no
    self.is_mock = is_mock

    # ... existing code ...

    # NEW: Try to load cached token
    if not is_mock:
        self._load_token_from_cache()
```

### 1.4 Testing Strategy

**Test Cases**:
1. ✅ **Token Generation Success**: Valid credentials → token received
2. ✅ **Token Caching**: Second call uses cached token (no API call)
3. ✅ **Token Expiry**: Expired cached token → new token requested
4. ❌ **Invalid Credentials**: Wrong app_key/secret → HTTPError
5. ❌ **Network Error**: Timeout/connection failure → requests.RequestException
6. ❌ **Rate Limit**: >1 request/day → 429 Too Many Requests

**Test Script**:
```bash
# Create test file
cat > tests/test_kis_authentication_day1.py << 'EOF'
#!/usr/bin/env python3
"""
KIS API Authentication Tests (Day 1)
"""
import os
import sys
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from modules.kis_trading_engine import KISAPIClient


def test_token_generation_success():
    """Test successful token generation"""
    client = KISAPIClient(
        app_key=os.getenv("KIS_APP_KEY"),
        app_secret=os.getenv("KIS_APP_SECRET"),
        account_no=os.getenv("KIS_ACCOUNT_NO"),
        is_mock=False
    )

    token = client.get_access_token()

    assert token is not None
    assert len(token) > 100  # JWT tokens are long
    assert client.token_expiry > datetime.now()
    print(f"✅ Token: {token[:20]}...")
    print(f"✅ Expires: {client.token_expiry}")


def test_token_caching():
    """Test token caching (no duplicate API calls)"""
    client = KISAPIClient(
        app_key=os.getenv("KIS_APP_KEY"),
        app_secret=os.getenv("KIS_APP_SECRET"),
        account_no=os.getenv("KIS_ACCOUNT_NO"),
        is_mock=False
    )

    # First call
    token1 = client.get_access_token()

    # Second call (should use cache)
    with patch('requests.post') as mock_post:
        token2 = client.get_access_token()
        mock_post.assert_not_called()  # No API call

    assert token1 == token2
    print("✅ Token caching works")


def test_invalid_credentials():
    """Test invalid credentials handling"""
    client = KISAPIClient(
        app_key="INVALID_KEY",
        app_secret="INVALID_SECRET",
        account_no="00000000-00",
        is_mock=False
    )

    with pytest.raises(requests.HTTPError):
        client.get_access_token()

    print("✅ Invalid credentials rejected")


def test_mock_mode():
    """Test mock mode token generation"""
    client = KISAPIClient(
        app_key="MOCK",
        app_secret="MOCK",
        account_no="MOCK",
        is_mock=True
    )

    token = client.get_access_token()

    assert token.startswith("MOCK_TOKEN_")
    assert client.token_expiry > datetime.now()
    print(f"✅ Mock token: {token}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
EOF

# Run tests
python3 tests/test_kis_authentication_day1.py
```

### 1.5 Day 1 Deliverables

- [ ] **Code**: `get_access_token()` implementation (90 lines)
- [ ] **Code**: `_save_token_to_cache()` helper (25 lines)
- [ ] **Code**: `_load_token_from_cache()` helper (30 lines)
- [ ] **Tests**: 5 test cases in `test_kis_authentication_day1.py`
- [ ] **Documentation**: Update `KIS_API_CREDENTIAL_SETUP_GUIDE.md` with token caching section
- [ ] **Verification**: Real API call with actual credentials (⚠️ 1 token/day limit)

**Success Criteria**:
- ✅ Token successfully generated with real credentials
- ✅ Token cached and reused for 24 hours
- ✅ All 5 test cases pass
- ✅ No more NotImplementedError at line 309

---

## 🔧 Day 2: Real-Time Price Query & Buy Order

### 2.1 Price Query Implementation (Line 332)

**API Endpoint**:
```
GET /uapi/domestic-stock/v1/quotations/inquire-price
```

**Headers**:
```
authorization: Bearer {access_token}
appkey: {app_key}
appsecret: {app_secret}
tr_id: FHKST01010100
```

**Query Parameters**:
```
FID_COND_MRKT_DIV_CODE: J (KOSPI/KOSDAQ)
FID_INPUT_ISCD: {ticker} (6-digit stock code)
```

**Response**:
```json
{
    "output": {
        "stck_prpr": "71000",  // 현재가 (current price)
        "prdy_vrss": "1000",   // 전일대비 (change from previous day)
        "prdy_vrss_sign": "2", // 등락 기호 (1:상한, 2:상승, 3:보합, 4:하한, 5:하락)
        "prdy_ctrt": "1.43",   // 전일대비율 (change rate %)
        "stck_oprc": "70000",  // 시가 (open)
        "stck_hgpr": "71500",  // 고가 (high)
        "stck_lwpr": "69800",  // 저가 (low)
        "acml_vol": "1234567", // 거래량 (volume)
        "acml_tr_pbmn": "87654321000"  // 거래대금 (trading value)
    }
}
```

**Implementation**:

```python
def get_current_price(self, ticker: str) -> float:
    """
    현재가 조회

    Args:
        ticker: 종목코드 (6자리, e.g., "005930")

    Returns:
        현재가 (float, KRW)

    Raises:
        requests.HTTPError: API request failed
        ValueError: Invalid ticker or response
    """
    self.rate_limiter.wait_if_needed()

    # 1. Mock mode fallback
    if self.is_mock:
        import random
        mock_price = random.uniform(10000, 100000)
        logger.debug(f"Mock price for {ticker}: {mock_price:.0f} KRW")
        return mock_price

    # 2. Validate ticker format
    if not ticker or len(ticker) != 6 or not ticker.isdigit():
        raise ValueError(f"Invalid ticker format: {ticker} (expected 6-digit number)")

    # 3. Ensure we have access token
    access_token = self.get_access_token()

    # 4. Prepare API request
    url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": self.app_key,
        "appsecret": self.app_secret,
        "tr_id": "FHKST01010100"
    }

    params = {
        "FID_COND_MRKT_DIV_CODE": "J",  # KOSPI/KOSDAQ
        "FID_INPUT_ISCD": ticker
    }

    # 5. Send GET request
    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)

        # 6. Handle errors
        if response.status_code != 200:
            error_msg = f"Price query failed: {response.status_code} - {response.text}"
            logger.error(f"❌ {error_msg}")
            raise requests.HTTPError(error_msg)

        # 7. Parse response
        data = response.json()

        if "output" not in data or "stck_prpr" not in data["output"]:
            error_msg = f"Invalid response format: {data}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        # 8. Extract current price
        current_price = float(data["output"]["stck_prpr"])

        # 9. Log additional info (optional)
        change = data["output"].get("prdy_vrss", "N/A")
        change_rate = data["output"].get("prdy_ctrt", "N/A")
        volume = data["output"].get("acml_vol", "N/A")

        logger.debug(f"📈 [{ticker}] Price: {current_price:,.0f} KRW (Change: {change} KRW, {change_rate}%, Vol: {volume})")

        return current_price

    except requests.exceptions.Timeout:
        logger.error(f"❌ Price query timed out for {ticker}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Price query failed for {ticker}: {e}")
        raise
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"❌ Failed to parse price response for {ticker}: {e}")
        raise
```

### 2.2 Buy Order Implementation (Line 369)

**API Endpoint**:
```
POST /uapi/domestic-stock/v1/trading/order-cash
```

**Headers**:
```
authorization: Bearer {access_token}
appkey: {app_key}
appsecret: {app_secret}
tr_id: TTTC0802U (모의투자) or VTTC0802U (실전투자)
```

**Body**:
```json
{
    "CANO": "12345678",          // 계좌번호 앞 8자리
    "ACNT_PRDT_CD": "01",        // 계좌번호 뒤 2자리
    "PDNO": "005930",            // 종목코드
    "ORD_DVSN": "00",            // 주문구분 (00:지정가, 01:시장가)
    "ORD_QTY": "10",             // 주문수량
    "ORD_UNPR": "71000"          // 주문단가 (지정가 시)
}
```

**Response**:
```json
{
    "rt_cd": "0",                // Return code (0:success)
    "msg_cd": "MCA00000",        // Message code
    "msg1": "정상처리 되었습니다",
    "output": {
        "KRX_FWDG_ORD_ORGNO": "91252",    // 주문조직번호
        "ODNO": "0000123456",             // 주문번호
        "ORD_TMD": "121530"               // 주문시각
    }
}
```

**Implementation**:

```python
def execute_buy_order(self, ticker: str, quantity: int, price: int, order_type: str = '00') -> Dict:
    """
    매수 주문 실행

    Args:
        ticker: 종목코드 (6자리)
        quantity: 주문 수량
        price: 주문 가격 (tick size adjusted, KRW)
        order_type: 주문 구분 (00:지정가, 01:시장가)

    Returns:
        {
            'success': bool,
            'order_id': str,
            'avg_price': float,
            'quantity': int,
            'message': str
        }

    Raises:
        requests.HTTPError: API request failed
        ValueError: Invalid parameters
    """
    self.rate_limiter.wait_if_needed()

    # 1. Mock mode fallback
    if self.is_mock:
        order_id = f"MOCK_BUY_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        logger.info(f"✅ Mock buy order: {ticker} x {quantity} @ {price} KRW")
        return {
            'success': True,
            'order_id': order_id,
            'avg_price': float(price),
            'quantity': quantity,
            'message': 'Mock order executed successfully'
        }

    # 2. Validate inputs
    if not ticker or len(ticker) != 6 or not ticker.isdigit():
        raise ValueError(f"Invalid ticker: {ticker}")
    if quantity <= 0:
        raise ValueError(f"Invalid quantity: {quantity}")
    if price <= 0:
        raise ValueError(f"Invalid price: {price}")
    if order_type not in ['00', '01']:
        raise ValueError(f"Invalid order_type: {order_type} (expected '00' or '01')")

    # 3. Parse account number (format: "12345678-01")
    if '-' in self.account_no:
        cano, acnt_prdt_cd = self.account_no.split('-')
    else:
        # Assume last 2 digits are product code
        cano = self.account_no[:-2]
        acnt_prdt_cd = self.account_no[-2:]

    # 4. Ensure we have access token
    access_token = self.get_access_token()

    # 5. Prepare API request
    url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": self.app_key,
        "appsecret": self.app_secret,
        "tr_id": "TTTC0802U"  # 모의투자 (change to VTTC0802U for real trading)
    }

    body = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "PDNO": ticker,
        "ORD_DVSN": order_type,
        "ORD_QTY": str(quantity),
        "ORD_UNPR": str(price) if order_type == '00' else "0"  # 시장가는 0
    }

    # 6. Send POST request
    try:
        logger.info(f"🛒 Placing BUY order: {ticker} x {quantity} @ {price} KRW")

        response = requests.post(url, headers=headers, json=body, timeout=10)

        # 7. Handle errors
        if response.status_code != 200:
            error_msg = f"Buy order failed: {response.status_code} - {response.text}"
            logger.error(f"❌ {error_msg}")
            raise requests.HTTPError(error_msg)

        # 8. Parse response
        data = response.json()

        # Check return code
        if data.get("rt_cd") != "0":
            error_msg = f"Order rejected: {data.get('msg1', 'Unknown error')}"
            logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'order_id': None,
                'avg_price': 0.0,
                'quantity': 0,
                'message': error_msg
            }

        # 9. Extract order info
        output = data.get("output", {})
        order_id = output.get("ODNO", "UNKNOWN")
        order_time = output.get("ORD_TMD", "UNKNOWN")

        logger.info(f"✅ BUY order placed successfully")
        logger.info(f"   Order ID: {order_id}")
        logger.info(f"   Order Time: {order_time}")
        logger.info(f"   Message: {data.get('msg1', 'N/A')}")

        return {
            'success': True,
            'order_id': order_id,
            'avg_price': float(price),  # Assuming full fill at order price
            'quantity': quantity,
            'message': data.get('msg1', 'Order executed successfully')
        }

    except requests.exceptions.Timeout:
        logger.error(f"❌ Buy order timed out for {ticker}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Buy order failed for {ticker}: {e}")
        raise
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"❌ Failed to parse buy order response: {e}")
        raise
```

### 2.3 Day 2 Testing

**Test Script**:
```python
#!/usr/bin/env python3
"""
KIS API Price & Buy Order Tests (Day 2)
"""

def test_get_current_price():
    """Test real-time price query"""
    client = KISAPIClient(
        app_key=os.getenv("KIS_APP_KEY"),
        app_secret=os.getenv("KIS_APP_SECRET"),
        account_no=os.getenv("KIS_ACCOUNT_NO"),
        is_mock=False
    )

    # Test with Samsung Electronics (005930)
    price = client.get_current_price("005930")

    assert price > 0
    assert 50000 <= price <= 100000  # Reasonable range
    print(f"✅ Samsung price: {price:,.0f} KRW")


def test_execute_buy_order_dry_run():
    """Test buy order (mock mode)"""
    engine = KISTradingEngine(
        db_path="data/spock_local.db",
        dry_run=True
    )

    result = engine.execute_buy_order(
        ticker="005930",
        amount_krw=100000  # 10만원
    )

    assert result.success
    assert result.quantity > 0
    print(f"✅ Mock buy: {result.quantity} shares @ {result.price:,.0f} KRW")
```

### 2.4 Day 2 Deliverables

- [ ] **Code**: `get_current_price()` implementation (80 lines)
- [ ] **Code**: `execute_buy_order()` implementation (120 lines)
- [ ] **Tests**: Price query test
- [ ] **Tests**: Buy order test (mock mode)
- [ ] **Verification**: Real price query with actual credentials
- [ ] **Warning**: Add safety check for real vs mock trading mode

---

## 🔧 Day 3: Sell Order & Integration Testing

### 3.1 Sell Order Implementation (Line 406)

**API Endpoint** (same as buy, different tr_id):
```
POST /uapi/domestic-stock/v1/trading/order-cash
```

**Headers**:
```
tr_id: TTTC0801U (모의투자) or VTTC0801U (실전투자)
```

**Body** (same structure):
```json
{
    "CANO": "12345678",
    "ACNT_PRDT_CD": "01",
    "PDNO": "005930",
    "ORD_DVSN": "00",
    "ORD_QTY": "10",
    "ORD_UNPR": "72000"
}
```

**Implementation** (similar to buy order):

```python
def execute_sell_order(self, ticker: str, quantity: int, price: int, order_type: str = '00') -> Dict:
    """
    매도 주문 실행

    Args:
        ticker: 종목코드 (6자리)
        quantity: 주문 수량
        price: 주문 가격 (tick size adjusted)
        order_type: 주문 구분 (00:지정가, 01:시장가)

    Returns:
        Same as execute_buy_order()
    """
    self.rate_limiter.wait_if_needed()

    # 1. Mock mode fallback
    if self.is_mock:
        order_id = f"MOCK_SELL_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        logger.info(f"✅ Mock sell order: {ticker} x {quantity} @ {price} KRW")
        return {
            'success': True,
            'order_id': order_id,
            'avg_price': float(price),
            'quantity': quantity,
            'message': 'Mock order executed successfully'
        }

    # 2-5: Same validation and setup as buy order
    # ...

    # 6. KEY DIFFERENCE: tr_id for sell
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": self.app_key,
        "appsecret": self.app_secret,
        "tr_id": "TTTC0801U"  # 모의투자 SELL (vs TTTC0802U for BUY)
    }

    # 7-9: Same request handling as buy order
    # ...
```

### 3.2 End-to-End Integration Test

**Full Pipeline Test**:
```python
def test_full_trading_pipeline():
    """
    Test complete trading workflow:
    1. Get price
    2. Place buy order
    3. Verify position
    4. Place sell order
    5. Verify P&L
    """
    engine = KISTradingEngine(
        db_path="data/spock_test.db",
        dry_run=True  # MOCK MODE for safety
    )

    ticker = "005930"

    # 1. Get current price
    price = engine.kis_client.get_current_price(ticker)
    logger.info(f"Current price: {price:,.0f} KRW")

    # 2. Buy order
    buy_result = engine.execute_buy_order(
        ticker=ticker,
        amount_krw=100000,
        sector="Technology",
        region="KR"
    )
    assert buy_result.success
    logger.info(f"✅ Bought {buy_result.quantity} shares @ {buy_result.price:,.0f} KRW")

    # 3. Check position
    positions = engine.get_current_positions()
    assert len(positions) == 1
    assert positions[0].ticker == ticker
    logger.info(f"✅ Position verified: {positions[0].quantity} shares")

    # 4. Sell order
    sell_result = engine.execute_sell_order(
        ticker=ticker,
        quantity=positions[0].quantity,
        reason="take_profit",
        region="KR"
    )
    assert sell_result.success
    logger.info(f"✅ Sold {sell_result.quantity} shares @ {sell_result.price:,.0f} KRW")

    # 5. Verify closed position
    positions_after = engine.get_current_positions()
    assert len(positions_after) == 0
    logger.info("✅ Position closed successfully")
```

### 3.3 Safety Checks & Production Readiness

**Environment Variable Validation**:
```python
def _validate_production_mode(self):
    """
    Validate configuration before real trading

    Raises:
        ValueError: Missing or invalid configuration
    """
    if not self.is_mock:
        # Check credentials
        if not self.app_key or self.app_key == "MOCK_KEY":
            raise ValueError("Missing KIS_APP_KEY for production mode")
        if not self.app_secret or self.app_secret == "MOCK_SECRET":
            raise ValueError("Missing KIS_APP_SECRET for production mode")
        if not self.account_no or self.account_no == "MOCK_ACCOUNT":
            raise ValueError("Missing KIS_ACCOUNT_NO for production mode")

        # Warn about real trading
        logger.warning("=" * 70)
        logger.warning("⚠️  PRODUCTION MODE ENABLED - REAL MONEY TRADING ⚠️")
        logger.warning("   All orders will be executed with real money")
        logger.warning("   Make sure you understand the risks")
        logger.warning("=" * 70)

        # Optional: Require explicit confirmation
        if os.getenv("KIS_PRODUCTION_CONFIRMED") != "YES":
            raise ValueError(
                "Production mode requires KIS_PRODUCTION_CONFIRMED=YES in .env"
            )
```

### 3.4 Day 3 Deliverables

- [ ] **Code**: `execute_sell_order()` implementation (120 lines)
- [ ] **Code**: Production mode validation (~40 lines)
- [ ] **Tests**: End-to-end pipeline test
- [ ] **Tests**: Safety check tests
- [ ] **Documentation**: Production deployment guide
- [ ] **Verification**: Full mock trading cycle (buy → hold → sell)

---

## ✅ Completion Checklist

### Code Changes
- [ ] Line 309: `get_access_token()` - REAL implementation (90 lines)
- [ ] Line 332: `get_current_price()` - REAL implementation (80 lines)
- [ ] Line 369: `execute_buy_order()` - REAL implementation (120 lines)
- [ ] Line 406: `execute_sell_order()` - REAL implementation (120 lines)
- [ ] New: `_save_token_to_cache()` helper (25 lines)
- [ ] New: `_load_token_from_cache()` helper (30 lines)
- [ ] New: `_validate_production_mode()` safety check (40 lines)

### Testing
- [ ] OAuth 2.0 authentication test
- [ ] Token caching test
- [ ] Price query test
- [ ] Buy order test (mock)
- [ ] Sell order test (mock)
- [ ] End-to-end pipeline test
- [ ] Production safety checks test

### Documentation
- [ ] Update `KIS_TRADING_ENGINE_DESIGN.md`
- [ ] Update `KIS_API_CREDENTIAL_SETUP_GUIDE.md`
- [ ] Create `PRODUCTION_DEPLOYMENT_CHECKLIST.md`
- [ ] Add API error code reference

### Verification
- [ ] Real OAuth 2.0 token obtained (⚠️ 1/day limit)
- [ ] Real price query successful
- [ ] Mock trading cycle complete (buy → sell)
- [ ] No NotImplementedError remaining
- [ ] All tests pass (7/7)

---

## 🚨 Critical Warnings

### ⚠️ Token Issuance Limit
- **Limit**: 1 token per day per account
- **Impact**: Failed token requests count toward limit
- **Mitigation**: Implement token caching (24-hour validity)
- **Testing**: Use mock mode first, then ONE real token request for final verification

### ⚠️ Production Trading Safety
- **Risk**: Real money loss if misconfigured
- **Mitigation**: Require `KIS_PRODUCTION_CONFIRMED=YES` in .env
- **Testing**: Always test in mock mode first
- **Monitoring**: Log all real orders with extra warnings

### ⚠️ Rate Limiting
- **Limit**: 20 req/sec, 1,000 req/min
- **Impact**: API suspension if exceeded
- **Mitigation**: RateLimiter class (already implemented)
- **Testing**: Verify rate limiter with burst tests

---

## 📊 Success Metrics

**Quantitative**:
- ✅ 0 NotImplementedError (down from 4)
- ✅ 100% test pass rate (7/7 tests)
- ✅ <10s for full buy-sell cycle (mock mode)
- ✅ <3s for price query (real API)
- ✅ <5s for order execution (real API)

**Qualitative**:
- ✅ Real token obtained successfully
- ✅ Real price query returns accurate data
- ✅ Mock orders execute without errors
- ✅ Production safety checks prevent accidental real trading
- ✅ Code ready for production deployment

---

**Document Version**: 1.0
**Last Updated**: 2025-10-20
**Status**: Design Complete → Ready for Implementation
