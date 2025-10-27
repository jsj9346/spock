# Quant Platform CLI Design - Quick Reference

**Full Design**: See `QUANT_PLATFORM_CLI_DESIGN.md` for complete specifications
**Implementation Checklist**: See `IMPLEMENTATION_CHECKLIST_CLI.md` for step-by-step tasks

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│           USER INTERFACES (Multi-Mode Support)              │
├──────────────┬──────────────┬──────────────────────────────┤
│   CLI        │    TUI       │    WebUI                     │
│  (argparse)  │  (Textual)   │  (Streamlit)                 │
└──────────────┴──────────────┴──────────────────────────────┘
                       ↕ HTTPS/REST + WebSocket
┌─────────────────────────────────────────────────────────────┐
│            BACKEND API (FastAPI)                            │
│  [Local: localhost:8000 | Cloud: AWS EC2]                  │
└─────────────────────────────────────────────────────────────┘
                       ↕ PostgreSQL Protocol
┌─────────────────────────────────────────────────────────────┐
│       DATABASE (PostgreSQL + TimescaleDB)                   │
│  [Local: localhost:5432 | Cloud: AWS RDS]                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Three Interface Modes

### 1. CLI (Command Line Interface)
**Purpose**: Scriptable automation, batch jobs, CI/CD
**Library**: `argparse` (standard library) + `rich` (formatting)

**Example Usage**:
```bash
# Authentication
quant_platform.py auth login --email user@example.com

# Run backtest
quant_platform.py backtest run \
  --strategy momentum_value \
  --start 2020-01-01 --end 2023-12-31 \
  --initial-capital 100000000

# Portfolio optimization
quant_platform.py optimize \
  --method mean_variance \
  --target-return 0.15

# Cloud mode
quant_platform.py --mode cloud backtest run --strategy momentum_value
```

**Command Groups**:
- `auth` - Login/logout/status
- `strategy` - List/create/update/delete strategies
- `backtest` - Run/list/show/delete backtests
- `optimize` - Portfolio optimization
- `factor` - Factor analysis
- `risk` - VaR/CVaR/stress testing
- `report` - Generate reports (PDF/HTML/Markdown)
- `config` - Configuration management
- `cloud` - Cloud deployment operations

---

### 2. TUI (Terminal User Interface)
**Purpose**: Interactive terminal experience with keyboard navigation
**Library**: `textual` (modern TUI framework)

**Launch**:
```bash
quant_platform.py --tui
```

**Screens**:
1. **Dashboard** - Portfolio overview, recent backtests
2. **Strategies** - Interactive strategy management
3. **Backtests** - Results viewer with ASCII charts
4. **Portfolio** - Holdings, sector allocation, risk metrics
5. **Settings** - Configuration, auth status, logs

**Key Bindings**:
- `1-5` - Switch screens
- `R` - Refresh data
- `N` - New item
- `V` - View details
- `Q` - Quit
- `/` - Search
- `?` - Help

**Sample TUI Screen**:
```
┌──────────────────────────────────────────────────────────┐
│ Quant Platform TUI                         [Q] Quit      │
├──────────────────────────────────────────────────────────┤
│ [1] Dashboard  [2] Strategies  [3] Backtests            │
├──────────────────────────────────────────────────────────┤
│ 📊 Dashboard Overview                                    │
│                                                          │
│ Portfolio Value: ₩128,450,000 (+28.45%)                 │
│ Active Strategies: 3                                     │
│                                                          │
│ Recent Backtests                                         │
│ ┌────────────┬──────┬─────────┬────────┐                │
│ │ Strategy   │Sharpe│ Max DD  │ Status │                │
│ ├────────────┼──────┼─────────┼────────┤                │
│ │Momentum_Val│ 1.85 │ -12.3%  │ ✓ Done │                │
│ └────────────┴──────┴─────────┴────────┘                │
│                                                          │
│ [R] Refresh  [N] New Backtest                           │
└──────────────────────────────────────────────────────────┘
```

---

### 3. WebUI (Streamlit Dashboard)
**Purpose**: Rich visualization, data exploration, research
**Library**: `streamlit` + `plotly`

**Launch**:
```bash
streamlit run dashboard/app.py
```

**Pages**:
1. **Strategy Builder** - Interactive factor selection, weight tuning
2. **Backtest Results** - Performance charts, trade analysis
3. **Portfolio Analytics** - Holdings, sector allocation, risk
4. **Factor Analysis** - Factor performance, correlation heatmaps
5. **Risk Dashboard** - VaR, CVaR, stress test scenarios

**Features**:
- Interactive Plotly charts (zoom, pan, hover)
- Real-time backtest progress via WebSocket
- Export results (CSV/Excel/PDF)
- Save/load strategy configurations

---

## Cloud/Local Hybrid Architecture

### Deployment Models

#### Local Mode (Development)
```bash
quant_platform.py --mode local backtest run
```
- API: `http://localhost:8000`
- Database: `postgresql://localhost:5432/quant_platform`
- Use Case: Development, testing, offline analysis

#### Cloud Mode (Production)
```bash
quant_platform.py --mode cloud backtest run
```
- API: `https://api.quant-platform.com`
- Database: AWS RDS PostgreSQL + TimescaleDB
- Use Case: Production, large-scale backtests, team collaboration

---

### Data Flow Optimization

**Problem**: OHLCV data for 10 years × 3000 tickers = ~500MB raw data

**Solution**: Cloud computation with result streaming

**Workflow**:
```
1. User (Local CLI):
   quant_platform.py backtest run --strategy momentum_value

2. API Call (HTTPS):
   POST /api/v1/backtest
   Body: {"strategy_id": "momentum_value", "start_date": "2020-01-01"}

3. Cloud Execution:
   ├─ Query PostgreSQL RDS for historical data
   ├─ Run backtest engine (compute-intensive)
   ├─ Store full results in S3 (100MB Parquet file)
   └─ Return summary + S3 download link

4. Client Response:
   {
     "backtest_id": "bt_20241022_001",
     "summary": {
       "total_return": 0.2845,
       "sharpe_ratio": 1.85,
       "max_drawdown": -0.123
     },
     "full_results_url": "s3://quant-backtests/bt_20241022_001.parquet"
   }

5. Local Display:
   ├─ CLI: Print summary table (Rich formatting)
   ├─ TUI: Show interactive charts (ASCII)
   └─ WebUI: Stream full results via WebSocket
```

**Bandwidth Savings**:
- Compression: gzip/brotli (10x reduction)
- Parquet format: Column storage (5x smaller than JSON)
- Pagination: Fetch 100 rows at a time
- Field selection: Only request needed fields
- Caching: Redis for frequently accessed data

---

## Authentication & Security

**See `AUTHENTICATION_ARCHITECTURE.md` for complete details**

### Multi-Mode Authentication

**Mode 1: Local (No Auth)** - For development
```bash
quant_platform.py --mode local backtest run
# No authentication required
```

**Mode 2: Simple Auth (Recommended for Personal Use)**
```bash
# First-time setup (creates admin account)
quant_platform.py setup

# Login with username/password
quant_platform.py auth login
# Session token stored in ~/.quant_platform/session.json
# 7-day session lifetime

# Use cloud backend
quant_platform.py --mode cloud backtest run --strategy momentum_value
```

**Mode 3: AWS CLI Auth** - Leverages AWS credentials
```bash
# Configure AWS CLI first
aws configure

# Login with AWS
quant_platform.py --mode cloud --auth aws auth login
# Uses AWS STS tokens, 1-hour lifetime
```

**Mode 4: JWT Auth (Future Commercial)**
```bash
# Full JWT authentication with OS keychain storage
# User management, RBAC, compliance features
```

**Security Features**:
- HTTPS/TLS 1.3 encryption
- bcrypt password hashing (Simple Auth)
- AWS STS integration (AWS Auth)
- Session-based authentication
- Audit logging (all API calls)

---

## Required Libraries

### Core Dependencies

```bash
# CLI/TUI
pip install rich textual httpx python-jose keyring pyyaml loguru

# API Backend
pip install fastapi uvicorn psycopg2-binary sqlalchemy boto3

# WebUI
pip install streamlit plotly
```

**Full Requirements**: See `requirements_cli.txt`

---

## Project Structure

```
~/spock-quant/
   quant_platform.py              # Main CLI entry point
   quant_platform_tui.py          # TUI launcher

   cli/                           # CLI implementation
      commands/                   # Command groups (auth, backtest, etc.)
      utils/                      # API client, auth manager, formatters

   tui/                           # TUI implementation
      screens/                    # Dashboard, strategies, backtests
      widgets/                    # Charts, tables, progress bars

   api/                           # FastAPI backend
      routes/                     # REST endpoints
      models/                     # Pydantic schemas
      services/                   # Business logic

   dashboard/                     # Streamlit UI
      pages/                      # 5 dashboard pages
      components/                 # Reusable components

   config/
      cli_config.yaml             # CLI configuration
      api_config.yaml             # API settings
```

---

## Implementation Timeline

### Quick Win (1-2 Days)
**Goal**: Minimal working CLI
- ✅ `quant_platform.py auth login/logout`
- ✅ `quant_platform.py backtest run`
- ✅ Formatted output with Rich
- ✅ JSON output mode

### Phase 1 (Week 1): CLI Foundation
- Complete CLI with all 8 command groups
- API client with authentication
- Local mode testing

### Phase 2 (Week 2): TUI + Additional Commands
- TUI dashboard with 5 screens
- Keyboard navigation
- ASCII charts

### Phase 3 (Week 3): Cloud Integration
- FastAPI backend deployment (AWS EC2)
- PostgreSQL RDS setup
- JWT authentication
- Cloud mode testing

### Phase 4 (Week 4): WebUI Enhancement
- Streamlit dashboard (5 pages)
- Real-time WebSocket updates
- Report export (PDF/Excel)

---

## Configuration Example

**config/cli_config.yaml**:
```yaml
api:
  local:
    base_url: "http://localhost:8000"
  cloud:
    base_url: "https://api.quant-platform.com"

auth:
  token_expiration: 3600  # 1 hour

output:
  default_format: "table"  # table, json, csv
  color_enabled: true

performance:
  connection_timeout: 30
  max_retries: 3

cache:
  enabled: true
  ttl: 3600  # 1 hour
```

---

## Success Criteria

### Phase 1 (CLI Foundation)
- ✅ Backtest executes in <30 seconds (local)
- ✅ Authentication stores tokens securely
- ✅ Output is professional and readable

### Phase 2 (TUI)
- ✅ All 8 command groups implemented
- ✅ TUI dashboard displays real-time data
- ✅ Keyboard navigation works smoothly

### Phase 3 (Cloud Integration)
- ✅ Cloud backend responds in <500ms
- ✅ Bandwidth usage <10MB per backtest
- ✅ WebSocket real-time updates functional

### Phase 4 (WebUI)
- ✅ End-to-end cloud workflow complete
- ✅ System supports 10+ concurrent users
- ✅ Export functionality working (PDF/Excel)

---

## Key Design Decisions

1. **API-First Architecture**: All interfaces consume same FastAPI backend
   - Benefit: Consistent behavior, easy testing, future extensibility

2. **JWT Authentication**: Industry-standard token-based auth
   - Benefit: Stateless, scalable, secure

3. **Cloud/Local Hybrid**: Single codebase, mode-switching via config
   - Benefit: Develop locally, deploy to cloud seamlessly

4. **Multi-Interface Support**: CLI, TUI, WebUI from one backend
   - Benefit: Choose interface based on use case (automation vs exploration)

5. **Rich Library for CLI**: Beautiful terminal output
   - Benefit: Professional UX, progress bars, colored tables

6. **Textual for TUI**: Modern Python TUI framework
   - Benefit: Reactive UI, mouse support, cross-platform

7. **Streamlit for WebUI**: Rapid prototyping, interactive charts
   - Benefit: Fast development, no frontend expertise needed

8. **Parquet for Data Transfer**: Efficient column storage
   - Benefit: 5-10x smaller than JSON, fast queries

9. **OS Keychain for Tokens**: Secure credential storage
   - Benefit: No plaintext passwords, OS-level security

10. **Compression + Pagination**: Optimize bandwidth
    - Benefit: Usable over slow connections, cost-effective

---

## Next Steps

1. **Read Full Design**: `docs/QUANT_PLATFORM_CLI_DESIGN.md`
2. **Follow Checklist**: `docs/IMPLEMENTATION_CHECKLIST_CLI.md`
3. **Install Dependencies**: `pip install -r requirements_cli.txt`
4. **Start Implementation**: Begin with Phase 1 (CLI Foundation)

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-22
**Status**: Design Complete - Ready for Implementation
