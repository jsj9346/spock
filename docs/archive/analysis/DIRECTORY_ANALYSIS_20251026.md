# SPOCK PROJECT DIRECTORY STRUCTURE ANALYSIS

## Executive Summary

**Project Status**: Architectural Pivot Complete
- **Legacy System**: Spock Automated Trading (kis_trading_engine.py, spock.py) - 407 Python files, 4.4G total
- **New Direction**: Quant Investment Platform (quant_platform.py) - Research-driven backtesting
- **Code Reuse**: 70% of modules remain (70% reusable components identified)
- **Total Analysis**: 407 Python files, 150+ markdown files, 30+ test files

---

## DIRECTORY STRUCTURE ORGANIZATION

```
/Users/13ruce/spock/                                    [4.4G - Total Project]
├── SPOCK LEGACY (TRADING SYSTEM) - 36K base file
│   ├── spock.py                                       [36K - Oct 16]
│   ├── spock.md                                       [7.9K - Sep 20] 
│   ├── spock_PRD.md                                   [33K - Oct 1]
│   ├── init_db.py                                     [75K - Oct 17] (SQLite legacy)
│   └── modules/kis_trading_engine.py                  [57K - Oct 20] (Real-time trading)
│
├── QUANT PLATFORM (NEW DIRECTION) - Active development
│   ├── quant_platform.py                              [5.4K - Oct 22] ✅
│   ├── modules/backtesting/                           [376K - Oct 26] ✅
│   ├── modules/factors/                               [352K - Oct 24] ✅
│   ├── modules/optimization/                          [192K - Oct 24] ✅
│   ├── modules/risk/                                  [Active]
│   └── modules/strategies/                            [Active]
│
├── REUSABLE COMPONENTS (70% Code Reuse)
│   ├── modules/api_clients/                           [Multi-region APIs]
│   ├── modules/market_adapters/                       [KR, US, CN, HK, JP, VN]
│   ├── modules/parsers/                               [Stock/ETF/Currency parsers]
│   ├── modules/db_manager_postgres.py                 [83K - Oct 21] ✅
│   ├── modules/db_manager_sqlite.py                   [69K - Oct 21] (Legacy)
│   └── modules/kelly_calculator.py                    [58K - Oct 17]
│
├── DOCUMENTATION
│   ├── docs/                                          [4.2M - 100+ markdown files]
│   ├── CLAUDE.md                                      [19K - Oct 26] ✅ (Current)
│   ├── CLAUDE_backup.md                               [34K - Oct 18] ⚠️ (Outdated)
│   ├── PROJECT_INDEX.md                               [18K - Oct 18]
│   ├── COMPONENT_REFERENCE.md                         [51K - Oct 18]
│   └── analysis/                                      [8.3M - 30+ reports]
│
├── TESTING
│   ├── tests/                                         [1.7M - 30+ test files]
│   ├── test_reports/                                  [3.0M - Phase 3-5 reports]
│   └── tests/test_kis_trading_engine.py               ⚠️ (Trading-specific)
│
├── INFRASTRUCTURE
│   ├── config/                                        [32M - Market configs, holidays]
│   ├── monitoring/                                    [504K - Prometheus/Grafana]
│   ├── logs/                                          [467M - Operational logs]
│   ├── data/                                          [3.4G - OHLCV, master files]
│   ├── backups/                                       [186M - DB backups]
│   └── api/                                           [132K - FastAPI routes]
│
└── DEVELOPMENT
    ├── scripts/                                       [2.0M - 50+ utility scripts]
    ├── examples/                                      [172K - Demo workflows]
    ├── cli/                                           [Auth/setup utilities]
    └── dashboard/                                     [Streamlit UI - minimal]
```

---

## DETAILED FILE CATEGORIZATION

### CATEGORY 1: SPOCK LEGACY FILES (DELETE/ARCHIVE)

**Size**: 36K-75K main files  
**Status**: Superseded by Quant Platform  
**Action**: Archive to `/archive/spock_legacy/` before deletion  

#### Core Trading System
| File Path | Size | Modified | Category | Action | Reason |
|-----------|------|----------|----------|--------|--------|
| `/spock.py` | 36K | Oct 16 | Legacy | Archive | Main trading orchestrator (7-stage pipeline) - replaced by quant_platform.py |
| `/spock.md` | 7.9K | Sep 20 | Legacy | Delete | Old project documentation |
| `/spock_PRD.md` | 33K | Oct 1 | Legacy | Archive | Product requirements for trading system - historical reference |
| `/init_db.py` | 75K | Oct 17 | Legacy | Archive | SQLite database initialization (27 table definitions) - replaced by PostgreSQL |
| `/modules/kis_trading_engine.py` | 57K | Oct 20 | Legacy | Archive | Real-time KIS API trading (order execution, P&L) - core Spock component |

#### Trading-Specific Test Files
| File Path | Size | Modified | Category | Action | Reason |
|-----------|------|----------|----------|--------|--------|
| `/tests/test_kis_trading_engine.py` | - | Oct 21 | Legacy | Delete | Tests for trading engine order execution |
| `/tests/test_kis_authentication_day1.py` | - | - | Legacy | Delete | KIS API auth integration tests |
| `/tests/test_kis_price_and_buy_day2.py` | - | - | Legacy | Delete | Trading execution tests (buy orders) |
| `/tests/test_kis_sell_and_integration_day3.py` | - | - | Legacy | Delete | Trading execution tests (sell orders) |
| `/tests/test_trading_engine_blacklist.py` | - | - | Legacy | Delete | Trading blacklist integration tests |
| `/tests/test_phase5_task4_integration.py` | - | - | Legacy | Delete | Phase 5 trading integration (portfolio sync) |

#### Trading Documentation
| File Path | Size | Modified | Category | Action | Reason |
|-----------|------|----------|----------|--------|--------|
| `/PHASE5_IMPLEMENTATION_PLAN.md` | 36K | Oct 7 | Legacy | Archive | Trading execution phase plan |
| `/PHASE5_TASK1_COMPLETION_REPORT.md` | 14K | Oct 7 | Legacy | Archive | Trading backend completion report |
| `/PHASE5_TASK1_COMPLETION_STATUS.md` | 8.8K | Oct 8 | Legacy | Delete | Trading status tracking |
| `/PHASE5_TRADING_EXECUTION_DESIGN.md` | 26K | Oct 14 | Legacy | Archive | KIS trading execution design |
| `/docs/KIS_TRADING_ENGINE_DESIGN.md` | 13K | Oct 14 | Legacy | Archive | Trading engine architecture |
| `/docs/KIS_TRADING_ENGINE_DAY1_3_IMPLEMENTATION_DESIGN.md` | 29K | Oct 20 | Legacy | Archive | Trading engine 3-day implementation plan |
| `/docs/KIS_TRADING_ENGINE_DAY2_3_COMPLETION_SUMMARY.md` | 8.6K | Oct 20 | Legacy | Archive | Trading completion status |
| `/docs/KIS_TRADING_ENGINE_QUICK_START.md` | 7.4K | Oct 20 | Legacy | Archive | Trading quickstart guide |
| `/docs/PORTFOLIO_ALLOCATION_SYSTEM.md` | 29K | Oct 15 | Legacy | Archive | Trading portfolio allocation design |
| `/docs/BLACKLIST_INTEGRATION_GUIDE.md` | 19K | Oct 17 | Legacy | Archive | Trading blacklist features |
| `/docs/BLACKLIST_INTEGRATION_TODO_PHASES_5_8.md` | 13K | Oct 17 | Legacy | Archive | Trading blacklist roadmap |

#### Other Legacy Files
| File Path | Size | Modified | Category | Action | Reason |
|-----------|------|----------|----------|--------|--------|
| `/CLAUDE_backup.md` | 34K | Oct 18 | Legacy | Delete | Backup of old CLAUDE.md - superseded by current CLAUDE.md (Oct 26) |
| `/test_cli_login.py` | 2.8K | Oct 22 | Testing | Delete | Single test file - likely debug artifact |
| `/SPOCK_FUNCTIONAL_COMPLETENESS_ANALYSIS.md` | 33K | Oct 19 | Legacy | Archive | Trading system completeness analysis |
| `/modules/kis_data_collector.py.backup_20251019_223148` | 54K | Oct 19 | Legacy | Delete | Backup of old data collector |

---

### CATEGORY 2: QUANT PLATFORM FILES (KEEP - ACTIVE DEVELOPMENT)

**Status**: Current primary direction  
**Action**: Keep and extend  

#### Core Platform
| File Path | Size | Modified | Category | Action | Reason |
|-----------|------|----------|----------|--------|--------|
| `/quant_platform.py` | 5.4K | Oct 22 | Core | Keep | New CLI entry point for quant research platform ✅ |
| `/modules/backtesting/` | 376K | Oct 26 | Core | Keep | Backtesting engine infrastructure (vectorbt, custom engine) ✅ |
| `/modules/factors/` | 352K | Oct 24 | Core | Keep | Factor library (value, momentum, quality, growth, low-vol, efficiency) ✅ |
| `/modules/optimization/` | 192K | Oct 24 | Core | Keep | Portfolio optimization (mean-variance, risk parity, Black-Litterman, Kelly) ✅ |
| `/modules/risk/` | Active | Oct 24 | Core | Keep | Risk management (VaR, CVaR, stress testing, correlation analysis) ✅ |
| `/modules/strategies/` | Active | Oct 24 | Core | Keep | Strategy templates and runners ✅ |

#### Database (PostgreSQL)
| File Path | Size | Modified | Category | Action | Reason |
|-----------|------|----------|----------|--------|--------|
| `/modules/db_manager_postgres.py` | 83K | Oct 21 | Core | Keep | PostgreSQL + TimescaleDB manager for unlimited OHLCV retention ✅ |

#### API & Dashboard
| File Path | Size | Modified | Category | Action | Reason |
|-----------|------|----------|----------|--------|--------|
| `/api/` | 132K | Oct 22 | Core | Keep | FastAPI backend (strategy CRUD, backtest routes, optimization) ✅ |
| `/cli/` | - | Oct 22 | Core | Keep | CLI infrastructure (auth, setup) ✅ |
| `/dashboard/` | Minimal | Oct 21 | Core | Keep | Streamlit dashboard (minimal for now, expand in P2) |

#### Quant Documentation
| File Path | Size | Modified | Category | Action | Reason |
|-----------|------|----------|----------|--------|--------|
| `/CLAUDE.md` | 19K | Oct 26 | Current | Keep | Active project instructions ✅ |
| `/docs/QUANT_BACKTESTING_ENGINES.md` | - | Oct 26 | Current | Keep | Backtesting engine comparison (custom vs vectorbt) |
| `/docs/QUANT_DATABASE_SCHEMA.md` | - | Oct 26 | Current | Keep | PostgreSQL schema design |
| `/docs/PHASE1_BACKTEST_ENGINE_EXECUTION_PLAN.md` | 24K | Oct 26 | Current | Keep | Backtesting engine implementation plan |
| `/docs/PHASE1_DETAILED_TASKS.md` | 47K | Oct 26 | Current | Keep | Phase 1 detailed breakdown |
| `/docs/IMPLEMENTATION_ROADMAP.md` | 18K | Oct 26 | Current | Keep | Quant platform roadmap |
| `/docs/UNIFIED_DEVELOPMENT_ROADMAP.md` | - | Oct 26 | Current | Keep | Development phases roadmap |
| `/docs/WALK_FORWARD_VALIDATION_GUIDE.md` | - | Oct 26 | Current | Keep | Out-of-sample testing methodology |

---

### CATEGORY 3: REUSABLE COMPONENTS (KEEP - 70% CODE REUSE)

**Status**: Multi-region, multi-market infrastructure  
**Action**: Keep and adapt for quant platform  

#### Data Collection (KIS API, APIs)
| File Path | Size | Modified | Category | Action | Reason |
|-----------|------|----------|----------|--------|--------|
| `/modules/api_clients/` | - | Oct 21 | Core | Keep | KIS, Polygon, yfinance, AkShare APIs (multi-region data sources) |
| `/modules/kis_data_collector.py` | 56K | Oct 19 | Core | Keep | KIS API OHLCV data collection (adaptable for quant research) |
| `/modules/fundamental_data_collector.py` | 25K | Oct 21 | Core | Keep | DART API fundamental data (financial metrics for factors) |
| `/modules/fx_data_collector.py` | 21K | Oct 24 | Core | Keep | FX data collection (currency pair analysis) |

#### Market Adapters (Multi-Region)
| File Path | Size | Modified | Category | Action | Keep |
|-----------|------|----------|----------|--------|------|
| `/modules/market_adapters/` | - | Oct 21 | Core | Keep | 6 regional adapters (KR, US, CN, HK, JP, VN) |
| `/modules/market_adapters/validators/` | - | Oct 21 | Core | Keep | Ticker validation, market calendars, GICS mapping |
| `/modules/market_adapters/sector_mappers/` | - | Oct 21 | Core | Keep | GICS sector mapping |

#### Data Parsers
| File Path | Size | Modified | Category | Action | Reason |
|-----------|------|----------|----------|----------|--------|
| `/modules/parsers/` | - | Oct 21 | Core | Keep | Stock/ETF parsers for all 6 regions |
| `/modules/parsers/cn_stock_parser.py` | - | Oct 21 | Core | Keep | China ticker/sector normalization |
| `/modules/parsers/us_stock_parser.py` | - | Oct 21 | Core | Keep | US SIC → GICS mapping |
| `/modules/parsers/jp_stock_parser.py` | - | Oct 21 | Core | Keep | Japan TSE → GICS mapping |

#### Financial Calculators
| File Path | Size | Modified | Category | Action | Reason |
|-----------|------|----------|----------|--------|--------|
| `/modules/kelly_calculator.py` | 58K | Oct 17 | Core | Keep | Position sizing (Kelly criterion) - extend for multi-asset portfolio |
| `/modules/stock_kelly_calculator.py` | - | Oct 17 | Core | Keep | Stock-specific Kelly implementation |
| `/modules/ic_calculator.py` | 15K | Oct 24 | Core | Keep | Information Coefficient calculation for factor analysis |

#### Financial Data
| File Path | Size | Modified | Category | Action | Reason |
|-----------|------|----------|----------|--------|--------|
| `/modules/dart_api_client.py` | 37K | Oct 25 | Core | Keep | DART API for Korean fundamental data |
| `/modules/fx_valuation_analyzer.py` | 29K | Oct 24 | Core | Keep | FX valuation metrics analysis |
| `/modules/stock_metadata_enricher.py` | - | Oct 21 | Core | Keep | Stock metadata enhancement |

#### Utilities
| File Path | Size | Modified | Category | Action | Reason |
|-----------|------|----------|----------|--------|--------|
| `/modules/stock_utils.py` | - | Oct 21 | Core | Keep | Market hours, date utilities, validation |
| `/modules/exchange_rate_manager.py` | 18K | Oct 16 | Core | Keep | Currency conversion utilities |
| `/modules/stock_pre_filter.py` | - | Oct 17 | Core | Keep | Pre-filtering logic (can be adapted) |
| `/modules/alert_system.py` | 20K | Oct 17 | Core | Keep | Alert infrastructure (can be extended for quant) |

---

### CATEGORY 4: EVALUATION REQUIRED (CONDITIONAL KEEP)

**Status**: Potentially useful, needs assessment  
**Action**: Review and decide case-by-case  

| File Path | Size | Modified | Category | Decision | Reason |
|-----------|------|----------|----------|----------|--------|
| `/modules/db_manager_sqlite.py` | 69K | Oct 21 | Database | Keep-Ref | Legacy SQLite - keep as reference for migration path |
| `/modules/scanner.py` | - | Oct 17 | Trading | Archive | Stock screening for trading (may inform factor selection) |
| `/modules/layered_scoring_engine.py` | 20K | Oct 17 | Trading | Archive | Scoring engine (architecture pattern useful) |
| `/modules/integrated_scoring_system.py` | 20K | Oct 17 | Trading | Archive | Scoring integration (pattern for factor combination) |
| `/modules/stock_sentiment.py` | - | Oct 17 | Analysis | Keep | Stock sentiment analysis (potential alternative factor) |
| `/modules/stock_gpt_analyzer.py` | - | Oct 17 | Analysis | Keep | GPT chart analysis (alternative to technical indicators) |
| `/modules/portfolio_manager.py` | 25K | Oct 15 | Portfolio | Keep | Portfolio management utilities (adaptable for quant) |
| `/modules/portfolio_allocator.py` | 24K | Oct 15 | Portfolio | Keep | Allocation logic (basis for optimization) |
| `/modules/risk_manager.py` | - | Oct 17 | Risk | Keep | Risk management (foundation for quant risk module) |
| `/modules/failure_tracker.py` | 36K | Oct 3 | Ops | Keep | Failure recovery (system reliability) |
| `/modules/auto_recovery_system.py` | 50K | Oct 16 | Ops | Keep | Automatic recovery (system resilience) |
| `/modules/market_filter_manager.py` | 19K | Oct 16 | Ops | Keep | Market filtering (infrastructure) |
| `/modules/blacklist_manager.py` | 20K | Oct 17 | Trading | Archive | Trading blacklist (not needed for research) |
| `/modules/sns_notification_system.py` | - | Oct 17 | Ops | Keep | Notifications (operational alerts) |
| `/modules/metrics_collector.py` | 21K | Oct 17 | Ops | Keep | Metrics collection (monitoring) |

---

### CATEGORY 5: ANALYSIS & REPORTS (EVALUATE RETENTION)

**Status**: Detailed analysis outputs from development  
**Size**: 8.3M across 30+ reports  
**Action**: Archive to `/archive/analysis_reports/` (not needed for active development)  

#### Recent Analysis (Keep as reference)
| File Path | Size | Modified | Status | Action |
|-----------|------|----------|--------|--------|
| `/analysis/walk_forward_validation_success_report_20251026.md` | 14K | Oct 26 | Latest | Keep for Phase 1 reference |
| `/analysis/phase3_equal_weighted_validation_results_20251026.md` | 11K | Oct 26 | Latest | Keep for Phase 1 reference |
| `/analysis/comprehensive_optimization_report_20251024.md` | 26K | Oct 24 | Recent | Keep as optimization baseline |

#### Older Analysis (Archive)
| File Path | Size | Modified | Status | Action |
|-----------|------|----------|--------|--------|
| `/analysis/*_20251023_*.md` | Various | Oct 23 | Dated | Archive |
| `/analysis/*_20251022_*.md` | Various | Oct 22 | Dated | Archive |
| `/analysis/IC_*.md` | 15K+ | Oct 23 | Dated | Archive |
| `/analysis/MONTH_*.md` | 20K+ | Oct 24 | Dated | Archive |

#### Complete List to Archive
- 25+ analysis reports from Oct 23-26 (detailed IC, factor optimization, validation reports)
- Keep: 3 latest (reference for Phase 1)
- Archive: Rest to `/archive/analysis_reports_20251026/`

---

### CATEGORY 6: TEST FILES (EVALUATE)

**Status**: 30+ test files, 1.7M total  
**Action**: Keep quant tests, delete trading tests  

#### Quant Platform Tests (KEEP)
| File Path | Status | Action |
|-----------|--------|--------|
| `/tests/backtesting/` | Active | Keep |
| `/tests/test_*_factor*.py` | Active | Keep |
| `/tests/test_*_optimization*.py` | Active | Keep |
| `/tests/test_risk*.py` | Active | Keep |
| `/tests/test_*_integration*.py` (quant-related) | Active | Keep |

#### Market & Adapter Tests (KEEP - Reusable)
| File Path | Status | Action |
|-----------|--------|--------|
| `/tests/test_*_adapter.py` (US, CN, HK, JP, VN) | Active | Keep |
| `/tests/test_*_parser.py` | Active | Keep |
| `/tests/test_integration_multi_region.py` | Active | Keep |
| `/tests/test_e2e_all_markets.py` | Active | Keep |

#### Trading Tests (DELETE)
| File Path | Status | Action |
|-----------|--------|--------|
| `/tests/test_kis_trading_engine.py` | Legacy | Delete |
| `/tests/test_kis_authentication_day1.py` | Legacy | Delete |
| `/tests/test_kis_price_and_buy_day2.py` | Legacy | Delete |
| `/tests/test_kis_sell_and_integration_day3.py` | Legacy | Delete |
| `/tests/test_trading_engine_blacklist.py` | Legacy | Delete |
| `/tests/test_phase5_task4_integration.py` | Legacy | Delete |
| `/tests/test_portfolio_manager.py` (trading-focused) | Legacy | Delete |
| `/tests/test_kis_index_query_v*.py` | Legacy | Delete |

---

### CATEGORY 7: DOCUMENTATION (CONSOLIDATE)

**Status**: 150+ markdown files, 4.2M in docs/  
**Action**: Archive old docs, maintain current roadmap  

#### Current Documentation (KEEP)
| File Path | Size | Purpose | Action |
|-----------|------|---------|--------|
| `/CLAUDE.md` | 19K | **Current project instructions** | Keep (Oct 26) |
| `/docs/PHASE1_BACKTEST_ENGINE_EXECUTION_PLAN.md` | 24K | Backtesting Phase 1 | Keep |
| `/docs/PHASE1_DETAILED_TASKS.md` | 47K | Detailed task breakdown | Keep |
| `/docs/IMPLEMENTATION_ROADMAP.md` | 18K | Development roadmap | Keep |
| `/docs/QUANT_BACKTESTING_ENGINES.md` | - | Engine comparison | Keep |
| `/docs/QUANT_DATABASE_SCHEMA.md` | - | DB schema design | Keep |
| `/docs/WALK_FORWARD_VALIDATION_GUIDE.md` | - | Validation methodology | Keep |

#### Legacy Documentation (ARCHIVE)
| File Pattern | Files | Total Size | Action |
|--------------|-------|-----------|--------|
| `/docs/PHASE5_*.md` | 5 files | 80K+ | Archive |
| `/docs/KIS_TRADING_ENGINE_*.md` | 6 files | 110K+ | Archive |
| `/docs/MAKENAIDE_GPT_ANALYZER_*.md` | 2 files | 45K | Archive |
| `/docs/PORTFOLIO_ALLOCATION_SYSTEM.md` | 1 file | 29K | Archive |
| `/docs/HISTORICAL_*.md` | 4 files | 80K+ | Archive |
| `/docs/ETF_*.md` | 10 files | 180K+ | Archive |
| `/docs/PHASE1_ETF_*.md` | 3 files | 40K | Archive |
| `/docs/MASTER_FILE_*.md` | 8 files | 120K+ | Archive |
| `/docs/*COMPLETION_REPORT*.md` | 30+ files | 800K+ | Archive |

---

### CATEGORY 8: CONFIGURATION FILES (KEEP)

**Status**: Market-specific, multi-region configurations  
**Action**: Keep all (essential infrastructure)  

| Directory | Files | Purpose | Action |
|-----------|-------|---------|--------|
| `/config/market_filters/` | 6 YAML | Regional market filtering | Keep |
| `/config/holidays/` | 6 YAML | Market-specific holidays | Keep |
| `/config/portfolio_templates.yaml` | 1 | Portfolio templates | Keep |
| `/config/optimization_constraints.yaml` | 1 | Portfolio constraints | Keep |
| `/config/risk_config.yaml` | 1 | Risk management config | Keep |
| `/config/backtest_config.yaml` | 1 | Backtesting parameters | Keep |
| `/config/factor_definitions.yaml` | 1 | Factor definitions | Keep |
| `/config/cli_config.yaml` | 1 | CLI configuration | Keep |
| `/config/market_tiers.yaml` | 1 | Market tier definitions | Keep |

---

### CATEGORY 9: INFRASTRUCTURE (KEEP/OPTIMIZE)

**Status**: Essential for operations  
**Action**: Keep monitoring, optimize data/logs  

| Component | Size | Action | Reason |
|-----------|------|--------|--------|
| `/monitoring/` | 504K | Keep | Prometheus + Grafana stack (operational monitoring) |
| `/logs/` | 467M | Archive | Application logs >30 days old (automatic cleanup) |
| `/data/` | 3.4G | Keep | OHLCV data, master files (research data) |
| `/backups/` | 186M | Clean | Archive old backups (keep 3 recent) |
| `/migration_ohlcv.log` | 192M | Delete | One-time migration log (no longer needed) |

---

## SUMMARY STATISTICS

### File Count by Category

| Category | Files | Size | Status |
|----------|-------|------|--------|
| **Spock Legacy (Trading)** | 12-15 | 200K+ | Archive/Delete |
| **Quant Platform** | 50+ | 1.2M | Keep (Active) |
| **Reusable Components** | 80+ | 1.5M | Keep (Adapt) |
| **API/Dashboard** | 30+ | 500K | Keep (Extend) |
| **Tests** | 30+ | 1.7M | Keep (Clean) |
| **Configuration** | 20+ | 32M+ | Keep (Essential) |
| **Documentation** | 150+ | 4.2M | Archive (Clean) |
| **Infrastructure** | Various | 2.1G | Keep (Optimize) |
| **Analysis Reports** | 30+ | 8.3M | Archive (Clean) |
| **Data/Backups** | Various | 3.7G | Optimize (Clean) |

### Cleanup Impact

**Deletion Candidates** (Safe to delete):
- 12-15 legacy trading files: ~200K
- 6 trading test files: ~100K
- 30+ old analysis reports: ~8.3M
- 1 migration log: ~192M
- Backup files: ~186M (keep 3)
- Logs >30 days: ~467M (auto-cleanup)

**Potential Cleanup**: ~853M space savings

---

## IMPLEMENTATION ROADMAP

### Phase 1: Archive Legacy Trading Files (Immediate)
```
1. Create /archive/spock_legacy/ directory
2. Move trading-specific files:
   - /spock.py
   - /spock_PRD.md
   - /modules/kis_trading_engine.py
   - All PHASE5_TRADING_*.md files
   - All KIS_TRADING_ENGINE_*.md docs
3. Keep reference copies of:
   - CLAUDE_backup.md (for history)
   - Architecture diagrams
4. Delete: Old PRDs, completion reports
```

### Phase 2: Clean Test Files (Week 1)
```
1. Delete 6 trading test files
   - test_kis_trading_engine.py
   - test_kis_authentication_day1.py
   - test_kis_price_and_buy_day2.py
   - test_kis_sell_and_integration_day3.py
   - test_trading_engine_blacklist.py
   - test_phase5_task4_integration.py
2. Keep: All quant, adapter, integration tests
3. Verify: pytest runs successfully
```

### Phase 3: Archive Documentation (Week 2)
```
1. Create /archive/documentation_legacy/
2. Move 100+ legacy markdown files
3. Keep active documents:
   - /CLAUDE.md (current instructions)
   - /docs/IMPLEMENTATION_ROADMAP.md
   - /docs/PHASE1_*.md (quant-related)
4. Update documentation index
```

### Phase 4: Cleanup Data & Logs (Week 3)
```
1. Archive old analysis reports (8.3M)
2. Clean logs >30 days (automate)
3. Delete migration logs
4. Clean old backups (keep 3 recent)
5. Compress archived data
```

### Phase 5: Update Project Structure Documentation (Week 3)
```
1. Update /CLAUDE.md with new structure
2. Create PROJECT_STRUCTURE.md
3. Update README.md with roadmap
4. Add deprecation notices to legacy files
```

---

## RECOMMENDATIONS

### Immediate Actions (This Week)

1. **Backup Current State**
   ```bash
   git tag -a v1_spock_legacy_20251026 -m "Spock trading system checkpoint"
   git commit -m "Spock legacy: Final trading system state before pivot to quant platform"
   ```

2. **Create Archive Structure**
   ```bash
   mkdir -p /archive/{spock_legacy,documentation_legacy,analysis_legacy}
   mkdir -p /archive/test_backups
   ```

3. **Verify Quant Platform Integrity**
   - Run all quant platform tests
   - Validate backtesting engine
   - Check factor library completeness
   - Confirm database migration status

4. **Document Architectural Pivot**
   - Update CLAUDE.md with clear "Transition Complete" note
   - Add deprecation notices to legacy files
   - Create migration guide for developers

### Short-Term (Next 2 Weeks)

1. **Consolidate Configuration**
   - Audit all 32M+ in /config/
   - Identify unused market filters
   - Create config consolidation plan

2. **Optimize Storage**
   - Archive 8.3M analysis reports
   - Clean 467M logs (automate)
   - Delete 192M migration log
   - Compress backups (keep 3)
   - Expected recovery: ~853M space

3. **Strengthen Tests**
   - Delete 6 trading tests
   - Verify quant tests are comprehensive
   - Add missing test coverage for Phase 1

4. **Update Documentation**
   - Archive 100+ legacy docs
   - Consolidate quant documentation
   - Create developer onboarding guide

### Long-Term (Next Month)

1. **Maintain Clean State**
   - Establish files to delete (legacy only)
   - Automate log cleanup (30-day retention)
   - Schedule quarterly documentation review

2. **Enable Future Transitions**
   - Ensure clean separation: Legacy vs. Current
   - Document reusable component locations
   - Maintain backward compatibility paths

---

## RISK ASSESSMENT

### Low Risk - Safe to Delete
- Legacy trading engine files (kis_trading_engine.py, spock.py)
- Trading-specific test files (6 files)
- Migration logs (one-time use)
- Old completion reports (historical reference only)

### Medium Risk - Archive First
- Old analysis reports (keep 3 recent, archive rest)
- Legacy documentation (preserve for historical reference)
- Old backup files (keep 3 recent)

### No Risk - Keep Always
- Quant platform files (active development)
- Market adapters (70% code reuse)
- API clients (essential infrastructure)
- Configuration files (essential for operations)
- Test infrastructure (growing codebase)

---

## CONCLUSION

**The project has successfully pivoted from automated trading (Spock) to quantitative research (Quant Platform).**

- 70% of code remains reusable (market adapters, APIs, data collection)
- 30% is new quant-specific infrastructure (backtesting, factors, optimization)
- Legacy trading system (12-15 files, ~200K) can be archived safely
- Estimated cleanup potential: ~853M space savings

**Next steps**: Archive legacy files, clean tests, consolidate documentation, and establish clean project structure for accelerated Phase 1 development.

