# Multi-Market Filtering System Design (Global Expansion)

**Document Version**: 2.0 (Global Markets)
**Date**: 2025-10-04
**Author**: Spock Trading System
**Status**: Design Phase - Global Market Support

---

## 1. Executive Summary

### 1.1 Design Philosophy Change

**V1 (Korea Only)** → **V2 (Global Markets)**:
- Hard-coded Korean market thresholds → **Market-agnostic architecture**
- Single currency (KRW) → **Multi-currency support** (KRW, USD, HKD, CNY, JPY, VND)
- KOSPI/KOSDAQ only → **6 global markets** (KR, US, HK, CN, JP, VN)

### 1.2 Key Insight

**Only Stage 0 is market-dependent**:
- Stage 0: Market cap, trading value, price range → **Currency-specific**
- Stage 1: Technical indicators (MA, RSI, volume) → **Market-agnostic** ✅
- Stage 2: Pattern recognition, scoring → **Market-agnostic** ✅

**Design Implication**:
- Stage 0 requires market-specific configuration files
- Stage 1-2 can reuse existing logic without modification

---

## 2. Supported Markets

### 2.1 Market Overview

| Region | Exchanges | Currency | Trading Hours (KST) | Phase |
|--------|-----------|----------|---------------------|-------|
| 🇰🇷 Korea | KOSPI, KOSDAQ | KRW | 09:00-15:30 | **Phase 3** (Current) |
| 🇺🇸 United States | NYSE, NASDAQ, AMEX | USD | 22:30-05:00 (next day) | **Phase 4** (Priority) |
| 🇭🇰 Hong Kong | HKEX | HKD | 10:30-17:00 (lunch: 13:00-14:00) | Phase 5 |
| 🇨🇳 China | SSE, SZSE | CNY | 10:30-16:00 (lunch: 12:30-14:00) | Phase 5 |
| 🇯🇵 Japan | TSE | JPY | 09:00-15:00 (lunch: 11:30-12:30) | Phase 6 (Optional) |
| 🇻🇳 Vietnam | HOSE, HNX | VND | 11:00-17:00 (lunch: 13:30-15:00) | Phase 6 (Optional) |

### 2.2 Exchange Rate Management

**Currency Normalization Strategy**:
All thresholds are normalized to **KRW (Korean Won)** for cross-market comparison.

**Exchange Rate Sources**:
1. **Primary**: KIS API real-time rates
2. **Fallback**: Bank of Korea (한국은행) official rates
3. **Update Frequency**: Hourly during trading hours

**Example Conversions** (2025 rates):
```
USD/KRW: 1,300 → $1 = ₩1,300
HKD/KRW: 170 → HK$1 = ₩170
CNY/KRW: 180 → ¥1 = ₩180
JPY/KRW: 10 → ¥1 = ₩10
VND/KRW: 0.055 → ₫1 = ₩0.055
```

---

## 3. Market-Agnostic Architecture

### 3.1 Three-Stage Filtering with Market Adaptation

```
┌─────────────────────────────────────────────────────────┐
│ INPUT: All Listed Stocks (Multi-Market)                │
│ Sources:                                                │
│   - Korea: KRX Data API (~3,000)                        │
│   - US: IEX Cloud / Polygon.io (~8,000)                 │
│   - HK: HKEX API (~2,500)                               │
│   - CN: Stock Connect list (~2,000)                     │
│   - JP: TSE API (~3,800)                                │
│   - VN: HOSE/HNX API (~1,500)                           │
│ Total: ~20,000 tickers                                  │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ STAGE 0: Market-Specific Basic Filter                  │
│─────────────────────────────────────────────────────────│
│ Configuration: config/market_filters/{region}_config.yaml│
│                                                         │
│ Process:                                                │
│   1. Load market-specific config (min_market_cap, etc.) │
│   2. Fetch current price data from market API          │
│   3. Convert to KRW using real-time exchange rate      │
│   4. Apply market-specific filters                      │
│   5. Cache results with currency metadata              │
│                                                         │
│ Filters (Market-Specific):                             │
│   - Min Market Cap (local currency)                    │
│   - Min Trading Value (local currency)                 │
│   - Price Range (local currency)                       │
│   - Special Rules (admin stocks, penny stocks, etc.)   │
│                                                         │
│ Output:                                                 │
│   - Korea: ~600 tickers                                 │
│   - US: ~1,500 tickers                                  │
│   - HK: ~400 tickers                                    │
│   - CN: ~300 tickers                                    │
│   - JP: ~600 tickers                                    │
│   - VN: ~200 tickers                                    │
│ Total: ~3,600 tickers (82% reduction)                   │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ STAGE 1: Market-Agnostic Technical Pre-screen          │
│─────────────────────────────────────────────────────────│
│ Same logic for ALL markets ✅                           │
│                                                         │
│ Technical Filters (Universal):                         │
│   1. MA20 > MA60 (medium-term uptrend)                  │
│   2. Volume increase (recent 3d > past 10d avg)        │
│   3. Price ≥ 70% of 52-week high (strength)             │
│   4. RSI ∈ [30, 70] (avoid extremes)                    │
│   5. MA alignment: MA5 > MA20 > MA60                    │
│                                                         │
│ Why Market-Agnostic?                                   │
│   - Technical indicators are normalized (percentages)   │
│   - Price/volume ratios are dimensionless              │
│   - Trend patterns are universal across markets        │
│                                                         │
│ Output: ~1,200 tickers (67% reduction from Stage 0)    │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ STAGE 2: Market-Agnostic Deep Analysis                 │
│─────────────────────────────────────────────────────────│
│ Same logic for ALL markets ✅                           │
│                                                         │
│ Analysis Engine:                                        │
│   - LayeredScoringEngine (100-point system)             │
│   - Weinstein Stage Analysis                           │
│   - Pattern Recognition (Cup & Handle, VCP, etc.)       │
│   - Kelly Formula Position Sizing                       │
│                                                         │
│ Output:                                                 │
│   - BUY Candidates (≥70 points): ~150-200 tickers       │
│   - WATCH List (50-69 points): ~300-400 tickers         │
│   - Total: ~500 tickers (58% reduction from Stage 1)    │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Market-Specific Configurations

### 4.1 Configuration File Structure

**Location**: `config/market_filters/`

**Files**:
```
config/market_filters/
  ├─ kr_filter_config.yaml    # Korea (KOSPI/KOSDAQ)
  ├─ us_filter_config.yaml    # United States (NYSE/NASDAQ/AMEX)
  ├─ hk_filter_config.yaml    # Hong Kong (HKEX)
  ├─ cn_filter_config.yaml    # China (SSE/SZSE via Stock Connect)
  ├─ jp_filter_config.yaml    # Japan (TSE)
  └─ vn_filter_config.yaml    # Vietnam (HOSE/HNX)
```

### 4.2 Configuration Schema

**Example: `kr_filter_config.yaml`**
```yaml
# ===================================
# Korea Market Filter Configuration
# ===================================

region: KR
market_name: "Korea (KOSPI/KOSDAQ)"
currency: KRW

# Exchange Rate (KRW is base currency)
exchange_rate:
  source: "fixed"  # KRW는 기준 통화이므로 1.0 고정
  default_rate: 1.0
  update_frequency_minutes: 0  # No update needed

# Stage 0 Filters (기본 시장 필터)
stage0_filters:
  # Market Cap (시가총액)
  min_market_cap_local: 100_000_000_000  # 1,000억원 (100B KRW)
  min_market_cap_krw: 100_000_000_000    # Same as local

  # Trading Value (거래대금)
  min_trading_value_local: 10_000_000_000  # 100억원/일 (10B KRW)
  min_trading_value_krw: 10_000_000_000    # Same as local

  # Price Range (가격 범위)
  price_range_min_local: 5_000      # 5,000원
  price_range_max_local: 500_000    # 500,000원
  price_range_min_krw: 5_000
  price_range_max_krw: 500_000

  # Market-Specific Rules
  exclude_admin_stocks: true          # 관리종목 제외
  exclude_delisting: true             # 정리매매 제외
  exclude_etf: true                   # ETF 제외
  exclude_etn: true                   # ETN 제외
  exclude_spac: true                  # SPAC 제외
  exclude_preferred_stock: true       # 우선주 제외
  exclude_konex: true                 # KONEX 제외

# API Configuration
api:
  data_source: "KIS_API"
  endpoint_pattern: "/uapi/domestic-stock/v1/quotations/inquire-price"
  tr_id: "FHKST01010100"
  rate_limit_per_sec: 20
  rate_limit_per_min: 1000

# Cache Settings
cache:
  ttl_market_hours: 3600       # 1 hour (장중)
  ttl_after_hours: 86400       # 24 hours (장외)
  table_name: "filter_cache_stage0"

# Trading Hours (KST)
trading_hours:
  timezone: "Asia/Seoul"
  regular_session:
    start: "09:00"
    end: "15:30"
  has_lunch_break: false
  lunch_break: null

# Tick Size Rules
tick_size_rules:
  - price_max: 10000
    tick_size: 5
  - price_max: 50000
    tick_size: 10
  - price_max: 200000
    tick_size: 50
  - price_max: 500000
    tick_size: 100
  - price_max: null  # No limit
    tick_size: 1000
```

### 4.3 United States Configuration

**Example: `us_filter_config.yaml`**
```yaml
region: US
market_name: "United States (NYSE/NASDAQ/AMEX)"
currency: USD

# Exchange Rate (USD → KRW)
exchange_rate:
  source: "kis_api"  # KIS API real-time rate
  default_rate: 1300  # Fallback: $1 = ₩1,300
  update_frequency_minutes: 60

# Stage 0 Filters
stage0_filters:
  # Market Cap
  min_market_cap_local: 100_000_000  # $100M (미국 소형주 기준)
  min_market_cap_krw: 130_000_000_000  # ₩130B (at 1,300 rate)

  # Trading Value
  min_trading_value_local: 10_000_000  # $10M/day
  min_trading_value_krw: 13_000_000_000  # ₩13B

  # Price Range
  price_range_min_local: 5.0      # $5 (penny stock 제외)
  price_range_max_local: 1000.0   # $1,000 (고가주 제한)
  price_range_min_krw: 6_500
  price_range_max_krw: 1_300_000

  # US-Specific Rules
  exclude_penny_stocks: true      # < $1 제외
  exclude_otc: true               # OTC 시장 제외
  exclude_pink_sheets: true       # Pink sheets 제외
  exclude_etf: true
  exclude_etn: true
  min_average_volume_3m: 500_000  # 3개월 평균 거래량 50만주

# API Configuration
api:
  data_source: "KIS_OVERSEAS_API"
  endpoint_pattern: "/uapi/overseas-stock/v1/quotations/price"
  tr_id: "HHDFS00000300"  # 해외주식 현재가
  rate_limit_per_sec: 20

# Trading Hours (KST, Summer Time)
trading_hours:
  timezone: "America/New_York"
  regular_session:
    start: "22:30"  # 09:30 EST = 22:30 KST (Summer)
    end: "05:00"    # 16:00 EST = 05:00 KST (next day)
  has_lunch_break: false
  daylight_saving: true
  winter_offset_hours: 1  # Winter: 23:30-06:00 KST

# Tick Size Rules
tick_size_rules:
  - price_max: 1.0
    tick_size: 0.0001  # Sub-penny for < $1
  - price_max: null
    tick_size: 0.01    # $0.01 for ≥ $1
```

### 4.4 Other Markets (Brief)

**Hong Kong (`hk_filter_config.yaml`)**:
- min_market_cap: HK$1B (≈ ₩170B)
- min_trading_value: HK$100M/day
- price_range: HK$1 ~ HK$500
- Special: Focus on Hang Seng Index constituents

**China (`cn_filter_config.yaml`)**:
- min_market_cap: ¥1B (≈ ₩180B)
- min_trading_value: ¥100M/day
- price_range: ¥5 ~ ¥300
- Special: **Stock Connect eligible only** (외국인 거래 가능)

**Japan (`jp_filter_config.yaml`)**:
- min_market_cap: ¥10B (≈ ₩100B)
- min_trading_value: ¥1B/day
- price_range: ¥500 ~ ¥10,000
- Special: TOPIX 500 우선 선택

**Vietnam (`vn_filter_config.yaml`)**:
- min_market_cap: ₫1T (≈ ₩55B)
- min_trading_value: ₫100B/day
- price_range: ₫10,000 ~ ₫200,000
- Special: VN30 Index 우선 선택

---

## 5. Database Schema (Multi-Market)

### 5.1 Updated Schema: filter_cache_stage0

**Key Changes from V1**:
- Add `region` to PRIMARY KEY (composite key)
- Add currency normalization fields (`*_krw`, `*_local`)
- Add exchange rate tracking

```sql
CREATE TABLE IF NOT EXISTS filter_cache_stage0 (
    -- Composite Primary Key (multi-market support)
    ticker TEXT NOT NULL,
    region TEXT NOT NULL,  -- 'KR', 'US', 'HK', 'CN', 'JP', 'VN'

    -- Basic Info
    name TEXT NOT NULL,
    exchange TEXT,  -- 'KOSPI', 'NASDAQ', 'HKEX', etc.

    -- Currency Normalization (KRW as base)
    market_cap_krw BIGINT,          -- Normalized to KRW
    trading_value_krw BIGINT,       -- Normalized to KRW
    current_price_krw INTEGER,      -- Normalized to KRW

    -- Original Values (Local Currency)
    market_cap_local REAL,          -- Original value
    trading_value_local REAL,       -- Original value
    current_price_local REAL,       -- Original value
    currency TEXT NOT NULL,         -- 'KRW', 'USD', 'HKD', 'CNY', 'JPY', 'VND'

    -- Exchange Rate Metadata
    exchange_rate_to_krw REAL,      -- Conversion rate used
    exchange_rate_date DATE,        -- Rate timestamp
    exchange_rate_source TEXT,      -- 'kis_api', 'bok', 'fixed'

    -- Market-Specific Fields
    market_warn_code TEXT,          -- Korea: 관리종목 코드
    is_stock_connect BOOLEAN,       -- China: Stock Connect 여부
    is_otc BOOLEAN,                 -- US: OTC market 여부
    is_delisting BOOLEAN,           -- All: 상장폐지 예정 여부

    -- Filter Result
    filter_date DATE NOT NULL,
    stage0_passed BOOLEAN DEFAULT TRUE,
    filter_reason TEXT,             -- If failed, reason

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Composite Primary Key
    PRIMARY KEY (ticker, region),

    -- Foreign Key to tickers table
    FOREIGN KEY (ticker, region) REFERENCES tickers(ticker, region)
);

-- Indexes for Performance
CREATE INDEX idx_stage0_region_date ON filter_cache_stage0(region, filter_date);
CREATE INDEX idx_stage0_passed ON filter_cache_stage0(stage0_passed);
CREATE INDEX idx_stage0_market_cap_krw ON filter_cache_stage0(market_cap_krw DESC);
CREATE INDEX idx_stage0_currency ON filter_cache_stage0(currency);
```

### 5.2 Updated Schema: filter_cache_stage1

```sql
CREATE TABLE IF NOT EXISTS filter_cache_stage1 (
    -- Composite Primary Key
    ticker TEXT NOT NULL,
    region TEXT NOT NULL,

    -- Stage 1 Technical Data (market-agnostic)
    ma5 REAL,
    ma20 REAL,
    ma60 REAL,
    rsi_14 REAL,
    current_price_krw INTEGER,  -- Always in KRW for comparison
    week_52_high_krw INTEGER,
    volume_3d_avg BIGINT,
    volume_10d_avg BIGINT,

    -- Data Window
    filter_date DATE NOT NULL,
    data_start_date DATE,
    data_end_date DATE,

    -- Filter Result
    stage1_passed BOOLEAN DEFAULT TRUE,
    filter_reason TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (ticker, region),
    FOREIGN KEY (ticker, region) REFERENCES filter_cache_stage0(ticker, region)
);

CREATE INDEX idx_stage1_region_date ON filter_cache_stage1(region, filter_date);
CREATE INDEX idx_stage1_passed ON filter_cache_stage1(stage1_passed);
```

### 5.3 Updated Schema: filter_execution_log

```sql
CREATE TABLE IF NOT EXISTS filter_execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    execution_date DATE NOT NULL,
    region TEXT NOT NULL,  -- Track per market
    stage INTEGER NOT NULL,  -- 0, 1, 2

    input_count INTEGER,
    output_count INTEGER,
    reduction_rate REAL,

    execution_time_sec REAL,
    api_calls INTEGER,
    error_count INTEGER,

    -- Currency tracking
    total_market_cap_krw BIGINT,  -- Sum of filtered stocks
    avg_trading_value_krw BIGINT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_execution_log_date_region ON filter_execution_log(execution_date, region);
```

---

## 6. Implementation: Market Filter Manager

### 6.1 MarketFilterManager Class

**File**: `modules/market_filter_manager.py`

```python
"""
Market Filter Manager - Multi-Market Configuration Loader

Handles:
1. Loading market-specific filter configs
2. Currency conversion to KRW
3. Threshold normalization
4. Market-specific rule application
"""

import yaml
import logging
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class MarketFilterConfig:
    """Market-specific filter configuration"""

    def __init__(self, config_path: str):
        """
        Load market configuration from YAML file

        Args:
            config_path: Path to market config YAML (e.g., 'config/market_filters/kr_filter_config.yaml')
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.region = self.config['region']
        self.currency = self.config['currency']
        self.exchange_rate = self.config['exchange_rate']['default_rate']

    def get_min_market_cap_krw(self) -> int:
        """Get minimum market cap threshold in KRW"""
        return self.config['stage0_filters']['min_market_cap_krw']

    def get_min_trading_value_krw(self) -> int:
        """Get minimum trading value threshold in KRW"""
        return self.config['stage0_filters']['min_trading_value_krw']

    def get_price_range_krw(self) -> tuple:
        """Get price range (min, max) in KRW"""
        return (
            self.config['stage0_filters']['price_range_min_krw'],
            self.config['stage0_filters']['price_range_max_krw']
        )

    def convert_to_krw(self, value_local: float) -> int:
        """
        Convert local currency value to KRW

        Args:
            value_local: Value in local currency

        Returns:
            Value in KRW (integer)
        """
        return int(value_local * self.exchange_rate)

    def should_exclude_ticker(self, ticker_data: Dict) -> tuple:
        """
        Check if ticker should be excluded based on market-specific rules

        Args:
            ticker_data: Ticker metadata dictionary

        Returns:
            (should_exclude: bool, reason: str)
        """
        filters = self.config['stage0_filters']

        # Korea-specific: Admin stocks
        if self.region == 'KR' and filters.get('exclude_admin_stocks'):
            if ticker_data.get('market_warn_code', '00') != '00':
                return True, 'admin_stock'

        # US-specific: Penny stocks
        if self.region == 'US' and filters.get('exclude_penny_stocks'):
            if ticker_data.get('price_local', 0) < 1.0:
                return True, 'penny_stock'

        # China-specific: Non-Stock Connect
        if self.region == 'CN' and filters.get('stock_connect_only'):
            if not ticker_data.get('is_stock_connect', False):
                return True, 'not_stock_connect'

        # Common: ETF/ETN exclusion
        asset_type = ticker_data.get('asset_type', 'STOCK')
        if filters.get('exclude_etf') and asset_type == 'ETF':
            return True, 'etf'
        if filters.get('exclude_etn') and asset_type == 'ETN':
            return True, 'etn'

        return False, ''


class MarketFilterManager:
    """Manages multi-market filter configurations"""

    def __init__(self, config_dir: str = 'config/market_filters'):
        """
        Initialize MarketFilterManager

        Args:
            config_dir: Directory containing market config YAML files
        """
        self.config_dir = Path(config_dir)
        self.configs: Dict[str, MarketFilterConfig] = {}

        # Load all available market configs
        self._load_all_configs()

    def _load_all_configs(self):
        """Load all market configuration files"""
        if not self.config_dir.exists():
            logger.warning(f"Config directory not found: {self.config_dir}")
            return

        for config_file in self.config_dir.glob('*_filter_config.yaml'):
            try:
                config = MarketFilterConfig(str(config_file))
                self.configs[config.region] = config
                logger.info(f"✅ Loaded config for {config.region} market")
            except Exception as e:
                logger.error(f"❌ Failed to load {config_file}: {e}")

    def get_config(self, region: str) -> Optional[MarketFilterConfig]:
        """
        Get filter configuration for specific market

        Args:
            region: Market region code ('KR', 'US', 'HK', 'CN', 'JP', 'VN')

        Returns:
            MarketFilterConfig instance or None if not found
        """
        return self.configs.get(region)

    def get_supported_regions(self) -> List[str]:
        """Get list of supported market regions"""
        return list(self.configs.keys())

    def apply_stage0_filter(self, region: str, ticker_data: Dict) -> tuple:
        """
        Apply Stage 0 filter for specific market

        Args:
            region: Market region code
            ticker_data: Ticker data with local currency values

        Returns:
            (passed: bool, reason: str, normalized_data: Dict)
        """
        config = self.get_config(region)
        if not config:
            return False, f'no_config_for_{region}', {}

        # Convert to KRW for threshold comparison
        market_cap_krw = config.convert_to_krw(ticker_data.get('market_cap_local', 0))
        trading_value_krw = config.convert_to_krw(ticker_data.get('trading_value_local', 0))
        price_krw = config.convert_to_krw(ticker_data.get('price_local', 0))

        # Check thresholds
        if market_cap_krw < config.get_min_market_cap_krw():
            return False, 'market_cap_too_low', {}

        if trading_value_krw < config.get_min_trading_value_krw():
            return False, 'trading_value_too_low', {}

        price_min, price_max = config.get_price_range_krw()
        if price_krw < price_min or price_krw > price_max:
            return False, 'price_out_of_range', {}

        # Market-specific exclusions
        should_exclude, exclude_reason = config.should_exclude_ticker(ticker_data)
        if should_exclude:
            return False, exclude_reason, {}

        # Passed - return normalized data
        normalized_data = {
            'market_cap_krw': market_cap_krw,
            'trading_value_krw': trading_value_krw,
            'current_price_krw': price_krw,
            'exchange_rate': config.exchange_rate,
            'currency': config.currency
        }

        return True, '', normalized_data
```

---

## 7. Implementation Plan (Revised)

### 7.1 Phase-Based Rollout

**Phase 3 (Current - Week 1-5)**:
- ✅ Implement Korea market (Stage 0-2)
- ✅ Create `kr_filter_config.yaml`
- ✅ Test with KOSPI/KOSDAQ data
- **Deliverable**: Korea market fully functional

**Phase 4 (Week 6-10)**:
- ⏳ Add `us_filter_config.yaml`
- ⏳ Integrate KIS Overseas Stock API
- ⏳ Test with US stocks (NYSE/NASDAQ)
- **Deliverable**: US market operational

**Phase 5 (Week 11-15)**:
- ⏳ Add `hk_filter_config.yaml`, `cn_filter_config.yaml`
- ⏳ Integrate HKEX API, Stock Connect data
- **Deliverable**: Hong Kong/China markets operational

**Phase 6 (Optional - Week 16-20)**:
- ⏳ Add `jp_filter_config.yaml`, `vn_filter_config.yaml`
- ⏳ Integrate TSE API, HOSE/HNX data
- **Deliverable**: Japan/Vietnam markets operational

### 7.2 Development Tasks (Phase 3 - Korea Only)

#### **Task 1: Create Configuration System** (Priority: P0)
- [ ] Create `config/market_filters/` directory
- [ ] Implement `MarketFilterConfig` class
- [ ] Implement `MarketFilterManager` class
- [ ] Create `kr_filter_config.yaml`
- **Estimated Time**: 3 hours

#### **Task 2: Update Database Schema** (Priority: P0)
- [ ] Create migration `003_add_multi_market_support.py`
- [ ] Update `filter_cache_stage0` with region, currency fields
- [ ] Update `filter_cache_stage1` with composite key
- [ ] Run migration and verify
- **Estimated Time**: 2 hours

#### **Task 3: Enhance scanner.py** (Priority: P0)
- [ ] Integrate `MarketFilterManager`
- [ ] Update `apply_stage0_filter()` to use config
- [ ] Add currency normalization logic
- [ ] Update cache operations for multi-market
- **Estimated Time**: 4 hours

#### **Task 4: Create stock_pre_filter.py** (Priority: P0)
- [ ] Implement `StockPreFilter` class (market-agnostic)
- [ ] Stage 1 filter logic (no changes needed)
- [ ] Update to use `filter_cache_stage1` new schema
- **Estimated Time**: 3 hours

#### **Task 5: Testing** (Priority: P1)
- [ ] Unit tests for `MarketFilterManager`
- [ ] Integration test: Korea market end-to-end
- [ ] Validate currency normalization accuracy
- **Estimated Time**: 3 hours

**Total Estimated Time**: **15 hours** (~2 working days)

---

## 8. Performance Expectations (Global Scale)

### 8.1 Multi-Market Throughput

| Market | Input | Stage 0 Output | Stage 1 Output | BUY Candidates | Total Time |
|--------|-------|----------------|----------------|----------------|------------|
| Korea | 3,000 | 600 | 250 | 30-50 | ~50s |
| US | 8,000 | 1,500 | 600 | 80-100 | ~2min |
| HK | 2,500 | 400 | 150 | 20-30 | ~40s |
| CN | 2,000 | 300 | 120 | 15-25 | ~30s |
| JP | 3,800 | 600 | 240 | 30-40 | ~50s |
| VN | 1,500 | 200 | 80 | 10-15 | ~25s |
| **TOTAL** | **20,800** | **3,600** | **1,440** | **185-260** | **~5min** |

### 8.2 Comparison: Single-Market vs Multi-Market

| Metric | Korea Only (V1) | Global (V2) | Scaling Factor |
|--------|----------------|-------------|----------------|
| Input Tickers | 3,000 | 20,800 | **7x** |
| BUY Candidates | 30-50 | 185-260 | **~6x** |
| Total Time | 50s | 5min | **6x** |
| API Calls | 850 | 5,800 | **~7x** |
| Storage | ~100MB | ~700MB | **7x** |

**Key Insight**: System scales **linearly** with market addition 🎯

---

## 9. Future Enhancements

### 9.1 Dynamic Threshold Adjustment

**Adaptive Filtering**: Adjust thresholds based on market conditions
- Bull market: Tighten filters (higher thresholds)
- Bear market: Loosen filters (more opportunities)
- Volatility spike: Increase min trading value

### 9.2 Cross-Market Arbitrage Detection

**Dual-Listed Stocks**: Compare prices across markets
- Example: Samsung Electronics (005930.KS) vs Samsung ADR (SSNLF.US)
- Example: Alibaba (BABA.US vs 9988.HK)

### 9.3 Sector-Specific Filters

**Industry Thresholds**: Different filters per sector
- Tech stocks: Higher growth, lower profitability requirements
- Financials: Higher liquidity, lower volatility
- Utilities: Lower growth, higher dividend yield

---

## 10. Appendix

### 10.1 Market Comparison Table

| Feature | Korea | US | Hong Kong | China | Japan | Vietnam |
|---------|-------|----|-----------| ------|-------|---------|
| **Tickers** | 3,000 | 8,000 | 2,500 | 2,000 | 3,800 | 1,500 |
| **Currency** | KRW | USD | HKD | CNY | JPY | VND |
| **Tick Size** | Variable | $0.01 | Variable | ¥0.01 | Variable | Variable |
| **Settlement** | T+2 | T+2 | T+2 | T+0 | T+2 | T+2 |
| **Trading Fee** | 0.015% | 0.25% | 0.25% | 0.25% | 0.25% | 0.30% |
| **Tax (Korean)** | 0% | 22% | 22% | 22% | 22% | 22% |
| **Lunch Break** | No | No | Yes | Yes | Yes | Yes |
| **Data Source** | KIS Domestic | KIS Overseas | KIS Overseas | KIS Overseas | KIS Overseas | KIS Overseas |

### 10.2 Configuration File Template

**Template: `_template_filter_config.yaml`**
```yaml
region: XX  # 2-letter code
market_name: "Market Name"
currency: XXX  # 3-letter ISO code

exchange_rate:
  source: "kis_api" | "fixed"
  default_rate: 1.0
  update_frequency_minutes: 60

stage0_filters:
  min_market_cap_local: 0
  min_market_cap_krw: 0
  min_trading_value_local: 0
  min_trading_value_krw: 0
  price_range_min_local: 0
  price_range_max_local: 0
  price_range_min_krw: 0
  price_range_max_krw: 0

  # Market-specific booleans
  exclude_admin_stocks: false
  exclude_delisting: true
  exclude_etf: true
  exclude_etn: true
  exclude_otc: false
  exclude_penny_stocks: false

api:
  data_source: "KIS_API"
  endpoint_pattern: "/uapi/..."
  tr_id: "XXXXXXXXXX"
  rate_limit_per_sec: 20

cache:
  ttl_market_hours: 3600
  ttl_after_hours: 86400

trading_hours:
  timezone: "Region/City"
  regular_session:
    start: "HH:MM"
    end: "HH:MM"
  has_lunch_break: false
```

---

**End of Document**
