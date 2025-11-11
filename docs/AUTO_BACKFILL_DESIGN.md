# Auto-Backfill System Design - Backtesting Engine Data Provider

**Author**: Spock Quant Platform
**Date**: 2025-10-29
**Version**: 1.0.0
**Status**: Design Specification

---

## 📋 Executive Summary

**Purpose**: Automated data backfilling system that seamlessly fetches missing data from external APIs when PostgreSQL database lacks sufficient historical data for backtesting.

**Key Benefits**:
- ✅ **Zero Data Gaps**: Automatic fallback to pykrx, yfinance, DART, KIS API
- ✅ **Transparent**: No code changes required in backtesting strategies
- ✅ **Performance**: Intelligent caching and batch optimization
- ✅ **Quality**: Multi-source validation and data quality checks

**Implementation Effort**: 2-3 hours (extends existing PostgresDataProvider)

---

## 🎯 Design Goals

### Primary Goals
1. **Transparency**: Backfill happens automatically without strategy code changes
2. **Performance**: Minimize API calls through intelligent caching
3. **Reliability**: Graceful degradation with multiple fallback sources
4. **Quality**: Data validation and quality assurance

### Non-Goals
- ❌ Real-time streaming data (backtesting only)
- ❌ Replacing primary data collection pipeline
- ❌ Complex data transformation (use parsers)

---

## 🏗️ System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Backtesting Strategy                        │
│         (No changes required - transparent)                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ get_ohlcv(ticker, start, end)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              PostgresDataProvider                            │
│   (Enhanced with Auto-Backfill Logic)                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Check Cache      → Cache Hit? → Return Data             │
│  2. Query PostgreSQL → Sufficient? → Return Data            │
│  3. Auto-Backfill    → API Fetch → Validate → Save → Return │
│                                                              │
└──────────────┬──────────────────────────────────────────────┘
               │
               │ (Auto-Backfill Triggered)
               │
        ┌──────┴──────────────────────────────┐
        │   BackfillOrchestrator              │
        │   - API priority management         │
        │   - Rate limiting coordination      │
        │   - Data validation                 │
        └──────┬──────────────────────────────┘
               │
      ┌────────┼────────┬────────────┐
      │        │        │            │
      ▼        ▼        ▼            ▼
  ┌─────┐ ┌──────┐ ┌───────┐  ┌──────────┐
  │ KIS │ │pykrx │ │yfinance│ │  DART    │
  │ API │ │ API  │ │  API   │ │   API    │
  └─────┘ └──────┘ └───────┘  └──────────┘
      │       │        │            │
      └───────┴────────┴────────────┘
                   │
                   ▼
          ┌─────────────────┐
          │   PostgreSQL    │
          │   (Persist)     │
          └─────────────────┘
```

### Data Flow

**Normal Flow (Cache/DB Hit)**:
```
Strategy → get_ohlcv() → Cache → Return (< 1ms)
                        ↓
                   PostgreSQL → Return (< 100ms)
```

**Backfill Flow (Missing Data)**:
```
Strategy → get_ohlcv() → Cache Miss
                        ↓
                   PostgreSQL (Insufficient Data)
                        ↓
                   BackfillOrchestrator
                        ↓
                   API Priority Selection
                        ↓
                   Fetch from API (1-5s)
                        ↓
                   Validate Data
                        ↓
                   Save to PostgreSQL
                        ↓
                   Update Cache
                        ↓
                   Return to Strategy
```

---

## 🔧 Component Design

### 1. PostgresDataProvider (Enhanced)

**Current Implementation**: `modules/backtesting/data_providers/postgres_data_provider.py`

**Enhancements**:

```python
class PostgresDataProvider(BaseDataProvider):
    """Enhanced with auto-backfill capability"""

    def __init__(
        self,
        db_manager: PostgresDatabaseManager,
        cache_enabled: bool = True,
        backfill_enabled: bool = True,  # NEW
        backfill_threshold: float = 0.8  # NEW: 80% data coverage required
    ):
        super().__init__(cache_enabled=cache_enabled)
        self.db = db_manager

        # NEW: Backfill components
        self.backfill_enabled = backfill_enabled
        self.backfill_threshold = backfill_threshold

        if backfill_enabled:
            self.backfill_orchestrator = BackfillOrchestrator(db_manager)
            logger.info("Auto-backfill enabled (threshold: {:.0%})".format(backfill_threshold))

    def get_ohlcv(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date,
        timeframe: str = '1d'
    ) -> pd.DataFrame:
        """
        Get OHLCV data with automatic backfill for missing data.

        Workflow:
        1. Check cache
        2. Query PostgreSQL
        3. Evaluate data completeness (>= threshold?)
        4. Auto-backfill if insufficient
        5. Return complete dataset
        """
        # Step 1: Check cache
        cache_key = self._generate_cache_key(ticker, region, start_date, end_date, timeframe)
        if self.cache_enabled and cache_key in self.cache:
            logger.debug(f"Cache hit: {ticker}")
            return self.cache[cache_key].copy()

        # Step 2: Query PostgreSQL
        df = self._query_postgres(ticker, region, start_date, end_date, timeframe)

        # Step 3: Evaluate completeness
        if self.backfill_enabled:
            expected_days = self._calculate_expected_trading_days(start_date, end_date, region)
            actual_days = len(df)
            coverage = actual_days / expected_days if expected_days > 0 else 0

            # Step 4: Auto-backfill if insufficient
            if coverage < self.backfill_threshold:
                logger.info(
                    f"Auto-backfill triggered: {ticker} ({region}) "
                    f"coverage={coverage:.1%} < {self.backfill_threshold:.1%}"
                )

                backfilled_df = self.backfill_orchestrator.backfill_ohlcv(
                    ticker=ticker,
                    region=region,
                    start_date=start_date,
                    end_date=end_date,
                    timeframe=timeframe,
                    existing_data=df
                )

                if backfilled_df is not None and len(backfilled_df) > len(df):
                    logger.info(
                        f"Backfill success: {ticker} "
                        f"{len(df)} → {len(backfilled_df)} records"
                    )
                    df = backfilled_df

        # Step 5: Cache and return
        if self.cache_enabled and not df.empty:
            self.cache[cache_key] = df.copy()

        return df

    def get_fundamentals(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date
    ) -> pd.DataFrame:
        """Get fundamental data with auto-backfill (similar workflow)"""
        # Similar implementation as get_ohlcv
        # Uses DART API for KR fundamentals
        pass
```

### 2. BackfillOrchestrator (NEW)

**Purpose**: Coordinate multi-source data fetching with priority-based fallback

**Location**: `modules/backtesting/data_providers/backfill_orchestrator.py`

**Key Features**:
- API priority management by region
- Rate limiting coordination
- Data validation and quality checks
- Efficient batch operations
- Error handling and retry logic

```python
class BackfillOrchestrator:
    """
    Coordinate data backfilling from multiple API sources.

    API Priority by Region:
    - KR: KIS API → pykrx → yfinance
    - US: yfinance → KIS API
    - CN/HK/JP: yfinance → KIS API

    Fundamental Data:
    - KR: DART → KIS API
    - Global: yfinance
    """

    def __init__(self, db_manager: PostgresDatabaseManager):
        self.db = db_manager

        # Initialize API clients
        self.apis = {
            'kis': None,  # Lazy initialization (requires auth)
            'pykrx': PyKRXAPI(),
            'yfinance': YFinanceAPI(rate_limit_per_second=1.0),
            'dart': None  # Lazy initialization (requires API key)
        }

        # API priority mapping
        self.ohlcv_priority = {
            'KR': ['kis', 'pykrx', 'yfinance'],
            'US': ['yfinance', 'kis'],
            'CN': ['yfinance', 'kis'],
            'HK': ['yfinance', 'kis'],
            'JP': ['yfinance', 'kis'],
            'VN': ['kis']
        }

        self.fundamental_priority = {
            'KR': ['dart', 'kis'],
            'US': ['yfinance'],
            'default': ['yfinance']
        }

        # Validation thresholds
        self.validation_config = {
            'min_records_per_year': 200,  # ~250 trading days
            'max_price_change_pct': 50.0,  # 50% max daily change
            'allow_zero_volume': False,
            'require_ohlc_consistency': True  # O/C within H/L
        }

    def backfill_ohlcv(
        self,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date,
        timeframe: str = '1d',
        existing_data: pd.DataFrame = None
    ) -> Optional[pd.DataFrame]:
        """
        Backfill OHLCV data from external APIs.

        Strategy:
        1. Identify missing date ranges
        2. Try API sources by priority
        3. Validate fetched data
        4. Merge with existing data
        5. Save to PostgreSQL
        6. Return complete dataset

        Args:
            ticker: Stock ticker symbol
            region: Market region code
            start_date: Start date for backfill
            end_date: End date for backfill
            timeframe: Data timeframe
            existing_data: Existing data from PostgreSQL (optional)

        Returns:
            Complete DataFrame or None if all sources fail
        """
        # Step 1: Identify missing ranges
        missing_ranges = self._identify_missing_ranges(
            existing_data, start_date, end_date, region
        )

        if not missing_ranges:
            logger.debug(f"No missing data for {ticker}")
            return existing_data

        logger.info(
            f"Missing data ranges for {ticker}: "
            f"{len(missing_ranges)} gaps (total {sum(r[1]-r[0] for r in missing_ranges).days} days)"
        )

        # Step 2: Try API sources by priority
        priority_list = self.ohlcv_priority.get(region, ['yfinance'])

        fetched_data = []
        for api_name in priority_list:
            try:
                logger.info(f"Attempting backfill from {api_name}...")

                api_client = self._get_api_client(api_name)
                if api_client is None:
                    logger.warning(f"{api_name} not available, skipping")
                    continue

                # Fetch from API
                df = self._fetch_from_api(
                    api_client,
                    api_name,
                    ticker,
                    region,
                    start_date,
                    end_date
                )

                if df is None or df.empty:
                    logger.warning(f"No data from {api_name}")
                    continue

                # Step 3: Validate
                is_valid, validation_errors = self._validate_ohlcv_data(df, ticker)
                if not is_valid:
                    logger.error(
                        f"Validation failed for {ticker} from {api_name}: "
                        f"{validation_errors}"
                    )
                    continue

                # Success!
                logger.info(f"✅ Fetched {len(df)} records from {api_name}")
                fetched_data.append(df)
                break  # Stop trying other sources

            except Exception as e:
                logger.error(f"Failed to fetch from {api_name}: {e}")
                continue

        if not fetched_data:
            logger.error(f"All API sources failed for {ticker}")
            return existing_data

        # Step 4: Merge with existing data
        complete_df = self._merge_data(existing_data, fetched_data[0])

        # Step 5: Save to PostgreSQL
        try:
            self._save_to_postgres(complete_df, ticker, region, timeframe)
            logger.info(f"✅ Saved {len(complete_df)} records to PostgreSQL")
        except Exception as e:
            logger.error(f"Failed to save backfilled data: {e}")
            # Still return the merged data even if save fails

        return complete_df

    def _identify_missing_ranges(
        self,
        existing_data: pd.DataFrame,
        start_date: date,
        end_date: date,
        region: str
    ) -> List[Tuple[date, date]]:
        """
        Identify missing date ranges in existing data.

        Returns:
            List of (start_date, end_date) tuples for missing ranges
        """
        if existing_data is None or existing_data.empty:
            return [(start_date, end_date)]

        # Convert to date range
        existing_dates = pd.to_datetime(existing_data['date']).dt.date.unique()

        # Generate expected trading days (simplified - exclude weekends)
        all_dates = pd.date_range(start_date, end_date, freq='B')  # Business days
        expected_dates = [d.date() for d in all_dates]

        # Find missing dates
        missing_dates = set(expected_dates) - set(existing_dates)

        if not missing_dates:
            return []

        # Group consecutive missing dates into ranges
        sorted_missing = sorted(missing_dates)
        ranges = []
        range_start = sorted_missing[0]
        range_end = sorted_missing[0]

        for i in range(1, len(sorted_missing)):
            if (sorted_missing[i] - sorted_missing[i-1]).days <= 5:  # Allow small gaps
                range_end = sorted_missing[i]
            else:
                ranges.append((range_start, range_end))
                range_start = sorted_missing[i]
                range_end = sorted_missing[i]

        ranges.append((range_start, range_end))
        return ranges

    def _fetch_from_api(
        self,
        api_client,
        api_name: str,
        ticker: str,
        region: str,
        start_date: date,
        end_date: date
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data from specific API"""
        if api_name == 'pykrx':
            # pykrx API
            days = (end_date - start_date).days
            ohlcv_list = api_client.get_ohlcv(ticker, days=days)
            if not ohlcv_list:
                return None
            df = pd.DataFrame(ohlcv_list)

        elif api_name == 'yfinance':
            # yfinance API
            # Convert ticker to yfinance format (e.g., '005930' → '005930.KS')
            yf_ticker = self._convert_to_yfinance_ticker(ticker, region)
            ticker_info = api_client.get_ticker_info(yf_ticker)
            if ticker_info is None:
                return None

            # Fetch historical data
            import yfinance as yf
            stock = yf.Ticker(yf_ticker)
            df = stock.history(start=start_date, end=end_date)

            if df.empty:
                return None

            # Standardize column names
            df = df.reset_index()
            df.columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'dividends', 'stock_splits']
            df = df[['date', 'open', 'high', 'low', 'close', 'volume']]

        elif api_name == 'kis':
            # KIS API (requires implementation)
            logger.warning("KIS API backfill not yet implemented")
            return None

        else:
            logger.error(f"Unknown API: {api_name}")
            return None

        return df

    def _validate_ohlcv_data(
        self,
        df: pd.DataFrame,
        ticker: str
    ) -> Tuple[bool, List[str]]:
        """
        Validate OHLCV data quality.

        Checks:
        1. Required columns present
        2. No NULL values in critical columns
        3. OHLC consistency (open/close within high/low)
        4. Price changes within reasonable limits
        5. Volume > 0 (optional)

        Returns:
            (is_valid: bool, errors: List[str])
        """
        errors = []

        # Check 1: Required columns
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        missing_cols = set(required_cols) - set(df.columns)
        if missing_cols:
            errors.append(f"Missing columns: {missing_cols}")
            return False, errors

        # Check 2: NULL values
        null_counts = df[required_cols].isnull().sum()
        if null_counts.any():
            errors.append(f"NULL values found: {null_counts[null_counts > 0].to_dict()}")

        # Check 3: OHLC consistency
        if self.validation_config['require_ohlc_consistency']:
            ohlc_invalid = (
                (df['open'] > df['high']) |
                (df['open'] < df['low']) |
                (df['close'] > df['high']) |
                (df['close'] < df['low'])
            )
            if ohlc_invalid.any():
                errors.append(
                    f"OHLC inconsistency detected in {ohlc_invalid.sum()} rows "
                    f"(open/close outside high/low range)"
                )

        # Check 4: Price changes
        df_sorted = df.sort_values('date')
        price_changes = df_sorted['close'].pct_change().abs() * 100
        extreme_changes = price_changes > self.validation_config['max_price_change_pct']
        if extreme_changes.any():
            extreme_count = extreme_changes.sum()
            max_change = price_changes.max()
            errors.append(
                f"Extreme price changes detected: {extreme_count} days with >{self.validation_config['max_price_change_pct']}% change "
                f"(max: {max_change:.1f}%)"
            )

        # Check 5: Zero volume
        if not self.validation_config['allow_zero_volume']:
            zero_volume = (df['volume'] <= 0).sum()
            if zero_volume > 0:
                errors.append(f"Zero/negative volume in {zero_volume} rows")

        # Check 6: Minimum record count
        years = (df['date'].max() - df['date'].min()).days / 365.25
        min_expected = int(years * self.validation_config['min_records_per_year'])
        if len(df) < min_expected:
            errors.append(
                f"Insufficient data: {len(df)} records < {min_expected} expected "
                f"({years:.1f} years × {self.validation_config['min_records_per_year']} days/year)"
            )

        is_valid = len(errors) == 0
        return is_valid, errors

    def _merge_data(
        self,
        existing_df: pd.DataFrame,
        new_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Merge existing and newly fetched data.

        Strategy:
        - Existing data takes precedence (higher quality)
        - New data fills gaps only
        - Remove duplicates (keep existing)
        - Sort by date
        """
        if existing_df is None or existing_df.empty:
            return new_df

        if new_df is None or new_df.empty:
            return existing_df

        # Ensure date columns are datetime
        existing_df['date'] = pd.to_datetime(existing_df['date'])
        new_df['date'] = pd.to_datetime(new_df['date'])

        # Concatenate
        combined = pd.concat([existing_df, new_df], ignore_index=True)

        # Remove duplicates (keep first = existing data)
        combined = combined.drop_duplicates(subset=['date'], keep='first')

        # Sort by date
        combined = combined.sort_values('date').reset_index(drop=True)

        logger.info(
            f"Merged data: {len(existing_df)} existing + {len(new_df)} new → "
            f"{len(combined)} total ({len(combined) - len(existing_df)} added)"
        )

        return combined

    def _save_to_postgres(
        self,
        df: pd.DataFrame,
        ticker: str,
        region: str,
        timeframe: str
    ):
        """Save backfilled data to PostgreSQL"""
        # Convert to records format
        records = df.to_dict('records')

        # Add metadata
        for record in records:
            record['ticker'] = ticker
            record['region'] = region
            record['timeframe'] = timeframe
            record['data_source'] = 'auto_backfill'

        # Bulk insert using existing db_manager method
        # (Assumes db_manager has bulk_insert_ohlcv method)
        self.db.bulk_insert_ohlcv(records)

    def _get_api_client(self, api_name: str):
        """Get or initialize API client"""
        if api_name not in self.apis:
            return None

        if self.apis[api_name] is not None:
            return self.apis[api_name]

        # Lazy initialization
        if api_name == 'kis':
            # Requires KIS API credentials
            from modules.api_clients.base_kis_api import KISApiClient
            try:
                self.apis['kis'] = KISApiClient()
            except Exception as e:
                logger.warning(f"KIS API initialization failed: {e}")
                return None

        elif api_name == 'dart':
            # Requires DART API key
            try:
                self.apis['dart'] = DARTApiClient()
            except Exception as e:
                logger.warning(f"DART API initialization failed: {e}")
                return None

        return self.apis[api_name]

    def _convert_to_yfinance_ticker(self, ticker: str, region: str) -> str:
        """Convert internal ticker to yfinance format"""
        suffix_map = {
            'KR': '.KS',  # KOSPI
            'US': '',     # No suffix
            'HK': '.HK',
            'JP': '.T',
            'CN': '.SS',  # Shanghai
        }

        suffix = suffix_map.get(region, '')

        # Special handling for Korean tickers
        if region == 'KR':
            # KOSDAQ tickers might need .KQ suffix
            # This requires checking market (simplified here)
            return f"{ticker}{suffix}"

        return f"{ticker}{suffix}"
```

---

## 📊 Data Validation Framework

### Validation Levels

**Level 1: Structural Validation** (Mandatory)
```python
✅ Required columns present: [date, open, high, low, close, volume]
✅ No NULL values in critical columns
✅ Correct data types (date: datetime, prices: float, volume: int)
```

**Level 2: Business Logic Validation** (Mandatory)
```python
✅ OHLC consistency: open/close within [low, high]
✅ Reasonable price changes: < 50% daily change
✅ Volume validation: volume >= 0 (allow zero for illiquid stocks)
```

**Level 3: Statistical Validation** (Warning-level)
```python
⚠️ Outlier detection: Z-score > 3 for returns
⚠️ Minimum liquidity: avg daily volume > threshold
⚠️ Completeness: >= 200 trading days per year
```

### Quality Scoring

```python
quality_score = (
    structural_score * 0.4 +      # Must be 100%
    business_logic_score * 0.4 +  # Must be >= 95%
    statistical_score * 0.2       # Warning only
)

# Accept if quality_score >= 0.9
```

---

## ⚡ Performance Optimization

### Caching Strategy

**3-Tier Caching**:
```
L1 Cache (In-Memory)    → <1ms    → Dict[cache_key, DataFrame]
L2 Cache (PostgreSQL)   → <100ms  → Database query
L3 Cache (API Backfill) → 1-5s    → External API fetch
```

**Cache Invalidation**:
- Time-based: Invalidate after 24 hours for recent data
- Event-based: Invalidate on manual data updates
- LRU eviction: Keep last 1000 queries in memory

### Batch Optimization

**Batch Backfill Strategy**:
```python
# Don't fetch one ticker at a time
for ticker in tickers:
    data = provider.get_ohlcv(ticker, ...)  # ❌ Slow (N API calls)

# Instead, use batch fetch
tickers_needing_backfill = provider.identify_backfill_candidates(tickers, ...)
backfilled_data = provider.batch_backfill(tickers_needing_backfill)  # ✅ Fast (1 batch call)
```

### Rate Limiting

**Per-API Limits**:
```python
rate_limits = {
    'pykrx': 1.0,      # 1 request/second
    'yfinance': 1.0,   # 1 request/second (conservative)
    'dart': 0.027,     # 100 requests/hour
    'kis': 5.0         # 5 requests/second (authenticated)
}
```

---

## 🔒 Error Handling

### Graceful Degradation

**Priority Fallback**:
```
Try KIS API
  ├─ Success → Return data
  ├─ Fail → Try pykrx
  │    ├─ Success → Return data
  │    └─ Fail → Try yfinance
  │         ├─ Success → Return data
  │         └─ Fail → Log error, return empty DataFrame
```

### Error Categories

**Category 1: Recoverable Errors** (Retry with backoff)
- Network timeout
- Rate limit exceeded
- Temporary API outage

**Category 2: Data Quality Errors** (Skip source, try next)
- Validation failed
- Incomplete data
- Data format mismatch

**Category 3: Fatal Errors** (Fail fast)
- Invalid ticker
- Invalid date range
- No API sources available

---

## 📝 Implementation Roadmap

### Phase 1: Core Infrastructure (1 hour)
- [x] Design specification (this document)
- [ ] Implement BackfillOrchestrator skeleton
- [ ] Add backfill_enabled flag to PostgresDataProvider
- [ ] Implement data coverage calculation

### Phase 2: API Integration (1 hour)
- [ ] Integrate pykrx API (OHLCV)
- [ ] Integrate yfinance API (OHLCV)
- [ ] Add ticker format conversion logic
- [ ] Implement API priority system

### Phase 3: Validation & Quality (30 min)
- [ ] Implement OHLCV validation rules
- [ ] Add quality scoring system
- [ ] Create validation test suite

### Phase 4: Testing & Documentation (30 min)
- [ ] Unit tests for BackfillOrchestrator
- [ ] Integration tests with real APIs
- [ ] Performance benchmarks
- [ ] Update user documentation

**Total Estimated Time: 2-3 hours**

---

## 🧪 Testing Strategy

### Unit Tests

```python
# tests/backtesting/data_providers/test_backfill_orchestrator.py

def test_identify_missing_ranges():
    """Test missing date range identification"""
    existing = pd.DataFrame({'date': [date(2024,1,1), date(2024,1,3)]})
    ranges = orchestrator._identify_missing_ranges(
        existing, date(2024,1,1), date(2024,1,5), 'KR'
    )
    assert len(ranges) == 1
    assert ranges[0] == (date(2024,1,2), date(2024,1,2))

def test_validate_ohlcv_data():
    """Test data validation"""
    # Valid data
    valid_df = pd.DataFrame({
        'date': [date(2024,1,1)],
        'open': [100],
        'high': [110],
        'low': [95],
        'close': [105],
        'volume': [1000]
    })
    is_valid, errors = orchestrator._validate_ohlcv_data(valid_df, '005930')
    assert is_valid

    # Invalid data (open > high)
    invalid_df = valid_df.copy()
    invalid_df.loc[0, 'open'] = 120
    is_valid, errors = orchestrator._validate_ohlcv_data(invalid_df, '005930')
    assert not is_valid
    assert 'OHLC inconsistency' in errors[0]
```

### Integration Tests

```python
# tests/backtesting/data_providers/test_auto_backfill_integration.py

def test_auto_backfill_pykrx():
    """Test automatic backfill from pykrx"""
    provider = PostgresDataProvider(db_manager, backfill_enabled=True)

    # Request data for ticker with gaps
    df = provider.get_ohlcv('005930', 'KR', date(2024,1,1), date(2024,12,31))

    # Should auto-backfill missing data
    assert len(df) >= 200  # Minimum trading days
    assert not df.isnull().any().any()  # No NULLs

def test_backfill_threshold():
    """Test backfill threshold configuration"""
    # High threshold (90%) - triggers backfill
    provider_high = PostgresDataProvider(
        db_manager,
        backfill_enabled=True,
        backfill_threshold=0.9
    )

    # Low threshold (50%) - may not trigger
    provider_low = PostgresDataProvider(
        db_manager,
        backfill_enabled=True,
        backfill_threshold=0.5
    )
```

---

## 📚 Usage Examples

### Example 1: Basic Backtest (Transparent)

```python
from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider
from modules.db_manager_postgres import PostgresDatabaseManager

# Setup (auto-backfill enabled by default)
db_manager = PostgresDatabaseManager(host='localhost', database='quant_platform')
provider = PostgresDataProvider(
    db_manager,
    cache_enabled=True,
    backfill_enabled=True,      # Auto-backfill enabled
    backfill_threshold=0.8      # Require 80% data coverage
)

# Use normally - backfill happens automatically
df = provider.get_ohlcv('005930', 'KR', date(2020,1,1), date(2024,12,31))

# If DB has gaps, backfill will:
# 1. Detect missing data (< 80% coverage)
# 2. Fetch from pykrx (KR priority)
# 3. Validate data quality
# 4. Save to PostgreSQL
# 5. Return complete dataset

# Strategy code unchanged!
```

### Example 2: Disable Backfill (DB-only)

```python
# Disable auto-backfill for testing
provider = PostgresDataProvider(
    db_manager,
    backfill_enabled=False  # Only use PostgreSQL data
)

df = provider.get_ohlcv('005930', 'KR', date(2020,1,1), date(2024,12,31))
# Returns exactly what's in DB (may have gaps)
```

### Example 3: Custom Threshold

```python
# Require 95% coverage before backfill
provider = PostgresDataProvider(
    db_manager,
    backfill_threshold=0.95  # Stricter than default 0.8
)

df = provider.get_ohlcv('005930', 'KR', date(2020,1,1), date(2024,12,31))
# Triggers backfill only if < 95% data coverage
```

### Example 4: Batch Backtest

```python
# Efficient batch backfill
tickers = ['005930', '000660', '035420', '051910']

# Old way (inefficient)
for ticker in tickers:
    df = provider.get_ohlcv(ticker, 'KR', start, end)  # May trigger 4 separate backfills

# New way (optimized)
data = provider.get_ohlcv_batch(tickers, 'KR', start, end)
# Batches backfill requests intelligently
```

---

## 🎯 Success Criteria

### Functional Requirements
- ✅ Automatic detection of missing data (< threshold coverage)
- ✅ Multi-source fallback (KIS → pykrx → yfinance)
- ✅ Data validation before saving
- ✅ Transparent to strategy code (no API changes)

### Non-Functional Requirements
- ✅ Performance: Backfill <5s per ticker
- ✅ Reliability: 99% success rate for available tickers
- ✅ Quality: >= 95% data validation pass rate
- ✅ Caching: >= 80% cache hit rate

### Testing Requirements
- ✅ >= 90% code coverage for backfill modules
- ✅ Integration tests with all API sources
- ✅ Performance benchmarks documented

---

## 🔮 Future Enhancements

### Phase 2 (Optional)
- [ ] Real-time data streaming integration
- [ ] Fundamental data backfill (DART integration)
- [ ] Multi-threaded batch backfill
- [ ] Grafana dashboard for backfill monitoring

### Phase 3 (Advanced)
- [ ] Machine learning for data quality scoring
- [ ] Predictive backfill (pre-fetch likely queries)
- [ ] Cross-regional data consistency checks
- [ ] Distributed caching (Redis)

---

## 📖 References

- **Current Implementation**: `modules/backtesting/data_providers/postgres_data_provider.py`
- **API Clients**: `modules/api_clients/`
- **Database Schema**: `docs/QUANT_DATABASE_SCHEMA.md`
- **Backtesting Guide**: `docs/QUANT_DEVELOPMENT_WORKFLOWS.md`

---

**Last Updated**: 2025-10-29
**Next Review**: After Phase 1 implementation
