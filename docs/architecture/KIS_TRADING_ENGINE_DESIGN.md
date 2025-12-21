# KIS Trading Engine - Design Document

**Date**: 2025-10-14
**Task**: Phase 5 Task 3 - KIS Trading Engine Implementation
**Code Reuse**: 60-70% from Makenaide trading_engine.py (2,419 lines)

---

## Executive Summary

### Design Philosophy
**"Simplify, then Add Lightness"** - Start with MVP (Minimum Viable Product) focused on core buy/sell execution, then iterate.

### Scope Reduction Strategy
- **Makenaide**: 2,419 lines with complex features (pyramiding, trailing stops, portfolio sync, direct purchases)
- **Spock MVP**: ~800-1,000 lines focusing on:
  1. ✅ Buy order execution with tick size compliance
  2. ✅ Sell order execution (stop loss / take profit)
  3. ✅ Basic portfolio tracking
  4. ✅ KIS API integration
  5. ❌ Advanced features deferred to Phase 6

### Code Reuse Breakdown
| Component | Reuse % | Notes |
|-----------|---------|-------|
| Order execution logic | 70% | Adapt Upbit → KIS API |
| Position tracking | 80% | Same database schema |
| Fee calculation | 90% | Update fee rates |
| Rate limiting | 100% | Direct copy |
| Trailing stops | 0% | Defer to Phase 6 |
| Pyramiding | 0% | Defer to Phase 6 |
| Portfolio sync | 50% | Simplified version |

---

## Core Architecture

### Class Structure
```python
class KISTradingEngine:
    """
    Simplified KIS trading engine for stock market

    Focus: Core buy/sell execution with proper risk management
    """

    def __init__(self, db_path: str, kis_config: Dict, dry_run: bool = False):
        self.db_path = db_path
        self.kis_config = kis_config
        self.dry_run = dry_run
        self.kis_client = None  # KIS API client

    # Core Methods (MVP)
    def execute_buy_order(self, ticker: str, amount_krw: float) -> TradeResult
    def execute_sell_order(self, ticker: str, quantity: float, reason: str) -> TradeResult
    def get_current_positions(self) -> List[PositionInfo]
    def check_sell_conditions(self, position: PositionInfo) -> Tuple[bool, str]

    # Supporting Methods
    def _adjust_price_to_tick_size(self, price: float) -> int
    def _calculate_fee_adjusted_amount(self, amount_krw: float) -> float
    def _save_trade_record(self, trade_result: TradeResult) -> bool
```

---

## Component Design

### 1. KIS API Integration

#### Authentication
```python
class KISAuthenticator:
    """KIS API 인증 관리자"""

    def __init__(self, app_key: str, app_secret: str):
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = None
        self.token_expiry = None

    def get_access_token(self) -> str:
        """Access token 발급 (24시간 유효)"""
        # POST /oauth2/tokenP

    def refresh_token_if_needed(self) -> bool:
        """토큰 만료 시 자동 갱신"""
```

#### Order Execution
```python
# Buy Order (현금 매수)
POST /uapi/domestic-stock/v1/trading/order-cash
Headers:
  - authorization: Bearer {access_token}
  - appkey: {app_key}
  - appsecret: {app_secret}
  - tr_id: TTTC0802U (모의투자) or VTTC0802U (실전투자)
Body:
  - CANO: 계좌번호 앞 8자리
  - ACNT_PRDT_CD: 계좌번호 뒤 2자리
  - PDNO: 종목코드 (6자리)
  - ORD_DVSN: 주문구분 (00:지정가, 01:시장가)
  - ORD_QTY: 주문수량
  - ORD_UNPR: 주문단가

# Sell Order (현금 매도)
POST /uapi/domestic-stock/v1/trading/order-cash
Headers: (동일)
Body: (동일, tr_id만 다름)
  - tr_id: TTTC0801U (모의투자) or VTTC0801U (실전투자)
```

#### Rate Limiting
```python
# KIS API 제한
- 초당 요청: 20 req/sec
- 분당 요청: 1,000 req/min

class RateLimiter:
    """API 호출 제한 관리"""
    def __init__(self, max_requests: int = 20, window: float = 1.0):
        self.max_requests = max_requests
        self.window = window
        self.requests = []

    def wait_if_needed(self):
        """필요시 대기"""
```

---

### 2. Tick Size Compliance

#### Tick Size Rules (한국 주식시장)
```python
TICK_SIZE_RULES_KRW = {
    # (min_price, max_price): tick_size
    (0, 1000): 1,                    # <1K: 1 KRW
    (1000, 5000): 5,                 # 1K-5K: 5 KRW
    (5000, 10000): 10,               # 5K-10K: 10 KRW
    (10000, 50000): 50,              # 10K-50K: 50 KRW
    (50000, 100000): 100,            # 50K-100K: 100 KRW
    (100000, 500000): 500,           # 100K-500K: 500 KRW
    (500000, float('inf')): 1000     # 500K+: 1,000 KRW
}

def adjust_price_to_tick_size(price: float) -> int:
    """
    KIS API 주문가격을 호가 단위에 맞게 조정

    예시:
    - 9,999 KRW → 9,995 KRW (5 KRW tick)
    - 49,999 KRW → 49,950 KRW (50 KRW tick)
    - 99,999 KRW → 99,900 KRW (100 KRW tick)
    """
    for (min_price, max_price), tick_size in TICK_SIZE_RULES_KRW.items():
        if min_price <= price < max_price:
            return int(round(price / tick_size) * tick_size)
    return int(price)
```

---

### 3. Order Execution Flow

#### Buy Order Workflow
```
User Request (ticker, amount_krw)
    ↓
Validate inputs (ticker exists, amount >= 10,000)
    ↓
Get current price from KIS API
    ↓
Adjust price to tick size
    ↓
Calculate quantity (amount_krw / adjusted_price)
    ↓
Calculate fee-adjusted quantity
    ↓
Execute KIS API buy order
    ↓
Parse response (order_id, avg_price, quantity)
    ↓
Save to trades table
    ↓
Return TradeResult
```

#### Sell Order Workflow
```
User Request (ticker, quantity, reason)
    ↓
Validate position exists
    ↓
Get current price from KIS API
    ↓
Adjust price to tick size
    ↓
Execute KIS API sell order
    ↓
Parse response (order_id, avg_price, quantity)
    ↓
Calculate P&L
    ↓
Update trades table (exit_price, pnl)
    ↓
Return TradeResult
```

---

### 4. Position Tracking

#### PositionInfo Dataclass
```python
@dataclass
class PositionInfo:
    """현재 보유 포지션 정보"""
    ticker: str
    quantity: float
    avg_buy_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    buy_timestamp: datetime
    hold_days: int

    @property
    def should_stop_loss(self) -> bool:
        """손절 조건 체크 (-8%)"""
        return self.unrealized_pnl_percent <= -8.0

    @property
    def should_take_profit(self) -> bool:
        """익절 조건 체크 (+20%)"""
        return self.unrealized_pnl_percent >= 20.0
```

#### Database Schema
```sql
-- trades table (existing)
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    region TEXT DEFAULT 'KR',
    entry_price REAL NOT NULL,
    exit_price REAL,
    quantity REAL NOT NULL,
    entry_timestamp TEXT NOT NULL,
    exit_timestamp TEXT,
    pnl REAL,
    pnl_percent REAL,
    trade_status TEXT DEFAULT 'OPEN',  -- OPEN, CLOSED
    exit_reason TEXT,  -- stop_loss, take_profit, manual
    created_at TEXT NOT NULL
);
```

---

### 5. Fee Calculation

#### Korean Stock Market Fees
```python
# Trading Fees (2025 기준)
TRADING_FEES = {
    'buy': {
        'commission': 0.00015,  # 0.015% (온라인 증권사)
        'securities_tax': 0.0,  # 매수 시 없음
        'total': 0.00015
    },
    'sell': {
        'commission': 0.00015,  # 0.015%
        'securities_tax': 0.0023,  # 0.23% (KOSPI), 0% (KOSDAQ)
        'total': 0.00245  # KOSPI 기준
    }
}

def calculate_fee_adjusted_amount(amount_krw: float, is_buy: bool = True) -> Dict:
    """
    수수료 반영한 실제 거래 금액 계산

    매수:
    - 실제 투입 금액 = amount_krw
    - 수수료 차감 후 매수 가능 금액 = amount_krw / (1 + 0.00015)

    매도:
    - 매도 금액 = quantity * price
    - 수수료 차감 후 실수령 금액 = amount * (1 - 0.00245)
    """
    if is_buy:
        fee_rate = TRADING_FEES['buy']['total']
        adjusted_amount = amount_krw / (1 + fee_rate)
        fee = amount_krw - adjusted_amount
    else:
        fee_rate = TRADING_FEES['sell']['total']
        adjusted_amount = amount_krw * (1 - fee_rate)
        fee = amount_krw - adjusted_amount

    return {
        'original_amount': amount_krw,
        'adjusted_amount': adjusted_amount,
        'fee': fee,
        'fee_rate': fee_rate
    }
```

---

### 6. Sell Condition Checking

#### Exit Logic
```python
def check_sell_conditions(self, position: PositionInfo) -> Tuple[bool, str]:
    """
    매도 조건 체크

    Returns:
        (should_sell, reason)
    """
    # 1. Stop Loss Check (-8%)
    if position.unrealized_pnl_percent <= -8.0:
        return (True, 'stop_loss')

    # 2. Take Profit Check (+20%)
    if position.unrealized_pnl_percent >= 20.0:
        return (True, 'take_profit')

    # 3. Time-based Exit (Optional: 90 days)
    if position.hold_days >= 90:
        if position.unrealized_pnl_percent > 0:
            return (True, 'time_based_profit')

    return (False, 'hold')
```

---

## Simplified Implementation Plan

### Phase 1: Core Buy/Sell (Days 1-3)
- ✅ KIS API authentication
- ✅ Buy order execution with tick size
- ✅ Sell order execution
- ✅ Trade record saving
- ✅ Basic error handling

### Phase 2: Position Management (Days 4-5)
- ✅ Get current positions from database
- ✅ Calculate unrealized P&L
- ✅ Check sell conditions
- ✅ Fee-adjusted calculations

### Phase 3: Testing & Validation (Days 6-7)
- ✅ Unit tests for all core methods
- ✅ Integration tests with KIS mock API
- ✅ Dry-run mode testing
- ✅ Performance benchmarking

---

## Deferred Features (Phase 6)

### Advanced Features Not in MVP
1. **Trailing Stops** (ATR-based)
   - Complex logic from Makenaide (200+ lines)
   - Requires additional database tables
   - Defer to Phase 6

2. **Pyramiding** (Position scaling)
   - Requires PyramidStateManager (300+ lines)
   - Complex state management
   - Defer to Phase 6

3. **Portfolio Sync** (Full reconciliation)
   - Complex mismatch detection (150+ lines)
   - Auto-sync policies
   - Defer to Phase 6

4. **Direct Purchase Handling**
   - Manual buy detection (100+ lines)
   - Defer to Phase 6

---

## Error Handling Strategy

### API Error Types
```python
class KISAPIError(Exception):
    """KIS API 오류"""
    pass

class OrderRejectedError(KISAPIError):
    """주문 거부 (잔고 부족, 호가 오류 등)"""
    pass

class AuthenticationError(KISAPIError):
    """인증 실패"""
    pass

class RateLimitError(KISAPIError):
    """API 호출 제한 초과"""
    pass
```

### Error Recovery
```python
def execute_buy_order_with_retry(self, ticker: str, amount_krw: float) -> TradeResult:
    """
    재시도 로직 포함 매수 주문

    - API 오류: 3회 재시도 (exponential backoff)
    - 호가 오류: 가격 조정 후 1회 재시도
    - 잔고 부족: 즉시 실패 (재시도 안 함)
    """
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            return self.execute_buy_order(ticker, amount_krw)
        except RateLimitError:
            wait_time = (2 ** retry_count) * 1.0  # 1s, 2s, 4s
            time.sleep(wait_time)
            retry_count += 1
        except OrderRejectedError as e:
            # 호가 오류인 경우 가격 조정 후 1회만 재시도
            if 'tick size' in str(e).lower() and retry_count == 0:
                retry_count += 1
                continue
            else:
                raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    raise KISAPIError(f"Failed after {max_retries} retries")
```

---

## Testing Strategy

### Unit Tests (test_kis_trading_engine.py)
```python
class TestKISTradingEngine:
    def test_tick_size_adjustment():
        """호가 단위 조정 테스트"""

    def test_fee_calculation():
        """수수료 계산 테스트"""

    def test_position_tracking():
        """포지션 추적 테스트"""

    def test_sell_condition_check():
        """매도 조건 체크 테스트"""
```

### Integration Tests (test_kis_api_integration.py)
```python
class TestKISAPIIntegration:
    def test_buy_order_execution_mock():
        """KIS mock API 매수 주문 테스트"""

    def test_sell_order_execution_mock():
        """KIS mock API 매도 주문 테스트"""

    def test_rate_limiting():
        """API 호출 제한 테스트"""
```

---

## Performance Targets

### Execution Speed
- Buy order execution: <500ms
- Sell order execution: <500ms
- Position query: <100ms
- Sell condition check: <50ms per position

### Reliability
- Order success rate: ≥99% (excluding insufficient balance)
- API error recovery: 95% auto-recovery within 3 retries
- Database integrity: 100% (no data loss)

---

## Deployment Checklist

### Pre-Deployment
- [ ] All unit tests passing (100%)
- [ ] Integration tests with KIS mock API passing
- [ ] Dry-run mode tested with 10 simulated trades
- [ ] Fee calculations validated
- [ ] Tick size compliance verified

### Deployment
- [ ] KIS API credentials configured (.env)
- [ ] Database backup created
- [ ] Dry-run mode enabled initially
- [ ] Monitor first 5 trades manually
- [ ] Switch to live mode after validation

---

## Success Metrics

### MVP Success Criteria
- ✅ Buy orders execute with correct tick size
- ✅ Sell orders execute with P&L calculation
- ✅ Position tracking accurate within 0.01%
- ✅ Fee calculations match KIS statements
- ✅ No database corruption after 100 trades
- ✅ API error recovery working

**Target Completion**: 7 days (Days 6-12 of Phase 5)

---

**Document Status**: Design Complete
**Next Step**: Implementation of kis_trading_engine.py (~800-1,000 lines)
