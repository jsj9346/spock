# Database Refresh System - Comprehensive Design

**Document Version**: 1.0.0
**Date**: 2025-11-04
**Status**: Design Phase

---

## Executive Summary

This document provides a comprehensive design for Spock's database refresh system, addressing multi-region ticker updates, incremental OHLCV updates, exchange rate tracking, sector classification, fundamental data collection, and ETF data management.

### Key Design Goals

1. **Multi-Region Support**: KR, US, HK, JP, CN, VN (excluding OTC markets)
2. **Incremental Updates**: Efficient delta updates for all data types
3. **Data Quality**: Automated backfill for NULL values and missing data
4. **Scalability**: Handle 20,000+ tickers across regions
5. **Reliability**: Checkpoint-based recovery and error handling
6. **Performance**: <30 minutes for full refresh, <5 minutes for incremental

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Ticker Refresh System](#2-ticker-refresh-system)
3. [OHLCV Update System](#3-ohlcv-update-system)
4. [Exchange Rate Tracking](#4-exchange-rate-tracking)
5. [Stock Classification System](#5-stock-classification-system)
6. [Fundamentals Update System](#6-fundamentals-update-system)
7. [ETF Data System](#7-etf-data-system)
8. [Data Flow Diagrams](#8-data-flow-diagrams)
9. [Implementation Plan](#9-implementation-plan)

---

## 1. System Architecture

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Spock Refresh Entry Point                    │
│                     (spock_refresh.py)                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│              Database Update Orchestrator                        │
│         (modules/orchestration/orchestrator.py)                  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Checkpoint Manager │ Rate Limiter │ Data Validator      │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────┬──────────┬──────────┬──────────┬──────────┬─────────┘
            │          │          │          │          │
    ┌───────▼──┐  ┌───▼────┐  ┌─▼─────┐  ┌─▼──────┐  ┌▼────────┐
    │ Ticker   │  │ OHLCV  │  │  FX   │  │ Stock  │  │   ETF   │
    │ Refresh  │  │ Update │  │Track  │  │Details │  │  Data   │
    └───────┬──┘  └───┬────┘  └─┬─────┘  └─┬──────┘  └┬────────┘
            │         │          │          │          │
    ┌───────▼─────────▼──────────▼──────────▼──────────▼─────────┐
    │              Regional Market Adapters                        │
    │  ┌──────┬──────┬──────┬──────┬──────┬──────┐               │
    │  │  KR  │  US  │  HK  │  JP  │  CN  │  VN  │               │
    │  └──────┴──────┴──────┴──────┴──────┴──────┘               │
    └──────────────────────────┬───────────────────────────────────┘
                               │
    ┌──────────────────────────▼───────────────────────────────────┐
    │                External Data Sources                          │
    │  ┌────────┬──────────┬─────────┬──────────┬──────────┐      │
    │  │ KIS    │ pykrx    │ DART    │ yfinance │  Alpha   │      │
    │  │ API    │          │ API     │          │  Vantage │      │
    │  └────────┴──────────┴─────────┴──────────┴──────────┘      │
    └──────────────────────────┬───────────────────────────────────┘
                               │
    ┌──────────────────────────▼───────────────────────────────────┐
    │          PostgreSQL + TimescaleDB Database                    │
    │  ┌────────────────────────────────────────────────────────┐  │
    │  │ tickers │ ohlcv_data │ exchange_rate_history │         │  │
    │  │ stock_details │ ticker_fundamentals │ etf_details      │  │
    │  └────────────────────────────────────────────────────────┘  │
    └──────────────────────────────────────────────────────────────┘
```

### 1.2 Component Responsibilities

| Component | Responsibility | Input | Output |
|-----------|---------------|-------|--------|
| **Orchestrator** | Pipeline coordination, checkpoint management | Config, regions | Status, metrics |
| **Ticker Refresh** | Ticker discovery, validation, deduplication | Region | Ticker list |
| **OHLCV Update** | Price data collection, technical indicators | Tickers | OHLCV records |
| **FX Tracker** | Exchange rate collection, valuation signals | Currency pairs | FX rates |
| **Stock Details** | Sector/industry classification | Tickers | Classification |
| **Fundamentals** | Financial data collection | Tickers | Financial metrics |
| **ETF Data** | ETF metadata, holdings collection | ETF tickers | ETF details |
| **Market Adapters** | Region-specific API integration | Ticker, region | Raw data |

### 1.3 Data Source Matrix

| Data Type | KR | US | HK | JP | CN | VN |
|-----------|----|----|----|----|----|----|
| **Tickers** | pykrx, KIS | yfinance | yfinance, KIS | yfinance, KIS | yfinance, KIS | KIS |
| **OHLCV** | pykrx, KIS | yfinance | yfinance, KIS | yfinance, KIS | yfinance, KIS | KIS |
| **Fundamentals** | DART, pykrx | yfinance | yfinance | yfinance | yfinance | yfinance |
| **Sectors** | pykrx, KRX | yfinance | yfinance | yfinance | yfinance | yfinance |
| **ETF Details** | pykrx, etfcheck | yfinance | yfinance | yfinance | yfinance | yfinance |
| **ETF Holdings** | pykrx | yfinance | yfinance | yfinance | yfinance | yfinance |

---

## 2. Ticker Refresh System

### 2.1 Design Requirements

**Functional Requirements:**
- ✅ Discover all listed stocks and ETFs from each exchange
- ✅ Exclude OTC markets and unlisted securities
- ✅ Detect newly listed (IPOs) and delisted securities
- ✅ Update ticker metadata (name, sector, market cap)
- ✅ Handle ticker symbol changes and corporate actions

**Non-Functional Requirements:**
- Performance: <2 minutes for KR market, <5 minutes for all regions
- Accuracy: 99.9% ticker discovery rate
- Deduplication: Handle duplicate symbols across exchanges

### 2.2 Ticker Refresh Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Ticker Refresh Workflow                       │
└─────────────────────────────────────────────────────────────────┘

1. Fetch Active Tickers from Exchange
   │
   ├─► KR: pykrx.stock.get_market_ticker_list()
   ├─► US: yfinance screener or pre-defined list
   ├─► HK: yfinance + manual curated list
   ├─► JP: yfinance + manual curated list
   ├─► CN: yfinance + manual curated list
   └─► VN: KIS API + manual curated list
   │
   ▼
2. Validate & Filter
   │
   ├─► Exclude OTC markets (US: OTCBB, Pink Sheets)
   ├─► Exclude unlisted securities
   ├─► Validate ticker format (KR: 6-digit, US: 1-5 chars)
   └─► Check if ticker already exists in DB
   │
   ▼
3. Fetch Ticker Metadata
   │
   ├─► Name, exchange, currency
   ├─► Sector, industry (preliminary)
   ├─► Market cap, listing date
   └─► Asset type (stock vs ETF)
   │
   ▼
4. Insert or Update Database
   │
   ├─► New tickers: INSERT INTO tickers
   ├─► Existing tickers: UPDATE metadata
   ├─► Mark inactive: UPDATE is_active=FALSE for delisted
   └─► Log changes: INSERT INTO audit_log
   │
   ▼
5. Verify & Report
   │
   ├─► Count new/updated/delisted tickers
   ├─► Check for anomalies (>10% change in ticker count)
   └─► Generate summary report
```

### 2.3 Implementation Design

**Module**: `modules/ticker_refresh/ticker_refresher.py`

```python
class TickerRefresher:
    """
    Multi-region ticker refresh system

    Responsibilities:
    - Discover tickers from exchanges
    - Validate and filter tickers
    - Update tickers table
    - Track ticker lifecycle (new, active, delisted)
    """

    def __init__(self, db: PostgresDatabaseManager):
        self.db = db
        self.adapters = self._initialize_adapters()

    def refresh_region(self, region: str,
                       incremental: bool = True) -> Dict:
        """
        Refresh tickers for a specific region

        Args:
            region: Region code (KR, US, HK, JP, CN, VN)
            incremental: If True, only update changed tickers

        Returns:
            Dict with statistics (new, updated, delisted counts)
        """
        logger.info(f"Refreshing tickers for region: {region}")

        # 1. Fetch tickers from exchange
        live_tickers = self._fetch_live_tickers(region)
        logger.info(f"Fetched {len(live_tickers)} tickers from {region}")

        # 2. Validate and filter
        valid_tickers = self._validate_tickers(live_tickers, region)
        logger.info(f"Validated {len(valid_tickers)} tickers")

        # 3. Get existing tickers from DB
        existing_tickers = self._get_existing_tickers(region)

        # 4. Detect changes
        new_tickers = self._detect_new_tickers(valid_tickers, existing_tickers)
        updated_tickers = self._detect_updated_tickers(valid_tickers, existing_tickers)
        delisted_tickers = self._detect_delisted_tickers(valid_tickers, existing_tickers)

        # 5. Apply updates
        stats = {
            'new': self._insert_new_tickers(new_tickers, region),
            'updated': self._update_existing_tickers(updated_tickers, region),
            'delisted': self._mark_delisted_tickers(delisted_tickers, region),
            'total': len(valid_tickers)
        }

        logger.info(f"Ticker refresh complete: {stats}")
        return stats

    def _fetch_live_tickers(self, region: str) -> List[Dict]:
        """Fetch tickers from exchange using region adapter"""
        adapter = self.adapters[region]
        return adapter.get_all_tickers()

    def _validate_tickers(self, tickers: List[Dict],
                          region: str) -> List[Dict]:
        """
        Validate and filter tickers

        Rules:
        - Must have valid ticker symbol (format check)
        - Must be listed on main exchange (no OTC)
        - Must have basic metadata (name, exchange)
        """
        valid = []

        for ticker in tickers:
            # Validate ticker format
            if not self._is_valid_ticker_format(ticker['ticker'], region):
                continue

            # Exclude OTC markets
            if self._is_otc_market(ticker.get('exchange', '')):
                continue

            # Require basic metadata
            if not ticker.get('name'):
                logger.warning(f"Ticker {ticker['ticker']} missing name")
                continue

            valid.append(ticker)

        return valid

    def _is_valid_ticker_format(self, ticker: str, region: str) -> bool:
        """Validate ticker symbol format by region"""
        if region == 'KR':
            # KR: 6-digit code
            return ticker.isdigit() and len(ticker) == 6
        elif region == 'US':
            # US: 1-5 uppercase letters
            return ticker.isalpha() and 1 <= len(ticker) <= 5
        elif region in ['HK', 'JP', 'CN', 'VN']:
            # Asian markets: various formats
            return len(ticker) >= 4 and len(ticker) <= 10
        return False

    def _is_otc_market(self, exchange: str) -> bool:
        """Check if exchange is OTC market"""
        otc_exchanges = [
            'OTCBB', 'PINK', 'OTCQB', 'OTCQX',  # US OTC
            'OTC', 'Grey Market'
        ]
        return any(otc in exchange.upper() for otc in otc_exchanges)
```

### 2.4 Database Schema Updates

**No schema changes required** - existing `tickers` table supports all requirements:

```sql
-- Existing schema (already supports requirements)
CREATE TABLE tickers (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL,
    name VARCHAR(200),
    sector VARCHAR(100),
    industry VARCHAR(100),
    market_cap BIGINT,
    currency VARCHAR(3) DEFAULT 'USD',
    exchange VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    listed_date DATE,
    delisted_date DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_ticker_region UNIQUE (ticker, region)
);
```

---

## 3. OHLCV Update System

### 3.1 Design Requirements

**Functional Requirements:**
- ✅ Incremental update: Only fetch missing dates for each ticker
- ✅ Backfill NULL technical indicators (MA, RSI, MACD, Bollinger Bands)
- ✅ Handle corporate actions (splits, dividends) retroactively
- ✅ Support multiple timeframes (1d default, 1h/5m optional)
- ✅ Validate data quality (no gaps, outliers detection)

**Non-Functional Requirements:**
- Performance: <10 minutes for 1,000 tickers (incremental)
- Data Quality: 99% completeness, <0.1% outliers
- Storage: Efficient compression for historical data (TimescaleDB)

### 3.2 OHLCV Update Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    OHLCV Update Workflow                         │
└─────────────────────────────────────────────────────────────────┘

1. Determine Update Range
   │
   ├─► Get latest date for each ticker from ohlcv_data
   ├─► Calculate missing date range (last_date+1 to today)
   └─► Skip if already up-to-date (last_date = today)
   │
   ▼
2. Fetch OHLCV Data
   │
   ├─► KR: pykrx.stock.get_market_ohlcv() or KIS API
   ├─► US: yfinance.download(ticker, start, end)
   ├─► Other: yfinance or KIS API
   └─► Handle rate limits and retries
   │
   ▼
3. Data Quality Validation
   │
   ├─► Check for missing dates (weekends/holidays OK)
   ├─► Detect outliers (>20% daily change needs review)
   ├─► Verify OHLC relationships (high>=low, etc)
   └─► Flag suspicious data for manual review
   │
   ▼
4. Insert to Database
   │
   ├─► Batch insert (1000 records per transaction)
   ├─► Use UPSERT (ON CONFLICT UPDATE)
   ├─► Handle split adjustments
   └─► Update adj_close retroactively if needed
   │
   ▼
5. Calculate Technical Indicators
   │
   ├─► MA20, MA50, MA200
   ├─► RSI14
   ├─► MACD (12, 26, 9)
   ├─► Bollinger Bands (20, 2)
   └─► Volume moving averages
   │
   ▼
6. Backfill NULL Indicators
   │
   ├─► Find records with NULL indicator values
   ├─► Recalculate using pandas_ta
   ├─► Update technical_analysis table
   └─► Verify completeness
```

### 3.3 Implementation Design

**Module**: `modules/ohlcv_update/ohlcv_updater.py`

```python
class OHLCVUpdater:
    """
    Incremental OHLCV update and technical indicator backfill

    Responsibilities:
    - Fetch missing OHLCV data
    - Calculate technical indicators
    - Backfill NULL values
    - Validate data quality
    """

    def __init__(self, db: PostgresDatabaseManager):
        self.db = db
        self.adapters = self._initialize_adapters()

    def update_ticker(self, ticker: str, region: str,
                      backfill_indicators: bool = True) -> Dict:
        """
        Update OHLCV data for a single ticker

        Args:
            ticker: Ticker symbol
            region: Region code
            backfill_indicators: If True, backfill NULL technical indicators

        Returns:
            Dict with update statistics
        """
        logger.info(f"Updating OHLCV for {ticker} ({region})")

        # 1. Determine update range
        last_date = self._get_last_ohlcv_date(ticker, region)
        today = datetime.now().date()

        if last_date == today:
            logger.info(f"{ticker} already up-to-date")
            return {'status': 'up_to_date', 'records': 0}

        start_date = last_date + timedelta(days=1) if last_date else today - timedelta(days=365*5)

        logger.info(f"Fetching OHLCV from {start_date} to {today}")

        # 2. Fetch data
        adapter = self.adapters[region]
        ohlcv_data = adapter.get_ohlcv(ticker, start_date, today)

        if not ohlcv_data:
            logger.warning(f"No data returned for {ticker}")
            return {'status': 'no_data', 'records': 0}

        # 3. Validate data
        validated_data = self._validate_ohlcv(ohlcv_data, ticker)

        # 4. Insert to database
        inserted = self._insert_ohlcv_batch(validated_data, ticker, region)

        # 5. Calculate technical indicators
        if backfill_indicators:
            self._calculate_indicators(ticker, region)

        logger.info(f"Updated {inserted} OHLCV records for {ticker}")

        return {
            'status': 'success',
            'records': inserted,
            'date_range': (start_date, today)
        }

    def backfill_null_indicators(self, region: str = None) -> Dict:
        """
        Backfill NULL technical indicators for all tickers

        Args:
            region: If specified, only backfill for this region

        Returns:
            Dict with backfill statistics
        """
        logger.info(f"Starting indicator backfill (region={region})")

        # 1. Find tickers with NULL indicators
        query = """
            SELECT DISTINCT ticker, region
            FROM ohlcv_data
            WHERE (ma_20 IS NULL OR rsi_14 IS NULL OR macd IS NULL)
        """

        if region:
            query += f" AND region = '{region}'"

        tickers_to_backfill = self.db.fetch_all(query)

        logger.info(f"Found {len(tickers_to_backfill)} tickers with NULL indicators")

        # 2. Backfill each ticker
        backfilled = 0
        for ticker_info in tickers_to_backfill:
            try:
                self._calculate_indicators(
                    ticker_info['ticker'],
                    ticker_info['region']
                )
                backfilled += 1
            except Exception as e:
                logger.error(f"Failed to backfill {ticker_info['ticker']}: {e}")

        logger.info(f"Backfilled indicators for {backfilled} tickers")

        return {
            'status': 'success',
            'tickers_processed': backfilled,
            'total_tickers': len(tickers_to_backfill)
        }

    def _calculate_indicators(self, ticker: str, region: str):
        """
        Calculate technical indicators using pandas_ta

        Indicators:
        - MA20, MA50, MA200
        - RSI14
        - MACD (12, 26, 9)
        - Bollinger Bands (20, 2)
        """
        # Fetch OHLCV data
        query = """
            SELECT date, open, high, low, close, volume
            FROM ohlcv_data
            WHERE ticker = %s AND region = %s
            ORDER BY date ASC
        """

        df = pd.read_sql(query, self.db.get_connection(), params=(ticker, region))
        df.set_index('date', inplace=True)

        # Calculate indicators
        import pandas_ta as ta

        # Moving averages
        df['ma_20'] = ta.sma(df['close'], length=20)
        df['ma_50'] = ta.sma(df['close'], length=50)
        df['ma_200'] = ta.sma(df['close'], length=200)

        # RSI
        df['rsi_14'] = ta.rsi(df['close'], length=14)

        # MACD
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        df['macd'] = macd['MACD_12_26_9']
        df['macd_signal'] = macd['MACDs_12_26_9']
        df['macd_hist'] = macd['MACDh_12_26_9']

        # Bollinger Bands
        bbands = ta.bbands(df['close'], length=20, std=2)
        df['bb_upper'] = bbands['BBU_20_2.0']
        df['bb_middle'] = bbands['BBM_20_2.0']
        df['bb_lower'] = bbands['BBL_20_2.0']

        # Update database
        self._update_indicators_batch(df, ticker, region)
```

### 3.4 Technical Indicator Storage

**Option 1: Store in ohlcv_data table** (Recommended for simplicity)

```sql
-- Add columns to ohlcv_data (if not exists)
ALTER TABLE ohlcv_data ADD COLUMN IF NOT EXISTS ma_20 DECIMAL(15,4);
ALTER TABLE ohlcv_data ADD COLUMN IF NOT EXISTS ma_50 DECIMAL(15,4);
ALTER TABLE ohlcv_data ADD COLUMN IF NOT EXISTS ma_200 DECIMAL(15,4);
ALTER TABLE ohlcv_data ADD COLUMN IF NOT EXISTS rsi_14 DECIMAL(10,4);
ALTER TABLE ohlcv_data ADD COLUMN IF NOT EXISTS macd DECIMAL(15,4);
ALTER TABLE ohlcv_data ADD COLUMN IF NOT EXISTS macd_signal DECIMAL(15,4);
ALTER TABLE ohlcv_data ADD COLUMN IF NOT EXISTS bb_upper DECIMAL(15,4);
ALTER TABLE ohlcv_data ADD COLUMN IF NOT EXISTS bb_lower DECIMAL(15,4);
```

**Option 2: Use existing technical_analysis table** (For complex analysis)

Already exists - use for advanced indicators or GPT-based analysis.

---

## 4. Exchange Rate Tracking

### 4.1 Design Requirements

**Functional Requirements:**
- ✅ Track major currency pairs (USD, KRW, JPY, HKD, CNY, VND)
- ✅ Daily incremental updates (latest rate only)
- ✅ Support FX valuation signals (trend, momentum, volatility)
- ✅ Historical backfill for missing dates

**Non-Functional Requirements:**
- Performance: <30 seconds for all currency pairs
- Accuracy: Official exchange rates (central bank sources preferred)
- Latency: Updated by market open time (9:00 AM local)

### 4.2 Currency Pairs Matrix

| Base | Quote | Source | Update Frequency |
|------|-------|--------|------------------|
| USD | KRW | Alpha Vantage, KIS | Daily |
| USD | JPY | Alpha Vantage, KIS | Daily |
| USD | HKD | Alpha Vantage, yfinance | Daily |
| USD | CNY | Alpha Vantage, yfinance | Daily |
| USD | VND | Alpha Vantage, manual | Daily |
| KRW | USD | Derived (1/USD_KRW) | Daily |

### 4.3 FX Tracking Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                 Exchange Rate Tracking Workflow                  │
└─────────────────────────────────────────────────────────────────┘

1. Determine Required Currency Pairs
   │
   ├─► Base on regions being updated
   ├─► KR → USD/KRW
   ├─► JP → USD/JPY
   └─► All → USD as base currency
   │
   ▼
2. Check Latest Rate in DB
   │
   ├─► Query: SELECT MAX(rate_date) FROM exchange_rate_history
   ├─► If today's rate exists, skip
   └─► Otherwise, fetch latest rate
   │
   ▼
3. Fetch Latest Exchange Rate
   │
   ├─► Primary: Alpha Vantage FX API
   ├─► Fallback 1: yfinance (FX=X format)
   ├─► Fallback 2: KIS API (for KRW)
   └─► Fallback 3: Manual entry from xe.com
   │
   ▼
4. Validate Rate
   │
   ├─► Check vs previous rate (<5% daily change)
   ├─► Verify rate is not zero or negative
   └─► Flag anomalies for review
   │
   ▼
5. Insert to Database
   │
   ├─► INSERT INTO exchange_rate_history
   ├─► Calculate derived rates (e.g., KRW/USD = 1/USD_KRW)
   └─► Update fx_valuation_signals (if needed)
   │
   ▼
6. Calculate FX Valuation Signals (Optional)
   │
   ├─► 1M, 3M, 6M, 12M returns
   ├─► Trend score, volatility
   └─► Attractiveness score
```

### 4.4 Implementation Design

**Module**: `modules/fx_tracking/fx_tracker.py`

```python
class FXTracker:
    """
    Exchange rate tracking and valuation signals

    Responsibilities:
    - Fetch latest FX rates
    - Track historical rates
    - Calculate FX valuation signals
    """

    def __init__(self, db: PostgresDatabaseManager):
        self.db = db
        self.alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY')

    def update_fx_rates(self, currency_pairs: List[str] = None) -> Dict:
        """
        Update FX rates for specified currency pairs

        Args:
            currency_pairs: List of pairs like ['USD_KRW', 'USD_JPY']
                           If None, update all major pairs

        Returns:
            Dict with update statistics
        """
        if currency_pairs is None:
            currency_pairs = ['USD_KRW', 'USD_JPY', 'USD_HKD', 'USD_CNY', 'USD_VND']

        logger.info(f"Updating {len(currency_pairs)} currency pairs")

        updated = 0
        for pair in currency_pairs:
            try:
                # Check if today's rate already exists
                if self._has_todays_rate(pair):
                    logger.info(f"{pair} already up-to-date")
                    continue

                # Fetch latest rate
                rate_data = self._fetch_latest_rate(pair)

                # Insert to database
                self._insert_fx_rate(rate_data)

                updated += 1
                logger.info(f"Updated {pair}: {rate_data['rate']}")

            except Exception as e:
                logger.error(f"Failed to update {pair}: {e}")

        logger.info(f"Updated {updated}/{len(currency_pairs)} FX rates")

        return {
            'status': 'success',
            'updated': updated,
            'total': len(currency_pairs)
        }

    def _fetch_latest_rate(self, pair: str) -> Dict:
        """
        Fetch latest FX rate with fallback sources

        Priority:
        1. Alpha Vantage (best data quality)
        2. yfinance (FX=X format)
        3. KIS API (for KRW)
        """
        base, quote = pair.split('_')

        # Try Alpha Vantage
        if self.alpha_vantage_key:
            try:
                rate = self._fetch_from_alpha_vantage(base, quote)
                if rate:
                    return {
                        'currency': pair,
                        'rate': rate,
                        'rate_date': datetime.now().date(),
                        'source': 'alpha_vantage'
                    }
            except Exception as e:
                logger.warning(f"Alpha Vantage failed for {pair}: {e}")

        # Try yfinance
        try:
            rate = self._fetch_from_yfinance(base, quote)
            if rate:
                return {
                    'currency': pair,
                    'rate': rate,
                    'rate_date': datetime.now().date(),
                    'source': 'yfinance'
                }
        except Exception as e:
            logger.warning(f"yfinance failed for {pair}: {e}")

        # Last resort: raise error
        raise ValueError(f"Failed to fetch FX rate for {pair} from all sources")

    def _fetch_from_alpha_vantage(self, base: str, quote: str) -> float:
        """Fetch from Alpha Vantage FX API"""
        url = f"https://www.alphavantage.co/query"
        params = {
            'function': 'CURRENCY_EXCHANGE_RATE',
            'from_currency': base,
            'to_currency': quote,
            'apikey': self.alpha_vantage_key
        }

        response = requests.get(url, params=params)
        data = response.json()

        rate_str = data['Realtime Currency Exchange Rate']['5. Exchange Rate']
        return float(rate_str)

    def _fetch_from_yfinance(self, base: str, quote: str) -> float:
        """Fetch from yfinance (FX ticker format)"""
        import yfinance as yf

        # yfinance uses format like 'USDKRW=X'
        ticker_symbol = f"{base}{quote}=X"

        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info

        # Get current price
        rate = info.get('regularMarketPrice') or info.get('previousClose')

        if rate:
            return float(rate)

        raise ValueError(f"No rate found for {ticker_symbol}")
```

### 4.5 Database Schema

**Use existing `exchange_rate_history` table** - already supports all requirements.

**Optional Enhancement**: Add `fx_valuation_signals` for advanced analysis.

---

## 5. Stock Classification System

### 5.1 Design Requirements

**Functional Requirements:**
- ✅ Backfill sector, sector_code, industry, industry_code for all stocks
- ✅ Detect SPAC and preferred stocks automatically
- ✅ Skip par_value (keep NULL)
- ✅ Handle multi-region classification systems

**Non-Functional Requirements:**
- Coverage: 95%+ classification rate
- Accuracy: Manual verification for ambiguous cases
- Performance: <5 minutes for 10,000 stocks

### 5.2 Classification Sources by Region

| Region | Sector Classification | Industry Classification | SPAC Detection |
|--------|----------------------|------------------------|----------------|
| **KR** | pykrx (WICS), KRX API | pykrx (WICS), KRX API | Name pattern |
| **US** | yfinance (GICS) | yfinance (GICS) | Name pattern, SEC filings |
| **HK** | yfinance (GICS) | yfinance (GICS) | Name pattern |
| **JP** | yfinance (GICS) | yfinance (GICS) | Name pattern |
| **CN** | yfinance (GICS) | yfinance (GICS) | Name pattern |
| **VN** | Manual mapping | Manual mapping | Name pattern |

### 5.3 Classification Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│              Stock Classification Workflow                       │
└─────────────────────────────────────────────────────────────────┘

1. Find Stocks with Missing Classification
   │
   ├─► Query: SELECT ticker, region FROM stock_details
   │           WHERE sector IS NULL OR industry IS NULL
   └─► Prioritize active tickers (is_active=TRUE in tickers table)
   │
   ▼
2. Fetch Classification Data
   │
   ├─► KR: pykrx.stock.get_market_sector_classifications()
   ├─► US/Others: yfinance.Ticker(ticker).info['sector', 'industry']
   └─► Fallback: Manual curated mapping files
   │
   ▼
3. Detect SPAC and Preferred Stock
   │
   ├─► SPAC Detection:
   │   ├─► Name contains: "SPAC", "Acquisition Corp", "Acquisition Co"
   │   └─► Sector = "Shell Companies" (US SEC classification)
   │
   └─► Preferred Stock Detection:
       ├─► Ticker contains: 'P' suffix (US: "AAPL-P")
       ├─► Name contains: "우선주" (KR)
       └─► Is in preferred_stock_mapping table
   │
   ▼
4. Update Database
   │
   ├─► UPDATE stock_details SET
   │       sector = %s,
   │       sector_code = %s,
   │       industry = %s,
   │       industry_code = %s,
   │       is_spac = %s,
   │       is_preferred = %s
   │   WHERE ticker = %s AND region = %s
   │
   └─► Log updates to audit_log
   │
   ▼
5. Verify & Report
   │
   ├─► Count classified vs unclassified stocks
   ├─► Generate classification coverage report
   └─► Flag ambiguous cases for manual review
```

### 5.4 Implementation Design

**Module**: `modules/classification/stock_classifier.py`

```python
class StockClassifier:
    """
    Stock sector/industry classification and SPAC/preferred detection

    Responsibilities:
    - Fetch sector/industry from data sources
    - Detect SPAC and preferred stocks
    - Backfill stock_details table
    """

    def __init__(self, db: PostgresDatabaseManager):
        self.db = db
        self.adapters = self._initialize_adapters()
        self.spac_keywords = ['SPAC', 'Acquisition Corp', 'Acquisition Co', 'Acquisition Company']
        self.preferred_patterns = {
            'KR': ['우선주', '우선'],
            'US': ['-P', 'Pfd', 'Preferred']
        }

    def classify_stocks(self, region: str = None) -> Dict:
        """
        Classify stocks with missing sector/industry

        Args:
            region: If specified, only classify for this region

        Returns:
            Dict with classification statistics
        """
        logger.info(f"Starting stock classification (region={region})")

        # 1. Find stocks with missing classification
        unclassified = self._find_unclassified_stocks(region)
        logger.info(f"Found {len(unclassified)} unclassified stocks")

        # 2. Classify each stock
        classified = 0
        for stock in unclassified:
            try:
                classification = self._fetch_classification(
                    stock['ticker'],
                    stock['region']
                )

                # Update database
                self._update_classification(
                    stock['ticker'],
                    stock['region'],
                    classification
                )

                classified += 1

            except Exception as e:
                logger.error(f"Failed to classify {stock['ticker']}: {e}")

        logger.info(f"Classified {classified} stocks")

        return {
            'status': 'success',
            'classified': classified,
            'total': len(unclassified)
        }

    def _fetch_classification(self, ticker: str, region: str) -> Dict:
        """
        Fetch sector/industry classification

        Returns:
            Dict with keys: sector, sector_code, industry, industry_code,
                           is_spac, is_preferred
        """
        classification = {
            'sector': None,
            'sector_code': None,
            'industry': None,
            'industry_code': None,
            'is_spac': False,
            'is_preferred': False
        }

        # Fetch from region adapter
        adapter = self.adapters[region]

        if region == 'KR':
            # Use pykrx for KR stocks
            sector_data = adapter.get_sector_info(ticker)
            classification['sector'] = sector_data.get('sector')
            classification['sector_code'] = sector_data.get('sector_code')
            classification['industry'] = sector_data.get('industry')
            classification['industry_code'] = sector_data.get('industry_code')

        else:
            # Use yfinance for other regions
            import yfinance as yf
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info

            classification['sector'] = info.get('sector')
            classification['industry'] = info.get('industry')
            # Note: yfinance doesn't provide sector/industry codes

        # Detect SPAC
        classification['is_spac'] = self._is_spac(ticker, region, classification)

        # Detect preferred stock
        classification['is_preferred'] = self._is_preferred(ticker, region)

        return classification

    def _is_spac(self, ticker: str, region: str, classification: Dict) -> bool:
        """Detect if stock is a SPAC"""
        # Check name from tickers table
        query = "SELECT name FROM tickers WHERE ticker=%s AND region=%s"
        result = self.db.fetch_one(query, (ticker, region))

        if not result:
            return False

        name = result['name'].upper()

        # Check for SPAC keywords
        return any(keyword.upper() in name for keyword in self.spac_keywords)

    def _is_preferred(self, ticker: str, region: str) -> bool:
        """Detect if stock is a preferred stock"""
        # Check ticker symbol pattern
        patterns = self.preferred_patterns.get(region, [])

        for pattern in patterns:
            if pattern in ticker or pattern in ticker.upper():
                return True

        # Check name from tickers table
        query = "SELECT name FROM tickers WHERE ticker=%s AND region=%s"
        result = self.db.fetch_one(query, (ticker, region))

        if not result:
            return False

        name = result['name']

        # KR: Check for "우선주"
        if region == 'KR' and '우선주' in name:
            return True

        # US: Check for "Preferred" or "Pfd"
        if region == 'US' and ('Preferred' in name or 'Pfd' in name):
            return True

        return False
```

---

## 6. Fundamentals Update System

### 6.1 Design Requirements

**Functional Requirements:**
- ✅ Incremental updates: Only fetch latest fiscal periods
- ✅ Backfill historical data (5 years minimum)
- ✅ Support annual and quarterly financial statements
- ✅ Handle multi-region accounting standards (GAAP, IFRS, K-GAAP)

**Non-Functional Requirements:**
- Coverage: 90%+ for active stocks
- Accuracy: Match official filings (DART, SEC, etc.)
- Performance: <30 minutes for full regional update

### 6.2 Fundamentals Update Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│             Fundamentals Update Workflow                         │
└─────────────────────────────────────────────────────────────────┘

1. Determine Update Scope
   │
   ├─► Get active stock tickers from tickers table
   ├─► Check latest fiscal period in ticker_fundamentals
   └─► Calculate missing periods (e.g., 2024 Q3, Q4)
   │
   ▼
2. Fetch Financial Statements
   │
   ├─► KR: DART API (get_financial_statement)
   ├─► US: yfinance (financials, balance_sheet, cashflow)
   ├─► Others: yfinance or manual curated data
   └─► Handle rate limits (DART: 1 req/s)
   │
   ▼
3. Parse & Transform
   │
   ├─► Extract key metrics: revenue, net_income, assets, etc.
   ├─► Calculate derived metrics: ROE, margins, ratios
   ├─► Handle missing values (NULL if not available)
   └─► Normalize accounting standards (GAAP → IFRS mappings)
   │
   ▼
4. Validate Data
   │
   ├─► Check for illogical values (negative assets, etc.)
   ├─► Verify totals (assets = liabilities + equity)
   ├─► Flag anomalies (>50% YoY change needs review)
   └─► Compare with previous periods for consistency
   │
   ▼
5. Insert or Update Database
   │
   ├─► UPSERT: ON CONFLICT (ticker, region, date, period_type)
   │             DO UPDATE SET ...
   ├─► Batch insert (100 records per transaction)
   └─► Log updates to audit_log
   │
   ▼
6. Calculate Derived Metrics
   │
   ├─► FCF = Operating CF - CapEx
   ├─► FCF Yield = FCF / Market Cap
   ├─► EBITDA = Operating Profit + Depreciation
   └─► Update ticker_fundamentals with calculated values
```

### 6.3 Implementation Design

**Module**: `modules/fundamentals_update/fundamentals_updater.py`

```python
class FundamentalsUpdater:
    """
    Incremental fundamentals update and historical backfill

    Responsibilities:
    - Fetch financial statements
    - Calculate derived metrics
    - Backfill historical data
    - Validate data quality
    """

    def __init__(self, db: PostgresDatabaseManager):
        self.db = db
        self.dart_client = DartApiClient() if os.getenv('DART_API_KEY') else None

    def update_fundamentals(self, region: str,
                           period_type: str = 'ANNUAL',
                           backfill_years: int = 0) -> Dict:
        """
        Update fundamentals for a region

        Args:
            region: Region code
            period_type: 'ANNUAL' or 'QUARTERLY'
            backfill_years: Number of years to backfill (0 = incremental only)

        Returns:
            Dict with update statistics
        """
        logger.info(f"Updating {period_type} fundamentals for {region}")

        # 1. Get tickers to update
        tickers = self._get_active_tickers(region)
        logger.info(f"Processing {len(tickers)} tickers")

        updated = 0
        for ticker_info in tickers:
            try:
                # 2. Determine update range
                last_period = self._get_last_fundamental_period(
                    ticker_info['ticker'],
                    region,
                    period_type
                )

                # 3. Fetch fundamentals
                if region == 'KR' and self.dart_client:
                    fund_data = self._fetch_from_dart(
                        ticker_info['ticker'],
                        period_type,
                        last_period,
                        backfill_years
                    )
                else:
                    fund_data = self._fetch_from_yfinance(
                        ticker_info['ticker'],
                        period_type
                    )

                # 4. Insert to database
                if fund_data:
                    self._insert_fundamentals_batch(fund_data, ticker_info['ticker'], region)
                    updated += 1

            except Exception as e:
                logger.error(f"Failed to update {ticker_info['ticker']}: {e}")

        logger.info(f"Updated fundamentals for {updated} tickers")

        return {
            'status': 'success',
            'updated': updated,
            'total': len(tickers)
        }

    def _fetch_from_dart(self, ticker: str, period_type: str,
                        last_period: Optional[str],
                        backfill_years: int) -> List[Dict]:
        """Fetch from DART API"""
        # ... implementation using DartApiClient ...
        pass

    def _fetch_from_yfinance(self, ticker: str,
                            period_type: str) -> List[Dict]:
        """Fetch from yfinance"""
        import yfinance as yf

        ticker_obj = yf.Ticker(ticker)

        # Get financial statements
        if period_type == 'ANNUAL':
            financials = ticker_obj.financials  # Income statement
            balance_sheet = ticker_obj.balance_sheet
            cash_flow = ticker_obj.cashflow
        else:  # QUARTERLY
            financials = ticker_obj.quarterly_financials
            balance_sheet = ticker_obj.quarterly_balance_sheet
            cash_flow = ticker_obj.quarterly_cashflow

        # Transform to our schema
        fund_data = self._transform_yfinance_data(
            financials, balance_sheet, cash_flow
        )

        return fund_data
```

---

## 7. ETF Data System

### 7.1 Design Requirements

**Functional Requirements:**
- ✅ Update ETF metadata (AUM, expense ratio, holdings count)
- ✅ Backfill ETF holdings (top 10-50 constituents)
- ✅ Track tracking error and performance metrics
- ✅ Support regional ETF sources

**Non-Functional Requirements:**
- Coverage: 95%+ for major ETFs
- Freshness: Monthly update for holdings
- Performance: <10 minutes for 500 ETFs

### 7.2 ETF Data Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    ETF Data Workflow                             │
└─────────────────────────────────────────────────────────────────┘

1. Identify ETFs
   │
   ├─► Query tickers table WHERE is_etf=TRUE (need to add this column)
   ├─► Or: Maintain separate etf_list table
   └─► Prioritize ETFs with >$100M AUM or high volume
   │
   ▼
2. Fetch ETF Details
   │
   ├─► KR: pykrx, etfcheck.co.kr
   ├─► US: yfinance, ETF provider websites
   ├─► Others: yfinance
   │
   └─► Metadata:
       ├─► AUM, TER, inception_date
       ├─► Tracking index, fund type
       └─► Holdings count, liquidity
   │
   ▼
3. Fetch ETF Holdings
   │
   ├─► KR: pykrx.etf.get_etf_portfolio_deposit_file()
   ├─► US: yfinance.Ticker(etf).get_holdings() (limited to top 10)
   ├─► Fallback: ETF provider websites (web scraping)
   │
   └─► Holdings data:
       ├─► Constituent ticker
       ├─► Weight (%)
       └─► Shares held
   │
   ▼
4. Calculate Tracking Error
   │
   ├─► Fetch ETF daily returns
   ├─► Fetch benchmark index returns
   ├─► Calculate: std(etf_return - index_return)
   └─► Store in etf_details.tracking_error_*
   │
   ▼
5. Insert or Update Database
   │
   ├─► UPDATE etf_details SET ...
   ├─► DELETE FROM etf_holdings WHERE etf_ticker=...
   ├─► INSERT INTO etf_holdings (batch)
   └─► Log updates to audit_log
```

### 7.3 Implementation Design

**Module**: `modules/etf_update/etf_updater.py`

```python
class ETFUpdater:
    """
    ETF metadata and holdings update system

    Responsibilities:
    - Fetch ETF details (AUM, TER, etc.)
    - Update ETF holdings
    - Calculate tracking error
    """

    def __init__(self, db: PostgresDatabaseManager):
        self.db = db

    def update_etf_data(self, region: str,
                       update_holdings: bool = True) -> Dict:
        """
        Update ETF data for a region

        Args:
            region: Region code
            update_holdings: If True, also update holdings

        Returns:
            Dict with update statistics
        """
        logger.info(f"Updating ETF data for {region}")

        # 1. Get ETF list
        etfs = self._get_etf_list(region)
        logger.info(f"Found {len(etfs)} ETFs")

        updated_details = 0
        updated_holdings = 0

        for etf in etfs:
            try:
                # 2. Update ETF details
                details = self._fetch_etf_details(etf['ticker'], region)
                self._update_etf_details(etf['ticker'], region, details)
                updated_details += 1

                # 3. Update holdings
                if update_holdings:
                    holdings = self._fetch_etf_holdings(etf['ticker'], region)
                    if holdings:
                        self._update_etf_holdings(etf['ticker'], region, holdings)
                        updated_holdings += 1

            except Exception as e:
                logger.error(f"Failed to update ETF {etf['ticker']}: {e}")

        logger.info(f"Updated {updated_details} ETF details, {updated_holdings} holdings")

        return {
            'status': 'success',
            'details_updated': updated_details,
            'holdings_updated': updated_holdings,
            'total_etfs': len(etfs)
        }

    def _get_etf_list(self, region: str) -> List[Dict]:
        """Get list of ETFs for region"""
        # Option 1: Query from etf_details table
        query = """
            SELECT ticker FROM etf_details
            WHERE region = %s
        """
        return self.db.fetch_all(query, (region,))

    def _fetch_etf_details(self, ticker: str, region: str) -> Dict:
        """Fetch ETF metadata"""
        if region == 'KR':
            return self._fetch_kr_etf_details(ticker)
        else:
            return self._fetch_yfinance_etf_details(ticker)

    def _fetch_kr_etf_details(self, ticker: str) -> Dict:
        """Fetch KR ETF details from pykrx and etfcheck"""
        from pykrx import etf

        # Get basic info from pykrx
        etf_info = etf.get_etf_ohlcv_by_ticker(ticker, freq='d')

        # Get holdings count
        holdings = etf.get_etf_portfolio_deposit_file(ticker)

        return {
            'aum': None,  # Need to scrape from etfcheck.co.kr
            'listed_shares': None,
            'underlying_asset_count': len(holdings),
            'expense_ratio': None,  # Need to scrape
            'tracking_error_20d': None  # Calculate separately
        }

    def _fetch_etf_holdings(self, ticker: str, region: str) -> List[Dict]:
        """Fetch ETF holdings"""
        if region == 'KR':
            from pykrx import etf
            holdings_df = etf.get_etf_portfolio_deposit_file(ticker)

            # Transform to list of dicts
            holdings = []
            for idx, row in holdings_df.iterrows():
                holdings.append({
                    'constituent_ticker': row['ticker'],
                    'constituent_name': row['name'],
                    'weight': row['weight'],
                    'shares': row['shares']
                })
            return holdings
        else:
            # yfinance holdings (limited)
            import yfinance as yf
            ticker_obj = yf.Ticker(ticker)

            try:
                holdings_data = ticker_obj.get_holdings()
                # ... transform to our format ...
            except:
                logger.warning(f"No holdings available for {ticker}")
                return []
```

---

## 8. Data Flow Diagrams

### 8.1 Overall Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                   Overall Data Flow Diagram                      │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐
│ spock_refresh│
│    .py       │
└──────┬───────┘
       │
       │ 1. User selects mode (quick/full/incremental)
       ▼
┌──────────────────────────────────────────────────────────────────┐
│            DatabaseUpdateOrchestrator                            │
│                                                                  │
│  Execute Steps:                                                  │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ Step 1: Tickers    → TickerRefresher                       ││
│  │ Step 2: OHLCV      → OHLCVUpdater                          ││
│  │ Step 3: FX         → FXTracker                             ││
│  │ Step 4: Details    → StockClassifier                       ││
│  │ Step 5: Fundamtls  → FundamentalsUpdater                   ││
│  │ Step 6: ETF        → ETFUpdater                            ││
│  └────────────────────────────────────────────────────────────┘│
└──────────────────┬───────────────────────────────────────────────┘
                   │
                   │ Each step uses region-specific adapters
                   ▼
┌──────────────────────────────────────────────────────────────────┐
│              Regional Market Adapters                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ KRAdapter: pykrx + KIS API + DART                         │  │
│  │ USAdapter: yfinance + Alpha Vantage                       │  │
│  │ HKAdapter: yfinance + KIS API                             │  │
│  │ JPAdapter: yfinance + KIS API                             │  │
│  │ CNAdapter: yfinance                                       │  │
│  │ VNAdapter: KIS API                                        │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────┬───────────────────────────────────────────────┘
                   │
                   │ Raw data from external sources
                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                PostgreSQL + TimescaleDB                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Tables Updated:                                            │ │
│  │ • tickers (new/updated/delisted)                           │ │
│  │ • ohlcv_data (incremental + indicators)                    │ │
│  │ • exchange_rate_history (daily rates)                      │ │
│  │ • stock_details (sector/industry/SPAC/preferred)           │ │
│  │ • ticker_fundamentals (financial statements)               │ │
│  │ • etf_details, etf_holdings (ETF data)                     │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 8.2 Incremental Update Flow

```
For each table:

1. Determine Missing Data
   ├─► Query: SELECT MAX(date) FROM table WHERE ticker=...
   ├─► Calculate: missing_dates = [last_date+1 ... today]
   └─► Skip if up-to-date (last_date == today)

2. Fetch Missing Data
   ├─► Use region adapter
   ├─► Apply rate limiting
   └─► Handle errors (retry with exponential backoff)

3. Validate Data
   ├─► Check for outliers
   ├─► Verify completeness
   └─► Flag anomalies

4. Insert to Database
   ├─► Use UPSERT (ON CONFLICT UPDATE)
   ├─► Batch insert (1000 records)
   └─► Commit transaction

5. Update Checkpoint
   └─► Save progress (ticker, last_date, status)
```

---

## 9. Implementation Plan

### 9.1 Phase 1: Foundation (Week 1)

**Goal**: Enhance orchestrator and create base modules

**Tasks**:
1. ✅ **Orchestrator Enhancement** (Day 1-2)
   - Add new steps: `fx_tracking`, `stock_classification`, `etf_data`
   - Implement step-level retry logic
   - Add progress tracking UI

2. ✅ **Base Module Structure** (Day 2-3)
   - Create module directories
   - Implement base classes for each updater
   - Set up logging and error handling

3. ✅ **Database Schema Validation** (Day 3)
   - Verify all required tables exist
   - Add missing indexes
   - Test TimescaleDB compression

### 9.2 Phase 2: Core Implementations (Week 2-3)

**Goal**: Implement all 6 update systems

**Priority 1: Ticker + OHLCV** (Days 1-5)
- Implement `TickerRefresher`
- Implement `OHLCVUpdater`
- Test with KR region (3,700 tickers)

**Priority 2: FX + Stock Classification** (Days 6-10)
- Implement `FXTracker`
- Implement `StockClassifier`
- Test with all regions

**Priority 3: Fundamentals + ETF** (Days 11-15)
- Implement `FundamentalsUpdater`
- Implement `ETFUpdater`
- Test with KR + US regions

### 9.3 Phase 3: Integration & Testing (Week 4)

**Goal**: End-to-end testing and optimization

**Tasks**:
1. **Integration Testing** (Days 1-3)
   - Test full pipeline (all steps)
   - Test incremental mode
   - Test resume from checkpoint

2. **Performance Optimization** (Days 4-5)
   - Profile slow operations
   - Implement parallel processing
   - Optimize database queries

3. **Data Quality Validation** (Days 6-7)
   - Run comprehensive validation
   - Fix data quality issues
   - Document known limitations

### 9.4 Phase 4: Production Deployment (Week 5)

**Goal**: Deploy to production and monitor

**Tasks**:
1. **Production Setup** (Days 1-2)
   - Configure environment variables
   - Set up scheduled jobs (cron/launchd)
   - Enable monitoring (Prometheus/Grafana)

2. **Documentation** (Days 3-4)
   - User guide for spock_refresh.py
   - Troubleshooting guide
   - Data source documentation

3. **Monitoring & Support** (Day 5+)
   - Monitor first production runs
   - Fix issues as they arise
   - Gather user feedback

---

## 10. Success Criteria

### 10.1 Functional Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| **Ticker Coverage** | 99%+ | (Active tickers in DB) / (Exchange listings) |
| **OHLCV Completeness** | 98%+ | (Records with all OHLC) / (Total records) |
| **Indicator Backfill** | 95%+ | (Records with indicators) / (Total records) |
| **FX Rate Updates** | 100% | Daily updates for all currency pairs |
| **Sector Classification** | 95%+ | (Classified stocks) / (Total stocks) |
| **Fundamentals Coverage** | 90%+ | (Stocks with fundamentals) / (Active stocks) |
| **ETF Holdings** | 80%+ | (ETFs with holdings) / (Total ETFs) |

### 10.2 Performance Criteria

| Operation | Target Time | Max Time |
|-----------|-------------|----------|
| **Quick Refresh** | <5 min | 10 min |
| **Full Refresh (KR)** | <20 min | 30 min |
| **Full Refresh (All)** | <45 min | 60 min |
| **Incremental** | <10 min | 15 min |
| **Single Ticker Update** | <2 sec | 5 sec |

### 10.3 Quality Criteria

| Metric | Target | Threshold |
|--------|--------|-----------|
| **Data Accuracy** | >99% | >95% |
| **Uptime** | 99.9% | 99% |
| **Error Rate** | <0.1% | <1% |
| **Recovery Time** | <5 min | <15 min |

---

## 11. Risk Mitigation

### 11.1 Data Source Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **API Rate Limits** | High | Implement rate limiter, use multiple sources |
| **API Changes** | High | Version checking, graceful degradation |
| **API Downtime** | Medium | Fallback sources, retry logic |
| **Data Quality Issues** | Medium | Validation, anomaly detection |

### 11.2 Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Database Connection Loss** | High | Connection pooling, automatic reconnection |
| **Disk Space Exhaustion** | High | Monitoring, compression, retention policies |
| **Memory Leaks** | Medium | Batch processing, resource cleanup |
| **Long-Running Queries** | Medium | Query optimization, timeout limits |

---

## 12. Next Steps

**Immediate Actions** (Next 24 hours):
1. Review and approve this design document
2. Set up development environment
3. Create module directories and base files

**Short-term Actions** (Next 7 days):
1. Implement Phase 1 (Foundation)
2. Write unit tests for base classes
3. Begin Phase 2 implementation

**Long-term Actions** (Next 30 days):
1. Complete all phases
2. Deploy to production
3. Monitor and optimize

---

**Document Status**: ✅ Ready for Review
**Next Review Date**: 2025-11-05
**Approval Required From**: Spock Development Team
