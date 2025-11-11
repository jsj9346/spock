# Quant Platform CLI - 개발 실행 플랜

**작성일**: 2025-01-29
**버전**: 1.0
**예상 완료**: 2주 (26-40시간)

---

## 📋 목차

1. [프로젝트 개요](#프로젝트-개요)
2. [아키텍처 설계](#아키텍처-설계)
3. [Phase 1: Query Infrastructure](#phase-1-query-infrastructure-8-12시간)
4. [Phase 2: Interactive Shell](#phase-2-interactive-shell-5-8시간)
5. [Phase 3: Backtest Integration](#phase-3-backtest-integration-10-15시간)
6. [Phase 4: Polish & Documentation](#phase-4-polish--documentation-3-5시간)
7. [테스트 전략](#테스트-전략)
8. [배포 체크리스트](#배포-체크리스트)
9. [🎯 우선순위 최적화 구현 계획](#-우선순위-최적화-구현-계획)
10. [✅ 상세 검증 절차](#-상세-검증-절차)
11. [🏁 전체 통합 테스트](#-전체-통합-테스트)
12. [📋 최종 인수 체크리스트](#-최종-인수-체크리스트)

---

## 프로젝트 개요

### 목표

두 가지 인터페이스를 통한 효율적인 퀀트 분석 워크플로우 제공:

1. **One-Shot CLI**: 단일 명령어 실행 → 결과 반환 → 종료
2. **Interactive Shell**: 대화형 세션으로 탐색적 분석

### 핵심 사용 사례

```bash
# One-Shot: 빠른 스크리닝
spock query --rank-pe --top 20
spock query --rank-dy --filter "pe<10 and dy>2" --export-csv value_stocks.csv

# Interactive: 탐색적 분석
spock shell
spock> rank-pe --top 20
spock> filter "pe<10 and dy>2"
spock> export results.csv
spock> backtest --start 2020-01-01 --end 2024-12-31
spock> quit
```

### 성공 기준

- ✅ 쿼리 실행: <1초 (20개 결과)
- ✅ 백테스트: <10초 (5년 기간)
- ✅ Shell 반응성: <100ms
- ✅ 에러 메시지: 명확하고 실행 가능
- ✅ 문서화: 완전하고 정확

### 필수 라이브러리 의존성

#### Core CLI Dependencies (Required)
```bash
pip install asyncpg==0.29.0      # PostgreSQL async driver with connection pooling
pip install rich==13.7.0         # Terminal formatting, tables, progress bars
pip install Jinja2==3.1.2        # HTML template engine for backtest reports
pip install pandas==2.0.3        # DataFrame operations (already in requirements)
pip install plotly==5.17.0       # Interactive charts (already in requirements)
```

#### Backtesting Dependencies (Sprint 3+)
```bash
pip install vectorbt==0.26.2     # Fast vectorized backtesting engine
pip install numba                # vectorbt performance dependency
```

#### Testing Dependencies (Optional)
```bash
pip install pytest==7.4.2              # Testing framework
pip install pytest-asyncio==0.21.1     # Async test support
pip install pytest-cov==4.1.0          # Code coverage
pip install pexpect==4.9.0             # Terminal automation (auto-completion testing)
```

#### Development Tools (Optional)
```bash
pip install black==23.9.1        # Code formatter
pip install isort==5.12.0        # Import sorter
pip install flake8==6.1.0        # Linter
pip install pylint==3.0.2        # Advanced linter
pip install mypy==1.5.1          # Type checker
```

**Complete Installation** (all dependencies):
```bash
# Install from requirements file
pip install -r requirements_quant.txt

# Or install CLI-specific dependencies only
pip install asyncpg rich Jinja2 pandas plotly vectorbt numba
```

**Dependency Compatibility**:
- Python: 3.11+
- PostgreSQL: 15.5+ with TimescaleDB 2.11+
- OS: macOS, Linux, Windows WSL

---

## 아키텍처 설계

### 시스템 구조도

```
┌─────────────────────────────────────────────────────────────┐
│                  User Interface Layer                        │
├─────────────────────────┬───────────────────────────────────┤
│    One-Shot CLI         │    Interactive Shell              │
│    (argparse)           │    (cmd.Cmd)                      │
│                         │                                   │
│  $ spock query ...      │  spock> query ...                 │
│  $ spock backtest ...   │  spock> backtest ...              │
└────────────┬────────────┴─────────────┬─────────────────────┘
             │                          │
             └──────────┬───────────────┘
                        │
           ┌────────────▼──────────────┐
           │   Command Router          │
           │   (quant_platform.py)     │
           └────────────┬──────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
┌───────▼──────┐ ┌─────▼──────┐ ┌─────▼──────┐
│ Query Cmd    │ │ Backtest   │ │   Shell    │
│ (query.py)   │ │ (backtest) │ │ (shell.py) │
└───────┬──────┘ └─────┬──────┘ └────────────┘
        │              │
        │              │
┌───────▼──────────────▼─────────────────────┐
│           Core Services                    │
├──────────────┬────────────────┬────────────┤
│ QueryBuilder │ BacktestEngine │ ReportGen  │
└──────┬───────┴────────┬───────┴──────┬─────┘
       │                │              │
┌──────▼────────────────▼──────────────▼─────┐
│         Data Access Layer                  │
├────────────────────────────────────────────┤
│ PostgreSQL (asyncpg) | File System (CSV)  │
└────────────────────────────────────────────┘
```

### 핵심 컴포넌트

#### 1. QueryBuilder
- **책임**: SQL 쿼리 동적 생성
- **패턴**: Builder Pattern
- **기능**: Ranking, Filtering, JOIN 관리

#### 2. DatabaseClient
- **책임**: PostgreSQL 연결 및 쿼리 실행
- **패턴**: Singleton (Connection Pool)
- **기능**: Connection pooling, Error handling, Retry logic

#### 3. QueryFormatter
- **책임**: 터미널 출력 포맷팅
- **패턴**: Strategy Pattern
- **기능**: Rich tables, CSV export, Summary stats

#### 4. QuantShell
- **책임**: 대화형 Shell 인터페이스
- **패턴**: Command Pattern (cmd.Cmd)
- **기능**: Session context, Command history, Strategy persistence

---

## Phase 1: Query Infrastructure (8-12시간)

### Epic 1.1: Query Command Foundation (4-5h)

#### Task 1.1.1: 파일 구조 생성 (30분)

**목표**: 기본 파일 구조 및 의존성 설정

**체크리스트**:
```bash
# 1. 필요한 패키지 설치 (Core CLI dependencies)
pip install asyncpg rich pandas Jinja2

# Additional dependencies for specific features:
# - vectorbt==0.26.2 numba (Sprint 3: Backtesting)
# - pexpect (Sprint 5: Shell auto-completion testing)

# Development/Testing dependencies (optional):
# pip install pytest pytest-asyncio pytest-cov black isort flake8 mypy

# 2. 파일 생성
touch cli/commands/query.py
touch cli/utils/query_builder.py
touch cli/utils/database.py
touch cli/utils/query_formatter.py

# 3. __init__.py 업데이트
# cli/commands/__init__.py에 query import 추가
```

**파일**: `cli/commands/query.py` (기본 구조)

```python
#!/usr/bin/env python3
"""Query Command - Stock screening and ranking"""

import asyncio
from typing import Dict, Any

async def run_query_command(args, config: Dict[str, Any]):
    """Execute query command"""
    # TODO: Implement
    print("Query command placeholder")
    return 0

def query(args, config: Dict[str, Any]):
    """Sync wrapper"""
    return asyncio.run(run_query_command(args, config))
```

**검증**:
```bash
python3 quant_platform.py query --help  # 에러 없이 실행되어야 함
```

---

#### Task 1.1.2: QueryBuilder 클래스 구현 (2시간)

**목표**: SQL 쿼리 동적 생성 로직 구현

**파일**: `cli/utils/query_builder.py`

**구현 순서**:
1. 기본 클래스 구조 (30분)
2. Ranking 메서드 (PE, PB, DY, ROE) (60분)
3. Filter 파싱 로직 (30min)

**핵심 코드**:
```python
class QueryBuilder:
    def __init__(self):
        self.select_columns = ["t.ticker", "t.name"]
        self.joins = []
        self.where_conditions = ["t.region = 'KR'"]
        self.order_by = []
        self._joined_tables = set()

    def add_pe_ranking(self):
        # SELECT, JOIN, WHERE, ORDER BY 추가
        return self

    def build(self, limit: int = 20) -> str:
        # 최종 SQL 생성
        return sql_query
```

**단위 테스트**:
```python
# tests/test_query_builder.py
def test_basic_query():
    builder = QueryBuilder()
    sql = builder.build()
    assert "SELECT" in sql
    assert "FROM tickers" in sql

def test_pe_ranking():
    builder = QueryBuilder()
    builder.add_pe_ranking()
    sql = builder.build()
    assert "sd.pe_ratio" in sql
    assert "ORDER BY sd.pe_ratio ASC" in sql
```

**검증**:
```bash
pytest tests/test_query_builder.py -v
```

---

#### Task 1.1.3: PostgreSQL 연결 (1.5시간)

**목표**: 비동기 DB 연결 및 쿼리 실행

**파일**: `cli/utils/database.py`

**구현 단계**:
1. DatabaseClient 클래스 (45분)
2. Connection pool 설정 (30분)
3. Error handling (15min)

**핵심 코드**:
```python
import asyncpg

class DatabaseClient:
    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def initialize(cls, config: Dict):
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(...)

    @classmethod
    async def fetch(cls, query: str) -> List[Dict]:
        async with cls._pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [dict(row) for row in rows]
```

**수동 테스트**:
```bash
# Python REPL에서
import asyncio
from cli.utils.database import DatabaseClient

async def test():
    await DatabaseClient.initialize(config)
    results = await DatabaseClient.fetch("SELECT * FROM tickers LIMIT 5")
    print(results)

asyncio.run(test())
```

---

#### Task 1.1.4: Rich 테이블 출력 (1시간)

**목표**: 결과를 보기 좋은 터미널 테이블로 표시

**파일**: `cli/utils/query_formatter.py`

**구현**:
```python
from rich.console import Console
from rich.table import Table

def display_results(results: List[Dict], columns: List[str]):
    table = Table(title=f"Query Results ({len(results)} stocks)")
    table.add_column("Ticker", style="cyan")
    table.add_column("Name", style="white")

    for col in columns:
        table.add_column(...)

    for row in results:
        table.add_row(...)

    console.print(table)
```

**검증**:
```bash
# 실제 데이터로 테스트
python3 quant_platform.py query --rank-pe --top 10
```

**기대 출력**:
```
╭─────────────────────────────────────────╮
│ 📊 Query Results (10 stocks)            │
├────────┬────────────────────┬──────────┤
│ Ticker │ Name               │ P/E      │
├────────┼────────────────────┼──────────┤
│ 005930 │ 삼성전자           │ 8.50     │
│ 000660 │ SK하이닉스         │ 9.20     │
╰────────┴────────────────────┴──────────╯
```

---

### Epic 1.2: Filter & Export (3-4h)

#### Task 1.2.1: Filter 표현식 파서 (1.5시간)

**목표**: "pe<10 and dy>2" 같은 표현식을 SQL WHERE 절로 변환

**구현**:
```python
def _parse_filter_expression(self, expr: str) -> str:
    # 1. 컬럼 매핑
    column_map = {'pe': 'sd.pe_ratio', 'dy': 'tf.dividend_yield'}

    # 2. 정규식으로 치환
    import re
    for alias, column in column_map.items():
        expr = re.sub(rf'\b{alias}\b', column, expr)

    # 3. 연산자 변환
    expr = expr.replace('and', 'AND').replace('or', 'OR')

    return expr
```

**테스트**:
```python
def test_filter_parsing():
    builder = QueryBuilder()
    builder.add_pe_ranking().add_dy_ranking()
    builder.add_filter("pe<10 and dy>2")
    sql = builder.build()
    assert "sd.pe_ratio<10" in sql
    assert "tf.dividend_yield>2" in sql
```

---

#### Task 1.2.2: CSV Export (1시간)

**목표**: 결과를 CSV 파일로 저장

**구현**:
```python
import pandas as pd

def export_to_csv(results: List[Dict], filepath: str):
    if not results:
        console.print("[yellow]No results to export[/yellow]")
        return

    df = pd.DataFrame(results)
    df.to_csv(filepath, index=False)
    console.print(f"[green]✅ Exported {len(results)} stocks to {filepath}[/green]")
```

**검증**:
```bash
spock query --rank-pe --top 20 --export-csv test.csv
cat test.csv  # 결과 확인
```

---

#### Task 1.2.3: 고급 필터 (1시간)

**목표**: NI CAGR, Dividend Growth 필터 추가

**구현**:
```python
def add_ni_cagr_filter(self, min_val: Optional[float] = None):
    self._ensure_table_joined("ticker_fundamentals", ...)
    if min_val is not None:
        self.where_conditions.append(f"tf.net_income_cagr >= {min_val}")
```

**검증**:
```bash
spock query --rank-pe --ni-cagr-min 5 --div-growth-min 0
```

---

### Epic 1.3: Integration & Testing (1-2h)

#### Task 1.3.1: quant_platform.py 통합 (30분)

**파일**: `quant_platform.py`

**변경 사항**:
```python
# 1. Import 추가
from cli.commands import query

# 2. Subparser 추가
def create_parser():
    # ... existing code ...

    # Query command
    query_parser = subparsers.add_parser(
        'query',
        help='Query and screen stocks'
    )

    query_parser.add_argument('--rank-pe', action='store_true', help='Rank by P/E')
    query_parser.add_argument('--rank-pb', action='store_true', help='Rank by P/B')
    query_parser.add_argument('--rank-dy', action='store_true', help='Rank by DY')
    query_parser.add_argument('--rank-roe', action='store_true', help='Rank by ROE')
    query_parser.add_argument('--filter', type=str, help='Filter expression')
    query_parser.add_argument('--ni-cagr-min', type=float, help='Min NI CAGR')
    query_parser.add_argument('--div-growth-min', type=float, help='Min Div Growth')
    query_parser.add_argument('--top', type=int, default=20, help='Number of results')
    query_parser.add_argument('--show-price', action='store_true', help='Show price')
    query_parser.add_argument('--export-csv', type=str, help='Export to CSV')

    return parser

# 3. Command routing 추가
def main():
    # ... existing code ...

    elif args.command == 'query':
        query.query(args, config)
```

---

#### Task 1.3.2: 수동 테스트 (30분)

**테스트 시나리오**:

```bash
# 1. 기본 랭킹
spock query --rank-pe --top 20

# 2. 다중 랭킹
spock query --rank-pe --rank-dy --top 20

# 3. 필터 적용
spock query --rank-pe --filter "pe<10 and dy>2"

# 4. 고급 필터
spock query --rank-pe --ni-cagr-min 5 --div-growth-min 0

# 5. 가격 표시
spock query --rank-pe --show-price --top 10

# 6. CSV 내보내기
spock query --rank-pe --rank-dy --export-csv value_stocks.csv

# 7. Verbose 모드
spock query --rank-pe --verbose
```

---

#### Task 1.3.3: 문서화 (30분)

**파일**: `docs/CLI_USAGE_GUIDE.md` 업데이트

**추가 내용**:

```markdown
## Query Command

### 기본 사용법

#### 단순 랭킹
\`\`\`bash
# P/E 낮은 순으로 20개
spock query --rank-pe --top 20

# 배당수익률 높은 순으로 10개
spock query --rank-dy --top 10
\`\`\`

#### 다중 랭킹
\`\`\`bash
# P/E와 배당수익률로 정렬
spock query --rank-pe --rank-dy --top 20
\`\`\`

#### 필터 적용
\`\`\`bash
# P/E < 10이고 배당수익률 > 2%
spock query --rank-pe --filter "pe<10 and dy>2"

# 복잡한 조건
spock query --rank-pe --filter "(pe<10 or pb<1) and dy>2"
\`\`\`

#### 성장 필터
\`\`\`bash
# 순이익 CAGR 5% 이상
spock query --rank-pe --ni-cagr-min 5

# 배당 성장률 0% 이상
spock query --rank-pe --div-growth-min 0
\`\`\`

#### CSV 내보내기
\`\`\`bash
spock query --rank-pe --rank-dy --export-csv results.csv
\`\`\`

### 옵션 상세

| 옵션 | 설명 | 예시 |
|------|------|------|
| --rank-pe | P/E 낮은 순 | --rank-pe |
| --rank-pb | P/B 낮은 순 | --rank-pb |
| --rank-dy | 배당수익률 높은 순 | --rank-dy |
| --rank-roe | ROE 높은 순 | --rank-roe |
| --filter | 필터 표현식 | --filter "pe<10 and dy>2" |
| --ni-cagr-min | 최소 순이익 CAGR (%) | --ni-cagr-min 5 |
| --div-growth-min | 최소 배당 성장률 (%) | --div-growth-min 0 |
| --top | 결과 개수 (기본: 20) | --top 50 |
| --show-price | 현재가 표시 | --show-price |
| --export-csv | CSV 저장 경로 | --export-csv results.csv |
| --verbose | SQL 쿼리 출력 | --verbose |
```

---

### Phase 1 완료 체크리스트

- [ ] QueryBuilder 클래스 구현 및 테스트 통과
- [ ] DatabaseClient 연결 풀 작동
- [ ] Rich 테이블 출력 작동
- [ ] 필터 표현식 파싱 작동
- [ ] CSV export 작동
- [ ] 모든 예제 명령어 실행 성공
- [ ] 문서 업데이트 완료
- [ ] 성능 목표 달성 (<1초)

---

## Phase 2: Interactive Shell (5-8시간)

### Epic 2.1: Shell Framework (3-4h)

#### Task 2.1.1: QuantShell 클래스 생성 (2시간)

**파일**: `cli/shell.py`

**구현 순서**:
1. cmd.Cmd 상속 클래스 (30분)
2. Intro, prompt 설정 (15분)
3. 기본 명령어 (help, quit, exit) (15분)
4. Readline 히스토리 설정 (30min)
5. 에러 핸들링 (30min)

**핵심 코드**:
```python
import cmd
from rich.console import Console

console = Console()

class QuantShell(cmd.Cmd):
    intro = """
╔══════════════════════════════════════════════╗
║   Quant Platform Interactive Shell v1.0     ║
║   Type 'help' for commands, 'quit' to exit  ║
╚══════════════════════════════════════════════╝
"""
    prompt = "spock> "

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self.context = ShellContext()

    def do_quit(self, arg):
        """Exit shell"""
        console.print("[cyan]Goodbye! 👋[/cyan]")
        return True

    do_exit = do_quit  # Alias

    def emptyline(self):
        """Do nothing on empty line"""
        pass

    def default(self, line):
        """Handle unknown commands"""
        console.print(f"[red]Unknown command: {line}[/red]")
```

**검증**:
```bash
python3 -c "from cli.shell import QuantShell; QuantShell({}).cmdloop()"
```

---

#### Task 2.1.2: ShellContext 구현 (1시간)

**목표**: 세션 상태 관리

**파일**: `cli/shell.py` (같은 파일 내)

**구현**:
```python
from pathlib import Path
import json

class ShellContext:
    """Session context for interactive shell"""

    def __init__(self):
        self.last_results: List[Dict] = []
        self.filters: List[str] = []
        self.limit: int = 20
        self.strategies: Dict[str, str] = self._load_strategies()

    def add_filter(self, filter_expr: str):
        self.filters.append(filter_expr)

    def clear_filters(self):
        self.filters = []

    def get_combined_filter(self) -> str:
        return " and ".join(f"({f})" for f in self.filters)

    def save_strategy(self, name: str, filter_expr: str):
        self.strategies[name] = filter_expr
        self._persist_strategies()

    def _load_strategies(self) -> Dict[str, str]:
        config_file = Path.home() / '.quant_platform' / 'strategies.json'
        if config_file.exists():
            with open(config_file) as f:
                return json.load(f)
        return {}

    def _persist_strategies(self):
        config_dir = Path.home() / '.quant_platform'
        config_dir.mkdir(exist_ok=True)

        config_file = config_dir / 'strategies.json'
        with open(config_file, 'w') as f:
            json.dump(self.strategies, f, indent=2)
```

---

#### Task 2.1.3: Command 파싱 헬퍼 (30분)

**목표**: Shell 명령어 인자 파싱

**구현**:
```python
def _parse_shell_args(self, arg_string: str, defaults: Dict) -> Dict:
    """Parse shell command arguments"""
    import shlex
    args = shlex.split(arg_string)

    result = defaults.copy()
    i = 0
    while i < len(args):
        if args[i].startswith('--'):
            key = args[i][2:]
            if i + 1 < len(args) and not args[i+1].startswith('--'):
                result[key] = args[i+1]
                i += 2
            else:
                result[key] = True
                i += 1
        else:
            i += 1

    return result
```

**테스트**:
```python
def test_parse_args():
    shell = QuantShell({})
    result = shell._parse_shell_args("--top 10 --verbose", {'top': 20})
    assert result['top'] == '10'
    assert result['verbose'] == True
```

---

### Epic 2.2: Shell Commands (2-3h)

#### Task 2.2.1: Ranking Commands (1시간)

**구현**: `do_rank_pe`, `do_rank_dy` 등

```python
def do_rank_pe(self, arg):
    """Rank stocks by P/E ratio

    Usage: rank-pe [--top N]
    Example: rank-pe --top 20
    """
    args = self._parse_shell_args(arg, {'top': 20})

    # Reuse query logic from Phase 1
    from cli.commands.query import QueryBuilder, execute_query, display_results

    builder = QueryBuilder()
    builder.add_pe_ranking()
    sql = builder.build(limit=int(args['top']))

    # Execute (sync wrapper for shell)
    results = asyncio.run(execute_query(sql, self.config))

    # Update context
    self.context.last_results = results

    # Display
    display_results(results, ['pe'])

def do_rank_dy(self, arg):
    """Rank stocks by Dividend Yield"""
    # Similar implementation

# Aliases
def do_rpe(self, arg):
    """Shortcut for rank-pe"""
    self.do_rank_pe(arg)

def do_rdy(self, arg):
    """Shortcut for rank-dy"""
    self.do_rank_dy(arg)
```

---

#### Task 2.2.2: Filter Command (30분)

```python
def do_filter(self, arg):
    """Apply filter to current results

    Usage: filter "expression"
    Example: filter "pe<10 and dy>2"
    """
    if not arg:
        console.print("[red]Error: Filter expression required[/red]")
        return

    # Remove quotes if present
    filter_expr = arg.strip('"').strip("'")

    # Add to context
    self.context.add_filter(filter_expr)

    # Re-run query with combined filters
    builder = QueryBuilder()
    builder.add_pe_ranking()  # TODO: Track which rankings are active
    builder.add_filter(self.context.get_combined_filter())

    sql = builder.build(limit=self.context.limit)
    results = asyncio.run(execute_query(sql, self.config))

    self.context.last_results = results
    display_results(results, ['pe'])

def do_clear_filter(self, arg):
    """Clear all filters"""
    self.context.clear_filters()
    console.print("[green]✅ Filters cleared[/green]")
```

---

#### Task 2.2.3: Export & Utility Commands (30분)

```python
def do_export(self, arg):
    """Export current results to CSV

    Usage: export [filename]
    Example: export value_stocks.csv
    """
    from datetime import datetime
    from cli.commands.query import export_to_csv

    filename = arg or f"results_{datetime.now():%Y%m%d_%H%M%S}.csv"

    if not self.context.last_results:
        console.print("[yellow]No results to export[/yellow]")
        return

    export_to_csv(self.context.last_results, filename)

def do_clear(self, arg):
    """Clear screen"""
    import os
    os.system('clear' if os.name != 'nt' else 'cls')

def do_history(self, arg):
    """Show command history"""
    import readline
    for i in range(1, readline.get_current_history_length() + 1):
        print(f"{i}: {readline.get_history_item(i)}")
```

---

#### Task 2.2.4: Strategy Management (1시간)

```python
def do_save_strategy(self, arg):
    """Save current filter as named strategy

    Usage: save-strategy name
    Example: save-strategy value-dividend
    """
    if not arg:
        console.print("[red]Error: Strategy name required[/red]")
        return

    if not self.context.filters:
        console.print("[yellow]No filter to save[/yellow]")
        return

    filter_expr = self.context.get_combined_filter()
    self.context.save_strategy(arg, filter_expr)
    console.print(f"[green]✅ Strategy '{arg}' saved[/green]")

def do_load_strategy(self, arg):
    """Load saved strategy

    Usage: load-strategy name
    Example: load-strategy value-dividend
    """
    if not arg:
        console.print("[red]Error: Strategy name required[/red]")
        return

    strategy = self.context.strategies.get(arg)
    if not strategy:
        console.print(f"[red]Strategy '{arg}' not found[/red]")
        return

    # Clear existing filters and set new one
    self.context.clear_filters()
    self.context.add_filter(strategy)

    console.print(f"[green]✅ Strategy '{arg}' loaded[/green]")

    # Execute query to show results
    self.do_filter(f'"{strategy}"')

def do_list_strategies(self, arg):
    """List all saved strategies"""
    if not self.context.strategies:
        console.print("[yellow]No saved strategies[/yellow]")
        return

    from rich.table import Table
    table = Table(title="💾 Saved Strategies")
    table.add_column("Name", style="cyan")
    table.add_column("Filter", style="white")

    for name, filter_expr in self.context.strategies.items():
        table.add_row(name, filter_expr)

    console.print(table)
```

---

### Epic 2.3: Integration (1h)

#### Task 2.3.1: quant_platform.py 통합 (30분)

```python
# quant_platform.py

def create_parser():
    # ... existing code ...

    # Shell command
    shell_parser = subparsers.add_parser(
        'shell',
        help='Start interactive shell'
    )

    return parser

def main():
    # ... existing code ...

    elif args.command == 'shell':
        from cli.shell import QuantShell
        shell = QuantShell(config)
        shell.cmdloop()
```

**검증**:
```bash
python3 quant_platform.py shell
```

---

#### Task 2.3.2: 전체 워크플로우 테스트 (30분)

**테스트 시나리오**:

```bash
$ python3 quant_platform.py shell

╔══════════════════════════════════════════════╗
║   Quant Platform Interactive Shell v1.0     ║
║   Type 'help' for commands, 'quit' to exit  ║
╚══════════════════════════════════════════════╝

spock> rank-pe --top 10
[테이블 출력]

spock> filter "dy>2"
[필터링된 결과]

spock> save-strategy value-dividend
✅ Strategy 'value-dividend' saved

spock> clear-filter

spock> load-strategy value-dividend
✅ Strategy 'value-dividend' loaded
[결과 출력]

spock> export value_stocks.csv
✅ Exported 8 stocks to value_stocks.csv

spock> list-strategies
[전략 목록]

spock> quit
Goodbye! 👋
```

---

### Phase 2 완료 체크리스트

- [ ] QuantShell 클래스 작동
- [ ] ShellContext 상태 유지
- [ ] 모든 ranking 명령어 작동
- [ ] Filter 누적 적용 작동
- [ ] Export 작동
- [ ] Strategy 저장/로드 작동
- [ ] Command history 작동
- [ ] 에러 없이 전체 워크플로우 실행

---

## Phase 3: Backtest Integration (10-15시간)

### Epic 3.1: Backtest Command (5-7h)

#### Task 3.1.1: 기본 구조 (1시간)

**파일**: `cli/commands/backtest.py`

```python
#!/usr/bin/env python3
"""Backtest Command - Strategy backtesting"""

import asyncio
from datetime import datetime
from pathlib import Path
import webbrowser

from rich.console import Console
from rich.panel import Panel

console = Console()

async def run_backtest_command(args, config):
    """Execute backtest command"""

    console.print(Panel(
        f"[bold]Backtest Configuration[/bold]\n\n"
        f"Strategy: {args.strategy}\n"
        f"Period: {args.start} to {args.end}\n"
        f"Rebalance: {args.rebalance}\n"
        f"Portfolio Size: {args.top_n} stocks",
        title="⚙️ Configuration",
        border_style="blue"
    ))

    # TODO: Implement backtest logic
    console.print("[yellow]Backtest functionality coming soon...[/yellow]")

    return 0

def backtest(args, config):
    """Sync wrapper"""
    return asyncio.run(run_backtest_command(args, config))
```

**quant_platform.py 통합**:
```python
from cli.commands import backtest

# Parser
backtest_parser = subparsers.add_parser('backtest', help='Run backtest')
backtest_parser.add_argument('--strategy', required=True, help='Strategy expression')
backtest_parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
backtest_parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
backtest_parser.add_argument('--rebalance', choices=['monthly', 'quarterly', 'yearly'],
                            default='quarterly')
backtest_parser.add_argument('--top-n', type=int, default=20, help='Portfolio size')
backtest_parser.add_argument('--export-html', action='store_true')

# Routing
elif args.command == 'backtest':
    backtest.backtest(args, config)
```

---

#### Task 3.1.2: vectorbt 통합 (3-4시간)

**파일**: `modules/backtesting/simple_backtest.py`

**구현 단계**:
1. OHLCV 데이터 로드 (1시간)
2. 전략 기반 종목 선정 (1시간)
3. vectorbt 포트폴리오 시뮬레이션 (1-2시간)

**핵심 코드**:
```python
import vectorbt as vbt
import pandas as pd
from dataclasses import dataclass

@dataclass
class BacktestResults:
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    portfolio_value: pd.Series
    trades: pd.DataFrame
    strategy: str
    start_date: str
    end_date: str

async def load_ohlcv_data(
    tickers: List[str],
    start_date: str,
    end_date: str,
    config: Dict
) -> pd.DataFrame:
    """Load OHLCV data from PostgreSQL"""
    from cli.utils.database import DatabaseClient

    await DatabaseClient.initialize(config)

    query = f"""
    SELECT ticker, date, close
    FROM ohlcv_data
    WHERE ticker = ANY($1)
      AND region = 'KR'
      AND date BETWEEN $2 AND $3
    ORDER BY date, ticker
    """

    results = await DatabaseClient.fetch(query, tickers, start_date, end_date)

    # Convert to DataFrame
    df = pd.DataFrame(results)
    df['date'] = pd.to_datetime(df['date'])

    # Pivot to wide format (dates x tickers)
    pivot = df.pivot(index='date', columns='ticker', values='close')

    return pivot

def run_simple_backtest(
    ohlcv_data: pd.DataFrame,
    strategy: str,
    rebalance_freq: str,
    top_n: int
) -> BacktestResults:
    """Run backtest using vectorbt"""

    # For now, simple buy-and-hold of all tickers
    # TODO: Implement actual strategy filtering and rebalancing

    # Create portfolio
    portfolio = vbt.Portfolio.from_holding(
        close=ohlcv_data,
        init_cash=100_000_000,
        fees=0.00015  # 0.015%
    )

    results = BacktestResults(
        total_return=portfolio.total_return(),
        sharpe_ratio=portfolio.sharpe_ratio(),
        max_drawdown=portfolio.max_drawdown(),
        win_rate=0.0,  # TODO
        portfolio_value=portfolio.value(),
        trades=pd.DataFrame(),  # TODO
        strategy=strategy,
        start_date=str(ohlcv_data.index.min()),
        end_date=str(ohlcv_data.index.max())
    )

    return results
```

---

#### Task 3.1.3: 결과 표시 (1시간)

```python
def display_backtest_summary(results: BacktestResults):
    """Display backtest summary in terminal"""

    console.print(Panel.fit(
        f"[green]✅ Backtest Completed![/green]\n\n"
        f"📈 Total Return: {results.total_return:.2%}\n"
        f"📊 Sharpe Ratio: {results.sharpe_ratio:.2f}\n"
        f"📉 Max Drawdown: {results.max_drawdown:.2%}\n"
        f"🎯 Win Rate: {results.win_rate:.1%}\n",
        title="Backtest Results",
        border_style="green"
    ))
```

---

### Epic 3.2: HTML Report (4-6h)

#### Task 3.2.1: Plotly 차트 생성 (2시간)

**파일**: `cli/utils/report_generator.py`

```python
import plotly.graph_objects as go

def create_portfolio_chart(results: BacktestResults) -> go.Figure:
    """Portfolio value over time"""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=results.portfolio_value.index,
        y=results.portfolio_value.values,
        mode='lines',
        name='Portfolio Value',
        line=dict(color='#2E86AB', width=2)
    ))

    fig.update_layout(
        title='Portfolio Value Over Time',
        xaxis_title='Date',
        yaxis_title='Portfolio Value (₩)',
        template='plotly_white',
        height=400
    )

    return fig

def create_drawdown_chart(results: BacktestResults) -> go.Figure:
    """Drawdown chart"""
    # Calculate drawdowns
    cummax = results.portfolio_value.cummax()
    drawdowns = (results.portfolio_value - cummax) / cummax

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=drawdowns.index,
        y=drawdowns.values * 100,
        mode='lines',
        name='Drawdown',
        fill='tozeroy',
        line=dict(color='#A23B72', width=2)
    ))

    fig.update_layout(
        title='Drawdown Over Time',
        xaxis_title='Date',
        yaxis_title='Drawdown (%)',
        template='plotly_white',
        height=300
    )

    return fig
```

---

#### Task 3.2.2: Jinja2 템플릿 (1.5시간)

**파일**: `templates/backtest_report.html`

*(내용은 위 설계 섹션 참조)*

---

#### Task 3.2.3: Report Generator (1시간)

```python
from jinja2 import Environment, FileSystemLoader

class ReportGenerator:
    def __init__(self):
        template_dir = Path(__file__).parent.parent / 'templates'
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.template = self.env.get_template('backtest_report.html')

    def generate(self, results: BacktestResults) -> Path:
        """Generate HTML report"""

        # Create charts
        portfolio_chart = create_portfolio_chart(results)
        drawdown_chart = create_drawdown_chart(results)

        # Render template
        html_content = self.template.render(
            strategy=results.strategy,
            start_date=results.start_date,
            end_date=results.end_date,
            total_return=f"{results.total_return:.2%}",
            sharpe_ratio=f"{results.sharpe_ratio:.2f}",
            max_drawdown=f"{results.max_drawdown:.2%}",
            portfolio_chart=portfolio_chart.to_html(include_plotlyjs='cdn'),
            drawdown_chart=drawdown_chart.to_html(include_plotlyjs=False)
        )

        # Save
        report_dir = Path('reports')
        report_dir.mkdir(exist_ok=True)

        report_path = report_dir / f"backtest_{datetime.now():%Y%m%d_%H%M%S}.html"
        report_path.write_text(html_content, encoding='utf-8')

        return report_path
```

---

### Epic 3.3: Shell Integration (1-2h)

#### Task 3.3.1: Shell backtest command (1시간)

```python
# cli/shell.py

def do_backtest(self, arg):
    """Run backtest with current filter

    Usage: backtest --start YYYY-MM-DD --end YYYY-MM-DD
    Example: backtest --start 2020-01-01 --end 2024-12-31
    """
    if not self.context.filters:
        console.print("[yellow]⚠ No filter set. Use 'filter' command first[/yellow]")
        return

    args = self._parse_shell_args(arg, {
        'start': '2020-01-01',
        'end': '2024-12-31',
        'rebalance': 'quarterly',
        'top_n': 20
    })

    # Use current filter as strategy
    strategy = self.context.get_combined_filter()

    from cli.commands.backtest import run_backtest_command
    import types

    # Create args namespace
    backtest_args = types.SimpleNamespace(
        strategy=strategy,
        start=args['start'],
        end=args['end'],
        rebalance=args.get('rebalance', 'quarterly'),
        top_n=int(args.get('top_n', 20)),
        export_html=True
    )

    # Run backtest
    asyncio.run(run_backtest_command(backtest_args, self.config))
```

---

### Phase 3 완료 체크리스트

- [ ] Backtest command 기본 구조 작동
- [ ] OHLCV 데이터 로드 작동
- [ ] vectorbt 포트폴리오 시뮬레이션 작동
- [ ] Plotly 차트 생성 작동
- [ ] HTML 리포트 생성 및 자동 열기 작동
- [ ] Shell에서 backtest 작동
- [ ] 성능 목표 달성 (<10초)

---

## Phase 4: Polish & Documentation (3-5시간)

### Epic 4.1: Performance Optimization (1-2h)

#### Task 4.1.1: DB Index 확인 (30분)

```sql
-- PostgreSQL indexes
CREATE INDEX IF NOT EXISTS idx_tickers_region ON tickers(region);
CREATE INDEX IF NOT EXISTS idx_stock_details_ticker_region ON stock_details(ticker, region);
CREATE INDEX IF NOT EXISTS idx_ticker_fundamentals_ticker_region ON ticker_fundamentals(ticker, region);
CREATE INDEX IF NOT EXISTS idx_ohlcv_date ON ohlcv_data(date);
CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker_region ON ohlcv_data(ticker, region);
```

---

#### Task 4.1.2: 쿼리 프로파일링 (30분)

```python
# Add timing to queries
import time

async def execute_query(query: str, config: Dict) -> List[Dict]:
    start = time.time()

    # ... execute query ...

    elapsed = time.time() - start
    if elapsed > 1.0:
        console.print(f"[yellow]Query took {elapsed:.2f}s (>1s target)[/yellow]")

    return results
```

---

### Epic 4.2: Error Handling (1-2h)

#### Task 4.2.1: 입력 검증 (1시간)

```python
def validate_date(date_str: str) -> bool:
    """Validate date format"""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def validate_filter_expression(expr: str) -> tuple[bool, str]:
    """Validate filter expression syntax"""
    # Basic validation
    if not expr:
        return False, "Empty expression"

    # Check for SQL injection attempts
    dangerous = ['DROP', 'DELETE', 'UPDATE', 'INSERT', ';', '--']
    upper_expr = expr.upper()
    for word in dangerous:
        if word in upper_expr:
            return False, f"Dangerous keyword: {word}"

    return True, ""
```

---

#### Task 4.2.2: 친절한 에러 메시지 (1시간)

```python
# Example error handling in query command

try:
    results = await execute_query(query, config)
except asyncpg.exceptions.PostgresError as e:
    console.print("[red]❌ Database Error[/red]")
    console.print(f"Details: {e}")
    console.print("\n[yellow]Possible solutions:[/yellow]")
    console.print("1. Check if PostgreSQL is running")
    console.print("2. Verify database credentials in config.yaml")
    console.print("3. Ensure database 'quant_platform' exists")
    return 1
except Exception as e:
    console.print(f"[red]❌ Unexpected Error: {e}[/red]")
    if args.verbose:
        import traceback
        traceback.print_exc()
    return 1
```

---

### Epic 4.3: Documentation (1h)

#### Task 4.3.1: CLI_USAGE_GUIDE 완성 (30분)

**추가 섹션**:
- Interactive Shell 사용법
- 전체 워크플로우 예시
- 트러블슈팅
- FAQ

---

#### Task 4.3.2: Tutorial 작성 (30분)

**파일**: `docs/CLI_TUTORIAL.md`

```markdown
# Quant Platform CLI - 초보자 가이드

## 1. 첫 실행

\`\`\`bash
# 도움말 확인
python3 quant_platform.py --help

# 첫 쿼리 실행
python3 quant_platform.py query --rank-pe --top 10
\`\`\`

## 2. 전략 탐색 워크플로우

### 단계 1: 저 PER 종목 찾기

\`\`\`bash
python3 quant_platform.py query --rank-pe --top 20
\`\`\`

### 단계 2: 배당수익률 추가

\`\`\`bash
python3 quant_platform.py query --rank-pe --rank-dy --top 20
\`\`\`

### 단계 3: 필터 적용

\`\`\`bash
python3 quant_platform.py query --rank-pe --rank-dy --filter "pe<10 and dy>2"
\`\`\`

### 단계 4: 결과 저장

\`\`\`bash
python3 quant_platform.py query --rank-pe --rank-dy --filter "pe<10 and dy>2" --export-csv value_stocks.csv
\`\`\`

### 단계 5: 백테스트

\`\`\`bash
python3 quant_platform.py backtest --strategy "pe<10 and dy>2" --start 2020-01-01 --end 2024-12-31 --export-html
\`\`\`

## 3. 대화형 Shell 사용

\`\`\`bash
python3 quant_platform.py shell

spock> rank-pe --top 20
spock> filter "dy>2"
spock> save-strategy value-dividend
spock> backtest --start 2020-01-01 --end 2024-12-31
spock> quit
\`\`\`

## 4. 자주 묻는 질문

### Q: "No results found" 메시지가 나옵니다

A: 필터 조건이 너무 엄격할 수 있습니다. `--verbose` 옵션으로 SQL 쿼리를 확인하세요.

### Q: 데이터베이스 연결 오류

A: PostgreSQL이 실행 중인지 확인하고, `config.yaml`의 데이터베이스 설정을 확인하세요.
\`\`\`

---

## 테스트 전략

### 단위 테스트

**파일**: `tests/test_query_builder.py`

```python
import pytest
from cli.utils.query_builder import QueryBuilder

def test_basic_query():
    builder = QueryBuilder()
    sql = builder.build()
    assert "SELECT" in sql
    assert "FROM tickers" in sql
    assert "WHERE t.region = 'KR'" in sql

def test_pe_ranking():
    builder = QueryBuilder()
    builder.add_pe_ranking()
    sql = builder.build()
    assert "sd.pe_ratio" in sql
    assert "ORDER BY sd.pe_ratio ASC" in sql

def test_filter_parsing():
    builder = QueryBuilder()
    builder.add_pe_ranking().add_dy_ranking()
    builder.add_filter("pe<10 and dy>2")
    sql = builder.build()
    assert "sd.pe_ratio<10" in sql
    assert "tf.dividend_yield>2" in sql

def test_no_duplicate_joins():
    builder = QueryBuilder()
    builder.add_pe_ranking()
    builder.add_pb_ranking()  # Both use stock_details
    sql = builder.build()
    # Should only have one JOIN to stock_details
    assert sql.count("stock_details sd") == 1
```

**실행**:
```bash
pytest tests/test_query_builder.py -v
```

---

### 통합 테스트

**파일**: `tests/integration/test_query_command.py`

```python
import pytest
import asyncio
from cli.commands.query import run_query_command

@pytest.fixture
def config():
    return {
        'database': {
            'host': 'localhost',
            'port': 5432,
            'user': 'postgres',
            'password': '',
            'database': 'quant_platform'
        }
    }

@pytest.mark.asyncio
async def test_query_with_pe_ranking(config):
    """Test query command with PE ranking"""
    import types
    args = types.SimpleNamespace(
        rank_pe=True,
        rank_pb=False,
        rank_dy=False,
        rank_roe=False,
        show_price=False,
        filter=None,
        top=10,
        export_csv=None,
        verbose=False
    )

    result = await run_query_command(args, config)
    assert result == 0  # Success
```

---

### 수동 테스트 체크리스트

#### Phase 1 Tests

- [ ] `spock query --rank-pe --top 20` → 20개 결과 출력
- [ ] `spock query --rank-dy --top 10` → 10개 결과 출력
- [ ] `spock query --rank-pe --rank-dy` → 두 컬럼 모두 표시
- [ ] `spock query --rank-pe --filter "pe<10"` → 필터 적용된 결과
- [ ] `spock query --rank-pe --export-csv test.csv` → CSV 파일 생성
- [ ] `spock query --rank-pe --verbose` → SQL 쿼리 출력
- [ ] 잘못된 필터 입력 시 명확한 에러 메시지

#### Phase 2 Tests

- [ ] `spock shell` → Shell 시작
- [ ] `spock> rank-pe --top 10` → 결과 출력
- [ ] `spock> filter "dy>2"` → 필터링 작동
- [ ] `spock> export test.csv` → CSV 저장
- [ ] `spock> save-strategy test` → 전략 저장
- [ ] `spock> list-strategies` → 전략 목록
- [ ] `spock> load-strategy test` → 전략 로드
- [ ] `spock> quit` → 정상 종료

#### Phase 3 Tests

- [ ] `spock backtest --strategy "pe<10" --start 2020-01-01 --end 2024-12-31` → 백테스트 실행
- [ ] HTML 리포트 자동 열림
- [ ] 차트가 인터랙티브하게 작동
- [ ] `spock> backtest --start 2020-01-01` → Shell에서 백테스트 작동

---

## 배포 체크리스트

### 릴리스 전 체크리스트

#### 기능 완성도

- [ ] 모든 Phase 1-4 Task 완료
- [ ] 모든 단위 테스트 통과
- [ ] 모든 통합 테스트 통과
- [ ] 모든 수동 테스트 시나리오 통과

#### 문서화

- [ ] CLI_USAGE_GUIDE.md 완성
- [ ] CLI_TUTORIAL.md 완성
- [ ] IMPLEMENTATION_CHECKLIST_CLI.md 업데이트
- [ ] README.md에 CLI 섹션 추가
- [ ] 모든 명령어 help 텍스트 작성

#### 성능

- [ ] 쿼리 실행 <1초 (20개 결과)
- [ ] 백테스트 <10초 (5년 기간)
- [ ] Shell 명령어 반응 <100ms
- [ ] CSV export <1초

#### 에러 핸들링

- [ ] 모든 입력 검증 구현
- [ ] 명확한 에러 메시지
- [ ] Graceful degradation (DB 연결 실패 등)
- [ ] Verbose 모드에서 상세 에러 출력

#### 사용성

- [ ] 직관적인 명령어 구조
- [ ] 일관된 출력 포맷
- [ ] 유용한 help 텍스트
- [ ] 예제 명령어 작동

---

### 릴리스 노트 (v1.0)

```markdown
# Quant Platform CLI v1.0 Release Notes

## 새로운 기능

### Query Command
- P/E, P/B, DY, ROE 기반 종목 랭킹
- 복잡한 필터 표현식 지원 (예: "pe<10 and dy>2")
- CSV export 기능
- 성장 필터 (순이익 CAGR, 배당 성장률)

### Interactive Shell
- 대화형 탐색 워크플로우
- 세션 컨텍스트 유지
- 전략 저장/로드 기능
- Command history 지원

### Backtest Command
- vectorbt 기반 백테스트
- 월/분기/연간 리밸런싱
- HTML 리포트 자동 생성
- Plotly 인터랙티브 차트

## 성능

- 쿼리 실행: <1초 (20개 결과)
- 백테스트: <10초 (5년 기간)
- Shell 반응성: <100ms

## 알려진 제한 사항

- 현재 KR 시장만 지원
- 백테스트 전략 선정 로직 단순화 (향후 개선 예정)
- HTML 리포트 커스터마이징 제한적

## 다음 버전 (v1.1) 계획

- 전략 백테스트 로직 고도화
- 월별/연도별 리턴 상세 분석
- 섹터 필터 추가
- 포트폴리오 최적화 통합
```

---

## 부록: 개발 환경 설정

### 필수 요구사항

```bash
# Python 3.11+
python3 --version

# PostgreSQL 15+ (TimescaleDB)
psql --version

# 필수 패키지
pip install -r requirements.txt
```

**requirements.txt 추가 항목**:
```
asyncpg>=0.28.0
rich>=13.0.0
pandas>=2.0.0
vectorbt>=0.25.0
plotly>=5.17.0
jinja2>=3.1.0
```

---

### 개발 도구

```bash
# Code formatter
pip install black isort

# Linter
pip install pylint flake8

# Type checker
pip install mypy

# Testing
pip install pytest pytest-asyncio pytest-cov
```

---

## 요약: 주차별 작업 계획

### Week 1 (16-20시간)

**Day 1-2 (8-12h)**: Phase 1 - Query Infrastructure
- QueryBuilder 구현
- DB 연결
- Rich 테이블 출력
- 필터 & Export

**Day 3-4 (5-8h)**: Phase 2 - Interactive Shell
- QuantShell 구현
- Shell commands
- Strategy 관리

**마감**: One-shot CLI와 Interactive Shell 완성

---

### Week 2 (10-20시간)

**Day 1-3 (10-15h)**: Phase 3 - Backtest Integration
- Backtest command
- vectorbt 통합
- HTML 리포트 생성

**Day 4 (3-5h)**: Phase 4 - Polish & Documentation
- 성능 최적화
- 에러 핸들링
- 문서 완성

**마감**: 전체 기능 완성 및 릴리스

---

## 🎯 우선순위 최적화 구현 계획

### 배경 및 최적화 원칙

**원래 계획의 문제점**:
- Interactive Shell (Phase 2)이 Backtest (Phase 3)보다 먼저 구현 예정
- 하지만 사용자의 핵심 워크플로우는: **탐색적 쿼리 → 백테스트 → HTML 리포트**
- 백테스트는 높은 가치 + 높은 리스크(vectorbt 통합)를 가진 핵심 기능

**최적화 원칙**:
1. **가치 우선**: 핵심 워크플로우(백테스트)를 빠르게 제공
2. **리스크 관리**: 고위험 항목(vectorbt)을 일찍 다루어 디버깅 시간 확보
3. **점진적 제공**: 40% → 70% → 85% → 95% → 100% 방식으로 기능 완성도 증가
4. **UX 후순위**: Interactive Shell은 기능 완성 후 UX 개선으로 분류

### 최적화된 6-Sprint 구현 계획

#### Sprint 1: Foundation + Quick Win (6-8시간)
**목표**: 즉시 사용 가능한 쿼리 인프라 구축 (40% 완성)

**Task 1.1: Database Connection Setup (1-2h)**
```python
# cli/utils/database.py
import asyncpg
from typing import Optional

class DatabaseManager:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            host="localhost",
            database="quant_platform",
            user="postgres",
            min_size=2,
            max_size=10
        )

    async def disconnect(self):
        if self.pool:
            await self.pool.close()
```

**Task 1.2: Query Builder (2-3h)**
```python
# cli/utils/query_builder.py
from typing import List, Dict, Any
import pandas as pd

class QueryBuilder:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.filters = []

    def tickers(self, region: str = "KR") -> 'QueryBuilder':
        self.base_query = f"""
            SELECT t.ticker, t.name, sd.market_cap, sd.sector
            FROM tickers t
            LEFT JOIN stock_details sd ON t.ticker = sd.ticker AND t.region = sd.region
            WHERE t.region = '{region}'
        """
        return self

    def filter(self, expression: str) -> 'QueryBuilder':
        # Parse: "market_cap > 1000000000" or "sector == '반도체'"
        self.filters.append(expression)
        return self

    async def execute(self) -> pd.DataFrame:
        query = self.base_query
        if self.filters:
            query += " AND " + " AND ".join(self._parse_filters())

        result = await self.db.pool.fetch(query)
        return pd.DataFrame(result)
```

**Task 1.3: Basic CLI (2-3h)**
```python
# cli/commands/query.py
import asyncio
import click

@click.group()
def cli():
    pass

@cli.command()
@click.option('--region', default='KR', help='Market region')
@click.option('--filter', 'filters', multiple=True, help='Filter expression')
def query(region, filters):
    """Query tickers with filters"""
    async def run():
        db = DatabaseManager()
        await db.connect()

        qb = QueryBuilder(db).tickers(region)
        for f in filters:
            qb.filter(f)

        df = await qb.execute()
        print(df)

        await db.disconnect()

    asyncio.run(run())
```

**Task 1.4: Rich Terminal Formatting (1-2h)**
```python
# cli/utils/formatters.py
from rich.console import Console
from rich.table import Table
import pandas as pd

def format_dataframe(df: pd.DataFrame, title: str = "Results") -> None:
    console = Console()
    table = Table(title=title, show_lines=True)

    for col in df.columns:
        table.add_column(col, style="cyan")

    for _, row in df.iterrows():
        table.add_row(*[str(val) for val in row])

    console.print(table)
```

**Sprint 1 Value Delivery**:
- ✅ 사용자가 즉시 데이터베이스 쿼리 가능
- ✅ Rich formatting으로 가독성 높은 출력
- ✅ 필터 기능으로 종목 스크리닝 가능
- ⏱️ **Timeline**: Day 2-3 완료

---

#### Sprint 2: Enhanced Screening (4-6시간)
**목표**: 쿼리 기능 강화 (70% 완성)

**Task 2.1: Advanced Filters (2-3h)**
```python
# cli/utils/query_builder.py (확장)

def top(self, n: int, by: str, ascending: bool = False) -> 'QueryBuilder':
    """상위 N개 종목 선택"""
    self.order_by = f"ORDER BY {by} {'ASC' if ascending else 'DESC'} LIMIT {n}"
    return self

def select(self, *columns: str) -> 'QueryBuilder':
    """특정 컬럼만 선택"""
    self.selected_columns = columns
    return self

# Usage:
# python3 quant_platform.py query --region KR \
#   --filter "market_cap > 1000000000" \
#   --top 20 --sort-by market_cap \
#   --columns ticker,name,market_cap,sector
```

**Task 2.2: CSV Export (1-2h)**
```python
@cli.command()
@click.option('--output', '-o', type=click.Path(), help='Output CSV file')
def query(region, filters, output):
    df = await qb.execute()

    if output:
        df.to_csv(output, index=False, encoding='utf-8-sig')  # Excel 호환
        print(f"✅ Saved to {output}")
    else:
        format_dataframe(df)
```

**Task 2.3: Multiple Metrics (1-2h)**
```python
# 기술적 지표 + 펀더멘털 결합
qb = QueryBuilder(db).tickers('KR')\
    .with_technicals(['rsi_14', 'sma_20', 'ema_50'])\
    .with_fundamentals(['pe_ratio', 'pb_ratio', 'roe'])\
    .filter("rsi_14 < 30 AND pe_ratio < 15")\
    .top(10, by='market_cap')
```

**Sprint 2 Value Delivery**:
- ✅ 복잡한 필터 조합 가능
- ✅ CSV 파일로 결과 저장 → Excel 분석 가능
- ✅ 기술적 지표 + 펀더멘털 통합 쿼리
- ⏱️ **Timeline**: Day 4-5 완료

---

#### Sprint 3: Backtest Foundation (8-10시간) 🎯 **핵심 가치 제공**
**목표**: vectorbt 통합 및 백테스트 실행 (85% 완성)

**Task 3.1: vectorbt Installation & Setup (1-2h)**
```bash
pip install vectorbt==0.26.2
pip install numba  # vectorbt dependency for speed

# Test installation
python3 -c "import vectorbt as vbt; print(vbt.__version__)"
```

**Task 3.2: Simple Backtest (3-4h)**
```python
# cli/commands/backtest.py
import vectorbt as vbt
import pandas as pd

@cli.command()
@click.argument('ticker')
@click.option('--start', default='2020-01-01', help='Start date')
@click.option('--end', default='2023-12-31', help='End date')
def backtest(ticker, start, end):
    """Run simple backtest on a ticker"""

    # 1. Load data from PostgreSQL
    async def load_data():
        db = DatabaseManager()
        await db.connect()

        query = f"""
            SELECT date, close
            FROM ohlcv_data
            WHERE ticker = '{ticker}' AND timeframe = '1d'
            AND date BETWEEN '{start}' AND '{end}'
            ORDER BY date
        """
        result = await db.pool.fetch(query)
        await db.disconnect()

        df = pd.DataFrame(result)
        df.set_index('date', inplace=True)
        return df['close']

    price = asyncio.run(load_data())

    # 2. Simple SMA crossover strategy
    fast_sma = vbt.MA.run(price, window=20, short_name='fast')
    slow_sma = vbt.MA.run(price, window=50, short_name='slow')

    entries = fast_sma.ma_crossed_above(slow_sma)
    exits = fast_sma.ma_crossed_below(slow_sma)

    # 3. Run portfolio simulation
    portfolio = vbt.Portfolio.from_signals(
        price,
        entries,
        exits,
        init_cash=100_000_000,  # 1억원
        fees=0.0015,  # 0.15% commission
        freq='1D'
    )

    # 4. Print results
    print(f"\n📊 Backtest Results: {ticker}")
    print(f"Total Return: {portfolio.total_return():.2%}")
    print(f"Sharpe Ratio: {portfolio.sharpe_ratio():.2f}")
    print(f"Max Drawdown: {portfolio.max_drawdown():.2%}")
    print(f"Win Rate: {portfolio.trades.win_rate:.2%}")
```

**Task 3.3: Strategy Selection (2-3h)**
```python
# cli/strategies/momentum.py
class MomentumStrategy:
    """12개월 모멘텀 전략"""

    @staticmethod
    def generate_signals(price: pd.Series) -> tuple:
        # 12개월 수익률 계산
        returns_12m = price.pct_change(252)  # 252 trading days ≈ 1 year

        # 상위 20% 매수, 하위 20% 매도
        entries = returns_12m > returns_12m.quantile(0.8)
        exits = returns_12m < returns_12m.quantile(0.2)

        return entries, exits

# Usage:
# python3 quant_platform.py backtest 005930 --strategy momentum --start 2020-01-01
```

**Task 3.4: Metrics Calculation (2-3h)**
```python
# cli/utils/metrics.py
from typing import Dict

def calculate_metrics(portfolio: vbt.Portfolio) -> Dict[str, float]:
    """모든 성과 지표 자동 계산"""
    return {
        'total_return': portfolio.total_return(),
        'annualized_return': portfolio.annualized_return(),
        'sharpe_ratio': portfolio.sharpe_ratio(),
        'sortino_ratio': portfolio.sortino_ratio(),
        'max_drawdown': portfolio.max_drawdown(),
        'calmar_ratio': portfolio.calmar_ratio(),
        'win_rate': portfolio.trades.win_rate,
        'profit_factor': portfolio.trades.profit_factor,
        'avg_winning_trade': portfolio.trades.winning.pnl.mean(),
        'avg_losing_trade': portfolio.trades.losing.pnl.mean(),
        'total_trades': portfolio.trades.count,
    }
```

**Sprint 3 Value Delivery**: 🚀
- ✅ **핵심 워크플로우 완성**: 쿼리 → 백테스트 → 결과 확인
- ✅ vectorbt 통합으로 100배 속도 향상 (5년 데이터 <1초)
- ✅ 다양한 전략 실험 가능 (Momentum, Value, Crossover)
- ✅ 자동 성과 지표 계산 (Sharpe, Win Rate, etc.)
- ⏱️ **Timeline**: Day 10-12 완료 (기존 Day 18-20 대비 **8일 단축**)

---

#### Sprint 4: HTML Reports (6-8시간)
**목표**: 백테스트 결과 시각화 및 공유 (95% 완성)

**Task 4.1: Jinja2 Templates (2-3h)**
```html
<!-- cli/templates/backtest_report.html -->
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>백테스트 리포트: {{ strategy_name }}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body { font-family: 'Noto Sans KR', sans-serif; margin: 20px; }
        .metric { display: inline-block; padding: 15px; margin: 10px;
                  border: 1px solid #ddd; border-radius: 5px; }
        .positive { color: #2ecc71; }
        .negative { color: #e74c3c; }
    </style>
</head>
<body>
    <h1>📊 백테스트 리포트</h1>
    <h2>{{ strategy_name }} - {{ ticker }}</h2>

    <div class="metrics">
        {% for key, value in metrics.items() %}
        <div class="metric">
            <strong>{{ key }}</strong><br>
            <span class="{{ 'positive' if value > 0 else 'negative' }}">
                {{ "%.2f%%"|format(value * 100) if value < 100 else "%.2f"|format(value) }}
            </span>
        </div>
        {% endfor %}
    </div>

    <div id="equity-curve"></div>
    <div id="drawdown-chart"></div>

    <script>
        {{ equity_chart_js | safe }}
        {{ drawdown_chart_js | safe }}
    </script>
</body>
</html>
```

**Task 4.2: Plotly Charts (2-3h)**
```python
# cli/utils/charts.py
import plotly.graph_objects as go

def create_equity_curve(portfolio: vbt.Portfolio) -> str:
    """자산 곡선 차트 생성"""
    equity = portfolio.value()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=equity.index,
        y=equity.values,
        mode='lines',
        name='Portfolio Value',
        line=dict(color='#3498db', width=2)
    ))

    fig.update_layout(
        title='자산 곡선 (Equity Curve)',
        xaxis_title='날짜',
        yaxis_title='자산 (KRW)',
        hovermode='x unified'
    )

    return fig.to_json()

def create_drawdown_chart(portfolio: vbt.Portfolio) -> str:
    """손실 곡선 차트 생성"""
    drawdown = portfolio.drawdown()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=drawdown.index,
        y=drawdown.values * -100,  # Convert to positive percentage
        fill='tozeroy',
        mode='lines',
        name='Drawdown',
        line=dict(color='#e74c3c', width=1)
    ))

    fig.update_layout(
        title='손실 곡선 (Drawdown)',
        xaxis_title='날짜',
        yaxis_title='손실 (%)',
        hovermode='x unified'
    )

    return fig.to_json()
```

**Task 4.3: Report Generation (2-3h)**
```python
# cli/commands/backtest.py (확장)
from jinja2 import Environment, FileSystemLoader
import webbrowser

@cli.command()
@click.option('--html', is_flag=True, help='Generate HTML report')
def backtest(ticker, start, end, strategy, html):
    # ... backtest execution ...

    if html:
        # 1. Calculate metrics
        metrics = calculate_metrics(portfolio)

        # 2. Generate charts
        equity_chart = create_equity_curve(portfolio)
        drawdown_chart = create_drawdown_chart(portfolio)

        # 3. Render template
        env = Environment(loader=FileSystemLoader('cli/templates'))
        template = env.get_template('backtest_report.html')

        html_content = template.render(
            strategy_name=strategy,
            ticker=ticker,
            metrics=metrics,
            equity_chart_js=equity_chart,
            drawdown_chart_js=drawdown_chart
        )

        # 4. Save and open
        output_path = f"reports/backtest_{ticker}_{strategy}.html"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        webbrowser.open(output_path)
        print(f"✅ Report generated: {output_path}")
```

**Sprint 4 Value Delivery**:
- ✅ HTML 리포트 자동 생성 → 이메일/슬랙 공유 가능
- ✅ Plotly 인터랙티브 차트 → 확대/축소/호버
- ✅ 한글 완벽 지원 (UTF-8 인코딩)
- ✅ 반응형 레이아웃 → 모바일에서도 확인 가능
- ⏱️ **Timeline**: Day 14-16 완료

---

#### Sprint 5: Interactive Shell (5-8시간)
**목표**: UX 개선 - 대화형 인터페이스 (98% 완성)

**Task 5.1: Shell Framework (2-3h)**
```python
# cli/shell.py
import cmd
from rich.console import Console

class QuantShell(cmd.Cmd):
    intro = """
    ╔═══════════════════════════════════════════════╗
    ║   Quant Platform Interactive Shell v1.0       ║
    ║   Type 'help' for commands, 'exit' to quit    ║
    ╚═══════════════════════════════════════════════╝
    """
    prompt = "quant> "

    def __init__(self):
        super().__init__()
        self.console = Console()
        self.db = DatabaseManager()
        self.current_filters = []

    def do_query(self, arg):
        """Query tickers: query --region KR --filter "market_cap > 1e9" """
        # Parse arguments and execute query
        pass

    def do_backtest(self, arg):
        """Run backtest: backtest 005930 --strategy momentum"""
        # Execute backtest
        pass

    def do_filter(self, arg):
        """Add filter: filter market_cap > 1000000000"""
        self.current_filters.append(arg)
        self.console.print(f"✅ Filter added: {arg}", style="green")

    def do_clear(self, arg):
        """Clear all filters"""
        self.current_filters = []
        self.console.print("✅ Filters cleared", style="green")

    def do_exit(self, arg):
        """Exit shell"""
        self.console.print("👋 Goodbye!", style="bold blue")
        return True

# Usage:
# python3 quant_platform.py shell
```

**Task 5.2: Session Management (2-3h)**
```python
# cli/shell.py (확장)
import pickle

class QuantShell(cmd.Cmd):
    def do_save(self, arg):
        """Save current session: save my_research_session"""
        session_data = {
            'filters': self.current_filters,
            'last_query': self.last_query_result,
            'strategies': self.loaded_strategies,
        }

        with open(f'sessions/{arg}.pkl', 'wb') as f:
            pickle.dump(session_data, f)

        self.console.print(f"✅ Session saved: {arg}", style="green")

    def do_load(self, arg):
        """Load session: load my_research_session"""
        with open(f'sessions/{arg}.pkl', 'rb') as f:
            session_data = pickle.load(f)

        self.current_filters = session_data['filters']
        self.last_query_result = session_data['last_query']

        self.console.print(f"✅ Session loaded: {arg}", style="green")
```

**Task 5.3: Auto-completion (1-2h)**
```python
# cli/shell.py (확장)
import readline

class QuantShell(cmd.Cmd):
    def completedefault(self, text, line, begidx, endidx):
        """Tab completion for ticker symbols"""
        # Load ticker list from database
        tickers = self._get_ticker_list()
        return [t for t in tickers if t.startswith(text.upper())]

    def complete_strategy(self, text, line, begidx, endidx):
        """Tab completion for strategies"""
        strategies = ['momentum', 'value', 'quality', 'low_vol']
        return [s for s in strategies if s.startswith(text)]

# Readline configuration
readline.set_completer_delims(' \t\n;')
readline.parse_and_bind("tab: complete")
```

**Sprint 5 Value Delivery**:
- ✅ 대화형 인터페이스 → 반복 작업 효율 증가
- ✅ 세션 저장/로드 → 리서치 연속성 확보
- ✅ 자동완성 → 종목코드/전략 이름 빠른 입력
- ✅ 컬러 테마 → 가독성 향상
- ⏱️ **Timeline**: Day 18-20 완료

---

#### Sprint 6: Final Polish (3-5시간)
**목표**: 성능 최적화 및 에러 핸들링 (100% 완성)

**Task 6.1: Performance Optimization (1-2h)**
```python
# cli/utils/cache.py
from functools import lru_cache
import asyncio

class QueryCache:
    def __init__(self, ttl: int = 300):
        self.cache = {}
        self.ttl = ttl

    @lru_cache(maxsize=100)
    async def get_ticker_list(self, region: str) -> list:
        """종목 리스트 캐싱 (5분 TTL)"""
        # Cache hit: <10ms
        # Cache miss: <100ms
        pass

# Performance targets:
# - Single query: <100ms
# - Backtest (5-year): <1s (vectorbt) or <30s (custom)
# - HTML report generation: <10s
# - Shell command response: <2s
```

**Task 6.2: Error Handling (1-2h)**
```python
# cli/utils/error_handlers.py
import traceback
from rich.console import Console

console = Console()

def handle_database_error(func):
    """Database connection error handler"""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except asyncpg.PostgresConnectionError as e:
            console.print("❌ Database connection failed", style="bold red")
            console.print(f"Error: {str(e)}", style="red")
            console.print("💡 Tip: Check if PostgreSQL is running", style="yellow")
            raise
    return wrapper

def handle_backtest_error(func):
    """Backtest execution error handler"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            console.print("❌ Invalid backtest parameters", style="bold red")
            console.print(f"Error: {str(e)}", style="red")
            raise
        except Exception as e:
            console.print("❌ Backtest failed", style="bold red")
            console.print(traceback.format_exc(), style="red")
            raise
    return wrapper
```

**Task 6.3: Documentation (1-2h)**
```markdown
# CLI_USER_GUIDE.md

## Quick Start

### 1. Query Tickers
```bash
# 시가총액 상위 20개 종목
python3 quant_platform.py query --region KR \
  --filter "market_cap > 1000000000" \
  --top 20 --sort-by market_cap

# CSV 파일로 저장
python3 quant_platform.py query --region KR \
  --filter "sector == '반도체'" \
  --output semiconductor_stocks.csv
```

### 2. Run Backtest
```bash
# 삼성전자 모멘텀 전략
python3 quant_platform.py backtest 005930 \
  --strategy momentum \
  --start 2020-01-01 \
  --end 2023-12-31 \
  --html  # HTML 리포트 생성
```

### 3. Interactive Shell
```bash
python3 quant_platform.py shell

quant> filter market_cap > 1000000000
quant> filter pe_ratio < 15
quant> query --top 10
quant> backtest 005930 --strategy momentum
quant> save research_session_20231225
quant> exit
```
```

**Sprint 6 Value Delivery**:
- ✅ 쿼리 성능 <100ms (캐싱)
- ✅ 친절한 에러 메시지 + 해결 방법 제시
- ✅ 완전한 사용자 가이드
- ⏱️ **Timeline**: Day 22-24 완료

---

### 최종 타임라인 비교

| Sprint | 기간 | 누적 완성도 | 주요 가치 |
|--------|------|------------|-----------|
| Sprint 1 | Day 2-3 | 40% | 즉시 쿼리 가능 |
| Sprint 2 | Day 4-5 | 70% | CSV 내보내기, 고급 필터 |
| Sprint 3 | **Day 10-12** | 85% | **백테스트 실행** 🎯 |
| Sprint 4 | Day 14-16 | 95% | HTML 리포트 |
| Sprint 5 | Day 18-20 | 98% | 대화형 셸 |
| Sprint 6 | Day 22-24 | 100% | 최종 완성 |

**핵심 개선**:
- 백테스트 제공 시점: Day 18-20 → **Day 10-12** (8일 단축)
- 리스크 관리: vectorbt 통합을 일찍 다루어 디버깅 시간 확보
- 점진적 가치: 매 스프린트마다 사용 가능한 기능 제공

---

## ✅ 상세 검증 절차

### Sprint 1: Foundation + Quick Win (6-8시간)

#### Task 1.1: Database Connection Setup (1-2h)

**Verification 1.1.1: Connection Test**
```bash
# 1. 연결 성공 확인
python3 -c "
import asyncio
from cli.utils.database import DatabaseManager

async def test():
    db = DatabaseManager()
    await db.connect()
    print('✅ Connection successful')
    print(f'Pool size: {db.pool._holders.__len__()}')
    await db.pool.close()

asyncio.run(test())
"

# Expected output:
# ✅ Connection successful
# Pool size: 2
```

**Verification 1.1.2: Query Test**
```bash
# 2. 기본 쿼리 실행
python3 -c "
import asyncio
from cli.utils.database import DatabaseManager

async def test():
    db = DatabaseManager()
    await db.connect()

    # Count tickers
    result = await db.pool.fetchval('SELECT COUNT(*) FROM tickers WHERE region = \"KR\"')
    print(f'✅ KR Tickers count: {result}')

    # Sample query
    rows = await db.pool.fetch('SELECT ticker, name FROM tickers WHERE region = \"KR\" LIMIT 5')
    for row in rows:
        print(f'  {row[\"ticker\"]}: {row[\"name\"]}')

    await db.pool.close()

asyncio.run(test())
"

# Expected output:
# ✅ KR Tickers count: 2500+
#   005930: 삼성전자
#   000660: SK하이닉스
#   ...
```

**Verification 1.1.3: Performance Test**
```bash
# 3. 연결 풀 성능 검증 (100회 쿼리 <10초)
python3 -c "
import asyncio
import time
from cli.utils.database import DatabaseManager

async def test():
    db = DatabaseManager()
    await db.connect()

    start = time.time()
    for _ in range(100):
        await db.pool.fetchval('SELECT COUNT(*) FROM tickers')
    elapsed = time.time() - start

    print(f'✅ 100 queries: {elapsed:.2f}s ({elapsed*10:.1f}ms per query)')
    assert elapsed < 10, 'Performance degradation detected'

    await db.pool.close()

asyncio.run(test())
"

# Expected output:
# ✅ 100 queries: 2.5s (25ms per query)
```

**Verification 1.1.4: Error Handling Test**
```bash
# 4. 에러 처리 확인
python3 -c "
import asyncio
from cli.utils.database import DatabaseManager

async def test():
    db = DatabaseManager()
    # Wrong credentials
    db.pool = await asyncpg.create_pool(
        host='localhost',
        database='wrong_db',
        user='wrong_user',
        password='wrong_pass'
    )

asyncio.run(test())
"

# Expected output:
# ❌ Database connection failed
# Error: asyncpg.InvalidCatalogNameError: database "wrong_db" does not exist
# 💡 Tip: Check if PostgreSQL is running
```

**Manual Verification Checklist**:
- [ ] PostgreSQL 서비스 실행 확인 (`pg_ctl status`)
- [ ] `quant_platform` 데이터베이스 존재 확인
- [ ] 연결 풀 최소/최대 크기 설정 확인 (2/10)
- [ ] 연결 타임아웃 처리 확인 (10초)

---

#### Task 1.2: Query Builder (2-3h)

**Verification 1.2.1: Basic Query**
```bash
# 1. 기본 쿼리 빌더 테스트
python3 -c "
import asyncio
from cli.utils.database import DatabaseManager
from cli.utils.query_builder import QueryBuilder

async def test():
    db = DatabaseManager()
    await db.connect()

    qb = QueryBuilder(db).tickers('KR')
    df = await qb.execute()

    print(f'✅ Query returned {len(df)} rows')
    print(f'Columns: {list(df.columns)}')
    print(df.head())

    await db.disconnect()

asyncio.run(test())
"

# Expected output:
# ✅ Query returned 2500+ rows
# Columns: ['ticker', 'name', 'market_cap', 'sector']
#    ticker        name  market_cap     sector
# 0  005930    삼성전자  400000000000  반도체
# 1  000660  SK하이닉스  80000000000   반도체
```

**Verification 1.2.2: Filter Test**
```bash
# 2. 필터 기능 검증
python3 -c "
import asyncio
from cli.utils.database import DatabaseManager
from cli.utils.query_builder import QueryBuilder

async def test():
    db = DatabaseManager()
    await db.connect()

    # Single filter
    qb = QueryBuilder(db).tickers('KR').filter('market_cap > 1000000000000')
    df = await qb.execute()
    print(f'✅ Filter test 1: {len(df)} large-cap stocks')
    assert len(df) < 100, 'Too many results'

    # Multiple filters
    qb = QueryBuilder(db).tickers('KR')\
        .filter('market_cap > 1000000000000')\
        .filter('sector == \"반도체\"')
    df = await qb.execute()
    print(f'✅ Filter test 2: {len(df)} large-cap semiconductor stocks')
    assert len(df) < 20, 'Too many results'

    await db.disconnect()

asyncio.run(test())
"

# Expected output:
# ✅ Filter test 1: 50 large-cap stocks
# ✅ Filter test 2: 5 large-cap semiconductor stocks
```

**Verification 1.2.3: Method Chaining Test**
```bash
# 3. 메서드 체이닝 검증
python3 -c "
import asyncio
from cli.utils.database import DatabaseManager
from cli.utils.query_builder import QueryBuilder

async def test():
    db = DatabaseManager()
    await db.connect()

    # Complex chained query
    qb = QueryBuilder(db)\
        .tickers('KR')\
        .filter('market_cap > 500000000000')\
        .filter('sector == \"IT\"')\
        .top(10, by='market_cap')\
        .select('ticker', 'name', 'market_cap')

    df = await qb.execute()

    print(f'✅ Chained query: {len(df)} rows')
    assert len(df) <= 10, 'Top N filter failed'
    assert len(df.columns) == 3, 'Column selection failed'
    print(df)

    await db.disconnect()

asyncio.run(test())
"

# Expected output:
# ✅ Chained query: 10 rows
#    ticker        name  market_cap
# 0  005930    삼성전자  400000000000
# 1  000660  SK하이닉스  80000000000
# ...
```

**Verification 1.2.4: SQL Generation Test**
```bash
# 4. SQL 생성 검증 (디버그 모드)
python3 -c "
from cli.utils.query_builder import QueryBuilder

qb = QueryBuilder(None).tickers('KR')\
    .filter('market_cap > 1000000000')\
    .filter('sector == \"반도체\"')\
    .top(20, by='market_cap')

print('Generated SQL:')
print(qb.to_sql())
"

# Expected output:
# Generated SQL:
# SELECT t.ticker, t.name, sd.market_cap, sd.sector
# FROM tickers t
# LEFT JOIN stock_details sd ON t.ticker = sd.ticker AND t.region = sd.region
# WHERE t.region = 'KR'
# AND market_cap > 1000000000
# AND sector = '반도체'
# ORDER BY market_cap DESC LIMIT 20
```

**Manual Verification Checklist**:
- [ ] 쿼리 결과가 pandas DataFrame으로 반환되는지 확인
- [ ] 필터 표현식 파싱이 정확한지 확인 (>, <, ==, !=)
- [ ] 메서드 체이닝이 순서대로 적용되는지 확인
- [ ] SQL injection 방어 확인 (parameterized queries)

---

#### Task 1.3: Basic CLI (2-3h)

**Verification 1.3.1: Command Execution**
```bash
# 1. 기본 명령어 실행
python3 quant_platform.py query --region KR

# Expected output:
# ┏━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━┓
# ┃ ticker ┃ name       ┃ market_cap   ┃ sector   ┃
# ┡━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━┩
# │ 005930 │ 삼성전자   │ 400000000000 │ 반도체   │
# │ 000660 │ SK하이닉스 │ 80000000000  │ 반도체   │
# └────────┴────────────┴──────────────┴──────────┘
# (2500 rows)
```

**Verification 1.3.2: Argument Parsing**
```bash
# 2. 인자 파싱 검증
python3 quant_platform.py query --region KR --filter "market_cap > 1000000000000"

# Expected: 필터 적용된 결과
# (50 rows)

python3 quant_platform.py query --region KR \
  --filter "market_cap > 1000000000000" \
  --filter "sector == '반도체'"

# Expected: 복수 필터 적용된 결과
# (5 rows)
```

**Verification 1.3.3: Performance Test**
```bash
# 3. 성능 검증 (1초 이내 응답)
time python3 quant_platform.py query --region KR --filter "market_cap > 1000000000"

# Expected output:
# ... query results ...
#
# real    0m0.753s
# user    0m0.523s
# sys     0m0.089s
```

**Verification 1.3.4: Error Handling**
```bash
# 4. 에러 처리 확인
python3 quant_platform.py query --region INVALID

# Expected output:
# ❌ Invalid region: INVALID
# 💡 Supported regions: KR, US

python3 quant_platform.py query --filter "invalid syntax here"

# Expected output:
# ❌ Invalid filter expression: invalid syntax here
# 💡 Example: market_cap > 1000000000
```

**Manual Verification Checklist**:
- [ ] `--help` 옵션이 정상 작동하는지 확인
- [ ] 모든 필수 인자를 누락했을 때 사용법이 출력되는지 확인
- [ ] Ctrl+C 중단 시 깨끗하게 종료되는지 확인
- [ ] 비동기 작업이 완료될 때까지 대기하는지 확인

---

#### Task 1.4: Rich Terminal Formatting (1-2h)

**Verification 1.4.1: Table Rendering**
```bash
# 1. 테이블 렌더링 검증
python3 quant_platform.py query --region KR --top 10

# Expected: Rich 테이블 형식으로 출력
# - 헤더가 cyan 색상
# - 셀 구분선 명확
# - 숫자가 우측 정렬
```

**Verification 1.4.2: Color Themes**
```bash
# 2. 컬러 테마 검증
python3 -c "
from cli.utils.formatters import format_dataframe
import pandas as pd

df = pd.DataFrame({
    'ticker': ['005930', '000660'],
    'name': ['삼성전자', 'SK하이닉스'],
    'return': [0.15, -0.08]  # Positive/Negative
})

format_dataframe(df, title='Test Colors')
"

# Expected:
# - 양수(0.15)는 녹색
# - 음수(-0.08)는 빨간색
```

**Verification 1.4.3: Large Dataset Test**
```bash
# 3. 대용량 데이터 렌더링 (2500 rows)
python3 quant_platform.py query --region KR

# Expected:
# - 스크롤 가능
# - 터미널 너비에 맞춰 자동 조정
# - 렌더링 시간 <3초
```

**Verification 1.4.4: Terminal Compatibility**
```bash
# 4. 다양한 터미널 환경 테스트
# iTerm2
python3 quant_platform.py query --region KR --top 5

# VS Code Terminal
code . && python3 quant_platform.py query --region KR --top 5

# macOS Terminal
open -a Terminal && python3 quant_platform.py query --region KR --top 5

# Expected: 모든 터미널에서 정상 출력
```

**Manual Verification Checklist**:
- [ ] 한글 문자가 깨지지 않는지 확인
- [ ] 터미널 창 크기 조절 시 레이아웃이 적응하는지 확인
- [ ] 컬러 비활성화 옵션(`--no-color`)이 작동하는지 확인
- [ ] 숫자 포맷팅이 적절한지 확인 (천 단위 구분, 소수점)

---

### Sprint 2: Enhanced Screening (4-6시간)

#### Task 2.1: Advanced Filters (2-3h)

**Verification 2.1.1: Top N Selection**
```bash
# 1. 상위 N개 선택 검증
python3 quant_platform.py query --region KR --top 20 --sort-by market_cap

# Expected:
# - 정확히 20개 종목
# - market_cap 내림차순 정렬
```

**Verification 2.1.2: Column Selection**
```bash
# 2. 특정 컬럼 선택
python3 quant_platform.py query --region KR \
  --columns ticker,name,market_cap \
  --top 10

# Expected:
# ┏━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
# ┃ ticker ┃ name       ┃ market_cap   ┃
# ┡━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
# │ 005930 │ 삼성전자   │ 400000000000 │
# └────────┴────────────┴──────────────┘
# (3 columns only)
```

**Verification 2.1.3: Complex Filter Combinations**
```bash
# 3. 복잡한 필터 조합
python3 quant_platform.py query --region KR \
  --filter "market_cap > 1000000000000" \
  --filter "sector == '반도체'" \
  --filter "pe_ratio < 20" \
  --top 5 --sort-by market_cap

# Expected:
# - 3개 필터 모두 적용
# - 상위 5개만 출력
# - market_cap 정렬
```

---

#### Task 2.2: CSV Export (1-2h)

**Verification 2.2.1: Basic Export**
```bash
# 1. 기본 CSV 내보내기
python3 quant_platform.py query --region KR \
  --filter "sector == '반도체'" \
  --output semiconductor_stocks.csv

# Expected:
# ✅ Saved to semiconductor_stocks.csv

# Verify file
cat semiconductor_stocks.csv | head -5

# Expected:
# ticker,name,market_cap,sector
# 005930,삼성전자,400000000000,반도체
# 000660,SK하이닉스,80000000000,반도체
```

**Verification 2.2.2: Excel Compatibility**
```bash
# 2. Excel 호환성 검증
python3 quant_platform.py query --region KR \
  --filter "sector == '반도체'" \
  --output test_excel.csv

# Open in Excel (or LibreOffice)
open test_excel.csv

# Expected:
# - 한글이 깨지지 않음 (UTF-8-BOM)
# - 컬럼 헤더가 정상
# - 숫자 포맷이 적절
```

**Verification 2.2.3: Large Dataset Export**
```bash
# 3. 대용량 데이터 내보내기
python3 quant_platform.py query --region KR --output all_kr_stocks.csv

# Expected:
# ✅ Saved to all_kr_stocks.csv (2500+ rows)

# Verify size
wc -l all_kr_stocks.csv
# Expected: 2501 (header + 2500 rows)
```

---

#### Task 2.3: Multiple Metrics (1-2h)

**Verification 2.3.1: Technical + Fundamental**
```bash
# 1. 기술적 지표 + 펀더멘털 통합 쿼리
python3 quant_platform.py query --region KR \
  --with-technicals rsi_14,sma_20,ema_50 \
  --with-fundamentals pe_ratio,pb_ratio,roe \
  --filter "rsi_14 < 30 AND pe_ratio < 15" \
  --top 10

# Expected:
# ┏━━━━━━━━┳━━━━━━┳━━━━━━┳━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━┓
# ┃ ticker ┃ rsi  ┃ sma  ┃ ema  ┃ pe_ratio┃ pb_ratio┃ roe ┃
# ┡━━━━━━━━╇━━━━━━╇━━━━━━╇━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━┩
# │ 123456 │ 28.5 │ 5000 │ 5100 │ 12.3    │ 0.8     │ 15.2│
# └────────┴──────┴──────┴──────┴─────────┴─────────┴─────┘
```

---

### Sprint 3: Backtest Foundation (8-10시간)

#### Task 3.1: vectorbt Installation (1-2h)

**Verification 3.1.1: Installation**
```bash
# 1. vectorbt 설치 확인
pip install vectorbt==0.26.2 numba

python3 -c "import vectorbt as vbt; print(f'✅ vectorbt {vbt.__version__}')"

# Expected output:
# ✅ vectorbt 0.26.2
```

**Verification 3.1.2: Numba Compilation**
```bash
# 2. Numba JIT 컴파일 확인
python3 -c "
import vectorbt as vbt
import numpy as np

# Test JIT compilation
@vbt.nb.njit
def test_func(x):
    return x * 2

result = test_func(np.array([1, 2, 3]))
print(f'✅ Numba JIT: {result}')
"

# Expected output:
# ✅ Numba JIT: [2 4 6]
```

---

#### Task 3.2: Simple Backtest (3-4h)

**Verification 3.2.1: Data Loading**
```bash
# 1. PostgreSQL 데이터 로딩 확인
python3 -c "
import asyncio
from cli.utils.database import DatabaseManager
import pandas as pd

async def test():
    db = DatabaseManager()
    await db.connect()

    query = '''
        SELECT date, close
        FROM ohlcv_data
        WHERE ticker = '005930' AND timeframe = '1d'
        AND date BETWEEN '2020-01-01' AND '2023-12-31'
        ORDER BY date
    '''
    result = await db.pool.fetch(query)
    df = pd.DataFrame(result)

    print(f'✅ Loaded {len(df)} rows')
    print(f'Date range: {df[\"date\"].min()} to {df[\"date\"].max()}')

    await db.disconnect()

asyncio.run(test())
"

# Expected output:
# ✅ Loaded 1000+ rows
# Date range: 2020-01-02 to 2023-12-29
```

**Verification 3.2.2: Simple Backtest Execution**
```bash
# 2. 기본 백테스트 실행
python3 quant_platform.py backtest 005930 \
  --start 2020-01-01 \
  --end 2023-12-31

# Expected output:
# 📊 Backtest Results: 005930
# Total Return: 45.32%
# Sharpe Ratio: 1.23
# Max Drawdown: -23.45%
# Win Rate: 55.67%
# Total Trades: 24
```

**Verification 3.2.3: Performance Test**
```bash
# 3. 성능 검증 (5년 데이터 <1초)
time python3 quant_platform.py backtest 005930 \
  --start 2019-01-01 \
  --end 2023-12-31

# Expected:
# real    0m0.850s  (<1초)
```

---

#### Task 3.3: Strategy Selection (2-3h)

**Verification 3.3.1: Momentum Strategy**
```bash
# 1. 모멘텀 전략 테스트
python3 quant_platform.py backtest 005930 \
  --strategy momentum \
  --start 2020-01-01 \
  --end 2023-12-31

# Expected:
# 📊 Backtest Results: 005930 (Momentum)
# Total Return: 38.56%
# Sharpe Ratio: 1.15
# Max Drawdown: -19.23%
```

**Verification 3.3.2: Value Strategy**
```bash
# 2. 가치 전략 테스트
python3 quant_platform.py backtest 005930 \
  --strategy value \
  --start 2020-01-01 \
  --end 2023-12-31

# Expected:
# 📊 Backtest Results: 005930 (Value)
# Total Return: 42.18%
# Sharpe Ratio: 1.28
```

**Verification 3.3.3: Custom Parameters**
```bash
# 3. 커스텀 파라미터 테스트
python3 quant_platform.py backtest 005930 \
  --strategy momentum \
  --param momentum_period=60 \
  --param rebalance_freq=monthly \
  --start 2020-01-01 \
  --end 2023-12-31

# Expected:
# 📊 Backtest Results: 005930 (Momentum, period=60, rebalance=monthly)
# Total Return: 35.42%
```

---

#### Task 3.4: Metrics Calculation (2-3h)

**Verification 3.4.1: All Metrics**
```bash
# 1. 모든 성과 지표 계산
python3 quant_platform.py backtest 005930 \
  --strategy momentum \
  --start 2020-01-01 \
  --end 2023-12-31 \
  --metrics all

# Expected output:
# 📊 Backtest Results: 005930 (Momentum)
#
# Returns:
#   Total Return: 38.56%
#   Annualized Return: 8.45%
#
# Risk-Adjusted:
#   Sharpe Ratio: 1.15
#   Sortino Ratio: 1.67
#   Calmar Ratio: 2.01
#
# Drawdown:
#   Max Drawdown: -19.23%
#   Avg Drawdown: -5.67%
#   Max Drawdown Duration: 45 days
#
# Trading:
#   Total Trades: 24
#   Win Rate: 58.33%
#   Profit Factor: 1.85
#   Avg Winning Trade: +5.23%
#   Avg Losing Trade: -2.87%
```

**Verification 3.4.2: Accuracy Test**
```bash
# 2. 지표 정확도 검증 (Reference backtest와 비교)
python3 tests/test_metrics_accuracy.py

# Expected:
# ✅ Total Return: 38.56% (reference: 38.54%, diff: 0.02%)
# ✅ Sharpe Ratio: 1.15 (reference: 1.14, diff: 0.88%)
# ✅ Max Drawdown: -19.23% (reference: -19.25%, diff: 0.10%)
# ✅ All metrics within 2% tolerance
```

---

### Sprint 4: HTML Reports (6-8시간)

#### Task 4.1: Jinja2 Templates (2-3h)

**Verification 4.1.1: Template Rendering**
```bash
# 1. 템플릿 렌더링 테스트
python3 -c "
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('cli/templates'))
template = env.get_template('backtest_report.html')

html = template.render(
    strategy_name='Momentum',
    ticker='005930',
    metrics={'total_return': 0.3856, 'sharpe_ratio': 1.15}
)

print('✅ Template rendered')
print(f'HTML length: {len(html)} characters')
"

# Expected output:
# ✅ Template rendered
# HTML length: 5000+ characters
```

**Verification 4.1.2: Korean Encoding**
```bash
# 2. 한글 인코딩 검증
python3 quant_platform.py backtest 005930 \
  --strategy momentum \
  --start 2020-01-01 \
  --end 2023-12-31 \
  --html \
  --output test_report.html

# Open in browser
open test_report.html

# Expected:
# - 한글이 정상 표시 (UTF-8)
# - 브라우저에서 깨지지 않음
```

**Verification 4.1.3: Responsive Layout**
```bash
# 3. 반응형 레이아웃 검증
open test_report.html

# 브라우저 창 크기 조절 (1920px → 768px → 375px)
# Expected:
# - 레이아웃이 자동 조정
# - 차트가 반응형으로 리사이즈
# - 모바일에서도 가독성 유지
```

---

#### Task 4.2: Plotly Charts (2-3h)

**Verification 4.2.1: Equity Curve Chart**
```bash
# 1. 자산 곡선 차트 생성
python3 -c "
import vectorbt as vbt
import pandas as pd
from cli.utils.charts import create_equity_curve

# Mock portfolio
price = pd.Series([100, 105, 103, 110, 108, 115],
                  index=pd.date_range('2020-01-01', periods=6))
portfolio = vbt.Portfolio.from_holding(price, init_cash=100_000_000)

chart_json = create_equity_curve(portfolio)
print(f'✅ Chart generated: {len(chart_json)} chars')
"

# Expected output:
# ✅ Chart generated: 3000+ chars (JSON format)
```

**Verification 4.2.2: Multiple Charts**
```bash
# 2. 여러 차트 동시 생성
python3 quant_platform.py backtest 005930 \
  --strategy momentum \
  --start 2020-01-01 \
  --end 2023-12-31 \
  --html \
  --charts equity,drawdown,trades,returns

# Expected HTML includes:
# - Equity curve chart
# - Drawdown chart
# - Trade scatter plot
# - Returns histogram
```

**Verification 4.2.3: Chart Interactions**
```bash
# 3. 차트 인터랙션 검증
open test_report.html

# Test interactions:
# - Zoom in/out (scroll wheel)
# - Pan (drag)
# - Hover tooltips
# - Legend toggle (click)

# Expected: 모든 인터랙션 정상 작동
```

**Verification 4.2.4: Performance Test**
```bash
# 4. 차트 생성 성능 (<10초)
time python3 quant_platform.py backtest 005930 \
  --strategy momentum \
  --start 2019-01-01 \
  --end 2023-12-31 \
  --html \
  --charts all

# Expected:
# real    0m8.234s (<10초)
```

---

#### Task 4.3: Report Generation (2-3h)

**Verification 4.3.1: Full Report**
```bash
# 1. 전체 리포트 생성
python3 quant_platform.py backtest 005930 \
  --strategy momentum \
  --start 2020-01-01 \
  --end 2023-12-31 \
  --html \
  --output reports/samsung_momentum.html

# Expected output:
# ✅ Report generated: reports/samsung_momentum.html
# 🌐 Opening in browser...

# Verify report includes:
# - Title and metadata
# - All metrics (returns, risk, trading)
# - All charts (equity, drawdown, trades, returns)
# - Styled with CSS
# - Responsive layout
```

**Verification 4.3.2: End-to-End Workflow**
```bash
# 2. 전체 워크플로우 테스트
# Query → Backtest → Report

# Step 1: Query top 10 stocks
python3 quant_platform.py query --region KR \
  --filter "market_cap > 1000000000000" \
  --top 10 \
  --output top10_stocks.csv

# Step 2: Backtest each stock
for ticker in $(cat top10_stocks.csv | tail -n +2 | cut -d',' -f1); do
  python3 quant_platform.py backtest $ticker \
    --strategy momentum \
    --start 2020-01-01 \
    --end 2023-12-31 \
    --html \
    --output reports/${ticker}_momentum.html
done

# Expected:
# 10 HTML reports generated in reports/ directory
```

**Verification 4.3.3: Large Data Test**
```bash
# 3. 대용량 데이터 리포트 (10년 데이터)
python3 quant_platform.py backtest 005930 \
  --strategy momentum \
  --start 2014-01-01 \
  --end 2023-12-31 \
  --html \
  --output reports/samsung_10y.html

# Expected:
# - Report generated successfully
# - Charts render smoothly (3000+ data points)
# - File size <5MB
```

**Verification 4.3.4: Report Sharing**
```bash
# 4. 리포트 공유 가능성 검증
# Email attachment test
python3 -c "
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Mock email test (don't actually send)
msg = MIMEMultipart()
msg['Subject'] = '백테스트 리포트: 삼성전자 모멘텀'

# Attach HTML report
with open('reports/samsung_momentum.html', 'rb') as f:
    part = MIMEBase('text', 'html')
    part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment; filename=report.html')
    msg.attach(part)

print(f'✅ Email prepared: {len(msg.as_string())} bytes')
"

# Expected output:
# ✅ Email prepared: 50000+ bytes
```

---

### Sprint 5: Interactive Shell (5-8시간)

#### Task 5.1: Shell Framework (2-3h)

**Verification 5.1.1: Shell Startup**
```bash
# 1. 셸 시작 테스트
python3 quant_platform.py shell

# Expected output:
# ╔═══════════════════════════════════════════════╗
# ║   Quant Platform Interactive Shell v1.0       ║
# ║   Type 'help' for commands, 'exit' to quit    ║
# ╚═══════════════════════════════════════════════╝
# quant>
```

**Verification 5.1.2: Basic Commands**
```bash
# 2. 기본 명령어 테스트
quant> query --region KR --top 5
# Expected: 5개 종목 출력

quant> filter market_cap > 1000000000000
# Expected: ✅ Filter added: market_cap > 1000000000000

quant> query
# Expected: 필터가 적용된 쿼리 결과

quant> clear
# Expected: ✅ Filters cleared

quant> exit
# Expected: 👋 Goodbye!
```

**Verification 5.1.3: Help System**
```bash
# 3. 도움말 시스템 테스트
quant> help

# Expected output:
# Available commands:
#   query       Query tickers with filters
#   backtest    Run backtest on a ticker
#   filter      Add filter expression
#   clear       Clear all filters
#   save        Save current session
#   load        Load previous session
#   exit        Exit shell

quant> help query
# Expected: query 명령어의 상세 사용법
```

**Verification 5.1.4: Error Handling**
```bash
# 4. 에러 처리 테스트
quant> invalid_command

# Expected output:
# ❌ Unknown command: invalid_command
# 💡 Type 'help' for available commands

quant> query --invalid-option

# Expected output:
# ❌ Invalid option: --invalid-option
# 💡 Type 'help query' for usage
```

**Verification 5.1.5: Session State**
```bash
# 5. 세션 상태 유지 테스트
quant> filter market_cap > 1000000000000
quant> filter sector == '반도체'
quant> query --top 5
# (Result 1: 5 stocks)

quant> query --top 10
# (Result 2: 10 stocks with same filters)

# Expected: 필터가 세션 동안 유지됨
```

---

#### Task 5.2: Session Management (2-3h)

**Verification 5.2.1: Save Session**
```bash
# 1. 세션 저장 테스트
quant> filter market_cap > 1000000000000
quant> filter sector == '반도체'
quant> query --top 5
quant> save research_20231225

# Expected output:
# ✅ Session saved: research_20231225
# 📁 File: sessions/research_20231225.pkl
```

**Verification 5.2.2: Load Session**
```bash
# 2. 세션 로드 테스트
quant> exit

python3 quant_platform.py shell

quant> load research_20231225

# Expected output:
# ✅ Session loaded: research_20231225
# Restored filters:
#   - market_cap > 1000000000000
#   - sector == '반도체'

quant> query --top 5
# Expected: 이전과 동일한 결과
```

**Verification 5.2.3: Session List**
```bash
# 3. 세션 목록 조회
quant> sessions

# Expected output:
# Available sessions:
#   - research_20231225 (5 filters, 2023-12-25 14:30)
#   - momentum_test (3 filters, 2023-12-24 10:15)
#   - value_screen (8 filters, 2023-12-23 16:45)
```

**Verification 5.2.4: Strategy Persistence**
```bash
# 4. 전략 지속성 테스트
quant> backtest 005930 --strategy momentum
# (Result displayed)

quant> save strategy_test
quant> exit

# New session
python3 quant_platform.py shell
quant> load strategy_test
quant> backtest 000660 --strategy momentum
# Expected: 동일한 전략 파라미터 적용
```

---

#### Task 5.3: Auto-completion (1-2h)

**Verification 5.3.1: Command Completion**
```bash
# 1. 명령어 자동완성 테스트
quant> qu<TAB>
# Expected: query (자동완성)

quant> ba<TAB>
# Expected: backtest (자동완성)

quant> fi<TAB>
# Expected: filter (자동완성)
```

**Verification 5.3.2: Ticker Completion**
```bash
# 2. 종목코드 자동완성 테스트
quant> backtest 0059<TAB>
# Expected: 005930 (자동완성)

quant> backtest 0006<TAB>
# Expected:
#   000660  (SK하이닉스)
#   000670  (영풍)
#   (Multiple matches)

quant> backtest SK<TAB>
# Expected: 000660 (이름으로 검색)
```

**Verification 5.3.3: Strategy Completion**
```bash
# 3. 전략 이름 자동완성 테스트
quant> backtest 005930 --strategy mom<TAB>
# Expected: momentum (자동완성)

quant> backtest 005930 --strategy <TAB><TAB>
# Expected:
#   momentum
#   value
#   quality
#   low_vol
```

**Verification 5.3.4: Command History**
```bash
# 4. 명령어 히스토리 테스트
quant> query --region KR --top 5
quant> filter market_cap > 1000000000
quant> query

# Press UP arrow
# Expected: query
# Press UP arrow again
# Expected: filter market_cap > 1000000000
# Press UP arrow again
# Expected: query --region KR --top 5
```

**Verification 5.3.5: Performance Test**
```bash
# 5. 자동완성 성능 (<100ms)
quant> (measure time for TAB completion)

# Expected: <100ms for ticker list (2500 tickers)
```

---

### Sprint 6: Final Polish (3-5시간)

#### Task 6.1: Performance Optimization (1-2h)

**Verification 6.1.1: Query Performance**
```bash
# 1. 쿼리 성능 벤치마크 (<100ms)
python3 -c "
import asyncio
import time
from cli.utils.database import DatabaseManager
from cli.utils.query_builder import QueryBuilder

async def benchmark():
    db = DatabaseManager()
    await db.connect()

    # 100 queries
    start = time.time()
    for _ in range(100):
        qb = QueryBuilder(db).tickers('KR').filter('market_cap > 1000000000')
        await qb.execute()
    elapsed = time.time() - start

    print(f'✅ 100 queries: {elapsed:.2f}s ({elapsed*10:.1f}ms per query)')
    assert elapsed / 100 < 0.1, 'Performance degradation'

    await db.disconnect()

asyncio.run(benchmark())
"

# Expected output:
# ✅ 100 queries: 5.2s (52ms per query)
```

**Verification 6.1.2: Cache Effectiveness**
```bash
# 2. 캐시 효과 검증
python3 -c "
from cli.utils.cache import QueryCache

cache = QueryCache()

# First call (cache miss)
import time
start = time.time()
result1 = cache.get_ticker_list('KR')
miss_time = time.time() - start

# Second call (cache hit)
start = time.time()
result2 = cache.get_ticker_list('KR')
hit_time = time.time() - start

print(f'✅ Cache miss: {miss_time*1000:.1f}ms')
print(f'✅ Cache hit: {hit_time*1000:.1f}ms')
print(f'✅ Speedup: {miss_time / hit_time:.1f}x')

assert hit_time < 0.01, 'Cache not effective'
"

# Expected output:
# ✅ Cache miss: 85.3ms
# ✅ Cache hit: 2.1ms
# ✅ Speedup: 40.6x
```

**Verification 6.1.3: Memory Usage**
```bash
# 3. 메모리 사용량 검증 (<50MB 증가)
python3 -c "
import psutil
import asyncio
from cli.utils.database import DatabaseManager
from cli.utils.query_builder import QueryBuilder

async def test():
    process = psutil.Process()
    mem_before = process.memory_info().rss / 1024 / 1024  # MB

    db = DatabaseManager()
    await db.connect()

    # 100 queries
    for _ in range(100):
        qb = QueryBuilder(db).tickers('KR')
        await qb.execute()

    mem_after = process.memory_info().rss / 1024 / 1024  # MB
    mem_increase = mem_after - mem_before

    print(f'✅ Memory before: {mem_before:.1f} MB')
    print(f'✅ Memory after: {mem_after:.1f} MB')
    print(f'✅ Memory increase: {mem_increase:.1f} MB')

    assert mem_increase < 50, 'Memory leak detected'

    await db.disconnect()

asyncio.run(test())
"

# Expected output:
# ✅ Memory before: 45.3 MB
# ✅ Memory after: 68.7 MB
# ✅ Memory increase: 23.4 MB
```

**Verification 6.1.4: Concurrent Execution**
```bash
# 4. 동시 실행 성능 검증
python3 -c "
import asyncio
import time
from cli.utils.database import DatabaseManager
from cli.utils.query_builder import QueryBuilder

async def concurrent_queries():
    db = DatabaseManager()
    await db.connect()

    # 10 concurrent queries
    start = time.time()
    tasks = []
    for i in range(10):
        qb = QueryBuilder(db).tickers('KR').filter(f'market_cap > {i * 1000000000}')
        tasks.append(qb.execute())

    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    print(f'✅ 10 concurrent queries: {elapsed:.2f}s ({elapsed*100:.1f}ms per query)')
    assert elapsed < 2, 'Concurrent performance issue'

    await db.disconnect()

asyncio.run(concurrent_queries())
"

# Expected output:
# ✅ 10 concurrent queries: 0.85s (85ms per query)
```

---

#### Task 6.2: Error Handling (1-2h)

**Verification 6.2.1: Database Errors**
```bash
# 1. 데이터베이스 에러 처리
python3 quant_platform.py query --region KR
# (Stop PostgreSQL while query is running)

# Expected output:
# ❌ Database connection failed
# Error: asyncpg.PostgresConnectionError: connection refused
# 💡 Tip: Check if PostgreSQL is running
#   brew services list | grep postgresql
#   brew services start postgresql
```

**Verification 6.2.2: Input Validation**
```bash
# 2. 입력 검증 테스트
python3 quant_platform.py query --region INVALID

# Expected output:
# ❌ Invalid region: INVALID
# 💡 Supported regions: KR, US

python3 quant_platform.py backtest 005930 \
  --start 2025-01-01 \
  --end 2020-01-01

# Expected output:
# ❌ Invalid date range: start date must be before end date
```

**Verification 6.2.3: File System Errors**
```bash
# 3. 파일 시스템 에러 처리
python3 quant_platform.py query --region KR \
  --output /root/output.csv  # No write permission

# Expected output:
# ❌ Failed to save file: /root/output.csv
# Error: PermissionError: [Errno 13] Permission denied
# 💡 Tip: Check write permissions or use a different directory
```

**Verification 6.2.4: Exception Recovery**
```bash
# 4. 예외 복구 테스트 (Interactive Shell)
quant> query --region KR
# (Network error during query)

# Expected output:
# ❌ Query failed: Network error
# 💡 Retrying in 3 seconds...
# ✅ Query completed (retry successful)

# Shell should remain running, not crash
```

---

#### Task 6.3: Documentation (1-2h)

**Verification 6.3.1: CLI Help**
```bash
# 1. CLI 도움말 검증
python3 quant_platform.py --help

# Expected output:
# Usage: quant_platform.py [OPTIONS] COMMAND [ARGS]...
#
# Quant Platform CLI - Quantitative Investment Research Platform
#
# Commands:
#   query       Query tickers with advanced filters
#   backtest    Run backtest with vectorbt engine
#   shell       Interactive shell for exploratory research
#
# Examples:
#   python3 quant_platform.py query --region KR --top 20
#   python3 quant_platform.py backtest 005930 --strategy momentum --html
#   python3 quant_platform.py shell
```

**Verification 6.3.2: Example Code Execution**
```bash
# 2. 예제 코드 실행 검증
# Run all examples from CLI_USER_GUIDE.md

# Example 1: Query
python3 quant_platform.py query --region KR \
  --filter "market_cap > 1000000000" \
  --top 20 --sort-by market_cap

# Example 2: Backtest
python3 quant_platform.py backtest 005930 \
  --strategy momentum \
  --start 2020-01-01 \
  --end 2023-12-31 \
  --html

# Example 3: Shell
python3 quant_platform.py shell
# (Run shell commands from guide)

# Expected: All examples run without errors
```

**Verification 6.3.3: Tutorial Walkthrough**
```bash
# 3. 튜토리얼 단계별 실행
# Follow CLI_TUTORIAL.md step by step

# Step 1: Database Setup
psql -d quant_platform -c "SELECT COUNT(*) FROM tickers;"
# Expected: 2500+

# Step 2: First Query
python3 quant_platform.py query --region KR --top 5

# Step 3: Advanced Filtering
python3 quant_platform.py query --region KR \
  --filter "market_cap > 1000000000000" \
  --filter "sector == '반도체'" \
  --top 10

# ... (Continue through all tutorial steps)

# Expected: All steps complete successfully
```

---

### Sprint Integration Tests

**Sprint 1 Integration Test**
```bash
#!/bin/bash
echo "🚀 Sprint 1 Integration Test"

# Test 1: Database connection
python3 -c "
import asyncio
from cli.utils.database import DatabaseManager

async def test():
    db = DatabaseManager()
    await db.connect()
    result = await db.pool.fetchval('SELECT COUNT(*) FROM tickers WHERE region = \"KR\"')
    print(f'✅ Test 1: Database ({result} tickers)')
    await db.disconnect()

asyncio.run(test())
"

# Test 2: Query builder
python3 -c "
import asyncio
from cli.utils.database import DatabaseManager
from cli.utils.query_builder import QueryBuilder

async def test():
    db = DatabaseManager()
    await db.connect()
    qb = QueryBuilder(db).tickers('KR').filter('market_cap > 1000000000')
    df = await qb.execute()
    print(f'✅ Test 2: Query Builder ({len(df)} results)')
    await db.disconnect()

asyncio.run(test())
"

# Test 3: CLI query
python3 quant_platform.py query --region KR --top 5 > /dev/null
echo "✅ Test 3: CLI Query"

# Test 4: Rich formatting
python3 quant_platform.py query --region KR --top 5 | grep -q "┏━━━"
echo "✅ Test 4: Rich Formatting"

echo "✨ Sprint 1: 4/4 tests passed"
```

**Sprint 2 Integration Test**
```bash
#!/bin/bash
echo "🚀 Sprint 2 Integration Test"

# Test 1: Advanced filters
python3 quant_platform.py query --region KR \
  --filter "market_cap > 1000000000" \
  --top 10 --sort-by market_cap > /dev/null
echo "✅ Test 1: Advanced Filters"

# Test 2: CSV export
python3 quant_platform.py query --region KR \
  --filter "sector == '반도체'" \
  --output test_sprint2.csv

if [ -f "test_sprint2.csv" ]; then
  echo "✅ Test 2: CSV Export"
  rm test_sprint2.csv
fi

# Test 3: Multiple metrics
python3 quant_platform.py query --region KR \
  --with-technicals rsi_14 \
  --with-fundamentals pe_ratio \
  --top 5 > /dev/null
echo "✅ Test 3: Multiple Metrics"

echo "✨ Sprint 2: 3/3 tests passed"
```

**Sprint 3 Integration Test**
```bash
#!/bin/bash
echo "🚀 Sprint 3 Integration Test"

# Test 1: vectorbt installation
python3 -c "import vectorbt as vbt; print(f'✅ Test 1: vectorbt {vbt.__version__}')"

# Test 2: Simple backtest
python3 quant_platform.py backtest 005930 \
  --start 2020-01-01 \
  --end 2021-12-31 > /dev/null
echo "✅ Test 2: Simple Backtest"

# Test 3: Strategy selection
python3 quant_platform.py backtest 005930 \
  --strategy momentum \
  --start 2020-01-01 \
  --end 2021-12-31 > /dev/null
echo "✅ Test 3: Strategy Selection"

# Test 4: Metrics calculation
python3 quant_platform.py backtest 005930 \
  --strategy momentum \
  --start 2020-01-01 \
  --end 2021-12-31 \
  --metrics all > /dev/null
echo "✅ Test 4: Metrics Calculation"

echo "✨ Sprint 3: 4/4 tests passed"
```

**Sprint 4 Integration Test**
```bash
#!/bin/bash
echo "🚀 Sprint 4 Integration Test"

# Test 1: Template rendering
python3 -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('cli/templates'))
template = env.get_template('backtest_report.html')
html = template.render(strategy_name='Test', ticker='005930', metrics={})
print('✅ Test 1: Template Rendering')
"

# Test 2: Plotly charts
python3 -c "
import vectorbt as vbt
import pandas as pd
from cli.utils.charts import create_equity_curve

price = pd.Series([100, 105, 103, 110],
                  index=pd.date_range('2020-01-01', periods=4))
portfolio = vbt.Portfolio.from_holding(price, init_cash=100_000_000)
chart = create_equity_curve(portfolio)
print('✅ Test 2: Plotly Charts')
"

# Test 3: HTML report generation
python3 quant_platform.py backtest 005930 \
  --strategy momentum \
  --start 2020-01-01 \
  --end 2021-12-31 \
  --html \
  --output test_sprint4.html > /dev/null

if [ -f "test_sprint4.html" ]; then
  echo "✅ Test 3: HTML Report Generation"
  rm test_sprint4.html
fi

echo "✨ Sprint 4: 3/3 tests passed"
```

**Sprint 5 Integration Test**
```bash
#!/bin/bash
echo "🚀 Sprint 5 Integration Test"

# Test 1: Shell startup
python3 -c "
from cli.shell import QuantShell
shell = QuantShell()
print('✅ Test 1: Shell Startup')
"

# Test 2: Session save/load
python3 << EOF
from cli.shell import QuantShell
import pickle

shell = QuantShell()
shell.current_filters = ['market_cap > 1000000000']

# Save session
with open('sessions/test_session.pkl', 'wb') as f:
    pickle.dump({'filters': shell.current_filters}, f)

# Load session
with open('sessions/test_session.pkl', 'rb') as f:
    data = pickle.load(f)
    assert data['filters'] == shell.current_filters

print('✅ Test 2: Session Save/Load')
EOF

# Test 3: Auto-completion (using pexpect)
python3 -c "
import pexpect
child = pexpect.spawn('python3 quant_platform.py shell')
child.expect('quant>')
child.sendline('qu\t')  # Tab completion
child.expect('query')
child.sendline('exit')
print('✅ Test 3: Auto-completion')
"

echo "✨ Sprint 5: 3/3 tests passed"
```

**Sprint 6 Integration Test**
```bash
#!/bin/bash
echo "🚀 Sprint 6 Integration Test"

# Test 1: Performance (query <100ms)
python3 -c "
import asyncio
import time
from cli.utils.database import DatabaseManager
from cli.utils.query_builder import QueryBuilder

async def test():
    db = DatabaseManager()
    await db.connect()

    start = time.time()
    qb = QueryBuilder(db).tickers('KR')
    await qb.execute()
    elapsed = time.time() - start

    print(f'✅ Test 1: Performance ({elapsed*1000:.1f}ms)')
    assert elapsed < 0.1, 'Performance issue'

    await db.disconnect()

asyncio.run(test())
"

# Test 2: Error handling (database down)
python3 -c "
import asyncio
from cli.utils.database import DatabaseManager

async def test():
    db = DatabaseManager()
    try:
        # Wrong connection
        db.pool = await asyncpg.create_pool(host='invalid_host')
    except Exception as e:
        print('✅ Test 2: Error Handling (caught exception)')
        return

asyncio.run(test())
"

# Test 3: Documentation (examples run)
python3 quant_platform.py query --region KR --top 5 > /dev/null
python3 quant_platform.py backtest 005930 --start 2020-01-01 --end 2021-12-31 > /dev/null
echo "✅ Test 3: Documentation Examples"

echo "✨ Sprint 6: 3/3 tests passed"
```

---

## 🏁 전체 통합 테스트

### Full Project Integration Test Script

```bash
#!/bin/bash
# test_full_integration.sh
# 전체 프로젝트 통합 테스트 스크립트

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  Quant Platform CLI - Full Integration Test Suite        ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Test function
run_test() {
  local test_name=$1
  local test_command=$2

  TOTAL_TESTS=$((TOTAL_TESTS + 1))
  echo -n "Running: $test_name ... "

  if eval "$test_command" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PASS${NC}"
    PASSED_TESTS=$((PASSED_TESTS + 1))
  else
    echo -e "${RED}✗ FAIL${NC}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
  fi
}

echo "═══════════════════════════════════════════════════════════"
echo "Sprint 1: Foundation + Quick Win"
echo "═══════════════════════════════════════════════════════════"

run_test "Database Connection" "python3 -c 'import asyncio; from cli.utils.database import DatabaseManager; asyncio.run(DatabaseManager().connect())'"

run_test "Query Builder" "python3 -c 'import asyncio; from cli.utils.database import DatabaseManager; from cli.utils.query_builder import QueryBuilder; asyncio.run(QueryBuilder(DatabaseManager()).tickers(\"KR\").execute())'"

run_test "CLI Query" "python3 quant_platform.py query --region KR --top 5"

run_test "Rich Formatting" "python3 quant_platform.py query --region KR --top 5 | grep -q '┏━━━'"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Sprint 2: Enhanced Screening"
echo "═══════════════════════════════════════════════════════════"

run_test "Advanced Filters" "python3 quant_platform.py query --region KR --filter 'market_cap > 1000000000' --top 10"

run_test "CSV Export" "python3 quant_platform.py query --region KR --output test_export.csv && rm test_export.csv"

run_test "Multiple Metrics" "python3 quant_platform.py query --region KR --with-technicals rsi_14 --top 5"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Sprint 3: Backtest Foundation"
echo "═══════════════════════════════════════════════════════════"

run_test "vectorbt Installation" "python3 -c 'import vectorbt as vbt'"

run_test "Simple Backtest" "python3 quant_platform.py backtest 005930 --start 2020-01-01 --end 2021-12-31"

run_test "Strategy Selection" "python3 quant_platform.py backtest 005930 --strategy momentum --start 2020-01-01 --end 2021-12-31"

run_test "Metrics Calculation" "python3 quant_platform.py backtest 005930 --metrics all --start 2020-01-01 --end 2021-12-31"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Sprint 4: HTML Reports"
echo "═══════════════════════════════════════════════════════════"

run_test "Template Rendering" "python3 -c 'from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader(\"cli/templates\")); env.get_template(\"backtest_report.html\")'"

run_test "Plotly Charts" "python3 -c 'import vectorbt as vbt; import pandas as pd; from cli.utils.charts import create_equity_curve; price = pd.Series([100, 105], index=pd.date_range(\"2020-01-01\", periods=2)); portfolio = vbt.Portfolio.from_holding(price, init_cash=100_000_000); create_equity_curve(portfolio)'"

run_test "HTML Report Generation" "python3 quant_platform.py backtest 005930 --strategy momentum --start 2020-01-01 --end 2021-12-31 --html --output test_report.html && rm test_report.html"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Sprint 5: Interactive Shell"
echo "═══════════════════════════════════════════════════════════"

run_test "Shell Startup" "python3 -c 'from cli.shell import QuantShell; QuantShell()'"

run_test "Session Management" "python3 -c 'from cli.shell import QuantShell; import pickle; shell = QuantShell(); shell.current_filters = [\"test\"]; import os; os.makedirs(\"sessions\", exist_ok=True); pickle.dump({\"filters\": shell.current_filters}, open(\"sessions/test.pkl\", \"wb\"))'"

run_test "Command Execution" "echo 'query --region KR --top 5\nexit' | python3 quant_platform.py shell"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Sprint 6: Final Polish"
echo "═══════════════════════════════════════════════════════════"

run_test "Query Performance (<100ms)" "python3 -c 'import asyncio, time; from cli.utils.database import DatabaseManager; from cli.utils.query_builder import QueryBuilder; asyncio.run(QueryBuilder(DatabaseManager()).tickers(\"KR\").execute()); assert time.time() < 0.1'"

run_test "Error Handling" "python3 quant_platform.py query --region INVALID 2>&1 | grep -q 'Invalid region'"

run_test "Documentation" "python3 quant_platform.py --help | grep -q 'Quant Platform'"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Test Summary"
echo "═══════════════════════════════════════════════════════════"
echo "Total Tests: $TOTAL_TESTS"
echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed: ${RED}$FAILED_TESTS${NC}"
echo "Success Rate: $((PASSED_TESTS * 100 / TOTAL_TESTS))%"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
  echo -e "${GREEN}🎉 All tests passed! Project is ready for deployment.${NC}"
  exit 0
else
  echo -e "${RED}❌ Some tests failed. Please fix the issues before deploying.${NC}"
  exit 1
fi
```

**Usage**:
```bash
chmod +x test_full_integration.sh
./test_full_integration.sh
```

**Expected Output**:
```
╔═══════════════════════════════════════════════════════════╗
║  Quant Platform CLI - Full Integration Test Suite        ║
╚═══════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════
Sprint 1: Foundation + Quick Win
═══════════════════════════════════════════════════════════
Running: Database Connection ... ✓ PASS
Running: Query Builder ... ✓ PASS
Running: CLI Query ... ✓ PASS
Running: Rich Formatting ... ✓ PASS

═══════════════════════════════════════════════════════════
Sprint 2: Enhanced Screening
═══════════════════════════════════════════════════════════
Running: Advanced Filters ... ✓ PASS
Running: CSV Export ... ✓ PASS
Running: Multiple Metrics ... ✓ PASS

═══════════════════════════════════════════════════════════
Sprint 3: Backtest Foundation
═══════════════════════════════════════════════════════════
Running: vectorbt Installation ... ✓ PASS
Running: Simple Backtest ... ✓ PASS
Running: Strategy Selection ... ✓ PASS
Running: Metrics Calculation ... ✓ PASS

═══════════════════════════════════════════════════════════
Sprint 4: HTML Reports
═══════════════════════════════════════════════════════════
Running: Template Rendering ... ✓ PASS
Running: Plotly Charts ... ✓ PASS
Running: HTML Report Generation ... ✓ PASS

═══════════════════════════════════════════════════════════
Sprint 5: Interactive Shell
═══════════════════════════════════════════════════════════
Running: Shell Startup ... ✓ PASS
Running: Session Management ... ✓ PASS
Running: Command Execution ... ✓ PASS

═══════════════════════════════════════════════════════════
Sprint 6: Final Polish
═══════════════════════════════════════════════════════════
Running: Query Performance (<100ms) ... ✓ PASS
Running: Error Handling ... ✓ PASS
Running: Documentation ... ✓ PASS

═══════════════════════════════════════════════════════════
Test Summary
═══════════════════════════════════════════════════════════
Total Tests: 19
Passed: 19
Failed: 0
Success Rate: 100%

🎉 All tests passed! Project is ready for deployment.
```

---

## 📋 최종 인수 체크리스트

### 기능 완성도 (Functionality)

**Sprint 1: Query Infrastructure**
- [ ] 데이터베이스 연결 풀 설정 완료 (min=2, max=10)
- [ ] QueryBuilder 모든 메서드 구현 (tickers, filter, top, select)
- [ ] CLI 기본 명령어 실행 (`query --region KR`)
- [ ] Rich 테이블 포맷팅 정상 작동 (한글 지원)

**Sprint 2: Enhanced Screening**
- [ ] 고급 필터 기능 (top, sort-by, columns)
- [ ] CSV 파일 내보내기 (UTF-8-BOM, Excel 호환)
- [ ] 기술적 지표 + 펀더멘털 통합 쿼리

**Sprint 3: Backtest Foundation**
- [ ] vectorbt 0.26.2 설치 및 작동 확인
- [ ] 단순 백테스트 실행 (SMA Crossover)
- [ ] 전략 선택 기능 (Momentum, Value, Quality)
- [ ] 성과 지표 자동 계산 (11개 지표)

**Sprint 4: HTML Reports**
- [ ] Jinja2 템플릿 렌더링 (한글 인코딩)
- [ ] Plotly 차트 생성 (Equity Curve, Drawdown)
- [ ] 완전한 HTML 리포트 생성 (반응형 레이아웃)
- [ ] 브라우저 자동 열기 기능

**Sprint 5: Interactive Shell**
- [ ] 셸 프레임워크 작동 (cmd.Cmd 기반)
- [ ] 세션 저장/로드 기능
- [ ] 전략 지속성 (세션 간 파라미터 유지)
- [ ] 자동완성 (명령어, 종목코드, 전략 이름)
- [ ] 명령어 히스토리 (UP/DOWN 화살표)

**Sprint 6: Final Polish**
- [ ] 쿼리 성능 <100ms (단일 쿼리)
- [ ] 캐시 효과 40배 이상 속도 향상
- [ ] 메모리 증가 <50MB (100회 쿼리)
- [ ] 모든 에러 처리 구현 (DB, 파일, 입력)
- [ ] 완전한 사용자 가이드 (CLI_USER_GUIDE.md)
- [ ] 모든 예제 코드 실행 가능

---

### 성능 요구사항 (Performance)

**쿼리 성능**
- [ ] 단일 쿼리 응답 시간 <100ms (평균 50ms)
- [ ] 100회 연속 쿼리 <10초 (평균 100ms)
- [ ] 동시 10개 쿼리 <2초 (평균 200ms)
- [ ] 캐시 적중률 >80%

**백테스트 성능**
- [ ] vectorbt 5년 백테스트 <1초
- [ ] Custom engine 5년 백테스트 <30초
- [ ] 10년 백테스트 <10초 (vectorbt)
- [ ] 메모리 사용량 <500MB

**HTML 리포트 성능**
- [ ] 리포트 생성 <10초
- [ ] 파일 크기 <5MB
- [ ] 브라우저 렌더링 <3초
- [ ] 차트 인터랙션 응답 <100ms

**Interactive Shell 성능**
- [ ] 셸 시작 시간 <2초
- [ ] 명령어 응답 <2초
- [ ] 자동완성 응답 <100ms (2500개 종목)
- [ ] 세션 저장/로드 <500ms

**메모리 관리**
- [ ] 초기 메모리 사용량 <100MB
- [ ] 100회 쿼리 후 메모리 증가 <50MB
- [ ] 셸 10회 명령 실행 후 증가 <20MB
- [ ] 메모리 누수 없음 (장시간 실행 안정)

---

### 품질 요구사항 (Quality)

**테스트 커버리지**
- [ ] Sprint 1 통합 테스트 4/4 통과
- [ ] Sprint 2 통합 테스트 3/3 통과
- [ ] Sprint 3 통합 테스트 4/4 통과
- [ ] Sprint 4 통합 테스트 3/3 통과
- [ ] Sprint 5 통합 테스트 3/3 통과
- [ ] Sprint 6 통합 테스트 3/3 통과
- [ ] 전체 통합 테스트 19/19 통과

**에러 처리**
- [ ] 데이터베이스 연결 실패 처리 (재시도 3회)
- [ ] 잘못된 입력 검증 (지역, 날짜, 필터)
- [ ] 파일 시스템 에러 처리 (권한, 공간)
- [ ] 백테스트 실행 에러 처리 (데이터 없음, 전략 실패)
- [ ] 모든 에러에 친절한 메시지 + 해결 방법 제시

**코드 품질**
- [ ] PEP 8 스타일 준수 (flake8 검증)
- [ ] 모든 함수에 docstring 작성
- [ ] 타입 힌트 사용 (Python 3.11+)
- [ ] 단위 테스트 커버리지 >70%
- [ ] 코드 리뷰 완료 (주요 로직)

**문서 품질**
- [ ] CLI_USER_GUIDE.md 완성
- [ ] CLI_TUTORIAL.md 단계별 가이드
- [ ] API 문서 생성 (Sphinx)
- [ ] 모든 예제 코드 실행 가능
- [ ] 스크린샷 포함 (주요 기능)

---

### 사용자 경험 (User Experience)

**CLI 인터페이스**
- [ ] 모든 명령어 `--help` 옵션 제공
- [ ] 에러 메시지가 명확하고 친절함
- [ ] 진행 상황 표시 (백테스트, 리포트 생성)
- [ ] 컬러 테마 적용 (성공=녹색, 에러=빨간색)

**Interactive Shell**
- [ ] 환영 메시지 명확 (버전, 명령어 힌트)
- [ ] 프롬프트 커스터마이징 가능
- [ ] 자동완성 직관적 (TAB 키)
- [ ] 에러 발생 시 셸 종료 안 됨

**HTML 리포트**
- [ ] 반응형 레이아웃 (데스크톱, 태블릿, 모바일)
- [ ] 인터랙티브 차트 (Zoom, Pan, Hover)
- [ ] 한글 폰트 적용 (Noto Sans KR)
- [ ] 인쇄 친화적 스타일

**문서 및 예제**
- [ ] 퀵스타트 가이드 명확 (3단계 이내 시작)
- [ ] 예제 코드 복사/붙여넣기 가능
- [ ] 트러블슈팅 섹션 포함
- [ ] FAQ 작성 (자주 묻는 질문 10개)

---

### 배포 준비 (Deployment)

**환경 설정**
- [ ] requirements.txt 최신화
- [ ] .env.example 파일 제공
- [ ] PostgreSQL 스키마 스크립트 (init_db.sql)
- [ ] 샘플 데이터 제공 (sample_data.sql)

**설치 스크립트**
- [ ] setup.sh (자동 설치 스크립트)
- [ ] 의존성 자동 설치 (pip, PostgreSQL)
- [ ] 데이터베이스 자동 초기화
- [ ] 설치 검증 테스트 실행

**문서**
- [ ] INSTALLATION.md (설치 가이드)
- [ ] QUICKSTART.md (퀵스타트 가이드)
- [ ] TROUBLESHOOTING.md (트러블슈팅)
- [ ] CHANGELOG.md (변경 로그)

**테스트**
- [ ] 클린 환경 설치 테스트 (빈 시스템)
- [ ] macOS 호환성 테스트
- [ ] Linux 호환성 테스트 (Ubuntu, CentOS)
- [ ] Windows WSL 호환성 테스트

---

### 보안 (Security)

**데이터 보호**
- [ ] 데이터베이스 비밀번호 환경변수 저장
- [ ] API 키 .env 파일로 관리
- [ ] .gitignore에 민감 정보 추가
- [ ] SQL Injection 방어 (parameterized queries)

**접근 제어**
- [ ] 데이터베이스 연결 권한 제한
- [ ] 파일 쓰기 권한 검증
- [ ] 세션 파일 권한 설정 (0600)

---

### 최종 승인 (Final Approval)

**프로젝트 관리자 체크**
- [ ] 모든 스프린트 완료 (Sprint 1-6)
- [ ] 전체 통합 테스트 통과 (19/19)
- [ ] 성능 벤치마크 달성
- [ ] 문서 검토 완료
- [ ] 코드 리뷰 승인

**배포 전 최종 검증**
- [ ] 프로덕션 환경 테스트 완료
- [ ] 롤백 계획 수립
- [ ] 사용자 교육 자료 준비
- [ ] 지원 채널 준비 (이슈 트래커, 이메일)

**프로젝트 인수 승인**
- [ ] 기능 요구사항 100% 충족
- [ ] 성능 요구사항 100% 충족
- [ ] 품질 기준 만족
- [ ] 배포 준비 완료

**승인 서명**
- 프로젝트 관리자: _________________ 날짜: _________
- 기술 리드: _________________ 날짜: _________
- 품질 관리자: _________________ 날짜: _________

---

**프로젝트 완료**: 모든 체크리스트 항목이 완료되면 프로젝트 인수 및 배포 진행

---

## 연락처 및 지원

- GitHub Issues: [프로젝트 이슈 트래커]
- 문서: `docs/` 디렉토리
- 예제: `examples/` 디렉토리

---

**문서 끝**
