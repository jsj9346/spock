# Option A Implementation Design: FXTracker & StockClassifier

**Date**: 2025-11-05
**Status**: Design Phase
**Estimated Duration**: 7-10 hours (FXTracker: 4-6h, StockClassifier: 3-4h)

---

## Executive Summary

Option A completes the Database Refresh System Phase 1 Day 3-4 by implementing:
1. **FXTracker**: Exchange rate tracking and FX valuation signals
2. **StockClassifier**: Sector/industry classification and SPAC/preferred stock detection

Both modules follow established patterns from ETFUpdater (604 lines, 18 tests) and integrate seamlessly with DatabaseUpdateOrchestrator.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [FXTracker Design](#2-fxtracker-design)
3. [StockClassifier Design](#3-stockclassifier-design)
4. [Implementation Plan](#4-implementation-plan)
5. [Testing Strategy](#5-testing-strategy)
6. [Integration Points](#6-integration-points)

---

## 1. Architecture Overview

### 1.1 Design Principles

Following patterns established in **ETFUpdater** (completed Day 4):

✅ **Separation of Concerns**: Data fetching → Validation → Database update
✅ **Error Handling**: Try-except with graceful degradation and mock data fallback
✅ **Database Strategies**: UPSERT for incremental updates, DELETE+INSERT for snapshots
✅ **Testing**: Comprehensive unit tests with mocks for external dependencies
✅ **Logging**: Detailed progress tracking with emoji indicators

### 1.2 Module Comparison

| Aspect | ETFUpdater (Reference) | FXTracker (New) | StockClassifier (New) |
|--------|----------------------|-----------------|----------------------|
| **Lines of Code** | 604 | ~350 (est.) | ~300 (est.) |
| **External APIs** | pykrx, yfinance | Alpha Vantage, yfinance | pykrx, yfinance |
| **Mock Fallback** | ✅ Yes | ✅ Yes | ✅ Yes |
| **DB Strategy** | UPSERT + DELETE+INSERT | UPSERT only | UPDATE only |
| **Unit Tests** | 18 tests | ~12 tests (est.) | ~10 tests (est.) |
| **Complexity** | High (3 tables) | Medium (1 table) | Medium (1 table) |

### 1.3 Integration with Orchestrator

```python
# DatabaseUpdateOrchestrator - Already implemented (Day 1-2)
STEP_ORDER = [
    'tickers',
    'ticker_refresh',    # ✅ Complete
    'fx_tracking',       # 🔄 FXTracker (this design)
    'ohlcv',
    'fundamentals',
    'classification',    # 🔄 StockClassifier (this design)
    'dividend',
    'etf_data',          # ✅ Complete (ETFUpdater)
    'quarterly'
]
```

**Orchestrator Integration Methods** (already exist, need implementation):
```python
def _track_exchange_rates(self, regions: List[str]) -> Dict:
    """Execute FX tracking step"""
    # TODO: Implement (Day 3-4)

def _classify_stocks(self, regions: List[str]) -> Dict:
    """Execute stock classification step"""
    # TODO: Implement (Day 3-4)
```

---

## 2. FXTracker Design

### 2.1 Requirements Summary

**Functional Requirements**:
- ✅ Track 6 major currency pairs (USD/KRW, USD/JPY, USD/HKD, USD/CNY, USD/VND, USD/EUR)
- ✅ Daily incremental updates (fetch only latest rate if not exists)
- ✅ Historical backfill capability (7-day, 30-day, 1-year)
- ✅ Multiple data source fallback (Alpha Vantage → yfinance → manual)

**Non-Functional Requirements**:
- Performance: <30 seconds for all 6 currency pairs
- Accuracy: ±0.1% vs official central bank rates
- Reliability: 99% uptime with fallback sources

### 2.2 Data Source Strategy

| Priority | Source | API | Cost | Rate Limit | Coverage |
|----------|--------|-----|------|-----------|----------|
| **1st** | Alpha Vantage | FX_DAILY | Free tier | 5 calls/min | USD/* pairs |
| **2nd** | yfinance | Ticker.history() | Free | Unlimited | Major pairs (=X suffix) |
| **3rd** | Mock Data | Hardcoded | Free | N/A | Fallback only |

**Alpha Vantage API Example**:
```python
# URL: https://www.alphavantage.co/query
params = {
    'function': 'FX_DAILY',
    'from_symbol': 'USD',
    'to_symbol': 'KRW',
    'apikey': '<API_KEY>'
}
# Response: {"Time Series FX (Daily)": {"2024-11-05": {"4. close": "1380.50"}}}
```

**yfinance Fallback Example**:
```python
# For USD/KRW: ticker = "KRW=X"
# For USD/JPY: ticker = "JPY=X"
import yfinance as yf
fx_data = yf.Ticker("KRW=X").history(period="1d")
rate = fx_data['Close'].iloc[-1]  # Latest close
```

### 2.3 Database Schema

**Table**: `exchange_rate_history` (already exists)

```sql
CREATE TABLE exchange_rate_history (
    id SERIAL PRIMARY KEY,
    from_currency VARCHAR(3) NOT NULL,  -- 'USD'
    to_currency VARCHAR(3) NOT NULL,    -- 'KRW', 'JPY', etc.
    rate NUMERIC(18, 6) NOT NULL,       -- Exchange rate
    rate_date DATE NOT NULL,            -- Rate date
    source VARCHAR(50),                 -- 'alpha_vantage', 'yfinance', 'mock'
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (from_currency, to_currency, rate_date)
);

-- Indexes
CREATE INDEX idx_exchange_rate_history_date ON exchange_rate_history(rate_date DESC);
CREATE INDEX idx_exchange_rate_history_pair ON exchange_rate_history(from_currency, to_currency);
```

**UPSERT Strategy** (same as ETFUpdater):
```sql
INSERT INTO exchange_rate_history (
    from_currency, to_currency, rate, rate_date, source
) VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (from_currency, to_currency, rate_date)
DO UPDATE SET
    rate = EXCLUDED.rate,
    source = EXCLUDED.source,
    created_at = NOW();
```

### 2.4 Module Architecture

**File**: `modules/fx_tracking/fx_tracker.py` (~350 lines)

```python
"""
FX Tracker - Exchange Rate Tracking System

Handles:
- Daily FX rate updates for major currency pairs
- Multiple data source fallback (Alpha Vantage → yfinance → mock)
- Historical backfill for missing dates
- Database updates to exchange_rate_history table

Database Strategy:
- FX rates: UPSERT (INSERT ... ON CONFLICT DO UPDATE)

Author: Spock Quant Platform
Date: 2025-11-05
"""

import logging
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

logger = logging.getLogger(__name__)


class FXTracker:
    """
    Exchange rate tracker with multi-source fallback

    Features:
    - Fetch FX rates from Alpha Vantage, yfinance, or mock data
    - Incremental daily updates (only fetch if missing)
    - Historical backfill capability
    - Validation and anomaly detection

    Usage:
        tracker = FXTracker(db_manager=db)
        result = tracker.update_fx_rates(
            currency_pairs=['USD/KRW', 'USD/JPY'],
            backfill_days=7,
            dry_run=False
        )
    """

    # Supported currency pairs
    SUPPORTED_PAIRS = [
        'USD/KRW',  # US Dollar → Korean Won
        'USD/JPY',  # US Dollar → Japanese Yen
        'USD/HKD',  # US Dollar → Hong Kong Dollar
        'USD/CNY',  # US Dollar → Chinese Yuan
        'USD/VND',  # US Dollar → Vietnamese Dong
        'USD/EUR',  # US Dollar → Euro
    ]

    # Data source priority
    DATA_SOURCES = ['alpha_vantage', 'yfinance', 'mock']

    # Validation thresholds
    MAX_DAILY_CHANGE = 0.05  # 5% max daily change
    MIN_RATE = 0.0001        # Minimum valid rate

    def __init__(self, db_manager=None):
        """
        Initialize FX Tracker

        Args:
            db_manager: Database manager instance (PostgresDatabaseManager)
        """
        self.db = db_manager
        self.logger = logger
        self.alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY')

    def update_fx_rates(self, currency_pairs: List[str] = None,
                       backfill_days: int = 0,
                       dry_run: bool = False) -> Dict:
        """
        Update FX rates for specified currency pairs

        Args:
            currency_pairs: List of pairs (e.g., ['USD/KRW']). None = all pairs
            backfill_days: Number of days to backfill (0 = today only)
            dry_run: If True, fetch but don't update database

        Returns:
            Dict with keys:
                - success: bool
                - pairs_updated: int
                - rates_inserted: int
                - errors: List[str]
                - source_used: str (alpha_vantage, yfinance, mock)
        """
        # Implementation details...

    def _fetch_rate_alpha_vantage(self, from_curr: str, to_curr: str,
                                  target_date: date) -> Optional[Dict]:
        """Fetch rate from Alpha Vantage API"""
        # Implementation...

    def _fetch_rate_yfinance(self, from_curr: str, to_curr: str,
                            target_date: date) -> Optional[Dict]:
        """Fetch rate from yfinance (fallback)"""
        # Implementation...

    def _get_mock_rate(self, from_curr: str, to_curr: str,
                      target_date: date) -> Dict:
        """Get mock rate for development/testing"""
        # Mock rates based on real 2024-11-05 data
        mock_rates = {
            'USD/KRW': Decimal('1380.50'),
            'USD/JPY': Decimal('151.75'),
            'USD/HKD': Decimal('7.78'),
            'USD/CNY': Decimal('7.24'),
            'USD/VND': Decimal('25350.00'),
            'USD/EUR': Decimal('0.93'),
        }
        # Implementation...

    def _validate_rate(self, rate: Decimal, pair: str,
                      previous_rate: Optional[Decimal]) -> bool:
        """Validate rate for anomalies"""
        # Check min rate, daily change threshold
        # Implementation...

    def _insert_rate(self, from_curr: str, to_curr: str, rate: Decimal,
                    rate_date: date, source: str):
        """Insert or update rate in database (UPSERT)"""
        # Implementation...
```

### 2.5 Key Methods

#### Method 1: `update_fx_rates()` (Main Entry Point)
**Lines**: ~80 lines
**Logic**:
1. Determine currency pairs (default: all 6 pairs)
2. Determine date range (today only or backfill N days)
3. For each pair and each date:
   - Check if rate exists in DB
   - If missing, fetch from data sources (priority order)
   - Validate rate
   - Insert to DB (if not dry_run)
4. Return statistics

#### Method 2: `_fetch_rate_alpha_vantage()` (Primary Source)
**Lines**: ~40 lines
**API Call**:
```python
import requests

url = "https://www.alphavantage.co/query"
params = {
    'function': 'FX_DAILY',
    'from_symbol': from_curr,
    'to_symbol': to_curr,
    'apikey': self.alpha_vantage_key
}
response = requests.get(url, params=params, timeout=10)
data = response.json()

# Parse response
time_series = data.get('Time Series FX (Daily)', {})
rate_data = time_series.get(str(target_date), None)
if rate_data:
    rate = Decimal(rate_data['4. close'])
    return {'rate': rate, 'source': 'alpha_vantage'}
```

#### Method 3: `_fetch_rate_yfinance()` (Fallback)
**Lines**: ~30 lines
**API Call**:
```python
import yfinance as yf

# Convert USD/KRW to KRW=X format
ticker_symbol = f"{to_curr}=X"
ticker = yf.Ticker(ticker_symbol)

# Fetch historical data
hist = ticker.history(start=target_date, end=target_date + timedelta(days=1))
if not hist.empty:
    rate = Decimal(str(hist['Close'].iloc[0]))
    return {'rate': rate, 'source': 'yfinance'}
```

#### Method 4: `_get_mock_rate()` (Final Fallback)
**Lines**: ~25 lines
**Logic**: Return hardcoded rates based on real 2024-11-05 data

### 2.6 Error Handling Strategy

**Pattern** (same as ETFUpdater):
```python
def update_fx_rates(self, currency_pairs: List[str] = None,
                   backfill_days: int = 0,
                   dry_run: bool = False) -> Dict:
    """Update FX rates with error handling"""

    result = {
        'success': True,
        'pairs_updated': 0,
        'rates_inserted': 0,
        'errors': []
    }

    try:
        # Main logic
        for pair in currency_pairs:
            try:
                # Fetch and insert rate
                pass
            except Exception as e:
                result['errors'].append(f"{pair}: {str(e)}")
                logger.warning(f"⚠️  Failed to update {pair}: {e}")
                # Continue with next pair (don't fail entire update)

    except Exception as e:
        result['success'] = False
        result['errors'].append(f"Fatal error: {str(e)}")
        logger.error(f"❌ FX update failed: {e}")

    return result
```

### 2.7 Testing Strategy

**File**: `tests/fx_tracking/test_fx_tracker.py` (~250 lines)

**Test Cases** (12 tests):

1. **Initialization Tests** (2 tests)
   - `test_init_with_db_manager`: Verify correct initialization
   - `test_init_loads_alpha_vantage_key`: Check env var loading

2. **Data Fetching Tests** (3 tests)
   - `test_fetch_rate_alpha_vantage_success`: Mock API response
   - `test_fetch_rate_yfinance_fallback`: Mock yfinance data
   - `test_get_mock_rate_fallback`: Verify mock data structure

3. **Validation Tests** (2 tests)
   - `test_validate_rate_within_threshold`: Normal rate change
   - `test_validate_rate_exceeds_threshold`: Anomaly detection

4. **Database Update Tests** (2 tests)
   - `test_insert_rate_new_record`: UPSERT creates new record
   - `test_insert_rate_update_existing`: UPSERT updates existing

5. **Integration Tests** (3 tests)
   - `test_update_fx_rates_single_pair`: Update USD/KRW only
   - `test_update_fx_rates_all_pairs`: Update all 6 pairs
   - `test_update_fx_rates_backfill_7_days`: Historical backfill

**Mock Strategy**:
```python
@patch('modules.fx_tracking.fx_tracker.requests.get')
def test_fetch_rate_alpha_vantage_success(self, mock_get):
    """Test Alpha Vantage API fetching"""

    # Mock API response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'Time Series FX (Daily)': {
            '2024-11-05': {'4. close': '1380.50'}
        }
    }
    mock_get.return_value = mock_response

    # Test
    tracker = FXTracker(db_manager=None)
    result = tracker._fetch_rate_alpha_vantage('USD', 'KRW', date(2024, 11, 5))

    # Assertions
    self.assertIsNotNone(result)
    self.assertEqual(result['rate'], Decimal('1380.50'))
    self.assertEqual(result['source'], 'alpha_vantage')
```

---

## 3. StockClassifier Design

### 3.1 Requirements Summary

**Functional Requirements**:
- ✅ Backfill sector, sector_code, industry, industry_code for all stocks
- ✅ Detect SPAC stocks automatically (name patterns, SEC filings)
- ✅ Detect preferred stocks (ticker suffixes, Korean keywords)
- ✅ Multi-region classification systems (GICS for US/global, WICS for KR)

**Non-Functional Requirements**:
- Coverage: 95%+ classification rate
- Performance: <5 minutes for 1,000 stocks
- Accuracy: Manual verification for ambiguous cases

### 3.2 Data Source Strategy

| Region | Sector/Industry Source | SPAC Detection | Preferred Stock Detection |
|--------|----------------------|----------------|--------------------------|
| **KR** | pykrx (WICS sectors) | Name pattern: "스팩" | Name pattern: "우선주", "우선" |
| **US** | yfinance (GICS) | Name pattern: "Acquisition Corp" | Ticker suffix: "-P", "Pfd" |
| **Others** | yfinance (GICS) | Name pattern | Ticker suffix |

**pykrx API Example** (KR):
```python
from pykrx import stock

# Get sector/industry for ticker
sector = stock.get_market_sector('005930')  # Samsung Electronics
# Returns: "전기전자" (Electronics)

# Or get all tickers with sectors
sector_dict = stock.get_market_sector_list(market="ALL")
# Returns: {'005930': '전기전자', '000660': '전기전자', ...}
```

**yfinance API Example** (US/Others):
```python
import yfinance as yf

ticker = yf.Ticker("AAPL")
info = ticker.info

sector = info.get('sector')          # 'Technology'
industry = info.get('industry')      # 'Consumer Electronics'
sector_code = info.get('sectorKey')  # 'technology'
```

### 3.3 Database Schema

**Table**: `stock_details` (already exists)

```sql
-- Existing schema (no changes needed)
CREATE TABLE stock_details (
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(3) NOT NULL,

    -- Classification fields (to be filled)
    sector VARCHAR(100),              -- NULL → fill
    sector_code VARCHAR(50),          -- NULL → fill
    industry VARCHAR(100),            -- NULL → fill
    industry_code VARCHAR(50),        -- NULL → fill

    -- Detection fields (to be filled)
    is_spac BOOLEAN DEFAULT FALSE,    -- FALSE → detect
    is_preferred BOOLEAN DEFAULT FALSE, -- FALSE → detect

    -- Skip this field (keep NULL)
    par_value NUMERIC(10, 2),         -- Skip

    -- Other fields
    market_cap BIGINT,
    shares_outstanding BIGINT,
    last_updated TIMESTAMP DEFAULT NOW(),

    PRIMARY KEY (ticker, region),
    FOREIGN KEY (ticker, region) REFERENCES tickers(ticker, region)
);
```

**UPDATE Strategy** (not UPSERT - only update NULL fields):
```sql
UPDATE stock_details
SET
    sector = %s,
    sector_code = %s,
    industry = %s,
    industry_code = %s,
    is_spac = %s,
    is_preferred = %s,
    last_updated = NOW()
WHERE ticker = %s AND region = %s
  AND (sector IS NULL OR industry IS NULL);  -- Only update if NULL
```

### 3.4 Module Architecture

**File**: `modules/classification/stock_classifier.py` (~300 lines)

```python
"""
Stock Classifier - Sector/Industry Classification and Special Stock Detection

Handles:
- Sector and industry classification (GICS, WICS systems)
- SPAC detection (name patterns, SEC data)
- Preferred stock detection (ticker suffixes, Korean keywords)
- Database updates to stock_details table

Database Strategy:
- Stock details: UPDATE (only update NULL fields, no UPSERT)

Author: Spock Quant Platform
Date: 2025-11-05
"""

import logging
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class StockClassifier:
    """
    Stock classification and special stock detection

    Features:
    - Fetch sector/industry from pykrx (KR) or yfinance (others)
    - Detect SPAC stocks by name patterns
    - Detect preferred stocks by ticker/name patterns
    - Update stock_details table (only NULL fields)

    Usage:
        classifier = StockClassifier(db_manager=db)
        result = classifier.classify_stocks(
            region='KR',
            batch_size=100,
            dry_run=False
        )
    """

    # SPAC detection keywords (case-insensitive)
    SPAC_KEYWORDS = {
        'KR': ['스팩', 'SPAC'],
        'US': ['Acquisition Corp', 'Acquisition Co', 'Acquisition Company', 'SPAC'],
    }

    # Preferred stock patterns
    PREFERRED_PATTERNS = {
        'KR': {
            'name_patterns': ['우선주', '우선'],  # Korean keywords
            'ticker_suffixes': []  # No special suffix for KR
        },
        'US': {
            'name_patterns': ['Preferred', 'Pfd'],
            'ticker_suffixes': ['-P', 'P', '.P']  # US preferred suffixes
        }
    }

    def __init__(self, db_manager=None):
        """
        Initialize Stock Classifier

        Args:
            db_manager: Database manager instance (PostgresDatabaseManager)
        """
        self.db = db_manager
        self.logger = logger

    def classify_stocks(self, region: str = None,
                       batch_size: int = 100,
                       dry_run: bool = False) -> Dict:
        """
        Classify stocks with missing sector/industry data

        Args:
            region: Region code (e.g., 'KR', 'US'). None = all regions
            batch_size: Number of stocks to process per batch
            dry_run: If True, fetch but don't update database

        Returns:
            Dict with keys:
                - success: bool
                - stocks_classified: int
                - spac_detected: int
                - preferred_detected: int
                - errors: List[str]
        """
        # Implementation details...

    def _find_unclassified_stocks(self, region: str = None) -> List[Dict]:
        """Find stocks with NULL sector or industry"""
        query = """
            SELECT s.ticker, s.region, t.name
            FROM stock_details s
            JOIN tickers t ON s.ticker = t.ticker AND s.region = t.region
            WHERE (s.sector IS NULL OR s.industry IS NULL)
              AND t.is_active = TRUE
        """
        if region:
            query += f" AND s.region = '{region}'"

        # Return list of dicts: [{'ticker': '005930', 'region': 'KR', 'name': '삼성전자'}, ...]

    def _fetch_classification_kr(self, ticker: str) -> Optional[Dict]:
        """Fetch sector/industry from pykrx (Korean market)"""
        try:
            from pykrx import stock

            # Get sector for ticker
            sector = stock.get_market_sector(ticker)

            if sector:
                return {
                    'sector': sector,
                    'sector_code': self._map_kr_sector_code(sector),
                    'industry': sector,  # pykrx doesn't separate industry
                    'industry_code': None
                }
        except Exception as e:
            self.logger.warning(f"⚠️  Failed to fetch KR classification for {ticker}: {e}")
            return None

    def _fetch_classification_yfinance(self, ticker: str, region: str) -> Optional[Dict]:
        """Fetch sector/industry from yfinance (US and other markets)"""
        try:
            import yfinance as yf

            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info

            return {
                'sector': info.get('sector'),
                'sector_code': info.get('sectorKey'),
                'industry': info.get('industry'),
                'industry_code': info.get('industryKey')
            }
        except Exception as e:
            self.logger.warning(f"⚠️  Failed to fetch yfinance classification for {ticker}: {e}")
            return None

    def _detect_spac(self, ticker: str, name: str, region: str) -> bool:
        """Detect if stock is a SPAC"""
        keywords = self.SPAC_KEYWORDS.get(region, self.SPAC_KEYWORDS['US'])

        # Check name for SPAC keywords
        name_upper = name.upper()
        for keyword in keywords:
            if keyword.upper() in name_upper:
                return True

        return False

    def _detect_preferred(self, ticker: str, name: str, region: str) -> bool:
        """Detect if stock is preferred stock"""
        patterns = self.PREFERRED_PATTERNS.get(region, self.PREFERRED_PATTERNS['US'])

        # Check ticker suffixes
        for suffix in patterns['ticker_suffixes']:
            if ticker.endswith(suffix):
                return True

        # Check name patterns
        for pattern in patterns['name_patterns']:
            if pattern in name:
                return True

        return False

    def _update_stock_details(self, ticker: str, region: str,
                             classification: Dict, is_spac: bool,
                             is_preferred: bool):
        """Update stock_details table (only NULL fields)"""
        query = """
            UPDATE stock_details
            SET
                sector = COALESCE(sector, %s),
                sector_code = COALESCE(sector_code, %s),
                industry = COALESCE(industry, %s),
                industry_code = COALESCE(industry_code, %s),
                is_spac = %s,
                is_preferred = %s,
                last_updated = NOW()
            WHERE ticker = %s AND region = %s
        """

        values = (
            classification.get('sector'),
            classification.get('sector_code'),
            classification.get('industry'),
            classification.get('industry_code'),
            is_spac,
            is_preferred,
            ticker,
            region
        )

        # Execute update
        # Implementation...

    def _map_kr_sector_code(self, sector: str) -> Optional[str]:
        """Map Korean sector name to code (WICS system)"""
        # Mapping dictionary: {'전기전자': 'IT', '자동차': 'AUTO', ...}
        kr_sector_map = {
            '전기전자': 'IT',
            '자동차': 'AUTO',
            '금융': 'FIN',
            '화학': 'CHEM',
            '건설': 'CONST',
            # ... more mappings
        }
        return kr_sector_map.get(sector)
```

### 3.5 Key Methods

#### Method 1: `classify_stocks()` (Main Entry Point)
**Lines**: ~60 lines
**Logic**:
1. Find stocks with NULL sector/industry
2. For each stock in batches:
   - Fetch classification (region-specific source)
   - Detect SPAC (name pattern)
   - Detect preferred (ticker/name pattern)
   - Update database (if not dry_run)
3. Return statistics

#### Method 2: `_fetch_classification_kr()` (KR Market)
**Lines**: ~25 lines
**pykrx API**:
```python
from pykrx import stock

# Option 1: Single ticker
sector = stock.get_market_sector('005930')

# Option 2: All tickers (more efficient for batch)
sector_dict = stock.get_market_sector_list(market="ALL")
# Returns: {'005930': '전기전자', '000660': '전기전자', ...}
```

#### Method 3: `_fetch_classification_yfinance()` (US/Others)
**Lines**: ~20 lines
**yfinance API**: See example above

#### Method 4: `_detect_spac()` & `_detect_preferred()`
**Lines**: ~15 lines each
**Logic**: Simple pattern matching on ticker and name

### 3.6 Testing Strategy

**File**: `tests/classification/test_stock_classifier.py` (~200 lines)

**Test Cases** (10 tests):

1. **Initialization Tests** (1 test)
   - `test_init_with_db_manager`: Verify correct initialization

2. **Classification Fetching Tests** (3 tests)
   - `test_fetch_classification_kr_success`: Mock pykrx response
   - `test_fetch_classification_yfinance_success`: Mock yfinance data
   - `test_fetch_classification_failure_fallback`: Handle API failures

3. **SPAC Detection Tests** (2 tests)
   - `test_detect_spac_kr`: Korean SPAC keyword detection
   - `test_detect_spac_us`: US Acquisition Corp detection

4. **Preferred Stock Detection Tests** (2 tests)
   - `test_detect_preferred_kr`: Korean "우선주" detection
   - `test_detect_preferred_us`: US "-P" suffix detection

5. **Integration Tests** (2 tests)
   - `test_classify_stocks_kr_batch`: Classify 10 KR stocks
   - `test_classify_stocks_us_batch`: Classify 10 US stocks

**Mock Strategy**:
```python
@patch('modules.classification.stock_classifier.stock.get_market_sector')
def test_fetch_classification_kr_success(self, mock_get_sector):
    """Test pykrx sector fetching"""

    # Mock pykrx response
    mock_get_sector.return_value = '전기전자'

    # Test
    classifier = StockClassifier(db_manager=None)
    result = classifier._fetch_classification_kr('005930')

    # Assertions
    self.assertIsNotNone(result)
    self.assertEqual(result['sector'], '전기전자')
    self.assertEqual(result['sector_code'], 'IT')
```

---

## 4. Implementation Plan

### 4.1 Task Breakdown

#### Phase 1: FXTracker Implementation (4-6 hours)

| Task | Duration | Priority |
|------|----------|----------|
| **1.1** Create module structure (`fx_tracker.py`, `__init__.py`) | 15 min | 🔴 High |
| **1.2** Implement `__init__()` and class setup | 30 min | 🔴 High |
| **1.3** Implement `_fetch_rate_alpha_vantage()` | 1 hour | 🔴 High |
| **1.4** Implement `_fetch_rate_yfinance()` | 45 min | 🟡 Medium |
| **1.5** Implement `_get_mock_rate()` | 30 min | 🟡 Medium |
| **1.6** Implement `_validate_rate()` | 30 min | 🟡 Medium |
| **1.7** Implement `_insert_rate()` (UPSERT) | 45 min | 🔴 High |
| **1.8** Implement `update_fx_rates()` (main logic) | 1.5 hours | 🔴 High |
| **1.9** Write unit tests (12 tests) | 1.5 hours | 🔴 High |
| **1.10** Manual testing with real APIs | 30 min | 🟡 Medium |

**Total Phase 1**: 4-6 hours

#### Phase 2: StockClassifier Implementation (3-4 hours)

| Task | Duration | Priority |
|------|----------|----------|
| **2.1** Create module structure (`stock_classifier.py`, `__init__.py`) | 15 min | 🔴 High |
| **2.2** Implement `__init__()` and pattern dictionaries | 30 min | 🔴 High |
| **2.3** Implement `_find_unclassified_stocks()` | 30 min | 🔴 High |
| **2.4** Implement `_fetch_classification_kr()` | 45 min | 🔴 High |
| **2.5** Implement `_fetch_classification_yfinance()` | 45 min | 🔴 High |
| **2.6** Implement `_detect_spac()` | 20 min | 🟡 Medium |
| **2.7** Implement `_detect_preferred()` | 20 min | 🟡 Medium |
| **2.8** Implement `_update_stock_details()` (UPDATE) | 30 min | 🔴 High |
| **2.9** Implement `classify_stocks()` (main logic) | 1 hour | 🔴 High |
| **2.10** Write unit tests (10 tests) | 1.5 hours | 🔴 High |

**Total Phase 2**: 3-4 hours

#### Phase 3: Orchestrator Integration (1-2 hours)

| Task | Duration | Priority |
|------|----------|----------|
| **3.1** Implement `_track_exchange_rates()` in orchestrator | 30 min | 🔴 High |
| **3.2** Implement `_classify_stocks()` in orchestrator | 30 min | 🔴 High |
| **3.3** Update orchestrator tests (unskip 4 tests) | 30 min | 🔴 High |
| **3.4** Run full pipeline test (9 steps) | 30 min | 🟡 Medium |

**Total Phase 3**: 1-2 hours

### 4.2 Dependencies

**External Libraries** (already in `requirements_quant.txt`):
- ✅ `pykrx` - Korean market data
- ✅ `yfinance` - Global market data
- ⚠️ `requests` - Alpha Vantage API (need to add)
- ✅ `python-dotenv` - Environment variables

**New Requirements**:
```txt
# Add to requirements_quant.txt
requests==2.31.0  # HTTP library for Alpha Vantage API
```

**Environment Variables**:
```bash
# .env file
ALPHA_VANTAGE_API_KEY=<your_key_here>  # Free tier: 5 calls/min, 500 calls/day
```

**Get Free Alpha Vantage API Key**: https://www.alphavantage.co/support/#api-key

### 4.3 Development Workflow

**Recommended Order**:

1. **Setup** (15 min)
   ```bash
   # Add requests to requirements
   echo "requests==2.31.0" >> requirements_quant.txt
   pip install requests

   # Get Alpha Vantage API key and add to .env
   echo "ALPHA_VANTAGE_API_KEY=<key>" >> .env
   ```

2. **FXTracker Development** (4-6 hours)
   ```bash
   # Create module structure
   mkdir -p modules/fx_tracking
   touch modules/fx_tracking/__init__.py
   touch modules/fx_tracking/fx_tracker.py

   # Create test structure
   mkdir -p tests/fx_tracking
   touch tests/fx_tracking/__init__.py
   touch tests/fx_tracking/test_fx_tracker.py

   # Implement in order (see Phase 1 tasks)
   # Run tests continuously
   python -m pytest tests/fx_tracking/ -v
   ```

3. **StockClassifier Development** (3-4 hours)
   ```bash
   # Create module structure
   mkdir -p modules/classification
   touch modules/classification/__init__.py
   touch modules/classification/stock_classifier.py

   # Create test structure
   mkdir -p tests/classification
   touch tests/classification/__init__.py
   touch tests/classification/test_stock_classifier.py

   # Implement in order (see Phase 2 tasks)
   # Run tests continuously
   python -m pytest tests/classification/ -v
   ```

4. **Orchestrator Integration** (1-2 hours)
   ```bash
   # Update orchestrator methods
   # Unskip 4 tests in test_orchestrator_phase1.py

   # Run full test suite
   python -m pytest tests/orchestration/test_orchestrator_phase1.py -v
   ```

5. **Manual E2E Test** (30 min)
   ```bash
   # Test full pipeline with real data
   python3 spock_refresh.py --quick --regions KR

   # Verify database updates
   psql -d quant_platform -c "
   SELECT from_currency, to_currency, rate, rate_date, source
   FROM exchange_rate_history
   ORDER BY rate_date DESC
   LIMIT 10;
   "

   psql -d quant_platform -c "
   SELECT ticker, region, sector, industry, is_spac, is_preferred
   FROM stock_details
   WHERE sector IS NOT NULL
   LIMIT 10;
   "
   ```

---

## 5. Testing Strategy

### 5.1 Unit Testing Philosophy

Following ETFUpdater pattern (18 tests, 100% pass rate):

**Key Principles**:
1. **Mock External Dependencies**: All API calls mocked
2. **Test Data Isolation**: No real database required for unit tests
3. **Comprehensive Coverage**: Test success paths, error paths, edge cases
4. **Fast Execution**: All 22 tests should complete in <5 seconds

### 5.2 Test Coverage Goals

| Module | Unit Tests | Integration Tests | Total | Target Coverage |
|--------|-----------|------------------|-------|-----------------|
| **FXTracker** | 12 tests | 3 tests | 15 tests | 85%+ |
| **StockClassifier** | 10 tests | 2 tests | 12 tests | 85%+ |
| **Orchestrator** | 4 tests (unskip) | 1 test (unskip) | 5 tests | 90%+ |
| **Total** | **26 tests** | **6 tests** | **32 tests** | **85%+** |

### 5.3 Integration Testing

**Integration Test 1: FXTracker + Real Database**
```python
def test_fx_tracker_real_db_integration():
    """Test FXTracker with real PostgreSQL database"""

    db = PostgresDatabaseManager()
    tracker = FXTracker(db_manager=db)

    # Update single currency pair
    result = tracker.update_fx_rates(
        currency_pairs=['USD/KRW'],
        backfill_days=0,
        dry_run=False
    )

    # Verify database update
    assert result['success'] == True
    assert result['rates_inserted'] >= 1

    # Query database
    rates = db.fetch_all("""
        SELECT * FROM exchange_rate_history
        WHERE from_currency = 'USD' AND to_currency = 'KRW'
        ORDER BY rate_date DESC LIMIT 1
    """)

    assert len(rates) >= 1
    assert rates[0]['rate'] > 0
```

**Integration Test 2: StockClassifier + Real Database**
```python
def test_stock_classifier_real_db_integration():
    """Test StockClassifier with real PostgreSQL database"""

    db = PostgresDatabaseManager()
    classifier = StockClassifier(db_manager=db)

    # Classify KR stocks
    result = classifier.classify_stocks(
        region='KR',
        batch_size=10,
        dry_run=False
    )

    # Verify database update
    assert result['success'] == True
    assert result['stocks_classified'] >= 1

    # Query database
    stocks = db.fetch_all("""
        SELECT * FROM stock_details
        WHERE region = 'KR' AND sector IS NOT NULL
        LIMIT 10
    """)

    assert len(stocks) >= 1
    assert stocks[0]['sector'] is not None
```

---

## 6. Integration Points

### 6.1 Orchestrator Integration

**File**: `modules/orchestration/orchestrator.py`

**Method 1: `_track_exchange_rates()`** (already exists as stub)
```python
def _track_exchange_rates(self, regions: List[str]) -> Dict:
    """
    Execute FX tracking step

    Args:
        regions: List of regions to track FX for

    Returns:
        Dict with success status and statistics
    """
    from modules.fx_tracking.fx_tracker import FXTracker

    logger.info(f"🌐 Executing FX tracking for regions: {regions}")

    try:
        tracker = FXTracker(db_manager=self.db)

        # Determine currency pairs based on regions
        currency_pairs = self._get_currencies_for_regions(regions)

        # Update FX rates (today only, no backfill)
        result = tracker.update_fx_rates(
            currency_pairs=currency_pairs,
            backfill_days=0,
            dry_run=False
        )

        if result['success']:
            logger.info(f"✅ FX tracking complete: {result['pairs_updated']} pairs, "
                       f"{result['rates_inserted']} rates inserted")
        else:
            logger.warning(f"⚠️  FX tracking completed with errors: {result['errors']}")

        return result

    except Exception as e:
        logger.error(f"❌ FX tracking failed: {e}")
        return {
            'success': False,
            'pairs_updated': 0,
            'rates_inserted': 0,
            'errors': [str(e)]
        }
```

**Method 2: `_classify_stocks()`** (already exists as stub)
```python
def _classify_stocks(self, regions: List[str]) -> Dict:
    """
    Execute stock classification step

    Args:
        regions: List of regions to classify stocks for

    Returns:
        Dict with success status and statistics
    """
    from modules.classification.stock_classifier import StockClassifier

    logger.info(f"🏷️  Executing stock classification for regions: {regions}")

    try:
        classifier = StockClassifier(db_manager=self.db)

        # Classify stocks for each region
        total_classified = 0
        total_spac = 0
        total_preferred = 0
        all_errors = []

        for region in regions:
            result = classifier.classify_stocks(
                region=region,
                batch_size=100,
                dry_run=False
            )

            if result['success']:
                total_classified += result['stocks_classified']
                total_spac += result['spac_detected']
                total_preferred += result['preferred_detected']
                logger.info(f"✅ {region}: {result['stocks_classified']} classified, "
                           f"{result['spac_detected']} SPACs, "
                           f"{result['preferred_detected']} preferred")
            else:
                all_errors.extend(result['errors'])
                logger.warning(f"⚠️  {region} classification failed")

        return {
            'success': len(all_errors) == 0,
            'stocks_classified': total_classified,
            'spac_detected': total_spac,
            'preferred_detected': total_preferred,
            'errors': all_errors
        }

    except Exception as e:
        logger.error(f"❌ Stock classification failed: {e}")
        return {
            'success': False,
            'stocks_classified': 0,
            'spac_detected': 0,
            'preferred_detected': 0,
            'errors': [str(e)]
        }
```

**Helper Method: `_get_currencies_for_regions()`** (already exists)
```python
def _get_currencies_for_regions(self, regions: List[str]) -> List[str]:
    """
    Get required currency pairs for regions

    Args:
        regions: List of region codes

    Returns:
        List of currency pairs (e.g., ['USD/KRW', 'USD/JPY'])
    """
    currency_map = {
        'KR': ['USD/KRW'],
        'US': [],  # No FX needed for USD base
        'JP': ['USD/JPY'],
        'HK': ['USD/HKD'],
        'CN': ['USD/CNY'],
        'VN': ['USD/VND']
    }

    pairs = []
    for region in regions:
        pairs.extend(currency_map.get(region, []))

    # Remove duplicates and return
    return list(set(pairs))
```

### 6.2 Test Integration

**File**: `tests/orchestration/test_orchestrator_phase1.py`

**Unskip 4 Tests**:
```python
# Remove @unittest.skip decorator from:

# Test 7: FXTracker integration
def test_track_exchange_rates(self):
    """Test FX tracking step execution"""

    with patch('modules.fx_tracking.fx_tracker.FXTracker') as mock_fx:
        # Mock FXTracker
        mock_instance = MagicMock()
        mock_instance.update_fx_rates.return_value = {
            'success': True,
            'pairs_updated': 1,
            'rates_inserted': 1,
            'errors': []
        }
        mock_fx.return_value = mock_instance

        # Test
        result = self.orchestrator._track_exchange_rates(['KR'])

        # Assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['pairs_updated'], 1)


# Test 8: StockClassifier integration
def test_classify_stocks_kr(self):
    """Test stock classification step execution"""

    with patch('modules.classification.stock_classifier.StockClassifier') as mock_classifier:
        # Mock StockClassifier
        mock_instance = MagicMock()
        mock_instance.classify_stocks.return_value = {
            'success': True,
            'stocks_classified': 10,
            'spac_detected': 1,
            'preferred_detected': 2,
            'errors': []
        }
        mock_classifier.return_value = mock_instance

        # Test
        result = self.orchestrator._classify_stocks(['KR'])

        # Assertions
        self.assertTrue(result['success'])
        self.assertEqual(result['stocks_classified'], 10)


# Test 9: Full pipeline with all 9 steps (integration test)
def test_full_pipeline_with_new_steps(self):
    """Test complete 9-step pipeline"""

    # Mock all step executors
    # ... (comprehensive integration test)


# Test 14: ETFUpdater integration (already passing, but verify)
def test_update_etf_data_kr(self):
    """Test ETF data update step execution"""
    # Already implemented and passing
```

### 6.3 CLI Integration

**File**: `spock_refresh.py` (no changes needed)

Orchestrator automatically calls all 9 steps including:
- Step 3: `fx_tracking` → `_track_exchange_rates()`
- Step 6: `classification` → `_classify_stocks()`
- Step 8: `etf_data` → `_update_etf_data()` (already working)

**Usage**:
```bash
# Quick refresh (includes FX and classification)
python3 spock_refresh.py --quick --regions KR

# Full refresh (all 9 steps)
python3 spock_refresh.py --full --regions KR US
```

---

## 7. Success Criteria

### 7.1 FXTracker Success Criteria

✅ **Functional**:
- [ ] Successfully fetch FX rates from Alpha Vantage API
- [ ] Fallback to yfinance if Alpha Vantage fails
- [ ] Mock data fallback for development
- [ ] UPSERT rates to `exchange_rate_history` table
- [ ] Validate rates (5% daily change threshold)
- [ ] Support 6 currency pairs (USD/KRW, USD/JPY, USD/HKD, USD/CNY, USD/VND, USD/EUR)

✅ **Performance**:
- [ ] <30 seconds to update all 6 currency pairs
- [ ] <5 seconds for single currency pair

✅ **Testing**:
- [ ] 12 unit tests passing (100%)
- [ ] 3 integration tests passing
- [ ] Code coverage >85%

### 7.2 StockClassifier Success Criteria

✅ **Functional**:
- [ ] Fetch sector/industry from pykrx (KR) and yfinance (US/others)
- [ ] Detect SPACs by name patterns (KR: "스팩", US: "Acquisition Corp")
- [ ] Detect preferred stocks (KR: "우선주", US: "-P" suffix)
- [ ] UPDATE `stock_details` table (only NULL fields)
- [ ] Support multi-region classification (KR, US, HK, JP, CN, VN)

✅ **Coverage**:
- [ ] >95% classification rate for active tickers
- [ ] >90% accuracy for SPAC detection
- [ ] >95% accuracy for preferred stock detection

✅ **Performance**:
- [ ] <5 minutes for 1,000 stocks
- [ ] <30 seconds for 100 stocks

✅ **Testing**:
- [ ] 10 unit tests passing (100%)
- [ ] 2 integration tests passing
- [ ] Code coverage >85%

### 7.3 Orchestrator Integration Criteria

✅ **Integration**:
- [ ] `_track_exchange_rates()` successfully calls FXTracker
- [ ] `_classify_stocks()` successfully calls StockClassifier
- [ ] All 4 previously skipped tests now passing
- [ ] Full 9-step pipeline executes without errors

✅ **Validation**:
- [ ] Database updated correctly (verify with SQL queries)
- [ ] Logging clear and informative
- [ ] Error handling graceful
- [ ] Retry logic working (from Day 1-2 implementation)

---

## 8. Risk Assessment

### 8.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Alpha Vantage API rate limit** | High | Medium | Implement yfinance fallback + mock data |
| **pykrx API changes** | Low | High | Pin version, use try-except, mock fallback |
| **yfinance API instability** | Medium | Medium | Retry logic, timeout handling |
| **Database connection issues** | Low | High | Use connection pooling, transaction safety |
| **Missing data from sources** | High | Low | Accept partial results, log warnings |

### 8.2 Schedule Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Implementation takes longer** | Medium | Medium | Reduce scope (skip optional features) |
| **Testing discovers bugs** | High | Low | Iterative testing during development |
| **API key acquisition delay** | Low | Low | Use mock data for development |
| **Integration issues** | Low | Medium | Follow ETFUpdater pattern exactly |

### 8.3 Quality Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Low test coverage** | Low | High | Write tests alongside implementation |
| **Poor error handling** | Low | High | Follow ETFUpdater error handling pattern |
| **Incomplete documentation** | Medium | Low | Update this design doc as needed |

---

## 9. Appendices

### Appendix A: Reference Implementations

**ETFUpdater** (completed Day 4):
- File: `/Users/13ruce/spock/modules/etf_update/etf_updater.py` (604 lines)
- Tests: `/Users/13ruce/spock/tests/etf_update/test_etf_updater.py` (458 lines, 18 tests)
- Completion Report: `/Users/13ruce/spock/docs/DAY4_COMPLETION_REPORT.md`

**DatabaseUpdateOrchestrator** (enhanced Day 1-2):
- File: `/Users/13ruce/spock/modules/orchestration/orchestrator.py` (+320 lines)
- Tests: `/Users/13ruce/spock/tests/orchestration/test_orchestrator_phase1.py` (14 tests, 10 passing, 4 skipped)
- Completion Report: `/Users/13ruce/spock/docs/DB_REFRESH_PHASE1_DAY1_2_COMPLETION_REPORT.md`

### Appendix B: External API Documentation

**Alpha Vantage**:
- Website: https://www.alphavantage.co/
- FX API: https://www.alphavantage.co/documentation/#fx
- Free Tier: 5 calls/min, 500 calls/day
- Example: `https://www.alphavantage.co/query?function=FX_DAILY&from_symbol=USD&to_symbol=KRW&apikey=demo`

**pykrx**:
- GitHub: https://github.com/sharebook-kr/pykrx
- Docs: https://github.com/sharebook-kr/pykrx/wiki
- Sector API: `stock.get_market_sector(ticker)`, `stock.get_market_sector_list(market="ALL")`

**yfinance**:
- GitHub: https://github.com/ranaroussi/yfinance
- Docs: https://github.com/ranaroussi/yfinance/wiki
- Sector API: `Ticker(ticker).info['sector']`, `Ticker(ticker).info['industry']`
- FX Tickers: `KRW=X`, `JPY=X`, `HKD=X`, etc.

### Appendix C: Database Schema Reference

**`exchange_rate_history` Table**:
```sql
SELECT * FROM exchange_rate_history LIMIT 5;

 from_currency | to_currency |   rate    | rate_date  |    source     |      created_at
---------------|-------------|-----------|------------|---------------|----------------------
 USD           | KRW         | 1380.50   | 2024-11-05 | alpha_vantage | 2024-11-05 10:15:00
 USD           | JPY         | 151.75    | 2024-11-05 | yfinance      | 2024-11-05 10:15:05
```

**`stock_details` Table**:
```sql
SELECT ticker, region, sector, industry, is_spac, is_preferred FROM stock_details WHERE sector IS NOT NULL LIMIT 5;

 ticker | region |    sector    |        industry        | is_spac | is_preferred
--------|--------|--------------|------------------------|---------|-------------
 005930 | KR     | 전기전자     | 전기전자               | FALSE   | FALSE
 000660 | KR     | 전기전자     | 전기전자               | FALSE   | FALSE
 AAPL   | US     | Technology   | Consumer Electronics   | FALSE   | FALSE
```

---

**Document Status**: ✅ Complete and Ready for Implementation
**Next Step**: Begin FXTracker implementation (Phase 1)
**Estimated Completion**: 2025-11-05 (7-10 hours from start)
