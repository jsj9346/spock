# Quant Platform Multi-Interface Architecture Design

**Document Version**: 1.0.0
**Last Updated**: 2025-10-22
**Author**: Quant Platform Development Team
**Status**: Design Specification

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Multi-Interface Design](#multi-interface-design)
4. [Cloud/Local Hybrid Deployment](#cloudlocal-hybrid-deployment)
5. [Required Libraries & Dependencies](#required-libraries--dependencies)
6. [Implementation Specification](#implementation-specification)
7. [Security & Authentication](#security--authentication)
8. [Performance Considerations](#performance-considerations)
9. [Migration Path](#migration-path)

---

## Executive Summary

### Design Goals

**Primary Objective**: Create a unified Quant Investment Platform orchestrator (`quant_platform.py`) that supports multiple interface modes (CLI, TUI, WebUI) with seamless cloud/local hybrid deployment.

### Key Requirements

1. **Multi-Interface Support**:
   - CLI (Command Line Interface) - Scriptable automation
   - TUI (Terminal User Interface) - Interactive terminal experience
   - WebUI (Streamlit Dashboard) - Rich visualization and exploration

2. **Cloud/Local Hybrid Architecture**:
   - Cloud backend: PostgreSQL + TimescaleDB on AWS RDS
   - Local execution: Lightweight client with result caching
   - Secure authentication and data streaming
   - Efficient bandwidth usage (streaming results, not raw data)

3. **Unified Backend API**:
   - Single FastAPI backend serving all interfaces
   - RESTful API for stateless operations
   - WebSocket support for real-time streaming
   - Consistent data models across interfaces

### Design Principles

- **Separation of Concerns**: Presentation layer (CLI/TUI/WebUI) separate from business logic
- **Cloud-First Architecture**: Heavy computation in cloud, light clients for interaction
- **Progressive Enhancement**: CLI → TUI → WebUI (increasing richness)
- **API-First Design**: All interfaces consume same backend API
- **Security by Default**: Authentication, encryption, audit logging

---

## Architecture Overview

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      USER INTERFACES (Client-Side)                   │
├─────────────────┬─────────────────┬─────────────────────────────────┤
│   CLI Mode      │   TUI Mode      │   WebUI Mode                    │
│   (argparse)    │   (Textual)     │   (Streamlit)                   │
│   ├─ backtest   │   ├─ Dashboard  │   ├─ Strategy Builder           │
│   ├─ optimize   │   ├─ Portfolio  │   ├─ Backtest Visualization     │
│   ├─ analyze    │   ├─ Analytics  │   ├─ Portfolio Analytics        │
│   └─ report     │   └─ Settings   │   └─ Risk Dashboard             │
└─────────────────┴─────────────────┴─────────────────────────────────┘
                              │
                              │ HTTP/REST + WebSocket
                              │ (Authentication: Multi-Mode - see AUTHENTICATION_ARCHITECTURE.md)
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│                   BACKEND API LAYER (FastAPI)                      │
│                   [Runs: Local or Cloud EC2]                       │
├────────────────────────────────────────────────────────────────────┤
│  API Routes:                                                       │
│    /auth/*           - Authentication & authorization              │
│    /strategies/*     - Strategy CRUD operations                    │
│    /backtest/*       - Backtesting execution & results             │
│    /optimize/*       - Portfolio optimization                      │
│    /factors/*        - Factor analysis & scoring                   │
│    /risk/*           - Risk metrics & stress testing               │
│    /data/*           - Market data retrieval                       │
│    /reports/*        - Report generation & export                  │
│                                                                    │
│  WebSocket Endpoints:                                              │
│    /ws/backtest      - Real-time backtest progress                 │
│    /ws/optimization  - Optimization iteration updates              │
│    /ws/data-stream   - Market data streaming (for monitoring)      │
└────────────────────────────────────────────────────────────────────┘
                              │
                              │ Database Connection
                              │ (PostgreSQL Protocol)
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│              DATABASE LAYER (PostgreSQL + TimescaleDB)             │
│                   [Runs: AWS RDS or Local]                         │
├────────────────────────────────────────────────────────────────────┤
│  Data Storage:                                                     │
│    ├─ ohlcv_data (Hypertable)      - Price/volume data            │
│    ├─ factor_scores                - Factor calculations          │
│    ├─ strategies                   - Strategy definitions         │
│    ├─ backtest_results             - Backtest outputs             │
│    ├─ portfolio_holdings           - Portfolio state              │
│    └─ trades                       - Trade history                │
│                                                                    │
│  Continuous Aggregates:                                            │
│    ├─ ohlcv_monthly                - Monthly rollups              │
│    ├─ ohlcv_quarterly              - Quarterly rollups            │
│    └─ performance_daily            - Daily performance metrics    │
└────────────────────────────────────────────────────────────────────┘
                              │
                              │ Market Data APIs
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│                   EXTERNAL DATA SOURCES                            │
├────────────────────────────────────────────────────────────────────┤
│  ├─ KIS API            - Korea Investment & Securities            │
│  ├─ Polygon.io         - US market data                           │
│  ├─ yfinance           - Global market data (backup)              │
│  └─ AKShare            - China market data                        │
└────────────────────────────────────────────────────────────────────┘
```

### Deployment Models

#### Model 1: Local Development
```
User Machine:
  ├─ quant_platform.py (CLI/TUI)
  ├─ FastAPI backend (localhost:8000)
  └─ PostgreSQL (localhost:5432)
```

#### Model 2: Cloud Backend (Recommended)
```
User Machine (Local):
  ├─ quant_platform.py (CLI/TUI client)
  └─ Streamlit dashboard (localhost:8501)
       │
       │ HTTPS + WSS
       ▼
AWS Cloud:
  ├─ FastAPI backend (EC2 instance)
  ├─ PostgreSQL + TimescaleDB (RDS instance)
  └─ S3 (report storage, backtest results cache)
```

#### Model 3: Fully Cloud (Production)
```
AWS Cloud:
  ├─ Streamlit dashboard (EC2 or ECS)
  ├─ FastAPI backend (EC2 or Lambda)
  ├─ PostgreSQL + TimescaleDB (RDS)
  └─ CloudFront CDN (static assets)

User Access:
  ├─ CLI via SSH tunnel
  └─ WebUI via HTTPS (https://quant.example.com)
```

---

## Multi-Interface Design

### 1. CLI (Command Line Interface)

**Purpose**: Scriptable automation, batch processing, CI/CD integration

**Library**: `argparse` (Python standard library)

**Command Structure**:
```bash
# Main command groups
quant_platform.py [OPTIONS] COMMAND [ARGS]

Commands:
  auth        Authentication management
  strategy    Strategy operations (list, create, update, delete)
  backtest    Run backtesting simulations
  optimize    Portfolio optimization
  factor      Factor analysis and research
  risk        Risk metrics calculation
  report      Generate reports
  config      Configuration management
  cloud       Cloud deployment operations
```

**Example Commands**:
```bash
# Authentication
quant_platform.py auth login --email user@example.com
quant_platform.py auth logout
quant_platform.py auth status

# Strategy management
quant_platform.py strategy list
quant_platform.py strategy create --name "Momentum_Value" --config strategy.yaml
quant_platform.py strategy show momentum_value

# Backtesting
quant_platform.py backtest run \
  --strategy momentum_value \
  --start 2020-01-01 \
  --end 2023-12-31 \
  --initial-capital 100000000 \
  --output backtest_results.json

# Portfolio optimization
quant_platform.py optimize \
  --method mean_variance \
  --target-return 0.15 \
  --constraints config/optimization_constraints.yaml

# Factor analysis
quant_platform.py factor analyze \
  --factors momentum,value,quality \
  --start 2018-01-01

# Risk analysis
quant_platform.py risk var \
  --portfolio current \
  --confidence 0.95 \
  --horizon 10

quant_platform.py risk stress \
  --scenarios 2008_crisis,2020_covid,2022_bear

# Report generation
quant_platform.py report generate \
  --type backtest \
  --id 123 \
  --format pdf \
  --output reports/backtest_2024.pdf

# Cloud operations
quant_platform.py cloud status
quant_platform.py cloud deploy --env production
quant_platform.py cloud logs --tail 100
```

**Implementation**: `quant_platform.py` (main CLI entry point)

---

### 2. TUI (Terminal User Interface)

**Purpose**: Interactive terminal experience with keyboard navigation

**Library**: `textual` (Modern Python TUI framework)

**Features**:
- Dashboard view with real-time updates
- Portfolio overview with performance charts (ASCII art)
- Interactive strategy builder
- Backtest results viewer with tabular data
- Keyboard shortcuts for navigation
- Mouse support (optional)

**Screen Layouts**:

```
┌─────────────────────────────────────────────────────────────────┐
│ Quant Platform TUI                                  [Q] Quit    │
├─────────────────────────────────────────────────────────────────┤
│ [1] Dashboard  [2] Strategies  [3] Backtests  [4] Portfolio    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📊 Dashboard Overview                                          │
│                                                                 │
│  Portfolio Value: ₩128,450,000 (+28.45%)                       │
│  Active Strategies: 3                                           │
│  Pending Backtests: 1                                           │
│                                                                 │
│  Recent Backtests                                               │
│  ┌────────────────┬──────────┬───────────┬──────────┐          │
│  │ Strategy       │ Sharpe   │ Max DD    │ Status   │          │
│  ├────────────────┼──────────┼───────────┼──────────┤          │
│  │ Momentum_Value │ 1.85     │ -12.3%    │ ✓ Done   │          │
│  │ Quality_LowVol │ Running  │ -         │ ⏳ Run   │          │
│  └────────────────┴──────────┴───────────┴──────────┘          │
│                                                                 │
│  [R] Refresh  [N] New Backtest  [V] View Details               │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ Status: Connected to cloud backend | Last update: 14:35:22     │
└─────────────────────────────────────────────────────────────────┘
```

**Key Bindings**:
- `1-4`: Switch between main views
- `R`: Refresh data
- `N`: Create new item
- `V`: View details
- `E`: Edit
- `D`: Delete
- `Q`: Quit
- `/`: Search
- `?`: Help

**Implementation**: `quant_platform_tui.py` (separate TUI launcher)

---

### 3. WebUI (Streamlit Dashboard)

**Purpose**: Rich visualization, data exploration, research workflows

**Library**: `streamlit` (Interactive web framework)

**Pages** (as defined in CLAUDE.md):
1. **Strategy Builder**: Interactive factor selection and weight configuration
2. **Backtest Results**: Performance charts, trade analysis, metrics
3. **Portfolio Analytics**: Holdings, sector allocation, risk metrics
4. **Factor Analysis**: Factor performance, correlation heatmaps
5. **Risk Dashboard**: VaR, CVaR, stress test scenarios

**Features**:
- Interactive Plotly charts (zoom, pan, hover)
- Real-time backtest progress with WebSocket
- Export results to CSV/Excel/PDF
- Save/load strategy configurations
- Collaborative features (share strategies via URL)

**Implementation**: `dashboard/app.py` + pages/

---

## Cloud/Local Hybrid Deployment

### Deployment Architecture

#### Backend API Modes

**Local Mode** (Development):
```python
# quant_platform.py --mode local
API_BASE_URL = "http://localhost:8000"
DATABASE_URL = "postgresql://localhost:5432/quant_platform"
```

**Cloud Mode** (Production):
```python
# quant_platform.py --mode cloud
API_BASE_URL = "https://api.quant-platform.com"
DATABASE_URL = "postgresql://user:pass@quant-db.aws.rds:5432/quant_platform"
```

#### Data Flow Optimization

**Problem**: Raw OHLCV data for 10 years × 3000 tickers = ~500MB per query
**Solution**: Cloud computation with result streaming

**Workflow**:
1. **User Request** (Local CLI):
   ```bash
   quant_platform.py backtest run --strategy momentum_value \
     --start 2018-01-01 --end 2023-12-31
   ```

2. **API Call** (HTTPS):
   ```
   POST /api/v1/backtest
   Body: {
     "strategy_id": "momentum_value",
     "start_date": "2018-01-01",
     "end_date": "2023-12-31"
   }
   Headers: {
     "Authorization": "Bearer <JWT_TOKEN>"
   }
   ```

3. **Cloud Backend Execution**:
   - Query PostgreSQL (AWS RDS) for historical data
   - Run backtest engine (compute-intensive)
   - Store full results in S3 (100MB backtest output)
   - Return summary + S3 download link

4. **Client Response**:
   ```json
   {
     "backtest_id": "bt_20241022_001",
     "status": "completed",
     "summary": {
       "total_return": 0.2845,
       "sharpe_ratio": 1.85,
       "max_drawdown": -0.123
     },
     "full_results_url": "s3://quant-backtests/bt_20241022_001.parquet",
     "report_url": "/api/v1/backtest/bt_20241022_001/report"
   }
   ```

5. **Local Display**:
   - CLI prints summary table
   - TUI shows interactive charts (fetch detailed data on demand)
   - WebUI streams full results via WebSocket

#### Authentication Flow

**JWT Token-Based Authentication**:

```
1. User Login (CLI/TUI/WebUI):
   ├─ POST /api/v1/auth/login
   ├─ Body: {"email": "user@example.com", "password": "***"}
   └─ Response: {"access_token": "eyJ...", "refresh_token": "***"}

2. Store Token Locally:
   ├─ ~/.quant_platform/credentials.json (encrypted)
   └─ Environment variable: QUANT_PLATFORM_TOKEN

3. Subsequent Requests:
   ├─ Header: "Authorization: Bearer eyJ..."
   └─ Backend validates JWT signature + expiration

4. Token Refresh (auto):
   ├─ POST /api/v1/auth/refresh
   └─ Body: {"refresh_token": "***"}
```

**Security Features**:
- HTTPS/TLS 1.3 encryption for all API calls
- JWT tokens with 1-hour expiration (access token)
- Refresh tokens with 7-day expiration
- IP whitelisting (optional)
- Audit logging (all API calls logged)

#### Bandwidth Optimization

**Techniques**:

1. **Compression**:
   - Response compression (gzip/brotli)
   - Parquet format for large datasets (10x smaller than JSON)

2. **Pagination**:
   ```python
   GET /api/v1/backtest/bt_001/trades?page=1&limit=100
   ```

3. **Field Selection**:
   ```python
   GET /api/v1/backtest/bt_001?fields=summary,performance_metrics
   # Excludes raw trade data (saves 90% bandwidth)
   ```

4. **Delta Updates** (WebSocket):
   ```python
   # Only send changed data during backtest progress
   {"type": "progress", "completed_days": 850, "total_days": 1000}
   ```

5. **Caching**:
   - Client-side cache for static data (factor definitions, strategy configs)
   - Server-side Redis cache for frequently accessed results
   - ETag/If-Modified-Since headers for conditional requests

---

## Required Libraries & Dependencies

### Core CLI Framework

```python
# requirements_cli.txt

# ============================================================================
# CLI Interface (argparse is stdlib, no install needed)
# ============================================================================

# Rich output formatting for CLI
rich==13.7.0              # Beautiful terminal formatting, tables, progress bars
click==8.1.7              # Alternative to argparse (optional, for subcommands)

# ============================================================================
# TUI Interface
# ============================================================================

textual==0.41.0           # Modern Python TUI framework
textual-plotext==0.2.0    # ASCII charts for TUI (optional)

# ============================================================================
# HTTP Client & API Communication
# ============================================================================

httpx==0.25.2             # Modern async HTTP client (requests replacement)
websockets==12.0          # WebSocket client for real-time updates
pydantic==2.5.0           # Data validation (request/response models)

# ============================================================================
# Authentication & Security
# ============================================================================

python-jose[cryptography]==3.3.0  # JWT token handling
cryptography==41.0.7      # Token encryption/decryption
keyring==24.3.0           # Secure credential storage (OS keychain)

# ============================================================================
# Configuration Management
# ============================================================================

python-dotenv==1.0.0      # Environment variable management
pyyaml==6.0.1             # YAML configuration files
toml==0.10.2              # TOML configuration (alternative)

# ============================================================================
# Logging & Monitoring
# ============================================================================

loguru==0.7.2             # Enhanced logging
python-json-logger==2.0.7 # Structured JSON logging

# ============================================================================
# Data Serialization & Compression
# ============================================================================

orjson==3.9.10            # Fast JSON serialization
msgpack==1.0.7            # Binary serialization (for large data transfers)
pyarrow==14.0.1           # Parquet file support (efficient data storage)

# ============================================================================
# Progress & Feedback
# ============================================================================

tqdm==4.66.1              # Progress bars for long-running operations
```

### Backend API (FastAPI)

```python
# requirements_api.txt

# ============================================================================
# FastAPI Backend
# ============================================================================

fastapi==0.103.1          # Async web framework
uvicorn[standard]==0.24.0 # ASGI server with WebSocket support
python-multipart==0.0.6   # File upload support
aiofiles==23.2.1          # Async file operations

# ============================================================================
# Database
# ============================================================================

psycopg2-binary==2.9.7    # PostgreSQL adapter
sqlalchemy==2.0.23        # ORM (optional, for complex queries)
asyncpg==0.29.0           # Async PostgreSQL driver

# ============================================================================
# Authentication
# ============================================================================

python-jose[cryptography]==3.3.0  # JWT tokens
passlib[bcrypt]==1.7.4    # Password hashing
python-multipart==0.0.6   # Form data parsing

# ============================================================================
# Caching & Performance
# ============================================================================

redis==5.0.1              # Redis client for caching
aiocache==0.12.2          # Async caching library

# ============================================================================
# AWS Integration (Cloud Mode)
# ============================================================================

boto3==1.29.7             # AWS SDK (S3, RDS, EC2)
botocore==1.32.7          # AWS core library
```

### WebUI (Streamlit)

```python
# requirements_webui.txt

# ============================================================================
# Streamlit Dashboard
# ============================================================================

streamlit==1.28.1         # Interactive web framework
plotly==5.17.0            # Interactive charts
streamlit-aggrid==0.3.4   # Advanced data tables

# ============================================================================
# Visualization
# ============================================================================

matplotlib==3.7.2         # Static plots
seaborn==0.12.2           # Statistical visualizations
```

### Platform-Specific Optimizations

**macOS** (M1/M2 Silicon):
```bash
# Use native ARM builds for better performance
pip install --upgrade --force-reinstall \
  numpy pandas scipy scikit-learn
```

**Linux** (AWS EC2):
```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y \
  postgresql-client \
  libpq-dev \
  python3-dev \
  build-essential
```

**Windows**:
```bash
# Windows-specific dependencies
pip install windows-curses  # For TUI support
```

---

## Implementation Specification

### Project Structure

```
~/spock-quant/
   quant_platform.py                 # Main CLI entry point
   quant_platform_tui.py             # TUI launcher

   cli/                              # CLI implementation
      __init__.py
      commands/                      # Command groups
         __init__.py
         auth.py                     # Authentication commands
         strategy.py                 # Strategy commands
         backtest.py                 # Backtesting commands
         optimize.py                 # Optimization commands
         factor.py                   # Factor analysis commands
         risk.py                     # Risk commands
         report.py                   # Report commands
         config.py                   # Configuration commands
         cloud.py                    # Cloud deployment commands
      utils/
         api_client.py               # HTTP client wrapper
         auth_manager.py             # JWT token management
         output_formatter.py         # Rich table/progress formatting
         config_loader.py            # Configuration file handling

   tui/                              # TUI implementation
      __init__.py
      app.py                         # Main TUI application
      screens/                       # TUI screens
         dashboard.py                # Dashboard view
         strategies.py               # Strategy management
         backtests.py                # Backtest results
         portfolio.py                # Portfolio overview
         settings.py                 # Settings screen
      widgets/                       # Reusable widgets
         chart.py                    # ASCII charts
         table.py                    # Data tables
         progress.py                 # Progress indicators

   api/                              # FastAPI backend
      main.py                        # FastAPI app entry point
      routes/                        # API routes
         auth_routes.py              # Authentication endpoints
         strategy_routes.py          # Strategy CRUD
         backtest_routes.py          # Backtesting endpoints
         optimization_routes.py      # Portfolio optimization
         factor_routes.py            # Factor analysis
         risk_routes.py              # Risk analysis
         data_routes.py              # Market data retrieval
         report_routes.py            # Report generation
      models/                        # Pydantic models
         auth_models.py              # Authentication schemas
         strategy_models.py          # Strategy schemas
         backtest_models.py          # Backtest schemas
      services/                      # Business logic
         backtest_service.py         # Backtest orchestration
         optimization_service.py     # Portfolio optimization
         factor_service.py           # Factor calculations
      middleware/
         auth_middleware.py          # JWT validation
         logging_middleware.py       # Request logging

   dashboard/                        # Streamlit UI
      app.py                         # Main Streamlit app
      pages/                         # Dashboard pages
         1_strategy_builder.py       # Strategy creation
         2_backtest_results.py       # Backtest visualization
         3_portfolio_analytics.py    # Portfolio analysis
         4_factor_analysis.py        # Factor performance
         5_risk_dashboard.py         # Risk metrics
      components/                    # Reusable components
         charts.py                   # Plotly charts
         tables.py                   # Data tables
         forms.py                    # Input forms

   config/
      cli_config.yaml                # CLI default settings
      api_config.yaml                # API configuration
      cloud_config.yaml              # Cloud deployment settings

   deployment/                       # Cloud deployment
      docker/
         Dockerfile.api              # API container
         Dockerfile.dashboard        # Dashboard container
         docker-compose.yml          # Local development
      terraform/                     # AWS infrastructure
         main.tf                     # Main configuration
         rds.tf                      # RDS PostgreSQL
         ec2.tf                      # EC2 instances
         s3.tf                       # S3 buckets
      scripts/
         deploy.sh                   # Deployment script
         migrate.sh                  # Database migration
```

### CLI Implementation (quant_platform.py)

**Main Entry Point**:

```python
#!/usr/bin/env python3
"""
Quant Investment Platform - Unified CLI Orchestrator

Multi-Interface Support:
  - CLI: Command-line interface (default)
  - TUI: Terminal user interface (--tui flag)
  - WebUI: Streamlit dashboard (separate launcher)

Cloud/Local Hybrid:
  - Local mode: --mode local (localhost backend)
  - Cloud mode: --mode cloud (AWS backend)

Usage:
  quant_platform.py [OPTIONS] COMMAND [ARGS]
  quant_platform.py --tui  # Launch TUI
  quant_platform.py auth login
  quant_platform.py backtest run --strategy momentum_value
"""

import sys
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

import argparse
from cli.commands import (
    auth,
    strategy,
    backtest,
    optimize,
    factor,
    risk,
    report,
    config,
    cloud
)
from cli.utils.config_loader import load_config
from cli.utils.output_formatter import console, print_error


def create_parser() -> argparse.ArgumentParser:
    """
    Create main argument parser with subcommands.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog='quant_platform',
        description='Quant Investment Platform - Multi-Interface Orchestrator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Authentication
  quant_platform.py auth login --email user@example.com

  # Backtesting
  quant_platform.py backtest run --strategy momentum_value \\
    --start 2020-01-01 --end 2023-12-31

  # Portfolio optimization
  quant_platform.py optimize --method mean_variance --target-return 0.15

  # Launch TUI
  quant_platform.py --tui

  # Cloud mode
  quant_platform.py --mode cloud backtest run --strategy momentum_value
        """
    )

    # Global options
    parser.add_argument(
        '--mode',
        choices=['local', 'cloud'],
        default='local',
        help='Execution mode: local (localhost) or cloud (AWS backend)'
    )
    parser.add_argument(
        '--config',
        type=Path,
        default=Path('config/cli_config.yaml'),
        help='Configuration file path'
    )
    parser.add_argument(
        '--tui',
        action='store_true',
        help='Launch Terminal User Interface (TUI)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='count',
        default=0,
        help='Increase verbosity (can be repeated: -vv, -vvv)'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress non-error output'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results in JSON format'
    )

    # Subcommands
    subparsers = parser.add_subparsers(
        dest='command',
        title='Commands',
        description='Available commands',
        help='Command to execute'
    )

    # Register command modules
    auth.register_subcommand(subparsers)
    strategy.register_subcommand(subparsers)
    backtest.register_subcommand(subparsers)
    optimize.register_subcommand(subparsers)
    factor.register_subcommand(subparsers)
    risk.register_subcommand(subparsers)
    report.register_subcommand(subparsers)
    config.register_subcommand(subparsers)
    cloud.register_subcommand(subparsers)

    return parser


def main():
    """Main entry point for CLI."""
    parser = create_parser()
    args = parser.parse_args()

    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        print_error(f"Failed to load configuration: {e}")
        sys.exit(1)

    # Launch TUI mode if requested
    if args.tui:
        from tui.app import QuantPlatformTUI
        app = QuantPlatformTUI(mode=args.mode, config=config)
        app.run()
        return

    # Require a command
    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    try:
        # Commands are registered with execute_COMMAND functions
        command_module = {
            'auth': auth,
            'strategy': strategy,
            'backtest': backtest,
            'optimize': optimize,
            'factor': factor,
            'risk': risk,
            'report': report,
            'config': config,
            'cloud': cloud
        }[args.command]

        # Pass config and args to command
        result = command_module.execute(args, config)

        # Exit with appropriate code
        sys.exit(0 if result else 1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        print_error(f"Command execution failed: {e}")
        if args.verbose >= 2:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
```

### API Client (cli/utils/api_client.py)

**HTTP Client Wrapper**:

```python
"""
API Client for Quant Platform

Handles authentication, request/response processing, and error handling.
"""

import httpx
from typing import Dict, Any, Optional
from pathlib import Path
import json
from cli.utils.auth_manager import AuthManager
from cli.utils.output_formatter import console, print_error


class APIClient:
    """
    HTTP client for Quant Platform API.

    Features:
      - Automatic JWT token injection
      - Token refresh on 401 Unauthorized
      - Retry logic with exponential backoff
      - Request/response logging
      - Error handling with user-friendly messages
    """

    def __init__(self, base_url: str, config: Dict[str, Any]):
        """
        Initialize API client.

        Args:
            base_url: API base URL (e.g., "https://api.quant-platform.com")
            config: Configuration dictionary
        """
        self.base_url = base_url.rstrip('/')
        self.config = config
        self.auth_manager = AuthManager()

        # Create HTTP client with default settings
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
            headers={
                "User-Agent": "QuantPlatform-CLI/1.0.0",
                "Accept": "application/json"
            }
        )

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers with JWT token."""
        token = self.auth_manager.get_access_token()
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """
        Handle API response.

        Args:
            response: HTTP response object

        Returns:
            Parsed JSON response

        Raises:
            APIError: On HTTP errors or invalid responses
        """
        # Handle 401 Unauthorized (token expired)
        if response.status_code == 401:
            # Attempt token refresh
            if self.auth_manager.refresh_token():
                # Retry original request with new token
                raise RetryWithNewToken()
            else:
                raise APIError("Authentication expired. Please login again.")

        # Handle other HTTP errors
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            error_detail = response.json().get('detail', str(e))
            raise APIError(f"API request failed: {error_detail}")

        # Parse JSON response
        try:
            return response.json()
        except json.JSONDecodeError:
            raise APIError("Invalid JSON response from API")

    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Send GET request.

        Args:
            endpoint: API endpoint (e.g., "/api/v1/strategies")
            params: Query parameters

        Returns:
            JSON response
        """
        headers = self._get_auth_headers()
        response = self.client.get(endpoint, params=params, headers=headers)
        return self._handle_response(response)

    def post(self, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Send POST request.

        Args:
            endpoint: API endpoint
            data: Request body (JSON)

        Returns:
            JSON response
        """
        headers = self._get_auth_headers()
        headers["Content-Type"] = "application/json"
        response = self.client.post(endpoint, json=data, headers=headers)
        return self._handle_response(response)

    def put(self, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Send PUT request."""
        headers = self._get_auth_headers()
        headers["Content-Type"] = "application/json"
        response = self.client.put(endpoint, json=data, headers=headers)
        return self._handle_response(response)

    def delete(self, endpoint: str) -> Dict[str, Any]:
        """Send DELETE request."""
        headers = self._get_auth_headers()
        response = self.client.delete(endpoint, headers=headers)
        return self._handle_response(response)

    def download_file(self, url: str, output_path: Path) -> None:
        """
        Download file from URL.

        Args:
            url: File URL (S3 pre-signed URL)
            output_path: Local file path to save
        """
        with self.client.stream("GET", url) as response:
            response.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)


class APIError(Exception):
    """API-related error."""
    pass


class RetryWithNewToken(Exception):
    """Internal exception for token refresh retry."""
    pass
```

### Command Example: Backtest (cli/commands/backtest.py)

```python
"""
Backtest command implementation.
"""

import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from rich.progress import Progress, SpinnerColumn, TextColumn
from cli.utils.api_client import APIClient
from cli.utils.output_formatter import console, create_table, print_success, print_error


def register_subcommand(subparsers):
    """Register backtest subcommand."""
    parser = subparsers.add_parser(
        'backtest',
        help='Run backtesting simulations',
        description='Execute backtesting for investment strategies'
    )

    # Subcommands
    backtest_subparsers = parser.add_subparsers(dest='action')

    # backtest run
    run_parser = backtest_subparsers.add_parser('run', help='Run new backtest')
    run_parser.add_argument('--strategy', required=True, help='Strategy name or ID')
    run_parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    run_parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    run_parser.add_argument('--initial-capital', type=float, default=100_000_000,
                           help='Initial capital (default: 100,000,000 KRW)')
    run_parser.add_argument('--output', type=Path, help='Output file path (JSON/CSV)')

    # backtest list
    list_parser = backtest_subparsers.add_parser('list', help='List backtest results')
    list_parser.add_argument('--limit', type=int, default=10, help='Number of results')

    # backtest show
    show_parser = backtest_subparsers.add_parser('show', help='Show backtest details')
    show_parser.add_argument('backtest_id', help='Backtest ID')

    # backtest delete
    delete_parser = backtest_subparsers.add_parser('delete', help='Delete backtest')
    delete_parser.add_argument('backtest_id', help='Backtest ID')


def execute(args: argparse.Namespace, config: Dict[str, Any]) -> bool:
    """
    Execute backtest command.

    Args:
        args: Parsed command-line arguments
        config: Configuration dictionary

    Returns:
        True if successful, False otherwise
    """
    # Initialize API client
    api_base_url = config['api'][args.mode]['base_url']
    api_client = APIClient(api_base_url, config)

    # Route to appropriate action
    if args.action == 'run':
        return run_backtest(args, api_client)
    elif args.action == 'list':
        return list_backtests(args, api_client)
    elif args.action == 'show':
        return show_backtest(args, api_client)
    elif args.action == 'delete':
        return delete_backtest(args, api_client)
    else:
        console.print("[red]Error:[/red] No action specified. Use 'run', 'list', 'show', or 'delete'.")
        return False


def run_backtest(args: argparse.Namespace, api_client: APIClient) -> bool:
    """
    Run new backtest.

    Args:
        args: Command arguments
        api_client: API client instance

    Returns:
        True if successful
    """
    console.print(f"[bold blue]Starting backtest for strategy:[/bold blue] {args.strategy}")
    console.print(f"Period: {args.start} to {args.end}")
    console.print(f"Initial Capital: ₩{args.initial_capital:,.0f}")

    # Submit backtest request
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Submitting backtest request...", total=None)

            response = api_client.post('/api/v1/backtest', data={
                "strategy_id": args.strategy,
                "start_date": args.start,
                "end_date": args.end,
                "initial_capital": args.initial_capital
            })

            backtest_id = response['backtest_id']
            progress.update(task, description=f"Backtest submitted: {backtest_id}")

        # Poll for completion (or use WebSocket in future)
        console.print(f"\n[green]✓[/green] Backtest {backtest_id} submitted successfully")
        console.print("Waiting for results...")

        # TODO: Implement WebSocket listener for real-time progress
        # For now, poll every 5 seconds
        import time
        while True:
            result = api_client.get(f'/api/v1/backtest/{backtest_id}')
            status = result['status']

            if status == 'completed':
                display_results(result)

                # Save to file if requested
                if args.output:
                    save_results(result, args.output)
                    print_success(f"Results saved to {args.output}")

                return True
            elif status == 'failed':
                print_error(f"Backtest failed: {result.get('error')}")
                return False

            console.print(f"Status: {status} ({result.get('progress', 0)}%)")
            time.sleep(5)

    except Exception as e:
        print_error(f"Backtest execution failed: {e}")
        return False


def display_results(result: Dict[str, Any]) -> None:
    """
    Display backtest results in formatted table.

    Args:
        result: Backtest result dictionary
    """
    summary = result['summary']

    # Create performance metrics table
    table = create_table("Backtest Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("Total Return", f"{summary['total_return']*100:.2f}%")
    table.add_row("Annualized Return", f"{summary.get('annualized_return', 0)*100:.2f}%")
    table.add_row("Sharpe Ratio", f"{summary['sharpe_ratio']:.2f}")
    table.add_row("Sortino Ratio", f"{summary.get('sortino_ratio', 0):.2f}")
    table.add_row("Max Drawdown", f"{summary['max_drawdown']*100:.2f}%")
    table.add_row("Win Rate", f"{summary.get('win_rate', 0)*100:.1f}%")
    table.add_row("Total Trades", str(summary.get('num_trades', 0)))

    console.print(table)


def save_results(result: Dict[str, Any], output_path: Path) -> None:
    """
    Save backtest results to file.

    Args:
        result: Backtest result dictionary
        output_path: Output file path
    """
    import json
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)


def list_backtests(args: argparse.Namespace, api_client: APIClient) -> bool:
    """List recent backtests."""
    try:
        response = api_client.get('/api/v1/backtest', params={'limit': args.limit})
        backtests = response['backtests']

        # Create table
        table = create_table("Backtest History")
        table.add_column("ID", style="cyan")
        table.add_column("Strategy", style="yellow")
        table.add_column("Period")
        table.add_column("Return", style="green")
        table.add_column("Sharpe")
        table.add_column("Status")

        for bt in backtests:
            table.add_row(
                bt['id'][:8],
                bt['strategy_name'],
                f"{bt['start_date']} to {bt['end_date']}",
                f"{bt['total_return']*100:.2f}%",
                f"{bt['sharpe_ratio']:.2f}",
                bt['status']
            )

        console.print(table)
        return True

    except Exception as e:
        print_error(f"Failed to list backtests: {e}")
        return False


def show_backtest(args: argparse.Namespace, api_client: APIClient) -> bool:
    """Show detailed backtest results."""
    try:
        result = api_client.get(f'/api/v1/backtest/{args.backtest_id}')
        display_results(result)
        return True

    except Exception as e:
        print_error(f"Failed to retrieve backtest: {e}")
        return False


def delete_backtest(args: argparse.Namespace, api_client: APIClient) -> bool:
    """Delete backtest result."""
    try:
        api_client.delete(f'/api/v1/backtest/{args.backtest_id}')
        print_success(f"Backtest {args.backtest_id} deleted successfully")
        return True

    except Exception as e:
        print_error(f"Failed to delete backtest: {e}")
        return False
```

---

## Security & Authentication

### Multi-Mode Authentication System

**IMPORTANT**: The Quant Platform uses a flexible multi-mode authentication system designed to support both personal use and future commercialization. For complete authentication architecture, see **`AUTHENTICATION_ARCHITECTURE.md`**.

### Authentication Modes Overview

The platform supports 4 authentication modes:

1. **Local Mode (No Auth)** - For personal development, no authentication required
2. **Simple Mode (Session-Based)** - Recommended for personal cloud deployment
3. **AWS Mode (AWS CLI Integration)** - Leverages existing AWS credentials
4. **JWT Mode (Full Auth)** - Future commercial deployment with RBAC

### Recommended Approach for Personal Use

**Mode 2: Simple Authentication (Session-Based)**

**First-Time Setup**:
```bash
# Run setup wizard (creates admin account if no users exist)
python3 quant_platform.py setup

# Output:
# No users found in database.
# Let's create your admin account.
# Admin username [admin]: admin
# Admin email: your@email.com
# Admin password: ***
# Confirm password: ***
# ✓ Admin account created: admin
```

**Login/Logout**:
```bash
# Login with username/password
python3 quant_platform.py auth login
# Username: admin
# Password: ***
# ✓ Login successful. Welcome, admin!

# Check authentication status
python3 quant_platform.py auth status
# Logged in as: admin
# Session expires: 2025-10-29 12:34:56

# Logout
python3 quant_platform.py auth logout
# ✓ Logged out successfully
```

**Session Management**:
- Session tokens stored in `~/.quant_platform/session.json`
- 7-day session lifetime (good UX, no frequent re-login)
- Automatic session validation on each API call
- Secure password storage using bcrypt

### Alternative: AWS CLI Authentication

**For AWS-native deployments**:
```bash
# Configure AWS CLI first
aws configure
# AWS Access Key ID: AKIA...
# AWS Secret Access Key: ***

# Login using AWS credentials
python3 quant_platform.py --mode cloud --auth aws auth login
# Authenticating with AWS CLI credentials...
# ✓ AWS authentication successful!
# Account: 123456789012
# User ARN: arn:aws:iam::123456789012:user/yourname

# Use cloud backend with AWS auth
python3 quant_platform.py --mode cloud --auth aws backtest run --strategy momentum_value
```

**Benefits**:
- No separate credentials to manage
- Leverages existing AWS security (IAM)
- Automatic user provisioning from AWS ARN
- 1-hour session lifetime (matches AWS STS tokens)

### Database Schema (Simple Auth)

```sql
-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),           -- bcrypt hash (empty for AWS users)
    aws_arn VARCHAR(255) UNIQUE,          -- For AWS authentication
    aws_account_id VARCHAR(12),           -- AWS account
    role VARCHAR(20) DEFAULT 'user',      -- 'admin', 'user', 'analyst'
    is_active BOOLEAN DEFAULT true,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Sessions table (7-day lifetime)
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(64) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Audit log
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(255),
    timestamp TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20)
);
```

### Migration to Commercial (Future)

When commercializing, migrate to **Mode 4 (JWT Authentication)**:

```bash
# Enable JWT mode in config
# config/cli_config.yaml
authentication:
  mode: jwt

# User management commands
python3 quant_platform.py admin user create --username alice --email alice@example.com --role analyst
python3 quant_platform.py admin user list
python3 quant_platform.py admin user deactivate bob

# JWT tokens stored in OS keychain (macOS/Windows/Linux)
python3 quant_platform.py auth login
# Email: alice@example.com
# Password: ***
# ✓ Login successful. Token stored securely in OS keychain.
```

**For complete implementation details, see `AUTHENTICATION_ARCHITECTURE.md`**

---

## Performance Considerations

### Optimization Techniques

1. **HTTP Connection Pooling**:
   ```python
   # Reuse connections for multiple requests
   client = httpx.Client(
       limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
   )
   ```

2. **Response Compression**:
   ```python
   # Server sends gzip-compressed responses
   headers = {"Accept-Encoding": "gzip, deflate, br"}
   ```

3. **Async Operations** (Future Enhancement):
   ```python
   # Use httpx.AsyncClient for concurrent requests
   async with httpx.AsyncClient() as client:
       responses = await asyncio.gather(
           client.get('/api/v1/strategies'),
           client.get('/api/v1/backtests'),
           client.get('/api/v1/portfolio')
       )
   ```

4. **Caching**:
   ```python
   # Cache static data (factor definitions, strategy configs)
   from functools import lru_cache

   @lru_cache(maxsize=128)
   def get_factor_definitions() -> Dict:
       return api_client.get('/api/v1/factors/definitions')
   ```

5. **Pagination**:
   ```python
   # Fetch large datasets in chunks
   def get_all_backtests(api_client: APIClient) -> List[Dict]:
       all_backtests = []
       page = 1
       while True:
           response = api_client.get('/api/v1/backtest', params={'page': page, 'limit': 100})
           all_backtests.extend(response['backtests'])
           if not response['has_more']:
               break
           page += 1
       return all_backtests
   ```

---

## Migration Path

### Phase 1: CLI Foundation (Week 1)

**Goal**: Basic CLI working with local backend

**Tasks**:
1. Implement `quant_platform.py` main entry point
2. Create API client wrapper (`cli/utils/api_client.py`)
3. Implement authentication command (`cli/commands/auth.py`)
4. Implement backtest command (`cli/commands/backtest.py`)
5. Local testing with FastAPI backend

**Deliverable**: `quant_platform.py auth login` and `quant_platform.py backtest run` working

---

### Phase 2: TUI Implementation (Week 2)

**Goal**: Interactive terminal interface

**Tasks**:
1. Setup Textual framework
2. Create dashboard screen (`tui/screens/dashboard.py`)
3. Create backtest results viewer
4. Implement keyboard navigation
5. ASCII chart widgets

**Deliverable**: `quant_platform.py --tui` launches interactive dashboard

---

### Phase 3: Cloud Integration (Week 3)

**Goal**: Cloud backend connection with authentication

**Tasks**:
1. Deploy FastAPI backend to AWS EC2
2. Setup PostgreSQL RDS instance
3. Implement JWT authentication in API
4. Test CLI/TUI with cloud backend
5. Performance optimization (compression, caching)

**Deliverable**: `quant_platform.py --mode cloud backtest run` works end-to-end

---

### Phase 4: WebUI Enhancement (Week 4)

**Goal**: Streamlit dashboard fully functional

**Tasks**:
1. Implement all 5 Streamlit pages
2. Integrate with FastAPI backend
3. Real-time updates via WebSocket
4. Report export functionality
5. User authentication in Streamlit

**Deliverable**: Full-featured WebUI accessible via browser

---

## Appendix: Configuration Files

### CLI Configuration (config/cli_config.yaml)

```yaml
# Quant Platform CLI Configuration

# API endpoints
api:
  local:
    base_url: "http://localhost:8000"
    websocket_url: "ws://localhost:8000/ws"
  cloud:
    base_url: "https://api.quant-platform.com"
    websocket_url: "wss://api.quant-platform.com/ws"

# Authentication
auth:
  token_expiration: 3600  # 1 hour
  refresh_token_expiration: 604800  # 7 days

# Output formatting
output:
  default_format: "table"  # table, json, csv
  color_enabled: true
  progress_bars: true

# Performance
performance:
  connection_timeout: 30
  read_timeout: 120
  max_retries: 3
  retry_delay: 1.0  # seconds

# Caching
cache:
  enabled: true
  ttl: 3600  # 1 hour
  max_size_mb: 100

# Logging
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  file: "~/.quant_platform/logs/cli.log"
  max_file_size_mb: 10
  backup_count: 5
```

---

**End of Design Document**
