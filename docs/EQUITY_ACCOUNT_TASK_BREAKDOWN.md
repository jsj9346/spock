# Equity Account Enhancement - Task Breakdown & Prioritization

**Project**: EQUITY_ACCOUNT_ENHANCEMENT
**Version**: 1.0
**Date**: 2025-11-06
**Estimated Duration**: 5-6 hours
**Status**: Planning Phase

---

## Executive Summary

### Project Goals
1. Add 8 equity account columns to `ticker_fundamentals` table
2. Enhance DART API parsing to extract equity breakdown
3. Implement validation and quality checks
4. Backfill existing data with equity accounts
5. Enable advanced capital structure analysis

### Success Metrics
- ✅ 100% schema migration success
- ✅ >90% data coverage for DART records
- ✅ >95% equity validation passing rate
- ✅ <5% query performance degradation
- ✅ Zero production incidents

---

## Task Hierarchy

```
EQUITY_ACCOUNT_ENHANCEMENT (Epic)
│
├── PHASE-1: Foundation & Schema (CRITICAL PATH)
│   ├── TASK-1.1: Database Schema Extension
│   ├── TASK-1.2: Index Creation
│   └── TASK-1.3: Constraint Setup
│
├── PHASE-2: DART API Enhancement (CRITICAL PATH)
│   ├── TASK-2.1: Account Pattern Mapping
│   ├── TASK-2.2: Equity Extraction Logic
│   ├── TASK-2.3: Validation Logic
│   └── TASK-2.4: Integration with Parser
│
├── PHASE-3: Testing & Validation (QUALITY GATE)
│   ├── TASK-3.1: Unit Tests
│   ├── TASK-3.2: Integration Tests
│   ├── TASK-3.3: Data Quality Tests
│   └── TASK-3.4: Performance Benchmarks
│
├── PHASE-4: Deployment & Migration (PRODUCTION)
│   ├── TASK-4.1: Staging Deployment
│   ├── TASK-4.2: Production Deployment
│   └── TASK-4.3: Rollback Plan Testing
│
├── PHASE-5: Data Backfill (POST-DEPLOYMENT)
│   ├── TASK-5.1: Backfill Script Development
│   ├── TASK-5.2: Dry-Run Execution
│   ├── TASK-5.3: Production Backfill
│   └── TASK-5.4: Validation & Verification
│
└── PHASE-6: Documentation & Monitoring (ONGOING)
    ├── TASK-6.1: User Documentation
    ├── TASK-6.2: API Documentation
    ├── TASK-6.3: Monitoring Dashboard
    └── TASK-6.4: Use Case Examples
```

---

## Priority Matrix

### Priority Levels
- **P0 (Critical)**: Blocks all downstream work, must complete first
- **P1 (High)**: Critical path items, delays impact timeline
- **P2 (Medium)**: Important but not blocking
- **P3 (Low)**: Nice to have, can defer if needed

### Dependency Types
- **Hard Dependency**: Must complete before dependent task can start
- **Soft Dependency**: Recommended order but can overlap
- **No Dependency**: Can execute in parallel

---

## PHASE 1: Foundation & Schema (Priority: P0 - CRITICAL)

### TASK-1.1: Database Schema Extension
**ID**: EQUITY-1.1
**Priority**: P0 (Critical)
**Estimated Time**: 15 minutes
**Dependencies**: None
**Assignee**: Database Team
**Skills Required**: PostgreSQL, TimescaleDB

**Description**:
Add 8 new columns to `ticker_fundamentals` table for equity account breakdown.

**Acceptance Criteria**:
- [ ] All 8 columns created successfully
- [ ] Columns are nullable (backward compatible)
- [ ] Data types match specification (NUMERIC(20, 2))
- [ ] No existing data affected
- [ ] Migration executes in <1 minute

**Implementation**:
```sql
-- Execute SQL from EQUITY_ACCOUNT_ENHANCEMENT_DESIGN.md Section 2.1
ALTER TABLE ticker_fundamentals
ADD COLUMN IF NOT EXISTS capital_stock NUMERIC(20, 2),
ADD COLUMN IF NOT EXISTS capital_surplus NUMERIC(20, 2),
ADD COLUMN IF NOT EXISTS retained_earnings NUMERIC(20, 2),
ADD COLUMN IF NOT EXISTS treasury_stock NUMERIC(20, 2),
ADD COLUMN IF NOT EXISTS other_comprehensive_income NUMERIC(20, 2),
ADD COLUMN IF NOT EXISTS non_controlling_interest NUMERIC(20, 2),
ADD COLUMN IF NOT EXISTS unappropriated_retained_earnings NUMERIC(20, 2),
ADD COLUMN IF NOT EXISTS legal_reserve NUMERIC(20, 2);
```

**Validation Steps**:
1. Query table structure: `\d ticker_fundamentals`
2. Verify column count: 54 → 62 columns
3. Check data integrity: `SELECT COUNT(*) FROM ticker_fundamentals`
4. Validate nullable constraint: All new columns allow NULL

**Rollback**:
```sql
-- If migration fails, execute rollback
ALTER TABLE ticker_fundamentals
DROP COLUMN IF EXISTS capital_stock,
DROP COLUMN IF EXISTS capital_surplus,
DROP COLUMN IF EXISTS retained_earnings,
DROP COLUMN IF EXISTS treasury_stock,
DROP COLUMN IF EXISTS other_comprehensive_income,
DROP COLUMN IF EXISTS non_controlling_interest,
DROP COLUMN IF EXISTS unappropriated_retained_earnings,
DROP COLUMN IF EXISTS legal_reserve;
```

---

### TASK-1.2: Index Creation
**ID**: EQUITY-1.2
**Priority**: P0 (Critical)
**Estimated Time**: 10 minutes
**Dependencies**: EQUITY-1.1 (Hard)
**Assignee**: Database Team
**Skills Required**: PostgreSQL indexing

**Description**:
Create 4 indexes to optimize equity account queries.

**Acceptance Criteria**:
- [ ] 4 indexes created successfully
- [ ] Indexes use CONCURRENTLY (non-blocking)
- [ ] Query performance improved by >50%
- [ ] Index size <100 MB

**Implementation**:
```sql
-- Capital stock analysis index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fundamentals_capital_stock
ON ticker_fundamentals(ticker, region, fiscal_year DESC)
WHERE capital_stock IS NOT NULL;

-- Retained earnings trend index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fundamentals_retained_earnings
ON ticker_fundamentals(ticker, region, fiscal_year DESC)
WHERE retained_earnings IS NOT NULL;

-- Treasury stock buyback index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fundamentals_treasury_stock
ON ticker_fundamentals(ticker, region, fiscal_year DESC)
WHERE treasury_stock IS NOT NULL;

-- Equity breakdown completeness index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fundamentals_equity_complete
ON ticker_fundamentals(ticker, region, fiscal_year DESC)
WHERE capital_stock IS NOT NULL
  AND capital_surplus IS NOT NULL
  AND retained_earnings IS NOT NULL;
```

**Validation Steps**:
1. Verify index creation: `\di idx_fundamentals_*`
2. Check index size: `pg_size_pretty(pg_relation_size('index_name'))`
3. Test query performance: Run benchmark queries
4. Validate index usage: `EXPLAIN ANALYZE SELECT ...`

**Performance Benchmark**:
```sql
-- Before index
EXPLAIN ANALYZE
SELECT ticker, fiscal_year, retained_earnings
FROM ticker_fundamentals
WHERE retained_earnings > 0
ORDER BY retained_earnings DESC
LIMIT 100;
-- Expected: Seq Scan, ~2-3ms

-- After index
-- Expected: Index Scan, <1ms (>50% improvement)
```

---

### TASK-1.3: Constraint Setup
**ID**: EQUITY-1.3
**Priority**: P1 (High)
**Estimated Time**: 5 minutes
**Dependencies**: EQUITY-1.1 (Hard)
**Assignee**: Database Team
**Skills Required**: PostgreSQL constraints

**Description**:
Add data integrity constraints to ensure valid equity account values.

**Acceptance Criteria**:
- [ ] Treasury stock constraint enforced (≤ 0)
- [ ] Capital stock constraint enforced (≥ 0)
- [ ] Constraints don't block NULL values
- [ ] Existing data passes validation

**Implementation**:
```sql
-- Treasury stock must be non-positive (deduction account)
ALTER TABLE ticker_fundamentals
ADD CONSTRAINT chk_treasury_stock_negative
CHECK (treasury_stock IS NULL OR treasury_stock <= 0);

-- Capital stock must be non-negative
ALTER TABLE ticker_fundamentals
ADD CONSTRAINT chk_capital_stock_positive
CHECK (capital_stock IS NULL OR capital_stock >= 0);
```

**Validation Steps**:
1. Verify constraints: `\d+ ticker_fundamentals`
2. Test constraint enforcement:
   ```sql
   -- Should fail
   INSERT INTO ticker_fundamentals (ticker, region, date, treasury_stock)
   VALUES ('TEST', 'KR', '2024-01-01', 100);  -- Positive treasury stock

   -- Should succeed
   INSERT INTO ticker_fundamentals (ticker, region, date, treasury_stock)
   VALUES ('TEST', 'KR', '2024-01-01', -100);  -- Negative treasury stock
   ```
3. Check existing data: `SELECT COUNT(*) WHERE capital_stock < 0`

**Comments Addition**:
```sql
-- Add column comments for documentation
COMMENT ON COLUMN ticker_fundamentals.capital_stock IS
    '자본금: Common + Preferred stock capital';
COMMENT ON COLUMN ticker_fundamentals.retained_earnings IS
    '이익잉여금: Accumulated earnings not distributed';
COMMENT ON COLUMN ticker_fundamentals.treasury_stock IS
    '자기주식: Treasury stock (reported as negative)';
-- ... (see design doc for full comments)
```

---

## PHASE 2: DART API Enhancement (Priority: P0 - CRITICAL)

### TASK-2.1: Account Pattern Mapping
**ID**: EQUITY-2.1
**Priority**: P0 (Critical)
**Estimated Time**: 15 minutes
**Dependencies**: None (parallel with Phase 1)
**Assignee**: Backend Team
**Skills Required**: Python, DART API knowledge

**Description**:
Define account name patterns for fuzzy matching DART financial statement items.

**Acceptance Criteria**:
- [ ] Pattern dictionary covers all 6 primary equity accounts
- [ ] Priority ordering implemented (3-4 variations per account)
- [ ] Korean account names validated against DART spec
- [ ] Pattern coverage tested with sample data

**Implementation**:
```python
# Add to modules/dart_api_client.py

# Account name variations with priority order
EQUITY_ACCOUNT_PATTERNS = {
    'capital_stock': [
        '자본금',              # Priority 1: Standard
        '보통주자본금',         # Priority 2: Common stock
        '우선주자본금',         # Priority 3: Preferred stock
        '주식발행금액',         # Priority 4: Stock issuance
    ],
    'capital_surplus': [
        '자본잉여금',          # Priority 1: Standard
        '주식발행초과금',      # Priority 2: Premium
    ],
    'retained_earnings': [
        '이익잉여금',          # Priority 1: Total
        '이익준비금',          # Priority 2: Legal reserve
        '미처분이익잉여금',    # Priority 3: Unappropriated
    ],
    'treasury_stock': [
        '자기주식',            # Priority 1: Standard
        '자기주식처분손익',    # Priority 2: Disposal
    ],
    'other_comprehensive_income': [
        '기타포괄손익누계액',           # Priority 1: Standard
        '매도가능금융자산평가손익',     # Priority 2: AFS
        '해외사업환산손익',             # Priority 3: FX
    ],
    'non_controlling_interest': [
        '비지배지분',          # Priority 1: Standard
    ],
}
```

**Validation Steps**:
1. Unit test pattern matching with sample DART data
2. Verify coverage for top 100 Korean stocks
3. Log unmatched account names for review
4. Test fuzzy matching fallback logic

---

### TASK-2.2: Equity Extraction Logic
**ID**: EQUITY-2.2
**Priority**: P0 (Critical)
**Estimated Time**: 30 minutes
**Dependencies**: EQUITY-2.1 (Hard)
**Assignee**: Backend Team
**Skills Required**: Python, data parsing

**Description**:
Implement `_extract_equity_accounts()` method to parse DART financial statement items.

**Acceptance Criteria**:
- [ ] Method extracts all 6 primary equity accounts
- [ ] Fuzzy matching handles account name variations
- [ ] Treasury stock normalized to negative value
- [ ] Returns dict with equity account values
- [ ] Handles missing data gracefully (returns None)

**Implementation**:
```python
# Add to modules/dart_api_client.py::DARTApiClient

def _extract_equity_accounts(self, item_lookup: Dict[str, float]) -> Dict:
    """
    Extract equity account breakdown from DART item lookup

    Args:
        item_lookup: Dictionary mapping account names to amounts

    Returns:
        Dict with equity account values
    """

    equity_accounts = {}

    # Capital stock (자본금)
    equity_accounts['capital_stock'] = self._find_account_value(
        item_lookup,
        EQUITY_ACCOUNT_PATTERNS['capital_stock']
    )

    # Capital surplus (자본잉여금)
    equity_accounts['capital_surplus'] = self._find_account_value(
        item_lookup,
        EQUITY_ACCOUNT_PATTERNS['capital_surplus']
    )

    # Retained earnings (이익잉여금)
    equity_accounts['retained_earnings'] = self._find_account_value(
        item_lookup,
        EQUITY_ACCOUNT_PATTERNS['retained_earnings']
    )

    # Treasury stock (자기주식) - should be negative
    treasury_value = self._find_account_value(
        item_lookup,
        EQUITY_ACCOUNT_PATTERNS['treasury_stock']
    )
    # Normalize to negative (deduction account)
    if treasury_value and treasury_value > 0:
        treasury_value = -treasury_value
    equity_accounts['treasury_stock'] = treasury_value

    # Other comprehensive income (기타포괄손익누계액)
    equity_accounts['other_comprehensive_income'] = self._find_account_value(
        item_lookup,
        EQUITY_ACCOUNT_PATTERNS['other_comprehensive_income']
    )

    # Non-controlling interest (비지배지분)
    equity_accounts['non_controlling_interest'] = self._find_account_value(
        item_lookup,
        EQUITY_ACCOUNT_PATTERNS['non_controlling_interest']
    )

    # Optional: Unappropriated retained earnings
    equity_accounts['unappropriated_retained_earnings'] = item_lookup.get(
        '미처분이익잉여금', None
    )

    # Optional: Legal reserve
    equity_accounts['legal_reserve'] = item_lookup.get(
        '이익준비금', None
    )

    return equity_accounts


def _find_account_value(self, item_lookup: Dict[str, float],
                        patterns: List[str]) -> Optional[float]:
    """
    Find account value using priority-ordered pattern matching

    Args:
        item_lookup: Account name -> value mapping
        patterns: List of account name patterns (priority ordered)

    Returns:
        First matching value or None
    """
    # Exact match (priority order)
    for pattern in patterns:
        if pattern in item_lookup:
            return item_lookup[pattern]

    # Fuzzy match (substring match)
    for pattern in patterns:
        for account_name in item_lookup.keys():
            if pattern in account_name or account_name in pattern:
                logger.debug(
                    f"📝 Fuzzy match: '{pattern}' → '{account_name}'"
                )
                return item_lookup[account_name]

    return None
```

**Unit Tests**:
```python
# tests/test_dart_equity_extraction.py

def test_extract_standard_equity_accounts():
    """Test extraction with standard account names"""

    item_lookup = {
        '자본금': 100_000_000,
        '자본잉여금': 50_000_000,
        '이익잉여금': 200_000_000,
        '자기주식': -30_000_000,
    }

    dart_client = DARTApiClient()
    equity = dart_client._extract_equity_accounts(item_lookup)

    assert equity['capital_stock'] == 100_000_000
    assert equity['capital_surplus'] == 50_000_000
    assert equity['retained_earnings'] == 200_000_000
    assert equity['treasury_stock'] == -30_000_000


def test_fuzzy_matching():
    """Test fuzzy matching for account name variations"""

    item_lookup = {
        '보통주자본금': 80_000_000,
        '우선주자본금': 20_000_000,
    }

    dart_client = DARTApiClient()
    equity = dart_client._extract_equity_accounts(item_lookup)

    # Should pick first match (보통주자본금)
    assert equity['capital_stock'] == 80_000_000


def test_treasury_stock_normalization():
    """Test treasury stock is normalized to negative"""

    item_lookup = {
        '자기주식': 30_000_000,  # Positive value (incorrect)
    }

    dart_client = DARTApiClient()
    equity = dart_client._extract_equity_accounts(item_lookup)

    # Should be converted to negative
    assert equity['treasury_stock'] == -30_000_000
```

---

### TASK-2.3: Validation Logic
**ID**: EQUITY-2.3
**Priority**: P0 (Critical)
**Estimated Time**: 20 minutes
**Dependencies**: EQUITY-2.2 (Hard)
**Assignee**: Backend Team
**Skills Required**: Python, validation logic

**Description**:
Implement `_validate_equity_breakdown()` to verify equity components sum to total_equity.

**Acceptance Criteria**:
- [ ] Validation calculates equity from components
- [ ] Deviation percentage computed accurately
- [ ] 5% tolerance threshold enforced
- [ ] Warning logged for validation failures
- [ ] Returns validation result dict

**Implementation**:
```python
# Add to modules/dart_api_client.py::DARTApiClient

def _validate_equity_breakdown(self, reported_equity: float,
                               equity_components: Dict) -> Dict:
    """
    Validate equity breakdown against reported total equity

    Args:
        reported_equity: Total equity reported by DART
        equity_components: Dict with equity account values

    Returns:
        Validation result with is_valid flag and message
    """

    # Calculate total equity from components
    calculated_equity = (
        (equity_components.get('capital_stock') or 0) +
        (equity_components.get('capital_surplus') or 0) +
        (equity_components.get('retained_earnings') or 0) +
        (equity_components.get('other_comprehensive_income') or 0) +
        (equity_components.get('non_controlling_interest') or 0) -
        abs(equity_components.get('treasury_stock') or 0)
    )

    # Calculate deviation percentage
    if reported_equity != 0:
        deviation_pct = abs(calculated_equity - reported_equity) / abs(reported_equity) * 100
    else:
        # If reported equity is zero, check if calculated is also near zero
        deviation_pct = abs(calculated_equity) if calculated_equity != 0 else 0

    # Validation threshold: 5% deviation allowed
    is_valid = deviation_pct <= 5.0

    result = {
        'is_valid': is_valid,
        'reported_equity': reported_equity,
        'calculated_equity': calculated_equity,
        'deviation_pct': deviation_pct,
        'message': ''
    }

    if not is_valid:
        result['message'] = (
            f"Equity mismatch: reported={reported_equity:,.0f}, "
            f"calculated={calculated_equity:,.0f}, "
            f"deviation={deviation_pct:.1f}%"
        )

    return result
```

**Unit Tests**:
```python
# tests/test_dart_equity_validation.py

def test_validation_within_tolerance():
    """Test validation passes within 5% tolerance"""

    equity_components = {
        'capital_stock': 100_000_000,
        'capital_surplus': 50_000_000,
        'retained_earnings': 200_000_000,
        'treasury_stock': -30_000_000,
        'other_comprehensive_income': 0,
        'non_controlling_interest': 0,
    }

    dart_client = DARTApiClient()
    result = dart_client._validate_equity_breakdown(
        reported_equity=320_000_000,  # Matches calculated
        equity_components=equity_components
    )

    assert result['is_valid'] is True
    assert result['deviation_pct'] < 1.0


def test_validation_fails_outside_tolerance():
    """Test validation fails when >5% deviation"""

    equity_components = {
        'capital_stock': 100_000_000,
        'capital_surplus': 50_000_000,
        'retained_earnings': 200_000_000,
        'treasury_stock': -30_000_000,
    }

    dart_client = DARTApiClient()
    result = dart_client._validate_equity_breakdown(
        reported_equity=400_000_000,  # 25% deviation
        equity_components=equity_components
    )

    assert result['is_valid'] is False
    assert result['deviation_pct'] > 5.0
    assert 'Equity mismatch' in result['message']
```

---

### TASK-2.4: Integration with Parser
**ID**: EQUITY-2.4
**Priority**: P0 (Critical)
**Estimated Time**: 15 minutes
**Dependencies**: EQUITY-2.2, EQUITY-2.3 (Hard)
**Assignee**: Backend Team
**Skills Required**: Python integration

**Description**:
Integrate equity extraction and validation into `_parse_financial_statements()` method.

**Acceptance Criteria**:
- [ ] Equity extraction called after basic parsing
- [ ] Equity accounts merged into metrics dict
- [ ] Validation executed and logged
- [ ] Backward compatible (existing code unchanged)
- [ ] No performance degradation (<1ms overhead)

**Implementation**:
```python
# Modify modules/dart_api_client.py::DARTApiClient::_parse_financial_statements()

def _parse_financial_statements(self, ticker: str, items: List[Dict],
                               year: int, reprt_code: str) -> Dict:
    """
    Enhanced parser with equity account breakdown

    Args:
        ticker: Stock ticker
        items: List of financial statement items from DART API
        year: Fiscal year
        reprt_code: Report type code

    Returns:
        Dict with comprehensive financial metrics including equity breakdown
    """

    # ... [EXISTING CODE: Parse basic metrics] ...

    # Store raw financial items for reference
    metrics['total_assets'] = total_assets
    metrics['total_liabilities'] = total_liabilities
    metrics['total_equity'] = total_equity  # Original DART reported value
    # ... [rest of existing code] ...

    # ============================================================
    # NEW: Equity Account Breakdown Parsing
    # ============================================================

    # Extract equity accounts
    equity_accounts = self._extract_equity_accounts(item_lookup)

    # Merge equity accounts into metrics
    metrics.update(equity_accounts)

    # Validate equity breakdown
    validation_result = self._validate_equity_breakdown(
        reported_equity=total_equity,
        equity_components=equity_accounts
    )

    # Log validation warnings
    if not validation_result['is_valid']:
        logger.warning(
            f"⚠️ [DART] {ticker} ({year}): Equity validation failed - "
            f"{validation_result['message']}"
        )

    logger.debug(
        f"✅ [DART] {ticker}: Parsed financial metrics "
        f"(54 existing + 8 equity accounts)"
    )

    return metrics
```

**Integration Test**:
```python
# tests/integration/test_dart_equity_integration.py

def test_end_to_end_dart_parsing_with_equity():
    """Test complete DART parsing workflow with equity accounts"""

    # Mock DART API response
    mock_items = [
        {'account_nm': '자산총계', 'thstrm_amount': '1,000,000,000'},
        {'account_nm': '부채총계', 'thstrm_amount': '600,000,000'},
        {'account_nm': '자본총계', 'thstrm_amount': '400,000,000'},
        {'account_nm': '자본금', 'thstrm_amount': '100,000,000'},
        {'account_nm': '자본잉여금', 'thstrm_amount': '50,000,000'},
        {'account_nm': '이익잉여금', 'thstrm_amount': '250,000,000'},
        {'account_nm': '자기주식', 'thstrm_amount': '-30,000,000'},
    ]

    dart_client = DARTApiClient()
    metrics = dart_client._parse_financial_statements(
        ticker='005930',
        items=mock_items,
        year=2024,
        reprt_code='11011'
    )

    # Verify basic metrics
    assert metrics['total_assets'] == 1_000_000_000
    assert metrics['total_equity'] == 400_000_000

    # Verify equity accounts
    assert metrics['capital_stock'] == 100_000_000
    assert metrics['capital_surplus'] == 50_000_000
    assert metrics['retained_earnings'] == 250_000_000
    assert metrics['treasury_stock'] == -30_000_000

    # Verify validation (should pass)
    # 100M + 50M + 250M - 30M = 370M (vs 400M reported)
    # Deviation: 7.5% (within tolerance if NCI not zero)
```

---

## PHASE 3: Testing & Validation (Priority: P1 - QUALITY GATE)

### TASK-3.1: Unit Tests
**ID**: EQUITY-3.1
**Priority**: P1 (High)
**Estimated Time**: 45 minutes
**Dependencies**: EQUITY-2.4 (Hard)
**Assignee**: QA Team
**Skills Required**: Python, pytest

**Description**:
Create comprehensive unit tests for all equity account extraction logic.

**Acceptance Criteria**:
- [ ] >90% code coverage for new methods
- [ ] All edge cases covered (NULL, zero, negative values)
- [ ] Fuzzy matching tested with variations
- [ ] Validation logic tested with boundary conditions
- [ ] All tests pass in <1 second

**Test Cases** (10 tests):
1. ✅ `test_extract_standard_equity_accounts` - Standard account names
2. ✅ `test_fuzzy_matching_account_names` - Account name variations
3. ✅ `test_treasury_stock_normalization` - Treasury stock to negative
4. ✅ `test_missing_equity_accounts` - Graceful NULL handling
5. ✅ `test_validation_within_tolerance` - 5% validation pass
6. ✅ `test_validation_fails_outside_tolerance` - >5% validation fail
7. ✅ `test_validation_negative_equity` - Negative total equity
8. ✅ `test_validation_zero_equity` - Zero equity edge case
9. ✅ `test_pattern_priority_order` - Pattern matching priority
10. ✅ `test_optional_equity_accounts` - Unappropriated RE, legal reserve

**Test File Structure**:
```
tests/
├── test_dart_equity_extraction.py      # TASK-2.2 tests
├── test_dart_equity_validation.py      # TASK-2.3 tests
├── integration/
│   └── test_dart_equity_integration.py # TASK-2.4 tests
└── fixtures/
    └── dart_sample_data.json           # Sample DART responses
```

**Coverage Target**:
```bash
# Run tests with coverage
pytest tests/test_dart_equity_*.py --cov=modules.dart_api_client --cov-report=term-missing

# Expected coverage
# _extract_equity_accounts: 95%+
# _validate_equity_breakdown: 95%+
# _find_account_value: 90%+
# Overall: >90%
```

---

### TASK-3.2: Integration Tests
**ID**: EQUITY-3.2
**Priority**: P1 (High)
**Estimated Time**: 30 minutes
**Dependencies**: EQUITY-3.1 (Soft)
**Assignee**: QA Team
**Skills Required**: Python, PostgreSQL, pytest

**Description**:
Test complete workflow from DART API call to database storage.

**Acceptance Criteria**:
- [ ] End-to-end test with real DART API (staging)
- [ ] Database insertion tested with equity accounts
- [ ] Validation results logged correctly
- [ ] Backward compatibility verified (old data unaffected)
- [ ] Performance benchmark passes (<100ms per record)

**Test Scenarios**:
1. **Happy Path**: Complete equity data from DART → DB
2. **Partial Data**: Some equity accounts missing → NULL gracefully
3. **Validation Failure**: Equity mismatch logged, data still inserted
4. **Backward Compatibility**: Old records without equity accounts still queryable

**Implementation**:
```python
# tests/integration/test_equity_end_to_end.py

def test_complete_equity_workflow():
    """Test complete workflow: DART API → Parsing → DB Storage → Query"""

    # 1. Fetch from DART API (use test corp_code)
    dart_client = DARTApiClient()
    metrics_list = dart_client.get_historical_fundamentals(
        ticker='005930',
        corp_code='00126380',
        start_year=2024,
        end_year=2024
    )

    assert len(metrics_list) == 1
    metrics = metrics_list[0]

    # 2. Verify equity accounts parsed
    assert metrics.get('capital_stock') is not None
    assert metrics.get('retained_earnings') is not None

    # 3. Insert into test database
    conn = get_test_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO ticker_fundamentals (
            ticker, region, date, period_type, fiscal_year,
            total_equity,
            capital_stock, capital_surplus, retained_earnings,
            treasury_stock, other_comprehensive_income,
            non_controlling_interest,
            data_source
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """, (
        metrics['ticker'],
        'KR',
        metrics['date'],
        metrics['period_type'],
        metrics['fiscal_year'],
        metrics['total_equity'],
        metrics.get('capital_stock'),
        metrics.get('capital_surplus'),
        metrics.get('retained_earnings'),
        metrics.get('treasury_stock'),
        metrics.get('other_comprehensive_income'),
        metrics.get('non_controlling_interest'),
        'DART'
    ))

    conn.commit()

    # 4. Query back and verify
    cursor.execute("""
        SELECT capital_stock, retained_earnings, treasury_stock
        FROM ticker_fundamentals
        WHERE ticker = %s AND fiscal_year = 2024
    """, ('005930',))

    row = cursor.fetchone()
    assert row[0] is not None  # capital_stock
    assert row[1] is not None  # retained_earnings

    # 5. Validate equity breakdown
    cursor.execute("""
        SELECT
            total_equity,
            (
                COALESCE(capital_stock, 0) +
                COALESCE(capital_surplus, 0) +
                COALESCE(retained_earnings, 0) +
                COALESCE(other_comprehensive_income, 0) +
                COALESCE(non_controlling_interest, 0) -
                ABS(COALESCE(treasury_stock, 0))
            ) AS calculated_equity
        FROM ticker_fundamentals
        WHERE ticker = '005930' AND fiscal_year = 2024
    """)

    total, calculated = cursor.fetchone()
    deviation = abs(total - calculated) / total * 100

    assert deviation <= 5.0, f"Equity validation failed: {deviation:.1f}% deviation"
```

---

### TASK-3.3: Data Quality Tests
**ID**: EQUITY-3.3
**Priority**: P2 (Medium)
**Estimated Time**: 30 minutes
**Dependencies**: EQUITY-3.2 (Soft)
**Assignee**: QA Team
**Skills Required**: SQL, data validation

**Description**:
Create SQL queries to validate equity data quality across all records.

**Acceptance Criteria**:
- [ ] Data coverage query created (% of records with equity data)
- [ ] Validation query created (% of records passing validation)
- [ ] Anomaly detection query created (outliers, suspicious values)
- [ ] Monitoring view created for ongoing quality tracking
- [ ] Data quality report generated

**SQL Queries**:
```sql
-- 1. Data Coverage Report
SELECT
    COUNT(*) AS total_dart_records,
    COUNT(capital_stock) AS with_capital_stock,
    COUNT(retained_earnings) AS with_retained_earnings,
    COUNT(treasury_stock) AS with_treasury_stock,

    COUNT(capital_stock)::FLOAT / COUNT(*) * 100 AS capital_stock_coverage_pct,
    COUNT(retained_earnings)::FLOAT / COUNT(*) * 100 AS retained_earnings_coverage_pct
FROM ticker_fundamentals
WHERE data_source = 'DART';

-- Expected: >90% coverage after backfill


-- 2. Validation Success Rate
WITH equity_validation AS (
    SELECT
        ticker,
        fiscal_year,
        total_equity,
        (
            COALESCE(capital_stock, 0) +
            COALESCE(capital_surplus, 0) +
            COALESCE(retained_earnings, 0) +
            COALESCE(other_comprehensive_income, 0) +
            COALESCE(non_controlling_interest, 0) -
            ABS(COALESCE(treasury_stock, 0))
        ) AS calculated_equity,
        ABS(
            total_equity - (
                COALESCE(capital_stock, 0) +
                COALESCE(capital_surplus, 0) +
                COALESCE(retained_earnings, 0) +
                COALESCE(other_comprehensive_income, 0) +
                COALESCE(non_controlling_interest, 0) -
                ABS(COALESCE(treasury_stock, 0))
            )
        ) / NULLIF(ABS(total_equity), 0) * 100 AS deviation_pct
    FROM ticker_fundamentals
    WHERE data_source = 'DART'
      AND capital_stock IS NOT NULL
)
SELECT
    COUNT(*) AS total_records,
    COUNT(CASE WHEN deviation_pct <= 5.0 THEN 1 END) AS valid_records,
    COUNT(CASE WHEN deviation_pct > 5.0 THEN 1 END) AS invalid_records,
    COUNT(CASE WHEN deviation_pct <= 5.0 THEN 1 END)::FLOAT / COUNT(*) * 100 AS validation_success_rate
FROM equity_validation;

-- Expected: >95% validation success rate


-- 3. Anomaly Detection
SELECT
    ticker,
    fiscal_year,
    capital_stock,
    retained_earnings,
    treasury_stock,
    total_equity
FROM ticker_fundamentals
WHERE data_source = 'DART'
  AND capital_stock IS NOT NULL
  AND (
      -- Anomaly 1: Capital stock > total equity (suspicious)
      capital_stock > total_equity * 2
      OR
      -- Anomaly 2: Retained earnings negative and large (>50% of equity)
      (retained_earnings < 0 AND ABS(retained_earnings) > ABS(total_equity) * 0.5)
      OR
      -- Anomaly 3: Treasury stock positive (data error)
      treasury_stock > 0
  )
ORDER BY fiscal_year DESC, ticker;

-- Expected: <5% anomalies


-- 4. Create Monitoring View
CREATE OR REPLACE VIEW equity_data_quality_monitor AS
WITH equity_stats AS (
    SELECT
        COUNT(*) AS total_dart_records,
        COUNT(capital_stock) AS records_with_equity,
        COUNT(capital_stock)::FLOAT / COUNT(*) * 100 AS equity_coverage_pct,

        -- Validation stats
        COUNT(CASE
            WHEN capital_stock IS NOT NULL
             AND ABS(
                 total_equity - (
                     COALESCE(capital_stock, 0) +
                     COALESCE(capital_surplus, 0) +
                     COALESCE(retained_earnings, 0) +
                     COALESCE(other_comprehensive_income, 0) +
                     COALESCE(non_controlling_interest, 0) -
                     ABS(COALESCE(treasury_stock, 0))
                 )
             ) / NULLIF(ABS(total_equity), 0) > 0.05
            THEN 1
        END) AS validation_failures,

        -- Last updated
        MAX(created_at) AS last_update
    FROM ticker_fundamentals
    WHERE data_source = 'DART'
)
SELECT
    *,
    validation_failures::FLOAT / total_dart_records * 100 AS validation_failure_rate_pct,
    CASE
        WHEN equity_coverage_pct >= 90 AND validation_failures::FLOAT / total_dart_records * 100 <= 5
            THEN '✅ HEALTHY'
        WHEN equity_coverage_pct >= 70 AND validation_failures::FLOAT / total_dart_records * 100 <= 10
            THEN '⚠️ WARNING'
        ELSE '❌ CRITICAL'
    END AS health_status
FROM equity_stats;

-- Query monitoring view
SELECT * FROM equity_data_quality_monitor;
```

**Acceptance Thresholds**:
- Data coverage: >90%
- Validation success: >95%
- Anomaly rate: <5%
- Health status: "HEALTHY"

---

### TASK-3.4: Performance Benchmarks
**ID**: EQUITY-3.4
**Priority**: P2 (Medium)
**Estimated Time**: 20 minutes
**Dependencies**: EQUITY-3.2 (Soft)
**Assignee**: Performance Team
**Skills Required**: PostgreSQL, benchmarking

**Description**:
Benchmark query performance with equity account columns.

**Acceptance Criteria**:
- [ ] SELECT * performance degradation <5%
- [ ] Equity-specific queries <1ms with indexes
- [ ] Bulk insert performance unchanged
- [ ] Storage overhead <15%
- [ ] Index effectiveness >80%

**Benchmark Tests**:
```sql
-- Test 1: SELECT * performance (before/after comparison)
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM ticker_fundamentals
WHERE ticker = '005930' AND fiscal_year = 2024;

-- Before (54 columns): ~0.05ms
-- After (62 columns): ~0.052ms
-- Degradation: 4% ✅ PASS (<5% threshold)


-- Test 2: Equity-specific query with index
EXPLAIN (ANALYZE, BUFFERS)
SELECT ticker, fiscal_year, retained_earnings
FROM ticker_fundamentals
WHERE retained_earnings > 0
ORDER BY retained_earnings DESC
LIMIT 100;

-- Expected: Index Scan, <1ms ✅ PASS


-- Test 3: Bulk insert performance
-- Insert 1,000 records with equity accounts
\timing on
INSERT INTO ticker_fundamentals (...);  -- 1,000 rows
\timing off

-- Before: ~2.5s
-- After: ~2.6s
-- Degradation: 4% ✅ PASS (<5% threshold)


-- Test 4: Storage overhead
SELECT
    pg_size_pretty(pg_total_relation_size('ticker_fundamentals')) AS total_size,
    pg_size_pretty(pg_relation_size('ticker_fundamentals')) AS table_size,
    pg_size_pretty(pg_total_relation_size('ticker_fundamentals') -
                   pg_relation_size('ticker_fundamentals')) AS indexes_size;

-- Before: 2.4 MB table + 1.2 MB indexes = 3.6 MB
-- After:  2.64 MB table + 1.4 MB indexes = 4.04 MB
-- Overhead: 12% ✅ PASS (<15% threshold)


-- Test 5: Index effectiveness
EXPLAIN (ANALYZE, BUFFERS)
SELECT ticker, fiscal_year, capital_stock
FROM ticker_fundamentals
WHERE capital_stock > 100000000000
ORDER BY capital_stock DESC;

-- Index scan vs Seq scan comparison
-- Index effectiveness: (seq_scan_time - index_scan_time) / seq_scan_time * 100
-- Expected: >80% ✅ PASS
```

**Performance Report**:
```markdown
# Equity Account Performance Benchmark Results

## Summary
- **SELECT * Degradation**: 4% ✅ PASS
- **Equity Query Performance**: <1ms ✅ PASS
- **Bulk Insert Overhead**: 4% ✅ PASS
- **Storage Overhead**: 12% ✅ PASS
- **Index Effectiveness**: 96% ✅ PASS

## Conclusion
All performance metrics within acceptable thresholds. No optimization required.
```

---

## PHASE 4: Deployment & Migration (Priority: P0 - PRODUCTION)

### TASK-4.1: Staging Deployment
**ID**: EQUITY-4.1
**Priority**: P0 (Critical)
**Estimated Time**: 20 minutes
**Dependencies**: EQUITY-3.1, EQUITY-3.2 (Hard)
**Assignee**: DevOps Team
**Skills Required**: Deployment, PostgreSQL

**Description**:
Deploy schema and code changes to staging environment for final validation.

**Acceptance Criteria**:
- [ ] Schema migration executes successfully in staging
- [ ] All indexes created without errors
- [ ] Code deployed and running
- [ ] Smoke tests pass (3 sample tickers)
- [ ] No errors in logs for 1 hour

**Deployment Steps**:
1. **Database Migration (Staging)**:
   ```bash
   # Connect to staging database
   psql -h staging-db.example.com -U postgres -d quant_platform

   # Execute schema migration
   \i scripts/migrations/add_equity_accounts.sql

   # Verify migration
   \d ticker_fundamentals
   \di idx_fundamentals_*
   ```

2. **Code Deployment**:
   ```bash
   # Deploy enhanced DART API client to staging
   git checkout feature/equity-accounts
   scp modules/dart_api_client.py staging-server:/app/modules/

   # Restart application
   ssh staging-server 'systemctl restart quant-platform'
   ```

3. **Smoke Tests**:
   ```python
   # Run smoke tests with 3 sample tickers
   python tests/smoke_tests/test_equity_accounts_staging.py

   # Test tickers: 005930 (Samsung), 000660 (SK Hynix), 035720 (Kakao)
   # Expected: All 3 tickers have equity accounts populated
   ```

4. **Monitor Logs**:
   ```bash
   # Monitor for 1 hour
   tail -f /var/log/quant-platform/application.log | grep -i equity

   # Check for errors
   grep -i "error\|fail\|exception" /var/log/quant-platform/application.log | grep -i equity

   # Expected: No errors related to equity accounts
   ```

**Rollback Procedure (if needed)**:
```bash
# If staging validation fails, execute rollback
psql -h staging-db.example.com -U postgres -d quant_platform \
  -f scripts/migrations/rollback_equity_accounts.sql
```

---

### TASK-4.2: Production Deployment
**ID**: EQUITY-4.2
**Priority**: P0 (Critical)
**Estimated Time**: 30 minutes
**Dependencies**: EQUITY-4.1 (Hard - staging must pass)
**Assignee**: DevOps Team
**Skills Required**: Production deployment, risk management

**Description**:
Deploy schema and code changes to production with zero downtime.

**Acceptance Criteria**:
- [ ] Zero downtime during deployment
- [ ] Schema migration completes in <1 minute
- [ ] Indexes created with CONCURRENTLY (non-blocking)
- [ ] Code deployed via rolling deployment
- [ ] Health checks pass after deployment
- [ ] No errors for 24 hours post-deployment

**Deployment Plan**:
```yaml
Pre-Deployment Checklist:
  - [ ] Staging validation passed (EQUITY-4.1)
  - [ ] All tests passing (EQUITY-3.x)
  - [ ] Database backup completed
  - [ ] Rollback plan tested
  - [ ] On-call team notified
  - [ ] Maintenance window scheduled (optional - zero downtime)

Deployment Steps:
  1. Database Migration (Production):
     - Execute schema migration (non-blocking ALTER TABLE)
     - Create indexes with CONCURRENTLY
     - Add constraints
     - Duration: <1 minute

  2. Code Deployment (Rolling):
     - Deploy to server-1, wait 5 minutes, monitor
     - Deploy to server-2, wait 5 minutes, monitor
     - Deploy to server-3, wait 5 minutes, monitor
     - Duration: ~20 minutes

  3. Health Checks:
     - Query fundamentals for 10 random tickers
     - Verify equity accounts populated for new data
     - Check error rates in logs
     - Duration: 5 minutes

  4. Monitoring (24 hours):
     - Error rate: Should remain <0.1%
     - Query latency: Should remain <100ms (p95)
     - Validation failures: Log and investigate

Post-Deployment Validation:
  - [ ] Health checks passed
  - [ ] Sample queries returning correct data
  - [ ] No errors in logs
  - [ ] Performance metrics within thresholds
```

**Deployment Commands**:
```bash
# 1. Database migration (production)
psql -h prod-db.example.com -U postgres -d quant_platform \
  -f scripts/migrations/add_equity_accounts.sql

# 2. Rolling deployment (blue-green)
# Deploy to server-1
ssh prod-server-1 'cd /app && git pull && systemctl restart quant-platform'
sleep 300  # Wait 5 minutes, monitor

# Deploy to server-2
ssh prod-server-2 'cd /app && git pull && systemctl restart quant-platform'
sleep 300

# Deploy to server-3
ssh prod-server-3 'cd /app && git pull && systemctl restart quant-platform'

# 3. Health checks
curl https://api.example.com/health
python scripts/health_checks/verify_equity_accounts.py
```

**Monitoring Dashboard**:
```
https://grafana.example.com/d/equity-accounts

Metrics to Monitor (24 hours):
- Query latency (p50, p95, p99)
- Error rate (by error type)
- Validation failures (equity mismatch)
- Data coverage (% of records with equity accounts)
```

---

### TASK-4.3: Rollback Plan Testing
**ID**: EQUITY-4.3
**Priority**: P1 (High)
**Estimated Time**: 15 minutes
**Dependencies**: EQUITY-4.1 (Soft - test in staging first)
**Assignee**: DevOps Team
**Skills Required**: Disaster recovery, SQL

**Description**:
Test rollback procedures in staging to ensure quick recovery if production deployment fails.

**Acceptance Criteria**:
- [ ] Rollback script tested in staging
- [ ] Rollback completes in <2 minutes
- [ ] No data loss after rollback
- [ ] Application functions normally post-rollback
- [ ] Rollback procedure documented

**Rollback Script**:
```sql
-- scripts/migrations/rollback_equity_accounts.sql

BEGIN;

-- Step 1: Remove constraints
ALTER TABLE ticker_fundamentals
DROP CONSTRAINT IF EXISTS chk_treasury_stock_negative,
DROP CONSTRAINT IF EXISTS chk_capital_stock_positive;

-- Step 2: Drop indexes
DROP INDEX IF EXISTS idx_fundamentals_capital_stock;
DROP INDEX IF EXISTS idx_fundamentals_retained_earnings;
DROP INDEX IF EXISTS idx_fundamentals_treasury_stock;
DROP INDEX IF EXISTS idx_fundamentals_equity_complete;

-- Step 3: Drop columns (data will be lost - ensure backup exists)
ALTER TABLE ticker_fundamentals
DROP COLUMN IF EXISTS capital_stock,
DROP COLUMN IF EXISTS capital_surplus,
DROP COLUMN IF EXISTS retained_earnings,
DROP COLUMN IF EXISTS treasury_stock,
DROP COLUMN IF EXISTS other_comprehensive_income,
DROP COLUMN IF EXISTS non_controlling_interest,
DROP COLUMN IF EXISTS unappropriated_retained_earnings,
DROP COLUMN IF EXISTS legal_reserve;

COMMIT;

-- Verification
\d ticker_fundamentals  -- Should show 54 columns (original)
```

**Rollback Test Procedure**:
```bash
# 1. Deploy to staging (if not already done)
psql -h staging-db -U postgres -d quant_platform \
  -f scripts/migrations/add_equity_accounts.sql

# 2. Verify deployment
psql -h staging-db -U postgres -d quant_platform \
  -c "\d ticker_fundamentals"  # Should show 62 columns

# 3. Execute rollback
psql -h staging-db -U postgres -d quant_platform \
  -f scripts/migrations/rollback_equity_accounts.sql

# 4. Verify rollback
psql -h staging-db -U postgres -d quant_platform \
  -c "\d ticker_fundamentals"  # Should show 54 columns

# 5. Test application
curl https://staging-api.example.com/fundamentals/005930
# Should return data without equity accounts (backward compatible)

# 6. Re-deploy for continued testing
psql -h staging-db -U postgres -d quant_platform \
  -f scripts/migrations/add_equity_accounts.sql
```

**Rollback Documentation**:
```markdown
# Production Rollback Procedure

## When to Rollback
- Critical bug discovered affecting data integrity
- Performance degradation >20%
- Error rate >1%
- Validation failure rate >20%

## Rollback Steps (Production)
1. **Notify Team**: Alert on-call and stakeholders
2. **Database Rollback**:
   ```bash
   psql -h prod-db -U postgres -d quant_platform \
     -f scripts/migrations/rollback_equity_accounts.sql
   ```
   Duration: <2 minutes

3. **Code Rollback** (rolling):
   ```bash
   # Revert to previous version
   git revert <commit-hash>
   # Deploy to all servers
   ```
   Duration: ~15 minutes

4. **Validation**:
   - Query 10 random tickers
   - Verify no errors in logs
   - Check application health

5. **Post-Mortem**:
   - Document root cause
   - Create fix plan
   - Schedule re-deployment

## Data Recovery
- Equity account data will be lost during rollback
- Backup can be restored from pre-deployment snapshot
- Re-run backfill after fixes deployed
```

---

## PHASE 5: Data Backfill (Priority: P2 - POST-DEPLOYMENT)

### TASK-5.1: Backfill Script Development
**ID**: EQUITY-5.1
**Priority**: P2 (Medium)
**Estimated Time**: 30 minutes
**Dependencies**: EQUITY-4.2 (Hard - production must be deployed)
**Assignee**: Backend Team
**Skills Required**: Python, PostgreSQL, DART API

**Description**:
Develop script to backfill equity accounts for existing DART fundamental data.

**Acceptance Criteria**:
- [ ] Script processes all DART records with NULL equity accounts
- [ ] Progress logging every 100 records
- [ ] Error handling with retry logic (3 attempts)
- [ ] Dry-run mode for validation
- [ ] Estimated completion time <2 hours (6,000 records)

**Implementation**:
```python
#!/usr/bin/env python3
"""
Backfill equity accounts for existing DART fundamental data

Usage:
    python scripts/backfill_equity_accounts.py --dry-run
    python scripts/backfill_equity_accounts.py --execute --limit 1000
    python scripts/backfill_equity_accounts.py --execute  # Full backfill
"""

import os
import sys
import time
import argparse
import logging
from typing import List, Tuple

import psycopg2
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.dart_api_client import DARTApiClient

# Load environment
load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('logs/backfill_equity_accounts.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_records_to_backfill(conn, limit: int = None) -> List[Tuple]:
    """Get list of records needing equity account backfill"""

    cursor = conn.cursor()

    query = """
        SELECT DISTINCT
            tf.ticker,
            tf.fiscal_year,
            t.name,
            COUNT(*) OVER() AS total_count
        FROM ticker_fundamentals tf
        JOIN tickers t ON tf.ticker = t.ticker AND tf.region = t.region
        WHERE tf.data_source = 'DART'
          AND tf.capital_stock IS NULL
          AND tf.fiscal_year IS NOT NULL
        ORDER BY tf.fiscal_year DESC, tf.ticker
    """

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    records = cursor.fetchall()
    cursor.close()

    return records


def get_corp_code(ticker: str) -> str:
    """
    Get DART corp_code for ticker

    TODO: Implement corp_code lookup from mapping file or database
    For now, return placeholder
    """
    # Placeholder - actual implementation would query corp_code mapping
    corp_code_mapping = {
        '005930': '00126380',  # Samsung Electronics
        '000660': '00164779',  # SK Hynix
        '035720': '00401731',  # Kakao
        # ... add more mappings
    }

    return corp_code_mapping.get(ticker, None)


def backfill_equity_accounts(dry_run: bool = True, limit: int = None):
    """Backfill equity account breakdown for existing DART data"""

    # Database connection
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        database=os.getenv('POSTGRES_DB', 'quant_platform'),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD')
    )

    # Get records to backfill
    logger.info("🔍 Discovering records to backfill...")
    records = get_records_to_backfill(conn, limit)

    if not records:
        logger.info("✅ No records to backfill")
        return

    total_count = records[0][3] if records else 0
    logger.info(f"📊 Found {total_count} records to backfill")

    if dry_run:
        logger.info("🔍 DRY RUN mode - no changes will be made")
        logger.info(f"Sample records: {records[:5]}")
        return

    # Initialize DART client
    dart_client = DARTApiClient()

    # Backfill counters
    success_count = 0
    error_count = 0
    skip_count = 0

    # Progress tracking
    start_time = time.time()

    for idx, (ticker, fiscal_year, name, _) in enumerate(records, 1):
        try:
            logger.info(f"[{idx}/{total_count}] Processing {ticker} ({name}) - {fiscal_year}...")

            # Get corp_code
            corp_code = get_corp_code(ticker)
            if not corp_code:
                logger.warning(f"  ⏭️ Skipping {ticker}: corp_code not found")
                skip_count += 1
                continue

            # Fetch financial data from DART
            metrics_list = dart_client.get_historical_fundamentals(
                ticker=ticker,
                corp_code=corp_code,
                start_year=fiscal_year,
                end_year=fiscal_year
            )

            if not metrics_list:
                logger.warning(f"  ⚠️ No data returned for {ticker} {fiscal_year}")
                error_count += 1
                continue

            metrics = metrics_list[0]

            # Verify equity accounts extracted
            if not metrics.get('capital_stock') and not metrics.get('retained_earnings'):
                logger.warning(f"  ⚠️ No equity accounts in DART data for {ticker} {fiscal_year}")
                error_count += 1
                continue

            # Update database
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE ticker_fundamentals
                SET capital_stock = %s,
                    capital_surplus = %s,
                    retained_earnings = %s,
                    treasury_stock = %s,
                    other_comprehensive_income = %s,
                    non_controlling_interest = %s,
                    unappropriated_retained_earnings = %s,
                    legal_reserve = %s
                WHERE ticker = %s
                  AND fiscal_year = %s
                  AND data_source = 'DART'
            """, (
                metrics.get('capital_stock'),
                metrics.get('capital_surplus'),
                metrics.get('retained_earnings'),
                metrics.get('treasury_stock'),
                metrics.get('other_comprehensive_income'),
                metrics.get('non_controlling_interest'),
                metrics.get('unappropriated_retained_earnings'),
                metrics.get('legal_reserve'),
                ticker,
                fiscal_year
            ))
            cursor.close()

            success_count += 1
            logger.info(f"  ✅ Updated {ticker} {fiscal_year}")

            # Checkpoint every 100 records
            if idx % 100 == 0:
                conn.commit()
                elapsed = time.time() - start_time
                rate = idx / elapsed if elapsed > 0 else 0
                eta = (total_count - idx) / rate if rate > 0 else 0
                logger.info(
                    f"📊 Checkpoint: {success_count}/{idx} successful "
                    f"(rate: {rate:.1f} records/s, ETA: {eta/60:.1f} min)"
                )

        except Exception as e:
            logger.error(f"  ❌ Error processing {ticker} {fiscal_year}: {e}")
            error_count += 1
            continue

    # Final commit
    conn.commit()

    # Summary
    elapsed = time.time() - start_time
    logger.info("\n" + "="*60)
    logger.info("📊 Backfill Summary:")
    logger.info(f"  Total records: {total_count}")
    logger.info(f"  ✅ Success: {success_count} ({success_count/total_count*100:.1f}%)")
    logger.info(f"  ❌ Errors: {error_count} ({error_count/total_count*100:.1f}%)")
    logger.info(f"  ⏭️ Skipped: {skip_count} ({skip_count/total_count*100:.1f}%)")
    logger.info(f"  ⏱️ Duration: {elapsed/60:.1f} minutes")
    logger.info(f"  ⚡ Rate: {total_count/elapsed:.1f} records/second")
    logger.info("="*60)

    conn.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Backfill equity accounts for DART data')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview changes without executing')
    parser.add_argument('--execute', action='store_true',
                       help='Execute backfill (use with caution)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of records to process')

    args = parser.parse_args()

    if args.execute:
        confirm = input("⚠️ This will modify production data. Continue? (yes/no): ")
        if confirm.lower() != 'yes':
            logger.info("Aborted by user")
            return

        backfill_equity_accounts(dry_run=False, limit=args.limit)
    else:
        backfill_equity_accounts(dry_run=True, limit=args.limit)


if __name__ == '__main__':
    main()
```

**Testing**:
```bash
# Test in development
python scripts/backfill_equity_accounts.py --dry-run --limit 10

# Test with small batch
python scripts/backfill_equity_accounts.py --execute --limit 100

# Full backfill
python scripts/backfill_equity_accounts.py --execute
```

---

### TASK-5.2: Dry-Run Execution
**ID**: EQUITY-5.2
**Priority**: P2 (Medium)
**Estimated Time**: 15 minutes
**Dependencies**: EQUITY-5.1 (Hard)
**Assignee**: Backend Team
**Skills Required**: Validation, data analysis

**Description**:
Execute backfill in dry-run mode to validate data and identify potential issues.

**Acceptance Criteria**:
- [ ] Dry-run completes without errors
- [ ] Sample output validated (10 random records)
- [ ] Corp_code mapping verified for top 100 stocks
- [ ] Estimated completion time calculated
- [ ] No data quality issues identified

**Execution**:
```bash
# Run dry-run for all records
python scripts/backfill_equity_accounts.py --dry-run

# Expected output:
# 📊 Found 6,000 records to backfill
# 🔍 DRY RUN mode - no changes will be made
# Sample records: [('005930', 2024, 'Samsung Electronics', 6000), ...]
```

**Validation Queries**:
```sql
-- Check current coverage (before backfill)
SELECT
    COUNT(*) AS total_dart_records,
    COUNT(capital_stock) AS with_equity_accounts,
    COUNT(capital_stock)::FLOAT / COUNT(*) * 100 AS coverage_pct
FROM ticker_fundamentals
WHERE data_source = 'DART';

-- Expected: 0% coverage (new feature)


-- Identify missing corp_codes
SELECT DISTINCT ticker, name
FROM ticker_fundamentals tf
JOIN tickers t ON tf.ticker = t.ticker AND tf.region = t.region
WHERE tf.data_source = 'DART'
  AND tf.capital_stock IS NULL
  AND tf.ticker NOT IN (
      '005930', '000660', '035720'  -- Known corp_codes
  )
ORDER BY ticker
LIMIT 20;

-- Action: Add missing corp_codes to mapping
```

---

### TASK-5.3: Production Backfill
**ID**: EQUITY-5.3
**Priority**: P2 (Medium)
**Estimated Time**: 2 hours (background process)
**Dependencies**: EQUITY-5.2 (Hard)
**Assignee**: Backend Team
**Skills Required**: Production operations, monitoring

**Description**:
Execute backfill in production to populate equity accounts for existing DART data.

**Acceptance Criteria**:
- [ ] Backfill completes in <2 hours
- [ ] Success rate >90%
- [ ] No production errors or downtime
- [ ] Progress monitored in real-time
- [ ] Data quality validated after completion

**Execution Plan**:
```bash
# 1. Start backfill in background
nohup python scripts/backfill_equity_accounts.py --execute \
  > logs/backfill_equity_$(date +%Y%m%d_%H%M%S).log 2>&1 &

# Get process ID
BACKFILL_PID=$!
echo "Backfill started with PID: $BACKFILL_PID"

# 2. Monitor progress in real-time
tail -f logs/backfill_equity_*.log

# 3. Check process status
ps aux | grep backfill_equity_accounts

# 4. Monitor database load
psql -h prod-db -U postgres -d quant_platform -c "
    SELECT
        pid,
        usename,
        application_name,
        state,
        query_start,
        LEFT(query, 100) AS query_preview
    FROM pg_stat_activity
    WHERE query LIKE '%ticker_fundamentals%'
      AND state = 'active';
"

# 5. Check error rate
grep -i "error\|fail" logs/backfill_equity_*.log | wc -l

# 6. Wait for completion
wait $BACKFILL_PID
echo "Backfill completed with exit code: $?"
```

**Monitoring Metrics**:
- Processing rate: Target >1 record/second
- Error rate: Target <10%
- Database CPU: Should remain <50%
- Memory usage: Should remain <80%

---

### TASK-5.4: Validation & Verification
**ID**: EQUITY-5.4
**Priority**: P2 (Medium)
**Estimated Time**: 30 minutes
**Dependencies**: EQUITY-5.3 (Hard)
**Assignee**: QA Team
**Skills Required**: SQL, data validation

**Description**:
Validate backfill results and verify data quality across all records.

**Acceptance Criteria**:
- [ ] Data coverage >90%
- [ ] Validation success rate >95%
- [ ] No critical anomalies detected
- [ ] Sample verification passed (100 random records)
- [ ] Data quality report generated

**Validation Queries**:
```sql
-- 1. Final coverage report
SELECT
    COUNT(*) AS total_dart_records,
    COUNT(capital_stock) AS with_equity_accounts,
    COUNT(capital_stock)::FLOAT / COUNT(*) * 100 AS coverage_pct
FROM ticker_fundamentals
WHERE data_source = 'DART';

-- Expected: >90% coverage


-- 2. Validation success rate
WITH equity_validation AS (
    SELECT
        ticker,
        fiscal_year,
        ABS(
            total_equity - (
                COALESCE(capital_stock, 0) +
                COALESCE(capital_surplus, 0) +
                COALESCE(retained_earnings, 0) +
                COALESCE(other_comprehensive_income, 0) +
                COALESCE(non_controlling_interest, 0) -
                ABS(COALESCE(treasury_stock, 0))
            )
        ) / NULLIF(ABS(total_equity), 0) * 100 AS deviation_pct
    FROM ticker_fundamentals
    WHERE data_source = 'DART'
      AND capital_stock IS NOT NULL
)
SELECT
    COUNT(*) AS total_with_equity,
    COUNT(CASE WHEN deviation_pct <= 5.0 THEN 1 END) AS valid_records,
    COUNT(CASE WHEN deviation_pct > 5.0 THEN 1 END) AS invalid_records,
    COUNT(CASE WHEN deviation_pct <= 5.0 THEN 1 END)::FLOAT / COUNT(*) * 100 AS validation_success_rate
FROM equity_validation;

-- Expected: >95% validation success rate


-- 3. Sample verification (100 random records)
WITH random_sample AS (
    SELECT *
    FROM ticker_fundamentals
    WHERE data_source = 'DART'
      AND capital_stock IS NOT NULL
    ORDER BY RANDOM()
    LIMIT 100
)
SELECT
    ticker,
    fiscal_year,
    total_equity,
    capital_stock,
    retained_earnings,
    treasury_stock,
    (
        COALESCE(capital_stock, 0) +
        COALESCE(capital_surplus, 0) +
        COALESCE(retained_earnings, 0) +
        COALESCE(other_comprehensive_income, 0) +
        COALESCE(non_controlling_interest, 0) -
        ABS(COALESCE(treasury_stock, 0))
    ) AS calculated_equity,
    ABS(
        total_equity - (
            COALESCE(capital_stock, 0) +
            COALESCE(capital_surplus, 0) +
            COALESCE(retained_earnings, 0) +
            COALESCE(other_comprehensive_income, 0) +
            COALESCE(non_controlling_interest, 0) -
            ABS(COALESCE(treasury_stock, 0))
        )
    ) / NULLIF(ABS(total_equity), 0) * 100 AS deviation_pct
FROM random_sample
ORDER BY deviation_pct DESC;

-- Manual review: Check top 10 deviations for validity


-- 4. Anomaly detection
SELECT
    COUNT(*) AS anomaly_count,
    COUNT(*)::FLOAT / (SELECT COUNT(*) FROM ticker_fundamentals WHERE data_source = 'DART' AND capital_stock IS NOT NULL) * 100 AS anomaly_rate
FROM ticker_fundamentals
WHERE data_source = 'DART'
  AND capital_stock IS NOT NULL
  AND (
      capital_stock > total_equity * 2
      OR (retained_earnings < 0 AND ABS(retained_earnings) > ABS(total_equity) * 0.5)
      OR treasury_stock > 0
  );

-- Expected: <5% anomaly rate


-- 5. Query data quality monitoring view
SELECT * FROM equity_data_quality_monitor;

-- Expected: health_status = '✅ HEALTHY'
```

**Validation Report**:
```markdown
# Equity Account Backfill Validation Report

## Summary
- **Total DART Records**: 6,000
- **Records with Equity Accounts**: 5,520 (92%)
- **Validation Success Rate**: 97.2%
- **Anomaly Rate**: 2.3%
- **Health Status**: ✅ HEALTHY

## Coverage by Year
- 2024: 98%
- 2023: 95%
- 2022: 90%
- 2021: 85%
- 2020: 80%

## Top 10 Validation Failures
1. Ticker 123456 (2024): 12.5% deviation - [reason]
2. Ticker 234567 (2023): 8.3% deviation - [reason]
...

## Anomalies Detected
- 48 records with capital_stock > 2x total_equity (investigate)
- 12 records with large negative retained_earnings (verified correct)
- 0 records with positive treasury_stock (✅ PASS)

## Conclusion
Backfill successful. Data quality within acceptable thresholds.
```

---

## PHASE 6: Documentation & Monitoring (Priority: P3 - ONGOING)

### TASK-6.1: User Documentation
**ID**: EQUITY-6.1
**Priority**: P3 (Low)
**Estimated Time**: 30 minutes
**Dependencies**: EQUITY-5.4 (Soft)
**Assignee**: Documentation Team
**Skills Required**: Technical writing

**Description**:
Create user-facing documentation for equity account analysis features.

**Acceptance Criteria**:
- [ ] User guide created with examples
- [ ] SQL query examples provided
- [ ] Use case documentation complete
- [ ] Markdown formatting correct
- [ ] Published to docs portal

**Documentation Outline**:
```markdown
# Equity Account Analysis Guide

## Overview
The `ticker_fundamentals` table now includes detailed equity account breakdown:
- Capital stock (자본금)
- Capital surplus (자본잉여금)
- Retained earnings (이익잉여금)
- Treasury stock (자기주식)
- Other comprehensive income (기타포괄손익누계액)
- Non-controlling interest (비지배지분)

## Use Cases

### 1. Negative Equity Analysis
Identify whether negative equity is due to:
- Real debt erosion (financial distress)
- Treasury stock buybacks (shareholder returns)

**Example Query**:
```sql
SELECT
    ticker,
    fiscal_year,
    total_equity,
    capital_stock,
    retained_earnings,
    treasury_stock,
    (capital_stock + capital_surplus + retained_earnings) AS operating_equity
FROM ticker_fundamentals
WHERE total_equity < 0
  AND fiscal_year = 2024
ORDER BY operating_equity DESC;
```

### 2. Retained Earnings Growth Tracking
Identify companies with consistent earnings reinvestment:

**Example Query**:
```sql
WITH re_growth AS (
    SELECT
        ticker,
        fiscal_year,
        retained_earnings,
        LAG(retained_earnings) OVER (PARTITION BY ticker ORDER BY fiscal_year) AS prev_year_re
    FROM ticker_fundamentals
    WHERE retained_earnings IS NOT NULL
)
SELECT
    ticker,
    fiscal_year,
    retained_earnings,
    prev_year_re,
    (retained_earnings - prev_year_re) / NULLIF(prev_year_re, 0) * 100 AS re_growth_pct
FROM re_growth
WHERE fiscal_year = 2024
  AND re_growth_pct > 20  -- 20% YoY growth
ORDER BY re_growth_pct DESC;
```

### 3. Shares Outstanding Estimation
Estimate shares outstanding from capital stock:

**Example Query**:
```sql
SELECT
    ticker,
    fiscal_year,
    capital_stock,
    capital_stock / 5000 AS estimated_shares,  -- Assuming 5,000 KRW par value
    shares_outstanding AS reported_shares,
    ABS(capital_stock / 5000 - shares_outstanding) / NULLIF(shares_outstanding, 0) * 100 AS estimation_error_pct
FROM ticker_fundamentals
WHERE capital_stock IS NOT NULL
  AND shares_outstanding IS NOT NULL
  AND fiscal_year = 2024;
```

## API Integration

### Python Example
```python
from modules.dart_api_client import DARTApiClient

dart_client = DARTApiClient()

# Get fundamental data with equity accounts
metrics = dart_client.get_fundamental_metrics(
    ticker='005930',
    corp_code='00126380'
)

print(f"Capital Stock: {metrics['capital_stock']:,.0f}")
print(f"Retained Earnings: {metrics['retained_earnings']:,.0f}")
print(f"Treasury Stock: {metrics['treasury_stock']:,.0f}")
```

## Data Quality

### Validation
All equity account data includes automatic validation:
- Equity breakdown must sum to total_equity within 5%
- Warnings logged for validation failures
- Monitoring view available: `equity_data_quality_monitor`

### Query Monitoring View
```sql
SELECT * FROM equity_data_quality_monitor;
```

## Troubleshooting

### Missing Equity Accounts
If equity accounts are NULL:
1. Check if data_source is 'DART' (equity accounts only for DART data)
2. Verify fiscal_year coverage (backfill may be in progress)
3. Check `backfill_equity_accounts.log` for errors

### Validation Failures
If validation fails (deviation >5%):
1. Check DART data source for inconsistencies
2. Verify account name mappings
3. Review equity_data_quality_monitor for systematic issues
```

---

### TASK-6.2: API Documentation
**ID**: EQUITY-6.2
**Priority**: P3 (Low)
**Estimated Time**: 20 minutes
**Dependencies**: EQUITY-6.1 (Soft)
**Assignee**: Documentation Team
**Skills Required**: API documentation

**Description**:
Document enhanced DART API methods and equity account data structures.

**Acceptance Criteria**:
- [ ] Method signatures documented
- [ ] Return values specified
- [ ] Examples provided
- [ ] Docstrings updated in code
- [ ] API reference published

**API Documentation**:
```python
# modules/dart_api_client.py

class DARTApiClient:
    """
    DART Open API client for fundamental data extraction

    Enhanced Features (v2.0):
    - Equity account breakdown (capital stock, retained earnings, etc.)
    - Automatic validation and quality checks
    - Fuzzy matching for account name variations
    """

    def _extract_equity_accounts(self, item_lookup: Dict[str, float]) -> Dict:
        """
        Extract equity account breakdown from DART financial statement items

        Args:
            item_lookup (Dict[str, float]): Mapping of account names to amounts
                Example: {'자본금': 100000000, '이익잉여금': 200000000, ...}

        Returns:
            Dict with equity account values:
            {
                'capital_stock': 100000000,           # 자본금
                'capital_surplus': 50000000,          # 자본잉여금
                'retained_earnings': 200000000,       # 이익잉여금
                'treasury_stock': -30000000,          # 자기주식 (negative)
                'other_comprehensive_income': 0,      # 기타포괄손익누계액
                'non_controlling_interest': 0,        # 비지배지분
                'unappropriated_retained_earnings': None,  # Optional
                'legal_reserve': None                 # Optional
            }

        Note:
            - Uses priority-ordered pattern matching for account names
            - Treasury stock normalized to negative value
            - Returns None for missing accounts (graceful handling)

        Example:
            >>> item_lookup = {'자본금': 100000000, '이익잉여금': 200000000}
            >>> equity = dart_client._extract_equity_accounts(item_lookup)
            >>> equity['capital_stock']
            100000000
        """
        pass


    def _validate_equity_breakdown(self, reported_equity: float,
                                   equity_components: Dict) -> Dict:
        """
        Validate equity breakdown against reported total equity

        Args:
            reported_equity (float): Total equity from DART (자본총계)
            equity_components (Dict): Equity account breakdown from _extract_equity_accounts()

        Returns:
            Dict with validation results:
            {
                'is_valid': True,              # True if deviation <= 5%
                'reported_equity': 400000000,
                'calculated_equity': 420000000,
                'deviation_pct': 5.0,
                'message': 'Equity mismatch: ...'  # Only if invalid
            }

        Validation Logic:
            calculated_equity = (
                capital_stock +
                capital_surplus +
                retained_earnings +
                other_comprehensive_income +
                non_controlling_interest -
                |treasury_stock|
            )

            deviation_pct = |reported - calculated| / |reported| * 100
            is_valid = deviation_pct <= 5.0

        Example:
            >>> equity_components = {'capital_stock': 100000000, ...}
            >>> result = dart_client._validate_equity_breakdown(400000000, equity_components)
            >>> result['is_valid']
            True
        """
        pass
```

---

### TASK-6.3: Monitoring Dashboard
**ID**: EQUITY-6.3
**Priority**: P3 (Low)
**Estimated Time**: 40 minutes
**Dependencies**: EQUITY-5.4 (Soft)
**Assignee**: DevOps Team
**Skills Required**: Grafana, SQL

**Description**:
Create Grafana dashboard for equity account data quality monitoring.

**Acceptance Criteria**:
- [ ] Dashboard created in Grafana
- [ ] 5 key metrics visualized
- [ ] Alerts configured for anomalies
- [ ] Dashboard exported to JSON
- [ ] Team has view access

**Dashboard Panels**:

1. **Data Coverage Trend**
   - Metric: % of DART records with equity accounts
   - Visualization: Time series line chart
   - Target: >90%
   - Alert: <80% for 24 hours

2. **Validation Success Rate**
   - Metric: % of records passing 5% validation
   - Visualization: Gauge chart
   - Target: >95%
   - Alert: <90% for 1 hour

3. **Top Validation Failures**
   - Metric: Records with >5% deviation
   - Visualization: Table with ticker, year, deviation%
   - Limit: Top 20
   - Alert: >100 failures

4. **Equity Account Distribution**
   - Metric: Count by account availability
   - Visualization: Stacked bar chart
   - Categories: Has capital_stock, Has RE, Has treasury_stock
   - No alert

5. **Backfill Progress**
   - Metric: Records backfilled per hour
   - Visualization: Time series bar chart
   - Target: >100 records/hour
   - Alert: 0 records for 2 hours (stuck)

**Grafana JSON**:
```json
{
  "dashboard": {
    "title": "Equity Account Data Quality",
    "panels": [
      {
        "id": 1,
        "title": "Data Coverage Trend",
        "targets": [
          {
            "rawSql": "SELECT NOW() AS time, COUNT(capital_stock)::FLOAT / COUNT(*) * 100 AS coverage_pct FROM ticker_fundamentals WHERE data_source = 'DART'"
          }
        ],
        "type": "timeseries"
      },
      {
        "id": 2,
        "title": "Validation Success Rate",
        "targets": [
          {
            "rawSql": "SELECT * FROM equity_data_quality_monitor"
          }
        ],
        "type": "gauge"
      }
      // ... more panels
    ],
    "alerts": [
      {
        "name": "Low Coverage Alert",
        "condition": "coverage_pct < 80",
        "for": "24h",
        "severity": "warning"
      },
      {
        "name": "Low Validation Rate Alert",
        "condition": "validation_success_rate < 90",
        "for": "1h",
        "severity": "critical"
      }
    ]
  }
}
```

---

### TASK-6.4: Use Case Examples
**ID**: EQUITY-6.4
**Priority**: P3 (Low)
**Estimated Time**: 30 minutes
**Dependencies**: EQUITY-6.1 (Soft)
**Assignee**: Product Team
**Skills Required**: SQL, Python, use case design

**Description**:
Create example scripts demonstrating equity account analysis use cases.

**Acceptance Criteria**:
- [ ] 3 Python examples created
- [ ] 5 SQL examples created
- [ ] Examples tested and verified
- [ ] Published to examples/ directory
- [ ] README with usage instructions

**Example Scripts**:

```python
# examples/equity_account_analysis/negative_equity_analyzer.py
"""
Negative Equity Root Cause Analyzer

Identifies whether negative equity is due to:
- Real financial distress (debt erosion)
- Treasury stock buybacks (shareholder value return)
- Mixed factors

Usage:
    python negative_equity_analyzer.py --ticker 005930
    python negative_equity_analyzer.py --all --year 2024
"""

import argparse
import psycopg2
from typing import Dict, List


def analyze_negative_equity(ticker: str, fiscal_year: int) -> Dict:
    """Analyze root cause of negative equity"""

    conn = psycopg2.connect(database='quant_platform')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            total_equity,
            capital_stock,
            capital_surplus,
            retained_earnings,
            treasury_stock,
            other_comprehensive_income
        FROM ticker_fundamentals
        WHERE ticker = %s AND fiscal_year = %s
    """, (ticker, fiscal_year))

    row = cursor.fetchone()
    if not row:
        return {'error': 'Data not found'}

    total_eq, cap_stock, cap_surplus, ret_earn, treas_stock, oci = row

    # Calculate operating equity (excluding treasury stock)
    operating_equity = (cap_stock or 0) + (cap_surplus or 0) + (ret_earn or 0)

    # Categorize
    if total_eq >= 0:
        category = 'POSITIVE_EQUITY'
        interpretation = 'Normal capital structure'
    elif operating_equity > 0 and abs(treas_stock or 0) > abs(total_eq):
        category = 'TREASURY_STOCK_BUYBACK'
        interpretation = (
            f"Negative equity ({total_eq:,.0f}) primarily due to "
            f"treasury stock buybacks ({treas_stock:,.0f}). "
            f"Operating equity is positive ({operating_equity:,.0f})."
        )
    elif operating_equity < 0:
        category = 'DEBT_EROSION'
        interpretation = (
            f"Operating equity is negative ({operating_equity:,.0f}), "
            f"indicating real financial distress."
        )
    else:
        category = 'MIXED'
        interpretation = f"Mixed factors contributing to negative equity"

    return {
        'ticker': ticker,
        'fiscal_year': fiscal_year,
        'category': category,
        'total_equity': total_eq,
        'operating_equity': operating_equity,
        'treasury_stock': treas_stock,
        'interpretation': interpretation
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ticker', help='Ticker to analyze')
    parser.add_argument('--year', type=int, default=2024)
    parser.add_argument('--all', action='store_true', help='Analyze all negative equity stocks')

    args = parser.parse_args()

    if args.ticker:
        result = analyze_negative_equity(args.ticker, args.year)
        print(f"\n{result['ticker']} ({args.year})")
        print(f"Category: {result['category']}")
        print(f"Interpretation: {result['interpretation']}\n")
    elif args.all:
        # Analyze all negative equity stocks
        conn = psycopg2.connect(database='quant_platform')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT ticker
            FROM ticker_fundamentals
            WHERE total_equity < 0 AND fiscal_year = %s
        """, (args.year,))

        for (ticker,) in cursor.fetchall():
            result = analyze_negative_equity(ticker, args.year)
            print(f"{ticker}: {result['category']}")


if __name__ == '__main__':
    main()
```

---

## Execution Timeline

### Day 1: Foundation & Development (3.5 hours)
- **08:00-08:30** (30 min): TASK-1.1 Database Schema Extension
- **08:30-08:45** (15 min): TASK-1.2 Index Creation
- **08:45-09:00** (15 min): TASK-1.3 Constraint Setup
- **09:00-09:30** (30 min): TASK-2.1 Account Pattern Mapping (parallel)
- **09:30-10:15** (45 min): TASK-2.2 Equity Extraction Logic
- **10:15-10:45** (30 min): TASK-2.3 Validation Logic
- **10:45-11:15** (30 min): TASK-2.4 Integration
- **11:15-12:30** (75 min): TASK-3.1 Unit Tests

### Day 2: Testing & Deployment (2 hours)
- **09:00-09:45** (45 min): TASK-3.2 Integration Tests
- **09:45-10:30** (45 min): TASK-3.3 Data Quality Tests
- **10:30-11:00** (30 min): TASK-4.1 Staging Deployment
- **14:00-14:45** (45 min): TASK-4.2 Production Deployment

### Day 3: Backfill & Documentation (3 hours)
- **09:00-09:45** (45 min): TASK-5.1 Backfill Script
- **09:45-10:15** (30 min): TASK-5.2 Dry-Run
- **10:15-12:15** (2 hours): TASK-5.3 Production Backfill (background)
- **14:00-14:45** (45 min): TASK-5.4 Validation
- **15:00-17:00** (2 hours): TASK-6.x Documentation (parallel)

**Total Duration**: ~8.5 hours (actual work), spread over 3 days

---

## Priority Summary

### P0 (Critical) - Must Complete First
1. TASK-1.1: Database Schema Extension
2. TASK-1.2: Index Creation
3. TASK-2.1: Account Pattern Mapping
4. TASK-2.2: Equity Extraction Logic
5. TASK-2.3: Validation Logic
6. TASK-2.4: Integration
7. TASK-4.1: Staging Deployment
8. TASK-4.2: Production Deployment

### P1 (High) - Complete Before Production
1. TASK-1.3: Constraint Setup
2. TASK-3.1: Unit Tests
3. TASK-3.2: Integration Tests
4. TASK-4.3: Rollback Plan Testing

### P2 (Medium) - Post-Deployment
1. TASK-3.3: Data Quality Tests
2. TASK-3.4: Performance Benchmarks
3. TASK-5.1: Backfill Script
4. TASK-5.2: Dry-Run
5. TASK-5.3: Production Backfill
6. TASK-5.4: Validation

### P3 (Low) - Ongoing/Optional
1. TASK-6.1: User Documentation
2. TASK-6.2: API Documentation
3. TASK-6.3: Monitoring Dashboard
4. TASK-6.4: Use Case Examples

---

## Dependencies Visualization

```
┌──────────────────────────────────────────────────────────────┐
│                    Critical Path (P0)                         │
└──────────────────────────────────────────────────────────────┘
    TASK-1.1 (DB Schema)
         │
         ├─────► TASK-1.2 (Indexes)
         │
    TASK-2.1 (Pattern Mapping - Parallel)
         │
         ▼
    TASK-2.2 (Extraction Logic)
         │
         ▼
    TASK-2.3 (Validation Logic)
         │
         ▼
    TASK-2.4 (Integration)
         │
         ▼
    TASK-3.1 (Unit Tests)
         │
         ▼
    TASK-4.1 (Staging Deploy)
         │
         ▼
    TASK-4.2 (Production Deploy)

┌──────────────────────────────────────────────────────────────┐
│              Post-Deployment Path (P2)                        │
└──────────────────────────────────────────────────────────────┘
    TASK-4.2 (Production)
         │
         ▼
    TASK-5.1 (Backfill Script)
         │
         ▼
    TASK-5.2 (Dry-Run)
         │
         ▼
    TASK-5.3 (Production Backfill)
         │
         ▼
    TASK-5.4 (Validation)

┌──────────────────────────────────────────────────────────────┐
│              Documentation Path (P3 - Parallel)               │
└──────────────────────────────────────────────────────────────┘
    TASK-6.1, TASK-6.2, TASK-6.3, TASK-6.4
    (Can execute in parallel with other tasks)
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Schema Migration Success** | 100% | No errors during ALTER TABLE |
| **Code Deployment Success** | 100% | All servers deployed successfully |
| **Test Pass Rate** | >95% | Unit + Integration tests passing |
| **Data Coverage** | >90% | % of DART records with equity accounts |
| **Validation Success Rate** | >95% | % of records passing 5% validation |
| **Query Performance** | <5% degradation | Before/after benchmark comparison |
| **Production Uptime** | 100% | No downtime during deployment |
| **Backfill Success Rate** | >90% | % of records backfilled successfully |

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Schema migration fails | Low | High | Test in staging, have rollback ready |
| Data quality issues | Medium | Medium | Implement validation, set 5% tolerance |
| Performance degradation | Low | Medium | Benchmark before/after, optimize indexes |
| Backfill errors | Medium | Low | Retry logic, error logging, manual review |
| Production incident | Very Low | High | Staging validation, rollback plan, monitoring |

---

**Document Control**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-06 | Quant Platform Team | Initial task breakdown |

---

**Next Steps**: Review task breakdown → Assign resources → Begin Phase 1 execution
