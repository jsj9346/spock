# Spock Global Market Expansion Architecture

## Executive Summary

This document extends the Spock trading system to support **global stock markets** beyond Korea, enabling access to world-class companies and ETFs across major exchanges. The system will support all markets accessible through KIS (Korea Investment & Securities) API, implementing market-specific regulations, timezone handling, and unified portfolio management.

**Supported Markets**:
- 🇰🇷 Korea: KOSPI, KOSDAQ
- 🇺🇸 United States: NYSE, NASDAQ, AMEX
- 🇭🇰 Hong Kong: HKEX
- 🇨🇳 China: Shanghai Stock Exchange (SSE), Shenzhen Stock Exchange (SZSE)
- 🇯🇵 Japan: Tokyo Stock Exchange (TSE)
- 🇻🇳 Vietnam: Ho Chi Minh Stock Exchange (HOSE), Hanoi Stock Exchange (HNX)

**Key Benefits**:
- Access to global blue-chip stocks (Apple, Microsoft, Alibaba, Toyota, etc.)
- Diversification across markets and currencies
- World-class ETFs (SPY, QQQ, VTI, etc.)
- 24-hour trading capability (US night session + Asia day session)
- Currency diversification (KRW, USD, HKD, CNY, JPY, VND)

**Strategic Approach**:
- Phase 1-3: Complete Korea market system (baseline)
- Phase 4: Add US market (highest priority)
- Phase 5: Add Hong Kong/China markets
- Phase 6: Add Japan/Vietnam markets (optional)

---

## 1. Global Market Overview

### 1.1 Supported Markets & Trading Hours

**Trading Hours (Korea Time - KST)**

| Market | Exchange | Trading Hours (KST) | Lunch Break | Currency |
|--------|----------|---------------------|-------------|----------|
| 🇰🇷 Korea | KOSPI/KOSDAQ | 09:00-15:30 | None | KRW |
| 🇯🇵 Japan | TSE | 09:00-11:30, 12:30-15:00 | 11:30-12:30 | JPY |
| 🇭🇰 Hong Kong | HKEX | 10:30-13:00, 14:00-17:00 | 13:00-14:00 | HKD |
| 🇨🇳 China | SSE/SZSE | 10:30-12:30, 14:00-16:00 | 12:30-14:00 | CNY |
| 🇻🇳 Vietnam | HOSE/HNX | 11:00-13:30, 15:00-17:00 | 13:30-15:00 | VND |
| 🇺🇸 US (Summer) | NYSE/NASDAQ | 22:30-05:00 (next day) | None | USD |
| 🇺🇸 US (Winter) | NYSE/NASDAQ | 23:30-06:00 (next day) | None | USD |

**24-Hour Operating Model**:
```
KST Time    Market Activity
────────────────────────────────────────────────
08:00-09:00  Asia Pre-Market (KR, JP preparation)
09:00-16:00  Asia Intraday (KR, JP, HK, CN, VN)
16:00-22:00  Asia Post-Market + US Pre-Market
22:30-06:00  US Intraday (Summer) / 23:30-06:00 (Winter)
06:00-08:00  US Post-Market + Global Analysis
```

---

### 1.2 Market-Specific Regulations

#### 1.2.1 Tick Size Rules

**Korea (KOSPI/KOSDAQ)**
| Price Range | Tick Size |
|-------------|-----------|
| < 10,000 KRW | 5 KRW |
| 10,000 - 50,000 | 10 KRW |
| 50,000 - 200,000 | 50 KRW |
| 200,000 - 500,000 | 100 KRW |
| ≥ 500,000 | 1,000 KRW |

**United States (NYSE/NASDAQ)**
| Price Range | Tick Size |
|-------------|-----------|
| < $1 | $0.0001 (sub-penny) |
| ≥ $1 | $0.01 |

**Hong Kong (HKEX)**
| Price Range | Tick Size |
|-------------|-----------|
| < 0.25 HKD | 0.001 HKD |
| 0.25 - 0.50 | 0.005 HKD |
| 0.50 - 10 | 0.01 HKD |
| 10 - 20 | 0.02 HKD |
| 20 - 100 | 0.05 HKD |
| 100 - 200 | 0.10 HKD |
| 200 - 500 | 0.20 HKD |
| 500 - 1,000 | 0.50 HKD |
| ≥ 1,000 | 1.00 HKD |

**Japan (TSE)**
| Price Range | Tick Size |
|-------------|-----------|
| < 1,000 JPY | 1 JPY |
| 1,000 - 3,000 | 1 JPY |
| 3,000 - 5,000 | 5 JPY |
| 5,000 - 10,000 | 10 JPY |
| 10,000 - 30,000 | 10 JPY |
| ≥ 30,000 | 100 JPY |

**China (SSE/SZSE)**
| Price Range | Tick Size |
|-------------|-----------|
| All prices | 0.01 CNY |

**Vietnam (HOSE/HNX)**
| Price Range | Tick Size |
|-------------|-----------|
| < 50,000 VND | 10 VND |
| ≥ 50,000 | 50 VND |

---

#### 1.2.2 Transaction Costs

**Korea (Domestic)**
- Trading Fee: 0.015% (online)
- Securities Transaction Tax: 0.23% (sell only, KOSPI), 0.15% (KOSDAQ sell)
- Settlement: T+2

**United States (Overseas)**
- Trading Fee: 0.25% (KIS overseas trading)
- SEC Fee: ~$0.000008 per dollar (negligible)
- Exchange Fee: Varies by exchange
- Currency Conversion: KRW ↔ USD (spread ~0.5%)
- Settlement: T+2

**Hong Kong (Overseas)**
- Trading Fee: 0.25-0.30%
- Stamp Duty: 0.1% (both buy and sell)
- Transaction Levy: 0.0027%
- Currency Conversion: KRW ↔ HKD
- Settlement: T+2

**China (Stock Connect)**
- Trading Fee: 0.25-0.30%
- Stamp Duty: 0.1% (sell only)
- Currency Conversion: KRW ↔ CNY
- Settlement: T+0 (same day)

**Japan (Overseas)**
- Trading Fee: 0.25-0.30%
- Consumption Tax: 10% on trading fee
- Currency Conversion: KRW ↔ JPY
- Settlement: T+2

**Vietnam (Overseas)**
- Trading Fee: 0.30-0.35%
- Securities Transaction Tax: 0.1% (sell only)
- Currency Conversion: KRW ↔ VND
- Settlement: T+2

---

#### 1.2.3 Tax Implications for Korean Residents

**Domestic Stocks (Korea)**
- Capital Gains Tax: **None** (tax-free)
- Transaction Tax: 0.23% (KOSPI sell), 0.15% (KOSDAQ sell)

**Overseas Stocks**
- Capital Gains Tax: **22%** on profits exceeding **2.5M KRW annually**
- Calculation: (Total Gains - Total Losses - 2.5M KRW deduction) × 22%
- Reporting: Annual tax filing (May of following year)
- Example:
  - Total gains: 10M KRW
  - Total losses: 2M KRW
  - Net gain: 8M KRW
  - Taxable: 8M - 2.5M = 5.5M KRW
  - Tax: 5.5M × 0.22 = **1.21M KRW**

**Currency Conversion for Tax**
- Gains/losses calculated at actual trade execution rates
- Must track buy/sell exchange rates separately
- KIS provides annual transaction statements

---

### 1.3 Currency Management

#### 1.3.1 Supported Currencies
- **KRW** (Korean Won): Base currency for portfolio valuation
- **USD** (US Dollar): US stocks
- **HKD** (Hong Kong Dollar): Hong Kong stocks
- **CNY** (Chinese Yuan): China stocks
- **JPY** (Japanese Yen): Japan stocks
- **VND** (Vietnamese Dong): Vietnam stocks

#### 1.3.2 Exchange Rate Management
**Real-Time Rate Sources**:
- KIS API provides official exchange rates
- Fallback: Bank of Korea (한국은행) official rates
- Update frequency: Every 1 hour during trading hours

**Currency Conversion Formula**:
```python
# Portfolio value in KRW (base currency)
total_value_krw = (
    kr_positions_value_krw +
    us_positions_value_usd * usd_krw_rate +
    hk_positions_value_hkd * hkd_krw_rate +
    cn_positions_value_cny * cny_krw_rate +
    jp_positions_value_jpy * jpy_krw_rate +
    vn_positions_value_vnd * vnd_krw_rate
)
```

#### 1.3.3 Currency Risk Management
**Hedging Strategy**:
- Natural hedging: Diversify across multiple currencies
- No active currency hedging (too complex for automated system)
- Position limits per currency region to manage exposure

**Currency Allocation Limits**:
- KRW (Korea): 30-50% of portfolio
- USD (US): 20-40% of portfolio
- HKD/CNY (HK/China): 10-20% combined
- JPY (Japan): 5-15% of portfolio
- VND (Vietnam): 0-10% of portfolio

---

## 2. Global Multi-Market Pipeline Architecture

### 2.1 24-Hour Execution Model

**Continuous Operation Schedule** (KST timezone)

```
┌──────────────────────────────────────────────────────────────────┐
│                     24-Hour Global Trading Cycle                 │
└──────────────────────────────────────────────────────────────────┘

08:00-09:00  ASIA PRE-MARKET
├─ Korea market preparation
├─ Japan market preparation
├─ US overnight results analysis
├─ Global sentiment update (VIX, Fear & Greed)
└─ Exchange rate updates

09:00-16:00  ASIA INTRADAY SESSION
├─ 09:00-15:30  Korea (KOSPI/KOSDAQ)
│   ├─ Morning buy window (09:00-10:00)
│   ├─ Continuous monitoring (10:00-15:00)
│   └─ Afternoon sell window (15:00-15:30)
│
├─ 09:00-15:00  Japan (TSE)
│   ├─ Morning session (09:00-11:30)
│   ├─ Lunch break (11:30-12:30)
│   └─ Afternoon session (12:30-15:00)
│
├─ 10:30-17:00  Hong Kong (HKEX)
│   ├─ Morning session (10:30-13:00)
│   ├─ Lunch break (13:00-14:00)
│   └─ Afternoon session (14:00-17:00)
│
├─ 10:30-16:00  China (SSE/SZSE)
│   ├─ Morning session (10:30-12:30)
│   ├─ Lunch break (12:30-14:00)
│   └─ Afternoon session (14:00-16:00)
│
└─ 11:00-17:00  Vietnam (HOSE/HNX)
    ├─ Morning session (11:00-13:30)
    ├─ Lunch break (13:30-15:00)
    └─ Afternoon session (15:00-17:00)

16:00-22:00  ASIA POST-MARKET + US PRE-MARKET
├─ Portfolio sync (all Asia markets)
├─ Daily P&L calculation (Asia markets)
├─ Asia market daily reports
├─ GPT-4 analysis (top Asia candidates)
├─ US market scanner preparation
├─ US stock OHLCV data collection
└─ US market technical analysis

22:30-06:00  US INTRADAY SESSION (SUMMER)
23:30-06:00  US INTRADAY SESSION (WINTER)
├─ US market opening (22:30 or 23:30)
├─ Morning buy window (first hour)
├─ Continuous monitoring
├─ Afternoon sell window (last 30 min)
└─ US market closing (05:00 or 06:00)

06:00-08:00  US POST-MARKET + GLOBAL ANALYSIS
├─ Portfolio sync (US market)
├─ Daily P&L calculation (US market)
├─ US market daily report
├─ Consolidated global portfolio report
├─ Weekly/Monthly reports (if applicable)
└─ Database maintenance and backups
```

---

### 2.2 Market-Specific Pipeline Instances

Each market operates an independent pipeline, but shares common infrastructure.

**Pipeline Components per Market**:
```
Market Instance: US (NYSE/NASDAQ)
├─ Scanner: us_stock_scanner.py
├─ Data Collector: us_data_collector.py (KIS US API)
├─ Technical Filter: stock_technical_filter.py (reused)
├─ GPT Analyzer: stock_gpt_analyzer.py (reused)
├─ Kelly Calculator: kelly_calculator.py (market-adjusted win rates)
├─ Trading Engine: us_trading_engine.py (USD, US tick sizes)
├─ Risk Manager: risk_manager.py (market-specific parameters)
└─ Portfolio Manager: multi_market_portfolio.py (unified)

Market Instance: Hong Kong (HKEX)
├─ Scanner: hk_stock_scanner.py
├─ Data Collector: hk_data_collector.py (KIS HK API)
├─ Technical Filter: stock_technical_filter.py (reused)
├─ GPT Analyzer: stock_gpt_analyzer.py (reused)
├─ Kelly Calculator: kelly_calculator.py (market-adjusted win rates)
├─ Trading Engine: hk_trading_engine.py (HKD, HK tick sizes)
├─ Risk Manager: risk_manager.py (market-specific parameters)
└─ Portfolio Manager: multi_market_portfolio.py (unified)

...similar for China, Japan, Vietnam...
```

**Shared Components** (Market-Agnostic):
- `layered_scoring_engine.py` (100% reusable)
- `integrated_scoring_system.py` (100% reusable)
- `basic_scoring_modules.py` (100% reusable)
- `adaptive_scoring_config.py` (100% reusable)
- `db_manager_sqlite.py` (schema extended for global markets)
- `auto_recovery_system.py` (100% reusable)
- `stock_utils.py` (extended with timezone utilities)

---

### 2.3 Unified Portfolio Management

**Multi-Market Portfolio Manager** (`multi_market_portfolio.py`)

**Responsibilities**:
1. **Aggregate Portfolio Value**: Convert all positions to KRW using real-time rates
2. **Market Allocation Tracking**: Monitor exposure by market region
3. **Currency Allocation Tracking**: Monitor exposure by currency
4. **Sector Allocation**: Track GICS sectors across all markets
5. **Risk Limits Enforcement**:
   - Per-stock limit: 15% of total portfolio (KRW)
   - Per-sector limit: 40% of total portfolio
   - Per-market limit: Configurable (default: KR 50%, US 40%, Others 20%)
   - Per-currency limit: Prevent over-concentration

**Key Methods**:
```python
class MultiMarketPortfolio:
    def get_global_portfolio_value(self) -> Dict[str, Any]:
        """
        Calculate total portfolio value in KRW

        Returns:
            {
                'total_value_krw': 50_000_000,
                'by_market': {
                    'KR': {'value_krw': 25_000_000, 'pct': 50.0},
                    'US': {'value_krw': 15_000_000, 'pct': 30.0},
                    'HK': {'value_krw': 7_000_000, 'pct': 14.0},
                    'CN': {'value_krw': 3_000_000, 'pct': 6.0}
                },
                'by_currency': {
                    'KRW': {'value_krw': 25_000_000, 'pct': 50.0},
                    'USD': {'value_krw': 15_000_000, 'pct': 30.0},
                    'HKD': {'value_krw': 7_000_000, 'pct': 14.0},
                    'CNY': {'value_krw': 3_000_000, 'pct': 6.0}
                },
                'by_sector': {
                    'Information Technology': {'value_krw': 18_000_000, 'pct': 36.0},
                    'Financials': {'value_krw': 12_000_000, 'pct': 24.0},
                    ...
                },
                'unrealized_pnl_krw': 5_000_000,
                'unrealized_pnl_pct': 11.1
            }
        """

    def check_allocation_limits(
        self,
        ticker: str,
        exchange: str,
        currency: str,
        sector: str,
        proposed_value_krw: float
    ) -> Dict[str, bool]:
        """
        Validate proposed trade against all allocation limits

        Returns:
            {
                'can_trade': True,
                'within_stock_limit': True,      # <15% total portfolio
                'within_market_limit': True,     # Market allocation OK
                'within_currency_limit': True,   # Currency allocation OK
                'within_sector_limit': True,     # <40% sector
                'available_allocation_krw': 5_000_000,
                'warnings': []
            }
        """

    def get_market_positions(
        self,
        market: str  # 'KR', 'US', 'HK', 'CN', 'JP', 'VN'
    ) -> pd.DataFrame:
        """
        Get all positions for a specific market

        Returns:
            DataFrame with columns:
                ticker, exchange, quantity, avg_price_local, avg_price_krw,
                current_price_local, current_price_krw, unrealized_pnl_krw,
                position_value_krw, position_pct_of_total
        """

    def sync_all_markets(
        self,
        auto_resolve: bool = True,
        threshold_krw: float = 2_000_000
    ) -> Dict[str, Any]:
        """
        Sync portfolio with KIS API for all markets

        Returns:
            {
                'sync_status': 'SUCCESS',
                'markets_synced': ['KR', 'US', 'HK'],
                'discrepancies': [...],
                'total_diff_krw': 150_000,
                'actions_taken': [...]
            }
        """
```

---

### 2.4 Global Risk Management

**Enhanced Risk Manager** (`global_risk_manager.py`)

**Additional Risk Considerations**:
1. **Currency Risk**: Fluctuations in exchange rates affect portfolio value
2. **Market Correlation**: Some markets move together (e.g., HK and CN)
3. **Timezone Risk**: Cannot monitor positions in real-time during off-hours
4. **Liquidity Risk**: Some markets have lower liquidity (VN)
5. **Regulatory Risk**: Different regulatory environments

**Risk Management Strategies**:

**1. Currency Hedging (Natural)**
- Diversify across multiple currencies
- No active FX hedging (complexity)
- Monitor currency concentration

**2. Market Correlation Analysis**
```python
# Correlation matrix for portfolio optimization
MARKET_CORRELATIONS = {
    ('KR', 'US'): 0.45,   # Moderate positive correlation
    ('KR', 'HK'): 0.60,   # High correlation (Asia)
    ('KR', 'CN'): 0.55,   # High correlation (Asia)
    ('KR', 'JP'): 0.50,   # Moderate correlation (Asia)
    ('US', 'HK'): 0.40,   # Moderate correlation
    ('HK', 'CN'): 0.75,   # Very high correlation
    ('JP', 'CN'): 0.45,   # Moderate correlation
}
```

**3. Timezone-Adjusted Stop Loss**
- Asia markets: Real-time ATR-based trailing stops (same as Korea system)
- US market: Wider stops due to overnight risk for Korean traders
  - Base ATR multiplier: 2.0× (vs 1.5× for Asia)
  - Min stop: 7% (vs 5% for Asia)
  - Max stop: 20% (vs 15% for Asia)

**4. Liquidity-Adjusted Position Sizing**
```python
LIQUIDITY_MULTIPLIERS = {
    'US': 1.0,    # High liquidity (NYSE, NASDAQ)
    'KR': 0.9,    # Good liquidity (KOSPI)
    'HK': 0.8,    # Moderate liquidity
    'JP': 0.8,    # Moderate liquidity
    'CN': 0.7,    # Lower liquidity (Stock Connect limits)
    'VN': 0.5,    # Low liquidity (smaller market)
}

# Adjust Kelly position size by liquidity
kelly_size_adjusted = kelly_size_base * liquidity_multiplier[market]
```

---

## 3. Global Database Schema Extensions

### 3.1 Modified Core Tables

#### 3.1.1 `tickers` Table (Extended)
```sql
CREATE TABLE tickers (
    ticker TEXT NOT NULL,              -- Stock symbol
    exchange TEXT NOT NULL,            -- 'KOSPI', 'NYSE', 'NASDAQ', 'HKEX', 'TSE', etc.
    market_region TEXT NOT NULL,       -- 'KR', 'US', 'HK', 'CN', 'JP', 'VN'
    currency TEXT NOT NULL,            -- 'KRW', 'USD', 'HKD', 'CNY', 'JPY', 'VND'

    name TEXT NOT NULL,
    name_en TEXT,                      -- English name (for non-English markets)

    sector TEXT,                       -- GICS sector (global standard)
    industry TEXT,                     -- GICS industry

    market_cap REAL,                   -- Market cap in local currency
    market_cap_krw REAL,               -- Market cap in KRW (for comparison)

    listed_shares INTEGER,
    listing_date TEXT,
    is_active BOOLEAN DEFAULT 1,

    last_updated TEXT,

    PRIMARY KEY (ticker, exchange)     -- Composite key: ticker can repeat across exchanges
);

CREATE INDEX idx_tickers_exchange ON tickers(exchange);
CREATE INDEX idx_tickers_region ON tickers(market_region);
CREATE INDEX idx_tickers_currency ON tickers(currency);
CREATE INDEX idx_tickers_sector ON tickers(sector);
CREATE INDEX idx_tickers_market_cap_krw ON tickers(market_cap_krw);
```

**Example Rows**:
```
ticker='AAPL', exchange='NASDAQ', market_region='US', currency='USD', name='Apple Inc.'
ticker='005930', exchange='KOSPI', market_region='KR', currency='KRW', name='삼성전자'
ticker='0700', exchange='HKEX', market_region='HK', currency='HKD', name='Tencent Holdings'
ticker='600519', exchange='SSE', market_region='CN', currency='CNY', name='贵州茅台'
ticker='7203', exchange='TSE', market_region='JP', currency='JPY', name='トヨタ自動車'
```

---

#### 3.1.2 `ohlcv_data` Table (Extended)
```sql
CREATE TABLE ohlcv_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    exchange TEXT NOT NULL,
    date TEXT NOT NULL,                -- 'YYYY-MM-DD'
    period TEXT NOT NULL,              -- 'D', 'W', 'M'

    -- Price data (in local currency)
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER NOT NULL,

    -- Exchange rate on this date (for historical P&L calculation)
    exchange_rate_to_krw REAL,         -- Local currency to KRW rate

    -- Price data in KRW (for cross-market comparison)
    close_krw REAL,

    -- Technical Indicators (JSON)
    indicators TEXT,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(ticker, exchange, date, period),
    FOREIGN KEY(ticker, exchange) REFERENCES tickers(ticker, exchange)
);

CREATE INDEX idx_ohlcv_ticker_exchange_date ON ohlcv_data(ticker, exchange, date);
CREATE INDEX idx_ohlcv_exchange_date ON ohlcv_data(exchange, date);
CREATE INDEX idx_ohlcv_date ON ohlcv_data(date);
```

---

#### 3.1.3 `portfolio` Table (Extended)
```sql
CREATE TABLE portfolio (
    ticker TEXT,
    exchange TEXT,
    market_region TEXT,
    currency TEXT,

    -- Position Details
    quantity INTEGER NOT NULL,
    avg_price REAL NOT NULL,           -- Average entry price (local currency)
    total_cost REAL NOT NULL,          -- Total invested (local currency, including fees)

    -- Exchange Rate at Entry
    avg_exchange_rate_to_krw REAL,     -- Average KRW exchange rate at entry
    total_cost_krw REAL,               -- Total cost in KRW

    -- Current State
    current_price REAL,                -- Current price (local currency)
    current_exchange_rate_to_krw REAL, -- Current KRW exchange rate
    last_price_update TEXT,

    -- P&L (both local currency and KRW)
    unrealized_pnl REAL,               -- Local currency P&L
    unrealized_pnl_pct REAL,
    unrealized_pnl_krw REAL,           -- KRW P&L (includes FX gains/losses)

    -- Position Metrics (in KRW for unified portfolio view)
    position_value_krw REAL,           -- current_price × quantity × exchange_rate
    position_pct_of_total REAL,        -- % of total portfolio value (KRW)

    -- Risk Management
    stop_loss_price REAL,              -- Local currency
    profit_target_price REAL,          -- Local currency
    trailing_stop_price REAL,          -- Local currency
    highest_price_since_entry REAL,    -- Local currency

    -- Context
    entry_date TEXT,
    entry_pattern TEXT,
    entry_score REAL,
    holding_days INTEGER,

    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (ticker, exchange),
    FOREIGN KEY(ticker, exchange) REFERENCES tickers(ticker, exchange)
);

CREATE INDEX idx_portfolio_region ON portfolio(market_region);
CREATE INDEX idx_portfolio_currency ON portfolio(currency);
CREATE INDEX idx_portfolio_value_krw ON portfolio(position_value_krw DESC);
```

---

#### 3.1.4 `trades` Table (Extended)
```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT UNIQUE NOT NULL,
    ticker TEXT NOT NULL,
    exchange TEXT NOT NULL,
    market_region TEXT,
    currency TEXT,

    -- Entry
    entry_date TEXT NOT NULL,
    entry_price REAL NOT NULL,         -- Local currency
    entry_quantity INTEGER NOT NULL,
    entry_cost REAL NOT NULL,          -- Local currency, including fees
    entry_exchange_rate_to_krw REAL,   -- Exchange rate at entry
    entry_cost_krw REAL,               -- Entry cost in KRW

    -- Exit
    exit_date TEXT,
    exit_price REAL,                   -- Local currency
    exit_quantity INTEGER,
    exit_proceeds REAL,                -- Local currency, including fees
    exit_exchange_rate_to_krw REAL,    -- Exchange rate at exit
    exit_proceeds_krw REAL,            -- Exit proceeds in KRW

    -- P&L (both local currency and KRW)
    realized_pnl REAL,                 -- Local currency P&L
    realized_pnl_pct REAL,
    realized_pnl_krw REAL,             -- KRW P&L (includes FX gains/losses)
    fx_gain_loss_krw REAL,             -- Currency gain/loss component

    holding_days INTEGER,

    -- Trade Context
    buy_signal_score REAL,
    buy_pattern TEXT,
    sell_reason TEXT,

    -- Risk Management
    stop_loss_price REAL,
    profit_target_price REAL,
    trailing_stop_activated BOOLEAN,

    -- Transaction Details (local currency)
    trading_fee_buy REAL,
    trading_fee_sell REAL,
    tax_paid REAL,                     -- Securities tax, stamp duty, etc.

    -- Tax Tracking (for Korean residents)
    taxable_gain_krw REAL,             -- For overseas stocks: subject to 22% tax

    -- Status
    status TEXT,                       -- 'OPEN', 'CLOSED', 'PARTIAL'

    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(ticker, exchange) REFERENCES tickers(ticker, exchange)
);

CREATE INDEX idx_trades_ticker_exchange ON trades(ticker, exchange);
CREATE INDEX idx_trades_region ON trades(market_region);
CREATE INDEX idx_trades_entry_date ON trades(entry_date);
CREATE INDEX idx_trades_status ON trades(status);
```

---

### 3.2 New Global Tables

#### 3.2.1 `exchange_config` Table
**Purpose**: Store market-specific configurations

```sql
CREATE TABLE exchange_config (
    exchange TEXT PRIMARY KEY,         -- 'KOSPI', 'NYSE', 'NASDAQ', 'HKEX', 'TSE', etc.

    market_region TEXT NOT NULL,       -- 'KR', 'US', 'HK', 'CN', 'JP', 'VN'
    currency TEXT NOT NULL,            -- 'KRW', 'USD', 'HKD', 'CNY', 'JPY', 'VND'
    timezone TEXT NOT NULL,            -- 'Asia/Seoul', 'America/New_York', 'Asia/Hong_Kong', etc.

    -- Trading Hours (JSON)
    trading_hours TEXT,                -- {"regular": "09:30-16:00", "lunch": "12:00-13:00"}

    -- Tick Size Rules (JSON)
    tick_size_rules TEXT,              -- [{range: [0, 1000], tick: 5}, ...]

    -- Transaction Costs (JSON)
    transaction_costs TEXT,            -- {"trading_fee": 0.0015, "tax": 0.0023, ...}

    -- Settlement
    settlement_days INTEGER,           -- T+2, T+0, etc.

    -- Limits
    daily_price_limit_pct REAL,        -- Daily price movement limit (e.g., 30% for KOSPI)
    min_order_value REAL,              -- Minimum order value (local currency)

    -- API Configuration
    kis_api_market_code TEXT,          -- KIS API market code

    is_active BOOLEAN DEFAULT 1,
    last_updated TEXT
);

-- Insert default configurations
INSERT INTO exchange_config VALUES (
    'KOSPI', 'KR', 'KRW', 'Asia/Seoul',
    '{"regular": "09:00-15:30"}',
    '[{"range": [0, 10000], "tick": 5}, {"range": [10000, 50000], "tick": 10}, ...]',
    '{"trading_fee": 0.00015, "securities_tax": 0.0023}',
    2, 30.0, 10000, 'KR', 1, CURRENT_TIMESTAMP
);

INSERT INTO exchange_config VALUES (
    'NYSE', 'US', 'USD', 'America/New_York',
    '{"regular": "09:30-16:00", "extended": "04:00-20:00"}',
    '[{"range": [0, 1], "tick": 0.0001}, {"range": [1, null], "tick": 0.01}]',
    '{"trading_fee": 0.0025, "sec_fee": 0.000008}',
    2, NULL, 1, 'US', 1, CURRENT_TIMESTAMP
);

-- Similar for NASDAQ, HKEX, SSE, SZSE, TSE, HOSE, HNX...
```

---

#### 3.2.2 `exchange_rates` Table
**Purpose**: Historical and current exchange rates

```sql
CREATE TABLE exchange_rates (
    date TEXT NOT NULL,
    from_currency TEXT NOT NULL,
    to_currency TEXT NOT NULL,         -- Always 'KRW' (base currency)
    rate REAL NOT NULL,                -- How many KRW for 1 unit of from_currency

    source TEXT,                       -- 'KIS_API', 'BANK_OF_KOREA', 'MANUAL'
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (date, from_currency, to_currency)
);

CREATE INDEX idx_exchange_rates_date ON exchange_rates(date);

-- Example rows
INSERT INTO exchange_rates VALUES
    ('2024-01-02', 'USD', 'KRW', 1305.50, 'KIS_API', CURRENT_TIMESTAMP),
    ('2024-01-02', 'HKD', 'KRW', 167.20, 'KIS_API', CURRENT_TIMESTAMP),
    ('2024-01-02', 'CNY', 'KRW', 183.40, 'KIS_API', CURRENT_TIMESTAMP),
    ('2024-01-02', 'JPY', 'KRW', 9.15, 'KIS_API', CURRENT_TIMESTAMP),
    ('2024-01-02', 'VND', 'KRW', 0.053, 'KIS_API', CURRENT_TIMESTAMP);
```

---

#### 3.2.3 `exchange_holidays` Table
**Purpose**: Market-specific holidays

```sql
CREATE TABLE exchange_holidays (
    exchange TEXT NOT NULL,
    date TEXT NOT NULL,
    holiday_name TEXT,
    is_full_day BOOLEAN DEFAULT 1,     -- Full day closure vs half day

    PRIMARY KEY (exchange, date)
);

CREATE INDEX idx_holidays_date ON exchange_holidays(date);
CREATE INDEX idx_holidays_exchange ON exchange_holidays(exchange);

-- Example: Load holidays for all exchanges
-- Korea holidays
INSERT INTO exchange_holidays VALUES ('KOSPI', '2024-01-01', 'New Year', 1);
INSERT INTO exchange_holidays VALUES ('KOSPI', '2024-02-09', 'Lunar New Year Eve', 1);
-- ... (Korean holidays)

-- US holidays
INSERT INTO exchange_holidays VALUES ('NYSE', '2024-01-01', 'New Year', 1);
INSERT INTO exchange_holidays VALUES ('NYSE', '2024-01-15', 'MLK Day', 1);
INSERT INTO exchange_holidays VALUES ('NYSE', '2024-07-04', 'Independence Day', 1);
-- ... (US holidays)

-- Hong Kong holidays
INSERT INTO exchange_holidays VALUES ('HKEX', '2024-01-01', 'New Year', 1);
INSERT INTO exchange_holidays VALUES ('HKEX', '2024-02-10', 'Lunar New Year', 1);
-- ... (HK holidays)

-- Similar for China, Japan, Vietnam...
```

---

#### 3.2.4 `market_allocation_limits` Table
**Purpose**: Configurable portfolio allocation limits

```sql
CREATE TABLE market_allocation_limits (
    config_name TEXT PRIMARY KEY,      -- 'default', 'conservative', 'aggressive'

    -- Market Region Limits (% of total portfolio)
    kr_min_pct REAL,
    kr_max_pct REAL,
    us_min_pct REAL,
    us_max_pct REAL,
    hk_min_pct REAL,
    hk_max_pct REAL,
    cn_min_pct REAL,
    cn_max_pct REAL,
    jp_min_pct REAL,
    jp_max_pct REAL,
    vn_min_pct REAL,
    vn_max_pct REAL,

    -- Currency Limits (% of total portfolio)
    krw_min_pct REAL,
    krw_max_pct REAL,
    usd_min_pct REAL,
    usd_max_pct REAL,
    hkd_min_pct REAL,
    hkd_max_pct REAL,
    cny_min_pct REAL,
    cny_max_pct REAL,
    jpy_min_pct REAL,
    jpy_max_pct REAL,
    vnd_min_pct REAL,
    vnd_max_pct REAL,

    -- Per-Stock Limit
    max_single_stock_pct REAL,         -- 15% default

    -- Per-Sector Limit
    max_sector_pct REAL,               -- 40% default

    last_updated TEXT
);

-- Default configuration
INSERT INTO market_allocation_limits VALUES (
    'default',
    30, 50,  -- KR: 30-50%
    20, 40,  -- US: 20-40%
    0, 20,   -- HK: 0-20%
    0, 20,   -- CN: 0-20%
    0, 15,   -- JP: 0-15%
    0, 10,   -- VN: 0-10%
    30, 50,  -- KRW: 30-50%
    20, 40,  -- USD: 20-40%
    0, 20,   -- HKD: 0-20%
    0, 20,   -- CNY: 0-20%
    0, 15,   -- JPY: 0-15%
    0, 10,   -- VND: 0-10%
    15,      -- Max 15% per stock
    40,      -- Max 40% per sector
    CURRENT_TIMESTAMP
);

-- Conservative configuration (more diversified)
INSERT INTO market_allocation_limits VALUES (
    'conservative',
    40, 60,  -- KR: 40-60% (home bias)
    15, 30,  -- US: 15-30%
    0, 15,   -- HK: 0-15%
    0, 10,   -- CN: 0-10%
    0, 10,   -- JP: 0-10%
    0, 5,    -- VN: 0-5%
    40, 60,  -- KRW: 40-60%
    15, 30,  -- USD: 15-30%
    0, 15,   -- HKD: 0-15%
    0, 10,   -- CNY: 0-10%
    0, 10,   -- JPY: 0-10%
    0, 5,    -- VND: 0-5%
    10,      -- Max 10% per stock (more conservative)
    30,      -- Max 30% per sector
    CURRENT_TIMESTAMP
);

-- Aggressive configuration (global focus)
INSERT INTO market_allocation_limits VALUES (
    'aggressive',
    20, 40,  -- KR: 20-40%
    30, 50,  -- US: 30-50% (more US exposure)
    0, 25,   -- HK: 0-25%
    0, 25,   -- CN: 0-25%
    0, 20,   -- JP: 0-20%
    0, 15,   -- VN: 0-15%
    20, 40,  -- KRW: 20-40%
    30, 50,  -- USD: 30-50%
    0, 25,   -- HKD: 0-25%
    0, 25,   -- CNY: 0-25%
    0, 20,   -- JPY: 0-20%
    0, 15,   -- VND: 0-15%
    20,      -- Max 20% per stock (more aggressive)
    50,      -- Max 50% per sector
    CURRENT_TIMESTAMP
);
```

---

## 4. KIS Global API Integration

### 4.1 KIS API Market Codes

**KIS API Endpoints by Market**:

**Korea (Domestic)**
- Base URL: `https://openapi.koreainvestment.com:9443`
- Market Code: `KR` (domestic) or `J` (KOSPI), `Q` (KOSDAQ)

**United States**
- Base URL: Same (unified API)
- Market Code: `US` or exchange-specific:
  - `NYSE`: New York Stock Exchange
  - `NASDAQ`: NASDAQ
  - `AMEX`: American Stock Exchange

**Hong Kong**
- Market Code: `HK` or `HKEX`

**China**
- Market Code: `CN` or exchange-specific:
  - `SSE`: Shanghai Stock Exchange (600xxx codes)
  - `SZSE`: Shenzhen Stock Exchange (000xxx, 002xxx codes)

**Japan**
- Market Code: `JP` or `TSE` (Tokyo Stock Exchange)

**Vietnam**
- Market Code: `VN` or exchange-specific:
  - `HOSE`: Ho Chi Minh Stock Exchange
  - `HNX`: Hanoi Stock Exchange

---

### 4.2 API Endpoint Mapping

**Unified Data Collector Architecture**:

```python
class GlobalDataCollector:
    """Unified data collector for all markets"""

    MARKET_ENDPOINTS = {
        'KR': {
            'daily_price': '/uapi/domestic-stock/v1/quotations/inquire-daily-price',
            'realtime': '/uapi/domestic-stock/v1/quotations/inquire-price',
            'investor': '/uapi/domestic-stock/v1/quotations/inquire-investor'
        },
        'US': {
            'daily_price': '/uapi/overseas-price/v1/quotations/dailyprice',
            'realtime': '/uapi/overseas-price/v1/quotations/price',
            'exchange_code': 'NASD'  # or 'NYSE', 'AMEX'
        },
        'HK': {
            'daily_price': '/uapi/overseas-price/v1/quotations/dailyprice',
            'realtime': '/uapi/overseas-price/v1/quotations/price',
            'exchange_code': 'SEHK'
        },
        'CN': {
            'daily_price': '/uapi/overseas-price/v1/quotations/dailyprice',
            'realtime': '/uapi/overseas-price/v1/quotations/price',
            'exchange_code': 'SHAA'  # or 'SZAA'
        },
        'JP': {
            'daily_price': '/uapi/overseas-price/v1/quotations/dailyprice',
            'realtime': '/uapi/overseas-price/v1/quotations/price',
            'exchange_code': 'TSE'
        },
        'VN': {
            'daily_price': '/uapi/overseas-price/v1/quotations/dailyprice',
            'realtime': '/uapi/overseas-price/v1/quotations/price',
            'exchange_code': 'HOSE'  # or 'HNX'
        }
    }

    def collect_ohlcv(
        self,
        ticker: str,
        exchange: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """Market-agnostic OHLCV collection"""
        market_region = self._get_market_region(exchange)
        endpoint_config = self.MARKET_ENDPOINTS[market_region]

        # Call appropriate API endpoint
        if market_region == 'KR':
            return self._collect_domestic(ticker, start_date, end_date)
        else:
            return self._collect_overseas(
                ticker,
                endpoint_config['exchange_code'],
                start_date,
                end_date
            )
```

---

### 4.3 Market-Specific Order Execution

**Trading Engine per Market**:

```python
class GlobalTradingEngine:
    """Unified trading engine with market-specific execution"""

    def execute_buy_order(
        self,
        ticker: str,
        exchange: str,
        quantity: int,
        order_type: str = 'LIMIT',
        limit_price: float = None
    ) -> Dict[str, Any]:
        """Market-agnostic buy order execution"""

        # Get market configuration
        exchange_config = self.db.get_exchange_config(exchange)

        # Apply tick size compliance
        if limit_price:
            limit_price = self._apply_tick_size(
                limit_price,
                exchange_config['tick_size_rules']
            )

        # Calculate transaction costs
        costs = self._calculate_costs(
            exchange,
            limit_price,
            quantity,
            'BUY'
        )

        # Check allocation limits
        currency = exchange_config['currency']
        current_rate = self.currency_converter.get_rate(currency, 'KRW')
        value_krw = limit_price * quantity * current_rate + costs['total']

        allocation_check = self.portfolio.check_allocation_limits(
            ticker, exchange, currency, sector, value_krw
        )

        if not allocation_check['can_trade']:
            return {'status': 'REJECTED', 'reason': allocation_check['warnings']}

        # Execute order via KIS API
        if exchange_config['market_region'] == 'KR':
            result = self._execute_domestic_order(ticker, quantity, limit_price, 'BUY')
        else:
            result = self._execute_overseas_order(
                ticker,
                exchange_config['kis_api_market_code'],
                quantity,
                limit_price,
                'BUY'
            )

        # Record trade with exchange rate
        if result['status'] == 'FILLED':
            self._record_trade(
                ticker, exchange, quantity, result['executed_price'],
                current_rate, costs
            )

        return result

    def _apply_tick_size(
        self,
        price: float,
        tick_rules: List[Dict]
    ) -> float:
        """Apply market-specific tick size rules"""
        for rule in tick_rules:
            min_price = rule['range'][0]
            max_price = rule['range'][1] or float('inf')
            if min_price <= price < max_price:
                tick = rule['tick']
                return round(price / tick) * tick
        return price

    def _calculate_costs(
        self,
        exchange: str,
        price: float,
        quantity: int,
        side: str
    ) -> Dict[str, float]:
        """Calculate market-specific transaction costs"""
        config = self.db.get_exchange_config(exchange)
        costs = json.loads(config['transaction_costs'])

        gross = price * quantity

        fees = {
            'trading_fee': gross * costs.get('trading_fee', 0),
            'tax': gross * costs.get('tax', 0) if side == 'SELL' else 0,
            'stamp_duty': gross * costs.get('stamp_duty', 0) if 'stamp_duty' in costs else 0,
        }

        fees['total'] = sum(fees.values())
        fees['net_amount'] = gross - fees['total'] if side == 'SELL' else gross + fees['total']

        return fees
```

---

## 5. Phased Development Roadmap

### Phase 1-3: Korea Market Foundation (Weeks 1-5)
**Status**: As per original PIPELINE_ARCHITECTURE.md

**Deliverables**:
- ✅ Complete Korea market system (KOSPI/KOSDAQ)
- ✅ Database schema (Korea-specific)
- ✅ LayeredScoringEngine (100% reusable globally)
- ✅ Kelly Calculator (100% reusable)
- ✅ Risk management (ATR stops, Stage detection)
- ✅ Validated with live/paper trading

---

### Phase 4: US Market Integration (Weeks 6-8)

**Objective**: Add US stock market (NYSE, NASDAQ, AMEX)

**Why US First**:
- Largest and most liquid market
- Best companies and ETFs (Apple, Microsoft, Tesla, SPY, QQQ)
- KIS API well-supported for US trading
- High demand from Korean investors

**Tasks**:

**Week 6: Database & Configuration**
1. **Database Schema Extension**
   - Extend `tickers` table with composite key (ticker, exchange)
   - Add `exchange_config`, `exchange_rates`, `exchange_holidays` tables
   - Add `market_allocation_limits` table
   - Migrate existing Korea data to new schema
   - Test database operations with multi-market data

2. **US Market Configuration**
   - Create `config/us_market_config.py`
   - Load US holidays (NYSE calendar)
   - Configure US tick size rules
   - Configure US transaction costs
   - Setup USD/KRW exchange rate fetching

**Week 7: US Data Pipeline**
3. **US Data Collector**
   - Create `us_data_collector.py` (adapt from `kis_data_collector.py`)
   - Implement KIS overseas API integration
   - Test OHLCV collection for US stocks (AAPL, MSFT, TSLA)
   - Implement incremental updates with gap detection
   - Add exchange rate tracking

4. **US Stock Scanner**
   - Create `us_stock_scanner.py`
   - Implement S&P 500 / Russell 1000 universe
   - Apply filters (market cap >$10B, volume >$100M)
   - Sector classification (GICS global standard)
   - Test scanner output (~200-500 US stocks)

**Week 8: US Trading & Portfolio Integration**
5. **US Trading Engine**
   - Create `us_trading_engine.py`
   - Implement USD tick size compliance ($0.01)
   - Implement US transaction cost calculation
   - Test dry-run order execution (paper trading)
   - Validate order confirmations

6. **Multi-Market Portfolio Manager**
   - Create `multi_market_portfolio.py`
   - Implement currency conversion (USD → KRW)
   - Implement unified portfolio valuation
   - Implement market allocation limits (KR 50%, US 40%)
   - Test portfolio sync (Korea + US positions)

7. **24-Hour Scheduler**
   - Update `spock.py` to support 24-hour operation
   - Implement timezone-aware scheduling
   - Add US market hours detection (with DST handling)
   - Test market transition (Korea close → US open)

**Deliverables**:
- ✅ US market data collection working
- ✅ US stock scanner filtering properly
- ✅ US trading engine executing dry-run orders
- ✅ Unified portfolio showing KR + US positions
- ✅ 24-hour operation with Korea day + US night trading

**Testing**:
```bash
# Test US data collection
python3 modules/us_data_collector.py --ticker AAPL --days 250

# Test US scanner
python3 modules/us_stock_scanner.py --min-market-cap 10000000000

# Test US trading engine (dry run)
python3 modules/us_trading_engine.py --ticker AAPL --quantity 10 --dry-run

# Test unified portfolio
python3 modules/multi_market_portfolio.py --show-all-markets

# Test 24-hour execution
python3 spock.py --dry-run --enable-us-market
```

---

### Phase 5: Hong Kong & China Markets (Weeks 9-11)

**Objective**: Add Hong Kong (HKEX) and China (SSE/SZSE via Stock Connect)

**Why HK/China Next**:
- Access to Chinese tech giants (Alibaba, Tencent, BYD)
- High correlation with Korea market (portfolio diversification benefit)
- Popular among Korean investors
- Stock Connect makes mainland China accessible

**Tasks**:

**Week 9: HK/CN Configuration**
1. **Database Updates**
   - Add HK/CN exchange configurations
   - Load HK/CN holidays
   - Add HKD/CNY exchange rate tracking

2. **HK Market Configuration**
   - HK tick size rules (complex, 8 tiers)
   - HK transaction costs (0.1% stamp duty both ways)
   - Trading hours with lunch break

3. **China Market Configuration**
   - CN tick size rules (simple: 0.01 CNY)
   - CN transaction costs (0.1% stamp duty on sell)
   - Stock Connect quota management

**Week 10: HK/CN Data Pipeline**
4. **HK/CN Data Collectors**
   - Create `hk_data_collector.py` and `cn_data_collector.py`
   - Implement KIS overseas API for HK/CN
   - Test with representative stocks (0700.HK Tencent, 600519.SS Moutai)

5. **HK/CN Stock Scanners**
   - Create `hk_stock_scanner.py` and `cn_stock_scanner.py`
   - Hang Seng Index + China A50 universe
   - Apply filters

**Week 11: HK/CN Trading Integration**
6. **HK/CN Trading Engines**
   - Create `hk_trading_engine.py` and `cn_trading_engine.py`
   - Implement HK complex tick sizes
   - Implement CN simple tick sizes
   - Test dry-run orders

7. **Portfolio Integration**
   - Update `multi_market_portfolio.py` for HK/CN
   - Add HKD/CNY currency handling
   - Update allocation limits (KR 40%, US 30%, HK/CN 20%)
   - Test unified portfolio with 4 markets

**Deliverables**:
- ✅ HK/CN data collection working
- ✅ HK/CN scanners operational
- ✅ HK/CN trading engines (dry-run)
- ✅ Unified portfolio with 4 markets (KR, US, HK, CN)

---

### Phase 6: Japan & Vietnam Markets (Weeks 12-14) - Optional

**Objective**: Add Japan (TSE) and Vietnam (HOSE/HNX) for full Asia coverage

**Why Last**:
- Lower priority (smaller markets for most investors)
- Vietnam: Emerging market, higher risk
- Japan: Mature but slower growth
- Optional phase - can be deferred

**Tasks** (similar structure to Phase 5):
- Week 12: JP/VN configuration
- Week 13: JP/VN data pipeline
- Week 14: JP/VN trading integration

**Deliverables**:
- ✅ JP/VN data collection (optional)
- ✅ JP/VN trading engines (optional)
- ✅ Complete 6-market system (KR, US, HK, CN, JP, VN)

---

## 6. Performance Targets (Global)

### 6.1 System Performance

| Metric | Target | Notes |
|--------|--------|-------|
| Pre-market execution | <10 min | All markets combined |
| Scoring per ticker | <10 sec | Same as Korea system |
| Order execution | <3 sec | Per market API latency |
| Portfolio sync | <30 sec | All markets combined |
| Currency rate update | <5 sec | 6 currencies |
| 24-hour uptime | ≥99% | Critical during market hours |

### 6.2 Trading Performance (Global Portfolio)

| Metric | Target | Baseline | Notes |
|--------|--------|----------|-------|
| Annual Return | ≥18% | MSCI ACWI ~10% | Global diversification premium |
| Sharpe Ratio | ≥1.8 | 1.5 (single market) | Better risk-adjusted returns |
| Max Drawdown | ≤12% | 15% (Korea only) | Reduced via diversification |
| Win Rate | ≥58% | 55% (Korea only) | US market efficiency |
| Currency Risk (StdDev) | ≤5% | N/A | FX volatility impact |

### 6.3 Market-Specific Win Rates (Expected)

Based on market efficiency and historical data:

| Market | Expected Win Rate | Avg Win/Loss | Kelly Multiplier |
|--------|------------------|--------------|------------------|
| Korea (KOSPI/KOSDAQ) | 55% | 2.0 | 1.0 |
| US (NYSE/NASDAQ) | 60% | 1.8 | 1.1 (higher win rate) |
| Hong Kong (HKEX) | 54% | 2.1 | 0.95 |
| China (SSE/SZSE) | 52% | 2.2 | 0.90 |
| Japan (TSE) | 53% | 1.9 | 0.95 |
| Vietnam (HOSE/HNX) | 48% | 2.5 | 0.70 (higher risk) |

**Kelly Position Sizing Adjustment**:
```python
# Adjust Kelly fraction by market efficiency
kelly_size_adjusted = (
    base_kelly_fraction *
    market_multiplier[market] *
    liquidity_multiplier[market]
)
```

---

## 7. Risk Management Considerations

### 7.1 Currency Risk

**Impact**:
- USD/KRW volatility: ~±5% annually
- Can significantly affect portfolio value
- Example: $100K position, USD/KRW moves 1300 → 1350 (+3.8%)
  - Stock flat: Portfolio gains 3.8% in KRW terms
  - Stock +10%: Total gain in KRW = 10% + 3.8% = 13.8%

**Mitigation**:
- Natural hedging through diversification
- Limit single currency exposure (<40%)
- Monitor currency trends alongside stock performance

### 7.2 Timezone Risk

**Challenge**: Cannot monitor US positions in real-time during Korean daytime

**Mitigation**:
- Wider stop-losses for US stocks (7-20% vs 5-15% for Asia)
- Larger ATR multiplier (2.0× vs 1.5×)
- Avoid highly volatile US stocks (beta >1.5)
- Use limit orders for US trading (not market orders)
- Nightly review of US positions before Korea market opens

### 7.3 Market Correlation

**High Correlation Pairs** (avoid over-concentration):
- Hong Kong ↔ China: 0.75 correlation
- Korea ↔ Japan: 0.50 correlation
- US ↔ Hong Kong: 0.40 correlation

**Portfolio Construction**:
- Limit combined HK+CN exposure to 20%
- Diversify across uncorrelated markets (US + Asia)
- Monitor sector overlap (e.g., Tech heavy in both US and Korea)

### 7.4 Regulatory Risk

**Market-Specific Risks**:
- **China**: Policy risk (government interventions), Stock Connect quotas
- **Vietnam**: Emerging market, lower liquidity, foreign ownership limits
- **Hong Kong**: Geopolitical risk (China relations)

**Mitigation**:
- Limit exposure to high-risk markets (CN ≤15%, VN ≤10%)
- Avoid politically sensitive sectors in China (education, gaming)
- Monitor news and regulatory changes

---

## 8. Tax Optimization Strategies

### 8.1 Annual Tax Planning

**Overseas Stock Capital Gains Tax** (22% on gains >2.5M KRW):

**Strategy 1: Loss Harvesting**
- Intentionally realize losses to offset gains
- Example:
  - Realized gains: 8M KRW
  - Unrealized losses in portfolio: -3M KRW
  - Action: Sell losing positions before year-end
  - New taxable gain: 8M - 3M = 5M KRW
  - Tax savings: 3M × 0.22 = 660K KRW saved

**Strategy 2: 2.5M KRW Deduction Maximization**
- Take profits strategically to use full deduction
- If current year gains < 2.5M, realize more gains (tax-free)
- If approaching 2.5M limit, defer profits to next year

**Strategy 3: Korea Stock Preference for Short-Term**
- Korea stocks: No capital gains tax
- Overseas stocks: 22% tax
- Strategy: Use overseas for long-term holds (Stage 2 uptrends)
- Use Korea for short-term trades (reduce tax drag)

### 8.2 Automated Tax Tracking

**System Features**:
```python
class TaxTracker:
    def get_annual_tax_summary(self, year: int) -> Dict:
        """
        Calculate annual overseas stock gains/losses

        Returns:
            {
                'total_realized_gains_krw': 8_000_000,
                'total_realized_losses_krw': 2_000_000,
                'net_gains_krw': 6_000_000,
                'deduction_krw': 2_500_000,
                'taxable_amount_krw': 3_500_000,
                'tax_due_krw': 770_000,  # 3.5M × 0.22
                'tax_rate': 0.22,
                'trades_summary': [...]
            }
        """

    def suggest_tax_optimization(
        self,
        current_date: str
    ) -> List[Dict]:
        """
        Suggest tax-efficient trades before year-end

        Returns:
            [
                {
                    'action': 'SELL',
                    'ticker': 'BABA',
                    'reason': 'Harvest loss (-15%) to offset gains',
                    'tax_savings_krw': 500_000
                },
                {
                    'action': 'HOLD',
                    'ticker': 'AAPL',
                    'reason': 'Defer gain (+25%) to next year',
                    'tax_deferral_krw': 1_200_000
                }
            ]
        """
```

---

## 9. Configuration Management

### 9.1 Multi-Market Configuration Structure

```
~/spock/config/
├── kis_api_config.py              # Korea market (existing)
├── global_market_config.py        # Global market settings (new)
├── exchange_configs/              # Market-specific configurations (new)
│   ├── us_market.json
│   ├── hk_market.json
│   ├── cn_market.json
│   ├── jp_market.json
│   └── vn_market.json
├── exchange_holidays/             # Holiday calendars (new)
│   ├── kospi_holidays_2024.json
│   ├── nyse_holidays_2024.json
│   ├── hkex_holidays_2024.json
│   ├── sse_holidays_2024.json
│   ├── tse_holidays_2024.json
│   └── hose_holidays_2024.json
└── stock_blacklist.json           # Global blacklist (extended)
```

### 9.2 `config/global_market_config.py`

```python
"""
Global multi-market configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

GLOBAL_CONFIG = {
    # Enabled Markets (turn on/off markets)
    'enabled_markets': {
        'KR': True,   # Korea (baseline)
        'US': True,   # United States (Phase 4)
        'HK': False,  # Hong Kong (Phase 5)
        'CN': False,  # China (Phase 5)
        'JP': False,  # Japan (Phase 6, optional)
        'VN': False,  # Vietnam (Phase 6, optional)
    },

    # Portfolio Allocation Profile
    'allocation_profile': 'default',  # 'default', 'conservative', 'aggressive'

    # Currency Settings
    'base_currency': 'KRW',
    'update_exchange_rates_frequency': 3600,  # Seconds (1 hour)

    # Tax Settings
    'tax_country': 'KR',  # Korean resident tax rules
    'overseas_tax_rate': 0.22,
    'overseas_tax_deduction': 2_500_000,  # KRW

    # Risk Management
    'global_circuit_breaker': {
        'max_daily_loss_pct': 0.07,      # 7% (vs 5% single market)
        'max_drawdown_pct': 0.12,        # 12% (vs 15% single market)
        'currency_risk_limit_pct': 0.05, # 5% FX volatility
    },

    # 24-Hour Operation
    'enable_24hour_operation': True,
    'us_daylight_saving': True,  # Auto-detect DST

    # Multi-Market Execution
    'parallel_market_execution': False,  # Execute markets sequentially for safety
    'market_priority': ['KR', 'US', 'HK', 'CN', 'JP', 'VN'],  # Execution order
}

# Market-Specific API Keys (if different from main KIS account)
US_MARKET_CONFIG = {
    'kis_account_number': os.getenv('KIS_US_ACCOUNT'),  # May be same as KR
    'enable_extended_hours': False,  # 04:00-20:00 ET (risky for automated)
}

# Exchange Rate Data Sources
EXCHANGE_RATE_SOURCES = {
    'primary': 'KIS_API',
    'fallback': 'BANK_OF_KOREA',
    'update_schedule': 'hourly',  # 'hourly', 'daily', 'realtime'
}
```

---

## 10. Next Steps & Implementation Priority

### 10.1 Immediate Actions (Week 1)

**Before Starting Phase 4 (US Market)**:
1. ✅ Complete Phase 1-3 (Korea market) successfully
2. ✅ Validate Korea system with paper trading (1-2 weeks)
3. ✅ Ensure profitability and stability

**Week 1 Preparation**:
1. Review this GLOBAL_MARKET_EXPANSION.md document
2. Design detailed database migration plan (Korea → Multi-market schema)
3. Setup development environment for multi-market testing
4. Obtain KIS API access for US market (if not already available)

### 10.2 Decision Points

**Go/No-Go Decision for Each Phase**:

**Phase 4 (US Market)**: Proceed if
- ✅ Korea system profitable for ≥1 month
- ✅ Sharpe ratio ≥1.3
- ✅ Max drawdown ≤18%
- ✅ No critical bugs in production

**Phase 5 (HK/CN Markets)**: Proceed if
- ✅ US market integration successful (≥1 month)
- ✅ Unified portfolio management working
- ✅ Currency conversion accurate
- ✅ Combined KR+US portfolio Sharpe ≥1.5

**Phase 6 (JP/VN Markets)**: Optional
- Evaluate based on Phase 5 results
- Consider investor interest and demand
- Assess risk/reward of adding emerging markets

### 10.3 Risk Mitigation

**Start Small**:
- Phase 4: Limit US positions to 10% of portfolio initially
- Gradually increase to 20%, then 30%, then target 40%
- Monitor for 1 month at each level

**Parallel Testing**:
- Run paper trading for new markets alongside live Korea trading
- Validate all components (scanner, data, scoring, trading) in paper mode
- Switch to live trading only after validation

**Rollback Plan**:
- Keep Korea system as independent fallback
- If global system fails, revert to Korea-only operation
- Maintain separate database backups

---

## 11. Expected Outcomes

### 11.1 Benefits of Global Expansion

**Diversification**:
- Reduced portfolio volatility (-20% expected)
- Lower drawdown (-3% absolute)
- Access to uncorrelated markets

**Better Opportunities**:
- World-class companies (FAANG, Alibaba, Toyota)
- Superior ETFs (SPY, QQQ, VTI)
- Sector coverage (e.g., US dominates tech)

**Enhanced Returns**:
- Target 18% annual return (vs 15% Korea-only)
- Higher Sharpe ratio (1.8 vs 1.5)
- Better risk-adjusted performance

**Investor Appeal**:
- Professional global portfolio management
- Automated currency handling
- Tax-optimized trading

### 11.2 Challenges

**Complexity**:
- 6 markets vs 1 market (6× operational complexity)
- Currency management overhead
- Timezone coordination
- Market-specific regulations

**Development Time**:
- Additional 6-9 weeks (Phase 4-6)
- Testing and validation overhead
- Higher maintenance burden

**Risk**:
- Currency risk
- Regulatory changes
- Increased monitoring requirements

---

## 12. Conclusion

This global market expansion transforms Spock from a **Korea-focused trading system** into a **world-class global portfolio management platform**. The phased approach ensures stability and validates each market before expansion.

**Recommendation**:
1. Complete and validate Korea system (Phase 1-3)
2. Proceed with US market integration (Phase 4) - **High Priority**
3. Evaluate HK/CN markets (Phase 5) based on Phase 4 results
4. Defer JP/VN markets (Phase 6) unless specific demand

**Timeline**:
- Phase 1-3 (Korea): Weeks 1-5 ✅
- Phase 4 (US): Weeks 6-8 🎯 **Next Priority**
- Phase 5 (HK/CN): Weeks 9-11 (conditional)
- Phase 6 (JP/VN): Weeks 12-14 (optional)

**Success Criteria**:
- Korea system: ≥15% annual return, Sharpe ≥1.5
- Global system: ≥18% annual return, Sharpe ≥1.8
- Max drawdown: ≤12% (vs 15% Korea-only)
- Currency risk: ≤5% volatility
- System uptime: ≥99% during market hours

---

**Document Version**: 1.0
**Last Updated**: 2024-01-01
**Status**: Design Document - Pending Korea System Validation
**Next Review**: After Phase 3 completion
