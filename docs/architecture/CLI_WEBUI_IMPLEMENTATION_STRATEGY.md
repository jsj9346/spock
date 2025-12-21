# CLI/WebUI 구현 전략 및 시점 분석

**작성일**: 2025-10-19
**목적**: 퀀트 트레이딩 시스템에서 CLI와 WebUI의 최적 구현 시점 결정

---

## Executive Summary

**권장 구현 순서**:
1. **Phase 1-3 (현재~Week 4)**: CLI 기반 개발 (데이터 수집, 지표 산출, 백테스팅)
2. **Phase 4 (Week 5-6)**: CLI + 정적 차트 생성 (matplotlib)
3. **Phase 5 (Week 6-7)**: TUI 실시간 모니터링 (rich 라이브러리)
4. **Phase 6 (Week 9-12, Optional)**: WebUI 구현 (Streamlit 기반 웹 대시보드)

**핵심 원칙**: "CLI First, WebUI Later" - 백엔드 로직이 안정화된 후 웹 인터페이스 구현

---

## 1. CLI vs WebUI 개념 정리

### CLI (Command Line Interface)
**정의**: 터미널에서 명령어로 실행하는 텍스트 기반 인터페이스

**특징**:
- 텍스트 출력만 가능
- SSH 원격 접속 가능
- 자동화 용이 (cron, CI/CD)
- 개발 시간 짧음 (1-2일)
- 개발자 친화적

**예시**:
```bash
$ python3 spock.py --collect-data --region US --days 250

[████████████████░░░░░░░░] 67% (4,372/6,532 tickers)
✅ AAPL: 250 days collected
✅ MSFT: 250 days collected
⚠️  ZZZZZ: No data (delisted)
```

### TUI (Terminal User Interface)
**정의**: 터미널에서 실행되지만 GUI처럼 보이는 텍스트 기반 인터페이스

**특징**:
- 터미널 내 표, 색상, 레이아웃 가능
- SSH 원격 접속 가능
- 실시간 업데이트 가능
- 키보드 인터랙션 (q=종료, r=새로고침)
- 개발 시간 중간 (1주)

**예시** (rich 라이브러리):
```bash
$ python3 spock.py --monitor

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
└─────────────────────────────────────────────────────────────┘
```

### GUI (Graphical User Interface) - Desktop App
**정의**: 데스크톱 애플리케이션 (윈도우, 맥, 리눅스)

**특징**:
- 설치 필요 (dmg, exe, deb)
- OS별 빌드 필요
- 원격 접속 불가
- 개발 시간 김 (4-8주)

**기술**: Electron, Qt, wxPython, Tkinter

**퀀트 시스템에는 부적합** - WebUI가 더 나음

### WebUI (Web User Interface)
**정의**: 웹 브라우저에서 실행되는 인터페이스

**특징**:
- 브라우저만 있으면 됨 (Chrome, Safari, Firefox)
- OS 독립적 (윈도우, 맥, 리눅스, 모바일)
- 원격 접속 가능 (http://server-ip:8501)
- 인터랙티브 차트, 드래그앤드롭, 실시간 업데이트
- 개발 시간 중간 (Streamlit: 2주, React: 4-6주)

**예시** (Streamlit):
```python
import streamlit as st

st.title("📊 Spock Trading Dashboard")
st.metric("Total Return", "+23.4%", delta="+2.1%")
st.line_chart(equity_curve)  # 인터랙티브 차트
```

**웹 브라우저에서 실행**:
- URL: `http://localhost:8501`
- 모바일에서도 접속 가능
- 실시간 차트 zoom, pan, tooltip

---

## 2. 퀀트 시스템 개발 단계별 UI/UX 요구사항

### Phase 1: Raw 데이터 수집 (Week 1-2) ✅ 현재 진행 중

**작업 내용**:
- KIS API 해외주식 데이터 수집
- SQLite 데이터베이스 구축
- 250일 OHLCV 데이터 수집 (6개 마켓)

**UI/UX 요구사항**:
- ✅ **CLI로 충분**: 진행률 표시, 에러 로깅
- ❌ **WebUI 불필요**: 일회성 작업, 자동화 가능

**CLI 예시**:
```bash
python3 spock.py --collect-data --region US --days 250

[████████████████░░░░░░░░] 67% (4,372/6,532 tickers)
✅ AAPL: 250 days collected
✅ MSFT: 250 days collected
```

**필요 도구**: `argparse`, `tqdm` (progress bar), `logging`

---

### Phase 2: 기술적 지표 산출 (Week 3)

**작업 내용**:
- LayeredScoringEngine 통합
- MA, RSI, MACD, BB, ATR 계산
- 100점 스코어링 시스템

**UI/UX 요구사항**:
- ✅ **CLI로 충분**: 배치 처리, 로그 확인
- ❌ **WebUI 불필요**: 백그라운드 계산

**CLI 예시**:
```bash
python3 spock.py --calculate-indicators --region US

📊 Technical Indicators Calculation
Batch 1/66: 100 tickers processed (1.2s)
✅ LayeredScoringEngine: 6,532 stocks scored
   - 127 stocks > 70 points (BUY)
   - 543 stocks 50-70 points (WATCH)
```

---

### Phase 3: 백테스팅 (Week 4-5)

**작업 내용**:
- Weinstein Stage 2 전략 검증
- VCP 패턴 백테스팅
- Kelly Formula 포지션 사이징 검증

**UI/UX 요구사항**:
- ⚠️ **CLI 기본 + 정적 차트 필요**: 결과 분석에 시각화 필수
- ✅ **matplotlib 기반 PNG 생성**: 터미널에서 실행 → PNG 저장 → 브라우저에서 확인
- ❌ **WebUI 불필요**: 배치 결과 확인용

**CLI + 차트 생성 예시**:
```bash
python3 spock.py --backtest --strategy stage2 --period 2023-2024

📈 Backtesting Results (2023-01-01 ~ 2024-12-31)
Total Return: +23.4% (KOSPI: +8.2%)
Sharpe Ratio: 1.82
Max Drawdown: -12.3%
Win Rate: 58.3% (62/106 trades)

📊 Generating performance charts...
✅ charts/equity_curve.png
✅ charts/drawdown.png
✅ charts/monthly_returns.png

👀 Open charts: open charts/equity_curve.png
```

**생성되는 차트**:
- Equity curve (수익률 곡선)
- Drawdown chart (낙폭 차트)
- Monthly returns heatmap (월별 수익률)
- Trade distribution (거래 분포도)

**구현 도구**: `matplotlib`, `seaborn`

---

### Phase 4: 실시간 트레이딩 모니터링 (Week 6-7) ⭐ TUI 전환점

**작업 내용**:
- KIS API 주문 실행
- 포트폴리오 모니터링
- 실시간 손익 추적

**UI/UX 요구사항**:
- ⚠️ **TUI 실시간 모니터링 필요**: 거래 중 상태 확인
- ✅ **rich 라이브러리 권장**: 터미널 내 실시간 테이블
- ❌ **WebUI 선택사항**: 편의성 좋지만 필수 아님

**TUI 예시** (rich):
```bash
python3 spock.py --monitor

┌────────────────────────────────────────────────────────┐
│ 🚀 Spock Trading Monitor - Live Update (1s)          │
├────────────────────────────────────────────────────────┤
│ 💰 Portfolio: ₩102,345,678 (+2.35%)                   │
├────────────────────────────────────────────────────────┤
│ Ticker    | Shares | P&L    | Value      | Signal   │
│ AAPL (US) | 100    | +5.2%  | $18,234    | HOLD     │
│ 005930    | 50     | +3.1%  | ₩3,850,000 | HOLD     │
│ MSFT (US) | 80     | -1.5%  | $12,400    | ⚠️ STOP   │
├────────────────────────────────────────────────────────┤
│ 🔔 Alerts                                              │
│ [14:30] MSFT triggered trailing stop (sell signal)   │
└────────────────────────────────────────────────────────┘

Press 'q' to quit, 'r' to refresh manually
```

**구현 도구**: `rich` (Terminal UI 라이브러리)

**TUI 구현 시점**: Week 6-7 (실시간 트레이딩 직전)

---

### Phase 5: WebUI 대시보드 (Week 9-12, Optional) 💎 편의성 향상

**작업 내용**:
- 포트폴리오 대시보드
- 실시간 차트 (TradingView 스타일)
- 백테스팅 결과 인터랙티브 분석
- 알림 및 설정 관리

**UI/UX 요구사항**:
- ✅ **편의성 대폭 향상**: 멀티 차트, 드릴다운 분석, 모바일 접속
- ❌ **필수 아님**: CLI/TUI로도 운영 가능
- **구현 비용**: 개발 2-4주 + 유지보수 지속

**WebUI 기술 스택 후보**:

#### Option 1: Streamlit ⭐⭐⭐⭐⭐ (권장)
**장점**: Python only, 빠른 개발 (2주), 퀀트에 최적화
**단점**: 커스터마이징 제한적

```python
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="Spock Dashboard", layout="wide")

# 메트릭 표시
col1, col2, col3 = st.columns(3)
col1.metric("Total Return", "+23.4%", delta="+2.1%")
col2.metric("Sharpe Ratio", "1.82", delta="+0.15")
col3.metric("Win Rate", "58.3%", delta="+2.4%")

# 인터랙티브 차트 (zoom, pan, tooltip)
fig = go.Figure()
fig.add_trace(go.Scatter(x=dates, y=equity, name="Portfolio"))
st.plotly_chart(fig, use_container_width=True)

# 포트폴리오 테이블
st.dataframe(portfolio_df, use_container_width=True)
```

**웹 브라우저에서 실행**:
- 로컬: `http://localhost:8501`
- 원격: `http://server-ip:8501` (방화벽 설정 필요)
- 모바일: 스마트폰 브라우저에서도 접속 가능

**개발 시간**: 2주
**유지보수**: 낮음
**적합성**: ⭐⭐⭐⭐⭐

#### Option 2: Gradio ⭐⭐⭐⭐
**장점**: AI/ML 친화적, GPT-4 차트 분석 결과 표시 용이
**단점**: 금융 특화 기능 부족

```python
import gradio as gr

def analyze_stock(ticker):
    # GPT-4 차트 분석
    chart = generate_chart(ticker)
    analysis = gpt4_analyze(chart)
    return chart, analysis

gr.Interface(
    fn=analyze_stock,
    inputs=gr.Textbox(label="Ticker"),
    outputs=[gr.Plot(), gr.Textbox(label="AI Analysis")]
).launch()
```

**개발 시간**: 1주
**유지보수**: 낮음
**적합성**: ⭐⭐⭐⭐

#### Option 3: Flask + React ⭐⭐⭐
**장점**: 완전한 커스터마이징, 프로덕션급
**단점**: 개발 시간 4-6주, React 학습 필요, Over-engineering 위험

```python
# Flask API
@app.route('/api/portfolio')
def get_portfolio():
    return jsonify(portfolio_data)

# React Frontend (별도 프로젝트)
fetch('/api/portfolio')
  .then(res => res.json())
  .then(data => setPortfolio(data))
```

**개발 시간**: 4-6주
**유지보수**: 높음
**적합성**: ⭐⭐⭐ (퀀트 시스템에는 과도함)

---

## 3. CLI vs TUI vs WebUI 비교표

| 특성 | CLI | TUI (rich) | WebUI (Streamlit) |
|-----|-----|-----------|------------------|
| **개발 시간** | 1-2일 | 1주 | 2-4주 |
| **유지보수** | 낮음 | 낮음 | 중간 |
| **실시간 업데이트** | 불가능 | 가능 (1초) | 가능 (실시간) |
| **차트 품질** | 정적 PNG | 터미널 차트 | 인터랙티브 (zoom, pan) |
| **원격 접속** | SSH | SSH | 웹 브라우저 |
| **모바일 접속** | 불가능 | 불가능 | 가능 |
| **자동화** | 매우 쉬움 | 불가능 | 어려움 |
| **멀티 차트** | 불가능 | 제한적 | 완벽 |
| **적합 사용자** | 개발자 | 개발자 | 개발자 + 일반 사용자 |

---

## 4. 최종 권장사항

### Phase별 UI/UX 전략

**Phase 1-3 (Week 1-5): CLI Only**
- 데이터 수집, 지표 산출, 백테스팅
- `argparse` + `logging` + `tqdm` + `matplotlib`
- **이유**: 백엔드 로직 집중, 빠른 개발, 자동화 용이

**Phase 4 (Week 5): CLI + 정적 차트**
- 백테스팅 결과 시각화 (matplotlib → PNG)
- Markdown 리포트 생성
- **이유**: 전략 검증에 시각화 필수, WebUI 없이도 가능

**Phase 5 (Week 6-7): TUI 실시간 모니터링**
- `rich` 라이브러리 기반 TUI
- 실시간 포트폴리오 추적
- **이유**: 실시간 트레이딩에 모니터링 필수, SSH로 원격 가능

**Phase 6 (Week 9-12, Optional): Streamlit WebUI**
- Streamlit 기반 웹 대시보드
- Plotly 인터랙티브 차트
- **이유**: 편의성 향상, 모바일 접속, 일반 사용자 친화적

### 핵심 원칙: "CLI First, WebUI Later"

1. **백엔드 로직 우선**: WebUI는 안정화 후 구현
2. **점진적 개선**: CLI → TUI → WebUI 순차 개발
3. **필요성 검증**: WebUI는 백테스팅 완료 후 판단
4. **자동화 친화적**: CLI는 cron, CI/CD 통합 용이

### 개발 비용 분석

| 컴포넌트 | 개발 시간 | 유지보수 비용 | ROI |
|---------|---------|-------------|-----|
| **CLI** | 1-2일 | 낮음 | ⭐⭐⭐⭐⭐ |
| **TUI (rich)** | 1주 | 낮음 | ⭐⭐⭐⭐ |
| **WebUI (Streamlit)** | 2주 | 중간 | ⭐⭐⭐ |
| **WebUI (React)** | 4주+ | 높음 | ⭐⭐ |

### 결론

**현재 (Week 1-2)**: CLI에 집중하여 데이터 수집 파이프라인 완성
**Week 6-7**: TUI로 실시간 모니터링 추가
**Week 9+**: 백테스팅 결과가 만족스러우면 Streamlit WebUI 구현 고려

**즉, WebUI는 시스템이 실제로 수익을 낼 수 있다는 검증 후에 구현하는 것이 합리적입니다.**

---

## 5. 다음 단계 (현재 진행 중인 작업)

### 우선순위 P0: KIS API OHLCV 수집 문제 해결

**현재 상황**:
- KIS Overseas API 엔드포인트/파라미터 불명확
- 6,532 US tickers 스캔 완료했으나 OHLCV 수집 0% 성공률

**해결 방안**:
1. **Option 1**: KIS API 공식 문서 확인 (권장)
2. **Option 2**: Legacy API (Polygon.io/yfinance) 사용 (임시)
3. **Option 3**: 한국투자증권 GitHub 예제 찾기

**결정 필요**: 사용자님께서 어떤 방향으로 진행할지 결정 부탁드립니다.

---

## 6. WebUI 구현 시 고려사항

### Streamlit 배포 옵션

**로컬 실행** (개발/테스트):
```bash
streamlit run dashboard.py
# http://localhost:8501
```

**원격 서버 배포** (프로덕션):
```bash
# EC2, DigitalOcean 등
streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0

# 방화벽 설정
sudo ufw allow 8501

# 접속: http://server-ip:8501
```

**Streamlit Cloud** (무료 호스팅):
- GitHub 연동 자동 배포
- HTTPS 자동 제공
- `your-app.streamlit.app`

### 보안 고려사항

**인증 추가** (Streamlit):
```python
import streamlit as st

def check_password():
    if "password_correct" not in st.session_state:
        st.text_input("Password", type="password", key="password")
        if st.session_state.password == "your-secret":
            st.session_state.password_correct = True
        else:
            st.error("Password incorrect")
            return False
    return True

if check_password():
    # 대시보드 표시
    st.title("Spock Dashboard")
```

**HTTPS 설정** (Nginx reverse proxy):
```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /etc/ssl/cert.pem;
    ssl_certificate_key /etc/ssl/key.pem;

    location / {
        proxy_pass http://localhost:8501;
    }
}
```

---

**작성자**: Claude Code
**최종 수정**: 2025-10-19
