# Quant Platform CLI 구현 플랜

**문서 버전**: 2.0.0
**최종 업데이트**: 2025-10-22
**상태**: 구현 준비 완료

---

## 목차

1. [개요](#개요)
2. [우선순위화된 구현 로드맵](#우선순위화된-구현-로드맵)
3. [Priority 1: 핵심 인프라](#priority-1-핵심-인프라)
4. [Priority 2: 인증 시스템](#priority-2-인증-시스템)
5. [Priority 3: API 통신 레이어](#priority-3-api-통신-레이어)
6. [Priority 4: 첫 번째 기능 명령어](#priority-4-첫-번째-기능-명령어)
7. [Priority 5: 추가 핵심 명령어](#priority-5-추가-핵심-명령어)
8. [Priority 6: AWS CLI 인증 (선택)](#priority-6-aws-cli-인증-선택)
9. [Priority 7: TUI 인터페이스 (선택)](#priority-7-tui-인터페이스-선택)
10. [테스트 전략](#테스트-전략)
11. [배포 가이드](#배포-가이드)

---

## 개요

### 설계 변경 사항

**인증 시스템 재설계**: 복잡한 JWT 방식에서 **4가지 모드를 지원하는 유연한 아키텍처**로 변경

| 변경 항목 | 기존 | 신규 |
|----------|------|------|
| 인증 방식 | JWT (고정) | 4가지 모드 선택 |
| 토큰 저장 | OS Keychain | 파일 기반 세션 |
| 의존성 | python-jose, keyring, cryptography | bcrypt만 필요 |
| 초기 설정 | 수동 | Setup 마법사 |

**참조 문서**:
- `AUTHENTICATION_ARCHITECTURE.md` - 인증 시스템 상세 설계
- `AUTHENTICATION_REVIEW_SUMMARY_KR.md` - 한글 요약

### 구현 철학

1. **점진적 개발**: Priority 1-5까지 순차적으로 완성
2. **검증 중심**: 각 Priority 완료 시 검증 포인트 통과
3. **최소 실행 가능 제품**: Week 1-2에 MVP 완성
4. **선택적 확장**: AWS Auth, TUI는 필요 시 추가

---

## 우선순위화된 구현 로드맵

```
┌────────────────────────────────────────────────────────────────────┐
│                        구현 타임라인                                 │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Week 1: 핵심 인프라 및 인증 시스템 (MVP Foundation)                │
│  ├─ Priority 1: 핵심 인프라 (Day 1-2, 12-16h)                     │
│  │  └─ Config, Output, Main Entry Point                          │
│  ├─ Priority 2: 인증 시스템 (Day 3-4, 8-12h)                      │
│  │  └─ Setup Wizard, AuthManager, Auth Commands                  │
│  └─ Priority 3: API 통신 (Day 5, 7-10h)                           │
│     └─ API Client, Backend Auth Routes                           │
│                                                                     │
│  Week 2: 기능 명령어 (Core Features)                               │
│  ├─ Priority 4: Backtest (Day 1-2, 8-12h)                        │
│  │  └─ CLI + API Backend Integration                             │
│  └─ Priority 5: Strategy/Optimize (Day 3-5, 10-14h)              │
│     └─ CRUD + Portfolio Optimization                             │
│                                                                     │
│  Week 3 (선택): AWS 통합                                           │
│  └─ Priority 6: AWS Auth (7-10h)                                  │
│                                                                     │
│  Week 4 (선택): TUI                                                │
│  └─ Priority 7: Terminal Dashboard (25-35h)                       │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

### 검증 마일스톤

| 마일스톤 | 완료 기준 | 예상 소요 |
|---------|----------|---------|
| **MVP Alpha** | Priority 1-2 완료, Setup → Login 동작 | Week 1 (Day 1-4) |
| **MVP Beta** | Priority 3 완료, CLI ↔ API 통신 성공 | Week 1 (Day 5) |
| **MVP 1.0** | Priority 4 완료, Backtest 실행 가능 | Week 2 (Day 1-2) |
| **Production Ready** | Priority 5 완료, 전략/최적화 동작 | Week 2 (Day 3-5) |
| **AWS Enhanced** | Priority 6 완료 (선택) | Week 3 |
| **Full Featured** | Priority 7 완료 (선택) | Week 4 |

---

## Priority 1: 핵심 인프라

**목표**: 최소 실행 가능한 CLI 기반 구축
**예상 소요**: 12-16시간 (Day 1-2)
**검증 포인트**: `python3 quant_platform.py --help` 실행 가능

### Task 1.1: 프로젝트 구조 및 의존성 설치

**예상 소요**: 4시간

#### 1.1.1 디렉토리 구조 생성

```bash
# 프로젝트 루트: ~/spock (이미 존재)
cd ~/spock

# CLI 관련 디렉토리
mkdir -p cli/commands
mkdir -p cli/utils
touch cli/__init__.py
touch cli/commands/__init__.py
touch cli/utils/__init__.py

# API 백엔드 디렉토리
mkdir -p api/routes
mkdir -p api/models
mkdir -p api/services
mkdir -p api/middleware
touch api/__init__.py
touch api/routes/__init__.py
touch api/models/__init__.py
touch api/services/__init__.py
touch api/middleware/__init__.py

# 설정 디렉토리
mkdir -p config

# 사용자 홈 디렉토리 (세션 저장용)
mkdir -p ~/.quant_platform
```

#### 1.1.2 의존성 설치

```bash
# 핵심 의존성 설치
pip install rich==13.7.0          # CLI 포매팅
pip install httpx==0.25.2         # HTTP 클라이언트
pip install bcrypt==4.1.2         # 비밀번호 해싱
pip install loguru==0.7.2         # 로깅
pip install orjson==3.9.10        # 빠른 JSON
pip install pyyaml==6.0.1         # YAML 설정

# FastAPI 백엔드 의존성
pip install fastapi==0.103.1
pip install uvicorn[standard]==0.24.0
pip install psycopg2-binary==2.9.7
pip install python-dotenv==1.0.0

# AWS 통합 (선택사항)
# pip install boto3==1.29.7
```

#### 1.1.3 기본 설정 파일 생성

**파일**: `config/cli_config.yaml`

```yaml
# Quant Platform CLI Configuration
# Version: 2.0.0

# Deployment mode
mode: local  # local, cloud

# Authentication settings
authentication:
  # Mode selection (auto-detect or explicit)
  mode: auto  # auto, simple, aws, jwt

  # Simple auth settings
  simple:
    session_lifetime_days: 7
    password_min_length: 8

  # AWS auth settings (optional)
  aws:
    enabled: false
    profile: default
    region: us-east-1

# API endpoints
api:
  local:
    base_url: "http://localhost:8000"
    timeout: 30

  cloud:
    base_url: "https://api.quant-platform.com"  # Update with your URL
    timeout: 60

# Database settings
database:
  local:
    host: localhost
    port: 5432
    database: quant_platform
    user: postgres
    # Password loaded from .env

  cloud:
    host: ""  # RDS endpoint
    port: 5432
    database: quant_platform
    user: quant_user
    # Password from AWS Secrets Manager

# Output settings
output:
  default_format: table  # table, json, csv
  color_enabled: true
  verbose: false

# Performance
performance:
  connection_timeout: 30
  max_retries: 3
  retry_delay: 1  # seconds

# Logging
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR
  file: logs/quant_platform.log
  rotation: "10 MB"
  retention: "30 days"
```

**파일**: `.env` (gitignore에 추가)

```bash
# Database credentials (local)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=quant_platform
DB_USER=postgres
DB_PASSWORD=your_secure_password

# API settings
API_BASE_URL=http://localhost:8000
API_SECRET_KEY=your_secret_key_here  # openssl rand -hex 32

# AWS credentials (optional, or use aws configure)
# AWS_ACCESS_KEY_ID=
# AWS_SECRET_ACCESS_KEY=
# AWS_REGION=us-east-1
```

**검증**:
```bash
# 디렉토리 구조 확인
tree -L 2 cli/ api/ config/

# 의존성 확인
pip list | grep -E "rich|httpx|bcrypt|fastapi"

# 설정 파일 확인
cat config/cli_config.yaml
```

---

### Task 1.2: Configuration Loader

**예상 소요**: 2-3시간

**파일**: `cli/utils/config_loader.py`

```python
"""
Configuration loader for Quant Platform CLI.

Loads configuration from YAML files and environment variables.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger
from dotenv import load_dotenv


class ConfigLoader:
    """
    Load and manage configuration settings.

    Priority order:
    1. Environment variables (highest)
    2. User config file (~/.quant_platform/config.yaml)
    3. Project config file (config/cli_config.yaml)
    4. Defaults (lowest)
    """

    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "cli_config.yaml"
    USER_CONFIG_PATH = Path.home() / ".quant_platform" / "config.yaml"

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration loader.

        Args:
            config_path: Optional custom config file path
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config: Dict[str, Any] = {}

        # Load environment variables
        load_dotenv()

        # Load configuration
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from files."""
        # Load project default config
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
            logger.debug(f"Loaded config from {self.config_path}")
        else:
            logger.warning(f"Config file not found: {self.config_path}")
            self.config = {}

        # Load user config (overrides defaults)
        if self.USER_CONFIG_PATH.exists():
            with open(self.USER_CONFIG_PATH, 'r') as f:
                user_config = yaml.safe_load(f) or {}
            self._merge_config(user_config)
            logger.debug(f"Loaded user config from {self.USER_CONFIG_PATH}")

        # Apply environment variable overrides
        self._apply_env_overrides()

    def _merge_config(self, override: Dict[str, Any]) -> None:
        """
        Recursively merge override config into base config.

        Args:
            override: Configuration to merge in
        """
        def merge_dict(base: Dict, ovr: Dict) -> Dict:
            for key, value in ovr.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    merge_dict(base[key], value)
                else:
                    base[key] = value
            return base

        merge_dict(self.config, override)

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        # Database overrides
        if db_host := os.getenv('DB_HOST'):
            self.config.setdefault('database', {}).setdefault('local', {})['host'] = db_host
        if db_port := os.getenv('DB_PORT'):
            self.config['database']['local']['port'] = int(db_port)
        if db_name := os.getenv('DB_NAME'):
            self.config['database']['local']['database'] = db_name
        if db_user := os.getenv('DB_USER'):
            self.config['database']['local']['user'] = db_user
        if db_password := os.getenv('DB_PASSWORD'):
            self.config['database']['local']['password'] = db_password

        # API overrides
        if api_url := os.getenv('API_BASE_URL'):
            self.config.setdefault('api', {}).setdefault('local', {})['base_url'] = api_url

        # Mode override
        if mode := os.getenv('QUANT_MODE'):
            self.config['mode'] = mode

        logger.debug("Applied environment variable overrides")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated key.

        Args:
            key: Configuration key (e.g., "api.local.base_url")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_api_base_url(self, mode: str = None) -> str:
        """
        Get API base URL for specified mode.

        Args:
            mode: Deployment mode (local/cloud), defaults to config mode

        Returns:
            API base URL
        """
        mode = mode or self.config.get('mode', 'local')
        return self.config.get('api', {}).get(mode, {}).get('base_url', 'http://localhost:8000')

    def get_database_config(self, mode: str = None) -> Dict[str, Any]:
        """
        Get database configuration for specified mode.

        Args:
            mode: Deployment mode (local/cloud), defaults to config mode

        Returns:
            Database configuration dictionary
        """
        mode = mode or self.config.get('mode', 'local')
        return self.config.get('database', {}).get(mode, {})

    def get_auth_mode(self) -> str:
        """
        Get authentication mode.

        Returns:
            Authentication mode (local, simple, aws, jwt)
        """
        auth_mode = self.config.get('authentication', {}).get('mode', 'auto')

        if auth_mode == 'auto':
            # Auto-detect based on deployment mode
            deployment_mode = self.config.get('mode', 'local')

            if deployment_mode == 'local':
                return 'local'  # No auth for local
            else:
                # Check if AWS CLI is configured
                if os.path.exists(Path.home() / '.aws' / 'credentials'):
                    # AWS available, but default to simple
                    return 'simple'
                else:
                    return 'simple'

        return auth_mode

    def is_cloud_mode(self) -> bool:
        """Check if running in cloud mode."""
        return self.config.get('mode', 'local') == 'cloud'

    def is_verbose(self) -> bool:
        """Check if verbose output is enabled."""
        return self.config.get('output', {}).get('verbose', False)


# Singleton instance
_config_loader: Optional[ConfigLoader] = None


def get_config(config_path: Optional[Path] = None) -> ConfigLoader:
    """
    Get singleton ConfigLoader instance.

    Args:
        config_path: Optional custom config file path

    Returns:
        ConfigLoader instance
    """
    global _config_loader

    if _config_loader is None or config_path is not None:
        _config_loader = ConfigLoader(config_path)

    return _config_loader
```

**테스트 코드**: `tests/test_config_loader.py`

```python
import pytest
from pathlib import Path
from cli.utils.config_loader import ConfigLoader, get_config


def test_config_loader_loads_default_config():
    """Test that config loader loads default configuration."""
    config = ConfigLoader()

    assert config.get('mode') in ['local', 'cloud']
    assert 'api' in config.config
    assert 'database' in config.config


def test_config_get_with_dot_notation():
    """Test getting config values with dot notation."""
    config = ConfigLoader()

    base_url = config.get('api.local.base_url')
    assert base_url is not None
    assert base_url.startswith('http')


def test_config_get_api_base_url():
    """Test getting API base URL."""
    config = ConfigLoader()

    local_url = config.get_api_base_url('local')
    assert 'localhost' in local_url or '127.0.0.1' in local_url


def test_config_singleton():
    """Test that get_config returns singleton."""
    config1 = get_config()
    config2 = get_config()

    assert config1 is config2
```

**검증**:
```bash
# 테스트 실행
pytest tests/test_config_loader.py -v

# 수동 테스트
python3 -c "from cli.utils.config_loader import get_config; config = get_config(); print(config.get_api_base_url())"
```

---

### Task 1.3: Output Formatter

**예상 소요**: 2-3시간

**파일**: `cli/utils/output_formatter.py`

```python
"""
Output formatting utilities for Quant Platform CLI.

Provides rich console formatting, tables, progress bars, and messages.
"""

from typing import Any, Dict, List, Optional
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.syntax import Syntax
from rich import box
import json


# Global console instance
console = Console()


def print_success(message: str) -> None:
    """
    Print success message in green.

    Args:
        message: Success message
    """
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str) -> None:
    """
    Print error message in red.

    Args:
        message: Error message
    """
    console.print(f"[red]✗[/red] {message}", style="bold red")


def print_warning(message: str) -> None:
    """
    Print warning message in yellow.

    Args:
        message: Warning message
    """
    console.print(f"[yellow]⚠[/yellow] {message}", style="yellow")


def print_info(message: str) -> None:
    """
    Print info message.

    Args:
        message: Info message
    """
    console.print(f"[cyan]ℹ[/cyan] {message}")


def print_table(
    data: List[Dict[str, Any]],
    title: Optional[str] = None,
    columns: Optional[List[str]] = None
) -> None:
    """
    Print data as a formatted table.

    Args:
        data: List of dictionaries containing row data
        title: Optional table title
        columns: Optional list of column names (defaults to dict keys)
    """
    if not data:
        print_warning("No data to display")
        return

    # Create table
    table = Table(title=title, box=box.ROUNDED, show_header=True, header_style="bold cyan")

    # Determine columns
    if columns is None:
        columns = list(data[0].keys())

    # Add columns
    for col in columns:
        table.add_column(col, style="dim", overflow="fold")

    # Add rows
    for row in data:
        table.add_row(*[str(row.get(col, "")) for col in columns])

    console.print(table)


def print_json(data: Any, title: Optional[str] = None) -> None:
    """
    Print data as formatted JSON.

    Args:
        data: Data to print as JSON
        title: Optional title
    """
    if title:
        console.print(f"\n[bold cyan]{title}[/bold cyan]")

    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
    console.print(syntax)


def print_panel(message: str, title: Optional[str] = None, style: str = "cyan") -> None:
    """
    Print message in a panel.

    Args:
        message: Message to display
        title: Optional panel title
        style: Panel style (color)
    """
    panel = Panel(message, title=title, border_style=style, box=box.ROUNDED)
    console.print(panel)


def create_progress() -> Progress:
    """
    Create a progress bar instance.

    Returns:
        Progress bar object
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console
    )


def print_backtest_results(results: Dict[str, Any]) -> None:
    """
    Print backtest results in formatted table.

    Args:
        results: Backtest results dictionary
    """
    # Summary panel
    summary = f"""
[bold]Backtest Summary[/bold]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Strategy: {results.get('strategy_name', 'N/A')}
Period: {results.get('start_date')} to {results.get('end_date')}
Initial Capital: ₩{results.get('initial_capital', 0):,.0f}
Final Capital: ₩{results.get('final_capital', 0):,.0f}
    """
    print_panel(summary, title="📊 Backtest Results", style="green")

    # Performance metrics table
    metrics = [
        {"Metric": "Total Return", "Value": f"{results.get('total_return', 0):.2%}"},
        {"Metric": "Sharpe Ratio", "Value": f"{results.get('sharpe_ratio', 0):.2f}"},
        {"Metric": "Max Drawdown", "Value": f"{results.get('max_drawdown', 0):.2%}"},
        {"Metric": "Win Rate", "Value": f"{results.get('win_rate', 0):.2%}"},
        {"Metric": "Number of Trades", "Value": str(results.get('num_trades', 0))},
    ]

    print_table(metrics, title="Performance Metrics")


def print_strategy_list(strategies: List[Dict[str, Any]]) -> None:
    """
    Print list of strategies.

    Args:
        strategies: List of strategy dictionaries
    """
    if not strategies:
        print_warning("No strategies found")
        return

    # Format for table display
    table_data = []
    for s in strategies:
        table_data.append({
            "ID": s.get('id', ''),
            "Name": s.get('name', ''),
            "Description": s.get('description', '')[:50] + "..." if len(s.get('description', '')) > 50 else s.get('description', ''),
            "Created": s.get('created_at', '').split('T')[0] if s.get('created_at') else ''
        })

    print_table(table_data, title="🎯 Strategies")


# Export functions
__all__ = [
    'console',
    'print_success',
    'print_error',
    'print_warning',
    'print_info',
    'print_table',
    'print_json',
    'print_panel',
    'create_progress',
    'print_backtest_results',
    'print_strategy_list'
]
```

**검증**:
```python
# tests/test_output_formatter.py
from cli.utils.output_formatter import *


def test_print_messages():
    """Test message printing functions."""
    print_success("Operation completed")
    print_error("An error occurred")
    print_warning("This is a warning")
    print_info("Information message")


def test_print_table():
    """Test table printing."""
    data = [
        {"Name": "Strategy A", "Return": "15.3%", "Sharpe": "1.85"},
        {"Name": "Strategy B", "Return": "12.1%", "Sharpe": "1.42"},
    ]
    print_table(data, title="Test Strategies")


def test_print_json():
    """Test JSON printing."""
    data = {"name": "Test", "value": 123, "nested": {"key": "value"}}
    print_json(data, title="Test JSON")
```

---

### Task 1.4: Main Entry Point

**예상 소요**: 4-6시간

**파일**: `quant_platform.py`

```python
#!/usr/bin/env python3
"""
Quant Platform CLI - Main Entry Point

Multi-interface orchestrator supporting CLI, TUI, and WebUI modes.
"""

import sys
import argparse
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from cli.utils.config_loader import get_config
from cli.utils.output_formatter import console, print_error, print_success, print_info
from loguru import logger


# Version
VERSION = "2.0.0"


def setup_logging(verbose: bool = False) -> None:
    """
    Setup logging configuration.

    Args:
        verbose: Enable verbose logging
    """
    # Remove default logger
    logger.remove()

    # Console logging
    log_level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level=log_level
    )

    # File logging
    logger.add(
        "logs/quant_platform.log",
        rotation="10 MB",
        retention="30 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
    )


def create_parser() -> argparse.ArgumentParser:
    """
    Create argument parser with all subcommands.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog='quant_platform',
        description='Quant Investment Platform - Multi-Interface CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Setup (first-time)
  %(prog)s setup

  # Authentication
  %(prog)s auth login
  %(prog)s auth status

  # Run backtest
  %(prog)s backtest run --strategy momentum_value --start 2020-01-01 --end 2023-12-31

  # List strategies
  %(prog)s strategy list

  # Portfolio optimization
  %(prog)s optimize --method mean_variance --target-return 0.15

  # Cloud mode
  %(prog)s --mode cloud backtest run --strategy momentum_value

  # TUI mode
  %(prog)s --tui

For more information, visit: https://github.com/your-org/quant-platform
        """
    )

    # Global options
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    parser.add_argument('--mode', choices=['local', 'cloud'], help='Deployment mode')
    parser.add_argument('--auth', choices=['simple', 'aws', 'jwt'], help='Authentication mode')
    parser.add_argument('--config', type=Path, help='Custom config file path')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--json', action='store_true', help='JSON output format')
    parser.add_argument('--tui', action='store_true', help='Launch TUI (Terminal UI) mode')

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Setup command (Priority 2)
    setup_parser = subparsers.add_parser('setup', help='First-time setup wizard')

    # Auth command (Priority 2)
    auth_parser = subparsers.add_parser('auth', help='Authentication management')
    auth_subparsers = auth_parser.add_subparsers(dest='auth_command')

    auth_subparsers.add_parser('login', help='Login to platform')
    auth_subparsers.add_parser('logout', help='Logout from platform')
    auth_subparsers.add_parser('status', help='Check authentication status')

    # Backtest command (Priority 4)
    backtest_parser = subparsers.add_parser('backtest', help='Backtesting operations')
    backtest_subparsers = backtest_parser.add_subparsers(dest='backtest_command')

    run_parser = backtest_subparsers.add_parser('run', help='Run backtest')
    run_parser.add_argument('--strategy', required=True, help='Strategy name')
    run_parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    run_parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    run_parser.add_argument('--initial-capital', type=float, default=100000000, help='Initial capital')

    backtest_subparsers.add_parser('list', help='List backtests')

    show_parser = backtest_subparsers.add_parser('show', help='Show backtest details')
    show_parser.add_argument('id', help='Backtest ID')

    delete_parser = backtest_subparsers.add_parser('delete', help='Delete backtest')
    delete_parser.add_argument('id', help='Backtest ID')

    # Strategy command (Priority 5)
    strategy_parser = subparsers.add_parser('strategy', help='Strategy management')
    strategy_subparsers = strategy_parser.add_subparsers(dest='strategy_command')

    strategy_subparsers.add_parser('list', help='List strategies')

    create_parser = strategy_subparsers.add_parser('create', help='Create strategy')
    create_parser.add_argument('--name', required=True, help='Strategy name')
    create_parser.add_argument('--file', type=Path, required=True, help='Strategy definition file')

    show_parser = strategy_subparsers.add_parser('show', help='Show strategy details')
    show_parser.add_argument('name', help='Strategy name')

    update_parser = strategy_subparsers.add_parser('update', help='Update strategy')
    update_parser.add_argument('name', help='Strategy name')
    update_parser.add_argument('--file', type=Path, required=True, help='Strategy definition file')

    delete_parser = strategy_subparsers.add_parser('delete', help='Delete strategy')
    delete_parser.add_argument('name', help='Strategy name')

    # Optimize command (Priority 5)
    optimize_parser = subparsers.add_parser('optimize', help='Portfolio optimization')
    optimize_parser.add_argument('--method', required=True,
                                choices=['mean_variance', 'risk_parity', 'black_litterman', 'kelly'],
                                help='Optimization method')
    optimize_parser.add_argument('--target-return', type=float, help='Target return (for mean-variance)')
    optimize_parser.add_argument('--constraints', type=Path, help='Constraints file (YAML)')

    # Placeholder for future commands
    subparsers.add_parser('factor', help='Factor analysis (not yet implemented)')
    subparsers.add_parser('risk', help='Risk management (not yet implemented)')
    subparsers.add_parser('report', help='Report generation (not yet implemented)')
    subparsers.add_parser('config', help='Configuration management (not yet implemented)')

    return parser


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        # Parse arguments
        parser = create_parser()
        args = parser.parse_args()

        # Setup logging
        setup_logging(args.verbose)
        logger.info(f"Quant Platform v{VERSION} starting...")

        # Load configuration
        config = get_config(args.config)

        # Apply mode override
        if args.mode:
            config.config['mode'] = args.mode

        # Apply auth mode override
        if args.auth:
            config.config['authentication']['mode'] = args.auth

        # TUI mode
        if args.tui:
            print_info("Launching TUI mode...")
            # TODO: Launch TUI (Priority 7)
            print_error("TUI mode not yet implemented")
            return 1

        # No command specified
        if not args.command:
            parser.print_help()
            return 0

        # Dispatch commands
        if args.command == 'setup':
            from cli.commands.setup import run_setup
            return run_setup(args, config)

        elif args.command == 'auth':
            from cli.commands.auth import run_auth
            return run_auth(args, config)

        elif args.command == 'backtest':
            from cli.commands.backtest import run_backtest
            return run_backtest(args, config)

        elif args.command == 'strategy':
            from cli.commands.strategy import run_strategy
            return run_strategy(args, config)

        elif args.command == 'optimize':
            from cli.commands.optimize import run_optimize
            return run_optimize(args, config)

        else:
            print_error(f"Command '{args.command}' not yet implemented")
            return 1

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        return 130

    except Exception as e:
        print_error(f"Unexpected error: {e}")
        logger.exception("Unexpected error occurred")
        return 1


if __name__ == '__main__':
    sys.exit(main())
```

**검증**:
```bash
# 도움말 확인
python3 quant_platform.py --help
python3 quant_platform.py auth --help
python3 quant_platform.py backtest --help

# 버전 확인
python3 quant_platform.py --version

# 로그 확인
tail -f logs/quant_platform.log
```

**Priority 1 완료 체크리스트**:
- [ ] 디렉토리 구조 생성 완료
- [ ] 의존성 설치 완료 (`pip list` 확인)
- [ ] 설정 파일 생성 (`config/cli_config.yaml`, `.env`)
- [ ] `ConfigLoader` 구현 및 테스트 통과
- [ ] `output_formatter` 구현 및 테스트 통과
- [ ] `quant_platform.py` 실행 가능 (`--help` 동작)
- [ ] 로그 파일 생성 확인 (`logs/quant_platform.log`)

---

## Priority 2: 인증 시스템

**목표**: Mode 2 (Simple Auth) 완전 구현
**예상 소요**: 8-12시간 (Day 3-4)
**검증 포인트**: Setup → Login → Status 플로우 테스트

### Task 2.1: Database Schema 생성

**예상 소요**: 1시간

**파일**: `scripts/init_auth_schema.sql`

```sql
-- Quant Platform Authentication Schema
-- Version: 2.0.0

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),           -- bcrypt hash (empty for AWS users)
    aws_arn VARCHAR(255) UNIQUE,          -- For AWS authentication
    aws_account_id VARCHAR(12),           -- AWS account
    role VARCHAR(20) DEFAULT 'user',      -- 'admin', 'user', 'analyst'
    is_active BOOLEAN DEFAULT true,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_aws_arn ON users(aws_arn) WHERE aws_arn IS NOT NULL;

-- Sessions table (7-day lifetime)
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(64) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sessions_token ON sessions(session_token);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);

-- Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,           -- 'login', 'logout', 'backtest_run', 'optimize'
    resource VARCHAR(255),                  -- Resource affected
    timestamp TIMESTAMP DEFAULT NOW(),
    ip_address INET,
    status VARCHAR(20) DEFAULT 'success'    -- 'success', 'failure'
);

CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_log_action ON audit_log(action);

-- Helper function to update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to clean expired sessions
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM sessions WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
```

**파일**: `scripts/init_auth_schema.py`

```python
#!/usr/bin/env python3
"""
Initialize authentication schema in PostgreSQL database.
"""

import sys
from pathlib import Path
import psycopg2
from psycopg2 import sql

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.utils.config_loader import get_config
from cli.utils.output_formatter import print_success, print_error, print_info


def init_schema():
    """Initialize authentication schema."""
    print_info("Initializing authentication schema...")

    # Load config
    config = get_config()
    db_config = config.get_database_config('local')

    try:
        # Connect to database
        conn = psycopg2.connect(
            host=db_config.get('host', 'localhost'),
            port=db_config.get('port', 5432),
            database=db_config.get('database', 'quant_platform'),
            user=db_config.get('user', 'postgres'),
            password=db_config.get('password', '')
        )

        # Read SQL file
        sql_file = Path(__file__).parent / 'init_auth_schema.sql'
        with open(sql_file, 'r') as f:
            schema_sql = f.read()

        # Execute SQL
        with conn.cursor() as cursor:
            cursor.execute(schema_sql)
            conn.commit()

        print_success("Authentication schema initialized successfully")

        # Verify tables
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('users', 'sessions', 'audit_log')
                ORDER BY table_name
            """)
            tables = cursor.fetchall()

            print_info(f"Created tables: {', '.join(t[0] for t in tables)}")

        conn.close()
        return 0

    except psycopg2.Error as e:
        print_error(f"Database error: {e}")
        return 1
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(init_schema())
```

**실행**:
```bash
# 스키마 초기화
python3 scripts/init_auth_schema.py

# 검증
psql -d quant_platform -c "\dt"
psql -d quant_platform -c "\d users"
psql -d quant_platform -c "\d sessions"
```

### Task 2.2: Authentication Manager

**예상 소요**: 2-3시간

**파일**: `cli/utils/auth_manager.py`

```python
"""
Authentication manager supporting multiple modes.

Modes:
- Local: No authentication (direct DB access)
- Simple: Session-based with file storage
- AWS: AWS CLI integration (AWS STS)
- JWT: Full token-based auth (future)
"""

import json
import secrets
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from loguru import logger


class AuthManager:
    """
    Unified authentication manager supporting multiple modes.
    """

    SESSION_FILE = Path.home() / '.quant_platform' / 'session.json'

    def __init__(self, mode: str = "local"):
        """
        Initialize authentication manager.

        Args:
            mode: Authentication mode (local, simple, aws, jwt)
        """
        self.mode = mode

        # Ensure session directory exists
        self.SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

    def authenticate(self) -> bool:
        """
        Check if user is authenticated based on mode.

        Returns:
            True if authenticated, False otherwise
        """
        if self.mode == "local":
            # No authentication needed for local mode
            return True

        elif self.mode in ["simple", "aws", "jwt"]:
            # Check for valid session
            session = self._load_session()
            if session:
                # Check expiration
                expires_at = datetime.fromisoformat(session['expires_at'])
                if expires_at > datetime.now():
                    return True
                else:
                    logger.debug("Session expired")
                    return False
            return False

        return False

    def save_session(self, session_token: str, expires_at: datetime,
                    username: str, user_id: Optional[int] = None) -> None:
        """
        Save session to local file.

        Args:
            session_token: Session token string
            expires_at: Expiration datetime
            username: Username
            user_id: User ID (optional)
        """
        session_data = {
            'session_token': session_token,
            'expires_at': expires_at.isoformat(),
            'username': username,
            'user_id': user_id,
            'mode': self.mode,
            'created_at': datetime.now().isoformat()
        }

        try:
            with open(self.SESSION_FILE, 'w') as f:
                json.dump(session_data, f, indent=2)

            logger.debug(f"Session saved for user: {username}")
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            raise

    def _load_session(self) -> Optional[Dict[str, Any]]:
        """
        Load session from local file.

        Returns:
            Session data dictionary or None
        """
        if not self.SESSION_FILE.exists():
            return None

        try:
            with open(self.SESSION_FILE, 'r') as f:
                session_data = json.load(f)

            # Verify mode matches
            if session_data.get('mode') != self.mode:
                logger.warning(f"Session mode mismatch: {session_data.get('mode')} vs {self.mode}")
                return None

            return session_data

        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load session: {e}")
            return None

    def get_session_token(self) -> Optional[str]:
        """
        Get current session token.

        Returns:
            Session token string or None
        """
        session = self._load_session()
        if session:
            return session.get('session_token')
        return None

    def get_username(self) -> Optional[str]:
        """
        Get current username.

        Returns:
            Username or None
        """
        session = self._load_session()
        if session:
            return session.get('username')
        return None

    def get_session_info(self) -> Optional[Dict[str, Any]]:
        """
        Get full session information.

        Returns:
            Session dictionary or None
        """
        return self._load_session()

    def clear_session(self) -> None:
        """Clear stored session (logout)."""
        if self.SESSION_FILE.exists():
            try:
                self.SESSION_FILE.unlink()
                logger.debug("Session cleared")
            except OSError as e:
                logger.error(f"Failed to clear session: {e}")
                raise

    def is_session_valid(self) -> bool:
        """
        Check if current session is valid (not expired).

        Returns:
            True if valid, False otherwise
        """
        return self.authenticate()

    @staticmethod
    def generate_session_token() -> str:
        """
        Generate cryptographically secure session token.

        Returns:
            64-character URL-safe token
        """
        return secrets.token_urlsafe(48)  # 48 bytes = 64 characters
```

**테스트**: `tests/test_auth_manager.py`

```python
import pytest
from datetime import datetime, timedelta
from cli.utils.auth_manager import AuthManager


def test_local_mode_no_auth():
    """Test local mode requires no authentication."""
    auth = AuthManager(mode="local")
    assert auth.authenticate() == True


def test_save_and_load_session():
    """Test saving and loading session."""
    auth = AuthManager(mode="simple")

    token = AuthManager.generate_session_token()
    expires = datetime.now() + timedelta(days=7)

    auth.save_session(token, expires, "testuser", 1)

    assert auth.get_session_token() == token
    assert auth.get_username() == "testuser"
    assert auth.is_session_valid() == True


def test_expired_session():
    """Test expired session detection."""
    auth = AuthManager(mode="simple")

    token = AuthManager.generate_session_token()
    expires = datetime.now() - timedelta(hours=1)  # Expired

    auth.save_session(token, expires, "testuser", 1)

    assert auth.is_session_valid() == False


def test_clear_session():
    """Test session clearing."""
    auth = AuthManager(mode="simple")

    token = AuthManager.generate_session_token()
    expires = datetime.now() + timedelta(days=7)

    auth.save_session(token, expires, "testuser", 1)
    assert auth.is_session_valid() == True

    auth.clear_session()
    assert auth.is_session_valid() == False


def test_generate_token():
    """Test token generation."""
    token1 = AuthManager.generate_session_token()
    token2 = AuthManager.generate_session_token()

    assert len(token1) == 64
    assert len(token2) == 64
    assert token1 != token2  # Must be unique
```

---

### Task 2.3-2.4: Setup & Auth Commands

**예상 소요**: 5-7시간 (통합)

**파일**: `cli/commands/setup.py` (2-3시간)
- Interactive wizard for first-time setup
- Check if users table empty → prompt for admin credentials
- bcrypt password hashing, insert admin user
- Success message with next steps

**파일**: `cli/commands/auth.py` (3-4시간)
- `auth login`: Username/password prompt → API call `/api/v1/auth/login` → save session
- `auth logout`: Clear session file, API call `/api/v1/auth/logout`
- `auth status`: Display current user, expiration, mode

**Priority 2 완료 체크리스트**:
- [ ] Database schema 초기화 완료
- [ ] AuthManager 구현 및 테스트 통과
- [ ] Setup command: `quant_platform.py setup` 동작
- [ ] Auth commands: login/logout/status 동작
- [ ] Session 저장/로드 검증 (`~/.quant_platform/session.json` 확인)

---

## Priority 3: API 통신 레이어

**목표**: CLI ↔ FastAPI 통신 완성
**예상 소요**: 7-10시간 (Day 5)
**검증 포인트**: Login 성공 → API 호출 → 응답 수신

### Task 3.1: API Client Wrapper

**파일**: `cli/utils/api_client.py` (3-4시간)
- `httpx.AsyncClient` 기반 클래스
- HTTP methods (GET, POST, PUT, DELETE) with retry logic
- Automatic session token injection in headers
- 401 → refresh session, 5xx → exponential backoff retry
- Error handling with user-friendly messages

### Task 3.2: FastAPI Backend - Auth Routes

**파일**: `api/main.py` + `api/routes/auth_routes.py` (4-6시간)
- FastAPI app setup with CORS middleware
- `/api/v1/auth/login` (POST): Verify bcrypt password → create session in DB → return token
- `/api/v1/auth/logout` (POST): Invalidate session in DB
- `/api/v1/auth/me` (GET): Return current user info
- PostgreSQL connection pool with psycopg2

**Priority 3 완료 체크리스트**:
- [ ] API Client 구현 완료
- [ ] FastAPI 백엔드 실행 가능 (`uvicorn api.main:app`)
- [ ] Auth routes 동작 (Swagger UI `/docs` 확인)
- [ ] CLI → API 통신 성공 (login 플로우 테스트)

---

## Priority 4: 첫 번째 기능 명령어

**목표**: Backtest 명령어 완전 동작
**예상 소요**: 8-12시간 (Week 2, Day 1-2)
**검증 포인트**: `backtest run` 실행 → 결과 출력

### Task 4.1: Backtest Command

**파일**: `cli/commands/backtest.py` (4-5시간)
- `backtest run`: Validate args → API call `/api/v1/backtest` → poll for results → display table
- `backtest list/show/delete`: CRUD operations via API
- Progress bar for long-running backtests
- Format results with `print_backtest_results()`

### Task 4.2: API Backend - Backtest Routes

**파일**: `api/routes/backtest_routes.py` + `api/services/backtest_service.py` (4-7시간)
- `/api/v1/backtest` (POST): Trigger backtest execution (async task)
- `/api/v1/backtest` (GET): List backtests
- `/api/v1/backtest/{id}` (GET): Get details
- Integration with existing backtest engine modules

**Priority 4 완료 체크리스트**:
- [ ] Backtest command 구현 완료
- [ ] API backend routes 완료
- [ ] End-to-end 테스트: CLI → API → Database → Results
- [ ] 결과 포매팅 확인 (표, JSON 출력)

---

## Priority 5: 추가 핵심 명령어

**목표**: Strategy & Optimize 명령어
**예상 소요**: 10-14시간 (Week 2, Day 3-5)

### Task 5.1: Strategy Command (4-5시간)
- CRUD operations for strategy management
- YAML file parsing for strategy definitions
- API integration (`/api/v1/strategies`)

### Task 5.2: Optimize Command (3-4시간)
- Portfolio optimization with method selection
- Constraints file loading
- Results visualization

### Task 5.3: API Backend Routes (3-5시간)
- Strategy CRUD endpoints
- Optimization endpoint with cvxpy integration

**Priority 5 완료 체크리스트**:
- [ ] Strategy list/create/show/delete 동작
- [ ] Optimize 실행 가능 (mean-variance, risk-parity)
- [ ] API routes 완성
- [ ] MVP 1.0 완료 (Production Ready)

---

## Priority 6: AWS CLI 인증 (선택)

**목표**: Mode 3 (AWS Auth) 구현
**예상 소요**: 7-10시간 (Week 3, 선택사항)

**핵심 구현**:
1. AWS CLI 감지 (`~/.aws/credentials` 확인)
2. boto3로 STS token 획득 (`sts.get_caller_identity()`)
3. AWS ARN 기반 user provisioning
4. 1-hour session lifetime with auto-refresh

**파일**: `cli/utils/aws_auth.py`, `api/routes/auth_routes.py` (AWS login endpoint 추가)

**검증**: `quant_platform.py --auth aws auth login` 성공

---

## Priority 7: TUI 인터페이스 (선택)

**목표**: Textual 기반 Terminal UI
**예상 소요**: 25-35시간 (Week 4, 선택사항)

**핵심 구현**:
1. **TUI Framework** (`tui/app.py`): Textual app with screen routing
2. **5 Screens**: Dashboard, Strategies, Backtests, Portfolio, Settings
3. **Widgets**: ASCII charts, tables, progress bars, modals
4. **Key Bindings**: 1-5 (screens), R (refresh), Q (quit)

**검증**: `quant_platform.py --tui` 실행 → 대시보드 표시

---

## 테스트 전략

### Unit Tests (Priority 1-5에 포함)
```bash
# 각 모듈별 테스트
pytest tests/test_config_loader.py -v
pytest tests/test_auth_manager.py -v
pytest tests/test_api_client.py -v
pytest tests/test_commands/ -v
```

### Integration Tests
```bash
# End-to-end 플로우 테스트
pytest tests/integration/test_auth_flow.py -v
pytest tests/integration/test_backtest_flow.py -v
pytest tests/integration/test_cli_api_integration.py -v
```

### Performance Tests
```bash
# API 응답 시간, 메모리 사용량
pytest tests/performance/ --benchmark-only
```

### Security Tests
```bash
# bcrypt 강도, session token 엔트로피
pytest tests/security/test_password_security.py -v
pytest tests/security/test_session_security.py -v
```

---

## 배포 가이드

### Local Development (완료 후 즉시 사용 가능)

```bash
# 1. 데이터베이스 초기화
python3 scripts/init_auth_schema.py

# 2. 첫 번째 setup
python3 quant_platform.py setup

# 3. 로그인
python3 quant_platform.py auth login

# 4. Backtest 실행
python3 quant_platform.py backtest run --strategy momentum_value --start 2020-01-01 --end 2023-12-31
```

### Cloud Deployment (추후)

**API Backend (AWS EC2)**:
```bash
# EC2 인스턴스 설정
sudo apt install postgresql postgresql-contrib
pip install -r requirements_cli.txt

# FastAPI 실행 (systemd service)
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Database (AWS RDS PostgreSQL)**:
- RDS PostgreSQL 15 인스턴스 생성
- TimescaleDB extension 활성화
- Security group: EC2에서만 접근 허용

**HTTPS (Let's Encrypt)**:
```bash
sudo certbot --nginx -d api.quant-platform.com
```

---

## 빠른 시작 (Quick Start)

### Week 1 목표: MVP Alpha (Login 동작)

```bash
# Day 1-2: Priority 1
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_cli.txt
python3 quant_platform.py --help

# Day 3-4: Priority 2
python3 scripts/init_auth_schema.py
python3 quant_platform.py setup
python3 quant_platform.py auth login

# Day 5: Priority 3
uvicorn api.main:app --reload
# 다른 터미널에서: python3 quant_platform.py auth status
```

### Week 2 목표: MVP 1.0 (Backtest 동작)

```bash
# Day 1-2: Priority 4
python3 quant_platform.py backtest run --strategy momentum_value --start 2020-01-01 --end 2023-12-31

# Day 3-5: Priority 5
python3 quant_platform.py strategy list
python3 quant_platform.py optimize --method mean_variance --target-return 0.15
```

---

## 문제 해결 (Troubleshooting)

### 일반적인 문제

**Q: `ImportError: No module named 'cli'`**
```bash
# PYTHONPATH 설정 또는 프로젝트 루트에서 실행
export PYTHONPATH=/Users/13ruce/spock:$PYTHONPATH
python3 quant_platform.py
```

**Q: Database connection failed**
```bash
# PostgreSQL 실행 확인
brew services list
brew services start postgresql

# .env 파일 확인
cat .env
```

**Q: Session 파일 권한 에러**
```bash
# 디렉토리 권한 확인
chmod 700 ~/.quant_platform
chmod 600 ~/.quant_platform/session.json
```

---

## 참조 문서

**인증 시스템**:
- `AUTHENTICATION_ARCHITECTURE.md` - 완전한 인증 설계
- `AUTHENTICATION_REVIEW_SUMMARY_KR.md` - 한글 요약

**CLI 설계**:
- `QUANT_PLATFORM_CLI_DESIGN.md` - 전체 CLI 설계
- `CLI_DESIGN_SUMMARY.md` - 빠른 참조
- `IMPLEMENTATION_CHECKLIST_CLI.md` - 원본 체크리스트

**Quant Platform**:
- `CLAUDE.md` - 전체 프로젝트 개요

---

**최종 업데이트**: 2025-10-22
**버전**: 2.0.0
**상태**: 구현 준비 완료 - Week 1 Day 1부터 시작 가능
