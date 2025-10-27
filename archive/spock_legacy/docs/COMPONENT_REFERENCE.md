# Spock Trading System - Component Reference

**Complete module documentation for 85 Python components**
**Last Updated**: 2025-10-18

---

## Table of Contents

1. [Core Trading Components](#1-core-trading-components) (11 modules)
2. [Market Adapters](#2-market-adapters) (13 modules)
3. [API Clients](#3-api-clients) (14 modules)
4. [Analysis Engines](#4-analysis-engines) (10 modules)
5. [Data Processing](#5-data-processing) (14 modules)
6. [Backtesting Framework](#6-backtesting-framework) (11 modules)
7. [Utilities & Infrastructure](#7-utilities--infrastructure) (12 modules)

---

## 1. Core Trading Components

Essential modules for trading operations, data collection, and portfolio management.

### 1.1 `kis_data_collector.py`
**Purpose**: Incremental OHLCV data collection with 250-day retention

**Key Classes**:
- `KISDataCollector`: Main data collection orchestrator

**Core Features**:
- Incremental data collection with gap detection
- 250-day rolling retention policy
- Technical indicator calculation (MA, RSI, MACD, BB, ATR)
- Batch processing with rate limiting (20 req/sec)
- Multi-region support (KR, US, CN, HK, JP, VN)

**Usage**:
```python
from modules.kis_data_collector import KISDataCollector
from modules.db_manager_sqlite import SQLiteDatabaseManager

db = SQLiteDatabaseManager()
collector = KISDataCollector(db, region='US')

# Collect data for specific tickers
collector.collect_stock_ohlcv(
    tickers=['AAPL', 'MSFT', 'GOOGL'],
    days=250,
    batch_size=100
)
```

**CLI**:
```bash
# Dry run
python3 modules/kis_data_collector.py --dry-run --tickers 005930

# Full collection
python3 modules/kis_data_collector.py --tickers 005930,000660 --days 250
```

---

### 1.2 `kis_trading_engine.py`
**Purpose**: KIS API order execution with tick size compliance

**Key Classes**:
- `KISTradingEngine`: Order execution manager
- `OrderValidator`: Pre-execution validation
- `TickSizeAdjuster`: Price adjustment for tick size compliance

**Core Features**:
- Market/limit order execution
- Automatic tick size adjustment
- Portfolio synchronization with KIS API
- Risk management integration (position limits, stop loss)
- Dry-run mode for testing

**Tick Size Rules**:
```
<10,000 KRW:     5 KRW tick
10,000-50,000:   10 KRW tick
50,000-200,000:  50 KRW tick
200,000-500,000: 100 KRW tick
500,000+:        1,000 KRW tick
```

**Usage**:
```python
from modules.kis_trading_engine import KISTradingEngine
from modules.db_manager_sqlite import SQLiteDatabaseManager

db = SQLiteDatabaseManager()
engine = KISTradingEngine(db, dry_run=True)

# Place buy order
result = engine.execute_buy_order(
    ticker='005930',
    quantity=10,
    price=70000,  # Auto-adjusted to nearest tick
    order_type='limit'
)
```

**CLI**:
```bash
# Dry run
python3 modules/kis_trading_engine.py --dry-run --no-gpt

# Live trading (requires confirmation)
python3 modules/kis_trading_engine.py --risk-level moderate
```

---

### 1.3 `portfolio_manager.py`
**Purpose**: Portfolio tracking and position management

**Key Classes**:
- `PortfolioManager`: Main portfolio orchestrator
- `PositionTracker`: Individual position tracking
- `PnLCalculator`: Profit/loss calculation

**Core Features**:
- Real-time portfolio synchronization with KIS API
- Position tracking with entry/exit prices
- P&L calculation (realized/unrealized)
- Position limits enforcement (15% per stock, 40% per sector)
- Rebalancing recommendations

**Database Tables**:
- `portfolio`: Current positions
- `trades`: Historical trade records

**Usage**:
```python
from modules.portfolio_manager import PortfolioManager

pm = PortfolioManager(db)

# Get current positions
positions = pm.get_current_positions()

# Calculate total P&L
total_pnl = pm.calculate_total_pnl()

# Check position limits
can_buy = pm.check_position_limit('005930', quantity=10)
```

---

### 1.4 `risk_manager.py`
**Purpose**: Risk management and position sizing

**Key Classes**:
- `RiskManager`: Risk assessment and enforcement
- `StopLossCalculator`: ATR-based trailing stops
- `PositionSizer`: Kelly-based position sizing

**Core Features**:
- ATR-based trailing stop loss (base 1.0 × ATR)
- Position size limits (max 15% per stock)
- Sector concentration limits (max 40% per sector)
- Cash reserve requirements (min 20%)
- Stage 3 detection for profit taking

**Risk Profiles**:
```yaml
conservative:
  max_position: 10%
  stop_loss: 3-8%
  profit_target: 15%
  min_score: 75

moderate:
  max_position: 15%
  stop_loss: 5-10%
  profit_target: 20%
  min_score: 70

aggressive:
  max_position: 20%
  stop_loss: 7-15%
  profit_target: 25%
  min_score: 65
```

**Usage**:
```python
from modules.risk_manager import RiskManager

rm = RiskManager(db, risk_profile='moderate')

# Calculate position size
position_size = rm.calculate_position_size(
    ticker='005930',
    pattern='Stage 2 Breakout',
    win_rate=0.65,
    avg_win_loss_ratio=2.0
)

# Calculate stop loss
stop_price = rm.calculate_stop_loss(
    ticker='005930',
    entry_price=70000,
    atr=1500
)
```

---

### 1.5 `scanner.py`
**Purpose**: Stock ticker discovery and filtering

**Key Classes**:
- `StockScanner`: Ticker scanning orchestrator
- `FilterEngine`: Multi-criteria filtering

**Core Features**:
- Market-specific ticker discovery (KRX, NYSE, NASDAQ, etc.)
- Multi-criteria filtering (market cap, volume, price)
- Blacklist integration
- ETF/SPAC exclusion
- Region-aware scanning

**Filtering Criteria**:
```yaml
default:
  min_market_cap: 1,000,000,000 KRW
  min_avg_volume: 100,000 shares
  min_price: 1,000 KRW
  max_price: 1,000,000 KRW
  exclude_etf: true
  exclude_spac: true
```

**Usage**:
```python
from modules.scanner import StockScanner

scanner = StockScanner(db, region='US')

# Scan with filters
tickers = scanner.scan_stocks(
    min_market_cap=1e9,
    min_avg_volume=1e5,
    force_refresh=True
)

# Get ticker details
details = scanner.get_ticker_details('AAPL')
```

---

### 1.6 `stock_pre_filter.py`
**Purpose**: Stage 1 technical pre-filtering (Weinstein Stage 2)

**Key Classes**:
- `StockPreFilter`: Stage 1 filter orchestrator
- `WeinsteinStageDetector`: Stage 2 detection logic

**Core Features**:
- Weinstein Stage 2 detection (uptrend breakout)
- MA alignment check (5/20/60/120/200)
- Volume profile analysis
- Stage transition detection
- Multi-region support

**Stage 2 Criteria**:
```yaml
stage_2:
  ma_alignment: true  # Price > MA5 > MA20 > MA60
  price_above_ma200: true
  ma200_slope: positive
  volume_above_avg: true
  stage_transition: 1 → 2 (accumulation → markup)
```

**Usage**:
```python
from modules.stock_pre_filter import StockPreFilter

pre_filter = StockPreFilter(db, region='US')

# Filter stocks for Stage 2
stage2_stocks = pre_filter.filter_stage2_stocks(
    tickers=['AAPL', 'MSFT', 'GOOGL'],
    min_score=70
)

# Get stage details
stage_info = pre_filter.get_stage_info('AAPL')
```

---

### 1.7 `etf_data_collector.py`
**Purpose**: ETF-specific data collection and analysis

**Key Classes**:
- `ETFDataCollector`: ETF data orchestrator
- `ETFHoldingsCollector`: Holdings collection
- `ETFMetricsCalculator`: TER, AUM, tracking error

**Core Features**:
- ETF ticker discovery (KRX, KOFIA)
- Holdings data collection
- Expense ratio (TER) tracking
- AUM (Assets Under Management) monitoring
- Underlying asset analysis

**Usage**:
```python
from modules.etf_data_collector import ETFDataCollector

etf_collector = ETFDataCollector(db)

# Collect ETF data
etf_collector.collect_etf_data(
    tickers=['KODEX200', 'TIGER200'],
    include_holdings=True
)

# Get ETF holdings
holdings = etf_collector.get_etf_holdings('KODEX200')
```

---

### 1.8 `kr_etf_collector.py`
**Purpose**: Korea-specific ETF data collection

**Key Classes**:
- `KREtfCollector`: Korea ETF orchestrator
- `KOFIAClient`: KOFIA API integration

**Core Features**:
- KOFIA API integration
- KRX ETF metadata collection
- TER data from multiple sources (KOFIA, KRX, Naver)
- Holdings data from fund companies

**Data Sources**:
- KOFIA API (official expense ratios)
- KRX API (listing metadata)
- Naver Finance (fallback TER)
- Fund company websites (holdings)

**Usage**:
```python
from modules.kr_etf_collector import KREtfCollector

kr_etf = KREtfCollector(db)

# Collect Korea ETF data
kr_etf.collect_kr_etf_data(
    tickers=['069500', '102110'],  # KODEX200, TIGER200
    include_holdings=True
)
```

---

### 1.9 `portfolio_allocator.py`
**Purpose**: Multi-region portfolio allocation

**Key Classes**:
- `PortfolioAllocator`: Allocation orchestrator
- `RegionAllocator`: Per-region allocation strategy
- `SectorBalancer`: Sector diversification

**Core Features**:
- Multi-region allocation (KR, US, CN, HK, JP, VN)
- Sector-based diversification
- Risk-adjusted allocation
- Rebalancing recommendations
- Currency exposure management

**Allocation Strategy**:
```yaml
default:
  KR: 40%  # Home bias
  US: 30%  # Largest market
  CN: 10%  # Emerging market
  HK: 10%  # Asia developed
  JP: 5%   # Asia developed
  VN: 5%   # Emerging market
```

**Usage**:
```python
from modules.portfolio_allocator import PortfolioAllocator

allocator = PortfolioAllocator(db, total_capital=100_000_000)

# Get allocation recommendations
allocation = allocator.get_recommended_allocation(
    risk_profile='moderate'
)

# Rebalance portfolio
rebalance_orders = allocator.generate_rebalance_orders()
```

---

### 1.10 `fundamental_data_collector.py`
**Purpose**: Fundamental data collection (financial statements)

**Key Classes**:
- `FundamentalDataCollector`: Fundamental data orchestrator
- `DARTClient`: DART API integration (Korea)

**Core Features**:
- Financial statement collection
- P/E, P/B, ROE, debt ratio tracking
- Earnings surprise analysis
- Dividend tracking
- Multi-source aggregation

**Usage**:
```python
from modules.fundamental_data_collector import FundamentalDataCollector

fund_collector = FundamentalDataCollector(db)

# Collect fundamental data
fund_collector.collect_fundamental_data(
    tickers=['005930', '000660'],
    years=3
)

# Get financial ratios
ratios = fund_collector.get_financial_ratios('005930')
```

---

### 1.11 `stock_metadata_enricher.py`
**Purpose**: Stock metadata enrichment from multiple sources

**Key Classes**:
- `StockMetadataEnricher`: Metadata orchestrator
- `MetadataAggregator`: Multi-source aggregation

**Core Features**:
- Multi-source metadata collection (KIS, yfinance, Naver)
- Market cap, sector, industry enrichment
- Lot size and tick size mapping
- Business description and financial metrics
- Fallback strategies for missing data

**Usage**:
```python
from modules.stock_metadata_enricher import StockMetadataEnricher

enricher = StockMetadataEnricher(db)

# Enrich stock metadata
enricher.enrich_stock_metadata(
    ticker='AAPL',
    region='US'
)

# Bulk enrichment
enricher.bulk_enrich(tickers=['AAPL', 'MSFT', 'GOOGL'])
```

---

## 2. Market Adapters

Region-specific adapters implementing BaseAdapter interface for 6 markets.

### 2.1 `base_adapter.py`
**Purpose**: Abstract base class for all market adapters

**Key Classes**:
- `BaseMarketAdapter`: Abstract adapter interface
- `RegionInjector`: Auto-inject region column

**Core Features**:
- Standard interface for all market adapters
- Automatic region column injection
- Common OHLCV data structure
- Sector normalization to GICS 11
- Trading hours and holiday management

**Required Methods**:
```python
class BaseMarketAdapter:
    def scan_stocks(self, force_refresh=False) -> List[Dict]
    def collect_stock_ohlcv(self, tickers, days=250)
    def get_ticker_details(self, ticker) -> Dict
    def is_market_open(self) -> bool
    def get_trading_hours(self) -> Tuple[time, time]
```

**Region Auto-Injection**:
- All OHLCV data automatically tagged with region (KR, US, CN, HK, JP, VN)
- Unique constraint: (ticker, region, timeframe, date)
- Migration completed 2025-10-15: 691,854 rows

---

### 2.2 `kr_adapter.py`
**Purpose**: Korea market adapter (KOSPI, KOSDAQ)

**Key Classes**:
- `KRAdapter`: Korea market orchestrator

**Core Features**:
- KIS Domestic API integration
- KRX sector mapping → GICS 11
- SPAC detection and exclusion
- Trading hours: 09:00-15:30 KST (no lunch break)
- Holiday management (Korea trading calendar)

**Data Sources**:
- KIS Domestic Stock API (OHLCV)
- KRX API (ticker list, sectors)
- Naver Finance (fallback metadata)

**Usage**:
```python
from modules.market_adapters import KRAdapter

kr_adapter = KRAdapter(db, app_key, app_secret)

# Scan Korea stocks
kr_stocks = kr_adapter.scan_stocks(force_refresh=True)

# Collect OHLCV
kr_adapter.collect_stock_ohlcv(
    tickers=['005930', '000660'],  # Samsung, SK Hynix
    days=250
)
```

---

### 2.3 `us_adapter_kis.py` (Phase 6) ✅ **RECOMMENDED**
**Purpose**: US market adapter with KIS Overseas API (240x faster)

**Key Classes**:
- `USAdapterKIS`: US market orchestrator (KIS API)

**Core Features**:
- KIS Overseas Stock API integration
- 240x faster than Polygon.io (20 req/sec vs 5 req/min)
- ~3,000 tradable stocks (Korean investors only)
- SIC code → GICS 11 sector mapping
- Trading hours: 09:30-16:00 EST

**Markets**:
- NASDAQ (~2,000 stocks)
- NYSE (~800 stocks)
- AMEX (~200 stocks)

**Usage**:
```python
from modules.market_adapters import USAdapterKIS

us_adapter = USAdapterKIS(db, app_key, app_secret)

# Scan US stocks (24-hour cache)
us_stocks = us_adapter.scan_stocks(force_refresh=True)

# Collect OHLCV (250 days, ~750,000 rows, ~10 min)
us_adapter.collect_stock_ohlcv(
    tickers=['AAPL', 'MSFT', 'GOOGL'],
    days=250
)
```

**Performance**:
- Ticker scan: ~3 min (~3,000 stocks)
- OHLCV collection: ~5 min (250 days × 3,000 stocks)
- Total deployment: ~10 min

---

### 2.4 `us_adapter.py` (Legacy)
**Purpose**: US market adapter with Polygon.io API

**Note**: ⚠️ **Deprecated in favor of USAdapterKIS (Phase 6)**

**Limitations**:
- 5 req/min rate limit (free tier)
- 240x slower than KIS API
- Requires separate Polygon.io API key
- All US stocks (~8,000), including non-tradable for Korean investors

---

### 2.5 `cn_adapter_kis.py` (Phase 6) ✅ **RECOMMENDED**
**Purpose**: China market adapter with KIS Overseas API (13x faster)

**Key Classes**:
- `CNAdapterKIS`: China market orchestrator (KIS API)

**Core Features**:
- KIS Overseas Stock API integration
- 13x faster than AkShare (20 req/sec vs 1.5 req/sec)
- Shanghai-Hong Kong Stock Connect (선강통) stocks only
- Shenzhen-Hong Kong Stock Connect (후강통) stocks only
- CSRC sector → GICS 11 mapping

**Markets**:
- Shanghai Stock Exchange (SSE) - 선강통 A-shares
- Shenzhen Stock Exchange (SZSE) - 후강통 A-shares
- ~300-500 tradable stocks (Korean investors)

**Trading Hours**: 09:30-11:30, 13:00-15:00 CST (lunch break)

**Usage**:
```python
from modules.market_adapters import CNAdapterKIS

cn_adapter = CNAdapterKIS(db, app_key, app_secret)

# Scan China stocks (24-hour cache)
cn_stocks = cn_adapter.scan_stocks(force_refresh=True)

# Collect OHLCV
cn_adapter.collect_stock_ohlcv(
    tickers=['600519', '000858'],  # Moutai, Wuliangye
    days=250
)
```

---

### 2.6 `cn_adapter.py` (Legacy)
**Purpose**: China market adapter with AkShare + yfinance

**Note**: ⚠️ **Deprecated in favor of CNAdapterKIS (Phase 6)**

**Limitations**:
- 1.5 req/sec rate limit (self-imposed)
- 13x slower than KIS API
- No API key required (open-source)
- All A-shares (~4,000+), including non-tradable for Korean investors

---

### 2.7 `hk_adapter_kis.py` (Phase 6) ✅ **RECOMMENDED**
**Purpose**: Hong Kong market adapter with KIS Overseas API (20x faster)

**Key Classes**:
- `HKAdapterKIS`: Hong Kong market orchestrator (KIS API)

**Core Features**:
- KIS Overseas Stock API integration
- 20x faster than yfinance (20 req/sec vs 1.0 req/sec)
- ~500-1,000 tradable stocks (Korean investors)
- Industry code → GICS 11 mapping

**Markets**:
- Hong Kong Stock Exchange (HKEX)

**Trading Hours**: 09:30-12:00, 13:00-16:00 HKT (lunch break)

**Usage**:
```python
from modules.market_adapters import HKAdapterKIS

hk_adapter = HKAdapterKIS(db, app_key, app_secret)

# Scan Hong Kong stocks
hk_stocks = hk_adapter.scan_stocks(force_refresh=True)

# Collect OHLCV
hk_adapter.collect_stock_ohlcv(
    tickers=['0700', '9988'],  # Tencent, Alibaba
    days=250
)
```

---

### 2.8 `hk_adapter.py` (Legacy)
**Purpose**: Hong Kong market adapter with yfinance

**Note**: ⚠️ **Deprecated in favor of HKAdapterKIS (Phase 6)**

---

### 2.9 `jp_adapter_kis.py` (Phase 6) ✅ **RECOMMENDED**
**Purpose**: Japan market adapter with KIS Overseas API (20x faster)

**Key Classes**:
- `JPAdapterKIS`: Japan market orchestrator (KIS API)

**Core Features**:
- KIS Overseas Stock API integration
- 20x faster than yfinance (20 req/sec vs 1.0 req/sec)
- ~500-1,000 tradable stocks (Korean investors)
- TSE 33 sectors → GICS 11 mapping

**Markets**:
- Tokyo Stock Exchange (TSE)

**Trading Hours**: 09:00-11:30, 12:30-15:00 JST (lunch break)

**Usage**:
```python
from modules.market_adapters import JPAdapterKIS

jp_adapter = JPAdapterKIS(db, app_key, app_secret)

# Scan Japan stocks
jp_stocks = jp_adapter.scan_stocks(force_refresh=True)

# Collect OHLCV
jp_adapter.collect_stock_ohlcv(
    tickers=['7203', '9984'],  # Toyota, SoftBank
    days=250
)
```

---

### 2.10 `jp_adapter.py` (Legacy)
**Purpose**: Japan market adapter with yfinance

**Note**: ⚠️ **Deprecated in favor of JPAdapterKIS (Phase 6)**

---

### 2.11 `vn_adapter_kis.py` (Phase 6) ✅ **RECOMMENDED**
**Purpose**: Vietnam market adapter with KIS Overseas API (20x faster)

**Key Classes**:
- `VNAdapterKIS`: Vietnam market orchestrator (KIS API)

**Core Features**:
- KIS Overseas Stock API integration
- 20x faster than yfinance (20 req/sec vs 1.0 req/sec)
- ~100-300 tradable stocks (Korean investors)
- VN30 index tracking (30 major Vietnamese stocks)
- ICB sector → GICS 11 mapping

**Markets**:
- Ho Chi Minh Stock Exchange (HOSE)
- Hanoi Stock Exchange (HNX)

**Trading Hours**: 09:00-11:30, 13:00-15:00 ICT (lunch break)

**Usage**:
```python
from modules.market_adapters import VNAdapterKIS

vn_adapter = VNAdapterKIS(db, app_key, app_secret)

# Scan Vietnam stocks
vn_stocks = vn_adapter.scan_stocks(force_refresh=True)

# Collect OHLCV
vn_adapter.collect_stock_ohlcv(
    tickers=['VCB', 'VHM'],  # Vietcombank, Vinhomes
    days=250
)
```

---

### 2.12 `vn_adapter.py` (Legacy)
**Purpose**: Vietnam market adapter with yfinance

**Note**: ⚠️ **Deprecated in favor of VNAdapterKIS (Phase 6)**

---

### 2.13 Sector Mappers & Validators

**Purpose**: Common utilities for all market adapters

**Modules**:
- `sector_mappers/base_mapper.py`: Base sector mapping interface
- `sector_mappers/gics_mapper.py`: GICS 11 sector standardization
- `validators/ticker_validator.py`: Multi-region ticker format validation
- `calendars/market_calendar.py`: Trading hours and holiday management

**Usage**:
```python
from modules.market_adapters.sector_mappers import GICSMapper
from modules.market_adapters.validators import TickerValidator
from modules.market_adapters.calendars import MarketCalendar

# Sector mapping
gics = GICSMapper()
sector = gics.map_to_gics('Technology')  # → 'Information Technology'

# Ticker validation
validator = TickerValidator()
is_valid = validator.validate('AAPL', region='US')  # → True

# Market calendar
calendar = MarketCalendar('US')
is_open = calendar.is_market_open()  # → True/False
```

---

## 3. API Clients

Low-level API wrappers for external data sources.

### 3.1 `base_kis_api.py`
**Purpose**: Base KIS API client with OAuth 2.0 and rate limiting

**Key Classes**:
- `BaseKISAPI`: Base KIS client
- `TokenManager`: OAuth token management
- `RateLimiter`: Request rate limiting (20 req/sec)

**Core Features**:
- OAuth 2.0 authentication with 24-hour token caching
- Exponential backoff retry logic
- Rate limiting (20 req/sec, 1,000 req/min)
- Error handling and logging

**Usage**:
```python
from modules.api_clients.base_kis_api import BaseKISAPI

kis_api = BaseKISAPI(app_key, app_secret)

# Make API request
response = kis_api.request(
    method='GET',
    endpoint='/uapi/domestic-stock/v1/quotations/inquire-price',
    params={'FID_COND_MRKT_DIV_CODE': 'J', 'FID_INPUT_ISCD': '005930'}
)
```

---

### 3.2 `kis_domestic_stock_api.py`
**Purpose**: KIS Domestic Stock API client (Korea)

**Key Classes**:
- `KISDomesticStockAPI`: Korea stock API client

**Core Features**:
- OHLCV data collection
- Real-time price quotes
- Order execution (buy/sell)
- Portfolio balance queries
- Trading hours and holiday calendar

**API Endpoints**:
- `/uapi/domestic-stock/v1/quotations/inquire-daily-price`: OHLCV
- `/uapi/domestic-stock/v1/quotations/inquire-price`: Real-time quote
- `/uapi/domestic-stock/v1/trading/order-cash`: Order execution
- `/uapi/domestic-stock/v1/trading/inquire-balance`: Portfolio balance

**Usage**:
```python
from modules.api_clients import KISDomesticStockAPI

domestic_api = KISDomesticStockAPI(app_key, app_secret)

# Get OHLCV data
ohlcv = domestic_api.get_daily_price(
    ticker='005930',
    start_date='20240101',
    end_date='20241018'
)

# Get real-time quote
quote = domestic_api.get_current_price('005930')

# Place order
order = domestic_api.place_order(
    ticker='005930',
    quantity=10,
    price=70000,
    order_type='buy'
)
```

---

### 3.3 `kis_overseas_stock_api.py` (Phase 6)
**Purpose**: KIS Overseas Stock API client (US, HK, CN, JP, VN)

**Key Classes**:
- `KISOverseasStockAPI`: Overseas stock API client

**Core Features**:
- Multi-region support (5 markets)
- Master file integration (ticker lists)
- OHLCV data collection
- Real-time price quotes
- Order execution (buy/sell)

**Supported Markets**:
```yaml
NASD: NASDAQ
NYSE: New York Stock Exchange
AMEX: American Stock Exchange
SEHK: Hong Kong Stock Exchange
SHAA: Shanghai A-shares (선강통)
SZAA: Shenzhen A-shares (후강통)
TKSE: Tokyo Stock Exchange
HASE: Ho Chi Minh Stock Exchange
VNSE: Hanoi Stock Exchange
```

**API Endpoints**:
- `/uapi/overseas-price/v1/quotations/dailyprice`: OHLCV
- `/uapi/overseas-price/v1/quotations/price`: Real-time quote
- `/uapi/overseas-stock/v1/trading/order`: Order execution
- `/uapi/overseas-stock/v1/trading/inquire-balance`: Portfolio balance

**Usage**:
```python
from modules.api_clients import KISOverseasStockAPI

overseas_api = KISOverseasStockAPI(app_key, app_secret)

# Get US OHLCV data
us_ohlcv = overseas_api.get_daily_price(
    ticker='AAPL',
    exchange='NASD',
    start_date='20240101',
    end_date='20241018'
)

# Get Hong Kong quote
hk_quote = overseas_api.get_current_price('0700', exchange='SEHK')

# Place order
order = overseas_api.place_order(
    ticker='AAPL',
    exchange='NASD',
    quantity=10,
    price=150.00,
    order_type='buy'
)
```

---

### 3.4 `kis_etf_api.py`
**Purpose**: KIS ETF API client (Korea)

**Key Classes**:
- `KISEtfAPI`: ETF API client

**Core Features**:
- ETF ticker list
- ETF OHLCV data
- Holdings data
- NAV tracking

**Usage**:
```python
from modules.api_clients import KISEtfAPI

etf_api = KISEtfAPI(app_key, app_secret)

# Get ETF list
etf_list = etf_api.get_etf_list()

# Get ETF OHLCV
etf_ohlcv = etf_api.get_etf_daily_price('069500')  # KODEX200

# Get ETF holdings
holdings = etf_api.get_etf_holdings('069500')
```

---

### 3.5 `kis_master_file_manager.py` (Phase 6)
**Purpose**: KIS master file downloader and parser

**Key Classes**:
- `KISMasterFileManager`: Master file orchestrator
- `MasterFileParser`: Binary file parser

**Core Features**:
- Automatic master file download from KIS FTP
- Binary file parsing (fixed-width format)
- 24-hour cache with auto-refresh
- Multi-region support (US, HK, CN, JP, VN)

**Master File URLs**:
```yaml
NASD: https://new.real.download.dws.co.kr/common/master/nasdaqlst.cod
NYSE: https://new.real.download.dws.co.kr/common/master/nyselst.cod
AMEX: https://new.real.download.dws.co.kr/common/master/amexlst.cod
SEHK: https://new.real.download.dws.co.kr/common/master/hkexlst.cod
SHAA: https://new.real.download.dws.co.kr/common/master/shanghailstALL.cod
SZAA: https://new.real.download.dws.co.kr/common/master/shenzhenlstALL.cod
TKSE: https://new.real.download.dws.co.kr/common/master/tokyolst.cod
HASE: https://new.real.download.dws.co.kr/common/master/vnlst.cod
```

**Usage**:
```python
from modules.api_clients import KISMasterFileManager

master_mgr = KISMasterFileManager()

# Download and parse NASDAQ master file
nasdaq_stocks = master_mgr.get_master_data('NASD', force_refresh=True)

# Auto-refresh if cache expired (24-hour TTL)
nyse_stocks = master_mgr.get_master_data('NYSE')  # Uses cache if fresh
```

---

### 3.6 `polygon_api.py` (Legacy)
**Purpose**: Polygon.io API client (US stocks)

**Note**: ⚠️ **Deprecated in favor of KISOverseasStockAPI (Phase 6)**

**Limitations**:
- 5 req/min rate limit (free tier)
- Requires separate Polygon.io API key
- 240x slower than KIS API

---

### 3.7 `akshare_api.py` (Legacy)
**Purpose**: AkShare API client (China stocks)

**Note**: ⚠️ **Deprecated in favor of KISOverseasStockAPI (Phase 6)**

**Limitations**:
- 1.5 req/sec rate limit (self-imposed)
- No API key required (open-source)
- 13x slower than KIS API

---

### 3.8 `yfinance_api.py` (Fallback)
**Purpose**: yfinance API client (Global stocks)

**Note**: Used as fallback when KIS API unavailable

**Core Features**:
- Global stock coverage
- No API key required
- 1.0 req/sec rate limit (self-imposed)
- Free and open-source

**Usage**:
```python
from modules.api_clients import YFinanceAPI

yf_api = YFinanceAPI()

# Get OHLCV data
ohlcv = yf_api.get_daily_price('AAPL', period='1y')

# Get quote
quote = yf_api.get_current_price('AAPL')
```

---

### 3.9 `pykrx_api.py`
**Purpose**: PyKRX API client (Korea KRX data)

**Key Classes**:
- `PyKRXAPI`: PyKRX wrapper

**Core Features**:
- KRX ticker list
- Market cap and trading volume
- Sector classification
- Trading halt status

**Usage**:
```python
from modules.api_clients import PyKRXAPI

pykrx_api = PyKRXAPI()

# Get ticker list
tickers = pykrx_api.get_stock_list('KOSPI')

# Get market cap
market_cap = pykrx_api.get_market_cap('005930')
```

---

### 3.10 `krx_data_api.py`
**Purpose**: KRX Open API client (Korea)

**Key Classes**:
- `KRXDataAPI`: KRX API wrapper

**Core Features**:
- Official KRX data
- Sector classification
- Trading statistics
- Market indices

**Usage**:
```python
from modules.api_clients import KRXDataAPI

krx_api = KRXDataAPI()

# Get sector data
sector_data = krx_api.get_sector_data('005930')
```

---

### 3.11 `krx_etf_api.py`
**Purpose**: KRX ETF API client (Korea)

**Key Classes**:
- `KRXEtfAPI`: KRX ETF wrapper

**Core Features**:
- ETF ticker list
- ETF metadata
- NAV tracking
- Holdings data

---

### 3.12 `dart_api_client.py`
**Purpose**: DART API client (Korea financial statements)

**Key Classes**:
- `DARTAPIClient`: DART wrapper

**Core Features**:
- Financial statement collection
- Earnings reports
- Corporate disclosures
- Corporate ID mapping

**Usage**:
```python
from modules.dart_api_client import DARTAPIClient

dart_api = DARTAPIClient(api_key)

# Get financial statements
statements = dart_api.get_financial_statements('00126380')  # Samsung
```

---

### 3.13-3.14 Additional API Clients

**Modules**:
- `modules/api_clients/__init__.py`: API client registry

---

## 4. Analysis Engines

Advanced analysis modules for scoring, pattern recognition, and sentiment analysis.

### 4.1 `layered_scoring_engine.py`
**Purpose**: 100-point scoring system (3-layer analysis)

**Key Classes**:
- `LayeredScoringEngine`: Main scoring orchestrator
- `Layer1Analyzer`: Macro analysis (25 points)
- `Layer2Analyzer`: Structural analysis (45 points)
- `Layer3Analyzer`: Micro analysis (30 points)

**3-Layer Architecture**:
```yaml
Layer 1 - Macro (25 points):
  MarketRegimeModule: 5 points     # Bull/sideways/bear
  VolumeProfileModule: 10 points   # Volume profile
  PriceActionModule: 10 points     # Price action strength

Layer 2 - Structural (45 points):
  StageAnalysisModule: 15 points   # Weinstein Stage 2
  MovingAverageModule: 15 points   # MA alignment
  RelativeStrengthModule: 15 points # Sector/market RS

Layer 3 - Micro (30 points):
  PatternRecognitionModule: 10 points # Chart patterns
  VolumeSpikeModule: 10 points        # Volume breakout
  MomentumModule: 10 points           # RSI, MACD momentum
```

**Scoring Thresholds**:
- **70+ points**: BUY recommendation
- **50-70 points**: WATCH list
- **<50 points**: AVOID

**Usage**:
```python
from modules.layered_scoring_engine import LayeredScoringEngine

engine = LayeredScoringEngine(db)

# Calculate score
score = engine.calculate_score(
    ticker='AAPL',
    region='US'
)

# Get layer breakdowns
layer_scores = engine.get_layer_breakdown('AAPL')
```

---

### 4.2 `integrated_scoring_system.py`
**Purpose**: Unified scoring system integrating all analysis modules

**Key Classes**:
- `IntegratedScoringSystem`: Main coordinator
- `ScoreAggregator`: Score aggregation logic

**Core Features**:
- Integrates LayeredScoringEngine
- Combines technical + fundamental + sentiment
- Adaptive thresholds based on market conditions
- Risk-adjusted scoring

**Usage**:
```python
from modules.integrated_scoring_system import IntegratedScoringSystem

scoring = IntegratedScoringSystem(db)

# Get integrated score
score = scoring.get_integrated_score(
    ticker='AAPL',
    region='US',
    include_fundamental=True,
    include_sentiment=True
)
```

---

### 4.3 `basic_scoring_modules.py`
**Purpose**: Technical indicator modules for LayeredScoringEngine

**Key Modules**:
- `MarketRegimeModule`: Bull/sideways/bear detection
- `VolumeProfileModule`: Volume profile analysis
- `PriceActionModule`: Price action strength
- `StageAnalysisModule`: Weinstein Stage 2
- `MovingAverageModule`: MA alignment (5/20/60/120/200)
- `RelativeStrengthModule`: Sector/market relative strength
- `PatternRecognitionModule`: Chart patterns
- `VolumeSpikeModule`: Volume breakout detection
- `MomentumModule`: RSI, MACD momentum

**Usage**:
```python
from modules.basic_scoring_modules import StageAnalysisModule

stage_analyzer = StageAnalysisModule(db)

# Detect Weinstein Stage
stage_score = stage_analyzer.calculate_score(
    ticker='AAPL',
    region='US'
)
```

---

### 4.4 `adaptive_scoring_config.py`
**Purpose**: Adaptive scoring thresholds based on market conditions

**Key Classes**:
- `AdaptiveScoringConfig`: Dynamic threshold manager

**Core Features**:
- Market regime detection (bull/bear/sideways)
- Adaptive threshold adjustment
- Volatility-based scoring
- Sector rotation awareness

**Threshold Adjustments**:
```yaml
bull_market:
  min_score: 70 → 65  # Easier entry
  stop_loss: 7% → 5%  # Tighter stop

bear_market:
  min_score: 70 → 75  # Harder entry
  stop_loss: 7% → 10% # Wider stop

sideways_market:
  min_score: 70       # No change
  stop_loss: 7%       # No change
```

**Usage**:
```python
from modules.adaptive_scoring_config import AdaptiveScoringConfig

config = AdaptiveScoringConfig(db)

# Get adaptive thresholds
thresholds = config.get_current_thresholds(region='US')

# Adjust based on market regime
config.update_market_regime('bull')
```

---

### 4.5 `stock_gpt_analyzer.py`
**Purpose**: GPT-4 powered chart pattern analysis

**Key Classes**:
- `StockGPTAnalyzer`: GPT-4 chart analyzer
- `ChartImageGenerator`: Generate chart images
- `PatternDetector`: AI pattern recognition

**Core Features**:
- GPT-4 Vision API integration
- Chart image generation (mplfinance)
- Pattern recognition (Cup & Handle, VCP, Triangle, etc.)
- Win rate prediction for Kelly Calculator
- Multi-timeframe analysis (daily, weekly, monthly)

**Supported Patterns**:
- Cup and Handle
- VCP (Volatility Contraction Pattern)
- Triangle Breakout
- Double Bottom
- Head and Shoulders
- Ascending Triangle
- Descending Triangle

**Usage**:
```python
from modules.stock_gpt_analyzer import StockGPTAnalyzer

gpt_analyzer = StockGPTAnalyzer(db, openai_api_key)

# Analyze chart pattern
pattern = gpt_analyzer.analyze_chart(
    ticker='AAPL',
    region='US',
    timeframe='daily'
)

# Get pattern details
print(pattern['pattern_name'])  # "Cup and Handle"
print(pattern['confidence'])    # 0.85
print(pattern['win_rate'])      # 0.62
```

---

### 4.6 `kelly_calculator.py`
**Purpose**: Kelly formula position sizing

**Key Classes**:
- `KellyCalculator`: Kelly formula calculator

**Core Features**:
- Pattern-based win rate mapping
- Kelly formula: (WinRate × AvgWin/Loss - (1 - WinRate)) / AvgWin/Loss
- Half Kelly adjustment (0.5 multiplier)
- Max position limit (15% of capital)

**Pattern Win Rates** (from backtesting):
```yaml
Stage 2 Breakout:
  win_rate: 0.65
  avg_win_loss_ratio: 2.0

VCP Pattern:
  win_rate: 0.62
  avg_win_loss_ratio: 2.1

Cup-and-Handle:
  win_rate: 0.58
  avg_win_loss_ratio: 1.8

Triangle Breakout:
  win_rate: 0.55
  avg_win_loss_ratio: 1.6
```

**Usage**:
```python
from modules.kelly_calculator import KellyCalculator

kelly = KellyCalculator()

# Calculate position size
position_size = kelly.calculate_position_size(
    pattern='Stage 2 Breakout',
    win_rate=0.65,
    avg_win_loss_ratio=2.0,
    total_capital=100_000_000
)

# Output: 15% position (max limit applied)
```

---

### 4.7 `stock_kelly_calculator.py`
**Purpose**: Stock-specific Kelly calculator with GPT integration

**Key Classes**:
- `StockKellyCalculator`: Stock Kelly orchestrator

**Core Features**:
- GPT-4 pattern detection integration
- Dynamic win rate from GPT confidence
- Risk-adjusted position sizing
- Multi-pattern support

**Usage**:
```python
from modules.stock_kelly_calculator import StockKellyCalculator

stock_kelly = StockKellyCalculator(db, gpt_analyzer)

# Calculate position size with GPT pattern detection
position = stock_kelly.calculate_position_size(
    ticker='AAPL',
    region='US',
    total_capital=100_000_000
)
```

---

### 4.8 `stock_sentiment.py`
**Purpose**: Market sentiment analysis

**Key Classes**:
- `StockSentiment`: Sentiment analyzer
- `VIXTracker`: VIX (Fear & Greed Index) tracking
- `ForeignInstitutionTracker`: Foreign/institution trading analysis

**Core Features**:
- VIX tracking (CNN Fear & Greed Index)
- Foreign net buying/selling (Korea KIS API)
- Institution net buying/selling (Korea KIS API)
- Sector rotation analysis
- Market breadth indicators

**Sentiment Signals**:
```yaml
strong_buy:
  vix: < 20 (low fear)
  foreign_buying: 3+ consecutive days, >100M KRW
  institution_buying: 3+ consecutive days, >100M KRW

strong_sell:
  vix: > 40 (extreme fear)
  foreign_selling: 3+ consecutive days, >100M KRW
  institution_selling: 3+ consecutive days, >100M KRW
```

**Usage**:
```python
from modules.stock_sentiment import StockSentiment

sentiment = StockSentiment(db)

# Get sentiment score
score = sentiment.get_sentiment_score(
    ticker='005930',
    region='KR'
)

# Get VIX
vix = sentiment.get_vix()

# Get foreign/institution trading
foreign = sentiment.get_foreign_trading('005930')
institution = sentiment.get_institution_trading('005930')
```

---

### 4.9 `predictive_analysis.py`
**Purpose**: Predictive analytics and machine learning

**Key Classes**:
- `PredictiveAnalyzer`: ML model orchestrator

**Core Features**:
- Price prediction (LSTM, Prophet)
- Trend prediction
- Volatility forecasting
- Pattern recognition (ML-based)

**Usage**:
```python
from modules.predictive_analysis import PredictiveAnalyzer

predictor = PredictiveAnalyzer(db)

# Predict price
prediction = predictor.predict_price(
    ticker='AAPL',
    region='US',
    horizon_days=30
)
```

---

### 4.10 `metrics_collector.py`
**Purpose**: Performance metrics collection and tracking

**Key Classes**:
- `MetricsCollector`: Metrics orchestrator

**Core Features**:
- Trade success rate tracking
- Sharpe ratio calculation
- Max drawdown tracking
- Win rate by pattern
- Portfolio performance metrics

**Usage**:
```python
from modules.metrics_collector import MetricsCollector

metrics = MetricsCollector(db)

# Get performance metrics
performance = metrics.get_performance_metrics(
    start_date='2024-01-01',
    end_date='2024-10-18'
)

# Get win rate by pattern
pattern_stats = metrics.get_pattern_statistics()
```

---

## 5. Data Processing

Parsers, mappers, and validators for data transformation and normalization.

### 5.1 `parsers/stock_parser.py`
**Purpose**: Generic stock data parser

**Key Classes**:
- `StockParser`: Base parser

**Core Features**:
- OHLCV data parsing
- Ticker normalization
- Date parsing and validation

---

### 5.2 `parsers/us_stock_parser.py`
**Purpose**: US-specific stock data parser

**Key Classes**:
- `USStockParser`: US parser

**Core Features**:
- SIC code → GICS 11 sector mapping
- Ticker format validation (1-5 uppercase letters)
- Date parsing (US market holidays)

**Usage**:
```python
from modules.parsers import USStockParser

us_parser = USStockParser()

# Parse ticker
ticker = us_parser.normalize_ticker('aapl')  # → 'AAPL'

# Map sector
sector = us_parser.map_sector('Technology')  # → 'Information Technology'
```

---

### 5.3 `parsers/cn_stock_parser.py`
**Purpose**: China-specific stock data parser

**Key Classes**:
- `CNStockParser`: China parser

**Core Features**:
- CSRC 62 industry → GICS 11 sector mapping
- Ticker format validation (6-digit with .SS/.SZ suffix)
- Shanghai/Shenzhen exchange detection

**Usage**:
```python
from modules.parsers import CNStockParser

cn_parser = CNStockParser()

# Parse ticker
ticker = cn_parser.normalize_ticker('600519')  # → '600519.SS' (Shanghai)

# Map sector
sector = cn_parser.map_sector('白酒')  # → 'Consumer Staples'
```

---

### 5.4 `parsers/hk_stock_parser.py`
**Purpose**: Hong Kong-specific stock data parser

**Key Classes**:
- `HKStockParser`: Hong Kong parser

**Core Features**:
- Industry code → GICS 11 sector mapping
- Ticker format validation (4-5 digit with .HK suffix)

**Usage**:
```python
from modules.parsers import HKStockParser

hk_parser = HKStockParser()

# Parse ticker
ticker = hk_parser.normalize_ticker('700')  # → '0700.HK' (Tencent)

# Map sector
sector = hk_parser.map_sector('Internet')  # → 'Communication Services'
```

---

### 5.5 `parsers/jp_stock_parser.py`
**Purpose**: Japan-specific stock data parser

**Key Classes**:
- `JPStockParser`: Japan parser

**Core Features**:
- TSE 33 sectors → GICS 11 sector mapping
- Ticker format validation (4-digit numeric)

**Usage**:
```python
from modules.parsers import JPStockParser

jp_parser = JPStockParser()

# Parse ticker
ticker = jp_parser.normalize_ticker('7203')  # → '7203' (Toyota)

# Map sector
sector = jp_parser.map_sector('自動車')  # → 'Consumer Discretionary'
```

---

### 5.6 `parsers/vn_stock_parser.py`
**Purpose**: Vietnam-specific stock data parser

**Key Classes**:
- `VNStockParser`: Vietnam parser

**Core Features**:
- ICB sector → GICS 11 sector mapping
- Ticker format validation (3-letter uppercase)
- HOSE/HNX exchange detection

**Usage**:
```python
from modules.parsers import VNStockParser

vn_parser = VNStockParser()

# Parse ticker
ticker = vn_parser.normalize_ticker('vcb')  # → 'VCB' (Vietcombank)

# Map sector
sector = vn_parser.map_sector('Banks')  # → 'Financials'
```

---

### 5.7 `parsers/etf_parser.py`
**Purpose**: ETF-specific data parser

**Key Classes**:
- `ETFParser`: ETF parser

**Core Features**:
- ETF metadata parsing
- Holdings data parsing
- TER (expense ratio) parsing
- AUM parsing

**Usage**:
```python
from modules.parsers import ETFParser

etf_parser = ETFParser()

# Parse ETF data
etf_data = etf_parser.parse_etf_metadata('069500')  # KODEX200

# Parse holdings
holdings = etf_parser.parse_holdings_data('069500')
```

---

### 5.8-5.14 Additional Parsers & Mappers

**Modules**:
- `parsers/__init__.py`: Parser registry
- `mappers/kr_corporate_id_mapper.py`: Korea corporate ID mapping (ticker ↔ DART ID)
- `corporate_id_mapper.py`: Multi-region corporate ID mapping

---

## 6. Backtesting Framework

Comprehensive backtesting and optimization framework.

### 6.1 `backtesting/backtest_engine.py`
**Purpose**: Main backtesting engine

**Key Classes**:
- `BacktestEngine`: Backtesting orchestrator
- `SimulatedBroker`: Order execution simulator

**Core Features**:
- Historical data simulation
- Order execution with slippage and commissions
- Portfolio tracking
- Performance metrics (Sharpe, drawdown, win rate)

**Usage**:
```python
from modules.backtesting import BacktestEngine

engine = BacktestEngine(db)

# Run backtest
results = engine.run_backtest(
    strategy='Weinstein Stage 2',
    start_date='2023-01-01',
    end_date='2024-10-18',
    initial_capital=100_000_000,
    region='US'
)

# Get metrics
print(results['sharpe_ratio'])
print(results['max_drawdown'])
print(results['win_rate'])
```

---

### 6.2 `backtesting/parameter_optimizer.py`
**Purpose**: Parameter optimization with grid search

**Key Classes**:
- `ParameterOptimizer`: Optimization orchestrator
- `GridSearchRunner`: Grid search implementation

**Core Features**:
- Grid search optimization
- Walk-forward analysis
- Overfitting detection
- Parameter sensitivity analysis

**Usage**:
```python
from modules.backtesting import ParameterOptimizer

optimizer = ParameterOptimizer(db)

# Optimize parameters
best_params = optimizer.optimize(
    strategy='Weinstein Stage 2',
    param_grid={
        'min_score': [65, 70, 75],
        'stop_loss': [0.05, 0.07, 0.10],
        'profit_target': [0.15, 0.20, 0.25]
    },
    metric='sharpe_ratio'
)
```

---

### 6.3 `backtesting/grid_search_optimizer.py`
**Purpose**: Grid search implementation

**Key Classes**:
- `GridSearchOptimizer`: Grid search runner

**Core Features**:
- Parallel execution
- Progress tracking
- Result caching

---

### 6.4 `backtesting/performance_analyzer.py`
**Purpose**: Performance analysis and reporting

**Key Classes**:
- `PerformanceAnalyzer`: Metrics calculator

**Core Features**:
- Sharpe ratio calculation
- Max drawdown calculation
- Win rate by pattern
- Risk-adjusted returns

---

### 6.5 `backtesting/portfolio_simulator.py`
**Purpose**: Portfolio simulation

**Key Classes**:
- `PortfolioSimulator`: Portfolio simulator

**Core Features**:
- Multi-stock portfolio simulation
- Rebalancing logic
- Cash management

---

### 6.6 `backtesting/historical_data_provider.py`
**Purpose**: Historical data provider for backtesting

**Key Classes**:
- `HistoricalDataProvider`: Data provider

**Core Features**:
- Historical OHLCV data retrieval
- Data caching
- Data quality validation

---

### 6.7 `backtesting/backtest_reporter.py`
**Purpose**: Backtest result reporting

**Key Classes**:
- `BacktestReporter`: Report generator

**Core Features**:
- Performance reports
- Trade logs
- Equity curves
- Drawdown charts

---

### 6.8 `backtesting/strategy_runner.py`
**Purpose**: Strategy execution framework

**Key Classes**:
- `StrategyRunner`: Strategy executor

**Core Features**:
- Strategy plugin system
- Signal generation
- Order generation

---

### 6.9 `backtesting/transaction_cost_model.py`
**Purpose**: Transaction cost modeling

**Key Classes**:
- `TransactionCostModel`: Cost calculator

**Core Features**:
- Commission calculation
- Slippage modeling
- Tax calculation (Korea: 0.23% transaction tax)

---

### 6.10 `backtesting/backtest_config.py`
**Purpose**: Backtesting configuration

**Key Classes**:
- `BacktestConfig`: Configuration manager

**Core Features**:
- Strategy parameters
- Risk parameters
- Execution parameters

---

### 6.11 `backtesting/__init__.py`
**Purpose**: Backtesting module registry

---

## 7. Utilities & Infrastructure

Database, logging, alerts, recovery, and monitoring utilities.

### 7.1 `db_manager_sqlite.py`
**Purpose**: SQLite database manager

**Key Classes**:
- `SQLiteDatabaseManager`: Database orchestrator

**Core Features**:
- Database initialization
- CRUD operations
- Transaction management
- Data retention policy (250 days)
- Backup and restore
- VACUUM optimization

**Database Tables**:
```
tickers             Stock/ETF metadata
ohlcv_data          250-day OHLCV with technical indicators
technical_analysis  LayeredScoringEngine results
trades              Order execution history
portfolio           Current positions
kelly_sizing        Pattern-based position sizing
kis_api_logs        API request/response logs
```

**Usage**:
```python
from modules.db_manager_sqlite import SQLiteDatabaseManager

db = SQLiteDatabaseManager()

# Insert OHLCV data
db.insert_ohlcv_data(ticker='AAPL', region='US', date='2024-10-18', ...)

# Query data
data = db.query('SELECT * FROM ohlcv_data WHERE ticker=? AND region=?', ('AAPL', 'US'))

# Cleanup old data
db.cleanup_old_ohlcv_data(retention_days=250)

# Backup database
db.backup_database('data/backups/backup_20241018.db')
```

---

### 7.2 `auto_recovery_system.py`
**Purpose**: Automated error detection and recovery

**Key Classes**:
- `AutoRecoverySystem`: Recovery orchestrator
- `ErrorDetector`: Error pattern detection
- `RecoveryAction`: Recovery action executor

**Core Features**:
- API error recovery (reconnect, rate limit, auth)
- Database error recovery (lock timeout, corruption, rollback)
- Trading error recovery (order rejection, tick size, balance)
- Automatic retry with exponential backoff

**Recovery Actions**:
```yaml
API_RECONNECT:        Reconnect to KIS API
API_RATE_LIMIT:       Wait and retry
ORDER_VALIDATION:     Re-validate order parameters
TICK_SIZE_ADJUSTMENT: Adjust price to nearest tick
DATABASE_REPAIR:      Repair corrupted database
PORTFOLIO_SYNC:       Re-sync portfolio with KIS API
```

**Usage**:
```python
from modules.auto_recovery_system import AutoRecoverySystem

recovery = AutoRecoverySystem(db)

# Register error handler
recovery.register_handler('API_TIMEOUT', recovery.handle_api_timeout)

# Trigger recovery
recovery.recover_from_error('API_TIMEOUT', context={'ticker': 'AAPL'})
```

---

### 7.3 `failure_tracker.py`
**Purpose**: Failure tracking and analysis

**Key Classes**:
- `FailureTracker`: Failure logger

**Core Features**:
- Failure logging
- Failure pattern detection
- Failure rate calculation
- Alert generation

**Usage**:
```python
from modules.failure_tracker import FailureTracker

tracker = FailureTracker(db)

# Log failure
tracker.log_failure(
    category='API_ERROR',
    error_code='TIMEOUT',
    details={'ticker': 'AAPL', 'endpoint': '/quotations/inquire-price'}
)

# Get failure rate
rate = tracker.get_failure_rate('API_ERROR', hours=24)
```

---

### 7.4 `alert_system.py`
**Purpose**: Alert and notification system

**Key Classes**:
- `AlertSystem`: Alert orchestrator
- `AlertChannel`: Multi-channel delivery (Email, SMS, Slack)

**Core Features**:
- Multi-channel alerts (Email, SMS, Slack)
- Alert prioritization (critical, warning, info)
- Alert throttling
- Alert history

**Alert Types**:
```yaml
CRITICAL:
  - Trading errors
  - API failures
  - Portfolio sync mismatches

WARNING:
  - Market hours violations
  - Approaching position limits
  - High failure rates

INFO:
  - Successful trades
  - Daily performance summary
  - System health checks
```

**Usage**:
```python
from modules.alert_system import AlertSystem

alerts = AlertSystem()

# Send critical alert
alerts.send_alert(
    level='CRITICAL',
    title='Trading Error',
    message='Order execution failed for AAPL',
    channels=['email', 'slack']
)
```

---

### 7.5 `sns_notification_system.py`
**Purpose**: AWS SNS integration for notifications

**Key Classes**:
- `SNSNotificationSystem`: SNS orchestrator

**Core Features**:
- AWS SNS topic publishing
- Multi-subscriber support
- SMS and email delivery

**Usage**:
```python
from modules.sns_notification_system import SNSNotificationSystem

sns = SNSNotificationSystem(topic_arn='arn:aws:sns:...')

# Send notification
sns.send_notification(
    subject='Trading Alert',
    message='Portfolio value: $100,000'
)
```

---

### 7.6 `stock_utils.py`
**Purpose**: Common utility functions

**Key Functions**:
- `calculate_technical_indicators()`: MA, RSI, MACD, BB, ATR
- `format_price()`: Price formatting with tick size
- `validate_ticker()`: Multi-region ticker validation
- `calculate_position_value()`: Position value calculation

**Usage**:
```python
from modules.stock_utils import calculate_technical_indicators, format_price

# Calculate indicators
data_with_indicators = calculate_technical_indicators(ohlcv_data)

# Format price
formatted_price = format_price(70123, region='KR')  # → 70,120 (nearest 10 KRW tick)
```

---

### 7.7 `blacklist_manager.py`
**Purpose**: Ticker blacklist management

**Key Classes**:
- `BlacklistManager`: Blacklist orchestrator

**Core Features**:
- Blacklist loading from JSON
- Ticker exclusion
- Blacklist updates
- Reason tracking

**Blacklist Categories**:
```yaml
categories:
  - fraud: Accounting fraud, manipulation
  - delisting: Delisting risk
  - halt: Long-term trading halt
  - bankruptcy: Bankruptcy risk
  - regulatory: Regulatory issues
```

**Usage**:
```python
from modules.blacklist_manager import BlacklistManager

blacklist = BlacklistManager()

# Check ticker
is_blacklisted = blacklist.is_blacklisted('AAPL')

# Add to blacklist
blacklist.add_ticker('SCAM', reason='fraud', category='fraud')
```

---

### 7.8 `exchange_rate_manager.py`
**Purpose**: Currency exchange rate management

**Key Classes**:
- `ExchangeRateManager`: Exchange rate orchestrator

**Core Features**:
- Real-time exchange rate fetching
- Multi-currency support (USD, CNY, HKD, JPY, VND)
- Rate caching (24-hour TTL)
- Historical rate tracking

**Supported Currencies**:
```yaml
KRW: Korean Won (base)
USD: US Dollar
CNY: Chinese Yuan
HKD: Hong Kong Dollar
JPY: Japanese Yen
VND: Vietnamese Dong
```

**Usage**:
```python
from modules.exchange_rate_manager import ExchangeRateManager

fx = ExchangeRateManager(db)

# Get exchange rate
usd_krw = fx.get_rate('USD', 'KRW')  # → 1,300.50

# Convert currency
krw_value = fx.convert(100, 'USD', 'KRW')  # → 130,050
```

---

### 7.9 `market_filter_manager.py`
**Purpose**: Market-specific filtering rules

**Key Classes**:
- `MarketFilterManager`: Filter orchestrator

**Core Features**:
- Region-specific filtering rules
- Market cap filters
- Volume filters
- Price filters

**Usage**:
```python
from modules.market_filter_manager import MarketFilterManager

filter_mgr = MarketFilterManager()

# Apply filters
filtered_tickers = filter_mgr.apply_filters(
    tickers=['AAPL', 'MSFT', 'GOOGL'],
    region='US',
    min_market_cap=1e9,
    min_avg_volume=1e5
)
```

---

### 7.10-7.12 Additional Utilities

**Modules**:
- `modules/__init__.py`: Module registry

---

## Module Dependencies

### Core Dependencies
```
pandas >= 2.0.3
numpy >= 1.24.3
pandas-ta >= 0.3.14b0
requests >= 2.31.0
```

### Optional Dependencies
```
openai >= 0.28.1        # GPT-4 chart analysis
matplotlib >= 3.7.0     # Chart visualization
mplfinance >= 0.12.9    # Financial charts
```

---

## Testing Coverage

### Test Statistics (57 test files)
- **Unit Tests**: 30 files (module-level)
- **Integration Tests**: 15 files (multi-module)
- **E2E Tests**: 12 files (full pipeline)

### Adapter Test Coverage
| Adapter | Tests | Coverage | Status |
|---------|-------|----------|--------|
| KR | 15 | 75% | ✅ Pass |
| US (KIS) | 33 | 71.70% | ✅ Pass |
| CN (KIS) | 19 | 82.47% | ✅ Pass |
| HK (KIS) | 15 | 71.70% | ✅ Pass |
| JP (KIS) | 16 | 100% | ✅ Pass |
| VN (KIS) | 17 | 100% | ✅ Pass |

---

## Next Steps

### For Developers
1. Review [PROJECT_INDEX.md](PROJECT_INDEX.md) for navigation
2. Study module interfaces and usage examples
3. Run tests: `pytest tests/test_<module>.py -v`
4. Refer to [API_INTEGRATION_GUIDE.md](API_INTEGRATION_GUIDE.md) for API details

### For Contributors
1. Follow module naming conventions
2. Implement BaseAdapter interface for new markets
3. Add comprehensive docstrings and type hints
4. Write unit tests (target: 80%+ coverage)
5. Update this document with new modules

---

**Last Updated**: 2025-10-18
**Maintained By**: Spock Development Team
