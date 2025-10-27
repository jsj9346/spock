# Spock UI Expansion Roadmap

**Status**: 📋 Backlog (Deferred until core system completion)
**Created**: 2025-10-16
**Priority**: Medium (Phase 7+)

## 개요

Spock 자동화 트레이딩 시스템을 일반 사용자가 활용할 수 있도록 대화형 CLI 도구와 웹 UI로 확장하는 로드맵입니다. 현재 spock.py는 사전 설정된 조건에 따라 완전 자동화된 파이프라인을 실행하지만, 사용자가 직접 파라미터를 조정하며 백테스트, 종목 발굴, 포트폴리오 관리를 할 수 있는 인터페이스가 필요합니다.

## CLI vs TUI vs WebUI 개념 구분

### CLI (Command Line Interface)
- **정의**: 터미널 텍스트 명령어 기반 인터페이스
- **특징**:
  - SSH 원격 실행 가능
  - 스크립트 자동화 용이
  - 배치 작업에 최적
  - 빠른 실행 속도
- **예시**: `spock-cli scan --region KR --min-score 70`
- **구현 시기**: Week 1-5 (Phase 7)

### TUI (Terminal User Interface)
- **정의**: 터미널 내 표, 색상, 실시간 업데이트 인터페이스
- **특징**:
  - SSH 원격 실행 가능
  - 실시간 데이터 모니터링
  - 인터랙티브한 탐색
  - 키보드 네비게이션
- **기술**: rich 라이브러리
- **예시**: 실시간 포트폴리오 대시보드, 트레이딩 모니터링
- **구현 시기**: Week 6-7 (Phase 7 후반)

### WebUI (Web User Interface)
- **정의**: 브라우저 기반 웹 인터페이스
- **특징**:
  - OS 독립적 (Windows, macOS, Linux)
  - 모바일 브라우저 접속 가능
  - 그래픽 차트 및 시각화
  - 멀티 탭/창 지원
- **기술**: Streamlit (권장), Gradio, FastAPI+React
- **예시**: `http://localhost:8501` 접속
- **구현 시기**: Week 9+ (Phase 8)

### GUI (Desktop App) - 제외
- **정의**: 네이티브 데스크톱 애플리케이션 (Electron, Qt, Tkinter)
- **퀀트 시스템에 부적합한 이유**:
  - OS별 별도 빌드 필요 (.dmg, .exe, .deb)
  - 설치 및 배포 복잡도 높음
  - 서버 자동화 불가능
  - 유지보수 비용 높음
- **결론**: ❌ Spock에서는 구현하지 않음

### 비교표

| 특성 | CLI | TUI | WebUI | GUI (제외) |
|-----|-----|-----|-------|-----------|
| **개발 시간** | 1-2일 | 1주 | 2-4주 | 4-8주 |
| **원격 접속** | SSH | SSH | HTTP | VPN |
| **모바일 지원** | ❌ | ❌ | ✅ | ❌ |
| **자동화** | ✅ | ❌ | ⚠️ | ❌ |
| **실시간 모니터링** | ❌ | ✅ | ✅ | ✅ |
| **그래픽 차트** | ❌ | ⚠️ | ✅ | ✅ |
| **OS 독립성** | ✅ | ✅ | ✅ | ❌ |
| **설치 필요** | ❌ | ❌ | ❌ | ✅ |

### 핵심 원칙: "CLI First, WebUI Later"

1. **Week 1-5**: CLI Only
   - 데이터 수집, 지표 계산, 백테스트
   - 자동화 스크립트 작성
   - 안정성 검증

2. **Week 6-7**: TUI 추가
   - 실시간 포트폴리오 모니터링
   - 트레이딩 세션 관찰
   - rich 라이브러리 활용

3. **Week 9+**: WebUI (선택적)
   - 백테스트 검증 완료 후
   - 비개발자 사용자 대상
   - Streamlit 우선 채택

**Rationale**: 백엔드 로직 안정화가 최우선. UI는 검증된 시스템 위에 구축.

## 전제 조건

이 확장 작업은 다음 조건이 충족된 후 시작합니다:

- ✅ Spock Core Engine 완성 (Phase 1-6)
- ✅ 모든 시장 어댑터 안정화 (KR, US, CN, HK, JP, VN)
- ✅ LayeredScoringEngine 검증 완료
- ✅ Kelly Calculator 백테스트 검증
- ✅ KIS API Trading Engine 실거래 검증
- ⏳ 최소 3개월 이상 실거래 데이터 축적
- ⏳ 시스템 안정성 검증 (99%+ uptime)

## Phase 7: Interactive CLI Tool + TUI (2-3주)

### 목적
개발자 및 파워유저가 터미널에서 대화형으로 백테스트 및 종목 분석을 수행할 수 있는 도구 제공

### 핵심 기능

#### 1. Interactive Mode
```
spock-cli
├── 종목 스캔 (Stock Scanning)
│   ├── 필터 설정 (market cap, volume, sector)
│   ├── 실시간 진행 상황 표시
│   └── 결과 테이블 출력
│
├── 기술적 분석 (Technical Analysis)
│   ├── 종목 선택 (autocomplete)
│   ├── LayeredScoringEngine 실행
│   └── 3-layer breakdown 시각화
│
├── 백테스트 (Backtesting)
│   ├── 파라미터 설정 (risk level, threshold, Kelly multiplier)
│   ├── 진행 상황 progress bar
│   └── 결과 리포트 (return, Sharpe, drawdown)
│
├── 포트폴리오 시뮬레이션 (Portfolio Simulation)
│   ├── 가상 포트폴리오 생성
│   ├── 리밸런싱 시뮬레이션
│   └── 리스크 분석
│
└── 파라미터 튜닝 (Parameter Tuning)
    ├── A/B 테스트 설정
    ├── 병렬 백테스트 실행
    └── 결과 비교 테이블
```

#### 2. Command Mode
```bash
# 종목 스캔
spock-cli scan --region KR --min-score 70 --sector IT

# 개별 종목 분석
spock-cli analyze --ticker 005930 --days 250

# 백테스트 실행
spock-cli backtest \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --risk-level moderate \
  --export results.json

# 결과 비교
spock-cli compare run1.json run2.json

# 포트폴리오 시뮬레이션
spock-cli portfolio simulate \
  --tickers 005930,000660,035720 \
  --allocation 0.3,0.3,0.4 \
  --start 2024-01-01
```

### 하이브리드 CLI 설계 (Command + Interactive)

#### Mode 1: Command Mode (단발성 작업)
```bash
# 빠른 조회/실행
spock-cli scan --region KR --min-score 70
spock-cli analyze 005930
spock-cli backtest --start 2024-01-01 --end 2024-12-31 --export results.json

# 스크립트/자동화에 적합
for ticker in $(cat tickers.txt); do
    spock-cli analyze $ticker >> analysis.log
done
```

**장점**:
- 빠른 실행 (단일 명령)
- 스크립트 자동화 가능
- 파이프라인 연결 가능 (`| grep`, `| jq`)
- CI/CD 통합 용이

**단점**:
- 매번 DB 연결 overhead
- 컨텍스트 유지 안 됨
- 연속 작업 시 반복 입력

#### Mode 2: Interactive Mode (대화형, diskpart 스타일)
```bash
$ spock-cli

╭──────────────────────────────────────────╮
│  Spock Trading System - Interactive CLI  │
│  Type 'help' for commands, 'exit' to quit │
╰──────────────────────────────────────────╯

spock> scan --region KR --min-score 70
[●●●●●●●●●●] 100% | Scanning KR stocks...
✅ Found 127 candidates

spock> analyze 005930
╭─── Samsung Electronics (005930) ───╮
│ Score: 78.5 (BUY)                  │
│ Stage: 2 (Uptrend)                 │
│ MA Alignment: ✅                   │
╰────────────────────────────────────╯

spock> backtest --start 2024-01-01 --interactive
Enter risk level [conservative/moderate/aggressive]: moderate
Enter max positions [1-20]: 10
Enter Kelly multiplier [0.1-1.0]: 0.5

[●●●●●●●●●●] 100% | Running backtest...
✅ Backtest complete
Total Return: +23.4%
Sharpe Ratio: 1.82

spock> history
1. scan --region KR --min-score 70
2. analyze 005930
3. backtest --start 2024-01-01 --interactive

spock> export session_20241016.json
💾 Session exported

spock> exit
Goodbye!
```

**장점**:
- DB 연결 유지 (빠른 연속 작업)
- 컨텍스트 보존 (이전 결과 참조)
- 대화형 프롬프트로 편한 입력
- 명령어 히스토리 (↑/↓ 키)
- Tab 자동완성

**단점**:
- 스크립트 자동화 어려움
- 초기 로딩 시간
- 프로세스 메모리 유지

#### Entry Point (모드 선택)
```python
# 3가지 실행 방법
spock-cli                      # Interactive mode (기본)
spock-cli --interactive        # Interactive mode (명시적)
spock-cli scan --region KR     # Command mode
```

### 기술 스택

**권장 라이브러리** (하이브리드 CLI):
```
rich==13.7.0              # Beautiful terminal UI
typer==0.9.0              # Type-safe CLI framework (click 기반)
questionary==2.0.1        # Interactive prompts (prompt-toolkit 기반)
colorama==0.4.6           # Cross-platform color support
```

**의존성 트리**:
- typer → click (자동 설치)
- questionary → prompt-toolkit (자동 설치)
- 중복 없는 깔끔한 구성

**UX 예시**:
```
$ spock-cli

╭─────────────────────────────────────────────╮
│    Spock Trading System - Interactive CLI   │
│    Korean & Global Markets                  │
╰─────────────────────────────────────────────╯

Select mode:
  1. 종목 스캔 (Stock Scanning)
  2. 기술적 분석 (Technical Analysis)
  3. 백테스트 (Backtesting)
  4. 포트폴리오 시뮬레이션 (Portfolio Simulation)
  5. 파라미터 튜닝 (Parameter Tuning)

> 3

╭─────────── Backtest Configuration ───────────╮
│ Start Date: 2024-01-01                       │
│ End Date: 2024-12-31                         │
│ Risk Level: moderate                         │
│ Scoring Threshold: 70.0                      │
│ Kelly Multiplier: 0.5                        │
│ Max Positions: 10                            │
╰──────────────────────────────────────────────╯

[●●●●●●●●●●] 100% | Stage 1: Scanning... | 3,245 candidates
[●●●●●●●●●●] 100% | Stage 2: Filtering... | 127 passed
[●●●●●●●●●●] 100% | Stage 3: Analysis... | 45 BUY signals

╭─────────── Backtest Results ─────────────╮
│ Total Return: +23.4%                      │
│ Sharpe Ratio: 1.82                        │
│ Max Drawdown: -8.3%                       │
│ Win Rate: 62.5% (25/40 trades)            │
│ Avg Win: +12.3% | Avg Loss: -5.7%        │
╰───────────────────────────────────────────╯

Export results? (y/n) > y
✅ Results saved to backtest_20241231.json
```

### 구현 아키텍처

#### 프로젝트 구조 (하이브리드 CLI)
```
cli/
├── __init__.py
├── main.py                    # Entry point (모드 선택)
├── command_mode.py            # Typer commands
├── interactive_mode.py        # REPL loop (diskpart 스타일)
├── commands/
│   ├── __init__.py
│   ├── base.py               # 공통 명령 인터페이스 (양쪽 모드 공유)
│   ├── scan.py               # Scan 명령 구현
│   ├── analyze.py            # Analyze 명령 구현
│   ├── backtest.py           # Backtest 명령 구현
│   ├── portfolio.py          # Portfolio 명령 구현
│   └── compare.py            # Compare 명령 구현
├── ui/
│   ├── __init__.py
│   ├── progress.py           # Progress bars (Rich)
│   ├── tables.py             # Rich table formatting
│   └── prompts.py            # Interactive prompts (Questionary)
└── shell/
    ├── __init__.py
    ├── completer.py          # Tab completion
    ├── history.py            # Command history
    └── context.py            # Session context (DB 연결, 결과 저장)
```

#### Shell Context (세션 상태 관리)
```python
# cli/shell/context.py
class ShellContext:
    """Interactive shell session context"""

    def __init__(self):
        self.db = SQLiteDatabaseManager()  # DB 연결 유지
        self.results_history = []           # 명령 실행 결과 저장
        self.session_start = datetime.now()
        self.variables = {}                 # 세션 변수

    def add_result(self, command, result):
        """Save command result to history"""
        self.results_history.append({
            'timestamp': datetime.now(),
            'command': command,
            'result': result
        })

    def get_last_result(self, command=None):
        """Get last result (필터 가능)"""
        # 이전 명령 결과 재사용 가능
        ...
```

#### 공통 명령 인터페이스
```python
# cli/commands/base.py
class BaseCommand(ABC):
    """Base class for all commands (양쪽 모드 공유)"""

    def __init__(self, context: ShellContext = None):
        self.context = context or ShellContext()

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """Execute command logic"""
        pass

    @abstractmethod
    def display_result(self, result: Any):
        """Display result with Rich formatting"""
        pass

    def export_results(self, result: Any, filename: str):
        """Export results to file (JSON, CSV, etc.)"""
        ...
```

### UX 개선 기능

#### 1. Tab Completion (자동완성)
- Command 자동완성: `scan`, `analyze`, `backtest` 등
- Option 자동완성: `--region`, `--min-score` 등
- Value 자동완성: `--region [KR|US|CN|HK|JP|VN]`

#### 2. Command History (히스토리 탐색)
- ↑/↓ 키로 이전 명령 탐색
- Ctrl+R로 히스토리 검색
- `.spock_history` 파일에 영구 저장

#### 3. Interactive Prompts (대화형 입력)
```python
# Questionary로 더 나은 UX
risk_level = questionary.select(
    "Select risk level:",
    choices=['conservative', 'moderate', 'aggressive']
).ask()

confirm = questionary.confirm(
    f"Run backtest ({risk_level})?",
    default=True
).ask()
```

#### 4. Session Export
```bash
spock> export session.json
💾 Exported:
  - 15 commands
  - 8 scan results
  - 3 backtest results
  - Session duration: 45 minutes
```

### 사용 예시 비교

#### Command Mode (스크립트 자동화)
```bash
#!/bin/bash
# daily_scan.sh - 자동화 스크립트

# KR 시장 스캔
spock-cli scan --region KR --min-score 70 --export kr_candidates.json

# US 시장 스캔
spock-cli scan --region US --min-score 75 --export us_candidates.json

# Top 10 종목 분석
for ticker in $(jq -r '.[0:10].ticker' kr_candidates.json); do
    spock-cli analyze $ticker --export "analysis_${ticker}.json"
done

# 백테스트 실행
spock-cli backtest \
    --start 2024-01-01 \
    --end 2024-12-31 \
    --risk-level moderate \
    --export backtest_results.json

# Slack 알림
curl -X POST $SLACK_WEBHOOK -d "{'text': 'Daily scan complete'}"
```

#### Interactive Mode (탐색적 분석)
```bash
$ spock-cli

spock> scan --region KR --min-score 70
✅ Found 127 candidates

spock> analyze 005930
╭─── Samsung Electronics (005930) ───╮
│ Score: 78.5 (BUY)                  │
╰────────────────────────────────────╯

spock> # 마음에 듦, 백테스트 해보자
spock> backtest --start 2024-01-01 --interactive
Enter risk level: moderate
✅ Total Return: +23.4%

spock> # 좋네, 다른 설정도 해보자
spock> backtest --start 2024-01-01 --risk-level aggressive
✅ Total Return: +31.2%
⚠️  Max Drawdown: -12.3%

spock> compare results_moderate.json results_aggressive.json
╭─── Comparison ───╮
│ Moderate: Better Sharpe (1.82 vs 1.54) │
╰──────────────────╯

spock> export session_20241016.json
💾 Session exported

spock> exit
Goodbye!
```

#### 3. Strategy Deployment (전략 배포)
```bash
# 백테스트 결과를 spock.py 파이프라인에 적용
spock-cli deploy --backtest-id bt_20241231 --mode production

# 전략 프로파일 생성 및 적용
spock-cli strategy create \
  --name "Moderate_v2" \
  --from-backtest bt_20241231 \
  --description "Optimized moderate strategy"

spock-cli strategy apply Moderate_v2 --confirm

# 전략 검증 (dry-run)
spock-cli strategy validate Moderate_v2 --days 30

# 전략 활성화/비활성화
spock-cli strategy activate Moderate_v2
spock-cli strategy deactivate Moderate_v2

# 현재 활성 전략 조회
spock-cli strategy status
```

**장점**:
- 백테스트 검증된 전략을 프로덕션에 안전하게 적용
- 버전 관리와 롤백 지원
- Dry-run으로 사전 검증 가능
- A/B 테스트 및 점진적 롤아웃

**안전장치**:
- 프로덕션 배포 전 필수 검증 단계
- 전략 버전 관리 (rollback 지원)
- 리스크 프로파일 일치 확인
- 최소 성과 기준 검증 (Sharpe ratio, max drawdown)

### 구현 아키텍처

#### Strategy Deployment System

**Database Schema 확장**:
```sql
-- 전략 프로파일 테이블
CREATE TABLE strategy_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    source_backtest_id TEXT,
    risk_level TEXT NOT NULL,
    scoring_threshold REAL NOT NULL,
    kelly_multiplier REAL NOT NULL,
    max_positions INTEGER NOT NULL,
    max_sector_weight REAL NOT NULL,
    min_cash_reserve REAL NOT NULL,
    profit_target REAL,
    stop_loss_base REAL,
    trailing_stop_enabled INTEGER DEFAULT 1,
    stage3_exit_enabled INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activated_at TIMESTAMP,
    deactivated_at TIMESTAMP,
    validation_metrics TEXT,  -- JSON: Sharpe, return, drawdown, etc.
    FOREIGN KEY (source_backtest_id) REFERENCES backtest_results(id)
);

-- 전략 변경 이력
CREATE TABLE strategy_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL,
    action TEXT NOT NULL,  -- 'created', 'activated', 'deactivated', 'modified'
    previous_config TEXT,  -- JSON
    new_config TEXT,       -- JSON
    performed_by TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES strategy_profiles(id)
);

-- 전략 성과 모니터링
CREATE TABLE strategy_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL,
    date DATE NOT NULL,
    total_return REAL,
    sharpe_ratio REAL,
    max_drawdown REAL,
    win_rate REAL,
    active_positions INTEGER,
    cash_reserve REAL,
    UNIQUE(strategy_id, date),
    FOREIGN KEY (strategy_id) REFERENCES strategy_profiles(id)
);
```

**전략 배포 워크플로우**:
```python
# cli/commands/strategy.py
class StrategyCommand(BaseCommand):
    """전략 배포 및 관리 명령"""

    def create_from_backtest(self, backtest_id: str, name: str, description: str = None):
        """백테스트 결과로부터 전략 프로파일 생성"""
        # 1. 백테스트 결과 조회
        backtest = self.db.get_backtest_result(backtest_id)
        if not backtest:
            raise ValueError(f"Backtest {backtest_id} not found")

        # 2. 백테스트 설정 추출
        config = {
            'risk_level': backtest['risk_level'],
            'scoring_threshold': backtest['scoring_threshold'],
            'kelly_multiplier': backtest['kelly_multiplier'],
            'max_positions': backtest['max_positions'],
            'max_sector_weight': backtest.get('max_sector_weight', 0.4),
            'min_cash_reserve': backtest.get('min_cash_reserve', 0.2),
            'profit_target': backtest.get('profit_target'),
            'stop_loss_base': backtest.get('stop_loss_base')
        }

        # 3. 성과 지표 검증 (최소 기준)
        validation_metrics = {
            'sharpe_ratio': backtest['sharpe_ratio'],
            'total_return': backtest['total_return'],
            'max_drawdown': backtest['max_drawdown'],
            'win_rate': backtest['win_rate']
        }

        min_requirements = {
            'sharpe_ratio': 1.0,
            'total_return': 0.10,  # 10% 이상
            'max_drawdown': -0.20,  # -20% 이하
            'win_rate': 0.50  # 50% 이상
        }

        if not self._meets_requirements(validation_metrics, min_requirements):
            raise ValueError("Backtest does not meet minimum requirements")

        # 4. 전략 프로파일 저장
        strategy_id = self.db.create_strategy_profile(
            name=name,
            description=description,
            source_backtest_id=backtest_id,
            validation_metrics=json.dumps(validation_metrics),
            **config
        )

        # 5. 이력 기록
        self.db.log_strategy_action(
            strategy_id=strategy_id,
            action='created',
            new_config=json.dumps(config)
        )

        return strategy_id

    def validate_strategy(self, strategy_id: int, days: int = 30):
        """전략 검증 (dry-run 시뮬레이션)"""
        # 1. 전략 설정 로드
        strategy = self.db.get_strategy_profile(strategy_id)

        # 2. 최근 N일 데이터로 시뮬레이션
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # 3. 백테스트 엔진 실행 (dry-run)
        from modules.backtest_engine import BacktestEngine
        backtest_engine = BacktestEngine(self.db)

        results = backtest_engine.run_simulation(
            start_date=start_date,
            end_date=end_date,
            config=strategy,
            mode='validation'
        )

        # 4. 검증 결과 저장
        validation_report = {
            'validation_date': datetime.now().isoformat(),
            'period': f"{start_date.date()} to {end_date.date()}",
            'expected_sharpe': strategy['validation_metrics']['sharpe_ratio'],
            'actual_sharpe': results['sharpe_ratio'],
            'expected_return': strategy['validation_metrics']['total_return'],
            'actual_return': results['total_return'],
            'deviation': abs(results['sharpe_ratio'] - strategy['validation_metrics']['sharpe_ratio'])
        }

        # 5. 큰 편차 발생 시 경고
        if validation_report['deviation'] > 0.3:
            print(f"⚠️  Warning: Sharpe ratio deviation > 0.3 ({validation_report['deviation']:.2f})")
            print("Consider re-running backtest with more recent data")

        return validation_report

    def activate_strategy(self, strategy_id: int, force: bool = False):
        """전략 활성화 (spock.py 파이프라인에 적용)"""
        # 1. 전략 설정 로드
        strategy = self.db.get_strategy_profile(strategy_id)

        # 2. 기존 활성 전략 비활성화
        current_active = self.db.get_active_strategy()
        if current_active and not force:
            raise ValueError(f"Strategy '{current_active['name']}' is already active. Use --force to override.")

        if current_active:
            self.deactivate_strategy(current_active['id'])

        # 3. spock.py 설정 파일 업데이트
        spock_config_path = Path("config/spock_config.yaml")
        with open(spock_config_path, 'r') as f:
            spock_config = yaml.safe_load(f)

        # 4. 전략 설정 적용
        spock_config['risk_profile'] = {
            'level': strategy['risk_level'],
            'scoring_threshold': strategy['scoring_threshold'],
            'kelly_multiplier': strategy['kelly_multiplier'],
            'max_positions': strategy['max_positions'],
            'max_sector_weight': strategy['max_sector_weight'],
            'min_cash_reserve': strategy['min_cash_reserve'],
            'profit_target': strategy['profit_target'],
            'stop_loss_base': strategy['stop_loss_base'],
            'trailing_stop_enabled': bool(strategy['trailing_stop_enabled']),
            'stage3_exit_enabled': bool(strategy['stage3_exit_enabled'])
        }

        spock_config['strategy'] = {
            'id': strategy['id'],
            'name': strategy['name'],
            'source_backtest_id': strategy['source_backtest_id'],
            'activated_at': datetime.now().isoformat()
        }

        # 5. 설정 파일 저장
        with open(spock_config_path, 'w') as f:
            yaml.safe_dump(spock_config, f, indent=2)

        # 6. DB에 활성화 상태 기록
        self.db.activate_strategy(strategy_id)

        # 7. 이력 기록
        self.db.log_strategy_action(
            strategy_id=strategy_id,
            action='activated',
            new_config=json.dumps(spock_config['risk_profile'])
        )

        print(f"✅ Strategy '{strategy['name']}' activated successfully")
        print(f"📝 spock.py will use this strategy on next run")

    def deactivate_strategy(self, strategy_id: int):
        """전략 비활성화"""
        strategy = self.db.get_strategy_profile(strategy_id)

        # DB에 비활성화 상태 기록
        self.db.deactivate_strategy(strategy_id)

        # 이력 기록
        self.db.log_strategy_action(
            strategy_id=strategy_id,
            action='deactivated',
            previous_config=json.dumps(strategy)
        )

        print(f"✅ Strategy '{strategy['name']}' deactivated")

    def get_status(self):
        """현재 활성 전략 조회"""
        active_strategy = self.db.get_active_strategy()

        if not active_strategy:
            print("No active strategy")
            return None

        # 최근 성과 조회
        recent_performance = self.db.get_strategy_performance(
            active_strategy['id'],
            days=30
        )

        # Rich 테이블로 출력
        from rich.table import Table
        from rich.console import Console

        console = Console()
        table = Table(title=f"Active Strategy: {active_strategy['name']}")

        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Strategy ID", str(active_strategy['id']))
        table.add_row("Risk Level", active_strategy['risk_level'])
        table.add_row("Source Backtest", active_strategy['source_backtest_id'])
        table.add_row("Activated At", active_strategy['activated_at'])
        table.add_row("", "")

        if recent_performance:
            table.add_row("30-Day Return", f"{recent_performance['total_return']:.2%}")
            table.add_row("30-Day Sharpe", f"{recent_performance['sharpe_ratio']:.2f}")
            table.add_row("Current Drawdown", f"{recent_performance['max_drawdown']:.2%}")
            table.add_row("Win Rate", f"{recent_performance['win_rate']:.2%}")

        console.print(table)

        return active_strategy
```

**Usage Examples**:
```bash
# 1. 백테스트 실행 및 결과 저장
spock-cli backtest \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --risk-level moderate \
  --export bt_20241231.json

# 2. 백테스트 결과 검토
spock-cli backtest show bt_20241231
# 출력:
# ✅ Backtest ID: bt_20241231
# Total Return: +23.4%
# Sharpe Ratio: 1.82
# Max Drawdown: -8.3%
# Win Rate: 62.5%

# 3. 전략 프로파일 생성
spock-cli strategy create \
  --name "Moderate_Optimized" \
  --from-backtest bt_20241231 \
  --description "2024년 검증된 moderate 전략"

# 4. 전략 검증 (최근 30일 데이터로 dry-run)
spock-cli strategy validate Moderate_Optimized --days 30
# 출력:
# ✅ Validation complete
# Expected Sharpe: 1.82 | Actual Sharpe: 1.79
# Deviation: 0.03 (acceptable)

# 5. 전략 활성화
spock-cli strategy activate Moderate_Optimized
# 프롬프트:
# ⚠️  This will apply the strategy to spock.py pipeline
# Current active: None
# New strategy: Moderate_Optimized (Sharpe: 1.82, Return: 23.4%)
# Continue? (y/n): y
# ✅ Strategy activated
# 📝 spock.py will use this strategy on next run

# 6. 전략 상태 조회
spock-cli strategy status
# 출력:
# Active Strategy: Moderate_Optimized
# Risk Level: moderate
# Activated At: 2024-10-17 14:30:00
# 30-Day Return: +4.2%
# 30-Day Sharpe: 1.75

# 7. spock.py 실행 (활성 전략 자동 적용)
python3 spock.py --region KR
# 출력:
# 🎯 Using active strategy: Moderate_Optimized
# Risk Level: moderate
# Scoring Threshold: 70.0
# Kelly Multiplier: 0.5
# Max Positions: 10
```

### 개발 태스크

**Week 1-5**: CLI Framework Setup (Command Mode)
- [ ] Typer CLI framework 구조 생성 (하이브리드 지원)
- [ ] Rich UI components 구현 (progress, tables, panels)
- [ ] `spock-cli scan` 명령 구현
- [ ] `spock-cli analyze` 명령 구현
- [ ] `spock-cli backtest` 명령 구현
- [ ] `spock-cli strategy` 명령 구현 (create, validate, activate, deactivate, status)
- [ ] Database schema 확장 (strategy_profiles, strategy_history, strategy_performance)
- [ ] spock.py 통합 (활성 전략 자동 로드)
- [ ] `spock-cli compare` 명령 구현
- [ ] Session export/import 기능 (JSON, CSV)
- [ ] 테스트 및 문서화

**Week 6-7**: TUI (Terminal User Interface) 추가
- [ ] Interactive mode REPL loop (rich 라이브러리)
- [ ] Shell Context 구현 (DB 연결, 결과 저장)
- [ ] 실시간 포트폴리오 대시보드
- [ ] Tab completion 구현
- [ ] Command history 구현
- [ ] 키보드 네비게이션 (↑/↓/Enter)
- [ ] 실시간 데이터 업데이트 (Live display)

### 성공 기준
- ✅ 모든 spock.py 기능을 CLI로 실행 가능
- ✅ 백테스트 전략을 프로덕션 파이프라인에 안전하게 배포 가능
- ✅ 전략 버전 관리 및 롤백 지원
- ✅ Interactive mode UX 검증 (5명 이상 테스터)
- ✅ Command mode 성능 (백테스트 실행 시간 <5분)
- ✅ 문서화 완료 (README, usage examples)

---

## Phase 8: Web UI MVP (4-6주)

### 목적
일반 투자자가 웹 브라우저에서 Spock 시스템을 활용할 수 있는 직관적인 인터페이스 제공

### 배포 환경: 로컬 우선 (AWS는 Phase 9+ 옵션)

**로컬 환경이 더 나은 이유**:
1. **보안**: KIS API credentials와 투자 데이터를 로컬에서만 관리
2. **비용**: AWS 배포 시 연간 $720-960 → 로컬은 $0
3. **성능**: 로컬 SQLite 직접 접근 (<10ms) vs API 네트워크 레이턴시 (50-100ms)
4. **간편함**: 복잡한 인프라 관리 불필요, git pull로 업데이트

**실행 방법** (로컬):
```bash
# Streamlit (추천)
streamlit run web-ui/streamlit_app.py
# → http://localhost:8501

# FastAPI + React (옵션)
cd api && uvicorn main:app --reload  # http://localhost:8000
cd web-ui && npm run dev              # http://localhost:5173
```

### 핵심 화면

#### 1. Dashboard (홈)
- **Portfolio Overview Panel**
  - 총 자산 가치 (KRW)
  - 일일 수익률 (%)
  - 보유 종목 수
  - 현금 비율

- **Equity Curve Chart**
  - 포트폴리오 가치 추이 (최근 90일)
  - 벤치마크 비교 (KOSPI, S&P500)

- **Top Recommendations Panel**
  - 오늘의 추천 종목 (Top 10 scores)
  - 티커, 이름, 점수, 신호 (BUY/WATCH)

- **Recent Trades Panel**
  - 최근 10건의 거래 내역
  - 매수/매도, 가격, 수익률

- **Market Sentiment Panel**
  - VIX 지수
  - Fear & Greed Index
  - 외국인/기관 매매 동향

#### 2. Stock Scanner
- **Filter Panel** (좌측 사이드바)
  - Region: KR, US, CN, HK, JP, VN
  - Market Cap: Min/Max slider
  - Volume: Min daily volume
  - Sector: Multi-select dropdown
  - Score Range: 0-100 slider

- **Scan Results Table**
  - Ticker, Name, Sector, Score, Signal
  - Sortable columns
  - 클릭 시 상세 분석 페이지로 이동

- **Actions**
  - Export to CSV/Excel
  - Add to watchlist
  - Quick analyze (modal)

#### 3. Stock Analysis (상세 페이지)
- **Price Chart** (상단)
  - OHLCV candlestick chart
  - Technical indicators overlay (MA5/20/60/120/200, BB, Volume)
  - Interactive zoom/pan (TradingView style)

- **Scoring Breakdown** (중앙)
  - 3-layer score visualization
    - Layer 1 - Macro (25 pts): Progress bar
    - Layer 2 - Structural (45 pts): Progress bar
    - Layer 3 - Micro (30 pts): Progress bar
  - Total Score: 큰 숫자 + color coding (green/yellow/red)
  - Recommendation: BUY / WATCH / AVOID badge

- **AI Analysis Panel** (하단)
  - GPT-4 chart pattern recognition
  - Detected patterns: VCP, Cup & Handle, etc.
  - Entry/Exit suggestions

- **Actions**
  - Add to portfolio (modal)
  - Set alert
  - Export report (PDF)

#### 4. Backtesting
- **Configuration Panel** (좌측)
  - Date Range: Start/End date pickers
  - Region: Dropdown
  - Risk Level: Conservative / Moderate / Aggressive
  - Scoring Threshold: Slider (0-100)
  - Kelly Multiplier: Slider (0.1-1.0)
  - Max Positions: Number input (1-20)

- **Run Backtest Button**
  - Real-time progress bar (WebSocket)
  - Stage updates (Scanning → Filtering → Analysis → Simulation)

- **Results Panel** (우측)
  - Equity Curve Chart
  - Drawdown Chart
  - Trade List Table
  - Metrics Cards:
    - Total Return
    - Sharpe Ratio
    - Max Drawdown
    - Win Rate
    - Avg Win/Loss

- **Comparison Mode**
  - Side-by-side parameter comparison (A/B testing)
  - Best parameters highlighting

- **Strategy Deployment** (새로운 기능)
  - "Create Strategy Profile" 버튼
  - 전략 이름 및 설명 입력 모달
  - 최소 성과 기준 검증 (Sharpe ≥ 1.0, Return ≥ 10%, etc.)
  - 검증 통과 시 전략 프로파일 생성
  - "Activate Strategy" 버튼으로 spock.py에 즉시 적용

#### 5. Portfolio Management
- **Holdings Table**
  - Ticker, Name, Quantity, Avg Price, Current Price, P&L (%), Value
  - Real-time price updates (WebSocket)
  - Sort by P&L, Value, Ticker

- **Sector Allocation Pie Chart**
  - GICS 11 sectors
  - % of portfolio per sector

- **Position Details Modal** (클릭 시)
  - Trade history for this position
  - Current score and recommendation
  - Exit suggestion (trailing stop level)

- **Rebalancing Suggestions**
  - Overweight sectors (>40% limit)
  - Underweight sectors
  - Recommended actions

#### 6. Strategy Management (새로운 화면)
- **Active Strategy Panel** (상단)
  - 현재 활성 전략 표시
  - 전략 이름, 소스 백테스트 ID, 활성화 시간
  - 최근 30일 성과 지표 (Return, Sharpe, Drawdown, Win Rate)
  - "Deactivate" 버튼 (전략 비활성화)

- **Strategy List Table** (중앙)
  - 저장된 전략 프로파일 목록
  - Columns: Name, Risk Level, Sharpe Ratio, Total Return, Created At, Status
  - Actions:
    - Activate: 전략 활성화 (확인 모달)
    - Validate: 최근 30일 데이터로 검증 실행
    - Edit: 전략 파라미터 수정
    - Delete: 전략 삭제 (확인 모달)
    - Clone: 전략 복제 후 수정

- **Strategy History Panel** (하단)
  - 전략 변경 이력 타임라인
  - 각 이력: Action (created/activated/deactivated), Timestamp, User
  - 전략 설정 변경 사항 비교 (diff view)

- **Create New Strategy Button**
  - 수동 전략 생성 (백테스트 없이)
  - 파라미터 직접 입력
  - Dry-run 검증 필수

#### 7. Settings
- **API Configuration**
  - KIS API credentials (APP_KEY, APP_SECRET)
  - Secure storage with encryption
  - Connection test button
  - **Token Caching** (자동 관리):
    - 최초 토큰 발급 후 24시간 캐싱
    - CLI와 Web UI 간 토큰 공유
    - 자동 만료 감지 및 재발급
    - Token 상태 표시 (유효/만료/재발급 중)

- **Risk Profile**
  - Select: Conservative / Moderate / Aggressive
  - Custom thresholds (optional)
  - "Create Strategy from Profile" 버튼 (현재 설정으로 전략 생성)

- **Notification Settings**
  - Slack webhook URL
  - Email settings (SMTP)
  - Push notifications (optional)
  - Alert triggers:
    - New BUY signal
    - Stop loss triggered
    - Daily report
    - Strategy activation/deactivation

- **System Settings**
  - Database backup schedule
  - Log retention days
  - Auto-trading enable/disable
  - Strategy auto-validation schedule (매일/매주)

### 기술 스택 (로컬 환경)

#### Option A: Streamlit (⭐⭐⭐⭐⭐ 강력 추천)
```
streamlit==1.31.0          # Web UI framework
plotly==5.18.0             # Interactive charts
pandas==2.0.3              # 이미 설치됨 (data manipulation)
```

**장점**:
- ⚡ 개발 속도 매우 빠름 (2-3주)
- 🐍 Python 기반으로 기존 코드 100% 재사용
- 👤 단일 사용자에 최적화 (로컬 환경)
- 🔧 별도 백엔드 불필요 (SQLite 직접 접근)
- 📊 풍부한 차트 라이브러리 (plotly, matplotlib)
- 🔄 실시간 업데이트 (`st.rerun()`)

**단점**:
- 커스터마이징 제한적 (CSS/JS 수정 어려움)
- 대규모 앱에 부적합 (로컬이므로 문제 없음)

**실행**: `streamlit run streamlit_app/app.py` → http://localhost:8501

**추천 사유**:
- Week 9-10에 MVP 완성 가능
- 백테스트 검증 후 바로 사용 가능
- 유지보수 비용 최소화

---

#### Option B: Gradio (⭐⭐⭐⭐ AI/ML 친화적)
```
gradio==4.19.0             # ML-focused web UI
```

**장점**:
- 🤖 AI/ML 모델 통합 용이 (GPT-4 분석 표시)
- ⚡ Streamlit과 비슷한 개발 속도 (1-2주)
- 🎨 현대적인 UI 디자인 (자동 responsive)

**단점**:
- Streamlit보다 범용성 떨어짐

**추천 사유**: GPT-4 chart analysis 중심 UI라면 고려

---

#### Option C: FastAPI + React (⭐⭐⭐ 선택적, 고급 사용자)
```
# Backend
fastapi==0.109.0
uvicorn[standard]==0.27.0
websockets==12.0

# Frontend
react==18.2.0
typescript==5.3.3
vite==5.0.12
tailwindcss==3.4.1
recharts==2.10.4           # Charts
zustand==4.5.0             # State management
```

**장점**:
- 완전한 커스터마이징
- 확장성 높음 (나중에 AWS 전환 용이)

**단점**:
- ⏱️ 개발 시간 오래 걸림 (4-6주)
- 🏗️ 복잡도 증가 (프론트/백엔드 분리)
- 🔧 유지보수 비용 높음

**로컬 환경에서는 불필요한 것들**:
- ❌ PostgreSQL (SQLite 유지)
- ❌ Redis (로컬 메모리 캐싱으로 충분)
- ❌ Celery (단일 사용자, 비동기 불필요)
- ❌ JWT 인증 (본인만 사용)
- ❌ Rate limiting (필요 없음)

**추천하지 않는 이유**:
- 로컬 환경에서는 Streamlit이 충분함
- 개발 시간 대비 효과 미미
- AWS 전환 시점에 고려 (Phase 9+)

---

### 기술 스택 우선순위 요약

| 옵션 | 평점 | 개발 기간 | 추천 대상 | 비고 |
|-----|------|---------|---------|------|
| **Streamlit** | ⭐⭐⭐⭐⭐ | 2-3주 | 로컬 환경 (권장) | Python 기반, 빠른 개발 |
| **Gradio** | ⭐⭐⭐⭐ | 1-2주 | AI/ML 중심 UI | GPT-4 분석 중심 |
| **FastAPI + React** | ⭐⭐⭐ | 4-6주 | AWS 전환 시 | 로컬에서는 비추천 |

**최종 추천**: Streamlit → Week 9-10 완성 → 만족하면 계속 사용 → React 불필요

### KIS API Token Caching 구현

**목적**: KIS API 토큰 정책에 따라 24시간 유효한 토큰을 캐싱하여 CLI와 Web UI 간 재사용

#### Token 정책 (KIS API)
- **유효 기간**: 최초 발급 후 24시간
- **발급 제한**: 1일 1회 발급 권장 (과도한 재발급 시 계정 제재 위험)
- **사용 제한**: 20 req/sec, 1,000 req/min

#### 캐싱 전략

**Option A: File-based Cache (간단, 추천)** ⭐
```python
# modules/kis_token_cache.py
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict

class KISTokenCache:
    """KIS API 토큰 캐싱 (24시간 TTL)"""

    CACHE_FILE = Path.home() / '.spock' / 'kis_token_cache.json'
    TOKEN_TTL_HOURS = 24

    def __init__(self):
        self.CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    def get_token(self) -> Optional[str]:
        """캐싱된 토큰 조회 (유효한 경우)"""
        if not self.CACHE_FILE.exists():
            return None

        try:
            with open(self.CACHE_FILE, 'r') as f:
                cache = json.load(f)

            # 만료 시간 체크
            issued_at = datetime.fromisoformat(cache['issued_at'])
            expires_at = issued_at + timedelta(hours=self.TOKEN_TTL_HOURS)

            if datetime.now() < expires_at:
                return cache['access_token']
            else:
                return None  # 만료됨
        except Exception:
            return None

    def save_token(self, access_token: str) -> None:
        """토큰 캐싱 (24시간 TTL)"""
        cache = {
            'access_token': access_token,
            'issued_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(hours=self.TOKEN_TTL_HOURS)).isoformat()
        }

        with open(self.CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)

        # Secure permissions (600)
        self.CACHE_FILE.chmod(0o600)

    def invalidate(self) -> None:
        """캐시 무효화 (수동 재발급 시)"""
        if self.CACHE_FILE.exists():
            self.CACHE_FILE.unlink()

    def get_status(self) -> Dict[str, any]:
        """토큰 상태 조회 (UI 표시용)"""
        if not self.CACHE_FILE.exists():
            return {'status': 'no_token', 'message': '토큰 없음'}

        try:
            with open(self.CACHE_FILE, 'r') as f:
                cache = json.load(f)

            issued_at = datetime.fromisoformat(cache['issued_at'])
            expires_at = datetime.fromisoformat(cache['expires_at'])
            now = datetime.now()

            if now < expires_at:
                remaining = (expires_at - now).total_seconds() / 3600
                return {
                    'status': 'valid',
                    'issued_at': cache['issued_at'],
                    'expires_at': cache['expires_at'],
                    'remaining_hours': round(remaining, 1),
                    'message': f'유효 (남은 시간: {remaining:.1f}시간)'
                }
            else:
                return {
                    'status': 'expired',
                    'expired_at': cache['expires_at'],
                    'message': '만료됨 (재발급 필요)'
                }
        except Exception as e:
            return {'status': 'error', 'message': f'오류: {str(e)}'}
```

**Usage Example**:
```python
# modules/kis_auth.py
from modules.kis_token_cache import KISTokenCache

class KISAuth:
    """KIS API 인증 with 토큰 캐싱"""

    def __init__(self, app_key: str, app_secret: str):
        self.app_key = app_key
        self.app_secret = app_secret
        self.cache = KISTokenCache()

    def get_access_token(self, force_refresh: bool = False) -> str:
        """Access token 조회 (캐싱 우선)"""

        # 강제 재발급이 아니면 캐시 확인
        if not force_refresh:
            cached_token = self.cache.get_token()
            if cached_token:
                return cached_token

        # 새 토큰 발급
        token = self._request_new_token()

        # 캐싱
        self.cache.save_token(token)

        return token

    def _request_new_token(self) -> str:
        """KIS API 토큰 발급 (실제 API 호출)"""
        # OAuth 2.0 토큰 발급 로직
        ...
```

**Option B: SQLite Cache (확장 가능)**
```python
# modules/db_manager_sqlite.py (추가)
def save_kis_token(self, access_token: str, expires_in_hours: int = 24):
    """KIS API 토큰 캐싱"""
    conn = self._get_connection()
    cursor = conn.cursor()

    issued_at = datetime.now()
    expires_at = issued_at + timedelta(hours=expires_in_hours)

    cursor.execute('''
        INSERT OR REPLACE INTO kis_token_cache
        (id, access_token, issued_at, expires_at, updated_at)
        VALUES (1, ?, ?, ?, ?)
    ''', (access_token, issued_at, expires_at, datetime.now()))

    conn.commit()
    conn.close()

def get_kis_token(self) -> Optional[str]:
    """유효한 토큰 조회"""
    conn = self._get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT access_token, expires_at
        FROM kis_token_cache
        WHERE id = 1
    ''')

    row = cursor.fetchone()
    conn.close()

    if row and datetime.now() < row[1]:
        return row[0]
    return None
```

#### CLI 통합

```python
# cli/commands/scan.py
from modules.kis_auth import KISAuth
from modules.kis_token_cache import KISTokenCache

class ScanCommand(BaseCommand):
    def execute(self, region: str, min_score: int = 70):
        # 캐싱된 토큰 사용
        auth = KISAuth(app_key, app_secret)
        token = auth.get_access_token()  # 자동으로 캐시 확인

        # Token 상태 표시 (verbose 모드)
        cache_status = auth.cache.get_status()
        if cache_status['status'] == 'valid':
            print(f"✅ Using cached token ({cache_status['remaining_hours']}h remaining)")

        # 스캔 로직
        ...
```

#### Web UI 통합 (Streamlit)

```python
# streamlit_app/pages/2_Scanner.py
import streamlit as st
from modules.kis_auth import KISAuth

# Sidebar: Token 상태 표시
with st.sidebar:
    st.subheader("🔐 KIS API Token")

    auth = KISAuth(app_key, app_secret)
    status = auth.cache.get_status()

    if status['status'] == 'valid':
        st.success(f"✅ {status['message']}")
        st.caption(f"만료: {status['expires_at']}")
    elif status['status'] == 'expired':
        st.warning(f"⚠️ {status['message']}")
        if st.button("🔄 토큰 재발급"):
            token = auth.get_access_token(force_refresh=True)
            st.success("토큰 재발급 완료")
            st.rerun()
    else:
        st.info("토큰 없음 (자동 발급 예정)")

    # 수동 재발급 버튼
    if st.button("강제 재발급"):
        auth.cache.invalidate()
        st.rerun()

# Main: 스캔 기능
st.title("📊 Stock Scanner")
...
```

#### Web UI 통합 (FastAPI + React)

**Backend (FastAPI)**:
```python
# api/dependencies.py
from modules.kis_auth import KISAuth

async def get_kis_token() -> str:
    """Dependency: KIS API 토큰 (캐싱)"""
    auth = KISAuth(app_key, app_secret)
    return auth.get_access_token()

# api/routers/scanner.py
@router.post("/scan")
async def scan_stocks(
    request: ScanRequest,
    token: str = Depends(get_kis_token)
):
    """종목 스캔 (토큰 자동 캐싱)"""
    ...
    return results

# api/routers/auth.py
@router.get("/token/status")
async def get_token_status():
    """토큰 상태 조회"""
    cache = KISTokenCache()
    return cache.get_status()

@router.post("/token/refresh")
async def refresh_token():
    """토큰 강제 재발급"""
    auth = KISAuth(app_key, app_secret)
    token = auth.get_access_token(force_refresh=True)
    return {"status": "success", "message": "토큰 재발급 완료"}
```

**Frontend (React)**:
```typescript
// src/components/TokenStatus.tsx
import { useQuery, useMutation } from '@tanstack/react-query';

export function TokenStatus() {
  const { data: status } = useQuery({
    queryKey: ['token-status'],
    queryFn: () => fetch('/api/token/status').then(r => r.json()),
    refetchInterval: 60000 // 1분마다 체크
  });

  const refreshMutation = useMutation({
    mutationFn: () => fetch('/api/token/refresh', { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries(['token-status'])
  });

  if (status?.status === 'valid') {
    return (
      <div className="badge badge-success">
        ✅ Token valid ({status.remaining_hours}h)
      </div>
    );
  } else if (status?.status === 'expired') {
    return (
      <button onClick={() => refreshMutation.mutate()}>
        🔄 Refresh Token
      </button>
    );
  }

  return <div className="badge badge-warning">⚠️ No token</div>;
}
```

#### 보안 고려사항

1. **파일 권한**: `~/.spock/kis_token_cache.json` 파일은 600 권한 (소유자만 읽기/쓰기)
2. **암호화 (선택)**: 민감한 환경에서는 토큰을 암호화하여 저장
3. **Git 제외**: `.gitignore`에 `~/.spock/` 추가하여 실수로 커밋 방지
4. **로그 제외**: 토큰 값은 절대 로그에 기록하지 않음

#### 트러블슈팅

**문제 1**: CLI와 Web UI에서 다른 토큰 사용
- **원인**: 캐시 파일 경로가 다름
- **해결**: `Path.home() / '.spock'` 공통 경로 사용

**문제 2**: 토큰 만료 후 자동 재발급 안 됨
- **원인**: `get_access_token()` 강제 재발급 플래그 미사용
- **해결**: 만료 감지 시 자동으로 `force_refresh=True` 호출

**문제 3**: KIS API 계정 제재
- **원인**: 과도한 토큰 재발급 (1일 여러 번)
- **해결**: 캐싱 로직 검증, 24시간 TTL 엄격 준수

### 아키텍처 설계 (로컬 환경)

**Option A: Streamlit (간단)** ⭐ 추천
```
┌─────────────────────────────────────────┐
│          User (본인)                     │
├─────────────────┬───────────────────────┤
│  CLI (Terminal) │  Web UI (Browser)     │
│                 │  localhost:8501       │
└────────┬────────┴──────────┬────────────┘
         │                   │
         └───────────────────┘
                  │
         ┌────────▼─────────┐
         │  Streamlit App   │
         │  (Python)        │
         ├──────────────────┤
         │  직접 호출:       │
         │  - StockScanner  │
         │  - Analyzer      │
         │  - Backtester    │
         └────────┬─────────┘
                  │
         ┌────────▼─────────┐
         │  SQLite          │
         │  (로컬 파일)      │
         └──────────────────┘
```

**Option B: FastAPI + React (복잡)** - 선택적
```
┌─────────────────────────────────────────┐
│          User (본인)                     │
├─────────────────┬───────────────────────┤
│  CLI (Terminal) │  Web UI (Browser)     │
│                 │  localhost:5173       │
└────────┬────────┴──────────┬────────────┘
         │                   │
         └───────────────────┘
                  │
         ┌────────▼─────────┐
         │  FastAPI         │
         │  localhost:8000  │
         ├──────────────────┤
         │  REST Endpoints  │
         │  WebSocket       │
         └────────┬─────────┘
                  │
         ┌────────▼─────────┐
         │  Spock Engine    │
         │  (기존 modules)  │
         └────────┬─────────┘
                  │
         ┌────────▼─────────┐
         │  SQLite          │
         └──────────────────┘
```

### 프로젝트 구조

```
api/
├── main.py                    # FastAPI app entry point
├── dependencies.py            # Shared dependencies
├── auth.py                    # JWT authentication
├── routers/
│   ├── __init__.py
│   ├── scanner.py            # POST /api/scanner/scan
│   ├── analysis.py           # GET /api/analysis/{ticker}
│   ├── backtest.py           # POST /api/backtest/run
│   ├── strategy.py           # 🆕 POST /api/strategy/create, /activate, /validate
│   ├── portfolio.py          # GET /api/portfolio/holdings
│   └── users.py              # POST /api/users/register
├── services/
│   ├── __init__.py
│   ├── scanner_service.py    # ScannerService
│   ├── analysis_service.py   # AnalysisService
│   ├── backtest_service.py   # BacktestService
│   ├── strategy_service.py   # 🆕 StrategyService
│   └── portfolio_service.py  # PortfolioService
├── models/
│   ├── __init__.py
│   ├── user.py               # SQLAlchemy User model
│   ├── portfolio.py          # Portfolio model
│   ├── backtest.py           # Backtest result model
│   └── strategy.py           # 🆕 Strategy profile model
├── schemas/
│   ├── __init__.py
│   ├── scanner.py            # Pydantic request/response
│   ├── analysis.py
│   ├── backtest.py
│   └── strategy.py           # 🆕 Strategy schemas
├── tasks/
│   ├── __init__.py
│   ├── celery_app.py         # Celery configuration
│   ├── backtest_tasks.py     # Async backtest tasks
│   └── strategy_tasks.py     # 🆕 Async strategy validation tasks
└── websockets/
    ├── __init__.py
    ├── realtime.py           # WebSocket for real-time data
    └── backtest.py           # WebSocket for backtest progress

web-ui/                        # React frontend (Option B)
├── src/
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── Scanner.tsx
│   │   ├── Analysis.tsx
│   │   ├── Backtest.tsx
│   │   ├── Strategy.tsx      # 🆕 Strategy management page
│   │   ├── Portfolio.tsx
│   │   └── Settings.tsx
│   ├── components/
│   │   ├── Chart.tsx
│   │   ├── StockTable.tsx
│   │   ├── ScoreCard.tsx
│   │   ├── FilterPanel.tsx
│   │   ├── ProgressBar.tsx
│   │   ├── StrategyCard.tsx       # 🆕 Strategy profile card
│   │   ├── StrategyModal.tsx      # 🆕 Create/Edit strategy modal
│   │   └── StrategyTimeline.tsx   # 🆕 Strategy history timeline
│   ├── services/
│   │   ├── api.ts            # FastAPI client (axios)
│   │   ├── strategy.ts       # 🆕 Strategy API client
│   │   └── websocket.ts      # WebSocket client
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useRealtime.ts
│   │   ├── useBacktest.ts
│   │   └── useStrategy.ts    # 🆕 Strategy state management hook
│   ├── store/
│   │   ├── authStore.ts      # Zustand auth state
│   │   ├── portfolioStore.ts
│   │   ├── strategyStore.ts  # 🆕 Strategy state
│   │   └── scannerStore.ts
│   ├── App.tsx
│   └── main.tsx
├── package.json
├── tsconfig.json
└── vite.config.ts

streamlit_app/                 # Streamlit MVP (Option A)
├── app.py                     # Main entry point
├── pages/
│   ├── 1_Dashboard.py
│   ├── 2_Scanner.py
│   ├── 3_Analysis.py
│   ├── 4_Backtest.py
│   ├── 5_Strategy.py         # 🆕 Strategy management page
│   └── 6_Portfolio.py
│   └── 7_Settings.py
└── components/
    ├── charts.py
    ├── tables.py
    └── strategy.py           # 🆕 Strategy UI components

cli/                           # CLI Tool (Phase 7)
├── commands/
│   ├── strategy.py           # 🆕 Strategy deployment commands
│   └── ...
└── ...
```

### 개발 태스크

**Week 1: Core Engine Refactoring**
- [ ] SpockOrchestrator → SpockEngine 분리
- [ ] Service Layer 구현 (Scanner, Analysis, Backtest, Portfolio, **Strategy**)
- [ ] Database schema 확장 (strategy_profiles, strategy_history, strategy_performance)
- [ ] 각 서비스 단위 테스트 작성

**Week 2: FastAPI Backend MVP**
- [ ] FastAPI 프로젝트 구조 생성
- [ ] `/api/scanner/scan` 엔드포인트 구현
- [ ] `/api/analysis/{ticker}` 엔드포인트 구현
- [ ] `/api/backtest/run` 엔드포인트 구현 (Celery 비동기)
- [ ] **`/api/strategy/create`** 엔드포인트 구현 (백테스트에서 전략 생성)
- [ ] **`/api/strategy/activate`** 엔드포인트 구현 (spock.py 설정 업데이트)
- [ ] **`/api/strategy/validate`** 엔드포인트 구현 (dry-run 검증)
- [ ] WebSocket `/ws/backtest` 구현 (진행 상황 push)

**Week 3-4: Streamlit MVP**
- [ ] Streamlit 프로젝트 구조 생성
- [ ] Dashboard 페이지 (포트폴리오 요약)
- [ ] Scanner 페이지 (필터 + 테이블)
- [ ] Analysis 페이지 (차트 + 점수)
- [ ] Backtest 페이지 (설정 + 결과 + **전략 생성 버튼**)
- [ ] **Strategy 페이지** (전략 관리, 활성화, 검증, 이력)
- [ ] Portfolio 페이지 (보유 종목, 섹터 분석)
- [ ] Settings 페이지 (API 설정, 리스크 프로파일, **전략 자동검증**)
- [ ] 내부 베타 테스트 (5명)

**Week 5-6: React Frontend (Optional)**
- [ ] Vite + React + TypeScript 프로젝트 생성
- [ ] UI 컴포넌트 라이브러리 선택 (shadcn/ui 추천)
- [ ] Dashboard 페이지 구현
- [ ] Scanner 페이지 구현
- [ ] Backtest 페이지 구현 (전략 배포 기능 포함)
- [ ] **Strategy 페이지 구현** (전략 카드, 타임라인, 모달)
- [ ] TradingView 차트 통합
- [ ] WebSocket 실시간 업데이트 구현
- [ ] Strategy state management (Zustand)

### 로컬 환경 최적화

#### 성능 최적화 (단일 사용자)
- **SQLite 최적화**:
  - WAL 모드 활성화 (동시 읽기/쓰기)
  - 인덱스 최적화 (ticker, region, date)
  - VACUUM 정기 실행

- **메모리 캐싱** (Redis 불필요):
  - Python dict 기반 in-memory cache
  - 분석 결과 캐싱 (session 동안 유효)
  - LRU cache decorator 활용

- **백테스트 최적화**:
  - Streamlit: `@st.cache_data` 활용
  - FastAPI: functools.lru_cache 활용
  - 병렬 처리: multiprocessing (로컬 CPU 활용)

#### 백업 및 데이터 관리
```bash
# 로컬 백업 (간단)
cp data/spock_local.db data/backups/spock_$(date +%Y%m%d).db

# 자동 백업 (cron)
0 2 * * * cp ~/spock/data/spock_local.db ~/spock/data/backups/spock_$(date +\%Y\%m\%d).db
```

### 성공 기준 (로컬 환경)

**Phase 8 완료 조건**:
- ✅ 7개 핵심 화면 모두 구현 (Dashboard, Scanner, Analysis, Backtest, **Strategy**, Portfolio, Settings)
- ✅ 백테스트 전략을 프로덕션 파이프라인에 안전하게 배포 가능
- ✅ 전략 버전 관리 및 롤백 지원
- ✅ 전략 검증 (dry-run) 및 성과 모니터링
- ✅ CLI와 Web UI 간 전략 공유 (동일 database 사용)
- ✅ 반응형 UI (데스크탑 최적화, 모바일은 선택)
- ✅ 로컬 실행 안정성 (99%+ uptime)
- ✅ 백테스트 성능 (<5분 for 1년 데이터)
- ✅ 문서화 (로컬 설치 가이드, 사용 매뉴얼, **전략 배포 가이드**)

### 예상 리소스 (로컬 환경)

**시스템 요구사항**:
- **CPU**: 4코어 이상 (백테스트 병렬 처리)
- **RAM**: 8GB 이상 (대량 데이터 분석)
- **Storage**: 50GB 여유 공간 (5년치 OHLCV 데이터)
- **OS**: macOS, Linux, Windows 10+

**비용**:
- **초기 비용**: $0 (기존 PC 활용)
- **월간 비용**: ~$2 (전기세)
- **연간 비용**: ~$24
- **5년 총비용**: ~$120

**개발 시간**:
- CLI Tool: 2주 (1 developer)
- Web UI MVP (Streamlit): 2-3주 (1 developer)
- Web UI Production (React): 4-6주 (1 frontend + 1 backend developer) - 선택적

---

## Phase 9+: Advanced Features (미래 확장)

### AWS 클라우드 배포 (다중 사용자 서비스 전환)

**AWS 배포가 의미 있는 경우**:
1. **다중 사용자 서비스**: 가족, 친구, 커뮤니티에게 서비스 제공
2. **24/7 자동 실행**: 본인 PC를 끌 수 없는 경우
3. **SaaS 비즈니스**: 월 구독료 기반 서비스

**필요한 변경 사항**:
- **Database**: SQLite → PostgreSQL (다중 사용자 동시 접속)
- **Cache**: In-memory → Redis (세션 관리, 분석 결과 캐싱)
- **Auth**: 로컬 접근 → JWT 기반 인증
- **Async**: 동기 실행 → Celery 비동기 작업 큐
- **Infra**: 로컬 → AWS (EC2, RDS, ElastiCache, S3)

**예상 비용**:
- **월간**: $60-80
- **연간**: $720-960
- **5년**: $3,600-4,800

**대안 (저비용 24/7 실행)**:
- **라즈베리파이**: $50 (일회성), 전기세 ~$5/년
- **중고 미니PC**: $100-200, 전기세 ~$10/년

### 모바일 앱 (React Native)
- iOS/Android 네이티브 앱
- Push notifications
- Face ID / Touch ID 인증

### 소셜 기능
- 커뮤니티 포럼 (종목 토론)
- 전략 공유 (공개 백테스트 결과)
- 리더보드 (수익률 순위)

### 고급 분석 도구
- 몬테카를로 시뮬레이션
- 시나리오 분석 (최악/최선/기대 시나리오)
- 포트폴리오 최적화 (Efficient Frontier)

### AI 어시스턴트
- 자연어 쿼리 ("삼성전자 분석해줘", "오늘 추천 종목은?")
- GPT-4 기반 대화형 분석
- 음성 명령 (Siri/Google Assistant 통합)

---

## 참고 자료

### 유사 제품 벤치마킹
- **TradingView**: 차트 분석, 커뮤니티, 알림
- **QuantConnect**: 백테스트, 알고리즘 트레이딩, IDE
- **Alpaca**: API 기반 트레이딩, 백테스트
- **Interactive Brokers**: 전문 트레이더 플랫폼

### 기술 레퍼런스
- FastAPI: https://fastapi.tiangolo.com/
- Streamlit: https://docs.streamlit.io/
- React + TailwindCSS: https://tailwindcss.com/docs
- TradingView Charts: https://www.tradingview.com/widget/
- Celery: https://docs.celeryq.dev/

### 관련 문서
- `spock_PRD.md`: 제품 요구사항 정의서
- `spock_architecture.mmd`: 시스템 아키텍처
- `GLOBAL_MARKET_EXPANSION.md`: 글로벌 시장 확장 전략

---

## 요약

### Phase 7: CLI Tool + TUI (2-3주)
- **Week 1-5**: CLI Command Mode
  - **기술 스택**: typer + rich
  - **핵심 명령어**: scan, analyze, backtest, **strategy (create/validate/activate/status)**, compare
  - **특징**: 배치 작업, 스크립트 자동화, 빠른 실행
- **Week 6-7**: TUI (Terminal User Interface)
  - **기술 스택**: rich (Live display, Tables, Panels)
  - **기능**: 실시간 포트폴리오 모니터링, 키보드 네비게이션
  - **특징**: SSH 원격 가능, 실시간 업데이트
- **공통 특징**: Strategy deployment, Session context, Command history
- **환경**: 로컬 실행 (터미널)

### Phase 8: Web UI (2-3주, Streamlit 권장)
- **⭐ 강력 추천**: Streamlit (2-3주, ⭐⭐⭐⭐⭐)
  - Python 기반, 기존 코드 100% 재사용
  - 별도 백엔드 불필요, SQLite 직접 접근
  - Week 9-10 완성 목표
- **선택 1**: Gradio (1-2주, ⭐⭐⭐⭐) - GPT-4 분석 중심 UI
- **선택 2**: FastAPI + React (4-6주, ⭐⭐⭐) - AWS 전환 시 고려
- **데이터베이스**: SQLite 유지 (PostgreSQL 불필요)
- **핵심 화면**: Dashboard, Scanner, Analysis, Backtest, **Strategy**, Portfolio, Settings (7개)
- **전략 배포**: 백테스트 → 전략 프로파일 생성 → 검증 → spock.py 적용
- **환경**: 로컬 실행 (http://localhost:8501)
- **비용**: $0 (AWS 배포 불필요)

### 핵심 원칙: "CLI First, WebUI Later"
- Week 1-5: CLI로 백엔드 로직 안정화
- Week 6-7: TUI로 실시간 모니터링
- Week 9+: WebUI (Streamlit)로 시각화 및 사용성 개선

### 전략 배포 워크플로우 (CLI & Web UI 공통)
1. **백테스트 실행**: 다양한 파라미터로 백테스트 수행
2. **전략 생성**: 성과 검증된 백테스트 → 전략 프로파일 생성
3. **검증**: 최근 30일 데이터로 dry-run 시뮬레이션
4. **활성화**: spock.py 설정 파일 자동 업데이트
5. **모니터링**: 실거래 성과 추적 및 편차 감지
6. **롤백**: 이전 전략으로 복구 (버전 관리)

### Phase 9+: 확장 옵션
- **AWS 배포**: 다중 사용자 서비스 전환 시
- **모바일 앱**: iOS/Android
- **고급 분석**: 몬테카를로, Efficient Frontier
- **AI 어시스턴트**: 자연어 쿼리
- **A/B 테스트**: 다중 전략 동시 실행 및 성과 비교

---

**최종 업데이트**: 2025-10-19
**상태**: 📋 Backlog (Core system 완성 후 재검토)
**환경 전략**: 로컬 우선 (AWS는 Phase 9+ 확장 옵션)
**핵심 추가 기능**: 백테스트 전략 배포 시스템 (CLI + Web UI)

**주요 업데이트 내역** (2025-10-19):
- ✅ CLI vs TUI vs WebUI 개념 명확화 (GUI 제외)
- ✅ Phase 7 타임라인 세분화 (Week 1-5 CLI, Week 6-7 TUI)
- ✅ WebUI 기술 스택 우선순위 재정립 (Streamlit ⭐⭐⭐⭐⭐)
- ✅ "CLI First, WebUI Later" 핵심 원칙 추가
- ✅ 비교표 추가 (CLI/TUI/WebUI/GUI)
- ✅ Desktop GUI 제외 사유 명확화
