# CLI/GUI 구현 전략 및 시점 분석

**작성일**: 2025-10-19
**목적**: 퀀트 트레이딩 시스템에서 CLI와 GUI의 최적 구현 시점 결정

---

## Executive Summary

**권장 구현 순서**:
1. **Phase 1-3 (현재~Week 4)**: CLI 기반 개발 (데이터 수집, 지표 산출, 백테스팅)
2. **Phase 4 (Week 5-6)**: 백테스팅 결과 시각화 CLI 도구
3. **Phase 5 (Week 7-8)**: 실시간 트레이딩 CLI 모니터링
4. **Phase 6 (Week 9-12)**: GUI 구현 (대시보드, 차트, 알림)

**핵심 원칙**: "CLI First, GUI Later" - 백엔드 로직이 안정화된 후 프론트엔드 구현

---

## 1. 퀀트 시스템 개발 단계별 UI/UX 요구사항

### Phase 1: Raw 데이터 수집 (Week 1-2)
**현재 진행 중**

**작업 내용**:
- KIS API 해외주식 데이터 수집
- SQLite 데이터베이스 구축
- 250일 OHLCV 데이터 수집 (6개 마켓)

**UI/UX 요구사항**:
- ✅ **CLI로 충분**: 진행률 표시, 에러 로깅
- ❌ **GUI 불필요**: 일회성 작업, 자동화 가능
- **필요 도구**: Progress bar, logging output

**CLI 예시**:
```bash
# 데이터 수집 진행률 표시
python3 spock.py --collect-data --region US --days 250

[████████████████░░░░░░░░] 67% (4,372/6,532 tickers)
✅ AAPL: 250 days collected
✅ MSFT: 250 days collected
⚠️  ZZZZZ: No data (delisted)
```

---

### Phase 2: 기술적 지표 산출 (Week 3)

**작업 내용**:
- LayeredScoringEngine 통합
- MA, RSI, MACD, BB, ATR 계산
- 100점 스코어링 시스템

**UI/UX 요구사항**:
- ✅ **CLI로 충분**: 배치 처리, 로그 확인
- ❌ **GUI 불필요**: 백그라운드 계산, 사용자 개입 최소
- **필요 도구**: Batch progress, validation reports

**CLI 예시**:
```bash
# 지표 산출 및 스코어링
python3 spock.py --calculate-indicators --region US

📊 Technical Indicators Calculation
Batch 1/66: 100 tickers processed (1.2s)
✅ LayeredScoringEngine: 6,532 stocks scored
   - 127 stocks > 70 points (BUY)
   - 543 stocks 50-70 points (WATCH)
   - 5,862 stocks < 50 points (AVOID)
```

---

### Phase 3: 백테스팅 (Week 4-5)

**작업 내용**:
- Weinstein Stage 2 전략 검증
- VCP 패턴 백테스팅
- Kelly Formula 포지션 사이징 검증

**UI/UX 요구사항**:
- ⚠️ **CLI 기본 + 시각화 필요**: 결과 분석에 차트 필요
- ✅ **간단한 플롯 CLI 도구**: matplotlib 기반 차트 생성
- ❌ **실시간 GUI 불필요**: 배치 결과 확인용

**CLI + 시각화 예시**:
```bash
# 백테스팅 실행 및 결과 시각화
python3 spock.py --backtest --strategy stage2 --period 2023-2024

📈 Backtesting Results (2023-01-01 ~ 2024-12-31)
Total Return: +23.4% (KOSPI: +8.2%)
Sharpe Ratio: 1.82
Max Drawdown: -12.3%
Win Rate: 58.3% (62/106 trades)

📊 Generating performance charts...
✅ equity_curve.png
✅ drawdown_chart.png
✅ monthly_returns.png
```

**이 단계에서 필요한 시각화**:
- Equity curve (수익률 곡선)
- Drawdown chart (낙폭 차트)
- Monthly returns heatmap (월별 수익률)
- Trade distribution (거래 분포도)

**구현 방법**:
```python
# CLI 기반 시각화 도구
python3 tools/visualize_backtest.py --results backtest_results.json

# matplotlib로 PNG 생성 → 브라우저에서 확인
# 또는 rich 라이브러리로 터미널 차트
```

---

### Phase 4: 실시간 트레이딩 모니터링 (Week 6-7)

**작업 내용**:
- KIS API 주문 실행
- 포트폴리오 모니터링
- 실시간 손익 추적

**UI/UX 요구사항**:
- ⚠️ **CLI 실시간 모니터링 필요**: 거래 중 상태 확인
- ✅ **TUI (Terminal UI) 권장**: `rich`, `textual` 라이브러리
- ❌ **Web GUI 선택사항**: 편의성은 좋지만 필수 아님

**TUI (Terminal UI) 예시** (rich 라이브러리):
```bash
python3 spock.py --monitor

┌─────────────────────────────────────────────────────────────┐
│ 🚀 Spock Trading Monitor - 2025-10-19 14:32:45            │
├─────────────────────────────────────────────────────────────┤
│ 💰 Portfolio                                                │
│   Total Value: ₩102,345,678 (+2.35% today)                 │
│   Cash: ₩23,456,789 (22.9%)                                │
│   Positions: 8 stocks                                       │
├─────────────────────────────────────────────────────────────┤
│ 📊 Active Positions                                         │
│   AAPL (US)  | 100 shares | +5.2% | $18,234                │
│   005930 (KR)| 50 shares  | +3.1% | ₩3,850,000            │
│   ...                                                       │
├─────────────────────────────────────────────────────────────┤
│ 🔔 Alerts                                                   │
│   [14:30] MSFT triggered trailing stop (sell signal)       │
│   [14:25] GOOGL entered Stage 3 (profit taking)            │
└─────────────────────────────────────────────────────────────┘

Press 'q' to quit, 'r' to refresh
```

**TUI 구현 시점**: Week 6-7 (실시간 트레이딩 직전)

---

### Phase 5: Web GUI 대시보드 (Week 9-12, Optional)

**작업 내용**:
- 포트폴리오 대시보드
- 실시간 차트 (TradingView 스타일)
- 백테스팅 결과 인터랙티브 분석
- 알림 및 설정 관리

**UI/UX 요구사항**:
- ✅ **편의성 향상**: 멀티 차트, 드릴다운 분석
- ❌ **필수 아님**: CLI/TUI로도 운영 가능
- **구현 비용**: 개발 4주 + 유지보수 지속

**GUI 기술 스택 후보**:

#### Option 1: Streamlit (권장) - 빠른 프로토타이핑
```python
# 장점: Python only, 빠른 개발
# 단점: 커스터마이징 제한적
import streamlit as st

st.title("Spock Trading Dashboard")
st.metric("Total Return", "+23.4%", delta="+2.1%")
st.line_chart(equity_curve)
```

**개발 시간**: 1-2주
**유지보수**: 낮음
**적합성**: ⭐⭐⭐⭐⭐

#### Option 2: Flask + React - 완전한 커스터마이징
```python
# 장점: 완전한 제어, 프로덕션급
# 단점: 개발 시간 4주+, React 학습 필요
@app.route('/api/portfolio')
def get_portfolio():
    return jsonify(portfolio_data)
```

**개발 시간**: 4-6주
**유지보수**: 높음
**적합성**: ⭐⭐⭐ (Over-engineering 위험)

#### Option 3: Gradio - AI/ML 친화적
```python
# 장점: GPT-4 차트 분석 결과 표시 용이
# 단점: 금융 특화 기능 부족
import gradio as gr

gr.Interface(
    fn=analyze_stock,
    inputs="text",
    outputs="plot"
).launch()
```

**개발 시간**: 1주
**유지보수**: 낮음
**적합성**: ⭐⭐⭐⭐

---

## 2. CLI/GUI 구현 우선순위 매트릭스

| 개발 단계 | CLI 필요성 | TUI 필요성 | GUI 필요성 | 권장 구현 |
|----------|----------|-----------|-----------|----------|
| **데이터 수집** | ⭐⭐⭐⭐⭐ | ⭐ | ☆ | CLI only |
| **지표 산출** | ⭐⭐⭐⭐⭐ | ⭐ | ☆ | CLI only |
| **백테스팅** | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | CLI + matplotlib |
| **실시간 모니터링** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | TUI (rich) |
| **포트폴리오 분석** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | GUI (Streamlit) |

---

## 3. 권장 구현 로드맵

### Week 1-2: CLI 기반 데이터 파이프라인 (현재)
**구현 항목**:
- ✅ `spock.py --collect-data` - 데이터 수집
- ✅ `spock.py --cleanup-db` - 데이터베이스 유지보수
- ✅ Progress bars (tqdm)
- ✅ Structured logging

**도구**:
- `argparse` - CLI 인자 파싱
- `tqdm` - 진행률 표시
- `logging` - 구조화된 로그

### Week 3-4: CLI + 지표 산출
**구현 항목**:
- `spock.py --calculate-indicators --region US`
- `spock.py --score-stocks --min-score 70`
- Batch processing logs

**도구**:
- `pandas` - 데이터 처리
- `logging` - 배치 처리 로그

### Week 5: CLI + 백테스팅 시각화
**구현 항목**:
- `spock.py --backtest --strategy stage2`
- `tools/visualize_backtest.py` - 정적 차트 생성
- Performance report (Markdown)

**도구**:
- `matplotlib` - 정적 차트
- `seaborn` - 통계 차트
- `Markdown` - 리포트 생성

### Week 6-7: TUI 실시간 모니터링 ⭐ **중요 전환점**
**구현 항목**:
- `spock.py --monitor` - 실시간 TUI 모니터링
- Live portfolio tracking
- Real-time alerts

**도구**:
- `rich` - 터미널 UI 라이브러리
  - Tables, progress bars, live updates
  - Color-coded outputs
  - Live refresh (1초 간격)

**예시 코드**:
```python
from rich.console import Console
from rich.table import Table
from rich.live import Live
import time

console = Console()

def generate_portfolio_table():
    table = Table(title="Portfolio")
    table.add_column("Ticker", style="cyan")
    table.add_column("Shares", justify="right")
    table.add_column("P&L", justify="right", style="green")

    for position in portfolio.get_positions():
        table.add_row(
            position['ticker'],
            str(position['shares']),
            f"+{position['pnl']:.2f}%"
        )
    return table

with Live(generate_portfolio_table(), refresh_per_second=1) as live:
    while True:
        time.sleep(1)
        live.update(generate_portfolio_table())
```

### Week 9-12: GUI 대시보드 (Optional) ⭐ **편의성 향상**
**구현 항목**:
- Streamlit 대시보드
- Interactive charts (Plotly)
- 백테스팅 결과 드릴다운 분석
- 알림 설정 UI

**도구**:
- `streamlit` - 웹 대시보드 프레임워크
- `plotly` - 인터랙티브 차트
- `pandas` - 데이터 처리

**예시 코드**:
```python
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="Spock Dashboard", layout="wide")

# Sidebar
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Portfolio", "Backtest", "Settings"])

if page == "Portfolio":
    st.title("📊 Portfolio Dashboard")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Value", "₩102M", "+2.35%")
    col2.metric("Daily P&L", "+₩2.4M", "+2.1%")
    col3.metric("Win Rate", "58.3%", "+1.2%")

    # Equity curve chart
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=equity, name="Portfolio"))
    st.plotly_chart(fig, use_container_width=True)
```

---

## 4. CLI vs TUI vs GUI 비교

| 특성 | CLI | TUI (rich) | GUI (Streamlit) |
|-----|-----|-----------|----------------|
| **개발 시간** | 1-2일 | 1주 | 2-4주 |
| **유지보수** | 낮음 | 낮음 | 중간 |
| **실시간 업데이트** | 불가능 | 가능 (1초) | 가능 (실시간) |
| **차트 품질** | 정적 PNG | 터미널 차트 | 인터랙티브 |
| **원격 접속** | SSH 가능 | SSH 가능 | 웹 브라우저 |
| **자동화** | 매우 쉬움 | 불가능 | 어려움 |
| **적합 사용자** | 개발자 | 개발자 | 일반 사용자 |

---

## 5. 최종 권장사항

### Phase별 UI/UX 전략

**Phase 1-3 (Week 1-5): CLI Only**
- 데이터 수집, 지표 산출, 백테스팅
- `argparse` + `logging` + `tqdm`
- **이유**: 백엔드 로직 집중, 빠른 개발

**Phase 4 (Week 5): CLI + 정적 시각화**
- 백테스팅 결과 차트 (matplotlib)
- Markdown 리포트 생성
- **이유**: 전략 검증에 시각화 필수

**Phase 5 (Week 6-7): TUI 실시간 모니터링**
- `rich` 라이브러리 기반 TUI
- 실시간 포트폴리오 추적
- **이유**: 실시간 트레이딩에 모니터링 필수

**Phase 6 (Week 9-12, Optional): GUI 대시보드**
- Streamlit 기반 웹 대시보드
- 인터랙티브 차트 (Plotly)
- **이유**: 편의성 향상, 일반 사용자 친화적

### 핵심 원칙: "CLI First, GUI Later"

1. **백엔드 로직 우선**: GUI는 안정화 후 구현
2. **점진적 개선**: CLI → TUI → GUI 순차 개발
3. **필요성 검증**: GUI는 백테스팅 완료 후 판단
4. **자동화 친화적**: CLI는 cron, CI/CD 통합 용이

### 개발 비용 분석

| 컴포넌트 | 개발 시간 | 유지보수 비용 | ROI |
|---------|---------|-------------|-----|
| **CLI** | 1-2일 | 낮음 | ⭐⭐⭐⭐⭐ |
| **TUI** | 1주 | 낮음 | ⭐⭐⭐⭐ |
| **GUI (Streamlit)** | 2주 | 중간 | ⭐⭐⭐ |
| **GUI (React)** | 4주+ | 높음 | ⭐⭐ |

### 결론

**현재 (Week 1-2)**: CLI에 집중하여 데이터 수집 파이프라인 완성
**Week 6-7**: TUI로 실시간 모니터링 추가
**Week 9+**: 백테스팅 결과가 만족스러우면 Streamlit GUI 구현 고려

**즉, GUI는 시스템이 실제로 수익을 낼 수 있다는 검증 후에 구현하는 것이 합리적입니다.**

---

## 6. 다음 단계 (현재 진행 중인 작업)

### 우선순위 P0: KIS API OHLCV 수집 문제 해결

**현재 상황**:
- KIS Overseas API 엔드포인트/파라미터 불명확
- 6,532 US tickers 스캔 완료했으나 OHLCV 수집 실패

**해결 방안**:
1. **Option 1**: KIS API 공식 문서 확인 (권장)
2. **Option 2**: Legacy API (Polygon.io/yfinance) 사용 (임시)
3. **Option 3**: 한국투자증권 GitHub 예제 찾기

**결정 필요**: 사용자님께서 어떤 방향으로 진행할지 결정 부탁드립니다.

---

**작성자**: Claude Code
**최종 수정**: 2025-10-19
