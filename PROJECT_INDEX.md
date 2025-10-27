# Spock Trading System - Project Index

**Status**: Production-ready multi-region automated stock trading system
**Version**: Phase 6 Complete (6 markets: KR, US, CN, HK, JP, VN)
**Last Updated**: 2025-10-18

## Quick Navigation

### 🚀 Getting Started
- [Quick Start Guide](#quick-start-guide) - New developer onboarding
- [CLAUDE.md](CLAUDE.md) - Complete project documentation
- [spock_PRD.md](spock_PRD.md) - Product requirements and investor journey

### 📚 Core Documentation
- [Architecture Overview](#architecture-overview)
- [Component Reference](COMPONENT_REFERENCE.md) - Module documentation
- [API Integration Guide](API_INTEGRATION_GUIDE.md) - KIS API reference
- [Troubleshooting Index](TROUBLESHOOTING_INDEX.md) - Common issues

### 🌍 Multi-Region Architecture
- [Global Market Expansion](docs/GLOBAL_MARKET_EXPANSION.md) - Multi-region overview
- [Global DB Architecture](docs/GLOBAL_DB_ARCHITECTURE_ANALYSIS.md) - Database design
- [Global Adapter Design](docs/GLOBAL_ADAPTER_DESIGN.md) - Adapter pattern

### 🔧 Operations
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) - Production deployment
- [Operations Runbook](docs/OPERATIONS_RUNBOOK.md) - Daily operations
- [Monitoring Guide](monitoring/README.md) - Prometheus/Grafana setup

---

## Project Statistics

| Metric | Count | Description |
|--------|-------|-------------|
| **Python Modules** | 85 | Core functionality |
| **Test Files** | 57 | Unit/integration/E2E tests |
| **Scripts** | 59 | Utilities and automation |
| **Documentation** | 100+ | MD files across project |
| **Markets** | 6 | KR, US, CN, HK, JP, VN |
| **Test Coverage** | 71-82% | Adapter test coverage |

---

## Architecture Overview

### Execution Flow (Phase-Based Pipeline)

```
Phase 0: Stock Scanner          → Ticker discovery with filters
Phase 1: Data Collection        → Incremental OHLCV (250-day retention)
Phase 2: Technical Filter       → Weinstein Stage 2 + LayeredScoringEngine
Phase 3: GPT Chart Analyzer     → AI pattern recognition (optional)
Phase 4: Kelly Calculator       → Pattern-based position sizing
Phase 5: Market Sentiment       → VIX + Foreign/Institution analysis
Phase 6: Trading Engine         → KIS API execution
```

### Core Components

```
spock/
├── modules/                    # 85 Python modules
│   ├── market_adapters/       # 6 regions (KR, US, CN, HK, JP, VN)
│   ├── api_clients/           # KIS, Polygon, AkShare, yfinance
│   ├── parsers/               # Ticker/sector normalization
│   └── [core modules]         # Scoring, Kelly, Trading, Portfolio
├── tests/                      # 57 test files
├── scripts/                    # 59 utility scripts
├── docs/                       # 100+ documentation files
├── config/                     # API credentials, market hours
├── data/                       # SQLite database + backups
├── logs/                       # Application logs (7-day retention)
└── monitoring/                 # Prometheus/Grafana stack
```

---

## Market Coverage (Phase Completion)

### Phase 1: Korea (KR) - ✅ COMPLETE
- **Markets**: KOSPI, KOSDAQ
- **API**: KIS Domestic API
- **Rate Limit**: 20 req/sec
- **Documentation**: [Phase 1 Reports](docs/PHASE1_*)
- **Status**: Production-ready

### Phase 2: United States (US) - ✅ COMPLETE
- **Markets**: NYSE, NASDAQ, AMEX
- **API**: KIS Overseas API (Phase 6) or Polygon.io
- **Rate Limit**: 20 req/sec (KIS) | 5 req/min (Polygon)
- **Performance**: 240x faster with KIS API
- **Documentation**: [US Adapter Deployment Guide](docs/US_ADAPTER_DEPLOYMENT_GUIDE.md)
- **Status**: Production-ready

### Phase 3: China/Hong Kong (CN/HK) - ✅ COMPLETE
- **Markets**: SSE, SZSE (CN) | HKEX (HK)
- **API**: KIS Overseas API (Phase 6) or AkShare+yfinance
- **Rate Limit**: 20 req/sec (KIS) | 1.5 req/sec (AkShare)
- **Performance**: 13x faster (CN), 20x faster (HK) with KIS API
- **Test Coverage**: 82.47% (CN), 71.70% (HK)
- **Documentation**: [Phase 3 Completion Report](docs/PHASE3_COMPLETION_REPORT.md)
- **Status**: Production-ready

### Phase 4: Japan (JP) - ✅ COMPLETE
- **Markets**: Tokyo Stock Exchange (TSE)
- **API**: KIS Overseas API (Phase 6) or yfinance
- **Rate Limit**: 20 req/sec (KIS) | 1.0 req/sec (yfinance)
- **Performance**: 20x faster with KIS API
- **Test Coverage**: 100% (16/16 tests passed)
- **Documentation**: [Phase 4 JP Completion Report](docs/PHASE4_JP_COMPLETION_REPORT.md)
- **Status**: Production-ready

### Phase 5: Vietnam (VN) - ✅ COMPLETE
- **Markets**: HOSE, HNX
- **API**: KIS Overseas API (Phase 6) or yfinance
- **Rate Limit**: 20 req/sec (KIS) | 1.0 req/sec (yfinance)
- **Performance**: 20x faster with KIS API
- **Test Coverage**: 100% (17/17 tests passed)
- **Documentation**: [Phase 5 VN Completion Report](docs/PHASE5_VN_COMPLETION_REPORT.md)
- **Status**: Production-ready

### Phase 6: KIS Global Integration - ✅ COMPLETE 🚀
- **Purpose**: Replace external APIs with unified KIS overseas stock API
- **Markets**: US, HK, CN, JP, VN (5 markets, single API key)
- **Performance**: 13x-240x faster data collection
- **Advantage**: Only tradable tickers for Korean investors (~60% fewer)
- **Test Coverage**: 29.73%-71.70% across adapters
- **Documentation**: [Phase 6 Completion Report](docs/PHASE6_COMPLETION_REPORT.md)
- **Status**: Production-ready

---

## Documentation Categories

### 1. Setup & Configuration (🔧)
Essential guides for getting started

| Document | Purpose | Audience |
|----------|---------|----------|
| [KIS API Credential Setup](docs/KIS_API_CREDENTIAL_SETUP_GUIDE.md) | API key configuration | Developers |
| [CLI Usage Guide](docs/CLI_USAGE_GUIDE.md) | Command-line reference | Operators |
| [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) | Production deployment | DevOps |

### 2. Architecture & Design (🏗️)
System design and technical decisions

| Document | Purpose | Category |
|----------|---------|----------|
| [Global Market Expansion](docs/GLOBAL_MARKET_EXPANSION.md) | Multi-region architecture | Architecture |
| [Global DB Architecture](docs/GLOBAL_DB_ARCHITECTURE_ANALYSIS.md) | Database design | Data Layer |
| [Global Adapter Design](docs/GLOBAL_ADAPTER_DESIGN.md) | Adapter pattern | Design Pattern |
| [Region-Based Architecture](docs/REGION_BASED_ARCHITECTURE.md) | Region isolation | Architecture |
| [Unified Market Adapters](docs/UNIFIED_MARKET_ADAPTERS.md) | Adapter unification | Design Pattern |

### 3. Data Collection & Processing (📊)
ETF, stock metadata, and OHLCV collection

| Document | Purpose | Phase |
|----------|---------|-------|
| [ETF Implementation Plan](docs/ETF_IMPLEMENTATION_PLAN.md) | ETF data collection | Design |
| [ETF Data Collection Design](docs/ETF_DATA_COLLECTION_DESIGN.md) | ETF architecture | Design |
| [ETF Holdings DB Design](docs/ETF_HOLDINGS_DB_DESIGN.md) | Holdings storage | Database |
| [Stock Metadata Enrichment](docs/GLOBAL_STOCK_METADATA_ENRICHMENT_DESIGN.md) | Metadata enrichment | Design |
| [KIS Overseas Master File Design](docs/KIS_OVERSEAS_MASTER_FILE_DESIGN.md) | Master file integration | Phase 6 |

### 4. Trading & Analysis (📈)
Technical analysis, scoring, and trading execution

| Document | Purpose | Component |
|----------|---------|-----------|
| [Filtering System Design](docs/FILTERING_SYSTEM_DESIGN.md) | Multi-stage filtering | Stage 1 |
| [Filtering System Design V2](docs/FILTERING_SYSTEM_DESIGN_V2_GLOBAL.md) | Global filtering | Stage 1 |
| [Stage 1B Technical Filter](docs/STAGE1B_TECHNICAL_FILTER_DOCUMENTATION.md) | Technical filtering | Stage 1B |
| [Stock GPT Analyzer Design](docs/STOCK_GPT_ANALYZER_DESIGN.md) | AI chart analysis | Stage 3 |
| [KIS Trading Engine Design](docs/KIS_TRADING_ENGINE_DESIGN.md) | Order execution | Trading |
| [Portfolio Allocation System](docs/PORTFOLIO_ALLOCATION_SYSTEM.md) | Position sizing | Risk Mgmt |

### 5. Monitoring & Operations (🔍)
System monitoring, logging, and troubleshooting

| Document | Purpose | Tool |
|----------|---------|------|
| [Monitoring README](monitoring/README.md) | Prometheus/Grafana setup | Monitoring |
| [Operations Runbook](docs/OPERATIONS_RUNBOOK.md) | Daily operations | Operations |
| [Operational Runbook (Master Files)](docs/OPERATIONAL_RUNBOOK_MASTER_FILES.md) | Master file ops | Operations |
| [Auto Cleanup Feature](docs/AUTO_CLEANUP_FEATURE.md) | Automated cleanup | Maintenance |

### 6. Phase Completion Reports (✅)
Detailed phase implementation reports

| Phase | Markets | Documentation | Status |
|-------|---------|---------------|--------|
| **Phase 1** | Korea | [Phase 1 Validation](docs/PHASE1_VALIDATION_REPORT.md) | ✅ Complete |
| **Phase 2** | US | [US Adapter Deployment](docs/US_ADAPTER_DEPLOYMENT_GUIDE.md) | ✅ Complete |
| **Phase 3** | CN/HK | [Phase 3 Completion](docs/PHASE3_COMPLETION_REPORT.md) | ✅ Complete |
| **Phase 4** | Japan | [Phase 4 JP Completion](docs/PHASE4_JP_COMPLETION_REPORT.md) | ✅ Complete |
| **Phase 5** | Vietnam | [Phase 5 VN Completion](docs/PHASE5_VN_COMPLETION_REPORT.md) | ✅ Complete |
| **Phase 6** | KIS Global | [Phase 6 Completion](docs/PHASE6_COMPLETION_REPORT.md) | ✅ Complete |

### 7. Specialized Features (⚙️)
Advanced functionality and integrations

| Document | Purpose | Feature |
|----------|---------|---------|
| [Kelly GPT Integration](docs/KELLY_GPT_INTEGRATION_COMPLETION_REPORT.md) | GPT-powered Kelly sizing | AI Integration |
| [Stock Sentiment Design](docs/DESIGN_stock_sentiment_UPDATED.md) | Market sentiment analysis | Sentiment |
| [Exchange Rate Manager](docs/EXCHANGE_RATE_MANAGER_COMPLETION_REPORT.md) | Currency conversion | Multi-Currency |
| [Lot Size Implementation](docs/LOT_SIZE_IMPLEMENTATION_PLAN.md) | Market-specific lot sizes | Trading |
| [Hybrid Metadata Enrichment](docs/HYBRID_METADATA_ENRICHMENT_SUMMARY.md) | Multi-source metadata | Data Quality |

### 8. Migration & Troubleshooting (🔧)
Database migrations and issue resolution

| Document | Purpose | Type |
|----------|---------|------|
| [Region Propagation Migration](docs/REGION_PROPAGATION_MIGRATION_REPORT.md) | Region column migration | Migration |
| [ETF NULL Fields Troubleshooting](docs/ETF_NULL_FIELDS_TROUBLESHOOTING_REPORT.md) | NULL field resolution | Troubleshooting |
| [Token Caching Implementation](docs/TOKEN_CACHING_IMPLEMENTATION.md) | API token caching | Optimization |
| [US Adapter Token Limit Issue](docs/US_ADAPTER_TOKEN_LIMIT_ISSUE.md) | Rate limit handling | Troubleshooting |

---

## Key Files Quick Reference

### Configuration Files
```
config/
├── kis_api_config.py              # KIS API credentials
├── stock_blacklist.json           # Blacklisted tickers
├── market_schedule.json           # Market hours
├── cn_holidays.yaml               # China trading calendar
├── hk_holidays.yaml               # Hong Kong trading calendar
├── jp_holidays.yaml               # Japan trading calendar
└── vn_holidays.yaml               # Vietnam trading calendar
```

### Core Modules
```
modules/
├── kis_data_collector.py          # OHLCV data collection
├── stock_scanner.py               # Ticker scanning
├── kis_trading_engine.py          # Trading execution
├── kelly_calculator.py            # Position sizing
├── stock_sentiment.py             # Market sentiment
├── stock_gpt_analyzer.py          # GPT chart analysis
├── layered_scoring_engine.py      # 100-point scoring
├── portfolio_manager.py           # Portfolio tracking
├── risk_manager.py                # Risk management
└── db_manager_sqlite.py           # Database manager
```

### Market Adapters (Phase 6 - KIS API)
```
modules/market_adapters/
├── base_adapter.py                # Abstract base class
├── kr_adapter.py                  # Korea (KIS Domestic)
├── us_adapter_kis.py              # US (KIS Overseas) ✅
├── cn_adapter_kis.py              # China (KIS Overseas) ✅
├── hk_adapter_kis.py              # Hong Kong (KIS Overseas) ✅
├── jp_adapter_kis.py              # Japan (KIS Overseas) ✅
└── vn_adapter_kis.py              # Vietnam (KIS Overseas) ✅
```

### Scripts
```
scripts/
├── setup_credentials.py           # Interactive credential setup
├── validate_kis_credentials.py    # Credential validation
├── test_kis_connection.py         # Connection diagnostics
├── deploy_us_adapter.py           # US market deployment
├── migrate_region_column.py       # Database migration
└── check_token_cache.py           # Token cache inspection
```

---

## Common Workflows

### 1. Initial Setup
```bash
# Step 1: Setup KIS API credentials
python3 scripts/setup_credentials.py

# Step 2: Validate credentials
python3 scripts/validate_kis_credentials.py

# Step 3: Test connection
python3 scripts/test_kis_connection.py

# Step 4: Initialize database
python3 -c "from spock_init_db import SpockDatabaseInitializer; \
SpockDatabaseInitializer().initialize_complete_database()"
```

### 2. Deploy US Market (Phase 6)
```bash
# Full deployment (scan + OHLCV collection)
python3 scripts/deploy_us_adapter.py --full --days 250

# Expected time: ~10 minutes
# Expected tickers: ~3,000
# Expected OHLCV rows: ~750,000
```

### 3. Run Main Pipeline
```bash
# Full pipeline with moderate risk profile
python3 spock.py --risk-level moderate

# Dry run for testing
python3 spock.py --dry-run --no-gpt

# Debug mode
python3 spock.py --debug --log-level DEBUG
```

### 4. Monitor System
```bash
# Start monitoring stack
cd monitoring && docker-compose up -d

# Start metrics exporter
python3 monitoring/exporters/spock_exporter.py --port 8000 &

# Access Grafana: http://localhost:3000 (admin/spock2025)
# Access Prometheus: http://localhost:9090
```

---

## Testing Strategy

### Test Categories
- **Unit Tests** (30 files): Individual module testing
- **Integration Tests** (15 files): Multi-module workflows
- **E2E Tests** (12 files): Full pipeline validation

### Run Tests
```bash
# All tests
pytest

# Specific adapter
pytest tests/test_us_adapter_kis.py -v

# Integration tests
pytest tests/test_integration_multi_region.py -v

# E2E tests
pytest tests/test_e2e_all_markets.py -v
```

---

## Performance Benchmarks

### API Performance (Phase 6 KIS vs Legacy)

| Market | KIS API | Legacy API | Speedup | Tickers |
|--------|---------|------------|---------|---------|
| **US** | 20 req/sec | 5 req/min | **240x** | ~3,000 |
| **CN** | 20 req/sec | 1.5 req/sec | **13x** | ~300-500 |
| **HK** | 20 req/sec | 1.0 req/sec | **20x** | ~500-1,000 |
| **JP** | 20 req/sec | 1.0 req/sec | **20x** | ~500-1,000 |
| **VN** | 20 req/sec | 1.0 req/sec | **20x** | ~100-300 |

### Data Collection Time

| Market | Tickers | OHLCV (250 days) | Total Time |
|--------|---------|------------------|------------|
| **US** | ~3,000 | ~750,000 rows | ~10 min |
| **CN** | ~300-500 | ~75,000-125,000 rows | ~3-5 min |
| **HK** | ~500-1,000 | ~125,000-250,000 rows | ~5-8 min |
| **JP** | ~500-1,000 | ~125,000-250,000 rows | ~5-8 min |
| **VN** | ~100-300 | ~25,000-75,000 rows | ~2-4 min |

---

## Database Schema

### Core Tables
- **tickers**: Stock/ETF ticker metadata (region, sector, market_cap, lot_size)
- **ohlcv_data**: 250-day OHLCV with technical indicators (region-tagged)
- **technical_analysis**: LayeredScoringEngine results (100-point scores)
- **trades**: Order execution history
- **portfolio**: Current positions and P&L
- **kelly_sizing**: Pattern-based position sizing
- **kis_api_logs**: API request/response logs

### Region Isolation
- **region column**: Auto-injected by BaseAdapter (KR, US, CN, HK, JP, VN)
- **Unique constraint**: (ticker, region, timeframe, date)
- **Migration**: 691,854 rows migrated (2025-10-15)
- **Quality check**: 0 NULL regions, 0 cross-region contamination

---

## Support & Resources

### Documentation
- **Primary**: [CLAUDE.md](CLAUDE.md) - Complete reference
- **Quick Start**: [Quick Start Guide](#quick-start-guide)
- **API Reference**: [API Integration Guide](API_INTEGRATION_GUIDE.md)
- **Troubleshooting**: [Troubleshooting Index](TROUBLESHOOTING_INDEX.md)

### Monitoring
- **Grafana Dashboards**: 7 dashboards (Overview + 6 regions)
- **Prometheus Metrics**: 21 metrics (data quality, API health, performance)
- **Alert Rules**: 25 rules (critical, warning, info)

### Testing
- **Test Reports**: `test_reports/` directory
- **Coverage**: 71-82% across adapters
- **CI/CD**: GitHub Actions (future)

---

## Next Steps

### For New Developers
1. Read [CLAUDE.md](CLAUDE.md) - Complete project overview
2. Follow [Quick Start Guide](#quick-start-guide) - Setup environment
3. Review [Component Reference](COMPONENT_REFERENCE.md) - Module documentation
4. Study [Phase 6 Completion Report](docs/PHASE6_COMPLETION_REPORT.md) - Latest architecture

### For Operators
1. Read [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) - Production setup
2. Review [Operations Runbook](docs/OPERATIONS_RUNBOOK.md) - Daily operations
3. Setup [Monitoring](monitoring/README.md) - Grafana dashboards
4. Follow [US Adapter Deployment Guide](docs/US_ADAPTER_DEPLOYMENT_GUIDE.md) - Deploy first market

### For Contributors
1. Review [Global Adapter Design](docs/GLOBAL_ADAPTER_DESIGN.md) - Adapter pattern
2. Study [Testing Strategy](#testing-strategy) - Test requirements
3. Follow [Development Workflow](CLAUDE.md#development-workflow) - Best practices
4. Submit Pull Requests - Contribute improvements

---

## Changelog

### 2025-10-18
- Created PROJECT_INDEX.md with comprehensive navigation
- Indexed 100+ documentation files
- Categorized 85 modules, 57 tests, 59 scripts

### 2025-10-15 (Phase 6 Complete)
- KIS Global Integration complete (US, HK, CN, JP, VN)
- 13x-240x performance improvement over legacy APIs
- 23/23 tests passed, 29.73%-71.70% coverage

### 2025-10-14 (Phase 5 Complete)
- Vietnam market integration (yfinance)
- 17/17 tests passed (100% coverage)
- VN30 index tracking

### 2025-10-13 (Phase 4 Complete)
- Japan market integration (yfinance)
- 16/16 tests passed (100% coverage)
- TSE sector mapping

### 2025-10-12 (Phase 3 Complete)
- China/Hong Kong market integration
- 34/34 tests passed, 82.47% coverage
- CSRC → GICS sector mapping

---

**Last Updated**: 2025-10-18
**Maintained By**: Spock Development Team
**License**: Proprietary
