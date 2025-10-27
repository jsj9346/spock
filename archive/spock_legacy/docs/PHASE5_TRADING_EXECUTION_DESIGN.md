# Phase 5: Trading Execution & Scoring System - Architecture Design

**Date**: 2025-10-14
**Status**: Design Phase
**Dependencies**: Phase 1-4 Complete (Global market expansion with 6 markets)

---

## 📋 Executive Summary

Phase 5 transforms Spock from a **data collection & analysis system** into a **complete automated trading system** by integrating proven trading logic from Makenaide (cryptocurrency bot). This phase implements the core trading decision-making and execution engine.

### Key Objectives
1. ✅ **LayeredScoringEngine Integration** - 100-point scoring system (95% code reuse)
2. ✅ **KIS Trading Engine** - Order execution with tick size compliance (70% code reuse)
3. ✅ **Kelly Calculator** - Pattern-based position sizing (100% code reuse)
4. ✅ **Portfolio Management** - Position tracking and risk management (80% code reuse)
5. ✅ **Risk Management** - ATR-based trailing stops and Stage 3 detection (90% code reuse)

### Code Reuse Strategy
- **Total Code Reuse**: ~70-75% from Makenaide
- **Proven Architecture**: 6+ months of live trading validation
- **Risk Reduction**: Leveraging battle-tested trading logic

---

## 🏗️ System Architecture

### Current Architecture (Phase 4 Complete)
```
┌────────────────────────────────────────────────────────────────┐
│                      spock.py (Orchestrator)                    │
│  ✅ Time-based routing (pre-market, intraday, post-market)     │
│  ✅ Market hours management                                     │
│  ✅ Multi-region support (KR, US, HK, CN, JP, VN)              │
└──────────────────────────┬─────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌──────────┐   ┌──────────────┐   ┌──────────────┐
    │ Stage 0  │   │   Stage 1    │   │   Database   │
    │ Scanner  │───│ Data + Filter│───│   Manager    │
    │  (6개국)  │   │  (Technical) │   │   (SQLite)   │
    └──────────┘   └──────────────┘   └──────────────┘
         ↓                 ↓                   ↓
    [Adapters]     [Technical Filter]   [CRUD Operations]
    KR/US/HK          Weinstein           ohlcv_data
    CN/JP/VN          Stage 2 Detection   tickers
                      4-Gate System        technical_analysis
```

### Target Architecture (Phase 5)
```
┌────────────────────────────────────────────────────────────────┐
│                      spock.py (Orchestrator)                    │
│  Current: Time-based routing + Scanner pipeline                 │
│  NEW:     + Trading execution + Portfolio monitoring            │
└──────────────────────────┬─────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌──────────┐   ┌──────────────┐   ┌──────────────┐
    │ Stage 0  │   │   Stage 1    │   │   Stage 2    │
    │ Scanner  │───│ Data + Filter│───│   Scoring    │  ⬅️ NEW
    │          │   │              │   │  (100-point) │
    └──────────┘   └──────────────┘   └──────┬───────┘
                                              │
                           ┌──────────────────┼──────────────────┐
                           │                  │                  │
                           ▼                  ▼                  ▼
                    ┌──────────┐      ┌─────────────┐   ┌──────────────┐
                    │  Kelly   │      │   Trading   │   │  Portfolio   │  ⬅️ NEW
                    │Calculator│──────│   Engine    │───│  Manager     │
                    │  (NEW)   │      │   (NEW)     │   │   (NEW)      │
                    └──────────┘      └─────────────┘   └──────────────┘
                         ↓                    ↓                  ↓
                    [Position      [KIS API Orders]    [Position Tracking]
                     Sizing]        Buy/Sell           ATR Trailing Stop
                    Kelly Formula   Tick Size          Stage 3 Detection
                    Pattern-based   Rate Limiting      P&L Management
```

---

## 🔧 Component Design

### 1. LayeredScoringEngine (Stage 2)

#### Purpose
Convert technical analysis into actionable **BUY/WATCH/AVOID** signals using a proven 100-point scoring system.

#### Architecture
```
LayeredScoringEngine (100 points total)
│
├── Layer 1: Macro Analysis (25 points)
│   ├── MarketRegimeModule (5 pts)  - Bull/Sideways/Bear detection
│   ├── VolumeProfileModule (10 pts) - Volume profile analysis
│   └── PriceActionModule (10 pts)   - Price action strength
│
├── Layer 2: Structural Analysis (45 points)
│   ├── StageAnalysisModule (15 pts)        - Weinstein Stage 2 focus
│   ├── MovingAverageModule (15 pts)        - MA5/20/60/120/200 alignment
│   └── RelativeStrengthModule (15 pts)     - Sector & market RS
│
└── Layer 3: Micro Analysis (30 points)
    ├── PatternRecognitionModule (10 pts)   - Chart patterns (Cup&Handle, VCP)
    ├── VolumeSpikeModule (10 pts)          - Volume breakout detection
    └── MomentumModule (10 pts)             - RSI, MACD momentum
```

#### Scoring Thresholds
```python
BUY_THRESHOLD = 70   # ≥70 points → Strong buy signal
WATCH_THRESHOLD = 50  # 50-69 points → Watch list
AVOID_THRESHOLD = 50  # <50 points → Avoid
```

#### Code Reuse from Makenaide
```bash
# Files to copy (100% reusable)
modules/integrated_scoring_system.py      # 583 lines - Main scoring system
modules/layered_scoring_engine.py         # 600 lines - 3-layer engine
modules/basic_scoring_modules.py          # 1,200 lines - 12 scoring modules
modules/adaptive_scoring_config.py        # 420 lines - Threshold configurations

# Total: ~2,800 lines, 95% reusable
```

#### Database Schema Changes
```sql
-- New table for Stage 2 scoring results
CREATE TABLE IF NOT EXISTS filter_cache_stage2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    region TEXT NOT NULL,              -- NEW: Multi-region support
    timestamp DATETIME NOT NULL,
    total_score INTEGER NOT NULL,       -- 0-100 points

    -- Layer 1 scores (25 points)
    market_regime_score INTEGER,
    volume_profile_score INTEGER,
    price_action_score INTEGER,

    -- Layer 2 scores (45 points)
    stage_analysis_score INTEGER,
    moving_average_score INTEGER,
    relative_strength_score INTEGER,

    -- Layer 3 scores (30 points)
    pattern_recognition_score INTEGER,
    volume_spike_score INTEGER,
    momentum_score INTEGER,

    -- Adaptive thresholds
    market_regime TEXT,                 -- bull/sideways/bear
    volatility_regime TEXT,             -- low/medium/high

    -- Module explanations (JSON)
    score_explanations TEXT,

    -- Metadata
    execution_time_ms INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(ticker, region, timestamp)   -- Multi-region unique constraint
);

CREATE INDEX IF NOT EXISTS idx_stage2_ticker_region ON filter_cache_stage2(ticker, region);
CREATE INDEX IF NOT EXISTS idx_stage2_score ON filter_cache_stage2(total_score DESC);
CREATE INDEX IF NOT EXISTS idx_stage2_timestamp ON filter_cache_stage2(timestamp DESC);
```

#### Integration Points
```python
# modules/scanner.py - Add Stage 2 execution
def run_full_pipeline(self, ...):
    # Stage 0: Scan stocks
    scan_result = self.scan_stocks(...)

    # Stage 1: Filter by technical criteria
    filter_result = self.run_technical_filter(...)

    # Stage 2: Score filtered stocks (NEW)
    scoring_result = self.run_stage2_scoring(filter_result['filtered_tickers'])

    return {
        'stage0': scan_result,
        'stage1': filter_result,
        'stage2': scoring_result  # NEW
    }
```

---

### 2. Kelly Calculator (Position Sizing)

#### Purpose
Calculate optimal position size based on pattern win rates and risk management principles.

#### Algorithm
```python
# Kelly Formula
kelly_fraction = (win_rate * avg_win_loss - (1 - win_rate)) / avg_win_loss

# Conservative adjustment (Half Kelly)
adjusted_kelly = kelly_fraction * 0.5

# Risk limits
max_position_per_stock = 15%  # Per stock
max_position_per_sector = 40%  # Per sector
min_cash_reserve = 20%        # Minimum cash
```

#### Pattern-Based Win Rates
```python
PATTERN_WIN_RATES = {
    'Stage 2 Breakout': {
        'win_rate': 0.65,
        'avg_win_loss': 2.0,
        'kelly_fraction': 0.15  # 15% position
    },
    'VCP Pattern': {
        'win_rate': 0.62,
        'avg_win_loss': 2.1,
        'kelly_fraction': 0.14  # 14% position
    },
    'Cup-and-Handle': {
        'win_rate': 0.58,
        'avg_win_loss': 1.8,
        'kelly_fraction': 0.11  # 11% position
    },
    'Triangle Breakout': {
        'win_rate': 0.55,
        'avg_win_loss': 1.6,
        'kelly_fraction': 0.09  # 9% position
    },
    'Default': {
        'win_rate': 0.55,
        'avg_win_loss': 1.5,
        'kelly_fraction': 0.08  # 8% position (conservative)
    }
}
```

#### Code Reuse from Makenaide
```bash
# File to copy (100% reusable)
modules/kelly_calculator.py  # 1,250 lines
# - Pattern-based Kelly calculation
# - Risk profile integration (Conservative/Moderate/Aggressive)
# - Portfolio constraints enforcement
```

#### Risk Profile Integration
```python
RISK_PROFILES = {
    'conservative': {
        'max_position_size': 0.10,     # 10% max per stock
        'kelly_multiplier': 0.5,       # Half Kelly
        'max_sector_exposure': 0.30,   # 30% per sector
        'min_score_threshold': 75      # Only top-scored stocks
    },
    'moderate': {
        'max_position_size': 0.15,     # 15% max per stock
        'kelly_multiplier': 0.6,       # 60% of Kelly
        'max_sector_exposure': 0.40,   # 40% per sector
        'min_score_threshold': 70      # Good-scored stocks
    },
    'aggressive': {
        'max_position_size': 0.20,     # 20% max per stock
        'kelly_multiplier': 0.75,      # 75% of Kelly
        'max_sector_exposure': 0.50,   # 50% per sector
        'min_score_threshold': 65      # Acceptable-scored stocks
    }
}
```

---

### 3. KIS Trading Engine (Order Execution)

#### Purpose
Execute buy/sell orders through KIS API with proper risk management and compliance.

#### Architecture
```python
class KISTradingEngine:
    """
    KIS API order execution engine

    Features:
    - Market/Limit order execution
    - Tick size compliance
    - Portfolio synchronization
    - Rate limiting (20 req/sec)
    - Order status tracking
    """

    def __init__(self, db_manager, kis_api_key, kis_api_secret):
        self.db = db_manager
        self.kis_auth = KISAuthenticator(api_key, api_secret)
        self.rate_limiter = RateLimiter(max_requests=20, window=1.0)

    def execute_buy_order(self, ticker, quantity, order_type='LIMIT'):
        """Execute buy order with tick size compliance"""

    def execute_sell_order(self, ticker, quantity, reason, order_type='LIMIT'):
        """Execute sell order (take profit or stop loss)"""

    def sync_portfolio(self):
        """Sync local database with KIS account balances"""

    def get_order_status(self, order_id):
        """Check order execution status"""
```

#### Tick Size Compliance
```python
TICK_SIZE_RULES_KRW = {
    (0, 10000): 5,           # <10K: 5 KRW tick
    (10000, 50000): 10,      # 10K-50K: 10 KRW tick
    (50000, 200000): 50,     # 50K-200K: 50 KRW tick
    (200000, 500000): 100,   # 200K-500K: 100 KRW tick
    (500000, float('inf')): 1000  # 500K+: 1,000 KRW tick
}

def adjust_price_to_tick_size(price: float) -> int:
    """Adjust order price to comply with tick size rules"""
    for (min_price, max_price), tick_size in TICK_SIZE_RULES_KRW.items():
        if min_price <= price < max_price:
            return round(price / tick_size) * tick_size
    return price
```

#### Code Reuse from Makenaide
```bash
# File to adapt (70% reusable)
modules/trading_engine.py  # 3,500 lines
# - Order execution logic (reusable)
# - Rate limiting (reusable)
# - Portfolio sync (adapt for KIS API)
# - Order status tracking (reusable)

# API changes required:
# - Upbit API → KIS API
# - Cryptocurrency → Stock market specifics
# - Tick size rules (crypto vs stock)
```

#### Transaction Cost Model
```python
TRANSACTION_COSTS_KR = {
    'trading_fee': 0.00015,      # 0.015% (online trading)
    'securities_tax': 0.0023,    # 0.23% (sell only, KOSPI)
    'securities_tax_kosdaq': 0,  # No tax for KOSDAQ
    'slippage_estimate': 0.001   # 0.1% average slippage
}

def calculate_total_cost(order_value, exchange='KOSPI', order_type='BUY'):
    """Calculate total transaction cost"""
    trading_fee = order_value * TRANSACTION_COSTS_KR['trading_fee']

    if order_type == 'SELL' and exchange == 'KOSPI':
        securities_tax = order_value * TRANSACTION_COSTS_KR['securities_tax']
    else:
        securities_tax = 0

    slippage = order_value * TRANSACTION_COSTS_KR['slippage_estimate']

    return trading_fee + securities_tax + slippage
```

---

### 4. Portfolio Management

#### Purpose
Track positions, calculate P&L, manage risk limits, and trigger automated exits.

#### Database Schema
```sql
-- Portfolio positions table
CREATE TABLE IF NOT EXISTS portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    region TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    avg_entry_price REAL NOT NULL,
    current_price REAL,
    unrealized_pnl REAL,
    unrealized_pnl_pct REAL,

    -- Risk management
    initial_stop_loss REAL NOT NULL,    -- ATR-based initial stop
    trailing_stop REAL,                 -- Dynamic trailing stop
    profit_target REAL,                 -- 20-25% target

    -- Pattern info
    entry_pattern TEXT,                 -- VCP, Cup&Handle, etc.
    entry_score INTEGER,                -- Stage 2 score at entry

    -- Stage tracking
    current_stage TEXT,                 -- Stage 2, Stage 3, Stage 4
    stage_transition_date DATETIME,     -- Last stage change

    -- Timestamps
    entry_date DATETIME NOT NULL,
    last_updated DATETIME,
    exit_date DATETIME,

    -- Status
    status TEXT DEFAULT 'OPEN',         -- OPEN, CLOSED

    UNIQUE(ticker, region, status)
);

-- Trade history table
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    region TEXT NOT NULL,

    -- Entry
    entry_date DATETIME NOT NULL,
    entry_price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    entry_pattern TEXT,
    entry_score INTEGER,

    -- Exit
    exit_date DATETIME,
    exit_price REAL,
    exit_reason TEXT,                   -- PROFIT_TARGET, STOP_LOSS, STAGE_3, MANUAL

    -- P&L
    realized_pnl REAL,
    realized_pnl_pct REAL,
    holding_days INTEGER,

    -- Transaction costs
    entry_commission REAL,
    exit_commission REAL,
    total_cost REAL,

    -- Risk metrics
    max_favorable_excursion REAL,      -- MFE
    max_adverse_excursion REAL,        -- MAE

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trades_ticker_region ON trades(ticker, region);
CREATE INDEX IF NOT EXISTS idx_trades_entry_date ON trades(entry_date DESC);
CREATE INDEX IF NOT EXISTS idx_trades_exit_reason ON trades(exit_reason);
```

#### Position Management Logic
```python
class PortfolioManager:
    """
    Portfolio tracking and risk management

    Features:
    - Position tracking
    - ATR-based trailing stops
    - Stage 3 detection (auto-sell)
    - P&L calculation
    - Risk limit enforcement
    """

    def add_position(self, ticker, region, quantity, entry_price,
                    pattern, score, atr):
        """Add new position with risk parameters"""

        # Calculate initial stop loss (ATR-based)
        initial_stop = entry_price - (atr * 1.0)  # 1.0 ATR below entry

        # Calculate profit target
        profit_target = entry_price * 1.25  # 25% target (aggressive)

        position = {
            'ticker': ticker,
            'region': region,
            'quantity': quantity,
            'avg_entry_price': entry_price,
            'initial_stop_loss': initial_stop,
            'trailing_stop': initial_stop,
            'profit_target': profit_target,
            'entry_pattern': pattern,
            'entry_score': score,
            'current_stage': 'Stage 2',
            'status': 'OPEN'
        }

        self.db.insert_position(position)

    def update_trailing_stops(self):
        """Update trailing stops for all open positions"""

        positions = self.db.get_open_positions()

        for position in positions:
            ticker = position['ticker']
            region = position['region']

            # Get current price and ATR
            current_data = self.db.get_latest_ohlcv(ticker, region)
            current_price = current_data['close']
            atr = current_data['atr_14']

            # Calculate new trailing stop (1.0 ATR below current price)
            new_stop = current_price - (atr * 1.0)

            # Only raise trailing stop, never lower it
            if new_stop > position['trailing_stop']:
                self.db.update_position(
                    ticker, region,
                    {'trailing_stop': new_stop}
                )

    def check_exit_conditions(self):
        """Check all positions for exit conditions"""

        positions = self.db.get_open_positions()
        exit_signals = []

        for position in positions:
            ticker = position['ticker']
            region = position['region']
            current_price = self.db.get_latest_price(ticker, region)

            # Check stop loss trigger
            if current_price <= position['trailing_stop']:
                exit_signals.append({
                    'ticker': ticker,
                    'region': region,
                    'reason': 'STOP_LOSS',
                    'price': current_price
                })
                continue

            # Check profit target
            if current_price >= position['profit_target']:
                exit_signals.append({
                    'ticker': ticker,
                    'region': region,
                    'reason': 'PROFIT_TARGET',
                    'price': current_price
                })
                continue

            # Check Stage 3 transition
            if self._is_stage3_transition(ticker, region):
                exit_signals.append({
                    'ticker': ticker,
                    'region': region,
                    'reason': 'STAGE_3',
                    'price': current_price
                })

        return exit_signals

    def _is_stage3_transition(self, ticker, region):
        """Detect Weinstein Stage 3 transition"""

        # Get MA30 weekly data
        weekly_data = self.db.get_weekly_ohlcv(ticker, region, days=60)

        if len(weekly_data) < 2:
            return False

        # Stage 3 detection:
        # - MA30 slopes down
        # - Price fails to make new highs
        # - Volume increases on down days

        ma30_current = weekly_data.iloc[-1]['ma30']
        ma30_previous = weekly_data.iloc[-2]['ma30']

        return ma30_current < ma30_previous  # Simplified check
```

#### Code Reuse from Makenaide
```bash
# Files to adapt (80% reusable)
modules/trading_engine.py (Portfolio methods)  # ~1,500 lines
# - Position tracking (reusable)
# - Trailing stop logic (reusable)
# - Stage detection (adapt for stocks)
# - P&L calculation (reusable)
```

---

## 🔄 Integration Workflow

### Daily Pipeline Flow (Market Hours)
```python
# spock.py orchestrator

def _execute_intraday(self):
    """Intraday trading workflow (09:00-15:30 KST)"""

    # 1. Portfolio monitoring (every 5 minutes)
    self.portfolio_manager.update_trailing_stops()
    exit_signals = self.portfolio_manager.check_exit_conditions()

    # Execute exit orders
    for signal in exit_signals:
        self.trading_engine.execute_sell_order(
            ticker=signal['ticker'],
            quantity=signal['quantity'],
            reason=signal['reason']
        )

    # 2. Check for new buy opportunities (every 30 minutes)
    if self._should_scan_for_entries():
        scoring_results = self.scanner.run_stage2_scoring(watch_list)

        buy_candidates = [r for r in scoring_results if r['score'] >= 70]

        for candidate in buy_candidates:
            # Calculate position size
            position_size = self.kelly_calculator.calculate_position_size(
                ticker=candidate['ticker'],
                pattern=candidate['pattern'],
                available_capital=self.portfolio_manager.get_available_cash()
            )

            # Execute buy order
            if position_size > 0:
                self.trading_engine.execute_buy_order(
                    ticker=candidate['ticker'],
                    quantity=position_size
                )

def _execute_after_hours(self):
    """After-hours analysis workflow (16:00-09:00 KST)"""

    # 1. Run full scanner pipeline
    result = self.scanner.run_full_pipeline(
        force_refresh=True,
        auto_stage1=True,
        auto_stage2=True  # NEW: Include Stage 2 scoring
    )

    # 2. Update watch list
    self.db.update_watch_list(result['stage2']['watch_list'])

    # 3. Generate daily report
    self._generate_daily_report(result)
```

---

## 📊 Performance Metrics & Validation

### Success Criteria
```python
TARGET_METRICS = {
    'annual_return': 0.15,        # ≥15% annually
    'sharpe_ratio': 1.5,          # ≥1.5
    'max_drawdown': 0.15,         # ≤15%
    'win_rate': 0.55,             # ≥55%
    'avg_hold_time': 30,          # ~30 days
    'profit_factor': 1.5,         # Avg win / Avg loss
}
```

### Validation Strategy
1. **Backtesting** (6 months historical data)
   - Test scoring system accuracy
   - Validate Kelly sizing effectiveness
   - Measure portfolio performance

2. **Paper Trading** (2 weeks)
   - Test with KIS mock API
   - Validate order execution
   - Test portfolio sync

3. **Live Trading** (Gradual rollout)
   - Start with 10% capital
   - Scale up after 1 month validation
   - Full deployment after 3 months

---

## 🗓️ Implementation Roadmap

### Task 1: LayeredScoringEngine Integration (Days 1-3)
- ✅ Copy 4 modules from Makenaide (~2,800 lines)
- ✅ Update database schema (filter_cache_stage2 table)
- ✅ Integrate into scanner.py
- ✅ Test with historical data
- **Deliverable**: Stage 2 scoring functional

### Task 2: Kelly Calculator Integration (Days 4-5)
- ✅ Copy kelly_calculator.py (~1,250 lines)
- ✅ Update pattern win rates for stock market
- ✅ Integrate with risk profiles
- ✅ Test position sizing logic
- **Deliverable**: Position sizing calculation

### Task 3: KIS Trading Engine (Days 6-10)
- ✅ Adapt trading_engine.py for KIS API (70% reuse)
- ✅ Implement tick size compliance
- ✅ Add order status tracking
- ✅ Build portfolio sync logic
- ✅ Test with KIS mock API
- **Deliverable**: Order execution working

### Task 4: Portfolio Management (Days 11-14)
- ✅ Add portfolio and trades tables
- ✅ Implement position tracking
- ✅ Add trailing stop logic
- ✅ Implement Stage 3 detection
- ✅ Test P&L calculations
- **Deliverable**: Full portfolio management

### Task 5: Integration & Testing (Days 15-20)
- ✅ Integrate all components into spock.py
- ✅ Backtest with 6 months data
- ✅ Paper trade for 2 weeks
- ✅ Generate performance reports
- **Deliverable**: Production-ready system

---

## 🚨 Risk Management

### Circuit Breakers
```python
CIRCUIT_BREAKERS = {
    'daily_loss_limit': 0.03,      # Stop trading if -3% daily loss
    'max_positions': 10,            # Max 10 concurrent positions
    'min_cash_reserve': 0.20,      # Always keep 20% cash
    'max_sector_exposure': 0.40,   # Max 40% in single sector
    'cooling_period': 3600,        # 1 hour after circuit breaker
}
```

### Error Recovery
```python
# Reuse from Makenaide
modules/auto_recovery_system.py  # 1,700 lines (95% reusable)
# - API failure recovery
# - Database lock handling
# - Portfolio sync mismatches
# - Order execution failures
```

---

## 📈 Expected Outcomes

### Code Statistics
- **Total New Code**: ~1,500 lines (30%)
- **Reused from Makenaide**: ~7,000 lines (70%)
- **Total Implementation**: ~8,500 lines

### Timeline
- **Implementation**: 15-20 days
- **Testing**: 5-7 days
- **Total**: ~4 weeks

### Performance Expectations
- **Annual Return**: 15-20% (vs KOSPI 8%)
- **Sharpe Ratio**: 1.5-2.0
- **Max Drawdown**: 10-15%
- **Win Rate**: 55-60%

---

**Last Updated**: 2025-10-14
**Status**: Design Complete - Ready for Implementation
**Next Step**: Begin Task 1 (LayeredScoringEngine Integration)
