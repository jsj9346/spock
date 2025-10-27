# Spock - 자동화 주식 트레이딩 시스템 PRD (Product Requirements Document)

## Document Information
- **Version**: 1.0
- **Last Updated**: 2025-10-01
- **Author**: Based on real investor behavior analysis
- **Status**: Initial Design Phase

---

## 1. Executive Summary

### 1.1 Product Vision
Spock은 검증된 투자 전략(Weinstein Stage 2, Minervini VCP)과 체계적인 리스크 관리를 결합한 자동화 주식 트레이딩 시스템입니다. 투자자의 감정적 편향을 제거하고, 일관된 투자 프로세스를 통해 장기적인 복리 수익을 추구합니다.

### 1.2 Core Philosophy
- **"잃지 않기" 우선**: 단기 수익보다 장기 생존과 복리 성장
- **전략 우선, 자동화는 도구**: 검증된 패턴의 체계적 실행
- **손실은 짧게, 이익은 길게**: 7-8% 손절, 20-25% 익절
- **감정 배제**: 객관적 데이터 기반 의사결정

### 1.3 Target Users
- **Primary**: 체계적 투자를 원하지만 시간이 부족한 직장인 투자자
- **Secondary**: 감정적 트레이딩에서 벗어나고 싶은 개인투자자
- **Tertiary**: 자동화 시스템 구축을 원하는 기술 투자자

---

## 2. Investor Journey & Pain Points

### 2.1 현재 투자자의 의사결정 프로세스

#### Phase 1: 종목 발굴 (Discovery)
**현재 행동**:
- 차트 보며 "오르는 종목" 탐색
- 시가총액, 거래량 필터링
- 테마주, 섹터 모멘텀 추종

**Pain Points**:
- ❌ 정보 과부하: 너무 많은 종목, 어디서부터?
- ❌ FOMO: 이미 많이 오른 종목 매수 (Stage 3 진입)
- ❌ 비체계적 스크리닝: 일관성 없는 기준
- ❌ 시간 소모: 매일 종목 발굴에 1-2시간 소요

**Spock Solution**:
- ✅ 자동화된 ticker scanning (KOSPI/KOSDAQ 전종목)
- ✅ 다단계 필터링: 시가총액, 거래량, 기술적 조건
- ✅ Stage 2 조기 포착: 상승 초기 단계 자동 감지
- ✅ 매일 watchlist 자동 업데이트

#### Phase 2: 초기 조사 (Initial Research)
**현재 행동**:
- 차트 확인 (추세, 이동평균선, 거래량)
- 기본 재무 지표 확인 (PER, PBR, 시가총액)
- 최근 뉴스 및 공시 검색
- 외국인/기관 매매 동향 확인

**Pain Points**:
- ❌ 일관성 부족: 매번 다른 기준으로 판단
- ❌ 확증 편향: 보고 싶은 것만 보기
- ❌ 정보 분산: 여러 사이트 오가며 정보 수집
- ❌ 객관성 부족: "느낌"에 의존한 판단

**Spock Solution**:
- ✅ 100점 객관적 스코어링 시스템
- ✅ 다층 분석 (거시/구조/미시 3단계)
- ✅ 자동화된 기술적 지표 계산 (MA, RSI, MACD, Bollinger Bands)
- ✅ 외국인/기관 순매수 추적 및 점수화
- ✅ 단일 대시보드에서 모든 정보 통합 제공

#### Phase 3: 심층 분석 (Deep Analysis)
**현재 행동**:
- 차트 패턴 분석 (컵앤핸들, VCP, 삼각수렴)
- 지지/저항 레벨 확인
- 섹터 강도 및 상대적 성과 비교
- 재무제표 분석 (매출 성장, 수익성)

**Pain Points**:
- ❌ 전문성 요구: 패턴 인식 어려움
- ❌ 시간 소모: 한 종목 분석에 30분~1시간
- ❌ 주관적 해석: 같은 차트, 다른 결론
- ❌ 섹터 비교 어려움: 수동 비교는 비효율적

**Spock Solution**:
- ✅ AI 기반 차트 패턴 인식 (GPT-4 integration)
- ✅ 자동화된 Weinstein Stage 분류
- ✅ 섹터 상대 강도 자동 계산 (11 GICS sectors)
- ✅ LayeredScoringEngine: 25개 지표 종합 분석
- ✅ 패턴별 승률 및 기대수익 제시

#### Phase 4: 리스크 평가 (Risk Assessment)
**현재 행동**:
- 진입가 결정 (현재가? 조정 대기?)
- 손절가 계산 (5%? 10%? 지지선?)
- 포지션 크기 결정 (얼마나 살까?)
- 포트폴리오 영향 검토 (분산투자 체크)
- 시장 상황 고려 (지금이 적기인가?)

**Pain Points**:
- ❌ 임의적 손절 설정: 근거 없는 %
- ❌ 과다/과소 투자: 포지션 사이징 어려움
- ❌ 분산투자 실패: 특정 섹터 쏠림
- ❌ 시장 타이밍 불확실성

**Spock Solution**:
- ✅ ATR 기반 동적 손절 (변동성 반영)
- ✅ Kelly Formula 포지션 사이징 (패턴 승률 기반)
- ✅ 자동 섹터/종목 익스포저 제한 (15% per stock, 40% per sector)
- ✅ 시장 sentiment 통합 (VIX, 외국인 수급)
- ✅ 최소 현금 보유 강제 (20% cash reserve)

#### Phase 5: 매수 결정 (Decision)
**현재 행동**:
- 기준 충족 여부 최종 점검
- 리스크/리워드 비율 평가
- 타이밍 적절성 판단 (기술적 셋업 완성?)
- 가용 자금 확인
- 포트폴리오 전략 적합성 검토

**Pain Points**:
- ❌ 분석 마비: 너무 많은 요소 고려
- ❌ 타이밍 놓침: 고민하다 기회 상실
- ❌ 감정 개입: 분석과 다른 결정
- ❌ 일관성 부족: 매번 다른 기준

**Spock Solution**:
- ✅ 명확한 BUY/WATCH/AVOID 신호 (≥70점 = BUY)
- ✅ 4-gate 필터링: 기술적/재무적/리스크/시장 게이트
- ✅ 자동화된 capital allocation check
- ✅ 감정 배제: 100% 룰 기반 의사결정
- ✅ 실시간 entry signal detection

#### Phase 6: 주문 실행 (Execution)
**현재 행동**:
- 주문 유형 선택 (시장가? 지정가?)
- 가격 결정 (현재가? 호가?)
- 주문 수량 계산 (호가 단위 맞추기)
- HTS/MTS에서 주문 입력 및 확인
- 초기 손절가 설정

**Pain Points**:
- ❌ 호가 단위 오류: 주문 거부
- ❌ 수수료 미고려: 실제 수익률 오차
- ❌ 슬리피지: 시장가 주문 시 불리한 체결
- ❌ 실수 가능성: 수동 입력 오류

**Spock Solution**:
- ✅ KIS API 자동 주문 실행
- ✅ Tick size 자동 준수 (price range별 호가 단위)
- ✅ 최우선 호가 지정가 주문 (슬리피지 최소화)
- ✅ 수수료 자동 계산 (0.015% 거래세 + 0.23% 증권거래세)
- ✅ 주문 확인 및 로깅
- ✅ 초기 stop loss 자동 설정

#### Phase 7: 모니터링 및 관리 (Monitoring)
**현재 행동**:
- 일일 가격 모니터링
- 손절선 조정 (trailing stop)
- 익절 목표 모니터링
- 청산 신호 감지 (Stage 3 전환)
- 포트폴리오 리밸런싱

**Pain Points**:
- ❌ 상시 모니터링 어려움: 직장인 불가능
- ❌ 감정적 손절 실패: "조금만 더 기다리면..."
- ❌ 조기 익절: 불안감에 너무 빨리 매도
- ❌ Stage 3 감지 실패: 하락 전환 놓침

**Spock Solution**:
- ✅ 24시간 자동 모니터링
- ✅ ATR 기반 자동 trailing stop 조정
- ✅ Stage 3 전환 자동 감지 및 청산
- ✅ 익절 목표 자동 추적 (20-25%)
- ✅ 포트폴리오 실시간 sync (SQLite ⇄ KIS API)
- ✅ 알림 시스템 (SMS/email/Slack)

---

## 3. Core Requirements

### 3.1 Functional Requirements

#### FR1: 종목 발굴 시스템 (Stock Discovery)
**Priority**: P0 (Critical)

**User Story**:
> 투자자로서, 매일 KOSPI/KOSDAQ 전종목을 스캔하여 Stage 2 초기 진입 종목을 자동으로 발굴하고 싶다.

**Acceptance Criteria**:
- [ ] KOSPI/KOSDAQ 전종목 자동 스캔 (3,000+ stocks)
- [ ] 필터링 기준:
  - 시가총액 ≥ 1,000억원
  - 일평균 거래량 ≥ 1억원
  - 유동성 ≥ 30% (공정거래법 기준)
  - 가격 범위: 5,000원 ~ 500,000원
- [ ] Blacklist 자동 제외 (관리종목, 투자주의, 정리매매)
- [ ] 섹터별 분류 (GICS 11 sectors)
- [ ] 일일 신규 발굴 종목 ≤ 50개 (과부하 방지)
- [ ] 스캔 성능: <5분 (전종목 처리)

**Technical Specs**:
- Module: `stock_scanner.py`
- Input: KIS API market data
- Output: SQLite `tickers` table
- Error Handling: API timeout → retry with exponential backoff

---

#### FR2: 데이터 수집 시스템 (Data Collection)
**Priority**: P0 (Critical)

**User Story**:
> 투자자로서, 발굴된 종목의 과거 250일 OHLCV 데이터와 기술적 지표를 자동으로 수집하고 싶다.

**Acceptance Criteria**:
- [ ] Incremental 데이터 수집 (gap detection)
- [ ] 250일 rolling window 유지 (MA200 계산용)
- [ ] 자동 데이터 정합성 검증 (gap, duplicate, outlier)
- [ ] 기술적 지표 자동 계산:
  - Moving Averages: MA5, MA20, MA60, MA120, MA200
  - Momentum: RSI(14), MACD(12,26,9), Stochastic
  - Volatility: Bollinger Bands(20), ATR(14), Keltner Channels
  - Volume: OBV, VWAP, AD
- [ ] 일일/주간/월간 timeframe 지원
- [ ] KIS API rate limiting 준수 (20 req/sec, 1,000 req/min)
- [ ] 수집 성능: 50 stocks in <3분

**Technical Specs**:
- Module: `kis_data_collector.py`
- Database: SQLite `ohlcv_data` table
- Retry Logic: 3 attempts with exponential backoff
- Cache: Session-level cache for duplicate requests

---

#### FR3: 기술적 분석 엔진 (Technical Analysis)
**Priority**: P0 (Critical)

**User Story**:
> 투자자로서, LayeredScoringEngine을 통해 100점 만점의 객관적 점수를 받아 종목을 비교하고 싶다.

**Acceptance Criteria**:
- [ ] **Layer 1 - Macro (25 points)**:
  - MarketRegimeModule (5점): Bull/sideways/bear 감지
  - VolumeProfileModule (10점): 거래량 프로파일 분석
  - PriceActionModule (10점): 가격 행동 강도

- [ ] **Layer 2 - Structural (45 points)**:
  - StageAnalysisModule (15점): Weinstein Stage 2 감지
  - MovingAverageModule (15점): MA alignment (5/20/60/120/200)
  - RelativeStrengthModule (15점): 섹터 및 시장 대비 상대 강도

- [ ] **Layer 3 - Micro (30 points)**:
  - PatternRecognitionModule (10점): 차트 패턴 (Cup & Handle, VCP 등)
  - VolumeSpikeModule (10점): 거래량 breakout 감지
  - MomentumModule (10점): RSI, MACD momentum 지표

- [ ] **Scoring Thresholds**:
  - ≥70점: BUY (Strong Buy)
  - 50-69점: WATCH (Watchlist)
  - <50점: AVOID (No Action)

- [ ] 점수별 상세 breakdown 제공 (transparency)
- [ ] 과거 승률 tracking (pattern별)

**Technical Specs**:
- Module: `integrated_scoring_system.py`, `layered_scoring_engine.py`
- Input: `ohlcv_data` with technical indicators
- Output: SQLite `technical_analysis` table
- Performance: 50 stocks scoring in <2분

---

#### FR4: AI 차트 분석 (GPT-4 Chart Analysis)
**Priority**: P1 (High, but optional)

**User Story**:
> 투자자로서, AI가 차트 패턴을 분석하고 사람이 읽을 수 있는 설명을 제공받고 싶다.

**Acceptance Criteria**:
- [ ] Chart pattern recognition:
  - Cup & Handle
  - VCP (Volatility Contraction Pattern)
  - Ascending Triangle
  - Bull Flag
  - Pennant

- [ ] Candlestick pattern analysis:
  - Bullish engulfing
  - Morning star
  - Hammer

- [ ] Market regime description (자연어)
- [ ] Support/Resistance level identification
- [ ] Pattern confidence score (0-100)
- [ ] 승률 기반 recommendation
- [ ] Token cost optimization (<1,000 tokens per analysis)

**Technical Specs**:
- Module: `stock_gpt_analyzer.py`
- API: OpenAI GPT-4o-mini (cost efficiency)
- Input: Chart image (matplotlib + mplfinance)
- Output: SQLite `gpt_analysis` table with JSON pattern data
- Fallback: Skip GPT if API unavailable (scoring system still works)

---

#### FR5: 리스크 관리 시스템 (Risk Management)
**Priority**: P0 (Critical)

**User Story**:
> 투자자로서, 과학적 포지션 사이징(Kelly Formula)과 자동 손절로 손실을 제한하고 싶다.

**Acceptance Criteria**:
- [ ] **Kelly Formula Position Sizing**:
  - Pattern별 승률 mapping:
    - Stage 2 Breakout: 65% win rate, 2.0 avg win/loss
    - VCP Pattern: 62% win rate, 2.1 avg win/loss
    - Cup-and-Handle: 58% win rate, 1.8 avg win/loss
    - Triangle Breakout: 55% win rate, 1.6 avg win/loss
  - Conservative Kelly: Half Kelly (0.5 multiplier)
  - Max position: 15% per stock
  - Max sector exposure: 40%
  - Min cash reserve: 20%

- [ ] **ATR-Based Trailing Stop**:
  - Base: 1.0 × ATR(14)
  - Min stop: 5% (low volatility)
  - Max stop: 15% (high volatility)
  - Dynamic adjustment based on realized volatility
  - Trailing activation at +15% profit

- [ ] **Profit Taking Strategy**:
  - Stage 3 detection → automatic exit
  - 20-25% profit target
  - Partial profit at key resistance levels (optional)

- [ ] **Portfolio Limits**:
  - Max 10 concurrent positions
  - Max 80% equity exposure
  - Sector diversification enforcement

**Technical Specs**:
- Module: `kelly_calculator.py`, `kis_trading_engine.py`
- Database: SQLite `kelly_sizing`, `portfolio` tables
- Real-time monitoring: Check every 5 minutes during market hours

---

#### FR6: 트레이딩 엔진 (Trading Engine)
**Priority**: P0 (Critical)

**User Story**:
> 투자자로서, KIS API를 통해 자동으로 주문을 실행하고 포트폴리오를 동기화하고 싶다.

**Acceptance Criteria**:
- [ ] **Order Execution**:
  - KIS API 통합 (OAuth 2.0 인증)
  - Tick size 자동 준수:
    - <10,000원: 5원 tick
    - 10,000-50,000원: 10원 tick
    - 50,000-200,000원: 50원 tick
    - 200,000-500,000원: 100원 tick
    - 500,000원+: 1,000원 tick
  - Order types: Limit order (최우선 호가)
  - Slippage minimization
  - Transaction cost calculation:
    - Trading fee: 0.015%
    - Securities tax: 0.23% (sell only, KOSPI)

- [ ] **Portfolio Management**:
  - Real-time sync: SQLite ⇄ KIS API
  - Sync policy (risk level dependent):
    - Conservative: Auto-sync <500,000원 discrepancy
    - Moderate: Auto-sync <2,000,000원
    - Aggressive: Auto-sync all
  - Position tracking with P&L
  - Cash balance monitoring
  - Dividend schedule tracking

- [ ] **Order Validation**:
  - Pre-order checks:
    - Capital availability
    - Position limits
    - Market hours
    - Trading halt status
  - Post-order confirmation
  - Error recovery (order rejection handling)

- [ ] **Market Hours Enforcement**:
  - Regular hours: 09:00-15:30 KST
  - No trading on holidays (market_schedule.json)
  - Pre-market analysis: 08:30
  - Post-market reporting: 16:00

**Technical Specs**:
- Module: `kis_trading_engine.py`
- API: KIS Developers API (REST)
- Database: SQLite `trades`, `portfolio`, `kis_api_logs` tables
- Retry Logic: 3 attempts for transient errors
- Audit Trail: Complete logging of all orders and reasons

---

#### FR7: 시장 sentiment 분석 (Market Sentiment)
**Priority**: P1 (High)

**User Story**:
> 투자자로서, 전체 시장 상황(VIX, 외국인 수급 등)을 고려하여 리스크를 조절하고 싶다.

**Acceptance Criteria**:
- [ ] **VIX Index Integration**:
  - VIX <20: Low volatility → 100% position sizing
  - VIX 20-30: Moderate → 75% position sizing
  - VIX 30-40: High → 50% position sizing
  - VIX >40: Extreme → 25% position sizing (defensive)

- [ ] **Foreign/Institution Trading Analysis**:
  - Net buying >100M for 3+ days → Bullish signal (+5 points)
  - Net selling >100M for 3+ days → Bearish signal (-5 points)
  - Integration into Layer 1 MarketRegimeModule

- [ ] **Fear & Greed Index** (CNN Money):
  - Extreme Fear (<25): Contrarian buy signal
  - Extreme Greed (>75): Caution signal

- [ ] **Global Market Correlation**:
  - US market (NASDAQ/Dow) overnight movement
  - USD/KRW, JPY/KRW exchange rate impact
  - Commodity prices (oil, gold, copper)

- [ ] **Sector Rotation Analysis**:
  - GICS 11 sector relative strength
  - Hot sector identification
  - Theme stock co-movement detection

**Technical Specs**:
- Module: `stock_sentiment.py`
- External APIs: CBOE (VIX), CNN Money, KIS API (foreign/institution)
- Database: SQLite `market_sentiment` table
- Update frequency: Daily at 08:30 KST

---

#### FR8: 자동 복구 시스템 (Auto Recovery)
**Priority**: P1 (High)

**User Story**:
> 투자자로서, 시스템 오류가 발생해도 자동으로 복구되어 거래 기회를 놓치지 않고 싶다.

**Acceptance Criteria**:
- [ ] **Error Detection**:
  - API errors: Connection timeout, rate limiting, auth failure
  - Database errors: Lock timeout, corruption, transaction rollback
  - Trading errors: Order rejection, insufficient balance, trading halt
  - System errors: Disk space, memory leak, logging failure

- [ ] **Recovery Actions**:
  - `API_RECONNECT`: KIS API 재연결
  - `API_RATE_LIMIT`: API 호출 속도 제한 준수
  - `ORDER_VALIDATION`: 주문 검증 재시도
  - `TICK_SIZE_ADJUSTMENT`: 호가 단위 자동 조정
  - `DATABASE_REPAIR`: SQLite DB 복구
  - `PORTFOLIO_SYNC`: 포트폴리오 강제 동기화

- [ ] **Recovery Strategy**:
  - 3 attempts with exponential backoff
  - Circuit breaker pattern (5 consecutive failures → stop)
  - Fallback to safe mode (read-only, no trading)
  - Alert escalation (email/SMS after 2 failures)

- [ ] **Monitoring & Logging**:
  - Error rate tracking
  - Recovery success rate
  - System health dashboard
  - Daily error summary report

**Technical Specs**:
- Module: `auto_recovery_system.py`
- Database: SQLite `system_errors`, `recovery_logs` tables
- Integration: All modules use AutoRecoverySystem wrapper

---

#### FR9: 보고 및 모니터링 (Reporting & Monitoring)
**Priority**: P1 (High)

**User Story**:
> 투자자로서, 시스템 성과를 명확하게 파악하고 개선점을 찾고 싶다.

**Acceptance Criteria**:
- [ ] **Daily Summary**:
  - Trades executed (count, total value)
  - P&L (realized, unrealized)
  - Portfolio composition (positions, cash, total value)
  - Watchlist updates (new candidates)
  - System errors and recoveries

- [ ] **Weekly Portfolio Report**:
  - Total return (%, amount)
  - Win rate by pattern
  - Average win/loss ratio
  - Sharpe ratio
  - Max drawdown
  - Sector allocation
  - Top performers / worst performers

- [ ] **Monthly Strategy Report**:
  - Pattern performance analysis
  - Kelly calculator accuracy (predicted vs actual win rate)
  - Risk-adjusted returns
  - Comparison vs benchmark (KOSPI, KOSDAQ)
  - Trade log export (CSV for tax reporting)

- [ ] **Real-time Alerts**:
  - Entry signal detected (watchlist stock)
  - Stop loss triggered
  - Profit target reached
  - Portfolio limit warnings
  - System errors (critical)

- [ ] **Dashboard/UI** (Future enhancement):
  - Portfolio overview
  - Watchlist with scores
  - Trade history
  - Performance charts
  - Manual override controls

**Technical Specs**:
- Module: `reporting.py` (new)
- Database: All tables for data aggregation
- Output formats: JSON, CSV, HTML email
- Delivery: Email, Slack webhook, SMS (Twilio)

---

### 3.2 Non-Functional Requirements

#### NFR1: Performance
- [ ] Stock scanning: <5분 (3,000+ stocks)
- [ ] Data collection: <3분 (50 stocks incremental)
- [ ] Scoring system: <2분 (50 stocks full analysis)
- [ ] Order execution: <5초 (from signal to KIS API confirmation)
- [ ] Portfolio sync: <10초 (SQLite ⇄ KIS API)

#### NFR2: Reliability
- [ ] System uptime: ≥99% during market hours
- [ ] Data accuracy: ≥99.9% (verified against KIS API)
- [ ] Order success rate: ≥98% (excluding market halts)
- [ ] Auto recovery success: ≥90% within 3 attempts

#### NFR3: Security
- [ ] API credentials: Encrypted storage (.env with 600 permissions)
- [ ] Database: SQLite with journal mode (transaction safety)
- [ ] Audit trail: Complete logging of all orders and changes
- [ ] No plaintext secrets in code or logs

#### NFR4: Maintainability
- [ ] Code reuse from Makenaide: ≥70%
- [ ] Type hints for all functions
- [ ] Docstrings for all public APIs
- [ ] Unit test coverage: ≥80% for core modules
- [ ] Integration test coverage: ≥60%

#### NFR5: Scalability
- [ ] Support up to 100 concurrent watchlist stocks
- [ ] Support up to 10 concurrent portfolio positions
- [ ] Database size: <1GB (250-day retention with cleanup)
- [ ] Memory usage: <500MB (Python process)
- [ ] CPU usage: <30% average during market hours

#### NFR6: Usability
- [ ] One-command execution: `python3 spock.py --risk-level moderate`
- [ ] Dry-run mode for safe testing: `--dry-run --no-gpt`
- [ ] Clear error messages with actionable guidance
- [ ] Comprehensive logging with DEBUG/INFO/WARNING/ERROR levels
- [ ] Configuration via .env and JSON files (no code changes)

---

## 4. Technical Architecture

### 4.1 System Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                     Spock Main Orchestrator                 │
│                        (spock.py)                           │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
     ┌────────────────┐ ┌────────────┐ ┌──────────────┐
     │ Stock Scanner  │ │ Data       │ │ Sentiment    │
     │ (Phase 0)      │ │ Collector  │ │ Analyzer     │
     │                │ │ (Phase 1)  │ │              │
     └────────────────┘ └────────────┘ └──────────────┘
              │               │               │
              └───────────────┼───────────────┘
                              ▼
                    ┌──────────────────┐
                    │ SQLite Database  │
                    │ (spock_local.db) │
                    └──────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
     ┌────────────────┐ ┌────────────┐ ┌──────────────┐
     │ Technical      │ │ GPT-4      │ │ Kelly        │
     │ Analysis       │ │ Analyzer   │ │ Calculator   │
     │ (Phase 2)      │ │ (Phase 3)  │ │              │
     └────────────────┘ └────────────┘ └──────────────┘
              │               │               │
              └───────────────┼───────────────┘
                              ▼
                    ┌──────────────────┐
                    │ Trading Engine   │
                    │ (Execution)      │
                    └──────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │ KIS API          │
                    │ (Buy/Sell)       │
                    └──────────────────┘
```

### 4.2 Data Flow
```
1. Stock Discovery:
   KIS API (market data) → stock_scanner.py → SQLite (tickers)

2. Data Collection:
   SQLite (tickers) → kis_data_collector.py → KIS API (OHLCV) → SQLite (ohlcv_data)

3. Technical Analysis:
   SQLite (ohlcv_data) → stock_technical_filter.py → LayeredScoringEngine → SQLite (technical_analysis)

4. AI Analysis (optional):
   SQLite (ohlcv_data) → stock_gpt_analyzer.py → GPT-4 API → SQLite (gpt_analysis)

5. Position Sizing:
   SQLite (technical_analysis + gpt_analysis) → kelly_calculator.py → SQLite (kelly_sizing)

6. Trading Decision:
   SQLite (kelly_sizing + portfolio + market_sentiment) → kis_trading_engine.py → KIS API (order)

7. Portfolio Sync:
   KIS API (balance) ⇄ SQLite (portfolio, trades)
```

### 4.3 Database Schema

#### Core Tables
- **tickers**: Stock ticker information with sector classification
- **ohlcv_data**: Daily/weekly/monthly OHLCV with technical indicators
- **technical_analysis**: Weinstein stage, quality scores, LayeredScoringEngine results
- **gpt_analysis**: GPT-4 chart pattern analysis results
- **trades**: Trade history with entry/exit prices, P&L tracking
- **portfolio**: Real-time position tracking with dividend schedules
- **kelly_sizing**: Pattern-based position sizing calculations
- **market_sentiment**: VIX, Fear & Greed, foreign/institution data
- **kis_api_logs**: API call logs for rate limiting and debugging
- **system_errors**: Error tracking for auto recovery
- **recovery_logs**: Recovery action history

See `spock_init_db.py` for complete schema definition.

---

## 5. Risk Profiles & Configuration

### 5.1 Risk Levels

#### Conservative Profile
```yaml
risk_level: conservative
description: "Capital preservation with steady growth"

position_sizing:
  kelly_multiplier: 0.5
  max_position_per_stock: 0.10  # 10%
  max_sector_exposure: 0.30     # 30%
  min_cash_reserve: 0.30        # 30%
  max_concurrent_positions: 5

stop_loss:
  atr_multiplier: 0.8
  min_stop_percent: 0.03  # 3%
  max_stop_percent: 0.08  # 8%

profit_taking:
  target_profit: 0.15     # 15%
  trailing_stop_activation: 0.10  # 10%

scoring:
  min_buy_score: 75
  min_watch_score: 65
  preferred_patterns: ["Stage 2 Breakout", "VCP Pattern"]

market_filter:
  vix_max: 30  # Don't trade if VIX >30
  foreign_buying_required: true
```

#### Moderate Profile (Default)
```yaml
risk_level: moderate
description: "Balanced growth with calculated risk"

position_sizing:
  kelly_multiplier: 1.0
  max_position_per_stock: 0.15  # 15%
  max_sector_exposure: 0.40     # 40%
  min_cash_reserve: 0.20        # 20%
  max_concurrent_positions: 8

stop_loss:
  atr_multiplier: 1.0
  min_stop_percent: 0.05  # 5%
  max_stop_percent: 0.10  # 10%

profit_taking:
  target_profit: 0.20     # 20%
  trailing_stop_activation: 0.15  # 15%

scoring:
  min_buy_score: 70
  min_watch_score: 60
  preferred_patterns: ["Stage 2 Breakout", "VCP Pattern", "Cup-and-Handle"]

market_filter:
  vix_max: 40  # Don't trade if VIX >40
  foreign_buying_required: false
```

#### Aggressive Profile
```yaml
risk_level: aggressive
description: "Maximum growth with higher volatility tolerance"

position_sizing:
  kelly_multiplier: 1.5
  max_position_per_stock: 0.20  # 20%
  max_sector_exposure: 0.50     # 50%
  min_cash_reserve: 0.15        # 15%
  max_concurrent_positions: 10

stop_loss:
  atr_multiplier: 1.2
  min_stop_percent: 0.07  # 7%
  max_stop_percent: 0.15  # 15%

profit_taking:
  target_profit: 0.25     # 25%
  trailing_stop_activation: 0.20  # 20%

scoring:
  min_buy_score: 65
  min_watch_score: 55
  preferred_patterns: ["All patterns"]

market_filter:
  vix_max: 50  # Trade even in high volatility
  foreign_buying_required: false
```

---

## 6. Success Metrics

### 6.1 Business Metrics
- **Total Return**: ≥15% annually (vs KOSPI ~8%)
- **Sharpe Ratio**: ≥1.5 (risk-adjusted returns)
- **Max Drawdown**: ≤15% (capital preservation)
- **Win Rate**: ≥55% (better than random)
- **Profit Factor**: ≥2.0 (avg win / avg loss)

### 6.2 System Metrics
- **Uptime**: ≥99% during market hours
- **Order Success Rate**: ≥98%
- **Data Accuracy**: ≥99.9%
- **Auto Recovery Rate**: ≥90%
- **False Signal Rate**: ≤20% (BUY signals that lose)

### 6.3 Efficiency Metrics
- **Code Reuse from Makenaide**: ≥70%
- **Development Time**: ≤8 weeks (vs 24 weeks from scratch)
- **Test Coverage**: ≥80% (core modules)
- **Bug Density**: ≤5 bugs per 1,000 LOC

---

## 7. Development Roadmap

### Phase 1: Foundation (Week 1) - 95% Reuse
- [x] Copy reusable modules from Makenaide
- [ ] Initialize SQLite schema with stock market tables
- [ ] Setup logging and monitoring system
- [ ] Create project directory structure
- [ ] Setup development environment (.env, dependencies)

### Phase 2: Analysis Engine (Weeks 2-3) - 95% Reuse
- [ ] Copy integrated_scoring_system.py and related modules
- [ ] Test LayeredScoringEngine with Korean stock data
- [ ] Validate Kelly Calculator with pattern win rates
- [ ] Adjust adaptive scoring thresholds for stock market
- [ ] Unit tests for scoring modules

### Phase 3: API Integration (Weeks 4-5) - 70% Reuse
- [ ] Develop KIS API connector module
- [ ] Convert data_collector.py → kis_data_collector.py
- [ ] Convert trading_engine.py → kis_trading_engine.py
- [ ] Convert scanner.py → stock_scanner.py
- [ ] Implement tick size compliance
- [ ] Integration tests with KIS mock API

### Phase 4: Main Pipeline (Weeks 6-7)
- [ ] Convert makenaide.py → spock.py
- [ ] Add market hours management
- [ ] Integrate sector analysis
- [ ] Implement foreign/institution trading analysis
- [ ] Full integration testing with dry-run mode
- [ ] Error handling and auto recovery validation

### Phase 5: Stock Market Features (Week 8)
- [ ] Add stock-specific sentiment indicators (VIX, etc.)
- [ ] Implement sector rotation analysis
- [ ] Global market correlation analysis
- [ ] Dividend schedule management
- [ ] Final backtesting and validation

### Phase 6: Production Deployment (Optional, future)
- [ ] AWS EC2 setup and deployment
- [ ] Monitoring and alerting (Slack, email)
- [ ] Performance optimization
- [ ] Production testing with small capital
- [ ] Documentation and user guide

---

## 8. Testing Strategy

### 8.1 Unit Testing
- [ ] Test all scoring modules independently
- [ ] Test Kelly calculator with known win rates
- [ ] Test tick size compliance logic
- [ ] Test ATR stop loss calculation
- [ ] Test Weinstein Stage classification
- [ ] Coverage target: ≥80%

### 8.2 Integration Testing
- [ ] Test full pipeline with dry-run mode
- [ ] Test KIS API integration with mock server
- [ ] Test database operations (CRUD, transactions)
- [ ] Test error recovery scenarios
- [ ] Test portfolio sync logic
- [ ] Coverage target: ≥60%

### 8.3 Backtesting
- [ ] Historical data backtesting (2020-2024)
- [ ] Pattern win rate validation
- [ ] Kelly formula accuracy check
- [ ] Strategy parameter optimization
- [ ] Risk profile comparison (conservative vs moderate vs aggressive)

### 8.4 Paper Trading
- [ ] KIS mock investment API testing
- [ ] 1-month paper trading validation
- [ ] Performance vs benchmark comparison
- [ ] Error rate monitoring
- [ ] Final go/no-go decision

---

## 9. Risk Management & Safeguards

### 9.1 Trading Safeguards
- [ ] **Pre-Order Validation**:
  - Capital availability check
  - Position limit enforcement
  - Market hours validation
  - Trading halt detection

- [ ] **Order Execution**:
  - Limit order only (no market orders)
  - Tick size compliance
  - Slippage monitoring
  - Order confirmation required

- [ ] **Post-Order Monitoring**:
  - Portfolio sync verification
  - P&L tracking
  - Stop loss monitoring
  - Alert on significant moves

### 9.2 System Safeguards
- [ ] **Circuit Breaker**:
  - 5 consecutive failures → stop trading
  - Max daily loss: 5% of portfolio → halt
  - Max daily trades: 10 → halt

- [ ] **Data Validation**:
  - OHLCV sanity checks (outlier detection)
  - Gap detection and handling
  - Duplicate prevention

- [ ] **Error Recovery**:
  - Automatic retry with exponential backoff
  - Fallback to safe mode (read-only)
  - Alert escalation (email/SMS)

### 9.3 Manual Override
- [ ] Emergency stop button (kill switch)
- [ ] Manual order placement (bypass automation)
- [ ] Risk level adjustment (mid-session)
- [ ] Blacklist addition (immediate exclusion)
- [ ] Portfolio rebalancing override

---

## 10. Monitoring & Alerts

### 10.1 Critical Alerts (Immediate Action)
- [ ] Trading error (order rejection)
- [ ] API failure (authentication, rate limit)
- [ ] Portfolio sync mismatch (>5%)
- [ ] Stop loss triggered
- [ ] System error (crash, memory leak)

### 10.2 Warning Alerts (Review Required)
- [ ] Market hours violation attempt
- [ ] Approaching position limits (>90%)
- [ ] Approaching sector limits (>90%)
- [ ] Low cash reserve (<10%)
- [ ] High error rate (>5% in 1 hour)

### 10.3 Info Alerts (FYI)
- [ ] Daily summary report
- [ ] New BUY signal (watchlist stock)
- [ ] Profit target reached
- [ ] Weekly performance report
- [ ] System health check (daily)

---

## 11. Future Enhancements (Post-MVP)

### 11.1 Phase 2 Features
- [ ] Web dashboard (Flask/Django)
- [ ] Mobile app (React Native)
- [ ] Advanced chart analysis (TradingView integration)
- [ ] Social trading (copy trading, leaderboard)
- [ ] Multi-account support (family members)

### 11.2 Phase 3 Features
- [ ] Options trading integration
- [ ] Futures trading (KOSPI 200)
- [ ] Global stock support (US, Japan)
- [ ] Cryptocurrency integration (reuse Makenaide modules)
- [ ] Robo-advisor mode (fully automated)

### 11.3 Advanced Analytics
- [ ] Machine learning pattern recognition
- [ ] Sentiment analysis (news, social media)
- [ ] Alternative data integration (satellite, credit card)
- [ ] Factor model portfolio construction
- [ ] Multi-timeframe analysis (intraday + daily + weekly)

---

## 12. Appendix

### 12.1 Glossary
- **Stage 2**: Weinstein uptrend stage (breakout and advance)
- **VCP**: Volatility Contraction Pattern (Mark Minervini)
- **Kelly Formula**: Position sizing formula based on win rate and payoff ratio
- **ATR**: Average True Range (volatility indicator)
- **Tick Size**: Minimum price increment for order placement
- **GICS**: Global Industry Classification Standard (11 sectors)

### 12.2 References
- **Weinstein's Stage Analysis**: "Secrets For Profiting in Bull and Bear Markets"
- **Mark Minervini**: "Trade Like a Stock Market Wizard"
- **Kelly Formula**: "A New Interpretation of Information Rate" (1956)
- **KIS API Documentation**: https://apiportal.koreainvestment.com
- **Makenaide Architecture**: `~/makenaide/makenaide_architecture.mmd`

### 12.3 Contact & Support
- **Project Owner**: 13ruce
- **Development Start**: 2025-10-01
- **Target MVP Date**: 2025-11-26 (8 weeks)
- **Repository**: ~/spock/

---

**Document Version**: 1.0
**Last Updated**: 2025-10-01
**Status**: Initial Design - Ready for Development

