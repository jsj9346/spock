# Lot Size Implementation Plan

**Purpose**: Support overseas stock trading units (lot size/board lot) for global market orders

**Created**: 2025-10-17
**Status**: Design Complete
**Target**: Week 1-3 Implementation

---

## 1. Market-Specific Lot Size Rules

### 1.1 Trading Unit Requirements by Region

| Region | Exchange | Lot Size | Type | Notes |
|--------|----------|----------|------|-------|
| **KR** | KOSPI/KOSDAQ | 1 share | Fixed | No restrictions |
| **US** | NYSE/NASDAQ/AMEX | 1 share | Fixed | No restrictions |
| **CN** | SSE/SZSE | 100 shares | Fixed | 1 lot = 100 shares |
| **HK** | HKEX | Variable | Ticker-specific | 100, 200, 400, 500, 1000, 2000 shares |
| **JP** | TSE | 100 shares | Fixed | 1 unit = 100 shares |
| **VN** | HOSE/HNX | 100 shares | Fixed | 1 lot = 100 shares |

### 1.2 Risk Assessment

**High Risk - Hong Kong (HK)**:
- ❌ Variable board lots (100-2,000 shares per ticker)
- ❌ No standard formula, must fetch from API
- ❌ Wrong lot size = Order rejection

**Medium Risk - CN/JP/VN**:
- ⚠️ Fixed 100 shares, but API validation needed
- ⚠️ Order rejection if incorrect

**Low Risk - KR/US**:
- ✅ 1 share minimum, effectively no restriction
- ✅ Already working correctly

---

## 2. Database Schema Design

### 2.1 Schema Modification

**Add `lot_size` column to `tickers` table**:

```sql
ALTER TABLE tickers ADD COLUMN lot_size INTEGER DEFAULT 1;
```

**Column Specifications**:
- **Type**: INTEGER (trading units are whole numbers)
- **Default**: 1 (safest default for KR/US)
- **Nullable**: Yes (allow NULL for gradual migration)
- **Index**: Not needed (not a query filter)

### 2.2 Default Values by Region

**Migration will set region-based defaults**:

```sql
-- Korea: 1 share
UPDATE tickers SET lot_size = 1 WHERE region = 'KR' AND lot_size IS NULL;

-- US: 1 share
UPDATE tickers SET lot_size = 1 WHERE region = 'US' AND lot_size IS NULL;

-- China: 100 shares
UPDATE tickers SET lot_size = 100 WHERE region = 'CN' AND lot_size IS NULL;

-- Hong Kong: NULL initially (fetch from API)
-- Will be populated during ticker scan

-- Japan: 100 shares
UPDATE tickers SET lot_size = 100 WHERE region = 'JP' AND lot_size IS NULL;

-- Vietnam: 100 shares
UPDATE tickers SET lot_size = 100 WHERE region = 'VN' AND lot_size IS NULL;
```

### 2.3 Data Integrity Constraints

**Validation Rules**:
```python
# In db_manager_sqlite.py
def validate_lot_size(lot_size: int, region: str) -> bool:
    """Validate lot_size before storage"""
    if lot_size is None:
        return True  # NULL allowed

    if lot_size <= 0:
        return False  # Must be positive

    # Region-specific validation
    valid_ranges = {
        'KR': (1, 1),           # Only 1
        'US': (1, 1),           # Only 1
        'CN': (100, 100),       # Only 100
        'JP': (100, 100),       # Only 100
        'VN': (100, 100),       # Only 100
        'HK': (100, 2000),      # Variable (100-2000)
    }

    min_lot, max_lot = valid_ranges.get(region, (1, 999999))
    return min_lot <= lot_size <= max_lot
```

---

## 3. Migration Strategy

### 3.1 Migration Script: `migrations/002_add_lot_size_column.py`

**Features**:
- ✅ Add lot_size column with validation
- ✅ Set region-based defaults
- ✅ Rollback support
- ✅ Data verification
- ✅ Backup before changes

**Execution**:
```bash
# Dry run (safe preview)
python3 migrations/002_add_lot_size_column.py --dry-run

# Apply migration
python3 migrations/002_add_lot_size_column.py

# Rollback if needed
python3 migrations/002_add_lot_size_column.py --rollback
```

### 3.2 Migration Safety Checklist

- [ ] Backup database before migration
- [ ] Run migration in dry-run mode first
- [ ] Verify default values are correct
- [ ] Test rollback functionality
- [ ] Validate data integrity after migration

---

## 4. Adapter Integration

### 4.1 BaseAdapter Interface Update

**File**: `modules/market_adapters/base_adapter.py`

**Add lot_size to ticker data structure**:

```python
class BaseMarketAdapter(ABC):
    """Base adapter for market-specific data collection"""

    @abstractmethod
    def scan_stocks(self, force_refresh: bool = False) -> List[Dict]:
        """
        Scan market for tradable stocks

        Returns:
            List of ticker dictionaries with fields:
                - ticker: str
                - name: str
                - exchange: str
                - region: str
                - currency: str
                - lot_size: int  # ← NEW FIELD
                ...
        """
        pass

    def _validate_ticker_data(self, ticker_data: Dict) -> bool:
        """Validate ticker data before insertion"""
        required_fields = ['ticker', 'name', 'exchange', 'region', 'currency', 'lot_size']

        for field in required_fields:
            if field not in ticker_data:
                logger.error(f"Missing required field: {field}")
                return False

        # Validate lot_size
        if not self._validate_lot_size(ticker_data['lot_size'], ticker_data['region']):
            logger.error(f"Invalid lot_size: {ticker_data['lot_size']} for {ticker_data['region']}")
            return False

        return True
```

### 4.2 KIS Adapter Updates

**Priority Order** (by risk level):

#### Priority 1: HKAdapterKIS (Highest Risk)

**File**: `modules/market_adapters/hk_adapter_kis.py`

```python
def scan_stocks(self, force_refresh: bool = False) -> List[Dict]:
    """Scan HKEX stocks with lot_size from KIS API"""

    # ... existing code ...

    # Fetch lot_size from KIS API
    lot_size = self._fetch_lot_size_from_api(ticker)

    ticker_data = {
        'ticker': ticker,
        'name': name,
        'exchange': 'HKEX',
        'region': 'HK',
        'currency': 'HKD',
        'lot_size': lot_size or 100,  # Fallback to 100 if API fails
        # ... other fields ...
    }
```

**KIS API Endpoint** (expected):
- `/uapi/overseas-price/v1/quotations/search-info`
- Look for fields: `ovrs_tr_mket_size`, `tr_unit`, `min_tr_qty`, `lot_size`

#### Priority 2: CNAdapterKIS, JPAdapterKIS, VNAdapterKIS

**Files**:
- `modules/market_adapters/cn_adapter_kis.py`
- `modules/market_adapters/jp_adapter_kis.py`
- `modules/market_adapters/vn_adapter_kis.py`

```python
def scan_stocks(self, force_refresh: bool = False) -> List[Dict]:
    """Scan stocks with fixed lot_size = 100"""

    ticker_data = {
        # ... existing fields ...
        'lot_size': 100,  # Fixed for CN/JP/VN
    }
```

#### Priority 3: USAdapterKIS, KRAdapter (Low Risk)

**Files**:
- `modules/market_adapters/us_adapter_kis.py`
- `modules/market_adapters/kr_adapter.py`

```python
def scan_stocks(self, force_refresh: bool = False) -> List[Dict]:
    """Scan stocks with lot_size = 1"""

    ticker_data = {
        # ... existing fields ...
        'lot_size': 1,  # Fixed for US/KR
    }
```

### 4.3 Database Insertion Update

**File**: `modules/db_manager_sqlite.py`

```python
def insert_ticker(self, ticker_data: Dict) -> bool:
    """Insert or replace ticker with lot_size"""

    cursor.execute("""
        INSERT OR REPLACE INTO tickers (
            ticker, name, name_eng, exchange, region, currency,
            asset_type, listing_date, is_active, delisting_date,
            lot_size,  -- ← NEW FIELD
            created_at, last_updated, data_source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker_data['ticker'],
        ticker_data['name'],
        ticker_data.get('name_eng'),
        ticker_data['exchange'],
        ticker_data['region'],
        ticker_data['currency'],
        ticker_data['asset_type'],
        ticker_data.get('listing_date'),
        ticker_data.get('is_active', True),
        ticker_data.get('delisting_date'),
        ticker_data.get('lot_size', 1),  -- ← NEW FIELD
        ticker_data['created_at'],
        ticker_data['last_updated'],
        ticker_data.get('data_source', 'Unknown'),
    ))
```

---

## 5. Trading Engine Integration

### 5.1 Order Quantity Rounding Logic

**File**: `modules/kis_trading_engine.py`

**Add lot_size-aware quantity rounding**:

```python
class KISTradingEngine:
    """KIS API trading engine with lot_size support"""

    def _round_quantity_to_lot_size(self, ticker: str, quantity: int) -> int:
        """
        Round order quantity to valid lot_size multiples

        Args:
            ticker: Stock ticker
            quantity: Desired quantity (from Kelly Calculator)

        Returns:
            Adjusted quantity (rounded DOWN to lot_size multiples)

        Raises:
            ValueError: If quantity < lot_size
        """
        # Fetch lot_size from database
        lot_size = self._get_lot_size(ticker)

        if lot_size is None or lot_size <= 0:
            logger.warning(f"[{ticker}] Invalid lot_size: {lot_size}, using default 1")
            lot_size = 1

        # Round DOWN to nearest lot_size multiple
        adjusted_qty = (quantity // lot_size) * lot_size

        # Validate minimum lot
        if adjusted_qty < lot_size:
            raise ValueError(
                f"[{ticker}] Insufficient quantity: {quantity} < lot_size {lot_size}. "
                f"Minimum order: {lot_size} shares"
            )

        # Log adjustment if quantity changed
        if adjusted_qty != quantity:
            logger.info(
                f"[{ticker}] Quantity adjusted for lot_size: "
                f"{quantity} → {adjusted_qty} (lot_size: {lot_size})"
            )

        return adjusted_qty

    def _get_lot_size(self, ticker: str) -> int:
        """Fetch lot_size from database (cached)"""
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT lot_size FROM tickers WHERE ticker = ?
        """, (ticker,))

        result = cursor.fetchone()
        conn.close()

        if result:
            return result['lot_size'] or 1
        else:
            logger.error(f"[{ticker}] Not found in tickers table")
            return 1  # Safe default

    def place_order(self, ticker: str, side: str, quantity: int, **kwargs) -> Dict:
        """
        Place order with lot_size validation

        Args:
            ticker: Stock ticker
            side: BUY or SELL
            quantity: Desired quantity (will be rounded to lot_size)
        """
        try:
            # Round quantity to lot_size multiples
            adjusted_qty = self._round_quantity_to_lot_size(ticker, quantity)

            # Existing order placement logic
            order_result = self._execute_kis_order(
                ticker=ticker,
                side=side,
                quantity=adjusted_qty,  # Use adjusted quantity
                **kwargs
            )

            return order_result

        except ValueError as e:
            logger.error(f"Order validation failed: {e}")
            return {'success': False, 'error': str(e)}
```

### 5.2 Kelly Calculator Integration

**File**: `modules/kelly_calculator.py`

**Update position sizing to account for lot_size constraints**:

```python
class KellyCalculator:
    """Kelly Formula position sizing with lot_size support"""

    def calculate_position_size(
        self,
        ticker: str,
        portfolio_value: float,
        current_price: float,
        pattern_type: str,
        lot_size: int = 1  # ← NEW PARAMETER
    ) -> Dict:
        """
        Calculate position size with lot_size rounding

        Returns:
            {
                'kelly_pct': float,
                'half_kelly_pct': float,
                'recommended_position_size': float,
                'recommended_quantity': int,  # Rounded to lot_size
                'actual_position_pct': float,  # After lot_size adjustment
            }
        """
        # Existing Kelly calculation
        kelly_pct = self._calculate_kelly_pct(pattern_type)
        half_kelly_pct = kelly_pct * 0.5

        # Raw position size
        position_size = portfolio_value * half_kelly_pct
        raw_quantity = int(position_size / current_price)

        # Round to lot_size multiples
        adjusted_quantity = (raw_quantity // lot_size) * lot_size

        # Recalculate actual position after rounding
        actual_position_size = adjusted_quantity * current_price
        actual_position_pct = (actual_position_size / portfolio_value) * 100

        logger.info(
            f"[{ticker}] Position sizing: "
            f"Raw {raw_quantity} → Adjusted {adjusted_quantity} shares "
            f"(lot_size: {lot_size}, {actual_position_pct:.2f}% of portfolio)"
        )

        return {
            'kelly_pct': kelly_pct,
            'half_kelly_pct': half_kelly_pct,
            'recommended_position_size': actual_position_size,
            'recommended_quantity': adjusted_quantity,
            'actual_position_pct': actual_position_pct,
        }
```

---

## 6. Error Handling & Edge Cases

### 6.1 Insufficient Lot Size

**Scenario**: Calculated quantity < lot_size

**Solution**:
```python
if adjusted_qty < lot_size:
    logger.warning(
        f"[{ticker}] Insufficient capital for minimum lot. "
        f"Required: {lot_size * current_price:.2f} KRW, "
        f"Available position size: {position_size:.2f} KRW"
    )
    return {'success': False, 'reason': 'INSUFFICIENT_CAPITAL_FOR_LOT'}
```

### 6.2 HK Lot Size API Failure

**Scenario**: KIS API doesn't provide HK board lot

**Fallback Strategy**:
```python
def _fetch_hk_lot_size(self, ticker: str) -> int:
    """Fetch HK board lot with fallback"""
    try:
        lot_size = self._fetch_from_kis_api(ticker)
        if lot_size:
            return lot_size
    except Exception as e:
        logger.warning(f"[{ticker}] KIS API lot_size fetch failed: {e}")

    # Conservative fallback: 500 shares (mid-range)
    logger.warning(f"[{ticker}] Using fallback lot_size: 500")
    return 500
```

### 6.3 Fractional Shares

**Scenario**: Rounding creates small residuals

**Acceptable**: Residuals < 1 lot are expected and acceptable
```python
# Example: Portfolio rebalancing
target_qty = 1250 shares
lot_size = 100
adjusted_qty = 1200 shares  # Rounded down
residual = 50 shares  # Acceptable (<1 lot)
```

### 6.4 Minimum Order Value

**Scenario**: Adjusted quantity meets lot_size but violates minimum order value

**Solution**:
```python
def validate_minimum_order_value(self, ticker: str, quantity: int, price: float) -> bool:
    """Check if order meets exchange minimum value requirements"""
    order_value = quantity * price

    min_values = {
        'KR': 10000,    # 10,000 KRW
        'US': 1,        # $1 USD
        'HK': 100,      # 100 HKD
        'CN': 100,      # 100 CNY
        'JP': 100,      # 100 JPY
        'VN': 10000,    # 10,000 VND
    }

    region = self._get_ticker_region(ticker)
    min_value = min_values.get(region, 0)

    if order_value < min_value:
        logger.error(
            f"[{ticker}] Order value {order_value} < minimum {min_value}"
        )
        return False

    return True
```

---

## 7. Testing Plan

### 7.1 Unit Tests

**File**: `tests/test_lot_size.py`

```python
class TestLotSizeRounding:
    """Unit tests for lot_size rounding logic"""

    def test_exact_lot_multiples(self):
        """Test quantities that are exact lot_size multiples"""
        assert round_to_lot(100, lot_size=100) == 100
        assert round_to_lot(200, lot_size=100) == 200

    def test_rounding_down(self):
        """Test rounding DOWN to nearest lot_size"""
        assert round_to_lot(150, lot_size=100) == 100
        assert round_to_lot(250, lot_size=100) == 200

    def test_insufficient_quantity(self):
        """Test error when quantity < lot_size"""
        with pytest.raises(ValueError):
            round_to_lot(50, lot_size=100)

    def test_hk_variable_lots(self):
        """Test HK variable board lots"""
        assert round_to_lot(450, lot_size=400) == 400
        assert round_to_lot(1500, lot_size=500) == 1500
```

### 7.2 Integration Tests

**File**: `tests/test_trading_engine_lot_size.py`

```python
class TestTradingEngineLotSize:
    """Integration tests with real DB and KIS API"""

    def test_kr_stock_no_rounding(self):
        """KR stocks: lot_size=1, no rounding"""
        order = engine.place_order('005930', 'BUY', quantity=15)
        assert order['quantity'] == 15

    def test_cn_stock_rounding(self):
        """CN stocks: lot_size=100, round to 100 multiples"""
        order = engine.place_order('600519', 'BUY', quantity=250)
        assert order['quantity'] == 200  # Rounded down

    def test_hk_stock_board_lot(self):
        """HK stocks: variable board lot from DB"""
        # Assuming 0700.HK has lot_size=500
        order = engine.place_order('0700', 'BUY', quantity=750)
        assert order['quantity'] == 500

    def test_insufficient_capital(self):
        """Test error when capital < minimum lot value"""
        order = engine.place_order('0700', 'BUY', quantity=50)
        assert order['success'] == False
        assert 'INSUFFICIENT' in order['reason']
```

### 7.3 Edge Case Tests

```python
def test_kelly_position_with_lot_size():
    """Test Kelly Calculator with lot_size constraints"""
    kelly = KellyCalculator()

    result = kelly.calculate_position_size(
        ticker='600519',
        portfolio_value=10_000_000,  # 10M KRW
        current_price=2000,          # 2000 KRW/share
        pattern_type='Stage 2 Breakout',
        lot_size=100
    )

    # Verify quantity is lot_size multiple
    assert result['recommended_quantity'] % 100 == 0

    # Verify position size recalculated after rounding
    expected_size = result['recommended_quantity'] * 2000
    assert result['recommended_position_size'] == expected_size
```

### 7.4 Production Validation

**Dry-run testing with real market data**:

```bash
# Test with dry-run mode (no real orders)
python3 spock.py --dry-run --region HK --tickers 0700,9988
python3 spock.py --dry-run --region CN --tickers 600519,000858
python3 spock.py --dry-run --region JP --tickers 7203,9984
python3 spock.py --dry-run --region VN --tickers VCB,VHM

# Expected output:
# ✅ Lot_size validation passed
# ✅ Quantity adjusted: 150 → 100 (lot_size: 100)
# ✅ Order placement successful (dry-run)
```

---

## 8. Rollout Schedule

### Week 1: Schema & HK Adapter (Highest Risk)

**Day 1-2: Database Migration**
- [ ] Create migration script `002_add_lot_size_column.py`
- [ ] Test migration in dry-run mode
- [ ] Execute migration on development DB
- [ ] Verify default values by region
- [ ] Test rollback functionality

**Day 3-5: HK Adapter**
- [ ] Update `HKAdapterKIS.scan_stocks()` to fetch lot_size
- [ ] Implement KIS API lot_size extraction
- [ ] Add fallback logic (default 500)
- [ ] Test with 10 sample HK tickers
- [ ] Validate lot_size stored in DB

### Week 2: Other Adapters & Trading Engine

**Day 1-2: CN/JP/VN Adapters**
- [ ] Update `CNAdapterKIS` (lot_size=100)
- [ ] Update `JPAdapterKIS` (lot_size=100)
- [ ] Update `VNAdapterKIS` (lot_size=100)
- [ ] Test ticker scanning with lot_size
- [ ] Verify DB storage

**Day 3-5: Trading Engine**
- [ ] Implement `_round_quantity_to_lot_size()`
- [ ] Update `place_order()` with lot_size validation
- [ ] Integrate with Kelly Calculator
- [ ] Add error handling for insufficient lots
- [ ] Unit tests for rounding logic

### Week 3: Testing & Production Deployment

**Day 1-3: Comprehensive Testing**
- [ ] Run unit tests (target: 100% coverage)
- [ ] Run integration tests with real DB
- [ ] Edge case testing (fractional, minimum value)
- [ ] Dry-run testing with real tickers
- [ ] Performance testing (latency impact)

**Day 4-5: Production Deployment**
- [ ] Backup production database
- [ ] Run migration on production
- [ ] Gradual rollout: HK → CN/JP/VN
- [ ] Monitor order execution logs
- [ ] Verify zero order rejections

---

## 9. Success Criteria

### 9.1 Functional Requirements

- ✅ **Zero order rejections** due to lot_size violations
- ✅ **100% ticker coverage** with valid lot_size data
- ✅ **Accurate rounding** for all markets (KR, US, CN, HK, JP, VN)
- ✅ **Graceful fallback** if KIS API doesn't provide lot_size

### 9.2 Performance Requirements

- ✅ **<1ms latency** impact on order execution
- ✅ **Single DB read** per order (cached lot_size)
- ✅ **No API calls** during order execution (cached in DB)

### 9.3 Data Quality Requirements

- ✅ **HK lot_size accuracy**: Validate against HKEX official board lots
- ✅ **CN/JP/VN consistency**: All tickers use lot_size=100
- ✅ **KR/US baseline**: All tickers use lot_size=1

### 9.4 Error Handling Requirements

- ✅ **Clear error messages** for insufficient lot size
- ✅ **Conservative fallbacks** for API failures
- ✅ **Logging** of all lot_size adjustments

---

## 10. Risk Mitigation

### 10.1 Database Migration Risks

**Risk**: Schema change breaks existing code
**Mitigation**:
- Nullable column (backward compatible)
- Rollback script tested
- Dry-run mode for validation

### 10.2 HK Lot Size Data Risks

**Risk**: KIS API doesn't provide board lot data
**Mitigation**:
- Fallback to conservative default (500)
- Manual validation against HKEX data
- Warning logs for fallback usage

### 10.3 Order Execution Risks

**Risk**: Lot_size rounding creates unfilled orders
**Mitigation**:
- Always round DOWN (avoid over-ordering)
- Validate minimum lot before order
- Clear error messages to user

### 10.4 Performance Risks

**Risk**: DB reads add latency to order execution
**Mitigation**:
- Single indexed query (<1ms)
- In-memory caching (optional)
- Bulk prefetch for batch orders

---

## 11. Future Enhancements

### 11.1 Dynamic Lot Size Updates

**Current**: lot_size cached during ticker scan
**Future**: Periodic updates from KIS API
```python
# Scheduled task: Update HK board lots monthly
def update_hk_lot_sizes():
    """Refresh HK board lots from KIS API"""
    hk_tickers = db.get_tickers(region='HK')
    for ticker in hk_tickers:
        new_lot_size = fetch_from_kis_api(ticker)
        db.update_lot_size(ticker, new_lot_size)
```

### 11.2 Fractional Share Support (Future Markets)

**Current**: Round DOWN to whole lots
**Future**: Support fractional shares for US markets
```python
# For US fractional shares (e.g., DriveWealth, Interactive Brokers)
def supports_fractional_shares(region: str) -> bool:
    return region == 'US' and broker.supports_fractional
```

### 11.3 Lot Size Change Notifications

**Current**: Static lot_size in DB
**Future**: Alert on lot_size changes
```python
# Monitor lot_size changes (HK board lot revisions)
if new_lot_size != old_lot_size:
    logger.warning(f"[{ticker}] Lot_size changed: {old_lot_size} → {new_lot_size}")
    notify_user(f"Board lot changed for {ticker}")
```

---

## 12. Appendix

### 12.1 KIS API Lot Size Fields (Expected)

**Endpoint**: `/uapi/overseas-price/v1/quotations/search-info`

**Expected Response Fields**:
```json
{
  "output": {
    "rsym": "0700.HK",
    "tr_unit": "500",           // ← Trading unit (lot_size)
    "min_tr_qty": "500",        // ← Minimum order quantity
    "ovrs_tr_mket_size": "500"  // ← Overseas trading market size
  }
}
```

**Parsing Logic**:
```python
def extract_lot_size_from_kis_response(response: Dict) -> int:
    """Extract lot_size from KIS API response"""
    output = response.get('output', {})

    # Try multiple field names
    lot_size_fields = ['tr_unit', 'min_tr_qty', 'ovrs_tr_mket_size']

    for field in lot_size_fields:
        if field in output:
            try:
                return int(output[field])
            except (ValueError, TypeError):
                continue

    logger.warning(f"Lot_size not found in KIS response: {response}")
    return None  # Fallback to default
```

### 12.2 Exchange-Specific References

**Hong Kong Stock Exchange (HKEX)**:
- Official Board Lot Table: https://www.hkex.com.hk/eng/market/sec_tradinfo/boardlot/boardlot.htm
- Board lot ranges: 100, 200, 400, 500, 1000, 2000, 5000 shares

**Shanghai/Shenzhen Stock Exchange**:
- Fixed lot size: 100 shares (1手 = 100股)
- Reference: http://www.sse.com.cn/

**Tokyo Stock Exchange (TSE)**:
- Fixed trading unit: 100 shares (売買単位 = 100株)
- Reference: https://www.jpx.co.jp/

**Vietnam Stock Exchange**:
- Fixed lot size: 100 shares (1 lô = 100 cổ phiếu)
- Reference: https://www.hsx.vn/

---

## 13. Contacts & Support

**Technical Lead**: Spock Trading System
**Database Admin**: SQLite DB Manager
**KIS API Integration**: Phase 6 Global Adapters Team

**Documentation**:
- Main PRD: `spock_PRD.md`
- Global Architecture: `GLOBAL_MARKET_EXPANSION.md`
- Phase 6 Report: `docs/PHASE6_COMPLETION_REPORT.md`

**Issue Tracking**:
- Migration issues: Check `migrations/002_add_lot_size_column.log`
- Adapter issues: Check `logs/YYYYMMDD_spock.log`
- Trading engine: Check `logs/kis_trading_engine.log`

---

**END OF IMPLEMENTATION PLAN**

_Document Version: 1.0_
_Last Updated: 2025-10-17_
_Next Review: Week 3 (Post-Deployment)_
