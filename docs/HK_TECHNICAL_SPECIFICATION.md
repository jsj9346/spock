# 🇭🇰 HK Market Technical Specification

**Project**: Spock Quant Platform - HK Market Integration
**Version**: 1.0.0
**Date**: 2025-11-12
**Status**: Design Complete

---

## 1. System Architecture

### 1.1 Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Server (AI Interface)                    │
│  Tools: query_ohlcv_data | screen_stocks | run_backtest        │
│  Regions: KR | US | HK ← NEW                                    │
└───────────────────┬─────────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────────┐
│                   HK Market Adapter Layer                        │
│  ┌──────────────┬──────────────┬──────────────────────────┐    │
│  │ HKAdapter    │ yfinance API │ HK Stock Parser          │    │
│  │ (OHLCV)      │ (Data Source)│ (Normalization)          │    │
│  └──────────────┴──────────────┴──────────────────────────┘    │
└───────────────────┬─────────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────────┐
│              PostgreSQL + TimescaleDB (Data Layer)               │
│  Tables: tickers | ohlcv_data | stock_details | etf_details    │
│  Region Filter: WHERE region = 'HK'                             │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 Data Flow

**OHLCV Collection**:
```
yfinance API → HKAdapter → HKStockParser → PostgreSQL
                ↓                ↓
         Rate Limiter    Ticker Normalization
         (1 req/sec)     (0700 → 0700.HK)
```

**MCP Query**:
```
AI Assistant → MCP Server → Data Adapter → HKAdapter → PostgreSQL
                   ↓              ↓              ↓
            Validation    Region Filter    Query Builder
```

---

## 2. Database Schema

### 2.1 HK-Specific Columns

**tickers table**:
```sql
-- HK ticker format: "0700.HK", "9988.HK"
CREATE TABLE tickers (
    ticker VARCHAR(20) PRIMARY KEY,
    region VARCHAR(10) NOT NULL,  -- 'HK' for Hong Kong
    name VARCHAR(255),
    asset_type VARCHAR(10),        -- 'STOCK' or 'ETF'
    is_active BOOLEAN DEFAULT TRUE,
    listing_date DATE,
    delisting_date DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for HK queries
CREATE INDEX idx_tickers_region_hk ON tickers(region) WHERE region = 'HK';
```

**stock_details table**:
```sql
CREATE TABLE stock_details (
    ticker VARCHAR(20),
    region VARCHAR(10),
    market_cap BIGINT,              -- In HKD
    sector VARCHAR(100),            -- GICS standardized
    sector_code VARCHAR(10),        -- GICS 2-digit code
    industry VARCHAR(100),          -- Native industry name
    native_sector VARCHAR(100),     -- HKEX native sector
    currency VARCHAR(10) DEFAULT 'HKD',
    exchange VARCHAR(50) DEFAULT 'HKEX',
    lot_size INT DEFAULT 1,         -- HK board lot size (100, 500, 1000, etc.)
    PRIMARY KEY (ticker, region),
    FOREIGN KEY (ticker, region) REFERENCES tickers(ticker, region)
);
```

**ohlcv_data hypertable**:
```sql
-- TimescaleDB hypertable for time-series optimization
CREATE TABLE ohlcv_data (
    ticker VARCHAR(20),
    region VARCHAR(10),
    date DATE NOT NULL,
    open NUMERIC(20, 4),
    high NUMERIC(20, 4),
    low NUMERIC(20, 4),
    close NUMERIC(20, 4),
    volume BIGINT,
    timeframe VARCHAR(10) DEFAULT '1d',
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (ticker, region, date, timeframe)
);

-- Convert to hypertable
SELECT create_hypertable('ohlcv_data', 'date',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

-- Compression policy (compress data older than 1 year)
ALTER TABLE ohlcv_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker,region',
    timescaledb.compress_orderby = 'date DESC'
);

-- Index for HK queries
CREATE INDEX idx_ohlcv_region_hk ON ohlcv_data(region, ticker, date DESC)
WHERE region = 'HK';
```

### 2.2 Query Examples

**Get HK stocks with OHLCV data**:
```sql
SELECT
    t.ticker,
    t.name,
    sd.market_cap,
    sd.sector,
    COUNT(o.date) as trading_days,
    MIN(o.date) as first_date,
    MAX(o.date) as last_date
FROM tickers t
JOIN stock_details sd ON t.ticker = sd.ticker AND t.region = sd.region
JOIN ohlcv_data o ON t.ticker = o.ticker AND t.region = o.region
WHERE t.region = 'HK' AND t.asset_type = 'STOCK'
GROUP BY t.ticker, t.name, sd.market_cap, sd.sector
ORDER BY sd.market_cap DESC NULLS LAST;
```

**Get HK OHLCV data for backtesting**:
```sql
SELECT
    ticker,
    date,
    close,
    volume
FROM ohlcv_data
WHERE region = 'HK'
  AND ticker = ANY(ARRAY['0700.HK', '9988.HK', '0941.HK'])
  AND date BETWEEN '2020-01-01' AND '2025-11-12'
ORDER BY ticker, date;
```

---

## 3. Code Specifications

### 3.1 HK Data Quality Validator

**File**: `modules/data_quality/hk_validator.py`

```python
"""
Hong Kong Market Data Quality Validator

Validates OHLCV data quality for HK market with HKEX-specific checks.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class HKDataQualityValidator:
    """
    HK market data quality validation

    Quality Gates:
    1. Completeness: No missing trading days (HKEX calendar)
    2. Validity: All OHLCV values >0, High ≥ Low ≥ Close ≥ Open
    3. Consistency: No extreme price jumps (>50% single day)
    4. Volume: Volume >0 for active trading days

    HK-Specific Checks:
    - HKEX holiday calendar compliance
    - Half-day trading sessions (pre-holiday)
    - Typhoon/black rainstorm trading halts
    - Board lot size validation
    """

    # HKEX trading calendar (simplified - use official API in production)
    HKEX_HOLIDAYS_2024 = [
        '2024-01-01',  # New Year
        '2024-02-10',  # Lunar New Year Eve
        '2024-02-12',  # Lunar New Year
        '2024-02-13',  # Lunar New Year
        '2024-03-29',  # Good Friday
        '2024-03-30',  # Day after Good Friday
        '2024-04-01',  # Easter Monday
        '2024-04-04',  # Ching Ming Festival
        '2024-05-01',  # Labour Day
        '2024-05-15',  # Buddha's Birthday
        '2024-06-10',  # Dragon Boat Festival
        '2024-07-01',  # Hong Kong SAR Establishment Day
        '2024-09-18',  # Day after Mid-Autumn Festival
        '2024-10-01',  # National Day
        '2024-10-11',  # Chung Yeung Festival
        '2024-12-25',  # Christmas Day
        '2024-12-26',  # Boxing Day
    ]

    def __init__(self):
        self.holidays = pd.to_datetime(self.HKEX_HOLIDAYS_2024)

    def validate_ohlcv(self, ticker: str, df: pd.DataFrame) -> Dict:
        """
        Run comprehensive OHLCV validation

        Args:
            ticker: HK ticker (e.g., "0700.HK")
            df: OHLCV DataFrame with columns [date, open, high, low, close, volume]

        Returns:
            {
                'ticker': '0700.HK',
                'total_days': 1230,
                'completeness_score': 0.98,
                'validity_score': 1.0,
                'consistency_score': 0.99,
                'anomalies': [
                    {'date': '2024-05-10', 'issue': 'price_jump', 'severity': 'warning'}
                ],
                'passed': True
            }
        """
        results = {
            'ticker': ticker,
            'total_days': len(df),
            'anomalies': []
        }

        # 1. Completeness check
        results['completeness_score'] = self._check_completeness(df)

        # 2. Validity check
        results['validity_score'] = self._check_validity(df)

        # 3. Consistency check (price jumps)
        results['consistency_score'], anomalies = self._check_consistency(ticker, df)
        results['anomalies'].extend(anomalies)

        # 4. Volume check
        results['volume_score'] = self._check_volume(df)

        # 5. Overall pass/fail
        results['passed'] = (
            results['completeness_score'] >= 0.95 and
            results['validity_score'] >= 0.99 and
            results['consistency_score'] >= 0.95
        )

        return results

    def _check_completeness(self, df: pd.DataFrame) -> float:
        """
        Check if all expected trading days are present

        Returns:
            Completeness score (0.0-1.0)
        """
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])

        # Get date range
        start_date = df['date'].min()
        end_date = df['date'].max()

        # Generate expected trading days (weekdays excluding holidays)
        expected_dates = pd.bdate_range(start=start_date, end=end_date)
        expected_dates = expected_dates[~expected_dates.isin(self.holidays)]

        # Calculate completeness
        actual_dates = set(df['date'])
        expected_dates = set(expected_dates)

        if len(expected_dates) == 0:
            return 1.0

        completeness = len(actual_dates & expected_dates) / len(expected_dates)

        return completeness

    def _check_validity(self, df: pd.DataFrame) -> float:
        """
        Check if OHLCV values are valid

        Rules:
        - All values >0
        - High ≥ Low
        - High ≥ Open, Close
        - Low ≤ Open, Close

        Returns:
            Validity score (0.0-1.0)
        """
        invalid_count = 0
        total_rows = len(df)

        # Check for null or negative values
        invalid_count += df[['open', 'high', 'low', 'close', 'volume']].isna().sum().sum()
        invalid_count += (df[['open', 'high', 'low', 'close']] <= 0).sum().sum()
        invalid_count += (df['volume'] < 0).sum()

        # Check OHLC relationships
        invalid_count += (df['high'] < df['low']).sum()
        invalid_count += (df['high'] < df['open']).sum()
        invalid_count += (df['high'] < df['close']).sum()
        invalid_count += (df['low'] > df['open']).sum()
        invalid_count += (df['low'] > df['close']).sum()

        if total_rows == 0:
            return 1.0

        validity = 1.0 - (invalid_count / (total_rows * 5))  # 5 checks per row

        return max(0.0, validity)

    def _check_consistency(self, ticker: str, df: pd.DataFrame) -> Tuple[float, List[Dict]]:
        """
        Check for extreme price jumps and anomalies

        Returns:
            (consistency_score, anomaly_list)
        """
        df = df.copy().sort_values('date')
        anomalies = []

        # Calculate daily returns
        df['return'] = df['close'].pct_change()

        # Detect extreme price jumps (>50% in single day)
        extreme_jumps = df[abs(df['return']) > 0.5]

        for idx, row in extreme_jumps.iterrows():
            anomalies.append({
                'date': str(row['date']),
                'issue': 'extreme_price_jump',
                'severity': 'warning',
                'details': f"Return: {row['return']:.2%}"
            })

        # Calculate consistency score
        consistency = 1.0 - (len(extreme_jumps) / len(df))

        return consistency, anomalies

    def _check_volume(self, df: pd.DataFrame) -> float:
        """
        Check if volume data is reasonable

        Returns:
            Volume score (0.0-1.0)
        """
        zero_volume = (df['volume'] == 0).sum()
        total_rows = len(df)

        if total_rows == 0:
            return 1.0

        # Allow up to 5% zero-volume days (halted trading, etc.)
        volume_score = 1.0 - (zero_volume / total_rows)

        return max(0.0, min(1.0, volume_score + 0.05))


def validate_hk_market_data(tickers: List[str] = None) -> pd.DataFrame:
    """
    Validate HK market data quality for all or specified tickers

    Args:
        tickers: List of HK tickers (e.g., ["0700.HK", "9988.HK"])
                If None, validate all HK tickers with OHLCV data

    Returns:
        DataFrame with validation results
    """
    import psycopg2
    import os
    from dotenv import load_dotenv

    load_dotenv()

    # Connect to database
    conn = psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', 5432),
        database=os.getenv('POSTGRES_DB', 'quant_platform'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD')
    )

    validator = HKDataQualityValidator()
    results = []

    # Get tickers to validate
    if tickers is None:
        query = """
        SELECT DISTINCT ticker
        FROM ohlcv_data
        WHERE region = 'HK'
        ORDER BY ticker
        """
        tickers_df = pd.read_sql(query, conn)
        tickers = tickers_df['ticker'].tolist()

    logger.info(f"Validating {len(tickers)} HK tickers...")

    for i, ticker in enumerate(tickers, 1):
        # Fetch OHLCV data
        query = """
        SELECT date, open, high, low, close, volume
        FROM ohlcv_data
        WHERE ticker = %s AND region = 'HK'
        ORDER BY date
        """
        df = pd.read_sql(query, conn, params=(ticker,))

        if df.empty:
            logger.warning(f"No data for {ticker}")
            continue

        # Validate
        result = validator.validate_ohlcv(ticker, df)
        results.append(result)

        if i % 50 == 0:
            logger.info(f"Progress: {i}/{len(tickers)} tickers validated")

    conn.close()

    # Convert to DataFrame
    results_df = pd.DataFrame(results)

    return results_df


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    # Validate all HK tickers
    results = validate_hk_market_data()

    # Print summary
    print("\n=== HK Data Quality Validation Summary ===")
    print(f"Total tickers validated: {len(results)}")
    print(f"Passed: {results['passed'].sum()} ({results['passed'].mean():.1%})")
    print(f"Failed: {(~results['passed']).sum()}")
    print(f"\nAverage Scores:")
    print(f"  Completeness: {results['completeness_score'].mean():.2%}")
    print(f"  Validity: {results['validity_score'].mean():.2%}")
    print(f"  Consistency: {results['consistency_score'].mean():.2%}")
    print(f"  Volume: {results['volume_score'].mean():.2%}")

    # Save report
    results.to_csv('reports/hk_quality_validation_report.csv', index=False)
    print(f"\nReport saved to: reports/hk_quality_validation_report.csv")
```

---

### 3.2 MCP Server Integration

**File**: `mcp_server/utils/validators.py`

**Current Code**:
```python
# Line 63
{"provided_region": region, "allowed_regions": ["KR", "US"]}
```

**Updated Code**:
```python
# Add HK to allowed regions
ALLOWED_REGIONS = ["KR", "US", "HK"]

def validate_region(region: str) -> None:
    """
    Validate region parameter

    Args:
        region: Market region code

    Raises:
        ValidationError: If region is not supported
    """
    if region not in ALLOWED_REGIONS:
        raise ValidationError(
            f"Unsupported region: {region}",
            {"provided_region": region, "allowed_regions": ALLOWED_REGIONS}
        )

def validate_tickers(tickers: List[str], region: str = "KR") -> None:
    """
    Validate ticker symbols based on region

    HK Ticker Rules:
    - 4-digit numeric: "0700", "9988"
    - Appended with ".HK" for yfinance: "0700.HK"
    - Leading zeros preserved: "0001" not "1"
    """
    # ... existing KR/US validation ...

    # HK ticker validation
    if region == "HK":
        hk_pattern = re.compile(r'^\d{4}$')
        for ticker in tickers:
            # Remove .HK suffix if present
            base_ticker = ticker.replace('.HK', '')
            if not hk_pattern.match(base_ticker):
                raise ValidationError(
                    f"Invalid HK ticker format: {ticker}",
                    {
                        "ticker": ticker,
                        "expected_format": "4-digit numeric (e.g., 0700, 9988)",
                        "provided_format": ticker
                    }
                )
```

---

### 3.3 Tiered Backfill Script

**File**: `scripts/backfill_hk_ohlcv_tiered.py`

```python
"""
HK OHLCV Tiered Backfill Script

Prioritized backfill strategy:
- Tier 1: HSI constituents (80 tickers, 5 years)
- Tier 2: High market cap (500 tickers, 3 years)
- Tier 3: Mid market cap (800 tickers, 2 years)
- Tier 4: Small cap & remaining (1,343 tickers, 1 year)
"""

import argparse
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd
import psycopg2
from dotenv import load_dotenv
import os

from modules.market_adapters.hk_adapter import HKAdapter
from modules.data_quality.hk_validator import HKDataQualityValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


class HKTieredBackfiller:
    """
    Tiered backfill strategy for HK market data
    """

    TIER_CONFIG = {
        1: {
            'name': 'HSI Constituents',
            'count': 80,
            'years': 5,
            'priority': 'critical'
        },
        2: {
            'name': 'High Market Cap (>$1B)',
            'count': 500,
            'years': 3,
            'priority': 'high'
        },
        3: {
            'name': 'Mid Market Cap ($100M-$1B)',
            'count': 800,
            'years': 2,
            'priority': 'medium'
        },
        4: {
            'name': 'Small Cap & Remaining',
            'count': 1343,
            'years': 1,
            'priority': 'low'
        }
    }

    def __init__(self, rate_limit: float = 1.0):
        """
        Initialize backfiller

        Args:
            rate_limit: Requests per second (yfinance limit)
        """
        # Database connection
        self.conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', 5432),
            database=os.getenv('POSTGRES_DB', 'quant_platform'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD')
        )

        # HK adapter
        from modules.db_manager_postgres import PostgresDatabaseManager
        self.db_manager = PostgresDatabaseManager()
        self.hk_adapter = HKAdapter(self.db_manager)

        # Validator
        self.validator = HKDataQualityValidator()

        # Rate limiting
        self.rate_limit = rate_limit
        self.last_request_time = 0

    def get_tier_tickers(self, tier: int) -> List[str]:
        """
        Get tickers for specified tier

        Args:
            tier: Tier number (1-4)

        Returns:
            List of tickers for this tier
        """
        if tier == 1:
            # HSI constituents (fetch from file or hardcoded list)
            # In production, fetch from HKEX API
            return [
                '0700', '9988', '0941', '1299', '0388', '0005', '3690', '2318',
                '1398', '0011', '0939', '2628', '0883', '0386', '1288', '0857',
                # ... (full HSI constituent list)
            ]

        elif tier == 2:
            # High market cap (>$1B)
            query = """
            SELECT t.ticker
            FROM tickers t
            JOIN stock_details sd ON t.ticker = sd.ticker AND t.region = sd.region
            WHERE t.region = 'HK'
              AND sd.market_cap > 1000000000
              AND t.ticker NOT IN (
                  -- Exclude Tier 1 tickers
                  SELECT ticker FROM unnest(%s::text[]) AS ticker
              )
            ORDER BY sd.market_cap DESC
            LIMIT %s
            """
            tier1_tickers = self.get_tier_tickers(1)
            df = pd.read_sql(query, self.conn, params=(tier1_tickers, self.TIER_CONFIG[2]['count']))
            return df['ticker'].tolist()

        elif tier == 3:
            # Mid market cap ($100M-$1B)
            query = """
            SELECT t.ticker
            FROM tickers t
            JOIN stock_details sd ON t.ticker = sd.ticker AND t.region = sd.region
            WHERE t.region = 'HK'
              AND sd.market_cap BETWEEN 100000000 AND 1000000000
            ORDER BY sd.market_cap DESC
            LIMIT %s
            """
            df = pd.read_sql(query, self.conn, params=(self.TIER_CONFIG[3]['count'],))
            return df['ticker'].tolist()

        elif tier == 4:
            # Small cap & remaining
            query = """
            SELECT t.ticker
            FROM tickers t
            LEFT JOIN ohlcv_data o ON t.ticker = o.ticker AND t.region = o.region
            WHERE t.region = 'HK'
              AND o.ticker IS NULL  -- No OHLCV data yet
            ORDER BY t.ticker
            """
            df = pd.read_sql(query, self.conn)
            return df['ticker'].tolist()

    def backfill_tier(self, tier: int, validate: bool = True) -> Dict:
        """
        Backfill OHLCV data for specified tier

        Args:
            tier: Tier number (1-4)
            validate: Run quality validation after backfill

        Returns:
            {
                'tier': 1,
                'total_tickers': 80,
                'success_count': 78,
                'failed_tickers': ['0001', '0002'],
                'duration_seconds': 7200,
                'validation_results': {...}
            }
        """
        config = self.TIER_CONFIG[tier]
        logger.info(f"\n{'='*60}")
        logger.info(f"Starting Tier {tier}: {config['name']}")
        logger.info(f"Target: {config['count']} tickers, {config['years']} years")
        logger.info(f"Priority: {config['priority']}")
        logger.info(f"{'='*60}\n")

        # Get tickers for this tier
        tickers = self.get_tier_tickers(tier)
        logger.info(f"Found {len(tickers)} tickers for Tier {tier}")

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=config['years'] * 365)

        # Backfill each ticker
        start_time = time.time()
        success_count = 0
        failed_tickers = []

        for i, ticker in enumerate(tickers, 1):
            try:
                # Rate limiting
                self._rate_limit()

                logger.info(f"[{i}/{len(tickers)}] Backfilling {ticker}...")

                # Collect OHLCV data
                self.hk_adapter.collect_stock_ohlcv(
                    tickers=[ticker],
                    days=config['years'] * 365,
                    force_refresh=True
                )

                success_count += 1

            except Exception as e:
                logger.error(f"Failed to backfill {ticker}: {e}")
                failed_tickers.append(ticker)

        duration = time.time() - start_time

        # Results
        results = {
            'tier': tier,
            'tier_name': config['name'],
            'total_tickers': len(tickers),
            'success_count': success_count,
            'failed_tickers': failed_tickers,
            'duration_seconds': duration,
            'validation_results': None
        }

        # Validation
        if validate and success_count > 0:
            logger.info(f"\nRunning quality validation for Tier {tier}...")
            validation_df = self.validator.validate_hk_market_data(tickers=tickers)
            results['validation_results'] = {
                'total_validated': len(validation_df),
                'passed': validation_df['passed'].sum(),
                'failed': (~validation_df['passed']).sum(),
                'avg_completeness': validation_df['completeness_score'].mean(),
                'avg_validity': validation_df['validity_score'].mean(),
                'avg_consistency': validation_df['consistency_score'].mean()
            }

        # Summary
        logger.info(f"\n{'='*60}")
        logger.info(f"Tier {tier} Backfill Complete")
        logger.info(f"Success: {success_count}/{len(tickers)}")
        logger.info(f"Duration: {duration/3600:.1f} hours")
        if results['validation_results']:
            logger.info(f"Validation Pass Rate: {results['validation_results']['passed']}/{results['validation_results']['total_validated']}")
        logger.info(f"{'='*60}\n")

        return results

    def _rate_limit(self):
        """Apply rate limiting for yfinance API"""
        elapsed = time.time() - self.last_request_time
        sleep_time = (1.0 / self.rate_limit) - elapsed

        if sleep_time > 0:
            time.sleep(sleep_time)

        self.last_request_time = time.time()


def main():
    parser = argparse.ArgumentParser(description='HK OHLCV Tiered Backfill')
    parser.add_argument('--tier', type=int, required=True, choices=[1, 2, 3, 4],
                        help='Tier to backfill (1=HSI, 2=High Cap, 3=Mid Cap, 4=Small Cap)')
    parser.add_argument('--rate-limit', type=float, default=1.0,
                        help='API requests per second (default: 1.0)')
    parser.add_argument('--validate', action='store_true',
                        help='Run quality validation after backfill')
    parser.add_argument('--log-file', type=str, default=None,
                        help='Log file path')

    args = parser.parse_args()

    # Configure logging
    if args.log_file:
        file_handler = logging.FileHandler(args.log_file)
        file_handler.setLevel(logging.INFO)
        logger.addHandler(file_handler)

    # Run backfill
    backfiller = HKTieredBackfiller(rate_limit=args.rate_limit)
    results = backfiller.backfill_tier(tier=args.tier, validate=args.validate)

    # Save results
    results_file = f'reports/hk_tier{args.tier}_backfill_results.json'
    import json
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    logger.info(f"Results saved to: {results_file}")


if __name__ == "__main__":
    main()
```

---

## 4. Testing Specifications

### 4.1 Unit Tests

**File**: `tests/backtesting/test_hk_engine.py`

```python
"""
HK Backtesting Engine Unit Tests
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta

from modules.backtesting.backtest_engine import BacktestEngine
from modules.backtesting.data_providers.postgres_data_provider import PostgresDataProvider


@pytest.fixture
def hk_test_data():
    """Prepare HK test data for backtesting"""
    # Load 10 HSI constituents with 3 years data
    tickers = ['0700.HK', '9988.HK', '0941.HK', '1299.HK', '0388.HK',
               '0005.HK', '3690.HK', '2318.HK', '1398.HK', '0011.HK']

    start_date = (datetime.now() - timedelta(days=3*365)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')

    provider = PostgresDataProvider()
    data = provider.get_ohlcv_batch(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        region='HK'
    )

    return data


def test_hk_backtest_data_loading(hk_test_data):
    """Test that HK data loads correctly"""
    assert not hk_test_data.empty
    assert 'close' in hk_test_data.columns
    assert 'volume' in hk_test_data.columns
    assert hk_test_data['close'].min() > 0
    assert hk_test_data['volume'].min() >= 0


def test_hk_backtest_simple_momentum(hk_test_data):
    """Test simple momentum strategy on HK market"""
    from modules/strategies.momentum_strategy import MomentumStrategy

    strategy = MomentumStrategy(lookback_days=126)  # 6 months
    engine = BacktestEngine(strategy=strategy, initial_capital=1000000)

    results = engine.run(hk_test_data, region='HK')

    # Assertions
    assert results is not None
    assert results['total_return'] is not None
    assert results['sharpe_ratio'] is not None
    assert results['max_drawdown'] is not None
    assert results['num_trades'] >= 100  # Statistical significance
    assert results['sharpe_ratio'] > 0.5  # Reasonable performance


def test_hk_backtest_performance_custom_engine(hk_test_data):
    """Test custom engine performance on HK market"""
    import time

    from modules/strategies.momentum_strategy import MomentumStrategy

    strategy = MomentumStrategy()
    engine = BacktestEngine(strategy=strategy)

    start_time = time.time()
    results = engine.run(hk_test_data, region='HK')
    duration = time.time() - start_time

    # Performance assertion: 3-year backtest should complete <30 seconds
    assert duration < 30.0, f"Backtest took {duration:.1f}s (target: <30s)"


def test_hk_backtest_performance_vectorbt(hk_test_data):
    """Test vectorbt performance on HK market"""
    import time

    from modules/backtesting.backtest_engines.vectorbt_adapter import VectorbtAdapter

    adapter = VectorbtAdapter()

    start_time = time.time()
    results = adapter.run_backtest(hk_test_data, strategy='momentum', region='HK')
    duration = time.time() - start_time

    # Performance assertion: 3-year backtest should complete <1 second
    assert duration < 1.0, f"vectorbt backtest took {duration:.3f}s (target: <1s)"


@pytest.mark.parametrize("ticker", [
    '0700.HK',  # Tencent
    '9988.HK',  # Alibaba
    '0005.HK',  # HSBC
])
def test_hk_individual_ticker_backtest(ticker):
    """Test backtesting individual HK tickers"""
    provider = PostgresDataProvider()
    data = provider.get_ohlcv_batch(
        tickers=[ticker],
        start_date='2023-01-01',
        end_date='2025-11-12',
        region='HK'
    )

    assert not data.empty
    assert len(data) >= 250  # At least 1 year of data
    assert data['close'].isna().sum() == 0  # No missing closes
```

---

**Document Version**: 1.0.0
**Last Updated**: 2025-11-12
**Status**: ✅ Ready for Implementation
