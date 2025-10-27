# Phase 5 Implementation Plan: Trading Execution & Scoring System

**Date**: 2025-10-07
**Status**: Planning
**Dependencies**: Phase 4 Complete (spock.py orchestrator, scanner pipeline, KIS data collector)

## Overview

Phase 5 integrates the core trading logic into Spock, transforming it from a data collection and filtering system into a complete automated trading system. This phase implements:

1. **LayeredScoringEngine Integration** (Stage 2)
2. **KIS Trading Engine** (order execution)
3. **Kelly Calculator** (position sizing)
4. **Portfolio Management** (position tracking)
5. **Risk Management** (stop-loss automation)

**Code Reuse**: ~70% from Makenaide (proven scoring system and risk management logic)

## Architecture Integration

```
┌─────────────────────────────────────────────────────────────────┐
│                      spock.py (Orchestrator)                     │
│  Current: Time-based routing + Scanner pipeline coordination     │
│  Phase 5: + Trading execution + Portfolio monitoring             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌──────────┐   ┌──────────────┐   ┌──────────────┐
    │ Stage 0  │   │   Stage 1    │   │   Stage 2    │
    │ Scanner  │───│ Data + Filter│───│   Scoring    │
    │          │   │              │   │  (NEW)       │
    └──────────┘   └──────────────┘   └──────┬───────┘
                                              │
                           ┌──────────────────┼──────────────────┐
                           │                  │                  │
                           ▼                  ▼                  ▼
                    ┌──────────┐      ┌─────────────┐   ┌──────────────┐
                    │  Kelly   │      │   Trading   │   │  Portfolio   │
                    │Calculator│──────│   Engine    │───│  Manager     │
                    │  (NEW)   │      │   (NEW)     │   │   (NEW)      │
                    └──────────┘      └─────────────┘   └──────────────┘
```

## Task Breakdown

### Task 1: LayeredScoringEngine Integration (3-4 days)

**Objective**: Copy and integrate the proven 100-point scoring system from Makenaide

**Code Reuse**: 95% (only database table names need adjustment)

#### Subtask 1.1: Copy Scoring Modules
```bash
# Copy from Makenaide (100% reusable)
cp ~/makenaide/modules/integrated_scoring_system.py modules/
cp ~/makenaide/modules/layered_scoring_engine.py modules/
cp ~/makenaide/modules/basic_scoring_modules.py modules/
cp ~/makenaide/modules/adaptive_scoring_config.py modules/
```

**Files to Copy**:
- `integrated_scoring_system.py` (IntegratedScoringSystem class)
- `layered_scoring_engine.py` (LayeredScoringEngine class)
- `basic_scoring_modules.py` (12 scoring modules)
- `adaptive_scoring_config.py` (threshold configurations)

**Expected Lines**: ~2,500 lines (100% reusable)

#### Subtask 1.2: Database Schema Updates

**New Tables Required**:
```sql
-- Stage 2 scoring results
CREATE TABLE IF NOT EXISTS filter_cache_stage2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    total_score INTEGER NOT NULL,              -- 0-100

    -- Layer 1: Macro (25 points)
    market_regime_score INTEGER,               -- MarketRegimeModule
    volume_profile_score INTEGER,              -- VolumeProfileModule
    price_action_score INTEGER,                -- PriceActionModule

    -- Layer 2: Structural (45 points)
    stage_analysis_score INTEGER,              -- StageAnalysisModule
    moving_average_score INTEGER,              -- MovingAverageModule
    relative_strength_score INTEGER,           -- RelativeStrengthModule

    -- Layer 3: Micro (30 points)
    pattern_recognition_score INTEGER,         -- PatternRecognitionModule
    volume_spike_score INTEGER,                -- VolumeSpikeModule
    momentum_score INTEGER,                    -- MomentumModule

    -- Adaptive thresholds
    market_regime TEXT,                        -- bull/sideways/bear
    volatility_regime TEXT,                    -- low/medium/high

    -- Module explanations (JSON)
    score_explanations TEXT,                   -- Detailed reasoning

    -- Metadata
    execution_time_ms INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(ticker, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_stage2_ticker ON filter_cache_stage2(ticker);
CREATE INDEX IF NOT EXISTS idx_stage2_score ON filter_cache_stage2(total_score DESC);
CREATE INDEX IF NOT EXISTS idx_stage2_timestamp ON filter_cache_stage2(timestamp DESC);
```

**Implementation File**: `spock_init_db.py` (update)

#### Subtask 1.3: Scanner Integration

**Modify**: `modules/scanner.py`

**Changes Required**:
1. Add Stage 2 execution to `run_full_pipeline()`
2. Integrate scoring system initialization
3. Add score-based filtering (≥70 = BUY, 50-70 = WATCH, <50 = AVOID)

**Code Example**:
```python
def run_stage2_scoring(self, tickers: List[str]) -> Dict[str, Any]:
    """
    Run Stage 2 scoring on filtered tickers

    Args:
        tickers: List of tickers that passed Stage 1

    Returns:
        Dict with scoring results and statistics
    """
    from modules.integrated_scoring_system import IntegratedScoringSystem

    scorer = IntegratedScoringSystem(
        db_path=self.db_path,
        region=self.region
    )

    results = {
        'buy_signals': [],      # score ≥70
        'watch_list': [],       # 50 ≤ score < 70
        'avoid_list': [],       # score < 50
        'scoring_results': []
    }

    for ticker in tickers:
        score_result = scorer.calculate_comprehensive_score(ticker)

        results['scoring_results'].append(score_result)

        if score_result['total_score'] >= 70:
            results['buy_signals'].append({
                'ticker': ticker,
                'score': score_result['total_score'],
                'recommendation': 'BUY'
            })
        elif score_result['total_score'] >= 50:
            results['watch_list'].append({
                'ticker': ticker,
                'score': score_result['total_score'],
                'recommendation': 'WATCH'
            })
        else:
            results['avoid_list'].append({
                'ticker': ticker,
                'score': score_result['total_score'],
                'recommendation': 'AVOID'
            })

    # Save to database
    self._save_stage2_results(results)

    return results
```

#### Subtask 1.4: Orchestrator Integration

**Modify**: `spock.py`

**Changes**:
1. Add Stage 2 execution to pipeline routines
2. Update reporting to include scoring statistics

**Code Example**:
```python
def _execute_after_hours(self) -> Dict[str, any]:
    """Execute after-hours routine with Stage 2 scoring"""

    # Execute Stage 0 → Stage 1 pipeline
    result = self.scanner.run_full_pipeline(
        force_refresh=force_refresh,
        auto_stage1=True,
        skip_data_collection=False
    )

    # Execute Stage 2 scoring (NEW)
    if 'stage1_filter' in result and result['stage1_filter']['passed_count'] > 0:
        stage1_tickers = result['stage1_filter']['passed_tickers']

        logger.info(f"\n📊 Running Stage 2 scoring on {len(stage1_tickers)} tickers...")
        stage2_result = self.scanner.run_stage2_scoring(stage1_tickers)

        result['stage2_scoring'] = stage2_result

        # Summary
        buy_count = len(stage2_result['buy_signals'])
        watch_count = len(stage2_result['watch_list'])

        logger.info(f"\n✅ Stage 2 Complete:")
        logger.info(f"   🟢 BUY signals: {buy_count}")
        logger.info(f"   🟡 WATCH list: {watch_count}")

    return result
```

**Success Criteria**:
- ✅ Scoring modules integrated successfully
- ✅ Database schema updated
- ✅ Scanner executes Stage 2 after Stage 1
- ✅ Scores saved to `filter_cache_stage2` table
- ✅ BUY/WATCH/AVOID classification working
- ✅ Orchestrator logs show scoring statistics

**Testing**:
```bash
# Test scoring on sample tickers
python3 modules/integrated_scoring_system.py --ticker 005930 --region KR

# Test full pipeline with scoring
python3 spock.py --mode manual --region KR --dry-run

# Verify database
python3 -c "
import sqlite3
conn = sqlite3.connect('data/spock_local.db')
df = conn.execute('SELECT ticker, total_score FROM filter_cache_stage2 ORDER BY total_score DESC LIMIT 10').fetchall()
print(df)
"
```

---

### Task 2: Kelly Calculator Integration (2-3 days)

**Objective**: Integrate pattern-based position sizing from Makenaide

**Code Reuse**: 90% (pattern win rates may need adjustment for stock market)

#### Subtask 2.1: Copy Kelly Calculator
```bash
cp ~/makenaide/modules/kelly_calculator.py modules/
```

**Expected Lines**: ~400 lines (90% reusable)

#### Subtask 2.2: Pattern Win Rate Configuration

**Create**: `config/pattern_win_rates_stock.yaml`

```yaml
# Pattern-based win rates for Korean stock market
# Based on backtesting and Makenaide crypto data (adjusted for stocks)

patterns:
  stage2_breakout:
    win_rate: 0.62              # 62% win rate (crypto: 0.65)
    avg_win_loss_ratio: 1.8     # R:R ratio (crypto: 2.0)
    min_score: 70
    description: "Weinstein Stage 2 breakout with volume"

  vcp_pattern:
    win_rate: 0.58              # 58% win rate (crypto: 0.62)
    avg_win_loss_ratio: 2.0
    min_score: 75
    description: "Mark Minervini VCP pattern"

  cup_and_handle:
    win_rate: 0.55              # 55% win rate (crypto: 0.58)
    avg_win_loss_ratio: 1.7
    min_score: 72
    description: "Cup and Handle formation"

  triangle_breakout:
    win_rate: 0.52              # 52% win rate (crypto: 0.55)
    avg_win_loss_ratio: 1.5
    min_score: 68
    description: "Triangle breakout with volume"

  high_score_generic:
    win_rate: 0.60              # Default for score ≥75
    avg_win_loss_ratio: 1.8
    min_score: 75
    description: "High score without specific pattern"

  medium_score_generic:
    win_rate: 0.55              # Default for 70 ≤ score < 75
    avg_win_loss_ratio: 1.6
    min_score: 70
    description: "Medium score generic setup"

# Risk profile multipliers
risk_profiles:
  conservative:
    kelly_fraction: 0.25        # Quarter Kelly
    max_position_pct: 10.0      # Max 10% per stock
    min_edge: 0.15              # Require 15%+ edge

  moderate:
    kelly_fraction: 0.35        # ~1/3 Kelly
    max_position_pct: 15.0      # Max 15% per stock
    min_edge: 0.10              # Require 10%+ edge

  aggressive:
    kelly_fraction: 0.50        # Half Kelly
    max_position_pct: 20.0      # Max 20% per stock
    min_edge: 0.08              # Require 8%+ edge
```

#### Subtask 2.3: Database Schema for Position Sizing

**New Table**:
```sql
CREATE TABLE IF NOT EXISTS kelly_sizing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    timestamp DATETIME NOT NULL,

    -- Scoring data
    total_score INTEGER NOT NULL,
    detected_pattern TEXT,                  -- Pattern type (or NULL)

    -- Kelly calculation inputs
    win_rate REAL NOT NULL,
    avg_win_loss_ratio REAL NOT NULL,
    kelly_fraction REAL NOT NULL,           -- 0.25-0.50 based on risk profile

    -- Position sizing results
    kelly_percentage REAL NOT NULL,         -- Raw Kelly %
    adjusted_percentage REAL NOT NULL,      -- After risk profile adjustment
    max_position_pct REAL NOT NULL,         -- Max allowed (10/15/20%)
    recommended_percentage REAL NOT NULL,   -- Final recommendation

    -- Portfolio context
    current_portfolio_value REAL,
    available_cash REAL,
    recommended_position_value REAL,

    -- Risk profile
    risk_profile TEXT NOT NULL,             -- conservative/moderate/aggressive

    -- Metadata
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(ticker, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_kelly_ticker ON kelly_sizing(ticker);
CREATE INDEX IF NOT EXISTS idx_kelly_timestamp ON kelly_sizing(timestamp DESC);
```

#### Subtask 2.4: Scanner Integration

**Modify**: `modules/scanner.py`

**Add Method**:
```python
def calculate_position_sizes(
    self,
    buy_signals: List[Dict],
    risk_profile: str = 'moderate',
    portfolio_value: float = 10000000  # 10M KRW default
) -> List[Dict]:
    """
    Calculate Kelly-based position sizes for buy signals

    Args:
        buy_signals: List of dicts with ticker, score, pattern
        risk_profile: conservative/moderate/aggressive
        portfolio_value: Current portfolio value in KRW

    Returns:
        List of dicts with position sizing recommendations
    """
    from modules.kelly_calculator import KellyCalculator

    kelly_calc = KellyCalculator(
        config_path='config/pattern_win_rates_stock.yaml',
        risk_profile=risk_profile
    )

    sized_signals = []

    for signal in buy_signals:
        sizing = kelly_calc.calculate_position_size(
            ticker=signal['ticker'],
            score=signal['score'],
            pattern=signal.get('detected_pattern'),
            portfolio_value=portfolio_value
        )

        signal['position_sizing'] = sizing
        sized_signals.append(signal)

        # Save to database
        self._save_kelly_sizing(signal['ticker'], sizing)

    return sized_signals
```

**Success Criteria**:
- ✅ Kelly calculator integrated
- ✅ Pattern win rates configured for stocks
- ✅ Position sizing calculated for buy signals
- ✅ Results saved to `kelly_sizing` table
- ✅ Risk profile adjustments working (conservative/moderate/aggressive)

**Testing**:
```bash
# Test Kelly calculator standalone
python3 modules/kelly_calculator.py \
    --score 78 \
    --pattern stage2_breakout \
    --portfolio-value 10000000 \
    --risk-profile moderate

# Expected output: ~8-12% position size

# Test full pipeline with position sizing
python3 spock.py --mode manual --region KR --risk-level moderate --dry-run
```

---

### Task 3: KIS Trading Engine Implementation (5-7 days)

**Objective**: Implement order execution via KIS API with tick size compliance and portfolio sync

**Code Reuse**: 60% from Makenaide (order logic reusable, API calls need replacement)

#### Subtask 3.1: Create Trading Engine Module

**New File**: `modules/kis_trading_engine.py`

**Expected Lines**: ~800 lines

**Key Components**:

1. **KISApiWrapper Class** (KIS API integration)
```python
class KISApiWrapper:
    """KIS API wrapper for trading operations"""

    def __init__(self, config_path: str = 'config/kis_api_config.yaml'):
        self.config = self._load_config(config_path)
        self.base_url = "https://openapi.koreainvestment.com:9443"
        self.token = None
        self.token_expires_at = None

    def authenticate(self) -> bool:
        """Get OAuth2 access token (24-hour validity)"""

    def get_current_price(self, ticker: str) -> Dict:
        """Get real-time quote for ticker"""

    def get_portfolio_balance(self) -> Dict:
        """Get current portfolio holdings and cash"""

    def place_order(
        self,
        ticker: str,
        order_type: str,  # 'buy' or 'sell'
        quantity: int,
        price: float,
        order_method: str = 'limit'  # 'market' or 'limit'
    ) -> Dict:
        """Place buy/sell order with tick size compliance"""

    def cancel_order(self, order_id: str) -> Dict:
        """Cancel pending order"""

    def get_order_status(self, order_id: str) -> Dict:
        """Check order execution status"""
```

2. **Tick Size Compliance**
```python
def adjust_price_to_tick_size(price: float) -> float:
    """
    Adjust price to comply with KRX tick size rules

    Tick Size Rules:
    - <10,000 KRW: 5 KRW
    - 10,000-50,000: 10 KRW
    - 50,000-200,000: 50 KRW
    - 200,000-500,000: 100 KRW
    - ≥500,000: 1,000 KRW
    """
    if price < 10000:
        return round(price / 5) * 5
    elif price < 50000:
        return round(price / 10) * 10
    elif price < 200000:
        return round(price / 50) * 50
    elif price < 500000:
        return round(price / 100) * 100
    else:
        return round(price / 1000) * 1000
```

3. **StockTradingEngine Class** (Main trading logic)
```python
class StockTradingEngine:
    """
    Main trading engine for stock market execution

    Responsibilities:
    - Order placement and execution
    - Portfolio synchronization
    - Transaction cost calculation
    - Order validation
    """

    def __init__(
        self,
        db_path: str,
        risk_profile: str = 'moderate',
        dry_run: bool = False
    ):
        self.db_manager = SQLiteDatabaseManager(db_path)
        self.kis_api = KISApiWrapper()
        self.risk_profile = risk_profile
        self.dry_run = dry_run

    def execute_buy_signal(
        self,
        ticker: str,
        recommended_position_value: float,
        current_price: float
    ) -> Dict:
        """
        Execute buy order with validation

        Steps:
        1. Validate portfolio capacity
        2. Calculate transaction costs
        3. Adjust quantity to minimum lot size (1 share for stocks)
        4. Adjust price to tick size
        5. Place order via KIS API
        6. Update database
        """

    def sync_portfolio(self) -> Dict:
        """
        Synchronize database with KIS API portfolio

        Returns:
            Dict with sync results and discrepancies
        """

    def calculate_transaction_cost(
        self,
        ticker: str,
        quantity: int,
        price: float,
        order_type: str
    ) -> float:
        """
        Calculate total transaction cost

        Components:
        - Trading fee: 0.015% (online)
        - Securities tax: 0.23% (sell only, KOSPI stocks only)
        """
```

#### Subtask 3.2: Database Schema for Trading

**New Tables**:
```sql
-- Trade execution log
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    trade_type TEXT NOT NULL,               -- 'buy' or 'sell'

    -- Order details
    order_id TEXT,                          -- KIS API order ID
    quantity INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL,

    -- Timing
    order_time DATETIME NOT NULL,
    fill_time DATETIME,
    exit_time DATETIME,

    -- P&L
    gross_profit REAL,
    transaction_cost REAL,
    net_profit REAL,
    return_pct REAL,

    -- Context
    entry_score INTEGER,                    -- Score at entry
    entry_pattern TEXT,                     -- Pattern detected
    exit_reason TEXT,                       -- stop_loss/profit_target/stage3

    -- Risk management
    stop_loss_price REAL,
    profit_target_price REAL,
    max_drawdown_pct REAL,

    -- Metadata
    risk_profile TEXT,
    dry_run BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Portfolio positions (real-time)
CREATE TABLE IF NOT EXISTS portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL UNIQUE,

    -- Position details
    quantity INTEGER NOT NULL,
    avg_entry_price REAL NOT NULL,
    current_price REAL,

    -- P&L
    unrealized_pnl REAL,
    unrealized_pnl_pct REAL,

    -- Risk management
    stop_loss_price REAL NOT NULL,
    profit_target_price REAL,
    trailing_stop_pct REAL,

    -- Position sizing
    position_value REAL,
    position_weight_pct REAL,              -- % of total portfolio

    -- Entry context
    entry_date DATETIME NOT NULL,
    entry_score INTEGER,
    entry_pattern TEXT,

    -- Metadata
    last_sync_time DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- KIS API call log (rate limiting + debugging)
CREATE TABLE IF NOT EXISTS kis_api_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,                  -- GET/POST

    -- Request
    request_params TEXT,                   -- JSON

    -- Response
    status_code INTEGER,
    response_body TEXT,
    error_message TEXT,

    -- Timing
    request_time DATETIME NOT NULL,
    response_time DATETIME,
    duration_ms INTEGER,

    -- Rate limiting
    requests_this_second INTEGER,
    requests_this_minute INTEGER,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades(ticker);
CREATE INDEX IF NOT EXISTS idx_trades_order_time ON trades(order_time DESC);
CREATE INDEX IF NOT EXISTS idx_portfolio_ticker ON portfolio(ticker);
CREATE INDEX IF NOT EXISTS idx_api_logs_endpoint ON kis_api_logs(endpoint);
CREATE INDEX IF NOT EXISTS idx_api_logs_time ON kis_api_logs(request_time DESC);
```

#### Subtask 3.3: Orchestrator Integration

**Modify**: `spock.py`

**Add Trading Execution**:
```python
def _execute_after_hours(self) -> Dict[str, any]:
    """Execute after-hours routine with trading"""

    # ... existing pipeline execution ...

    # Execute trading (NEW)
    if 'stage2_scoring' in result:
        buy_signals = result['stage2_scoring']['buy_signals']

        if buy_signals and not self.dry_run:
            logger.info(f"\n💰 Executing {len(buy_signals)} buy signals...")

            trading_engine = StockTradingEngine(
                db_path=self.db_path,
                risk_profile=self.risk_level,
                dry_run=self.dry_run
            )

            execution_results = []
            for signal in buy_signals:
                result = trading_engine.execute_buy_signal(
                    ticker=signal['ticker'],
                    recommended_position_value=signal['position_sizing']['recommended_position_value'],
                    current_price=signal['current_price']
                )
                execution_results.append(result)

            logger.info(f"✅ Executed {len(execution_results)} orders")

    return result
```

**Success Criteria**:
- ✅ KIS API authentication working
- ✅ Order placement successful with tick size compliance
- ✅ Portfolio sync working (database ↔ KIS API)
- ✅ Transaction costs calculated correctly
- ✅ Orders logged to `trades` table
- ✅ Portfolio positions tracked in `portfolio` table
- ✅ API rate limiting respected

**Testing**:
```bash
# Test KIS API connection
python3 modules/kis_trading_engine.py --test-auth

# Test tick size adjustment
python3 modules/kis_trading_engine.py --test-tick-size

# Test dry-run order (no actual execution)
python3 modules/kis_trading_engine.py \
    --ticker 005930 \
    --action buy \
    --quantity 10 \
    --dry-run

# Test full pipeline with dry-run trading
python3 spock.py --mode manual --region KR --risk-level moderate --dry-run

# Test real trading (CAUTION)
python3 spock.py --mode manual --region KR --risk-level conservative
```

---

### Task 4: Risk Management & Stop-Loss Automation (3-4 days)

**Objective**: Implement automated stop-loss and profit-taking based on ATR and Stage 3 detection

**Code Reuse**: 80% from Makenaide

#### Subtask 4.1: Copy Risk Management Module
```bash
cp ~/makenaide/modules/risk_manager.py modules/stock_risk_manager.py
```

#### Subtask 4.2: Implement Position Monitoring

**New File**: `modules/position_monitor.py`

**Expected Lines**: ~500 lines

**Key Components**:
```python
class PositionMonitor:
    """
    Real-time position monitoring for stop-loss and profit-taking

    Monitors:
    - ATR-based trailing stops
    - Stage 3 transitions (uptrend → downtrend)
    - Profit target levels
    - Maximum holding period
    """

    def __init__(self, db_path: str, trading_engine: StockTradingEngine):
        self.db_manager = SQLiteDatabaseManager(db_path)
        self.trading_engine = trading_engine

    def check_exit_conditions(self, ticker: str) -> Optional[Dict]:
        """
        Check if position should be exited

        Exit Conditions:
        1. Stop-loss hit (ATR-based trailing)
        2. Stage 3 detected (uptrend → downtrend)
        3. Profit target reached
        4. Maximum holding period exceeded (60 days)

        Returns:
            Dict with exit recommendation or None
        """

    def calculate_atr_stop(self, ticker: str) -> float:
        """
        Calculate ATR-based stop-loss price

        Formula: Current Price - (1.0 × ATR_14)
        Constraints:
        - Min stop: 5% (low volatility)
        - Max stop: 15% (high volatility)
        """

    def detect_stage3_transition(self, ticker: str) -> bool:
        """
        Detect Weinstein Stage 3 transition

        Signals:
        - Price breaks below MA30
        - MA30 flattens or turns down
        - Volume on down days increases
        """

    def update_trailing_stop(self, ticker: str) -> float:
        """
        Update trailing stop as price advances

        Logic:
        - Initial: 1.0 × ATR
        - At +10%: Move to breakeven
        - At +15%: Activate trailing stop (1.0 × ATR)
        - At +20%: Tighten to 0.75 × ATR
        """
```

#### Subtask 4.3: Orchestrator Integration for Live Monitoring

**Modify**: `spock.py`

**Add Intraday Monitoring**:
```python
def _execute_market_open(self) -> Dict[str, any]:
    """
    Execute intraday monitoring (09:00-15:30 KST)

    NEW IMPLEMENTATION (replacing placeholder)
    """
    logger.info("\n" + "=" * 70)
    logger.info("📈 MARKET OPEN - LIVE MONITORING")
    logger.info("=" * 70)

    if self.dry_run:
        logger.info("🔍 DRY RUN: Previewing intraday monitoring...")
        return {'status': 'dry_run', 'phase': 'market_open'}

    # Initialize position monitor
    from modules.position_monitor import PositionMonitor
    from modules.kis_trading_engine import StockTradingEngine

    trading_engine = StockTradingEngine(
        db_path=self.db_path,
        risk_profile=self.risk_level,
        dry_run=self.dry_run
    )

    monitor = PositionMonitor(
        db_path=self.db_path,
        trading_engine=trading_engine
    )

    # Get current positions
    positions = self.db_manager.get_active_positions()

    logger.info(f"📊 Monitoring {len(positions)} active positions...")

    exit_signals = []
    for position in positions:
        # Check exit conditions
        exit_recommendation = monitor.check_exit_conditions(position['ticker'])

        if exit_recommendation:
            logger.info(f"🚨 EXIT SIGNAL: {position['ticker']} - {exit_recommendation['reason']}")
            exit_signals.append(exit_recommendation)

            # Execute exit
            result = trading_engine.execute_sell_signal(
                ticker=position['ticker'],
                quantity=position['quantity'],
                reason=exit_recommendation['reason']
            )

            logger.info(f"✅ Sold {position['ticker']}: {result}")

    return {
        'status': 'success',
        'phase': 'market_open',
        'positions_monitored': len(positions),
        'exit_signals': len(exit_signals)
    }
```

**Success Criteria**:
- ✅ ATR-based stop-loss calculated correctly
- ✅ Trailing stop updates as price advances
- ✅ Stage 3 detection working
- ✅ Exit orders executed automatically
- ✅ Exit reasons logged (stop_loss/profit_target/stage3)

**Testing**:
```bash
# Test position monitor standalone
python3 modules/position_monitor.py --ticker 005930

# Test intraday monitoring (market hours only)
python3 spock.py --mode auto --region KR --risk-level moderate
```

---

### Task 5: Performance Reporting & Monitoring (2-3 days)

**Objective**: Implement daily/weekly/monthly performance tracking and alerts

**Code Reuse**: 75% from Makenaide

#### Subtask 5.1: Create Reporting Module

**New File**: `modules/performance_reporter.py`

**Expected Lines**: ~400 lines

**Key Reports**:
```python
class PerformanceReporter:
    """
    Generate performance reports and metrics

    Reports:
    - Daily P&L summary
    - Weekly performance review
    - Monthly portfolio metrics
    - Trade analysis (win rate, avg R:R)
    """

    def generate_daily_summary(self, date: str) -> Dict:
        """
        Daily P&L summary

        Metrics:
        - Trades executed
        - Realized P&L
        - Unrealized P&L
        - Portfolio value change
        - Win rate today
        """

    def generate_weekly_report(self, start_date: str) -> Dict:
        """
        Weekly performance review

        Metrics:
        - Total return %
        - Sharpe ratio
        - Max drawdown
        - Win rate
        - Avg profit per trade
        - Best/worst performers
        """

    def generate_monthly_report(self, month: str) -> Dict:
        """
        Monthly portfolio metrics

        Metrics:
        - Total return % vs KOSPI
        - Sharpe ratio
        - Max drawdown
        - Win rate by pattern
        - Sector allocation
        - Top 10 performers
        """

    def calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio (risk-adjusted returns)"""

    def calculate_max_drawdown(self, portfolio_values: List[float]) -> float:
        """Calculate maximum peak-to-trough decline"""
```

#### Subtask 5.2: Orchestrator Integration for Reporting

**Modify**: `spock.py`

**Add Post-Market Reporting**:
```python
def _execute_post_market(self) -> Dict[str, any]:
    """
    Execute post-market routine (15:30-16:00 KST)

    NEW METHOD
    """
    logger.info("\n" + "=" * 70)
    logger.info("🌆 POST-MARKET - DAILY SUMMARY")
    logger.info("=" * 70)

    from modules.performance_reporter import PerformanceReporter

    reporter = PerformanceReporter(db_path=self.db_path)

    # Generate daily summary
    today = datetime.now().strftime('%Y-%m-%d')
    summary = reporter.generate_daily_summary(today)

    logger.info(f"\n📊 Daily Performance Summary:")
    logger.info(f"   Trades Executed: {summary['trades_count']}")
    logger.info(f"   Realized P&L: {summary['realized_pnl']:,.0f} KRW")
    logger.info(f"   Unrealized P&L: {summary['unrealized_pnl']:,.0f} KRW")
    logger.info(f"   Portfolio Value: {summary['portfolio_value']:,.0f} KRW ({summary['daily_return_pct']:+.2f}%)")
    logger.info(f"   Win Rate Today: {summary['win_rate']:.1f}%")

    return {
        'status': 'success',
        'phase': 'post_market',
        'summary': summary
    }
```

**Success Criteria**:
- ✅ Daily P&L calculated correctly
- ✅ Sharpe ratio and max drawdown computed
- ✅ Reports generated automatically after market close
- ✅ Alerts sent for exceptional performance (±5% daily)

**Testing**:
```bash
# Test daily report generation
python3 modules/performance_reporter.py --report daily --date 2025-10-07

# Test weekly report
python3 modules/performance_reporter.py --report weekly --start-date 2025-10-01

# Test monthly report
python3 modules/performance_reporter.py --report monthly --month 2025-10
```

---

## Integration Testing Plan

### Test Scenarios

#### Scenario 1: Full Pipeline (After-Hours)
```bash
python3 spock.py --mode auto --region KR --risk-level moderate --dry-run
```

**Expected Flow**:
1. Check market hours → after_hours
2. Execute scanner (Stage 0)
3. Collect OHLCV data (Stage 1)
4. Apply technical filters (Stage 1)
5. Calculate scores (Stage 2) → BUY signals
6. Calculate Kelly position sizes
7. Execute buy orders (dry-run)
8. Generate daily summary report

#### Scenario 2: Live Monitoring (Market Hours)
```bash
python3 spock.py --mode auto --region KR --risk-level moderate
```

**Expected Flow**:
1. Check market hours → market_open
2. Load active positions from database
3. Monitor exit conditions (stop-loss, Stage 3, profit target)
4. Execute sell orders if conditions met
5. Log exit reasons

#### Scenario 3: Pre-Market Warm-Up
```bash
python3 spock.py --mode auto --region KR --risk-level moderate
```

**Expected Flow**:
1. Check market hours → pre_market
2. Execute scanner + data collection
3. Generate watchlist for intraday
4. No trading execution

#### Scenario 4: Manual Execution
```bash
python3 spock.py --mode manual --region KR --risk-level aggressive
```

**Expected Flow**:
1. Ignore market hours
2. Execute full pipeline immediately
3. Trade execution based on risk level

### Performance Benchmarks

**Target Metrics** (Phase 5):
- Pipeline Execution: <5 minutes (Stage 0 → Stage 2)
- Scoring Per Ticker: <2 seconds
- Order Placement: <500ms per order
- Portfolio Sync: <1 second
- Daily Report Generation: <5 seconds

**Success Criteria**:
- All pipeline stages execute without errors
- Scores match expected ranges (0-100)
- Position sizes comply with risk profiles
- Orders respect tick size rules
- Portfolio sync accuracy: 100%
- Stop-loss/profit-taking triggers correctly

---

## Database Migration Plan

### Phase 5 Schema Additions

**New Tables**: 4 tables
- `filter_cache_stage2` (scoring results)
- `kelly_sizing` (position sizing)
- `trades` (trade execution log)
- `portfolio` (real-time positions)
- `kis_api_logs` (API call tracking)

**Migration Script**: `migrations/migrate_phase5.sql`

```sql
-- Run after Phase 4
-- Adds Phase 5 trading and scoring tables

BEGIN TRANSACTION;

-- (Include all CREATE TABLE statements from above)

COMMIT;
```

**Rollback Strategy**:
```sql
-- Rollback Phase 5 migration
BEGIN TRANSACTION;

DROP TABLE IF EXISTS filter_cache_stage2;
DROP TABLE IF EXISTS kelly_sizing;
DROP TABLE IF EXISTS trades;
DROP TABLE IF EXISTS portfolio;
DROP TABLE IF EXISTS kis_api_logs;

COMMIT;
```

---

## Risk Management

### Phase 5 Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| KIS API rate limit exceeded | High | Medium | Implement request queuing + retry logic |
| Order rejection (tick size) | Medium | Low | Comprehensive tick size testing |
| Portfolio sync failure | High | Low | Automatic reconciliation + alerts |
| Stop-loss not triggered | Critical | Low | Redundant monitoring + alerts |
| Pattern win rates inaccurate | Medium | Medium | Conservative Kelly fraction (0.25-0.35) |
| Trading during market halt | High | Low | Real-time market status checks |

### Safety Mechanisms

1. **Dry-Run Mode**: Always available for testing
2. **Position Limits**: 10/15/20% max per stock based on risk profile
3. **Kelly Fraction**: Conservative multipliers (0.25-0.50)
4. **Stop-Loss Enforcement**: Automatic exit on breach
5. **API Rate Limiting**: Request throttling to prevent account suspension
6. **Portfolio Sync Validation**: Daily reconciliation with KIS API

---

## Success Criteria (Phase 5 Complete)

- ✅ LayeredScoringEngine integrated (100-point system)
- ✅ Kelly Calculator position sizing working
- ✅ KIS Trading Engine executing orders
- ✅ Tick size compliance 100%
- ✅ Portfolio sync accuracy 100%
- ✅ ATR-based stop-loss automation
- ✅ Stage 3 exit detection
- ✅ Daily/weekly/monthly reports generated
- ✅ All integration tests passing
- ✅ Performance benchmarks met

**Target Completion**: Phase 5 complete in 15-20 days

---

## Phase 6 Preview (Future)

After Phase 5:
1. **Daemon Mode**: Background monitoring with systemd/cron
2. **GPT-4 Chart Analysis**: Pattern recognition integration
3. **Advanced Risk Management**: Dynamic position sizing based on volatility
4. **Multi-Region Support**: US market integration (NYSE, NASDAQ)
5. **Backtesting Framework**: Historical strategy validation
6. **Web Dashboard**: Real-time portfolio monitoring UI

---

**Document Status**: Draft
**Next Action**: Review plan → Begin Task 1 (Scoring Integration)
**Dependencies**: Phase 4 complete ✅
